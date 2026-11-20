using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeStructuralSetup(NativeIntegratedCandidate Signal, NativeEntryThesis Thesis,
    decimal[] ContextFeatures);

public sealed record NativeStructuralFamilyModel(NativeCompleteDistribution Contextual,
    NativeCompleteDistribution Pooled, int CalibrationDays);

public sealed record NativeStructuralModels(long AvailableAt, Dictionary<string, NativeStructuralFamilyModel> Families)
{
    public NativeCompletePrediction? Predict(string variant, string family, decimal[] features, long at, decimal risk)
    {
        if (at < AvailableAt || !Families.TryGetValue(family, out var model)) return null;
        return variant switch
        {
            "POOLED" => model.Pooled.Predict(new[] { 0m }, at, risk),
            "RANK" => model.Contextual.Predict(features, at, risk),
            "SELECT" when model.CalibrationDays >= 4 => model.Contextual.Predict(features, at, risk),
            _ => null
        };
    }
}

public static class NativeStructuralOpportunity
{
    public const string Prefix = "CLOSED_MARKET_";
    public const string Compression = "COMPRESSION_RELEASE";
    public const string Rejection = "RANGE_EDGE_REJECTION";
    internal const string Combined = "COMBINED";
    internal const string CombinedRandom = "COMBINED_RANDOM";
    internal const string CombinedWithoutExhaustion = "COMBINED_WITHOUT_EXHAUSTION";
    public static readonly string[] Variants = { "CASH", "FIRST", "RANDOM", "TREND", "REJECTION", "POOLED", "RANK", "SELECT" };

    public static bool IsPolicy(string policy)
    {
        if (!policy.StartsWith(Prefix, StringComparison.Ordinal)) return false;
        string variant = Variant(policy);
        return variant is "PROBE" or "EXHAUSTION" || IsCompetition(variant) ||
            Variants.Contains(variant, StringComparer.Ordinal);
    }

    internal static bool IsCompetition(string variant) =>
        variant is Combined or CombinedRandom or CombinedWithoutExhaustion;

    public static string Variant(string policy)
        => policy.EndsWith("_ADVERSE", StringComparison.Ordinal) ? policy[Prefix.Length..^8] : policy[Prefix.Length..];

    static NativeBarWindow? Ready(Ucp1MarketFrame market, NativeBarTimeframe period)
        => market.ClosedBars is { } context && context.DecisionAt == market.Quote.At &&
            context.Windows.FirstOrDefault(w => w.Timeframe == period) is { Ready: true } window ? window : null;

    public static bool ContextReady(Ucp1MarketFrame market) =>
        Ready(market, NativeBarTimeframe.M1) is { } minute &&
        Ready(market, NativeBarTimeframe.M5) is { } trigger && minute.ExpectedCloseAt == trigger.ExpectedCloseAt &&
        Ready(market, NativeBarTimeframe.M15) is not null &&
        Ready(market, NativeBarTimeframe.M30) is not null && Ready(market, NativeBarTimeframe.H1) is not null;

    static decimal Travel(NativeClosedMarketBar[] bars) => bars[^1].Close - bars[0].Open;

