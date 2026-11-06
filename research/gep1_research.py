"""GEP1: one preregistered bounded two-premise portfolio discovery, one authentic readback.

Every 2025-11/2026-11 source week was previously exposed globally; a new
mechanism on these dates is exploratory and cannot establish independent edge.
Preflight uses actual development strategy-aligned return variation at the
calendar-week cluster level. NEVER score selection of a group that fails it.
No existing closed research predictors are invoked, and no orders are sent.
"""
import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev, NormalDist

from .multiscale_conditional_research import recover, extract_costs
from .integrated_predictive_funded import cost_context

PROTOCOL = Path("research/gep1_protocol.json")
M5 = 300000
H = 3600000
W = 7 * 24 * H
GROUPS = ("GOLD_RISK_TO_JPY/USDJPY", "USD_FUNDING_TO_US_INDEX/US500",
          "USD_FUNDING_TO_US_INDEX/NAS100")
USD_BASKET = ("EURUSD", "GBPUSD", "AUDUSD", "USDCAD")


def require(x, reason):
    if not x:
        raise ValueError("GEP1_" + reason)


def sgn(x):
    return (x > 0) - (x < 0)


def signal_side(group, views, t):
    def change(symbol):
        v = views[symbol]
        a, b = v.get(t-H), v.get(t)
        return None if a is None or b is None or a[5] <= 0 or b[5] <= 0 else math.log(b[5] / a[5])
    if group.startswith("GOLD_RISK"):
        x = change("XAUUSD")
        return None if x is None or x == 0 else -sgn(x)
    vals = [change(s) for s in USD_BASKET]
    if any(v is None or v == 0 for v in vals):
        return None
    aligned = [-sgn(vals[0]), -sgn(vals[1]), -sgn(vals[2]), sgn(vals[3])]
    consensus = sum(aligned)
    # Four component signs; exactly three aligned means |sum| = 2.
    return -sgn(consensus) if abs(consensus) >= 2 else None


def forecast_rows(p, bars):
    c = p["calendar"]
    views = {s: {int(x[1]): x for x in rows} for s, rows in bars.items()}
    known = defaultdict(lambda: defaultdict(list))
    counters = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    t = c["start"]
    while t < c["end"]:
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
        if d.weekday() not in c["weekdays"] or d.hour not in c["utcDecisionHours"]:
            t += H
            continue
        stage = "development" if t < c["developmentEnd"] else "selection"
        cutoff = c["developmentEnd"] if stage == "development" else c["end"]
        w = (t-c["start"]) // W
        for group in GROUPS:
            target = group.split("/")[1]
            v = views.get(target, {})
            counts = counters[group][stage]
            counts["clockSlots"] += 1
            side = signal_side(group, views, t)
            if side is None:
                counts["noCausalFeatureOrConsensus"] += 1
                continue
            a, b = v.get(t-H), v.get(t)
            if a is None or b is None or a[5] <= 0 or b[5] <= 0:
                counts["missingTargetBenchmark"] += 1
                continue
            benchmark = sgn(math.log(b[5] / a[5]))
            if benchmark == 0:
                counts["flatTargetBenchmark"] += 1
                continue
            counts["causalSignals"] += 1
            entry, exit_at = t + M5, t + M5 + p["clock"]["holdingMinutes"]*60000
            if exit_at >= cutoff:
                counts["crossesPhase"] += 1
                continue
            if entry not in v or exit_at not in v:
                counts["missingSourcePricedEntryOrExit"] += 1
                continue
            counts["completeSourcePricedLabels"] += 1
            # Store only fixed causal directions, refs and dates before pilot;
            # selection forward outcomes are not read unless development power passes.
            known[group][stage].append((w, side, benchmark, entry, exit_at))
        t += H
    return views, known, counters


def weekly_outcomes(rows, target, views, cost):
    v = views[target]
    weeks = defaultdict(list)
    for w, side, benchmark, entry, exit_at in rows:
        opening, ending = v[entry][5], v[exit_at][5]
        require(opening > 0 and ending > 0, "NONPOSITIVE_PRICE")
        outcome = 10000 * math.log(ending / opening)
        gross = side * outcome
        # Paired benchmark is same target, clocks, horizon and cost.
        matched = benchmark * outcome
        weeks[w].append(dict(gross=gross,
                             central=gross-cost["centralBps"],
                             adverse=gross-cost["adverseBps"],
                             incremental=gross-matched))
    return weeks


def mean_metric(weeks, key):
    return mean(mean(x[key] for x in rs) for rs in weeks.values()) if weeks else None


def active_weeks(weeks, n):
    return [mean(x["adverse"] for x in weeks[w]) for w in range(n) if weeks.get(w)]


