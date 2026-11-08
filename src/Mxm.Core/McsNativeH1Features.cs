using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Native, causal H1 economics signs for original-account cross-class MCS1.
// Zero execution/network/dependency. Linked into the SAME Mxm.Core Cloud cBot.
// These feature signs are not broker orders nor funded EUR settlement.
public sealed record McsH1Bar(long CloseAt,double Open,double High,double Low,
    double Close,long TickVolume);
public sealed record McsH1Frame(string Mechanism,string Symbol,string? Peer,
    long Clock,McsH1Bar[] Target,McsH1Bar[]? PeerBars);
public sealed record McsH1Signs(int Side,int BenchmarkSide,bool Complete);

public static class McsNativeH1Features
{
    public const string Gas="NATGAS_H4_EXHAUSTION_USDX_QUIET_REVERSAL";
    public const string Dollar="USDX_OVERLAP_TWO_HOUR_DRIFT";
    public const string Equity="AMD_US_INTRADAY_TICK_ACTIVITY_EXHAUSTION";
    public const long Hour=3600000L;
    public const long Day=24*Hour;
    static int Sign(double x)=>x>0?1:x<0?-1:0;
    static double Return(double a,double b)=>10000d*Math.Log(a/b);
    static Dictionary<long,McsH1Bar>? Index(McsH1Bar[]? rows,long clock)
    {
        if(rows is null)return null;
        var d=new Dictionary<long,McsH1Bar>();
        foreach(var x in rows)
        {
            if(x.CloseAt>clock)continue;
            if(x.CloseAt<=0 || x.Open<=0 || x.Close<=0 || x.Low<=0 ||
               x.High<x.Low || x.High<x.Open || x.High<x.Close ||
               x.Low>x.Open || x.Low>x.Close || x.TickVolume<0 ||
               !double.IsFinite(x.Open+x.High+x.Low+x.Close) ||
               !d.TryAdd(x.CloseAt,x))return null;
        }
        return d;
    }
    static McsH1Bar[]? Path(Dictionary<long,McsH1Bar>? rows,long t,int n)
    {
        if(rows is null)return null;
        var path=new McsH1Bar[n+1];
        for(int i=0;i<=n;i++)
        {
            if(!rows.TryGetValue(t-i*Hour,out var b))return null;
            path[i]=b;
        }
        return path; // newest first; every H1 interval truly contiguous.
    }
    public static McsH1Signs Evaluate(McsH1Frame x)
    {
        if(x is null || x.Clock<=0 || x.Clock%Hour!=0)
            return new(0,0,false);
        var dt=DateTimeOffset.FromUnixTimeMilliseconds(x.Clock);
        if(dt.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)
            return new(0,0,false);
        int hour=(int)(x.Clock%Day/Hour);
        var d=Index(x.Target,x.Clock);
        if(x.Mechanism==Gas && x.Symbol=="NatGas" && x.Peer=="USDX" &&
           hour>=12 && hour<=19)
        {
            var a=Path(d,x.Clock,4);
            var other=Path(Index(x.PeerBars,x.Clock),x.Clock,2);
            if(a is null||other is null)return new(0,0,false);
            double gas4=Return(a[0].Close,a[4].Close);
            double last=Return(a[0].Close,a[1].Close);
            double usd2=Return(other[0].Close,other[2].Close);
            double older=(a[1].TickVolume+a[2].TickVolume+a[3].TickVolume)/3.0;
            int side=older>0&&Math.Abs(gas4)>=35d&&Math.Abs(usd2)<10d&&
                last*gas4<0&&a[0].TickVolume>=1.10*older ? Sign(last):0;
            return new(side,Sign(gas4),true);
        }
        if(x.Mechanism==Dollar && x.Symbol=="USDX" &&
           hour>=12&&hour<=19)
        {
            var a=Path(d,x.Clock,2);
            if(a is null)return new(0,0,false);
            double drift=Return(a[0].Close,a[2].Close);
            double last=Return(a[0].Close,a[1].Close);
            int side=Math.Abs(drift)>=4d&&Sign(drift)==Sign(last)&&
                a[0].TickVolume>0 ? Sign(drift):0;
            return new(side,1,true); // predeclared same-event USDX long-only.
        }
        if(x.Mechanism==Equity && x.Symbol=="AMD.US" &&
           hour>=15&&hour<=19)
        {
            var a=Path(d,x.Clock,4);
            if(a is null)return new(0,0,false);
            double last=Return(a[0].Close,a[1].Close);
            double prev=(a[1].TickVolume+a[2].TickVolume+
                         a[3].TickVolume+a[4].TickVolume)/4.0;
            int side=prev>0&&Math.Abs(last)>=80d&&
                a[0].TickVolume>=1.25*prev ? -Sign(last):0;
            return new(side,Sign(last),true);
        }
        return new(0,0,false);
    }
    public static McsH1Signs[] EvaluateBatch(McsH1Frame[] frames)=>
        frames.Select(Evaluate).ToArray();
}
