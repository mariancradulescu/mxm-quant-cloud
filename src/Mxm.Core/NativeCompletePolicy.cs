using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeQuoteResidence(decimal Mean, decimal LateChange, decimal MidDisplacement);
public sealed record NativeCompleteSample(string Symbol, long DecisionAt, long SettledAt, decimal[] Features, decimal OutcomeR)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? AssetClass { get; init; }
}
public sealed record NativeCompletePrediction(decimal Mean, decimal Lower, decimal PositiveProbability,
    decimal P10, decimal P50, decimal P90, int Observations, int Days);
public sealed record NativeCompleteHold(long ObservedAt, long BarCloseAt, decimal[] Features, decimal ScaleEur,
    decimal? EstimatedContinueEur, bool CloseRequested);
public sealed record NativeCompleteEntry(decimal[] Features, decimal ScaleEur,
    NativeCompletePrediction? Prediction, NativeCompleteHold? Hold = null);
public sealed record NativeCompleteProbe(string Symbol, int Side, long At, bool CloseAtHoldCheckpoint = false);

public sealed record NativeCompleteDistribution(NativeCompleteSample[] Samples, bool WithoutResidence,
    decimal BiasR = 0m, decimal UncertaintyR = 0m)
{
    // Opt-in only: values and presence flags are interleaved. Legacy FPE/PAV/SCP
    // distributions keep their original feature distance and serialization.
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool MaskedEconomicContext { get; init; }

    // Experimental exact selector; baseline remains the default until measured parity is certified.
    static readonly bool BoundedNeighbors=Environment.GetEnvironmentVariable("MXM_ECONOMIC_BOUNDED_NEIGHBORS")=="1";

    internal static IEnumerable<(NativeCompleteSample sample,decimal distance,int index)> SelectBoundedNeighbors(
        IEnumerable<(NativeCompleteSample sample,decimal distance,int index)> candidates)
    {
        var order=Comparer<(NativeCompleteSample sample,decimal distance,int index)>.Create((a,b)=>
        {
            int c=a.distance.CompareTo(b.distance);
            if(c==0)c=a.sample.DecisionAt.CompareTo(b.sample.DecisionAt);
            if(c==0)c=StringComparer.Ordinal.Compare(a.sample.Symbol,b.sample.Symbol);
            return c==0?a.index.CompareTo(b.index):c;
        });
        var worstFirst=Comparer<(NativeCompleteSample sample,decimal distance,int index)>.Create((a,b)=>order.Compare(b,a));
        var byDay=new Dictionary<long,PriorityQueue<(NativeCompleteSample sample,decimal distance,int index),
            (NativeCompleteSample sample,decimal distance,int index)>>();
        void Keep(PriorityQueue<(NativeCompleteSample sample,decimal distance,int index),
            (NativeCompleteSample sample,decimal distance,int index)> heap,
            (NativeCompleteSample sample,decimal distance,int index) row,int limit)
        {
            if(heap.Count<limit)heap.Enqueue(row,row);
            else if(order.Compare(row,heap.Peek())<0)
            {
                heap.Dequeue();
                heap.Enqueue(row,row);
            }
        }
        foreach(var row in candidates)
        {
            long day=row.sample.DecisionAt/NativeCompletePolicy.Day;
            if(!byDay.TryGetValue(day,out var heap))byDay.Add(day,heap=new(worstFirst));
            Keep(heap,row,8);
        }
        // Any row outside its day's first eight cannot enter the original selected set.
        // The global first 48 among the surviving rows exactly match the original scan.
        var global=new PriorityQueue<(NativeCompleteSample sample,decimal distance,int index),
            (NativeCompleteSample sample,decimal distance,int index)>(worstFirst);
        foreach(var heap in byDay.Values)
            foreach(var row in heap.UnorderedItems)Keep(global,row.Element,48);
        return global.UnorderedItems.Select(x=>x.Element).OrderBy(x=>x,order);
    }

    public NativeCompletePrediction? Predict(decimal[] features, long clock, decimal scale)
        =>Predict(features,clock,scale,out _);

    internal NativeCompletePrediction? Predict(decimal[] features,long clock,decimal scale,
        out (decimal Minimum,decimal Maximum) range,string? symbol=null,string? assetClass=null)
    {
        using var predictionProfile=NativeEconomicProfiler.Measure("distribution.predict");
        range=default;
        if (scale <= 0m) throw new ArgumentException("COMPLETE_POLICY_RISK_SCALE");
        var ranked=RankNeighbors(features,clock,symbol,assetClass);
        var days = new Dictionary<long, int>();
        var values = new List<(decimal Return, decimal Weight)>();
        using (NativeEconomicProfiler.Measure("distribution.rank_select"))
        foreach (var (sample, distance, _) in ranked)
        {
            long day = sample.DecisionAt / NativeCompletePolicy.Day;
            int count = days.GetValueOrDefault(day);
            if (count >= 8) continue;
            days[day] = count + 1;
            values.Add(((sample.OutcomeR + BiasR) * scale, 1m / (1m + distance)));
            if (values.Count == 48) break;
        }
        return Summarize(values,days.Count,scale,out range);
    }

    IEnumerable<(NativeCompleteSample sample,decimal distance,int index)> RankNeighbors(decimal[] features,long clock,
        string? symbol,string? assetClass)
    {
        int first = WithoutResidence ? 2 : 0;
        var candidates = Samples.Select((sample,index)=>(sample,index)).Where(row=>row.sample.SettledAt<clock).Select(row =>
        {
            var (sample,index)=row;
            if (sample.Features.Length != features.Length) throw new ArgumentException("COMPLETE_POLICY_FEATURE_COUNT");
            decimal distance = 0m;
            if(MaskedEconomicContext)
            {
                using var distanceProfile=NativeEconomicProfiler.MeasureDistance();
                distance=ContextDistance(features,sample.Features,symbol,sample.Symbol,assetClass,sample.AssetClass);
            }
            else
                for (int i = first; i < features.Length; i++)
                {
                    decimal delta = features[i] - sample.Features[i];
                    distance += delta * delta;
                }
            return (sample, distance, index);
        });
        IEnumerable<(NativeCompleteSample sample,decimal distance,int index)> ranked =
            BoundedNeighbors
                ? DeferredBounded()
                : candidates.OrderBy(v=>v.distance).ThenBy(v=>v.sample.DecisionAt)
                    .ThenBy(v=>v.sample.Symbol,StringComparer.Ordinal);
        IEnumerable<(NativeCompleteSample sample,decimal distance,int index)> DeferredBounded()
        {
            foreach(var row in SelectBoundedNeighbors(candidates))yield return row;
        }
        return ranked;
    }

    // Caller holds a validated, common ordered sample geometry. Only outcome and
    // calibration differ; distance, causal eligibility, daily cap and tie order are common.
    internal (NativeCompletePrediction? Gross,NativeCompletePrediction? Net) PredictPaired(
        NativeCompleteDistribution net,decimal[] features,long clock,decimal scale,
        out (decimal Minimum,decimal Maximum) range,string? symbol,string? assetClass)
    {
        using var predictionProfile=NativeEconomicProfiler.Measure("distribution.predict_pair");
        if(scale<=0m)throw new ArgumentException("COMPLETE_POLICY_RISK_SCALE");
        var days=new Dictionary<long,int>();
        var grossValues=new List<(decimal Return,decimal Weight)>();
        var netValues=new List<(decimal Return,decimal Weight)>();
        using (NativeEconomicProfiler.Measure("distribution.rank_select"))
        foreach(var (sample,distance,index) in RankNeighbors(features,clock,symbol,assetClass))
        {
            long day=sample.DecisionAt/NativeCompletePolicy.Day;
            int count=days.GetValueOrDefault(day);
            if(count>=8)continue;
            days[day]=count+1;
            decimal weight=1m/(1m+distance);
            grossValues.Add(((sample.OutcomeR+BiasR)*scale,weight));
            netValues.Add(((net.Samples[index].OutcomeR+net.BiasR)*scale,weight));
            if(grossValues.Count==48)break;
        }
        return (Summarize(grossValues,days.Count,scale,out _),
            net.Summarize(netValues,days.Count,scale,out range));
    }

    NativeCompletePrediction? Summarize(List<(decimal Return,decimal Weight)> values,int dayCount,decimal scale,
        out (decimal Minimum,decimal Maximum) range)
    {
        range=default;
        using var summaryProfile=NativeEconomicProfiler.Measure("distribution.summarize");
        if (values.Count < 12 || dayCount < 4) return null;
        decimal weight = values.Sum(x => x.Weight);
        decimal mean = values.Sum(x => x.Return * x.Weight) / weight;
        var ordered = values.OrderBy(x => x.Return).ToArray();
        range=(ordered[0].Return,ordered[^1].Return);
        decimal Quantile(decimal fraction)
        {
            decimal sum = 0m;
            foreach (var row in ordered)
            {
                sum += row.Weight;
                if (sum >= weight * fraction) return row.Return;
            }
            return ordered[^1].Return;
        }
        return new(mean, mean - UncertaintyR * scale, values.Where(x => x.Return > 0m).Sum(x => x.Weight) / weight,
            Quantile(.10m), Quantile(.50m), Quantile(.90m), values.Count, dayCount);
    }

    internal static decimal ContextDistance(decimal[] target,decimal[] observed,string? symbol=null,
        string? observedSymbol=null,string? assetClass=null,string? observedClass=null)
    {
        if(target.Length!=observed.Length||target.Length%2!=0)
            throw new ArgumentException("COMPLETE_POLICY_MASKED_FEATURE_COUNT");
        decimal sum=0m;
        int available=0;
        for(int i=0;i<target.Length;i+=2)
        {
            bool a=target[i+1]==1m,b=observed[i+1]==1m;
            if(!a&&!b)continue;
            available++;
            if(a!=b){sum+=1m;continue;}
            decimal delta=Math.Clamp((target[i]-observed[i])/2m,-1m,1m);
            sum+=delta*delta;
        }
        // Equal-weight blocks for market state, instrument and official class.
        // Missing context is not the same observation as an actual zero.
        decimal distance=available>0?sum/available:1m;
        if(symbol is not null&&observedSymbol is not null&&symbol!=observedSymbol)distance+=1m;
        if(assetClass is not null&&observedClass is not null&&assetClass!=observedClass)distance+=1m;
        return distance;
    }

    public NativeCompleteDistribution Calibrate(IEnumerable<NativeCompleteSample> observations)
    {
        using var calibrationProfile=NativeEconomicProfiler.Measure("distribution.calibrate");
        var errors = observations.Select(row =>
            (row.DecisionAt, Predicted: Predict(row.Features,row.DecisionAt,1m,out _,row.Symbol,row.AssetClass), row.OutcomeR))
            .Where(row => row.Predicted is not null)
            .GroupBy(row => row.DecisionAt / NativeCompletePolicy.Day)
            .Select(g => g.Average(row => row.OutcomeR - row.Predicted!.Mean)).ToArray();
        return WithCalibrationErrors(errors);
    }

    internal NativeCompleteDistribution WithCalibrationErrors(decimal[] errors)
    {
        if (errors.Length < 4) return this;
        decimal mean = errors.Average();
        decimal sampleVariance = errors.Sum(e => (e - mean) * (e - mean)) / (errors.Length - 1);
        return this with { BiasR = mean, UncertaintyR = (decimal)Math.Sqrt((double)(sampleVariance / errors.Length)) };
    }
}

