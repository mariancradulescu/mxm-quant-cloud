using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;
using static Cpe1IntegratedEconomicChecks;

internal static class Cpe1RecoveryParityChecks
{
    const long M5 = 300_000;
    const long Day = 86_400_000;
    static readonly long Afternoon = new DateTimeOffset(2026, 11, 23, 14, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly long BeforeSwap = Afternoon + (7 * 60 + 45) * 60_000;

    static void Require(bool valid, string caseName)
    {
        if (!valid) throw new InvalidOperationException("CPE1_TECHNICAL_FIXTURE_" + caseName);
    }

    static string Hash<T>(T value) =>
        Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(value))).ToLowerInvariant();

    static Ucp1Frame At(long origin, int slot, decimal bid, bool unknownSwap = false) =>
        Frame(origin, origin + slot * M5, bid, unknownSwap);

    static Ucp1Frame Both(Ucp1Frame frame, decimal? secondMargin = null) =>
        frame with { Markets = new[] { frame.Markets[0], Named(frame.Markets[0], "GBPUSD", secondMargin) } };

    internal static Ucp1Frame[] FinancingFrames(bool unknown) =>
        new[] { At(BeforeSwap,1,100.95m,unknown), At(BeforeSwap,2,100.95m,unknown),
                At(BeforeSwap,3,100.11m,unknown), At(BeforeSwap,4,100.10m,unknown) }
        .Select(frame => frame with { Markets = new[] { frame.Markets[0] with {
            Contract = frame.Markets[0].Contract with { LongSwap = -1.2m, ShortSwap = -0.4m }
        } } }).ToArray();

    static object Trace(string scenario, Ucp1Frame[] frames, int[] restartAfter,
        Action<NativeUnifiedPortfolioEngine, Ucp1FrameResult[]> validate)
    {
        var engine = new NativeUnifiedPortfolioEngine("CPE1_ECONOMIC");
        var resumed = new NativeUnifiedPortfolioEngine("CPE1_ECONOMIC");
        var decisions = new Ucp1FrameResult[frames.Length];
        for (int i = 0; i < frames.Length; i++)
        {
            decisions[i] = engine.Advance(frames[i]);
            Require(resumed.Advance(frames[i]) == decisions[i], scenario + "_RESUMED_DECISION");
            if (restartAfter.Contains(i))
                resumed = NativeUnifiedPortfolioEngine.Restore(resumed.Checkpoint());
        }
        validate(engine, decisions);

        var events = engine.OriginalModelEvents;
        var ledger = new NativeFundedLedger();
        foreach (var fact in events) ledger.Apply(fact);
        Require(ledger.Summary() == engine.ModelSummary, scenario + "_LEDGER_RECONCILED");
        string checkpoint = engine.Checkpoint();
        Require(resumed.Checkpoint() == checkpoint, scenario + "_RESUMED_CHECKPOINT");
        return new
        {
            Scenario = scenario, Frames = frames.Length, Events = events.Length,
            Stops = events.Count(e => e.Kind == "CLOSE_FILL" && e.Reason.Contains("STOP", StringComparison.Ordinal)),
            FinancingFacts = events.Count(e => e.Kind == "FINANCING"),
            Completed = engine.CompleteModelTrips.Length,
            DecisionsSha256 = Hash(decisions), EventFactsSha256 = Hash(events),
            SettlementsSha256 = Hash(ledger.ClosedFragments()),
            BookSha256 = Hash(ledger.Checkpoint()),
            CheckpointSha256 = Hash(checkpoint), engine.ModelSummary.EventChainHash
        };
    }

    public static void WriteTrace()
    {
        var cases = new List<object>();
        var held = new[] { At(Afternoon,1,100.95m), Both(At(Afternoon,2,100.95m)),
                           Both(At(Afternoon,3,100.95m),250m), At(Afternoon,4,100.11m),
                           At(Afternoon,5,100.10m) };
        cases.Add(Trace("HeldPendingAndProtectiveClose", held, new[] { 0, 1, 3 }, (engine, decisions) =>
        {
            Require(decisions[1] is { Held:1, Pending:1 } &&
                    decisions[2] is { Held:1, Pending:0 }, "SHARED_FINANCING");
            Require(engine.OriginalModelEvents.Any(x => x.Kind == "MODEL_OPEN_INTENT_EXPIRED" &&
                x.Reason == "MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED"), "REPRICED_PENDING_REJECTED");
            Require(decisions[3] is { Held:1, Pending:1 } &&
                    decisions[4] is { Held:0, Pending:0 }, "PROTECTIVE_CLOSE_SETTLED_LATER");
        }));

        foreach (bool unknown in new[] { false, true })
        {
            cases.Add(Trace(unknown ? "UnknownSwap" : "KnownNonzeroSwap", FinancingFrames(unknown),
                new[] { 1, 2 }, (engine, _) =>
                {
                    var trip = engine.CompleteModelTrips.Single();
                    Require(trip.EconomicEvidence?.ConditionalNetKnown == !unknown &&
                            engine.Cpe1UnreconciledFunding == unknown, "SWAP_DISCLOSURE");
                    var financing = engine.OriginalModelEvents.Where(x => x.Kind == "FINANCING").ToArray();
                    Require(unknown ? financing.Length == 0 :
                        financing.Length == 1 && financing[0].SignedFinancingEur == -.00012m, "SWAP_CASH_FACT");
                    Require(trip.CloseAt == BeforeSwap + 4*M5, "SWAP_PROTECTIVE_CLOSE_CLOCK");
                }));
        }

        var gap = new[] { At(Afternoon,1,100.95m), At(Afternoon,2,100.95m), At(Afternoon,3,100.11m),
            new Ucp1Frame(Afternoon + 4*M5, Array.Empty<Ucp1MarketFrame>()), At(Afternoon,5,100.10m) };
        cases.Add(Trace("ObservationGap", gap, new[] { 2, 3 }, (engine, decisions) =>
        {
            Require(decisions[3] is { Held:1, Pending:1, ModelBook.LiquidationEquityEur:null },
                "GAP_RETAINS_EXPOSURE");
            Require(engine.CompleteModelTrips.Single().CrossedUnknownHistory &&
                    engine.ModelSummary.HistoryEvidenceIncomplete, "GAP_CENSORED");
        }));

        var learning = new List<Ucp1Frame>();
        for (int day = 0; day < 4; day++)
        for (int cycle = 0; cycle < 8; cycle++)
        {
            long origin = Afternoon + Day*day + 12*M5*cycle;
            learning.AddRange(new[] { At(origin,1,100.95m), At(origin,2,100.95m),
                At(origin,3,100.11m), At(origin,4,100.07m + .01m*(cycle%5)) });
        }
        cases.Add(Trace("CausalFamilyHistory", learning.ToArray(), new[] { 39, 77, 79 }, (engine, _) =>
        {
            var trips = engine.CompleteModelTrips;
            Require(trips.Length == 20 && trips.Select(t => t.CloseAt/Day).Distinct().Count() >= 3 &&
                    trips.All(t => t.EconomicEvidence is { ConditionalNetKnown:true, RealizedGrossR:<0m } &&
                                  !t.CrossedUnknownHistory), "THREE_DAY_LOWER_GROSS_GATE");
        }));
        Console.WriteLine(JsonSerializer.Serialize(cases));
    }
}
