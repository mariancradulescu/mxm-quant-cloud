namespace Mxm.Core;

// Frozen YRC1 pre-outcome research on original completed M15 and quote-update
// volume; no historical future bars, interpolation or directional inversion.
internal static class NativeYenRiskReleaseResearch
{
    internal const string FailedAuction="YRC1_NZDJPY_FAILED_AUCTION_EQUILIBRIUM";
    internal const string RelativeRepricing="YRC1_CADJPY_RELATIVE_YEN_REPRICING";

    internal static (int Side,decimal Magnitude,string Mechanism) Forecast(
        NativeProductMarket market,
        IReadOnlyDictionary<string,NativeProductMarket> markets,long at)
    {
        if(at%900000L!=1500L)return default;
        var t=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minute=t.Hour*60+t.Minute;
        if(t.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday ||
           minute<240 || minute>360)return default;
        var b=Window(market,at);
        if(b is null)return default;
        if(market.Symbol=="NZDJPY")
        {
            var prior=b.Skip(4).Take(3).ToArray();
            decimal upper=prior.Max(x=>x.High),lower=prior.Min(x=>x.Low);
            decimal mean=b.Average(x=>x.Close);
            decimal body=Math.Abs(b[7].Close-b[7].Open);
            decimal upperWick=b[7].High-Math.Max(b[7].Close,b[7].Open);
            decimal lowerWick=Math.Min(b[7].Close,b[7].Open)-b[7].Low;
            decimal activity=prior.Average(x=>(decimal)x.TickVolume);
            if((decimal)b[7].TickVolume<=activity)return default;
            int side=0;
            if(b[7].High>upper && b[7].Close<upper &&
               upperWick>0m && upperWick>2m*body &&
               b[7].Close>mean)
                side=-1;
            else if(b[7].Low<lower && b[7].Close>lower &&
                    lowerWick>0m && lowerWick>2m*body &&
                    b[7].Close<mean)
                side=1;
            decimal gross=Math.Abs(b[7].Close-mean)/b[7].Close;
            return side!=0 && gross>0m ?(side,gross,FailedAuction):default;
        }
        if(market.Symbol=="CADJPY")
        {
            if(!markets.TryGetValue("CHFJPY",out var chf) ||
               !markets.TryGetValue("USDJPY",out var usd))
                return default;
            var h=Window(chf,at);
            var u=Window(usd,at);
            if(h is null||u is null)return default;
            decimal cad=Move(b),safe=Move(h),dollar=Move(u);
            if(cad==0m||dollar==0m ||
               Math.Sign(cad)!=Math.Sign(dollar) ||
               Math.Abs(cad)<=Math.Abs(safe))return default;
            int side=Math.Sign(cad);
            var prior=b.Skip(4).Take(3).ToArray();
            bool accepted=side>0 ? b[7].Close>prior.Max(x=>x.High):
                                     b[7].Close<prior.Min(x=>x.Low);
            if(!accepted ||
               (decimal)b[7].TickVolume<=prior.Average(x=>(decimal)x.TickVolume))
                return default;
            decimal gross=Math.Min(Math.Abs(cad)-Math.Abs(safe),
                                    Math.Abs(dollar));
            return gross>0m?(side,gross,RelativeRepricing):default;
        }
        return default;
    }
    private static decimal Move(NativeClosedMarketBar[] b)=>
        b[7].Close/b[3].Close-1m;
    private static NativeClosedMarketBar[]? Window(
        NativeProductMarket m,long at)
    {
        var b=m.M15.TakeLast(8).ToArray();
        return b.Length==8 && b[^1].CloseAt==at-1500L &&
               b.All(x=>x.Open>0m && x.Close>0m &&
                   x.High>=x.Low && x.CloseAt-x.OpenAt==900000L) &&
               b.Zip(b.Skip(1)).All(x=>x.First.CloseAt==x.Second.OpenAt)
                   ?b:null;
    }
}
