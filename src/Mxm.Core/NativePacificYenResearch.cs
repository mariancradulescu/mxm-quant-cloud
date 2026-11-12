namespace Mxm.Core;

// JYP1: separate AUDJPY/NZDJPY Pacific-session economic hypotheses.
// All inputs are completed contiguous M15 bars, known at decision-1500ms.
internal static class NativePacificYenResearch
{
    internal const string CatchUp = "JYP1_NZDJPY_YEN_RISK_DELAYED_CATCHUP";
    internal const string Acceptance = "JYP1_AUDJPY_PACIFIC_ACCEPTANCE";

    internal static (int Side,decimal Magnitude,string Mechanism) Forecast(
        NativeProductMarket market,NativeProductMarket? peer,long at)
    {
        if(peer is null || at%900000L!=1500L)return default;
        var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minute=utc.Hour*60+utc.Minute;
        if(utc.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday ||
           minute<195 || minute>315)return default;
        var own=Window(market,at);
        var other=Window(peer,at);
        if(own is null || other is null)return default;

        decimal myMove=own[7].Close/own[3].Close-1m;
        decimal peerMove=other[7].Close/other[3].Close-1m;
        if(myMove==0m || peerMove==0m || Math.Sign(myMove)!=Math.Sign(peerMove))
            return default;
        int side=Math.Sign(peerMove);

        if(market.Symbol=="NZDJPY" && peer.Symbol=="AUDJPY")
        {
            decimal gap=Math.Abs(peerMove)-Math.Abs(myMove);
            if(gap<=0m || side*(own[7].Close-own[7].Open)<=0m)
                return default;
            decimal target=Math.Min(gap,Math.Abs(peerMove)/2m);
            return target>0m?(side,target,CatchUp):default;
        }
        if(market.Symbol=="AUDJPY" && peer.Symbol=="NZDJPY")
        {
            var previous=own.Skip(4).Take(3).ToArray();
            bool outside=side>0 ?
                own[7].Close>previous.Max(x=>x.High) :
                own[7].Close<previous.Min(x=>x.Low);
            decimal meanActivity=previous.Average(x=>(decimal)x.TickVolume);
            if(!outside || own[7].TickVolume<=meanActivity)return default;
            decimal target=Math.Min(Math.Abs(myMove),Math.Abs(peerMove))/2m;
            return target>0m?(side,target,Acceptance):default;
        }
        return default;
    }

    private static NativeClosedMarketBar[]? Window(NativeProductMarket m,long at)
    {
        var b=m.M15.TakeLast(8).ToArray();
        if(b.Length!=8 || b[^1].CloseAt!=at-1500L ||
           b.Any(x=>x.CloseAt-x.OpenAt!=900000L ||
               x.Open<=0m || x.Close<=0m || x.High<x.Low) ||
           b.Zip(b.Skip(1)).Any(z=>z.First.CloseAt!=z.Second.OpenAt))
            return null;
        return b;
    }
}
