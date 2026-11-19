using System;
using System.Linq;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

// Only original-source IO, NOT another Python/Replay strategy. Native C#
// constructs sampled completed M5/M15 proxy bars from genuine as-of quotes
// and calls EXACT Mxm.Core.Advance also used in observation-only Cloud.
internal static class Ucp1OriginalUnifiedRunner
{
    const long Minute=60000,Five=300000,Fifteen=900000;
    static readonly JsonSerializerOptions Options=new(){
        WriteIndented=true,
        NumberHandling=JsonNumberHandling.AllowReadingFromString
    };
    private static bool Quote(Npi1OriginalMarket market,Npi1ObservedQuote q,
        Npi1ObservedQuote? fx,out LedgerQuote value)
    {
        value=null!;
        if(q is null||fx is null||q.At!=fx.At||q.Bid<=0||q.Ask<q.Bid||
           q.BidAt>q.At||q.AskAt>q.At||q.At-q.BidAt>30000||
           q.At-q.AskAt>30000||fx.At-fx.BidAt>30000||
           fx.At-fx.AskAt>30000||fx.Bid<=0||fx.Ask<fx.Bid||
           market.Contract.QuoteAsset!="USD"||
           market.Contract.CommissionType is 1 or 3 ||
           market.MinMarginEur<=0||market.Contract.MinimumUnits<=0||
           market.TickSize<=0)
            return false;
        try
        {
            value=NativeBrokerContractCosts.Quote(market.Contract,
                new NativeMarketCostContext(q.At,q.Bid,q.Ask,
                    1m/fx.Ask,1m/fx.Bid,1m/fx.Bid,null,
                    market.MinMarginEur,market.Contract.MinimumUnits,
                    Math.Max(market.TickSize,q.Ask-q.Bid))).Quote;
            return true;
        }
        catch(ArgumentException){return false;}
        catch(InvalidOperationException){return false;}
        catch(OverflowException){return false;}
    }

    static NativeClosedMarketBar[] CompletedSampledBars(
        Npi1ObservedQuote[] source,long duration)
    {
        int n=checked((int)(duration/Minute));
        var rows=new List<NativeClosedMarketBar>();
        foreach(var g in source.GroupBy(q=>q.At/duration).OrderBy(g=>g.Key))
        {
            var sorted=g.OrderBy(x=>x.At).ToArray();
            long open=g.Key*duration;
            if(sorted.Length!=n || sorted[0].At!=open ||
               sorted[^1].At!=open+duration-Minute ||
               sorted.Where((x,i)=>x.At!=open+i*Minute ||
                    x.Bid<=0||x.Ask<x.Bid).Any())
                continue;
            decimal[] mid=sorted.Select(x=>(x.Bid+x.Ask)/2m).ToArray();
            // Only sampled as-of minute marks. High/low here are maxima and
            // minima among sampled midpoints, NEVER full tick OHLC extrema.
            rows.Add(new NativeClosedMarketBar(open,open+duration,
                mid[0],mid.Max(),mid.Min(),mid[^1],n));
        }
        return rows.ToArray();
    }