public sealed record NativeCompleteModels(long AvailableAt, NativeCompleteDistribution? Hold,
    NativeCompleteDistribution? Entry = null, NativeCompleteDistribution? Ablation = null);

public sealed class NativeQuoteResidenceStream
{
    readonly Dictionary<string, Queue<LedgerQuote>> windows = new(StringComparer.Ordinal);

    public Ucp1Frame Observe(Ucp1Frame frame)
    {
        var observed = new Ucp1MarketFrame[frame.Markets.Length];
        for (int i = 0; i < observed.Length; i++)
        {
            var market = frame.Markets[i];
            var last = market.Quote;
            observed[i] = market;
            if (!windows.TryGetValue(market.Symbol, out var window))
                windows[market.Symbol] = window = new();
            if (window.Count > 0 && last.At - window.Last().At != NativeIntegratedLifecycle.IntervalMs)
                window.Clear();
            if (market.Integrated is not { Path.Complete: true } evidence)
            {
                window.Clear();
                continue;
            }
            window.Enqueue(last);
            if (window.Count > 30) window.Dequeue();
            if (window.Count < 30) continue;
            var quotes = window.ToArray();
            decimal Mid(LedgerQuote q) => (q.Bid + q.Ask) / 2m;
            decimal anchor = quotes.Take(10).Average(Mid);
            var states = quotes.Skip(10).Select(q => q.Bid > anchor ? 1m : q.Ask < anchor ? -1m : 0m).ToArray();
            observed[i] = market with { Integrated = evidence with {
                Residence = new(states.Average(), states.Skip(10).Average() - states.Take(10).Average(),
                    Mid(last) - Mid(quotes[0]))
            }};
        }
        return frame with { Markets = observed };
    }
}

