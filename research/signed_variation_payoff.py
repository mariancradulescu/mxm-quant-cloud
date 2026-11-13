"""Frozen conditional economic comparison on the original NXE1 quotes."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import log
from pathlib import Path
from random import Random
from statistics import median

from .us500_quote_confirmation import (
    CIPHER_SHA, M5, RECEIPT_SHA, RUN, SOURCE_SHA, START,
    convert, markout, midpoint, need, original_tape,
)

TARGETS = ("EURUSD", "US500")
POLICIES = ("variation", "momentum", "long", "short", "cash")


def direction(value):
    return (value > 0) - (value < 0)


def valuation(path, side, units, commission):
    gross, central, adverse, _ = markout(path, side, units)
    entry_fee = commission * float(path[0]["UsdToEur"])
    exit_fee = commission * float(path[-1]["UsdToEur"])
    fee = entry_fee + exit_fee
    # Match the base adverse convention at every observed liquidation clock.
    worst = min(markout([path[0], mark], side, units)[2] - entry_fee
                - commission * float(mark["UsdToEur"]) for mark in path)
    return gross, central - fee, adverse - fee, worst


def evaluate(tape, receipt, symbol):
    market = {}
    for mark in tape["Marks"]:
        if mark["Symbol"] != symbol:
            continue
        at = mark["At"]
        need(at % M5 == 1500 and at not in market
             and 0 < float(mark["Bid"]) <= float(mark["Ask"])
             and 0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
             and float(mark["UsdToEur"]) > 0 and float(mark["SlippagePerSideQuote"]) >= 0,
             "INVALID_MARK")
        market[at] = mark
    contract = next(iter(market.values()))["Contract"]
    public_terms = receipt["CurrentContractsBySymbol"][symbol]
    terms = {k: v for k, v in contract.items() if k != "ObservedAtUtcMs"}
    need(terms == {k: v for k, v in public_terms.items() if k != "ObservedAtUtcMs"}
         and contract["OriginalBrokerAuthenticated"] and not contract["HistoricalTariffContinuityCertified"]
         and contract["QuoteAsset"] == "USD" and contract["CommissionType"] == 2
         and contract["PreciseMinimumWire"] == contract["PnlConversionFeeBps"] == 0
         and all(m["Contract"] == contract and m["At"] < contract["ObservedAtUtcMs"]
                 for m in market.values()), "COST_TERMS_MISMATCH")
    units = float(contract["MinimumUnits"])
    rollover = contract["SwapTimeUtcMinute"]
    margin = receipt["ObservedMarginGridBySymbol"][symbol][0]
    need(units == float(margin["VolumeUnits"]) > 0 and isinstance(rollover, int)
         and 0 <= rollover < 1440, "MINIMUM_OR_ROLLOVER_UNVERIFIED")
    commission = float(contract["PreciseRateWire"]) / 1e8 * units / float(contract["LotUnits"])
    records, notionals, worst, excursions = [], [], [], []
    for w in range(17):
        week = START + timedelta(weeks=w)
        result = dict(week=week.isoformat(), scheduled=35, missing_decision=0,
                      missing_path=0, priced=0, variation_intents=0, variation_priced=0,
                      differing_directions=0, eur={p: [0.] * 3 for p in POLICIES})
        for d in range(5):
            day = week + timedelta(days=d)
            for hour in range(10, 17):
                t = int(datetime(day.year, day.month, day.day, hour,
                                 tzinfo=timezone.utc).timestamp()) * 1000 + 1500
                history = [market.get(t - j * M5) for j in range(12, -1, -1)]
                if None in history:
                    result["missing_decision"] += 1
                    continue
                mids = [midpoint(x) for x in history]
                returns = [log(b / a) for a, b in zip(mids, mids[1:])]
                signal = direction(sum(r * abs(r) for r in returns))
                own = direction(sum(returns))
                result["variation_intents"] += int(bool(signal))
                path = [market.get(t + j * M5) for j in range(1, 13)]
                charge = t // 86400000 * 86400000 + rollover * 60000
                if None in path or t + M5 < charge <= t + 12 * M5:
                    result["missing_path"] += 1
                    continue
                result["priced"] += 1
                result["differing_directions"] += int(signal != own)
                priced = {s: valuation(path, s, units, commission) for s in (-1, 1)}
                for policy, side in zip(POLICIES, (signal, own, 1, -1, 0)):
                    if side:
                        for i, amount in enumerate(priced[side][:3]):
                            result["eur"][policy][i] += amount
                if signal:
                    result["variation_priced"] += 1
                    notionals.append(convert(midpoint(path[0]) * units, path[0]))
                    worst.append(priced[signal][3])
                    start_mid = midpoint(path[0])
                    moves = [convert((midpoint(m) - start_mid) * units * signal, m) for m in path]
                    excursions.append((max(moves), min(moves)))
        records.append(result)

    def sum_window(window):
        return {p: [sum(w["eur"][p][i] for w in window) for i in range(3)] for p in POLICIES}

    totals = sum_window(records)
    halves = [sum_window(records[:8]), sum_window(records[8:])]
    rng = Random(20261113)
    draws = []
    for _ in range(3000):
        block = [records[(start + j) % 17] for _ in range(6)
                 for start in [rng.randrange(17)] for j in range(3)][:17]
        n = sum(w["priced"] for w in block)
        if n:
            sample = sum_window(block)
            draws.append((sample["variation"][2] / n,
                          (sample["variation"][2] - sample["momentum"][2]) / n))
    bounds = [[sorted(v)[int(q * (len(v) - 1))] for q in (.025, .975)] for v in zip(*draws)]
    return {
        "counts": {k: sum(w[k] for w in records) for k in records[0] if k not in ("week", "eur")},
        "minimum_margin_snapshot_eur": margin, "commission_usd_per_side": commission,
        "median_nominal_eur": median(notionals) if notionals else None,
        "median_favorable_and_adverse_excursion_gross_eur":
            [median(e[i] for e in excursions) for i in (0, 1)] if excursions else None,
        "worst_sampled_adverse_position_eur": min(worst, default=None),
        "gross_central_adverse_eur": totals, "chronological_halves": halves,
        "descriptive_95pct_eur_per_clock_absolute_and_increment_vs_momentum": bounds,
        "followup": all(h["variation"][2] > 0 for h in halves)
        and totals["variation"][2] > max(totals[p][2] for p in POLICIES[1:]),
        "weekly": records,
    }


def main():
    tape, receipt = original_tape()
    result = {
        "source_run": int(RUN), "source_cipher_artifact": 14015883688,
        "source_cipher_sha256": CIPHER_SHA, "source_plaintext_sha256": SOURCE_SHA,
        "source_receipt_sha256": RECEIPT_SHA,
        "protocol_sha256": sha256(Path(__file__).with_name("SIGNED_VARIATION_PAYOFF.md").read_bytes()).hexdigest(),
        "classification": "EXPOSED_CONDITIONAL_MINIMUM_SIZE_EUR",
        "targets": {symbol: evaluate(tape, receipt, symbol) for symbol in TARGETS},
        "funded_round_trips": 0, "funded_net_eur": None, "independent_confirmation": False,
        "orders_submitted": 0, "cloud_activated": False, "new_broker_requests": 0,
    }
    Path("signed-variation-payoff-public.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
