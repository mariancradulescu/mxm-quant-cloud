using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public static class NativeFundedActionResearch
{
    const long Day = NativeCompletePolicy.Day;
    const long Week = NativeCompletePolicy.Week;
    const long Hour = 3_600_000L;
    const long EpochMonday = 4 * Day;
    public static readonly long Start = new DateTimeOffset(2026, 11, 23, 0, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();
    public static readonly long FitEnd = Start + 6 * Week;
    public static readonly long CalibrationStart = FitEnd + Week;
    public static readonly long CalibrationEnd = CalibrationStart + 2 * Week;
    public static readonly long EvaluationStart = CalibrationEnd + Week;
    public static readonly long End = EvaluationStart + 4 * Week;
    public static readonly IReadOnlyList<string> Universe = Array.AsReadOnly(new[]
        { "EURUSD", "GBPUSD", "XAUUSD", "SpotBrent", "US500", "AAPL.US" });

    internal sealed record Label(NativeFundedActionOffer Offer, long SettledAt, decimal DeltaEur)
    {
        public NativeCompleteSample Sample => new(Offer.Symbol, Offer.At, SettledAt, Offer.Features, DeltaEur / Offer.ScaleEur);
    }
    internal sealed record LabelWindow(long From, long Until, long? MaturityUntil = null);
    internal sealed record LabelPhase(LabelWindow Window, List<Label> Labels, Dictionary<string, int> Counts);
    internal sealed record ResearchCohort(long From, long Until, LedgerSummary Book);
    internal sealed record LabelObservation(LabelPhase[] Phases, LedgerSummary PilotBook,
        ResearchCohort[]? IndependentCohorts = null);
    internal sealed record EvaluationFold(long FitEnd, long CalibrationStart, long From, long Until);

    static NativeUnifiedPortfolioEngine Pilot(string suffix)
        => new(NativeStructuralOpportunity.Prefix + NativeFundedActionValue.First + suffix);

    static Ucp1FrameResult Observe(NativeUnifiedPortfolioEngine engine, Ucp1Frame frame, NativeFundedActionProbe probe)
        => engine.Advance(frame, NativeStructuralOpportunity.Describe, NativeImpulseExhaustionResearch.Describe, probe);

    internal static (decimal? DeltaEur, long At, string Status) Paired(string checkpoint, NativeFundedActionOffer offer,
        Ucp1Frame[] frames, int first, IReadOnlyDictionary<string, NativeObservedContractTerms> contracts,
        long untilExclusive = long.MaxValue)
    {
        long lastAt = frames[first].At;
        if (lastAt >= untilExclusive) throw new ArgumentException("FUNDED_ACTION_EMPTY_FORK_INTERVAL");
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
        for (int i = first + 1; i < frames.Length && frames[i].At < untilExclusive; i++)
        {
            lastAt = frames[i].At;
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
        return (null, lastAt, "RIGHT_CENSORED");
    }

    internal static LabelObservation ObserveLabels(Ucp1Frame[] frames, LabelWindow[] windows, string suffix,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        if (windows.Any(w => w.From >= w.Until || w.MaturityUntil < w.Until) ||
            windows.Zip(windows.Skip(1)).Any(pair => pair.First.Until > pair.Second.From))
            throw new ArgumentException("FUNDED_ACTION_LABEL_WINDOW_OVERLAP");

        var phases = windows.Select(w => new LabelPhase(w, new(), new(StringComparer.Ordinal))).ToArray();
        var engine = Pilot(suffix);
        int window = 0;
        for (int i = 0; i < frames.Length; i++)
        {
            var frame = frames[i];
            while (window < phases.Length && frame.At >= phases[window].Window.Until) window++;
            // Only the counterfactual branches stop at a label boundary. The pilot prices and
            // manages the same positions and intents at every clock, including embargoes.
            if (window == phases.Length || frame.At < phases[window].Window.From ||
                frame.At % Hour != NativeIntegratedEconomicPolicy.ClockOffsetMs ||
                !frame.Markets.Any(NativeStructuralOpportunity.ContextReady))
            {
                engine.Advance(frame);
                continue;
            }
            var phase = phases[window];
            string checkpoint = engine.ActionForkCheckpoint();
            var probe = new NativeFundedActionProbe();
            Observe(engine, frame, probe);
            foreach (var kind in probe.Available.GroupBy(o => o.Kind))
            {
                var offer = kind.OrderBy(ProbeOrder, StringComparer.Ordinal).First();
                var (delta, settled, status) = Paired(checkpoint, offer, frames, i, contracts, phase.Window.MaturityUntil ?? phase.Window.Until);
                string key = offer.Group + "/" + status;
                phase.Counts[key] = phase.Counts.GetValueOrDefault(key) + 1;
                if (delta is decimal value) phase.Labels.Add(new(offer, settled, value));
            }
        }
        return new(phases, engine.ModelSummary);
    }

    // NEW, distinct development mode only: fixed chronological Monday-to-Monday
    // research cohorts start from separately funded EUR300 pilot experiments.
    // Their cash/PNL MUST NEVER be summed, promoted or represented as the
    // continuous EUR300 economic portfolio. Each actual tested policy remains
    // a single uninterrupted funded book in Evaluate().
    // Historical as-of quotes and the identical counterfactual fill engine
    // continue to determine every research label. An exhausted pilot in one
    // research week cannot erase the future weeks' available market actions.
    internal static LabelObservation ObserveIndependentResearchCohorts(
        Ucp1Frame[] frames, LabelWindow[] windows, string suffix,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        if (frames.Length == 0 || windows.Length == 0 ||
            windows.Any(w => w.From >= w.Until || w.MaturityUntil < w.Until) ||
            windows.Zip(windows.Skip(1)).Any(pair => pair.First.Until > pair.Second.From))
            throw new ArgumentException("FUNDED_ACTION_COHORT_WINDOW_INVALID");

        var phases = windows.Select(w => new LabelPhase(w, new(), new(StringComparer.Ordinal))).ToArray();
        var cohorts = new List<ResearchCohort>(phases.Length);
        int next = 0;
        foreach (var phase in phases)
        {
            // Ex-ante fixed observation cohort, not a backtest reset or
            // portfolio replenishment. The cohort never carries its debt
            // or cash into the next week's research observation schedule.
            var pilot = Pilot(suffix);
            while (next < frames.Length && frames[next].At < phase.Window.From) next++;
            int i = next;
            for (; i < frames.Length && frames[i].At < phase.Window.Until; i++)
            {
                var frame = frames[i];
                if (frame.At % Hour != NativeIntegratedEconomicPolicy.ClockOffsetMs ||
                    !frame.Markets.Any(NativeStructuralOpportunity.ContextReady))
                {
                    pilot.Advance(frame);
                    continue;
                }
                string checkpoint = pilot.ActionForkCheckpoint();
                var probe = new NativeFundedActionProbe();
                Observe(pilot, frame, probe);
                foreach (var kind in probe.Available.GroupBy(o => o.Kind))
                {
                    var offer = kind.OrderBy(ProbeOrder, StringComparer.Ordinal).First();
                    var (delta, settled, status) = Paired(checkpoint, offer, frames, i, contracts,
                        phase.Window.MaturityUntil ?? phase.Window.Until);
                    string key = offer.Group + "/" + status;
                    phase.Counts[key] = phase.Counts.GetValueOrDefault(key) + 1;
                    if (delta is decimal value) phase.Labels.Add(new(offer, settled, value));
                }
            }
            cohorts.Add(new(phase.Window.From, phase.Window.Until, pilot.ModelSummary));
            next = i;
        }
        return new(phases, cohorts[^1].Book, cohorts.ToArray());
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
                calibration.Any(x => x.DecisionAt < fitEnd || x.SettledAt >= calibrationEnd || x.SettledAt <= x.DecisionAt))
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

    sealed record ScoredLabel(Label Label, NativeFundedActionModel Model);

    static object Metrics(ScoredLabel[] rows, string variant)
    {
        var scored = rows.Select(x => (x.Label, Prediction: x.Model.Predict(variant, x.Label.Offer)))
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

    static decimal?[] WeeklyNet(NativeUnifiedPortfolioEngine engine, long start, long end,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        var closes = engine.CommonBookEquityPath.GroupBy(x => (x.At - start) / Week)
            .ToDictionary(g => g.Key, g => g.Last());
        var unsupported = engine.CompleteModelTrips
            .Where(t => t.CrossedUnknownHistory || NativeStructuralResearch.FinancingUnverified(t, contracts[t.Symbol]))
            .Select(t => (t.CloseAt - start) / Week).ToHashSet();
        var result = new decimal?[(end - start) / Week];
        Ucp1CurvePoint? previous = null;
        for (int i = 0; i < result.Length; i++)
        {
            var close = closes[i];
            if ((previous is null or { Held: 0, Pending: 0 }) && close is { Held: 0, Pending: 0 } && !unsupported.Contains(i))
                result[i] = close.CashEur - (previous?.CashEur ?? OwnerRiskAuthority.InitialCapitalEur);
            previous = close;
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

    static bool CompleteClock(Ucp1Frame[] frames, long start, long end)
        => frames.Length > 0 && frames[0].At == start + NativeIntegratedEconomicPolicy.ClockOffsetMs &&
            frames[^1].At == end - NativeIntegratedLifecycle.IntervalMs + NativeIntegratedEconomicPolicy.ClockOffsetMs &&
            !frames.Zip(frames.Skip(1)).Any(pair => pair.Second.At - pair.First.At != NativeIntegratedLifecycle.IntervalMs);

    public static object Run(Ucp1Frame[] frames, IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        if (!CompleteClock(frames, Start, End)) throw new ArgumentException("FUNDED_ACTION_PROSPECTIVE_CALENDAR");
        var windows = new LabelWindow[] { new(Start, FitEnd), new(CalibrationStart, CalibrationEnd), new(EvaluationStart, End) };
        return Evaluate(frames, windows, new[] { new EvaluationFold(FitEnd, CalibrationStart, EvaluationStart, End) },
            contracts, prospective: true);
    }

    internal static (LabelWindow[] Windows, EvaluationFold[] Folds) HistoricalSchedule(long start, long end)
    {
        // Unix epoch was Thursday; Monday after epoch is day four.
        long firstMonday = EpochMonday + (start - EpochMonday + Week - 1) / Week * Week;
        long fullWeeks = (end - firstMonday) / Week;
        if (fullWeeks < 3) throw new ArgumentException("FUNDED_ACTION_HISTORICAL_FIT_CALIBRATION_TEST_WEEKS");
        var windows = Enumerable.Range(0, (int)fullWeeks)
            .Select(i => new LabelWindow(firstMonday + i * Week, firstMonday + (i + 1) * Week, end)).ToArray();
        var folds = windows.Skip(2).Select(w => new EvaluationFold(w.From - Week, w.From - Week, w.From, w.Until)).ToArray();
        return (windows, folds);
    }

    // The previously executed RunHistorical remains frozen. This separately
    // named development path changes the research sampling experiment only.
    public static object RunHistoricalIndependentCohorts(Ucp1Frame[] frames, long start, long end,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        if (start < Week || start % Day != 0 || end % Day != 0 || !CompleteClock(frames, start, end))
            throw new ArgumentException("FUNDED_ACTION_HISTORICAL_COHORT_CALENDAR");
        var (windows, folds) = HistoricalSchedule(start, end);
        return Evaluate(frames, windows, folds, contracts, prospective: false, independentCohorts: true);
    }

    public static object RunHistorical(Ucp1Frame[] frames, long start, long end,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        if (start < Week || start % Day != 0 || end % Day != 0 || !CompleteClock(frames, start, end))
            throw new ArgumentException("FUNDED_ACTION_HISTORICAL_CALENDAR");
        var (windows, folds) = HistoricalSchedule(start, end);
        return Evaluate(frames, windows, folds, contracts, prospective: false);
    }

    static object Evaluate(Ucp1Frame[] frames, LabelWindow[] windows, EvaluationFold[] folds,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts, bool prospective,
        bool independentCohorts = false)
    {
        long evaluationStart = folds[0].From, evaluationEnd = folds[^1].Until;
        var cases = frames.Where(f => f.At >= evaluationStart && f.At < evaluationEnd).ToArray();
        var weeks = cases.GroupBy(f => (f.At - evaluationStart) / Week).Select(g => new
        {
            WeekStart = evaluationStart + g.Key * Week,
            Clocks = g.Count(),
            ObservedClocks = g.Count(f => f.Markets.Length > 0),
            Symbols = g.SelectMany(f => f.Markets).GroupBy(m => m.Symbol).ToDictionary(m => m.Key,
                m => new { Quotes = m.Count(), ReadyContext = m.Count(NativeStructuralOpportunity.ContextReady),
                    CompletePaths = m.Count(x => x.Integrated?.Path?.Complete == true) })
        }).ToArray();

        object Scenario(string suffix)
        {
            var observed = independentCohorts
                ? ObserveIndependentResearchCohorts(frames, windows, suffix, contracts)
                : ObserveLabels(frames, windows, suffix, contracts);
            var labels = observed.Phases.SelectMany(p => p.Labels).ToArray();
            var models = folds.Select(fold =>
            {
                var fit = labels.Where(x => x.SettledAt < fold.FitEnd);
                var calibration = labels.Where(x => x.Offer.At >= fold.CalibrationStart && x.SettledAt < fold.From)
                    .ToLookup(x => x.Offer.Group, StringComparer.Ordinal);
                long availableAt = prospective ? CalibrationEnd : fold.From;
                var model = BuildModel(fit.GroupBy(x => x.Offer.Group).Select(g => (g.Key, g.Select(x => x.Sample).ToArray(),
                    calibration[g.Key].Select(x => x.Sample).ToArray())), fold.FitEnd, availableAt, suffix == "_ADVERSE");
                return model with { SourceSymbols = contracts.Keys.OrderBy(x => x, StringComparer.Ordinal).ToArray() };
            }).ToArray();
            var test = folds.SelectMany((fold, i) => labels.Where(x => x.Offer.At >= fold.From && x.Offer.At < fold.Until)
                .Select(x => new ScoredLabel(x, models[i]))).ToArray();
            var books = new Dictionary<string, object>(StringComparer.Ordinal);
            var net = new Dictionary<string, decimal?>(StringComparer.Ordinal);
            var weekly = new Dictionary<string, decimal?[]>(StringComparer.Ordinal);
            foreach (string variant in NativeFundedActionValue.Variants)
            {
                var engine = new NativeUnifiedPortfolioEngine(NativeStructuralOpportunity.Prefix + variant + suffix);
                int next = 0;
                foreach (var frame in cases)
                {
                    if (next < folds.Length && frame.At >= folds[next].From)
                    {
                        engine.UseFundedActionModel(models[next], frame.At);
                        next++;
                    }
                    engine.Advance(frame);
                }
                var report = NativeStructuralResearch.DevelopmentBook(engine, evaluationStart, evaluationEnd, contracts,
                    includeEquityTrace: prospective);
                var completeTrips = engine.CompleteModelTrips;
                var bySymbol = completeTrips.GroupBy(t => t.Symbol).ToDictionary(g => g.Key,
                    g => new { Trades = g.Count(), NetEur = g.Sum(t => t.NetEur) });
                books.Add(variant, new { Book = report.Report, ActionValues = engine.FundedActionReceipts, BySymbol = bySymbol });
                net.Add(variant, report.CompleteModeledNet);
                weekly.Add(variant, WeeklyNet(engine, evaluationStart, evaluationEnd, contracts));
            }

            var variants = new[] { NativeFundedActionValue.Context, NativeFundedActionValue.Pooled, NativeFundedActionValue.Placebo };
            object Forecasts(ScoredLabel[] rows) => variants.ToDictionary(v => v, v => Metrics(rows, v));
            var common = test.Where(x => variants.All(v => x.Model.Predict(v, x.Label.Offer) is not null)).ToArray();
            var primary = new[] { NativeFundedActionValue.Cash, NativeFundedActionValue.First }.Select(v =>
            {
                var deltas = weekly[NativeFundedActionValue.Context].Zip(weekly[v], (context, control) => context - control).ToArray();
                return (Control: v, Deltas: deltas, P: prospective ? SignFlipProbability(deltas) : null);
            }).OrderBy(x => x.P ?? decimal.MaxValue).ToArray();
            var holm = primary.All(x => x.P.HasValue) ? primary.Select((x, i) => new
            {
                x.Control, WeeklyDeltasEur = x.Deltas, OneSidedP = x.P,
                HolmRejectedAtFivePercent = primary.Take(i + 1).Select((t, rank) => t.P <= .05m / (2 - rank)).All(x => x)
            }).ToArray() : null;
            return new
            {
                // In the new mode there is deliberately NO single continuous
                // research pilot. Only evaluated policies have continuous books.
                Pilot = independentCohorts ? (object?)null : observed.PilotBook,
                ResearchSampling = independentCohorts
                    ? "FIXED_WEEKLY_INDEPENDENT_EUR300_LABEL_EXPERIMENTS_NOT_PORTFOLIO_PNL"
                    : "CONTINUOUS_FIRST_PILOT",
                IndependentResearchCohorts = observed.IndependentCohorts,
                LabelCoverage = observed.Phases.Select(p => new { p.Window, p.Counts }),
                Training = prospective ? observed.Phases[0].Counts : null,
                Calibration = prospective ? observed.Phases[1].Counts : null,
                TestLabels = prospective ? observed.Phases[2].Counts : null,
                Model = prospective ? models[0] : null,
                ModelCohorts = folds.Select((f, i) => new { Fold = f, models[i].AvailableAt,
                    Groups = models[i].Actions.ToDictionary(x => x.Key, x => x.Value.Context?.Samples.Length) }),
                CalibrationMetrics = Forecasts(test),
                MatchedForecastRows = Forecasts(common),
                ByMechanism = test.GroupBy(x => x.Label.Offer.Group).ToDictionary(g => g.Key, g => Forecasts(g.ToArray())),
                ByRegime = test.GroupBy(x => x.Label.Offer.Features[1] * x.Label.Offer.Features[3] > 0m
                    ? "M15_H1_ALIGNED" : "M15_H1_OTHER").ToDictionary(g => g.Key, g => Forecasts(g.ToArray())),
                Books = books, CompleteModeledNetEur = net, CompleteComparableWeeklyNetEur = weekly,
                PrimaryAdverseComparisons = suffix == "_ADVERSE" ? holm : null,
                ContextMinusControlsEur = net.Where(x => x.Key != NativeFundedActionValue.Context)
                    .ToDictionary(x => x.Key, x => net[NativeFundedActionValue.Context] - x.Value)
            };
        }

        return new
        {
            Evidence = prospective ? "PROSPECTIVE_RESEARCH" : "HISTORICAL_DEVELOPMENT",
            SourceStart = frames[0].At - NativeIntegratedEconomicPolicy.ClockOffsetMs,
            SourceEnd = frames[^1].At + NativeIntegratedLifecycle.IntervalMs - NativeIntegratedEconomicPolicy.ClockOffsetMs,
            EvaluationStart = evaluationStart, End = evaluationEnd,
            FitEnd = prospective ? FitEnd : (long?)null,
            CalibrationStart = prospective ? CalibrationStart : (long?)null,
            CalibrationEnd = prospective ? CalibrationEnd : (long?)null,
            Symbols = contracts.Keys.OrderBy(x => x, StringComparer.Ordinal), EvaluationCoverage = weeks,
            Central = Scenario(""), Adverse = Scenario("_ADVERSE"), ResearchOnly = true,
            IndependentConfirmation = false, Orders = 0, CloudActivation = false
        };
    }
}
