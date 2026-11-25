using System;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;

namespace Mxm.Core;

public enum NativeBarTimeframe
{
    M1 = 1, M5 = 5, M15 = 15, M30 = 30, H1 = 60, H4 = 240, D1 = 1440
}

public enum NativeBarStatus
{
    Ready, SourceMissing, CloseUnobserved, LatestBarMissing, InsufficientHistory,
    MissingInterval, InvalidBar
}

public sealed record NativeBarRequirement(NativeBarTimeframe Timeframe, int Count);

public sealed record NativeBarWindow(NativeBarTimeframe Timeframe, int RequiredBars, long ExpectedCloseAt,
    long? WitnessAt, string Source, NativeBarStatus Status, NativeClosedMarketBar[] Bars)
{
    public bool Ready => Status == NativeBarStatus.Ready;
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public int? DailyCalendarBreaks { get; init; }

    // Provenance is kept separately. These are the exact market values made available to a consumer.
    public string? ValuesSha256() => Ready
        ? Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(new { Timeframe, Bars }))).ToLowerInvariant()
        : null;
}

public sealed record NativeBarContext(long DecisionAt, NativeBarWindow[] Windows)
{
    public NativeBarWindow For(NativeBarTimeframe timeframe) => Windows.Single(w => w.Timeframe == timeframe);
}

public static class NativeClosedMarketContext
{
    // Coverage profile for the source census. Individual mechanisms declare their own requirements.
    public static readonly NativeBarRequirement[] CoverageWindows =
    {
        new(NativeBarTimeframe.M1, 15), new(NativeBarTimeframe.M5, 12),
        new(NativeBarTimeframe.M15, 8), new(NativeBarTimeframe.M30, 8),
        new(NativeBarTimeframe.H1, 6), new(NativeBarTimeframe.H4, 6), new(NativeBarTimeframe.D1, 5)
    };

    public static long Duration(NativeBarTimeframe timeframe) => (int)timeframe * 60_000L;

    // A delayed poll can consider the most recent elapsed clock even before the next bucket's offset.
    public static long LatestClock(long observedAt, long interval, long offset)
    {
        if (interval <= 0L || offset < 0L || offset >= interval || observedAt < offset)
            throw new ArgumentOutOfRangeException(nameof(observedAt));
        return observedAt - (observedAt - offset) % interval;
    }

    public static long? QuoteWitness(long at, long bidAt, long askAt, long maximumAge)
        => bidAt > 0 && askAt > 0 && bidAt <= at && askAt <= at &&
            at - bidAt <= maximumAge && at - askAt <= maximumAge
            ? Math.Max(bidAt, askAt) : null;

    public static NativeBarWindow History(NativeBarRequirement window, long at, long? witnessAt,
        string source, NativeClosedMarketBar[]? history)
        => Read(window, at, witnessAt, source, history?.Length ?? 0,
            i => history![i].OpenAt, i => history![i], platform: false);

    public static NativeBarWindow Platform(NativeBarRequirement window, long at, long? witnessAt,
        int barCount, Func<int, long> openAt, Func<int, NativeClosedMarketBar> read)
        => Read(window, at, witnessAt, "CTRADER_ALGO_BARS", barCount, openAt, read, platform: true);

    // Use only a witnessed successor for daily context. Calendar gaps are
    // retained as evidence; no missing session is replaced by an invented bar.
    public static NativeBarWindow WitnessedDailySessions(int required,long at,long? witnessAt,string source,
        int count,Func<int,long> openAt,Func<int,NativeClosedMarketBar> read)
    {
        const long width=86_400_000L;
        if(at<=0||required<2)throw new ArgumentOutOfRangeException(nameof(at));
        NativeBarWindow Empty(NativeBarStatus status,long expected)
            =>new(NativeBarTimeframe.D1,required,expected,witnessAt,source,status,Array.Empty<NativeClosedMarketBar>());
        if(count==0)return Empty(NativeBarStatus.SourceMissing,0);
        if(witnessAt is not long tick||tick>at)return Empty(NativeBarStatus.CloseUnobserved,0);
        long limit=Math.Min(at-1,tick);
        int left=0,right=count;
        while(left<right)
        {
            int pivot=left+(right-left)/2;
            if(openAt(pivot)<=limit)left=pivot+1;else right=pivot;
        }
        int active=left-1;
        if(active<0||limit-openAt(active)>=width)
            return Empty(NativeBarStatus.LatestBarMissing,0);
        long anchor=openAt(active);
        if(active<required)return Empty(NativeBarStatus.InsufficientHistory,anchor);
        var window=new NativeClosedMarketBar[required];
        int breaks=0;
        for(int i=0;i<required;i++)
        {
            int index=active-required+i;
            var bar=read(index);
            long successor=openAt(index+1);
            if(bar.OpenAt!=openAt(index)||bar.CloseAt!=bar.OpenAt+width||bar.CloseAt>successor||
                bar.CloseAt>=at||bar.OpenAt<0||bar.Low<=0m||bar.Low>Math.Min(bar.Open,bar.Close)||
                bar.High<Math.Max(bar.Open,bar.Close)||bar.TickVolume<0)
                return Empty(NativeBarStatus.InvalidBar,anchor);
            if(bar.CloseAt!=successor)breaks++;
            window[i]=bar;
        }
        return new(NativeBarTimeframe.D1,required,anchor,witnessAt,source,NativeBarStatus.Ready,window)
            { DailyCalendarBreaks=breaks };
    }

