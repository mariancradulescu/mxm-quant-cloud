using System;
using System.Linq;
namespace Mxm.Core;

// Bounded pure native C# predictor math for PVE3. The final Cloud cBot can
// perform this math without Python, HTTP, platform orders or background daemon.
// Bars, tick volume and peer feature INPUTS require a separate causal
// closed-bar native parity test; this class does not certify that collection.
public static class NativePve3FeatureMath
{
    static double Clip(double x)=>Math.Clamp(x,-4d,4d);
    public static double[] Expand(double[] core)
    {
        if(core is null || core.Length!=13 || core.Any(x=>double.IsNaN(x)||double.IsInfinity(x)))
            throw new ArgumentException("PVE3_INVALID_CORE_FEATURES");
        return core.Concat(new[]{
            Clip(core[0]*core[3]),Clip(core[6]*core[7]),
            Clip(core[4]*core[9]),Clip(core[8]*core[2])
        }).ToArray();
    }
    public static double Predict(double[] beta,double[] x,int[] columns)
    {
        if(beta is null || x is null || columns is null ||
           beta.Length!=columns.Length+1 || x.Length!=17 ||
           columns.Any(i=>i<0 || i>=x.Length) ||
           beta.Any(v=>!double.IsFinite(v)) || x.Any(v=>!double.IsFinite(v)))
            throw new ArgumentException("PVE3_RIDGE_MODEL_OR_FEATURE_INVALID");
        double value=beta[0];
        for(int k=0;k<columns.Length;k++)value+=beta[k+1]*x[columns[k]];
        return value;
    }
}
