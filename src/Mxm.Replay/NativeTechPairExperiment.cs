using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

// Research-only ETP1 original-account historical receiver. Nothing is traded.
internal static class NativeTechPairExperiment
{
    internal static int Run(string input,string output)
    {
        try
        {
            byte[] raw=File.ReadAllBytes(input);
            var source=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(
                raw,new JsonSerializerOptions {
                    NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
                })??throw new ArgumentException("ETP1_EMPTY_ORIGINAL_SOURCE");
            var expected=new[]{"AAPL.US-24","EURUSD","GOOG.US-24"};
            if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_ETP1_TECH_2026" ||
               !source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(expected) ||
               source.Marks.Any(x=>!expected.Contains(x.Symbol,StringComparer.Ordinal)))
                throw new ArgumentException("ETP1_ORIGINAL_SOURCE_UNIVERSE_INVALID");
            var adapted=NativeOriginalOpenApiProductAdapter.Convert(source);
            var tape=adapted with {Quotes=adapted.Quotes.Select(x=>x.Quote.Symbol switch {
                "AAPL.US-24"=>x with { HoldingMinutes=90,ExitPolicy=NativeCausalExitResearch.Chandelier },
                "GOOG.US-24"=>x with { HoldingMinutes=105,ExitPolicy=NativeCausalExitResearch.PredictionInvalidation },
                _=>x
            }).ToArray()};
            LedgerClosedFragment[] closed=Array.Empty<LedgerClosedFragment>();
            NativeHistoricalMarketReceipt Run(string mode,Action<NativeFundedLedger>? observe=null)=>
                NativeHistoricalProductReplay.Evaluate(tape,true,"ETP1_"+mode,observe);
            var joint=Run("JOINT",ledger=>closed=ledger.ClosedFragments());
            var leader=Run("LEADER");
            var follower=Run("FOLLOWER");
            var longOnly=Run("LONG");
            var shortOnly=Run("SHORT");
            var fixed90=Run("FIXED");
            var cash=Run("CASH");
            object Summary(NativeHistoricalMarketReceipt r)=>new {
                r.CompletedModelRoundTrips,r.ModelIntentCount,r.ModelRejectedCount,
                r.ModelClosedCentralNetEur,r.ModelClosedAdverseNetEur,
                CentralReturnOnEUR300=r.ModelClosedCentralNetEur/300m,
                AdverseReturnOnEUR300=r.ModelClosedAdverseNetEur/300m,
                r.MaximumObservedMarginEur,r.ModelTripsPerObservedIsoWeek,
                r.ExitReasonCounts,r.RejectionReasons,r.SignalsByMechanism,
                r.AdverseFailureKind,r.OpenModelPositions,r.PendingModelRequests,
                r.ClosedNetByMechanismEur,r.UnfinancedModelOpenCancellations
            };
            decimal peak=300m,drawdown=0m,marginMinutes=0m;
            long observed=0,unknown=0;
            foreach(var item in joint.SampledEquity)
            {
                if(item.AdverseEquityEur is decimal v)
                {
                    peak=Math.Max(peak,v);
                    drawdown=Math.Max(drawdown,(peak-v)/peak);
                }
                else unknown++;
                if(item.UsedMarginEur is decimal m)
                {
                    observed++;
                    marginMinutes+=m*5m;
                }
            }
            var booked=closed.Where(c=>c.CompletesRoundTrip).ToArray();
            var durations=booked.Select(c=>(c.ClosedAt-c.OpenedAt)/60000m).Order().ToArray();
            var quoteClocks=tape.Quotes.Select(q=>(q.At,q.Quote.Symbol)).ToHashSet();
            long heldExpected=0,heldMissing=0;
            foreach(var trade in booked)
                for(long at=trade.OpenedAt;at<=trade.ClosedAt;at+=300000L)
                {
                    heldExpected++;
                    if(!quoteClocks.Contains((at,trade.Symbol)))heldMissing++;
                }
            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="ETP1",SourceSha256=Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant(),
                OriginalInputLabel=source.SourceLabel,
                OriginalInputBars=source.Bars.Sum(x=>x.M5.Length),
                OriginalInputMarks=source.Marks.Length,
                Joint=Summary(joint),LeaderOnly=Summary(leader),FollowerOnly=Summary(follower),
                Long=Summary(longOnly),Short=Summary(shortOnly),Fixed90=Summary(fixed90),
                Cash=Summary(cash),
                MarginalLeaderAdverseEur=joint.ModelClosedAdverseNetEur-follower.ModelClosedAdverseNetEur,
                MarginalFollowerAdverseEur=joint.ModelClosedAdverseNetEur-leader.ModelClosedAdverseNetEur,
                AdaptiveVsFixedAdverseEur=joint.ModelClosedAdverseNetEur-fixed90.ModelClosedAdverseNetEur,
                SampledAdverseDrawdown=drawdown,
                EquityMarksUnknown=unknown,
                ObservedMarginEurMinutes=marginMinutes,ObservedMarginClockMarks=observed,
                ClosedRoundtripDurationMinutes=durations,
                HeldFiveMinuteExpectedMarks=heldExpected,HeldFiveMinuteUnknownMarks=heldMissing,
                ExitReasonCounts=joint.ExitReasonCounts,
                ClosedCostComponents=new {
                    SpreadEur=booked.All(x=>x.SpreadEur.HasValue)
                        ?booked.Sum(x=>x.SpreadEur!.Value):(decimal?)null,
                    SlippageEur=booked.All(x=>x.SlippageEur.HasValue)
                        ?booked.Sum(x=>x.SlippageEur!.Value):(decimal?)null,
                    CommissionsEur=booked.Sum(x=>x.CommissionsEur),
                    FinancingEur=booked.Sum(x=>x.FinancingEur)
                },
                BrokerOrdersSubmitted=0,CloudActivated=false,IndependentConfirmation=false,
                HistoricalFillsCertified=false,ContinuousDD30Certified=false,TradingQualified=false
            }));
            return 0;
        }
        catch(Exception ex)
        {
            Console.Error.WriteLine("ETP1_REJECTED:"+ex.GetType().Name+":"+ex.Message);
            return 67;
        }
    }
}
