"""ORX1 restricted hindsight opportunity census on immutable CVP1 public receipts.

No market-source collection, policy replay, broker calls, training or execution.
The diagnostic is NOT a market-wide oracle nor independent confirmation.
"""
import bisect
import hashlib
import json
import math
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("docs/CVP1_ORIGINAL_PUBLIC_44162043538.zip")
PINNED_SHA256 = "a5125582a1cf4690871ad4d7640090c376ea8e85196228bf235d4a25ee7bc569"
WEEKS = ("2026-W28", "2026-W29", "2026-W30")
COST_FIELDS = ("SpreadEur", "SlippageEur", "ConversionEur", "CommissionsEur", "FinancingEur")
ZERO = 1e-10


def need(condition, reason):
    if not condition:
        raise ValueError("ORX1_" + reason)


def week(utc_ms):
    w = datetime.fromtimestamp(utc_ms / 1000, timezone.utc).isocalendar()
    return f"{w.year}-W{w.week:02d}"


def optimum_one_slot(rows):
    """Exact weighted interval DP on immutable, non-overlapping completed trades."""
    ordered = sorted(rows, key=lambda r: (r["ClosedAt"], r["OpenedAt"], r["PositionId"]))
    ends = [r["ClosedAt"] for r in ordered]
    dp = [0.0] * (len(ordered) + 1)
    chosen = [False] * (len(ordered) + 1)
    previous = [0] * (len(ordered) + 1)
    for i, row in enumerate(ordered, 1):
        p = bisect.bisect_right(ends, row["OpenedAt"], 0, i-1)
        with_row = dp[p] + row["NetEur"]
        without_row = dp[i - 1]
        if with_row > without_row + ZERO:
            dp[i], previous[i], chosen[i] = with_row, p, True
        else:
            dp[i], previous[i] = without_row, i-1
    selected = []
    i = len(ordered)
    while i:
        if chosen[i]:
            selected.append(ordered[i-1])
        i = previous[i]
    selected.reverse()
    need(all(a["ClosedAt"] <= b["OpenedAt"] for a, b in zip(selected, selected[1:])),
         "ORACLE_OVERLAP")
    need(math.isclose(math.fsum(x["NetEur"] for x in selected), dp[-1], abs_tol=1e-7),
         "ORACLE_DP_RECONCILIATION")
    return selected


def maximum_count_one_slot(rows):
    selected, end = [], -1
    for r in sorted(rows, key=lambda x: (x["ClosedAt"], x["OpenedAt"], x["PositionId"])):
        if r["OpenedAt"] >= end:
            selected.append(r)
            end = r["ClosedAt"]
    return selected


def sum_field(rows, key):
    return math.fsum(float(x[key] or 0) for x in rows)


