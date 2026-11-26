namespace Mxm.Core;

// Official GetTickDataRes is newest first. hasMore omits older ticks; a
// complete leading timestamp can identify the last available price as of a
// charge without asserting a new quote, an open market, or a broker settlement.
public sealed record NativeHistoricalFundingPrefix(string Status,long SearchFrom,long SearchThrough,
    long At,decimal Price,bool PrefixNewestFirst,bool LeadingTimestampComplete)
{
    public decimal? PriceAtCharge(long charge,long maximumAgeMs)
        =>Status=="AUTHENTIC_LATEST_PREFIX"&&PrefixNewestFirst&&LeadingTimestampComplete&&
          maximumAgeMs>0&&maximumAgeMs<=604_800_000L&&SearchFrom>=0&&SearchThrough==charge&&
          At>=SearchFrom&&At<=charge&&charge-At<=maximumAgeMs&&Price>0m?Price:null;
}
