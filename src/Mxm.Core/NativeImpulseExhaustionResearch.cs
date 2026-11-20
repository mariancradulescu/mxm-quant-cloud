using System;
using System.Linq;

namespace Mxm.Core;

// Prospective, economically distinct hypothesis: impulse/liquidity exhaustion.
// This does not modify the frozen W46 compression/rejection detectors.
// A completed M5 sweep fails to retain its prior extreme *while* recent M1
// tick activity subsides and M15/H1 still show the preceding impulse.
// A later as-of BID/ASK observation must still price the reclaimed boundary.
// All features and levels are from published, witnessed closed bar windows.
public static class NativeImpulseExhaustionResearch
{
    public const string Family = "IMPULSE_LIQUIDITY_EXHAUSTION";

    private static NativeBarWindow? Ready(Ucp1MarketFrame market, NativeBarTimeframe period)
        => market.ClosedBars is { } c && c.DecisionAt == market.Quote.At
            ? c.Windows.FirstOrDefault(w => w.Timeframe == period && w.Ready)
            : null;

    private static decimal Clip(decimal v) => Math.Max(-4m, Math.Min(4m, v));

    public static NativeStructuralSetup? Describe(Ucp1MarketFrame market)
    {
        if (!NativeStructuralOpportunity.ContextReady(market) ||
            market.Integrated is not { TickSize: > 0m } evidence)
            return null;

        var m1 = Ready(market, NativeBarTimeframe.M1)!.Bars;
        var m5 = Ready(market, NativeBarTimeframe.M5)!.Bars;
        var m15 = Ready(market, NativeBarTimeframe.M15)!.Bars;
        var m30 = Ready(market, NativeBarTimeframe.M30)!.Bars;
        var h1 = Ready(market, NativeBarTimeframe.H1)!.Bars;
        var bar = m5[^1];
        if (bar.CloseAt != m1[^1].CloseAt || m5.Length < 7 ||
            m1.Length < 15 || m15.Length < 2 || m30.Length < 2 || h1.Length < 2)
            return null;
        int impulse = Math.Sign(h1[^1].Close - h1[0].Open);
        if (impulse == 0 || impulse != Math.Sign(m15[^1].Close - m15[0].Open))
            return null;

        var prior = m5.Skip(m5.Length - 7).Take(6).ToArray();
        decimal priorHigh = prior.Max(x => x.High), priorLow = prior.Min(x => x.Low);
        decimal recentActivity = m1.TakeLast(5).Average(x => (decimal)x.TickVolume);
        decimal earlyActivity = m1.Take(10).Average(x => (decimal)x.TickVolume);
        if (earlyActivity <= 0m || recentActivity >= earlyActivity)
            return null;

        // A completed extreme that did not hold is different from an
        // expansion break of a narrow range or an M30 boundary rejection.
        bool failedSweep = impulse > 0
            ? bar.High > priorHigh && bar.Close < priorHigh && bar.Close > priorLow &&
              m1[^1].Close < m1[^2].Close
            : bar.Low < priorLow && bar.Close > priorLow && bar.Close < priorHigh &&
              m1[^1].Close > m1[^2].Close;
        if (!failedSweep) return null;

        int side = -impulse;
        decimal level = impulse > 0 ? priorHigh : priorLow;
        decimal tick = evidence.TickSize;
        decimal stop = impulse > 0
            ? Math.Ceiling((bar.High + tick) / tick) * tick
            : Math.Floor((bar.Low - tick) / tick) * tick;
        decimal range30 = m30.TakeLast(2).Average(x => x.High - x.Low);
        if (range30 <= 0m) return null;
        decimal rawTarget = impulse > 0
            ? m30.TakeLast(2).Min(x => x.Low)
            : m30.TakeLast(2).Max(x => x.High);
        decimal target = side > 0
            ? Math.Ceiling(rawTarget / tick) * tick
            : Math.Floor(rawTarget / tick) * tick;
        var quote = market.Quote;
        decimal entering = side > 0 ? quote.Ask : quote.Bid;
        decimal liquidation = side > 0 ? quote.Bid : quote.Ask;
        if (stop <= 0m || target <= 0m ||
            side * (liquidation - level) <= 0m ||
            side * (target - entering) <= 0m ||
            !NativeIntegratedLifecycle.ProtectionCompatible(side, stop, target, market))
            return null;

        decimal volatility = Math.Max(tick, m5.TakeLast(6).Average(x => x.High - x.Low));
        decimal failedWidth = impulse > 0 ? bar.High - bar.Close : bar.Close - bar.Low;
        var features = new[]
        {
            Clip(side * (h1[^1].Close - h1[0].Open) / range30),
            Clip(side * (m15[^1].Close - m15[0].Open) / range30),
            Clip((recentActivity - earlyActivity) / earlyActivity),
            Clip(failedWidth / range30),
            Clip((priorHigh - priorLow) / range30),
            Clip(side * (2m * bar.Close - bar.High - bar.Low) /
                 Math.Max(tick, bar.High - bar.Low))
        };
        return new(new(Family, side, stop, target, volatility, bar.CloseAt),
            new(Family, level, m15[^1].CloseAt), features);
    }
}
