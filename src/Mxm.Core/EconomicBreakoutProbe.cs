namespace Mxm.Core;

/// <summary>
/// Entirely NEW fixed price-only economic challenger, not the closed H1 model.
/// An executable price, spread, slippage, account margin, financing and FX are
/// intentionally not supplied by OHLC. Never infer a funded NET roundtrip.
/// </summary>
public sealed record PriceOnlyBar(string Symbol, string Resolution,
    DateTime OpenUtc, DateTime AvailableUtc, int PeriodMinutes,
    long Open, long High, long Low, long Close);

public sealed record PriceOnlyEpisode(DateTime ExitUtc, decimal GrossPips);
public sealed record EconomicPriceScreen(
    int Episodes, decimal? MeanGrossPips, decimal? MedianGrossPips,
    decimal? PositiveFraction, decimal? EarlySliceGrossPips,
    decimal? MiddleSliceGrossPips, decimal? LateSliceGrossPips,
    int ObservedExitWeeks, int WeeksWith21Proxies,
    string Verdict);

public static class EconomicBreakoutProbe
{
    // Precisely ONE frozen causal control rule, no data-derived parameter fit.
    public const int PriorRangeLookback=12;
    public const int ExitBarsAfterSignal=4;
    public const string PriceOnly="GROSS_OHLC_PROXY_NOT_EXECUTABLE_NET";
    public static EconomicPriceScreen Assess(IEnumerable<PriceOnlyBar> input,
        int pipPosition)
    {
        if(pipPosition<0 || pipPosition>5)
            throw new ArgumentException("UNVERIFIED_SYMBOL_PIP_SCALE");
        var rows=input.OrderBy(b=>b.OpenUtc).ToArray();
        if(rows.Length==0)
            return new(0,null,null,null,null,null,null,0,0,"NO_CANDIDATE_SOURCE");
        var symbol=rows[0].Symbol;
        var period=rows[0].PeriodMinutes;
        var resolution=rows[0].Resolution;
        if(string.IsNullOrWhiteSpace(symbol) || period<1 ||
           (resolution!="H4" && resolution!="M15"))
            throw new ArgumentException("RESEARCH_BAR_IDENTITY_INVALID");
        for(int i=0;i<rows.Length;i++)
        {
            var b=rows[i];
            if(b.Symbol!=symbol || b.Resolution!=resolution ||
               b.PeriodMinutes!=period || b.OpenUtc.Kind!=DateTimeKind.Utc ||
               b.AvailableUtc != b.OpenUtc.AddMinutes(period) ||
               b.Low<=0 || b.Low>b.Open || b.Open>b.High ||
               b.Low>b.Close || b.Close>b.High ||
               (i>0 && b.OpenUtc<=rows[i-1].OpenUtc))
                throw new ArgumentException("RESEARCH_CAUSAL_SOURCE_INVALID");
        }
        decimal ticksPerPip=1m;
        for(int d=pipPosition;d<5;d++)ticksPerPip*=10m;
        var episodes=new List<PriceOnlyEpisode>();
        for(int i=PriorRangeLookback;i+ExitBarsAfterSignal<rows.Length;i++)
        {
            var signal=rows[i];
            // A gap anywhere in a prior lookback or after the signal is a
            // hard exclusion; no weekend interpolation or forced fill.
            if(signal.OpenUtc - rows[i-PriorRangeLookback].OpenUtc !=
                TimeSpan.FromMinutes(PriorRangeLookback*period) ||
               rows[i+ExitBarsAfterSignal].OpenUtc - signal.OpenUtc !=
                TimeSpan.FromMinutes(ExitBarsAfterSignal*period))
                continue;
            long priorHigh=rows.Skip(i-PriorRangeLookback)
                .Take(PriorRangeLookback).Max(x=>x.High);
            long priorLow=rows.Skip(i-PriorRangeLookback)
                .Take(PriorRangeLookback).Min(x=>x.Low);
            int sign=signal.Close>priorHigh?1:
                signal.Close<priorLow?-1:0;
            if(sign==0)continue;
            // Next bar OHLC open = optimistic research price *proxy*; not a
            // verified broker ask/bid fill. Exit = 4th bar close, also proxy.
            var entry=rows[i+1].Open;
            var exit=rows[i+ExitBarsAfterSignal].Close;
            var grossPips=sign*(exit-entry)/ticksPerPip;
            episodes.Add(new PriceOnlyEpisode(
                rows[i+ExitBarsAfterSignal].AvailableUtc,grossPips));
            i+=ExitBarsAfterSignal; // no overlapping proxy positions/symbol
        }
        if(episodes.Count==0)
            return new(0,null,null,null,null,null,null,0,0,
                "NO_COMPLETE_CANDIDATE_ROUNDTRIPS");
        var all=episodes.Select(x=>x.GrossPips).OrderBy(x=>x).ToArray();
        decimal median=all.Length%2==1 ? all[all.Length/2] :
            (all[all.Length/2-1]+all[all.Length/2])/2m;
        var first=rows[0].OpenUtc;
        var last=rows[^1].AvailableUtc;
        var timeSpan=last-first;
        var cutA=first.AddTicks(timeSpan.Ticks*3/5); // 60% chronological
        var cutB=first.AddTicks(timeSpan.Ticks*4/5); // 80% chronological
        decimal? AvgSegment(Func<DateTime,bool> segment)
        {
            var values=episodes.Where(x=>segment(x.ExitUtc)).ToArray();
            return values.Length==0 ? null : values.Average(x=>x.GrossPips);
        }
        static DateTime WeekUtc(DateTime date)
        {
            var offset=((int)date.DayOfWeek+6)%7;
            return date.Date.AddDays(-offset);
        }
        var groups=episodes.GroupBy(e=>WeekUtc(e.ExitUtc)).ToArray();
        return new(episodes.Count,episodes.Average(x=>x.GrossPips),
            median,(decimal)episodes.Count(x=>x.GrossPips>0)/episodes.Count,
            AvgSegment(t=>t<cutA),AvgSegment(t=>t>=cutA && t<cutB),
            AvgSegment(t=>t>=cutB),groups.Length,
            groups.Count(g=>g.Count()>=21),
            PriceOnly);
    }
}
