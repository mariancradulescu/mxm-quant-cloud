"""JAR1: pre-frozen prior-session index-opening reversal on AIP1 authentic labels.

Use ONLY source selection phase and matured prior 120-minute close returns.
Not an AIP1 refit, COL1 retune, independent result or funded replay.
"""
from collections import defaultdict
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path

EXPECTED_SOURCE_SHA256 = "ed23b6d7ce289ce1eeede6626ef8d9bce09d2cfbdb59fd6fe4b4493a75a4bd3c"
SYMBOLS = ("AUS200", "GER40", "JPN225", "NAS100", "UK100", "US500")
WEEK_MS = 604800000
MAX_PRIOR_GAP_MS = 96 * 3600000
HAC_LAGS = 3
Z_BONFERRONI = 1.959963984540054
POLICIES = ("JAR1_Reversal", "MatchedPriorContinuation", "MatchedLong", "MatchedShort", "Cash")


def finite_number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def hac_lower(weekly):
    n = len(weekly)
    avg = sum(weekly) / n
    e = [x - avg for x in weekly]
    gamma = [sum(e[t] * e[t-k] for t in range(k, n)) / n
             for k in range(HAC_LAGS + 1)]
    long_run = gamma[0] + 2 * sum((1 - k/(HAC_LAGS+1))*gamma[k]
                                   for k in range(1, HAC_LAGS+1))
    se = math.sqrt(max(0.0, long_run/n))
    return {"meanBps": avg, "hac3SeBps": se,
            "multiplicityAdjustedLowerBps": avg - Z_BONFERRONI*se}


