"""Recover the ETHUSD selection contrast on original XUA1 development data."""
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean

from .xua1_research import H, W, NAMES, PROTOCOL, asof_index, valid, decide, decrypt_source, cost_models

RECEIPT = Path("docs/XUA1_AUTHENTIC_RESULT_20261108.json")
SYMBOL = "ETHUSD"
FAMILY = NAMES[1]


def summarize(weeks, cost):
    return dict(Observations=sum(map(len,weeks)), ActiveWeeks=sum(bool(w) for w in weeks),
                EqualCalendarWeekGrossBps=mean(mean(w) if w else 0 for w in weeks),
                EqualCalendarWeekCentralBps=mean(mean(w)-cost["centralBps"] if w else 0 for w in weeks),
                EqualCalendarWeekAdverseBps=mean(mean(w)-cost["adverseBps"] if w else 0 for w in weeks),
                SumGrossBpsByWeek=[sum(w) for w in weeks],
                SumAdverseBpsByWeek=[sum(w)-len(w)*cost["adverseBps"] for w in weeks])


def main():
    original = RECEIPT.read_bytes()
    receipt = json.loads(original)
    p = json.loads(PROTOCOL.read_bytes())
    source = next(s for s in p["source"]["sourceRuns"] if SYMBOL in s["instruments"])
    authenticated = decrypt_source(source,p)
    history = authenticated["bars"][SYMBOL]
    costs = authenticated["quoteCosts"][SYMBOL]
    terms = authenticated["contracts"][SYMBOL]
    if (authenticated["truncations"][SYMBOL] or not terms["tradingModeOpening"] or
        not 0 < terms["currentMinMarginEur"] < 300 or
        len(history) < p["eligibility"]["requiredHistoricalH1ClosesAtLeast"] or
        len(costs) < p["eligibility"]["requiredFreshPairedBidAskCostClocksAtLeast"]):
        raise ValueError("XUA1_CORRECTION_SOURCE_ELIGIBILITY")
    cost = cost_models(costs)
    start = p["chronology"]["startUtcMs"]
    end = p["chronology"]["developmentEndUtcMs"]
    timeline = sorted(history)
    cells = defaultdict(list)
    for t in timeline:
        if not start <= t < end:
            continue
        h = asof_index(history,t,timeline)
        prev = history.get(t-H)
        if not valid(h) or prev is None:
            continue
        side = (h[-1][4]>prev[4])-(h[-1][4]<prev[4])
        if not side:
            continue
        entry, exit_at = t+H, t+7*H
        if exit_at >= end or any(z not in history for z in range(entry,exit_at+H,H)):
            continue
        if datetime.fromtimestamp(entry/1000,timezone.utc).date() != datetime.fromtimestamp(exit_at/1000,timezone.utc).date():
            continue
        fired = decide(FAMILY,SYMBOL,h)
        if fired and fired != side:
            raise ValueError("XUA1_CORRECTION_DIRECTION")
        cells[(t-start)//W].append((bool(fired),side*10000*math.log(history[exit_at][4]/history[entry][4])))
    blocks = [cells[w] for w in range(26)]
    filtered = summarize([[v for yes,v in block if yes] for block in blocks],cost)
    frozen = receipt["originalEvaluatedFamilies"][FAMILY]["development"]
    if (filtered["Observations"] != frozen["signalCount"] or
        abs(filtered["EqualCalendarWeekAdverseBps"]-frozen["equalCalendarWeekMeanBps"]["adverse"]) > 1e-8):
        raise ValueError("XUA1_CORRECTION_ORIGINAL_FILTER_PARITY")
    result = dict(Study="XUA1_CRYPTO_BENCHMARK_CORRECTION", OriginalReceiptSha256=sha256(original).hexdigest(),
                  OriginalProtocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(), OriginalSource=source,
                  ProtocolSha256=sha256(Path("research/XUA1_BENCHMARK_CORRECTION.md").read_bytes()).hexdigest(),
                  Filtered=filtered, Momentum=summarize([[v for _,v in block] for block in blocks],cost),
                  Unselected=summarize([[v for yes,v in block if not yes] for block in blocks],cost),
                  Cash=summarize([[] for _ in blocks],cost), DevelopmentWeeks=26, SelectionScored=False,
                  PortfolioExecuted=False, IndependentConfirmation=False, BrokerRequests=0, OrdersSubmitted=0, CloudActivated=False)
    Path("xua1-benchmark-correction-public.json").write_text(json.dumps(result,indent=2)+"\n")


if __name__ == "__main__":
    main()
