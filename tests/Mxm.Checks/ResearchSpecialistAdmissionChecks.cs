using Mxm.Core;

static class ResearchSpecialistAdmissionChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long clock=100;
        var account=new ScenarioSizingInputs(200,200,200,1,1,1,10,1,2,0);
        var grid=new AdaptiveRiskInputs(200,0,200,1,1,1,10,0,false,false,2,0);
        var states=new[]{
            new PortfolioScenario("A",20,true,0,0,0,0),
            new PortfolioScenario("B",20,true,0,0,0,0)};
        var scenarios=new[]{
            new OpportunityScenario("A",20,true,.2m,0,.1m,.1m),
            new OpportunityScenario("B",20,true,.2m,0,.1m,.1m)};
        var opp=new EconomicOpportunity("ONE","SCOUT","EURUSD","ONE",1,80,40,
            EvidenceLevel.Preliminary,false,grid,scenarios);
        var request=new ResearchOrchestrationRequest("NATIVE_FUNDED_CYCLE_DEVELOPMENT_NOT_CERTIFIED",
            0,clock,account,states,new[]{opp},true,new[]{"ONE"});
        var e=new SpecialistEuroEvidence("ONE",70,70,5,60,true,true,true,true,false,
            1m,.1m,.1m,.1m,.1m,.1m,.1m,.1m,10m);
        var ok=ResearchSpecialistAdmission.Inspect(clock,opp,e);
        check(ok.AdmittedForConditionalResearch && ok.IncrementalLowerEur==.3m,
            "known research EUR cost and uncertainty must clear neutral benchmark");
        var priced=ResearchSpecialistAdmission.Inspect(clock,opp,e with {
            PricesAlreadyContainBidAsk=true});
        check(priced.ExtraSpreadEur==0m && priced.IncrementalLowerEur==.4m,
            "already executable BID/ASK price cannot charge spread again");
        check(ResearchSpecialistAdmission.Inspect(clock,opp,e with {
            FinancingEur=null}).Reason=="SPECIALIST_UNKNOWN_EUR_COST_OR_FINANCING",
            "missing historical financing cannot be invented as zero");
        check(!ResearchSpecialistAdmission.Inspect(clock,opp,e with {
            SupportedVsBenchmark=false}).AdmittedForConditionalResearch,
            "gross amplitude does not imply predictive skill");
        check(!ResearchSpecialistAdmission.Inspect(clock,opp,e with {
            CostKnownAt=clock+1}).AdmittedForConditionalResearch,
            "future contract cost observation cannot enter old clock");
        check(!ResearchSpecialistAdmission.Inspect(clock,opp,e with {
            GrossAboveBenchmarkEur=.2m}).AdmittedForConditionalResearch,
            "insufficient alpha versus fees is rejected");
        var routed=ResearchSpecialistAdmission.Estimate(request,new[]{e});
        check(routed.NativeAllocation.Allocations.Length==1 &&
            routed.NativeAllocation.ReservedMarginEur==10m &&
            !routed.NativeAllocation.Qualified && !routed.OrdersEnabled &&
            !routed.IndependentConfirmation && !routed.FundedNetCertified,
            "only existing native one-capital selector sizes conditional evidence");
        var blocked=ResearchSpecialistAdmission.Estimate(request,new[]{e with {FinancingEur=null}});
        check(blocked.NativeAllocation.Allocations.Length==0 &&
              blocked.NativeAllocation.Declined.Single().Reason=="SPECIALIST_UNKNOWN_EUR_COST_OR_FINANCING",
              "skeptic prevents unsupported opportunity reaching native allocator");
        // A positive specialist estimate must not let an optimistic, separately
        // priced scenario silently manufacture excess expected EUR NET.
        var optimistic=opp with {Scenarios=opp.Scenarios.Select(s=>s with {
            NetPerUnitEur=2m}).ToArray()};
        var incompatible=ResearchSpecialistAdmission.Estimate(request with {
            Opportunities=new[]{optimistic}},new[]{e});
        check(incompatible.NativeAllocation.Allocations.Length==0 &&
              incompatible.NativeAllocation.Declined.Single().Reason=="SPECIALIST_SCENARIO_NET_EXCEEDS_EVIDENCE",
              "incompatible optimistic scenario matrix cannot bypass EUR benchmark and cost gate");
        var wrongHorizon=ResearchSpecialistAdmission.Estimate(request with {
            Scope="EPA2_CONDITIONAL_RESEARCH_NOT_CERTIFIED",CommonHorizonMinutes=120},new[]{e});
        check(wrongHorizon.NativeAllocation.Allocations.Length==0 &&
              wrongHorizon.NativeAllocation.Declined.Single().Reason=="SPECIALIST_HORIZON_SCENARIO_MISMATCH",
              "specialist holding time must match common scenario horizon when declared");
        // The original EUR200 is not a permanent margin ceiling once the
        // same continuous capital has earned more; current free margin still rules.
        var grownGrid=grid with {MarginPerUnitEur=210m};
        var grownOpp=opp with {VolumeGrid=grownGrid};
        var grownEvidence=e with {CurrentMinMarginEur=210m};
        var grownRequest=request with {Account=account with {
            EquityEur=320m,PeakReferenceEur=320m,FreeMarginEur=320m},
            Opportunities=new[]{grownOpp}};
        var grown=ResearchSpecialistAdmission.Estimate(grownRequest,new[]{grownEvidence});
        check(grown.NativeAllocation.Allocations.Length==1 &&
              grown.NativeAllocation.ReservedMarginEur==210m,
              "continuous profitable capital may finance a broker minimum margin above initial EUR200");
        var lowFree=ResearchSpecialistAdmission.Estimate(grownRequest with {
            Account=grownRequest.Account with {FreeMarginEur=200m}},new[]{grownEvidence});
        check(lowFree.NativeAllocation.Allocations.Length==0 &&
              lowFree.NativeAllocation.Declined.Single().Reason=="SPECIALIST_CURRENT_FREE_MARGIN_INSUFFICIENT",
              "same higher-margin contract is refused without adequate current free margin");
    }
}
