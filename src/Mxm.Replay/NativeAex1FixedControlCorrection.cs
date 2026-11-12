using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

// Narrow postclosure AEX1 defect correction: reexecute ONLY the false fixed
// 90-minute comparison, never original AEX1 joint or other closed policies.
internal static class NativeAex1FixedControlCorrection
{
    internal static int Run(string input,string output)
    {
        try
        {
            byte[] bytes=File.ReadAllBytes(input);
            var original=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(
                bytes,new JsonSerializerOptions {
                    NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
                })??throw new ArgumentException("AEX1_FIXED_EMPTY_TAPE");
            var expected=new[]{"AUDUSD","EURUSD","GBPUSD","NZDUSD","SpotBrent","XAUUSD"};
            if(original.SourceLabel!="ORIGINAL_PEPPERSTONE_FCE1_FEB_MAR_2026" ||
               !original.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
                   .SequenceEqual(expected) ||
               original.Marks.Any(x=>!expected.Contains(x.Symbol,StringComparer.Ordinal)))
                throw new ArgumentException("AEX1_FIXED_ORIGINAL_UNIVERSE_MISMATCH");
            var adapted=NativeOriginalOpenApiProductAdapter.Convert(original);
            var fixedTape=adapted with {Quotes=adapted.Quotes.Select(x=>x with {
                ExitPolicy=NativeCausalExitResearch.FrozenFixed,
                HoldingMinutes=90
            }).ToArray()};
            LedgerClosedFragment[] closed=Array.Empty<LedgerClosedFragment>();
            var receipt=NativeHistoricalProductReplay.Evaluate(fixedTape,
                true,"AEX1_FIXED",ledger=>closed=ledger.ClosedFragments());
            if(receipt.ExitReasonCounts is {Count:>0} && receipt.ExitReasonCounts.Keys.Any(
                x=>x!= "FROZEN_LEGACY_TIME"))
                throw new InvalidOperationException("AEX1_FIXED_EXIT_ADAPTIVE_REASON_STILL_PRESENT");
            if(receipt.CompletedModelRoundTrips!=closed.Count(x=>x.CompletesRoundTrip))
                throw new InvalidOperationException("AEX1_FIXED_CLOSURE_COUNT_MISMATCH");
            var completed=closed.Where(x=>x.CompletesRoundTrip).ToArray();
            var holding=completed.Select(x=>(x.ClosedAt-x.OpenedAt)/60000m).ToArray();
            decimal peak=300m,dd=0m;
            foreach(var row in receipt.SampledEquity)
                if(row.AdverseEquityEur is decimal equity)
                {
                    peak=Math.Max(peak,equity);
                    dd=Math.Max(dd,(peak-equity)/peak);
                }
            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="AEX1_FIXED_CONTROL_TECHNICAL_CORRECTION",
                SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                OriginalAex1RunId=43240155847L,OriginalAex1ArtifactId=13954129933L,
                ActualFixedPolicy=NativeCausalExitResearch.FrozenFixed,
                ActualHoldMinutes=90,
                CorrectedControl=new {
                    receipt.CompletedModelRoundTrips,receipt.ModelIntentCount,
                    receipt.ModelRejectedCount,receipt.ModelClosedCentralNetEur,
                    receipt.ModelClosedAdverseNetEur,
                    PercentCentralOfInitial300=receipt.ModelClosedCentralNetEur/3m,
                    PercentAdverseOfInitial300=receipt.ModelClosedAdverseNetEur/3m,
                    receipt.ModelTripsPerObservedIsoWeek,
                    receipt.ExitReasonCounts,
                    receipt.MaximumObservedMarginEur,receipt.OpenModelPositions,
                    receipt.PendingModelRequests,receipt.AdverseFailureKind,
                    SampledAdverseDrawdown=dd,HoldMinutesObserved=holding,
                    ClosedCommissionsEur=completed.Sum(x=>x.CommissionsEur),
                    ClosedSlippageEur=completed.All(x=>x.SlippageEur.HasValue)
                        ?completed.Sum(x=>x.SlippageEur!.Value):(decimal?)null
                },
                AllFixedExitReasonsVerified=true,NoIndependentConfirmation=true,
                OriginalJointFinancialsUnchanged=true,NoBrokerRequests=true,
                OrdersSubmitted=0,CloudActivated=false,TradingQualified=false
            }));
            return 0;
        }
        catch(Exception ex)
        {
            Console.Error.WriteLine("AEX1_FIXED_CORRECTION_REJECTED:"+ex.GetType().Name+":"+ex.Message);
            return 67;
        }
    }
}
