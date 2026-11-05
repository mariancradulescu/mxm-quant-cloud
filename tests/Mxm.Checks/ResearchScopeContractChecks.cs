using Mxm.Core;

static class ResearchScopeContractChecks
{
    public static void Run(Action<bool,string> check)
    {
        var definitions=ResearchScopeContract.Definitions;
        check(definitions.Length==9 &&
            definitions.Select(d=>d.Scope).Distinct(StringComparer.Ordinal).Count()==definitions.Length &&
            definitions.All(d=>d.Horizons.Length>0 && d.Horizons.Distinct().Count()==d.Horizons.Length),
            "canonical research scope/horizon identities are unique and nonempty");
        var sizing=new ScenarioSizingInputs(300,300,300,1,1,1,20,1,2,0);
        ResearchOrchestrationRequest Request(string scope,int horizon)=>new(scope,horizon,1000,sizing,
            new[]{new PortfolioScenario("A",100,true,0,0,0,0),
                  new PortfolioScenario("B",100,true,0,0,0,0)},
            Array.Empty<EconomicOpportunity>(),true,Array.Empty<string>());
        foreach(var definition in definitions)
            foreach(var horizon in definition.Horizons)
            {
                ResearchScopeContract.Require(definition.Scope,horizon);
                var result=OpportunityOrchestrator.Estimate(Request(definition.Scope,horizon));
                check(!result.Qualified && result.Allocations.Length==0,
                    "registered scope/horizon reaches the same unqualified native orchestrator");
                bool permitted=true;
                try{ResearchScopeContract.RequireBatch(new[]{Request(definition.Scope,horizon)});}
                catch(ArgumentException){permitted=false;}
                check(permitted==definition.BatchEnabled,
                    "native batch and orchestrator agree on registered scope and horizon");
            }
        check(definitions.Any(d=>d.Scope=="PVE1_CALENDAR_CONDITIONAL_RESEARCH_NOT_CERTIFIED"&&d.BatchEnabled),
            "closed PVE1 declared scope is synthetically reachable without re-scoring the study");
        bool wrongHorizon=false,unknownScope=false,oversizedBatch=false;
        try{ResearchScopeContract.Require("PVE2_DAILY_PULLBACK_EUR300_CONDITIONAL_ONLY_NOT_CERTIFIED",60);}
        catch(ArgumentException){wrongHorizon=true;}
        try{OpportunityOrchestrator.Estimate(Request("UNREGISTERED_FUTURE_STUDY",0));}
        catch(ArgumentException ex){unknownScope=ex.Message=="UNDECLARED_CONDITIONAL_RESEARCH_SCOPE";}
        try{ResearchScopeContract.RequireBatch(Enumerable.Repeat(Request(
            "PVE2_DAILY_PULLBACK_EUR300_CONDITIONAL_ONLY_NOT_CERTIFIED",0),6).ToArray());}
        catch(ArgumentException){oversizedBatch=true;}
        check(wrongHorizon && unknownScope && oversizedBatch,
            "future undeclared scope, invalid horizon and oversized batch fail closed");
    }
}
