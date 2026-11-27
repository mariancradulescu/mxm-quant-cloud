using Mxm.Core;
internal static class NativePathDistributionChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long day=86400000L;long at=30*day;
        var rows=Enumerable.Range(1,24).Select(i=>new NativePathSample("A","FX",(i+1)*day,(i+1)*day+1,
            new double?[]{.2,.3,.1},1m,2m,.5m,0m,1m,60m)).ToArray();
        var f=NativeCausalPathDistribution.Estimate(rows,"A","FX",new double?[]{.2,.3,.1},at)!;
        check(f.Mean==1m&&f.LatestAvailableAt<at,"distribution uses mature labels with explicit availability");
        var future=rows[0] with {AvailableAt=at,Outcome=-10000m};
        var g=NativeCausalPathDistribution.Estimate(rows.Append(future),"A","FX",new double?[]{.2,.3,.1},at)!;
        check(f==g||f.Mean==g.Mean&&f.Samples==g.Samples&&f.LowerMean==g.LowerMean,"future perturbation cannot alter distribution");
        check(f.Quantiles.Zip(f.Quantiles.Skip(1)).All(p=>p.First<=p.Second),"conditional quantiles remain ordered");
        check(f.UpperFirstLower==0m&&f.UpperFirstUpper==1m,"ambiguous first passage is retained as bounds");
        check(NativeCausalPathDistribution.Estimate(rows.Select(x=>x with {AvailableAt=day+1,DecisionAt=day}),"A","FX",new double?[]{.2,.3,.1},at) is null,
            "many correlated same-day labels cannot substitute for calendar support");
        check(NativeCausalPathDistribution.Estimate(rows,"B","OTHER",new double?[]{.2,.3,.1},at) is null,
            "transfer requires an official matching asset class");
        check(NativeCausalPathDistribution.Estimate(rows,"B","FX",new double?[]{.2,.3,.1},at,"LOCAL") is null,
            "local ablation excludes peer observations");
    }
}
