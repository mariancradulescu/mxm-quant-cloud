using System;
using System.Linq;
using System.Text.Json;

namespace Mxm.Core;

// Historical-only wrapper. Existing cloud/live UCP1 checkpoint format remains unchanged.
public sealed partial class NativeUnifiedPortfolioEngine
{
    const string EurResearchCheckpointVersion="EUR_RESEARCH_STATE_V1";

    sealed record Cpe1FamilyResearchState(string Family,bool FundingAware,decimal[] GrossReturns,
        long[] CloseDays,decimal? LowerBound,bool ReturnsChanged,int Settled,int Winners);

    sealed record EurResearchState(string Version,string CoreCheckpoint,string Policy,string? FundingScenarioId,
        long LastAt,NativeEurCalibrationOutcome[] History,NativeEurOpportunity[] Opportunities,
        Ucp1EurDecisionActivity[] DecisionActivity,Ucp1MarginObservation[] MarginMaxima,
        Ucp1MarginObservation[] MarginExceedances,Cpe1FamilyResearchState[] Cpe1Families,
        string[] Cpe1ScoredEpisodes);

    internal string HistoricalEurCheckpoint()
    {
        if(!OwnerEur||FundingScenarioId is null||researchFork)
            throw new InvalidOperationException("EUR_HISTORICAL_CHECKPOINT_REPLAY_ONLY");
        return JsonSerializer.Serialize(new EurResearchState(EurResearchCheckpointVersion,Checkpoint(),
            PolicyName,FundingScenarioId,LastObservationAt,eurHistory.Values.SelectMany(x=>x).ToArray(),
            eurOpportunities.ToArray(),eurDecisionActivity.ToArray(),eurMarginMaxima.Values.ToArray(),
            eurMarginExceedances.ToArray(),cpe1History.Select(x=>x.Value.ResearchState(x.Key)).ToArray(),
            cpe1ScoredEpisodes.ToArray()));
    }

    internal static NativeUnifiedPortfolioEngine RestoreHistoricalEurCheckpoint(string checkpoint)
    {
        var s=JsonSerializer.Deserialize<EurResearchState>(checkpoint)
            ??throw new ArgumentException("EUR_HISTORICAL_CHECKPOINT_REQUIRED");
        if(s.Version!=EurResearchCheckpointVersion)
            throw new ArgumentException("EUR_HISTORICAL_CHECKPOINT_VERSION");
        var book=Restore(s.CoreCheckpoint);
        if(!book.OwnerEur||book.researchFork||book.FundingScenarioId is null||
           book.FundingScenarioId!=s.FundingScenarioId||book.PolicyName!=s.Policy||
           book.LastObservationAt!=s.LastAt||
           s.History.Any(x=>x.AvailableAt>s.LastAt)||
           s.Opportunities.Any(x=>x.At>s.LastAt)||
           s.DecisionActivity.Any(x=>x.At>s.LastAt)||
           s.MarginMaxima.Any(x=>x.At>s.LastAt)||s.MarginExceedances.Any(x=>x.At>s.LastAt))
            throw new ArgumentException("EUR_HISTORICAL_CHECKPOINT_IDENTITY_OR_CAUSALITY");
        book.eurHistory.Clear();
        foreach(var row in s.History)book.AddEurOutcome(row);
        book.eurOpportunities.Clear();
        book.eurOpportunities.AddRange(s.Opportunities);
        book.eurDecisionActivity.Clear();
        book.eurDecisionActivity.AddRange(s.DecisionActivity);
        book.eurMarginMaxima.Clear();
        foreach(var row in s.MarginMaxima)book.eurMarginMaxima.Add(row.Phase,row);
        book.eurMarginExceedances.Clear();
        book.eurMarginExceedances.AddRange(s.MarginExceedances);
        book.cpe1History.Clear();
        foreach(var family in s.Cpe1Families)
        {
            if(!family.FundingAware||family.Settled<family.GrossReturns.Length||family.Winners>family.Settled)
                throw new ArgumentException("EUR_HISTORICAL_CHECKPOINT_FAMILY_HISTORY");
            book.cpe1History.Add(family.Family,new Cpe1FamilyHistory(family));
        }
        book.cpe1ScoredEpisodes.Clear();
        foreach(var id in s.Cpe1ScoredEpisodes)
            if(!book.cpe1ScoredEpisodes.Add(id))throw new ArgumentException("EUR_HISTORICAL_CHECKPOINT_DUPLICATE_EPISODE");
        return book;
    }
}
