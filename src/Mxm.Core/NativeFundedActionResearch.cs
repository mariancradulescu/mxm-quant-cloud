using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public static class NativeFundedActionResearch
{
    const long Day = NativeCompletePolicy.Day;
    const long Week = NativeCompletePolicy.Week;
    const long Hour = 3_600_000L;
    public static readonly long Start = new DateTimeOffset(2026, 11, 23, 0, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();
    public static readonly long FitEnd = Start + 6 * Week;
    public static readonly long CalibrationStart = FitEnd + Week;
    public static readonly long CalibrationEnd = CalibrationStart + 2 * Week;
    public static readonly long EvaluationStart = CalibrationEnd + Week;
    public static readonly long End = EvaluationStart + 4 * Week;
    public static readonly IReadOnlyList<string> Universe = Array.AsReadOnly(new[]
        { "EURUSD", "GBPUSD", "XAUUSD", "SpotBrent", "US500", "AAPL.US" });

    sealed record Label(NativeFundedActionOffer Offer, long SettledAt, decimal DeltaEur)
    {
        public NativeCompleteSample Sample => new(Offer.Symbol, Offer.At, SettledAt, Offer.Features, DeltaEur / Offer.ScaleEur);
    }
    sealed record LabelPhase(Label[] Labels, Dictionary<string, int> Counts);

    static NativeUnifiedPortfolioEngine Pilot(string suffix)
        => new(NativeStructuralOpportunity.Prefix + NativeFundedActionValue.First + suffix);

    static Ucp1FrameResult Observe(NativeUnifiedPortfolioEngine engine, Ucp1Frame frame, NativeFundedActionProbe probe)
        => engine.Advance(frame, NativeStructuralOpportunity.Describe, NativeImpulseExhaustionResearch.Describe, probe);

    internal static (decimal? DeltaEur, long At, string Status) Paired(string checkpoint, NativeFundedActionOffer offer,
        Ucp1Frame[] frames, int first, IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        var chosen = NativeUnifiedPortfolioEngine.Restore(checkpoint);
        var alternative = NativeUnifiedPortfolioEngine.Restore(checkpoint);
        var action = new NativeFundedActionProbe
        {
            Enter = offer.Kind == NativeFundedActionValue.Enter ? offer.Key : null,
            Close = offer.Kind == NativeFundedActionValue.Close ? offer.Key : null
        };
        var baseline = new NativeFundedActionProbe { Wait = offer.Kind == NativeFundedActionValue.Enter };
        int tripsBefore = chosen.ModelSummary.CompleteRoundTrips;
        var take = Observe(chosen, frames[first], action);
        var leave = Observe(alternative, frames[first], baseline);
        if (!action.Available.Any(x => x.Kind == offer.Kind && x.Key == offer.Key) ||
            !baseline.Available.Any(x => x.Kind == offer.Kind && x.Key == offer.Key))
            throw new InvalidOperationException("FUNDED_ACTION_FORK_PREFIX_MISMATCH");

        bool HasGap(NativeUnifiedPortfolioEngine branch, Ucp1Frame frame, Ucp1FrameResult result)
            => result.Held > 0 && result.ModelBook.LiquidationEquityEur is null ||
                branch.ActiveSymbols.Any(symbol => !frame.Markets.Any(m => m.Symbol == symbol && m.Integrated?.Path?.Complete == true));
        bool unknownPath = HasGap(chosen, frames[first], take) || HasGap(alternative, frames[first], leave);
        for (int i = first + 1; i < frames.Length; i++)
        {
            take = chosen.Advance(frames[i]);
            leave = alternative.Advance(frames[i]);
            unknownPath |= HasGap(chosen, frames[i], take) || HasGap(alternative, frames[i], leave);
            if (take.Held + take.Pending + leave.Held + leave.Pending != 0) continue;
            var trips = chosen.CompleteModelTrips.Skip(tripsBefore).Concat(alternative.CompleteModelTrips.Skip(tripsBefore)).ToArray();
            if (unknownPath || trips.Any(t => t.CrossedUnknownHistory))
                return (null, frames[i].At, "UNKNOWN_PATH_OR_MARK");
            if (trips.Any(t => NativeStructuralResearch.FinancingUnverified(t, contracts[t.Symbol])))
                return (null, frames[i].At, "UNVERIFIED_FINANCING");
            return (take.ModelBook.CashEur - leave.ModelBook.CashEur, frames[i].At, "SETTLED");
        }
        return (null, frames[^1].At, "RIGHT_CENSORED");
    }

    static LabelPhase ObserveLabels(Ucp1Frame[] frames, long from, long until, string suffix,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        var labels = new List<Label>();
        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var day in frames.Where(f => f.At >= from && f.At < until).GroupBy(f => f.At / Day))
        {
            var observations = day.ToArray();
            var engine = Pilot(suffix);
            for (int i = 0; i < observations.Length; i++)
            {
                var frame = observations[i];
                // A fixed hourly anchor bounds paired exploration without choosing successful paths.
                if (frame.At % Hour != NativeIntegratedEconomicPolicy.ClockOffsetMs || frame.Markets.Length == 0)
                {
                    engine.Advance(frame);
                    continue;
                }
                string checkpoint = engine.Checkpoint();
                var probe = new NativeFundedActionProbe();
                Observe(engine, frame, probe);
                foreach (var kind in probe.Available.GroupBy(o => o.Kind))
                {
                    var offer = kind.OrderBy(o => ProbeOrder(o), StringComparer.Ordinal).First();
                    var (delta, settled, status) = Paired(checkpoint, offer, observations, i, contracts);
                    string key = offer.Group + "/" + status;
                    counts[key] = counts.GetValueOrDefault(key) + 1;
                    if (delta is decimal value) labels.Add(new(offer, settled, value));
                }
            }
        }
        return new(labels.ToArray(), counts);
    }

    static string ProbeOrder(NativeFundedActionOffer o)
        => Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(
            FormattableString.Invariant($"FUNDED_ACTION_20261120/{o.At}/{o.Group}/{o.Key}"))));

    internal static NativeFundedActionModel BuildModel(IEnumerable<(string Key, NativeCompleteSample[] Training,
        NativeCompleteSample[] Calibration)> data, long fitEnd, long calibrationEnd, bool adverse)
    {
        var result = new Dictionary<string, NativeFundedActionDistributions>(StringComparer.Ordinal);
        foreach (var (key, training, calibration) in data)
        {
            if (training.Any(x => x.SettledAt >= fitEnd || x.SettledAt <= x.DecisionAt) ||
                calibration.Any(x => x.DecisionAt <= fitEnd || x.SettledAt >= calibrationEnd || x.SettledAt <= x.DecisionAt))
                throw new ArgumentException("FUNDED_ACTION_FIT_FOLD_OVERLAP");
            var pooled = training.Select(x => x with { Features = new[] { 0m } }).ToArray();
            // Break the feature/outcome link within each training week. No holdout row is transformed or fitted.
            var placebo = training.GroupBy(x => x.DecisionAt / Week).SelectMany(g =>
            {
                var rows = g.OrderBy(x => x.DecisionAt).ThenBy(x => x.Symbol, StringComparer.Ordinal).ToArray();
                return rows.Length < 2 ? Array.Empty<NativeCompleteSample>() :
                    rows.Select((x, i) => x with { Features = rows[(i + rows.Length / 2) % rows.Length].Features });
            }).ToArray();
            result.Add(key, new(Calibrate(training, calibration, false), Calibrate(pooled, calibration, true),
                Calibrate(placebo, calibration, false)));
        }
        var model = new NativeFundedActionModel(fitEnd, calibrationEnd, adverse, result);
        model.Validate();
        return model;
    }

    static NativeCompleteDistribution? Calibrate(NativeCompleteSample[] fit, NativeCompleteSample[] calibration, bool pooled)
    {
        var model = new NativeCompleteDistribution(fit, false);
        var days = calibration.Select(x => (x, Forecast: model.Predict(pooled ? new[] { 0m } : x.Features, x.DecisionAt, 1m)))
            .Where(x => x.Forecast is not null).GroupBy(x => x.x.DecisionAt / Day)
            .Select(g => g.Average(x => x.x.OutcomeR - x.Forecast!.Mean)).OrderBy(x => x).ToArray();
        if (days.Length < 4) return null;
        decimal bias = days.Average();
        decimal residualP10 = days[(int)Math.Floor((days.Length - 1) * .10m)];
        return model with { BiasR = bias, UncertaintyR = Math.Max(0m, bias - residualP10) };
    }

    static object Metrics(Label[] rows, NativeFundedActionModel model, string variant)
    {
        var scored = rows.Select(x => (Label: x, Prediction: model.Predict(variant, x.Offer)))
            .Where(x => x.Prediction is not null).Select(x => (x.Label, P: x.Prediction!)).ToArray();
        if (scored.Length == 0) return new { Eligible = rows.Length, Scored = 0 };
        return new
        {
            Eligible = rows.Length, Scored = scored.Length,
            MeanPredictionEur = scored.Average(x => x.P.Mean), MeanSettledDeltaEur = scored.Average(x => x.Label.DeltaEur),
            MeanAbsoluteErrorEur = scored.Average(x => Math.Abs(x.P.Mean - x.Label.DeltaEur)),
            Brier = scored.Average(x =>
            {
                decimal residual = x.P.PositiveProbability - (x.Label.DeltaEur > 0m ? 1m : 0m);
                return residual * residual;
            }),
            P10P90Coverage = (decimal)scored.Count(x => x.P.P10 <= x.Label.DeltaEur && x.P.P90 >= x.Label.DeltaEur) / scored.Length,
            ProbabilityBins = scored.GroupBy(x => Math.Min(4, (int)(5 * x.P.PositiveProbability))).ToDictionary(g => g.Key,
                g => new { N = g.Count(), Forecast = g.Average(x => x.P.PositiveProbability),
                    Observed = (decimal)g.Count(x => x.Label.DeltaEur > 0m) / g.Count() })
        };
    }

    static decimal?[] WeeklyNet(NativeUnifiedPortfolioEngine engine, IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        var marks = engine.CommonBookEquityPath;
        var trips = engine.CompleteModelTrips;
        var result = new decimal?[4];
        for (int i = 0; i < result.Length; i++)
        {
            long from = EvaluationStart + i * Week;
            var start = marks.LastOrDefault(x => x.At < from);
            var close = marks.Last(x => x.At < from + Week);
            if ((start is null or { Held: 0, Pending: 0 }) && close is { Held: 0, Pending: 0 } &&
                !trips.Any(t => t.CloseAt >= from && t.CloseAt < from + Week &&
                    (t.CrossedUnknownHistory || NativeStructuralResearch.FinancingUnverified(t, contracts[t.Symbol]))))
                result[i] = close.CashEur - (start?.CashEur ?? OwnerRiskAuthority.InitialCapitalEur);
        }
        return result;
    }

    static decimal? SignFlipProbability(decimal?[] deltas)
    {
        if (deltas.Any(x => x is null)) return null;
        var values = deltas.Select(x => x!.Value).ToArray();
        decimal observed = values.Sum();
        int patterns = 1 << values.Length, asHigh = 0;
        for (int mask = 0; mask < patterns; mask++)
            if (values.Select((x, i) => (mask & (1 << i)) == 0 ? x : -x).Sum() >= observed) asHigh++;
        return (decimal)asHigh / patterns;
    }

    public static object Run(Ucp1Frame[] frames, IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        if (frames.Length == 0 || frames[0].At != Start + NativeIntegratedEconomicPolicy.ClockOffsetMs ||
            frames[^1].At != End - NativeIntegratedLifecycle.IntervalMs + NativeIntegratedEconomicPolicy.ClockOffsetMs ||
            frames.Zip(frames.Skip(1)).Any(pair => pair.Second.At - pair.First.At != NativeIntegratedLifecycle.IntervalMs))
            throw new ArgumentException("FUNDED_ACTION_PROSPECTIVE_CALENDAR");

        object Evaluate(string suffix)
        {
            var fit = ObserveLabels(frames, Start, FitEnd, suffix, contracts);
            var calibration = ObserveLabels(frames, CalibrationStart, CalibrationEnd, suffix, contracts);
            var validation = ObserveLabels(frames, EvaluationStart, End, suffix, contracts);
            var calibrationGroups = calibration.Labels.ToLookup(x => x.Offer.Group, StringComparer.Ordinal);
            var model = BuildModel(fit.Labels.GroupBy(x => x.Offer.Group).Select(g => (g.Key,
                g.Select(x => x.Sample).ToArray(), calibrationGroups[g.Key].Select(x => x.Sample).ToArray())),
                FitEnd, CalibrationEnd, suffix == "_ADVERSE");
            var books = new Dictionary<string, object>(StringComparer.Ordinal);
            var net = new Dictionary<string, decimal?>(StringComparer.Ordinal);
            var weekly = new Dictionary<string, decimal?[]>(StringComparer.Ordinal);
            foreach (string variant in NativeFundedActionValue.Variants)
            {
                var engine = new NativeUnifiedPortfolioEngine(NativeStructuralOpportunity.Prefix + variant + suffix, actionModel: model);
                foreach (var frame in frames.Where(f => f.At >= EvaluationStart)) engine.Advance(frame);
                var report = NativeStructuralResearch.DevelopmentBook(engine, EvaluationStart, End, contracts);
                books.Add(variant, new { Book = report.Report, ActionValues = engine.FundedActionReceipts });
                net.Add(variant, report.CompleteModeledNet);
                weekly.Add(variant, WeeklyNet(engine, contracts));
            }
            var variants = new[] { NativeFundedActionValue.Context, NativeFundedActionValue.Pooled, NativeFundedActionValue.Placebo };
            object Forecasts(Label[] rows) => variants.ToDictionary(v => v, v => Metrics(rows, model, v));
            var common = validation.Labels.Where(x => variants.All(v => model.Predict(v, x.Offer) is not null)).ToArray();
            var primary = new[] { NativeFundedActionValue.Cash, NativeFundedActionValue.First }.Select(v =>
            {
                var deltas = weekly[NativeFundedActionValue.Context].Zip(weekly[v], (context, control) => context - control).ToArray();
                return (Control: v, Deltas: deltas, P: SignFlipProbability(deltas));
            }).OrderBy(x => x.P ?? decimal.MaxValue).ToArray();
            var holm = primary.All(x => x.P.HasValue) ? primary.Select((x, i) => new
            {
                x.Control, WeeklyDeltasEur = x.Deltas, OneSidedP = x.P,
                HolmRejectedAtFivePercent = primary.Take(i + 1).Select((test, rank) => test.P <= .05m / (2 - rank)).All(x => x)
            }).ToArray() : null;
            // Compare realized books independently started at EUR300. Censoring propagates to each delta.
            return new
            {
                Training = fit.Counts, Calibration = calibration.Counts, TestLabels = validation.Counts,
                Model = model, CalibrationMetrics = Forecasts(validation.Labels),
                MatchedForecastRows = Forecasts(common),
                ByMechanism = validation.Labels.GroupBy(x => x.Offer.Group).ToDictionary(g => g.Key, g => Forecasts(g.ToArray())),
                ByRegime = validation.Labels.GroupBy(x => x.Offer.Features[1] * x.Offer.Features[3] > 0m
                    ? "M15_H1_ALIGNED" : "M15_H1_OTHER").ToDictionary(g => g.Key, g => Forecasts(g.ToArray())),
                Books = books, CompleteModeledNetEur = net, CompleteComparableWeeklyNetEur = weekly,
                PrimaryAdverseComparisons = suffix == "_ADVERSE" ? holm : null,
                ContextMinusControlsEur = net.Where(x => x.Key != NativeFundedActionValue.Context)
                    .ToDictionary(x => x.Key, x => net[NativeFundedActionValue.Context] - x.Value)
            };
        }
        var coverage = frames.Where(f => f.At >= EvaluationStart).GroupBy(f => (f.At - EvaluationStart) / Week)
            .Select(g => new { WeekStart = EvaluationStart + g.Key * Week, Clocks = g.Count(),
                ObservedClocks = g.Count(f => f.Markets.Length > 0),
                Symbols = g.SelectMany(f => f.Markets).GroupBy(m => m.Symbol).ToDictionary(m => m.Key,
                    m => new { Quotes = m.Count(), ReadyContext = m.Count(NativeStructuralOpportunity.ContextReady),
                        CompletePaths = m.Count(x => x.Integrated?.Path?.Complete == true) }) }).ToArray();
        return new { Start, FitEnd, CalibrationStart, CalibrationEnd, EvaluationStart, End, Universe, EvaluationCoverage = coverage,
            Central = Evaluate(""), Adverse = Evaluate("_ADVERSE"), ResearchOnly = true,
            IndependentConfirmation = false, Orders = 0, CloudActivation = false };
    }
}
