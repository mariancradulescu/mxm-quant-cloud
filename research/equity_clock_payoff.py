"""Exposed development comparison on the original Pepperstone US-24 archive."""
import argparse
import csv
from datetime import date, datetime, timedelta
from hashlib import file_digest, sha256
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import numpy as np

ARCHIVE_SHA = "09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259"
START = date(2025, 9, 22)
END = date(2026, 9, 14)
NY = ZoneInfo("America/New_York")
CLOCKS = tuple(range(600, 931, 30))
M5 = 300


def read_archive(path):
    with path.open("rb") as source:
        if file_digest(source, "sha256").hexdigest() != ARCHIVE_SHA:
            raise ValueError("Original archive hash mismatch")
    binding = re.search(r'HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT = "([0-9a-f]+)"',
                        Path(__file__).with_name("collect.py").read_text())[1]
    with ZipFile(path) as bundle:
        capture = json.loads(bundle.read("CAPTURE_MANIFEST.json"))
        payload_bytes = bundle.read("V3_CAPTURE_PAYLOAD.json")
        payload = json.loads(payload_bytes)
        if (sha256(capture["account_fingerprint"].encode()).hexdigest() != binding
                or payload["account_fingerprint_sha256"] != capture["account_fingerprint"]
                or not capture["read_only_assertion"] or capture["orders_placed"]
                or payload["classification"] != "DEVELOPMENT_ONLY"
                or sha256(payload_bytes).hexdigest() !=
                capture["sha256_per_canonical_payload"]["V3_CAPTURE_PAYLOAD.json"]):
            raise ValueError("Source commitment mismatch")
        identity = json.loads(bundle.read("SELECTED_IDENTITY_MANIFEST.json"))
        series = {row["broker_symbol"]: row for row in payload["series"]}
        names = sorted(row["broker_symbol"] for row in identity["symbols"]
                       if row["broker_symbol"].endswith(".US-24"))
        if len(names) != 17 or len(set(names)) != 17:
            raise ValueError("Fixed equity cohort mismatch")
        quality = {row["symbol"]: row for row in
                   json.loads(bundle.read("DATA_QUALITY_TABLE.json"))["rows"]}
        bars = {}
        provenance = {}
        for name in names:
            info = series[name]
            data = bundle.read(info["file"])
            digest = sha256(data).hexdigest()
            if digest != info["sha256"]:
                raise ValueError(f"Series commitment mismatch for {name}")
            closes = {}
            for row in csv.DictReader(io.StringIO(data.decode())):
                at = int(datetime.fromisoformat(row["time_utc"]).timestamp()) + M5
                price = float(row["close"])
                if at % M5 or at in closes or not np.isfinite(price) or price <= 0:
                    raise ValueError(f"Invalid close for {name}")
                closes[at] = price
            if len(closes) != info["row_count"]:
                raise ValueError(f"Unexpected series count for {name}")
            bars[name] = closes
            provenance[name] = {
                "bars": len(closes), "sha256": digest,
                "minimum_margin_probe_eur": quality[name]["minimum_margin_estimate_for_EUR200"],
            }
    return bars, provenance


