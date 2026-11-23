using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Prospective ONLY: a reporting/evidence contract for the EXISTING C# funded
// portfolio engine. No detector, allocator, exit policy, broker order or replay.
// The closed RVC1 original has no published per-episode records: NEVER call
// this on reconstructed/hypothetical RVC1 individual trades.
public enum NativeJointExitCause
{
    Convergence,StructuralInvalidation,ObservedProtectivePrice,
    CapitalProtection,OrphanProtection,GapRecovery,OtherObservedCause
}

public sealed record NativeJointOpportunityEntry(
    string EpisodeId,long DecisionAt,long FillAt,
    string SourceEvidenceHash, string EconomicThesis,
    int RequiredLegs,decimal ProjectedRewardEur,decimal ReservedRiskEur,
    decimal ResidualUsdNotional,decimal ReservedMarginEur,
    bool FullyFundableAtEntry);

public sealed record NativeJointOpportunityMark(
    long ObservedAt,long SourceClosedAt,
    decimal? JointLiquidationGrossEur,
    bool WholeBookQuoteAndFxKnown);

public sealed record NativeJointOpportunityLegClose(
    string PositionId,long OpenedAt,long ClosedAt,
    decimal GrossEur,decimal? NetEur,
    bool FinancingAndCostsKnown);

public sealed record NativeJointOpportunityEpisodeEvidence(
    string EpisodeId,bool CompletePair,bool ConditionalGrossKnown,
    bool ConditionalNetKnown,int ExpectedLegs,int ClosedLegs,
    decimal ProjectedRewardEur,decimal ReservedRiskEur,
    decimal ProjectedRewardRisk,
    decimal? ClosedGrossEur,decimal? ClosedNetEur,
    decimal? RealizedGrossR,decimal? RealizedNetR,
    long? DurationMs,decimal? SampledMfeEur,decimal? SampledMaeEur,
    bool MarkCoverageComplete,NativeJointExitCause? ExitCause,
    int UnknownMarkClocks,string EvidenceStatus);

public static class NativeJointOpportunityEvidence
{
    public static NativeJointOpportunityEpisodeEvidence Evaluate(
        NativeJointOpportunityEntry entry,
        IReadOnlyList<NativeJointOpportunityMark> marks,
        IReadOnlyList<NativeJointOpportunityLegClose> closed,
        NativeJointExitCause? exitCause,
        bool noUnwitnessedMarketIntervals)
    {
        ArgumentNullException.ThrowIfNull(entry);
        ArgumentNullException.ThrowIfNull(marks);
        ArgumentNullException.ThrowIfNull(closed);
        if(string.IsNullOrWhiteSpace(entry.EpisodeId)||
           string.IsNullOrWhiteSpace(entry.EconomicThesis)||
           string.IsNullOrWhiteSpace(entry.SourceEvidenceHash)||
           entry.DecisionAt<0||entry.FillAt<=entry.DecisionAt||
           entry.RequiredLegs<1||entry.ProjectedRewardEur<0m||
           entry.ReservedRiskEur<=0m||entry.ReservedMarginEur<=0m||
           !entry.FullyFundableAtEntry)
            throw new ArgumentException("JOINT_DIAGNOSTIC_UNFUNDED_OR_RISK_UNVERIFIED");

        var ids=new HashSet<string>(StringComparer.Ordinal);
        long previous=entry.FillAt;
        int unknown=0;
        var verifiedMarks=new List<decimal>();
        foreach(var mark in marks)
        {
            if(mark.ObservedAt<entry.FillAt||mark.ObservedAt<=previous||
               mark.SourceClosedAt>mark.ObservedAt||
               mark.SourceClosedAt<entry.FillAt)
                throw new ArgumentException("JOINT_DIAGNOSTIC_NONCAUSAL_MARK");
            previous=mark.ObservedAt;
            if(!mark.WholeBookQuoteAndFxKnown||
               mark.JointLiquidationGrossEur is null){unknown++;continue;}
            verifiedMarks.Add(mark.JointLiquidationGrossEur.Value);
        }
        foreach(var leg in closed)
        {
            if(string.IsNullOrWhiteSpace(leg.PositionId)||
               !ids.Add(leg.PositionId)||leg.OpenedAt<entry.FillAt||
               leg.ClosedAt<leg.OpenedAt)
                throw new ArgumentException("JOINT_DIAGNOSTIC_BAD_LEG_CLOSURE");
        }
        if(closed.Count>entry.RequiredLegs)
            throw new ArgumentException("JOINT_DIAGNOSTIC_MORE_LEGS_THAN_OPENED");
        bool complete=closed.Count==entry.RequiredLegs;
        if(complete && (exitCause is null ||
             closed.Any(x=>x.ClosedAt<entry.FillAt)))
            throw new ArgumentException("JOINT_DIAGNOSTIC_EXIT_PROVENANCE_REQUIRED");
        if(!complete&&exitCause is not null)
            throw new ArgumentException("JOINT_DIAGNOSTIC_UNSETTLED_CANNOT_CLAIM_EXIT");
        decimal? gross=complete?closed.Sum(x=>x.GrossEur):null;
        bool netKnown=complete&&closed.All(x=>x.FinancingAndCostsKnown&&x.NetEur.HasValue);
        decimal? net=netKnown?closed.Sum(x=>x.NetEur!.Value):null;
        long? duration=complete?closed.Max(x=>x.ClosedAt)-entry.FillAt:null;
        bool marksComplete=noUnwitnessedMarketIntervals&&unknown==0&&marks.Count>0;
        // A mark is only a witnessed, as-of source-close liquidation
        // observation; it is NOT a reconstructed intrabar extreme.
        decimal? mfe=verifiedMarks.Count>0?Math.Max(0m,verifiedMarks.Max()):null;
        decimal? mae=verifiedMarks.Count>0?Math.Min(0m,verifiedMarks.Min()):null;
        return new NativeJointOpportunityEpisodeEvidence(
            entry.EpisodeId,complete,complete,netKnown,
            entry.RequiredLegs,closed.Count,
            entry.ProjectedRewardEur,entry.ReservedRiskEur,
            entry.ProjectedRewardEur/entry.ReservedRiskEur,
            gross,net,gross/entry.ReservedRiskEur,net/entry.ReservedRiskEur,
            duration,mfe,mae,marksComplete,complete?exitCause:null,
            unknown,!complete?"UNSETTLED_OR_PARTIAL_PAIR":
                !netKnown?"FINANCING_OR_COSTS_UNKNOWN_CANNOT_SCORE_NET":
                !marksComplete?"COMPLETE_CASH_BUT_SAMPLE_MARKS_INCOMPLETE":
                "COMPLETE_CONDITIONAL_MODELED_EPISODE");
    }

