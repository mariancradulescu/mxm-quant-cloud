using Mxm.Core;
using System.Text.Json;
static class FundedDecisionCycleChecks
{
    public static void Run(Action<bool,string> check)
    {
        const string proof="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        var session=new NativeFundedSession("SYNTHETIC_CYCLE");
        LedgerQuote Q(string s,long at,decimal bid=10)=>new(s,at,bid,bid+.01m,1,1,0,.1m,20);
        LedgerEvent E(string id,long at,string kind,string pid,string symbol,decimal units=1,decimal price=0,LedgerQuote[]? quotes=null)=>
            new(id,at,kind,pid,symbol,1,units,price,.1m,20,0,0,0,1000,"CONTRACT_TEST",proof,quotes??Array.Empty<LedgerQuote>());
        var grid=new AdaptiveRiskInputs(999,0,999,1,1,1,20,0,false,false,2,0);
        var sizing=new ScenarioSizingInputs(999,999,999,1,1,1,20,1,2,0);
        var empty=new[]{new PortfolioScenario("A",100,true,0,0,0,0),new PortfolioScenario("B",100,true,0,0,0,0)};
        EconomicOpportunity O(string id,string s)=>new(id,"CONTRACT_TEST",s,id,1,900,100,EvidenceLevel.Exploratory,false,grid,
            new[]{new OpportunityScenario("A",100,true,5,0,1,0),new OpportunityScenario("B",100,true,6,0,1,0)});
        NativeResearchDecision D(string id,long clock,EconomicOpportunity[] offered,ResearchExposureScenarios[]? held=null)=>
            new(id,clock,sizing,empty,offered,held??Array.Empty<ResearchExposureScenarios>(),
                offered.Select(o=>new ResearchEntryTerms(o.Id,1000,0,proof)).ToArray(),proof);
        session.ApplyResearchFacts(new[]{E("mark",1000,"MARK","","",quotes:new[]{Q("X",1000),Q("Y",1000)})});
        // Verify the actual NativeFundedSession decision path: a specialist
        // negative/unknown economic input cannot create even a modeled intent.
        var observedOnly=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        var scout=O("known-negative","X");
        var evidence=new SpecialistEuroEvidence(scout.Id,700,700,5,60,
            true,false,true,true,false,-.1m,null,null,null,null,null,null,null,20m);
        var noEdge=D("real-gate-no-edge",1000,new[]{scout}) with {
            SpecialistEvidence=new[]{evidence}};
        var rejected=observedOnly.DecideResearch(noEdge);
        check(rejected.Selection.Allocations.Length==0 &&
            rejected.Selection.Declined.Single().Reason=="SPECIALIST_NO_PREDICTIVE_BENCHMARK_SUPPORT" &&
            rejected.Ledger.PendingIntents==0 && rejected.Ledger.CashEur==200m,
            "economic benchmark rejection reaches common native ledger with zero new intents and unchanged cash");
        observedOnly=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        var missingFunding=D("real-gate-missing-financing",1000,new[]{scout}) with {
            SpecialistEvidence=new[]{evidence with {SupportedVsBenchmark=true,
                GrossAboveBenchmarkEur=2m,PredictionUncertaintyEur=1m,
                ObservedOneRoundTripSpreadEur=.1m,EntryFeeEur=.1m,ExitFeeEur=.1m,
                ConversionFeeEur=.1m,SlippageEur=.1m,FinancingEur=null}}};
        var unknown=observedOnly.DecideResearch(missingFunding);
        check(unknown.Selection.Allocations.Length==0 &&
            unknown.Selection.Declined.Single().Reason=="SPECIALIST_UNKNOWN_EUR_COST_OR_FINANCING" &&
            unknown.Ledger.PendingIntents==0,
            "unknown financing cannot bypass shared session to reserve capital");
        observedOnly=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        var economic=D("real-gate-complete-conditional",1000,new[]{scout}) with {
            SpecialistEvidence=new[]{evidence with {SupportedVsBenchmark=true,
                GrossAboveBenchmarkEur=10m,PredictionUncertaintyEur=1m,
                ObservedOneRoundTripSpreadEur=.1m,EntryFeeEur=.1m,ExitFeeEur=.1m,
                ConversionFeeEur=.1m,SlippageEur=.1m,FinancingEur=.1m}}};
        var beforeProspective=observedOnly.Ledger.Checkpoint();
        bool bypassRejected=false;
        try{observedOnly.DecideProspective(D("new-decision-no-gate",1000,new[]{scout}));}
        catch(ArgumentException ex){bypassRejected=ex.Message=="PROSPECTIVE_SPECIALIST_EVIDENCE_REQUIRED";}
        check(bypassRejected && observedOnly.Ledger.Checkpoint()==beforeProspective,
            "prospective path rejects missing EUR economic evidence without changing funded state");
        var conditional=observedOnly.DecideProspective(economic);
        check(conditional.Selection.Allocations.Length==1 &&
            conditional.Ledger.PendingIntents==1 && conditional.Ledger.CashEur==200m &&
            !conditional.OrdersEnabled && !conditional.Qualified,
            "supported conditional specialist shares existing EUR200 ledger and creates request only, not fill");
        // Same specialist-admitted ID through the existing one-capital modeled
        // ledger: entry BID/ASK, per-side commissions, then complete close.
        // No broker fill or real profit is implied by synthetic execution facts.
        var pricedSession=NativeFundedSession.Restore(observedOnly.Checkpoint(),observedOnly.AccountBinding);
        pricedSession.ApplyResearchFacts(new[]{
            E("specialist-fill",2000,"OPEN_FILL",scout.Id,"X",price:10.01m,
                quotes:new[]{Q("X",2000)})});
        check(pricedSession.Ledger.Summary().CashEur==199.9m &&
            pricedSession.Ledger.Summary().OpenPositions==1,
            "one specialist-admitted modeled fill debits entry fee exactly once");
        pricedSession.ApplyResearchFacts(new[]{
            E("specialist-close-request",3000,"REQUEST_CLOSE",scout.Id,"X")});
        pricedSession.ApplyResearchFacts(new[]{
            E("specialist-close-fill",4000,"CLOSE_FILL",scout.Id,"X",price:11m,
                quotes:new[]{Q("X",4000,11m)})});
        var settled=pricedSession.Ledger.Summary();
        check(settled.CashEur==200.79m && settled.ClosedNetEur==.79m &&
            settled.CompleteRoundTrips==1 && settled.OpenPositions==0 &&
            settled.PendingIntents==0 && !settled.BrokerStateReconciled && !settled.OrdersEnabled,
            "specialist forecast through common allocation, modeled fill and close reconciles EUR200 once without broker qualification");
        observedOnly=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        var negative=observedOnly.DecideResearch(economic with {Id="real-gate-negative-gross",
            SpecialistEvidence=new[]{economic.SpecialistEvidence![0] with {GrossAboveBenchmarkEur=-.2m}}});
        check(negative.Selection.Allocations.Length==0 &&
            negative.Selection.Declined.Single().Reason=="SPECIALIST_NONPOSITIVE_GROSS_EDGE",
            "negative authenticated gross prediction is not misclassified as negative trading fees");
        var decision=D("one",1000,new[]{O("px","X"),O("py","Y")});
        var first=session.DecideResearch(decision);
        var originalJson=JsonSerializer.Serialize(new {decision.Id,decision.Clock,decision.Sizing,
            decision.EmptyStates,decision.Opportunities,decision.Exposure,decision.EntryTerms,decision.EvidenceHash});
        var originalHash=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes(originalJson))).ToLowerInvariant();
        check(first.InputHash==originalHash,"legacy native research decision hash stays unchanged without specialist evidence");
        check(first.Selection.Allocations.Length==2 && first.Ledger.CashEur==200 && first.Ledger.PendingIntents==2 && first.PendingMarginReservedEur==40,
            "native selector creates two financed intents on one EUR200 ledger without inventing fills");
        session=NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
        check(JsonSerializer.Serialize(session.DecideResearch(decision))==JsonSerializer.Serialize(first) && session.Ledger.Summary().PendingIntents==2,
            "native decision receipt survives restart and deduplicates before reranking");
        bool conflict=false;
        try{session.DecideResearch(decision with {Clock=1001});}catch(ArgumentException){conflict=true;}
        check(conflict,"conflicting decision ID cannot silently resubmit intents");
        var missing=session.DecideResearch(D("missing",1001,new[]{O("pz","Z")}));
        check(missing.Selection.Allocations.Length==0 && missing.Status.Contains("PENDING_SCENARIOS"),
            "pending entries require joint economic risk before more exposure");
        var before=session.Ledger.Checkpoint();bool atomic=false;
        try{session.ApplyResearchFacts(new[]{E("fx",2000,"OPEN_FILL","px","X",price:10.01m,quotes:new[]{Q("X",2000),Q("Y",2000)}),
            E("bad",2000,"OPEN_FILL","py","Y",price:99)});}catch(ArgumentException){atomic=true;}
        check(atomic && session.Ledger.Checkpoint()==before,"invalid second fill rolls back entire native money batch");
        session.ApplyResearchFacts(new[]{E("fx",2000,"OPEN_FILL","px","X",price:10.01m,quotes:new[]{Q("X",2000),Q("Y",2000)}),
            E("fy",2000,"OPEN_FILL","py","Y",price:10.01m)});
        check(session.Ledger.Summary().OpenPositions==2 && session.Ledger.Summary().CashEur==199.8m,
            "both actual model fills enter the same existing native ledger and debit real modeled fees once");
        ResearchExposureScenarios Exposure(string pid,string s)=>new(pid,s,1,1,
            empty.Select(x=>x with {LossEur=1,MarginEur=20}).ToArray());
        var held=new[]{Exposure("px","X"),Exposure("py","Y")};
        var blocked=session.DecideResearch(D("occupied",2000,new[]{O("px2","X")},held));
        check(blocked.Selection.Allocations.Length==0 && blocked.Selection.Declined[0].Reason.Contains("HELD_OR_PENDING"),
            "current held symbols cannot be re-entered by another candidate");
        session.ApplyResearchFacts(new[]{E("gap",4000,"MARK","","")});
        var paused=session.DecideResearch(D("pause",4000,new[]{O("pz","Z")},held));
        check(paused.Selection.Allocations.Length==0 && paused.Status.Contains("MARK_UNKNOWN"),"missing current marks pause new conditional entries");
        session.ApplyResearchFacts(new[]{E("fresh",5000,"MARK","","",quotes:new[]{Q("X",5000),Q("Y",5000),Q("Z",5000)})});
        var resumed=session.DecideResearch(D("resume",5000,new[]{O("pz","Z")},held));
        check(resumed.Selection.Allocations.Length==1 && resumed.Ledger.HistoryEvidenceIncomplete,
            "fresh marks automatically restore conditional decision eligibility while missing historical path remains disclosed");
        session.ApplyResearchFacts(new[]{E("cancelZ",5001,"CONFIRMED_CANCEL","pz","Z"),
            E("closeX",6000,"REQUEST_CLOSE","px","X"),E("closeY",6000,"REQUEST_CLOSE","py","Y"),
            E("cx",7000,"CLOSE_FILL","px","X",price:11,quotes:new[]{Q("X",7000,11),Q("Y",7000,11)}),
            E("cy",7000,"CLOSE_FILL","py","Y",price:11)});
        check(session.Ledger.Summary().CompleteRoundTrips==2 && session.Ledger.Summary().CashEur==201.58m &&
            !resumed.OrdersEnabled && !resumed.Qualified,
            "full native selector-to-close lifecycle reconciles one EUR200 capital without trading qualification");
    }
}
