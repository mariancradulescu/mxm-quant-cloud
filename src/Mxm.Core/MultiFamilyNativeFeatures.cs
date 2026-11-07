using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Deterministic, observation-only Cloud-native economic FEATURE surface.
// No trading, secrets, external network, file persistence or fitted parameters.
public sealed record NativeFamilyBar(long EndAt,double Open,double High,double Low,
    double Close,long TickVolume);
public sealed record NativeFamilyCase(string Symbol,string Peer,long Clock,
    NativeFamilyBar[] Bars,NativeFamilyBar[] PeerBars);
public sealed record NativeFamilySigns(int Squeeze,int Pullback,int VolumeClimax,
    int ReopenGap,int IndexDispersion);

public static class MultiFamilyNativeFeatures
{
    public const long FiveMinutes=300000L;
    public const long FifteenMinutes=900000L;
    public const long Hour=3600000L;
    private static int Sign(double x)=>x>0?1:x<0?-1:0;
    private static bool Valid(NativeFamilyBar b)=>
        b.EndAt>0&&b.Open>0&&b.Close>0&&b.Low>0&&
        b.High>=b.Open&&b.High>=b.Close&&b.High>=b.Low&&
        b.Low<=b.Open&&b.Low<=b.Close&&b.TickVolume>=0&&
        double.IsFinite(b.Open)&&double.IsFinite(b.Close)&&
        double.IsFinite(b.Low)&&double.IsFinite(b.High);
    private static Dictionary<long,NativeFamilyBar>? Index(NativeFamilyBar[]? rows,long clock)
    {
        if(rows==null)return null;
        var d=new Dictionary<long,NativeFamilyBar>();
        foreach(var b in rows)
        {
            if(b.EndAt>clock)continue; // Never use current forming/future samples.
            if(!Valid(b)||d.ContainsKey(b.EndAt))return null;
            d[b.EndAt]=b;
        }
        return d;
    }
    private static NativeFamilyBar[]? Path(
        Dictionary<long,NativeFamilyBar>? d,long t,int intervals)
    {
        if(d is null)return null;
        var arr=new NativeFamilyBar[intervals+1];
        for(int i=0;i<=intervals;i++)
            if(!d.TryGetValue(t-i*FiveMinutes,out arr[i]!))return null;
        return arr; // newest first, completed close at clock.
    }
    public static NativeFamilySigns Evaluate(NativeFamilyCase q)
    {
        if(q==null||q.Clock<=0||string.IsNullOrWhiteSpace(q.Symbol))
            return new(0,0,0,0,0);
        var d=Index(q.Bars,q.Clock);
        var e=Index(q.PeerBars,q.Clock);
        if(d is null)return new(0,0,0,0,0);
        int sq=0,pull=0,climax=0,gap=0,disp=0;
        var r=Path(d,q.Clock,48);
        if(r is not null)
        {
            if(q.Clock%FifteenMinutes==0)
            {
                // 36 older M5 returns, 9 quiet returns, newest 3-bar impulse.
                double older=0,quiet=0;
                for(int i=13;i<=48;i++)
                    older+=Math.Abs(Math.Log(r[i-1].Close/r[i].Close));
                for(int i=4;i<=12;i++)
                    quiet+=Math.Abs(Math.Log(r[i-1].Close/r[i].Close));
                older/=36;quiet/=9;
                double impulse=Math.Log(r[0].Close/r[3].Close);
                if(older>0&&quiet<=.75*older&&
                   Math.Abs(impulse)>=Math.Max(3*quiet,.0002))
                    sq=Sign(impulse);
            }
            if(q.Clock%Hour==0)
            {
                double trend=Math.Log(r[6].Close/r[48].Close);
                double correction=Math.Log(r[0].Close/r[6].Close);
                if(Math.Abs(trend)>=.0006&&trend*correction<0&&
                   Math.Abs(correction)>=.15*Math.Abs(trend)&&
                   Math.Abs(correction)<=.60*Math.Abs(trend))
                    pull=Sign(trend);
            }
        }
        var v=Path(d,q.Clock,24);
        if(v is not null&&q.Clock%FifteenMinutes==0)
        {
            double previous=0,newVolume=0,priorThree=0;
            for(int i=3;i<=23;i++)previous+=v[i].TickVolume;
            for(int i=0;i<=2;i++)newVolume+=v[i].TickVolume;
            for(int i=6;i<=24;i+=3)
                priorThree+=Math.Abs(Math.Log(v[i-3].Close/v[i].Close));
            double move=Math.Log(v[0].Close/v[3].Close);
            if(previous>0&&newVolume/3>=2.5*previous/21&&
               Math.Abs(move)>=Math.Max(1.8*priorThree/7,.0003))
                climax=-Sign(move);
        }
        // Open/close discontinuity after a GENUINE absence of source M5.
        if(d.TryGetValue(q.Clock,out var current))
        {
            NativeFamilyBar? prev=null;
            foreach(var row in d.Values)
                if(row.EndAt<q.Clock&&
                    (prev is null||row.EndAt>prev.EndAt))prev=row;
            if(prev is not null)
            {
                long delta=q.Clock-prev.EndAt;
                if(delta>=Hour&&delta<=72*Hour)
                {
                    double jump=Math.Log(current.Open/prev.Close);
                    if(Math.Abs(jump)>=.0008)gap=-Sign(jump);
                }
            }
        }
        if(q.Clock%Hour==0&&
           (q.Symbol=="US500"||q.Symbol=="NAS100")&&
           ((q.Symbol=="US500"&&q.Peer=="NAS100")||
            (q.Symbol=="NAS100"&&q.Peer=="US500")))
        {
            var peer=Path(e,q.Clock,48);
            if(r is not null&&peer is not null)
            {
                double target=Math.Log(r[0].Close/r[48].Close);
                double leader=Math.Log(peer[0].Close/peer[48].Close);
                double diff=target-leader;
                if(Math.Abs(diff)>=.0008)disp=-Sign(diff);
            }
        }
        return new(sq,pull,climax,gap,disp);
    }
}
