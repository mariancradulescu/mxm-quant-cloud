using System.Text.Json;
using Mxm.Cloud;
using Mxm.Core;

internal static class NativeFundedActionChecks
{
    static Ucp1Frame Observation(long bar, long at, decimal bid = 100.60m)
    {
        var frame = NativeImpulseExhaustionChecks.Frame(bar, at);
        return frame with { Markets = new[] { NativeImpulseExhaustionChecks.Reprice(frame.Markets[0], bid) } };
    }

    static Ucp1FrameResult Probe(NativeUnifiedPortfolioEngine engine, Ucp1Frame frame, NativeFundedActionProbe probe)
        => engine.Advance(frame, NativeStructuralOpportunity.Describe, NativeImpulseExhaustionResearch.Describe, probe);

    static NativeFundedActionModel Fit(NativeFundedActionOffer offer, decimal outcome, bool adverse = false, bool addFuture = false)
    {
        long day = NativeCompletePolicy.Day;
        long fitEnd = offer.At - 7 * day;
        var fit = Enumerable.Range(1, 4).SelectMany(d => Enumerable.Range(0, 4).Select(i =>
            new NativeCompleteSample(offer.Symbol, fitEnd - d * day + i * 30_000,
                fitEnd - d * day + i * 30_000 + 1000, offer.Features, outcome))).ToArray();
        if (addFuture) fit[0] = fit[0] with { SettledAt = offer.At };
        var calibration = Enumerable.Range(1, 4).Select(d =>
            new NativeCompleteSample(offer.Symbol, fitEnd + d * day, fitEnd + d * day + 30_000, offer.Features, outcome)).ToArray();
        return NativeFundedActionResearch.BuildModel(new[] { (offer.Group, fit, calibration) }, fitEnd, offer.At - day, adverse);
    }