    public static NativeStructuralSetup? Describe(Ucp1MarketFrame market)
    {
        if (!ContextReady(market) || market.Integrated is not { TickSize: > 0m } input) return null;
        var m5 = Ready(market, NativeBarTimeframe.M5)!.Bars;
        var m15 = Ready(market, NativeBarTimeframe.M15)!.Bars;
        var m30 = Ready(market, NativeBarTimeframe.M30)!.Bars;
        var h1 = Ready(market, NativeBarTimeframe.H1)!.Bars;
        var trigger = m5[^1];
        var m1 = Ready(market, NativeBarTimeframe.M1)!.Bars;
        if (m1[^1].CloseAt != trigger.CloseAt || trigger.High <= trigger.Low) return null;
        decimal recentActivity = m1.TakeLast(5).Average(b => (decimal)b.TickVolume);
        decimal earlierActivity = m1.Take(10).Average(b => (decimal)b.TickVolume);
        if (earlierActivity <= 0m) return null;

        decimal h1Travel = Travel(h1), m15Travel = Travel(m15);
        decimal range30 = m30.Average(bar => bar.High - bar.Low);
        if (range30 <= 0m) return null;
        var preceding = m5.Skip(m5.Length - 7).Take(6).ToArray();
        decimal localLow = preceding.Min(x => x.Low);
        decimal localHigh = preceding.Max(x => x.High);
        decimal localWidth = localHigh - localLow;
        var q = market.Quote;
        decimal volatility = Math.Max(input.TickSize, m5.Average(x => x.High - x.Low));

        NativeStructuralSetup? Setup(string family, int side, decimal level, decimal stop, decimal target)
        {
            target = (side > 0 ? Math.Floor(target / input.TickSize) : Math.Ceiling(target / input.TickSize)) * input.TickSize;
            decimal executable = side > 0 ? q.Bid : q.Ask;
            decimal entering = side > 0 ? q.Ask : q.Bid;
            if (stop <= 0m || target <= 0m || side * (target - entering) <= 0m ||
                side * (executable - level) <= 0m ||
                !NativeIntegratedLifecycle.ProtectionCompatible(side, stop, target, market))
                return null;
            var signal = new NativeIntegratedCandidate(family, side, stop, target, volatility, trigger.CloseAt);
            var thesis = new NativeEntryThesis(family, level, m15[^1].CloseAt);
            return new(signal, thesis, Clip(side * h1Travel / range30, side * m15Travel / range30,
                side * Travel(m30) / range30, localWidth / range30,
                recentActivity / earlierActivity - 1m,
                side * (2m * trigger.Close - trigger.High - trigger.Low) / (trigger.High - trigger.Low)));
        }

        int trend = Math.Sign(h1Travel);
        if (trend != 0 && trend == Math.Sign(m15Travel))
        {
            decimal boundary = trend > 0 ? localHigh : localLow;
            if (localWidth > range30 || trend * (trigger.Close - boundary) <= 0m || recentActivity <= earlierActivity)
                return null;
            return Setup(Compression, trend, boundary, trend > 0 ? localLow - input.TickSize : localHigh + input.TickSize,
                trend > 0 ? h1.Max(x => x.High) : h1.Min(x => x.Low));
        }

        var reference = m30.Where(b => b.CloseAt <= trigger.OpenAt).TakeLast(2).ToArray();
        if (reference.Length < 2) return null;
        decimal low = reference.Min(x => x.Low), high = reference.Max(x => x.High);
        bool sweptLow = trigger.Low < low, sweptHigh = trigger.High > high;
        if (sweptLow == sweptHigh || trigger.Close <= low || trigger.Close >= high) return null;
        int reversal = sweptLow ? 1 : -1;
        if (reversal * (m1[^1].Close - m1[^2].Close) <= 0m || reversal * (m1[^2].Close - m1[^3].Close) <= 0m)
            return null;
        return Setup(Rejection, reversal, sweptLow ? low : high,
            sweptLow ? trigger.Low - input.TickSize : trigger.High + input.TickSize, (low + high) / 2m);
    }

    static decimal[] Clip(params decimal[] values) => values.Select(v => Math.Max(-4m, Math.Min(4m, v))).ToArray();

    public static decimal[] Features(NativeStructuralSetup setup, NativeIntegratedTerms terms, LedgerQuote quote)
        => setup.ContextFeatures.Concat(Clip((quote.Ask - quote.Bid) / setup.Signal.Volatility,
            terms.RewardEur / terms.RiskEur)).ToArray();

    public static decimal[] Reprice(decimal[] features, NativeIntegratedTerms terms, LedgerQuote quote, decimal volatility)
        => features.Take(features.Length - 2).Concat(Clip((quote.Ask - quote.Bid) / volatility,
            terms.RewardEur / terms.RiskEur)).ToArray();

    public static NativeEntryThesis? AtFill(NativeEntryThesis thesis, int side, Ucp1MarketFrame market)
    {
        var m15 = Ready(market, NativeBarTimeframe.M15);
        decimal price = side > 0 ? market.Quote.Bid : market.Quote.Ask;
        if (m15 is null || m15.ExpectedCloseAt < thesis.AdmissionM15CloseAt ||
            side * (price - thesis.ReclaimedBoundary) <= 0m ||
            m15.ExpectedCloseAt > thesis.AdmissionM15CloseAt &&
                side * (m15.Bars[^1].Close - thesis.ReclaimedBoundary) <= 0m)
            return null;
        return thesis with { FillM15CloseAt = m15.ExpectedCloseAt };
    }

    public static NativeEntryThesis Observe(NativeEntryThesis thesis, int side, long filledAt, Ucp1MarketFrame market)
    {
        var m15 = Ready(market, NativeBarTimeframe.M15);
        return thesis.InvalidatingM15CloseAt == 0L && m15 is not null &&
            m15.ExpectedCloseAt > Math.Max(filledAt, thesis.FillM15CloseAt) &&
            side * (m15.Bars[^1].Close - thesis.ReclaimedBoundary) <= 0m
            ? thesis with { InvalidatingM15CloseAt = m15.ExpectedCloseAt } : thesis;
    }
}
