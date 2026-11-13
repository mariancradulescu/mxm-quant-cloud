"""Frozen economic participation comparison using original synchronized quotes."""
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from random import Random
from statistics import mean, median

from .custody import unseal_new
from .index_joint_risk import RUN, CIPHER_SHA, PLAIN_SHA, START, M5, NAMES, clock
from .us500_quote_confirmation import markout, midpoint, need

POLICIES = ("spread_state", "pooled", "always", "equal_frequency", "cash")


def evaluate(marks):
    market = {}
    for mark in marks:
        t = mark["At"]
        need(t % M5 == 1500 and t not in market
             and 0 < float(mark["Bid"]) <= float(mark["Ask"])
             and 0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
             and float(mark["SlippagePerSideQuote"]) >= 0, "MARK_INVALID")
        market[t] = mark
    contract = marks[0]["Contract"]
    units = float(contract["MinimumUnits"])
    swap = contract["SwapTimeUtcMinute"]
    need(units == .1 and isinstance(swap, int) and 0 <= swap < 1440
         and contract["OriginalBrokerAuthenticated"] and not contract["HistoricalTariffContinuityCertified"]
         and all(contract[k] == 0 for k in ("PreciseRateWire", "PreciseMinimumWire", "PnlConversionFeeBps"))
         and all(m["Contract"] == contract and m["At"] < contract["ObservedAtUtcMs"] for m in marks),
         "CONTRACT_MISMATCH")
    weeks = []
    prior = []
    for w in range(12):
        start = START + timedelta(weeks=w)
        # Freeze both forecasts from prior completed weeks, before creating intents.
        thresholds = {h: median([r[1] for r in prior if r[0] == h]) for h in range(10, 15)} if prior else {}
        pooled = [r[2][2] for r in prior if r[2] is not None]
        cells = {high: [r[2][2] for r in prior if r[2] is not None
                        and (r[1] > thresholds[r[0]]) == high] for high in (False, True)}
        estimates = {key: mean(values) if len(values) >= 20 else None
                     for key, values in cells.items()}
        pool_est = mean(pooled) if len(pooled) >= 20 else None
        rows = []
        report = {"week": start.isoformat(), "scheduled": 25, "missing_decision": 0, "flat": 0,
                  "missing_path": 0, "wide": 0, "intents": dict.fromkeys(POLICIES[:3], 0),
                  "priced": dict.fromkeys(POLICIES[:3], 0), "net_eur": {p: [0.] * 3 for p in POLICIES},
                  "worst_sampled_selected_eur": None}
        for d in range(5):
            day = start + timedelta(days=d)
            for h in range(10, 15):
                t = clock(day, h)
                current, past = market.get(t), market.get(t - 6 * M5)
                if current is None or past is None:
                    report["missing_decision"] += 1
                    continue
                change = midpoint(current) - midpoint(past)
                side = (change > 0) - (change < 0)
                spread = float(current["Ask"]) - float(current["Bid"])
                high = bool(prior and spread > thresholds[h])
                if not side:
                    report["flat"] += 1
                    rows.append((h, spread, None))
                    continue
                report["wide"] += int(high)
                state_est = estimates[high]
                decisions = (state_est is not None and state_est > 0,
                             pool_est is not None and pool_est > 0, True)
                for p, decision in zip(POLICIES, decisions):
                    report["intents"][p] += int(decision)
                path = [market.get(t + j * M5) for j in range(1, 11)]
                rollover = t // 86400000 * 86400000 + swap * 60000
                if None in path or t + M5 < rollover <= t + 10 * M5:
                    rows.append((h, spread, None))
                    report["missing_path"] += 1
                    continue
                value = markout(path, side, units)
                rows.append((h, spread, value))
                for p, decision in zip(POLICIES, decisions):
                    if decision:
                        report["priced"][p] += 1
                        for k in range(3):
                            report["net_eur"][p][k] += value[k]
                if decisions[0]:
                    old = report["worst_sampled_selected_eur"]
                    report["worst_sampled_selected_eur"] = value[3] if old is None else min(old, value[3])
        if report["priced"]["always"]:
            ratio = report["priced"]["spread_state"] / report["priced"]["always"]
            report["net_eur"]["equal_frequency"] = [ratio * v for v in report["net_eur"]["always"]]
        prior.extend(rows)
        weeks.append(report)

    def totals(segment):
        return {p: [sum(w["net_eur"][p][i] for w in segment) for i in range(3)] for p in POLICIES}

    scored = weeks[4:]
    overall = totals(scored)
    phases = [totals(scored[:4]), totals(scored[4:])]
    deltas = [w["net_eur"]["spread_state"][2] - w["net_eur"]["equal_frequency"][2] for w in scored]
    rng = Random(20261113)
    samples = sorted(sum(deltas[(start + j) % 8] for _ in range(4)
                         for start in [rng.randrange(8)] for j in range(2)) / 8 for _ in range(3000))
    return {
        "contract_minimum_units": units, "weekly": weeks,
        "evaluation_totals": overall, "evaluation_halves": phases,
        "evaluation_intents": {p: sum(w["intents"][p] for w in scored) for p in POLICIES[:3]},
        "evaluation_priced": {p: sum(w["priced"][p] for w in scored) for p in POLICIES[:3]},
        "weekly_increment_vs_equal_frequency_descriptive_95pct_eur": [samples[75], samples[2924]],
        "followup": all(x["spread_state"][2] > 0 for x in phases)
        and overall["spread_state"][2] > max(overall[p][2] for p in POLICIES[1:]),
    }


def main():
    cipher = Path("original-index/ger40-nas100-acceleration-source.v2.enc").read_bytes()
    need(sha256(cipher).hexdigest() == CIPHER_SHA, "CIPHERTEXT_MISMATCH")
    raw = unseal_new(cipher, os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode(), RUN)
    need(sha256(raw).hexdigest() == PLAIN_SHA, "PLAINTEXT_MISMATCH")
    tape = json.loads(raw)
    need(tape["SourceLabel"] == "ORIGINAL_PEPPERSTONE_GER40_NAS100_ACCELERATION"
         and len(tape["Marks"]) == 17203, "SOURCE_IDENTITY_MISMATCH")
    report = {
        "classification": "EXPOSED_CONDITIONAL_EUR",
        "source_run": int(RUN), "source_artifact": 14026439419,
        "source_cipher_sha256": CIPHER_SHA, "source_plaintext_sha256": PLAIN_SHA,
        "protocol_sha256": sha256(Path(__file__).with_name("INDEX_LIQUIDITY_HURDLE.md").read_bytes()).hexdigest(),
        "targets": {s: evaluate([m for m in tape["Marks"] if m["Symbol"] == s]) for s in NAMES},
        "margin_grid": tape["MarginGrid"], "amount_order": ["gross", "central", "adverse"],
        "new_broker_requests": 0, "orders_submitted": 0, "cloud_activated": False,
        "funded_round_trips": 0, "funded_net_eur": None, "independent_confirmation": False,
    }
    Path("index-liquidity-hurdle-public.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
