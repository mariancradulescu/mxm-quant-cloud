"""CIT1 frozen protocol: intraday inventory transfer on globally exposed data.

Two fixed tests of economic mechanisms, no parameter fitting or promotion:
* GER40 morning impulse losing follow-through as US liquidity approaches.
* XAUUSD disagreement with the completed EURUSD/GBPUSD common USD move.
"""
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist, mean

from .integrated_predictive_funded import cost_context
from .multiscale_conditional_research import extract_costs, recover

M5 = 300_000
HOUR = 12 * M5
DAY = 24 * HOUR
WEEK = 7 * DAY
START = 1762128000000
SPLITS = ((0, 26), (26, 39), (39, 52))
GROUPS = (("GER40", 14), ("XAUUSD", 13))
MIN_WEEKS = 10
MIN_LABELS = 30


def sign(value):
    return (value > 0) - (value < 0)


def close_return(prices, start, end):
    if start not in prices or end not in prices:
        return None
    return math.log(prices[end] / prices[start])


def signal(symbol, views, now):
    own = views[symbol]
    last = close_return(own, now - HOUR, now)
    if last is None:
        return None
    if symbol == "GER40":
        morning = close_return(own, now - 6 * HOUR, now - 2 * HOUR)
        if morning is None:
            return None
        if sign(morning) == -sign(last) and last:
            return sign(last), sign(morning)
    else:
        eur = close_return(views["EURUSD"], now - HOUR, now)
        gbp = close_return(views["GBPUSD"], now - HOUR, now)
        if eur is None or gbp is None:
            return None
        if sign(eur) == sign(gbp) == -sign(last) and last:
            return sign(eur), sign(last)
    return (0, 0)


def model_costs(samples):
    costs = cost_context(samples)
    for symbol, cost in costs.items():
        # Conversion friction is applied to signed P&L, separately from the
        # existing spread, fee and slippage sensitivity.
        cost["conversionWedge"] = max(
            float(x["ProfitConversionRate"]) for x in samples if x["Symbol"] == symbol
        )
    return costs


