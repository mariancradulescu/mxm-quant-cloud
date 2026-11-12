using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static class NativePacificYenExperiment
{
    private const long M5=300000L;
    internal static int Run(string input,string output)
    {
        try
        {
            byte[] original=File.ReadAllBytes(input);
            var source=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(
                original,new JsonSerializerOptions {
                    NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
                })??throw new ArgumentException("JYP1_ORIGINAL_INPUT_MISSING");
            var universe=new[]{"AUDJPY","EURUSD","NZDJPY","USDJPY"};
            if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_JYP1_PACIFIC_2026" ||
               !source.Bars.Select(b=>b.Symbol).OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(universe) ||
               source.Marks.Any(q=>!universe.Contains(q.Symbol,StringComparer.Ordinal)))
                throw new ArgumentException("JYP1_ORIGINAL_BROKER_SOURCE_UNIVERSE");
            var tape=NativeOriginalOpenApiProductAdapter.Convert(source);
            tape=tape with {Quotes=tape.Quotes.Select(x=>x.Quote.Symbol switch
            {
                "NZDJPY"=>x with {HoldingMinutes=150,ExitPolicy=NativeCausalExitResearch.PredictionInvalidation},
                "AUDJPY"=>x with {HoldingMinutes=135,ExitPolicy=NativeCausalExitResearch.Chandelier},
                _=>x
            }).ToArray()};

            LedgerClosedFragment[] jointClosed=Array.Empty<LedgerClosedFragment>();
            LedgerClosedFragment[] fixedClosed=Array.Empty<LedgerClosedFragment>();
            NativeHistoricalMarketReceipt Run(string mode,
                Action<NativeFundedLedger>? observe=null)
            {
                var inputTape=mode=="FIXED"?tape with {Quotes=tape.Quotes.Select(x=>
                    x with {HoldingMinutes=90,ExitPolicy=NativeCausalExitResearch.FrozenFixed}
                    ).ToArray()}:tape;
                return NativeHistoricalProductReplay.Evaluate(inputTape,true,
                    "JYP1_"+mode,observe);
            }
            var joint=Run("JOINT",ledger=>jointClosed=ledger.ClosedFragments());
            var nz=Run("NZD");
            var aud=Run("AUD");
            var longOnly=Run("LONG");
            var shortOnly=Run("SHORT");
            var fixed90=Run("FIXED",ledger=>fixedClosed=ledger.ClosedFragments());
            var cash=Run("CASH");

            object Book(NativeHistoricalMarketReceipt x)=>new {
                x.CompletedModelRoundTrips,x.ModelIntentCount,x.ModelRejectedCount,
                x.ModelClosedGrossEur,x.ModelClosedCentralNetEur,x.ModelClosedAdverseNetEur,
                PercentCentralOfCapital=x.ModelClosedCentralNetEur/3m,
                PercentAdverseOfCapital=x.ModelClosedAdverseNetEur/3m,
                x.MaximumObservedMarginEur,x.ModelTripsPerObservedIsoWeek,
                x.ExitReasonCounts,x.RejectionReasons,x.RejectionCategories,
                x.SignalsByMechanism,x.ClosedNetByMechanismEur,
                x.OpenModelPositions,x.PendingModelRequests,x.AdverseFailureKind,
                x.UnfinancedModelOpenCancellations
            };
            var completed=jointClosed.Where(x=>x.CompletesRoundTrip).ToArray();
            var duration=completed.Select(x=>(x.ClosedAt-x.OpenedAt)/60000m)
                .Order().ToArray();
            var clocks=tape.Quotes.Select(x=>(x.At,x.Quote.Symbol)).ToHashSet();
            (long expected,long missing) Coverage(LedgerClosedFragment[] records)
            {
                long required=0,absent=0;
                foreach(var fill in records.Where(x=>x.CompletesRoundTrip))
                {
                    long from=((fill.OpenedAt-1500L)/M5)*M5+1500L;
                    long until=((fill.ClosedAt-1500L)/M5)*M5+1500L;
                    for(long at=from;at<=until;at+=M5)
                    {
                        required++;
                        if(!clocks.Contains((at,fill.Symbol)))absent++;
                    }
                }
                return(required,absent);
            }
            var cov=Coverage(jointClosed);
            var fixedCov=Coverage(fixedClosed);
            decimal peak=300m,dd=0m,marginClockMinutes=0m;
            int unknown=0,occupied=0;
            foreach(var mark in joint.SampledEquity)
            {
                if(mark.AdverseEquityEur is decimal equity)
                {
                    peak=Math.Max(peak,equity);
                    dd=Math.Max(dd,(peak-equity)/peak);
                }
                else unknown++;
                if(mark.UsedMarginEur is decimal margin && margin>0)
                {
                    occupied++;
                    marginClockMinutes+=margin*5m;
                }
            }
            object? Duration() => duration.Length==0?null:new {
                MeanMinutes=duration.Average(),
                MedianMinutes=duration[(duration.Length-1)/2],
                P90Minutes=duration[(duration.Length-1)*9/10],
                MinimumMinutes=duration[0],MaximumMinutes=duration[^1]
            };
            if(fixed90.ExitReasonCounts is {Count:>0} &&
               fixed90.ExitReasonCounts.Keys.Any(x=>x!="FROZEN_LEGACY_TIME"))
                throw new ArgumentException("JYP1_FIXED_90_IS_NOT_FIXED");

            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="JYP1",
                SourceSha256=Convert.ToHexString(SHA256.HashData(original)).ToLowerInvariant(),
                OriginalInputLabel=source.SourceLabel,
                OriginalBarCounts=source.Bars.ToDictionary(x=>x.Symbol,x=>x.M5.Length),
                OriginalMarkCounts=source.Marks.GroupBy(x=>x.Symbol).ToDictionary(x=>x.Key,x=>x.Count()),
                Receipt=joint with {SampledEquity=joint.SampledEquity.Where(x=>
                    x.UsedMarginEur>0m || x.AdverseUsedMarginEur>0m ||
                    !x.CentralEquityEur.HasValue || !x.AdverseEquityEur.HasValue).ToArray()},
                NzOnly=Book(nz),AudOnly=Book(aud),
                FundedLong=Book(longOnly),FundedShort=Book(shortOnly),
                TrueFixed90=Book(fixed90),Cash=Book(cash),
                NzMarginalAdverseEur=joint.ModelClosedAdverseNetEur-aud.ModelClosedAdverseNetEur,
                AudMarginalAdverseEur=joint.ModelClosedAdverseNetEur-nz.ModelClosedAdverseNetEur,
                AdaptiveVsFixedAdverseEur=joint.ModelClosedAdverseNetEur-fixed90.ModelClosedAdverseNetEur,
                DurationStatistics=Duration(),
                JointSampledAdverseDrawdown=dd,
                JointMarginEurFiveMinuteClockIntegral=marginClockMinutes,
                JointOccupiedFiveMinuteClocks=occupied,
                JointUnknownAdverseEquityClockCount=unknown,
                JointRequiredHeldQuoteClocks=cov.expected,
                JointMissingHeldQuoteClocks=cov.missing,
                FixedRequiredHeldQuoteClocks=fixedCov.expected,
                FixedMissingHeldQuoteClocks=fixedCov.missing,
                JointFees=new {
                    CommissionsEur=completed.Sum(x=>x.CommissionsEur),
                    FinancingEur=completed.Sum(x=>x.FinancingEur),
                    SpreadEur=completed.All(x=>x.SpreadEur.HasValue)
                        ?completed.Sum(x=>x.SpreadEur!.Value):(decimal?)null,
                    SlippageEur=completed.All(x=>x.SlippageEur.HasValue)
                        ?completed.Sum(x=>x.SlippageEur!.Value):(decimal?)null
                },
                SharedInitialModelCapitalEur=300m,
                IndependentlyConfirmed=false,
                HistoricalBrokerFillsCertified=false,
                CloudActivated=false,OrdersSubmitted=0,
                ContinuousDrawdownCertified=false,
                Verdict="EXPOSED_DEVELOPMENT_ONLY_NO_PORTFOLIO_PROMOTION"
            }));
            return 0;
        }
        catch(Exception e)
        {
            Console.Error.WriteLine("JYP1_NATIVE_REPLAY_REJECTED:"+e.GetType().Name+":"+e.Message);
            return 67;
        }
    }
}
