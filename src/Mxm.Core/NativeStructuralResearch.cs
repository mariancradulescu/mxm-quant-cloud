using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

public static class NativeStructuralResearch
{
    sealed record Offer(int Index, string Symbol, NativeIntegratedCandidate Signal);
    sealed record Label(string Family, NativeCompleteSample Sample, decimal RiskEur);
    sealed record LabeledPhase(Label[] Labels, Dictionary<string, int> Outcomes);

    static void Add(Dictionary<string, int> counts, string key) => counts[key] = counts.GetValueOrDefault(key) + 1;

    static Offer[] Offers(Ucp1Frame[] frames, Dictionary<string, int> census)
    {
        var latest = new Dictionary<string, long>(StringComparer.Ordinal);
        var offers = new List<Offer>();
        for (int i = 0; i < frames.Length; i++)
        {
            foreach (var market in frames[i].Markets)
            {
                Add(census, "MONEY_MARK/" + market.Symbol);
                if (!NativeStructuralOpportunity.ContextReady(market)) continue;
                long close = market.M5[^1].CloseAt;
                if (latest.GetValueOrDefault(market.Symbol) >= close) continue;
                latest[market.Symbol] = close;
                Add(census, "READY_NEW_M5/" + market.Symbol);
                if (NativeStructuralOpportunity.Describe(market) is not { } setup) continue;
                Add(census, setup.Signal.Family + "/" + market.Symbol);
                offers.Add(new(i, market.Symbol, setup.Signal));
            }
        }
        return offers.ToArray();
    }

    static bool FinancingUnverified(Ucp1Episode trip, NativeObservedContractTerms terms)
    {
        if (terms.SwapPeriodHours is not (> 0 and <= 24) || terms.SwapTimeUtcMinute is not (>= 0 and < 1440))
            return true;
        long period = terms.SwapPeriodHours.Value * 3_600_000L, offset = terms.SwapTimeUtcMinute.Value * 60_000L;
        return (trip.CloseAt - offset) / period != (trip.OpenAt - offset) / period;
    }

