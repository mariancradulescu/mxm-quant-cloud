"""VIA1: newly frozen causal impulse absorption on unchanged NXE1 source.

Original ciphertext is authenticated by original_tape(). No broker requests.
Historical quotes and current tariff metadata imply CONDITIONAL markouts only.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import log
from pathlib import Path
from statistics import median

from . import us500_quote_confirmation as nx
from .signed_variation_payoff import valuation

TARGETS = ("EURUSD", "US500")
POLICIES = ("via1", "fixed_reversion", "own_momentum", "long", "short", "cash")
M5 = nx.M5


def side_of(value):
    return (value > 0) - (value < 0)


def frozen_decision(midpoints):
    """Nineteen completed M5 mark midpoints ending at decision clock."""
    nx.need(len(midpoints) == 19 and all(x > 0 for x in midpoints),
            "INVALID_DECISION_WINDOW")
    changes = [log(midpoints[(i + 1) * 3] / midpoints[i * 3])
               for i in range(6)]
    last = changes[-1]
    if not last or abs(last) <= max(abs(x) for x in changes[:-1]):
        return None
    recent = log(midpoints[-1] / midpoints[-2])
    if recent * last >= 0:
        return None
    direction = -side_of(last)
    shock_start = midpoints[-4]
    extreme = (max if last > 0 else min)(midpoints[-4:])
    return direction, shock_start, extreme


def exit_reason(mid, direction, start, extreme):
    if direction > 0:
        return "target" if mid >= start else ("invalidation" if mid <= extreme else None)
    return "target" if mid <= start else ("invalidation" if mid >= extreme else None)


def valid_mark(mark, contract):
    nx.need(mark["Contract"] == contract and mark["At"] < contract["ObservedAtUtcMs"]
            and 0 < float(mark["Bid"]) <= float(mark["Ask"])
            and 0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
            and float(mark["UsdToEur"]) > 0
            and float(mark["SlippagePerSideQuote"]) >= 0,
            "INVALID_AUTHENTIC_QUOTE_OR_COST")


def zero():
    return {p: [0., 0., 0.] for p in POLICIES}


def aggregate(weeks, key):
    return {p: [sum(w[key][p][k] for w in weeks) for k in range(3)]
            for p in POLICIES}


def run_symbol(tape, receipt, symbol):
    market = {}
    for mark in tape["Marks"]:
        if mark["Symbol"] == symbol:
            at = mark["At"]
            nx.need(at % M5 == 1500 and at not in market, "DUPLICATE_OR_BAD_MARK")
            market[at] = mark
    nx.need(bool(market), "MISSING_AUTHENTIC_SYMBOL_QUOTES")
    contract = next(iter(market.values()))["Contract"]
    terms = receipt["CurrentContractsBySymbol"][symbol]
    nx.need({k: v for k, v in contract.items() if k != "ObservedAtUtcMs"} ==
            {k: v for k, v in terms.items() if k != "ObservedAtUtcMs"}
            and contract["OriginalBrokerAuthenticated"]
            and not contract["HistoricalTariffContinuityCertified"]
            and contract["QuoteAsset"] == "USD"
            and contract["CommissionType"] == 2
            and contract["PreciseMinimumWire"] == 0
            and contract["PnlConversionFeeBps"] == 0,
            "UNPRICED_CURRENT_TARIFF")
    margin = receipt["ObservedMarginGridBySymbol"][symbol][0]
    units = float(contract["MinimumUnits"])
    nx.need(units == float(margin["VolumeUnits"]) > 0 and
            float(contract["LotUnits"]) > 0 and
            isinstance(contract["SwapTimeUtcMinute"], int) and
            0 <= contract["SwapTimeUtcMinute"] < 1440,
            "INVALID_MINIMUM_SIZE_OR_ROLLOVER")
    commission = (float(contract["PreciseRateWire"]) / 1e8 * units /
                  float(contract["LotUnits"]))
    weeks, durations, sampled_worst = [], [], []
    for w in range(17):
        monday = nx.START + timedelta(weeks=w)
        record = dict(week=monday.isoformat(), scheduled=140,
                      missing_decision=0, no_signal=0, intent=0,
                      missing_entry=0, already_target_or_invalid=0,
                      unknown_monitoring=0, unknown_financing=0,
                      adaptive_priced=0, paired_priced=0,
                      paired_unavailable_after_exit=0,
                      exits={"target": 0, "invalidation": 0, "ceiling": 0},
                      adaptive_eur=zero(), paired_eur=zero())
        for d in range(5):
            day = monday + timedelta(days=d)
            for minute in range(600, 1006, 15):
                t = (int(datetime(day.year, day.month, day.day,
                                  minute // 60, minute % 60,
                                  tzinfo=timezone.utc).timestamp()) * 1000 + 1500)
                history = [market.get(t - (18 - i) * M5) for i in range(19)]
                if any(x is None for x in history):
                    record["missing_decision"] += 1
                    continue
                for mark in history:
                    valid_mark(mark, contract)
                mids = [nx.midpoint(mark) for mark in history]
                decision = frozen_decision(mids)
                if decision is None:
                    record["no_signal"] += 1
                    continue
                record["intent"] += 1
                side, shock_start, shock_extreme = decision
                entry = market.get(t + M5)
                if entry is None:
                    record["missing_entry"] += 1
                    continue
                valid_mark(entry, contract)
                entry_mid = nx.midpoint(entry)
                if exit_reason(entry_mid, side, shock_start, shock_extreme):
                    record["already_target_or_invalid"] += 1
                    continue
                path = [entry]
                reason = None
                for j in range(1, 19):  # full protective window = 90 min from entry
                    mark = market.get(t + (j + 1) * M5)
                    if mark is None:
                        break
                    valid_mark(mark, contract)
                    path.append(mark)
                    reason = exit_reason(nx.midpoint(mark), side,
                                         shock_start, shock_extreme)
                    if reason:
                        break
                else:
                    reason = "ceiling"
                if reason is None:
                    record["unknown_monitoring"] += 1
                    continue
                # The source's present-day rollover term is not a certified
                # historical calendar. Crossing it invalidates conditional NET.
                charge = (t // 86400000 * 86400000 +
                          contract["SwapTimeUtcMinute"] * 60000)
                if entry["At"] < charge <= path[-1]["At"]:
                    record["unknown_financing"] += 1
                    continue
                candidate = valuation(path, side, units, commission)
                record["adaptive_priced"] += 1
                record["exits"][reason] += 1
                durations.append((path[-1]["At"] - entry["At"]) / 60000)
                sampled_worst.append(candidate[3])
                for i in range(3):
                    record["adaptive_eur"]["via1"][i] += candidate[i]
                # Paired 90-minute benchmark returns are reported on complete
                # paths only; an early exit must not imply future availability.
                whole = [market.get(t + j * M5) for j in range(1, 20)]
                if any(x is None for x in whole) or (
                    entry["At"] < charge <= t + 19 * M5
                ):
                    record["paired_unavailable_after_exit"] += 1
                    continue
                for mark in whole:
                    valid_mark(mark, contract)
                record["paired_priced"] += 1
                fixed = {s: valuation(whole, s, units, commission)
                         for s in (-1, 1)}
                vals = dict(via1=candidate, fixed_reversion=fixed[side],
                            own_momentum=fixed[-side], long=fixed[1],
                            short=fixed[-1], cash=(0., 0., 0.))
                for policy, vector in vals.items():
                    for i in range(3):
                        record["paired_eur"][policy][i] += vector[i]
        nx.need(record["scheduled"] == record["missing_decision"] +
                record["no_signal"] + record["intent"], "DECISION_COUNT_MISMATCH")
        nx.need(record["intent"] == record["missing_entry"] +
                record["already_target_or_invalid"] +
                record["unknown_monitoring"] + record["unknown_financing"] +
                record["adaptive_priced"], "INTENT_COUNT_MISMATCH")
        weeks.append(record)

    totals = aggregate(weeks, "paired_eur")
    phases = [aggregate(weeks[:8], "paired_eur"),
              aggregate(weeks[8:], "paired_eur")]
    absolute = aggregate(weeks, "adaptive_eur")
    pass_screen = (
        all(h["via1"][0] > 0 and h["via1"][2] > 0 for h in phases)
        and totals["via1"][2] > max(totals[p][2] for p in POLICIES[1:])
    )
    return {
        "current_minimum_margin_snapshot_eur": margin,
        "minimum_volume_units": units,
        "commission_usd_per_side_current_terms": commission,
        "count_totals": {k: sum(x[k] for x in weeks) for k in weeks[0]
                         if k not in ("week", "exits", "adaptive_eur", "paired_eur")},
        "exit_counts": {k: sum(x["exits"][k] for x in weeks)
                        for k in weeks[0]["exits"]},
        "all_causal_exits_eur_gross_central_adverse": absolute["via1"],
        "paired_eur_gross_central_adverse": totals,
        "paired_chronological_8_and_9_week_halves": phases,
        "median_minutes_held": median(durations) if durations else None,
        "worst_sampled_position_adverse_eur": min(sampled_worst, default=None),
        "economic_preliminary_screen_passed": pass_screen,
        "weeks": weeks,
    }


def main():
    tape, receipt = nx.original_tape()
    outcome = {
        "classification": "EXPOSED_DEVELOPMENT_CONDITIONAL_CURRENT_TARIFF_UNFUNDED",
        "protocol_sha256": sha256(
            Path(__file__).with_name("VIA1_IMPULSE_ABSORPTION.md").read_bytes()
        ).hexdigest(),
        "original_nxe1_run": int(nx.RUN),
        "original_cipher_artifact": 14015883688,
        "original_public_receipt_artifact": 14016671008,
        "original_cipher_sha256": nx.CIPHER_SHA,
        "original_plaintext_sha256": nx.SOURCE_SHA,
        "original_receipt_sha256": nx.RECEIPT_SHA,
        "target_results": {symbol: run_symbol(tape, receipt, symbol)
                           for symbol in TARGETS},
        "broker_requests": 0,
        "funded_round_trips": 0,
        "funded_net_eur": None,
        "independent_confirmation": False,
        "orders_submitted": 0,
        "cloud_activated": False,
        "disclosure": "Development replay; as-of M5 quote snapshots, not "
                      "intermediate highs/lows or broker fills. Current tariffs "
                      "are not certified historical. Candidate overlapping clocks "
                      "are not independent funded positions.",
    }
    Path("via1-impulse-absorption-public.json").write_text(
        json.dumps(outcome, indent=2, allow_nan=False) + "\n")
    print("VIA1_COMPLETE", {s: x["count_totals"]["paired_priced"]
                             for s, x in outcome["target_results"].items()})


if __name__ == "__main__":
    main()
