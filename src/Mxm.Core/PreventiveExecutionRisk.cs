namespace Mxm.Core;

// Native, pre-entry scenario sizing; never submits or alters orders.
public sealed record StopExecutionTerms(decimal MinimumUnits,decimal StepUnits,decimal MaximumUnits,
    decimal StopPriceDistance,decimal TakeProfitPriceDistance,decimal MinimumBrokerStopDistance,
    decimal GapPriceStress,decimal AdverseSlippagePriceStress,decimal SpreadPriceStress,
    decimal QuoteToEurAdverseRate,decimal CostPerUnitEur,decimal FixedRoundTripCostEur,
    decimal MarginPerUnitEur,bool BrokerContractObserved,bool ReconciledAccount);
public sealed record ReservedPositionRisk(string Key,decimal AdditionalLossEur,decimal FavorablePeakEur,decimal MarginEur);
public sealed record PreventiveSize(decimal Units,decimal StressLossEur,decimal StressPeakEur,
    decimal StressDrawdown,decimal MarginEur,string Reason,bool AbsoluteGuarantee);
// Distribution-free legacy signature cannot select economically justified volume.
// Call AdaptivePortfolioRisk with causal calibrated joint scenarios instead.
public static class PreventiveExecutionRisk
{
    public static PreventiveSize Size(decimal equity,decimal peak,decimal freeMargin,
        IEnumerable<ReservedPositionRisk> positions,StopExecutionTerms terms)
        =>new(0,0,peak,0,0,"ADAPTIVE_JOINT_ECONOMIC_SCENARIOS_REQUIRED_MONITOR_CONTINUES",false);
}
