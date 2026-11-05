namespace Mxm.Core;

// Role contract: observer + predictor + skeptic, then the EXISTING common
// OpportunityOrchestrator.Estimate and NativeFundedSession/NativeFundedLedger.
// Units and all financial quantities are EUR at the minimum broker volume.
public sealed record SpecialistEuroEvidence(
    string OpportunityId,long FeatureKnownAt,long CostKnownAt,
    int FeaturePeriodMinutes,int HoldingMinutes,
    bool AuthenticCausalSource,bool SupportedVsBenchmark,bool ValidBidAsk,
    bool CompleteCurrentContractFxAndMargin,bool PricesAlreadyContainBidAsk,
    decimal? GrossAboveBenchmarkEur,decimal? PredictionUncertaintyEur,
    decimal? ObservedOneRoundTripSpreadEur,decimal? EntryFeeEur,
    decimal? ExitFeeEur,decimal? ConversionFeeEur,decimal? SlippageEur,
    decimal? FinancingEur,decimal? CurrentMinMarginEur);
public sealed record SpecialistEuroGate(string OpportunityId,bool AdmittedForConditionalResearch,
    decimal? IncrementalLowerEur,decimal? ExtraSpreadEur,decimal? TotalFrictionEur,string Reason);
public sealed record SpecialistEuroEstimate(OrchestrationResult NativeAllocation,
    SpecialistEuroGate[] EvidenceGates,bool FundedNetCertified=false,
    bool OrdersEnabled=false,bool IndependentConfirmation=false);

public static class ResearchSpecialistAdmission
{
    public static SpecialistEuroGate Inspect(long clock,EconomicOpportunity o,SpecialistEuroEvidence e)
    {
        SpecialistEuroGate Block(string why)=>new(o.Id,false,null,null,null,why);
        if(e.OpportunityId!=o.Id || e.FeaturePeriodMinutes<=0 || e.HoldingMinutes<=0 ||
           e.FeatureKnownAt<0 || e.FeatureKnownAt>=clock || e.FeatureKnownAt>o.AvailableAt ||
           e.CostKnownAt<0 || e.CostKnownAt>clock)
            return Block("SPECIALIST_CAUSAL_CLOCK_OR_ID_MISSING");
        if(!e.AuthenticCausalSource || !e.ValidBidAsk || !e.CompleteCurrentContractFxAndMargin)
            return Block("SPECIALIST_BROKER_QUOTE_CONTRACT_FX_UNKNOWN");
        if(!e.SupportedVsBenchmark)return Block("SPECIALIST_NO_PREDICTIVE_BENCHMARK_SUPPORT");
        decimal?[] values={e.GrossAboveBenchmarkEur,e.PredictionUncertaintyEur,
            e.ObservedOneRoundTripSpreadEur,e.EntryFeeEur,e.ExitFeeEur,
            e.ConversionFeeEur,e.SlippageEur,e.FinancingEur,e.CurrentMinMarginEur};
        if(values.Any(v=>v is null))return Block("SPECIALIST_UNKNOWN_EUR_COST_OR_FINANCING");
        if(values.Any(v=>v!.Value<0))return Block("SPECIALIST_NEGATIVE_COST");
        if(e.CurrentMinMarginEur<=0 || e.CurrentMinMarginEur>200m ||
           e.CurrentMinMarginEur>o.VolumeGrid.MinimumUnits*o.VolumeGrid.MarginPerUnitEur*1.000001m)
            return Block("SPECIALIST_MIN_VOLUME_MARGIN_NOT_FINANCED");
        decimal spread=e.PricesAlreadyContainBidAsk?0m:e.ObservedOneRoundTripSpreadEur!.Value;
        decimal friction=spread+e.EntryFeeEur!.Value+e.ExitFeeEur!.Value+
            e.ConversionFeeEur!.Value+e.SlippageEur!.Value+e.FinancingEur!.Value;
        decimal lower=e.GrossAboveBenchmarkEur!.Value-friction-e.PredictionUncertaintyEur!.Value;
        return new(o.Id,lower>0,lower,spread,friction,lower>0?
            "CONDITIONAL_BENCHMARK_AND_COST_GATE_ONLY":"NO_EUR_EDGE_AFTER_COST_AND_UNCERTAINTY");
    }

    public static SpecialistEuroEstimate Estimate(ResearchOrchestrationRequest request,
        SpecialistEuroEvidence[] evidence)
    {
        if(evidence.Length!=request.Opportunities.Length ||
           evidence.Select(x=>x.OpportunityId).Distinct(StringComparer.Ordinal).Count()!=evidence.Length ||
           request.Opportunities.Any(o=>!evidence.Any(e=>e.OpportunityId==o.Id)))
            throw new ArgumentException("SPECIALIST_EVIDENCE_SET_NOT_ALIGNED");
        var gates=request.Opportunities.Select(o=>Inspect(request.Clock,o,
            evidence.Single(e=>e.OpportunityId==o.Id))).ToArray();
        var offered=request.Opportunities.Where(o=>gates.Any(g=>g.OpportunityId==o.Id &&
            g.AdmittedForConditionalResearch)).ToArray();
        var native=OpportunityOrchestrator.Estimate(request with {
            Opportunities=offered,ScenarioCompleteOpportunityIds=request.ScenarioCompleteOpportunityIds
                .Where(id=>offered.Any(o=>o.Id==id)).ToArray()});
        var blocked=gates.Where(g=>!g.AdmittedForConditionalResearch).Select(g=>
            new OpportunityAllocation(g.OpportunityId,0,0,0,g.Reason)).ToArray();
        return new(native with {Declined=native.Declined.Concat(blocked).ToArray(),
            Qualified=false,Status="COMMON_EUR200_NATIVE_CONDITIONAL_ONLY_NO_TRADING"},gates);
    }
}
