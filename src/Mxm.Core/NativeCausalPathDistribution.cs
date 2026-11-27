using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativePathSample(string Symbol,string? AssetClass,long DecisionAt,long AvailableAt,
    double?[] Features,decimal Outcome,decimal Favorable,decimal Adverse,
    decimal UpperFirstLower,decimal UpperFirstUpper,decimal DurationMinutes);
public sealed record NativePathDistributionForecast(int Samples,int Days,decimal EffectiveDays,
    decimal Mean,decimal LowerMean,decimal[] Quantiles,decimal PositiveProbability,
    decimal UpperFirstLower,decimal UpperFirstUpper,decimal MeanFavorable,decimal MeanAdverse,
    decimal ExpectedShortfall,decimal MeanDurationMinutes,decimal RegimeEntropy,long LatestAvailableAt)
{
    public decimal MinimumOutcome { get; init; }
    public decimal MaximumOutcome { get; init; }
}

// An empirical conditional distribution over mature paths, with day-balanced
// context kernels and optional absolute-age forgetting. No order or exit clock.
public static class NativeCausalPathDistribution
{
    public static NativePathDistributionForecast? Estimate(IEnumerable<NativePathSample> history,
        string symbol,string? assetClass,double?[] features,long at,string mode="CONTEXT",int halfLifeDays=28,
        int minimumSamples=24,int minimumDays=5,decimal penalty=1.645m)
    {
        if(mode is not ("LOCAL" or "POOLED" or "CONTEXT")||halfLifeDays<0||minimumSamples<2||minimumDays<2)
            throw new ArgumentException("PATH_DISTRIBUTION_OPTIONS");
        var rows=history.Where(x=>x.AvailableAt<at&&x.DecisionAt<x.AvailableAt&&x.Features.Length==features.Length&&
            x.Favorable>=0m&&x.Adverse>=0m&&x.UpperFirstLower>=0m&&x.UpperFirstLower<=x.UpperFirstUpper&&
            x.UpperFirstUpper<=1m&&x.DurationMinutes>0m&&
            (x.Symbol==symbol||mode!="LOCAL"&&assetClass is not null&&x.AssetClass==assetClass))
            .OrderByDescending(x=>x.AvailableAt).Take(1024).ToArray();
        if(rows.Length<minimumSamples||rows.Select(x=>x.AvailableAt/86400000L).Distinct().Count()<minimumDays)return null;
        var dayCounts=rows.GroupBy(x=>x.AvailableAt/86400000L).ToDictionary(g=>g.Key,g=>g.Count());
        var weighted=rows.Select(x=>
        {
            double distance=0;int dimensions=0;
            if(mode=="CONTEXT")for(int i=0;i<features.Length;i++)
            {
                if(features[i] is double a&&x.Features[i] is double b&&double.IsFinite(a)&&double.IsFinite(b))
                {double delta=Math.Atan(a)-Math.Atan(b);distance+=delta*delta;dimensions++;}
                else if(features[i].HasValue!=x.Features[i].HasValue){distance+=1;dimensions++;}
            }
            double kernel=mode=="CONTEXT"?Math.Exp(-3*distance/Math.Max(1,dimensions)):1;
            double age=halfLifeDays==0?1:Math.Pow(.5,(at-x.AvailableAt)/(86400000d*halfLifeDays));
            double scope=x.Symbol==symbol?1:.25;
            decimal w=(decimal)(kernel*age*scope)/dayCounts[x.AvailableAt/86400000L];
            return (Sample:x,Weight:w);
        }).Where(x=>x.Weight>0m).ToArray();
        decimal total=weighted.Sum(x=>x.Weight);if(total<=0m)return null;
        decimal Mean(Func<NativePathSample,decimal> get)=>weighted.Sum(x=>get(x.Sample)*x.Weight)/total;
        var days=weighted.GroupBy(x=>x.Sample.AvailableAt/86400000L).Select(g=>
        {
            decimal w=g.Sum(x=>x.Weight);return (Weight:w,Mean:g.Sum(x=>x.Sample.Outcome*x.Weight)/w);
        }).ToArray();
        decimal effective=total*total/days.Sum(x=>x.Weight*x.Weight);
        if(effective<minimumDays)return null;
        decimal mean=Mean(x=>x.Outcome);
        decimal variance=days.Sum(x=>x.Weight*(x.Mean-mean)*(x.Mean-mean))/total;
        decimal lower=mean-penalty*(decimal)Math.Sqrt((double)(variance/Math.Max(1m,effective-1m)));
        var sorted=weighted.OrderBy(x=>x.Sample.Outcome).ToArray();
        decimal Quantile(decimal p)
        {
            decimal mass=0m;foreach(var x in sorted){mass+=x.Weight;if(mass>=total*p)return x.Sample.Outcome;}
            return sorted[^1].Sample.Outcome;
        }
        var quantiles=Enumerable.Range(1,9).Select(i=>Quantile(i/10m)).ToArray();
        decimal tailMass=0m,tail=0m;
        foreach(var x in sorted)
        {decimal w=Math.Min(x.Weight,total*.1m-tailMass);if(w<=0m)break;tail+=w*x.Sample.Outcome;tailMass+=w;}
        double entropy=0;
        foreach(var g in weighted.GroupBy(x=>x.Sample.Features.Length>2?Math.Sign(x.Sample.Features[2]??0):0))
        {double p=(double)(g.Sum(x=>x.Weight)/total);entropy-=p*Math.Log(p);}
        return new(rows.Length,days.Length,effective,mean,lower,quantiles,Mean(x=>x.Outcome>0m?1m:0m),
            Mean(x=>x.UpperFirstLower),Mean(x=>x.UpperFirstUpper),Mean(x=>x.Favorable),Mean(x=>x.Adverse),
            tailMass>0m?tail/tailMass:0m,Mean(x=>x.DurationMinutes),(decimal)entropy,rows.Max(x=>x.AvailableAt))
            {MinimumOutcome=rows.Min(x=>x.Outcome),MaximumOutcome=rows.Max(x=>x.Outcome)};
    }
}
