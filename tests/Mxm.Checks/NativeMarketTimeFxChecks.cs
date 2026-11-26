using Mxm.Core;
internal static class NativeMarketTimeFxChecks
{
    internal static void Run(Action<bool,string> check)
    {
        const long fri=1794607200000L,sat=fri+86400000L,sun=sat+86400000L,mon=sun+86400000L;
        const long observed=fri-300000L;
        var open=Enumerable.Range(0,288*4).Select(i=>fri-86400000L+i*300000L+15000L)
            .Where(t=>t<fri||t>=sun+3600000L).ToArray();
        var calendar=new NativeMarketTimeCalendar(fri-86400000L,mon+86400000L,open,Array.Empty<long>(),new string('b',64));
        NativeHistoricalFundingPrefix Prefix(long at)=>new("AUTHENTIC_LATEST_PREFIX",observed-1,at,observed,1.1m,true,true);
        check(Prefix(sat).PriceAtCharge(sat,7200000L) is null&&NativeMarketTimeFx.Resolve(Prefix(sat),sat,calendar) is
            {Price:1.1m,ObservedAt:observed,UsedClosedSessions:true,OpenAgeMs:<=7200000L},
            "Verified closed sessions may carry authentic closing FX only in the separate conditional model");
        check(NativeMarketTimeFx.Resolve(Prefix(sun),sun,calendar)?.Price==1.1m&&
            NativeMarketTimeFx.Resolve(Prefix(mon),mon,calendar) is null,
            "Trading-age rule admits weekend closure but rejects more than two hours of reopened FX market");
        check(NativeMarketTimeFx.Resolve(Prefix(sat),sat,null) is null,
            "Missing official calendar never becomes a presumed closed market");
        var ambiguous=new NativeMarketTimeCalendar(fri-86400000L,mon+86400000L,open,new[]{fri+15000L},new string('b',64));
        check(NativeMarketTimeFx.Resolve(Prefix(sat),sat,ambiguous) is null,
            "Ambiguous holiday/session interval cannot support conditional carried FX");
        check(NativeMarketTimeFx.Resolve(Prefix(sat) with {LeadingTimestampComplete=false},sat,calendar) is null&&
            NativeMarketTimeFx.Resolve(Prefix(sat) with {At=sat+1},sat,calendar) is null,
            "Incomplete latest prefix and future quotes remain unsupported");
        var duplicate=new NativeMarketTimeCalendar(fri-86400000L,mon+86400000L,open.Append(open[^1]).ToArray(),Array.Empty<long>(),new string('b',64));
        check(!duplicate.Valid&&NativeMarketTimeFx.Resolve(Prefix(sat),sat,duplicate) is null,
            "Duplicate or unsorted calendar clocks cannot silently erase open trading time");
        check(NativeMarketTimeFx.Resolve(Prefix(sat),sat+1,calendar) is null,
            "Latest-prefix search end must bind to the exact valuation or charge time");
    }
}