    // Return UNKNOWN (null) rather than fit a "win rate" or expectancy on
    // missing/censored outcomes. The hard count below is a diagnostic minimum,
    // not a hyperparameter to be retuned after outcomes.
    public static object Distribution(
        IReadOnlyList<NativeJointOpportunityEpisodeEvidence> episodes,
        int minimumCompleteObservations=20)
    {
        ArgumentNullException.ThrowIfNull(episodes);
        if(minimumCompleteObservations<20)
            throw new ArgumentException("JOINT_DIAGNOSTIC_MIN_SAMPLE_UNDER20");
        if(episodes.GroupBy(x=>x.EpisodeId,StringComparer.Ordinal).Any(x=>x.Count()!=1))
            throw new ArgumentException("JOINT_DIAGNOSTIC_DUPLICATE_PAIR");
        var settled=episodes.Where(x=>x.CompletePair&&x.ConditionalNetKnown).ToArray();
        if(settled.Length<minimumCompleteObservations)
            return new {Episodes=episodes.Count,Settled=settled.Length,
                Unknown=episodes.Count-settled.Length,WinRate=(decimal?)null,
                MeanGrossEur=(decimal?)null,MeanNetEur=(decimal?)null,
                MeanRealizedNetR=(decimal?)null,Qualification="INSUFFICIENT_SETTLED_EPISODES"};
        return new {Episodes=episodes.Count,Settled=settled.Length,
            Unknown=episodes.Count-settled.Length,
            WinRate=(decimal?)settled.Count(x=>x.ClosedNetEur>0m)/(decimal)settled.Length,
            MeanGrossEur=(decimal?)settled.Average(x=>x.ClosedGrossEur!.Value),
            MeanNetEur=(decimal?)settled.Average(x=>x.ClosedNetEur!.Value),
            MeanRealizedNetR=(decimal?)settled.Average(x=>x.RealizedNetR!.Value),
            Qualification="CONDITIONAL_ONLY_NO_INDEPENDENCE_OR_INTRABAR_CERTIFICATE"};
    }
}
