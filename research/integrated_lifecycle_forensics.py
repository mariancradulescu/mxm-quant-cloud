"""Join immutable original position events to sealed source observations. No replay."""

import bisect
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .decode import need
from .integrated_market_readback import readback
from .integrated_market_source import MINUTE, PUBLIC_DIR, digest

ORIGINAL = Path("integrated-existing-economic")
OUTPUT = Path("integrated-lifecycle-forensics-public")
ECONOMIC_SHA = "1aad8fe715a7986de1452508ec46b7c3122acba4da092322733b4a86f4b5151b"
RECEIPT_SHA = "b81474d62847d28a0bf5690449a495175950799420c7d51adb21b4adf2b9f141"
SOURCE_SHA = "1f4621b9e76cb38d0ac69f0d88ea02b4face3d124b5528a56ba853d1ac9877ee"
REGIME = "MODEL_UNTRANSMITTED_CLOSED_BAR_REGIME_INVALIDATION"


def checked_json(file, sha):
    body = file.read_bytes()
    need(digest(body) == sha, "INTEGRATED_FORENSIC_ORIGINAL_HASH_MISMATCH")
    return json.loads(body, parse_float=Decimal)


def event_traces(policy):
    traces = defaultdict(list)
    for event in policy["NonMarkEvents"]:
        traces[event["PositionId"]].append(event)
    return traces


def quote_lookup(markets):
    return {market["Name"]: {quote["At"]: quote for quote in market["Quotes"]} for market in markets}


def m15_context(market):
    bars = market["M15"]
    clocks = [bar["CloseAt"] for bar in bars]

    def at(clock):
        i = bisect.bisect_left(clocks, clock)
        if i < 2 or bars[i - 2]["CloseAt"] != bars[i - 1]["OpenAt"]:
            return None, 0
        delta = Decimal(bars[i - 1]["Close"]) - Decimal(bars[i - 2]["Close"])
        return clocks[i - 1], (delta > 0) - (delta < 0)

    return at


def fact_pair(trip, trace):
    opened = next(event for event in trace if event["Kind"] == "OPEN_FILL")
    closed = next(event for event in reversed(trace) if event["Kind"] == "CLOSE_FILL")
    requested = next(event for event in reversed(trace)
                     if event["Kind"] == "REQUEST_CLOSE" and event["At"] < closed["At"])
    need(opened["At"] == trip["OpenAt"] and closed["At"] == trip["CloseAt"]
         and requested["Reason"] == closed["Reason"] == trip["ExitReason"],
         "INTEGRATED_FORENSIC_EVENT_BINDING")
    return opened, requested, closed


