using System;
using System.Linq;
using Mxm.Core;

// No historical RVC1 execution or new economic research: synthetic-only
// source/episode diagnostic invariants and pair cardinality evidence.
public static class NativeJointOpportunityEvidenceChecks
{
    static bool Throws(Action run)
    {
        try{run();return false;}
        catch(ArgumentException){return true;}
    }

    public static void Run(Action<bool,string> check)
    {
        var entry=new NativeJointOpportunityEntry(
            "PAIR-A",900,1000,"SYNTHETIC_HASH","JOINT_INVENTORY",
            2,2.0m,1.0m,100m,65m,true);
        var marks=new[]{
            new NativeJointOpportunityMark(1100,1050,.8m,true),
            new NativeJointOpportunityMark(1200,1150,-.4m,true)
        };
        var a=new NativeJointOpportunityLegClose("EUR",1000,1300,4m,.3m,true);
        var b=new NativeJointOpportunityLegClose("GBP",1000,1300,-3m,-.1m,true);
        var full=NativeJointOpportunityEvidence.Evaluate(entry,marks,
            new[]{a,b},NativeJointExitCause.Convergence,true);
        check(full.CompletePair&&full.ExpectedLegs==2&&full.ClosedLegs==2&&
            full.ProjectedRewardRisk==2m&&full.ClosedGrossEur==1m&&
            full.ClosedNetEur==.2m&&full.RealizedNetR==.2m&&
            full.DurationMs==300&&full.SampledMfeEur==.8m&&
            full.SampledMaeEur==-.4m&&full.MarkCoverageComplete&&
            full.ExitCause==NativeJointExitCause.Convergence,
            "Joint two-leg EUR payoff/initial risk/modeled R/MFE/MAE and one complete episode");
        var partial=NativeJointOpportunityEvidence.Evaluate(entry,marks,
            new[]{a},null,true);
        check(!partial.CompletePair&&partial.ClosedGrossEur is null&&
            partial.ClosedNetEur is null&&partial.RealizedNetR is null&&
            partial.ExitCause is null,
            "Unsettled single leg of pair cannot count as a completed joint opportunity");
        var unknownFinance=NativeJointOpportunityEvidence.Evaluate(entry,marks,
            new[]{a,b with {NetEur=null,FinancingAndCostsKnown=false}},
            NativeJointExitCause.CapitalProtection,true);
        check(unknownFinance.CompletePair&&unknownFinance.ConditionalGrossKnown&&
            !unknownFinance.ConditionalNetKnown&&
            unknownFinance.ClosedGrossEur==1m&&
            unknownFinance.ClosedNetEur is null&&unknownFinance.RealizedNetR is null,
            "Protective close with missing overnight financing retains gross but never invents NET");
        var uncertain=NativeJointOpportunityEvidence.Evaluate(entry,
            new[]{new NativeJointOpportunityMark(1100,1050,null,false)},
            new[]{a,b},NativeJointExitCause.ObservedProtectivePrice,false);
        check(uncertain.UnknownMarkClocks==1&&!uncertain.MarkCoverageComplete&&
            uncertain.SampledMfeEur is null&&uncertain.SampledMaeEur is null,
            "Unknown future/gap exposure not scored as zero MFE/MAE");
        check(Throws(()=>NativeJointOpportunityEvidence.Evaluate(entry,
            new[]{new NativeJointOpportunityMark(1100,1120,.3m,true)},
            new[]{a,b},NativeJointExitCause.Convergence,true)),
            "A future-unclosed source bar cannot be used as an observed mark");
        check(Throws(()=>NativeJointOpportunityEvidence.Evaluate(entry,
            new[]{new NativeJointOpportunityMark(1400,1200,9m,true)},
            new[]{a,b},NativeJointExitCause.Convergence,true)),
            "A post-closure favorable mark is hindsight and cannot inflate MFE");
        check(Throws(()=>NativeJointOpportunityEvidence.Evaluate(entry,marks,
            new[]{a,a},NativeJointExitCause.Convergence,true)),
            "Both legs need distinct financed PositionId witnesses");
        check(Throws(()=>NativeJointOpportunityEvidence.Evaluate(
            entry with {ReservedRiskEur=0m},marks,new[]{a,b},
            NativeJointExitCause.Convergence,true)),
            "Zero/unknown financial risk cannot produce an inflated RR or R");
        var distribution=NativeJointOpportunityEvidence.Distribution(
            new[]{full,partial,unknownFinance});
        check(distribution is not null &&
            distribution.ToString()!.Contains("INSUFFICIENT_SETTLED_EPISODES"),
            "Three synthetic episodes cannot be misadvertised as stable win probability");
    }
}
