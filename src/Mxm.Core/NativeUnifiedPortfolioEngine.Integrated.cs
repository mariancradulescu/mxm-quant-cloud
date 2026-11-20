using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed partial class NativeUnifiedPortfolioEngine
{
    sealed record FinancedCandidate(Ucp1MarketFrame Market, NativeIntegratedCandidate Signal,
        NativeIntegratedTerms Terms, NativeEntryThesis? Thesis, decimal ReservedRiskEur, NativeCompleteEntry? Complete = null);

    static IEnumerable<NativeStructuralSetup> StructuralSetups(string variant, Ucp1MarketFrame market,
        Func<Ucp1MarketFrame, NativeStructuralSetup?> describeLegacy,
        Func<Ucp1MarketFrame, NativeStructuralSetup?> describeExhaustion)
    {
        if (variant != "EXHAUSTION" && describeLegacy(market) is { } legacy)
            yield return legacy;
        if (((variant is "EXHAUSTION" or NativeStructuralOpportunity.Combined or NativeStructuralOpportunity.CombinedRandom) ||
            NativeFundedActionValue.IsVariant(variant) && variant != NativeFundedActionValue.WithoutExhaustion) &&
            describeExhaustion(market) is { } exhaustion)
            yield return exhaustion;
    }

    static string CompetitionOrder(long at, FinancedCandidate offer) => Sha(FormattableString.Invariant(
        $"POST415_PROSPECTIVE_COMBINED/{at}/{offer.Market.Symbol}/{offer.Signal.Family}/{offer.Signal.Side}"));

    Ucp1FrameResult AdvanceIntegrated(long at, Ucp1Frame frame,
        Func<Ucp1MarketFrame, NativeStructuralSetup?> describeLegacy,
        Func<Ucp1MarketFrame, NativeStructuralSetup?> describeExhaustion,
        NativeFundedActionProbe? actionProbe)
    {
        var ledger = model.Ledger;
        var book = ledger.Summary(at);
        if (policy is "INTEGRATED_CASH" or NativeIntegratedLifecycle.Cash)
            return RecordIntegratedFrame(at, book);
        bool coherent = CoherentIntegrated;
        string variant = StructuralPolicy ? NativeStructuralOpportunity.Variant(policy) :
            CompletePolicy ? NativeCompletePolicy.Variant(policy) : "";
        bool competition = StructuralPolicy && NativeStructuralOpportunity.IsCompetition(variant);
        bool fundedValue = StructuralPolicy && NativeFundedActionValue.IsVariant(variant);
        if (variant is "CASH" or NativeFundedActionValue.Cash || CompletePolicy && !NativeCompletePolicy.IsDecision(at) ||
            ExecutableBracketTerms && completeProbe is { } probe && at != probe.At)
            return RecordIntegratedFrame(at, book);
        bool economic = NativeIntegratedLifecycle.SelectsEconomically(policy);
        bool adverse = policy.EndsWith("_ADVERSE", StringComparison.Ordinal);
        if (integratedCalibration is not null && !integratedCalibration.Evaluation(at))
        {
            if (economic) integratedCalibration.Observe(frame, adverse);
            return RecordIntegratedFrame(at, book);
        }
        if (coherent && !StructuralPolicy && at % 60_000L != NativeIntegratedEconomicPolicy.ClockOffsetMs)
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
            if (market.Integrated is not { } evidence || market.M5.Length == 0 ||
                StructuralPolicy && !NativeStructuralOpportunity.ContextReady(market))
                continue;
            long completedBar = market.M5[^1].CloseAt;
            if (at <= completedBar || completedBar <= lastSignalBar.GetValueOrDefault(market.Symbol))
                continue;
            lastSignalBar[market.Symbol] = completedBar;
            if (completeProbe is { } desired && market.Symbol != desired.Symbol) continue;
            var offers = StructuralPolicy
                ? StructuralSetups(variant, market, describeLegacy, describeExhaustion)
                    .Select(setup => (Signal: setup.Signal, Setup: (NativeStructuralSetup?)setup))
                : (CompletePolicy ? NativeCompletePolicy.Describe(market, at) : NativeIntegratedEconomicPolicy.Describe(market, at))
                    .Select(signal => (Signal: signal, Setup: (NativeStructuralSetup?)null));
            foreach (var (detected, setup) in offers.OrderBy(x => x.Signal.Family, StringComparer.Ordinal))
            {
                if (CompletePolicy && (variant == "LONG" && detected.Side != 1 ||
                    variant == "SHORT" && detected.Side != -1 ||
                    completeProbe is { } force && detected.Side != force.Side)) continue;
                if (StructuralPolicy &&
                    (variant == "TREND" && detected.Family != NativeStructuralOpportunity.Compression ||
                     variant == "REJECTION" && detected.Family != NativeStructuralOpportunity.Rejection ||
                     completeProbe is { } structuralProbe && detected.Side != structuralProbe.Side))
                    continue;
                proposed++;
                string instrument = "/" + market.Symbol;
                void CountOffer(string reason)
                {
                    Count(reason + instrument);
                    if (competition) Count("FAMILY/" + detected.Family + instrument + "/" + reason);
                }
                CountOffer("DETECTED");
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
                    CountOffer("GEOMETRY_DIRECTION_OR_CONTRACT_UNAVAILABLE");
                    rejections++;
                    continue;
                }
                if (ExecutableBracketTerms)
                    minTerms = ExecutableTerms(minTerms, signal.Side, signal.Stop, signal.Target, market);
                NativeEntryThesis? thesis = null;
                decimal reserved = minTerms.RiskEur;
                if (coherent)
                {
                    thesis = StructuralPolicy ? setup!.Thesis :
                        CompletePolicy ? new NativeEntryThesis("", 0m, signal.DecisionBar) :
                            NativeIntegratedLifecycle.Freeze(signal, market, directionControl);
                    if (thesis is null || !NativeIntegratedLifecycle.ProtectionCompatible(
                        signal.Side, signal.Stop, signal.Target, market))
                    {
                        CountOffer("ENTRY_THESIS_OR_PROTECTION_NOT_COMPATIBLE");
                        rejections++;
                        continue;
                    }
                    CountOffer(evidence.Protection is null ? "PROTECTION_DISTANCE_UNATTESTED" :
                        "PROTECTION_DISTANCE_CURRENT_SNAPSHOT_COMPATIBLE");
                    reserved = NativeIntegratedLifecycle.StressedRisk(minTerms, signal.Volatility, market.Quote);
                }
                CountOffer("LEGAL_MIN_WITH_COST_AND_MARGIN");
                if (!marksKnown)
                {
                    CountOffer("COMMON_MARK_UNKNOWN");
                    rejections++;
                    continue;
                }
                decimal directionalMargin = signal.Side == 1 ? minimum!.BuyMargin : minimum!.SellMargin;
                decimal fee = 2m * Fee(market.Quote, minTerms.Units);
                if (directionalMargin + fee > book.FreeMarginEur!.Value - pendingMargin)
                {
                    CountOffer("DIRECTIONAL_MIN_EXCEEDS_FREE_MARGIN");
                    rejections++;
                    continue;
                }
                CountOffer("MIN_WITHIN_AVAILABLE_MARGIN_AT_OBSERVED_TERMS");
                if (occupied.Contains(market.Symbol) || evidence.Path?.Complete != true ||
                    book.MaximumSampledDrawdown >= .30m ||
                    minTerms.MarginEur + fee > marginBudget ||
                    reserved > Math.Min(riskBudget, .02m * equity))
                {
                    string reason = occupied.Contains(market.Symbol) ? "SYMBOL_ALREADY_EXPOSED" :
                        evidence.Path?.Complete != true ? "INCOMPLETE_CURRENT_PATH" :
                        minTerms.MarginEur + fee > marginBudget ? "RESERVED_MARGIN_BUDGET" : "JOINT_RISK_BUDGET";
                    CountOffer(reason);
                    rejections++;
                    continue;
                }
                if (ExecutableBracketTerms && DirectionalRisk(signal.Side) + reserved > equity * .04m)
                {
                    CountOffer("USD_DIRECTION_STRESS_BUDGET");
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
                CountOffer("PORTFOLIO_FEASIBLE");
                NativeCompleteEntry? entry = null;
                if (CompletePolicy)
                {
                    var features = NativeCompletePolicy.EntryFeatures(evidence.Residence!, terms, signal, market.Quote);
                    var forecast = CompleteEntryModel(variant, at)?.Predict(features, at, terms.RiskEur);
                    entry = new(features, terms.RiskEur, forecast);
                }
                if (setup is not null)
                {
                    var features = NativeStructuralOpportunity.Features(setup, terms, market.Quote);
                    var forecast = structuralModels?.Predict(variant, signal.Family, features, at, terms.RiskEur);
                    entry = new(features, terms.RiskEur, forecast);
                }
                financeable.Add(new(market, signal, terms, thesis, coherent ? reserved : terms.RiskEur, entry));
            }
        }

        if (financeable.Count > 0)
        {
            Count("CLOCK_WITH_FINANCED_CHOICE");
            if (financeable.Count > 1) Count("CLOCK_WITH_COMPETING_CHOICES");
            if (financeable.Select(x => x.Market.Symbol).Distinct(StringComparer.Ordinal).Count() > 1)
                Count("CLOCK_WITH_COMPETING_SYMBOLS");
            if (competition && financeable.GroupBy(x => x.Market.Symbol, StringComparer.Ordinal)
                .Any(g => g.Select(x => x.Signal.Family).Distinct(StringComparer.Ordinal).Skip(1).Any()))
                Count("CLOCK_WITH_COMPETING_FAMILIES_SAME_SYMBOL");
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
            if (variant == "ECONOMIC")
            {
                int rejected = financeable.RemoveAll(offer => offer.Complete?.Prediction?.Lower is not > 0m);
                if (rejected > 0) Count("FULL_POLICY_NO_POSITIVE_UNCERTAINTY_ADJUSTED_OFFER");
                rejections += rejected;
                if (financeable.Count == 0) return RecordIntegratedFrame(at, book);
            }
            bool structuralRank = StructuralPolicy && variant is "RANK" or "SELECT" or "POOLED";
            if (structuralRank)
            {
                int removed = financeable.RemoveAll(offer => offer.Complete?.Prediction is null ||
                    variant == "SELECT" && offer.Complete.Prediction.Lower <= 0m);
                if (removed > 0) Count("CLOSED_MARKET_NO_SUPPORTED_ECONOMIC_OFFER");
                rejections += removed;
                if (financeable.Count == 0) return RecordIntegratedFrame(at, book);
            }
            var selected = fundedValue
                ? SelectFundedAction(variant, frame, book, committed, financeable, actionProbe)
                : structuralRank
                ? financeable.OrderByDescending(x => x.Complete!.Prediction!.Mean / x.ReservedRiskEur).First()
                : variant is "RANK" or "ABLATION" or "ECONOMIC"
                ? financeable.OrderByDescending(x => x.Complete?.Prediction?.Mean ?? decimal.MinValue).First()
                : variant == "RANDOM"
                    ? financeable.OrderBy(x => Sha((StructuralPolicy ? "CLOSED_MARKET_20261120/" : "COMPLETE_POLICY_20261120/") + at + "/" + x.Market.Symbol + "/" +
                        x.Signal.Side), StringComparer.Ordinal).First()
                : variant is NativeStructuralOpportunity.Combined or NativeStructuralOpportunity.CombinedWithoutExhaustion
                    // Planned target payoff is a ranking proxy, with no fitted outcome probability.
                    ? financeable.OrderByDescending(x => x.Terms.RewardEur / x.ReservedRiskEur)
                        .ThenBy(x => CompetitionOrder(at, x), StringComparer.Ordinal).First()
                : variant == NativeStructuralOpportunity.CombinedRandom
                    ? financeable.OrderBy(x => CompetitionOrder(at, x), StringComparer.Ordinal).First()
                : economic
                ? financeable.OrderByDescending(x => x.Thesis!.EstimatedEdgeAtAdmissionEur).First()
                : policy.Contains("_STRUCTURE_", StringComparison.Ordinal)
                    ? financeable.OrderByDescending(x => x.Terms.RewardEur / x.Terms.RiskEur).First()
                    : policy is "INTEGRATED_RANDOM_MIN" or NativeIntegratedLifecycle.Random
                        ? financeable.OrderBy(x => Sha((coherent ? "OWNER_INTEGRATED_LIFECYCLE/" : "20261120/") +
                            at + "/" + x.Market.Symbol + "/" + x.Signal.Family + "/" + x.Signal.Side),
                            StringComparer.Ordinal).First()
                        : financeable[0];
            if (selected is null) return RecordIntegratedFrame(at, book);
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
                    { Thesis = selected.Thesis, EntrySlippage = coherent ? terms.ExecutionSlippage : null,
                      CompletePolicy = selected.Complete }));
            admitted++;
            Count("ADMITTED/" + market.Symbol);
            if (competition)
            {
                Count("FAMILY/" + signal.Family + "/" + market.Symbol + "/ADMITTED");
                foreach (var offer in financeable.Where(offer => offer != selected))
                    Count("FAMILY/" + offer.Signal.Family + "/" + offer.Market.Symbol + "/FINANCEABLE_NOT_SELECTED");
            }
        }
        // The funding session may replace its ledger after an atomic intent.
        return RecordIntegratedFrame(at, ExecutableBracketTerms ? model.Ledger.Summary(at) : ledger.Summary(at));
    }

    FinancedCandidate? SelectFundedAction(string variant, Ucp1Frame frame, LedgerSummary book,
        decimal committed, List<FinancedCandidate> candidates, NativeFundedActionProbe? probe)
    {
        if (probe is null && !NativeFundedActionValue.Forecasts(variant))
            return variant == NativeFundedActionValue.Hash
                ? candidates.OrderBy(x => CompetitionOrder(frame.At, x), StringComparer.Ordinal).First()
                : candidates[0];

        var assessed = candidates.Select(c =>
        {
            var features = NativeFundedActionValue.Features(c.Market, frame, c.Signal.Side, book, committed,
                c.ReservedRiskEur, c.Terms.MarginEur, new[]
                {
                    (c.Market.Quote.Ask - c.Market.Quote.Bid) / c.Signal.Volatility,
                    c.Terms.RewardEur / c.ReservedRiskEur,
                    (decimal)(candidates.Count - 1)
                });
            var offer = new NativeFundedActionOffer(NativeFundedActionValue.Enter,
                c.Market.Symbol + "/" + c.Signal.Family + "/" + c.Signal.Side, c.Market.Symbol, c.Signal.Family,
                c.Signal.Side, frame.At, c.ReservedRiskEur, features);
            probe?.Available.Add(offer);
            var prediction = NativeFundedActionValue.Forecasts(variant)
                ? fundedActionModel?.Predict(variant, offer) : null;
            return (Candidate: c, Offer: offer, Prediction: prediction);
        }).ToArray();
        if (probe is not null)
        {
            if (probe.Wait) return null;
            if (probe.Enter is not null) return assessed.Single(x => x.Offer.Key == probe.Enter).Candidate;
        }
        if (!NativeFundedActionValue.Forecasts(variant)) return candidates[0];
        var selected = assessed.Where(x => x.Prediction?.Lower > 0m)
            .OrderByDescending(x => x.Prediction!.Mean)
            .ThenBy(x => CompetitionOrder(frame.At, x.Candidate), StringComparer.Ordinal).FirstOrDefault();
        foreach (var x in assessed)
            fundedActions.Add(new(x.Offer, x.Prediction, x.Offer == selected.Offer ? "ENTER" :
                x.Prediction is null ? "WAIT_UNCALIBRATED" : x.Prediction.Lower <= 0m ? "WAIT_NONPOSITIVE" : "WAIT_OTHER_OFFER"));
        return selected.Candidate;
    }

    (Ucp1Plan, NativeModelCloseInstruction?) ManageFundedAction(Ucp1Plan plan, LedgerPosition position,
        Ucp1MarketFrame market, Ucp1Frame frame, NativeFundedActionProbe? probe)
    {
        string variant = NativeStructuralOpportunity.Variant(policy);
        if ((probe is null && !NativeFundedActionValue.ValuesHolding(variant)) ||
            plan.Integrated is not { CompletePolicy: { } entry } geometry ||
            market.Integrated?.Path?.Complete != true || !NativeStructuralOpportunity.ContextReady(market) ||
            model.Ledger.PendingSnapshot().Any(e => e.PositionId == position.Id))
            return (plan, null);
        var book = model.Ledger.Summary(frame.At);
        long closed = market.ClosedBars!.For(NativeBarTimeframe.M15).ExpectedCloseAt;
        if (book.LiquidationEquityEur is not > 0m || book.UsedMarginEur is null ||
            closed <= Math.Max(plan.OpenAt, entry.Hold?.BarCloseAt ?? 0L))
            return (plan, null);
        var q = market.Quote;
        decimal sidePrice = position.Side > 0 ? q.Bid : q.Ask;
        decimal liquidation = NativeExecutableEconomics.EstimateNet(position.EntryQuote!, q, position.Side,
            position.Units, plan.Entry, sidePrice, q.LiquidationSlippagePerSide ?? position.SlippagePerSide);
        var features = NativeFundedActionValue.Features(market, frame, position.Side, book,
            plans.Values.Sum(p => p.RiskEur), plan.RiskEur, position.Units * q.MarginPerUnit,
            new[] { liquidation / plan.RiskEur, plan.MfeEur / plan.RiskEur,
                plan.MaeEur / plan.RiskEur, (frame.At - plan.OpenAt) / (decimal)NativeCompletePolicy.Day });
        var offer = new NativeFundedActionOffer(NativeFundedActionValue.Close, position.Id, market.Symbol,
            plan.Family, position.Side, frame.At, plan.RiskEur, features);
        probe?.Available.Add(offer);
        var prediction = NativeFundedActionValue.ValuesHolding(variant) ? fundedActionModel?.Predict(variant, offer) : null;
        bool close = probe?.Close == position.Id || prediction?.Lower > 0m;
        if (NativeFundedActionValue.ValuesHolding(variant))
            fundedActions.Add(new(offer, prediction, close ? "CLOSE" : "KEEP"));
        var hold = new NativeCompleteHold(frame.At, closed, features, plan.RiskEur, -prediction?.Mean, close);
        return (plan with { Integrated = geometry with { CompletePolicy = entry with { Hold = hold } } },
            close ? new("INTEGRATED_FUNDED_ACTION_VALUE_CLOSE", position.Units) : null);
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

    NativeCompleteDistribution? CompleteEntryModel(string variant, long at)
        => completeModels is { } models && models.AvailableAt <= at && variant is "RANK" or "ECONOMIC" or "ABLATION"
            ? variant == "ABLATION" ? models.Ablation : models.Entry : null;

    decimal DirectionalRisk(int side, string? except = null)
        => plans.Values.Where(p => p.Id != except && p.Side == side).Sum(p => p.RiskEur);

    static NativeIntegratedTerms ExecutableTerms(NativeIntegratedTerms terms, int side, decimal stop,
        decimal target, Ucp1MarketFrame market)
    {
        var q = market.Quote;
        var exact = NativeExecutableEconomics.Bracket(q, side, terms.Units, stop, target, terms.ExecutionSlippage,
            q.LiquidationSlippagePerSide ?? terms.ExecutionSlippage);
        return terms with { RiskEur = exact.RiskEur, RewardEur = exact.RewardEur, MarginEur = terms.Units * q.MarginPerUnit };
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
        var thesis = StructuralPolicy
            ? NativeStructuralOpportunity.AtFill(geometry.Thesis!, plan.Side, input)
            : NativeIntegratedLifecycle.AtFill(geometry.Thesis!, plan.Side, input);
        if (thesis is null) return null;
        var terms = new NativeIntegratedTerms(plan.Units, geometry.InitialRiskEur, geometry.InitialRewardEur,
            plan.Units * q.MarginPerUnit, geometry.EntrySlippage!.Value);
        terms = ExecutableBracketTerms ? ExecutableTerms(terms, plan.Side, geometry.Stop, geometry.Target, input) :
            NativeIntegratedLifecycle.Revalue(terms, plan.Side, geometry.Stop, geometry.Target, input);
        decimal stressed = NativeIntegratedLifecycle.StressedRisk(terms, plan.Atr, q);
        decimal usedRisk = plans.Values.Sum(p => p.RiskEur) - plan.RiskEur;
        decimal fee = 2m * Fee(q, plan.Units);
        if (stressed > equity * .02m ||
            usedRisk + stressed > Math.Min(equity * .06m, equity - .70m * summary.ObservedPeakEur) ||
            terms.MarginEur + fee > Math.Min(free, equity * .75m - used))
            return null;
        if (ExecutableBracketTerms && DirectionalRisk(plan.Side, plan.Id) + stressed > equity * .04m)
            return null;
        if (StructuralPolicy && NativeStructuralOpportunity.Variant(policy) == "SELECT" &&
            geometry.CompletePolicy is { } scored)
        {
            var repriced = NativeStructuralOpportunity.Reprice(scored.Features, terms, q, plan.Atr);
            if (structuralModels?.Predict("SELECT", plan.Family, repriced, q.At, terms.RiskEur)?.Lower is not > 0m)
                return null;
        }
        if ((policy is NativeCompletePolicy.Economic or NativeCompletePolicy.EconomicAdverse) &&
            geometry.CompletePolicy is { } planned)
        {
            var inputFeatures = planned.Features.ToArray();
            inputFeatures[3] = Math.Min(4m, (q.Ask - q.Bid) / plan.Atr);
            inputFeatures[4] = Math.Max(-4m, Math.Min(4m, terms.RewardEur / terms.RiskEur));
            if (CompleteEntryModel("ECONOMIC", q.At)?.Predict(inputFeatures, q.At, terms.RiskEur)?.Lower is not > 0m)
                return null;
        }
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
            equity - summary.ObservedPeakEur * .70m <= heldRisk ||
            ExecutableBracketTerms && Math.Max(DirectionalRisk(1), DirectionalRisk(-1)) > equity * .04m;
    }

    (Ucp1Plan, NativeModelCloseInstruction?) ManageIntegrated(Ucp1Plan plan,
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
        decimal exitSlip = q.LiquidationSlippagePerSide ?? position.SlippagePerSide;
        decimal Move(decimal price)
        {
            decimal change = side * (price - plan.Entry) - exitSlip;
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
            geometry = geometry with { Thesis = StructuralPolicy
                ? NativeStructuralOpportunity.Observe(thesis, side, plan.OpenAt, market)
                : NativeIntegratedLifecycle.Observe(thesis, side, plan.OpenAt, market) };
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
        if (!StructuralPolicy && geometry.CompletePolicy is { } entry)
        {
            if (NativeCompletePolicy.SessionExit(q.At, plan.OpenAt))
                return (plan, new("INTEGRATED_SESSION_COVERAGE_EXIT", position.Units));
            if (entry.Hold is { CloseRequested: true })
                return (plan, new("INTEGRATED_OBSERVED_HOLD_VALUE_EXIT", position.Units));

            long lastM15 = market.M15.Where(x => x.CloseAt < q.At).Select(x => x.CloseAt).LastOrDefault();
            if (entry.Hold is null && lastM15 > plan.OpenAt &&
                market.Integrated is { Residence: { } residence, Path.Complete: true })
            {
                decimal liquidation = NativeExecutableEconomics.EstimateNet(position.EntryQuote!, q, side,
                    position.Units, plan.Entry, now, exitSlip);
                var features = NativeCompletePolicy.HoldFeatures(residence, side, liquidation, plan.MfeEur,
                    geometry.InitialRiskEur, q.At);
                var expectation = completeModels is { } model && model.AvailableAt <= q.At
                    ? model.Hold?.Predict(features, q.At, geometry.InitialRiskEur) : null;
                bool close = completeProbe?.CloseAtHoldCheckpoint == true || expectation?.Mean is <= 0m;
                var hold = new NativeCompleteHold(q.At, lastM15, features, geometry.InitialRiskEur,
                    expectation?.Mean, close);
                geometry = geometry with { CompletePolicy = entry with { Hold = hold } };
                plan = plan with { Integrated = geometry };
                if (close) return (plan, new("INTEGRATED_OBSERVED_HOLD_VALUE_EXIT", position.Units));
            }
        }

        if (side * (now - plan.Entry) * 2m >= side * (geometry.Target - plan.Entry))
        {
            decimal fee = Fee(q, position.Units);
            decimal protectedLevel = plan.Entry + side * (exitSlip +
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
                { Thesis = geometry.Thesis, CompletePolicy = geometry.CompletePolicy } };
    }
}
