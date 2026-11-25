using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Owned sample arrays must remain immutable for the lifetime of this pair.
public sealed class NativeCompleteDistributionPair
{
    public NativeCompleteDistribution Gross { get; }
    public NativeCompleteDistribution Net { get; }

    public NativeCompleteDistributionPair(NativeCompleteDistribution gross,NativeCompleteDistribution net)
    {
        if(gross.WithoutResidence!=net.WithoutResidence||
           gross.MaskedEconomicContext!=net.MaskedEconomicContext||
           gross.Samples.Length!=net.Samples.Length)
            throw new ArgumentException("COMPLETE_POLICY_PAIRED_GEOMETRY");
        for(int i=0;i<gross.Samples.Length;i++)
        {
            var a=gross.Samples[i];
            var b=net.Samples[i];
            if(a.Symbol!=b.Symbol||a.AssetClass!=b.AssetClass||a.DecisionAt!=b.DecisionAt||
                a.SettledAt!=b.SettledAt||!a.Features.SequenceEqual(b.Features))
                throw new ArgumentException("COMPLETE_POLICY_PAIRED_GEOMETRY");
        }
        Gross=gross;
        Net=net;
    }

    public (NativeCompletePrediction? Gross,NativeCompletePrediction? Net) Predict(decimal[] features,long clock,decimal scale)
        =>Predict(features,clock,scale,out _,null,null);

    internal (NativeCompletePrediction? Gross,NativeCompletePrediction? Net) Predict(decimal[] features,long clock,decimal scale,
        out (decimal Minimum,decimal Maximum) range,string? symbol,string? assetClass)
        =>Gross.PredictPaired(Net,features,clock,scale,out range,symbol,assetClass);

    public NativeCompleteDistributionPair Calibrate()
    {
        using var profile=NativeEconomicProfiler.Measure("distribution.calibrate_pair");
        var residuals=new List<(long Day,decimal Gross,decimal Net)>();
        for(int i=0;i<Gross.Samples.Length;i++)
        {
            var row=Gross.Samples[i];
            var (gross,net)=Predict(row.Features,row.DecisionAt,1m,out _,row.Symbol,row.AssetClass);
            if(gross is null||net is null)
            {
                if(gross is not null||net is not null)throw new InvalidOperationException("COMPLETE_POLICY_PAIRED_SUPPORT");
                continue;
            }
            residuals.Add((row.DecisionAt/NativeCompletePolicy.Day,
                row.OutcomeR-gross.Mean,Net.Samples[i].OutcomeR-net.Mean));
        }
        var grouped=residuals.GroupBy(x=>x.Day).ToArray();
        var calibratedGross=Gross.WithCalibrationErrors(grouped.Select(g=>g.Average(x=>x.Gross)).ToArray());
        var calibratedNet=Net.WithCalibrationErrors(grouped.Select(g=>g.Average(x=>x.Net)).ToArray());
        return new NativeCompleteDistributionPair(calibratedGross,calibratedNet);
    }
}
