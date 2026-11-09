using System;
using System.Linq;
using Mxm.Core;

public static class NativeCausalExitResearchChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long m5=300000L, m15=900000L;
        long closed=DateTimeOffset.Parse("2026-11-09T09:00:00Z")
            .ToUnixTimeMilliseconds();
        NativeClosedMarketBar[] Bars(int n,long step)
        {
            return Enumerable.Range(0,n).Select(i=>{
                long open=closed-(n-i)*step;
                decimal p=1.1000m+i*.0001m;
                return new NativeClosedMarketBar(open,open+step,
                    p,p+.0003m,p-.0003m,p+.0001m,100+i);
            }).ToArray();
        }
        var five=Bars(16,m5);
        var fifteen=Bars(8,m15);
        long openAt=closed+2000L,now=openAt+m5;
        check(NativeCausalExitResearch.TrySeed(five,fifteen,openAt,out var seed) &&
              seed.AtrQuote>0m && seed.EquilibriumQuote>0m,
              "entry ATR and equilibrium use only consecutive completed bars");
        decimal entry=1.1030m,atr=seed.AtrQuote;
        LedgerQuote Q(decimal bid)=>new("EURUSD",now,bid,bid+.0001m,
            1m,1m,0m,0m,1m);
        var barAfter=new NativeClosedMarketBar(
            closed,closed+m5,entry,entry+.0001m,entry-.0001m,
            entry,110);
        var seen=five.Append(barAfter).ToArray();
        NativeExitVerdict Assess(string mode,decimal price,
            decimal extreme=0m,decimal? equilibrium=null,
            NativeClosedMarketBar[]? m15Override=null,int minutes=180)
        {
            var fixedSeed=seed with {EquilibriumQuote=equilibrium??seed.EquilibriumQuote};
            return NativeCausalExitResearch.Assess(mode,now,openAt,1,
                entry,fixedSeed,extreme==0m?entry:extreme,Q(price),seen,
                m15Override??fifteen,minutes);
        }
        var risk=Assess(NativeCausalExitResearch.Chandelier,entry-2m*atr);
        check(risk.RequestClose &&
              risk.Reason=="ENTRY_VOLATILITY_INVALIDATION",
              "observed adverse bid quote overrides trailing policy");
        var trail=Assess(NativeCausalExitResearch.Chandelier,
            entry+2m*atr,entry+5m*atr);
        check(trail.RequestClose &&
              trail.Reason=="COMPLETED_BAR_ATR_CHANDELIER",
              "chandelier can close before maximum holding period");
        var target=Assess(NativeCausalExitResearch.VolatilityTarget,
            entry+3m*atr);
        check(target.RequestClose &&
              target.Reason=="ENTRY_ATR_PROFIT_TARGET",
              "volatility target can close on observed quote");
        var equilibrium=Assess(NativeCausalExitResearch.EquilibriumReversion,
            entry+atr,entry,entry+atr*.5m);
        check(equilibrium.RequestClose &&
              equilibrium.Reason=="ENTRY_M15_EQUILIBRIUM_REACHED",
              "entry-frozen M15 equilibrium governs reversion exit");
        var reversed=fifteen.ToArray();
        reversed[^1]=reversed[^1] with {Close=reversed[^3].Close-.0005m};
        var invalidate=Assess(NativeCausalExitResearch.PredictionInvalidation,
            entry,m15Override:reversed);
        check(invalidate.RequestClose &&
              invalidate.Reason=="CLOSED_M15_PREDICTION_REVERSED",
              "completed M15 reversal invalidates directional prediction");
        var frozen=NativeCausalExitResearch.Assess(
            NativeCausalExitResearch.FrozenFixed,now,openAt,1,
            entry,new(0m,0m),0m,Q(entry-3m*atr),seen,fifteen,30);
        check(!frozen.RequestClose &&
              frozen.Reason=="FROZEN_LEGACY_TIME",
              "existing exact historical 30-minute hold is unchanged");
        // Legacy must not suddenly depend on the adaptive feature-bar
        // gate. The recorded time-only exit is reproducible unchanged.
        var legacyWithNewerBar=NativeCausalExitResearch.Assess(
            NativeCausalExitResearch.FrozenFixed,now,openAt,1,
            entry,new(0m,0m),0m,Q(entry),seen.Append(
                new NativeClosedMarketBar(now,now+m5,entry,entry,entry,
                    entry,100)).ToArray(),fifteen,30);
        check(!legacyWithNewerBar.RequestClose &&
              legacyWithNewerBar.Reason=="FROZEN_LEGACY_TIME",
              "frozen time exit bypasses only new adaptive candle gates");
        var limited=Assess(NativeCausalExitResearch.PredictionInvalidation,
            entry,minutes:15);
        check(!limited.RequestClose,
            "nonlegacy policy is not a universal 30-minute exit");
        bool futureRejected=false;
        try
        {
            NativeCausalExitResearch.Assess(
                NativeCausalExitResearch.Chandelier,now,openAt,1,entry,
                seed,entry,Q(entry),seen.Append(new NativeClosedMarketBar(
                    now,now+m5,entry,entry,entry,entry,1)).ToArray(),
                fifteen,180);
        }
        catch(ArgumentException){futureRejected=true;}
        check(futureRejected,"future closed candle cannot influence exit");
        var withGap=five.ToArray();
        withGap[^1]=withGap[^1] with {OpenAt=withGap[^1].OpenAt+m5};
        check(!NativeCausalExitResearch.TrySeed(withGap,fifteen,openAt,out _),
            "missing M5 continuity refuses exit-policy entry calibration");
        check(!NativeCausalExitResearch.Supported("BEST_IN_HINDSIGHT"),
            "no arbitrary retrospective exit mode or optimizer");
    }
}
