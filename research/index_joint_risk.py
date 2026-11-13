"""Joint liquidation reserve comparison on the immutable original index tape."""
from datetime import timedelta
from hashlib import sha256
import json
from math import ceil
import os
from pathlib import Path
from random import Random
from statistics import mean, median

from .custody import unseal_new
from .ger40_nas100_acceleration import M5, NAMES, START, clock, direction
from .us500_quote_confirmation import convert, midpoint, need

RUN = "43404751751"
CIPHER_SHA = "cf3050f69c2d8130b4b4f0f36493c1bd9b9f3cdd89bd8fc2fa0ec3434785372f"
PLAIN_SHA = "5b1d92766dabc3413ba8aa21f31b5ff91e8fca053b0f37dc4c12261363cc13cb"
Q = .95


def adverse_path(path, side, units):
    entry = path[0]
    slip = float(entry["SlippagePerSideQuote"])
    spread = float(entry["Ask"]) - float(entry["Bid"])
    start = float(entry["Ask" if side == 1 else "Bid"]) + side * slip
    output = []
    for mark in path:
        end_slip = float(mark["SlippagePerSideQuote"])
        end = float(mark["Bid" if side == 1 else "Ask"]) - side * end_slip
        stress = spread + float(mark["Ask"]) - float(mark["Bid"]) + 2 * (slip + end_slip)
        fx = (float(mark["QuoteDebitToEur"]) + float(mark["QuoteCreditToEur"])) / 2
        output.append(convert((end - start) * side * units, mark) - stress * units * fx)
    return output


def quantile(values):
    return sorted(values)[ceil(Q * len(values)) - 1]


def pinball(actual, estimate):
    error = actual - estimate
    return max(Q * error, (Q - 1) * error)


def summarize(rows):
    n = len(rows)
    return {
        "clocks": n,
        "pooled_pinball_eur": mean(r[0] for r in rows) if n else None,
        "conditional_pinball_eur": mean(r[1] for r in rows) if n else None,
        "pooled_misses": sum(r[2] for r in rows),
        "conditional_misses": sum(r[3] for r in rows),
        "pooled_median_reserve_eur": median(r[4] for r in rows) if n else None,
        "conditional_median_reserve_eur": median(r[5] for r in rows) if n else None,
        "fallbacks": sum(r[6] for r in rows),
    }


def forecast(weeks, exposure, margin):
    previous = [row for week in weeks[:4] for row in week]
    evaluated = []
    for week in weeks[4:]:
        reserve = quantile([row[1][exposure][0] for row in previous])
        scores = []
        for agree, labels in week:
            cell = [r[1][exposure][0] for r in previous if r[0] == agree]
            conditional = quantile(cell) if len(cell) >= 20 else reserve
            realized = labels[exposure][0]
            scores.append((pinball(realized, reserve), pinball(realized, conditional),
                           realized > reserve, realized > conditional, reserve, conditional,
                           len(cell) < 20))
        evaluated.append(scores)
        previous.extend(week)
    phase = [summarize([r for w in group for r in w])
             for group in (evaluated[:4], evaluated[4:])]
    totals = summarize([r for w in evaluated for r in w])
    rng = Random(20261113)
    draws = []
    for _ in range(3000):
        rows = [r for _ in range(4) for start in [rng.randrange(8)]
                for j in range(2) for r in evaluated[(start + j) % 8]]
        if rows:
            draws.append(mean(r[0] - r[1] for r in rows))
    draws.sort()
    labels = [row[1][exposure] for week in weeks for row in week]
    risks = [x[0] for x in labels]
    return {
        "maximum_sampled_joint_loss_eur": max(risks),
        "descriptive_p95_sampled_joint_loss_eur": quantile(risks),
        "maximum_sum_of_separate_worst_losses_eur": max(x[1] for x in labels),
        "median_sum_minus_synchronous_loss_eur": median(x[1] - x[0] for x in labels),
        "static_scenarios": {str(equity): {
            "headroom_before_costs_and_float_eur": round(equity - margin, 2),
            "sampled_losses_above_headroom": sum(r > equity - margin for r in risks),
            "minimum_start_margin_shortfall_eur": round(max(0, margin - equity), 2),
            "observations": len(risks),
        } for equity in (300, 210)},
        "last_eight_weeks": totals,
        "chronological_halves": phase,
        "descriptive_95pct_block_interval_pinball_improvement_eur":
            [draws[int(q * (len(draws) - 1))] for q in (.025, .975)] if draws else None,
        "reserve_followup_passed": (
            all(x["clocks"] and x["conditional_pinball_eur"] < x["pooled_pinball_eur"] for x in phase)
            and totals["conditional_misses"] <= totals["pooled_misses"]
        ),
    }


