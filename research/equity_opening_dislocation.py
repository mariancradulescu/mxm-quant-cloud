"""Frozen development test on archived original Pepperstone US-24 bars."""
import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from research.equity_clock_payoff import ARCHIVE_SHA, END, M5, NY, START, read_archive


def clock(day, hour, minute=0):
    return int(datetime(day.year, day.month, day.day, hour, minute, tzinfo=NY).timestamp())


def summarize(weeks):
    paired = [v for w in weeks for v in w["paired"]]
    available = [v for w in weeks for v in w["available"]]
    uniform = [v for w in weeks for v in w["uniform"]]
    return {
        "paired_clocks": len(paired),
        "rank_bps": float(np.mean([v[0] for v in paired])) if paired else None,
        "opening_reversal_bps": float(np.mean([v[1] for v in paired])) if paired else None,
        "increment_bps": float(np.mean([v[0] - v[1] for v in paired])) if paired else None,
        "available_model_clocks": len(available),
        "available_model_bps": float(np.mean([v[0] for v in available])) if available else None,
        "median_favorable_adverse_excursion_bps":
            np.median(np.asarray(available)[:, 1:], axis=0).tolist() if available else None,
        "model_p05_bps": float(np.quantile([v[0] for v in available], .05)) if available else None,
        "uniform_complete_clocks": len(uniform),
        "uniform_bps": float(np.mean([v[1] for v in uniform])) if uniform else None,
        "rank_bps_on_uniform_clocks": float(np.mean([v[0] for v in uniform])) if uniform else None,
    }


def evaluate(bars):
    weeks = []
    for week_index in range((END - START).days // 7):
        start = START + timedelta(weeks=week_index)
        counts = dict(scheduled=5, no_cohort=0, no_signal=0, selected=0,
                      model_path_missing=0, benchmark_path_missing=0, uniform_path_missing=0)
        week = dict(week=start.isoformat(), counts=counts, paired=[], available=[], uniform=[])
        for weekday in range(5):
            day = start + timedelta(days=weekday)
            prior = day - timedelta(days=3 if weekday == 0 else 1)
            premarket, decision = clock(day, 9, 25), clock(day, 9, 45)
            previous = clock(prior, 16)
            eligible = {name: closes for name, closes in bars.items()
                        if all(t in closes for t in (previous, premarket, decision))}
            if len(eligible) < 8:
                counts["no_cohort"] += 1
                continue
            names = tuple(eligible)
            overnight = np.asarray([np.log(eligible[s][premarket] / eligible[s][previous])
                                    for s in names])
            opening = np.asarray([np.log(eligible[s][decision] / eligible[s][premarket])
                                  for s in names])
            overnight -= overnight.mean()
            opening -= opening.mean()
            valid = (overnight > 0) & (opening < 0)
            if not valid.any():
                counts["no_signal"] += 1
                continue
            chosen = names[int(np.argmin(np.where(valid, opening, np.inf)))]
            control = names[int(np.argmin(opening))]
            counts["selected"] += 1
            paths = {}
            for s, closes in eligible.items():
                prices = [closes.get(decision + j * M5) for j in range(1, 11)]
                if None not in prices:
                    moves = 10000 * np.log(np.asarray(prices) / prices[0])
                    paths[s] = (float(moves[-1]), float(max(moves)), float(min(moves)))
            counts["model_path_missing"] += int(chosen not in paths)
            counts["benchmark_path_missing"] += int(control not in paths)
            counts["uniform_path_missing"] += int(len(paths) != len(eligible))
            if chosen in paths:
                actual = paths[chosen]
                week["available"].append(actual)
                if control in paths:
                    week["paired"].append((actual[0], paths[control][0]))
                if len(paths) == len(eligible):
                    week["uniform"].append((actual[0], float(np.mean([p[0] for p in paths.values()]))))
        weeks.append(week)
    return weeks


def uncertainty(weeks):
    sums = np.asarray([[len(w["paired"]), sum(p[0] for p in w["paired"]),
                        sum(p[0] - p[1] for p in w["paired"])] for w in weeks])
    n = len(weeks)
    rng = np.random.default_rng(20261113)
    starts = rng.integers(0, n - 3, (5000, (n + 3) // 4))
    positions = (starts[..., None] + np.arange(4)).reshape(5000, -1)[:, :n]
    draws = sums[positions].sum(axis=1)
    draws = draws[draws[:, 0] > 0]
    return (np.quantile(draws[:, 1:] / draws[:, :1], [.025, .975], axis=0).T.tolist()
            if len(draws) else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bars, source = read_archive(args.archive)
    weeks = evaluate(bars)
    halves = [summarize(weeks[:25]), summarize(weeks[25:])]
    result = {
        "classification": "EXPOSED_DEVELOPMENT_BID_BAR_GROSS_PROXY",
        "archive_sha256": ARCHIVE_SHA,
        "protocol_sha256": sha256(Path(__file__).with_name("EQUITY_OPENING_DISLOCATION.md").read_bytes()).hexdigest(),
        "source": source, "hold_minutes": 45, "cash_bps": 0,
        "counts": {k: sum(w["counts"][k] for w in weeks) for k in weeks[0]["counts"]},
        "overall": summarize(weeks), "chronological_halves": halves,
        "descriptive_95pct_4week_block_absolute_and_increment_bps": uncertainty(weeks),
        "cost_recovery_screen_passed": all(h["paired_clocks"] and min(h["rank_bps"], h["increment_bps"]) > 0
                                           for h in halves),
        "weekly": [dict(week=w["week"], counts=w["counts"], **summarize([w])) for w in weeks],
        "gross_eur": None, "net_eur": None, "funded_round_trips": 0,
        "new_broker_requests": 0, "orders_submitted": 0, "cloud_activated": False,
        "independent_confirmation": False,
    }
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
