using System;
using System.Linq;
using System.Collections.Generic;

namespace Mxm.Core;

// Two prospectively registered FX session mechanisms. Completed M15 OHLCV
// only; no price/outcome lookahead, orders, Python, storage or internet needed.
// Linked into the same Mxm.Core as the final cTrader Cloud observation cBot.
public sealed record SfxM15Bar(long CloseAt, double Close, long TickVolume);
public sealed record SfxFeatureFrame(
    string Mechanism,string Symbol,long Clock,SfxM15Bar[] Target,
    SfxM15Bar[]? PeerA,SfxM15Bar[]? PeerB);
public sealed record SfxFeatureDecision(int Side,int MomentumBenchmarkSide,bool HistoryComplete);

public static class SfxNativeSessionFeatures
{
    public const string Jpy="JPY_BASKET_0815_DISPERSION_RECOMPRESSION_M15_H4";
    public const string Nzd="NZDUSD_0700_H4_TO_M15_INTRASESSION_REVERSAL";
    const long Fifteen=900000L;
    const long Day=86400000L;

    static int Sign(double x)=>x>0d?1:x<0d?-1:0;
    static Dictionary<long,SfxM15Bar>? Index(SfxM15Bar[]? rows,long at)
    {
        if(rows is null)return null;
        var o=new Dictionary<long,SfxM15Bar>();
        foreach(var b in rows)
        {
            if(b.CloseAt>at)continue;
            if(b.CloseAt<=0||b.Close<=0||b.TickVolume<0||
               !double.IsFinite(b.Close)||!o.TryAdd(b.CloseAt,b))return null;
        }
        return o;
    }
    static double[]? Complete(Dictionary<long,SfxM15Bar>? bars,long end,int count)
    {
        if(bars is null)return null;
        var closes=new double[count+1];
        for(int i=0;i<=count;i++)
        {
            if(!bars.TryGetValue(end-i*Fifteen,out var b))return null;
            closes[i]=b.Close;
        }
        return closes;
    }
    static double ReturnBps(double newer,double older)=>10000d*Math.Log(newer/older);

    public static SfxFeatureDecision Evaluate(SfxFeatureFrame x)
    {
        if(x is null||x.Clock<=0||x.Clock%Fifteen!=0)
            return new(0,0,false);
        var date=DateTimeOffset.FromUnixTimeMilliseconds(x.Clock);
        if(date.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)
            return new(0,0,false);
        long local=x.Clock%Day;
        var target=Index(x.Target,x.Clock);
        if(x.Mechanism==Jpy && (x.Symbol is "EURJPY" or "AUDJPY" or "NZDJPY") &&
           local==8*3600000L+15*60000L)
        {
            // Last *complete* H4 close was 08:00; count all 16 M15 slots.
            var a=Complete(target,x.Clock-Fifteen,16);
            var b=Complete(Index(x.PeerA,x.Clock),x.Clock-Fifteen,16);
            var c=Complete(Index(x.PeerB,x.Clock),x.Clock-Fifteen,16);
            if(a is null||b is null||c is null)return new(0,0,false);
            double self=ReturnBps(a[0],a[16]);
            double p=ReturnBps(b[0],b[16]);
            double q=ReturnBps(c[0],c[16]);
            double mean=(p+q)/2d,disp=self-mean;
            // Common JPY pressure on BOTH peers, material idiosyncratic gap.
            int side=Sign(p)==Sign(q)&&Math.Abs(mean)>=8d&&Math.Abs(disp)>=12d?
                -Sign(disp):0;
            return new(side,Sign(self),true);
        }
        if(x.Mechanism==Nzd && x.Symbol=="NZDUSD" && local==7*3600000L)
        {
            var a=Complete(target,x.Clock,28);
            if(a is null||target is null)return new(0,0,false);
            double h4=ReturnBps(a[12],a[28]); // 04:00 vs 00:00 H4
            double micro=ReturnBps(a[0],a[2]); // 07:00 vs 06:30 M15
            decimal recent=0m,older=0m;
            for(int i=0;i<=1;i++)recent+=target[x.Clock-i*Fifteen].TickVolume;
            for(int i=2;i<=5;i++)older+=target[x.Clock-i*Fifteen].TickVolume;
            bool activity=older>0 && recent/2m>=1.1m*older/4m;
            int side=Math.Abs(h4)>=8d && Math.Abs(micro)>=4d &&
                Sign(h4)*Sign(micro)==-1 && activity?Sign(micro):0;
            return new(side,Sign(h4),true);
        }
        return new(0,0,false);
    }
    public static SfxFeatureDecision[] EvaluateBatch(SfxFeatureFrame[] frames)=>
        frames.Select(Evaluate).ToArray();
}