def scan(symbol, hour, views, cost, first, end):
    counts = Counter()
    weeks = defaultdict(list)
    prices = views[symbol]
    for day in range(first * 7, end * 7):
        now = START + day * DAY + hour * HOUR
        if datetime.fromtimestamp(now / 1000, timezone.utc).weekday() >= 5:
            continue
        counts["decisionClocks"] += 1
        pair = signal(symbol, views, now)
        if pair is None:
            counts["missingFeature"] += 1
            continue
        side, benchmark = pair
        if not side:
            counts["noSignal"] += 1
            continue
        counts["signals"] += 1
        entry = now + M5
        # Source-close label only. Stop monitoring the shared benchmark clock
        # when the strategy's signed move fails its last completed 15m check.
        exit_at = entry + HOUR
        for check in range(entry + 3 * M5, entry + HOUR, 3 * M5):
            move = close_return(prices, entry, check)
            if move is None:
                exit_at = None
                break
            if side * move <= 0:
                exit_at = check + M5
                break
        if exit_at is None or (outcome := close_return(prices, entry, exit_at)) is None:
            counts["missingSourceOutcome"] += 1
            continue
        counts["completePredictiveLabels"] += 1
        gross = 10000 * side * outcome
        matched = 10000 * benchmark * outcome
        row = dict(gross=gross, matchedGross=matched, grossIncrement=gross - matched)
        if cost is not None:
            rollover = cost["swapMinute"]
            if cost["fundingKnown"] and entry % DAY < rollover * 60_000 <= exit_at % DAY:
                counts["knownRolloverCostWindowExcluded"] += 1
            elif not cost["fundingKnown"]:
                counts["missingFundingTerms"] += 1
            else:
                # Log-return basis-point sensitivity, not a fill or EUR ledger.
                wedge = cost["conversionWedge"]
                for scenario in ("central", "adverse"):
                    friction = cost[scenario + "Bps"]
                    row[scenario] = gross - abs(gross) * wedge - friction
                    comparator = matched - abs(matched) * wedge - friction
                    row[scenario + "Increment"] = row[scenario] - comparator
                counts["conditionalCostLabels"] += 1
        else:
            counts["missingCostContext"] += 1
        weeks[day // 7].append(row)
    return counts, weeks


def estimate(weeks, key, first, end):
    active = {
        week: mean(values)
        for week, rows in weeks.items()
        if (values := [row[key] for row in rows if key in row])
    }
    if not active:
        return None
    average = mean(active.values())
    result = dict(bps=average, activeWeeks=len(active), adjustedLowerBps=None)
    if len(active) < MIN_WEEKS:
        return result
    errors = [active[week] - average if week in active else 0 for week in range(first, end)]
    variance = sum(x * x for x in errors)
    for lag in range(1, 4):
        variance += 2 * (1 - lag / 4) * sum(a * b for a, b in zip(errors, errors[lag:]))
    # Two groups × four tests × two selection/audit partitions. HAC normal
    # interval is exploratory, especially with thirteen calendar clusters.
    critical = NormalDist().inv_cdf(1 - 0.05 / 16)
    result["adjustedLowerBps"] = average - critical * math.sqrt(max(0, variance)) / len(active)
    return result


def score(symbol, hour, views, cost):
    phases = {}
    for phase, (first, end) in zip(("development", "selection", "exposedAudit"), SPLITS):
        counts, weeks = scan(symbol, hour, views, cost, first, end)
        keys = ("gross", "matchedGross", "grossIncrement", "central", "centralIncrement",
                "adverse", "adverseIncrement")
        phases[phase] = dict(counts=dict(counts), metrics={
            key: estimate(weeks, key, first, end) for key in keys
        })
    gates = ("gross", "grossIncrement", "adverse", "adverseIncrement")
    supported = all(
        phases[phase]["counts"].get("conditionalCostLabels", 0) >= MIN_LABELS
        and all((stat := phases[phase]["metrics"][key]) is not None
                and stat["adjustedLowerBps"] is not None and stat["adjustedLowerBps"] > 0
                for key in gates)
        for phase in ("selection", "exposedAudit")
    )
    return dict(phases=phases, costContext=cost, clearsExploratoryGate=supported,
                currentMinimumMarginBelow300=None if cost is None else cost["minimumMarginEur"] < 300,
                fundedReplay="UNAVAILABLE_WITHOUT_MATCHED_BID_ASK_AND_CONTRACT_CLOCKS")


def main():
    custody = json.loads(Path("research/hrc1_protocol.json").read_text())
    if [row["run"] for row in custody["source"]] != [41724643418, 41735441128]:
        raise ValueError("CIT1_SOURCE_IDENTITY")
    bars, samples, authentication = {}, [], []
    for row in custody["source"]:
        source, decoded, proof = recover(Path(row["folder"]), row["run"], row["hash"],
                                         row["schema"], row["protocol"])
        if not proof["rawAccountAndBarsReconstructed"] or bars.keys() & source["bars"].keys():
            raise ValueError("CIT1_SOURCE_BINDING")
        bars.update(source["bars"])
        observations, _ = extract_costs(source, decoded)
        samples.extend(observations)
        authentication.append(proof)
    if len(bars) != 12 or sum(map(len, bars.values())) != 836087 or len(samples) != 166:
        raise ValueError("CIT1_SOURCE_COUNTS")
    views = {symbol: {row[1]: row[5] for row in bars[symbol]}
             for symbol in ("GER40", "XAUUSD", "EURUSD", "GBPUSD")}
    costs = model_costs(samples)
    report = dict(
        study="CIT1", runId=int(os.environ.get("GITHUB_RUN_ID", "0")),
        protocolSha256=hashlib.sha256(Path("research/CIT1.md").read_bytes()).hexdigest(),
        source=authentication, sourceBars=836087, originalCostContexts=len(samples),
        independentlyConfirmed=False, closedStudiesReplayed=0, initialCapitalEur=300,
        ordersSubmitted=0, cloudActivated=False, netCentralEur=None, netAdverseEur=None,
        hard21=None, globalDrawdown=None, fundedModelClosures=0,
        mechanisms={symbol: score(symbol, hour, views, costs.get(symbol))
                    for symbol, hour in GROUPS},
    )
    output = json.dumps(report, indent=2, allow_nan=False) + "\n"
    Path("cit1-public.json").write_text(output)
    print(output)


if __name__ == "__main__":
    main()
