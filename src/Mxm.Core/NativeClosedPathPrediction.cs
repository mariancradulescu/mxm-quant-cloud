using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Information-only forecasts. No order, stop, holding duration, allocation or
// leverage decision is authorized by these scores. Future outcomes are external.
public static class NativeClosedPathPrediction
{
    public sealed record Context(decimal Atr, decimal FastEfficiency, decimal MediumEfficiency,
        decimal SlowEfficiency, decimal FastDisplacement, decimal SlowDisplacement)
    {
        public decimal Alignment => (FastEfficiency+MediumEfficiency+SlowEfficiency)/3m;
        public decimal PullbackRepair => Math.Sign(SlowEfficiency)==Math.Sign(MediumEfficiency) &&
            Math.Sign(FastEfficiency)==-Math.Sign(SlowEfficiency)
            ? (SlowEfficiency+MediumEfficiency)/2m : 0m;
        public decimal Exhaustion => -FastDisplacement*(1m-Math.Abs(FastEfficiency));
    }

    static (decimal Efficiency,decimal Displacement,decimal Atr)? Measure(NativeBarWindow? w,long at,int count)
    {
        if(w is null||!w.Ready||w.Bars.Length<count||w.Bars.Any(b=>b.CloseAt>=at))return null;
        var rows=w.Bars.TakeLast(count).ToArray();
        if(rows.Any(b=>b.Close<=0m||b.Low<=0m||b.Low>b.High)||
            rows.Zip(rows.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt))return null;
        decimal path=0m,range=0m;
        for(int i=1;i<rows.Length;i++)
        {
            var b=rows[i];decimal prev=rows[i-1].Close;
            path+=Math.Abs(b.Close-prev);
            range+=Math.Max(b.High-b.Low,Math.Max(Math.Abs(b.High-prev),Math.Abs(b.Low-prev)));
        }
        decimal atr=range/(rows.Length-1);
        if(atr<=0m)return null;
        decimal delta=rows[^1].Close-rows[0].Close;
        return (path==0m?0m:delta/path,delta/(atr*(rows.Length-1)),atr);
    }

    public static Context? Observe(Ucp1MarketFrame frame,long at)
    {
        if(frame.Quote.At!=at||frame.ClosedBars is not { } windows)return null;
        NativeBarWindow? W(NativeBarTimeframe t)=>windows.Windows.SingleOrDefault(x=>x.Timeframe==t);
        var f=Measure(W(NativeBarTimeframe.M5),at,6);
        var m=Measure(W(NativeBarTimeframe.M15),at,4);
        var s=Measure(W(NativeBarTimeframe.H1),at,4);
        return f is { } a&&m is { } b&&s is { } c
            ?new(a.Atr,a.Efficiency,b.Efficiency,c.Efficiency,a.Displacement,c.Displacement):null;
    }

    // Relative displacement is defined only on synchronized, officially
    // classified peers; no assumed correlation or future peer returns.
    public static decimal? RelativeDisplacement(Context local,IEnumerable<Context> peers)
    {
        var p=peers.ToArray();
        if(p.Length<2)return null;
        return local.SlowDisplacement-p.Average(x=>x.SlowDisplacement);
    }
}
