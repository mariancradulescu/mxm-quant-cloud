using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static class NativeDiscoveryExperiment
{
    private sealed record BlockEstimate(int Weeks, decimal EffectiveWeeks, decimal MeanBps, decimal AllowanceBps);
    private sealed record SelectionRow(string Cohort, string Decision, BlockEstimate? Own, BlockEstimate? Incremental,
        decimal? Brier, decimal? BaselineBrier);

    internal static int Run(string input, string output)
    {
        byte[] bytes = File.ReadAllBytes(input);
        var source = JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes, new JsonSerializerOptions {
            NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        });
        if (source?.SourceLabel != "ORIGINAL_PEPPERSTONE_IPC2")
            throw new ArgumentException("DCP1_SOURCE_LABEL");

        var tape = NativeOriginalOpenApiProductAdapter.Convert(source);
        tape = tape with {
            Quotes = tape.Quotes.Where(q => NativeConditionalResearch.Family(q.Quote.Symbol) is not null ||
                q.Quote.Symbol == "EURUSD")
                .Select(q => q with { HoldingMinutes = NativeIntegratedResearch.Holding(q.Quote.Symbol),
                    ExitPolicy = NativeDiscoveryResearch.Exit(q.Quote.Symbol) }).ToArray()
        };
        long selectionStart = NativeDiscoveryResearch.SelectionStart;
        long evaluationStart = NativeDiscoveryResearch.EvaluationStart;
        var prior = tape with {
            Bars = tape.Bars.Select(s => s with { M5 = s.M5.Where(b => b.CloseAt < evaluationStart).ToArray() }).ToArray(),
            Quotes = tape.Quotes.Where(q => q.At < evaluationStart).ToArray()
        };
        var future = tape with { Quotes = tape.Quotes.Where(q => q.At >= evaluationStart).ToArray() };

        (NativeHistoricalMarketReceipt Financial, NativeEntryCalibrationReport Labels, string Trace, int PeakOpen)
            Replay(NativeHistoricalMarketTape slice, long boundary, string policy, NativeIntegratedSnapshot? model = null)
        {
            NativeEntryCalibrationReport? report = null;
            LedgerClosedFragment[] closed = Array.Empty<LedgerClosedFragment>();
            using var trace = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            var result = NativeHistoricalProductReplay.Evaluate(slice, UnqualifiedShadowMode: false,
                ResearchMode: "DCP1_" + policy, ObserveFinalLedger: ledger => closed = ledger.ClosedFragments(),
                ObserveCalibration: value => report = value, IntegratedSnapshot: model,
                ObserveSignal: signal => trace.AppendData(JsonSerializer.SerializeToUtf8Bytes(signal)),
                CalibrationBoundary: boundary);
            int peak = result.SampledEquity.Select(q => closed.Count(c => c.OpenedAt <= q.At && c.ClosedAt > q.At))
                .DefaultIfEmpty().Max();
            Console.WriteLine("DCP1 completed " + policy + " " + boundary);
            return (result, report ?? throw new ArgumentException("DCP1_MISSING_LABELS"),
                Convert.ToHexString(trace.GetHashAndReset()), peak);
        }

        var screening = Replay(prior, selectionStart, "CASH").Labels;
        var timeControl = Replay(prior, selectionStart, "FIXED").Labels;
        var trained = NativeIntegratedSnapshot.Open(screening.FrozenModel!);
        var decisions = trained.Conditional!.Keys.OrderBy(x => x, StringComparer.Ordinal)
            .Select(cohort => Select(cohort, screening.DiscoveryWeekly!.GetValueOrDefault(cohort),
                trained.Conditional[cohort])).ToArray();
        var unfiltered = trained with { Boundary = evaluationStart };
        var selected = unfiltered with {
            Conditional = decisions.ToDictionary(x => x.Cohort,
                x => x.Decision == "SHORTLISTED" ? trained.Conditional[x.Cohort] : null)
        };
        string envelope = selected.Seal();
        var joint = Replay(future, evaluationStart, "JOINT", selected);
        var rebuilt = Replay(future, evaluationStart, "JOINT", NativeIntegratedSnapshot.Open(envelope));
        if (joint.Trace != rebuilt.Trace || JsonSerializer.Serialize(joint.Financial) != JsonSerializer.Serialize(rebuilt.Financial))
            throw new ArgumentException("DCP1_RECONSTRUCTION_MISMATCH");
        var portfolios = new Dictionary<string, object>();
        var net = new Dictionary<string, decimal?>();
        NativeEntryCalibrationReport? outerAll = null;
        foreach (string name in new[] { "JOINT", "UNFILTERED", "FX", "METAL", "LONG", "SHORT", "CASH" })
        {
            var run = name == "JOINT" ? joint : name == "UNFILTERED"
                ? Replay(future, evaluationStart, "JOINT", unfiltered)
                : Replay(future, evaluationStart, name, selected);
            if (name == "UNFILTERED") outerAll = run.Labels;
            var r = run.Financial;
            net[name] = r.ModelClosedAdverseNetEur;
            decimal peak = 300m, drawdown = 0m;
            foreach (var mark in r.SampledEquity)
            {
                if (mark.AdverseEquityEur is not decimal equity) continue;
                peak = Math.Max(peak, equity);
                drawdown = Math.Max(drawdown, (peak - equity) / peak);
            }
            portfolios.Add(name, new {
                r.ForecastsGenerated, r.ModelIntentCount, r.CompletedModelRoundTrips, r.ModelClosedGrossEur,
                r.ModelClosedCentralNetEur, r.ModelClosedAdverseNetEur, r.RejectionReasons,
                r.MaximumObservedMarginEur, r.MaximumSampledCentralDrawdown, r.ModelTripsPerObservedIsoWeek,
                r.ClosedNetByMechanismEur, r.ExitReasonCounts, r.UnfinancedModelOpenCancellations, r.OpenModelPositions, r.PendingModelRequests, r.AdverseFailureKind,
                r.DistinctHistoricalStressDecisions, r.DistinctHistoricalStressDecisionsWithExposure,
                MaximumSampledAdverseDrawdown = drawdown,
                MaximumSampledAdverseMarginEur = r.SampledEquity.Max(m => m.AdverseUsedMarginEur), PeakClosedPositionOverlap = run.PeakOpen,
                MissingCentralEquity = r.SampledEquity.Count(m => m.CentralEquityEur is null),
                MissingAdverseEquity = r.SampledEquity.Count(m => m.AdverseEquityEur is null),
                OpportunityFunnel = run.Labels.OpportunityFunnel
            });
        }

        var timeModel = NativeIntegratedSnapshot.Open(timeControl.FrozenModel!) with { Boundary = evaluationStart };
        var outerTime = Replay(future, evaluationStart, "FIXED", timeModel).Labels;
        File.WriteAllText(output, JsonSerializer.Serialize(new {
            Study = "DCP1", SourceSha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            SelectionStartUtcMs = selectionStart, EvaluationStartUtcMs = evaluationStart, NominalSlotsPerWeek = 120,
            MinimumVolumeCapacity = source.Marks.Where(x => x.Symbol != "EURUSD").GroupBy(x => x.Symbol)
                .ToDictionary(x => x.Key, x => new {
                    x.First().Contract.MinimumUnits, MinimumMarginEur = x.Min(m => m.MarginRequirementEur),
                    MaximumMarginEur = x.Max(m => m.MarginRequirementEur)
                }),
            SourceBars = source.Bars.ToDictionary(s => s.Symbol, s => s.M5.Length),
            SourceMarks = source.Marks.GroupBy(x => x.Symbol).ToDictionary(x => x.Key, x => x.Count()),
            SelectionComparisons = decisions, ScreeningAdaptive = screening, ScreeningFixed = timeControl,
            EvaluationAdaptive = outerAll, EvaluationSelected = joint.Labels, EvaluationFixed = outerTime, Portfolios = portfolios,
            AdverseIncrementalEur = net.Where(x => x.Key != "JOINT").ToDictionary(x => x.Key, x => net["JOINT"] - x.Value),
            ModelReconstruction = new { SameDecisionTrace = true, SameFinancialPath = true, TraceSha256 = joint.Trace },
            Verdict = decisions.All(x => x.Decision != "SHORTLISTED") ? "NO_CELL_SHORTLISTED" : "EXPOSED_DEVELOPMENT_NO_ADMISSION",
            CloudActivated = false, IndependentConfirmation = false, OrdersSubmitted = 0
        }));
        return 0;
    }

    private static SelectionRow Select(string cohort, Dictionary<long, NativeConditionalDistribution>? blocks,
        NativeEntryForecast? model)
    {
        if (model is null) return new(cohort, "INSUFFICIENT_TRAINING_WEEKS", null, null, null, null);
        var weeks = blocks?.OrderBy(x => x.Key).Select(x => x.Value).ToArray();
        if (weeks is null || weeks.Length != 4 || weeks.Any(w => w.Pairs < 3 || w.Brier is null || w.TrainingPooledBrier is null))
            return new(cohort, "INSUFFICIENT_SELECTION_WEEK_COVERAGE", null, null, null, null);
        var own = Estimate(weeks.Select(w => w.AdverseBps).ToArray());
        var incremental = Estimate(weeks.Select(w => w.AdverseBps - w.ReverseBps).ToArray());
        decimal brier = weeks.Average(w => w.Brier!.Value), baseline = weeks.Average(w => w.TrainingPooledBrier!.Value);
        string decision = own.EffectiveWeeks < 2.5m || incremental.EffectiveWeeks < 2.5m
            ? "INSUFFICIENT_EFFECTIVE_SELECTION_WEEKS"
            : brier >= baseline ? "NO_INCREMENTAL_PROBABILITY_SKILL"
            : own.MeanBps <= own.AllowanceBps ? "NO_OWN_ADVERSE_EDGE_ABOVE_ALLOWANCE"
            : incremental.MeanBps <= incremental.AllowanceBps ? "NO_DIRECTIONAL_ADVERSE_EDGE_ABOVE_ALLOWANCE"
            : "SHORTLISTED";
        return new(cohort, decision, own, incremental, brier, baseline);
    }

    private static BlockEstimate Estimate(decimal[] sample)
    {
        decimal mean = sample.Average();
        var centered = sample.Select(x => x - mean).ToArray();
        decimal variation = centered.Sum(x => x * x);
        decimal lag = variation == 0m ? 0m : centered.Zip(centered.Skip(1)).Sum(x => x.First * x.Second) / variation;
        decimal effective = sample.Length / (1m + 2m * Math.Max(0m, lag));
        decimal allowance = 3m * (decimal)Math.Sqrt((double)(variation / ((sample.Length - 1) * effective)));
        return new(sample.Length, effective, mean, allowance);
    }
}