def summarize_case(name, book):
    trades = book["Trades"]
    entries = {e["Id"]: e for e in book["Entries"]}
    need(len(entries) == len(book["Entries"]), "DUPLICATE_ENTRY")
    need(len(trades) == len(entries), "ORIGINAL_SETTLEMENT_CARDINALITY")
    need(book["FullSettlementKnown"], "ORIGINAL_BOOK_UNSETTLED")
    need(book["Ledger"]["OpenPositions"] == 0 and book["Ledger"]["PendingIntents"] == 0,
         "ORIGINAL_BOOK_POSITIONS")
    original = sum_field(trades, "NetEur")
    need(math.isclose(original, book["Scorecard"]["NetEur"], abs_tol=1e-6),
         "ORIGINAL_NET_MISMATCH")
    need(math.isclose(300 + original, book["Ledger"]["CashEur"], abs_tol=1e-6),
         "ORIGINAL_CASH_MISMATCH")
    observed_weeks = tuple(book["Scorecard"]["FundedCompletionsByIsoWeek"].keys())
    need(set(observed_weeks) == set(WEEKS), "UNEXPECTED_EVALUATION_WEEKS")
    known_positive, uncertain, risk_rejected = [], 0, 0
    seen = set()
    for t in trades:
        uid = t["PositionId"]
        need(uid in entries and uid not in seen, "MISSING_OR_DUPLICATE_POSITION")
        seen.add(uid)
        e = entries[uid]
        need(bool(t["CompletesRoundTrip"]) and 0 < t["OpenedAt"] < t["ClosedAt"],
             "INCOMPLETE_INTERVAL")
        need(float(e["InitialRiskEur"]) > 0, "MISSING_INITIAL_RISK")
        need(week(t["ClosedAt"]) in WEEKS, "TRADE_OUTSIDE_EVALUATION")
        cost = sum_field([t], "SpreadEur") + sum_field([t], "SlippageEur")
        cost += sum_field([t], "CommissionsEur") + sum_field([t], "ConversionEur")
        cost += sum_field([t], "FinancingEur")
        need(math.isclose(t["GrossEur"] - cost, t["NetEur"], abs_tol=1e-6),
             "SOURCE_TRADE_COST_NET")
        if bool(e["Uncertain"]):
            uncertain += 1
        if t["NetEur"] > 0 and not bool(e["Uncertain"]):
            if float(e["InitialRiskEur"]) <= 90:
                known_positive.append(t)
            else:
                risk_rejected += 1
    need(uncertain >= 0, "UNCERTAINTY")
    need(book["PeakCurrentMarginEur"] <= 300, "ORIGINAL_MARGIN_OVER_300")
    selected = optimum_one_slot(known_positive)
    count_selected = maximum_count_one_slot(known_positive)
    upper = sum_field(known_positive, "NetEur")
    best = sum_field(selected, "NetEur")
    need(best <= upper + 1e-6, "HINDSIGHT_ABOVE_ENVELOPE")
    by_week = {}
    for w in WEEKS:
        all_w = [t for t in trades if week(t["ClosedAt"]) == w]
        pos_w = [t for t in known_positive if week(t["ClosedAt"]) == w]
        pick_w = [t for t in selected if week(t["ClosedAt"]) == w]
        count_w = [t for t in count_selected if week(t["ClosedAt"]) == w]
        by_week[w] = dict(
            originalSimpleTrades=len(all_w),
            riskScreenedKnownPositiveRecordedTrades=len(pos_w),
            relaxedPositiveValueEur=sum_field(pos_w, "NetEur"),
            oneSlotMaxNetSelectedTrades=len(pick_w),
            oneSlotMaxNetEur=sum_field(pick_w, "NetEur"),
            oneSlotMaxPositiveCount=len(count_w),
            oneSlotCountCouldReach21=len(count_w) >= 21,
            recordedSubsetRelaxedCountCouldReach21=len(pos_w) >= 21)
    gross = sum_field(selected, "GrossEur")
    costs = {k: sum_field(selected, k) for k in COST_FIELDS}
    allcost = math.fsum(costs.values())
    need(math.isclose(gross - allcost, best, abs_tol=1e-6),
         "SELECTED_COST_RECONCILIATION")
    need(all(float(entries[t["PositionId"]]["InitialRiskEur"]) <= 90 for t in selected),
         "RISK_SCREEN")
    result = dict(
        originalCompletedTrades=len(trades),
        originalSimpleNetEur=original,
        originalSimpleGrossEur=sum_field(trades, "GrossEur"),
        originalSimpleCostsEur={k: sum_field(trades, k) for k in COST_FIELDS},
        originalKnownMarkDrawdownPct=100 * book["SampledCurrentExitCostFloatingDrawdown"],
        originalUnknownHoldingMarks=book["UnknownHoldingMarks"],
        originalUncertainTradeCount=book["UncertainTrades"],
        entriesFlaggedUncertain=uncertain,
        recordedKnownPositiveRiskScreenedCount=len(known_positive),
        positiveButOver90InitialRiskExcluded=risk_rejected,
        recordedRelaxedUpperNetEur=upper,
        oneSlotPerfectHindsightMaxNetEur=best,
        oneSlotPerfectHindsightTrades=len(selected),
        oneSlotPerfectHindsightSelectedIds=[t["PositionId"] for t in selected],
        oneSlotMaxPositiveTradeCount=len(count_selected),
        oneSlotMaxNetGrossEur=gross,
        oneSlotMaxNetCostBreakdownEur=costs,
        oneSlotMaxNetCostTotalEur=allcost,
        selectedGrossCaptureFractionNeededToBreakEven=(allcost/gross if gross > 0 else None),
        finalCashAfterFixedOutcomeSelectedSubsetEur=300 + best,
        recordedWeeks=by_week,
        knownContinuousFloatingDrawdown=False,
        alteredSubsetBrokerFundingAndFillsCertified=False,
        mathematicallyExactOnlyForImmutableNonoverlappingRecordedIntervals=True)
    need(all(x["oneSlotMaxNetSelectedTrades"] <= x["riskScreenedKnownPositiveRecordedTrades"]
             for x in by_week.values()), "WEEK_COUNT")
    return result


