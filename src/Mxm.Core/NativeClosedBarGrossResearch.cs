using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

internal sealed record NativeGrossMarket(string Symbol,string Category,
    Dictionary<string,NativeClosedMarketBar[]> Bars);

// A price-only causal comparison. The next witnessed M5 close is a price
// proxy. It cannot certify spread, real fills, funding, EUR, or portfolio DD.
internal static class NativeClosedBarGrossResearch
{
    const long M5=300_000;
    const string Continuation="MULTISCALE_CONTINUATION";
    const string Source="CTRADER_ORIGINAL_OR_CONTIGUOUS_M5_ROLLUP";

    sealed record Observation(NativeGrossMarket Market,NativeClosedMarketBar Mark,
        NativeClosedMarketBar[] M5Window,NativeBarWindow M15,NativeBarWindow M30,NativeBarWindow H1,
        NativeBarWindow[] AdditionalContext);
    sealed record Candidate(string Symbol,string Category,int Side,string Family,
        decimal Stop,decimal Target,decimal Equilibrium,decimal Score,long At);
    sealed record Position(Candidate Thesis,long OpenedAt,decimal Entry,long LastMark,long? ExitRequestedAt=null);
    sealed record Outcome(string Symbol,string Category,string Family,long ClosedAt,decimal Bps);

    sealed class Comparison
    {
        readonly bool rank;
        readonly List<Outcome> outcomes=new();
        Candidate? pending;
        Position? held;
        int entries,entryCensored,gapMarks,acrossBucketOpportunities;

        public Comparison(bool rank)=>this.rank=rank;

        public void Advance(long clock,IReadOnlyList<Observation> observations,IReadOnlyList<Candidate> choices)
        {
            if (held is { } position)
            {
                var observation=observations.FirstOrDefault(o=>o.Market.Symbol==position.Thesis.Symbol);
                if(observation is null)return;
                var mark=observation.Mark;
                if(mark.OpenAt!=position.LastMark)gapMarks++;
                var thesis=position.Thesis;
                if(position.ExitRequestedAt is long requested && clock>requested)
                {
                    decimal bps=10_000m*thesis.Side*(mark.Close-position.Entry)/position.Entry;
                    outcomes.Add(new(thesis.Symbol,thesis.Category,thesis.Family,clock,bps));
                    held=null;
                }
                else
                {
                    var context=observation.M15;
                    bool observedReversal=context.Ready && context.Bars[^1].CloseAt>position.OpenedAt &&
                        thesis.Side*(context.Bars[^1].Close-context.Bars[^2].Close)<0m &&
                        thesis.Side*(context.Bars[^1].Close-thesis.Equilibrium)<=0m;
                    bool observedLevel=thesis.Side*(mark.Close-thesis.Stop)<=0m ||
                        thesis.Side*(mark.Close-thesis.Target)>=0m;
                    held=position with {LastMark=mark.CloseAt,
                        ExitRequestedAt=observedReversal||observedLevel?clock:null};
                    return;
                }
            }
            if(pending is { } intent)
            {
                var observation=observations.FirstOrDefault(o=>o.Market.Symbol==intent.Symbol);
                pending=null;
                if(observation is not null && observation.Mark.OpenAt==intent.At &&
                    intent.Side*(observation.Mark.Close-intent.Stop)>0m &&
                    intent.Side*(intent.Target-observation.Mark.Close)>0m)
                {
                    held=new(intent,clock,observation.Mark.Close,clock);
                    entries++;
                    return;
                }
                entryCensored++;
            }
            if(choices.Count==0)return;
            if(choices.Select(c=>c.Category).Distinct(StringComparer.Ordinal).Skip(1).Any())
                acrossBucketOpportunities++;
            pending=(rank?choices.OrderByDescending(c=>c.Score):choices.OrderBy(c=>0))
                .ThenBy(c=>c.Symbol,StringComparer.Ordinal).ThenBy(c=>c.Family,StringComparer.Ordinal).First();
        }

        public object Report()=>new
        {
            Policy=rank?"CLOSED_MULTISCALE_REWARD_RISK_RANK":"MATCHED_STABLE_SEQUENTIAL_PRIORITY",
            EntryProxies=entries,CancelledEntryProxies=entryCensored,UnresolvedPosition=held is not null,
            UnresolvedEntry=pending is not null,ObservedGapsWhileHeld=gapMarks,
            SelectionClocksWithCompetingCategories=acrossBucketOpportunities,Totals=Stats(outcomes),
            Weekly=outcomes.GroupBy(o=>Week(o.ClosedAt)).OrderBy(g=>g.Key).ToDictionary(g=>g.Key,g=>Stats(g)),
            Families=outcomes.GroupBy(o=>o.Family).ToDictionary(g=>g.Key,g=>Stats(g)),
            Categories=outcomes.GroupBy(o=>o.Category).ToDictionary(g=>g.Key,g=>Stats(g)),
            Instruments=outcomes.GroupBy(o=>o.Symbol).ToDictionary(g=>g.Key,g=>Stats(g))
        };
    }

