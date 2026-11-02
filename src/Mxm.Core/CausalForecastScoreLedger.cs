namespace Mxm.Core;

// Proper scoring rule on a causally observable NEXT completed bar.
// This is a *predictive* screen, not a trade or a gross/NET cash simulation.
public sealed record CausalForecastAggregate(
    int Count, decimal MeanBrier, decimal BaselineMeanBrier,
    decimal BrierSkillVersusNeutral, string Qualification);

public sealed class CausalForecastScoreLedger
{
    private int count;
    private decimal squaredErrorSum, neutralSquaredErrorSum;
    public void Score(decimal probabilityUp, decimal realizedDirection)
    {
        if(probabilityUp<0m || probabilityUp>1m ||
            (realizedDirection!=0m && realizedDirection!=.5m && realizedDirection!=1m))
            throw new ArgumentException("CAUSAL_SCORE_INPUT_INVALID");
        var error=probabilityUp-realizedDirection;
        var neutral=.5m-realizedDirection;
        squaredErrorSum+=error*error;
        neutralSquaredErrorSum+=neutral*neutral;
        count++;
    }

    public CausalForecastAggregate Summarize(int privacyMinimum=100)
    {
        if(privacyMinimum<100)throw new ArgumentException("PUBLIC_MINIMUM_CANNOT_BE_LOWERED");
        if(count<privacyMinimum) return new(count,0m,0m,0m,
            "INSUFFICIENT_OBSERVATIONS_NO_PUBLIC_NUMERIC_SKILL");
        var model=squaredErrorSum/count;
        var baseline=neutralSquaredErrorSum/count;
        var skill=baseline==0m ? 0m : 1m-model/baseline;
        return new(count,model,baseline,skill,
            "PRICE_ONLY_PREDICTIVE_SCREEN_NOT_NET_OR_INDEPENDENT_CONFIRMATION");
    }
}
