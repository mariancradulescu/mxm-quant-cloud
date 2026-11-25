using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Prospective development-only GENERATOR, not a profit-seeking signal rule.
// Unlike COMPRESSION/REJECTION/EXHAUSTION, it does not require a particular
// historical bar pattern: both executable directions are always proposed when
// closed as-of state, bid/ask, contract and protective geometry are available.
// The chronological funded action-value model must learn ENTER vs WAIT.
// All paths, funding, volume, drawdown and CLOSE/REDUCE remain in the shared engine.
public static class NativeGeneralOpportunity
{
    public const string Distribution = "GENERAL_BIDIRECTIONAL_DISTRIBUTION";
    public const string Equilibrium = "GENERAL_HOURLY_EQUILIBRIUM";

    private static decimal Clip(decimal x) => Math.Max(-4m, Math.Min(4m, x));
    private static decimal Tick(decimal value, decimal tick, bool ceil)
        => (ceil ? Math.Ceiling(value / tick) : Math.Floor(value / tick)) * tick;

    public static NativeStructuralSetup[] Describe(Ucp1MarketFrame market)
        => Describe(market, market.Integrated?.TickSize ?? 0m);

    internal static NativeStructuralSetup[] Describe(Ucp1MarketFrame market, decimal tick)
    {
        if (!NativeStructuralOpportunity.ContextReady(market) ||
            market.ClosedBars is not { } context ||
            tick <= 0m ||
            market.Quote.Bid <= 0m || market.Quote.Ask < market.Quote.Bid)
            return Array.Empty<NativeStructuralSetup>();

        var q = market.Quote;
        var m1 = context.For(NativeBarTimeframe.M1).Bars;
        var m5 = context.For(NativeBarTimeframe.M5).Bars;
        var m15 = context.For(NativeBarTimeframe.M15).Bars;
        var m30 = context.For(NativeBarTimeframe.M30).Bars;
        var h1 = context.For(NativeBarTimeframe.H1).Bars;
        if (m1.Length < 10 || m5.Length < 5 || m15.Length < 2 ||
            m30.Length < 2 || h1.Length < 2 ||
            m5[^1].CloseAt >= q.At || m5[^1].CloseAt != m1[^1].CloseAt)
            return Array.Empty<NativeStructuralSetup>();

        decimal span = m5.TakeLast(5).Average(b => b.High - b.Low);
        if (span <= 0m || m5.TakeLast(5).Any(b => b.High <= b.Low))
            return Array.Empty<NativeStructuralSetup>();
        decimal volatility = Math.Max(tick, span);
        decimal center = h1.TakeLast(2).Average(b => (b.High + b.Low) / 2m);
        decimal mid = (q.Ask + q.Bid) / 2m;
        decimal previousRange = Math.Max(tick, m30.TakeLast(2).Average(b => b.High - b.Low));
        decimal previousVolume = m1.Take(m1.Length - 5).Average(b => (decimal)b.TickVolume);
        decimal recentVolume = m1.TakeLast(5).Average(b => (decimal)b.TickVolume);
        decimal h1Range = Math.Max(tick, h1.TakeLast(2).Max(b => b.High) -
            h1.TakeLast(2).Min(b => b.Low));
        var setups = new List<NativeStructuralSetup>(3);

        void Add(string family, int side, decimal stop, decimal target)
        {
            decimal entering = side == 1 ? q.Ask : q.Bid;
            decimal exiting = side == 1 ? q.Bid : q.Ask;
            if (stop <= 0m || target <= 0m ||
                side * (exiting - stop) <= 0m ||
                side * (target - entering) <= 0m ||
                !NativeIntegratedLifecycle.ProtectionCompatible(side, stop, target, market))
                return;

            // All observations precede the decision. No feature is formed from
            // the post-decision quote path or a future unfinished M15/H1 bar.
            var state = new[]
            {
                Clip(side * (m5[^1].Close - m5[^5].Open) / volatility),
                Clip(side * (m15[^1].Close - m15[0].Open) / previousRange),
                Clip(side * (h1[^1].Close - h1[0].Open) / h1Range),
                Clip(side * (mid - center) / h1Range),
                Clip(volatility / previousRange),
                Clip((recentVolume - previousVolume) / Math.Max(1m, previousVolume)),
                Clip(side * (mid - m5.TakeLast(5).Average(b => b.Close)) / volatility),
                Clip((q.Ask - q.Bid) / volatility)
            };
            var signal = new NativeIntegratedCandidate(family, side, stop, target,
                volatility, m5[^1].CloseAt);
            // Zero structural boundary: this mode is not a reclaimed-edge rule.
            // Its causal fill admissibility has its own explicit clock check.
            var thesis = new NativeEntryThesis(family, 0m,
                context.For(NativeBarTimeframe.M15).ExpectedCloseAt);
            setups.Add(new(signal, thesis, state));
        }

        // Mechanism A: full-state direction-neutral distributional choice.
        // One recent completed-bar price range is the *frozen* risk unit; the
        // symmetric two-unit target is a declared comparator, not fitted.
        // No result-dependent activity, trend or breakout threshold.
        foreach (int side in new[] { 1, -1 })
        {
            decimal stop = Tick((side == 1 ? q.Bid : q.Ask) - side * volatility,
                tick, side < 0);
            decimal target = Tick((side == 1 ? q.Ask : q.Bid) + side * 2m * volatility,
                tick, side > 0);
            Add(Distribution, side, stop, target);
        }

        // Mechanism B: restoring the observed center of the last two CLOSED
        // hourly ranges. This is geometric opportunity detection, with no
        // filter on the *direction* of historical returns.
        int toward = Math.Sign(center - mid);
        if (toward != 0)
        {
            decimal stop = Tick((toward == 1 ? q.Bid : q.Ask) - toward * volatility,
                tick, toward < 0);
            decimal target = Tick(center, tick, toward > 0);
            Add(Equilibrium, toward, stop, target);
        }
        return setups.ToArray();
    }

    // Causal fill check, distinct from structural boundary reclaim validation.
    public static NativeEntryThesis? AtFill(NativeEntryThesis thesis, int side,
        Ucp1MarketFrame market)
    {
        if (side is not (1 or -1) || thesis.Family is not (Distribution or Equilibrium) ||
            !NativeStructuralOpportunity.ContextReady(market) ||
            market.ClosedBars is not { } context)
            return null;
        var m15 = context.For(NativeBarTimeframe.M15);
        if (m15.ExpectedCloseAt < thesis.AdmissionM15CloseAt ||
            m15.ExpectedCloseAt >= market.Quote.At)
            return null;
        return thesis with { FillM15CloseAt = m15.ExpectedCloseAt };
    }

    // Exit comparisons and path protection belong to the monetary lifecycle.
    // Do not manufacture a new pattern-based invalidation after admission.
    public static NativeEntryThesis Observe(NativeEntryThesis thesis) => thesis;
}