    static NativeBarWindow Read(NativeBarRequirement window, long at, long? witnessAt, string source,
        int count, Func<int, long> openAt, Func<int, NativeClosedMarketBar> read, bool platform)
    {
        if (at <= 0 || window.Count <= 0 || !Enum.IsDefined(typeof(NativeBarTimeframe), window.Timeframe))
            throw new ArgumentOutOfRangeException(nameof(window));
        long width = Duration(window.Timeframe);
        long close = (at - 1L) / width * width;
        NativeBarWindow Stop(NativeBarStatus status)
            => new(window.Timeframe, window.Count, close, witnessAt, source, status, Array.Empty<NativeClosedMarketBar>());

        if (count == 0) return Stop(NativeBarStatus.SourceMissing);
        if (witnessAt is not long witness || witness > at) return Stop(NativeBarStatus.CloseUnobserved);

        int FirstAtOrAfter(long boundary, int length)
        {
            int lo = 0, hi = length;
            while (lo < hi)
            {
                int pivot = lo + (hi - lo) / 2;
                if (openAt(pivot) < boundary) lo = pivot + 1;
                else hi = pivot;
            }
            return lo;
        }

        int completed;
        if (window.Timeframe is NativeBarTimeframe.H4 or NativeBarTimeframe.D1)
        {
            // The broker's current opening timestamp anchors this series. Read only that
            // timestamp and require a contemporaneous tick. No mutable OHLC is inspected.
            long lastObservableOpen = Math.Min(at - 1L, witness);
            int active = FirstAtOrAfter(lastObservableOpen + 1L, count) - 1;
            if (active < 0 || lastObservableOpen - openAt(active) >= width)
                return Stop(NativeBarStatus.LatestBarMissing);
            close = openAt(active);
            completed = active;
        }
        else
        {
            if (witness < close) return Stop(NativeBarStatus.CloseUnobserved);
            // GetBars during OnTimer includes a mutable tail. Exclude it even if its nominal
            // time range has elapsed, until the platform has published a successor row.
            completed = FirstAtOrAfter(close, platform ? count - 1 : count);
        }
        // The archived trendbar gives the nominal boundary. A same-symbol market observation
        // from the next bucket is required by the decision clock.
        if (completed == 0 || openAt(completed - 1) < close - width) return Stop(NativeBarStatus.LatestBarMissing);
        if (openAt(completed - 1) != close - width) return Stop(NativeBarStatus.InvalidBar);
        if (completed < window.Count) return Stop(NativeBarStatus.InsufficientHistory);

        var bars = new NativeClosedMarketBar[window.Count];
        for (int j = 0; j < bars.Length; j++)
        {
            var bar = read(completed - bars.Length + j);
            long expectedOpen = close - (bars.Length - j) * width;
            if (bar.OpenAt < expectedOpen) return Stop(NativeBarStatus.MissingInterval);
            if (bar.OpenAt != expectedOpen || bar.OpenAt < 0 || bar.CloseAt != expectedOpen + width ||
                bar.Low <= 0m || bar.Low > Math.Min(bar.Open, bar.Close) ||
                bar.High < Math.Max(bar.Open, bar.Close) || bar.TickVolume < 0)
                return Stop(NativeBarStatus.InvalidBar);
            bars[j] = bar;
        }
        return new(window.Timeframe, window.Count, close, witnessAt, source, NativeBarStatus.Ready, bars);
    }
}
