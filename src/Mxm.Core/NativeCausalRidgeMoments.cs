using System;

namespace Mxm.Core;

// Shared native price-information fit. Economic utility and execution remain
// in the funded common ledger; the prediction horizon is not a profit exit.
public sealed record NativeRidgeEconomicForecast(long DecisionAt,long FitBefore,long LatestTrainingAt,int TrainingDays,
    int HorizonMinutes,string Method,int Side,decimal MeanAtr,decimal FavorableAtr,decimal AdverseAtr,decimal AnchorPrice,decimal Atr);

public sealed class NativeCausalRidgeMoments
{
    public double[,] A=new double[D,D];
    public double[,] B=new double[D,3];
    public double Mass;
    public int Days;
    public long LatestTrainingAt;
    const int D=12;
    public void Add(double[] x,decimal move,decimal up,decimal down,double weight,long availableAt=0)
    {
        Mass+=weight;
        if(x.Length!=D)throw new ArgumentException("RIDGE_FEATURE_DIMENSION");
        LatestTrainingAt=Math.Max(LatestTrainingAt,availableAt);
        double[] y={(double)move,(double)up,(double)down};
        for(int i=0;i<D;i++)
        {
            for(int j=0;j<D;j++)A[i,j]+=weight*x[i]*x[j];
            for(int j=0;j<3;j++)B[i,j]+=weight*x[i]*y[j];
        }
    }
    public void AddDay(NativeCausalRidgeMoments source,double scale)
    {
        if(source.Mass<=0)return;
        Mass+=scale;LatestTrainingAt=Math.Max(LatestTrainingAt,source.LatestTrainingAt);
        for(int i=0;i<D;i++)
        {
            for(int j=0;j<D;j++)A[i,j]+=source.A[i,j]/source.Mass*scale;
            for(int j=0;j<3;j++)B[i,j]+=source.B[i,j]/source.Mass*scale;
        }
    }
    public double[,]? Fit()
    {
        if(Days<20||Mass<=0)return null;
        var a=new double[D,D+3];
        for(int i=0;i<D;i++)
        {
            for(int j=0;j<D;j++)a[i,j]=A[i,j]/Mass+(i==j ? 0.1 : 0.0);
            for(int j=0;j<3;j++)a[i,D+j]=B[i,j]/Mass;
        }
        for(int i=0;i<D;i++)
        {
            int pivot=i;
            for(int j=i+1;j<D;j++)if(Math.Abs(a[j,i])>Math.Abs(a[pivot,i]))pivot=j;
            if(Math.Abs(a[pivot,i])<1e-12)return null;
            if(pivot!=i)for(int j=i;j<D+3;j++)(a[i,j],a[pivot,j])=(a[pivot,j],a[i,j]);
            double z=a[i,i];for(int j=i;j<D+3;j++)a[i,j]/=z;
            for(int k=0;k<D;k++)if(k!=i)
            {
                double v=a[k,i];for(int j=i;j<D+3;j++)a[k,j]-=v*a[i,j];
            }
        }
        var result=new double[D,3];
        for(int i=0;i<D;i++)for(int j=0;j<3;j++)result[i,j]=a[i,D+j];
        return result;
    }
}
