namespace Mxm.Core;
// Frozen PR16 evaluator only. Not an authorized admission path.
internal static class HistoricalPr16Risk
{
    public static PreventiveSize Size(decimal equity,decimal peak,decimal freeMargin,
        IEnumerable<ReservedPositionRisk> positions,StopExecutionTerms terms)
    {
        var open=positions.ToArray();
        PreventiveSize Deny(string reason)=>new(0,0,peak,0,0,reason,false);
        if(!terms.BrokerContractObserved || !terms.ReconciledAccount)return Deny("UNRECONCILED_EXECUTION_TERMS_MONITOR_CONTINUES");
        if(equity<=0 || peak<200 || peak<equity || freeMargin<0 || terms.MinimumUnits<=0 || terms.StepUnits<=0 ||
           terms.MaximumUnits<terms.MinimumUnits || terms.StopPriceDistance<=0 || terms.TakeProfitPriceDistance<=0 ||
           terms.MinimumBrokerStopDistance<0 || terms.StopPriceDistance<terms.MinimumBrokerStopDistance ||
           terms.GapPriceStress<0 || terms.AdverseSlippagePriceStress<0 || terms.SpreadPriceStress<0 ||
           terms.QuoteToEurAdverseRate<=0 || terms.CostPerUnitEur<0 || terms.FixedRoundTripCostEur<0 || terms.MarginPerUnitEur<=0 ||
           open.Any(p=>string.IsNullOrWhiteSpace(p.Key) || p.AdditionalLossEur<0 || p.FavorablePeakEur<0 || p.MarginEur<0) ||
           open.Select(p=>p.Key).Distinct().Count()!=open.Length)return Deny("INVALID_PREVENTIVE_RISK_INPUT");
        decimal lossPerUnit=(terms.StopPriceDistance+terms.GapPriceStress+terms.AdverseSlippagePriceStress+terms.SpreadPriceStress)*terms.QuoteToEurAdverseRate+terms.CostPerUnitEur;
        decimal gainPerUnit=(terms.TakeProfitPriceDistance+terms.GapPriceStress)*terms.QuoteToEurAdverseRate;
        decimal existingLoss=open.Sum(p=>p.AdditionalLossEur),existingPeak=open.Sum(p=>p.FavorablePeakEur);
        decimal headroom=equity-.70m*Math.Max(peak,equity+existingPeak)-existingLoss;
        if(headroom<=terms.FixedRoundTripCostEur)return Deny("NO_STRESS_DRAWDOWN_HEADROOM");
        // Dynamic 2% equity / 20% remaining headroom is a policy, not historical OWNER EUR2 cap.
        decimal budget=Math.Min(.02m*equity,.20m*headroom);
        decimal units=Math.Min(terms.MaximumUnits,Math.Min((budget-terms.FixedRoundTripCostEur)/lossPerUnit,freeMargin/terms.MarginPerUnitEur));
        units=terms.MinimumUnits+Math.Floor((units-terms.MinimumUnits)/terms.StepUnits)*terms.StepUnits;
        while(units>=terms.MinimumUnits)
        {
            decimal stress=existingLoss+units*lossPerUnit+terms.FixedRoundTripCostEur;
            decimal stressedPeak=Math.Max(peak,equity+existingPeak+units*gainPerUnit);
            decimal dd=1m-(equity-stress)/stressedPeak;
            if(dd<.30m && open.Sum(p=>p.MarginEur)+units*terms.MarginPerUnitEur+stress<=equity && units*terms.MarginPerUnitEur<=freeMargin)
                return new(units,stress-existingLoss,stressedPeak,dd,units*terms.MarginPerUnitEur,"SIZED_WITHIN_DECLARED_STOP_GAP_COST_STRESS",false);
            units-=terms.StepUnits;
        }
        return Deny("BROKER_MINIMUM_EXCEEDS_PREVENTIVE_STRESS_CAPACITY");
    }
}
