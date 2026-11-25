using System;
using System.Linq;
namespace Mxm.Core;

// CVP1 mathematical indicator/linear-value primitives only. No orders, account
// state, old research policies, hidden data or external runtime dependency.
public static class NativeContextValueResearch
{
    public const int FeatureCount=35;
    public static double Clip(double v)=>Math.Clamp(v,-4d,4d);
    public static double Ema(double[] values,int period)
    {
        if(values.Length<period||values.Any(x=>!double.IsFinite(x)||x<=0))throw new ArgumentException("CVP1_EMA_WINDOW");
        double m=values[0],alpha=2d/(period+1);
        foreach(double v in values.Skip(1))m+=alpha*(v-m);return m;
    }
    public static double[] Frame(NativeClosedMarketBar[] b)
    {
        if(b.Length!=64 || b.Any(x=>x.Open<=0||x.Low<=0||x.High<x.Low||x.Close<x.Low||x.Close>x.High)
            || b.Zip(b.Skip(1)).Any(p=>p.First.CloseAt>p.Second.OpenAt))throw new ArgumentException("CVP1_FRAME_WINDOW");
        double[] c=b.Select(x=>(double)x.Close).ToArray();double tr=0,gain=0,loss=0;
        for(int i=50;i<64;i++)
        {
            tr+=Math.Max((double)(b[i].High-b[i].Low),Math.Max(Math.Abs((double)b[i].High-c[i-1]),Math.Abs((double)b[i].Low-c[i-1])));
            gain+=Math.Max(0,c[i]-c[i-1]);loss+=Math.Max(0,c[i-1]-c[i]);
        }
        double atr=tr/14;if(atr<=0)throw new ArgumentException("CVP1_ZERO_ATR");
        double slow=Ema(c,21),activity=b.Skip(43).Take(20).Average(x=>(double)x.TickVolume);
        double rsi=gain+loss>0?(gain-loss)/(gain+loss):0;
        return new[]{Clip((Ema(c,8)-slow)/atr),Clip((c[^1]-slow)/atr),rsi,
            Clip(activity>0?b[^1].TickVolume/activity-1:0),atr,slow};
    }
    public static double[] Orient(double[] features,int side,string variant)
    {
        if(features.Length!=FeatureCount || side is not (1 or -1) || features.Any(v=>!double.IsFinite(v)))throw new ArgumentException("CVP1_FEATURE_CONTRACT");
        var x=(double[])features.Clone();
        for(int i=0;i<28;i++)if(i%4!=3)x[i]*=side;
        x[28]*=side;for(int i=32;i<35;i++)x[i]*=side;
        if(variant=="NO_PEER")for(int i=32;i<35;i++)x[i]=0;
        if(variant=="NO_ACTIVITY")for(int i=3;i<28;i+=4)x[i]=0;
        return x;
    }
    public static double Predict(double[] beta,double[] x)
    {if(beta.Length!=x.Length+1)throw new ArgumentException("CVP1_DIMENSION");double v=beta[0];for(int i=0;i<x.Length;i++)v+=beta[i+1]*x[i];return v;}
    public static double[] Ridge(double[][] x,double[] y)
    {
        if(x.Length!=y.Length||x.Length==0)throw new ArgumentException("CVP1_TRAIN_EMPTY");
        int n=x[0].Length+1;var a=new double[n,n+1];
        for(int r=0;r<x.Length;r++)
        {
            if(x[r].Length+1!=n||!double.IsFinite(y[r]))throw new ArgumentException("CVP1_TRAIN_INVALID");
            for(int i=0;i<n;i++){double xi=i==0?1:x[r][i-1];a[i,n]+=xi*y[r];for(int j=0;j<n;j++)a[i,j]+=xi*(j==0?1:x[r][j-1]);}
        }
        for(int i=1;i<n;i++)a[i,i]+=16;
        Solve(a,n,1);
        var b=Enumerable.Range(0,n).Select(i=>a[i,n]).ToArray();if(b.Any(v=>!double.IsFinite(v)))throw new ArgumentException("CVP1_NONFINITE_MODEL");return b;
    }
    internal static (double[] Gross,double[] Net) WeightedRidgePair(
        (double[] X,double Gross,double Net,double Weight)[] rows,double ridge)
    {
        int n=rows[0].X.Length;
        var a=new double[n,n+2];
        foreach(var row in rows)
            for(int i=0;i<n;i++)
            {
                double v=row.Weight*row.X[i];
                a[i,n]+=v*row.Gross;
                a[i,n+1]+=v*row.Net;
                for(int j=0;j<=i;j++)a[i,j]+=v*row.X[j];
            }
        for(int i=1;i<n;i++)
        {
            a[i,i]+=ridge;
            for(int j=0;j<i;j++)a[j,i]=a[i,j];
        }
        Solve(a,n,2);
        return (Enumerable.Range(0,n).Select(i=>a[i,n]).ToArray(),
            Enumerable.Range(0,n).Select(i=>a[i,n+1]).ToArray());
    }

    static void Solve(double[,] a,int n,int targets)
    {
        for(int i=0;i<n;i++)
        {
            int pivot=i;for(int r=i+1;r<n;r++)if(Math.Abs(a[r,i])>Math.Abs(a[pivot,i]))pivot=r;
            if(Math.Abs(a[pivot,i])<1e-14)throw new ArgumentException("CVP1_SINGULAR");
            for(int j=i;j<n+targets;j++)(a[i,j],a[pivot,j])=(a[pivot,j],a[i,j]);
            double d=a[i,i];for(int j=i;j<n+targets;j++)a[i,j]/=d;
            for(int r=0;r<n;r++)if(r!=i){double k=a[r,i];for(int j=i;j<n+targets;j++)a[r,j]-=k*a[i,j];}
        }
    }

}