def power_gate(p, group, rows, counters, views, cost):
    target = group.split("/")[1]
    sci = p["scientific"]
    dev = rows["development"]
    sel = rows["selection"]
    dev_weeks = weekly_outcomes(dev, target, views, cost)
    development_active = len(dev_weeks)
    selection_active = len({x[0] for x in sel})
    reasons = []
    def gate(why, fail):
        if fail: reasons.append(why)
    gate("INSUFFICIENT_AUTHENTIC_COST_OR_CONTRACT",
         cost.get("observed", 0) < 3 or
         cost.get("minimumMarginEur", 0) <= 0 or
         cost.get("minimumNotionalEur", 0) <= 0 or
         cost.get("adverseBps", 0) <= 0)
    gate("INSUFFICIENT_DEVELOPMENT_MECHANISM_WEEKS",
         development_active < sci["minimumDevelopmentActiveWeeks"])
    gate("INSUFFICIENT_SELECTION_SOURCE_WEEKS",
         selection_active < sci["minimumSelectionSourceWeeks"])
    gate("INSUFFICIENT_DEVELOPMENT_COMPLETE_SIGNAL_COUNT",
         len(dev) < sci["minimumDevelopmentCompleteSignals"])
    gate("INSUFFICIENT_SELECTION_SOURCE_COMPLETE_SIGNAL_COUNT",
         len(sel) < sci["minimumSelectionCompleteSignals"])
    gate("CURRENT_MINIMUM_MARGIN_EXCEEDS_EUR300",
         cost.get("minimumMarginEur", float("inf")) >= p["ownerProspectiveInitialCashEur"])
    pilot = dict(developmentComplete=len(dev),
                 selectionSourceCompleteWithoutOutcomes=len(sel),
                 developmentActiveWeeks=development_active,
                 selectionSourceActiveWeeks=selection_active,
                 developmentGrossMeanBps=mean_metric(dev_weeks, "gross"),
                 developmentConditionalCentralMeanBps=mean_metric(dev_weeks, "central"),
                 developmentConditionalAdverseMeanBps=mean_metric(dev_weeks, "adverse"),
                 developmentIncrementalOwnMomentumMeanBps=mean_metric(dev_weeks, "incremental"),
                 currentMinimumMarginEur=cost.get("minimumMarginEur"),
                 currentMinNotionalEur=cost.get("minimumNotionalEur"),
                 sourceQuoteCostSamples=cost.get("observed", 0),
                 estimatedEffectiveSelectionWeeksUpperBound=selection_active,
                 effectThresholdAdverseCost125pctBps=1.25*cost.get("adverseBps", float("inf")),
                 signedStrategyWeeklySdBps=None,
                 pairedIncrementalWeeklySdBps=None,
                 mechanismSpecificMdeBps=None,
                 dependenceCaveat="Calendar weeks are clusters; serial dependence across weeks not certified independent; 26 selection weeks globally previously exposed.")
    if development_active >= 3 and selection_active >= 3:
        a = [mean(x["adverse"] for x in rs) for rs in dev_weeks.values()]
        b = [mean(x["incremental"] for x in rs) for rs in dev_weeks.values()]
        sd_a, sd_b = stdev(a), stdev(b)
        # Bonferroni across all six fixed group/comparator tests.
        alpha = sci["familywiseAlpha"] / (sci["groups"] * sci["oneSidedComparisonsPerGroup"])
        z = NormalDist().inv_cdf(1-alpha) + NormalDist().inv_cdf(sci["powerTarget"])
        mde = z*max(sd_a, sd_b)/math.sqrt(selection_active)
        pilot.update(signedStrategyWeeklySdBps=sd_a,
                     pairedIncrementalWeeklySdBps=sd_b,
                     mechanismSpecificMdeBps=mde)
        gate("MECHANISM_SIGNED_WEEKLY_MDE_EXCEEDS_COST_RELEVANT_EFFECT",
             not math.isfinite(mde) or mde > pilot["effectThresholdAdverseCost125pctBps"])
    else:
        gate("INSUFFICIENT_MECHANISM_WEEKLY_VARIANCE", True)
    return dict(passPreScoring=not reasons,reasons=reasons,
                mechanismSpecificDevelopmentPilot=pilot)


def score_selection(p, group, rows, views, cost):
    """Only after a PASS of the mechanism-specific, development-only screen."""
    target = group.split("/")[1]
    weeks = weekly_outcomes(rows, target, views, cost)
    pwr = p["scientific"]
    alpha = pwr["familywiseAlpha"] / (pwr["groups"] * pwr["oneSidedComparisonsPerGroup"])
    z = NormalDist().inv_cdf(1-alpha)
    def lower(metric):
        xs = [mean(y[metric] for y in values) for values in weeks.values()]
        if len(xs) < 3 or stdev(xs) <= 0:
            return None
        return mean(xs)-z*stdev(xs)/math.sqrt(len(xs))
    adverse_lb, inc_lb = lower("adverse"), lower("incremental")
    return dict(completeSourcePricedSignals=len(rows),
                activeWeeks=len(weeks),
                conditionalMeanBps={k:mean_metric(weeks,k)
                        for k in ("gross","central","adverse","incremental")},
                adjustedAdverseWeeklyLowerBps=adverse_lb,
                adjustedIncrementalVsOwnMomentumWeeklyLowerBps=inc_lb,
                sourceOnlyPositiveBoth=bool(adverse_lb is not None and inc_lb is not None and
                                            adverse_lb > 0 and inc_lb > 0),
                independentlyConfirmed=False,
                physicalEurFundedNet=None,
                historicalFillsKnown=False,
                selectionObservationsGloballyExposed=True)