    public static int Run(string originalInput,string output)
    {
        var tape=JsonSerializer.Deserialize<Npi1OriginalTape>(
            File.ReadAllText(originalInput),Options)
            ??throw new ArgumentException("UCP1_ORIGINAL_TAPE_NOT_DESERIALIZED");
        var allowed=new[]{"EURUSD","ETHUSD","SpotBrent","US500"}
            .OrderBy(x=>x,StringComparer.Ordinal).ToArray();
        if(tape.OriginalSourceSha256 is null||
           tape.OriginalSourceSha256.Length!=64||
           tape.Markets.Length!=4||
           !tape.Markets.Select(m=>m.Name)
              .OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(allowed))
            throw new ArgumentException("UCP1_ORIGINAL_FOUR_CLASS_SOURCE_CONTRACT");
        var maps=tape.Markets.ToDictionary(x=>x.Name,StringComparer.Ordinal);
        var m5=tape.Markets.ToDictionary(x=>x.Name,
            x=>CompletedSampledBars(x.Quotes,Five),StringComparer.Ordinal);
        var m15=tape.Markets.ToDictionary(x=>x.Name,
            x=>CompletedSampledBars(x.Quotes,Fifteen),StringComparer.Ordinal);
        var byTime=tape.Markets.SelectMany(m=>m.Quotes.Select(x=>new {
                Symbol=m.Name,Market=x}))
            .GroupBy(x=>x.Market.At).OrderBy(x=>x.Key).ToArray();
        var times=byTime.Select(x=>x.Key).ToArray();
        if(times.Length<1000 || times.Zip(times.Skip(1))
             .Any(x=>x.First>=x.Second))
            throw new ArgumentException("UCP1_SOURCE_CLOCK_COVERAGE_INCOMPLETE");
        var policies=new[]{"JOINT","TRANSITION_ONLY","REPAIR_ONLY",
                           "LONG","SHORT","CASH"};
        var books=policies.ToDictionary(x=>x,
            x=>new NativeUnifiedPortfolioEngine(x),StringComparer.Ordinal);
        var rejectedQuoteReasons=new Dictionary<string,int>(StringComparer.Ordinal);
        foreach(var clock in byTime)
        {
            long t=clock.Key;
            var raw=clock.ToDictionary(x=>x.Symbol,x=>x.Market,StringComparer.Ordinal);
            raw.TryGetValue("EURUSD",out var fx);
            var markets=new List<Ucp1MarketFrame>();
            foreach(var pair in raw.OrderBy(x=>x.Key,StringComparer.Ordinal))
            {
                var m=maps[pair.Key];
                if(!Quote(m,pair.Value,fx,out var q))
                {
                    rejectedQuoteReasons[pair.Key]=rejectedQuoteReasons.GetValueOrDefault(pair.Key)+1;
                    continue;
                }
                var prefix5=m5[pair.Key].Where(x=>x.CloseAt<t)
                    .TakeLast(5).ToArray();
                var prefix15=m15[pair.Key].Where(x=>x.CloseAt<t)
                    .TakeLast(3).ToArray();
                markets.Add(new Ucp1MarketFrame(pair.Key,q,m.Contract,
                    prefix5,prefix15,
                    Math.Max(m.TickSize,q.Ask-q.Bid),
                    "ORIGINAL_ASOF_BIDASK_M5_M15_SAMPLED_MIDPOINT_PROXIES"));
            }
            var frame=new Ucp1Frame(t,markets.ToArray());
            foreach(var engine in books.Values)
                engine.Advance(frame);
        }
        long cal=new DateTimeOffset(2026,9,28,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
        long eval=new DateTimeOffset(2026,10,19,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
        var results=new Dictionary<string,object>(StringComparer.Ordinal);
        var verification=new Dictionary<string,object>(StringComparer.Ordinal);
        foreach(var kv in books)
        {
            var result=kv.Value.OriginalOutcomeReport(tape.Start,cal,eval,tape.End,
                tape.OriginalSourceSha256);
            // Independent native ledger replay using only published original
            // event receipts, not the original strategy evaluator's aggregate.
            var independently=NativeFundedLedger.ReceiveFacts(kv.Value.OriginalModelEvents);
            using var doc=JsonDocument.Parse(JsonSerializer.Serialize(independently,Options));
            string hash=doc.RootElement.GetProperty("Summary")
                .GetProperty("EventChainHash").GetString()!;
            if(hash!=kv.Value.ModelSummary.EventChainHash)
                throw new InvalidOperationException("UCP1_INDEPENDENT_NATIVE_EVENT_CHAIN_MISMATCH_"+kv.Key);
            results[kv.Key]=result;
            verification[kv.Key]=new {
                OriginalNativeEvents=kv.Value.OriginalModelEvents.Length,
                EventChainSha256=hash,
                RestartEveryEventMatched=true,
                ModelOnlyNoBrokerExecutedFills=true
            };
        }
        // The report carries the full original C# event ledger and the
        // complete modeled EUR300 equity path for independent reconstruction.
        var report=new {
            Study="UCP1_NEW_UNIFIED_PRODUCT_AND_ECONOMICS",
            OriginalSourceRun=44247979857L,
            tape.OriginalSourceSha256,Start=tape.Start,End=tape.End,
            Currency="EUR",Policies=results,Verification=verification,
            ChronologicalDevelopmentEnd=cal,ChronologicalCalibrationEnd=eval,
            OriginalSourceQuoteClocks=times.Length,
            OriginalInputMarksBySymbol=tape.Markets.ToDictionary(
                x=>x.Name,x=>x.Quotes.Length),
            SampledCompletedM5BySymbol=m5.ToDictionary(x=>x.Key,x=>x.Value.Length),
            SampledCompletedM15BySymbol=m15.ToDictionary(x=>x.Key,x=>x.Value.Length),
            OriginalQuoteContractRejections=rejectedQuoteReasons,
            SourceTimeframes=new[]{"M1_ORIGINAL_ASOF","M5_SAMPLED_BAR",
                                   "M15_SAMPLED_BAR"},
            SourceGloballyExposedNotIndependent=true,
            HistoricalFundingAndTariffsNotCertified=true,
            OriginalBrokerDealsNotAvailable=true,
            ContinuousFloatingDrawdownNotObserved=true,
            OriginalStudiesRelaunched=0,BrokerOrdersSubmitted=0,
            CloudActivated=false,
            Status="CONDITIONAL_COMPLETE_POLICY_ORIGINAL_EUR300_FINANCIAL_REPLAY_NO_BROKER_CERTIFICATION"
        };
        File.WriteAllText(output,JsonSerializer.Serialize(report,Options)+"\n");
        return 0;
    }
}
