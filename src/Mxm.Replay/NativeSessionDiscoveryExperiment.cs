using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class NativeSessionDiscoveryExperiment
{
    private static readonly string[] Targets = { "GBPUSD", "NatGas" };
    private static readonly JsonSerializerOptions Wire = new() { NumberHandling = JsonNumberHandling.AllowReadingFromString };
    private static readonly long Evaluation = new DateTimeOffset(2025,11,3,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    private const long Hour = 3600000L, Day = 24 * Hour;
    private sealed record Payoff(decimal Gross, decimal Central, decimal Adverse, decimal Notional, decimal Margin);
    private sealed record Pair(long At, string Week, bool Confirmed, Payoff Selected, Payoff Opposite, Payoff Long, Payoff Short);

    internal static int Run(string input, string output, bool contracts)
    {
        try
        {
            byte[] bytes = File.ReadAllBytes(input);
            if (contracts)
            {
                var terms = JsonSerializer.Deserialize<NativeObservedContractTerms[]>(bytes,Wire);
                if (terms is null || !terms.Select(x => x.Symbol).OrderBy(x => x, StringComparer.Ordinal)
                    .SequenceEqual(new[] {"EURUSD","GBPUSD","NatGas"}))
                    throw new ArgumentException("FSD1_CONTRACT_SET");
                foreach (var term in terms) NativeBrokerContractCosts.Validate(term,term.MinimumUnits);
                File.WriteAllText(output,"{}");
                return 0;
            }

            var source = JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes,Wire);
            if (source?.SourceLabel != "ORIGINAL_PEPPERSTONE_FSD1")
                throw new ArgumentException("FSD1_SOURCE_LABEL");
            var tape = NativeOriginalOpenApiProductAdapter.Convert(source);
            var outcomes = new Dictionary<string,object>();
            foreach (string symbol in Targets)
            {
                var bars = tape.Bars.Single(x => x.Symbol == symbol).M5.ToDictionary(x => x.OpenAt);
                var marks = tape.Quotes.Where(x => x.Quote.Symbol == symbol).ToDictionary(x => x.At);
                var rows = new List<Pair>();
                var counts = new Dictionary<string,int>();
                void Reject(string cause) => counts[cause] = counts.GetValueOrDefault(cause) + 1;
                long start = new DateTimeOffset(2025,8,11,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
                long end = new DateTimeOffset(2026,11,9,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
                for (long day = start; day < end; day += Day)
                {
                    var date = DateTimeOffset.FromUnixTimeMilliseconds(day);
                    if (date.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday) continue;
                    long at = day + 14 * Hour + 1500;
                    var signal = NativeSessionConfirmation.Observe(symbol, at, bars);
                    if (signal is null) { Reject("MISSING_CAUSAL_BARS_OR_NEUTRAL_DIRECTION"); continue; }
                    if (!marks.TryGetValue(at, out var entry)) { Reject("MISSING_ENTRY_MARK"); continue; }
                    long exitAt = at + 2 * Hour;
                    if (symbol == "NatGas" && signal.Confirmed)
                    {
                        if (!marks.TryGetValue(at + Hour, out var review)) { Reject("MISSING_GAS_REVIEW_MARK"); continue; }
                        if (NativeSessionConfirmation.Invalidated(signal,review.Quote)) exitAt = review.At;
                    }
                    if (!marks.TryGetValue(exitAt, out var exit)) { Reject("MISSING_CHOSEN_EXIT_MARK"); continue; }
                    var buy = Value(entry,exit,1);
                    var sell = Value(entry,exit,-1);
                    if (buy is null || sell is null) { Reject("MISSING_SIGNED_FINANCING"); continue; }
                    string week = ISOWeek.GetYear(date.UtcDateTime)+"-W"+ISOWeek.GetWeekOfYear(date.UtcDateTime).ToString("00");
                    rows.Add(new(at,week,signal.Confirmed,signal.Direction>0?buy:sell,
                        signal.Direction>0?sell:buy,buy,sell));
                }
                var prior = rows.Where(x => x.At < Evaluation).ToArray();
                var outer = rows.Where(x => x.At >= Evaluation).ToArray();
                var confirmed = outer.Where(x => x.Confirmed).ToArray();
                var conditionalTrain = prior.Where(x => x.Confirmed).GroupBy(x => x.Week).ToArray();
                var pooled = prior.GroupBy(x => x.Week).ToArray();
                decimal? Prob(IGrouping<string,Pair>[] groups) => groups.Length < 8 ? null :
                    groups.Average(w => w.Average(x => x.Selected.Adverse > 0 ? 1m : 0m));
                decimal? Brier(decimal? probability) => probability is decimal p && confirmed.Length > 0
                    ? confirmed.GroupBy(x => x.Week).Average(w => w.Average(x => {
                        decimal error = p - (x.Selected.Adverse > 0 ? 1m : 0m);
                        return error * error;
                    })) : null;
                var loss = Brier(Prob(conditionalTrain));
                var baseLoss = Brier(Prob(pooled));
                var own = Bound(confirmed, x => x.Selected.Adverse);
                var incremental = Bound(confirmed, x => x.Selected.Adverse - x.Opposite.Adverse);
                string verdict = own.Weeks < 40 || loss is null || baseLoss is null ? "INSUFFICIENT_COVERAGE" :
                    loss >= baseLoss ? "NO_INCREMENTAL_PROBABILITY_SKILL" : own.Lower <= 0m ?
                    "NO_STANDALONE_ADVERSE_EDGE_ABOVE_ALLOWANCE" : incremental.Lower <= 0m ?
                    "NO_INCREMENTAL_ADVERSE_EDGE_ABOVE_ALLOWANCE" : "VIABILITY_SIGNAL_REQUIRES_FUNDED_REPLAY";
                outcomes.Add(symbol,new {
                    Verdict=verdict,TrainingPairs=prior.Length,TrainingConfirmedWeeks=conditionalTrain.Length,
                    EvaluationPairs=outer.Length,EvaluationConfirmed=confirmed.Length,ConditionalBrier=loss,PooledBrier=baseLoss,
                    ConditionalTrainProbability=Prob(conditionalTrain),PooledTrainProbability=Prob(pooled),
                    Coverage=new { FirstBarUtcMs=bars.Values.Min(x=>x.OpenAt),LastBarUtcMs=bars.Values.Max(x=>x.CloseAt),
                        FirstMarkUtcMs=marks.Keys.Select(x=>(long?)x).Min(),LastMarkUtcMs=marks.Keys.Select(x=>(long?)x).Max(),
                        FirstPricedEvaluationUtcMs=outer.Select(x=>(long?)x.At).FirstOrDefault(),
                        LastPricedEvaluationUtcMs=outer.Select(x=>(long?)x.At).LastOrDefault() },
                    Rejected=counts,OwnAdverseWeekly=own,IncrementalVsOppositeAdverseWeekly=incremental,
                    Weekly=outer.GroupBy(x=>x.Week).ToDictionary(x=>x.Key,x=>new { Priced=x.Count(),Confirmed=x.Count(y=>y.Confirmed) }),
                    Confirmed=Distribution(confirmed.Select(x=>x.Selected).ToArray()),
                    Other=Distribution(outer.Where(x=>!x.Confirmed).Select(x=>x.Selected).ToArray()),
                    MatchedLong=Distribution(confirmed.Select(x=>x.Long).ToArray()),
                    MatchedShort=Distribution(confirmed.Select(x=>x.Short).ToArray())
                });
            }

            decimal jointMargin = tape.Quotes.Where(x=>Targets.Contains(x.Quote.Symbol))
                .GroupBy(x=>x.Quote.Symbol).Sum(g=>g.Max(x=>x.Quote.MarginPerUnit*x.Contract!.MinimumUnits));
            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="FSD1",SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                Receipt=outcomes,EvaluationStartUtcMs=Evaluation,JointMinimumMarginEnvelopeEur=jointMargin,
                CashBenchmarkEur=300,PortfolioExecuted=false,PortfolioAdmission=false,HistoricalTariffsCertified=false
            }));
            return 0;
        }
        catch(Exception error)
        {
            Console.Error.WriteLine("FSD1_NATIVE_REPLAY_REJECTED:"+error.GetType().Name);
            return 67;
        }
    }

    private static Payoff? Value(NativeHistoricalQuoteObservation entry, NativeHistoricalQuoteObservation exit, int side)
    {
        var a = entry.Quote;
        var b = exit.Quote;
        var terms = entry.Contract!;
        decimal units = terms.MinimumUnits;
        decimal midA = (a.Ask+a.Bid)/2m, midB = (b.Ask+b.Bid)/2m;
        decimal buySellCost = (a.Ask-a.Bid+b.Ask-b.Bid)/2m + entry.SlippagePerSideQuote + exit.SlippagePerSideQuote;
        decimal movement = side*(midB-midA);
        decimal fx = (b.EurDebit+b.EurCredit)/2m;
        decimal fee = Math.Max(a.ExitFeeFloor, a.ExitFeePerUnit*units) + Math.Max(b.ExitFeeFloor,b.ExitFeePerUnit*units);
        decimal? financing = NativeBrokerContractCosts.SignedFinancing(terms,entry.At,exit.At,side,units,b.EurCredit,b.EurDebit);
        if (financing is null) return null;
        decimal gross = movement*units*fx;
        decimal central = movement-buySellCost;
        decimal adverse = movement-2m*buySellCost;
        return new(gross,central*units*(central>=0m?b.EurCredit:b.EurDebit)-fee+financing.Value,
            adverse*units*(adverse>=0m?b.EurCredit*.999m:b.EurDebit*1.001m)-2m*fee+2m*Math.Min(0m,financing.Value),
            midA*units*(a.EurDebit+a.EurCredit)/2m,a.MarginPerUnit*units);
    }

    private sealed record WeeklyBound(int Weeks, decimal? EffectiveWeeks, decimal? Mean, decimal? Lower);
    private static WeeklyBound Bound(Pair[] pairs, Func<Pair,decimal> value)
    {
        var values = pairs.GroupBy(x=>x.Week).OrderBy(x=>x.Key,StringComparer.Ordinal).Select(g=>g.Average(value)).ToArray();
        if (values.Length < 2) return new(values.Length,null,null,null);
        decimal mean = values.Average();
        var dev = values.Select(x=>x-mean).ToArray();
        decimal variation = dev.Sum(x=>x*x);
        decimal lag = variation==0 ? 0 : dev.Zip(dev.Skip(1)).Sum(p=>p.First*p.Second)/variation;
        decimal effective = dev.Length/(1m+2m*Math.Max(0m,lag));
        decimal allowance = 3m*(decimal)Math.Sqrt((double)(variation/((dev.Length-1)*effective)));
        return new(values.Length,effective,mean,mean-allowance);
    }

    private static object? Distribution(Payoff[] rows)
    {
        if (rows.Length == 0) return null;
        var ordered = rows.Select(x=>10000m*x.Adverse/x.Notional).OrderBy(x=>x).ToArray();
        decimal Q(decimal fraction) => ordered[(int)Math.Floor((ordered.Length-1)*fraction)];
        return new { Pairs=rows.Length,Wins=rows.Count(x=>x.Adverse>0),Losses=rows.Count(x=>x.Adverse<0),
            MeanGrossBps=rows.Average(x=>10000m*x.Gross/x.Notional),
            MeanCentralNetBps=rows.Average(x=>10000m*x.Central/x.Notional),
            MeanAdverseNetBps=ordered.Average(),AdverseP10Bps=Q(.1m),AdverseMedianBps=Q(.5m),AdverseP90Bps=Q(.9m),
            GrossEur=rows.Sum(x=>x.Gross),CentralNetEur=rows.Sum(x=>x.Central),AdverseNetEur=rows.Sum(x=>x.Adverse),
            MeanAdverseFrictionBps=rows.Average(x=>10000m*(x.Gross-x.Adverse)/x.Notional),
            MinimumVolumeMaximumMarginEur=rows.Max(x=>x.Margin) };
    }
}
