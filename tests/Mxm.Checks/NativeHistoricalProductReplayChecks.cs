using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Mxm.Core;

public static class NativeHistoricalProductReplayChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long width=300000L;
        long baseAt=DateTimeOffset.Parse("2026-11-02T00:00:00Z")
            .ToUnixTimeMilliseconds();
        NativeClosedMarketBar[] raw=Enumerable.Range(1,160).Select(i=>{
            decimal price=1.05m+i*.00024m;
            return new NativeClosedMarketBar(baseAt+(i-1)*width,
                baseAt+i*width,price,price+.00013m,
                price-.00013m,price,1000+i);
        }).ToArray();
        NativeObservedContractTerms C(long at)=>new(
            "HIST_SYNTH","USD",at,1000,1000,1000,100000,
            2,300000000,1,0,"USD",10,
            0,-.02m,-.03m,4,24,1320,3,false,0,
            true,false);
        NativeHistoricalQuoteObservation Q(int ix)
        {
            long at=baseAt+ix*width+1000;
            decimal bid=raw[ix-1].Close-.00005m;
            return new NativeHistoricalQuoteObservation(at,
                new LedgerQuote("HIST_SYNTH",at,bid,bid+.00010m,
                    .99m,1.01m,.00002m,.07m,.02m),
                C(at),.00001m,30);
        }
        var quotes=Enumerable.Range(106,19).Select(Q).ToArray();
        var original=new NativeHistoricalMarketTape("FULL_SYNTHETIC_M5_TAPE_NO_BROKER_CLAIM",
            new[]{new NativeHistoricalBars("HIST_SYNTH",raw)},quotes);
        var m15=NativeHistoricalProductReplay.AggregateCompletedM15(raw);
        check(m15.Length>=50 && m15.All(x=>x.CloseAt%900000L==0&&
              x.CloseAt-x.OpenAt==900000L),
            "native historical M15 contains exactly completed three-M5 candles");
        var out1=NativeHistoricalProductReplay.Evaluate(original,
            UnqualifiedShadowMode:true);
        check(out1.InstrumentsWithCompleteM5==1&&
              out1.OriginalM5Bars==160&&out1.CausalM15Bars==m15.Length&&
              out1.QuoteObservations==19&&out1.DistinctQuoteClocks==19&&
              out1.ModelFinalCashEur.HasValue &&
              !out1.BrokerNetCertified&&!out1.IndependentConfirmation&&
              out1.OriginalProviderAuthenticity.StartsWith("INPUT_FILE_NOT"),
            "adapter executes every model clock without claiming source authentication or broker execution");
        check(out1.SampledEquity.All(x=>x.At>0)&&
              out1.ModelTripsPerObservedIsoWeek.Count>=1 &&
              out1.ModelTripsPerObservedIsoWeek.Values.Sum()==out1.CompletedModelRoundTrips,
            "weekly model frequency accounts for all observed weeks including zero-trade weeks");
        // Alter ONLY future source prices, but keep earlier quote readings
        // exactly frozen: prior equity, signals and earlier model decisions
        // cannot change when the future OHLCV tape changes.
        var changed=raw.Select((x,i)=>i>=120?x with {
            Open=x.Open+.002m,Close=x.Close+.002m,
            High=x.High+.002m,Low=x.Low+.002m}:x).ToArray();
        var altered=NativeHistoricalProductReplay.Evaluate(original with {
            Bars=new[]{new NativeHistoricalBars("HIST_SYNTH",changed)}},true);
        check(JsonSerializer.Serialize(out1.SampledEquity.Take(8))==
              JsonSerializer.Serialize(altered.SampledEquity.Take(8)),
            "prices in future historical source cannot affect earlier C# forecast/ledger path");
        var sparse=NativeHistoricalProductReplay.Evaluate(original with {
            Quotes=quotes.Where((_,i)=>i!=7).ToArray()},true);
        check(sparse.UnscoredM5ClockSlots>=1 &&
              !sparse.ContinuousHistoricalEquityObserved,
            "historical missing quote is counted as an unscored clock, never forward-filled");
        bool futureQuoteRejected=false;
        try{NativeHistoricalProductReplay.Evaluate(original with {
            Quotes=quotes.Append(quotes[0] with {At=quotes[0].At-1}).ToArray()},true);}
        catch(ArgumentException){futureQuoteRejected=true;}
        check(futureQuoteRejected,"quote observed after declared historical decision time is rejected");
        bool duplicateBarsRejected=false;
        try{NativeHistoricalProductReplay.Evaluate(original with {
            Bars=new[]{new NativeHistoricalBars("HIST_SYNTH",raw
                .Take(10).Append(raw[9]).Concat(raw.Skip(10)).ToArray())}},true);}
        catch(ArgumentException){duplicateBarsRejected=true;}
        check(duplicateBarsRejected,"duplicate historical M5 bar never becomes a second signal");
        // Explicit RETROSPECTIVE tariff: real account contract is read after
        // the historical price observation, never backdated to the quote.
        var historicalClock=baseAt+110*width+1000;
        var laterObserved=C(baseAt+180*width) with {
            ObservedAtUtcMs=baseAt+180*width};
        var currentOriginal=new NativeOriginalOpenApiTape(
            "SYNTHETIC_CURRENT_BROKER_TARIFF_RETROSPECTIVE",
            new[]{new NativeHistoricalBars("HIST_SYNTH",raw)},
            new[]{new NativeOriginalOpenApiMarketMark(
                historicalClock,"HIST_SYNTH",1.1m,1.1002m,
                .92m,.93m,.92m,50m,.00001m,laterObserved)});
        var costed=NativeOriginalOpenApiProductAdapter.Convert(currentOriginal);
        check(costed.Quotes.Single().At==historicalClock &&
              costed.Quotes.Single().Contract!.ObservedAtUtcMs>historicalClock &&
              !costed.Quotes.Single().Contract!.HistoricalTariffContinuityCertified,
              "original observed contract timestamp is NEVER backdated for historical replay; tariff is explicit retrospective scenario");
        var scen=NativeHistoricalProductReplay.Evaluate(original,true,
            ResearchMode:"FX_CAUSAL_BREAKOUT_PLUS_RELATIVE_VALUE");
        var withoutCross=NativeHistoricalProductReplay.Evaluate(original,true,
            ResearchMode:"FX_ONLY_BREAKOUT");
        var withoutBreak=NativeHistoricalProductReplay.Evaluate(original,true,
            ResearchMode:"FX_ONLY_RELATIVE_VALUE");
        check(scen.ResearchMode=="FX_CAUSAL_BREAKOUT_PLUS_RELATIVE_VALUE" &&
              scen.RejectionReasons is not null &&
              scen.RejectionCategories is not null &&
              scen.SignalsByMechanism is not null &&
              scen.ClosedNetByMechanismEur is not null &&
              scen.RejectionCategories.Values.Sum()==
                scen.RejectionReasons.Values.Sum() &&
              scen.MaximumObservedMarginEur is not null &&
              withoutCross.ResearchMode=="FX_ONLY_BREAKOUT" &&
              withoutBreak.ResearchMode=="FX_ONLY_RELATIVE_VALUE",
              "two preregistered causal FX research hypotheses and two separately EUR300-funded ablations report all reasons, family allocations and common margin");
        Console.WriteLine("MXM_PRODUCT_HISTORICAL_ADAPTER_SYNTHETIC_RECEIPT="+
            JsonSerializer.Serialize(new {
                source=out1.SourceLabel,
                instruments=out1.InstrumentsWithCompleteM5,
                originalM5=out1.OriginalM5Bars,
                derivedM15=out1.CausalM15Bars,
                quoteClocks=out1.DistinctQuoteClocks,
                modelSignals=out1.ForecastsGenerated,
                modelIntents=out1.ModelIntentCount,
                modelClosedRoundTrips=out1.CompletedModelRoundTrips,
                modelCentralNetEur=out1.ModelClosedCentralNetEur,
                modelAdverseNetEur=out1.ModelClosedAdverseNetEur,
                matchedBenchmarkNetEur=out1.MatchedLongBenchmarkNetEur,
                descriptiveIncrementalNetEur=out1.IncrementalVsLongNetEur,
                sampledDd=out1.MaximumSampledCentralDrawdown,
                continuousIntrabarEquityCertified=false,
                authenticatedBrokerData=false,independentConfirmation=false
            }));
    }
}
