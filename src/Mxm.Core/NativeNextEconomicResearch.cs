using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Core;

// Frozen BEFORE NXE1 source acquisition; not a fitted or validated alpha.
public static class NativeNextEconomicResearch
{
    public const string Existing="NXE1_EURUSD_US500_RISK_TRANSFER";
    public const string New="NXE1_US30_BROAD_INDEX_INDUSTRIAL_RESIDUAL";
    public static (int Side,decimal Magnitude,string Mechanism) Forecast(
        NativeProductMarket market,
        IReadOnlyDictionary<string,NativeProductMarket> all,long at)
    {
        if(at%900000L!=1500L)return default;
        if(!all.TryGetValue("US500",out var broad))return default;
        var own=market.M15.TakeLast(8).ToArray();
        var index=broad.M15.TakeLast(8).ToArray();
        bool Valid(NativeClosedMarketBar[] bars)=>bars.Length==8 &&
            bars[^1].CloseAt==at-1500L && bars.All(x=>x.Close>0m) &&
            bars.Zip(bars.Skip(1)).All(x=>x.First.CloseAt==x.Second.OpenAt);
        if(!Valid(own)||!Valid(index))return default;
        decimal move=own[^1].Close/own[3].Close-1m;
        decimal marketMove=index[^1].Close/index[3].Close-1m;
        if(move==0m || marketMove==0m)return default;
        if(market.Symbol=="EURUSD")
        {
            if(marketMove>=-.001m || move>=0m ||
               Math.Abs(move)>=Math.Abs(marketMove)/3m)return default;
            return (-1,Math.Abs(marketMove)/3m-Math.Abs(move),Existing);
        }
        if(market.Symbol=="US30")
        {
            decimal volume=(own[4].TickVolume+own[5].TickVolume+
                own[6].TickVolume)/3m;
            if(volume<=0m||own[^1].TickVolume>=volume||
               Math.Abs(move-marketMove)<.0005m)return default;
            int side=move<marketMove?1:-1;
            return (side,Math.Abs(move-marketMove)/2m,New);
        }
        return default;
    }
}
