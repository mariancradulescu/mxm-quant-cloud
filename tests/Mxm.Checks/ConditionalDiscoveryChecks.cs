using Mxm.Core;
internal static class ConditionalDiscoveryChecks
{
    public static void Run(Action<bool,string> check)
    {
        long day=86400000L,start=1762128000000L,dev=start+26*7*day;
        var samples=Enumerable.Range(0,6).Select(i=>new EmpiricalCostObservation("TEST",start+i*7*day,1,.2,1,1000,30,true,1320,1,2,.001)).ToArray();
        var model=new ConditionalEmpiricalCosts(samples,dev);
        var central=model.Estimate("TEST",dev,1,0,1,60,0);
        check(Math.Abs(central.TotalBps-1.7)<1e-10,"BID-return conditional cost charges one spread plus separate two-side slippage and fees");
        check(central.EvidenceClass=="CONDITIONAL_COST_MODEL"&&!central.ActualFills&&!central.HistoricalTermsVerified,"statistical costs cannot become execution facts");
        var adverse=model.Estimate("TEST",dev,1,.1,1,60,1);var stress=model.Estimate("TEST",dev,1,.1,1,60,2);
        check(adverse.TotalBps>central.TotalBps&&stress.TotalBps>adverse.TotalBps,"declared adverse and stress frictions increase without outcome selection");
        var funding=model.Estimate("TEST",dev+21*3600000L,1,0,-1,120,0);
        check(funding.FinancingBps==6,"current schedule crossing conservatively charges three directional daily debits");
        var unknown=new ConditionalEmpiricalCosts(samples.Select(x=>x with {DailyFundingKnown=false}).ToArray(),dev);
        check(!unknown.Estimate("TEST",dev,1,0,1,60,0).FundingKnown,"unknown funding does not become admissible zero financing");
        bool rejected=false;try{_=new ConditionalEmpiricalCosts(samples.Append(samples[0] with {At=dev}).ToArray(),dev);}catch(ArgumentException){rejected=true;}
        check(rejected,"cost estimates reject post-development observations");
        var filterA=new MultiscaleConditionalResearch.Filter();var filterB=new MultiscaleConditionalResearch.Filter();
        for(int i=0;i<140;i++){
            var b=new ProgramBar("TEST",start+i*300000L,start+(i+1)*300000L,100,101,99,100+Math.Sin(i*.1),100);
            filterA.Observe(b);filterB.Observe(b);
        }
        var bars=Enumerable.Range(0,200).Select(i=>new ProgramBar("TEST",start+i*300000L,start+(i+1)*300000L,100,102,98,100+Math.Sin(i*.1),100)).ToArray();
        var volume=bars.ToDictionary(x=>x.End,_=>1d);
        var full=MultiscaleConditionalResearch.Forecasts(bars,5,4,volume)[0];
        var truncated=MultiscaleConditionalResearch.Forecasts(bars.Take(160).ToArray(),5,4,volume)[0];
        check(truncated.TakeLast(4).All(x=>x.OutcomeBps is null)&&truncated.All(x=>full.Single(f=>f.At==x.At).MeanBps==x.MeanBps),
            "future source truncation retains every earlier forecast and censors only labels, not past admissions");
        var before=filterA.Forecast(4,0);var same=filterB.Forecast(4,0);
        filterB.Observe(new ProgramBar("TEST",start+140*300000L,start+141*300000L,100,201,99,200,100));
        check(before==same&&before.Up is >=0 and <=1&&double.IsFinite(before.Mean),"structural forecasts depend only on observed prefix; later shock cannot mutate prior prediction");
    }
}
