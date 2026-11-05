using System.Text.Json;
namespace Mxm.Core;

// Conditional development input, never a broker fill or a trading permission.
// One scenario vector prices the WHOLE remaining exposure, in EUR, not per unit.
public sealed record ResearchExposureScenarios(string PositionId,string Symbol,int Side,decimal Units,
    PortfolioScenario[] States);
public sealed record ResearchEntryTerms(string OpportunityId,long LatencyMs,decimal SlippagePerSide,string EvidenceHash);
public sealed record NativeResearchDecision(string Id,long Clock,ScenarioSizingInputs Sizing,
    PortfolioScenario[] EmptyStates,EconomicOpportunity[] Opportunities,
    ResearchExposureScenarios[] Exposure,ResearchEntryTerms[] EntryTerms,string EvidenceHash,
    SpecialistEuroEvidence[]? SpecialistEvidence=null);
public sealed record NativeResearchDecisionReceipt(string InputHash,OrchestrationResult Selection,
    LedgerSummary Ledger,decimal PendingMarginReservedEur,string Status,
    bool Qualified=false,bool OrdersEnabled=false);
public sealed record NativeResearchFrame(LedgerEvent[] Facts,NativeResearchDecision? Decision);

public sealed partial class NativeFundedLedger
{
    internal LedgerEvent[] PendingSnapshot()=>state.Pending.Values.ToArray();
    internal decimal ResearchMargin(string symbol,decimal units,decimal entryMargin,long at)
        =>units*Math.Max(entryMargin,Quote(state.Quotes,symbol,at).MarginPerUnit);
}

public sealed partial class NativeFundedSession
{
    public Dictionary<string,NativeResearchDecisionReceipt> ResearchDecisions {get;private set;}=new(StringComparer.Ordinal);

    // Apply on a candidate so rejected monetary batches cannot leave half an
    // entry, a changed cash balance or an unrecorded decision behind.
    public LedgerSummary ApplyResearchFacts(LedgerEvent[] facts)
    {
        if(Ledger.MonetaryDomain!="MODEL_REPLAY")throw new ArgumentException("RESEARCH_CANNOT_MUTATE_BROKER_BOOK");
        var candidate=NativeFundedLedger.Restore(Ledger.Checkpoint());
        foreach(var fact in facts)candidate.Apply(fact);
        Ledger=candidate;
        return Ledger.Summary();
    }

