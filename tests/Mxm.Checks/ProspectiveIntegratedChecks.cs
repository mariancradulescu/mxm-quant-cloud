using Mxm.Core;

// One end-to-end *synthetic* prediction -> cost/benchmark -> prospective native
// admission -> common allocator -> native settlement, without any broker/API/Cloud.
internal static class ProspectiveIntegratedChecks
{
    public static void Run(Action<bool,string> check)
    {
        const string h="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        const long span=300000L;
        const long start=1000000L;
        NativeWarmupReport Warmup(string symbol,bool rising)
        {
            var bars=Enumerable.Range(0,33).Select(i=>{
                decimal close=(rising?10m+i*.001m:20m-i*.001m);
                return new NativeClosedMarketBar(start+i*span,start+(i+1)*span,
                    close,close+.002m,close-.002m,close,100+i);
            }).ToArray();
            return NativeCausalWarmup.Rebuild(new(symbol,"M5",5,bars[^1].CloseAt+1000,bars));
        }
        var a=Warmup("SYNTH_A",true);
        var b=Warmup("SYNTH_B",false);
        check(a.Ready && b.Ready && a.NormalizedDrift>0 && b.NormalizedDrift<0 &&
              a.RelativeTickActivity>0 && b.RelativeTickActivity>0 &&
              !a.ForecastModelRestored && !b.BrokerDecisionEligible,
              "synthetic 33 closed OHLCV bars yield finite causal feature prefixes, not a fitted model or trading certificate");
        // Deliberately simple *test predictor* defined only from past drift,
        // not an economically scored hypothesis or an asserted real forecast.
        int directionA=a.NormalizedDrift>0?1:-1;
        int directionB=b.NormalizedDrift>0?1:-1;
        check(directionA==1 && directionB==-1 && a.LastClosedAt==b.LastClosedAt,
              "predictor sign is determined at the same closed-bar causal clock");
        long clock=a.LastClosedAt+1000;
        LedgerQuote Q(string s,long at,decimal bid)=>s=="SYNTH_A"
            ?new(s,at,bid,bid+.02m,1m,1m,0m,.1m,20m)
            :new(s,at,bid,bid+.04m,.9m,.93m,0m,.1m,25m);
        LedgerEvent E(string id,long at,string kind,string pid="",string sym="",
            int side=0,decimal units=0,decimal price=0,decimal fee=0,
            decimal margin=1,decimal slip=0,LedgerQuote[]? quotes=null,decimal financing=0)=>
            new(id,at,kind,pid,sym,side,units,price,fee,margin,slip,
                0,0,1000,"F1_SYNTHETIC_ONLY",h,quotes??Array.Empty<LedgerQuote>(),financing);
        var session=new NativeFundedSession("SYNTHETIC_F1_ACCOUNT");
        session.ApplyResearchFacts(new[]{E("initial-mark",clock,"MARK",quotes:
            new[]{Q("SYNTH_A",clock,10m),Q("SYNTH_B",clock,20m)})});
        var sizing=new ScenarioSizingInputs(300,300,300,1,1,1,1,1,2,0);
        var grid=new AdaptiveRiskInputs(300,0,300,1,1,1,20,0,false,false,2,0);
        var empty=new[]{new PortfolioScenario("A",clock-100,true,0,0,0,0),
                        new PortfolioScenario("B",clock-100,true,0,0,0,0)};
        EconomicOpportunity Opportunity(string id,string symbol,int direction,decimal volume,decimal margin)=>
            new(id,"F1_SYNTHETIC_NOT_ECONOMIC_CANDIDATE",symbol,id,direction,
                clock,clock-50,EvidenceLevel.Exploratory,false,
                grid with {MinimumUnits=volume,MaximumUnits=volume,MarginPerUnitEur=margin},
                new[]{new OpportunityScenario("A",clock-100,true,1.0m,0,.15m,0),
                      new OpportunityScenario("B",clock-100,true,1.1m,0,.15m,0)});
        var x=Opportunity("F1-A","SYNTH_A",directionA,2m,20m);
        var y=Opportunity("F1-B","SYNTH_B",directionB,1m,25m);
        SpecialistEuroEvidence Evidence(EconomicOpportunity o,NativeWarmupReport warmup)=>
            new(o.Id,warmup.LastClosedAt,clock-1,5,60,
                true,true,true,true,false,5m,.1m,.04m,.1m,.1m,.01m,.03m,.05m,
                o.VolumeGrid.MinimumUnits*o.VolumeGrid.MarginPerUnitEur);
        // The "authentic" and benchmark flags are deliberately synthetic
        // harness assertions, never broker/independence qualifications.
        var ex=Evidence(x,a);var ey=Evidence(y,b);
        NativeResearchDecision Decision(string id,SpecialistEuroEvidence[] evidence)=>new(
            id,clock,sizing,empty,new[]{x,y},Array.Empty<ResearchExposureScenarios>(),
            new[]{new ResearchEntryTerms(x.Id,1000,.005m,h),
                  new ResearchEntryTerms(y.Id,1000,.01m,h)},h,evidence);
        var snapshot=session.Checkpoint();
        var wrong=session.DecideProspective(Decision("reject-gross",new[]{
            ex with {GrossAboveBenchmarkEur=-.1m},ey with {SupportedVsBenchmark=false}}));
        check(wrong.Selection.Allocations.Length==0 && wrong.Ledger.CashEur==300m &&
            wrong.Ledger.PendingIntents==0 &&
            wrong.Selection.Declined.Any(z=>z.Reason=="SPECIALIST_NONPOSITIVE_GROSS_EDGE") &&
            wrong.Selection.Declined.Any(z=>z.Reason=="SPECIALIST_NO_PREDICTIVE_BENCHMARK_SUPPORT"),
            "prospective gross and benchmark rejection cannot create conditional orders or deposits");
        session=NativeFundedSession.Restore(snapshot,session.AccountBinding);
        var missingCost=session.DecideProspective(Decision("reject-missing-funding",new[]{
            ex with {FinancingEur=null},ey with {CompleteCurrentContractFxAndMargin=false}}));
        check(missingCost.Selection.Allocations.Length==0 && missingCost.Ledger.PendingIntents==0 &&
            missingCost.Selection.Declined.Any(z=>z.Reason=="SPECIALIST_UNKNOWN_EUR_COST_OR_FINANCING"),
            "unknown funding or contract/FX cannot be treated as zero cost");
        session=NativeFundedSession.Restore(snapshot,session.AccountBinding);
        bool noEvidence=false;
        try{session.DecideProspective(Decision("bypass",new[]{ex,ey}) with {SpecialistEvidence=null});}
        catch(ArgumentException z){noEvidence=z.Message=="PROSPECTIVE_SPECIALIST_EVIDENCE_REQUIRED";}
        check(noEvidence && session.Ledger.Summary().CashEur==300m &&
              session.Ledger.Summary().PendingIntents==0,
              "future prospective gate cannot silently use the legacy ungated research decision path");
        var admitted=session.DecideProspective(Decision("accepted-synthetic",new[]{ex,ey}));
        check(admitted.Selection.Allocations.Length==2 &&
            admitted.Selection.Allocations.Single(z=>z.Id==x.Id).Units==2 &&
            admitted.Selection.Allocations.Single(z=>z.Id==y.Id).Units==1 &&
            admitted.Ledger.PendingIntents==2 && admitted.Ledger.CashEur==300m &&
            admitted.PendingMarginReservedEur==65m && !admitted.Qualified && !admitted.OrdersEnabled,
            "positive specialist preflight reaches same common allocation and one EUR300 funded intent ledger");
        session=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        var repeated=session.DecideProspective(Decision("accepted-synthetic",new[]{ex,ey}));
        check(System.Text.Json.JsonSerializer.Serialize(repeated)==System.Text.Json.JsonSerializer.Serialize(admitted) && session.Ledger.Summary().PendingIntents==2,
            "identical prospective decision after restart cannot allocate twice");
        long t=clock;
        session.ApplyResearchFacts(new[]{
            E("open-A",t+2000,"OPEN_FILL",x.Id,x.Symbol,1,2m,10.025m,.1m,20m,.005m,
                new[]{Q("SYNTH_A",t+2000,10m),Q("SYNTH_B",t+2000,20m)}),
            E("open-B",t+2100,"OPEN_FILL",y.Id,y.Symbol,-1,1m,19.99m,.1m,25m,.01m,
                new[]{Q("SYNTH_A",t+2100,10m),Q("SYNTH_B",t+2100,20m)})});
        var entered=session.Ledger.Summary();
        check(entered.OpenPositions==2 && entered.CashEur==299.8m &&
              entered.UsedMarginEur==65m && entered.LiquidationEquityEur<300m,
              "two distinct concurrent physical-volume positions debit only entry commissions; floating exposure is marked BID/ASK");
        session.ApplyResearchFacts(new[]{
            E("adverse-floating-mark",t+3000,"MARK",quotes:new[]{
                Q("SYNTH_A",t+3000,9.9m),Q("SYNTH_B",t+3000,20.1m)}),
            E("carry-A",t+3000,"FINANCING",x.Id,x.Symbol,1,2m,financing:-.05m),
            E("carry-B",t+3001,"FINANCING",y.Id,y.Symbol,-1,1m,financing:.02m)});
        check(session.Ledger.Summary().MaximumSampledDrawdown>0m,
            "native marked equity captures an interim drawdown instead of using closed NET only");
        session=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        session.ApplyResearchFacts(new[]{
            E("close-request-A",t+4000,"REQUEST_CLOSE",x.Id,x.Symbol,1,2m),
            E("partial-A",t+5100,"CLOSE_FILL",x.Id,x.Symbol,1,1m,10.995m,.1m,20m,.005m,
                new[]{Q("SYNTH_A",t+5100,11m),Q("SYNTH_B",t+5100,20m)})});
        check(session.Ledger.Summary().OpenPositions==2 &&
              session.Ledger.Summary().CompleteRoundTrips==0 &&
              session.Ledger.ClosedFragments().Length==1 &&
              !session.Ledger.ClosedFragments()[0].CompletesRoundTrip,
              "partial settlement changes cash and volume but not completed HARD21 trade count");
        session.ApplyResearchFacts(new[]{
            E("final-A",t+6100,"CLOSE_FILL",x.Id,x.Symbol,1,1m,10.995m,.1m,20m,.005m,
                new[]{Q("SYNTH_A",t+6100,11m),Q("SYNTH_B",t+6100,20m)}),
            E("close-request-B",t+7000,"REQUEST_CLOSE",y.Id,y.Symbol,-1,1m),
            E("final-B",t+8100,"CLOSE_FILL",y.Id,y.Symbol,-1,1m,19.05m,.1m,25m,.01m,
                new[]{Q("SYNTH_B",t+8100,19m)})});
        var settled=session.Ledger.Summary();
        check(settled.CashEur==302.256m && settled.LiquidationEquityEur==302.256m &&
            settled.FreeMarginEur==302.256m && settled.UsedMarginEur==0 &&
            settled.ClosedNetEur==2.256m && settled.OpenPositions==0 &&
            settled.PendingIntents==0 && settled.CompleteRoundTrips==2 &&
            !settled.GlobalDrawdownCertified && !settled.BrokerStateReconciled &&
            !settled.OrdersEnabled,
            "positive forecast-to-native-fills net exactly reconciles independent EUR300 event oracle, without broker qualification");
        var final=session.Ledger.ClosedFragments();
        check(final.Length==3 && final.Count(z=>z.CompletesRoundTrip)==2 &&
              final[0].NetEur==.795m && final[1].NetEur==.795m && final[2].NetEur==.666m,
              "two partial A close fragments and one B close reconcile each EUR cash component independently");
        session=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        var before=session.Ledger.Summary();
        session.ApplyResearchFacts(new[]{
            E("final-B",t+8100,"CLOSE_FILL",y.Id,y.Symbol,-1,1m,19.05m,.1m,25m,.01m,
                new[]{Q("SYNTH_B",t+8100,19m)})});
        check(session.Ledger.Summary()==before && before.CompleteRoundTrips==2 &&
              before.MaximumSampledDrawdown>0,
              "completed accounting, accumulated risk and trade counter persist through restart and duplicate");
    }
}
