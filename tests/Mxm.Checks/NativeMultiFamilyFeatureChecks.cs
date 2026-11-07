using System;
using System.Linq;
using Mxm.Core;

public static class NativeMultiFamilyFeatureChecks
{
    public static void Run(Action<bool,string> check)
    {
        long t=100*MultiFamilyNativeFeatures.Hour;
        var baseBars=Enumerable.Range(0,97).Select(i=>{
            long at=t-(96-i)*MultiFamilyNativeFeatures.FiveMinutes;
            double close=100.0+(i%4==0?.01:0);
            return new NativeFamilyBar(at,close,close+.1,close-.1,close,10);
        }).ToArray();
        var baseline=MultiFamilyNativeFeatures.Evaluate(
            new NativeFamilyCase("EURUSD","",t,baseBars,
            Array.Empty<NativeFamilyBar>()));
        var future=baseBars.Append(new NativeFamilyBar(t+300000,1e9,1e9,1,1e9,1)).ToArray();
        var after=MultiFamilyNativeFeatures.Evaluate(
            new NativeFamilyCase("EURUSD","",t,future,
            Array.Empty<NativeFamilyBar>()));
        check(baseline==after,"MFA1 future/unfinished bar does not change any causal signal");
        var gapBars=new[]{
            new NativeFamilyBar(t-2*MultiFamilyNativeFeatures.Hour,100,100.1,99.9,100,10),
            new NativeFamilyBar(t,101,101.3,100.9,101.2,10)
        };
        var gap=MultiFamilyNativeFeatures.Evaluate(
            new NativeFamilyCase("EURUSD","",t,gapBars,
                Array.Empty<NativeFamilyBar>()));
        check(gap.ReopenGap==-1&&gap.Squeeze==0&&gap.Pullback==0,
            "MFA1 genuine source-market reopen gap can fade without fabricated contiguous bars");
        var madeUp=MultiFamilyNativeFeatures.Evaluate(
            new NativeFamilyCase("EURUSD","",t,new[]{
                gapBars[0] with { EndAt=t-300000 },gapBars[1]},
                Array.Empty<NativeFamilyBar>()));
        check(madeUp.ReopenGap==0,
            "MFA1 a normal contiguous bar is never falsely labeled a market reopen");
        var target=baseBars.Select((row,i)=>row with {
            Close=i==96?101:(i==48?99.0:100.0),
            Open=100.0,High=102.0,Low=98.0}).ToArray();
        var other=baseBars.Select(row=>row with {
            Open=100.0,High=101.0,Low=99.0,Close=100.0}).ToArray();
        var relative=MultiFamilyNativeFeatures.Evaluate(
            new NativeFamilyCase("US500","NAS100",t,target,other));
        check(relative.IndexDispersion==-1,
            "MFA1 4h US500/NAS100 relative outperformance is faded using CLOSED peer bars only");
        var missing=MultiFamilyNativeFeatures.Evaluate(
            new NativeFamilyCase("US500","NAS100",t,target,
                other.Where(row=>row.EndAt!=t-15*300000).ToArray()));
        check(missing.IndexDispersion==0,
            "MFA1 missing peer bar stops relative feature without interpolation");
        var noPrice=MultiFamilyNativeFeatures.Evaluate(
            new NativeFamilyCase("US500","NAS100",t+300000,target,other));
        check(noPrice==new NativeFamilySigns(0,0,0,0,0),
            "MFA1 no current closed target bar implies abstention");
    }
}
