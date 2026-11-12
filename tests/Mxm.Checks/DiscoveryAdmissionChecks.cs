using Mxm.Core;

// A manufactured market with an independently specified payoff.
// Calibration learns from quote paths and never receives forecast fixtures.
public static class DiscoveryAdmissionChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long step = 300000;
        const long week = 7 * 86400000L;
        long first = DateTimeOffset.Parse("2026-01-05T08:00:01.500Z").ToUnixTimeMilliseconds();
        long evaluation = first + 6 * week;
        const string custody = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

        NativeProductMarket Market(string symbol, long at, int tick, decimal margin, decimal spread)
        {
            NativeClosedMarketBar[] Bars(long period)
            {
                long end = at / period * period;
                return Enumerable.Range(0, 33).Select(i =>
                {
                    decimal open = 99m + .025m * i;
                    long start = end - (33 - i) * period;
                    return new NativeClosedMarketBar(start,start + period,open,open + .022m,
                        open - .002m,open + .020m,100);
                }).ToArray();
            }
            var contract = new NativeObservedContractTerms(symbol,"USD",at,1,1,1,1,2,0,
                1,0,"USD",0,0,0,0,2,24,1320,3,false,0,true,false);
            decimal mid = 100m + .50m * tick;
            var quote = NativeBrokerContractCosts.Quote(contract,
                new(at,mid - spread / 2,mid + spread / 2,1m,1m,1m,null,margin,1m,.001m));
            return new(symbol,Bars(step),Bars(3 * step),quote.Quote,contract,.001m,45,false,
                NativeCausalExitResearch.Chandelier);
        }

        NativeProductMarket[] Frame(long at, int tick, decimal secondMargin = 20m, decimal spread = .01m)
        {
            return new[] { Market("AUDUSD",at,tick,20m,spread),
                Market("NZDUSD",at,tick,secondMargin,spread), Market("EURUSD",at,tick,20m,.01m) };
        }

        var calibration = new NativeProductResearchLoop("DCP1_CASH",evaluation);
        for (int w = 0; w < 6; w++)
        for (int tick = 0; tick < 23; tick++)
        {
            long at = first + w * week + tick * step;
            calibration.Advance(at,Frame(at,tick),false);
        }
        calibration.Advance(evaluation,Frame(evaluation,0),false);
        var report = calibration.CalibrationReport!;
        var fitted = NativeIntegratedSnapshot.Open(report.FrozenModel!);
        var fx = fitted.Conditional!["FX/HIGH"];
        check(report.TrainingPairs >= 12 && fx is {TrainingDays:6,StandaloneAdverseNetReturn:>0m,
            IncrementalAdverseNetReturn:>0m} && fx.OutcomesKnownThrough < evaluation,
            "admission audit learns positive executable outcomes from six strictly earlier weekly blocks");

        NativeIntegratedSnapshot Only(NativeEntryForecast? estimate) => fitted with
        {
            Conditional = fitted.Conditional!.ToDictionary(p => p.Key,
                p => p.Key == "FX/HIGH" ? estimate : p.Value)
        };

        NativeProductResearchLoop Loop(NativeEntryForecast? estimate) =>
            new("DCP1_JOINT",evaluation,Only(estimate));

        var funded = Loop(fx);
        var start = funded.Advance(evaluation,Frame(evaluation,0),false);
        var open = funded.Advance(evaluation+step,Frame(evaluation+step,1),false);
        check(start.AcceptedModelIntents == 2 && start.ModelPendingIntents == 2 &&
            open.ModelOpenPositions == 2 && funded.ResearchSession.Ledger.Summary().UsedMarginEur == 40m,
            "two predicted positive opportunities are financed at valid minimum units in one EUR300 book");
        var restored = NativeProductResearchLoop.RestoreIntegrityCheckpoint(
            funded.ExportIntegrityCheckpoint(custody),custody);
        for (int tick = 2; tick < 23; tick++)
        {
            long at = evaluation + tick * step;
            var one = funded.Advance(at,Frame(at,tick),false);
            var two = restored.Advance(at,Frame(at,tick),false);
            check(one.LatestSignals.SequenceEqual(two.LatestSignals) && one.ModelCashEur == two.ModelCashEur &&
                one.ModelEquityEur == two.ModelEquityEur,"admission audit restart preserves decisions and equity");
        }
        var settled = funded.ResearchSession.Ledger.ClosedFragments();
        check(settled.Length >= 2 && settled.All(x => x.Units == 1m && x.NetEur > 0m) &&
            funded.AdverseScenario.Summary is {CashEur:>300m} &&
            settled.SequenceEqual(restored.ResearchSession.Ledger.ClosedFragments()),
            "known favorable synthetic payoff settles positively after costs in both books");

        var unavailable = Loop(null).Advance(evaluation,Frame(evaluation,0),false);
        var uncertain = Loop(fx! with {MeanUncertaintyReturn=.20m})
            .Advance(evaluation,Frame(evaluation,0),false);
        var noEdge = Loop(fx with {StandaloneAdverseNetReturn=0m})
            .Advance(evaluation,Frame(evaluation,0),false);
        var expensive = Loop(fx).Advance(evaluation,Frame(evaluation,0,spread:4m),false);
        check(unavailable.AcceptedModelIntents==0 && unavailable.LatestSignals.All(s=>s.Status=="MODEL_CALIBRATION_UNAVAILABLE"),
            "absent or prefiltered calibration does not reach sizing");
        check(uncertain.AcceptedModelIntents==0 && uncertain.LatestSignals.All(s=>
            s.DecisionReason=="NO_EUR_EDGE_AFTER_COST_AND_UNCERTAINTY"),
            "uncertainty alone prevents reservation");
        check(noEdge.AcceptedModelIntents==0 && noEdge.LatestSignals.All(s=>
            s.DecisionReason=="PROSPECTIVE_NO_STANDALONE_NET_AFTER_COST_AND_UNCERTAINTY"),
            "nonpositive standalone edge prevents reservation");
        check(expensive.AcceptedModelIntents==0 && expensive.LatestSignals.All(s=>
            s.DecisionReason=="NO_EUR_EDGE_AFTER_COST_AND_UNCERTAINTY"),
            "executable spread alone prevents reservation");

        var constrained = Loop(fx).Advance(evaluation,Frame(evaluation,0,secondMargin:295m),false);
        check(constrained.AcceptedModelIntents == 1 && constrained.ModelPendingIntents == 1,
            "shared margin rejects competing executable demand above EUR300");
        var risky = Loop(fx with {DownsideReturn=1m}).Advance(evaluation,Frame(evaluation,0),false);
        check(risky.AcceptedModelIntents==0 && risky.ModelCashEur==300m,
            "loss scenario above the drawdown limit rejects a positive expected return");
        Console.WriteLine("MXM_DISCOVERY_SYNTHETIC_ADMISSION=" + System.Text.Json.JsonSerializer.Serialize(new {
            report.TrainingPairs, ConcurrentPositions=open.ModelOpenPositions, MarginEur=40,
            SettledFragments=settled.Length, CentralClosedNetEur=settled.Sum(x=>x.NetEur),
            AdverseCashEur=funded.AdverseScenario.Summary?.CashEur,
            CostRejections=expensive.LatestSignals.Select(s=>s.DecisionReason),
            MarginRejections=constrained.LatestSignals.Select(s=>s.DecisionReason),
            RiskRejections=risky.LatestSignals.Select(s=>s.DecisionReason),
            Synthetic=true, OrdersSubmitted=0
        }));
    }
}