def make_panel(bars):
    days = (END - START).days // 7 * 5
    shape = (days, len(CLOCKS), len(bars))
    ready = np.zeros(shape, dtype=bool)
    outcomes = np.full((*shape, 3), np.nan)
    for day in range(days):
        current = START + timedelta(weeks=day // 5, days=day % 5)
        for clock_index, minute in enumerate(CLOCKS):
            clock = int(datetime(current.year, current.month, current.day,
                                 minute // 60, minute % 60, tzinfo=NY).timestamp())
            for name_index, closes in enumerate(bars.values()):
                ready[day, clock_index, name_index] = clock in closes
                path = [closes.get(clock + i * M5) for i in range(1, 7)]
                if not ready[day, clock_index, name_index] or any(p is None for p in path):
                    continue
                moves = 10000 * np.log(np.asarray(path) / path[0])
                outcomes[day, clock_index, name_index] = (moves[-1], max(moves), min(moves))
    return ready, outcomes


def scores(training):
    finite = np.isfinite(training)
    counts = finite.sum(axis=2, keepdims=True)
    baseline = np.divide(np.nansum(training, axis=2, keepdims=True), counts,
                         out=np.zeros_like(counts, dtype=float), where=counts >= 8)
    residuals = np.where(counts >= 8, training - baseline, np.nan)
    result = []
    for axis in (0, (0, 1)):
        count = np.isfinite(residuals).sum(axis=axis)
        result.append(np.divide(np.nansum(residuals, axis=axis), count,
                                out=np.full(count.shape, np.nan), where=count >= 20))
    return result


def score_week(ready, outcomes, start, names):
    timed, pooled = scores(outcomes[start - 40:start, :, :, 0])
    compared, observed, selections = [], [], {}
    skipped = dict(no_decision=0, model_path_missing=0, pooled_path_missing=0,
                   incomplete_uniform_path=0)
    for day in range(start, start + 5):
        for clock in range(len(CLOCKS)):
            eligible = ready[day, clock] & np.isfinite(timed[clock]) & np.isfinite(pooled)
            if not eligible.any():
                skipped["no_decision"] += 1
                continue
            model = np.argmax(np.where(eligible, timed[clock], -np.inf))
            control = np.argmax(np.where(eligible, pooled, -np.inf))
            selections[names[model]] = selections.get(names[model], 0) + 1
            paths = outcomes[day, clock]
            actual = paths[model]
            benchmark = paths[control, 0]
            basket = paths[eligible, 0]
            model_ok = bool(np.isfinite(actual[0]))
            control_ok = bool(np.isfinite(benchmark))
            uniform_ok = bool(np.isfinite(basket).all())
            skipped["model_path_missing"] += int(not model_ok)
            skipped["pooled_path_missing"] += int(not control_ok)
            skipped["incomplete_uniform_path"] += int(not uniform_ok)
            if model_ok:
                observed.append(actual)
            if model_ok and control_ok and uniform_ok:
                compared.append([*actual, benchmark, basket.mean()])
    return np.asarray(compared).reshape(-1, 5), np.asarray(observed).reshape(-1, 3), selections, skipped


def payoff(rows):
    if not len(rows):
        return None
    return {
        "gross_bps": float(rows[:, 0].mean()),
        "gross_p05_p50_p95_bps": np.quantile(rows[:, 0], [.05, .5, .95]).tolist(),
        "median_favorable_excursion_bps": float(np.median(rows[:, 1])),
        "median_adverse_excursion_bps": float(np.median(rows[:, 2])),
        "adverse_excursion_p05_bps": float(np.quantile(rows[:, 2], .05)),
        "losing_fraction": float(np.mean(rows[:, 0] < 0)),
    }


def summary(rows):
    return {
        "paired_clocks": len(rows), "model": payoff(rows),
        "cash_bps": 0,
        "pooled_bps": float(rows[:, 3].mean()),
        "uniform_one_position_bps": float(rows[:, 4].mean()),
        "increment_vs_pooled_bps": float(np.mean(rows[:, 0] - rows[:, 3])),
        "increment_vs_uniform_bps": float(np.mean(rows[:, 0] - rows[:, 4])),
    }


def uncertainty(weeks):
    sums = np.asarray([[len(w), w[:, 0].sum(), (w[:, 0] - w[:, 3]).sum(),
                        (w[:, 0] - w[:, 4]).sum()] for w in weeks])
    n = len(weeks)
    rng = np.random.default_rng(20261113)
    starts = rng.integers(0, n - 3, (5000, (n + 3) // 4))
    indices = (starts[..., None] + np.arange(4)).reshape(5000, -1)[:, :n]
    draws = sums[indices].sum(axis=1)
    intervals = np.quantile(draws[:, 1:] / draws[:, :1], [.025, .975], axis=0).T
    return dict(zip(("gross", "increment_vs_pooled", "increment_vs_uniform"), intervals.tolist()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    bars, provenance = read_archive(args.archive)
    ready, paths = make_panel(bars)
    records, paired, observed = [], [], []
    for start in range(60, len(ready), 5):
        matched, available, selections, skipped = score_week(ready, paths, start, tuple(bars))
        paired.append(matched)
        observed.append(available)
        records.append(dict(
            week=(START + timedelta(weeks=start // 5)).isoformat(),
            paired_clocks=len(matched), available_model_clocks=len(available),
            model_paired_gross_bps_sum=float(matched[:, 0].sum()),
            selections_by_symbol=selections, missing=skipped,
        ))
    all_rows = np.concatenate(paired)
    phases = [summary(np.concatenate(paired[:19])), summary(np.concatenate(paired[19:]))]
    counts = [len(w) for w in paired]
    selected_counts = [len(w) for w in observed]
    result = {
        "classification": "EXPOSED_DEVELOPMENT_BID_BAR_PAYOFF_PROXY",
        "archive_sha256": ARCHIVE_SHA, "original_account_commitment_matched": True,
        "protocol_sha256": sha256(Path(__file__).with_name("EQUITY_CLOCK_PAYOFF.md").read_bytes()).hexdigest(),
        "source": provenance, "scheduled_clocks": len(records) * 5 * len(CLOCKS),
        "holding_minutes": 25, "overall": summary(all_rows), "chronology": phases,
        "available_case": {"clocks": sum(selected_counts), **payoff(np.concatenate(observed))},
        "paired_weekly_count_min_median_max": [min(counts), float(np.median(counts)), max(counts)],
        "95pct_descriptive_week_block_bps": uncertainty(paired),
        "both_segments_positive_gross_and_increments": all(
            min(s["model"]["gross_bps"], s["increment_vs_pooled_bps"],
                s["increment_vs_uniform_bps"]) > 0 for s in phases),
        "weekly": records, "central_net_eur": None, "adverse_net_eur": None,
        "funded_round_trips": 0, "continuous_floating_drawdown": None,
        "independent_confirmation": False, "new_broker_requests": 0,
        "orders_submitted": 0, "cloud_activated": False,
    }
    args.receipt.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
