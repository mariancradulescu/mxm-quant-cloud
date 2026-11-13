"""Evaluate the frozen altcoin breadth hypothesis on original development bars."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from hashlib import file_digest, sha256
import io
import json
from math import isfinite, log
from pathlib import Path
import re
from statistics import mean, median
from zipfile import ZipFile

import numpy as np

from research.equity_clock_payoff import ARCHIVE_SHA, END, M5, START

NAMES = ("ATMUSD", "GLMRUSD", "POLUSD", "TRUMPUSD", "XLMUSD")
TARGETS = ("XLMUSD", "POLUSD")
POLICIES = ("peer", "own", "long", "short", "cash")


def load_source(path):
    with path.open("rb") as handle:
        if file_digest(handle, "sha256").hexdigest() != ARCHIVE_SHA:
            raise ValueError("Original archive digest mismatch")
    commitment = re.search(r'HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT = "([0-9a-f]+)"',
                           Path(__file__).with_name("collect.py").read_text())[1]
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read("CAPTURE_MANIFEST.json"))
        raw = archive.read("V3_CAPTURE_PAYLOAD.json")
        payload = json.loads(raw)
        if (sha256(raw).hexdigest() != manifest["sha256_per_canonical_payload"]["V3_CAPTURE_PAYLOAD.json"]
                or sha256(manifest["account_fingerprint"].encode()).hexdigest() != commitment
                or payload["account_fingerprint_sha256"] != manifest["account_fingerprint"]
                or payload["classification"] != "DEVELOPMENT_ONLY"
                or not manifest["read_only_assertion"] or manifest["orders_placed"]):
            raise ValueError("Original account or manifest mismatch")
        series = {row["broker_symbol"]: row for row in payload["series"]}
        quality = {row["symbol"]: row for row in json.loads(archive.read("DATA_QUALITY_TABLE.json"))["rows"]}
        bars, provenance = {}, {}
        for name in NAMES:
            row = series[name]
            data = archive.read(row["file"])
            digest = sha256(data).hexdigest()
            if digest != row["sha256"]:
                raise ValueError(f"Invalid series digest for {name}")
            closes = {}
            for item in csv.DictReader(io.StringIO(data.decode())):
                at = int(datetime.fromisoformat(item["time_utc"]).timestamp()) + M5
                value = float(item["close"])
                if at % M5 or at in closes or not isfinite(value) or value <= 0:
                    raise ValueError(f"Invalid bar for {name}")
                closes[at] = value
            if len(closes) != row["row_count"]:
                raise ValueError(f"Invalid row count for {name}")
            bars[name] = closes
            provenance[name] = {"sha256": digest, "bars": len(closes),
                                "indicative_minimum_margin_eur": quality[name]["minimum_margin_estimate_for_EUR200"]}
    return bars, provenance


def direction(x):
    return (x > 0) - (x < 0)


def signal(moves, target):
    peers = [moves[name] for name in NAMES if name != target]
    broad = median(peers)
    side = direction(broad)
    return side if (abs(broad) >= 25 and sum(direction(x) == side for x in peers) >= 3
                    and abs(moves[target]) <= abs(broad) / 2) else 0


def evaluate(bars):
    result = {target: [] for target in TARGETS}
    for week in range((END - START).days // 7):
        start = START + timedelta(weeks=week)
        records = {target: {"week": start.isoformat(), "scheduled": 28, "missing_decision": 0,
                            "intents": 0, "missing_path": 0, "weekend_priced": 0,
                            "own_same_flat_opposite": [0] * 3, "outcomes": []} for target in TARGETS}
        for weekday in range(7):
            day = start + timedelta(days=weekday)
            for hour in (6, 10, 14, 18):
                at = int(datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc).timestamp())
                clocks = range(at - 12 * M5, at + 1, M5)
                if any(clock not in bars[name] for name in NAMES for clock in clocks):
                    for record in records.values():
                        record["missing_decision"] += 1
                    continue
                moves = {name: 10000 * log(bars[name][at] / bars[name][at - 12 * M5]) for name in NAMES}
                for target, record in records.items():
                    side = signal(moves, target)
                    if not side:
                        continue
                    record["intents"] += 1
                    path = [bars[target].get(at + j * M5) for j in range(1, 14)]
                    if None in path:
                        record["missing_path"] += 1
                        continue
                    own = direction(moves[target])
                    record["own_same_flat_opposite"][1 - side * own] += 1
                    record["weekend_priced"] += int(weekday >= 5)
                    change = [10000 * log(price / path[0]) for price in path]
                    outcome = change[-1]
                    signed = [side * move for move in change]
                    record["outcomes"].append((side * outcome, own * outcome, outcome, -outcome,
                                               0., max(signed), min(signed)))
        for target in TARGETS:
            result[target].append(records[target])
    return result


def summary(weeks):
    rows = [row for w in weeks for row in w["outcomes"]]
    return {
        "priced": len(rows),
        "mean_gross_bps": {p: mean(r[i] for r in rows) if rows else None
                           for i, p in enumerate(POLICIES)},
        "increment_vs_own_bps": mean(r[0] - r[1] for r in rows) if rows else None,
        "median_favorable_adverse_excursion_bps":
            [median(r[i] for r in rows) for i in (5, 6)] if rows else None,
    }


def results(weeks):
    overall = summary(weeks)
    phases = [summary(weeks[:25]), summary(weeks[25:])]
    totals = np.asarray([[len(w["outcomes"]), sum(r[0] for r in w["outcomes"]),
                          sum(r[0] - r[1] for r in w["outcomes"])] for w in weeks])
    n = len(weeks)
    rng = np.random.default_rng(20261113)
    starts = rng.integers(0, n - 3, (5000, (n + 3) // 4))
    indices = (starts[..., None] + np.arange(4)).reshape(5000, -1)[:, :n]
    samples = totals[indices].sum(axis=1)
    samples = samples[samples[:, 0] > 0]
    gross = overall["mean_gross_bps"]
    return {
        "counts": {k: sum(w[k] for w in weeks)
                   for k in ("scheduled", "missing_decision", "intents", "missing_path", "weekend_priced")},
        "own_same_flat_opposite": [sum(w["own_same_flat_opposite"][i] for w in weeks) for i in range(3)],
        "overall": overall, "chronological_segments": phases,
        "descriptive_95pct_4week_interval_absolute_and_increment_bps":
            np.quantile(samples[:, 1:] / samples[:, :1], [.025, .975], axis=0).T.tolist()
            if len(samples) else None,
        "cost_verification_screen_passed": bool(
            all(p["priced"] and min(p["mean_gross_bps"]["peer"], p["increment_vs_own_bps"]) > 0
                for p in phases) and gross["peer"] > max(gross["long"], gross["short"])),
        "weekly": [dict({k: v for k, v in w.items() if k != "outcomes"}, **summary([w])) for w in weeks],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bars, provenance = load_source(args.archive)
    report = {
        "classification": "EXPOSED_BID_BAR_GROSS_PROXY",
        "archive_sha256": ARCHIVE_SHA,
        "protocol_sha256": sha256(Path(__file__).with_name("ALTCOIN_BREADTH_DIFFUSION.md").read_bytes()).hexdigest(),
        "source": provenance, "hold_minutes": 60,
        "targets": {t: results(w) for t, w in evaluate(bars).items()},
        "gross_eur": None, "net_eur": None, "funded_round_trips": 0,
        "new_broker_requests": 0, "orders_submitted": 0, "cloud_activated": False,
        "independent_confirmation": False,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
