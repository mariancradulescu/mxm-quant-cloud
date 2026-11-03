namespace Mxm.Core;

// All scenario vectors MUST share the same joint market/FX/liquidity states.
// OpenPortfolioNet includes pending and bounded ambiguous intent losses and costs.
public sealed record JointRiskScenario(decimal OpenPortfolioNetEur, decimal ProposedNetPerUnitEur,
    decimal ProposedFixedCostEur, decimal IntrahorizonOpenLossEur, decimal IntrahorizonLossPerUnitEur,
    decimal FavorablePeakEur, decimal ExistingMarginEur, bool InEstimationSample,
    decimal ProposedFavorablePeakPerUnitEur = 0m);
public sealed record AdaptiveRiskInputs(decimal EquityEur, decimal CertifiedPeakEur, decimal FreeMarginEur,
    decimal MinimumUnits, decimal StepUnits, decimal MaximumUnits, decimal MarginPerUnitEur,
    decimal BrokerStopoutEquityToMargin, bool Reconciled, bool CompleteJointRiskEvidence,
    int EffectiveIndependentBlocks, decimal UncertaintyMultiplier);
public sealed record AdaptiveRiskChoice(decimal Units, double UtilityLowerBound,
    decimal WorstScenarioDrawdown, decimal WorstEquityEur, decimal MarginEur,
    decimal? SampleRuinFraction, int FeasibleVolumes, string Reason, bool AbsoluteGuarantee);

// Mathematical scenario inputs carry no certified-peak or broker-stopout claim.
public sealed record ScenarioSizingInputs(decimal EquityEur, decimal PeakReferenceEur, decimal FreeMarginEur,
    decimal MinimumUnits, decimal StepUnits, decimal MaximumUnits, decimal MarginPerUnitEur,
    decimal MarginCoverageScenarioRatio, int EffectiveIndependentBlocks, decimal UncertaintyMultiplier);

public static class AdaptivePortfolioRisk
{
    // Experiment-specific confidence/support inputs, not OWNER risk percentages.
    // Maximise conservative expected log incremental wealth versus doing nothing.
    public static AdaptiveRiskChoice Choose(AdaptiveRiskInputs a, IEnumerable<JointRiskScenario> scenarios)
    {
        if(!a.Reconciled || !a.CompleteJointRiskEvidence)
            return new(0,0,0,a.EquityEur,0,null,0,"JOINT_ACCOUNT_OR_RISK_EVIDENCE_MISSING_MONITOR_CONTINUES",false);
        return Evaluate(ToScenario(a),scenarios);
    }
    public static ScenarioSizingInputs ToScenario(AdaptiveRiskInputs a) => new(a.EquityEur,a.CertifiedPeakEur,
        a.FreeMarginEur,a.MinimumUnits,a.StepUnits,a.MaximumUnits,a.MarginPerUnitEur,
        a.BrokerStopoutEquityToMargin,a.EffectiveIndependentBlocks,a.UncertaintyMultiplier);

