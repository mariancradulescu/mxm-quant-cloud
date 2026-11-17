using System;
using System.Linq;
namespace Mxm.Core;

// Pure cTrader-compatible closed-M1 path features, no broker dependency.
// Receives only 61 genuinely observed contiguous closed M1 OHLC close
// prices and tick-volume observations. Chronology/contiguity must be
// established by caller; an M5 source can NEVER reconstruct this input.
public static class NativeMrf1M1FeatureMath
{
    static double Clip(double v)=>Math.Clamp(v,-4d,4d);
    static int Sign(double v)=>v>0?1:v<0?-1:0;
    static double Rms(double[] v)=>Math.Sqrt(v.Select(x=>x*x).Average());
    public static double[] Compute(double[] closes,double[] tickVolumes)
    {
        if(closes is null || tickVolumes is null ||
           closes.Length!=61 || tickVolumes.Length!=61 ||
           closes.Any(x=>!double.IsFinite(x)||x<=0) ||
           tickVolumes.Any(x=>!double.IsFinite(x)||x<0))
            throw new ArgumentException("MRF1_M1_SOURCE_WINDOW_INVALID");
        var returns=Enumerable.Range(1,60)
            .Select(i=>Math.Log(closes[i]/closes[i-1])).ToArray();
        var last=returns.Skip(55).ToArray();
        var before=returns.Take(55).ToArray();
        double efficiency=last.Sum()/Math.Max(1e-12,last.Sum(x=>Math.Abs(x)));
        double accel=Rms(last)/Math.Max(.0001,Rms(before))-1;
        double flips=Enumerable.Range(1,4)
            .Count(i=>Sign(last[i])!=Sign(last[i-1]))/4d;
        var old=returns.Skip(5).Take(50).ToArray();
        double oldFlips=Enumerable.Range(1,old.Length-1)
            .Count(i=>Sign(old[i])!=Sign(old[i-1]))/(double)(old.Length-1);
        double tickDenom=tickVolumes.Take(56).Sum()/56d*5;
        double activity=tickDenom>0?tickVolumes.Skip(56).Sum()/tickDenom-1:0;
        return new[]{Clip(efficiency),Clip(accel),
            Clip(flips-oldFlips),Clip(activity)};
    }
}
