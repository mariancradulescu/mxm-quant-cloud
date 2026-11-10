"""RCG1: causal intermarket regime confirmation against matched directional exposure."""
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist, mean

from .cit1_research import M5, HOUR, DAY, START, SPLITS, close_return, model_costs, sign
from .multiscale_conditional_research import extract_costs, recover

GROUPS = {
    "CADJPY_RISK_CONFIRM_EURUSD": ("EURUSD", "USDJPY", "USDCAD", -1),
    "CADJPY_RISK_CONFIRM_GBPUSD": ("GBPUSD", "USDJPY", "USDCAD", -1),
    "EU_BREADTH_CONFIRM_US500": ("US500", "GER40", "UK100", 1),
    "EU_BREADTH_CONFIRM_NAS100": ("NAS100", "GER40", "UK100", 1),
}
HOURS = (8, 10, 12, 14, 16, 18)
METRICS = ("gross", "central", "adverse")


def observations(views, group, cost, first, end):
    target, a, b, orientation = group
    prices = views[target]
    counts = Counter()
    weeks = defaultdict(lambda: defaultdict(list))
    opportunities = Counter()
    for day in range(first * 7, end * 7):
        if day % 7 >= 5:
            continue
        for hour in HOURS:
            now = START + day * DAY + hour * HOUR
            counts["scheduled"] += 1
            own, ra, rb = (close_return(views[s], now - HOUR, now) for s in (target, a, b))
            if any(x is None for x in (own, ra, rb)):
                counts["missingFeatures"] += 1
                continue
            side = sign(own)
            if side == 0:
                counts["flatTarget"] += 1
                continue
            # CADJPY = USDJPY / USDCAD. For index breadth both regional
            # constituents must agree with the target direction.
            confirmed = (sign(ra + orientation * rb) == side if orientation < 0
                         else sign(ra) == sign(rb) == side)
            if confirmed:
                counts["causalOpportunities"] += 1
                opportunities[day // 7] += 1
            entry, exit_at = now + M5, now + 7 * M5
            outcome = close_return(prices, entry, exit_at)
            if outcome is None:
                counts["missingLabels"] += 1
                continue
            counts["directionalLabels"] += 1
            gross = 10000 * side * outcome
            result = {"gross": gross}
            if (cost and cost["fundingKnown"]
                    and not entry % DAY < cost["swapMinute"] * 60000 <= exit_at % DAY):
                for case in ("central", "adverse"):
                    result[case] = gross - abs(gross) * cost["conversionWedge"] - cost[case + "Bps"]
            if confirmed:
                counts["selectedLabels"] += 1
                counts["selectedCostLabels"] += int("adverse" in result)
            weeks[day // 7][hour, side].append((confirmed, result))
    return counts, weeks, opportunities


def paired_weeks(weeks, metric):
    results = {}
    for week, strata in weeks.items():
        strategy, benchmark = [], []
        for observations in strata.values():
            pool = [row[metric] for _, row in observations if metric in row]
            chosen = [row[metric] for selected, row in observations if selected and metric in row]
            if chosen:
                strategy.extend(chosen)
                benchmark.extend([mean(pool)] * len(chosen))
        if strategy:
            results[week] = (mean(strategy), mean(benchmark), mean(strategy) - mean(benchmark))
    return results


def lower(values, first, end):
    if len(values) < 10:
        return None
    average = mean(values.values())
    errors = [values[week] - average if week in values else 0 for week in range(first, end)]
    variance = sum(x * x for x in errors)
    for lag in range(1, 4):
        variance += 2 * (1 - lag / 4) * sum(a * b for a, b in zip(errors, errors[lag:]))
    critical = NormalDist().inv_cdf(1 - 0.05 / 32)
    return average - critical * math.sqrt(max(0, variance)) / len(values)


def metrics(weeks, first, end):
    output = {}
    for metric in METRICS:
        pairs = paired_weeks(weeks, metric)
        names = ("strategyBps", "matchedBps", "incrementBps")
        values = {name: mean(row[i] for row in pairs.values()) if pairs else None
                  for i, name in enumerate(names)}
        for i, name in ((0, "strategyLowerBps"), (2, "incrementLowerBps")):
            values[name] = lower({w: row[i] for w, row in pairs.items()}, first, end)
        output[metric] = dict(values, activeWeeks=len(pairs))
    return output


def clears(result):
    if result["counts"].get("selectedCostLabels", 0) < 30:
        return False
    for mode in ("gross", "adverse"):
        for key in ("strategyLowerBps", "incrementLowerBps"):
            bound = result["metrics"][mode][key]
            if bound is None or bound <= 0:
                return False
    return True


def main():
    custody = json.loads(Path("research/hrc1_protocol.json").read_text())
    if [row["run"] for row in custody["source"]] != [41724643418, 41735441128]:
        raise ValueError("RCG1_SOURCE_IDENTITY")
    bars, samples, authentication = {}, [], []
    for row in custody["source"]:
        source, decoded, proof = recover(Path(row["folder"]), row["run"], row["hash"],
                                         row["schema"], row["protocol"])
        if not proof["rawAccountAndBarsReconstructed"] or bars.keys() & source["bars"].keys():
            raise ValueError("RCG1_SOURCE_BINDING")
        bars.update(source["bars"])
        observed, _ = extract_costs(source, decoded)
        samples.extend(observed)
        authentication.append(proof)
    if len(bars) != 12 or sum(map(len, bars.values())) != 836087 or len(samples) != 166:
        raise ValueError("RCG1_SOURCE_COUNTS")
    views = {symbol: {row[1]: row[5] for row in bars[symbol]}
             for group in GROUPS.values() for symbol in group[:3]}
    costs = model_costs(samples)
    results = {}
    combined = Counter()
    for name, group in GROUPS.items():
        cost = costs.get(group[0])
        phases = {}
        for phase, (first, end) in zip(("development", "selection", "exposedAudit"), SPLITS):
            counts, weeks, opportunities = observations(views, group, cost, first, end)
            combined.update(opportunities)
            phases[phase] = dict(counts=dict(counts), metrics=metrics(weeks, first, end),
                                 opportunitiesByWeek=[opportunities[w] for w in range(first, end)])
        candidate = bool(cost and cost["minimumMarginEur"] < 300
                         and all(clears(phases[p]) for p in ("selection", "exposedAudit")))
        results[name] = dict(phases=phases, minimumMarginEur=cost and cost["minimumMarginEur"],
                             originalCostSamples=cost and cost["observed"], candidate=candidate)
    report = dict(
        study="RCG1", runId=int(os.environ.get("GITHUB_RUN_ID", "0")),
        protocolSha256=hashlib.sha256(Path("research/RCG1.md").read_bytes()).hexdigest(),
        source=authentication, sourceBars=836087, originalCostContexts=len(samples),
        groups=results, rawSystemOpportunitiesByWeek=[combined[w] for w in range(52)],
        weeksWithAtLeast21RawOpportunities=sum(combined[w] >= 21 for w in range(52)),
        initialCapitalEur=300, fundedClosures=0, netCentralEur=None, netAdverseEur=None,
        hard21=None, floatingDrawdown=None, independentlyConfirmed=False,
        closedStudiesReplayed=0, ordersSubmitted=0, cloudActivated=False,
    )
    output = json.dumps(report, indent=2, allow_nan=False) + "\n"
    Path("rcg1-public.json").write_text(output)
    print(output)


if __name__ == "__main__":
    main()
