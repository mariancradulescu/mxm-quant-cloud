using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace Mxm.Core;

// Deterministic rolling FEATURE state, not a predictive strategy nor a
// reconstruction of any frozen model's fitted coefficients.
public sealed record NativeClosedMarketBar(long OpenAt,long CloseAt,decimal Open,
    decimal High,decimal Low,decimal Close,long TickVolume);
public sealed record NativeWarmupInput(string Symbol,string Timeframe,int Minutes,
    long ObservedAt,NativeClosedMarketBar[] ClosedBars);
public sealed record NativeWarmupReport(bool Ready,string Reason,string Symbol,
    string Timeframe,long LastClosedAt,int UsedBars,int MissingIntervals,
    decimal? NormalizedDrift,decimal? MeanAbsoluteReturn,
    decimal? RelativeRange,decimal? RelativeTickActivity,string? EvidenceHash,
    bool ForecastModelRestored=false,bool BrokerDecisionEligible=false);

public static class NativeCausalWarmup
{
    public const int WindowReturns=32;
    public const int WindowBars=WindowReturns+1;
    public static NativeWarmupReport Rebuild(NativeWarmupInput input)
    {
        NativeWarmupReport Reject(string reason,int gaps=0)=>new(false,reason,input.Symbol,
            input.Timeframe,0,0,gaps,null,null,null,null,null);
        if(string.IsNullOrWhiteSpace(input.Symbol)||string.IsNullOrWhiteSpace(input.Timeframe)||
           input.Minutes is not (5 or 60 or 240 or 1440)||input.ObservedAt<=0||
           input.ClosedBars is null)
            return Reject("WARMUP_SYMBOL_TIMEFRAME_OR_CLOCK_UNAVAILABLE");
        if(input.ClosedBars.Length<WindowBars)return Reject("WARMUP_INSUFFICIENT_CLOSED_BARS");
        var rows=input.ClosedBars.TakeLast(WindowBars).ToArray();
        long width=checked(input.Minutes*60000L);
        if(rows.Any(x=>x.OpenAt<0 || x.CloseAt!=x.OpenAt+width ||
             x.CloseAt>input.ObservedAt || x.CloseAt<=x.OpenAt ||
             x.Open<=0m || x.High<x.Open || x.High<x.Close ||
             x.Low>x.Open || x.Low>x.Close || x.Low<=0m ||
             x.Close<=0m || x.High<x.Low || x.TickVolume<0))
            return Reject("WARMUP_INVALID_OR_UNCLOSED_SOURCE_BAR");
        int gaps=0;
        for(int i=1;i<rows.Length;i++)
        {
            if(rows[i].OpenAt<=rows[i-1].OpenAt)
                return Reject("WARMUP_DUPLICATED_OR_REVERSED_BAR");
            if(rows[i].OpenAt!=rows[i-1].CloseAt)gaps++;
        }
        if(input.ObservedAt-rows[^1].CloseAt>2*width)
            return Reject("WARMUP_LAST_BAR_STALE");
        // Weekends and exchange holidays are real time gaps, not fictional
        // zero-volume bars. Exclude their cross-gap returns without inventing
        // an opening price or a broker market-hours history.
        decimal abs=0m,net=0m,range=0m,volume=0m;
        int observedTransitions=0;
        for(int i=1;i<rows.Length;i++)
        {
            if(rows[i].OpenAt!=rows[i-1].CloseAt)continue;
            observedTransitions++;
            decimal prev=rows[i-1].Close;
            decimal r=rows[i].Close/prev-1m;
            net+=r;
            abs+=Math.Abs(r);
            range+=(rows[i].High-rows[i].Low)/rows[i].Open;
            volume+=rows[i].TickVolume;
        }
        if(observedTransitions<16)
            return Reject("WARMUP_TOO_FEW_UNBROKEN_RETURNS",gaps);
        decimal current=rows[^1].TickVolume;
        decimal? activity=volume>0 ? current*observedTransitions/volume:null;
        var hash=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            JsonSerializer.Serialize(new {input.Symbol,input.Timeframe,Rows=rows}))))
            .ToLowerInvariant();
        return new(true,gaps>0
                ?"WARMUP_GAPPED_OBSERVATIONS_EXCLUDED_NOT_MODEL_READY"
                :"WARMUP_CAUSAL_FEATURE_PREFIX_ONLY_NOT_MODEL_READY",
            input.Symbol,input.Timeframe,rows[^1].CloseAt,WindowBars,gaps,
            net/observedTransitions,abs/observedTransitions,
            range/observedTransitions,activity,hash);
    }
}
