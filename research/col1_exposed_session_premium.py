"""COL1: exploratory fixed-clock intraday equity-index risk premium on published AIP1 rows.

Never reuse the closed AIP1 trading prediction as a filter. Never read audit or
future/held-out observations. Does not obtain raw bars or authenticate new source.
Comparison to frozen AIP1 forecast-side is ONLY a matched descriptive baseline.
NOT independent validation, executable fills, financed P&L, HARD21 or DD30.

Usage: python -m research.col1_exposed_session_premium
"""
import json
import math
from pathlib import Path

SOURCE = Path("docs/AIP1_AUTHENTIC_RESULT.json")
SYMBOLS = ("AUS200", "GER40", "JPN225", "NAS100", "UK100", "US500")
WEEK_MS = 604800000
Z_BONFERRONI_TWO_ENDPOINTS = 1.959963984540054
HAC_LAGS = 3


def hac3_lower(weekly):
    n = len(weekly)
    mean = sum(weekly) / n
    e = [x - mean for x in weekly]
    gamma = [sum(e[t] * e[t-lag] for t in range(lag, n)) / n
             for lag in range(HAC_LAGS + 1)]
    long_run = gamma[0] + 2 * sum(
        (1-lag/(HAC_LAGS+1))*gamma[lag] for lag in range(1, HAC_LAGS+1))
    se = math.sqrt(max(0.0, long_run / n))
    return {"meanBps":mean, "hac3SeBps":se,
            "multiplicityAdjustedLowerBps":mean - Z_BONFERRONI_TWO_ENDPOINTS * se}


def calculate(data):
    p = data["Protocol"]
    start, end = int(p["developmentEnd"]), int(p["selectionEnd"])
    assert end - start == 13 * WEEK_MS, "SELECTION_NOT_13_WEEKS"
    assert set(x["canonical"] for x in p["sessionSpecs"]) == set(SYMBOLS)
    assert data["RawReadbackMatched"] is True
    assert data["SourceAudit"]["originalAccountBindingRechecked"] is True
    weeks = [[] for _ in range(13)]
    other_phase = 0
    for r in data["Forecasts"]:
        at = int(r["At"])
        if not (start <= at and int(r["Exit"]) < end):
            other_phase += 1
            continue
        if r["Symbol"] not in SYMBOLS:
            raise ValueError("UNEXPECTED_SOURCE_SYMBOL")
        w = (at - start) // WEEK_MS
        assert 0 <= w < 13
        weeks[w].append(r)
    rows = []
    for i, group in enumerate(weeks):
        returns = []
        missing = 0
        for r in group:
            if r["OutcomeBps"] is None or r["CostBps"] is None:
                missing += 1
                continue
            gross = float(r["OutcomeBps"])
            cost = float(r["CostBps"])
            side = int(r["Side"])
            if not math.isfinite(gross) or not math.isfinite(cost) or cost < 0 or side not in (-1, 1):
                raise ValueError("INVALID_SOURCE_FIELD")
            # Published AIP1 OutcomeBps = source close-only raw return * 10000,
            # NOT the forecast-side return. See AuctionInventoryResearch.cs.
            # A completely fixed all-symbol long-only rule; no features or fitting.
            returns.append((gross, gross-cost, gross-2*cost,
                            gross - side*gross))
        den = len(returns)
        def mean(k):
            return sum(v[k] for v in returns) / den if den else 0.0
        rows.append({"week":i, "sourceScheduledEvents":len(group),
                     "completeGrossCostEvents":den, "missing":missing,
                     "days":len(set(x["At"]//86400000 for x in group)),
                     "equalEventGrossBps":mean(0),
                     "equalEventConditionalCentralNetBps":mean(1),
                     "equalEventConditionalAdverseNetBps":mean(2),
                     "equalEventIncrementalVsFrozenAip1AdverseBps":mean(3)})
    fields = ("equalEventGrossBps", "equalEventConditionalCentralNetBps",
              "equalEventConditionalAdverseNetBps",
              "equalEventIncrementalVsFrozenAip1AdverseBps")
    endpoints = {
      "adverseVsCash":hac3_lower([r[fields[2]] for r in rows]),
      "adverseIncrementalVsFrozenAip1SideBenchmark":
        hac3_lower([r[fields[3]] for r in rows])
    }
    missing = sum(r["missing"] for r in rows)
    return {
      "schema":"MXM_COL1_EXPOSED_SELECTION_ONLY_EXPLORATORY_V1",
      "source":"docs/AIP1_AUTHENTIC_RESULT.json",
      "mechanism":"ALL_SIX_INDEXES_LONG_CASH_OPEN_PLUS30_TO_PLUS150_MIN",
      "sourceIdentity":"PRIORLY_AUTHENTICATED_ORIGINAL_PEPPERSTONE_SOURCE_LABELS_NO_NEW_REQUEST",
      "sampleRestriction":"AIP1_ALREADY_EXPOSED_SELECTION_ONLY; AUDIT_FORECASTS_UNTOUCHED",
      "cannotAssertNewIndependentEvidence":True,
      "eventSubsetBias":"PUBLISHED_AIP1_SCHEDULED_FEATURE_ROWS; NOT THE COMPLETE_BROKER_OPEN_CALENDAR",
      "selectionWeekCount":13, "selectionEvents":sum(r["sourceScheduledEvents"] for r in rows),
      "completeProxyEvents":sum(r["completeGrossCostEvents"] for r in rows),
      "missing":missing, "otherPhaseSourceRowsNotScored":other_phase,
      "weekly":rows, "weeklyFullCalendarMeansBps":{k:sum(r[k] for r in rows)/13 for k in fields},
      "jointHac3BonferroniDescriptive":endpoints,
      "maxPotentialSignalSlotsByWeek":[r["sourceScheduledEvents"] for r in rows],
      "financedRoundTrips":0, "conditionalNetEur":None,
      "nativeCsharpNewMechanismParity":False, "actualBrokerFills":False,
      "globalDrawdown30Proven":False, "hard21Proven":False,
      "independentConfirmation":False, "tradingQualification":False,
      "newOrders":0, "cloudActivated":False,
      "costInterpretation":"CostBps is AIP1 source-date modelled roundtrip cost, not historical quote fills; central=1x, adverse=2x conditional cost; no historical FX financing/tariff certificates",
      "priceInterpretation":"Forward broker OHLC close-only label; not historical bid/ask executable trade",
      "notARerunOfClosedAip1":"No model retraining, refitting, re-selection, parameter tuning or original primary result rescore; frozen predicted side only as fixed comparator"
    }


if __name__ == "__main__":
    print(json.dumps(calculate(json.loads(SOURCE.read_text())), indent=2, sort_keys=True))
