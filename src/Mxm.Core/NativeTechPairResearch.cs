namespace Mxm.Core;

// ETP1: causal lead/lag price discovery on two new extended-session equity CFDs.
// Only completed M5 bars strictly before the original 5-minute quote clock.
internal static class NativeTechPairResearch
{
    internal const string Leader = "ETP1_AAPL_ACCEPTED_RANGE_BREAK";
    internal const string Follower = "ETP1_GOOG_PEER_LAG_CATCHUP";
    internal static (int Side,decimal Magnitude,string Mechanism) Forecast(
        NativeProductMarket market, NativeProductMarket? peer,long at)
    {
        var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minute=utc.Hour*60+utc.Minute;
        if(utc.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday ||
           minute<930 || minute>1020 || at%900000L!=1500L ||
           peer is null) return default;
        var own=Window(market,at);
        var other=Window(peer,at);
        if(own is null || other is null) return default;
        decimal last=Return(own,12,15);
        if(last==0m) return default;
        int side=Math.Sign(last);
        long vol=own.Skip(12).Sum(x=>x.TickVolume);
        long oldVol=own.Skip(8).Take(4).Sum(x=>x.TickVolume);
        if(vol<=oldVol) return default;
        if(market.Symbol=="AAPL.US-24" && peer.Symbol=="GOOG.US-24")
        {
            decimal peerNow=Return(other,12,15);
            var prior=own.Take(12);
            bool accepted=side>0 ? own[^1].Close>prior.Max(x=>x.High):
                                      own[^1].Close<prior.Min(x=>x.Low);
            if(!accepted || side*peerNow<=0m ||
               Math.Abs(last)<=Math.Abs(peerNow))return default;
            decimal magnitude=Math.Min(Math.Abs(last),Math.Abs(peerNow));
            return magnitude>0m?(side,magnitude,Leader):default;
        }
        if(market.Symbol=="GOOG.US-24" && peer.Symbol=="AAPL.US-24")
        {
            decimal earlierPeer=Return(other,8,11);
            if(side*earlierPeer<=0m ||
               Math.Abs(earlierPeer)<2m*Math.Abs(last) ||
               side*(own[^1].Close-own[^2].Close)<=0m ||
               side*(own[^2].Close-own[^3].Close)<=0m)return default;
            decimal magnitude=Math.Min(Math.Abs(earlierPeer),2m*Math.Abs(last))/2m;
            return magnitude>0m?(side,magnitude,Follower):default;
        }
        return default;
    }
    private static NativeClosedMarketBar[]? Window(NativeProductMarket market,long at)
    {
        var b=market.M5.TakeLast(16).ToArray();
        return b.Length==16 && b[^1].CloseAt==at-1500L &&
            b.All(x=>x.CloseAt-x.OpenAt==300000L) &&
            b.Zip(b.Skip(1)).All(x=>x.First.CloseAt==x.Second.OpenAt)
            ? b :null;
    }
    private static decimal Return(NativeClosedMarketBar[] b,int start,int end) =>
        b[end].Close/b[start].Open-1m;
}