def run(source=SOURCE):
    blob = Path(source).read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    need(digest == PINNED_SHA256, "FROZEN_ORIGINAL_ZIP_SHA256")
    with zipfile.ZipFile(source) as z:
        need("economic.json" in z.namelist() and "source.json" in z.namelist(),
             "ARCHIVE_SCHEMA")
        economic = json.loads(z.read("economic.json"))
        origin = json.loads(z.read("source.json"))
    need(economic["Study"] == "CVP1" and origin["Completed"] and
         origin["NativeTapeSha256"] == economic["SourceSha256"], "SOURCE_BINDING")
    need(str(origin["OriginalRun"]) == "44162043538" and
         origin["OrdersSubmitted"] == 0 and origin["CloudActivated"] is False,
         "SOURCE_BROKER_BOUNDARY")
    need(economic["StartingCapitalEur"] == 300 and
         economic["IndependentConfirmation"] is False and
         economic["Qualified"] is False, "FROZEN_ECONOMIC_CONTEXT")
    books = economic["Books"]
    need(len(books) == 16, "FROZEN_BOOK_CARDINALITY")
    cases = {n: summarize_case(n, books[n]) for n in
             ("SIMPLE_adverse", "SIMPLE_central")}
    return dict(
        study="ORX1_RECORDED_OPPORTUNITIES_RESTRICTED",
        protocol="research/ORX1_FROZEN_RECORDED_OPPORTUNITY_DIAGNOSTIC_20261118.md",
        originalStudy="CVP1_CLOSED_UNCHANGED",
        originalRun=44162043538,
        originalZipSha256=digest,
        marketPathOracle=False,
        strategySignal=False,
        retrospectiveFutureKnowledge=True,
        sourceOnlyPublicReceipt=True,
        allDatesGloballyExposed=True,
        independentConfirmation=False,
        noNativePortfolioRerun=True,
        riskAndIntrapositionDDCertified=False,
        historicalBrokerFillsCertified=False,
        actionOrders=0,
        cloudActivated=False,
        scope="Only originally funded SIMPLE full-trip records with their original exact outcomes; no other entries, paths, instruments or policies",
        oracleCases=cases,
        publishedComparatorsAdverseEur={k: books[k+"_adverse"]["Scorecard"]["NetEur"]
          for k in ("CASH", "FULL", "NO_PEER", "NO_ACTIVITY", "PROTECT_ONLY", "SIMPLE")},
        promotion=False,
        phase1FullMarketOpportunityCensusCompleted=False)


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/orx1-restricted-result.json")
    report = run()
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "study": report["study"],
        "status": "RESTRICTED_SECONDARY_DIAGNOSTIC_NO_PROMOTION",
        "result": {k: {"original": v["originalSimpleNetEur"],
                       "oneSlotHindsight": v["oneSlotPerfectHindsightMaxNetEur"],
                       "count": v["oneSlotPerfectHindsightTrades"],
                       "weekCounts": {w: d["oneSlotMaxPositiveCount"]
                                      for w, d in v["recordedWeeks"].items()}}
                   for k, v in report["oracleCases"].items()},
        "output": str(output)}, sort_keys=True))