    public static void Run(Action<bool, string> check)
    {
        long bar = NativeFundedActionResearch.Start + 10 * 3_600_000L;
        var frames = new[] { Observation(bar, bar + 15_000), Observation(bar, bar + 45_000),
            Observation(bar, bar + 75_000, 99.4m), Observation(bar, bar + 105_000, 99.4m) };
        var contracts = frames[0].Markets.ToDictionary(m => m.Symbol, m => m.Contract, StringComparer.Ordinal);
        const string pilot = NativeStructuralOpportunity.Prefix + NativeFundedActionValue.First;
        var fitted = new List<NativeFundedActionModel>();
        foreach (string suffix in new[] { "", "_ADVERSE" })
        {
            var engine = new NativeUnifiedPortfolioEngine(pilot + suffix);
            string checkpoint = engine.Checkpoint();
            var capture = new NativeFundedActionProbe();
            Probe(engine, frames[0], capture);
            var offer = capture.Available.Single();
            var settled = NativeFundedActionResearch.Paired(checkpoint, offer, frames, 0, contracts);
            // A fork-only checkpoint must preserve every economic decision, settlement,
            // monetary chain and completed trip while avoiding unneeded diagnostics.
            var seed = NativeUnifiedPortfolioEngine.Restore(checkpoint);
            var leanLabel = NativeFundedActionResearch.Paired(
                seed.ActionForkCheckpoint(), offer, frames, 0, contracts);
            var fullLabel = NativeFundedActionResearch.Paired(
                seed.ActionForkCheckpoint(suppressResearchTrace: false), offer, frames, 0, contracts);
            check(leanLabel == fullLabel && fullLabel == settled,
                "diagnostic-free counterfactual forks preserve both funded decision outcomes");
            var lean = NativeUnifiedPortfolioEngine.Restore(seed.ActionForkCheckpoint());
            var full = NativeUnifiedPortfolioEngine.Restore(
                seed.ActionForkCheckpoint(suppressResearchTrace: false));
            foreach (var step in frames)
                check(lean.Advance(step) == full.Advance(step),
                    "counterfactual fork suppresses traces without changing any per-clock funded decision or chain");
            check(lean.ModelSummary == full.ModelSummary &&
                JsonSerializer.Serialize(lean.CompleteModelTrips) ==
                    JsonSerializer.Serialize(full.CompleteModelTrips) &&
                lean.CommonBookEquityPath.Length == 0 &&
                lean.OriginalModelEvents.Length == 0 &&
                full.CommonBookEquityPath.Length == frames.Length &&
                full.OriginalModelEvents.Length > 0,
                "fork numerical/trip parity holds while only redundant event and equity traces disappear");
            check(settled.DeltaEur > 0m && settled.At == frames[^1].At, "paired funded ENTER and WAIT settle at a later common flat mark");
            var truncated = NativeFundedActionResearch.Paired(checkpoint, offer, frames.Take(2).ToArray(), 0, contracts);
            check(truncated.Status == "RIGHT_CENSORED" && truncated.DeltaEur is null, "an unsettled funded branch cannot become a zero label");
            var model = Fit(offer, .25m, adverse: suffix != "");
            fitted.Add(model);
            check(model.Predict(NativeFundedActionValue.Context, offer with { At = model.AvailableAt }) is null,
                "the frozen model is unavailable at its calibration watermark");
            bool rejected = false;
            try { Fit(offer, .25m, addFuture: true); }
            catch (ArgumentException) { rejected = true; }
            check(rejected, "a label settled after the fit boundary is rejected");
            string policy = NativeStructuralOpportunity.Prefix + NativeFundedActionValue.Context + suffix;
            var replay = new NativeUnifiedPortfolioEngine(policy, actionModel: model);
            var adapter = new NativeUnifiedCloudParityAdapter(policy, actionModel: model);
            foreach (var frame in frames)
                check(replay.Advance(frame) == adapter.Observe(frame), "funded action adapter matches replay frame and monetary hash");
            check(replay.CompleteModelTrips.Length == 1 && replay.ModelSummary.ClosedNetEur == settled.DeltaEur &&
                JsonSerializer.Serialize(replay.FundedActionReceipts) == JsonSerializer.Serialize(adapter.FundedActions),
                "funded action forecast, selection, fill, closure and receipts match from identical frames");
            var restored = NativeUnifiedPortfolioEngine.Restore(replay.Checkpoint());
            check(restored.ModelSummary == replay.ModelSummary &&
                JsonSerializer.Serialize(restored.FundedActionReceipts) == JsonSerializer.Serialize(replay.FundedActionReceipts),
                "funded action model and receipts survive the existing checkpoint");
            var abstain = new NativeUnifiedPortfolioEngine(policy, actionModel: Fit(offer, -.20m, adverse: suffix != ""));
            check(abstain.Advance(frames[0]).Admitted == 0 && abstain.FundedActionReceipts.Single().Decision == "WAIT_NONPOSITIVE",
                "admission requires a positive calibrated incremental value");
        }

        CheckCompetingCapital(bar, pilot, check);
        CheckCrossSession(pilot, check);
        CheckHistoricalSchedule(check);
        CheckIndependentResearchCohorts(check);
        CheckGeneralState(check);
        var track = new NativeUnifiedPortfolioEngine(pilot);
        for (long at = bar + 15_000; at < bar + 900_000; at += 30_000)
            track.Advance(Observation(bar, at));
        string heldCheckpoint = track.Checkpoint();
        long later = bar + 900_000;
        var holdFrames = new[] { Observation(later, later + 15_000), Observation(later, later + 45_000),
            Observation(later, later + 75_000, 99.4m), Observation(later, later + 105_000, 99.4m) };
        var heldCapture = new NativeFundedActionProbe();
        Probe(track, holdFrames[0], heldCapture);
        var held = heldCapture.Available.Single(o => o.Kind == NativeFundedActionValue.Close);
        var comparison = NativeFundedActionResearch.Paired(heldCheckpoint, held, holdFrames, 0, contracts);
        check(comparison.DeltaEur < 0m && comparison.At == holdFrames[^1].At,
            "early exit versus continuation measures the difference after both books settle");

        var holdModel = Fit(held, .35m);
        var joint = fitted[0] with { Actions = fitted[0].Actions.Concat(holdModel.Actions).ToDictionary(x => x.Key, x => x.Value) };
        string withManagement = NativeStructuralOpportunity.Prefix + NativeFundedActionValue.Context;
        var learned = new NativeUnifiedPortfolioEngine(withManagement, actionModel: joint);
        var cloud = new NativeUnifiedCloudParityAdapter(withManagement, actionModel: joint);
        for (long at = bar + 15_000; at < later; at += 30_000)
        {
            var frame = Observation(bar, at);
            check(learned.Advance(frame) == cloud.Observe(frame), "holding path retains common replay-adapter state");
        }
        foreach (var frame in holdFrames)
            check(learned.Advance(frame) == cloud.Observe(frame), "valued exit yields the same funded book in both adapters");
        check(learned.FundedActionReceipts.Any(x => x.Decision == "CLOSE") &&
            learned.CompleteModelTrips.Single().ExitReason == "MODEL_UNTRANSMITTED_INTEGRATED_FUNDED_ACTION_VALUE_CLOSE",
            "the calibrated hold alternative can place a native conditional close intent");
    }

