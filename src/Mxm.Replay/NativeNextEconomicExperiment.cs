using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

// Separate NXE1 read-only replay. The prospective portfolio gate MUST refuse
// historical evidence with a later (current) contract/schedule timestamp.
// Independent of that, score all prespecified fixed-horizon diagnostic labels
// on original paired BID/ASK if complete. Those labels are NEVER financed
// entries, broker stop executions, or an independently held-out confirmation.
internal static class NativeNextEconomicExperiment
{
    const long M5=300000L;
    private sealed record Label(long At,long MatureAt,string Mechanism,int Side,
        decimal? CentralEur,decimal? AdverseEur,
        decimal? LongEur,decimal? ShortEur,decimal? SpreadEur,
        decimal? CommissionEur,decimal? SlippageEur,
        string Status);
    static NativeClosedMarketBar[] Prefix(NativeClosedMarketBar[] bars,long at)
    {
        int lo=0,hi=bars.Length;
        while(lo<hi)
        {
            int mid=lo+(hi-lo)/2;
            if(bars[mid].CloseAt<=at-1500L)lo=mid+1;else hi=mid;
        }
        int count=Math.Min(8,lo);
        return bars.Skip(lo-count).Take(count).ToArray();
    }
    static decimal Fee(LedgerQuote q,decimal units)=>
        Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);
    static decimal CalculateNet(NativeHistoricalQuoteObservation entry,
        NativeHistoricalQuoteObservation exit,int side)
    {
        var a=entry.Quote;var z=exit.Quote;
        decimal units=entry.Contract!.MinimumUnits;
        decimal start=side==1?a.Ask+entry.SlippagePerSideQuote:
            a.Bid-entry.SlippagePerSideQuote;
        decimal end=side==1?z.Bid-exit.SlippagePerSideQuote:
            z.Ask+exit.SlippagePerSideQuote;
        decimal gross=(end-start)*side*units;
        decimal fx=gross>=0m?z.EurCredit:z.EurDebit;
        return gross*fx-Fee(a,units)-Fee(z,units);
    }
    static string Week(long at)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return System.Globalization.ISOWeek.GetYear(d)+"-W"+
          System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
    }
    static object Group(IEnumerable<Label> data)
    {
        var all=data.ToArray();
        var complete=all.Where(x=>x.Status=="COMPLETE_FIXED_HORIZON").ToArray();
        return new {
            Signals=all.Length,CompleteMatchedLabels=complete.Length,
            MissingOrUnsafeLabels=all.Length-complete.Length,
            DistinctCalendarWeeks=all.Select(x=>Week(x.At)).Distinct().Count(),
            MeanCentralEur=complete.Length==0?(decimal?)null:complete.Average(x=>x.CentralEur!.Value),
            MeanAdverseEur=complete.Length==0?(decimal?)null:complete.Average(x=>x.AdverseEur!.Value),
            SumOverlappingUnfundedCentralEur=complete.Length==0?(decimal?)null:complete.Sum(x=>x.CentralEur!.Value),
            SumOverlappingUnfundedAdverseEur=complete.Length==0?(decimal?)null:complete.Sum(x=>x.AdverseEur!.Value),
            MeanMatchedLongEur=complete.Length==0?(decimal?)null:complete.Average(x=>x.LongEur!.Value),
            MeanMatchedShortEur=complete.Length==0?(decimal?)null:complete.Average(x=>x.ShortEur!.Value),
            MeanRoundtripSpreadEur=complete.Length==0?(decimal?)null:complete.Average(x=>x.SpreadEur!.Value),
            MeanCommissionsEur=complete.Length==0?(decimal?)null:complete.Average(x=>x.CommissionEur!.Value),
            MeanSlippageEur=complete.Length==0?(decimal?)null:complete.Average(x=>x.SlippageEur!.Value),
            WeeklyCompleteLabels=complete.GroupBy(x=>Week(x.At)).ToDictionary(x=>x.Key,x=>x.Count()),
            MissingReasons=all.Where(x=>x.Status!="COMPLETE_FIXED_HORIZON")
                .GroupBy(x=>x.Status).ToDictionary(x=>x.Key,x=>x.Count())
        };
    }
    internal static int Run(string input,string output)
    {
        try
        {
            var bytes=System.IO.File.ReadAllBytes(input);
            var source=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes,
                new JsonSerializerOptions {
                    NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
                })??throw new ArgumentException("NXE1_SOURCE_MISSING");
            var symbols=source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal).ToArray();
            if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_NXE1_CROSS_ASSET_INDUSTRIAL_2026"||
               !new[]{"EURUSD","US500"}.All(x=>symbols.Contains(x,StringComparer.Ordinal))||
               symbols.Any(x=>x is not ("EURUSD" or "US500" or "US30"))||
               symbols.Length!=symbols.Distinct(StringComparer.Ordinal).Count()||
               source.Marks.Any(x=>!symbols.Contains(x.Symbol,StringComparer.Ordinal)))
                throw new ArgumentException("NXE1_FROZEN_UNIVERSE_OR_ORIGINAL_SOURCE_INVALID");
            var converted=NativeOriginalOpenApiProductAdapter.Convert(source);
            using var json=JsonDocument.Parse(bytes);
            var sessions=json.RootElement.GetProperty("Schedules");
            var tape=converted with {Quotes=converted.Quotes.Select(x=>{
                string sym=x.Quote.Symbol;
                int horizon=sym=="US30"?180:120;
                string policy=sym=="US30"?NativeCausalExitResearch.Chandelier:
                    NativeCausalExitResearch.PredictionInvalidation;
                var c=x.Contract!;
                var broker=sessions.GetProperty(sym);
                var intervals=broker.GetProperty("Intervals").EnumerateArray().Select(z=>
                    new NativeWeeklyTradingInterval(z[0].GetInt32(),z[1].GetInt32())).ToArray();
                var proof=new NativeProspectiveSessionRiskEvidence(
                    broker.GetProperty("TimeZone").GetString()??"",
                    intervals,c.ObservedAtUtcMs,x.At,horizon,1000,
                    HolidayCalendarCovered:false,
                    PriorHoldingQuoteCoverageSufficient:false,
                    CommonLiquidationEquityEur:null,CommonPeakEquityEur:null,
                    CommonFreeMarginEur:null,
                    NewMarginEur:x.Quote.MarginPerUnit*c.MinimumUnits,
                    MarginalAdverseLossEur:null) {
                    QuoteConversionRouteCovered=x.Quote.EurCredit>0m&&x.Quote.EurDebit>0m,
                    MonitoringCalendarCoveredThroughMs=x.At,
                    GapReserveCoversAllInterruptions=false
                };
                return x with {HoldingMinutes=horizon,ExitPolicy=policy,
                    SessionAdmissionEvidence=proof};
            }).ToArray()};
            // Actual prospective route: it must FAIL CLOSED because
            // schedules retrieved in Nov 2026 postdate historical decision clocks.
            var joint=NativeHistoricalProductReplay.Evaluate(tape,true,"NXE1_JOINT");
            var cash=NativeHistoricalProductReplay.Evaluate(tape,true,"NXE1_CASH");
            if(joint.ModelIntentCount!=0||joint.CompletedModelRoundTrips!=0||
               cash.ModelIntentCount!=0||cash.CompletedModelRoundTrips!=0)
                throw new ArgumentException("NXE1_RETROSPECTIVE_SCHEDULE_BYPASSED_RISK_GATE");
            // Independently audit new structural features against strictly
            // earlier completed M15 bars and observed 5-minute BID/ASK clocks.
            var m15=tape.Bars.ToDictionary(x=>x.Symbol,
                x=>NativeHistoricalProductReplay.AggregateCompletedM15(x.M5),
                StringComparer.Ordinal);
            var quotes=tape.Quotes.ToDictionary(x=>(x.Quote.Symbol,x.At));
            var all=new List<Label>();
            var signals=new List<(long At,string Symbol,string Mechanism,int Side,decimal Driver)>();
            foreach(var group in tape.Quotes.Where(x=>x.At%900000L==1500L)
                .GroupBy(x=>x.At))
            {
                var available=group.ToDictionary(x=>x.Quote.Symbol,
                    x=>new NativeProductMarket(x.Quote.Symbol,
                        Array.Empty<NativeClosedMarketBar>(),
                        Prefix(m15[x.Quote.Symbol],group.Key),
                        x.Quote,x.Contract,x.SlippagePerSideQuote,x.HoldingMinutes),
                    StringComparer.Ordinal);
                foreach(string target in new[]{"EURUSD","US30"})
                {
                    if(!available.TryGetValue(target,out var current))continue;
                    var f=NativeNextEconomicResearch.Forecast(current,available,group.Key);
                    if(f.Side!=0)signals.Add((group.Key,target,f.Mechanism,f.Side,f.Magnitude));
                }
            }
            foreach(var signal in signals)
            {
                int duration=signal.Symbol=="US30"?180:120;
                // Freeze causal execution latency: first model entry at
                // the NEXT observed 5-minute mark after the signal, never
                // at the information clock used to decide the direction.
                long opened=signal.At+M5;
                long until=opened+duration*60000L;
                if(!quotes.TryGetValue((signal.Symbol,signal.At),out var decision))
                    continue;
                int missing=0;
                for(long at=signal.At;at<=until;at+=M5)
                    if(!quotes.ContainsKey((signal.Symbol,at)))missing++;
                if(missing>0)
                {
                    all.Add(new(signal.At,until,signal.Mechanism,signal.Side,
                        null,null,null,null,null,null,null,
                        "MISSING_HELD_BIDASK_OR_EUR_CONVERSION_CLOCK"));
                    continue;
                }
                var first=quotes[(signal.Symbol,opened)];
                var last=quotes[(signal.Symbol,until)];
                // Current tariff is an EX-POST sensitivity only; no financing
                // default to zero at an unknown rollover.
                var ct=first.Contract!;
                if(ct.SwapTimeUtcMinute is not int rollover)
                {
                    all.Add(new(signal.At,until,signal.Mechanism,signal.Side,
                        null,null,null,null,null,null,null,
                        "CONTRACT_ROLLOVER_TIME_UNATTESTED"));
                    continue;
                }
                var d1=DateTimeOffset.FromUnixTimeMilliseconds(opened).UtcDateTime;
                var d2=DateTimeOffset.FromUnixTimeMilliseconds(until).UtcDateTime;
                bool crossesSwap=false;
                for(var d=d1.Date;d<=d2.Date;d=d.AddDays(1))
                {
                    var when=d.AddMinutes(rollover);
                    if(when>d1 && when<=d2)crossesSwap=true;
                }
                if(crossesSwap)
                {
                    all.Add(new(signal.At,until,signal.Mechanism,signal.Side,
                        null,null,null,null,null,null,null,
                        "FINANCING_CROSSING_UNPRICED_NO_ZERO_IMPUTATION"));
                    continue;
                }
                decimal central=CalculateNet(first,last,signal.Side);
                decimal alternate=CalculateNet(first,last,-signal.Side);
                decimal units=ct.MinimumUnits;
                decimal fx=(last.Quote.EurCredit+last.Quote.EurDebit)/2m;
                decimal addCost=(first.Quote.Ask-first.Quote.Bid+
                    last.Quote.Ask-last.Quote.Bid+
                    2m*(first.SlippagePerSideQuote+last.SlippagePerSideQuote))*units*fx;
                decimal spread=(first.Quote.Ask-first.Quote.Bid+
                    last.Quote.Ask-last.Quote.Bid)*units*fx;
                decimal slip=(first.SlippagePerSideQuote+last.SlippagePerSideQuote)*units*fx;
                decimal commission=Fee(first.Quote,units)+Fee(last.Quote,units);
                all.Add(new(signal.At,until,signal.Mechanism,signal.Side,central,
                    central-addCost,signal.Side==1?central:alternate,
                    signal.Side==-1?central:alternate,spread,commission,slip,
                    "COMPLETE_FIXED_HORIZON"));
            }
            // PREQUENTIAL causal calibration: only outcomes matured strictly
            // before each prediction can provide an estimated next-period NET.
            var calibrated=all.Where(x=>x.Status=="COMPLETE_FIXED_HORIZON")
                .OrderBy(x=>x.At).ToArray();
            int maturePredictions=0,positivePredictions=0,matureCorrect=0;
            decimal sumPredicted=0m,sumRealized=0m,sumBrier=0m;
            foreach(var x in calibrated)
            {
                var training=calibrated.Where(y=>y.Mechanism==x.Mechanism &&
                    y.MatureAt<x.At).ToArray();
                if(training.Length<30 ||
                   training.Select(y=>Week(y.At)).Distinct().Count()<4)
                    continue;
                decimal predicted=training.Average(y=>y.AdverseEur!.Value);
                decimal prob=(training.Count(y=>y.AdverseEur>0m)+1m)/
                    (training.Length+2m);
                decimal actual=x.AdverseEur!.Value>0m?1m:0m;
                sumBrier+=(prob-actual)*(prob-actual);
                sumPredicted+=predicted;sumRealized+=x.AdverseEur!.Value;
                maturePredictions++;if(predicted>0m)positivePredictions++;
                if((predicted>0m)==(actual>0m))matureCorrect++;
            }
            var byFamily=all.GroupBy(x=>x.Mechanism)
                .ToDictionary(g=>g.Key,g=>Group(g),StringComparer.Ordinal);
            var result=new {
                Study="NXE1",
                OriginalBrokerSourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                SourceLabel=source.SourceLabel,
                Symbols=symbols,
                BarsBySymbol=source.Bars.ToDictionary(x=>x.Symbol,x=>x.M5.Length),
                OriginalPairedBidAskWithEurConversionMarks=tape.Quotes.Length,
                FirstOriginalMarketClock=tape.Quotes.Min(x=>x.At),
                LastOriginalMarketClock=tape.Quotes.Max(x=>x.At),
                Receipt=joint with {SampledEquity=joint.SampledEquity.Where(x=>
                    !x.CentralEquityEur.HasValue || x.UsedMarginEur>0m).Take(30).ToArray()},
                Cash= new {cash.CompletedModelRoundTrips,cash.ModelClosedCentralNetEur,
                    cash.ModelClosedAdverseNetEur},
                NewFamilyPresent=symbols.Contains("US30",StringComparer.Ordinal),
                ExploratoryFixedHorizon=byFamily,
                CrossFamilyHypotheticalSignals=all.Count,
                CausalPrequentialForecasts=maturePredictions,
                CausalPrequentialPositiveNetForecasts=positivePredictions,
                CausalPrequentialSignAccuracy=maturePredictions==0?(decimal?)null:(decimal)matureCorrect/maturePredictions,
                CausalPrequentialBrier=maturePredictions==0?(decimal?)null:sumBrier/maturePredictions,
                CausalPrequentialMeanPredictedAdverseEur=maturePredictions==0?(decimal?)null:sumPredicted/maturePredictions,
                CausalPrequentialMeanActualAdverseEur=maturePredictions==0?(decimal?)null:sumRealized/maturePredictions,
                InitialCommonModelCapitalEur=300m,
                AdmittedPortfolioCapitalEur=300m,
                AdmittedPortfolioModelNetCentralEur=0m,
                AdmittedPortfolioModelNetAdverseEur=0m,
                AdmittedModelTrades=0,
                NoFinancedTradesReason="POSTDATED_CURRENT_BROKER_SESSION_TERMS_ARE_NOT_HISTORICAL_ASOF_PERMISSION",
                HypotheticalResultsAreNotFinancedOrIndependentlyConfirmed=true,
                OriginalContractTermsExPostNotHistoricalTariffCertified=true,
                AdaptiveExitBrokerFillCertified=false,
                ContinuousDrawdownCertified=false,
                CashBenchmarkEur=300m,
                StrictHeldFiveMinuteQuoteCoverageRequired=true,
                MissingQuoteAndSwapWindowsRemainUnscored=true,
                IndependentConfirmation=false,
                OrdersSubmitted=0,CloudActivated=false,
                Verdict="EXPLORATORY_PREDICTIVE_DATA_ONLY_NO_PORTFOLIO_PROMOTION"
            };
            System.IO.File.WriteAllText(output,JsonSerializer.Serialize(result));
            return 0;
        }
        catch(Exception e)
        {
            Console.Error.WriteLine("NXE1_NATIVE_RESEARCH_REJECTED:"+
                e.GetType().Name+":"+(e.Message.StartsWith("NXE1_")?e.Message:"REDACTED"));
            return 67;
        }
    }
}
