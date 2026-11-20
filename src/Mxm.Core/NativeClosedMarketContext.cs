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
            i => history![i].OpenAt, i => history![i]);

    public static NativeBarWindow Platform(NativeBarRequirement window, long at, long? witnessAt,
        int barCount, Func<int, long> openAt, Func<int, NativeClosedMarketBar> read)
        // MarketData.GetBars includes a mutable tail during OnTimer. A successor must have appeared.
        => Read(window, at, witnessAt, "CTRADER_ALGO_BARS", Math.Max(0, barCount - 1), openAt, read);

    static NativeBarWindow Read(NativeBarRequirement window, long at, long? witnessAt, string source,
        int count, Func<int, long> openAt, Func<int, NativeClosedMarketBar> read)
    {
        if (at <= 0 || window.Count <= 0 || !Enum.IsDefined(typeof(NativeBarTimeframe), window.Timeframe))
            throw new ArgumentOutOfRangeException(nameof(window));
        long width = Duration(window.Timeframe);
        long close = (at - 1L) / width * width;
        NativeBarWindow Stop(NativeBarStatus status)
            => new(window.Timeframe, window.Count, close, witnessAt, source, status, Array.Empty<NativeClosedMarketBar>());

        if (count == 0) return Stop(NativeBarStatus.SourceMissing);
        // The archived trendbar gives the nominal boundary. A same-symbol market observation
        // from the next bucket is additionally required by the decision clock.
        if (witnessAt is not long witness || witness < close || witness > at)
            return Stop(NativeBarStatus.CloseUnobserved);
        int lo = 0, hi = count;
        while (lo < hi)
        {
            int pivot = lo + (hi - lo) / 2;
            if (openAt(pivot) < close) lo = pivot + 1;
            else hi = pivot;
        }
        if (lo == 0 || openAt(lo - 1) < close - width) return Stop(NativeBarStatus.LatestBarMissing);
        if (openAt(lo - 1) != close - width) return Stop(NativeBarStatus.InvalidBar);
        if (lo < window.Count) return Stop(NativeBarStatus.InsufficientHistory);

        var bars = new NativeClosedMarketBar[window.Count];
        for (int j = 0; j < bars.Length; j++)
        {
            var bar = read(lo - bars.Length + j);
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
