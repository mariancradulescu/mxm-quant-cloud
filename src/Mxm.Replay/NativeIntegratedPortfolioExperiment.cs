using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static class NativeIntegratedPortfolioExperiment
{
    internal static int Run(string input,string output)
    {
        try
        {
            var bytes=File.ReadAllBytes(input);
            var source=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes,new JsonSerializerOptions {
                NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
            }) ?? throw new ArgumentException("IPC2_SOURCE_EMPTY");
            if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_IPC2")throw new ArgumentException("IPC2_SOURCE_LABEL");
            var tape=NativeOriginalOpenApiProductAdapter.Convert(source);
            tape=tape with {Quotes=tape.Quotes.Where(q=>NativeIntegratedResearch.Family(q.Quote.Symbol)!=null)
                .Select(q=>q with {HoldingMinutes=NativeIntegratedResearch.Holding(q.Quote.Symbol),
                    ExitPolicy=NativeIntegratedResearch.Exit(q.Quote.Symbol)}).ToArray()};
            var boundary=NativeIntegratedResearch.Boundary;
            var testTape=tape with {Quotes=tape.Quotes.Where(q=>q.At>=boundary).ToArray()};
            static string Week(long at)
            {
                var day=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                return System.Globalization.ISOWeek.GetYear(day)+"-W"+
                    System.Globalization.ISOWeek.GetWeekOfYear(day).ToString("00");
            }
            (NativeHistoricalMarketReceipt Result,NativeEntryCalibrationReport? Diagnostics,string Trace,
                int PeakOpen,Dictionary<string,int> Reserved)
                Replay(string mode,NativeIntegratedSnapshot? snapshot=null)
            {
                NativeEntryCalibrationReport? diagnostics=null;
                LedgerClosedFragment[] closed=Array.Empty<LedgerClosedFragment>();
                var reservations=new Dictionary<string,int>();
                using var trace=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
                var result=NativeHistoricalProductReplay.Evaluate(snapshot is null?tape:testTape,
                    UnqualifiedShadowMode:false,ResearchMode:"IPC2_"+mode,IntegratedSnapshot:snapshot,
                    ObserveFinalLedger:ledger=>closed=ledger.ClosedFragments(),
                    ObserveCalibration:value=>diagnostics=value,ObserveSignal:signal=>{
                        if(signal.At<boundary)return;
                        trace.AppendData(JsonSerializer.SerializeToUtf8Bytes(signal));
                        if(signal.Status=="SHADOW_MODEL_INTENT_ALLOCATED_NOT_TRADING")
                        {
                            string week=Week(signal.At);
                            reservations[week]=reservations.GetValueOrDefault(week)+1;
                        }
                    });
                var peakOpen=result.SampledEquity.Where(q=>q.At>=boundary)
                    .Select(q=>closed.Count(c=>c.OpenedAt<=q.At && c.ClosedAt>q.At)).DefaultIfEmpty().Max();
                Console.WriteLine("IPC2 completed policy "+mode);
                return (result,diagnostics,Convert.ToHexString(trace.GetHashAndReset()),peakOpen,reservations);
            }

            var joint=Replay("JOINT");
            var model=NativeIntegratedSnapshot.Open(joint.Diagnostics?.FrozenModel??
                throw new ArgumentException("IPC2_FROZEN_MODEL_UNAVAILABLE"));
            var restarted=Replay("JOINT",model);
            static object Outcome(NativeHistoricalMarketReceipt r)=>new {
                r.ModelIntentCount,r.CompletedModelRoundTrips,r.ModelClosedGrossEur,
                r.ModelClosedCentralNetEur,r.ModelClosedAdverseNetEur,r.RejectionReasons,
                r.MaximumObservedMarginEur,r.OpenModelPositions,r.PendingModelRequests,r.AdverseFailureKind
            };
            if(joint.Trace!=restarted.Trace ||
                JsonSerializer.Serialize(Outcome(joint.Result))!=JsonSerializer.Serialize(Outcome(restarted.Result)))
                throw new ArgumentException("IPC2_FROZEN_MODEL_RECONSTRUCTION_MISMATCH");

            var policies=new Dictionary<string,object>();
            foreach(var mode in new[]{"JOINT","FX","METAL","LONG","SHORT","CASH"})
            {
                var replay=mode=="JOINT"?joint:Replay(mode);
                var r=replay.Result;
                decimal peak=300m,adverseDd=0m;
                var marks=r.SampledEquity.Where(q=>q.At>=boundary).ToArray();
                foreach(var m in marks)
                    if(m.AdverseEquityEur is decimal eq)
                    {
                        peak=Math.Max(peak,eq);
                        adverseDd=Math.Max(adverseDd,(peak-eq)/peak);
                    }
                policies.Add(mode,new {
                    r.ForecastsGenerated,r.ModelIntentCount,r.CompletedModelRoundTrips,r.ModelClosedGrossEur,
                    r.ModelClosedCentralNetEur,r.ModelClosedAdverseNetEur,r.RejectionReasons,
                    r.ClosedNetByMechanismEur,r.MaximumObservedMarginEur,r.MaximumSampledCentralDrawdown,
                    r.OpenModelPositions,r.PendingModelRequests,r.AdverseFailureKind,
                    MissingCentralMarks=marks.Count(q=>q.CentralEquityEur is null),
                    MissingAdverseMarks=marks.Count(q=>q.AdverseEquityEur is null),
                    MaximumSampledAdverseDrawdown=adverseDd,PeakConcurrentClosedPositions=replay.PeakOpen,
                    ReservationsByWeek=replay.Reserved,
                    Weeks=r.ModelTripsPerObservedIsoWeek.Where(q=>string.CompareOrdinal(q.Key,"2026-W34")>=0)
                        .ToDictionary(q=>q.Key,q=>q.Value),
                    Diagnostics=mode is "JOINT" or "FX" or "METAL"?replay.Diagnostics:null
                });
            }
            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="IPC2",SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                EvaluationBoundaryUtcMs=boundary,NominalSlotsPerWeek=80,
                ProbabilityTarget="POSITIVE_ADVERSE_NET",Policies=policies,Receipt=policies["JOINT"],
                Reconstruction=new {SameSignalTrace=true,SameFundedResult=true,SignalTraceSha256=joint.Trace},
                IndependentConfirmation=false,CloudActivated=false,OrdersSubmitted=0
            }));
            return 0;
        }
        catch(Exception e)
        {
            var reason=e is ArgumentException && System.Text.RegularExpressions.Regex.IsMatch(
                e.Message,@"^[A-Z0-9_]{3,100}$")?e.Message:e.GetType().Name;
            Console.Error.WriteLine("IPC2_NATIVE_REPLAY_REJECTED:"+reason);
            return 67;
        }
    }
}