public static class NativeCompletePolicy
{
    public const long Day = 86_400_000L;
    public const long Week = 7 * Day;
    const long EntryFirst = (8 * 60 + 15) * 60_000L;
    const long EntryLast = (10 * 60 + 30) * 60_000L;
    const long SessionSafety = (10 * 60 + 54) * 60_000L;
    public const string Prefix = "COMPLETE_POLICY_";
    public const string Probe = Prefix + "PROBE";
    public const string Economic = Prefix + "ECONOMIC";
    public const string EconomicAdverse = Economic + "_ADVERSE";
    public static readonly string[] Variants = { "CASH", "FIRST", "RANDOM", "LONG", "SHORT", "RANK", "ABLATION", "ECONOMIC" };

    public static bool IsPolicy(string policy) => policy.StartsWith(Prefix, StringComparison.Ordinal)
        && (Variant(policy) == "PROBE" || Variants.Contains(Variant(policy), StringComparer.Ordinal));

    public static string Variant(string policy)
        => policy[Prefix.Length..].Replace("_ADVERSE", "", StringComparison.Ordinal);

    public static bool IsDecision(long at)
        => at % 900_000L == NativeIntegratedEconomicPolicy.ClockOffsetMs &&
           at % Day >= EntryFirst && at % Day <= EntryLast + NativeIntegratedEconomicPolicy.ClockOffsetMs;

