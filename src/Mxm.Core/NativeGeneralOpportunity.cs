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

        decimal center = h1.TakeLast(2).Average(b => (b.High + b.Low) / 2m);
        decimal mid = (q.Ask + q.Bid) / 2m;
        decimal previousRange = Math.Max(tick, m30.TakeLast(2).Average(b => b.High - b.Low));
        decimal previousVolume = m1.Take(m1.Length - 5).Average(b => (decimal)b.TickVolume);
        decimal recentVolume = m1.TakeLast(5).Average(b => (decimal)b.TickVolume);
        decimal h1Range = Math.Max(tick, h1.TakeLast(2).Max(b => b.High) -
            h1.TakeLast(2).Min(b => b.Low));
        return Geometries(market,tick,m5,h1,2m).Select(signal =>
        {
            int side = signal.Side;
            decimal volatility = signal.Volatility;
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
            var thesis = new NativeEntryThesis(signal.Family, 0m,
                context.For(NativeBarTimeframe.M15).ExpectedCloseAt);
            return new NativeStructuralSetup(signal,thesis,state);
        }).ToArray();
    }

    internal static NativeIntegratedCandidate[] Geometries(Ucp1MarketFrame market,decimal tick,
        NativeClosedMarketBar[] m5,NativeClosedMarketBar[] h1,decimal targetRanges)
    {
        var q = market.Quote;
        if (tick <= 0m || q.Bid <= 0m || q.Ask < q.Bid || m5.Length < 5 ||
            m5.TakeLast(5).Any(b=>b.CloseAt>=q.At||b.High<=b.Low))
            return Array.Empty<NativeIntegratedCandidate>();
        decimal volatility = Math.Max(tick, m5.TakeLast(5).Average(b=>b.High-b.Low));
        var candidates = new List<NativeIntegratedCandidate>(3);
        void Add(string family,int side,decimal target)
        {
            decimal entering=side==1?q.Ask:q.Bid;
            decimal exiting=side==1?q.Bid:q.Ask;
            decimal stop=Tick(exiting-side*volatility,tick,side<0);
            if(stop>0m&&target>0m&&side*(exiting-stop)>0m&&side*(target-entering)>0m&&
                NativeIntegratedLifecycle.ProtectionCompatible(side,stop,target,market))
                candidates.Add(new(family,side,stop,target,volatility,m5[^1].CloseAt));
        }
        foreach (int side in new[] { 1, -1 })
        {
            decimal target = Tick((side == 1 ? q.Ask : q.Bid) + side * targetRanges * volatility,
                tick, side > 0);
            Add(Distribution, side, target);
        }
        if(h1.Length>=2&&h1.TakeLast(2).All(bar=>bar.CloseAt<q.At))
        {
            decimal center=h1.TakeLast(2).Average(b=>(b.High+b.Low)/2m);
            int toward=Math.Sign(center-(q.Ask+q.Bid)/2m);
            if(toward!=0)Add(Equilibrium,toward,Tick(center,tick,toward>0));
        }
        return candidates.ToArray();
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
