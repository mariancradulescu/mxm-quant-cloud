namespace Mxm.Core;

public sealed record OwnerLimitDecision(bool Allowed,decimal AggregateLossEur,decimal AggregateMarginEur,
    decimal FreeReserveAfterEur,decimal AvailableLossEur,string Reason);
public static class OwnerRiskLimits
{
    public const string Authority="OWNER_EXPLICIT_CORRECTION_AFTER_PR16_PR17_20261103";
    public const decimal RiskFraction=.01m,MarginFraction=.40m,ReserveFraction=.60m;
    // Existing rows MUST include positions, pending and bounded ambiguous intents.
    // FreeMargin already excludes existing broker margin; do not subtract it twice.
    public static OwnerLimitDecision Check(decimal equity,decimal freeMargin,decimal existingLoss,decimal existingMargin,
        decimal proposedLoss,decimal proposedMargin)
    {
        if(equity<=0 || freeMargin<0 || freeMargin>equity || existingLoss<0 || existingMargin<0 || proposedLoss<0 || proposedMargin<0)
            return new(false,0,0,0,0,"OWNER_INPUT_INVALID");
        decimal loss=existingLoss+proposedLoss,margin=existingMargin+proposedMargin;
        decimal reserve=Math.Min(equity-margin,freeMargin-proposedMargin);
        string reason=loss>RiskFraction*equity?"OWNER_AGGREGATE_RISK_1_PERCENT":
            margin>MarginFraction*equity?"OWNER_AGGREGATE_MARGIN_40_PERCENT":
            reserve<ReserveFraction*equity?"OWNER_FREE_RESERVE_60_PERCENT":"OWNER_AGGREGATE_LIMITS_SATISFIED";
        return new(reason=="OWNER_AGGREGATE_LIMITS_SATISFIED",loss,margin,reserve,Math.Max(0,RiskFraction*equity-loss),reason);
    }
}