def run():
    original = PROTOCOL.read_bytes()
    p = json.loads(original)
    require(p["id"]=="GEP1" and p["status"]=="PREDECLARED_UNSCORED" and
            p["ownerProspectiveInitialCashEur"] == 300 and
            p["proof"]["locked"] and p["source"]["all52WeeksGloballyExposed"],"PROTOCOL_AUTHORITY")
    require(sum(x["groups"] for x in p["families"]) == 3,"FAMILY_GROUP_COUNT")
    source = json.loads(Path("research/hrc1_protocol.json").read_text())
    require([x["run"] for x in source["source"]]==p["source"]["preexistingAuthenticatedRuns"],
            "SOURCE_RUN_IDENTITY")
    bars, costs, authentication = {}, [], []
    for row in source["source"]:
        b, decoded, auth = recover(Path(row["folder"]),row["run"],row["hash"],row["schema"],row["protocol"])
        require(auth,"AUTHENTIC_ORIGINAL_SOURCE")
        require(not set(b["bars"]).intersection(bars),"DUPLICATE_SOURCE_ASSET")
        bars.update(b["bars"])
        rc,_ = extract_costs(b,decoded)
        costs.extend(rc)
        authentication.append(dict(run=row["run"],authentic=True,sourceSymbols=len(b["bars"])))
    require(sum(map(len,bars.values())) == p["source"]["originalSealedM5Bars"] and len(costs)==166,
            "ORIGINAL_SOURCE_COUNTS")
    require(all(s in bars for s in p["source"]["sourceUniverse"]),"UNIVERSE_MISSING")
    views, rows, counters = forecast_rows(p, bars)
    price_cost = cost_context(costs)
    results = {}
    for group in GROUPS:
        target = group.split("/")[1]
        cost = price_cost.get(target,{})
        q = power_gate(p,group,rows[group],counters[group],views,cost)
        # Never inspect selection outcomes until this exact group's pilot passes.
        selection = (score_selection(p,group,rows[group]["selection"],views,cost)
                     if q["passPreScoring"] else None)
        results[group] = dict(pilot=q,selection=selection,
                              selectionViewed=selection is not None,
                              observationsByStage={k:dict(v) for k,v in counters[group].items()},
                              originalCurrentTermCost={
                                  k:cost.get(k) for k in ("centralBps","adverseBps","minimumMarginEur",
                                  "minimumNotionalEur","observed","fundingKnown")})
    margins = [price_cost.get(s,{}).get("minimumMarginEur") for s in
               ("USDJPY","US500","NAS100")]
    static_margin_sum = sum(margins) if all(x is not None for x in margins) else None
    supported = [g for g,x in results.items() if
                 x["selection"] is not None and x["selection"]["sourceOnlyPositiveBoth"]]
    report=dict(schema="MXM_GEP1_AUTHENTIC_TWO_FAMILY_SYSTEM_V1",
                originalSourceAuthentication=authentication,
                rawSealedSourceM5Bars=sum(map(len,bars.values())),
                originalAuthenticCostContexts=len(costs),
                sourceReusedReadOnly=True,
                prospectiveProtocolSha256=hashlib.sha256(original).hexdigest(),
                originalRuns=p["source"]["preexistingAuthenticatedRuns"],
                runId=int(os.environ.get("GITHUB_RUN_ID","0")),
                groups=results,selectionConditionalSupport=supported,
                maximumGroups=3,closedPredictorsCalled=False,
                previouslyExposedWeeks=52,independentConfirmation=False,
                currentThreeTargetMinimumMarginSumEur=static_margin_sum,
                staticThreeConcurrentMinimumMarginsBelow300=(static_margin_sum is not None
                                                               and static_margin_sum < 300),
                costModel="CONDITIONAL_ONLY_NOT_BROKER_EXECUTION",
                nativePhysicalFundingQualification=False,nativeCSharpFundedTrades=0,
                netFundedEur=None,hard21Certified=False,
                continuousFloatingDrawdown30Certified=False,
                noBrokerRequests=0,closedStudyReruns=0,ordersSubmitted=0,cloudActivated=False)
    Path("gep1-authentic-public.json").write_text(
        json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    print("GEP1_SUMMARY "+json.dumps({
        k:v for k,v in report.items() if k in ("runId","rawSealedSourceM5Bars",
        "originalAuthenticCostContexts","selectionConditionalSupport",
        "currentThreeTargetMinimumMarginSumEur","nativeCSharpFundedTrades",
        "hard21Certified","noBrokerRequests","ordersSubmitted")},sort_keys=True),flush=True)
    for name,result in results.items():
        print("GEP1_GROUP "+json.dumps(dict(name=name,**result),sort_keys=True),flush=True)


if __name__=="__main__":
    run()