    static object Stats(IEnumerable<Outcome> outcome)
    {
        var observations=outcome.ToArray();
        decimal total=observations.Sum(o=>o.Bps);
        return new {CompletedProxies=observations.Length,GrossSumBps=total,
            GrossMeanBps=observations.Length==0?(decimal?)null:total/observations.Length,
            Positive=observations.Count(o=>o.Bps>0m),Negative=observations.Count(o=>o.Bps<0m),
            Weeks=observations.Select(o=>Week(o.ClosedAt)).Distinct().Count(),
            PositiveWeeks=observations.GroupBy(o=>Week(o.ClosedAt)).Count(g=>g.Sum(o=>o.Bps)>0m)};
    }

    static string Week(long time)
    {
        var date=DateTimeOffset.FromUnixTimeMilliseconds(time).UtcDateTime;
        return string.Format(CultureInfo.InvariantCulture,"{0:D4}-W{1:D2}",ISOWeek.GetYear(date),ISOWeek.GetWeekOfYear(date));
    }

    static NativeClosedMarketBar[] Rollup(NativeClosedMarketBar[] m5,long width)
        =>m5.GroupBy(b=>b.OpenAt/width).Where(g=>g.Count()==width/M5 &&
            g.First().OpenAt==g.Key*width && g.Last().CloseAt==(g.Key+1)*width &&
            g.Zip(g.Skip(1)).All(z=>z.First.CloseAt==z.Second.OpenAt))
            .Select(g=>new NativeClosedMarketBar(g.First().OpenAt,g.Last().CloseAt,g.First().Open,
                g.Max(b=>b.High),g.Min(b=>b.Low),g.Last().Close,g.Sum(b=>b.TickVolume))).ToArray();

    static NativeGrossMarket BuildContext(NativeGrossMarket market)
    {
        var bars=new Dictionary<string,NativeClosedMarketBar[]>(market.Bars,StringComparer.Ordinal);
        var m5=bars["M5"];
        if(!bars.ContainsKey("M15"))bars.Add("M15",NativeHistoricalProductReplay.AggregateCompletedM15(m5));
        if(!bars.ContainsKey("M30"))bars.Add("M30",Rollup(m5,1_800_000));
        if(!bars.ContainsKey("H1"))bars.Add("H1",Rollup(m5,3_600_000));
        return market with {Bars=bars};
    }

    static Observation Observe(NativeGrossMarket market,int position)
    {
        var bars=market.Bars["M5"];
        var mark=bars[position];
        long at=mark.CloseAt+1;
        NativeBarWindow Window(NativeBarTimeframe timeframe,int count)
            =>NativeClosedMarketContext.History(new(timeframe,count),at,mark.CloseAt,Source,
                market.Bars.GetValueOrDefault(timeframe.ToString()));
        return new(market,mark,bars[Math.Max(0,position-4)..(position+1)],
            Window(NativeBarTimeframe.M15,3),Window(NativeBarTimeframe.M30,2),Window(NativeBarTimeframe.H1,2),
            AdditionalFrames.Where(timeframe=>market.Bars.ContainsKey(timeframe.ToString()))
                .Select(timeframe=>Window(timeframe,2)).Where(history=>history.Ready).ToArray());
    }

    static readonly NativeBarTimeframe[] AdditionalFrames={NativeBarTimeframe.M1,NativeBarTimeframe.H4,NativeBarTimeframe.D1};

