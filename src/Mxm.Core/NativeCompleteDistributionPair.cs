using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

internal sealed record NativeCompleteResidual(decimal Gross,decimal Net);

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

    public NativeCompleteDistributionPair Calibrate() => Calibrate(Array.Empty<NativeCompleteResidual?>(),out _);

    internal bool CanReuseCalibration(NativeCompleteDistributionPair previous)
    {
        int count=previous.Gross.Samples.Length;
        if(count>Gross.Samples.Length || Gross.MaskedEconomicContext!=previous.Gross.MaskedEconomicContext ||
            Gross.WithoutResidence!=previous.Gross.WithoutResidence)
            return false;
        long lastDecision=0;
        for(int i=0;i<count;i++)
        {
            var old=previous.Gross.Samples[i];
            var current=Gross.Samples[i];
            if(old.Symbol!=current.Symbol || old.AssetClass!=current.AssetClass || old.DecisionAt!=current.DecisionAt ||
                old.SettledAt!=current.SettledAt || old.OutcomeR!=current.OutcomeR ||
                previous.Net.Samples[i].OutcomeR!=Net.Samples[i].OutcomeR ||
                !old.Features.SequenceEqual(current.Features))
                return false;
            lastDecision=Math.Max(lastDecision,old.DecisionAt);
        }
        // A newly matured row may be reused only after proving it could not
        // have been a neighbor of any previously calibrated decision.
        return Gross.Samples.Skip(count).All(row=>row.SettledAt>=lastDecision);
    }

    internal NativeCompleteDistributionPair Calibrate(NativeCompleteResidual?[] prefix,out NativeCompleteResidual?[] residuals)
    {
        using var profile=NativeEconomicProfiler.Measure("distribution.calibrate_pair");
        if(prefix.Length>Gross.Samples.Length)
            throw new ArgumentException("COMPLETE_POLICY_CALIBRATION_PREFIX_LENGTH");
        residuals=new NativeCompleteResidual?[Gross.Samples.Length];
        Array.Copy(prefix,residuals,prefix.Length);
        for(int i=prefix.Length;i<Gross.Samples.Length;i++)
        {
            var row=Gross.Samples[i];
            var (gross,net)=Predict(row.Features,row.DecisionAt,1m,out _,row.Symbol,row.AssetClass);
            if(gross is null||net is null)
            {
                if(gross is not null||net is not null)throw new InvalidOperationException("COMPLETE_POLICY_PAIRED_SUPPORT");
                continue;
            }
            residuals[i]=new(row.OutcomeR-gross.Mean,Net.Samples[i].OutcomeR-net.Mean);
        }
        var grouped=residuals.Select((r,i)=>(Residual:r,Day:Gross.Samples[i].DecisionAt/NativeCompletePolicy.Day))
            .Where(x=>x.Residual is not null).GroupBy(x=>x.Day).ToArray();
        var calibratedGross=Gross.WithCalibrationErrors(grouped.Select(g=>g.Average(x=>x.Residual!.Gross)).ToArray());
        var calibratedNet=Net.WithCalibrationErrors(grouped.Select(g=>g.Average(x=>x.Residual!.Net)).ToArray());
        return new NativeCompleteDistributionPair(calibratedGross,calibratedNet);
    }
}