    // Explicit conditional research endpoint. It cannot create a peak
    // certificate or set verified execution/operational evidence to true.
    public static AdaptiveRiskChoice Estimate(ScenarioSizingInputs a, IEnumerable<JointRiskScenario> scenarios,
        bool ledgerReconciled, bool scenarioInputsComplete)
    {
        if(!ledgerReconciled || !scenarioInputsComplete)
            return new(0,0,0,a.EquityEur,0,null,0,"CONDITIONAL_SCENARIO_INPUTS_MISSING",false);
        var result=Evaluate(a,scenarios);
        return result with {Reason="CONDITIONAL_ESTIMATE_"+result.Reason};
    }
    private static AdaptiveRiskChoice Evaluate(ScenarioSizingInputs a, IEnumerable<JointRiskScenario> scenarios)
    {
        var s=scenarios.ToArray();
        AdaptiveRiskChoice Deny(string why)=>new(0,0,0,a.EquityEur,0,null,0,why,false);
        if(a.EquityEur<=0 || a.PeakReferenceEur<200 || a.PeakReferenceEur<a.EquityEur || a.FreeMarginEur<0 ||
           a.MinimumUnits<=0 || a.StepUnits<=0 || a.MaximumUnits<a.MinimumUnits || a.MarginPerUnitEur<=0 ||
           a.MarginCoverageScenarioRatio<0 || a.EffectiveIndependentBlocks<2 || a.UncertaintyMultiplier<0 || s.Length<2 ||
           s.Count(x=>x.InEstimationSample)<2 || a.EffectiveIndependentBlocks>s.Count(x=>x.InEstimationSample) ||
           s.Any(x=>x.ProposedFixedCostEur<0 || x.IntrahorizonOpenLossEur<0 || x.IntrahorizonLossPerUnitEur<0 ||
                    x.FavorablePeakEur<0 || x.ProposedFavorablePeakPerUnitEur<0 || x.ExistingMarginEur<0))return Deny("INVALID_ADAPTIVE_EVIDENCE");
        decimal max=Math.Min(a.MaximumUnits,a.FreeMarginEur/a.MarginPerUnitEur);
        if(max<a.MinimumUnits)return Deny("BROKER_MINIMUM_NOT_FINANCED");
        int count=(int)Math.Min(10001m,1m+Math.Floor((max-a.MinimumUnits)/a.StepUnits));
        if(count>10000)return Deny("EXPLICIT_SEARCH_GRID_REQUIRED_FOR_LARGE_CONTRACT");
        var best=Deny("NO_POSITIVE_UNCERTAINTY_ADJUSTED_INCREMENTAL_UTILITY");
        int feasible=0;
        for(int k=0;k<count;k++)
        {
            decimal u=a.MinimumUnits+k*a.StepUnits,margin=u*a.MarginPerUnitEur;
            decimal worst=a.EquityEur,dd=0;bool ok=true;var utilities=new List<double>();
            foreach(var x in s)
            {
                decimal baseline=a.EquityEur+x.OpenPortfolioNetEur;
                decimal terminal=baseline+u*x.ProposedNetPerUnitEur-x.ProposedFixedCostEur;
                decimal low=Math.Min(terminal,a.EquityEur-x.IntrahorizonOpenLossEur-u*x.IntrahorizonLossPerUnitEur-x.ProposedFixedCostEur);
                // Candidate peak scales with volume; terminal gains also bound the peak.
                decimal peak=Math.Max(a.PeakReferenceEur,Math.Max(terminal,
                    a.EquityEur+x.FavorablePeakEur+u*x.ProposedFavorablePeakPerUnitEur));
                decimal d=1m-low/peak;worst=Math.Min(worst,low);dd=Math.Max(dd,d);
                // No correlation/netting discount: each joint adverse state survives.
                if(baseline<=0 || terminal<=0 || d>=.30m ||
                   low<=(x.ExistingMarginEur+margin)*a.MarginCoverageScenarioRatio ||
                   x.ExistingMarginEur+margin>low || margin+Math.Max(0,a.EquityEur-low)>a.FreeMarginEur)ok=false;
                if(x.InEstimationSample && baseline>0 && terminal>0)utilities.Add(Math.Log((double)(terminal/baseline)));
            }
            if(!ok)continue;
            feasible++;
            double mean=utilities.Average();
            double variance=utilities.Sum(v=>(v-mean)*(v-mean))/(utilities.Count-1);
            double lower=mean-(double)a.UncertaintyMultiplier*Math.Sqrt(variance/a.EffectiveIndependentBlocks);
            if(lower>best.UtilityLowerBound)best=new(u,lower,dd,worst,margin,0,feasible,"SCENARIO_FEASIBLE_ADAPTIVE_RESEARCH_ONLY",false);
        }
        return best with {FeasibleVolumes=feasible};
    }
}
