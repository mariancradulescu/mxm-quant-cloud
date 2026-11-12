using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class NativeSessionEconomicsMap
{
    private static readonly string[] Targets = { "EURUSD", "NAS100", "XAUUSD", "SpotBrent", "XAGEUR", "ETHEUR" };
    private static readonly string[] FilterTargets = { "NAS100", "XAGEUR", "ETHEUR" };
    private static readonly int[] Horizons = { 30, 90 };
    private static readonly JsonSerializerOptions Wire = new() { NumberHandling = JsonNumberHandling.AllowReadingFromString };
    private const long Minute = 60000;
    private const long M5 = 5 * Minute;
    private static readonly DateTimeOffset Start = new(2026, 8, 17, 0, 0, 0, TimeSpan.Zero);

    internal sealed record Schedule(string? TimeZone, int[][] Intervals);
    private sealed record Tape(string SourceLabel, NativeHistoricalBars[] Bars, NativeOriginalOpenApiMarketMark[] Marks,
        Dictionary<string, Schedule> Schedules, Dictionary<string, long[]> RawPairClocks);
    private sealed record Payoff(decimal Gross, decimal Central, decimal Adverse, decimal Notional, decimal AdverseFrictionBps);
    private sealed record Row(int Week, bool Weekend, int Hour, long Entry, bool ContractOpen,
        bool RawQuotes, bool EntryQuote, decimal? SpreadBps, Payoff? Buy, Payoff? Sell, int? Signal, int Momentum);
    private sealed record Bounds(int Weeks, decimal? Mean, decimal? Lower);

    internal static int Run(string input, string output, bool contracts, bool filterDiagnostic = false)
    {
        try
        {
            byte[] bytes = File.ReadAllBytes(input);
            if (contracts)
            {
                var terms = JsonSerializer.Deserialize<NativeObservedContractTerms[]>(bytes, Wire)
                    ?? throw new ArgumentException("Missing terms");
                if (terms.Count(t => t.Symbol == "EURUSD") != 1 || terms.Any(t => !Targets.Contains(t.Symbol)))
                    throw new ArgumentException("Unexpected terms");
                foreach (var term in terms) NativeBrokerContractCosts.Validate(term, term.MinimumUnits);
                File.WriteAllText(output, "{}");
                return 0;
            }

            var tape = JsonSerializer.Deserialize<Tape>(bytes, Wire);
            if (tape?.SourceLabel != "ORIGINAL_PEPPERSTONE_SEM1")
                throw new ArgumentException("Unexpected source");
            var bars = tape.Bars.ToDictionary(b => b.Symbol, b => b.M5.ToDictionary(x => x.OpenAt));
            var marks = tape.Marks.GroupBy(m => m.Symbol).ToDictionary(g => g.Key, g => g.ToDictionary(x => x.At));
            var results = new Dictionary<string, object>();
            var active = new List<(string Symbol, int Horizon, long At)>();
            foreach (string symbol in filterDiagnostic ? FilterTargets : Targets)
            {
                if (!bars.ContainsKey(symbol))
                {
                    results.Add(symbol, new { Verdict = "CONTRACT_OR_BAR_SOURCE_UNAVAILABLE" });
                    continue;
                }

                var schedule = tape.Schedules.GetValueOrDefault(symbol);
                var zone = Zone(schedule?.TimeZone);
                var quotes = marks.GetValueOrDefault(symbol) ?? new();
                var raw = (tape.RawPairClocks.GetValueOrDefault(symbol) ?? Array.Empty<long>()).ToHashSet();
                var routes = new Dictionary<int, object>();
                foreach (int horizon in Horizons)
                {
                    var rows = new List<Row>();
                    for (int week = 0; week < 10; week++)
                    {
                        var day = Start.AddDays(7 * week + week % 5);
                        Observe(day, week, false);
                        if (symbol == "ETHEUR") Observe(Start.AddDays(7 * week + 5 + week % 2), week, true);
                    }

                    void Observe(DateTimeOffset day, int week, bool weekend)
                    {
                        for (int hour = 1; hour < 24; hour += 3)
                        {
                            long clock = day.AddHours(hour).ToUnixTimeMilliseconds();
                            long entry = clock + 1500;
                            long exit = entry + horizon * Minute;
                            bool open = IsOpen(schedule, zone, entry, exit);
                            bool rawPair = raw.Contains(entry) && raw.Contains(exit);
                            quotes.TryGetValue(entry, out var first);
                            quotes.TryGetValue(exit, out var last);
                            decimal? spread = first is null ? null : 20000m * (first.Ask - first.Bid) / (first.Ask + first.Bid);
                            bool pricedEndpoints = open && first is not null && last is not null;
                            Payoff? buy = pricedEndpoints ? Price(first!, last!, 1) : null;
                            Payoff? sell = pricedEndpoints ? Price(first!, last!, -1) : null;
                            var (signal, momentum) = Signal(symbol, bars, clock);
                            if (buy is not null && sell is not null && signal is not (null or 0))
                                active.Add((symbol, horizon, entry));
                            rows.Add(new(week, weekend, hour, entry, open, rawPair, first is not null, spread,
                                buy, sell, signal, momentum));
                        }
                    }

                    bool Complete(Row r) => r.Buy is not null && r.Sell is not null;
                    bool Triggered(Row r) => Complete(r) && r.Signal is not (null or 0);
                    var first = rows.Where(r => r.Week < 5 && Triggered(r)).ToArray();
                    var last = rows.Where(r => r.Week >= 5 && Triggered(r)).ToArray();
                    Payoff Select(Row r) => r.Signal > 0 ? r.Buy! : r.Sell!;
                    Payoff Momentum(Row r) => r.Momentum switch {
                        > 0 => r.Buy!, < 0 => r.Sell!, _ => new(0, 0, 0, r.Buy!.Notional, 0)
                    };
                    if (filterDiagnostic)
                    {
                        routes.Add(horizon, CompareFilter(rows.Where(r => Complete(r) &&
                            r.Signal.HasValue && r.Momentum != 0).ToArray()));
                        continue;
                    }

                    var earlyOwn = Bound(first, r => Select(r).Adverse);
                    var earlyDelta = Bound(first, r => Select(r).Adverse - Momentum(r).Adverse);
                    var lateOwn = Bound(last, r => Select(r).Adverse);
                    var lateDelta = Bound(last, r => Select(r).Adverse - Momentum(r).Adverse);
                    string verdict = earlyOwn.Weeks < 4 || lateOwn.Weeks < 4 ? "INSUFFICIENT_SIGNAL_WEEKS" :
                        earlyOwn.Mean > 0 && earlyDelta.Mean > 0 && lateOwn.Lower > 0 && lateDelta.Lower > 0
                            ? "WARRANTS_FUNDED_REPLAY" : "NO_REPEATABLE_ADVERSE_INCREMENT";
                    object Segment(Row[] rr) => new {
                        Rule = Summary(rr.Select(Select)), Momentum = Summary(rr.Select(Momentum)),
                        Long = Summary(rr.Select(r => r.Buy!)), Short = Summary(rr.Select(r => r.Sell!)), Cash = 0
                    };

                    routes.Add(horizon, new {
                        Verdict = verdict,
                        Early = Segment(first), Late = Segment(last),
                        EarlyOwn = earlyOwn, EarlyDelta = earlyDelta, LateOwn = lateOwn, LateDelta = lateDelta,
                        WeeklyPricedSignals = rows.GroupBy(r => r.Week).ToDictionary(g =>
                            $"{ISOWeek.GetYear(Start.AddDays(g.Key * 7).UtcDateTime)}-W{ISOWeek.GetWeekOfYear(Start.AddDays(g.Key * 7).UtcDateTime):00}",
                            g => g.Count(Triggered)),
                        Sessions = rows.GroupBy(r => (r.Weekend, r.Hour)).Select(g => {
                            var priced = g.Where(Complete).ToArray();
                            var signals = priced.Where(Triggered).ToArray();
                            var spreads = g.Where(r => r.SpreadBps.HasValue).Select(r => r.SpreadBps!.Value);
                            return new {
                                g.Key.Weekend, EntryHourUtc = g.Key.Hour, Clocks = g.Count(),
                                ContractOpen = g.Count(r => r.ContractOpen), HistoricalQuotePairs = g.Count(r => r.RawQuotes),
                                EntryMarksAfterConversion = g.Count(r => r.EntryQuote), CostComplete = priced.Length,
                                FeatureComplete = g.Count(r => r.Signal.HasValue), PricedSignals = signals.Length,
                                MedianEntrySpreadBps = Quantile(spreads, .5m), P90EntrySpreadBps = Quantile(spreads, .9m),
                                MedianAbsoluteTerminalMoveBps = Quantile(priced.Select(r => 10000m * Math.Abs(r.Buy!.Gross) / r.Buy.Notional), .5m),
                                MedianAdverseCostBps = Quantile(priced.Select(r => (r.Buy!.AdverseFrictionBps + r.Sell!.AdverseFrictionBps) / 2), .5m),
                                TerminalMoveCouldCoverAdverseCost = priced.Count(r => Math.Max(r.Buy!.Adverse, r.Sell!.Adverse) > 0),
                                Rule = Summary(signals.Select(Select)), Momentum = Summary(signals.Select(Momentum))
                            };
                        }).ToArray()
                    });
                }
                results.Add(symbol, routes);
            }
            File.WriteAllText(output, JsonSerializer.Serialize(new {
                Study = filterDiagnostic ? "SEM1_FILTER_DIAGNOSTIC" : "SEM1", Receipt = results, SourceSha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                EntryClocksWithConcurrentSymbols = active.GroupBy(r => r.At).Count(g => g.Select(r => r.Symbol).Distinct().Count() > 1),
                PortfolioExecuted = false, PortfolioAdmission = false, ContinuousDrawdownMeasured = false
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("SEM1_NATIVE_REPLAY_REJECTED:" + error.GetType().Name);
            return 67;
        }
    }

    private static object CompareFilter(Row[] eligible)
    {
        Payoff OwnMomentum(Row r) => r.Momentum > 0 ? r.Buy! : r.Sell!;
        decimal Bps(Row r) => 10000m * OwnMomentum(r).Adverse / OwnMomentum(r).Notional;
        object Half(Row[] rows)
        {
            var controls = rows.Where(r => r.Signal == 0)
                .GroupBy(r => (r.Weekend, r.Hour, r.Momentum))
                .ToDictionary(g => g.Key, g => g.Average(Bps));
            var selected = rows.Where(r => r.Signal == r.Momentum).ToArray();
            var matched = selected.Where(r => controls.ContainsKey((r.Weekend, r.Hour, r.Momentum))).ToArray();
            return new {
                Selected = selected.Length, Matched = matched.Length, AvailableUnselectedControls = rows.Length - selected.Length,
                Own = Bound(matched, Bps),
                Incremental = Bound(matched, r => Bps(r) - controls[(r.Weekend, r.Hour, r.Momentum)]),
                MatchedSelectedEconomics = Summary(matched.Select(OwnMomentum))
            };
        }
        return new {
            Early = Half(eligible.Where(r => r.Week < 5).ToArray()),
            Late = Half(eligible.Where(r => r.Week >= 5).ToArray())
        };
    }

    internal static TimeZoneInfo? Zone(string? name)
    {
        if (string.IsNullOrWhiteSpace(name)) return null;
        try { return TimeZoneInfo.FindSystemTimeZoneById(name); }
        catch (TimeZoneNotFoundException) { return null; }
        catch (InvalidTimeZoneException) { return null; }
    }

    internal static bool IsOpen(Schedule? schedule, TimeZoneInfo? zone, long start, long end)
    {
        if (schedule is null || zone is null) return false;
        int WeekSecond(long at)
        {
            var local = TimeZoneInfo.ConvertTime(DateTimeOffset.FromUnixTimeMilliseconds(at), zone);
            return (int)local.DayOfWeek * 86400 + (int)local.TimeOfDay.TotalSeconds;
        }
        int from = WeekSecond(start), until = WeekSecond(end);
        return schedule.Intervals.Any(interval => interval[0] <= from && from <= until && until < interval[1]);
    }

    internal static (int? Signal, int Momentum) Signal(string name,
        Dictionary<string, Dictionary<long, NativeClosedMarketBar>> bars, long clock)
    {
        NativeClosedMarketBar[]? Prefix(string symbol, int count)
        {
            if (!bars.TryGetValue(symbol, out var series)) return null;
            var items = new NativeClosedMarketBar[count];
            for (int i = 0; i < count; i++)
            {
                long open = clock - (count - i) * M5;
                if (!series.TryGetValue(open, out var bar) || bar.CloseAt != open + M5 || bar.Open <= 0 || bar.Close <= 0)
                    return null;
                items[i] = bar;
            }
            return items;
        }
        decimal Move(NativeClosedMarketBar[] b, int end, int length) =>
            b[end - 1].Close / b[end - length].Open - 1m;
        int Sign(decimal x) => Math.Sign(x);

        int length = name switch {
            "XAGEUR" => 12, "NAS100" or "XAUUSD" => 24, "SpotBrent" => 36, _ => 48
        };
        var own = Prefix(name, length);
        if (own is null) return (null, 0);
        decimal hour = Move(own, length, 12);
        int momentum = Sign(hour);
        int lastQuarter = Sign(Move(own, length, 3));
        switch (name)
        {
            case "EURUSD":
                int earlierThree = Sign(Move(own, length - 12, 36));
                return (momentum == -earlierThree && Sign(Move(own, 48, 1)) == earlierThree ? earlierThree : 0, momentum);
            case "NAS100":
                decimal priorHour = Move(own, length - 12, 12);
                return (momentum == -Sign(priorHour) && lastQuarter == momentum && Math.Abs(hour) > Math.Abs(priorHour) ? momentum : 0, momentum);
            case "XAUUSD":
                var fx = Prefix("EURUSD", 24);
                if (fx is null) return (null, momentum);
                int gold = Sign(Move(own, length - 12, 12));
                return (gold == Sign(Move(fx, 12, 12)) && lastQuarter == -gold && Sign(Move(fx, 24, 3)) == gold ? gold : 0, momentum);
            case "SpotBrent":
                var index = Prefix("NAS100", 36);
                if (index is null) return (null, momentum);
                int three = Sign(Move(own, length, 36));
                return (three == Sign(Move(index, 36, 36)) && momentum == -three ? three : 0, momentum);
            case "XAGEUR":
                var goldBars = Prefix("XAUUSD", 12);
                var euro = Prefix("EURUSD", 12);
                if (goldBars is null || euro is null) return (null, momentum);
                decimal lead = (1m + Move(goldBars, 12, 12)) / (1m + Move(euro, 12, 12)) - 1m;
                return (momentum == Sign(lead) && Math.Abs(hour) < Math.Abs(lead) ? momentum : 0, momentum);
            default:
                bool active = own.Skip(45).Sum(b => b.TickVolume) > own.Skip(42).Take(3).Sum(b => b.TickVolume);
                return (active && Sign(Move(own, length - 12, 36)) == momentum && lastQuarter == momentum ? momentum : 0, momentum);
        }
    }

    private static Payoff? Price(NativeOriginalOpenApiMarketMark a, NativeOriginalOpenApiMarketMark b, int side)
    {
        var terms = a.Contract;
        decimal units = terms.MinimumUnits;
        NativeMarketCostContext Context(NativeOriginalOpenApiMarketMark m) => new(
            m.At, m.Bid, m.Ask, m.QuoteCreditToEur, m.QuoteDebitToEur, m.UsdToEur,
            m.MinimumFeeAssetToEur, m.MarginRequirementEur, units, m.SlippagePerSideQuote);
        var enter = NativeBrokerContractCosts.Quote(terms, Context(a), executionIsBuy: side > 0);
        var exit = NativeBrokerContractCosts.Quote(terms, Context(b), a.At, side, executionIsBuy: side < 0);
        if (exit.FinancingSignedEur is not decimal funding) return null;
        decimal entryMid = (a.Ask + a.Bid) / 2m;
        decimal motion = side * ((b.Ask + b.Bid) / 2m - entryMid);
        decimal cost = (a.Ask - a.Bid + b.Ask - b.Bid) / 2m + a.SlippagePerSideQuote + b.SlippagePerSideQuote;
        decimal fees = enter.OneSideCommissionEur + exit.OneSideCommissionEur;
        decimal stress = terms.QuoteAsset == "EUR" ? 0m : .001m;
        decimal gross = motion * units * (b.QuoteCreditToEur + b.QuoteDebitToEur) / 2m;
        decimal centralMove = motion - cost, adverseMove = motion - 2m * cost;
        decimal central = centralMove * units * (centralMove >= 0 ? exit.Quote.EurCredit : exit.Quote.EurDebit) - fees + funding;
        decimal adverseDebit = exit.Quote.EurDebit * (1m + stress);
        decimal adverse = adverseMove * units * (adverseMove >= 0 ? exit.Quote.EurCredit * (1m - stress) : adverseDebit)
            - 2m * fees + 2m * Math.Min(0m, funding);
        decimal notional = entryMid * units * (a.QuoteCreditToEur + a.QuoteDebitToEur) / 2m;
        decimal zeroMoveCost = 2m * cost * units * adverseDebit + 2m * fees - 2m * Math.Min(0m, funding);
        return new(gross, central, adverse, notional, 10000m * zeroMoveCost / notional);
    }

    private static Bounds Bound(Row[] rows, Func<Row, decimal> score)
    {
        var weeks = rows.GroupBy(r => r.Week).OrderBy(g => g.Key).Select(g => (g.Key, Value: g.Average(score))).ToArray();
        if (weeks.Length < 2) return new(weeks.Length, weeks.Length == 0 ? null : weeks[0].Value, null);
        decimal mean = weeks.Average(w => w.Value);
        decimal variance = weeks.Sum(w => (w.Value - mean) * (w.Value - mean));
        decimal cross = weeks.Zip(weeks.Skip(1)).Where(w => w.Second.Key == w.First.Key + 1)
            .Sum(w => (w.First.Value - mean) * (w.Second.Value - mean));
        decimal lag = variance == 0m ? 0m : Math.Max(0m, cross / variance);
        decimal allowance = 3m * (decimal)Math.Sqrt((double)(variance * (1m + 2m * lag) / ((weeks.Length - 1) * weeks.Length)));
        return new(weeks.Length, mean, mean - allowance);
    }

    private static decimal? Quantile(IEnumerable<decimal> values, decimal q)
    {
        var ordered = values.Order().ToArray();
        return ordered.Length == 0 ? null : ordered[(int)((ordered.Length - 1) * q)];
    }

    private static object Summary(IEnumerable<Payoff> values)
    {
        var rows = values.ToArray();
        return new {
            Count = rows.Length, DirectionWins = rows.Count(r => r.Gross > 0),
            GrossEur = rows.Sum(r => r.Gross), CentralNetEur = rows.Sum(r => r.Central), AdverseNetEur = rows.Sum(r => r.Adverse),
            AdverseWins = rows.Count(r => r.Adverse > 0), MedianAdverseBps = Quantile(rows.Select(r => 10000m * r.Adverse / r.Notional), .5m)
        };
    }
}
