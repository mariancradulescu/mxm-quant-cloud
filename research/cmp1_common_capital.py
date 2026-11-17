"""CMP1: new common-book causal information research on pre-exposed authentic bar outcomes.

Never reexecute AIP1. No broker fills, no native-funded NET, no independence claim.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any

SOURCE = Path("docs/AIP1_AUTHENTIC_RESULT.json")
REGISTRY = Path("research/evidence_registry.json")
PROTOCOL = Path("research/CMP1_COMMON_CAPITAL_PROTOCOL_20261117.md")
UNIVERSE = ("AUS200", "GER40", "JPN225", "NAS100", "UK100", "US500")
POLICIES = ("JOINT", "OWN", "PEER", "JOINT_UNRANKED",
            "JOINT_NO_ABSTENTION", "JOINT_ONE_SLOT", "CASH")
HORIZON_MS = 7_200_000
D = Decimal

@dataclass(frozen=True)
class Event:
    at: int
    exit: int
    symbol: str
    outcome: float | None
    cost: float
    notional: Decimal
    margin: Decimal
    financing_scenario_covered: bool

@dataclass(frozen=True)
class Candidate:
    row: Event
    side: int
    predicted: float
    rank: float
    threshold: float

def source_rows(document: dict[str, Any]) -> list[Event]:
    if document.get("SourceRunId") != 41735441128:
        raise ValueError("CMP1_ORIGINAL_SOURCE_RUN_BINDING")
    costs = {x["Symbol"]: x for x in document["CostContexts"]}
    if set(costs) != set(UNIVERSE):
        raise ValueError("CMP1_COST_UNIVERSE")
    if len(document["Forecasts"]) != 646:
        raise ValueError("CMP1_ORIGINAL_SOURCE_ROWS")
    rows: list[Event] = []
    seen: set[tuple[int, str]] = set()
    for x in document["Forecasts"]:
        at, exit_at, symbol = int(x["At"]), int(x["Exit"]), x["Symbol"]
        if symbol not in UNIVERSE or exit_at - at != HORIZON_MS:
            raise ValueError("CMP1_SOURCE_CLOCK")
        if (at, symbol) in seen:
            raise ValueError("CMP1_DUPLICATE_CLOCK_SYMBOL")
        seen.add((at, symbol))
        c = costs[symbol]
        notional = D(str(c["MinimumNotionalEur"]))
        margin = D(str(c["CurrentMinimumMarginEur"]))
        row_cost = float(x["CostBps"])
        if notional <= 0 or margin <= 0 or row_cost < 0:
            raise ValueError("CMP1_INVALID_CURRENT_COST_CONTEXT")
        outcome = None if x["OutcomeBps"] is None else float(x["OutcomeBps"])
        rows.append(Event(at, exit_at, symbol, outcome, row_cost, notional,
                          margin, bool(x["FinancingScenarioCovered"])))
    return sorted(rows, key=lambda x: (x.at, x.symbol))

def causal_prediction(row: Event, known: dict[str, list[Event]],
                      mode: str) -> tuple[Candidate | None, str]:
    own = known[row.symbol][-4:]
    if len(own) != 4:
        return None, "OWN_CAUSAL_WARMUP"
    values = [float(x.outcome) for x in own]
    own_prediction = max(-150., min(150., mean(values)))
    se = stdev(values) / 2
    scale = max(10., mean(abs(x) for x in values))
    peer_values: list[float] = []
    for symbol in UNIVERSE:
        if symbol == row.symbol:
            continue
        hist = known[symbol][-4:]
        if len(hist) != 4 or row.at - hist[-1].exit > 72 * 3600_000:
            continue
        past = [float(x.outcome) for x in hist]
        peer_values.append(float(hist[-1].outcome) / max(10., mean(abs(x) for x in past)))
    peer_prediction = max(-150., min(150., scale * mean(peer_values))) if len(peer_values) >= 2 else None
    if mode in ("JOINT", "JOINT_UNRANKED", "JOINT_NO_ABSTENTION", "JOINT_ONE_SLOT"):
        if peer_prediction is None:
            return None, "PEER_CAUSAL_WARMUP"
        expected = (own_prediction + peer_prediction) / 2
    elif mode == "OWN":
        expected = own_prediction
    elif mode == "PEER":
        if peer_prediction is None:
            return None, "PEER_CAUSAL_WARMUP"
        expected = peer_prediction
    else:
        raise ValueError("CMP1_UNKNOWN_POLICY")
    if expected == 0:
        return None, "ZERO_CAUSAL_PREDICTION"
    threshold = 2 * row.cost + .5 * se
    if mode != "JOINT_NO_ABSTENTION" and abs(expected) <= threshold:
        return None, "ABSTAIN_BELOW_COST_AND_UNCERTAINTY"
    return Candidate(row, 1 if expected > 0 else -1, expected,
                     (abs(expected) - threshold) / scale, threshold), "OFFER"

def iso_week(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%G-W%V")

def run_policy(rows: list[Event], mode: str) -> dict[str, Any]:
    if mode == "CASH":
        return dict(policy=mode, conditionalTerminalCashEur="300",
                    conditionalClosedNetProxyEur="0", completeConditionalRoundTrips=0,
                    conditionalClosedOnlyDrawdown=0, maximumReservedMarginEur="0",
                    conditionalRoundTripsPerIsoWeek={}, originalFutureLabelsMissing=0,
                    pendingAtEnd=0, admittedIntents=0, rejectedAtCapacity=0, abstentions=0,
                    offeredCandidates=0, causalPredictionClockViolations=0,
                    nativeFundedNetEur=None)
    cash = D(300)
    peak = cash
    dd = D(0)
    maximum_reserved = D(0)
    held: list[tuple[Candidate, Decimal]] = []
    known: dict[str, list[Event]] = defaultdict(list)
    pending_maturity = sorted(rows, key=lambda x: (x.exit, x.at, x.symbol))
    maturity_i = 0
    weekly: dict[str, int] = defaultdict(int)
    total_closed = total_admitted = rejected_capacity = abstentions = offered = missing = 0
    trace: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = []
    all_clocks = sorted(set(x.at for x in rows))
    by_at: dict[int, list[Event]] = defaultdict(list)
    for x in rows:
        by_at[x.at].append(x)
    unknown_cash = False

    def settle(clock: int) -> None:
        nonlocal cash, peak, dd, total_closed, unknown_cash, missing
        survivors = []
        for c, m in held:
            if c.row.exit > clock:
                survivors.append((c, m))
                continue
            if c.row.outcome is None or not c.row.financing_scenario_covered:
                unknown_cash = True
                missing += 1
                continue
            gross = D(str(c.side * c.row.outcome)) * c.row.notional / D(10000)
            conditional_cost = D(str(2 * c.row.cost)) * c.row.notional / D(10000)
            conditional_net = gross - conditional_cost
            cash += conditional_net
            peak = max(peak, cash)
            if peak > 0:
                dd = max(dd, (peak - cash) / peak)
            total_closed += 1
            weekly[iso_week(c.row.at)] += 1
            scored.append(dict(symbol=c.row.symbol, entryAt=c.row.at,
                               matureExit=c.row.exit, side=c.side,
                               predictedBps=round(c.predicted, 6),
                               realizedPriceReturnBps=c.row.outcome,
                               conditionalGrossEur=str(gross),
                               conditionalRoundTripCostProxyEur=str(conditional_cost),
                               conditionalClosedProxyEur=str(conditional_net),
                               sourceIsBrokerFill=False))
        held[:] = survivors

    for now in all_clocks:
        settle(now)
        # STRICT: a label at the same exact decision boundary is not yet in knowledge.
        while maturity_i < len(pending_maturity) and pending_maturity[maturity_i].exit < now:
            item = pending_maturity[maturity_i]
            if item.outcome is not None:
                known[item.symbol].append(item)
            maturity_i += 1
        if unknown_cash:
            continue
        candidates = []
        for row in by_at[now]:
            cand, why = causal_prediction(row, known, mode)
            if cand is None:
                abstentions += 1
            else:
                offered += 1
                candidates.append(cand)
        if mode == "JOINT_UNRANKED":
            candidates.sort(key=lambda x: x.row.symbol)
        else:
            candidates.sort(key=lambda x: (-x.rank, x.row.symbol))
        active_symbols = {c.row.symbol for c, _ in held}
        reserved = sum((m for _, m in held), D(0))
        for cand in candidates:
            if cand.row.symbol in active_symbols:
                rejected_capacity += 1
                continue
            if mode == "JOINT_ONE_SLOT" and held:
                rejected_capacity += 1
                continue
            # Borrowing, missing floating marks, historical margin changes are NOT assumed away.
            if cash <= D(210) or reserved + cand.row.margin > D(".6") * cash:
                rejected_capacity += 1
                continue
            if not cand.row.financing_scenario_covered:
                abstentions += 1
                continue
            held.append((cand, cand.row.margin))
            active_symbols.add(cand.row.symbol)
            reserved += cand.row.margin
            maximum_reserved = max(maximum_reserved, reserved)
            total_admitted += 1
            trace.append(dict(at=now, symbol=cand.row.symbol, direction=cand.side,
                              score=round(cand.rank, 6),
                              predictedBps=round(cand.predicted, 6),
                              thresholdBps=round(cand.threshold, 6),
                              reservedMarginAfterEur=str(reserved),
                              currentClosedOnlyCashProxyEur=str(cash)))
    settle(max(x.exit for x in rows) + 1)
    conditional = None if unknown_cash else str(cash)
    return dict(policy=mode,
                conditionalTerminalCashEur=conditional,
                conditionalClosedNetProxyEur=None if unknown_cash else str(cash - D(300)),
                completeConditionalRoundTrips=total_closed,
                admittedIntents=total_admitted, offeredCandidates=offered,
                abstentions=abstentions, rejectedAtCapacity=rejected_capacity,
                maximumReservedMarginEur=str(maximum_reserved),
                conditionalClosedOnlyDrawdown=float(dd),
                conditionalRoundTripsPerIsoWeek=dict(sorted(weekly.items())),
                originalFutureLabelsMissing=missing,
                causalPredictionClockViolations=0,
                pendingAtEnd=len(held),
                decisionTrace=trace,
                closedPriceProxyTrace=scored,
                nativeFundedNetEur=None)

def evaluate(rows: list[Event]) -> dict[str, Any]:
    if len(rows) != 646 or sorted({x.symbol for x in rows}) != list(UNIVERSE):
        raise ValueError("CMP1_FROZEN_FULL_COVERAGE")
    models = {p: run_policy(rows, p) for p in POLICIES}
    primary = models["JOINT"]
    def delta(other: str) -> str | None:
        a = primary["conditionalClosedNetProxyEur"]
        b = models[other]["conditionalClosedNetProxyEur"]
        if a is None or b is None:
            return None
        return str(D(a) - D(b))
    first, last = min(x.at for x in rows), max(x.exit for x in rows)
    weeks = []
    at = datetime.fromtimestamp(first / 1000, timezone.utc).date()
    at -= timedelta(days=at.weekday())
    end = datetime.fromtimestamp(last / 1000, timezone.utc).date()
    while at <= end:
        label = at.strftime("%G-W%V")
        weeks.append(dict(isoWeek=label,
                          scheduledObservableDecisions=sum(iso_week(x.at) == label for x in rows),
                          completeConditionalJointRoundTrips=primary["conditionalRoundTripsPerIsoWeek"].get(label, 0),
                          hard21Certified=False))
        at += timedelta(days=7)
    return dict(schema="mxm-cmp1-common-capital-v1",
                study="CMP1", inputObservationCount=len(rows),
                observedUniverse=list(UNIVERSE),
                uniqueDecisionClocks=len({x.at for x in rows}),
                evaluationFirstClock=first, evaluationLastExit=last,
                sourceExposure="PREVIOUSLY_EXPOSED_AIP1_DEVELOPMENT_ONLY",
                originalSourceRunId=41735441128, originalSourceRecollected=False,
                reusedClosedAip1Predictions=False, onlineLabelsMatureStrictlyBeforeDecision=True,
                anyMarketOrders=False, cloudActivated=False,
                conditionalCurrency="EUR300_CLOSED_ONLY_PRIOR_BID_BAR_RETURN_PROXY_NOT_EXECUTABLE_NET",
                quoteOrFillEvidenceForNewPolicy=False, historicTermsCertified=False,
                floatingDrawdownCertified=False, independentChronologicalConfirmation=False,
                hard21Certified=False, qualified=False,
                nativeFundedNetEur=None, adverseExecutableNetEur=None,
                brokerExecutionNetEur=None, financingEur=None,
                nativeDecideResearchFillCycle="NOT_EXECUTED_NO_ORIGINAL_BIDASK_PER_SELECTED_EVENT",
                completeSystemWeeks=weeks,
                scenarioProxyIncrementalVsCashEur=delta("CASH"),
                scenarioProxyIncrementalVsOwnEur=delta("OWN"),
                scenarioProxyIncrementalVsPeerEur=delta("PEER"),
                scenarioProxyIncrementalVsUnrankedEur=delta("JOINT_UNRANKED"),
                scenarioProxyIncrementalVsNoAbstentionEur=delta("JOINT_NO_ABSTENTION"),
                scenarioProxyIncrementalVsOneSlotEur=delta("JOINT_ONE_SLOT"),
                policies=models,
                verdict="EXPOSED_SHARED_CASH_PROXY_ONLY_NOT_NATIVE_FUNDED_ECONOMIC_QUALIFICATION")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cmp1-common-capital.public.json")
    args = ap.parse_args()
    doc_bytes = SOURCE.read_bytes()
    registry = json.loads(REGISTRY.read_text())
    expected = registry["frozenFileSha256"]["docs/AIP1_AUTHENTIC_RESULT.json"]
    received = hashlib.sha256(doc_bytes).hexdigest()
    if received != expected:
        raise ValueError("CMP1_IMMUTABLE_AUTHENTIC_PUBLIC_SOURCE_HASH_MISMATCH")
    rows = source_rows(json.loads(doc_bytes))
    result = evaluate(rows)
    result["protocolSha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    result["sourcePublicSha256"] = received
    result["sourceEncryptedSha256"] = "fa684ca1de58c6d1e8bdee410834855d05389af0c0ae4523b095367dce0e5331"
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("CMP1_EXPOSED_COMMON_BOOK_RESULT " + json.dumps({
        k: result[k] for k in (
            "study", "inputObservationCount", "sourceExposure",
            "scenarioProxyIncrementalVsCashEur", "scenarioProxyIncrementalVsOwnEur",
            "nativeFundedNetEur", "adverseExecutableNetEur", "verdict")}, sort_keys=True))

if __name__ == "__main__":
    main()
