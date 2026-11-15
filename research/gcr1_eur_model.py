"""GCR1 A1 source-independent intent and conditional EUR finance.

This module has NO network, broker order, OAuth, or external service.
The *original* combined GCR1 decision in gcr1_macro_signal is unchanged.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D
from math import isfinite
from statistics import mean
from .gcr1_macro_signal import (
    BarClose, NUM_CLOSES, STEP_MS, decide, _log_return, scheduled_clocks,
    ENTRY_AFTER_MS, EXIT_AFTER_MS,
)
from .rne1_source_financial_preflight import Unpriced
from .rne1_eur_protected_exact_reconciliation import current_eur, no_swap

SCALER = D(100000)
POLICIES = ("combined", "copperOnly", "inverseGoldOnly",
            "audOwnMomentum", "long", "short", "cash")
SCENARIOS = (("central", D("0.5")), ("adverse", D("2")))
TARGET = "AUDUSD"
FX = "EURUSD"


def sign(x):
    return (x > 0) - (x < 0)


def bar_window(day_bars, name, clock):
    """Select ONLY expected, completed <= decision endpoints from source."""
    by_end = day_bars.get(name) or {}
    series = []
    for i in range(NUM_CLOSES):
        end = clock - (NUM_CLOSES - 1 - i) * STEP_MS
        raw = by_end.get(str(end))
        if raw is None:
            return []
        try:
            raw = int(raw)
            if raw <= 0:
                return []
        except (ValueError, TypeError):
            return []
        series.append(BarClose(end, float(D(raw) / SCALER)))
    return series


def intents(day_bars, clock):
    """Never access a later t+5 entry/t+4h05 exit or the quote panel."""
    copper = bar_window(day_bars, "Copper", clock)
    gold = bar_window(day_bars, "XAUUSD", clock)
    aud = bar_window(day_bars, TARGET, clock)
    original = decide(copper, gold, clock)
    c, _ = _log_return(copper, clock)
    g, _ = _log_return(gold, clock)
    a, _ = _log_return(aud, clock)
    sides = {
        "combined": original.side,
        "copperOnly": sign(c) if c is not None else None,
        "inverseGoldOnly": -sign(g) if g is not None else None,
        "audOwnMomentum": sign(a) if a is not None else None,
        "long": 1, "short": -1, "cash": 0,
    }
    row = {
        "clock": clock,
        "originalIntent": original.state,
        "sides": sides,
        "decisionKnown": {p: sides[p] is not None for p in POLICIES},
        "inputKnown": {"Copper": c is not None,
                       "XAUUSD": g is not None, "AUDUSD": a is not None},
        "metalCell": (
            "COPPER_POS_GOLD_NEG" if c is not None and g is not None and c > 0 and g < 0
            else "COPPER_NEG_GOLD_POS" if c is not None and g is not None and c < 0 and g > 0
            else "BOTH_SAME_SIGN" if c is not None and g is not None and c * g > 0
            else "EITHER_ZERO" if c is not None and g is not None
            else "MISSING_DECISION_METAL"
        ),
    }
    return row


def asof_pair(panel, symbol, clock):
    """Paired independent genuine original quotes; no future, no midpoint fill."""
    sample = panel.get(symbol, {}).get(str(clock))
    if not isinstance(sample, dict) or sample.get("hasMore") is True:
        return None
    b, a = sample.get("bid"), sample.get("ask")
    if not isinstance(b, dict) or not isinstance(a, dict):
        return None
    for side in (b, a):
        if (not isinstance(side.get("at"), int)
                or not isinstance(side.get("raw"), int)
                or side["raw"] <= 0 or side["at"] > clock
                or clock - side["at"] > 20000):
            return None
    if b["raw"] > a["raw"]:
        return None
    return (D(b["raw"]) / SCALER, D(a["raw"]) / SCALER)


def price_all(day_quotes, t, contract, min_margin):
    """Return same-clock full source panel independent of ANY policy direction."""
    entry = t + ENTRY_AFTER_MS
    ending = t + EXIT_AFTER_MS
    q0, q1 = asof_pair(day_quotes, TARGET, entry), asof_pair(day_quotes, TARGET, ending)
    f0, f1 = asof_pair(day_quotes, FX, entry), asof_pair(day_quotes, FX, ending)
    if any(q is None for q in (q0, q1, f0, f1)):
        return None, "FINANCIAL_UNKNOWN_ENTRY_EXIT_FX"
    if min_margin is None or min_margin <= 0 or min_margin >= D(300):
        return None, "FINANCIAL_UNKNOWN_OR_UNFUNDED_CURRENT_MIN_MARGIN"
    if contract is None:
        return None, "FINANCIAL_UNKNOWN_CURRENT_CONTRACT"
    try:
        no_swap(contract, entry, ending)
        money = {}
        for scenario, slip in SCENARIOS:
            money[scenario] = {}
            for side in (-1, 0, 1):
                money[scenario][str(side)] = current_eur(
                    contract, q0, q1, f0, f1, side, slip
                )
    except (Unpriced, ValueError, ArithmeticError, AttributeError,
            TypeError, ZeroDivisionError):
        return None, "FINANCIAL_UNKNOWN_ORIGINAL_CURRENT_FEES_OR_SWAP"
    return money, "COMMON_EUR_PRICED"


def evaluate(tape, contract, min_margin):
    """Evaluate ex-ante rows only AFTER protected raw source is encrypted."""
    schedules = scheduled_clocks()
    assert len(schedules) == 780
    rows = []
    for t in schedules:
        day = datetime.fromtimestamp(t / 1000, timezone.utc).date().isoformat()
        rec = tape[day]
        frozen = rec["intents"][str(t)]
        check = intents(rec["bars"], t)
        if check != frozen:
            raise ValueError("GCR1_PREQUOTE_IMMUTABLE_INTENTS_NOT_REPRODUCIBLE")
        money, status = price_all(rec["quotes"], t, contract, min_margin)
        row = {
            "t": t, "week": (len(rows) // 15),
            "intent": frozen,
            "money": None, "financeStatus": status,
            "riskStatus": "RISK_PATH_UNKNOWN_NOT_CONTINUOUS_BID_ASK",
        }
        if money is not None:
            outcomes = {scenario: {
                policy: (money[scenario][str(frozen["sides"][policy])]
                         if frozen["sides"][policy] is not None else None)
                for policy in POLICIES
            } for scenario, _ in SCENARIOS}
            row["money"] = outcomes
        rows.append(row)
    return {
        "overall": summary(rows),
        "first26Weeks": summary(rows[:390]),
        "last26Weeks": summary(rows[390:]),
        "all52Weeks": [summary(rows[i:i+15]) for i in range(0, 780, 15)],
        "jointFundedNativeNetEur": None,
        "continuousFloatingDrawdownCertified": False,
        "independentConfirmation": False,
        "ordersSubmitted": 0,
    }


def summary(rows):
    cells = Counter(r["intent"]["metalCell"] for r in rows)
    intents_by_policy = {}
    for p in POLICIES:
        states = [r["intent"]["sides"][p] for r in rows]
        intents_by_policy[p] = {
            "buy": states.count(1), "sell": states.count(-1),
            "abstain": states.count(0), "decisionUnknown": states.count(None),
        }
    common = [r for r in rows if r["money"] is not None and
              all(r["money"]["adverse"][p] is not None for p in POLICIES)]
    result = {
        "scheduled": len(rows),
        "commonPricedClocks": len(common),
        "commonUnknownClocks": len(rows) - len(common),
        "originalCausalIntents": intents_by_policy,
        "metalStates": dict(cells),
        "financeStates": dict(Counter(r["financeStatus"] for r in rows)),
        "riskPathsCertifiedContinuous": 0,
        "fullyClosedFundedNativeTrades": None,
    }
    for scenario, _ in SCENARIOS:
        sums = {p: round(sum(r["money"][scenario][p]["netEur"]
                              for r in common), 6) for p in POLICIES}
        result[scenario + "MatchedNetEur"] = sums
        result[scenario + "MatchedMeanNetEurPerClock"] = {
            p: round(sums[p] / len(common), 6) if common else None for p in POLICIES
        }
        result[scenario + "PrimaryIncrementalEur"] = {
            p: round(sums["combined"] - sums[p], 6)
            for p in POLICIES if p != "combined"
        }
        result[scenario + "ConditionalActiveTradeNetEur"] = {}
        for p in POLICIES:
            active = [r["money"][scenario][p]["netEur"] for r in common
                      if r["intent"]["sides"][p] not in (None, 0)]
            result[scenario + "ConditionalActiveTradeNetEur"][p] = {
                "pricedEntries": len(active),
                "netEur": round(sum(active), 6),
                "meanNetEur": round(mean(active), 6) if active else None,
                "wins": sum(x > 0 for x in active),
                "losses": sum(x < 0 for x in active),
            }
        result[scenario + "SameSignControlNetEur"] = {
            p: round(sum(r["money"][scenario][p]["netEur"] for r in common
                          if r["intent"]["metalCell"] == "BOTH_SAME_SIGN"), 6)
            for p in ("combined", "copperOnly", "inverseGoldOnly")
        }
    return result