    static IEnumerable<Candidate> Describe(Observation o)
    {
        var recent=o.M5Window;
        if(recent.Length<5 || !o.M15.Ready || !o.M30.Ready || !o.H1.Ready ||
            !recent.Zip(recent.Skip(1)).All(p=>p.First.CloseAt==p.Second.OpenAt))
            yield break;
        long at=o.Mark.CloseAt;
        var h1=o.H1.Bars;
        var m30=o.M30.Bars;
        decimal Change(NativeClosedMarketBar[] bars)=>bars[^1].Close-bars[^2].Close;
        decimal hourTrend=Change(h1),halfHourTrend=Change(m30);
        var signals=Ucp1CausalSignals.Describe(o.Market.Symbol,recent,o.M15.Bars,at+1).ToList();
        int orientation=Math.Sign(hourTrend);
        decimal center=(h1[^1].High+h1[^1].Low)/2m;
        decimal range=recent.Average(b=>b.High-b.Low);
        if(orientation!=0 && orientation*halfHourTrend>0m && range>0m &&
            orientation*(recent[^2].Close-center)<=0m && orientation*(o.Mark.Close-center)>0m)
            signals.Add(new(o.Market.Symbol,Continuation,orientation,range,center,
                Math.Abs(hourTrend),at));

        foreach(var signal in signals)
        {
            int side=signal.Side;
            decimal stop=side>0?recent.TakeLast(3).Min(b=>b.Low):recent.TakeLast(3).Max(b=>b.High);
            decimal target=signal.Family=="EQUILIBRIUM_REPAIR"?signal.Equilibrium:
                o.Mark.Close+side*signal.ExpectedMove;
            decimal reward=side*(target-o.Mark.Close), risk=side*(o.Mark.Close-stop);
            if(reward<=0m || risk<=0m || target<=0m)continue;
            decimal Trend(NativeClosedMarketBar[] bars)
                =>Change(bars)/Math.Max(signal.Atr,bars.Max(b=>b.High)-bars.Min(b=>b.Low));
            decimal contextTrend=Trend(h1)+Trend(m30)+o.AdditionalContext.Sum(window=>Trend(window.Bars));
            decimal score=reward/risk+side*contextTrend/(2+o.AdditionalContext.Length);
            yield return new(o.Market.Symbol,o.Market.Category,side,signal.Family,stop,target,
                signal.Equilibrium,score,at);
        }
    }

    public static object Compare(string source,NativeGrossMarket[] input)
    {
        if(input.Select(m=>m.Symbol).Distinct(StringComparer.Ordinal).Count()!=input.Length)
            throw new ArgumentException("GROSS_SOURCE_SYMBOL_COLLISION");
        var markets=input.Select(BuildContext).ToArray();
        var indexes=new int[markets.Length];
        var queue=new PriorityQueue<int,(long,int)>();
        void Enqueue(int i)
        {
            var bars=markets[i].Bars["M5"];
            if(indexes[i]<bars.Length)queue.Enqueue(i,(bars[indexes[i]].CloseAt,i));
        }
        for(int i=0;i<markets.Length;i++)Enqueue(i);
        var ranking=new Comparison(true);
        var control=new Comparison(false);
        var candidates=new Dictionary<string,int>(StringComparer.Ordinal);
        var additionalContext=new Dictionary<string,int>(StringComparer.Ordinal);
        var scheduledWeeks=new HashSet<string>(StringComparer.Ordinal);
        int clocks=0,matchedClocks=0;
        while(queue.TryPeek(out _,out var turn))
        {
            var observations=new List<Observation>();
            long clock=turn.Item1;
            while(queue.TryPeek(out int i,out var next) && next.Item1==clock)
            {
                queue.Dequeue();
                observations.Add(Observe(markets[i],indexes[i]++));
                Enqueue(i);
            }
            clocks++;
            scheduledWeeks.Add(Week(clock));
            foreach(var window in observations.SelectMany(o=>o.AdditionalContext))
            {
                string key=window.Timeframe.ToString();
                additionalContext[key]=additionalContext.GetValueOrDefault(key)+1;
            }
            var options=observations.SelectMany(Describe).ToArray();
            if(options.Length>0)matchedClocks++;
            foreach(var option in options)candidates[option.Family]=candidates.GetValueOrDefault(option.Family)+1;
            ranking.Advance(clock,observations,options);
            control.Advance(clock,observations,options);
        }
        return new
        {
            Source=source,EvaluationClocks=clocks,ClocksWithMatchedChoices=matchedClocks,
            SourceWeeks=scheduledWeeks.Count,ProposalsByFamily=candidates,PriceProxy="NEXT_WITNESSED_M5_CLOSE",
            AvailableAdditionalWindows=additionalContext,
            OriginalRowsByTimeframe=input.SelectMany(m=>m.Bars).GroupBy(b=>b.Key)
                .ToDictionary(g=>g.Key,g=>g.Sum(b=>b.Value.Length)),
            MarketCount=markets.Length,CategoryCount=markets.Select(m=>m.Category).Distinct().Count(),
            Ranked=ranking.Report(),MatchedControl=control.Report(),CashGrossBps=0m,
            QualifiedNetEur=(decimal?)null,Hard21Certified=false,ContinuousDrawdownCertified=false
        };
    }
}
