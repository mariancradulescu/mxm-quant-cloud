namespace Mxm.Core;

public sealed record EmpiricalCostObservation(string Symbol,long At,double SpreadBps,double CommissionBps,
    double PastVolBps,double MinimumNotionalEur,decimal CurrentMinimumMarginEur,
    bool DailyFundingKnown,int SwapMinute,double LongDailyDebitBps,double ShortDailyDebitBps,double ProfitConversionRate=0);
public sealed record ConditionalCostEstimate(string EvidenceClass,int Scenario,double SpreadBps,double CommissionBps,
    double SlippageBps,double FinancingBps,double TotalBps,int Samples,int DistinctDates,string Cell,
    bool FundingKnown,double ProfitConversionRate,bool HistoricalTermsVerified=false,bool ActualFills=false);

// A predeclared statistical scenario on observed development quotes/current terms.
// Never fabricated historical quotes; never use together with an ASK/BID fill charge.
public sealed class ConditionalEmpiricalCosts
{
    readonly Dictionary<string,EmpiricalCostObservation[]> samples;
    public ConditionalEmpiricalCosts(EmpiricalCostObservation[] observations,long developmentEnd)
    {
        if(observations.Any(x=>x.At>=developmentEnd || x.At<=0 || x.SpreadBps<0 || x.CommissionBps<0 ||
            x.PastVolBps<0 || x.MinimumNotionalEur<=0 || x.CurrentMinimumMarginEur<=0 ||
            !double.IsFinite(x.SpreadBps+x.CommissionBps+x.PastVolBps+x.MinimumNotionalEur+x.LongDailyDebitBps+x.ShortDailyDebitBps) ||
            x.LongDailyDebitBps<0 || x.ShortDailyDebitBps<0 || x.ProfitConversionRate<0 || !double.IsFinite(x.ProfitConversionRate) || x.DailyFundingKnown&&(x.SwapMinute<0||x.SwapMinute>=1440)) ||
            observations.GroupBy(x=>(x.Symbol,x.At)).Any(g=>g.Count()!=1))throw new ArgumentException("INVALID_DEVELOPMENT_COST_OBSERVATIONS");
        samples=observations.GroupBy(x=>x.Symbol).ToDictionary(g=>g.Key,g=>g.OrderBy(x=>x.At).ToArray());
    }
    public static double Quantile(IEnumerable<double> values,double p)
    {
        var a=values.OrderBy(x=>x).ToArray();if(a.Length==0)return 0;
        double ix=(a.Length-1)*p;int i=(int)ix;return a[i]+(a[Math.Min(i+1,a.Length-1)]-a[i])*(ix-i);
    }
    static int Dates(IEnumerable<EmpiricalCostObservation> a)=>a.Select(x=>x.At/86400000).Distinct().Count();
    static double DaySe(EmpiricalCostObservation[] a)
    {
        var daily=a.GroupBy(x=>x.At/86400000).Select(g=>g.Average(x=>x.SpreadBps)).ToArray();
        if(daily.Length<2)return 0;double m=daily.Average();return Math.Sqrt(daily.Sum(x=>(x-m)*(x-m))/(daily.Length-1)/daily.Length);
    }
    public ConditionalCostEstimate Estimate(string symbol,long at,double m5Vol,double latencyVol,int side,int horizonMinutes,int scenario)
    {
        if(scenario is <0 or >2 || side is not (-1 or 1) || horizonMinutes<=0 || m5Vol<0 || latencyVol<0 ||
            !double.IsFinite(m5Vol+latencyVol))throw new ArgumentException("INVALID_COST_REQUEST");
        if(!samples.TryGetValue(symbol,out var all)||all.Length==0)throw new ArgumentException("COST_SOURCE_MISSING");
        if(all.Any(x=>x.At>=at))throw new ArgumentException("COST_ESTIMATION_NOT_PAST_DEVELOPMENT");
        int hour=DateTimeOffset.FromUnixTimeMilliseconds(at).Hour/8;
        double median=Quantile(all.Select(x=>x.PastVolBps),.5);
        var local=all.Where(x=>DateTimeOffset.FromUnixTimeMilliseconds(x.At).Hour/8==hour && (x.PastVolBps>median)==(m5Vol>median)).ToArray();
        string cell="INSTRUMENT_HOUR_VOL";
        bool Supported(EmpiricalCostObservation[] a)=>a.Length>=4&&Dates(a)>=3;
        if(!Supported(local)){local=all.Where(x=>DateTimeOffset.FromUnixTimeMilliseconds(x.At).Hour/8==hour).ToArray();cell="INSTRUMENT_HOUR_FALLBACK";}
        if(!Supported(local)){local=all;cell="INSTRUMENT_GLOBAL_FALLBACK";}
        double spread=scenario==0?local.Average(x=>x.SpreadBps):scenario==1?
            Math.Max(Quantile(local.Select(x=>x.SpreadBps),.9),local.Average(x=>x.SpreadBps)+2.5*DaySe(local)):
            2*all.Max(x=>x.SpreadBps)+2.5*DaySe(all);
        double commissions=scenario==0?local.Average(x=>x.CommissionBps):(scenario==2?2:1)*all.Max(x=>x.CommissionBps);
        double slip=2*((scenario==0?.25:scenario==1?.5:1)*spread+(scenario+1)*latencyVol);
        bool known=all.All(x=>x.DailyFundingKnown)&&all.Select(x=>x.SwapMinute).Distinct().Count()==1;
        double finance=0;
        if(known)
        {
            long end=at+horizonMinutes*60000L,day=at/86400000;int minute=all[0].SwapMinute;
            for(long t=day*86400000+minute*60000L;t<=end;t+=86400000)
                if(t>at)finance+=3*all.Max(x=>side>0?x.LongDailyDebitBps:x.ShortDailyDebitBps);
        }
        return new("CONDITIONAL_COST_MODEL",scenario,spread,commissions,slip,finance,
            spread+commissions+slip+finance,local.Length,Dates(local),cell,known,all.Max(x=>x.ProfitConversionRate));
    }
    public object[] Describe()=>samples.OrderBy(x=>x.Key).Select(p=>{
        var a=p.Value;int n=Dates(a);
        return (object)new {Symbol=p.Key,Samples=a.Length,DistinctDates=n,
            MeanObservedSpreadBps=a.Average(x=>x.SpreadBps),P90ObservedSpreadBps=Quantile(a.Select(x=>x.SpreadBps),.9),
            MaxObservedSpreadBps=a.Max(x=>x.SpreadBps),DateMeanSpreadSe=DaySe(a),
            MeanCurrentCommissionRoundTripBps=a.Average(x=>x.CommissionBps),
            MinimumNotionalEur=a.Max(x=>x.MinimumNotionalEur),CurrentMinimumMarginEur=a.Max(x=>x.CurrentMinimumMarginEur),
            CurrentMarginBeforeCostsFitsInitial200=a.Max(x=>x.CurrentMinimumMarginEur)<200,
            AllDailyFundingKnown=a.All(x=>x.DailyFundingKnown),
            ZeroDistributionFree95PercentTailGuarantee=true,
            IllustrativeIidDateProbabilityMaxCovers95thPercentile=1-Math.Pow(.95,n),
            IidDatesNotEstablished=true,SpreadObservationClass="OBSERVED_HISTORICAL_BID_ASK_CONTEXTS",TariffObservationClass="CURRENT_TARIFF_SCENARIO",SlippageObservationClass="UNMEASURED_DECLARED_SCENARIOS",CostClassification="CONDITIONAL_COST_MODEL",HistoricalTermsVerified=false};
    }).ToArray();
}
