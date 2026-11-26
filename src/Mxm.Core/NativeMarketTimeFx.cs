namespace Mxm.Core;

// Conditional historical valuation: closing prices are carried over verified
// closed sessions. This is not a broker settlement or executable FX.
public sealed class NativeMarketTimeCalendar
{
    readonly long[] opened,ambiguous;
    readonly long from,through;
    const long StepMs=300000L,OffsetMs=15000L;
    public string EvidenceSha256 { get; }
    public bool Valid { get; }
    public NativeMarketTimeCalendar(long from,long through,long[]? openClocks,long[]? ambiguousClocks,string evidenceSha256)
    {
        this.from=from;this.through=through;EvidenceSha256=evidenceSha256;
        opened=openClocks?.ToArray()??Array.Empty<long>();ambiguous=ambiguousClocks?.ToArray()??Array.Empty<long>();
        bool Grid(long[] rows)=>rows.Select((t,i)=>t>=from&&t<through&&t%StepMs==OffsetMs&&(i==0||t>rows[i-1])).All(x=>x);
        Valid=from>=0&&through>from&&evidenceSha256 is {Length:64}&&evidenceSha256.All(Uri.IsHexDigit)&&
            openClocks is not null&&ambiguousClocks is not null&&Grid(opened)&&Grid(ambiguous);
    }
    static int Upper(long[] rows,long at)
    {int i=Array.BinarySearch(rows,at);return i<0?~i:i+1;}
    public long? OpenAge(long observed,long at)
    {
        if(!Valid||observed<from||at>=through||at<observed)return null;
        long lo=observed-(observed-OffsetMs)%StepMs,hi=at+(StepMs-(at-OffsetMs)%StepMs)%StepMs;
        if(Upper(ambiguous,hi)>Upper(ambiguous,lo-1))return null;
        return (Upper(opened,hi)-Upper(opened,lo-1))*StepMs;
    }
}
public sealed record NativeMarketTimePrice(decimal Price,long ObservedAt,long WallAgeMs,
    long OpenAgeMs,bool UsedClosedSessions,string CalendarSha256);
public static class NativeMarketTimeFx
{
    public static NativeMarketTimePrice? Resolve(NativeHistoricalFundingPrefix prefix,long at,
        NativeMarketTimeCalendar? calendar,long maximumOpenAgeMs=7200000L)
    {
        if(prefix.PriceAtCharge(at,345600000L) is not decimal price||maximumOpenAgeMs<=0)return null;
        long wall=at-prefix.At;
        if(wall<=maximumOpenAgeMs)return new(price,prefix.At,wall,wall,false,calendar?.EvidenceSha256??"");
        long? open=calendar?.OpenAge(prefix.At,at);
        return open is long elapsed&&elapsed<=maximumOpenAgeMs&&elapsed<wall
            ?new(price,prefix.At,wall,elapsed,true,calendar!.EvidenceSha256):null;
    }
}