    static LabeledPhase Labels(Ucp1Frame[] frames, IEnumerable<Offer> offers, long cutoff, string suffix,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        var labels = new List<Label>();
        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var offer in offers)
        {
            long start = frames[offer.Index].At;
            string family = offer.Signal.Family;
            void Count(string verdict) => Add(counts, family + "/" + verdict);
            Count("OFFER");
            var engine = new NativeUnifiedPortfolioEngine(NativeStructuralOpportunity.Prefix + "PROBE" + suffix,
                probe: new(offer.Symbol, offer.Signal.Side, start));
            bool terminal = false;
            for (int i = offer.Index; i < frames.Length && frames[i].At < cutoff; i++)
            {
                var frame = frames[i];
                var result = engine.Advance(frame with { Markets = frame.Markets.Where(x => x.Symbol == offer.Symbol).ToArray() });
                if (result.CloseFills > 0)
                {
                    terminal = true;
                    var trip = engine.CompleteModelTrips.Single();
                    Count("SETTLED");
                    if (trip.CrossedUnknownHistory)
                    {
                        Count("PATH_UNKNOWN");
                        break;
                    }
                    if (FinancingUnverified(trip, contracts[offer.Symbol]))
                    {
                        Count("FINANCING_UNKNOWN");
                        break;
                    }
                    var entry = trip.Integrated!.CompletePolicy!;
                    labels.Add(new(family, new(offer.Symbol, start, trip.CloseAt, entry.Features,
                        trip.NetEur / entry.ScaleEur), entry.ScaleEur));
                    Count("LABEL");
                    break;
                }
                if (result.Pending == 0 && result.Held == 0)
                {
                    terminal = true;
                    Count("NO_EXECUTION");
                    break;
                }
            }
            if (!terminal) Count("CENSORED_AT_FOLD");
        }
        return new(labels.ToArray(), counts);
    }

    static NativeStructuralModels Fit(LabeledPhase train, LabeledPhase calibration, long availableAt)
    {
        var families = new Dictionary<string, NativeStructuralFamilyModel>(StringComparer.Ordinal);
        foreach (var family in train.Labels.GroupBy(x => x.Family))
        {
            var rows = family.Select(x => x.Sample).ToArray();
            var reference = new[] { 0m };
            var contextual = new NativeCompleteDistribution(rows, false);
            var pooled = new NativeCompleteDistribution(rows.Select(x => x with { Features = reference }).ToArray(), false);
            var calibrate = calibration.Labels.Where(x => x.Family == family.Key).Select(x => x.Sample).ToArray();
            int days = calibrate.Where(x => contextual.Predict(x.Features, x.DecisionAt, 1m) is not null)
                .Select(x => x.DecisionAt / NativeCompletePolicy.Day).Distinct().Count();
            families.Add(family.Key, new(contextual.Calibrate(calibrate),
                pooled.Calibrate(calibrate.Select(x => x with { Features = reference })), days));
        }
        return new(availableAt, families);
    }

    static object Forecasts(LabeledPhase phase, NativeStructuralModels models, string mode)
    {
        var values = phase.Labels.Select(x => (Label: x, Prediction: models.Predict(mode, x.Family, x.Sample.Features,
                x.Sample.DecisionAt, x.RiskEur))).Where(x => x.Prediction is not null).ToArray();
        decimal Actual(Label x) => x.Sample.OutcomeR * x.RiskEur;
        return new
        {
            Eligible = phase.Labels.Length, Scored = values.Length,
            MeanAbsoluteErrorEur = values.Length == 0 ? (decimal?)null :
                values.Average(x => Math.Abs(x.Prediction!.Mean - Actual(x.Label))),
            Brier = values.Length == 0 ? (decimal?)null : values.Average(x =>
            {
                decimal error = x.Prediction!.PositiveProbability - (Actual(x.Label) > 0m ? 1m : 0m);
                return error * error;
            })
        };
    }

    static NativeFundedLedger ReconcileLedger(LedgerEvent[] events, LedgerSummary summary)
    {
        var audit = new NativeFundedLedger();
        foreach (var fact in events) audit.Apply(fact);
        if (audit.Summary() != summary) throw new InvalidOperationException("CLOSED_MARKET_LEDGER_RECONCILIATION");
        return audit;
    }

    static object Book(NativeUnifiedPortfolioEngine engine, long start, long end,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        var summary = engine.ModelSummary;
        var events = engine.OriginalModelEvents;
        ReconcileLedger(events, summary);
        var trips = engine.CompleteModelTrips;
        var equity = engine.CommonBookEquityPath;
        var costs = new
        {
            Commission = trips.Sum(t => t.Integrated!.CommissionsEur),
            Spread = trips.Sum(t => t.Integrated!.SpreadEur),
            Slippage = trips.Sum(t => t.Integrated!.SlippageEur),
            Conversion = trips.Sum(t => t.Integrated!.ConversionEur)
        };
        decimal gross = trips.Sum(t => t.GrossEur);
        if (Math.Abs(gross - costs.Commission - costs.Spread - costs.Slippage - costs.Conversion -
            summary.ClosedNetEur) > .000000001m)
            throw new InvalidOperationException("CLOSED_MARKET_COST_RECONCILIATION");
        return new
        {
            Ledger = summary, GrossEur = gross, Costs = costs, Hard21 = trips.Length >= 21,
            WinRate = trips.Length == 0 ? (decimal?)null : (decimal)trips.Count(t => t.NetEur > 0m) / trips.Length,
            ExpectancyEur = trips.Length == 0 ? (decimal?)null : trips.Average(t => t.NetEur),
            WorstNetEur = trips.Length == 0 ? (decimal?)null : trips.Min(t => t.NetEur),
            MeanR = trips.Length == 0 ? (decimal?)null : trips.Average(t => t.R),
            StopRiskOverruns = trips.Count(t => t.NetEur < -t.EntryRiskEur),
            UnknownPathTrips = trips.Count(t => t.CrossedUnknownHistory),
            FinancingUnverifiedTrips = trips.Count(t => FinancingUnverified(t, contracts[t.Symbol])),
            UnknownEquityClocks = equity.Count(m => m.Held > 0 && m.EquityEur is null),
            MaxConcurrent = equity.Max(m => m.Held),
            MaxMarginEur = equity.Max(m => m.UsedMarginEur),
            ExitReasons = trips.GroupBy(t => t.ExitReason).ToDictionary(g => g.Key, g => g.Count()),
            BySymbol = trips.GroupBy(t => t.Symbol).ToDictionary(g => g.Key,
                g => new { Trades = g.Count(), NetEur = g.Sum(t => t.NetEur) }),
            Outcome = engine.OriginalOutcomeReport(start, start, start, end,
                "CLOSED_MARKET_PROTECTED_SOURCE", includeTrace: false),
            SettlementEvents = events.Where(e => e.Kind != "MARK").Select(e => e with { Quotes = Array.Empty<LedgerQuote>() }),
            SampledEquity = equity,
            LedgerReconciled = true
        };
    }

    static (object Report, decimal RealizedLedgerNet, decimal? CompleteModeledNet) DevelopmentBook(
        NativeUnifiedPortfolioEngine engine, long start, long end,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        var summary = engine.ModelSummary;
        var events = engine.OriginalModelEvents;
        var audit = ReconcileLedger(events, summary);
        var trips = engine.CompleteModelTrips;
        var equity = engine.CommonBookEquityPath;
        var fragments = audit.ClosedFragments();
        var positions = audit.PositionSnapshot();
        var pending = audit.PendingSnapshot();
        var finalCloses = fragments.Where(f => f.CompletesRoundTrip)
            .ToDictionary(f => f.PositionId, StringComparer.Ordinal);
        var byPosition = fragments.ToLookup(f => f.PositionId, StringComparer.Ordinal);
        const decimal tolerance = .000000001m;
        if (finalCloses.Count != trips.Length || trips.Select(t => t.PositionId).Distinct().Count() != trips.Length ||
            trips.Any(t => t.OpenAt < start || t.OpenAt >= t.CloseAt || t.CloseAt >= end ||
                !finalCloses.TryGetValue(t.PositionId, out var close) || close.ClosedAt != t.CloseAt ||
                Math.Abs(byPosition[t.PositionId].Sum(f => f.NetEur) - t.NetEur) > tolerance))
            throw new InvalidOperationException("POST415_COMPLETE_FUNDED_TRIP_RECONCILIATION");

        var costs = new
        {
            Commission = fragments.Sum(f => f.CommissionsEur),
            Spread = fragments.Sum(f => f.SpreadEur ?? 0m),
            Slippage = fragments.Sum(f => f.SlippageEur ?? 0m),
            Conversion = fragments.Sum(f => f.ConversionEur ?? 0m),
            Financing = fragments.Sum(f => f.FinancingEur)
        };
        decimal gross = fragments.Sum(f => f.GrossEur);
        decimal realized = summary.ClosedNetEur;
        decimal openCashAdjustments = positions.Sum(p =>
            p.FinancingRemaining - p.EntryFeeRemaining - p.EntryConversionRemaining);
        if (Math.Abs(gross - costs.Commission - costs.Spread - costs.Slippage -
            costs.Conversion - costs.Financing - realized) > tolerance ||
            Math.Abs(OwnerRiskAuthority.InitialCapitalEur + realized + openCashAdjustments - summary.CashEur) > tolerance)
            throw new InvalidOperationException("POST415_DEVELOPMENT_CASH_AND_COST_RECONCILIATION");

        var weekly = new Dictionary<string, int>(StringComparer.Ordinal);
        for (long from = start; from < end; from += NativeCompletePolicy.Week)
        {
            var day = DateTimeOffset.FromUnixTimeMilliseconds(from).UtcDateTime;
            string key = FormattableString.Invariant($"{ISOWeek.GetYear(day)}-W{ISOWeek.GetWeekOfYear(day):00}");
            weekly.Add(key, finalCloses.Values.Count(f => f.ClosedAt >= from && f.ClosedAt < from + NativeCompletePolicy.Week));
        }
        var hard21 = weekly.ToDictionary(w => w.Key, w => w.Value >= 21, StringComparer.Ordinal);
        bool censored = positions.Length > 0 || pending.Length > 0;
        decimal? completeModeledNet = censored ? null : realized;
        var report = new
        {
            Financial = new
            {
                Ledger = summary,
                GrossEur = gross,
                Costs = costs,
                RealizedLedgerNetEur = realized,
                CompletedTripNetEur = trips.Sum(t => t.NetEur),
                RealizedFromStillOpenPositionsEur = fragments.Where(f => !finalCloses.ContainsKey(f.PositionId)).Sum(f => f.NetEur),
                RemainingOpenCashAdjustmentsEur = openCashAdjustments,
                CompleteModeledNetEur = completeModeledNet,
                Boundary = new
                {
                    EndExclusiveAt = end,
                    LastSampledAt = equity[^1].At,
                    CashEur = summary.CashEur,
                    // The source stops before the boundary; a prior mark is only a sample.
                    LastSampledEquityEur = summary.LiquidationEquityEur,
                    EquityEur = positions.Length == 0 ? (decimal?)summary.CashEur : null,
                    RightCensored = censored,
                    CompleteModeledComparisonAvailable = !censored,
                    OpenPositions = positions.Select(p => new { p.Id, p.Symbol, p.Side, p.Units, p.EntryAt,
                        p.EntryFeeRemaining, p.EntryConversionRemaining, p.FinancingRemaining }).ToArray(),
                    PendingIntents = pending.Select(p => new { p.PositionId, p.Symbol, p.Kind, p.Side, p.Units, p.At }).ToArray()
                },
                StopRiskOverruns = trips.Count(t => t.NetEur < -t.EntryRiskEur),
                UnknownPathTrips = trips.Count(t => t.CrossedUnknownHistory),
                FinancingUnverifiedTrips = trips.Count(t => FinancingUnverified(t, contracts[t.Symbol])),
                UnknownEquityClocks = equity.Count(m => m.Held > 0 && m.EquityEur is null),
                MaxConcurrent = equity.Max(m => m.Held),
                MaxMarginEur = equity.Max(m => m.UsedMarginEur),
                MaxPlannedRiskEur = equity.Max(m => m.PlannedAggregateRiskEur),
                Outcome = engine.OriginalOutcomeReport(start, start, start, end,
                    "CLOSED_MARKET_PROTECTED_SOURCE", includeTrace: false),
                SettlementEvents = events.Where(e => e.Kind != "MARK")
                    .Select(e => e with { Quotes = Array.Empty<LedgerQuote>() }).ToArray(),
                RealizedFragments = fragments,
                SampledEquity = equity,
                LedgerReconciled = true
            },
            CompletedTradesByWeek = weekly,
            Hard21ByWeek = hard21,
            WeeksWithHard21 = hard21.Values.Count(meets => meets),
            BothWeeksHard21 = hard21.Values.All(meets => meets),
            ByFamily = trips.GroupBy(t => t.Family).ToDictionary(g => g.Key,
                g => new { Trades = g.Count(), NetEur = g.Sum(t => t.NetEur) })
        };
        return (report, realized, completeModeledNet);
    }

    public static object Run(Ucp1Frame[] frames, long start, long end,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        long week = NativeCompletePolicy.Week;
        if (end - start != 3 * week || frames.Length == 0)
            throw new ArgumentException("CLOSED_MARKET_CHRONOLOGY");
        var census = new Dictionary<string, int>(StringComparer.Ordinal);
        var offers = Offers(frames, census);
        var trainEnd = start + week;
        var calibrationEnd = trainEnd + week;
        var evaluationFrames = frames.Where(f => f.At >= calibrationEnd).ToArray();
        Offer[] Between(long low, long high) => offers.Where(o => frames[o.Index].At >= low && frames[o.Index].At < high).ToArray();
        var trainOffers = Between(start, trainEnd);
        var calOffers = Between(trainEnd, calibrationEnd);
        var evalOffers = Between(calibrationEnd, end);
        var offerEvidence = offers.Select(offer =>
        {
            var frame = frames[offer.Index];
            var market = frame.Markets.Single(m => m.Symbol == offer.Symbol);
            return new { frame.At, offer.Symbol, offer.Signal.Family, offer.Signal.Side, offer.Signal.DecisionBar,
                Windows = market.ClosedBars!.Windows
                    .Where(w => NativeClosedMarketContext.Duration(w.Timeframe) <= 3_600_000L)
                    .Select(w => new { Timeframe = w.Timeframe.ToString(), w.Source, w.RequiredBars,
                        FirstOpenAt = w.Bars[0].OpenAt, w.ExpectedCloseAt, w.WitnessAt, ValuesSha256 = w.ValuesSha256() }) };
        }).ToArray();
        object Scenario(string suffix)
        {
            var train = Labels(frames, trainOffers, trainEnd, suffix, contracts);
            var calibration = Labels(frames, calOffers, calibrationEnd, suffix, contracts);
            var models = Fit(train, calibration, calibrationEnd);
            var evaluation = Labels(frames, evalOffers, end, suffix, contracts);
            var books = new Dictionary<string, object>(StringComparer.Ordinal);
            var allNet = new Dictionary<string, decimal>(StringComparer.Ordinal);
            foreach (string variant in NativeStructuralOpportunity.Variants)
            {
                var engine = new NativeUnifiedPortfolioEngine(NativeStructuralOpportunity.Prefix + variant + suffix,
                    closedContextModels: models);
                foreach (var frame in evaluationFrames) engine.Advance(frame);
                allNet.Add(variant, engine.ModelSummary.ClosedNetEur);
                books.Add(variant, Book(engine, calibrationEnd, end, contracts));
            }
            return new
            {
                Training = train.Outcomes, Calibration = calibration.Outcomes, Evaluation = evaluation.Outcomes,
                CalibrationDays = models.Families.ToDictionary(x => x.Key, x => x.Value.CalibrationDays),
                ForecastEvaluation = new { Context = Forecasts(evaluation, models, "RANK"), Pooled = Forecasts(evaluation, models, "POOLED") },
                IncrementVsFirstEur = allNet.ToDictionary(x => x.Key, x => x.Value - allNet["FIRST"]),
                Books = books
            };
        }
        return new { start, trainEnd, calibrationEnd, end, Census = census, OfferEvidence = offerEvidence,
            Central = Scenario(""), Adverse = Scenario("_ADVERSE"), ExposedHistory = true,
            AssetFinancingAndDrawdownCertified = false, IndependentConfirmation = false, Orders = 0, CloudActivation = false };
    }

    // Distinct post-415 development only. The input may include W46 for custody,
    // but this method never advances any engine at or after the W45 boundary.
    // These two already exposed weeks are NOT an independent holdout.
    public static object RunExhaustionDevelopment(Ucp1Frame[] frames, long start, long end,
        IReadOnlyDictionary<string, NativeObservedContractTerms> contracts)
    {
        long week = NativeCompletePolicy.Week;
        if (end - start != 3 * week || start != 1792972800000L || frames.Length == 0)
            throw new ArgumentException("POST415_DEVELOPMENT_ORIGINAL_SOURCE_BOUNDARY");
        long developmentEnd = start + 2 * week; // [2026-10-26, 2026-11-09)
        var scoped = frames.Where(f => f.At >= start && f.At < developmentEnd).ToArray();
        if (scoped.Length == 0)
            throw new ArgumentException("POST415_DEVELOPMENT_COHORT_MISSING");

        var census = new Dictionary<string, int>(StringComparer.Ordinal);
        var seen = new Dictionary<string, long>(StringComparer.Ordinal);
        foreach (var frame in scoped)
            foreach (var market in frame.Markets)
            {
                if (!NativeStructuralOpportunity.ContextReady(market)) continue;
                long lastM5 = market.M5[^1].CloseAt;
                if (seen.GetValueOrDefault(market.Symbol) >= lastM5) continue;
                seen[market.Symbol] = lastM5;
                Add(census, "CAUSAL_CONTEXT/" + market.Symbol);
                var previous = NativeStructuralOpportunity.Describe(market);
                var exhaustion = NativeImpulseExhaustionResearch.Describe(market);
                if (previous is not null) Add(census, "LEGACY_MECHANISM/" + previous.Signal.Family + "/" + market.Symbol);
                if (exhaustion is not null) Add(census, "NEW_EXHAUSTION/" + market.Symbol);
                if (previous is not null && exhaustion is not null)
                    Add(census, "SIMULTANEOUS_FAMILIES/" + market.Symbol);
            }

        object Scenario(string suffix)
        {
            var books = new Dictionary<string, (object Report, decimal RealizedLedgerNet, decimal? CompleteModeledNet)>(
                StringComparer.Ordinal);
            foreach (var variant in new[] { "CASH", "FIRST", "RANDOM", "TREND",
                "REJECTION", "EXHAUSTION", NativeStructuralOpportunity.Combined,
                NativeStructuralOpportunity.CombinedRandom, NativeStructuralOpportunity.CombinedWithoutExhaustion })
            {
                var engine = new NativeUnifiedPortfolioEngine(
                    NativeStructuralOpportunity.Prefix + variant + suffix);
                foreach (var frame in scoped) engine.Advance(frame);
                books.Add(variant, DevelopmentBook(engine, start, developmentEnd, contracts));
            }
            var first = books["FIRST"];
            var combined = books[NativeStructuralOpportunity.Combined];
            var withoutExhaustion = books[NativeStructuralOpportunity.CombinedWithoutExhaustion];
            return new
            {
                Books = books.ToDictionary(b => b.Key, b => b.Value.Report, StringComparer.Ordinal),
                RealizedLedgerNetVsFirstEur = books.ToDictionary(b => b.Key,
                    b => b.Value.RealizedLedgerNet - first.RealizedLedgerNet, StringComparer.Ordinal),
                CompleteModeledNetVsFirstEur = books.ToDictionary(b => b.Key,
                    b => b.Value.CompleteModeledNet - first.CompleteModeledNet, StringComparer.Ordinal),
                FullBookExhaustionAblation = new
                {
                    Policy = NativeStructuralOpportunity.Combined,
                    Comparator = NativeStructuralOpportunity.CombinedWithoutExhaustion,
                    RealizedLedgerNetDifferenceEur = combined.RealizedLedgerNet - withoutExhaustion.RealizedLedgerNet,
                    CompleteModeledNetDifferenceEur = combined.CompleteModeledNet - withoutExhaustion.CompleteModeledNet
                },
                ForecastVerification = "NOT_TRAINED_IN_THIS_MECHANISM_ONLY_DEVELOPMENT_RUN" };
        }
        return new
        {
            SourceStart = start, OriginalSourceEnd = end, DevelopmentEnd = developmentEnd,
            W46AdvancedClocks = 0, W44W45PreviouslyExposed = true,
            IndependentConfirmation = false, BrokerNetCertified = false,
            CombinedSelection = "PLANNED_NET_TARGET_EUR_PER_RESERVED_STRESSED_RISK_EUR_THEN_FIXED_HASH",
            CombinedRandomSelection = "FIXED_HASH_OVER_ALL_FINANCEABLE_PROPOSALS",
            Orders = 0, CloudActivation = false, Census = census,
            Central = Scenario(""), Adverse = Scenario("_ADVERSE")
        };
    }
}
