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
            new OpportunityScenario("A",20,true,.5m,0,.1m,.1m),
            new OpportunityScenario("B",20,true,.5m,0,.1m,.1m)};
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
        check(priced.AdditionalSpreadEur==0m && priced.IncrementalLowerEur==.4m,
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
    }
}
