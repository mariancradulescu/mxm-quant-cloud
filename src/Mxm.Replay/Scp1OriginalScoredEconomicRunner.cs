using System;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

// SCP1 owner-frozen authentic HXC1 completed native M5/M15 score discovery,
// method selection only on CAL, then a *NEW* economically conditional EUR300
// portfolio-selection test on already-exposed OEI1 original quote clocks.
// THIS DOES NOT REEXECUTE OR RESCORE THE FROZEN UCP1 ORIGINAL STUDY.
internal static class Scp1OriginalScoredEconomicRunner
{
    static readonly JsonSerializerOptions Opt=new(){
        WriteIndented=true,NumberHandling=JsonNumberHandling.AllowReadingFromString
    };
    static string Sha(string s)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    private static bool OriginalQuote(Scp1OriginalQuoteSource market,
        Npi1ObservedQuote x,Npi1ObservedQuote? fx,out LedgerQuote quote)
    {
        quote=null!;
        if(fx is null || x.At!=fx.At ||x.Bid<=0||x.Ask<x.Bid||
           x.BidAt>x.At||x.AskAt>x.At||x.At-x.BidAt>30000L||
           x.At-x.AskAt>30000L||fx.Bid<=0||fx.Ask<fx.Bid||
           fx.At-fx.BidAt>30000L||fx.At-fx.AskAt>30000L||
           market.MinMarginEur<=0m||market.TickSize<=0m||
           market.Contract.MinimumUnits<=0m||
           market.Contract.QuoteAsset!="USD"||
           market.Contract.CommissionType is 1 or 3)
            return false;
        try
        {
            var ctx=new NativeMarketCostContext(x.At,x.Bid,x.Ask,
                1m/fx.Ask,1m/fx.Bid,1m/fx.Bid,null,
                market.MinMarginEur,market.Contract.MinimumUnits,
                Math.Max(market.TickSize,x.Ask-x.Bid));
            quote=NativeBrokerContractCosts.Quote(market.Contract,ctx).Quote;
            return true;
        }
        catch(ArgumentException){return false;}
        catch(InvalidOperationException){return false;}
        catch(OverflowException){return false;}
    }

