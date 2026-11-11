using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Core;

// Reusable deterministic adapter for FULL historical closed Pepperstone OHLCV
// plus independently observed BID/ASK/FX/volume/contract cost snapshots.
// It never reverse-engineers BID/ASK from M5 mid bars and never regards input
// filenames/claims as a cryptographic broker custody attestation.
public sealed record NativeHistoricalBars(string Symbol,
    NativeClosedMarketBar[] M5);
public sealed record NativeHistoricalQuoteObservation(
    long At,LedgerQuote Quote,NativeObservedContractTerms? Contract,
    decimal SlippagePerSideQuote,int HoldingMinutes=30,
    string ExitPolicy=NativeCausalExitResearch.FrozenFixed);
public sealed record NativeHistoricalMarketTape(
    string SourceLabel,NativeHistoricalBars[] Bars,
    NativeHistoricalQuoteObservation[] Quotes);
public sealed record NativeHistoricalEquityObservation(
    long At,decimal? CentralEquityEur,decimal? AdverseEquityEur,
    decimal? UsedMarginEur,int ClosedModelRoundTrips,
    int ForecastCount,int CumulativeUnknownM5Slots,
    decimal? AdverseUsedMarginEur=null,decimal? AdverseFreeMarginEur=null);
public sealed record NativeHistoricalMarketReceipt(
    string SourceLabel,string OriginalProviderAuthenticity,
    int InstrumentsWithCompleteM5,int OriginalM5Bars,
    int CausalM15Bars,int QuoteObservations,int DistinctQuoteClocks,
    int CompletedModelRoundTrips,int ModelIntentCount,int ModelRejectedCount,
    decimal? ModelFinalCashEur,decimal? ModelClosedGrossEur,
    decimal? ModelClosedCentralNetEur,decimal? ModelClosedAdverseNetEur,
    decimal? MatchedLongBenchmarkNetEur,decimal? IncrementalVsLongNetEur,
    decimal? MaximumSampledCentralDrawdown,
    Dictionary<string,int> ModelTripsPerObservedIsoWeek,
    NativeHistoricalEquityObservation[] SampledEquity,
    int UnscoredM5ClockSlots,bool ContinuousHistoricalEquityObserved,
    int OpenModelPositions,int PendingModelRequests,
    bool IndependentConfirmation=false,bool BrokerNetCertified=false,
    bool OrdersEnabled=false,string Verdict="EXPLORATORY_ONLY_NOT_BROKER_QUALIFIED",
    int ForecastsGenerated=0,string[]? ObservedSymbols=null,
    string[]? ActuallyScoredTimeframes=null,
    bool CompleteSampledSnapshotCalendar=false,
    string BenchmarkContract="CASH_ZERO_AND_MATCHED_SAME_CLOCK_ALWAYS_LONG_UNFUNDED_DESCRIPTIVE",
    Dictionary<string,int>? RejectionReasons=null,
    Dictionary<string,int>? RejectionCategories=null,
    Dictionary<string,int>? SignalsByMechanism=null,
    Dictionary<string,decimal>? ClosedNetByMechanismEur=null,
    decimal? MaximumObservedMarginEur=null,
    string ResearchMode="FROZEN_LEGACY_M5_M15",
    Dictionary<string,int>? ExitReasonCounts=null,
    decimal? MatchedShortBenchmarkNetEur=null,
    decimal? MatchedOppositeSignalBenchmarkNetEur=null,
    decimal? IncrementalVsBestConstantSideEur=null,
    decimal? IncrementalVsOppositeSignalEur=null,
    int UnfinancedModelOpenCancellations=0,
    string AdverseFailureKind="",long? AdverseFailureAt=null,string AdverseFailureEventKind="",
    [property: System.Text.Json.Serialization.JsonIgnore(
        Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    int? DistinctHistoricalStressDecisions=null,
    [property: System.Text.Json.Serialization.JsonIgnore(
        Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    int? DistinctHistoricalStressDecisionsWithExposure=null);

public static class NativeHistoricalProductReplay
{
    private const long M5=300000L,M15=900000L;
    private static string RejectionCategory(string r)
    {
        var u=r.ToUpperInvariant();
        if(u.Contains("SYMBOL_ALREADY")||u.Contains("POSITION_PER_SYMBOL")||
           u.Contains("OPEN_OR_PENDING"))return "SYMBOL_OCCUPIED";
        if(u.Contains("SPREAD")||u.Contains("COMMISSION")||
           u.Contains("SLIPPAGE")||u.Contains("FUNDING")||
           u.Contains("FINANCING")||u.Contains("COST")||
           u.Contains("FEE"))return "COST_AND_FUNDING";
        if(u.Contains("MARGIN")||u.Contains("CAPITAL")||
           u.Contains("FREE_FUNDS")||u.Contains("INSUFFICIENT_CASH"))
            return "FINANCING_CAPACITY";
        if(u.Contains("RISK")||u.Contains("DRAWDOWN")||
           u.Contains("LOSS")||u.Contains("ADVERSE"))
            return "JOINT_RISK";
        if(u.Contains("SOURCE")||u.Contains("CLOCK")||
           u.Contains("UNKNOWN")||u.Contains("UNAVAILABLE")||
           u.Contains("STALE")||u.Contains("DATA")||
           u.Contains("MISSING"))return "DATA_AND_CAUSAL_COVERAGE";
        // Existing native selector rejection: CONDITIONAL_ESTIMATE_
        // NO_POSITIVE_UNCERTAINTY_ADJUSTED_INCREMENTAL_UTILITY.
        // It is a missing economic advantage, NOT a generic technical
        // rejection. This classifies receipt text only; no selection,
        // forecast, model fill, risk, broker data or price is changed.
        if(u.Contains("NO_POSITIVE")||u.Contains("UNCERTAINTY_ADJUSTED")||
           u.Contains("INCREMENTAL_UTILITY")||
           u.Contains("BENCHMARK")||u.Contains("PREDICT")||
           u.Contains("EDGE")||u.Contains("ADVANTAGE")||
           u.Contains("ALPHA")||u.Contains("ECONOMIC")||
           u.Contains("PROFIT"))return "NO_DEMONSTRATED_EDGE";
        return "OTHER_NATIVE_SELECTOR_REASON";
    }
    private static string Week(long at)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00");
    }
    public static NativeClosedMarketBar[] AggregateCompletedM15(
        NativeClosedMarketBar[] m5)
    {
        var result=new List<NativeClosedMarketBar>();
        if(m5 is null)throw new ArgumentException("TAPE_RAW_M5_MISSING");
        for(int k=2;k<m5.Length;k++)
        {
            var a=m5[k-2];var b=m5[k-1];var c=m5[k];
            if(c.CloseAt%M15!=0 || b.OpenAt!=a.CloseAt ||
                c.OpenAt!=b.CloseAt || c.CloseAt-c.OpenAt!=M5 ||
                a.CloseAt-a.OpenAt!=M5 || b.CloseAt-b.OpenAt!=M5)
                continue;
            result.Add(new NativeClosedMarketBar(a.OpenAt,c.CloseAt,
                a.Open,Math.Max(a.High,Math.Max(b.High,c.High)),
                Math.Min(a.Low,Math.Min(b.Low,c.Low)),c.Close,
                checked(a.TickVolume+b.TickVolume+c.TickVolume)));
        }
        return result.ToArray();
    }
    private static int Until(NativeClosedMarketBar[] data,long at)
    {
        int left=0,right=data.Length;
        while(left<right)
        {
            int mid=left+(right-left)/2;
            if(data[mid].CloseAt<=at)left=mid+1;
            else right=mid;
        }
        return left;
    }
    private static NativeClosedMarketBar[] Prefix(
        NativeClosedMarketBar[] all,long at)
    {
        int until=Until(all,at),n=Math.Min(until,NativeCausalWarmup.WindowBars);
        var prefix=new NativeClosedMarketBar[n];
        Array.Copy(all,until-n,prefix,0,n);
        return prefix;
    }
    public static NativeHistoricalMarketReceipt Evaluate(
        NativeHistoricalMarketTape tape,bool UnqualifiedShadowMode=true,
        string ResearchMode="FROZEN_LEGACY_M5_M15",
        Action<NativeFundedLedger>? ObserveFinalLedger=null)
    {
        if(tape is null||tape.Bars is null||tape.Quotes is null||
           string.IsNullOrWhiteSpace(tape.SourceLabel)||
           tape.Bars.Select(x=>x.Symbol).Distinct(StringComparer.Ordinal).Count()!=tape.Bars.Length||
           tape.Bars.Length==0)
            throw new ArgumentException("HISTORICAL_TAPE_SOURCE_STRUCTURE_INVALID");
        var paths=new Dictionary<string,(NativeClosedMarketBar[] M5,NativeClosedMarketBar[] M15)>(
            StringComparer.Ordinal);
        long total5=0,total15=0;
        foreach(var source in tape.Bars)
        {
            var b=source.M5;
            if(string.IsNullOrWhiteSpace(source.Symbol) || b is null||
               b.Length==0 || b.Any(x=>x.CloseAt-x.OpenAt!=M5 ||
                  x.CloseAt<=x.OpenAt||x.OpenAt<0||x.Open<=0||
                  x.Close<=0||x.High<x.Open||x.High<x.Close||
                  x.Low>x.Open||x.Low>x.Close||x.TickVolume<0))
                throw new ArgumentException("HISTORICAL_TAPE_INVALID_OHLCV_GEOMETRY");
            if(b.Zip(b.Skip(1)).Any(z=>z.First.CloseAt>z.Second.OpenAt))
                throw new ArgumentException("HISTORICAL_TAPE_DUPLICATED_OR_REVERSED_M5");
            var m15=AggregateCompletedM15(b);
            paths.Add(source.Symbol,(b,m15));
            total5+=b.Length;total15+=m15.Length;
        }
        if(total5>12000000||total15>4000000||
           tape.Quotes.Length>14000000||
           tape.Quotes.Any(x=>x.At<=0||x.Quote is null||
               x.Quote.At!=x.At||x.Contract is null||
               x.Quote.Symbol!=x.Contract.Symbol||
               !paths.ContainsKey(x.Quote.Symbol)||
               x.SlippagePerSideQuote<0||x.HoldingMinutes<15||
               x.HoldingMinutes>240||
               !NativeCausalExitResearch.Supported(x.ExitPolicy)))
            throw new ArgumentException("HISTORICAL_TAPE_BROKER_QUOTE_CONTRACT_MISSING");
        var samples=tape.Quotes.OrderBy(x=>x.At)
            .ThenBy(x=>x.Quote.Symbol,StringComparer.Ordinal).ToArray();
        if(samples.Zip(samples.Skip(1)).Any(x=>
            x.First.At==x.Second.At&&x.First.Quote.Symbol==x.Second.Quote.Symbol))
            throw new ArgumentException("HISTORICAL_TAPE_DUPLICATED_QUOTE_SYMBOL_CLOCK");
        var simulation=new NativeProductResearchLoop(ResearchMode);
        var reasonCounts=new Dictionary<string,int>(StringComparer.Ordinal);
        var categoryCounts=new Dictionary<string,int>(StringComparer.Ordinal);
        var signalFamilies=new Dictionary<string,int>(StringComparer.Ordinal);
        decimal maxMargin=0m;
        var traces=new List<NativeHistoricalEquityObservation>();
        var weeks=new SortedDictionary<string,int>(StringComparer.Ordinal);
        NativeProductResearchReport? last=null;
        foreach(var group in samples.GroupBy(x=>x.At))
        {
            var inputs=group.Select(x=>{
                var bars=paths[x.Quote.Symbol];
                // Both complete M5 and M15 windows are anchored at the
                // current quote clock, never at the tape's final future bar.
                return new NativeProductMarket(x.Quote.Symbol,
                    Prefix(bars.M5,group.Key),Prefix(bars.M15,group.Key),
                    x.Quote,x.Contract,x.SlippagePerSideQuote,x.HoldingMinutes,
                    IndependentlySupportedAgainstBenchmark:false,
                    ExitPolicy:x.ExitPolicy);
            }).ToArray();
            last=simulation.Advance(group.Key,inputs,UnqualifiedShadowMode);
            foreach(var signal in last.LatestSignals)
            {
                signalFamilies[signal.Mechanism]=
                    signalFamilies.GetValueOrDefault(signal.Mechanism)+1;
                if(signal.Status=="SHADOW_MODEL_INTENT_ALLOCATED_NOT_TRADING")continue;
                string reason=signal.DecisionReason;
                reasonCounts[reason]=reasonCounts.GetValueOrDefault(reason)+1;
                var category=RejectionCategory(reason);
                categoryCounts[category]=categoryCounts.GetValueOrDefault(category)+1;
            }
            var central=simulation.ResearchSession.Ledger.Summary(group.Key);
            if(central.UsedMarginEur is decimal used)
                maxMargin=Math.Max(maxMargin,used);
            var adverse=simulation.AdverseScenario.Summary;
            traces.Add(new(group.Key,central.LiquidationEquityEur,
                adverse?.LiquidationEquityEur,central.UsedMarginEur,
                central.CompleteRoundTrips,last.Forecasts,
                last.ObservedM5SlotsNotScored,adverse?.UsedMarginEur,
                adverse?.FreeMarginEur));
            weeks.TryAdd(Week(group.Key),0);
        }
        if(last is null)throw new ArgumentException("HISTORICAL_TAPE_NO_QUOTES");
        foreach(var pair in last.ModelRoundTripsPerIsoWeek)
            weeks[pair.Key]=pair.Value;
        var monetary=simulation.ResearchSession.Ledger.Summary();
        ObserveFinalLedger?.Invoke(simulation.ResearchSession.Ledger);
        // Quote clocks are evidence of market MARKS, not a complete intrabar
        // equity path. No zero DD is certified when between-mark prices absent.
        bool complete=last.HistoryPathComplete &&
            monetary.LiquidationEquityEur is not null &&
            monetary.OpenPositions==0&&monetary.PendingIntents==0 &&
            traces.All(x=>x.CentralEquityEur.HasValue);
        return new(tape.SourceLabel,
            "INPUT_FILE_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED_BY_THIS_ADAPTER",
            paths.Count,checked((int)total5),checked((int)total15),
            tape.Quotes.Length,traces.Count,
            last.ModelClosedRoundTrips,last.AcceptedModelIntents,last.RejectedIntents,
            monetary.CashEur,
            last.ModelGrossEur,last.ModelCentralNetEur,
            last.ModelAdverseNetProxyEur,last.ModelMatchedLongBenchmarkEur,
            last.ModelIncrementalVsLongEur,
            monetary.MaximumSampledDrawdown,
            new Dictionary<string,int>(weeks,StringComparer.Ordinal),
            traces.ToArray(),last.ObservedM5SlotsNotScored,
            // M5 closes/quote snapshots NEVER prove the complete intrabar
            // floating-equity path needed for DD30 certification.
            false,
            monetary.OpenPositions,monetary.PendingIntents,
            ForecastsGenerated:last.Forecasts,
            ObservedSymbols:paths.Keys.OrderBy(x=>x,StringComparer.Ordinal).ToArray(),
            ActuallyScoredTimeframes:new[]{"M5","M15_AGGREGATED_FROM_COMPLETED_M5"},
            CompleteSampledSnapshotCalendar:complete,
            RejectionReasons:reasonCounts,
            RejectionCategories:categoryCounts,
            SignalsByMechanism:signalFamilies,
            ClosedNetByMechanismEur:simulation.ResearchSession.Ledger
                .ClosedFragments().GroupBy(x=>
                    x.PositionId.Split('/').Length>=4 ?
                    x.PositionId.Split('/')[1]:"FROZEN_LEGACY_M5_M15",
                    StringComparer.Ordinal).ToDictionary(
                    x=>x.Key,x=>x.Sum(v=>v.NetEur),StringComparer.Ordinal),
            MaximumObservedMarginEur:maxMargin,
            ResearchMode:ResearchMode,
            ExitReasonCounts:last.ModelExitReasons,
            MatchedShortBenchmarkNetEur:last.ModelMatchedShortBenchmarkEur,
            MatchedOppositeSignalBenchmarkNetEur:
                last.ModelMatchedOppositeSignalBenchmarkEur,
            IncrementalVsBestConstantSideEur:
                last.ModelMatchedShortBenchmarkEur is decimal sh &&
                last.ModelMatchedLongBenchmarkEur is decimal lo ?
                last.ModelCentralNetEur-Math.Max(0m,Math.Max(sh,lo)):null,
            IncrementalVsOppositeSignalEur:
                last.ModelMatchedOppositeSignalBenchmarkEur is decimal flip ?
                last.ModelCentralNetEur-flip:null,
            UnfinancedModelOpenCancellations:simulation.UnfinancedModelOpenCancellations,
            AdverseFailureKind:simulation.AdverseScenario.FailureKind,
            AdverseFailureAt:simulation.AdverseScenario.FailureAt,
            AdverseFailureEventKind:simulation.AdverseScenario.FailureEventKind,
            DistinctHistoricalStressDecisions:ResearchMode.StartsWith("JRS1_",StringComparison.Ordinal)
                ?simulation.DistinctHistoricalStressDecisions:null,
            DistinctHistoricalStressDecisionsWithExposure:ResearchMode.StartsWith("JRS1_",StringComparison.Ordinal)
                ?simulation.DistinctHistoricalStressDecisionsWithExposure:null);
    }
}