    static void CheckGeneralState(Action<bool, string> check)
    {
        long bar = NativeFundedActionResearch.Start + 10 * 3_600_000L;
        var frames = new[] { Observation(bar, bar + 15_000),
            Observation(bar, bar + 45_000),
            Observation(bar, bar + 75_000, 99.4m),
            Observation(bar, bar + 105_000, 99.4m) };
        var market = frames[0].Markets[0];
        var fresh = NativeGeneralOpportunity.Describe(market);
        check(fresh.Count(x => x.Signal.Family == NativeGeneralOpportunity.Distribution) == 2 &&
            fresh.Any(x => x.Signal.Family == NativeGeneralOpportunity.Distribution && x.Signal.Side == 1) &&
            fresh.Any(x => x.Signal.Family == NativeGeneralOpportunity.Distribution && x.Signal.Side == -1) &&
            fresh.All(x => NativeIntegratedLifecycle.ProtectionCompatible(
                x.Signal.Side, x.Signal.Stop, x.Signal.Target, market)),
            "general closed-state generator has both LONG and SHORT without detector trigger");
        var futureContext = market with
        {
            ClosedBars = market.ClosedBars! with { DecisionAt = market.Quote.At + 30_000 }
        };
        check(NativeGeneralOpportunity.Describe(futureContext).Length == 0 &&
            NativeGeneralOpportunity.Describe(market with { ClosedBars = null }).Length == 0,
            "the general generator refuses future context and missing closed bars");

        const string basePolicy = NativeStructuralOpportunity.Prefix;
        var first = new NativeUnifiedPortfolioEngine(basePolicy + NativeFundedActionValue.GeneralFirst);
        var capture = new NativeFundedActionProbe();
        string initial = first.ActionForkCheckpoint();
        Probe(first, frames[0], capture);
        check(capture.Available.Count(x => x.Kind == NativeFundedActionValue.Enter &&
                x.Family == NativeGeneralOpportunity.Distribution) == 2 &&
            capture.Available.Select(x => x.Side).Distinct().Count() == 2,
            "new funded offer path preserves both directions before the common allocator");
        var longOffer = capture.Available.First(x => x.Kind == NativeFundedActionValue.Enter &&
            x.Family == NativeGeneralOpportunity.Distribution && x.Side == 1);
        var contracts = frames[0].Markets.ToDictionary(x => x.Symbol, x => x.Contract, StringComparer.Ordinal);
        var label = NativeFundedActionResearch.Paired(initial, longOffer, frames, 0, contracts);
        check(label.Status == "SETTLED" && label.DeltaEur is not null && label.At > longOffer.At,
            "general ENTER versus WAIT uses future observed conditional fills and a common settled book");

        foreach (var suffix in new[] { "", "_ADVERSE" })
        {
            string policy = basePolicy + NativeFundedActionValue.GeneralContext + suffix;
            var model = Fit(longOffer, .25m, adverse: suffix.Length > 0);
            var core = new NativeUnifiedPortfolioEngine(policy, actionModel: model);
            var cloud = new NativeUnifiedCloudParityAdapter(policy, actionModel: model);
            foreach (var frame in frames)
                check(core.Advance(frame) == cloud.Observe(frame),
                    "general state policy reuses authoritative Core and observation-only Cloud finance");
            check(core.ModelSummary.OrdersEnabled == false &&
                core.ModelSummary.CompleteRoundTrips <= 1,
                "general policy never submits broker orders or creates a second portfolio");

            var noEdge = new NativeUnifiedPortfolioEngine(policy,
                actionModel: Fit(longOffer, -.25m, adverse: suffix.Length > 0));
            noEdge.Advance(frames[0]);
            check(noEdge.ModelSummary.PendingIntents == 0 &&
                noEdge.FundedActionReceipts.Any(x => x.Decision == "WAIT_NONPOSITIVE"),
                "negative uncertainty-adjusted general value abstains without forced HARD21 trades");
        }

        long week = NativeCompletePolicy.Week;
        var windows = new[]
        {
            new NativeFundedActionResearch.LabelWindow(bar, bar + week),
            new NativeFundedActionResearch.LabelWindow(bar + week, bar + 2 * week)
        };
        var counted = NativeFundedActionResearch.ObserveIndependentResearchCohorts(
            frames, new[] { windows[0] }, "", contracts, generalized: true);
        check(counted.IndependentCohorts?.Length == 1 &&
            counted.Phases[0].Counts.Keys.Any(k => k.Contains(NativeGeneralOpportunity.Distribution)) &&
            counted.Phases[0].Counts.Keys.Any(k => k.Contains("/LONG/")) &&
            counted.Phases[0].Counts.Keys.Any(k => k.Contains("/SHORT/")),
            "new label sampler tests both directions, retaining censored forks separately");
        check(!NativeFundedActionValue.Variants.Contains(NativeFundedActionValue.GeneralContext) &&
            NativeFundedActionValue.GeneralVariants.Contains(NativeFundedActionValue.GeneralContext),
            "frozen legacy variants are not silently replaced");
    }