    public NativeResearchDecisionReceipt DecideResearch(NativeResearchDecision d)
    {
        // Null specialist evidence retains the historical exact decision hash format.
        // Existing closed/legacy development receipts must not be invalidated by
        // adding this prospective, strictly optional evidence gate.
        string hash=Hash(d.SpecialistEvidence is null ?
            JsonSerializer.Serialize(new {d.Id,d.Clock,d.Sizing,d.EmptyStates,
                d.Opportunities,d.Exposure,d.EntryTerms,d.EvidenceHash}) :
            JsonSerializer.Serialize(d));
        if(ResearchDecisions.TryGetValue(d.Id,out var previous))
        {
            if(previous.InputHash!=hash)throw new ArgumentException("CONFLICTING_NATIVE_RESEARCH_DECISION");
            return previous;
        }
        if(Ledger.MonetaryDomain!="MODEL_REPLAY" || string.IsNullOrWhiteSpace(d.Id) || d.Clock<=0 ||
            d.EvidenceHash.Length!=64 || !d.EvidenceHash.All(Uri.IsHexDigit))
            throw new ArgumentException("NATIVE_RESEARCH_DECISION_DOMAIN_OR_IDENTITY");
        var summary=Ledger.Summary(d.Clock);
        NativeResearchDecisionReceipt Pause(string reason)
        {
            // A pause is retryable with a new decision ID after fresh facts.
            // It does not remove exposure or clear retained risk/history flags.
            return new(hash,new(Array.Empty<OpportunityAllocation>(),
                d.Opportunities.Select(o=>new OpportunityAllocation(o.Id,0,0,0,reason)).ToArray(),0,false,reason),
                summary,0,reason);
        }
        if(summary.LiquidationEquityEur is not decimal equity || summary.FreeMarginEur is not decimal free)
            return Pause("NATIVE_RESEARCH_CURRENT_HOLDING_MARK_UNKNOWN_RETRY");
        if(summary.MaximumSampledDrawdown>=.30m || equity<=0)
            return Pause("NATIVE_RESEARCH_RETAINED_DRAWDOWN_LIMIT");
        if(d.EmptyStates.Length<2 || d.EmptyStates.Select(s=>s.StateId).Distinct().Count()!=d.EmptyStates.Length ||
           d.EmptyStates.Any(s=>s.NetEur!=0 || s.LossEur!=0 || s.PeakEur!=0 || s.MarginEur!=0 || s.KnownAt>=d.Clock))
            throw new ArgumentException("NATIVE_RESEARCH_EMPTY_JOINT_STATES");
        var held=Ledger.PositionSnapshot();
        var pending=Ledger.PendingSnapshot().Where(p=>p.Kind=="REQUEST_OPEN").ToArray();
        // Close requests retain the held position's risk and are not counted twice.
        var exposures=held.Select(p=>(Id:p.Id,p.Symbol,p.Side,p.Units,p.MarginPerUnit))
            .Concat(pending.Select(p=>(Id:p.PositionId,p.Symbol,p.Side,p.Units,p.MarginPerUnit))).ToArray();
        if(d.Exposure.Select(x=>x.PositionId).Distinct().Count()!=d.Exposure.Length ||
           d.Exposure.Length!=exposures.Length || exposures.Any(p=>!d.Exposure.Any(x=>
                x.PositionId==p.Id && x.Symbol==p.Symbol && x.Side==p.Side && x.Units==p.Units)))
            return Pause("NATIVE_RESEARCH_HELD_OR_PENDING_SCENARIOS_UNKNOWN_RETRY");
        var states=d.EmptyStates.ToArray();
        decimal reserved=0;
        try {
        foreach(var p in exposures)
        {
            var x=d.Exposure.Single(x=>x.PositionId==p.Id);
            if(x.States.Length!=states.Length || x.States.Select(s=>s.StateId).Distinct().Count()!=states.Length)
                throw new ArgumentException("NATIVE_RESEARCH_HELD_JOINT_ALIGNMENT");
            var map=x.States.ToDictionary(s=>s.StateId,StringComparer.Ordinal);
            decimal margin=Ledger.ResearchMargin(p.Symbol,p.Units,p.MarginPerUnit,d.Clock);
            states=states.Select(s=>{
                if(!map.TryGetValue(s.StateId,out var r) || r.KnownAt>=d.Clock || r.KnownAt<0 ||
                   r.Estimation!=s.Estimation || r.LossEur<0 || r.PeakEur<0 || r.MarginEur<margin)
                    throw new ArgumentException("NATIVE_RESEARCH_HELD_RISK_OR_MARGIN_UNKNOWN");
                return s with {KnownAt=Math.Max(s.KnownAt,r.KnownAt),NetEur=s.NetEur+r.NetEur,
                    LossEur=s.LossEur+r.LossEur,PeakEur=s.PeakEur+r.PeakEur,MarginEur=s.MarginEur+r.MarginEur};
            }).ToArray();
        }
        reserved=pending.Sum(p=>Ledger.ResearchMargin(p.Symbol,p.Units,p.MarginPerUnit,d.Clock));
        } catch(InvalidOperationException) {return Pause("NATIVE_RESEARCH_CURRENT_PENDING_MARK_UNKNOWN_RETRY");}
        if(free-reserved<0)return Pause("NATIVE_RESEARCH_PENDING_MARGIN_NOT_FINANCED");
        if(d.EntryTerms.Select(x=>x.OpportunityId).Distinct().Count()!=d.EntryTerms.Length ||
            d.EntryTerms.Length!=d.Opportunities.Length || d.Opportunities.Any(o=>!d.EntryTerms.Any(t=>
                t.OpportunityId==o.Id && t.LatencyMs>0 && t.SlippagePerSide>=0 &&
                t.EvidenceHash.Length==64 && t.EvidenceHash.All(Uri.IsHexDigit))))
            throw new ArgumentException("NATIVE_RESEARCH_ENTRY_CONTRACT");
        // Physical broker volume units are used throughout. No implicit lot
        // multiplier or future fill price enters selection or intent creation.
        var blocked=d.Opportunities.Where(o=>exposures.Any(p=>p.Symbol==o.Symbol)).ToArray();
        var offered=d.Opportunities.Except(blocked).ToArray();
        var account=d.Sizing with {EquityEur=equity,FreeMarginEur=free-reserved,
            PeakReferenceEur=Math.Max(summary.ObservedPeakEur,equity)};
        var request=new ResearchOrchestrationRequest(
            "NATIVE_FUNDED_CYCLE_DEVELOPMENT_NOT_CERTIFIED",0,d.Clock,account,states,
            offered,true,offered.Select(o=>o.Id).ToArray());
        // Legacy conditional replay remains byte-for-byte decision-compatible.
        // New multi-specialist research passes cost, causal benchmark and EUR
        // uncertainty through the gate BEFORE the SAME allocator and ledger.
        // No direct deployment, trading or second capital book is possible.
        OrchestrationResult selection;
        if(d.SpecialistEvidence is null)
            selection=OpportunityOrchestrator.Estimate(request);
        else
        {
            if(d.SpecialistEvidence.Length!=d.Opportunities.Length ||
               d.SpecialistEvidence.Select(x=>x.OpportunityId).Distinct(StringComparer.Ordinal).Count()!=d.SpecialistEvidence.Length ||
               d.Opportunities.Any(o=>!d.SpecialistEvidence.Any(e=>e.OpportunityId==o.Id)))
                throw new ArgumentException("NATIVE_SPECIALIST_EVIDENCE_SET_MISMATCH");
            var relevant=d.SpecialistEvidence.Where(e=>offered.Any(o=>o.Id==e.OpportunityId)).ToArray();
            selection=ResearchSpecialistAdmission.Estimate(request,relevant).NativeAllocation;
        }
        selection=selection with {Declined=selection.Declined.Concat(blocked.Select(o=>
            new OpportunityAllocation(o.Id,0,0,0,"NATIVE_RESEARCH_SYMBOL_HELD_OR_PENDING"))).ToArray()};
        var candidate=NativeFundedLedger.Restore(Ledger.Checkpoint());
        foreach(var allocation in selection.Allocations)
        {
            var o=offered.Single(o=>o.Id==allocation.Id);
            var terms=d.EntryTerms.Single(t=>t.OpportunityId==o.Id);
            candidate.Apply(new("DECISION/"+d.Id+"/"+o.Id,d.Clock,"REQUEST_OPEN",o.Id,o.Symbol,o.Direction,
                allocation.Units,0,0,o.VolumeGrid.MarginPerUnitEur,terms.SlippagePerSide,
                o.AvailableAt,o.CalibratedThrough,terms.LatencyMs,"NATIVE_CONDITIONAL_SELECTION",terms.EvidenceHash,
                Array.Empty<LedgerQuote>()));
        }
        var receipt=new NativeResearchDecisionReceipt(hash,selection,candidate.Summary(d.Clock),
            reserved+selection.ReservedMarginEur,"NATIVE_CONDITIONAL_INTENTS_ONLY_NO_FILLS_OR_TRADING");
        Ledger=candidate;ResearchDecisions.Add(d.Id,receipt);
        return receipt;
    }
}
