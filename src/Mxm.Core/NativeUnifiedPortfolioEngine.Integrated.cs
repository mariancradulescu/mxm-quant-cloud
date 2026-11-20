using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed partial class NativeUnifiedPortfolioEngine
{
    sealed record FinancedCandidate(Ucp1MarketFrame Market, NativeIntegratedCandidate Signal,
        NativeIntegratedTerms Terms, NativeEntryThesis? Thesis, decimal ReservedRiskEur);

    Ucp1FrameResult AdvanceIntegrated(long at, Ucp1Frame frame)
    {
        var ledger = model.Ledger;
        var book = ledger.Summary(at);
        if (policy is "INTEGRATED_CASH" or NativeIntegratedLifecycle.Cash)
            return RecordIntegratedFrame(at, book);
        bool coherent = integratedCalibration is not null;
        bool economic = NativeIntegratedLifecycle.SelectsEconomically(policy);
        bool adverse = policy.EndsWith("_ADVERSE", StringComparison.Ordinal);
        if (integratedCalibration is not null && !integratedCalibration.Evaluation(at))
        {
            if (economic) integratedCalibration.Observe(frame, adverse);
            return RecordIntegratedFrame(at, book);
        }
        if (coherent && at % 60_000L != NativeIntegratedEconomicPolicy.ClockOffsetMs)
            return RecordIntegratedFrame(at, book);

        var markets = frame.Markets.ToDictionary(m => m.Symbol, StringComparer.Ordinal);
        var pending = ledger.PendingSnapshot().Where(f => f.Kind == "REQUEST_OPEN").ToArray();
        var occupied = ledger.PositionSnapshot().Select(f => f.Symbol)
            .Concat(pending.Select(f => f.Symbol)).ToHashSet(StringComparer.Ordinal);
        bool marksKnown = book.LiquidationEquityEur is not null && book.FreeMarginEur is not null
            && pending.All(f => markets.ContainsKey(f.Symbol));
        decimal equity = book.LiquidationEquityEur ?? 0m;
        decimal pendingMargin = pending.Where(f => markets.ContainsKey(f.Symbol))
            .Sum(f => f.Units * Math.Max(f.MarginPerUnit, markets[f.Symbol].Quote.MarginPerUnit));
        decimal usedMargin = book.UsedMarginEur ?? 0m;
        decimal marginBudget = Math.Max(0m, equity * .75m - usedMargin - pendingMargin);
        decimal committed = plans.Values.Sum(p => p.RiskEur);
        decimal riskBudget = Math.Max(0m, Math.Min(equity * .06m,
            equity - .70m * book.ObservedPeakEur) - committed);
        bool budgeted = policy.Contains("_BUDGET", StringComparison.Ordinal);
        var financeable = new List<FinancedCandidate>();

        foreach (var market in frame.Markets.OrderBy(m => m.Symbol, StringComparer.Ordinal))
        {
            if (market.Integrated is not { } evidence || market.M5.Length == 0)
                continue;
            long completedBar = market.M5[^1].CloseAt;
            if (at <= completedBar || completedBar <= lastSignalBar.GetValueOrDefault(market.Symbol))
                continue;
            lastSignalBar[market.Symbol] = completedBar;
            var signals = NativeIntegratedEconomicPolicy.Describe(market, at);
            foreach (var detected in signals.OrderBy(x => x.Family, StringComparer.Ordinal))
            {
                proposed++;
                string instrument = "/" + market.Symbol;
                Count("DETECTED" + instrument);
                var signal = detected;
                bool directionControl = policy is "INTEGRATED_LONG_MIN" or "INTEGRATED_SHORT_MIN"
                    or NativeIntegratedLifecycle.Long or NativeIntegratedLifecycle.Short;
                if (directionControl)
                {
                    int side = policy is "INTEGRATED_LONG_MIN" or NativeIntegratedLifecycle.Long ? 1 : -1;
                    decimal reference = market.M5[^1].Close;
                    signal = signal with { Side = side,
                        Stop = reference - side * Math.Abs(reference - signal.Stop),
                        Target = reference + side * Math.Abs(reference - signal.Target) };
                }
                var minimum = evidence.Volumes.FirstOrDefault(v => v.Units == market.Contract.MinimumUnits);
                var minTerms = minimum is null ? null :
                    NativeIntegratedEconomicPolicy.Terms(signal, market, minimum, adverse);
                if (minTerms is null)
                {
                    Count("GEOMETRY_DIRECTION_OR_CONTRACT_UNAVAILABLE" + instrument);
                    rejections++;
                    continue;
                }
                NativeEntryThesis? thesis = null;
                decimal reserved = minTerms.RiskEur;
                if (coherent)
                {
                    thesis = NativeIntegratedLifecycle.Freeze(signal, market, directionControl);
                    if (thesis is null || !NativeIntegratedLifecycle.ProtectionCompatible(
                        signal.Side, signal.Stop, signal.Target, market))
                    {
                        Count("ENTRY_THESIS_OR_PROTECTION_NOT_COMPATIBLE" + instrument);
                        rejections++;
                        continue;
                    }
                    Count((evidence.Protection is null ? "PROTECTION_DISTANCE_UNATTESTED" :
                        "PROTECTION_DISTANCE_CURRENT_SNAPSHOT_COMPATIBLE") + instrument);
                    reserved = NativeIntegratedLifecycle.StressedRisk(minTerms, signal.Volatility, market.Quote);
                }
                Count("LEGAL_MIN_WITH_COST_AND_MARGIN" + instrument);
                if (!marksKnown)
                {
                    Count("COMMON_MARK_UNKNOWN" + instrument);
                    rejections++;
                    continue;
                }
                decimal directionalMargin = signal.Side == 1 ? minimum!.BuyMargin : minimum!.SellMargin;
                decimal fee = 2m * Fee(market.Quote, minTerms.Units);
                if (directionalMargin + fee > book.FreeMarginEur!.Value - pendingMargin)
                {
                    Count("DIRECTIONAL_MIN_EXCEEDS_FREE_MARGIN" + instrument);
                    rejections++;
                    continue;
                }
                Count("MIN_WITHIN_AVAILABLE_MARGIN_AT_OBSERVED_TERMS" + instrument);
                if (occupied.Contains(market.Symbol) || evidence.Path?.Complete != true ||
                    book.MaximumSampledDrawdown >= .30m ||
                    minTerms.MarginEur + fee > marginBudget ||
                    reserved > Math.Min(riskBudget, .02m * equity))
                {
                    string reason = occupied.Contains(market.Symbol) ? "SYMBOL_ALREADY_EXPOSED" :
                        evidence.Path?.Complete != true ? "INCOMPLETE_CURRENT_PATH" :
                        minTerms.MarginEur + fee > marginBudget ? "RESERVED_MARGIN_BUDGET" : "JOINT_RISK_BUDGET";
                    Count(reason + instrument);
                    rejections++;
                    continue;
                }
                var terms = minTerms;
                if (budgeted)
                {
                    var affordable = evidence.Volumes.Select(v =>
                        NativeIntegratedEconomicPolicy.Terms(signal, market, v, adverse))
                        .OfType<NativeIntegratedTerms>()
                        .Where(v => v.RiskEur <= Math.Min(riskBudget, .01m * equity) &&
                                    v.MarginEur + 2m * Fee(market.Quote, v.Units) <= marginBudget)
                        .OrderBy(v => v.Units).ToArray();
                    if (affordable.Length > 0) terms = affordable[^1];
                }
                Count("PORTFOLIO_FEASIBLE" + instrument);
                financeable.Add(new(market, signal, terms, thesis, coherent ? reserved : terms.RiskEur));
            }
        }

        if (financeable.Count > 0)
        {
            Count("CLOCK_WITH_FINANCED_CHOICE");
            if (financeable.Count > 1) Count("CLOCK_WITH_COMPETING_CHOICES");
            if (financeable.Select(x => x.Market.Symbol).Distinct(StringComparer.Ordinal).Count() > 1)
                Count("CLOCK_WITH_COMPETING_SYMBOLS");
            if (economic)
            {
                for (int i = financeable.Count - 1; i >= 0; i--)
                {
                    var offer = financeable[i];
                    decimal reward = offer.Terms.RewardEur;
                    var p = integratedCalibration!.Probability(offer.Signal.Family, reward, offer.ReservedRiskEur);
                    decimal? edge = p is decimal rate
                        ? NativeIntegratedLifecycle.EstimatedEdge(rate, reward, offer.ReservedRiskEur) : null;
                    if (edge is > 0m)
                    {
                        financeable[i] = offer with { Thesis = offer.Thesis! with {
                            ProbabilityLower = p, EstimatedEdgeAtAdmissionEur = edge } };
                    }
                    else
                    {
                        string reason = reward <= 0m ? "NET_TARGET_NONPOSITIVE" :
                            p is null ? "BARRIER_EVIDENCE_INSUFFICIENT" : "ESTIMATED_EDGE_NONPOSITIVE";
                        Count(reason + "/" + offer.Market.Symbol);
                        rejections++;
                        financeable.RemoveAt(i);
                    }
                }
                if (financeable.Count == 0) return RecordIntegratedFrame(at, book);
                Count("CLOCK_WITH_POSITIVE_ECONOMIC_OFFER");
            }
            var selected = economic
                ? financeable.OrderByDescending(x => x.Thesis!.EstimatedEdgeAtAdmissionEur).First()
                : policy.Contains("_STRUCTURE_", StringComparison.Ordinal)
                    ? financeable.OrderByDescending(x => x.Terms.RewardEur / x.Terms.RiskEur).First()
                    : policy is "INTEGRATED_RANDOM_MIN" or NativeIntegratedLifecycle.Random
                        ? financeable.OrderBy(x => Sha((coherent ? "OWNER_INTEGRATED_LIFECYCLE/" : "20261120/") +
                            at + "/" + x.Market.Symbol + "/" + x.Signal.Family + "/" + x.Signal.Side),
                            StringComparer.Ordinal).First()
                        : financeable[0];
            var signal = selected.Signal;
            var market = selected.Market;
            var terms = selected.Terms;
            string id = "UCP1/" + policy + "/" + market.Symbol + "/" + signal.Family + "/" + at;
            Apply(Event("REQUEST_OPEN", at, id, market.Symbol, signal.Side, terms.Units,
                margin: market.Quote.MarginPerUnit, slip: terms.ExecutionSlippage,
                reason: "NATIVE_CONDITIONAL_SELECTION"));
            plans.Add(id, new(id, market.Symbol, signal.Family, signal.Side,
                signal.Volatility, signal.Target, selected.ReservedRiskEur, signal.Stop, 0m, 0, 0m,
                terms.Units, 0m, 0m, 0, false,
                new NativeIntegratedPlan(signal.Stop, signal.Target, terms.RiskEur, terms.RewardEur)
                    { Thesis = selected.Thesis, EntrySlippage = coherent ? terms.ExecutionSlippage : null }));
            admitted++;
            Count("ADMITTED/" + market.Symbol);
        }
        return RecordIntegratedFrame(at, ledger.Summary(at));
    }

    Ucp1FrameResult RecordIntegratedFrame(long at, LedgerSummary summary)
    {
        previousClock = at;
        curve.Add(new Ucp1CurvePoint(at, summary.CashEur, summary.LiquidationEquityEur, summary.UsedMarginEur,
            summary.OpenPositions, summary.PendingIntents, summary.CompleteRoundTrips)
            { PlannedAggregateRiskEur=plans.Values.Sum(p=>p.RiskEur) });
        return new(policy, at, summary, proposed, admitted, openFills, trips.Count,
            summary.PendingIntents, summary.OpenPositions, lastBrokerEvidence, summary.EventChainHash);
    }

    bool IntegratedFillStillAdmissible(Ucp1Plan plan, Ucp1MarketFrame input, LedgerSummary summary, decimal execution)
    {
        var entry = plan.Integrated!;
        var q = input.Quote;
        if (input.Integrated?.Path?.Complete != true || summary.LiquidationEquityEur is not decimal equity ||
            summary.UsedMarginEur is not decimal used || summary.MaximumSampledDrawdown >= .30m ||
            plan.Side * (execution - entry.Stop) <= 0m ||
            plan.Side * (entry.Target - execution) <= 0m ||
            (plan.Side > 0 ? q.Bid <= entry.Stop : q.Ask >= entry.Stop))
            return false;
        decimal fee = 2m * Fee(q, plan.Units);
        decimal risk = (plan.Side * (execution - entry.Stop) + q.Ask - q.Bid)
            * plan.Units * q.EurDebit + fee;
        decimal allRisk = plans.Values.Sum(p => p.RiskEur) - plan.RiskEur + risk;
        return risk <= Math.Min(entry.InitialRiskEur * 1.10m, equity * .02m) &&
            allRisk <= Math.Min(equity * .06m, equity - .70m * summary.ObservedPeakEur) &&
            used + plan.Units * q.MarginPerUnit + fee <= equity * .75m;
    }

    NativeIntegratedPlan? CoherentFill(Ucp1Plan plan, Ucp1MarketFrame input, LedgerSummary summary,
        decimal execution)
    {
        var geometry = plan.Integrated!;
        var q = input.Quote;
        if (input.Integrated?.Path?.Complete != true || summary.LiquidationEquityEur is not decimal equity ||
            summary.UsedMarginEur is not decimal used || summary.FreeMarginEur is not decimal free ||
            summary.MaximumSampledDrawdown >= .30m || plan.Side * (geometry.Target - execution) <= 0m ||
            !NativeIntegratedLifecycle.ProtectionCompatible(plan.Side, geometry.Stop, geometry.Target, input))
            return null;
        var thesis = NativeIntegratedLifecycle.AtFill(geometry.Thesis!, plan.Side, input);
        if (thesis is null) return null;
        var terms = NativeIntegratedLifecycle.Revalue(new(plan.Units, geometry.InitialRiskEur,
            geometry.InitialRewardEur, plan.Units * q.MarginPerUnit, geometry.EntrySlippage!.Value),
            plan.Side, geometry.Stop, geometry.Target, input);
        decimal stressed = NativeIntegratedLifecycle.StressedRisk(terms, plan.Atr, q);
        decimal usedRisk = plans.Values.Sum(p => p.RiskEur) - plan.RiskEur;
        decimal fee = 2m * Fee(q, plan.Units);
        if (stressed > equity * .02m ||
            usedRisk + stressed > Math.Min(equity * .06m, equity - .70m * summary.ObservedPeakEur) ||
            terms.MarginEur + fee > Math.Min(free, equity * .75m - used))
            return null;
        if (NativeIntegratedLifecycle.SelectsEconomically(policy))
        {
            var p = integratedCalibration!.Probability(plan.Family, terms.RewardEur, stressed);
            if (terms.RewardEur <= 0m || p is not decimal rate) return null;
            var edge = NativeIntegratedLifecycle.EstimatedEdge(rate, terms.RewardEur, stressed);
            if (edge <= 0m) return null;
            thesis = thesis with { EstimatedEdgeAtFillEur = edge };
        }
        return geometry with { InitialRiskEur = terms.RiskEur, InitialRewardEur = terms.RewardEur,
            Thesis = thesis with { StressedRiskAtFillEur = stressed } };
    }

    bool CoherentDeRisk(LedgerSummary summary)
    {
        if (summary.OpenPositions == 0 || summary.LiquidationEquityEur is not decimal equity ||
            summary.UsedMarginEur is not decimal used) return false;
        decimal heldRisk = plans.Values.Where(x => x.OpenAt > 0L).Sum(x => x.RiskEur);
        return summary.MaximumSampledDrawdown >= .30m || used > equity * .75m ||
            equity - summary.ObservedPeakEur * .70m <= heldRisk;
    }

    static (Ucp1Plan, NativeModelCloseInstruction?) ManageIntegrated(Ucp1Plan plan,
        LedgerPosition position, Ucp1MarketFrame market, bool deRisk)
    {
        var geometry = plan.Integrated!;
        var q = market.Quote;
        var path = market.Integrated?.Path;
        int side = position.Side;
        decimal now = side > 0 ? q.Bid : q.Ask;
        decimal low = side > 0 ? path?.BidLow ?? now : path?.AskLow ?? now;
        decimal high = side > 0 ? path?.BidHigh ?? now : path?.AskHigh ?? now;
        decimal adverse = side > 0 ? low : high;
        decimal favorable = side > 0 ? high : low;
        bool stopped = side * (adverse - geometry.Stop) <= 0m;
        bool rewarded = side * (favorable - geometry.Target) >= 0m;
        if (geometry.FirstBarrier == "" && (stopped || rewarded))
            geometry = geometry with { FirstBarrier = stopped && rewarded ? "AMBIGUOUS_BOTH" :
                stopped ? "INVALIDATION_FIRST" : "TARGET_FIRST" };
        decimal Move(decimal price)
        {
            decimal change = side * (price - plan.Entry) - position.SlippagePerSide;
            return change * position.Units * (change >= 0m ? q.EurCredit : q.EurDebit);
        }
        plan = plan with { MfeEur = Math.Max(plan.MfeEur, Move(favorable)),
            MaeEur = Math.Min(plan.MaeEur, Move(adverse)), Integrated = geometry };
        bool adaptiveStop = false;
        if (geometry.Thesis is { } thesis)
        {
            decimal stop = NativeCausalExitResearch.AdaptivePathStop(side, plan.Entry, geometry.Stop,
                plan.Extreme, plan.Atr);
            adaptiveStop = side * (adverse - stop) <= 0m;
            geometry = geometry with { Thesis = NativeIntegratedLifecycle.Observe(thesis, side, plan.OpenAt, market) };
            plan = plan with { Integrated = geometry,
                Extreme = side > 0 ? Math.Max(plan.Extreme, favorable) : Math.Min(plan.Extreme, favorable) };
        }
        if (stopped) return (plan, new("INTEGRATED_OBSERVED_INVALIDATION", position.Units));
        if (adaptiveStop) return (plan, new("INTEGRATED_ADAPTIVE_PATH_STOP", position.Units));
        if (rewarded) return (plan, new("INTEGRATED_OBSERVED_TARGET", position.Units));
        if (geometry.ProtectedLevel != 0m && side * (adverse - geometry.ProtectedLevel) <= 0m)
            return (plan, new("INTEGRATED_PROTECT_ACCUMULATED_GAIN", position.Units));

        if (geometry.Thesis is not null && deRisk)
            return (plan, new("INTEGRATED_COMMON_BOOK_RISK_REDUCTION", position.Units));
        if (geometry.Thesis is { InvalidatingM15CloseAt: > 0L })
            return (plan, new("INTEGRATED_NEW_M15_THESIS_INVALIDATION", position.Units));

        if (side * (now - plan.Entry) * 2m >= side * (geometry.Target - plan.Entry))
        {
            decimal fee = Fee(q, position.Units);
            decimal protectedLevel = plan.Entry + side * (position.SlippagePerSide +
                (position.EntryFeeRemaining + fee) / (position.Units * q.EurCredit));
            if (side * (now - protectedLevel) > 0m &&
                (geometry.ProtectedLevel == 0m || side * (protectedLevel - geometry.ProtectedLevel) > 0m))
                plan = plan with { Integrated = geometry with { ProtectedLevel = protectedLevel } };
            decimal reduce = market.Contract.MinimumUnits;
            decimal remaining = position.Units - reduce;
            if (!geometry.Reduced && remaining >= reduce &&
                (remaining - reduce) % market.Contract.VolumeStepUnits == 0m &&
                side * (now - protectedLevel) > 0m)
                return (plan, new("INTEGRATED_FAVORABLE_REDUCTION", reduce));
        }
        return (plan, null);
    }

    Ucp1Episode CompleteIntegrated(Ucp1Episode trip, Ucp1Plan plan)
    {
        var geometry = plan.Integrated!;
        var parts = model.Ledger.ClosedFragments().Where(f => f.PositionId == trip.PositionId).ToArray();
        decimal gross = parts.Sum(f => f.GrossEur);
        decimal net = parts.Sum(f => f.NetEur);
        decimal r = net / geometry.InitialRiskEur;
        return trip with { Units = parts.Sum(f => f.Units), GrossEur = gross, NetEur = net,
            EntryRiskEur = geometry.InitialRiskEur, R = r, Integrated = new(
                geometry.InitialRewardEur, geometry.InitialRewardEur / geometry.InitialRiskEur, r,
                geometry.FirstBarrier == "" ? "UNOBSERVED_BEFORE_OTHER_EXIT" : geometry.FirstBarrier,
                trip.CrossedUnknownHistory, geometry.Reduced, trip.SampledMfeEur > 0m ? gross / trip.SampledMfeEur : 0m,
                parts.Sum(f => f.CommissionsEur), parts.Sum(f => f.SpreadEur ?? 0m),
                parts.Sum(f => f.SlippageEur ?? 0m), parts.Sum(f => f.ConversionEur ?? 0m))
                { Thesis = geometry.Thesis } };
    }
}
