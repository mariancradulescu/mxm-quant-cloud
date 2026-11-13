"""Score the frozen NOKJPY oil pilot on the original local development ZIP."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import file_digest, sha256
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile

import numpy as np


SYMBOLS = ("NOKJPY", "SEKJPY", "WTOIL-PERP")
FIVE_MINUTES = 300
WEEK = 7 * 86400


def read_source(path):
    binding = re.search(
        r'HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT = "([0-9a-f]+)"',
        Path(__file__).with_name("collect.py").read_text(),
    )[1]
    with ZipFile(path) as bundle:
        manifest = json.loads(bundle.read("CAPTURE_MANIFEST.json"))
        payload_bytes = bundle.read("V3_CAPTURE_PAYLOAD.json")
        payload = json.loads(payload_bytes)
        if (sha256(manifest["account_fingerprint"].encode("ascii")).hexdigest() != binding
                or manifest["account_fingerprint"] != payload["account_fingerprint_sha256"]
                or not manifest["read_only_assertion"]
                or manifest["orders_placed"]
                or payload["classification"] != "DEVELOPMENT_ONLY"
                or sha256(payload_bytes).hexdigest() !=
                manifest["sha256_per_canonical_payload"]["V3_CAPTURE_PAYLOAD.json"]):
            raise ValueError("Original development source binding failed")

        checksums = dict(line.split(maxsplit=1)[::-1]
                         for line in bundle.read("CHECKSUMS.sha256").decode().splitlines())
        quality_bytes = bundle.read("DATA_QUALITY_TABLE.json")
        if sha256(quality_bytes).hexdigest() != checksums["DATA_QUALITY_TABLE.json"]:
            raise ValueError("Contract probe table hash mismatch")
        quality = {row["symbol"]: row for row in json.loads(quality_bytes)["rows"]}

        series = {row["broker_symbol"]: row for row in payload["series"]}
        bars = {}
        provenance = {}
        for symbol in SYMBOLS:
            row = series[symbol]
            blob = bundle.read(row["file"])
            digest = sha256(blob).hexdigest()
            if digest != row["sha256"] or digest != checksums[row["file"]]:
                raise ValueError(f"Source series hash mismatch: {symbol}")
            closes = {}
            for item in csv.DictReader(io.StringIO(blob.decode())):
                at = int(datetime.fromisoformat(item["time_utc"]).timestamp()) + FIVE_MINUTES
                close = float(item["close"])
                if at % FIVE_MINUTES or at in closes or not np.isfinite(close) or close <= 0:
                    raise ValueError(f"Invalid clock or close: {symbol}")
                closes[at] = close
            if len(closes) != row["row_count"]:
                raise ValueError(f"Source series row count mismatch: {symbol}")
            bars[symbol] = closes
            provenance[symbol] = {"sha256": digest, "bars": len(closes)}
        probe = quality["NOKJPY"]
        return bars, {
            "archive": path.name,
            "account_commitment_matched": True,
            "manifest_payload_sha256": sha256(payload_bytes).hexdigest(),
            "series": provenance,
            "capture_start_utc": manifest["capture_start_utc"],
            "capture_end_utc": manifest["capture_end_utc"],
            "nokjpy_two_sided_historical_probe": probe["shortability"],
            "nokjpy_minimum_margin_historical_probe_estimate_eur":
                probe["minimum_margin_estimate_for_EUR200"],
        }


def sample_weeks(bars):
    start = int(datetime(2025, 9, 22, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2026, 9, 14, tzinfo=timezone.utc).timestamp())
    weeks = []
    for week in range(start, end, WEEK):
        rows = []
        for day in range(5):
            for hour in range(8, 16):
                at = week + day * 86400 + hour * 3600
                prior = range(at - 3600, at + 1, FIVE_MINUTES)
                if any(t not in bars[symbol] for symbol in SYMBOLS for t in prior):
                    continue
                entry = at + FIVE_MINUTES
                exit_at = entry + 3600
                target = bars["NOKJPY"]
                if any(t not in target for t in range(entry, exit_at + 1, FIVE_MINUTES)):
                    continue
                x = [10_000 * np.log(bars[symbol][at] / bars[symbol][at - 3600])
                     for symbol in SYMBOLS]
                y = 10_000 * np.log(target[exit_at] / target[entry])
                rows.append((*x, y))
        weeks.append((week, np.asarray(rows, dtype=float).reshape(-1, 4)))
    return weeks


def forecast(training, scoring, columns):
    x = training[:, :columns]
    y = training[:, 3]
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    if np.any(scale == 0):
        raise ValueError("Training feature has zero variation")
    z = (x - center) / scale
    weights = np.linalg.solve(z.T @ z + 0.01 * len(z) * np.eye(columns), z.T @ (y - y.mean()))
    return y.mean() + ((scoring[:, :columns] - center) / scale) @ weights, weights / scale


def paired_interval(block_sums, block_counts):
    rng = np.random.default_rng(20261113)
    width = 4
    n = len(block_counts)
    starts = rng.integers(0, n - width + 1, size=(5000, (n + width - 1) // width))
    indexes = (starts[:, :, None] + np.arange(width)).reshape(5000, -1)[:, :n]
    draws = block_sums[indexes].sum(axis=1) / block_counts[indexes].sum(axis=1)[:, None]
    return np.quantile(draws, [0.025, 0.975], axis=0).T.tolist()


def summarize(weeks):
    training = [rows for _, rows in weeks[:20]]
    scored = []
    weekly = []
    coefficients = []
    for week, rows in weeks[20:]:
        base, _ = forecast(np.concatenate(training), rows, 2)
        model, weights = forecast(np.concatenate(training), rows, 3)
        training.append(rows)
        coefficients.append(weights[-1])
        realized = rows[:, 3]
        gross = np.sign(model) * realized
        observations = np.column_stack((
            (realized - base) ** 2, (realized - model) ** 2,
            gross, np.sign(base) * realized, realized, -realized,
        ))
        scored.append(observations)
        weekly.append({
            "week_utc": datetime.fromtimestamp(week, timezone.utc).date().isoformat(),
            "slots": len(rows),
            "missing": 40 - len(rows),
            "gross_model_bps_sum": float(gross.sum()),
        })

    all_scores = np.concatenate(scored)
    base_mse, model_mse, gross, baseline, long, short = all_scores.mean(axis=0)
    sums = np.asarray([rows.sum(axis=0) for rows in scored])
    counts = np.asarray([len(rows) for rows in scored])
    contrasts = np.column_stack((
        sums[:, 0] - sums[:, 1], sums[:, 2],
        sums[:, 2] - sums[:, 3], sums[:, 2] - sums[:, 4], sums[:, 2] - sums[:, 5],
    ))
    intervals = paired_interval(contrasts, counts)
    return {
        "training_slots_initial": sum(len(rows) for _, rows in weeks[:20]),
        "evaluation_slots": len(all_scores),
        "evaluation_missing": 40 * len(scored) - len(all_scores),
        "median_eligible_slots_week": float(np.median(counts)),
        "horizon_minutes": 60,
        "models_mse_bps2": {"with_oil": model_mse, "without_oil": base_mse},
        "mean_gross_bps_per_slot": {
            "with_oil": gross, "without_oil": baseline, "long": long, "short": short, "cash": 0,
        },
        "gross_break_even_all_in_bps_per_slot": gross,
        "weekly_bootstrap_95pct": dict(zip(
            ("mse_improvement_bps2", "model_bps", "increment_vs_no_oil_bps",
             "increment_vs_long_bps", "increment_vs_short_bps"), intervals)),
        "oil_coefficient_positive_weeks": int(np.count_nonzero(np.asarray(coefficients) > 0)),
        "oil_coefficient_range": [float(min(coefficients)), float(max(coefficients))],
        "gross_per_slot_bps_quantiles": dict(zip(
            ("p01", "p05", "p50", "p95"), np.quantile(all_scores[:, 2], [.01, .05, .50, .95]))),
        "gross_losing_slots": int(np.count_nonzero(all_scores[:, 2] < 0)),
        "paired_development_screen_passed": bool(
            base_mse > model_mse and gross > max(0, baseline, long, short)),
        "weekly": weekly,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bars, provenance = read_source(args.archive)
    result = summarize(sample_weeks(bars))
    with args.archive.open("rb") as source:
        provenance["archive_sha256"] = file_digest(source, "sha256").hexdigest()
    result.update({
        "classification": "EXPOSED_DEVELOPMENT_BAR_RETURN_DIAGNOSTIC",
        "source": provenance,
        "protocol_sha256": sha256(Path(__file__).with_name("NOK_OIL_INCREMENTAL.md").read_bytes()).hexdigest(),
        "central_net_eur": None,
        "adverse_net_eur": None,
        "funded_round_trips": 0,
        "continuous_floating_drawdown": None,
        "independent_confirmation": False,
        "new_broker_requests": 0,
        "orders_submitted": 0,
        "cloud_activated": False,
    })
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
