using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static class NativeChronologicalFundingExperiment
{
    private const long Minute = 60000L;
    private static readonly long Boundary =
        new DateTimeOffset(2026, 3, 2, 0, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();

    internal static int Run(string input, string output)
    {
        try
        {
            var bytes = File.ReadAllBytes(input);
            var source = JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes, new JsonSerializerOptions
            {
                NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
            }) ?? throw new ArgumentException("WFG1_EMPTY_SOURCE");
            var universe = new[] { "AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "SpotBrent", "XAUUSD" };
            if (source.SourceLabel != "ORIGINAL_PEPPERSTONE_FCE1_FEB_MAR_2026" ||
                !source.Bars.Select(b => b.Symbol).OrderBy(x => x, StringComparer.Ordinal).SequenceEqual(universe) ||
                source.Marks.Any(x => !universe.Contains(x.Symbol, StringComparer.Ordinal)))
                throw new ArgumentException("WFG1_SOURCE_BINDING");

            var adapted = NativeOriginalOpenApiProductAdapter.Convert(source);
            var tape = adapted with
            {
                Quotes = adapted.Quotes.Select(mark => mark.Quote.Symbol switch
                {
                    "AUDUSD" or "GBPUSD" or "NZDUSD" => mark with
                    {
                        HoldingMinutes = 45, ExitPolicy = NativeCausalExitResearch.EquilibriumReversion
                    },
                    "SpotBrent" or "XAUUSD" => mark with
                    {
                        HoldingMinutes = 75, ExitPolicy = NativeCausalExitResearch.Chandelier
                    },
                    _ => mark
                }).ToArray()
            };
            var training = tape with
            {
                Quotes = tape.Quotes.Where(x => x.At < Boundary).ToArray(),
                Bars = tape.Bars.Select(x => x with
                {
                    M5 = x.M5.Where(bar => bar.CloseAt < Boundary).ToArray()
                }).ToArray()
            };
            var evaluation = tape with { Quotes = tape.Quotes.Where(x => x.At >= Boundary).ToArray() };

            var fxTraining = EvaluateFamily(training, "FX");
            var commodityTraining = EvaluateFamily(training, "COMMODITY");
            bool fx = Qualifies(fxTraining), commodity = Qualifies(commodityTraining);
            string gate = (fx, commodity) switch
            {
                (true, true) => "JOINT", (true, false) => "FX",
                (false, true) => "COMMODITY", _ => "CASH"
            };

            var ungatedClosed = Array.Empty<LedgerClosedFragment>();
            var ungated = Evaluate(evaluation, "JOINT", ledger => ungatedClosed = ledger.ClosedFragments());
            var fxOnly = Evaluate(evaluation, "FX");
            var commodityOnly = Evaluate(evaluation, "COMMODITY");
            var longOnly = Evaluate(evaluation, "LONG");
            var shortOnly = Evaluate(evaluation, "SHORT");
            var closed = Array.Empty<LedgerClosedFragment>();
            var gated = Evaluate(evaluation, gate, ledger => closed = ledger.ClosedFragments());
            var gatedLong = gate switch
            {
                "JOINT" => longOnly, "CASH" => gated, _ => Evaluate(evaluation, gate + "_LONG")
            };
            var gatedShort = gate switch
            {
                "JOINT" => shortOnly, "CASH" => gated, _ => Evaluate(evaluation, gate + "_SHORT")
            };

            var marks = evaluation.Quotes.Select(x => (x.At, x.Quote.Symbol)).ToHashSet();
            var gatedCoverage = HeldCoverage(gated, closed, marks);
            var ungatedCoverage = HeldCoverage(ungated, ungatedClosed, marks);
            File.WriteAllText(output, JsonSerializer.Serialize(new
            {
                Study = "WFG1", SourceSha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                EvaluationStartUtcMs = Boundary, LockedSelection = gate,
                Selection = new { Fx = TrainingSummary(fxTraining, fx),
                                  Commodity = TrainingSummary(commodityTraining, commodity) },
                Receipt = gated with { SampledEquity = gated.SampledEquity.Where(x =>
                    x.UsedMarginEur > 0m || x.AdverseUsedMarginEur > 0m ||
                    !x.CentralEquityEur.HasValue || !x.AdverseEquityEur.HasValue).ToArray() },
                GatedLong = Summary(gatedLong), GatedShort = Summary(gatedShort),
                Ungated = Summary(ungated), FundedLong = Summary(longOnly), FundedShort = Summary(shortOnly),
                OnlyFx = Summary(fxOnly), OnlyCommodity = Summary(commodityOnly),
                GateMarginalAdverseEur = gated.ModelClosedAdverseNetEur - ungated.ModelClosedAdverseNetEur,
                FxMarginalAdverseEur = ungated.ModelClosedAdverseNetEur - commodityOnly.ModelClosedAdverseNetEur,
                CommodityMarginalAdverseEur = ungated.ModelClosedAdverseNetEur - fxOnly.ModelClosedAdverseNetEur,
                GatedHeldCoverage = gatedCoverage, UngatedHeldCoverage = ungatedCoverage,
                GatedRisk = Summary(gated),
                EvaluationMarkObservations = evaluation.Quotes.Length,
                Qualification = "EXPOSED_CHRONOLOGICAL_DEVELOPMENT_ONLY"
            }));
            return 0;
        }
        catch (Exception ex)
        {
            var reason = System.Text.RegularExpressions.Regex.IsMatch(ex.Message, @"^[A-Z][A-Z0-9_]{2,100}$")
                ? ex.Message : ex.GetType().Name;
            Console.Error.WriteLine("WFG1_NATIVE_REPLAY_REJECTED:" + reason);
            return 67;
        }
    }

    private static NativeHistoricalMarketReceipt Evaluate(NativeHistoricalMarketTape tape,
        string mode, Action<NativeFundedLedger>? observe = null) =>
        NativeHistoricalProductReplay.Evaluate(tape, UnqualifiedShadowMode: true,
            ResearchMode: "WFG1_" + mode, ObserveFinalLedger: observe);

    private static (NativeHistoricalMarketReceipt Model, NativeHistoricalMarketReceipt Long,
        NativeHistoricalMarketReceipt Short) EvaluateFamily(NativeHistoricalMarketTape tape, string family) =>
        (Evaluate(tape, family), Evaluate(tape, family + "_LONG"), Evaluate(tape, family + "_SHORT"));

    private static bool Settled(NativeHistoricalMarketReceipt r) =>
        r.CompletedModelRoundTrips > 0 && r.OpenModelPositions == 0 && r.PendingModelRequests == 0 &&
        r.ModelClosedAdverseNetEur.HasValue && string.IsNullOrEmpty(r.AdverseFailureKind);

    private static bool Qualifies((NativeHistoricalMarketReceipt Model, NativeHistoricalMarketReceipt Long,
        NativeHistoricalMarketReceipt Short) result) =>
        Settled(result.Model) && Settled(result.Long) && Settled(result.Short) &&
        result.Model.CompletedModelRoundTrips >= 5 &&
        result.Model.ModelTripsPerObservedIsoWeek.Count(w => w.Value > 0) >= 2 &&
        result.Model.ModelClosedAdverseNetEur > 0m &&
        result.Model.ModelClosedAdverseNetEur > result.Long.ModelClosedAdverseNetEur &&
        result.Model.ModelClosedAdverseNetEur > result.Short.ModelClosedAdverseNetEur;

    private static object TrainingSummary((NativeHistoricalMarketReceipt Model,
        NativeHistoricalMarketReceipt Long, NativeHistoricalMarketReceipt Short) result, bool qualified) =>
        new { Qualified = qualified, Model = Summary(result.Model),
              FundedLong = Summary(result.Long), FundedShort = Summary(result.Short) };

    private static object HeldCoverage(NativeHistoricalMarketReceipt receipt,
        LedgerClosedFragment[] closed, HashSet<(long, string)> marks)
    {
        int required = 0, missing = 0;
        foreach (var fill in closed)
            for (long at = fill.OpenedAt; at <= fill.ClosedAt; at += Minute)
            {
                required++;
                if (!marks.Contains((at, fill.Symbol))) missing++;
            }
        return new
        {
            RequiredClosedTradeHeldMinuteMarks = required, MissingClosedTradeHeldMinuteMarks = missing,
            PeakConcurrentClosedTradePositions = receipt.SampledEquity.Max(mark => closed.Count(
                fill => fill.OpenedAt <= mark.At && mark.At < fill.ClosedAt))
        };
    }

    private static object Summary(NativeHistoricalMarketReceipt r)
    {
        decimal peak = 300m, drawdown = 0m;
        foreach (var mark in r.SampledEquity)
        {
            if (mark.AdverseEquityEur is not decimal value) continue;
            peak = Math.Max(peak, value);
            drawdown = Math.Max(drawdown, (peak - value) / peak);
        }
        return new
        {
            r.ForecastsGenerated, r.CompletedModelRoundTrips, r.ModelClosedGrossEur,
            r.ModelClosedCentralNetEur, r.ModelClosedAdverseNetEur, r.ModelTripsPerObservedIsoWeek,
            r.MaximumObservedMarginEur, r.OpenModelPositions, r.PendingModelRequests, r.AdverseFailureKind,
            r.SignalsByMechanism, r.DistinctHistoricalStressDecisionsWithExposure,
            SampledAdverseDrawdown = drawdown,
            MissingAdverseMarks = r.SampledEquity.Count(x => !x.AdverseEquityEur.HasValue)
        };
    }
}
