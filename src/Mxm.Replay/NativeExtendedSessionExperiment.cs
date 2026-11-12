using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class NativeExtendedSessionExperiment
{
    private static readonly JsonSerializerOptions Wire = new() { NumberHandling = JsonNumberHandling.AllowReadingFromString };
    private static readonly string[] Targets = { "NAS100", "LTCUSD", "BTCEUR", "ETHEUR" };
    private const long Minute = 60000;
    private const long Day = 1440 * Minute;
    private sealed record Payoff(decimal Gross, decimal Central, decimal Adverse, decimal Notional);
    private sealed record Sample(long At, string Week, Payoff Rule, Payoff Momentum, Payoff Long, Payoff Short, decimal Margin);

    internal static int Run(string input, string output, bool contracts)
    {
        try
        {
            byte[] bytes = File.ReadAllBytes(input);
            if (contracts)
            {
                var terms = JsonSerializer.Deserialize<NativeObservedContractTerms[]>(bytes, Wire)
                    ?? throw new ArgumentException("Missing terms");
                if (terms.Count(t => t.Symbol == "EURUSD") != 1 ||
                    terms.Any(t => t.Symbol != "EURUSD" && !Targets.Contains(t.Symbol)))
                    throw new ArgumentException("Unexpected contract");
                foreach (var term in terms)
                    NativeBrokerContractCosts.Validate(term, term.MinimumUnits);
                File.WriteAllText(output, "{}");
                return 0;
            }

            var source = JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes, Wire);
            if (source?.SourceLabel != "ORIGINAL_PEPPERSTONE_ESD1")
                throw new ArgumentException("Unexpected source");
            var receipt = Targets.ToDictionary(symbol => symbol, symbol => Evaluate(source, symbol));
            File.WriteAllText(output, JsonSerializer.Serialize(new {
                Study = "ESD1", SourceSha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                Receipt = receipt, PortfolioExecuted = false, PortfolioAdmission = false,
                HistoricalTariffsCertified = false, ContinuousDrawdownMeasured = false
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("ESD1_NATIVE_REPLAY_REJECTED:" + error.GetType().Name);
            return 67;
        }
    }

    private static long At(int month, int day) =>
        new DateTimeOffset(2026, month, day, 0, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();

    private static object Evaluate(NativeOriginalOpenApiTape tape, string symbol)
    {
        var bars = tape.Bars.SingleOrDefault(x => x.Symbol == symbol)?.M5;
        if (bars is null) return new { Verdict = "CONTRACT_UNAVAILABLE" };
        var history = bars.ToDictionary(x => x.OpenAt);
        var quotes = tape.Marks.Where(x => x.Symbol == symbol).ToDictionary(x => x.At);
        var samples = new List<Sample>();
        var rejected = new Dictionary<string,int>();
        var weekly = new Dictionary<string,int[]>();
        void Reject(string reason) => rejected[reason] = rejected.GetValueOrDefault(reason) + 1;
        bool cryptoWeekend = symbol is "BTCEUR" or "ETHEUR";
        int[] hours = cryptoWeekend ? new[] { 8, 16 } : new[] { 7, 13 };
        int barsRequired = cryptoWeekend ? 6 : 12;
        for (long day = At(7, 20); day < At(11, 9); day += Day)
        {
            var date = DateTimeOffset.FromUnixTimeMilliseconds(day).UtcDateTime;
            bool weekend = date.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday;
            if (weekend != cryptoWeekend) continue;
            string week = $"{ISOWeek.GetYear(date)}-W{ISOWeek.GetWeekOfYear(date):00}";
            if (!weekly.TryGetValue(week, out var count)) weekly.Add(week, count = new int[4]);
            foreach (int hour in hours)
            {
                count[0]++;
                long clock = day + hour * 60 * Minute;
                var prefix = Enumerable.Range(0, barsRequired)
                    .Select(i => history.GetValueOrDefault(clock - (barsRequired - i) * 5 * Minute)).ToArray();
                if (prefix.Any(x => x is null || x.CloseAt != x.OpenAt + 5 * Minute || x.CloseAt > clock))
                {
                    Reject("MISSING_COMPLETED_BARS");
                    continue;
                }
                count[1]++;
                int momentum = Math.Sign(prefix[^1]!.Close - prefix[0]!.Open);
                int side = Signal(symbol, prefix!);
                if (side == 0) continue;
                count[2]++;
                long entryAt = clock + 1500;
                long exitAt = entryAt + (cryptoWeekend ? 30 : 60) * Minute;
                if (!quotes.TryGetValue(entryAt, out var entry) || !quotes.TryGetValue(exitAt, out var exit))
                {
                    Reject("MISSING_PAIRED_MARK_OR_CONVERSION");
                    continue;
                }
                var buy = Value(entry, exit, 1);
                var sell = Value(entry, exit, -1);
                if (buy is null || sell is null)
                {
                    Reject("FINANCING_UNAVAILABLE");
                    continue;
                }
                var cash = new Payoff(0, 0, 0, buy.Notional);
                count[3]++;
                samples.Add(new(entryAt, week, side > 0 ? buy : sell,
                    momentum > 0 ? buy : momentum < 0 ? sell : cash, buy, sell, entry.MarginRequirementEur));
            }
        }

        var early = samples.Where(x => x.At < At(9, 14)).ToArray();
        var late = samples.Where(x => x.At >= At(9, 14)).ToArray();
        var earlyOwn = Bound(early, x => x.Rule.Adverse);
        var earlyIncrement = Bound(early, x => x.Rule.Adverse - x.Momentum.Adverse);
        var lateOwn = Bound(late, x => x.Rule.Adverse);
        var lateIncrement = Bound(late, x => x.Rule.Adverse - x.Momentum.Adverse);
        string verdict = earlyOwn.Weeks < 6 || lateOwn.Weeks < 6 ? "INSUFFICIENT_PRICED_SIGNAL_WEEKS" :
            earlyOwn.Mean <= 0 || earlyIncrement.Mean <= 0 || lateOwn.Lower <= 0 || lateIncrement.Lower <= 0
                ? "NO_REPEATABLE_ADVERSE_EDGE" : "WARRANTS_FUNDED_REPLAY";
        object Segment(Sample[] rows) => new {
            Rule = Distribution(rows.Select(x => x.Rule).ToArray()),
            Momentum = Distribution(rows.Select(x => x.Momentum).ToArray()),
            Long = Distribution(rows.Select(x => x.Long).ToArray()),
            Short = Distribution(rows.Select(x => x.Short).ToArray()),
            CashEur = 0, MaximumMinimumMarginEur = rows.Select(x => (decimal?)x.Margin).Max()
        };
        return new {
            Verdict = verdict, HistoricalBars = bars.Length, PairedMarks = quotes.Count,
            Weekly = weekly.ToDictionary(x => x.Key, x => new {
                ExpectedClocks = x.Value[0], BarComplete = x.Value[1], Signals = x.Value[2], Priced = x.Value[3]
            }),
            Rejected = rejected, Early = Segment(early), Late = Segment(late),
            EarlyOwn = earlyOwn, EarlyIncrement = earlyIncrement, LateOwn = lateOwn, LateIncrement = lateIncrement
        };
    }

    private static int Signal(string symbol, IReadOnlyList<NativeClosedMarketBar> bars)
    {
        var latest = bars[^1];
        if (symbol == "NAS100")
        {
            decimal impulse = bars[^4].Close - bars[0].Open;
            decimal retracement = latest.Close - bars[^3].Open;
            if (Math.Sign(impulse) == -Math.Sign(retracement) &&
                Math.Abs(retracement) * 2 <= Math.Abs(impulse))
                return -Math.Sign(impulse);
            return 0;
        }
        if (symbol == "LTCUSD")
        {
            var prior = bars.Take(9);
            if (bars.Skip(9).Sum(x => x.TickVolume) <= bars.Skip(6).Take(3).Sum(x => x.TickVolume))
                return 0;
            if (latest.Close > prior.Max(x => x.High)) return 1;
            if (latest.Close < prior.Min(x => x.Low)) return -1;
            return 0;
        }

        var range = bars.Take(5);
        decimal low = range.Min(x => x.Low);
        decimal high = range.Max(x => x.High);
        decimal midpoint = (low + high) / 2;
        if (latest.Close <= low || latest.Close >= high) return 0;
        if (latest.Low < low && latest.High <= high && latest.Close < midpoint) return 1;
        if (latest.High > high && latest.Low >= low && latest.Close > midpoint) return -1;
        return 0;
    }

    private static Payoff? Value(NativeOriginalOpenApiMarketMark a, NativeOriginalOpenApiMarketMark b, int side)
    {
        var terms = a.Contract;
        decimal units = terms.MinimumUnits;
        NativeMarketCostContext Context(NativeOriginalOpenApiMarketMark m) => new(
            m.At, m.Bid, m.Ask, m.QuoteCreditToEur, m.QuoteDebitToEur, m.UsdToEur,
            m.MinimumFeeAssetToEur, m.MarginRequirementEur, units, m.SlippagePerSideQuote);
        var entry = NativeBrokerContractCosts.Quote(terms, Context(a), executionIsBuy: side > 0);
        var exit = NativeBrokerContractCosts.Quote(terms, Context(b), a.At, side, executionIsBuy: side < 0);
        if (exit.FinancingSignedEur is not decimal financing) return null;
        decimal midA = (a.Ask + a.Bid) / 2, midB = (b.Ask + b.Bid) / 2;
        decimal move = side * (midB - midA);
        decimal friction = (a.Ask - a.Bid + b.Ask - b.Bid) / 2 +
            a.SlippagePerSideQuote + b.SlippagePerSideQuote;
        decimal central = move - friction, adverse = move - 2 * friction;
        decimal fee = entry.OneSideCommissionEur + exit.OneSideCommissionEur;
        decimal fxStress = terms.QuoteAsset == "EUR" ? 0m : .001m;
        return new(move * units * (b.QuoteCreditToEur + b.QuoteDebitToEur) / 2,
            central * units * (central >= 0 ? exit.Quote.EurCredit : exit.Quote.EurDebit) - fee + financing,
            adverse * units * (adverse >= 0 ? exit.Quote.EurCredit * (1 - fxStress) :
                exit.Quote.EurDebit * (1 + fxStress)) - 2 * fee + 2 * Math.Min(0, financing),
            midA * units * (a.QuoteCreditToEur + a.QuoteDebitToEur) / 2);
    }

    private sealed record WeeklyBound(int Weeks, decimal? Mean, decimal? Lower);
    private static WeeklyBound Bound(Sample[] rows, Func<Sample,decimal> field)
    {
        var weeks = rows.GroupBy(x => x.Week).OrderBy(g => g.Key).Select(g => g.Average(field)).ToArray();
        if (weeks.Length < 2) return new(weeks.Length, null, null);
        decimal mean = weeks.Average();
        var deviations = weeks.Select(x => x - mean).ToArray();
        decimal variance = deviations.Sum(x => x * x);
        decimal lag = variance == 0 ? 0 : deviations.Zip(deviations.Skip(1)).Sum(p => p.First * p.Second) / variance;
        decimal effective = weeks.Length / (1 + 2 * Math.Max(0, lag));
        return new(weeks.Length, mean, mean - 3 * (decimal)Math.Sqrt((double)(variance / ((weeks.Length - 1) * effective))));
    }

    private static object? Distribution(Payoff[] rows)
    {
        if (rows.Length == 0) return null;
        var net = rows.Select(x => 10000 * x.Adverse / x.Notional).Order().ToArray();
        decimal Quantile(decimal p) => net[(int)((net.Length - 1) * p)];
        return new {
            Count = rows.Length, GrossDirectionalWins = rows.Count(x => x.Gross > 0),
            AdverseWins = rows.Count(x => x.Adverse > 0),
            GrossEur = rows.Sum(x => x.Gross), CentralNetEur = rows.Sum(x => x.Central),
            AdverseNetEur = rows.Sum(x => x.Adverse), AdverseMedianBps = Quantile(.5m),
            AdverseP10Bps = Quantile(.1m), AdverseP90Bps = Quantile(.9m),
            MeanAdverseFrictionBps = rows.Average(x => 10000 * (x.Gross - x.Adverse) / x.Notional)
        };
    }
}