    public static bool SessionExit(long at, long opened)
        => at / Day > opened / Day || at % Day >= SessionSafety;

    static decimal[] Clip(params decimal[] values)
        => values.Select(v => Math.Max(-4m, Math.Min(4m, v))).ToArray();

    static decimal Session(long at) => (at % Day - EntryFirst) / (SessionSafety - EntryFirst);

    public static decimal[] EntryFeatures(NativeQuoteResidence state, NativeIntegratedTerms terms,
        NativeIntegratedCandidate signal, LedgerQuote quote)
        => Clip(signal.Side * state.Mean, signal.Side * state.LateChange, signal.Side * state.MidDisplacement / signal.Volatility,
            (quote.Ask - quote.Bid) / signal.Volatility, terms.RewardEur / terms.RiskEur, Session(quote.At));

    public static decimal[] HoldFeatures(NativeQuoteResidence state, int side, decimal liquidationEur, decimal mfe, decimal risk, long at)
        => Clip(side * state.Mean, liquidationEur / risk, mfe / risk, Session(at));

    public static NativeIntegratedCandidate[] Describe(Ucp1MarketFrame market, long at)
    {
        if (!IsDecision(at) || market.Integrated is not { Residence: not null } context ||
            market.M5.Length < 5 || at - market.M5[^1].CloseAt > 300_000L ||
            market.M5[^1].CloseAt >= at || context.H1.Length == 0) return Array.Empty<NativeIntegratedCandidate>();
        var bars = market.M5.TakeLast(5).ToArray();
        if (bars.Any(x => x.CloseAt - x.OpenAt != 300_000L || x.High <= x.Low) ||
            bars.Zip(bars.Skip(1)).Any(x => x.First.CloseAt != x.Second.OpenAt))
            return Array.Empty<NativeIntegratedCandidate>();
        var hour = context.H1[^1];
        var q = market.Quote;
        if (hour.CloseAt >= at || at - hour.CloseAt > 3_600_000L || hour.High <= hour.Low)
            return Array.Empty<NativeIntegratedCandidate>();
        decimal atr = Math.Max(context.TickSize, bars.Average(x => x.High - x.Low));
        var recent = bars.TakeLast(3).ToArray();
        var choices = new List<NativeIntegratedCandidate>();
        foreach (int side in new[] { 1, -1 })
        {
            decimal exit = side > 0 ? q.Bid : q.Ask;
            decimal entry = side > 0 ? q.Ask : q.Bid;
            decimal permittedStopDistance = context.Protection is { } p
                ? p.Stop * (p.Percentage ? exit / 100m : 1m) : 0m;
            decimal distance = Math.Max(atr, permittedStopDistance);
            decimal stop = side > 0 ? Math.Min(recent.Min(b => b.Low) - context.TickSize, exit - distance)
                : Math.Max(recent.Max(b => b.High) + context.TickSize, exit + distance);
            decimal target = side > 0 ? hour.High : hour.Low;
            if (side * (target - entry) <= 0m) target = entry + side * (hour.High - hour.Low);
            stop = (side > 0 ? Math.Floor(stop / context.TickSize) : Math.Ceiling(stop / context.TickSize)) * context.TickSize;
            target = (side > 0 ? Math.Ceiling(target / context.TickSize) : Math.Floor(target / context.TickSize)) * context.TickSize;
            if (stop > 0m && target > 0m)
                choices.Add(new("QUOTE_RESIDENCE", side, stop, target, atr, at - NativeIntegratedEconomicPolicy.ClockOffsetMs));
        }
        return choices.ToArray();
    }
}
