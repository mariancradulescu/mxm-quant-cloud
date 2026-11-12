using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static class NativeAdaptiveExitExperiment
{
    private const long Minute=60000L;

    internal static int Run(string input,string output)
    {
        const string label="ORIGINAL_PEPPERSTONE_FCE1_FEB_MAR_2026";
        try
        {
            byte[] original=File.ReadAllBytes(input);
            var source=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(
                original,new JsonSerializerOptions {
                    NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
                })??throw new ArgumentException("AEX1_EMPTY_SOURCE");
            var names=new[]{"AUDUSD","EURUSD","GBPUSD","NZDUSD","SpotBrent","XAUUSD"};
            if(source.SourceLabel!=label ||
               !source.Bars.Select(b=>b.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
                   .SequenceEqual(names) ||
               source.Marks.Any(q=>!names.Contains(q.Symbol,StringComparer.Ordinal)))
                throw new ArgumentException("AEX1_SOURCE_IDENTITY_OR_UNIVERSE_INVALID");

            var adapted=NativeOriginalOpenApiProductAdapter.Convert(source);
            var tape=adapted with {
                Quotes=adapted.Quotes.Select(mark=>mark.Quote.Symbol switch {
                    "AUDUSD" or "GBPUSD" or "NZDUSD"=>mark with {
                        HoldingMinutes=135,ExitPolicy=NativeCausalExitResearch.Chandelier },
                    "SpotBrent" or "XAUUSD"=>mark with {
                        HoldingMinutes=120,ExitPolicy=NativeCausalExitResearch.PredictionInvalidation },
                    _=>mark
                }).ToArray()
            };
            LedgerClosedFragment[] jointClosed=Array.Empty<LedgerClosedFragment>();
            LedgerClosedFragment[] fixedClosed=Array.Empty<LedgerClosedFragment>();
            NativeHistoricalMarketReceipt Evaluate(string name,
                Action<NativeFundedLedger>? observe=null)=>
                NativeHistoricalProductReplay.Evaluate(tape,true,"AEX1_"+name,observe);
            var joint=Evaluate("JOINT",ledger=>jointClosed=ledger.ClosedFragments());
            var fx=Evaluate("FX");
            var commodity=Evaluate("COMMODITY");
            var longOnly=Evaluate("LONG");
            var shortOnly=Evaluate("SHORT");
            var fixed90=Evaluate("FIXED",ledger=>fixedClosed=ledger.ClosedFragments());
            var cash=Evaluate("CASH");

            var quoteClocks=tape.Quotes.Select(q=>(q.At,q.Quote.Symbol)).ToHashSet();
            var covered=Held(jointClosed,quoteClocks);
            decimal peak=300m,maxDrawdown=0m;
            long integratedMarginClockMinutes=0;
            decimal observedMarginMinutes=0m;
            foreach(var q in joint.SampledEquity)
            {
                if(q.AdverseEquityEur is decimal equity)
                {
                    peak=Math.Max(peak,equity);
                    maxDrawdown=Math.Max(maxDrawdown,(peak-equity)/peak);
                }
                if(q.UsedMarginEur is decimal margin)
                {
                    observedMarginMinutes+=margin;
                    integratedMarginClockMinutes++;
                }
            }

            var completed=jointClosed.Where(c=>c.CompletesRoundTrip).ToArray();
            var durations=completed.Select(c=>(c.ClosedAt-c.OpenedAt)/60000m).Order().ToArray();
            object? DurationSummary()=>
                durations.Length==0?null:new {
                    P10Minutes=durations[(durations.Length-1)/10],
                    MedianMinutes=durations[(durations.Length-1)/2],
                    P90Minutes=durations[((durations.Length-1)*9)/10],
                    MeanMinutes=durations.Average(),
                    MinimumMinutes=durations[0],MaximumMinutes=durations[^1]
                };
            object Summary(NativeHistoricalMarketReceipt x)=>new {
                x.CompletedModelRoundTrips,x.ModelIntentCount,x.ModelRejectedCount,
                x.ModelClosedCentralNetEur,x.ModelClosedAdverseNetEur,
                ReturnCentralOfInitialEur300=x.ModelClosedCentralNetEur/300m,
                ReturnAdverseOfInitialEur300=x.ModelClosedAdverseNetEur/300m,
                x.MaximumObservedMarginEur,x.ModelTripsPerObservedIsoWeek,
                x.ExitReasonCounts,x.OpenModelPositions,x.PendingModelRequests,
                x.AdverseFailureKind,x.AdverseFailureAt,x.AdverseFailureEventKind,
                x.UnfinancedModelOpenCancellations,
                x.RejectionCategories,x.SignalsByMechanism,x.ClosedNetByMechanismEur
            };
            var heldTrace=joint.SampledEquity.Where(x=>
                x.UsedMarginEur>0m || x.AdverseUsedMarginEur>0m ||
                !x.CentralEquityEur.HasValue || !x.AdverseEquityEur.HasValue).ToArray();
            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="AEX1",SourceSha256=Convert.ToHexString(SHA256.HashData(original)).ToLowerInvariant(),
                OriginalProviderAuthenticity="ORIGINAL_PEPPERSTONE_FCE1_ACCOUNT_SOURCE_REUSED_VERIFIED_CUSTODY",
                OriginalExposure="SIX_WEEKS_EXPOSED_DEVELOPMENT_NO_INDEPENDENT_CONFIRMATION",
                StartingModelCashEur=300m,
                Joint=Summary(joint),OnlyFx=Summary(fx),OnlyCommodity=Summary(commodity),
                FundedLong=Summary(longOnly),FundedShort=Summary(shortOnly),
                SameOpportunityFixed90Control=Summary(fixed90),
                Cash=Summary(cash),
                FxMarginalAdverseEur=joint.ModelClosedAdverseNetEur-commodity.ModelClosedAdverseNetEur,
                CommodityMarginalAdverseEur=joint.ModelClosedAdverseNetEur-fx.ModelClosedAdverseNetEur,
                AdaptiveVsFixed90AdverseEur=joint.ModelClosedAdverseNetEur-fixed90.ModelClosedAdverseNetEur,
                JointDuration=DurationSummary(),
                JointCommissionsEur=completed.Sum(x=>x.CommissionsEur),
                JointSpreadEur=completed.All(x=>x.SpreadEur.HasValue)
                    ?completed.Sum(x=>x.SpreadEur!.Value):null,
                JointSlippageEur=completed.All(x=>x.SlippageEur.HasValue)
                    ?completed.Sum(x=>x.SlippageEur!.Value):null,
                JointFinancingEur=completed.Sum(x=>x.FinancingEur),
                JointObservedMarginEurMinutes=observedMarginMinutes,
                JointObservedMarginMinuteMarks=integratedMarginClockMinutes,
                JointSampledAdverseDrawdown=maxDrawdown,
                JointHeldMinuteCoverage=covered,
                FixedControlHeldMinuteCoverage=Held(fixedClosed,quoteClocks),
                JointHeldOrUnknownEquityTrace=heldTrace,
                HistoricalSourceUnchanged=true,NoBrokerRequests=true,
                OrdersSubmitted=0,CloudActivated=false,IndependentConfirmation=false,
                ContinuousDrawdown30Certified=false,HistoricallyExecutedFillCertificate=false,
                TradingQualified=false
            }));
            return 0;
        }
        catch(Exception ex)
        {
            Console.Error.WriteLine("AEX1_REJECTED:"+ex.GetType().Name+":"+ex.Message);
            return 67;
        }
    }

    private static object Held(LedgerClosedFragment[] closed,
        HashSet<(long At,string Symbol)> marks)
    {
        long required=0,missing=0;
        foreach(var trade in closed.Where(x=>x.CompletesRoundTrip))
            for(long t=trade.OpenedAt;t<=trade.ClosedAt;t+=Minute)
            {
                required++;
                if(!marks.Contains((t,trade.Symbol)))missing++;
            }
        return new {RequiredTradeHeldMinuteMarks=required,
            MissingTradeHeldMinuteMarks=missing,
            BrokerTimeContinuityBeyondOriginalMinuteMarksUnobserved=true};
    }
}
