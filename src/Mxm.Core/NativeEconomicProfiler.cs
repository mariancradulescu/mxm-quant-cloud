using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Linq;
using System.Threading;

namespace Mxm.Core;

// Opt-in diagnostics only. Neither timers nor allocation counts participate in economic decisions.
// Scopes are synchronous and must be disposed in reverse nesting order on the creating thread.
public static class NativeEconomicProfiler
{
    public static readonly bool Enabled =
        Environment.GetEnvironmentVariable("MXM_ECONOMIC_PROFILE") == "1";
    public static readonly bool DetailedDistance =
        Enabled && Environment.GetEnvironmentVariable("MXM_ECONOMIC_PROFILE_DISTANCE") == "1";
    static readonly ConcurrentDictionary<string, Counter> Counters = new(StringComparer.Ordinal);
    [ThreadStatic] static long accountedTicks;
    [ThreadStatic] static long accountedBytes;

    sealed class Counter
    {
        public long Calls, InclusiveTicks, ExclusiveTicks, InclusiveBytes, ExclusiveBytes;
    }

    public readonly record struct Measurement(string Component, long Calls, double InclusiveMs,
        double ExclusiveMs, long InclusiveAllocatedBytes, long ExclusiveAllocatedBytes);

    public static Scope Measure(string component) => Enabled ? new Scope(component) : default;
    public static Scope MeasureDistance() => DetailedDistance ? new Scope("distribution.context_distance") : default;

    public readonly struct Scope : IDisposable
    {
        readonly string? component;
        readonly long started, bytes, childTicks, childBytes;

        internal Scope(string name)
        {
            component = name;
            childTicks = accountedTicks;
            childBytes = accountedBytes;
            bytes = GC.GetAllocatedBytesForCurrentThread();
            started = Stopwatch.GetTimestamp();
        }

        public void Dispose()
        {
            if (component is null) return;
            long elapsed = Stopwatch.GetTimestamp() - started;
            long allocated = GC.GetAllocatedBytesForCurrentThread() - bytes;
            long exclusive = Math.Max(0L, elapsed - (accountedTicks - childTicks));
            long exclusiveBytes = Math.Max(0L, allocated - (accountedBytes - childBytes));
            accountedTicks += exclusive;
            accountedBytes += exclusiveBytes;
            var counter = Counters.GetOrAdd(component, _ => new Counter());
            Interlocked.Increment(ref counter.Calls);
            Interlocked.Add(ref counter.InclusiveTicks, elapsed);
            Interlocked.Add(ref counter.ExclusiveTicks, exclusive);
            Interlocked.Add(ref counter.InclusiveBytes, allocated);
            Interlocked.Add(ref counter.ExclusiveBytes, exclusiveBytes);
        }
    }

    public static Measurement[] Snapshot() => Counters.OrderBy(x => x.Key, StringComparer.Ordinal).Select(x =>
        new Measurement(x.Key, Interlocked.Read(ref x.Value.Calls),
            Interlocked.Read(ref x.Value.InclusiveTicks) * 1000d / Stopwatch.Frequency,
            Interlocked.Read(ref x.Value.ExclusiveTicks) * 1000d / Stopwatch.Frequency,
            Interlocked.Read(ref x.Value.InclusiveBytes), Interlocked.Read(ref x.Value.ExclusiveBytes))).ToArray();
}
