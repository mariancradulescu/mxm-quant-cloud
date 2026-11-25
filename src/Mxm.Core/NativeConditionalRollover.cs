using System;
using System.Linq;

namespace Mxm.Core;

// An observed pre-charge endpoint, not a fresh execution quote or a broker
// settlement. Acquisition time is deliberately distinct from market time.
public sealed record NativeConditionalRolloverSide(long At,long[] RawPrices,bool Complete,long AcquiredAt)
{
    public bool Usable(long charge)=>Complete && At>0 && At<=charge &&
        charge-At<=7_200_000L && AcquiredAt>=At &&
        RawPrices is {Length:>0} && RawPrices.All(x=>x>0) &&
        RawPrices.Distinct().Count()==RawPrices.Length;
}

public static class NativeConditionalRollover
{
    // A deterministic adverse choice among genuinely observed endpoint
    // values. This is a model scenario, never a guaranteed bound.
    public static decimal? MarketBid(NativeConditionalRolloverSide? bid,long charge,decimal signedRate)
        =>bid is not null && bid.Usable(charge) ?
            (signedRate<0m?bid.RawPrices.Max():bid.RawPrices.Min())/100_000m:null;

    public static NativeOriginalFxRate? UsdToEur(NativeConditionalRolloverSide? bid,
        NativeConditionalRolloverSide? ask,long charge)
    {
        if(bid is null||ask is null||!bid.Usable(charge)||!ask.Usable(charge))return null;
        decimal lowBid=bid.RawPrices.Min()/100_000m,highAsk=ask.RawPrices.Max()/100_000m;
        if(highAsk<lowBid)return null;
        return new(1m/highAsk,1m/lowBid,new[]{"EURUSD"});
    }
}
