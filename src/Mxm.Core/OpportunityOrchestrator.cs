namespace Mxm.Core;

public enum EvidenceLevel { Exploratory = 1, Preliminary = 2, Incremental = 3, QualifiedPortfolio = 4, NativeReady = 5 }
public sealed record OpportunityScenario(string StateId, long KnownAt, bool Estimation,
    decimal NetPerUnitEur, decimal FixedCostEur, decimal LossPerUnitEur, decimal PeakPerUnitEur);
public sealed record EconomicOpportunity(string Id, string Candidate, string Symbol, string RedundancyKey,
    int Direction, long AvailableAt, long CalibratedThrough, EvidenceLevel Level,
    bool ExecutionEvidenceComplete, AdaptiveRiskInputs VolumeGrid, OpportunityScenario[] Scenarios);
public sealed record PortfolioScenario(string StateId, long KnownAt, bool Estimation,
    decimal NetEur, decimal LossEur, decimal PeakEur, decimal MarginEur);
public sealed record OpportunityAllocation(string Id, decimal Units, double MarginalUtilityLower,
    decimal ScenarioDrawdown, string Reason);
public sealed record OrchestrationResult(OpportunityAllocation[] Allocations,
    OpportunityAllocation[] Declined, decimal ReservedMarginEur, bool Qualified, string Status);

// Pure research decision kernel. Joint states are aligned explicitly; never
// infer independence, diversification credit or qualification from model counts.
// Greedy marginal log utility is a prospective heuristic, NOT a global optimum.
public static class OpportunityOrchestrator
{
    public static OrchestrationResult Select(long clock, AdaptiveRiskInputs account,
        PortfolioScenario[] baseline, EconomicOpportunity[] opportunities)
    {
        if (clock <= 0 || baseline.Length < 2 || baseline.Any(s => string.IsNullOrWhiteSpace(s.StateId) ||
            s.KnownAt >= clock || s.LossEur < 0 || s.PeakEur < 0 || s.MarginEur < 0) ||
            baseline.Select(s => s.StateId).Distinct(StringComparer.Ordinal).Count() != baseline.Length ||
            opportunities.Select(o => o.Id).Distinct(StringComparer.Ordinal).Count() != opportunities.Length)
            throw new ArgumentException("AMBIGUOUS_OR_NONCAUSAL_JOINT_STATE");
        var remaining = opportunities.OrderBy(o => o.Id, StringComparer.Ordinal).ToList();
        var chosen = new List<OpportunityAllocation>(); var declined = new List<OpportunityAllocation>();
        var keys = new HashSet<string>(StringComparer.Ordinal);
        var symbols = new Dictionary<string,int>(StringComparer.Ordinal);
        decimal reserved = 0;
        var states = baseline.ToArray();
        while (remaining.Count > 0)
        {
            EconomicOpportunity? winner = null; AdaptiveRiskChoice? best = null;
            var reasons = new Dictionary<string,string>(StringComparer.Ordinal);
            foreach (var o in remaining)
            {
                string? invalid = string.IsNullOrWhiteSpace(o.Id) || string.IsNullOrWhiteSpace(o.Candidate) ||
                    string.IsNullOrWhiteSpace(o.Symbol) || string.IsNullOrWhiteSpace(o.RedundancyKey) ||
                    o.Direction is not (-1 or 1) || o.Level < EvidenceLevel.Exploratory || o.Level > EvidenceLevel.NativeReady ||
                    o.AvailableAt > clock || o.AvailableAt < 0 || o.CalibratedThrough >= o.AvailableAt || o.CalibratedThrough < 0
                    ? "INVALID_OR_NONCAUSAL_OPPORTUNITY" :
                    !o.ExecutionEvidenceComplete ? "EXECUTION_NET_EVIDENCE_MISSING" :
                    keys.Contains(o.RedundancyKey) ? "REDUNDANT_OPPORTUNITY" :
                    symbols.TryGetValue(o.Symbol, out var direction) && direction != o.Direction ? "CONTRADICTORY_SYMBOL_EXPOSURE" : null;
                if (invalid != null) { reasons[o.Id] = invalid; continue; }
                if (o.Scenarios.Length != states.Length || o.Scenarios.Select(s=>s.StateId).Distinct().Count()!=states.Length)
                    throw new ArgumentException("JOINT_STATE_ALIGNMENT_MISSING");
                var map = o.Scenarios.ToDictionary(s => s.StateId, StringComparer.Ordinal);
                var joint = states.Select(s => {
                    if (!map.TryGetValue(s.StateId, out var x) || x.KnownAt >= clock || x.KnownAt > o.CalibratedThrough ||
                        x.Estimation != s.Estimation) throw new ArgumentException("JOINT_STATE_CLOCK_OR_ALIGNMENT");
                    return new JointRiskScenario(s.NetEur,x.NetPerUnitEur,x.FixedCostEur,s.LossEur,
                        x.LossPerUnitEur,s.PeakEur,s.MarginEur,s.Estimation,x.PeakPerUnitEur);
                }).ToArray();
                var grid = o.VolumeGrid with {EquityEur=account.EquityEur, CertifiedPeakEur=account.CertifiedPeakEur,
                    FreeMarginEur=account.FreeMarginEur-reserved,
                    Reconciled=account.Reconciled && o.VolumeGrid.Reconciled,
                    CompleteJointRiskEvidence=account.CompleteJointRiskEvidence && o.VolumeGrid.CompleteJointRiskEvidence};
                var choice = AdaptivePortfolioRisk.Choose(grid, joint);
                reasons[o.Id] = choice.Reason;
                if (choice.Units > 0 && (best == null || choice.UtilityLowerBound > best.UtilityLowerBound))
                    { winner=o; best=choice; }
            }
            if (winner == null || best == null)
            {
                declined.AddRange(remaining.Select(o=>new OpportunityAllocation(o.Id,0,0,0,reasons[o.Id]))); break;
            }
            var selected=winner; var sized=best;
            chosen.Add(new(selected.Id,sized.Units,sized.UtilityLowerBound,sized.WorstScenarioDrawdown,sized.Reason));
            var additions=selected.Scenarios.ToDictionary(s=>s.StateId,StringComparer.Ordinal);
            states=states.Select(s=> {
                var x=additions[s.StateId];
                return s with {NetEur=s.NetEur+sized.Units*x.NetPerUnitEur-x.FixedCostEur,
                    LossEur=s.LossEur+sized.Units*x.LossPerUnitEur+x.FixedCostEur,
                    PeakEur=s.PeakEur+sized.Units*x.PeakPerUnitEur,MarginEur=s.MarginEur+sized.MarginEur};
            }).ToArray();
            reserved+=sized.MarginEur; keys.Add(selected.RedundancyKey); symbols[selected.Symbol]=selected.Direction;
            remaining.Remove(selected);
        }
        return new(chosen.ToArray(),declined.ToArray(),reserved,false,"UNQUALIFIED_RESEARCH_ALLOCATION_ONLY");
    }
}

public sealed record OrchestrationRequest(long Clock, AdaptiveRiskInputs Account,
    PortfolioScenario[] Baseline, EconomicOpportunity[] Opportunities);