def evaluate(data):
    p = data["Protocol"]
    start, end = int(p["developmentEnd"]), int(p["selectionEnd"])
    if end-start != 13*WEEK_MS or set(s["canonical"] for s in p["sessionSpecs"]) != set(SYMBOLS):
        raise ValueError("JAR1_ORIGINAL_CALENDAR_UNEXPECTED")
    if data["RawReadbackMatched"] is not True or data["SourceAudit"]["originalAccountBindingRechecked"] is not True:
        raise ValueError("JAR1_AUTHENTIC_ORIGINAL_ACCOUNT_UNVERIFIED")
    rows = [r for r in data["Forecasts"] if start<=int(r["At"]) and int(r["Exit"])<end]
    if len(rows) != 287 or any(r["Symbol"] not in SYMBOLS for r in rows):
        raise ValueError("JAR1_SOURCE_SELECTION_COUNT_UNEXPECTED")
    rows.sort(key=lambda r:(int(r["At"]),r["Symbol"]))
    prev = {}
    weeks = [[] for _ in range(13)]
    weekly_raw = [0]*13
    rejects = defaultdict(int)
    unknown = 0
    for r in rows:
        at = int(r["At"])
        w = (at-start)//WEEK_MS
        if not 0<=w<13:
            raise ValueError("JAR1_WEEK_RANGE_UNEXPECTED")
        weekly_raw[w] += 1
        symbol = r["Symbol"]
        p = prev.get(symbol)
        if p is None:
            rejects["NO_PRIOR_SELECTION_EVENT"] += 1
        else:
            age = at-int(p["Exit"])
            prior_move = finite_number(p["OutcomeBps"])
            if age<=0: rejects["PRIOR_LABEL_NOT_MATURED"] += 1
            elif age>MAX_PRIOR_GAP_MS: rejects["LATEST_PRIOR_SOURCE_TOO_OLD"] += 1
            elif prior_move is None: rejects["LATEST_PRIOR_SOURCE_UNOBSERVED"] += 1
            elif prior_move==0: rejects["LATEST_PRIOR_SOURCE_ZERO_MOVE"] += 1
            else:
                prior_side = 1 if prior_move>0 else -1
                sides = {"JAR1_Reversal":-prior_side,"MatchedPriorContinuation":prior_side,
                         "MatchedLong":1,"MatchedShort":-1,"Cash":0}
                current = finite_number(r["OutcomeBps"])
                cost = finite_number(r["CostBps"])
                weeks[w].append((symbol,sides,current,cost))
                if current is None or cost is None or cost<0: unknown += 1
        # Always use latest scheduled event, not latest favorable known event.
        prev[symbol] = r
    by_symbol = {s:{"CandidateClocks":0,"CostComplete":0} for s in SYMBOLS}
    weekly = []
    for w, candidates in enumerate(weeks):
        values = {p:[] for p in POLICIES}
        good = 0
        for symbol,sides,current,cost in candidates:
            by_symbol[symbol]["CandidateClocks"] += 1
            if current is None or cost is None or cost<0:continue
            good+=1
            by_symbol[symbol]["CostComplete"] += 1
            for policy in POLICIES:
                side=sides[policy]
                gross=side*current
                fee=cost if side else 0
                values[policy].append((gross,gross-fee,gross-2*fee))
        means={p:{
            "GrossBps":sum(v[0] for v in vals)/len(vals) if vals else 0,
            "CentralProxyBps":sum(v[1] for v in vals)/len(vals) if vals else 0,
            "AdverseProxyBps":sum(v[2] for v in vals)/len(vals) if vals else 0
        } for p,vals in values.items()}
        weekly.append({"WeekIndex":w,"SourceScheduledClocks":weekly_raw[w],
                       "CausalCandidates":len(candidates),"CompleteProxyLabels":good,
                       "UnknownCurrentOutcomeOrCost":len(candidates)-good,
                       "ByPolicyEqualEventMeanBps":means})
    def series(policy):
        return [r["ByPolicyEqualEventMeanBps"][policy]["AdverseProxyBps"] for r in weekly]
    jar=series("JAR1_Reversal")
    matched_long=series("MatchedLong")
    paired_delta=[x-y for x,y in zip(jar,matched_long)]
    own=hac_lower(jar)
    vs_long=hac_lower(paired_delta)
    first=sum(jar[:6])/6
    second=sum(jar[6:])/7
    active_first=sum(weekly[w]["CompleteProxyLabels"]>0 for w in range(6))
    active_second=sum(weekly[w]["CompleteProxyLabels"]>0 for w in range(6,13))
    gate=(active_first>=4 and active_second>=4 and first>0 and second>0
          and own["meanBps"]>0 and own["multiplicityAdjustedLowerBps"]>0
          and vs_long["multiplicityAdjustedLowerBps"]>0 and unknown==0)
    return {
        "Study":"JAR1_CAUSAL_PRIOR_SESSION_INDEX_OPENING_REVERSAL",
        "Classification":"EXPOSED_NEW_DISTINCT_MECHANISM_DEVELOPMENT_ONLY",
        "Source":"docs/AIP1_AUTHENTIC_RESULT.json","SourceSha256":EXPECTED_SOURCE_SHA256,
        "OriginalPepperstoneSourceRunId":41735441128,
        "OriginalPublicSourceArtifactId":13279217153,
        "Window":"ORIGINAL_13_SELECTION_WEEKS_ONLY","AllSixIndices":list(SYMBOLS),
        "PriorLabelMustBeMatured":True,"MaximumGapHours":96,
        "Signal":"OPPOSITE_LATEST_PREVIOUS_COMPLETED_SAME_SYMBOL_120M_RETURN",
        "NoClosedStudyRescoredOrRetuned":True,"NewBrokerRequests":0,"NewOrders":0,
        "CloudActivated":False,"Aip1ForecastSideOrPrimaryUsed":False,
        "PolicySampleMatched":True,"FundedEUR300PortfolioExecuted":False,
        "HistoricalCostsCertified":False,"IndependentConfirmation":False,
        "ContinuousFloatingDrawdownCertified":False,
        "SourceScheduledSelectionClocks":sum(weekly_raw),
        "CausalSignalCandidates":sum(len(w) for w in weeks),
        "CompleteCostAndReturnProxyLabels":sum(w["CompleteProxyLabels"] for w in weekly),
        "UnobservedCandidatePayoffs":unknown,
        "RejectedBeforeEntryByReason":dict(rejects),
        "BySymbolSourceCoverage":by_symbol,"Weekly":weekly,
        "PolicyFullCalendarEqualWeekAdverseMeanBps":{p:sum(series(p))/13 for p in POLICIES},
        "PrimaryAdverseVsCashHac3Bonferroni":own,
        "PrimaryAdverseVsMatchedLongHac3Bonferroni":vs_long,
        "EarlySixWeeksMeanAdverseBps":first,"LateSevenWeeksMeanAdverseBps":second,
        "EarlyDistinctActiveWeeks":active_first,"LateDistinctActiveWeeks":active_second,
        "PredeclaredExploratoryEconomicScreenPassed":gate,
        "Verdict":"EXPLORATORY_PRELIMINARY_ONLY_NOT_PORTFOLIO_QUALIFIED" if gate
            else "REJECT_EXACT_RULE_OR_INSUFFICIENT_SUPPORT",
        "Limitations":[
            "Exposed AIP1 source-selected event calendar is not all broker-open days",
            "Two-hour close-only price returns and source-date conditional costs, not fills/eur PnL",
            "No C# native joint EUR300 replay, cash/margin accounting, financing or Cloud parity",
            "No independent chronology, continuous drawdown or systemic HARD21 evidence",
            "Multiple symbols/sessions may have dependent outcomes",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",default="docs/AIP1_AUTHENTIC_RESULT.json")
    parser.add_argument("--output",default=None)
    args=parser.parse_args()
    raw=Path(args.source).read_bytes()
    if sha256(raw).hexdigest()!=EXPECTED_SOURCE_SHA256:
        raise ValueError("JAR1_ORIGINAL_PUBLIC_SOURCE_SHA256_MISMATCH")
    result=evaluate(json.loads(raw))
    text=json.dumps(result,indent=2)+"\n"
    if args.output: Path(args.output).write_text(text)
    else: print(text)


if __name__=="__main__":
    main()
