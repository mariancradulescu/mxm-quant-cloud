using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

// SPE1: pre-frozen genuine OHLCV price-information research using the SAME C#
// Core. Never constructs fictitious BID/ASK, fills, EUR cash, margin or NET.
public static class NativeSignalEconomicResearch
{
    private const long M15=900000L;
    private static long U(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    private static readonly (string Name,long Start,long End)[] Stages={
        ("DEVELOPMENT_EXPOSED",U(2025,11,16),U(2026,5,17)),
        ("SELECTION_DIAGNOSTIC_EXPOSED",U(2026,5,17),U(2026,8,17)),
        ("EVALUATION_GLOBALLY_EXPOSED",U(2026,8,17),U(2026,11,16))
    };
    private static readonly string[] Expected={"AUDUSD","AUS200","EURUSD","GBPUSD","GER40","JPN225",
        "NAS100","UK100","US500","USDCAD","USDJPY","XAUUSD"};
    private const decimal Scale=100000m;
    private sealed record Frame(string Symbol,long At,decimal Close,decimal Open,
        decimal Atr,decimal Mean32,decimal High16,decimal Low16,decimal VolumeRatio,
        decimal Slow16,int StructureSide,int ReversionSide);
    private sealed record Position(string Symbol,string Family,int Side,long EnteredAt,
        long LastAt,decimal EntryClose,decimal BestClose,int HeldBars);
    public sealed record PriceOnlyTrade(string Book,string Stage,string Symbol,string Family,
        int Side,long EntryDecisionAt,long ExitDecisionAt,decimal GrossCloseToCloseBps,
        decimal MatchedLongBps,decimal MatchedShortBps,string ExitReason);
    private sealed record BookResult(string Book,string Stage,int Proposed,int Accepted,
        int BlockedOccupied,int BlockedSlots,int Conflicts,int Completed,int Censored,
        int PeakConcurrent,int SafetyTimeouts,decimal? MeanPriceOnlyBps,
        decimal SumPriceOnlyBps,decimal? MedianPriceOnlyBps,
        decimal MatchedLongPriceOnlySumBps,decimal MatchedShortPriceOnlySumBps,
        decimal? CostToleranceMeanBps,
        Dictionary<string,int> ExitReasons,Dictionary<string,int> CompletedPerIsoWeek,
        Dictionary<string,int> CompletedPerSymbol,PriceOnlyTrade[] Trades,
        decimal? NetEur=null,int? GenuineFinancedTrades=null,bool Hard21Certified=false,
        decimal? ContinuousFloatingDd=null,bool GenuineEur300LedgerEvaluated=false);

    private static string Week(long at)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);
    }
    private static decimal Price(long integer)=>integer/Scale;
    private static Frame[] Frames(Cdh1Input input)
    {
        if(input is null||input.Streams is null||
           input.Streams.Length!=Expected.Length ||
           !input.Streams.Select(s=>s.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
             .SequenceEqual(Expected) ||
           input.Streams.Any(s=>s.Period!="M15" || s.Bars is null || s.Bars.Length<65))
            throw new ArgumentException("SPE1_AUTHENTIC_TWELVE_M15_SOURCE_REQUIRED");
        var result=new List<Frame>(input.Streams.Sum(x=>x.Bars.Length));
        foreach(var stream in input.Streams)
        {
            var b=stream.Bars;
            if(b.Any(x=>x.End-x.Start!=M15||x.Open<=0||x.Low<=0||
                  x.Low>Math.Min(x.Open,x.Close)||
                  x.High<Math.Max(x.Open,x.Close)||x.Volume<0)||
               b.Zip(b.Skip(1)).Any(x=>x.Second.Start<x.First.End))
                throw new ArgumentException("SPE1_SOURCE_GEOMETRY_INVALID");
            for(int i=64;i<b.Length;i++)
            {
                bool consecutive=true;
                for(int j=i-63;j<=i;j++)
                    if(b[j].Start!=b[j-1].End){consecutive=false;break;}
                if(!consecutive)continue;
                decimal atr=0m;
                for(int j=i-15;j<=i;j++)
                {
                    decimal hi=Price(b[j].High),lo=Price(b[j].Low),prev=Price(b[j-1].Close);
                    atr+=Math.Max(hi-lo,Math.Max(Math.Abs(hi-prev),Math.Abs(lo-prev)));
                }
                atr/=16m;if(atr<=0m)continue;
                decimal p=Price(b[i].Close),o=Price(b[i].Open);
                decimal eq=Enumerable.Range(i-31,32).Average(j=>Price(b[j].Close));
                decimal high=Enumerable.Range(i-16,16).Max(j=>Price(b[j].High));
                decimal low=Enumerable.Range(i-16,16).Min(j=>Price(b[j].Low));
                decimal vol=Enumerable.Range(i-16,16).Average(j=>(decimal)b[j].Volume);
                if(vol<=0m)continue;
                decimal ratio=b[i].Volume/vol;
                decimal slow=p-Price(b[i-16].Close); // Four completed H1-scale 4-bar blocks.
                int structure= p>high&&p>o&&slow>0&&ratio>=1.10m?1:
                    p<low&&p<o&&slow<0&&ratio>=1.10m?-1:0;
                int reversion=Math.Abs(slow)<=6m*atr&&ratio>=1.10m?
                    p<=eq-1.5m*atr&&p>o?1:
                    p>=eq+1.5m*atr&&p<o?-1:0:0;
                result.Add(new(stream.Symbol,b[i].End,p,o,atr,eq,high,low,ratio,
                    slow,structure,reversion));
            }
        }
        return result.OrderBy(x=>x.At).ThenBy(x=>x.Symbol,StringComparer.Ordinal).ToArray();
    }

    private static BookResult Simulate(string book,(string Name,long Start,long End) stage,Frame[] all)
    {
        var positions=new Dictionary<string,Position>(StringComparer.Ordinal);
        var closed=new List<PriceOnlyTrade>();
        var exits=new Dictionary<string,int>(StringComparer.Ordinal);
        var weeks=new SortedDictionary<string,int>(StringComparer.Ordinal);
        var perSymbol=new Dictionary<string,int>(StringComparer.Ordinal);
        int proposed=0,accepted=0,occupied=0,slots=0,conflicts=0,censored=0,peak=0;
        // Objective calendar counted even on no-signal weeks, never claim funding.
        for(long date=stage.Start;date<stage.End;date+=604800000L)
            weeks.TryAdd(Week(date),0);
        foreach(var batch in all.Where(f=>f.At>=stage.Start&&f.At<stage.End)
                     .GroupBy(f=>f.At))
        {
            var sameClockClosed=new HashSet<string>(StringComparer.Ordinal);
            foreach(var f in batch)
            {
                if(!positions.TryGetValue(f.Symbol,out var p))continue;
                if(f.At-p.LastAt!=M15)
                {
                    censored++;positions.Remove(f.Symbol);sameClockClosed.Add(f.Symbol);
                    continue; // Original market gap: no imputed close or PnL.
                }
                var verdict=NativeCausalExitResearch.AssessClosedBarThesis(
                    p.Family,p.Side,p.EntryClose,p.BestClose,f.Close,f.Mean32,
                    f.Atr,f.Slow16,f.High16,f.Low16,p.HeldBars+1);
                if(!verdict.RequestClose)
                {
                    positions[f.Symbol]=p with {BestClose=verdict.FavorableExtreme,
                        LastAt=f.At,HeldBars=p.HeldBars+1};
                    continue;
                }
                decimal lbps=(f.Close/p.EntryClose-1m)*10000m;
                decimal gross=p.Side*lbps;
                var row=new PriceOnlyTrade(book,stage.Name,f.Symbol,p.Family,p.Side,
                    p.EnteredAt,f.At,gross,lbps,-lbps,verdict.Reason);
                closed.Add(row);
                exits[verdict.Reason]=exits.GetValueOrDefault(verdict.Reason)+1;
                string week=Week(f.At);
                weeks[week]=weeks.GetValueOrDefault(week)+1;
                perSymbol[f.Symbol]=perSymbol.GetValueOrDefault(f.Symbol)+1;
                positions.Remove(f.Symbol);
                sameClockClosed.Add(f.Symbol);
            }
            // The allocator sees each predecision signal on the same clock;
            // no hindsight rank, per-family HARD21 gate, or future close.
            var pending=new List<(Frame Frame,string Family,int Side)>();
            foreach(var f in batch)
            {
                if(book is "JOINT" or "STRUCTURE_ONLY")
                    if(f.StructureSide!=0)
                        pending.Add((f,"STRUCTURE_CONTINUATION",f.StructureSide));
                if(book is "JOINT" or "REVERSION_ONLY")
                    if(f.ReversionSide!=0)
                        pending.Add((f,"EXTREME_REVERSION",f.ReversionSide));
            }
            proposed+=pending.Count;
            foreach(var g in pending.GroupBy(p=>p.Frame.Symbol)
                        .OrderBy(g=>g.Key,StringComparer.Ordinal))
            {
                var offers=g.OrderBy(x=>x.Family=="STRUCTURE_CONTINUATION"?0:1)
                    .ThenBy(x=>x.Family,StringComparer.Ordinal).ToArray();
                if(offers.Select(x=>x.Side).Distinct().Count()>1)
                {conflicts+=offers.Length;continue;}
                if(offers.Length>1)conflicts+=offers.Length-1; // deterministically choose one.
                var offer=offers[0];
                if(positions.ContainsKey(g.Key)||sameClockClosed.Contains(g.Key))
                {occupied++;continue;}
                if(positions.Count>=2){slots++;continue;}
                var f=offer.Frame;
                positions.Add(g.Key,new Position(g.Key,offer.Family,offer.Side,
                    f.At,f.At,f.Close,f.Close,0));
                accepted++;peak=Math.Max(peak,positions.Count);
            }
        }
        censored+=positions.Count; // Stage boundary NEVER invents terminal outcome.
        var gross=closed.Select(t=>t.GrossCloseToCloseBps).ToArray();
        var ordered=gross.OrderBy(x=>x).ToArray();
        decimal? mean=gross.Length>0?gross.Average():null;
        decimal? median=ordered.Length>0?ordered[ordered.Length/2]:null;
        return new(book,stage.Name,proposed,accepted,occupied,slots,conflicts,
            gross.Length,censored,peak,closed.Count(t=>t.ExitReason.StartsWith("SAFETY_",
                StringComparison.Ordinal)),mean,gross.Sum(),median,
            closed.Sum(t=>t.MatchedLongBps),closed.Sum(t=>t.MatchedShortBps),
            mean>0m?mean:null,exits,new(weeks,StringComparer.Ordinal),
            perSymbol,closed.ToArray());
    }

    public static object Evaluate(Cdh1Input original)
    {
        var frames=Frames(original);
        var reports=new List<BookResult>();
        foreach(var stage in Stages)
            foreach(var policy in new[]{"STRUCTURE_ONLY","REVERSION_ONLY","JOINT"})
                reports.Add(Simulate(policy,stage,frames));
        return new {
            Protocol="SPE1_FROZEN_NATIVE_SIGNAL_EXIT_TWO_ECONOMIC_MECHANISMS",
            original.SourceRunId,original.ProtocolSha256,original.CiphertextSha256,
            OriginalBars=original.Streams.Sum(s=>s.Bars.Length),
            OriginalSymbols=Expected,UsableChronologicalFrames=frames.Length,
            MultiResolution="M15_CLOSED_PLUS_CAUSAL_16_M15_H1_SCALE_REGIME",
            PriorExposure="GLOBAL_EXPOSED_NOT_INDEPENDENT",
            SourceProviderAuthenticity="ORIGINAL_PEPPRSTONE_RAW_PROTOBUF_VERIFIED_BY_PROTECTED_RUNNER",
            PriceOnlyProxy="DECISION_CLOSE_TO_SIGNAL_EXIT_CLOSE_NOT_EXECUTABLE_FILL",
            CommonBookSlots=2,FinancialCapitalReferenceEur=300m,
            StageReports=reports,
            CashPriceOnlyBps=0m,
            NetEur=(decimal?)null,AdverseNetEur=(decimal?)null,
            GenuineFinancedRoundTrips=(int?)null,Hard21SystemicCertified=false,
            ContinuousFloatingDrawdown=(decimal?)null,
            LegallyFinancedCommonEur300LedgerEvaluated=false,
            HistoricalBidAskFeesFxSwapsOrMarginCertified=false,
            IndependentTwelveMonths=false,OrdersSubmitted=0,CloudActivated=false,
            EconomicQualification=false
        };
    }
}
