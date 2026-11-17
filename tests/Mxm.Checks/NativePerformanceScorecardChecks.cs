using System;
using System.Linq;
using Mxm.Core;

internal static class NativePerformanceScorecardChecks
{
    public static void Run(Action<bool,string> check)
    {
        var empty=NativePerformanceScorecard.Calculate(new NativeEconomicScorecardInput(
            "CASH",Array.Empty<LedgerClosedFragment>(),
            Array.Empty<NativeEconomicMark>(),Array.Empty<NativeEntryRisk>(),
            new[]{"2026-W19","2026-W20"},300m,0m,0m,true,false,false));
        check(empty.CompletedRoundTrips==0 && empty.NetEur==0m && empty.ReturnOnCapital==0m &&
              empty.NetExpectancyPerTradeEur is null && empty.WinRate is null &&
              empty.ProfitFactor is null && empty.ExpectedShortfall5PctEur is null &&
              !empty.Hard21AllEligibleWeeks && empty.MaximumSampledFloatingDrawdown is null,
              "No trade metrics null while cash net identity remains zero");
        check(empty.UnknownOrNotApplicable.Contains("NO_FINANCED_ROUND_TRIPS_CASH_IS_NOT_PERFORMANCE"),
              "Cash never satisfies profitable-portfolio scorecard");
        var trades=Enumerable.Range(0,20).Select(i=>
            new LedgerClosedFragment("P"+i,"S",1000+i*1000L,1001+i*1000L,1,
                i%2==0?3m:-1m,0m,0m,0m,0m,0m,i%2==0?3m:-1m,true,"Synthetic")).ToArray();
        var risks=Enumerable.Range(0,20).Select(i=>new NativeEntryRisk("P"+i,2m,900+i*1000L,"known-in-advance")).ToArray();
        var marks=new[]{new NativeEconomicMark(999,300m,0m,300m,0),
            new NativeEconomicMark(2000,290m,20m,270m,1),
            new NativeEconomicMark(3000,321m,0m,321m,0)};
        var filled=NativePerformanceScorecard.Calculate(new NativeEconomicScorecardInput(
            "SYNTH",trades,marks,risks,new[]{"1970-W01"},300m,20m,0m,true,false,false));
        check(filled.NetEur==20m && filled.CompletedRoundTrips==20 &&
              filled.NetExpectancyPerTradeEur==1m && filled.WinRate==0.5m &&
              filled.MeanWinEur==3m && filled.MeanLossEur==-1m &&
              filled.ProfitFactor==3m && filled.PayoffRatio==3m &&
              filled.MeanRiskMultiple==0.5m && filled.TotalNetToCommittedRisk==0.5m,
              "Full sample win loss PF payoff R multiple and net identity");
        check(filled.ExpectedShortfall5PctEur==-1m &&
              filled.MaximumConsecutiveLosses==1 &&
              filled.MaximumSampledFloatingDrawdown==(300m-290m)/300m &&
              filled.PeakMarginEur==20m && filled.MinimumFreeMarginEur==270m &&
              filled.MaximumConcurrentPositions==1 && !filled.ContinuousDrawdownCertified,
              "Tail loss, streak and sampled floating risk are not continuous certificate");
        bool missingRisk=false;
        try{
            NativePerformanceScorecard.Calculate(new NativeEconomicScorecardInput("BAD",trades,marks,risks,
                new[]{"1970-W01"},300m,21m,0m,true,false,false));
        }catch(ArgumentException e){missingRisk=e.Message.Contains("NATIVE_SCORECARD_CASH_TRADE_IDENTITY");}
        check(missingRisk,"Cannot present ledger inconsistent terminal PnL");
        var bad=NativePerformanceScorecard.Calculate(new NativeEconomicScorecardInput(
            "UNKNOWN",trades,marks,Array.Empty<NativeEntryRisk>(),new[]{"1970-W01"},300m,
            null,0m,false,false,false));
        check(bad.NetEur is null && bad.ReturnOnCapital is null &&
              bad.MeanRiskMultiple is null && !bad.FullFinancialOutcomeKnown,
              "No fabricated NET or R risk when evidence absent");
    }
}
