using Mxm.Core;
internal static class NativePathDistributionChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long day=86400000L;long at=30*day;
        check(NativeDistributionTailCapacity.Allows(300m,300m,5m,2m,200m,-3m),
            "tail capacity accepts a candidate financed with held and pending stop commitments");
        check(!NativeDistributionTailCapacity.Allows(300m,300m,5m,2m,200m,-6m),
            "a positive mean cannot make an adverse distribution fit the trade risk budget");
        check(!NativeDistributionTailCapacity.Allows(null,300m,0m,1m,1m,-1m),
            "tail capacity cannot manufacture missing equity");
        check(!NativeDistributionTailCapacity.Allows(211m,300m,0m,2m,1m,-2m),
            "tail capacity preserves the global portfolio drawdown floor");
        check(!NativeDistributionTailCapacity.Allows(300m,300m,5m,2m,208m,-3m),
            "tail capacity reserves risk before comparing margin headroom");
        check(!NativeDistributionTailCapacity.Allows(300m,300m,0m,5m,1m,10m),
            "favorable distribution estimates never release the proposed stop reserve");
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
        var extended=rows.Select((r,i)=>r with {Outcome=(i%5-2)/10m,
            Features=new double?[]{.2,.3,.1,.1,.2,.3,.4,.5,i%5,i%5}}).ToArray();
        double?[] query={.2,.3,.1,.1,.2,.3,.4,.5,4,4};
        var masked=NativeCausalPathDistribution.Estimate(extended,"A","FX",query,at,activeFeatureCount:8)!;
        var copied=NativeCausalPathDistribution.Estimate(extended.Select(r=>r with {Features=r.Features[..8]}),"A","FX",query[..8],at)!;
        check(masked.Mean==copied.Mean&&masked.LowerMean==copied.LowerMean&&masked.ExpectedShortfall==copied.ExpectedShortfall&&
            masked.Quantiles.SequenceEqual(copied.Quantiles)&&masked.Samples==copied.Samples,
            "feature masking is numerically identical to the registered copied-feature ablation");
        check(masked.Mean!=NativeCausalPathDistribution.Estimate(extended,"A","FX",query,at)!.Mean,
            "feature mask removes informative peer columns without cloning mature samples");
    }
}
