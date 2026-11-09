using System;
using System.Linq;

namespace Mxm.Core;

// Pure deterministic model research only. All decisions are made at a supplied
// post-bar quote clock; it never assumes an intrabar trigger, stop fill, or order.
public sealed record NativeExitSeed(decimal AtrQuote, decimal EquilibriumQuote);
public sealed record NativeExitVerdict(bool RequestClose, string Reason,
    decimal FavorableExtreme);

public static class NativeCausalExitResearch
{
    public const string FrozenFixed = "FROZEN_LEGACY_FIXED";
    public const string PredictionInvalidation = "M15_PREDICTION_INVALIDATION";
    public const string Chandelier = "M5_ATR_CHANDELIER";
    public const string VolatilityTarget = "M5_VOLATILITY_TARGET";
    public const string EquilibriumReversion = "M15_EQUILIBRIUM_REVERSION";

    public static bool Supported(string mode) => mode is
        (FrozenFixed or PredictionInvalidation or Chandelier or
         VolatilityTarget or EquilibriumReversion);

    // ATR(14) from fifteen strictly consecutive COMPLETED M5 candles.
    // Equilibrium is the mean of eight consecutive completed M15 closes.
    // Both values are frozen at the modeled OPEN FILL, not optimized at exit.
    public static bool TrySeed(NativeClosedMarketBar[] m5,
        NativeClosedMarketBar[] m15, long decisionAt,
        out NativeExitSeed seed)
    {
        seed = new(0m, 0m);
        if(m5 is null || m15 is null || m5.Length<15 ||
           m15.Length<8 || decisionAt<=0) return false;
        var bars=m5.TakeLast(15).ToArray();
        var context=m15.TakeLast(8).ToArray();
        if(bars[^1].CloseAt>=decisionAt ||
           decisionAt-bars[^1].CloseAt>315000L ||
           context[^1].CloseAt>=decisionAt ||
           decisionAt-context[^1].CloseAt>960000L)
            return false;
        if(bars.Any(x=>x.Open<=0 || x.High<x.Low ||
             x.CloseAt-x.OpenAt!=300000L) ||
           context.Any(x=>x.CloseAt-x.OpenAt!=900000L ||
             x.Close<=0) ||
           bars.Zip(bars.Skip(1)).Any(x=>
             x.First.CloseAt!=x.Second.OpenAt) ||
           context.Zip(context.Skip(1)).Any(x=>
             x.First.CloseAt!=x.Second.OpenAt))
            return false;
        decimal sum=0m;
        for(int i=1;i<bars.Length;i++)
        {
            decimal prev=bars[i-1].Close;
            sum+=Math.Max(bars[i].High-bars[i].Low,
                Math.Max(Math.Abs(bars[i].High-prev),
                         Math.Abs(bars[i].Low-prev)));
        }
        decimal atr=sum/14m;
        if(atr<=0m)return false;
        seed=new(atr,context.Average(x=>x.Close));
        return true;
    }

    public static NativeExitVerdict Assess(string policy,long at,long openAt,
        int side,decimal entryPrice,NativeExitSeed seed,decimal priorExtreme,
        LedgerQuote quote,NativeClosedMarketBar[] m5,
        NativeClosedMarketBar[] m15,int maximumMinutes)
    {
        if(!Supported(policy) || at<=openAt || openAt<=0 ||
           side is not (1 or -1) || entryPrice<=0 ||
           quote is null || quote.At!=at || quote.Bid<=0 ||
           quote.Ask<quote.Bid || maximumMinutes is <15 or >240 ||
           m5 is null || m15 is null ||
           m5.Any(b=>b.CloseAt>=at) || m15.Any(b=>b.CloseAt>=at))
            throw new ArgumentException("EXIT_POLICY_NONCAUSAL_OR_UNSUPPORTED");
        if(policy!=FrozenFixed && (seed.AtrQuote<=0 ||
             seed.EquilibriumQuote<=0 || priorExtreme<=0))
            throw new ArgumentException("EXIT_POLICY_ENTRY_SEED_MISSING");

        var afterEntry=m5.Where(b=>b.CloseAt>openAt &&
            b.CloseAt<at).ToArray();
        decimal extreme=priorExtreme>0?priorExtreme:entryPrice;
        if(afterEntry.Length>0)
            extreme=side==1?
                Math.Max(extreme,afterEntry.Max(b=>b.High)):
                Math.Min(extreme,afterEntry.Min(b=>b.Low));

        // The old hold rule remains ONLY for exact historical reproduction.
        if(policy==FrozenFixed)
            return new(at-openAt>=maximumMinutes*60000L,
                "FROZEN_LEGACY_TIME",extreme);

        // Current bid/ask mark, NOT a guaranteed historical stop execution.
        decimal actionable=side==1?quote.Bid:quote.Ask;
        if(side==1? actionable<=entryPrice-1.5m*seed.AtrQuote:
                    actionable>=entryPrice+1.5m*seed.AtrQuote)
            return new(true,"ENTRY_VOLATILITY_INVALIDATION",extreme);

        if(policy==PredictionInvalidation && m15.Length>=3)
        {
            decimal recent=m15[^1].Close-m15[^3].Close;
            if(side*recent<0m)
                return new(true,"CLOSED_M15_PREDICTION_REVERSED",extreme);
        }
        if(policy==Chandelier)
        {
            // A completed-candle high/low is a trailing reference, not a
            // claim that the historical intrabar trail was actually filled.
            decimal trail=extreme-side*2m*seed.AtrQuote;
            if(side==1? actionable<=trail:actionable>=trail)
                return new(true,"COMPLETED_BAR_ATR_CHANDELIER",extreme);
        }
        if(policy==VolatilityTarget &&
           side*(actionable-entryPrice)>=2m*seed.AtrQuote)
            return new(true,"ENTRY_ATR_PROFIT_TARGET",extreme);
        if(policy==EquilibriumReversion &&
           (side==1? actionable>=seed.EquilibriumQuote:
                     actionable<=seed.EquilibriumQuote))
            return new(true,"ENTRY_M15_EQUILIBRIUM_REACHED",extreme);

        // A protective maximum exposure limit, never the sole universal
        // profit-taking rule. No exit is imputed between observations.
        if(at-openAt>=maximumMinutes*60000L)
            return new(true,"MAXIMUM_EXPOSURE_SAFETY_LIMIT",extreme);
        return new(false,"HOLD_CAUSALLY_OBSERVED",extreme);
    }
}
