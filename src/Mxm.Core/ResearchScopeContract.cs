namespace Mxm.Core;

// One active C# source of truth for research-only scope/horizon support.
// The replay CLI and the orchestrator must use this SAME table; adding a
// Python adapter alone never authorizes a new scope or a funded certificate.
public sealed record ResearchScopeDefinition(string Scope,int[] Horizons,bool BatchEnabled);
public static class ResearchScopeContract
{
    private static readonly ResearchScopeDefinition[] Rules =
    {
        new("EPA1_CONDITIONAL_RESEARCH_NOT_CERTIFIED",new[]{240},false),
        new("EPA2_CONDITIONAL_RESEARCH_NOT_CERTIFIED",new[]{120,240},false),
        new("SQP1_CONDITIONAL_RESEARCH_NOT_CERTIFIED",new[]{60},false),
        new("IPF1_MULTI_HORIZON_CONDITIONAL_RESEARCH_NOT_CERTIFIED",new[]{0},true),
        new("NATIVE_FUNDED_CYCLE_DEVELOPMENT_NOT_CERTIFIED",new[]{0},false),
        new("RCP1_GLOBAL_RISK_DELAYED_FILL_CONDITIONAL_NOT_CERTIFIED",new[]{0},true),
        new("TWC1_CALENDAR_CONDITIONAL_RESEARCH_NOT_CERTIFIED",new[]{0},true),
        // Previously declared in PVE1 Python but missing from BOTH C# allowlists.
        // Admission is for synthetic compatibility checks only: PVE1 is CLOSED.
        new("PVE1_CALENDAR_CONDITIONAL_RESEARCH_NOT_CERTIFIED",new[]{0},true),
        new("PVE2_DAILY_PULLBACK_EUR300_CONDITIONAL_ONLY_NOT_CERTIFIED",new[]{0},true)
    };
    public static ResearchScopeDefinition[] Definitions=>Rules.Select(r=>
        new ResearchScopeDefinition(r.Scope,r.Horizons.ToArray(),r.BatchEnabled)).ToArray();
    public static void Require(string scope,int commonHorizonMinutes)
    {
        if(!Rules.Any(r=>r.Scope==scope && r.Horizons.Contains(commonHorizonMinutes)))
            throw new ArgumentException("UNDECLARED_CONDITIONAL_RESEARCH_SCOPE");
    }
    public static void RequireBatch(ResearchOrchestrationRequest[] requests)
    {
        if(requests is null || requests.Length>5 ||
           requests.Any(r=>r is null || !Rules.Any(rule=>rule.BatchEnabled &&
               rule.Scope==r.Scope && rule.Horizons.Contains(r.CommonHorizonMinutes))))
            throw new ArgumentException("UNDECLARED_CONDITIONAL_BATCH_SCOPE");
        foreach(var request in requests)Require(request.Scope,request.CommonHorizonMinutes);
    }
}
