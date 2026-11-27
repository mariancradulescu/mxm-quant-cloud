using System;
namespace Mxm.Core;
// Candidate-level distributional capacity test. Existing held/pending stop
// commitments stay reserved, and every original capital guard still applies.
// Expected shortfall is an estimate, never a continuous drawdown certificate.
internal static class NativeDistributionTailCapacity
{
    internal static bool Allows(decimal? equity,decimal peak,decimal otherRisk,decimal proposedRisk,
        decimal marginAfter,decimal? expectedShortfall)
    {
        if(equity is not >0m||peak<=0m||otherRisk<0m||proposedRisk<=0m||marginAfter<0m||expectedShortfall is null)return false;
        decimal loss=Math.Max(proposedRisk,Math.Max(0m,-expectedShortfall.Value));
        return loss<=equity.Value*NativePendingCapitalGate.MaximumTradeStopFraction&&
            otherRisk+loss<=equity.Value*NativePendingCapitalGate.MaximumAggregateStopFraction&&
            equity.Value-otherRisk-loss>=peak*(1m-OwnerRiskAuthority.MaximumSystemDrawdown)&&
            NativePendingCapitalGate.StopAdjustedMarginFits(equity.Value,marginAfter,otherRisk+loss);
    }
}
