using System;
using System.Linq;
using Mxm.Core;

public static class NativeProductResearchLoopChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long m5=300000L,m15=900000L;
        long anchor=DateTimeOffset.Parse("2026-11-04T21:45:00Z").ToUnixTimeMilliseconds();
        NativeClosedMarketBar[] Window(string symbol,long step,long at)
        {
            long end=(at/step)*step;
            return Enumerable.Range(0,33).Select(i=>{
                decimal close=symbol=="SYNTH_A"
                    ?10.16m+i*.12m:22m-i*.12m;
                long open=end-(33-i)*step;
                return new NativeClosedMarketBar(open,open+step,close,
                    close+.02m,close-.02m,close,100+i);
            }).ToArray();
        }
        NativeObservedContractTerms Contract(string symbol,long at)=>
            new(symbol,"USD",at,1,1,1,1,2,5000000,
                1,0,"USD",10,0,-.05m,-.08m,2,24,1320,3,
                false,0,true,false);
        NativeProductMarket Market(string symbol,long at,int tick,
            bool support=false)
        {
            decimal bid=symbol=="SYNTH_A"
                ?14m+Math.Max(0,tick-1)*.12m
                :18m-Math.Max(0,tick-1)*.10m;
            var c=Contract(symbol,at);
            var cost=new NativeMarketCostContext(at,bid,bid+.02m,
                .99m,1.01m,1m,null,20m,1m,.005m);
            var charge=NativeBrokerContractCosts.Quote(c,cost);
            check(!charge.HistoricalExecutionCertified&&charge.OneSideCommissionEur>0,
                "current-term native cost source prices commission without claiming actual fills");
            return new(symbol,Window(symbol,m5,at-2000),
                Window(symbol,m15,at-2000),charge.Quote,c,.005m,30,support);
        }
        var cashOnly=new NativeProductResearchLoop();
        var at=anchor+2000;
        var refused=cashOnly.Advance(at,new[]{Market("SYNTH_A",at,0)},
            EnableUnqualifiedShadowSimulation:false);
        check(refused.Forecasts==1&&refused.AcceptedModelIntents==0&&
            refused.RejectedIntents>=1&&refused.ModelCashEur==300m&&
            refused.ModelClosedRoundTrips==0,
            "no independent predictive benchmark refuses prospective entry without mutating EUR300 cash");
        var assertedSupport=new NativeProductResearchLoop().Advance(at,
            new[]{Market("SYNTH_A",at,0,support:true)},EnableUnqualifiedShadowSimulation:false);
        check(assertedSupport.Forecasts==1 && assertedSupport.AcceptedModelIntents==0 &&
              assertedSupport.ModelPendingIntents==0 &&
              assertedSupport.LatestSignals.Single().DecisionReason==
                  "SPECIALIST_NO_PREDICTIVE_BENCHMARK_SUPPORT",
            "benchmark support flag cannot convert a raw gross forecast into measured incremental edge");
        // Two distinct markets arriving on different M5 decision clocks
        // must still compete against ONE existing held and pending budget.
        var staggered=new NativeProductResearchLoop();
        var t0=anchor+2000;
        var onlyA=staggered.Advance(t0,new[]{Market("SYNTH_A",t0,0)},true);
        check(onlyA.AcceptedModelIntents==1&&onlyA.ModelPendingIntents==1,
            "first symbol reserves one EUR300 model intent before second market appears");
        const string provisionalSource="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        var livePending=NativeProductResearchLoop.RestoreIntegrityCheckpoint(
            staggered.ExportIntegrityCheckpoint(provisionalSource),provisionalSource);
        var t1=t0+m5;
        var newB=livePending.Advance(t1,new[]{
            Market("SYNTH_A",t1,1),Market("SYNTH_B",t1,1)},true);
        check(newB.AcceptedModelIntents==2&&newB.ModelOpenPositions==1&&
              newB.ModelPendingIntents==1&&newB.ModelCashEur<300m,
            "staggered B is assessed with A held and common margin, with pending state restored across checkpoint");
        // A cTrader Algo Symbol observation must NEVER be silently upgraded
        // to an authenticated original Pepperstone contract.
        var algoTerms=Contract("SYNTH_A",t0) with {OriginalBrokerAuthenticated=false};
        var algoContext=new NativeMarketCostContext(t0,10m,10.02m,
            1m,1m,1m,1m,20m,1m,.005m);
        bool originalTariffRejects=false;
        try{NativeBrokerContractCosts.Quote(algoTerms,algoContext);}
        catch(ArgumentException){originalTariffRejects=true;}
        var algoOnly=NativeBrokerContractCosts.QuoteCurrentAlgo(algoTerms,algoContext);
        check(originalTariffRejects&&
              !algoOnly.HistoricalExecutionCertified&&
              algoOnly.EvidenceLevel.Contains("UNATTESTED"),
            "current Algo fees are priced conditionally without inventing original account cryptographic proof");
        var loop=new NativeProductResearchLoop();
        var a=loop.Advance(at,new[]{Market("SYNTH_A",at,0),
            Market("SYNTH_B",at,0)},EnableUnqualifiedShadowSimulation:true);
        check(a.LatestSignals.Length==2&&a.LatestSignals.All(x=>
            x.Status=="SHADOW_MODEL_INTENT_ALLOCATED_NOT_TRADING" &&
            x.DecisionReason.Contains("CONDITIONAL")),
            "both shadow allocations carry causal symbol-specific native reasoning");
        check(refused.LatestSignals.Single().DecisionReason==
            "SPECIALIST_NO_PREDICTIVE_BENCHMARK_SUPPORT",
            "unqualified prospective rejection reports the original native specialist economic reason");
        check(a.Forecasts==2&&a.AcceptedModelIntents==2&&
            a.ModelPendingIntents==2&&a.ModelCashEur==300m&&
            !a.Qualified&&!a.OrdersEnabled&&!a.BrokerNetCertified,
            "causal M5 plus M15 creates TWO common-capital conditional research intents only");
        NativeProductResearchReport r=a;
        for(int tick=1;tick<=9;tick++)
        {
            long clock=at+tick*m5;
            r=loop.Advance(clock,new[]{Market("SYNTH_A",clock,tick),
                Market("SYNTH_B",clock,tick)},
                EnableUnqualifiedShadowSimulation:tick<8);
            if(tick==1)
                check(r.ModelOpenPositions==2&&r.ModelCashEur<300m&&
                    r.ModelEquityEur<r.ModelCashEur,
                    "next market clock fills both model requests using real-side bid ask commission");
        }
        var settlement=loop.ResearchSession.Ledger;
        var summary=settlement.Summary();
        var fragments=settlement.ClosedFragments();
        check(r.ModelClosedRoundTrips==2&&summary.OpenPositions==0&&
            summary.PendingIntents==0&&r.ModelRoundTripsPerIsoWeek.Values.Sum()==2,
            "two closed model round trips are counted per UTC ISO week after 30m holding");
        check(summary.CashEur==300m+fragments.Sum(x=>x.NetEur)&&
            r.ModelCentralNetEur==summary.ClosedNetEur&&
            r.ModelGrossEur==fragments.Sum(x=>x.GrossEur),
            "one EUR300 funded MODEL domain reconciles gross, fees and cash without extra deposits");
        check(fragments.Any(x=>x.ConversionEur>0)&&
            fragments.All(x=>x.CommissionsEur>0)&&
            fragments.Any(x=>x.FinancingEur>0)&&
            fragments.All(x=>x.SpreadEur>0)&&
            fragments.All(x=>x.SlippageEur>0),
            "full modeled settlement itemizes conversion, commission, actual modeled rollover charge, spread and slippage");
        check(r.ModelAdverseNetProxyEur is decimal stressed &&
              stressed<r.ModelCentralNetEur &&
              r.AdversePathFullyRepriced &&
              r.ModelMatchedLongBenchmarkEur.HasValue &&
              r.ModelIncrementalVsLongEur==
                  r.ModelCentralNetEur-r.ModelMatchedLongBenchmarkEur &&
              r.ModelMaximumSampledDrawdown>0m&&!r.Qualified&&
              !r.BrokerNetCertified,
            "adverse bid/ask, fee, slippage, FX and swap are financially repriced in a second native ledger; matched same-clock long benchmark and floating equity remain descriptive");
        bool backwardRejected=false;
        try{loop.Advance(at+1,Array.Empty<NativeProductMarket>(),false);}
        catch(ArgumentException){backwardRejected=true;}
        check(backwardRejected,
            "out-of-order replay observations cannot overwrite a newer financial state");
        // A real deterministic numerical reception from THIS synthetic test,
        // never source-authenticated Pepperstone performance or funded broker NET.
        Console.WriteLine("MXM_PRODUCT_NATIVE_SYNTHETIC_MODEL_RECEIPT="+
            System.Text.Json.JsonSerializer.Serialize(new {
                initialCapitalEur=300m,
                grossModelEur=r.ModelGrossEur,
                centralNetModelEur=r.ModelCentralNetEur,
                adverseFullRepricedNetModelEur=r.ModelAdverseNetProxyEur,
                matchedLongBenchmarkNetModelEur=r.ModelMatchedLongBenchmarkEur,
                incrementalVsMatchedLongModelEur=r.ModelIncrementalVsLongEur,
                unobservedM5Slots=r.ObservedM5SlotsNotScored,
                adverseFullyRepriced=r.AdversePathFullyRepriced,
                cashEur=r.ModelCashEur,
                closedRoundTrips=r.ModelClosedRoundTrips,
                sampledFloatingDrawdown=r.ModelMaximumSampledDrawdown,
                weekly=r.ModelRoundTripsPerIsoWeek,
                brokerNetCertified=false,independentConfirmation=false,
                ordersEnabled=false,source="PURELY_SYNTHETIC_NUMERICAL_FIXTURE"
            }));
        // New, opt-in policies use the SAME EUR300 native session, modeled
        // fill/cost/financing and close-request latency. They are not trading
        // instructions and do not rewrite any historical frozen receipt.
        var managed=new NativeProductResearchLoop();
        NativeProductMarket ManagedMarket(long clock,int tick)=>
            Market("SYNTH_A",clock,tick) with {
                ExitPolicy=NativeCausalExitResearch.VolatilityTarget,
                HoldingMinutes=180
            };
        _=managed.Advance(t0,new[]{ManagedMarket(t0,0)},true);
        NativeProductResearchReport managedReport=managed.Advance(t0+m5,
            new[]{ManagedMarket(t0+m5,1)},true);
        for(int tick=2;tick<=6;tick++)
        {
            long clock=t0+tick*m5;
            managedReport=managed.Advance(clock,
                new[]{ManagedMarket(clock,tick)},true);
        }
        check(managedReport.ModelExitReasons is not null &&
              managedReport.ModelExitReasons.GetValueOrDefault(
                  "ENTRY_ATR_PROFIT_TARGET")>=1 &&
              managedReport.ModelClosedRoundTrips>=1 &&
              managedReport.ModelCentralNetEur==
                  managed.ResearchSession.Ledger.Summary().ClosedNetEur,
            "opt-in ATR target closes via existing funded EUR300 ledger before 180m cap");

        const string sourceHash="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
        string full=loop.ExportIntegrityCheckpoint(sourceHash);
        var cloned=NativeProductResearchLoop.RestoreIntegrityCheckpoint(full,sourceHash);
        check(cloned.ModelEpochId==loop.ModelEpochId &&
              cloned.ResearchSession.Ledger.Summary()==loop.ResearchSession.Ledger.Summary() &&
              cloned.AdverseScenario.Summary==loop.AdverseScenario.Summary,
              "source-bound integrity checkpoint restores original session and fully repriced adverse cash without second EUR300 deposit");
        bool differentSourceRejected=false;
        try{NativeProductResearchLoop.RestoreIntegrityCheckpoint(full,
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");}
        catch(ArgumentException){differentSourceRejected=true;}
        check(differentSourceRejected,"different historical source cannot adopt a previous model capital run");
        var oneMissed=new NativeProductResearchLoop();
        _=oneMissed.Advance(at,new[]{Market("SYNTH_A",at,0)},false);
        var delayed=oneMissed.Advance(at+2*m5,new[]{
            Market("SYNTH_A",at+2*m5,2)},false);
        check(delayed.ObservedM5SlotsNotScored>=1 &&
              !delayed.HistoryPathComplete &&
              delayed.UnresolvedCalendarGaps>=1,
              "M5 skipped decision clock and unobserved floating path explicitly invalidate complete history");
        var checkpoint=loop.ResearchSession.Checkpoint();
        var restored=NativeFundedSession.Restore(checkpoint,loop.ResearchSession.AccountBinding);
        check(restored.Ledger.Summary()==loop.ResearchSession.Ledger.Summary(),
            "model-replay session checkpoint restarts with unchanged cash and closed round trips");
    }
}