def forensic_report(economics, markets):
    market_by_name = {market["Name"]: market for market in markets}
    context = {name: m15_context(market) for name, market in market_by_name.items()}
    quotes = quote_lookup(markets)
    policy = economics["Policies"]["INTEGRATED_STRUCTURE_MIN"]
    trades = policy["Outcome"]["IndividualTrips"]
    traces = event_traces(policy)
    by_cohort = defaultdict(Counter)
    regime_events, overruns, nonpositive = [], [], []
    for trip in trades:
        symbol, side = trip["Symbol"], trip["Side"]
        trace = traces[trip["PositionId"]]
        intent = next(event for event in trace if event["Kind"] == "REQUEST_OPEN")
        opened, requested, closed = fact_pair(trip, trace)
        week = datetime.fromtimestamp(closed["At"] / 1000, timezone.utc).strftime("%G-W%V")
        cohort = by_cohort[(symbol, trip["Family"], week)]
        cohort.update(Complete=1)
        cohort["NetEur"] += trip["NetEur"]
        cohort["GrossEur"] += trip["GrossEur"]
        cohort["CostsEur"] += trip["GrossEur"] - trip["NetEur"]
        if trip["Integrated"]["InitialPlannedRewardEur"] <= 0:
            nonpositive.append(trip["PositionId"])
            cohort.update(NonpositivePlannedReward=1)
        if requested["Reason"] == REGIME:
            admission_at, admission_side = context[symbol](intent["At"])
            entry_at, entry_side = context[symbol](opened["At"])
            request_at, request_side = context[symbol](requested["At"])
            need(side * request_side < 0, "INTEGRATED_FORENSIC_LEGACY_DIRECTION_MISMATCH")
            stale = entry_at == request_at
            entry_adverse = side * entry_side < 0
            row = {"PositionId": trip["PositionId"], "Family": trip["Family"], "Symbol": symbol,
                   "Week": week, "Side": side, "AdmissionAt": intent["At"], "FillAt": opened["At"],
                   "CloseRequestAt": requested["At"], "CloseFillAt": closed["At"],
                   "AdmissionM15CloseAt": admission_at, "EntryM15CloseAt": entry_at,
                   "ExitDecisionM15CloseAt": request_at, "AdmissionM15Direction": admission_side,
                   "EntryM15Direction": entry_side, "ExitDecisionM15Direction": request_side,
                   "SameM15AtAdmission": admission_at == request_at, "SameM15AtEntry": stale,
                   "AlreadyAdverseAtEntry": entry_adverse, "NewAdverseDirection": not stale and not entry_adverse,
                   "ExactlyTwoMinutes": closed["At"] - opened["At"] == 2 * MINUTE,
                   "FirstObservedBarrier": trip["Integrated"]["FirstObservedBarrier"],
                   "NetEur": trip["NetEur"], "CostsEur": trip["GrossEur"] - trip["NetEur"]}
            regime_events.append(row)
            cohort.update(LegacyRegime=1, SameEntryBar=int(stale), TwoMinutes=int(row["ExactlyTwoMinutes"]))
        if trip["NetEur"] < -trip["EntryRiskEur"]:
            adverse_side = "Bid" if side == 1 else "Ask"
            mark = quotes[symbol][requested["At"]]
            final = quotes[symbol][closed["At"]]
            fx_mark = quotes["EURUSD"][requested["At"]]
            effect = side * (Decimal(final[adverse_side]) - Decimal(mark[adverse_side]))
            row = {"PositionId": trip["PositionId"], "Symbol": symbol, "Week": week,
                   "Reason": trip["ExitReason"], "EntryRiskEur": trip["EntryRiskEur"],
                   "NetEur": trip["NetEur"], "R": trip["R"], "UnknownPath": trip["CrossedUnknownHistory"],
                   "ObservedRequestAt": requested["At"], "ModelFillAt": closed["At"],
                   "ElapsedMs": closed["At"] - requested["At"],
                   "QuoteMoveAfterRequestEurAtRequestFx": effect * trip["Units"] / Decimal(fx_mark["Bid"]),
                   "FirstObservedBarrier": trip["Integrated"]["FirstObservedBarrier"]}
            if requested["Reason"] == "MODEL_UNTRANSMITTED_INTEGRATED_OBSERVED_INVALIDATION":
                market = market_by_name[symbol]
                bars = [bar for bar in market["M5"] if bar["CloseAt"] < intent["At"]]
                structure = bars[-1:] if trip["Family"] == "FAILED_AUCTION" else bars[-3:]
                level = (min(Decimal(bar["Low"]) for bar in structure) if side > 0
                         else max(Decimal(bar["High"]) for bar in structure)) - side * Decimal(market["TickSize"])
                extreme = Decimal(mark["Path"]["BidLow" if side > 0 else "AskHigh"])
                need(side * (extreme - level) <= 0, "INTEGRATED_FORENSIC_OBSERVED_STOP_NOT_CROSSED")
                row["BeyondStopAtRequestEurAtRequestFx"] = (
                    side * (Decimal(mark[adverse_side]) - level) * trip["Units"] / Decimal(fx_mark["Bid"]))
                row["StopObservedInCompleteRequestInterval"] = mark["Path"]["Complete"]
            overruns.append(row)
            cohort.update(RiskOverrun=1)
    budget = economics["Policies"]["INTEGRATED_STRUCTURE_BUDGET"]
    peak = budget["Outcome"]["PeakSampledEquityEur"]
    floor = budget["MinimumObservedLiquidationEquityEur"]
    dd = budget["Outcome"]["SampledMaximumDrawdownNotContinuous"]
    need(len(overruns) == policy["Overruns"], "INTEGRATED_FORENSIC_OVERRUN_COUNT")
    two = [row for row in regime_events if row["ExactlyTwoMinutes"]]

    def totals(rows):
        return {key: sum(bool(row[key]) for row in rows)
                for key in ("SameM15AtAdmission", "SameM15AtEntry", "AlreadyAdverseAtEntry",
                            "NewAdverseDirection", "ExactlyTwoMinutes")}

    return {
        "OriginalEconomicRun": "44691260616", "OriginalSourceRun": "44687919474",
        "Mode": "ORIGINAL_EVENTS_AND_SOURCE_READ_ONLY_NO_ENGINE_REPLAY",
        "OriginalEconomicSha256": ECONOMIC_SHA, "OriginalSourcePublicSha256": SOURCE_SHA,
        "RegimeExitCount": len(regime_events), "RegimeExitTotals": totals(regime_events),
        "RegimeTwoMinuteTotals": totals(two),
        "RegimeExitEvents": regime_events, "NonpositiveRewardCompleteIds": nonpositive,
        "RiskOverruns": overruns, "WorstR": min(overruns, key=lambda row: row["R"]),
        "Cohorts": [{"Symbol": name, "Family": family, "Week": week, **counts}
                    for (name, family, week), counts in sorted(by_cohort.items())],
        "BudgetSampledDrawdown": {"PeakEur": peak, "MinimumEndOfFrameEquityEur": floor,
                                  "LedgerFactSampledDrawdown": dd,
                                  "MaximumPossibleTroughAtLedgerWorstDrawdownEur": peak * (1 - dd),
                                  "EndOfFrameGapBelow30PercentOfGlobalPeakEur": peak * Decimal(".70") - floor},
        "OrdersSubmitted": 0, "CloudActivated": False, "BrokerStopFillCertified": False,
    }


def main():
    source = checked_json(PUBLIC_DIR / "source.json", SOURCE_SHA)
    receipt = checked_json(ORIGINAL / "receipt.json", RECEIPT_SHA)
    economics = checked_json(ORIGINAL / "economic.json", ECONOMIC_SHA)
    need(source["RunId"] == economics["SourceRun"] == receipt["SourceRun"] == "44687919474"
         and receipt["NativeOutputSha256"] == ECONOMIC_SHA and receipt["OriginalEncryptedShards"] == source["Shards"]
         and source["NewOrders"] == economics["OrdersSubmitted"] == 0
         and not source["CloudActivated"] and not economics["CloudActivated"],
         "INTEGRATED_FORENSIC_RECEIPT_BINDING")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "INTEGRATED_FORENSIC_CUSTODY_KEY_MISSING")
    report = forensic_report(economics, readback(source, key))
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "forensics.json").write_text(json.dumps(report, default=str, indent=2) + "\n")
    print("INTEGRATED_FORENSIC_VERIFIED", report["RegimeExitTotals"], report["RegimeTwoMinuteTotals"],
          "OVERRUNS", len(report["RiskOverruns"]), flush=True)


if __name__ == "__main__":
    main()
