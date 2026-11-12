using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static class NativeCalibratedOutcomeExperiment
{
    internal static int Run(string input,string output)
    {
        try
        {
            var bytes=File.ReadAllBytes(input);
            var source=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes,new JsonSerializerOptions {
                NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
            }) ?? throw new ArgumentException("CAL1_SOURCE_EMPTY");
            if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_FCE1_FEB_MAR_2026")
                throw new ArgumentException("CAL1_SOURCE_LABEL");
            var tape=NativeOriginalOpenApiProductAdapter.Convert(source);
            tape=tape with {
                Quotes=tape.Quotes.Where(q=>q.At%300000L<60000L &&
                    NativeEntryOutcomeCalibration.Family(q.Quote.Symbol)!=null).Select(q=>q with {
                    HoldingMinutes=NativeEntryOutcomeCalibration.HoldingMinutes,
                    ExitPolicy=NativeEntryOutcomeCalibration.ExitPolicy
                }).ToArray()
            };
            var receipts=new Dictionary<string,object>(StringComparer.Ordinal);
            foreach(var mode in new[]{"JOINT","FX","COMMODITY","LONG","SHORT","CASH"})
            {
                NativeEntryCalibrationReport? diagnostics=null;
                var result=NativeHistoricalProductReplay.Evaluate(tape,
                    UnqualifiedShadowMode:false,ResearchMode:"CAL1_"+mode,
                    ObserveCalibration:r=>diagnostics=r);
                var weeks=result.ModelTripsPerObservedIsoWeek.Where(w=>
                    StringComparer.Ordinal.Compare(w.Key,"2026-W10")>=0).ToDictionary(w=>w.Key,w=>w.Value);
                decimal peak=300m,drawdown=0m;
                var evaluation=result.SampledEquity.Where(r=>r.At>=NativeEntryOutcomeCalibration.DevelopmentBoundary).ToArray();
                foreach(var mark in evaluation)
                    if(mark.AdverseEquityEur is decimal equity)
                    {
                        peak=Math.Max(peak,equity);
                        drawdown=Math.Max(drawdown,1m-equity/peak);
                    }
                receipts.Add(mode,new {
                    result.ForecastsGenerated,result.ModelIntentCount,result.ModelRejectedCount,
                    result.CompletedModelRoundTrips,result.ModelClosedGrossEur,
                    result.ModelClosedCentralNetEur,result.ModelClosedAdverseNetEur,
                    result.MaximumObservedMarginEur,result.MaximumSampledCentralDrawdown,
                    result.OpenModelPositions,result.PendingModelRequests,
                    result.RejectionReasons,result.ExitReasonCounts,result.SignalsByMechanism,
                    result.ClosedNetByMechanismEur,result.UnfinancedModelOpenCancellations,
                    result.AdverseFailureKind,TripsByEvaluationWeek=weeks,
                    MaximumSampledAdverseDrawdown=drawdown,
                    MissingCentralEquityMarks=evaluation.Count(m=>!m.CentralEquityEur.HasValue),
                    MissingAdverseEquityMarks=evaluation.Count(m=>!m.AdverseEquityEur.HasValue),
                    PredictiveDiagnostics=mode=="JOINT"?diagnostics:null
                });
                Console.WriteLine("CAL1 completed policy "+mode);
            }
            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="CAL1",SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                EvaluationBoundaryUtcMs=NativeEntryOutcomeCalibration.DevelopmentBoundary,
                InitialCapitalEur=300m,EvaluationQuoteMarks=tape.Quotes.Count(q=>
                    q.At>=NativeEntryOutcomeCalibration.DevelopmentBoundary),
                Policies=receipts,IndependentConfirmation=false,CloudActivated=false,OrdersSubmitted=0,
                ContinuousDrawdownCertified=false
            }));
            return 0;
        }
        catch(ArgumentException e)
        {
            Console.Error.WriteLine(System.Text.RegularExpressions.Regex.IsMatch(e.Message,@"^[A-Z0-9_]{3,100}$")
                ?e.Message:"CAL1_SOURCE_OR_INPUT_CONTRACT");
            return 67;
        }
        catch(Exception e)
        {
            Console.Error.WriteLine("CAL1_FAILURE_"+e.GetType().Name);
            return 67;
        }
    }
}