    static void CheckCrossSession(string policy, Action<bool, string> check)
    {
        const long hour = 3_600_000;
        const long step = NativeIntegratedLifecycle.IntervalMs;
        long midnight = NativeFundedActionResearch.Start + NativeCompletePolicy.Day;
        long prior = midnight - hour;

        Ucp1Frame At(long clock, decimal bid = 100.60m, bool competitor = false)
        {
            var frame = Observation(clock < midnight ? prior : midnight, clock);
            var original = frame.Markets[0];
            var occupied = NativeImpulseExhaustionChecks.Reprice(original, bid, marginPerUnit: 600m);
            var alternative = NativeImpulseExhaustionChecks.Reprice(original, 100.60m, "GBPUSD", 400m);
            return frame with { Markets = competitor ? new[] { occupied, alternative } : new[] { occupied } };
        }
        var prefix = Enumerable.Range(0, (int)(hour / step)).Select(i => At(prior + 15_000 + i * step)).ToArray();
        var later = new[] { At(midnight + 15_000, competitor: true), At(midnight + 45_000, competitor: true),
            At(midnight + 75_000, 99.40m), At(midnight + 105_000, 99.40m) };
        var contracts = later[0].Markets.ToDictionary(m => m.Symbol, m => m.Contract, StringComparer.Ordinal);
        var firstWindow = new NativeFundedActionResearch.LabelWindow(prior, midnight);
        var secondWindow = new NativeFundedActionResearch.LabelWindow(midnight, midnight + hour);
        var frames = prefix.Concat(later).ToArray();
        var study = NativeFundedActionResearch.ObserveLabels(frames, new[] { firstWindow, secondWindow }, "", contracts);
        var uninterrupted = new NativeUnifiedPortfolioEngine(policy);
        var adapter = new NativeUnifiedCloudParityAdapter(policy);
        Ucp1FrameResult overnight = default!;
        bool prefixParity = true;
        foreach (var frame in prefix)
        {
            overnight = uninterrupted.Advance(frame);
            prefixParity &= overnight == adapter.Observe(frame);
        }
        check(prefixParity, "overnight replay and Cloud adapter prefix are identical");
        check(overnight.Held == 1 && overnight.ModelBook.UsedMarginEur == 150m && overnight.ModelBook.CashEur < 300m,
            "an overnight hold retains the funded inventory, entry cost and reserved margin");
        var preMidnight = uninterrupted.Checkpoint();
        var afterMidnight = uninterrupted.Advance(later[0]);
        var diagnostic = JsonSerializer.SerializeToElement(uninterrupted.OriginalOutcomeReport(prior, prior, prior,
            midnight + hour, "SYNTHETIC_TEST_ONLY", includeTrace: false));
        const string rejection = "RESERVED_MARGIN_BUDGET/GBPUSD";
        check(afterMidnight == adapter.Observe(later[0]) && afterMidnight.Held == 1 &&
            afterMidnight.ModelBook.UsedMarginEur == 150m &&
            diagnostic.GetProperty("reasons").TryGetProperty(rejection, out var count) && count.GetInt32() == 1,
            "capital reserved before midnight prevents a competing entry after midnight");
        foreach (var frame in later.Skip(1))
            check(uninterrupted.Advance(frame) == adapter.Observe(frame), "overnight settlement remains identical across adapters");
        check(study.PilotBook == uninterrupted.ModelSummary && study.PilotBook.CompleteRoundTrips == 1 &&
            study.Phases[0].Labels.Count == 0 && study.Phases[0].Counts.Single().Key.EndsWith("/RIGHT_CENSORED"),
            "the label cutoff censors the first fork while the same pilot closes later with identical cash and ledger hash");

        var nextDayLabel = study.Phases[1].Labels.Single();
        check(nextDayLabel.Offer.Kind == NativeFundedActionValue.Close && nextDayLabel.Offer.Symbol == "EURUSD" &&
            nextDayLabel.DeltaEur < 0m && nextDayLabel.SettledAt == later[^1].At,
            "next-day management values the inherited position at the later common settlement");
        var left = NativeUnifiedPortfolioEngine.Restore(preMidnight);
        Probe(left, later[0], new() { Close = nextDayLabel.Offer.Key });
        foreach (var frame in later.Skip(1)) left.Advance(frame);
        check(left.CompleteModelTrips.Single().CloseAt < uninterrupted.CompleteModelTrips.Single().CloseAt,
            "the two continuations settle on different clocks");
        var fenced = NativeFundedActionResearch.Paired(preMidnight, nextDayLabel.Offer, later, 0, contracts, later[^1].At);
        check(fenced.Status == "RIGHT_CENSORED" && fenced.DeltaEur is null && fenced.At == later[^2].At,
            "an observation exactly at the cutoff cannot settle a label");

        var laterMaturity = NativeFundedActionResearch.ObserveLabels(frames,
            new[] { firstWindow with { MaturityUntil = secondWindow.Until }, secondWindow }, "", contracts);
        var matured = laterMaturity.Phases[0].Labels.Single();
        check(matured.SettledAt >= secondWindow.From && matured.Offer.At < secondWindow.From &&
            laterMaturity.PilotBook == study.PilotBook,
            "an overnight label may mature later without changing the financial trajectory");

        var missingPath = later.ToArray();
        missingPath[1] = missingPath[1] with { Markets = Array.Empty<Ucp1MarketFrame>() };
        var unknown = NativeFundedActionResearch.Paired(preMidnight, nextDayLabel.Offer, missingPath, 0, contracts);
        check(unknown.DeltaEur is null && unknown.Status is "UNKNOWN_PATH_OR_MARK" or "RIGHT_CENSORED",
            "an absent held observation cannot produce an economic training value");

        var trailingIntent = prefix.ToArray();
        trailingIntent[^1] = At(midnight - 15_000, 99.40m);
        var heldIntent = NativeFundedActionResearch.ObserveLabels(trailingIntent, new[] { firstWindow }, "", contracts);
        var settledIntent = NativeFundedActionResearch.ObserveLabels(trailingIntent.Concat(later.Select(frame =>
            At(frame.At, 99.40m))).ToArray(), new[] { firstWindow, secondWindow }, "", contracts);
        check(heldIntent.PilotBook.OpenPositions == 1 && heldIntent.PilotBook.PendingIntents == 1 &&
            settledIntent.PilotBook.CompleteRoundTrips == 1 && settledIntent.PilotBook.PendingIntents == 0,
            "a protection intent pending before midnight settles in the inherited next-day book");

        var duringEmbargo = NativeFundedActionResearch.ObserveLabels(frames, new[] { secondWindow }, "", contracts);
        check(duringEmbargo.PilotBook == study.PilotBook && duringEmbargo.Phases[0].Labels.Single().DeltaEur == nextDayLabel.DeltaEur,
            "ineligible clocks and embargoes preserve the full financial state");

        var rolling = new NativeUnifiedPortfolioEngine(policy);
        var rollingAdapter = new NativeUnifiedCloudParityAdapter(policy);
        foreach (var frame in prefix)
        {
            rolling.Advance(frame);
            rollingAdapter.Observe(frame);
        }
        var model = Fit(nextDayLabel.Offer, -.20m) with { AvailableAt = midnight };
        var before = rolling.ModelSummary;
        rolling.UseFundedActionModel(model, later[0].At);
        rollingAdapter.UseFundedActionModel(model, later[0].At);
        check(rolling.ModelSummary == before && rolling.Advance(later[0]) == rollingAdapter.Observe(later[0]),
            "a causal model refresh preserves the funded inventory and uses the same adapter logic");
        bool stale = false;
        try { rolling.UseFundedActionModel(model, later[1].At); }
        catch (ArgumentException) { stale = true; }
        bool fromFuture = false;
        try { rolling.UseFundedActionModel(model with { AvailableAt = later[1].At }, later[1].At); }
        catch (ArgumentException) { fromFuture = true; }
        check(stale && fromFuture, "a stale or contemporaneously unavailable snapshot is rejected");
    }

