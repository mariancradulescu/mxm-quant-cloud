using System.Text.Json;
namespace Mxm.Core;

// Frozen SYSTEM development probe JOP1: all six source instruments, H4,
// two fixed causal descriptors (six-bar drift and last-bar reversal). No fit,
// parameter search, survivor selection, historical model import or NET proxy.
public static class JointOpportunityResearch
{
    public sealed record Observation(string Candidate,string Symbol,long Clock,long Exit,int Side,double? GrossBps);
    public static Observation[] Describe(RegimeDiscovery.Bar[] source)
    {
        var result=new List<Observation>();
        foreach(var g in source.Where(b=>b.Tf=="H4").GroupBy(b=>b.Symbol).OrderBy(g=>g.Key,StringComparer.Ordinal))
        {
            var bars=g.OrderBy(b=>b.T).ToArray();
            if(bars.Length<20)continue;
            // Only the first 80% of previously exposed source. Last20 remains
            // unscored; even that last20 is NOT declared independent by default.
            long stop=bars[0].T+(bars[^1].End-bars[0].T)*8/10;
            for(int i=6;i<bars.Length;i++)
            {
                var b=bars[i];
                var next=i+1<bars.Length && bars[i+1].T==b.End ? bars[i+1] : null;
                long plannedExit=b.End+14400000L;
                if(plannedExit>=stop || !Enumerable.Range(i-5,6).All(j=>bars[j].T==bars[j-1].End))continue;
                int drift=Math.Sign(b.C-bars[i-6].C),reversal=-Math.Sign(b.C-b.O);
                foreach(var (family,side) in new[]{("JOP1_SIX_BAR_DRIFT",drift),("JOP1_LAST_BAR_REVERSAL",reversal)})
                    if(side!=0)result.Add(new(family,g.Key,b.End,plannedExit,side,
                        next!=null && next.End==plannedExit ? side*(next.C/next.O-1)*10000 : null));
            }
        }
        return result.OrderBy(r=>r.Clock).ThenBy(r=>r.Symbol,StringComparer.Ordinal).ThenBy(r=>r.Candidate,StringComparer.Ordinal).ToArray();
    }
    public static object Assess(JsonElement source)
    {
        var bars=RegimeDiscovery.Read(source);var rows=Describe(bars);
        var groups=rows.GroupBy(r=>(r.Candidate,r.Symbol)).ToArray();
        // Execute the SAME native selector at every multi-asset clock. The
        // source only has sparse quote samples, not full H4 event execution
        // evidence, so no invented costs/scenarios may open a funded position.
        var account=new AdaptiveRiskInputs(200,200,200,1,1,1,1,.5m,true,false,2,3);
        var baseline=new[]{new PortfolioScenario("UNPROVEN_A",0,true,0,0,0,0),new PortfolioScenario("UNPROVEN_B",0,true,0,0,0,0)};
        int admitted=0,blocked=0,simultaneous=0,conflicting=0;
        foreach(var batch in rows.GroupBy(r=>r.Clock))
        {
            var a=batch.Select(r=>new EconomicOpportunity($"{r.Candidate}/{r.Symbol}/{r.Clock}",r.Candidate,r.Symbol,
                $"{r.Symbol}/{r.Clock}/{r.Side}",r.Side,r.Clock,r.Clock-1,EvidenceLevel.Exploratory,false,account,
                Array.Empty<OpportunityScenario>())).ToArray();
            var result=OpportunityOrchestrator.Select(batch.Key,account,baseline,a);
            admitted+=result.Allocations.Length;blocked+=result.Declined.Length;
            if(batch.Select(r=>r.Symbol).Distinct().Count()>1)simultaneous++;
            conflicting+=batch.GroupBy(r=>r.Symbol).Count(g=>g.Select(r=>r.Side).Distinct().Count()>1);
        }
        return new {schema="mxm-joint-opportunity-development-v1",sourceRunId=41476636915L,
            study="JOP1_ALL_SOURCE_ASSETS_H4_TWO_FIXED_DESCRIPTORS_FIRST80_NO_SELECTION",
            evidenceLevel=1,priorCalendarExposure="GLOBAL_DEVELOPMENT_EXPOSED_NOT_INDEPENDENT",
            opportunities=rows.Length,causalDecisionClocks=rows.Select(r=>r.Clock).Distinct().Count(),
            simultaneousMultiAssetClocks=simultaneous,contradictorySymbolClocks=conflicting,
            sourceInstrumentCount=bars.Select(b=>b.Symbol).Distinct().Count(),
            results=groups.Select(g=>new {candidate=g.Key.Candidate,symbol=g.Key.Symbol,observations=g.Count(),
                labeledObservations=g.Count(r=>r.GrossBps.HasValue),
                meanDirectionalGrossBps=g.Average(r=>r.GrossBps),positiveFraction=g.Any(r=>r.GrossBps.HasValue) ?
                    (double?)g.Count(r=>r.GrossBps>0)/g.Count(r=>r.GrossBps.HasValue) : null,
                status="GROSS_PRICE_DESCRIPTOR_NOT_EXECUTABLE_NET"}).ToArray(),
            nativeSelectorAdmitted=admitted,nativeSelectorEvidenceBlocked=blocked,
            commonFundedReplayStarted=false,initialCapitalEur=200,endingNoTradeCapitalEur=200,
            netOpportunityEstimateEur=(decimal?)null,incrementalContributionDemonstrated=false,
            independentConfirmation=false,hard21Proven=false,globalDrawdownCertified=false,
            missing="Historical H4 entry/exit BID+ASK, synchronized holding marks, historical tariffs, conversion, financing and joint EUR risk samples",
            unexposedEvaluatedCalendarMonths=0,ordersSubmitted=0,economicQualification=false};
    }
}
