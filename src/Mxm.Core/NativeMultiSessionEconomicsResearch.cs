namespace Mxm.Core;

// MSE1: NEW predeclared, original USD broker account multi-class economic
// predictors. Completed and contiguous M15 only; no future bars or prices.
internal static class NativeMultiSessionEconomicsResearch
{
    internal const string Index = "MSE1_US2000_US500_BREADTH_ACCEPTANCE";
    internal const string Oil = "MSE1_SPOTCRUDE_EQUITY_RISK_SYNC_ACCEPTANCE";
    internal const string Agriculture = "MSE1_COFFEE_AGRICULTURE_FAILED_AUCTION";

    internal static (int Side,decimal Magnitude,string Mechanism) Forecast(
        NativeProductMarket market,
        IReadOnlyDictionary<string,NativeProductMarket> universe,long at)
    {
        if(at%900000L!=1500L)return default;
        var clock=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        if(clock.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)return default;
        int minute=clock.Hour*60+clock.Minute;
        if(minute<900 || minute>1035)return default;

        var bars=CompletedEight(market,at);
        if(bars is null)return default;
        var previous=bars.Skip(4).Take(3).ToArray();
        decimal recentActivity=previous.Average(x=>(decimal)x.TickVolume);
        if(bars[7].TickVolume<=recentActivity || recentActivity<=0m)return default;

        if(market.Symbol is "US2000" or "SpotCrude")
        {
            if(!universe.TryGetValue("US500",out var broad))return default;
            var reference=CompletedEight(broad,at);
            if(reference is null)return default;
            decimal move=bars[7].Close/bars[3].Close-1m;
            decimal broadMove=reference[7].Close/reference[3].Close-1m;
            if(move==0m || broadMove==0m ||
               Math.Sign(move)!=Math.Sign(broadMove))return default;
            int side=Math.Sign(move);
            if(side>0 && bars[7].Close<=previous.Max(x=>x.High) ||
               side<0 && bars[7].Close>=previous.Min(x=>x.Low))return default;
            decimal remaining=Math.Min(Math.Abs(move),Math.Abs(broadMove));
            decimal projected=remaining * (market.Symbol=="US2000"?0.65m:0.5m);
            return projected>0m?(side,projected,
                market.Symbol=="US2000"?Index:Oil):default;
        }

        if(market.Symbol!="Coffee")return default;
        var last=bars[7];
        decimal ceiling=previous.Max(x=>x.High);
        decimal floor=previous.Min(x=>x.Low);
        decimal mean=bars.Average(x=>x.Close);
        decimal body=Math.Abs(last.Close-last.Open);
        bool upper=last.High>ceiling && last.Close<ceiling &&
                    last.High-Math.Max(last.Open,last.Close)>2m*body &&
                    last.Close>mean;
        bool lower=last.Low<floor && last.Close>floor &&
                    Math.Min(last.Open,last.Close)-last.Low>2m*body &&
                    last.Close<mean;
        if(upper==lower)return default; // exactly one failed auction edge
        decimal target=Math.Abs(last.Close-mean)/last.Close;
        return target>0m?(upper?-1:1,target,Agriculture):default;
    }

    private static NativeClosedMarketBar[]? CompletedEight(
        NativeProductMarket market,long at)
    {
        var b=market.M15.TakeLast(8).ToArray();
        if(b.Length!=8 || b[^1].CloseAt!=at-1500L ||
           b.Any(x=>x.CloseAt-x.OpenAt!=900000L || x.Open<=0 ||
                x.Close<=0 || x.Low<=0 || x.High<x.Low ||
                x.Close>x.High || x.Close<x.Low) ||
           b.Zip(b.Skip(1)).Any(x=>x.First.CloseAt!=x.Second.OpenAt))
            return null;
        return b;
    }
}