def evaluate(tape):
    marks = {s: {} for s in NAMES}
    for mark in tape["Marks"]:
        s = mark["Symbol"]
        if s not in marks:
            continue
        at = mark["At"]
        need(at % M5 == 1500 and at not in marks[s]
             and 0 < float(mark["Bid"]) <= float(mark["Ask"])
             and 0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
             and float(mark["SlippagePerSideQuote"]) >= 0, "MARK_INVALID")
        marks[s][at] = mark
    contracts = {s: next(iter(marks[s].values()))["Contract"] for s in NAMES}
    margin = 0
    for s, c in contracts.items():
        grid = tape["MarginGrid"][s][0]
        need(c["OriginalBrokerAuthenticated"] and not c["HistoricalTariffContinuityCertified"]
             and float(c["MinimumUnits"]) == float(grid["VolumeUnits"]) == .1
             and all(c[k] == 0 for k in ("PreciseRateWire", "PreciseMinimumWire", "PnlConversionFeeBps"))
             and isinstance(c["SwapTimeUtcMinute"], int) and 0 <= c["SwapTimeUtcMinute"] < 1440
             and all(m["Contract"] == c for m in marks[s].values()), "CONTRACT_MISMATCH")
        margin += max(float(grid[k]) for k in ("BuyMarginEur", "SellMarginEur"))
    weeks = []
    counts = dict(scheduled=300, decision_missing=0, path_missing=0, complete=0, agree=0)
    for week in range(12):
        rows = []
        for day in range(5):
            for hour in range(10, 15):
                t = clock(START + timedelta(weeks=week, days=day), hour)
                features = [[marks[s].get(t - lag * M5) for lag in (12, 0)] for s in NAMES]
                if any(None in f for f in features):
                    counts["decision_missing"] += 1
                    continue
                moves = [direction(midpoint(b) - midpoint(a)) for a, b in features]
                agree = bool(moves[0] and moves[0] == moves[1])
                entry, end = t + M5, t + 10 * M5
                paths = {s: [marks[s].get(a) for a in range(entry, end + 1, M5)] for s in NAMES}
                midnight = entry // 86400000 * 86400000
                if any(None in paths[s] or entry < midnight + contracts[s]["SwapTimeUtcMinute"] * 60000 <= end
                       for s in NAMES):
                    counts["path_missing"] += 1
                    continue
                counts["complete"] += 1
                counts["agree"] += agree
                marked = {(s, side): adverse_path(paths[s], side, .1)
                          for s in NAMES for side in (-1, 1)}
                labels = {}
                for name, relative in (("same", 1), ("opposite", -1)):
                    losses, separate = [], []
                    for sign in (-1, 1):
                        a, b = marked[(NAMES[0], sign)], marked[(NAMES[1], relative * sign)]
                        losses.append(max(0, -min(x + y for x, y in zip(a, b))))
                        separate.append(max(0, -min(a)) + max(0, -min(b)))
                    labels[name] = (max(losses), max(separate))
                rows.append((agree, labels))
        weeks.append(rows)
    need(all(weeks) and counts["complete"] > 0, "WEEKLY_COVERAGE_UNSUPPORTED")
    return {"counts": counts, "complete_by_week": [len(w) for w in weeks],
            "combined_observed_minimum_margin_eur": margin,
            "exposures": {name: forecast(weeks, name, margin) for name in ("same", "opposite")}}


def main():
    ciphertext = Path("original-index/ger40-nas100-acceleration-source.v2.enc").read_bytes()
    need(sha256(ciphertext).hexdigest() == CIPHER_SHA, "CIPHER_HASH_MISMATCH")
    raw = unseal_new(ciphertext, os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode(), RUN)
    need(sha256(raw).hexdigest() == PLAIN_SHA, "SOURCE_HASH_MISMATCH")
    tape = json.loads(raw)
    need(tape["SourceLabel"] == "ORIGINAL_PEPPERSTONE_GER40_NAS100_ACCELERATION"
         and len(tape["Marks"]) == 17203, "SOURCE_IDENTITY_MISMATCH")
    report = evaluate(tape)
    report.update(source_run=int(RUN), source_artifact=14026439419,
                  source_cipher_sha256=CIPHER_SHA, source_plain_sha256=PLAIN_SHA,
                  protocol_sha256=sha256(Path(__file__).with_name("INDEX_JOINT_RISK.md").read_bytes()).hexdigest(),
                  classification="EXPOSED_CONDITIONAL_JOINT_LIQUIDATION_RISK",
                  broker_requests=0, orders_submitted=0, cloud_activated=False,
                  funded_round_trips=0, funded_net_eur=None, independent_confirmation=False)
    Path("index-joint-risk-public.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
