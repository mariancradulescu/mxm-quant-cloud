namespace Mxm.Core;

public sealed record CarryMargin(decimal Units,decimal BuyEur,decimal SellEur);
public sealed record CarryTerm(string Symbol,string BaseAsset,string QuoteAsset,decimal MinUnits,decimal StepUnits,decimal MaxUnits,
    int PipPosition,int? SwapType,decimal? SwapLong,decimal? SwapShort,int? SwapPeriod,int? SwapMinute,CarryMargin[] Margins);
public sealed record CarryQuote(string Symbol,decimal Bid,decimal Ask,decimal EurCreditPerQuote,decimal EurDebitPerQuote,
    decimal FeeLinearEurPerUnit,decimal FeeFloorEur);
public sealed record CarryCycleContext(string Name,string BaseUsd,string BaseJpy,long QuoteAt,CarryQuote[] Quotes);
public sealed record CarryPreflightInput(CarryTerm[] Terms,CarryCycleContext[] Contexts,bool NormalAccountEffective,int MoneyDigits);

// Current-term financial premise, NOT historical NET, a spot-return forecast,
// risk-free arbitrage, execution probability or a trading admission.
public static class CarryCyclePreflight
{
    public static object Evaluate(CarryPreflightInput a)
    {
        var terms=a.Terms.ToDictionary(t=>t.Symbol);var rows=new List<object>();int usable=0,financed=0,positiveRaw=0,positiveFive=0;
        if(a.MoneyDigits is <0 or >8)throw new ArgumentException("UNKNOWN_MONEY_PRECISION");
        decimal quantum=1;for(int i=0;i<a.MoneyDigits;i++)quantum/=10;
        foreach(var context in a.Contexts)
        {
            var quotes=context.Quotes.ToDictionary(q=>q.Symbol);
            string[] names={context.BaseUsd,context.BaseJpy,"USDJPY"};
            if(!names.All(s=>terms.ContainsKey(s)&&quotes.ContainsKey(s))){rows.Add(new {context.Name,Reason="MISSING_ROUTE_OR_CONTRACT"});continue;}
            var ts=names.Select(s=>terms[s]).ToArray();var qs=names.Select(s=>quotes[s]).ToArray();
            bool funding=a.NormalAccountEffective&&ts.All(t=>t.SwapType==0&&t.SwapLong.HasValue&&t.SwapShort.HasValue&&t.SwapPeriod==24&&t.SwapMinute.HasValue);
            bool currencies=ts[0].QuoteAsset=="USD"&&ts[1].QuoteAsset=="JPY"&&ts[2].BaseAsset=="USD"&&ts[2].QuoteAsset=="JPY"&&ts[0].BaseAsset==ts[1].BaseAsset;
            if(!funding||!currencies){rows.Add(new {context.Name,Reason="FUNDING_UNIT_SCHEDULE_OR_CURRENCY_UNPROVEN"});continue;}
            usable++;
            var baseGrid=ts[0].Margins.Select(x=>x.Units).Intersect(ts[1].Margins.Select(x=>x.Units)).OrderBy(x=>x).ToArray();
            foreach(decimal units in baseGrid)
            {
                decimal usdTarget=units*(qs[0].Bid+qs[0].Ask)/2;
                var grid=ts[2].Margins.Select(x=>x.Units).OrderBy(x=>x).ToArray();
                var hedges=grid.Where(x=>x<=usdTarget).TakeLast(1).Concat(grid.Where(x=>x>=usdTarget).Take(1)).Distinct().ToArray();
                foreach(decimal hedge in hedges)foreach(int orientation in new[]{1,-1})
                {
                    decimal[] volumes={units,units,hedge};int[] sides={orientation,-orientation,orientation};
                    decimal margin=0,cost=0,carry=0,adverseCarry=0;
                    for(int i=0;i<3;i++)
                    {
                        var t=ts[i];var q=qs[i];decimal v=volumes[i];
                        if(v<t.MinUnits||v>t.MaxUnits||t.StepUnits<=0||(v-t.MinUnits)%t.StepUnits!=0)throw new ArgumentException("UNSUPPORTED_BROKER_VOLUME_GRID");
                        var m=t.Margins.Single(x=>x.Units==v);margin+=sides[i]>0?m.BuyEur:m.SellEur;
                        cost+=2*Math.Max(v*q.FeeLinearEurPerUnit,q.FeeFloorEur)+3*(q.Ask-q.Bid)*v*q.EurDebitPerQuote;
                        decimal pip=1;for(int j=0;j<t.PipPosition;j++)pip/=10;
                        decimal raw=v*(sides[i]>0?t.SwapLong!.Value:t.SwapShort!.Value)*pip;
                        decimal eur=raw*(raw>=0?q.EurCreditPerQuote:q.EurDebitPerQuote);carry+=eur;
                        adverseCarry+=eur>=0?Math.Floor(eur/quantum)*quantum:-Math.Ceiling(-eur/quantum)*quantum;
                    }
                    bool capacity=margin>=0&&margin+cost<200;
                    if(capacity){financed++;if(carry>0)positiveRaw++;if(5*adverseCarry-cost>0)positiveFive++;}
                    rows.Add(new {context.Name,context.QuoteAt,Orientation=orientation,BaseUnits=units,HedgeUsdUnits=hedge,
                        ResidualUsd=orientation*(hedge-usdTarget),ResidualJpy=orientation*(units*(qs[1].Bid+qs[1].Ask)/2-hedge*(qs[2].Bid+qs[2].Ask)/2),
                        CurrentQueriedMarginEur=margin,RoundTripCostScenarioEur=cost,RawCarryPerOrdinaryChargeEur=carry,
                        AdverseRoundedCarryPerOrdinaryChargeEur=adverseCarry,CurrentInitialCapitalCapacity=capacity,
                        FlatBasisOneChargeCounterfactualEur=adverseCarry-cost,FlatBasisThreeChargeCounterfactualEur=3*adverseCarry-cost,
                        FlatBasisFiveChargeCounterfactualEur=5*adverseCarry-cost,IsExecutedNet=false});
                }
            }
        }
        return new {Schema="mxm-carry-cycle-preflight-v1",UsableCycles=usable,EnumeratedGridRows=rows.Count,
            CurrentCapacityRows=financed,PositiveRawCarryCapacityRows=positiveRaw,PositiveFiveChargeCounterfactualRows=positiveFive,Rows=rows,
            Verdict=usable==0?"SOURCE_OR_UNIT_SUPPORT_BLOCKED":financed==0?"CURRENT_JOINT_VOLUME_MARGIN_CAPACITY_BLOCKED":positiveRaw==0?
                "CURRENT_TERMS_REJECT_CARRY_ONLY_PREMISE_BEFORE_COSTS":"CONDITIONAL_CASHFLOW_CAPACITY_PRICE_AND_EXECUTION_EVIDENCE_MISSING",
            FullStudyAdmitted=false,PriceReturnsForecast=false,FundingRateContinuityProven=false,HistoricalMarginsProven=false,
            RiskFreeArbitrage=false,ZeroResidualExposureAssumed=false,FundedNetEur=(decimal?)null,IndependentEconomicEdge=false,
            OrdersSubmitted=0,CloudActivated=false};
    }
}
