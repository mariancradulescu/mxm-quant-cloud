using System;
using System.Linq;
using Mxm.Core;

static class SfxNativeChecks
{
    public static void Run(Action<bool,string> check)
    {
        long clock=new DateTimeOffset(2026,11,4,8,15,0,TimeSpan.Zero)
            .ToUnixTimeMilliseconds();
        SfxM15Bar[] Path(double first,double last,long anchor,int count)
            =>Enumerable.Range(0,count+1).Select(i=>new SfxM15Bar(
                anchor-(count-i)*900000L,
                first+(last-first)*i/count,100L)).ToArray();
        var target=Path(100,99.8,clock-900000L,16);
        var peer1=Path(100,100.3,clock-900000L,16);
        var peer2=Path(100,100.25,clock-900000L,16);
        var f=new SfxFeatureFrame(SfxNativeSessionFeatures.Jpy,
            "EURJPY",clock,target,peer1,peer2);
        var decision=SfxNativeSessionFeatures.Evaluate(f);
        check(decision.HistoryComplete && decision.Side==1 &&
            decision.MomentumBenchmarkSide==-1,
            "JPY cross dispersion uses two completed peer H4 returns at fixed London clock");
        var future=target.Append(new SfxM15Bar(clock+900000L,1e9,1000)).ToArray();
        check(SfxNativeSessionFeatures.Evaluate(f with {Target=future})==decision,
            "future M15 price cannot affect sealed earlier JPY decision");
        check(!SfxNativeSessionFeatures.Evaluate(f with {
            PeerA=peer1.Skip(1).ToArray()}).HistoryComplete,
            "missing true H4 M15 interval invalidates session signal");
        check(SfxNativeSessionFeatures.Evaluate(f with {
            Symbol="EURUSD"}).Side==0,"distinct mechanism cannot migrate to converter symbol");
        long nzClock=new DateTimeOffset(2026,11,4,7,0,0,TimeSpan.Zero)
            .ToUnixTimeMilliseconds();
        var nzd=Path(100,100.1,nzClock,28);
        nzd[16]=nzd[16] with {Close=100.2};
        nzd[26]=nzd[26] with {Close=100.2};
        nzd[27]=nzd[27] with {TickVolume=200};
        nzd[28]=nzd[28] with {Close=100.1,TickVolume=200};
        var n=new SfxFeatureFrame(SfxNativeSessionFeatures.Nzd,
            "NZDUSD",nzClock,nzd,null,null);
        check(SfxNativeSessionFeatures.Evaluate(n).HistoryComplete &&
            SfxNativeSessionFeatures.Evaluate(n).Side==-1,
            "NZD H4 prior regime and M15 late reversal coexist causally");
        check(SfxNativeSessionFeatures.Evaluate(n with {Clock=nzClock+900000L}).Side==0,
            "NZD rule trades only fixed eligible clock, no arbitrary M15 grid");
    }
}
