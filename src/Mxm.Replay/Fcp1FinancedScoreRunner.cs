using System;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

// FCP1 distinct source-bound financed-FIRST economic comparator. Uses the
// FROZEN public original SCP1-A1 fitted snapshot as an already-failed forecast
// negative control; DOES NOT TRAIN, RESCORE OR RERUN THE CLOSED SCP1-A1 STUDY.
// All previously visible dates remain globally exposed. No broker orders.
internal static class Fcp1FinancedScoreRunner
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
    public static int Run(string sourceFile,string frozenScp1ReportFile,string outputFile)
    {
        var input=JsonSerializer.Deserialize<Scp1OriginalInput>(
            File.ReadAllText(sourceFile),Opt)
            ??throw new ArgumentException("SCP1_PROTECTED_ORIGINAL_INPUT_NOT_READABLE");
        var genuineSix=new[]{"BTCUSD","ETHUSD","EURUSD","NAS100","US500","XAUUSD"}
            .OrderBy(x=>x,StringComparer.Ordinal).ToArray();
        if(input.SourceGeometry!="SCP1_A1_REAL_CXL1_M5_AND_HXC1_M1_TO_M5" ||
           input.OriginalCxl1CipherHashes is null ||
           input.OriginalCxl1CipherHashes.Length!=2 ||
           input.OriginalCxl1CipherHashes.Any(x=>x.Length!=64) ||
           input.Streams.Length!=6 ||
           !input.Streams.Select(s=>s.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(genuineSix) ||
           !input.QuoteMarkets.Select(x=>x.Symbol)
               .OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(new[]{"ETHUSD","EURUSD","US500"}.OrderBy(x=>x,StringComparer.Ordinal)) ||
           input.OriginalHxc1SourceSha256.Length!=64 ||
           input.OriginalOei1SourceSha256.Length!=64)
            throw new ArgumentException("SCP1_A1_REAL_M5_SIX_SOURCE_SCOPE_MISMATCH");
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
        // Read frozen ORIGINAL PUBLIC model JSON only. There is NO call to
        // BuildTrainingEpisodes, Train or Diagnose in this distinct runner.
        using var frozenDocument=JsonDocument.Parse(
            File.ReadAllText(frozenScp1ReportFile));
        var root=frozenDocument.RootElement;
        if(root.GetProperty("Study").GetString()!=
               "SCP1_NATIVE_CAUSAL_ECONOMIC_RANKING" ||
           root.GetProperty("OriginalHxc1SourceSha256").GetString()!=
               input.OriginalHxc1SourceSha256 ||
           root.GetProperty("OriginalOei1SourceSha256").GetString()!=
               input.OriginalOei1SourceSha256 ||
           root.GetProperty("SourceGeometry").GetString()!=
               input.SourceGeometry)
            throw new ArgumentException("FCP1_ORIGINAL_A1_SNAPSHOT_SOURCE_MISMATCH");
        var snapshot=root.GetProperty("Model").Deserialize<Scp1ScoreModel>(Opt)
            ??throw new ArgumentException("FCP1_ORIGINAL_A1_MODEL_MISSING");
        if(snapshot.Version!=NativeScp1EconomicScorer.Version ||
           snapshot.Method!="NO_SCORE" ||
           !snapshot.MethodSelectedWithoutEvaluation)
            throw new ArgumentException("FCP1_UNEXPECTED_FROZEN_MODEL_CHOICE");
        var diag=root.GetProperty("Diagnostics").Clone();
        int frozenTrainingCount=root.GetProperty("PriceOnlyTrainingLabelCount").GetInt32();
        int frozenCompleteCount=root.GetProperty("CompleteTrainingLabels").GetInt32();
        string frozenTrainingHash=root.GetProperty("PriceOnlyTrainingSourceHash").GetString()??"";
        string frozenModelFileHash=Convert.ToHexString(SHA256.HashData(
            File.ReadAllBytes(frozenScp1ReportFile))).ToLowerInvariant();

        // ALL finance policies execute independent, internally SHARED EUR300
        // books, the same C# Core, scored on the same original quote clocks.
        var names=NativeFcp1FinancedSelection.Policies;
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
            Study="FCP1_NATIVE_FINANCED_FIRST_VS_SCORED_ECONOMICS",
            input.OriginalHxc1SourceSha256,input.OriginalOei1SourceSha256,
            Protocol=NativeFcp1FinancedSelection.Version,
            FrozenOriginalScp1ModelVersion=NativeScp1EconomicScorer.Version,
            FrozenOriginalSCP1ReportSha256=frozenModelFileHash,
            Model=snapshot,
            SourceClass="REUSED_VERIFIED_ORIGINAL_CXL1_M5_HXC1_M1_TO_M5_WITH_ORIGINAL_OEI1_QUOTES",
            input.SourceGeometry,input.OriginalCxl1CipherHashes,
            FinancialDecisionWindow="ONLY_EVALUATION_2026_10_19_THROUGH_2026_11_09_POST_CAL",
            NoInSampleFinancialDecisionLeakage=true,
            PriceOnlyTrainingLabelCount=frozenTrainingCount,
            CompleteTrainingLabels=frozenCompleteCount,
            PriceOnlyTrainingSourceHash=frozenTrainingHash,
            Diagnostics=diag,
            ModelSelectionUsedOnlyCalibration=true,
            FrozenOriginalModelReusedWithoutRefit=true,
            OriginalScp1A1ExecutionReplayed=false,
            Comparators=names,
            FirstAdmissionOrder="SYMBOL_FAMILY_SIDE_FINANCE_BEFORE_FIRST",
            LearnedScoreEvidence="FAILED_PRIOR_CALIBRATION_USED_ONLY_AS_EXPLORATORY_NEGATIVE_CONTROL",
            FullyIndependentConfirmation=false,
            AllPhasesHistoricallyGloballyExposed=true,
            SameClockGenuineQuoteFinanceFrames=genuineFinanceFrames,
            OriginalQuoteClocks=times.Length,
            TrainingEligibleSourceSymbols=new[]{"BTCUSD","ETHUSD"},
            LateOnlyCrossMarketSourceSymbols=new[]{"EURUSD","US500","XAUUSD","NAS100"},
            FundingEligibleSymbols=new[]{"EURUSD","US500","ETHUSD"},
            SourceCounts=input.Streams.ToDictionary(s=>s.Symbol,
                s=>new {AuthenticM5=s.M5.Length,AuthenticM15=s.M15.Length}),
            FundingIneligibleClassesWithoutMatchingNativeM5M15=
                new[]{"BTCUSD","XAUUSD","NAS100","SpotBrent"},
            ObservedCandidateFamilies=familyProposals,
            MissingFinancialOrBarEvidence=rejected,
            ConditionalPolicies=result,LedgerReceipts=chains,
            IncrementalClosedModelNetVsFirstEur=engines.ToDictionary(x=>x.Key,
                x=>x.Value.ModelSummary.ClosedNetEur-
                    engines["FCP1_FIRST"].ModelSummary.ClosedNetEur),
            IncrementalCompletedTripsVsFirst=engines.ToDictionary(x=>x.Key,
                x=>x.Value.CompleteModelTrips.Length-
                    engines["FCP1_FIRST"].CompleteModelTrips.Length),
            ScoreConditionedConditionalEurPerformance=scoreConditionalBins,
            OrdersSubmitted=0,CloudActivated=false,
            BrokerNetCertified=false,
            HistoricFundingCertified=false,
            ContinuousFloatingDrawdownCertified=false,
            Hard21Certified=false,Independent12Months=false,
            ResultStatus="FCP1_GLOBALLY_EXPOSED_FINANCED_FIRST_SCORE_NEGATIVE_CONTROL_NO_BROKER_CERTIFICATE"
        };
        File.WriteAllText(outputFile,JsonSerializer.Serialize(original,Opt)+"\n");
        return 0;
    }
}