    static void CheckHistoricalSchedule(Action<bool, string> check)
    {
        long start = new DateTimeOffset(2026, 8, 17, 0, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();
        long day = NativeCompletePolicy.Day, week = NativeCompletePolicy.Week;
        long end = start + 9 * week + day;
        var (windows, folds) = NativeFundedActionResearch.HistoricalSchedule(start + day, end);
        check(windows.Length == 8 && folds.Length == 6 && folds[0].FitEnd == start + 2 * week &&
            folds[0].CalibrationStart == folds[0].FitEnd && folds[0].From == start + 3 * week &&
            folds[^1].Until == start + 9 * week && windows.All(w => w.MaturityUntil == end),
            "historical folds use whole ISO weeks, past-only fit and calibration, and let earlier branches mature");
    }

    static void CheckIndependentResearchCohorts(Action<bool, string> check)
    {
        // The original continuous source runner stays unchanged. Only the new
        // explicitly chosen research sampler creates independent EUR300 pilot
        // experiments. Financial evaluation of actual candidate policies
        // must still carry a single book across all tested weeks.
        const long hour = 3_600_000L;
        long start = NativeFundedActionResearch.Start + 10 * hour;
        long week = NativeCompletePolicy.Week;
        Ucp1Frame[] WeekFrames(long bar) => new[]
        {
            Observation(bar, bar + 15_000),
            Observation(bar, bar + 45_000),
            Observation(bar, bar + 75_000, 99.4m),
            Observation(bar, bar + 105_000, 99.4m)
        };
        var first = WeekFrames(start);
        var second = WeekFrames(start + week);
        var windows = new[]
        {
            new NativeFundedActionResearch.LabelWindow(start, start + week),
            new NativeFundedActionResearch.LabelWindow(start + week, start + 2 * week)
        };
        var contracts = first[0].Markets.ToDictionary(m => m.Symbol, m => m.Contract, StringComparer.Ordinal);
        foreach (string suffix in new[] { "", "_ADVERSE" })
        {
            var jointlySampled = NativeFundedActionResearch.ObserveIndependentResearchCohorts(
                first.Concat(second).ToArray(), windows, suffix, contracts);
            var isolatedFirst = NativeFundedActionResearch.ObserveLabels(
                first, new[] { windows[0] }, suffix, contracts);
            var isolatedSecond = NativeFundedActionResearch.ObserveLabels(
                second, new[] { windows[1] }, suffix, contracts);
            check(jointlySampled.IndependentCohorts?.Length == 2 &&
                jointlySampled.IndependentCohorts[0].Book == isolatedFirst.PilotBook &&
                jointlySampled.IndependentCohorts[1].Book == isolatedSecond.PilotBook,
                "fixed research cohorts are separate actual EUR300 funding experiments");
            check(jointlySampled.Phases[0].Labels.Count > 0 &&
                jointlySampled.Phases[1].Labels.Count > 0 &&
                JsonSerializer.Serialize(jointlySampled.Phases[0].Labels) ==
                    JsonSerializer.Serialize(isolatedFirst.Phases[0].Labels) &&
                JsonSerializer.Serialize(jointlySampled.Phases[1].Labels) ==
                    JsonSerializer.Serialize(isolatedSecond.Phases[0].Labels) &&
                JsonSerializer.Serialize(jointlySampled.Phases[0].Counts) ==
                    JsonSerializer.Serialize(isolatedFirst.Phases[0].Counts) &&
                JsonSerializer.Serialize(jointlySampled.Phases[1].Counts) ==
                    JsonSerializer.Serialize(isolatedSecond.Phases[0].Counts),
                "independent cohort labels, outcomes and censure equal individually verified research weeks");
            var legacy = NativeFundedActionResearch.ObserveLabels(
                first.Concat(second).ToArray(), windows, suffix, contracts);
            check(legacy.IndependentCohorts is null,
                "original continuous pilot route is unchanged and separately identifiable");
        }
    }

    static void CheckCompetingCapital(long bar, string pilot, Action<bool, string> check)
    {
        Ucp1Frame ObservationWithCapital(long offset, decimal eurBid, decimal? gbpBid)
        {
            var frame = Observation(bar, bar + offset);
            var eur = NativeImpulseExhaustionChecks.Reprice(frame.Markets[0], eurBid, marginPerUnit: 600m);
            if (gbpBid is not decimal price) return frame with { Markets = new[] { eur } };
            var gbp = NativeImpulseExhaustionChecks.Reprice(frame.Markets[0], price, "GBPUSD", marginPerUnit: 400m);
            return frame with { Markets = new[] { eur, gbp } };
        }
        var frames = new[]
        {
            ObservationWithCapital(15_000, 100.60m, null), ObservationWithCapital(45_000, 100.60m, 100.60m),
            ObservationWithCapital(75_000, 99.40m, 100.60m), ObservationWithCapital(105_000, 99.40m, 99.20m),
            ObservationWithCapital(135_000, 99.40m, 99.20m)
        };
        var contracts = frames[1].Markets.ToDictionary(m => m.Symbol, m => m.Contract, StringComparer.Ordinal);
        var chosen = new NativeUnifiedPortfolioEngine(pilot);
        string checkpoint = chosen.Checkpoint();
        var capture = new NativeFundedActionProbe();
        Probe(chosen, frames[0], capture);
        foreach (var frame in frames.Skip(1)) chosen.Advance(frame);
        var alone = chosen.CompleteModelTrips.Single(t => t.Symbol == "EURUSD");
        var pair = NativeFundedActionResearch.Paired(checkpoint, capture.Available.Single(), frames, 0, contracts);
        check(pair.Status == "SETTLED" && pair.At == frames[^1].At && pair.DeltaEur < alone.NetEur,
            "paired WAIT can finance a competing instrument that the ENTER branch displaced");
    }
}
