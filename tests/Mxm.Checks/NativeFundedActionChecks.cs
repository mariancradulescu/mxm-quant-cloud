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
