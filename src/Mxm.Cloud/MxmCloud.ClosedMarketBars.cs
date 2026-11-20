using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using Mxm.Core;

namespace cAlgo.Robots;

public partial class MxmCloud
{
    [Parameter("Closed market context observation", DefaultValue = false)]
    public bool ObserveClosedMarketBars { get; set; }

    readonly Dictionary<(string Symbol, NativeBarTimeframe Period), Bars> closedBarSources = new();
    long lastContextClock;
    string lastContextStatus = "";

    static TimeFrame PlatformTimeframe(NativeBarTimeframe period) => period switch
    {
        NativeBarTimeframe.M1 => TimeFrame.Minute,
        NativeBarTimeframe.M5 => TimeFrame.Minute5,
        NativeBarTimeframe.M15 => TimeFrame.Minute15,
        NativeBarTimeframe.M30 => TimeFrame.Minute30,
        NativeBarTimeframe.H1 => TimeFrame.Hour,
        NativeBarTimeframe.H4 => TimeFrame.Hour4,
        NativeBarTimeframe.D1 => TimeFrame.Daily,
        _ => throw new ArgumentOutOfRangeException(nameof(period))
    };

    NativeBarContext ReadClosedMarketBars(string symbol, long at, long? tickAt)
    {
        var windows = new List<NativeBarWindow>();
        foreach (var requirement in NativeClosedMarketContext.CoverageWindows)
        {
            var period = requirement.Timeframe;
            var key = (symbol, period);
            long width = NativeClosedMarketContext.Duration(period);
            if (!closedBarSources.TryGetValue(key, out var bars))
            {
                bars = MarketData.GetBars(PlatformTimeframe(period), symbol);
                closedBarSources[key] = bars;
            }

            long OpenAt(int index) => Stamp(bars.OpenTimes[index]);
            NativeClosedMarketBar Read(int index)
            {
                long open = OpenAt(index);
                return new(open, open + width, (decimal)bars.OpenPrices[index], (decimal)bars.HighPrices[index],
                    (decimal)bars.LowPrices[index], (decimal)bars.ClosePrices[index], (long)bars.TickVolumes[index]);
            }
            windows.Add(NativeClosedMarketContext.Platform(requirement, at, tickAt, bars.Count, OpenAt, Read));
        }
        return new(at, windows.ToArray());
    }

    void ReportClosedMarketBars(string[] symbols)
    {
        long at = NativeClosedMarketContext.LatestClock(Stamp(Server.TimeInUtc),
            NativeIntegratedLifecycle.IntervalMs, NativeIntegratedEconomicPolicy.ClockOffsetMs);
        if (at <= lastContextClock) return;
        lastContextClock = at;
        var counts = new Dictionary<NativeBarStatus, int>();
        int missingQuotes = 0, sourceErrors = 0;
        foreach (string symbol in symbols)
        {
            try
            {
                var tick = ReadTickAsOf(symbol, at);
                if (tick is null)
                {
                    missingQuotes++;
                    continue;
                }
                foreach (var window in ReadClosedMarketBars(symbol, at, tick.Value.At).Windows)
                    counts[window.Status] = counts.GetValueOrDefault(window.Status) + 1;
            }
            catch (Exception)
            {
                sourceErrors++;
            }
        }
        string status = string.Join(", ", counts.OrderBy(x => x.Key).Select(x => $"{x.Key}={x.Value}")) +
            $", no quote={missingQuotes}, source unavailable={sourceErrors}";
        if (status == lastContextStatus) return;
        lastContextStatus = status;
        Print("MXM closed market context {0}: {1}", at, status);
    }
}
