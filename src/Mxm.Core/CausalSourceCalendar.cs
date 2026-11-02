namespace Mxm.Core;

// Exact, timestamp-derived SOURCE CLOCK diagnostics for any timeframe and symbol.
// This is not broker execution proof, account authentication or scientific validation.
public sealed record SourceBarClock(string Symbol, DateTime OpenUtc,
    DateTime AvailableUtc, TimeSpan Duration, string SourceSha256);

public sealed record SourceCalendarAudit(
    int ObservedBars, int DistinctSymbols, DateTime EarliestOpenUtc,
    DateTime LatestAvailableUtc, int DistinctObservedIsoWeeks,
    int DiscontinuitiesBetweenSuccessiveSameSymbolBars,
    bool TwelveCalendarMonthsObservedForAnySymbol,
    string Status);

public static class CausalSourceCalendar
{
    public static SourceCalendarAudit Assess(IEnumerable<SourceBarClock> observations)
    {
        ArgumentNullException.ThrowIfNull(observations);
        var rows=observations.ToArray();
        if(rows.Length==0)
            throw new ArgumentException("SOURCE_CLOCK_EMPTY");
        var unique=new HashSet<(string,DateTime,TimeSpan)>();
        foreach(var r in rows)
        {
            if(string.IsNullOrWhiteSpace(r.Symbol) || r.Symbol.Length>40 ||
               r.OpenUtc.Kind != DateTimeKind.Utc ||
               r.AvailableUtc.Kind != DateTimeKind.Utc ||
               r.Duration<=TimeSpan.Zero || r.Duration>TimeSpan.FromDays(7) ||
               r.AvailableUtc < r.OpenUtc+r.Duration ||
               r.SourceSha256 is not {Length:64} hash || !hash.All(Uri.IsHexDigit) ||
               !unique.Add((r.Symbol,r.OpenUtc,r.Duration)))
                throw new ArgumentException("SOURCE_CLOCK_INVALID_OR_DUPLICATE");
        }
        var earliest=rows.Min(r=>r.OpenUtc);
        var last=rows.Max(r=>r.AvailableUtc);
        int discontinuities=0;
        bool twelve=false;
        foreach(var group in rows.GroupBy(r=>(r.Symbol,r.Duration)))
        {
            var ordered=group.OrderBy(r=>r.OpenUtc).ToArray();
            twelve |= ordered[0].OpenUtc.AddMonths(12) <= ordered[^1].AvailableUtc;
            for(int i=1;i<ordered.Length;i++)
            {
                if(ordered[i].OpenUtc < ordered[i-1].OpenUtc+ordered[i-1].Duration)
                    throw new ArgumentException("OVERLAPPING_SOURCE_BARS");
                if(ordered[i].OpenUtc != ordered[i-1].OpenUtc+ordered[i-1].Duration)
                    discontinuities++;
            }
        }
        // Week count is only OBSERVED support. It is never a declaration of
        // eligible weeks or complete trade cycles, and cross-symbol breadth
        // does not add more calendar weeks.
        var weeks=rows.Select(r=>{
            var date=r.OpenUtc.Date;
            var monday=date.AddDays(-((int)date.DayOfWeek+6)%7);
            return monday;
        }).Distinct().Count();
        return new SourceCalendarAudit(rows.Length,
            rows.Select(r=>r.Symbol).Distinct(StringComparer.Ordinal).Count(),
            earliest,last,weeks,discontinuities,twelve,
            "SOURCE_CLOCK_ONLY_NOT_EXECUTION_OR_CONFIRMED_TWELVE_MONTHS");
    }
}