    static string Week(long t)
    {
        var x=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return System.Globalization.ISOWeek.GetYear(x)+"-W"+
            System.Globalization.ISOWeek.GetWeekOfYear(x).ToString("00");
    }
    public static int Run(string sourceFile,string outputFile)
    {
        var input=JsonSerializer.Deserialize<Scp1OriginalInput>(
            File.ReadAllText(sourceFile),Opt)
            ??throw new ArgumentException("SCP1_PROTECTED_ORIGINAL_INPUT_NOT_READABLE");
        if(input.Streams.Length!=12 ||
           input.Streams.Select(s=>s.Symbol).Distinct(StringComparer.Ordinal).Count()!=12 ||
           input.QuoteMarkets.Select(x=>x.Symbol)
               .OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(new[]{"EURUSD","US500"})==false ||
           input.OriginalHxc1SourceSha256.Length!=64||
           input.OriginalOei1SourceSha256.Length!=64)
            throw new ArgumentException("SCP1_ORIGINAL_SOURCE_SCOPE_MISMATCH");
        // Full original genuine completed M5/M15; no resampled mid extrema.
        foreach(var s in input.Streams)
        {
            if(s.M5.Length<3000||s.M15.Length<1000 ||
               s.M5.Zip(s.M5.Skip(1)).Any(p=>
                   p.First.CloseAt>p.Second.OpenAt)||
               s.M15.Zip(s.M15.Skip(1)).Any(p=>
                   p.First.CloseAt>p.Second.OpenAt)||
               s.M5.Any(b=>b.CloseAt-b.OpenAt!=300000L)||
               s.M15.Any(b=>b.CloseAt-b.OpenAt!=900000L))
                throw new ArgumentException("SCP1_GENUINE_M5_M15_CONSISTENCY");
        }
        var training=NativeScp1EconomicScorer.BuildTrainingEpisodes(input.Streams);
        var snapshot=NativeScp1EconomicScorer.Train(training,
            input.OriginalHxc1SourceSha256);
        var methods=new[]{"NO_SCORE","BAYES_CONTEXT","RIDGE_NONLINEAR"};
        var diag=methods.SelectMany(method=>new[]{
            NativeScp1EconomicScorer.Diagnose(snapshot,training,
                "TRAIN_EXPOSED",method,NativeScp1EconomicScorer.Start,
                NativeScp1EconomicScorer.EndTrain),
            NativeScp1EconomicScorer.Diagnose(snapshot,training,
                "CALIBRATION_EXPOSED",method,NativeScp1EconomicScorer.EndTrain,
                NativeScp1EconomicScorer.EndCal),
            NativeScp1EconomicScorer.Diagnose(snapshot,training,
                "EVALUATION_GLOBALLY_EXPOSED",method,
                NativeScp1EconomicScorer.EndCal,
                NativeScp1EconomicScorer.EndEval)
        }).ToArray();

        // ALL finance policies execute independent, internally SHARED EUR300
        // books, the same C# Core, scored on the same original quote clocks.
        var names=new[]{"SCP1_FIRST","SCP1_SCORE","SCP1_MARGINAL",
                        "SCP1_ABSTAIN","SCP1_LONG","SCP1_SHORT","SCP1_CASH"};
        var engines=names.ToDictionary(x=>x,
            x=>new NativeUnifiedPortfolioEngine(x,"",snapshot),
            StringComparer.Ordinal);
        var bars=input.Streams.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        var markets=input.QuoteMarkets.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        var times=input.QuoteMarkets.SelectMany(m=>m.Quotes.Select(q=>
            (Symbol:m.Symbol,Quote:q)))
            .GroupBy(x=>x.Quote.At).OrderBy(x=>x.Key).ToArray();
        // Both original financial price clocks and the same causal M15
        // context breadth refer only to native completed observations.
        var pointers=input.Streams.ToDictionary(s=>s.Symbol,
            s=>(M5:0,M15:0),StringComparer.Ordinal);
        var rejected=new Dictionary<string,int>(StringComparer.Ordinal);
        var familyProposals=new Dictionary<string,int>(StringComparer.Ordinal);
        int genuineFinanceFrames=0;
        foreach(var at in times)
        {
            long t=at.Key;
            // CAUSAL ANTI-LEAKAGE: fit uses observations before Sep 28;
            // estimator method selection uses CAL before Oct 19. No frozen
            // fitted model is permitted to take hypothetical economic
            // decisions in either period where its own fit was unavailable.
            // All 7 money books start fresh EUR300 only in the EXPOSED
            // post-calibration evaluation period.
            if(t<NativeScp1EconomicScorer.EndCal ||
               t>=NativeScp1EconomicScorer.EndEval)continue;
            var raw=at.ToDictionary(x=>x.Symbol,x=>x.Quote,StringComparer.Ordinal);
            raw.TryGetValue("EURUSD",out var fx);
            var mt=new List<Ucp1MarketFrame>();
            // Form exactly the M5/M15 feature universe that Cloud would
            // see at this clock; BROKER bars include true source OHLC.
            var context=new Dictionary<string,(NativeClosedMarketBar[] M5,
                NativeClosedMarketBar[] M15)>(StringComparer.Ordinal);
            foreach(var s in input.Streams)
            {
                var ix=pointers[s.Symbol];
                while(ix.M5<s.M5.Length&&s.M5[ix.M5].CloseAt<t)ix.M5++;
                while(ix.M15<s.M15.Length&&s.M15[ix.M15].CloseAt<t)ix.M15++;
                pointers[s.Symbol]=ix;
                var x=s.M5.Skip(Math.Max(0,ix.M5-5)).Take(5).ToArray();
                var z=s.M15.Skip(Math.Max(0,ix.M15-3)).Take(3).ToArray();
                if(x.Length!=5||z.Length!=3)continue;
                context[s.Symbol]=(x,z);
            }
            var dirs=context.Values.Select(v=>{
                var z=v.M15;
                return z[^2].CloseAt==z[^1].OpenAt &&
                    t-z[^1].CloseAt<=900000L
                    ?Math.Sign(z[^1].Close-z[^2].Close):0;
            }).Where(v=>v!=0).ToArray();
            decimal breadth=dirs.Length>=4?
                (decimal)dirs.Sum()/dirs.Length:0m;
            foreach(var pair in raw.OrderBy(x=>x.Key,StringComparer.Ordinal))
            {
                if(!markets.TryGetValue(pair.Key,out var market)||
                   !context.TryGetValue(pair.Key,out var barsHere))
                {
                    rejected[pair.Key+"/NO_REAL_M5_M15"]=
                        rejected.GetValueOrDefault(pair.Key+"/NO_REAL_M5_M15")+1;
                    continue;
                }
                if(!OriginalQuote(market,pair.Value,fx,out var quote))
                {
                    rejected[pair.Key+"/NO_FINANCED_ORIGINAL_QUOTE"]=
                        rejected.GetValueOrDefault(pair.Key+"/NO_FINANCED_ORIGINAL_QUOTE")+1;
                    continue;
                }
                var obs=new Ucp1MarketFrame(pair.Key,quote,market.Contract,
                    barsHere.M5,barsHere.M15,
                    Math.Max(market.TickSize,quote.Ask-quote.Bid),
                    "HXC1_AUTHENTIC_M5_M15_OHLCV_NOT_SAMPLE_PROXY");
                mt.Add(obs);
                foreach(var signal in Ucp1CausalSignals.Describe(obs,t))
                    familyProposals[signal.Family]=
                        familyProposals.GetValueOrDefault(signal.Family)+1;
            }
            if(mt.Count>0)genuineFinanceFrames++;
            var frame=new Ucp1Frame(t,mt.ToArray(),IntermarketBreadth:breadth);
            foreach(var book in engines.Values)
                book.Advance(frame);
        }
        // Performance BY PREDECISION SCORE BINS, with bin boundaries
        // set from ALL observed proposals, not retrospectively from winners.
        // Untraded proposals have unknown funded P&L and are NOT treated
        // as fictitious executed losing/winning controls.
        object ScoreConditionedEconomicOutcome(NativeUnifiedPortfolioEngine e)
        {
            var offered=e.Scp1ChoiceReceipts
                .Where(x=>x.ConditionalExpectedNetEur.HasValue)
                .OrderBy(x=>x.ConditionalExpectedNetEur!.Value).ToArray();
            if(offered.Length==0)
                return new {Evidence="NO_RELIABLE_OFFERED_SCORE_TO_BIN",
                    Bands=Array.Empty<object>()};
            decimal[] bounds=Enumerable.Range(1,4)
                .Select(i=>offered[Math.Min(offered.Length-1,
                    i*offered.Length/5)].ConditionalExpectedNetEur!.Value)
                .ToArray();
            var linked=e.CompleteModelTrips.Select(x=>{
                long at=0;
                string token=x.PositionId.Split('/').Last();
                _=long.TryParse(token,out at);
                var score=offered.FirstOrDefault(y=>
                    y.At==at&&y.Symbol==x.Symbol&&y.Family==x.Family&&
                    y.Side==x.Side);
                int bin=score?.ConditionalExpectedNetEur is decimal v?
                    1+bounds.Count(z=>v>z):0;
                return new {Trip=x,Band=bin};
            }).ToArray();
            var bands=Enumerable.Range(1,5).Select(k=>{
                var group=linked.Where(x=>x.Band==k)
                    .Select(x=>x.Trip).ToArray();
                return (object)new {
                    ScoreBin=k,
                    OfferedProposalCount=offered.Count(x=>
                        1+bounds.Count(z=>x.ConditionalExpectedNetEur!.Value>z)==k),
                    ActuallyClosedModeledTrips=group.Length,
                    ConditionalClosedModelNetEur=group.Sum(x=>x.NetEur),
                    ConditionalMeanEurPerCompletedTrip=group.Length>0?
                        (decimal?)group.Average(x=>x.NetEur):null,
                    WinRate=group.Length>0?
                        (decimal?)group.Count(x=>x.NetEur>0m)/group.Length:null,
                    ScoreBoundariesFromAllPredecisionCandidates=true,
                    BrokerNetCertified=false
                };
            }).ToArray();
            return new {Evidence="CONDITIONAL_EUR_FINANCED_NATIVE_BOOK_COMPLETED_TRIPS_BY_EX_ANTE_SCORE_QUINTILE",
                Offered=offered.Length,
                CompletedWithMatchedPredecisionScore=linked.Count(x=>x.Band>0),
                CompletedWithUnmatchedOrMissingScore=linked.Count(x=>x.Band==0),
                Bands=bands};
        }
        var result=new Dictionary<string,object>(StringComparer.Ordinal);
        var chains=new Dictionary<string,object>(StringComparer.Ordinal);
        var scoreConditionalBins=new Dictionary<string,object>(StringComparer.Ordinal);
        foreach(var (policy,engine) in engines)
        {
            object outcome=engine.OriginalOutcomeReport(
                NativeScp1EconomicScorer.Start,
                NativeScp1EconomicScorer.EndTrain,
                NativeScp1EconomicScorer.EndCal,
                NativeScp1EconomicScorer.EndEval,
                input.OriginalOei1SourceSha256);
            var independently=new NativeFundedLedger();
            foreach(var e in engine.OriginalModelEvents)
                independently.Apply(e);
            var aggregate=engine.ModelSummary;
            var verified=independently.Summary();
            if(verified.EventChainHash!=aggregate.EventChainHash||
               verified.CashEur!=aggregate.CashEur||
               verified.CompleteRoundTrips!=aggregate.CompleteRoundTrips||
               verified.OpenPositions!=aggregate.OpenPositions||
               verified.PendingIntents!=aggregate.PendingIntents)
                throw new InvalidOperationException("SCP1_INDEPENDENT_COMMON_EUR_LEDGER_REPLAY_MISMATCH_"+policy);
            result[policy]=outcome;
            scoreConditionalBins[policy]=ScoreConditionedEconomicOutcome(engine);
            chains[policy]=new {
                Events=engine.OriginalModelEvents.Length,
                ChainHash=aggregate.EventChainHash,
                VerifiedWithFreshNativeFundedLedger=true,
                AllModelFillsRequireLaterQuote=true,
                BrokerFillsImported=0
            };
        }
        var original=new {
            Study="SCP1_NATIVE_CAUSAL_ECONOMIC_RANKING",
            input.OriginalHxc1SourceSha256,input.OriginalOei1SourceSha256,
            Protocol=NativeScp1EconomicScorer.Version,
            Model=snapshot,
            SourceClass="GENUINE_ORIGINAL_PEPPERSTONE_HXC1_M5_M15_AND_OEI1_QUOTE",
            FinancialDecisionWindow="ONLY_EVALUATION_2026_10_19_THROUGH_2026_11_09_POST_CAL",
            NoInSampleFinancialDecisionLeakage=true,
            PriceOnlyTrainingLabelCount=training.Length,
            CompleteTrainingLabels=training.Count(x=>x.Complete),
            PriceOnlyTrainingSourceHash=Sha(string.Join("|",training.Select(x=>
                x.At+":"+x.Symbol+":"+x.Family+":"+x.Side+":"+
                (x.Complete?x.GrossPriceOnlyR.ToString():x.ExitReason)))),
            Diagnostics=diag,
            ModelSelectionUsedOnlyCalibration=true,
            FullyIndependentConfirmation=false,
            AllPhasesHistoricallyGloballyExposed=true,
            SameClockGenuineQuoteFinanceFrames=genuineFinanceFrames,
            OriginalQuoteClocks=times.Length,
            SourceCounts=input.Streams.ToDictionary(s=>s.Symbol,
                s=>new {AuthenticM5=s.M5.Length,AuthenticM15=s.M15.Length}),
            FundingIneligibleClassesWithoutMatchingNativeM5M15=
                new[]{"ETHUSD","SpotBrent"},
            ObservedCandidateFamilies=familyProposals,
            MissingFinancialOrBarEvidence=rejected,
            ConditionalPolicies=result,LedgerReceipts=chains,
            ScoreConditionedConditionalEurPerformance=scoreConditionalBins,
            OrdersSubmitted=0,CloudActivated=false,
            BrokerNetCertified=false,
            HistoricFundingCertified=false,
            ContinuousFloatingDrawdownCertified=false,
            Hard21Certified=false,Independent12Months=false,
            ResultStatus="SCORE_SELECTION_TEST_ORIGINAL_SOURCE_CONDITIONAL_EUR300_NO_BROKER_CERTIFICATE"
        };
        File.WriteAllText(outputFile,JsonSerializer.Serialize(original,Opt)+"\n");
        return 0;
    }
}
