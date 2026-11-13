"""Collect and score the frozen read-only GER40/NAS100 comparison."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import log
import os
from pathlib import Path
from random import Random
from statistics import median

from .custody import seal_new
from .custody_new import checked_public
from .us500_quote_confirmation import NY, midpoint, markout, convert, need

START = date(2026, 8, 17)
NAMES = ("GER40", "NAS100")
POLICIES = ("peer", "own_acceleration", "own_momentum", "long", "short", "cash")
M5 = 300000


def direction(value):
    return (value > 0) - (value < 0)


def clock(day, hour):
    return int(datetime(day.year, day.month, day.day, hour, tzinfo=NY).timestamp()) * 1000 + 1500


def evaluate(tape):
    quotes = {s: {} for s in NAMES}
    for mark in tape["Marks"]:
        s = mark["Symbol"]
        if s in quotes:
            at = mark["At"]
            need(at % M5 == 1500 and at not in quotes[s]
                 and 0 < float(mark["Bid"]) <= float(mark["Ask"])
                 and 0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
                 and float(mark["SlippagePerSideQuote"]) >= 0, "INVALID_MARK")
            quotes[s][at] = mark
    records = {}
    for name, peer in (NAMES, NAMES[::-1]):
        market = quotes[name]
        contract = next(iter(market.values()), {}).get("Contract")
        if not contract:
            records[name] = {"status": "TARGET_MARKS_UNAVAILABLE"}
            continue
        if not contract["OriginalBrokerAuthenticated"] or any(
                contract[k] for k in ("PreciseRateWire", "PreciseMinimumWire", "PnlConversionFeeBps")):
            records[name] = {"status": "TARGET_TERMS_UNPRICED"}
            continue
        swap = contract["SwapTimeUtcMinute"]
        if swap is None:
            records[name] = {"status": "ROLLOVER_UNKNOWN"}
            continue
        units = float(contract["MinimumUnits"])
        need(units > 0 and 0 <= swap < 1440
             and all(mark["Contract"] == contract for mark in market.values()),
             "CONTRACT_PROFILE_MISMATCH")
        weeks, nominal, worst = [], [], []
        for index in range(12):
            start = START + timedelta(weeks=index)
            sums = {p: [0.0] * 3 for p in POLICIES}
            week = dict(week=start.isoformat(), scheduled=25, decision_missing=0,
                        path_missing=0, priced=0, peer_intents=0, peer_priced=0, eur=sums)
            for day in range(5):
                for hour in range(10, 15):
                    t = clock(start + timedelta(days=day), hour)
                    features = [[quotes[s].get(t - offset * M5) for offset in (12, 6, 0)]
                                for s in (name, peer)]
                    if any(None in row for row in features):
                        week["decision_missing"] += 1
                        continue
                    moves = []
                    for row in features:
                        a, b, c = map(midpoint, row)
                        own = log(c / b)
                        moves.append((own - log(b / a), own))
                    sides = (direction(moves[1][0]), direction(moves[0][0]),
                             direction(moves[0][1]), 1, -1, 0)
                    week["peer_intents"] += int(sides[0] != 0)
                    path = [market.get(t + j * M5) for j in range(1, 11)]
                    entry = t + M5
                    day_start = entry // 86400000 * 86400000
                    if None in path or entry < day_start + swap * 60000 <= t + 10 * M5:
                        week["path_missing"] += 1
                        continue
                    week["priced"] += 1
                    priced = {s: markout(path, s, units) for s in (-1, 1)}
                    for policy, side in zip(POLICIES, sides):
                        if side:
                            for i, amount in enumerate(priced[side][:3]):
                                sums[policy][i] += amount
                    if sides[0]:
                        week["peer_priced"] += 1
                        nominal.append(convert(midpoint(path[0]) * units, path[0]))
                        worst.append(priced[sides[0]][3])
            weeks.append(week)

        def combine(window):
            return {p: [sum(w["eur"][p][i] for w in window) for i in range(3)]
                    for p in POLICIES}

        totals = combine(weeks)
        phases = [combine(weeks[:6]), combine(weeks[6:])]
        rng = Random(20261113)
        draws = []
        for _ in range(3000):
            sample = [weeks[(start + i) % 12] for _ in range(4)
                      for start in [rng.randrange(12)] for i in range(3)]
            n = sum(w["priced"] for w in sample)
            if n:
                totals_sample = combine(sample)
                draws.append((totals_sample["peer"][2] / n,
                              (totals_sample["peer"][2] - totals_sample["own_acceleration"][2]) / n))
        bounds = [[sorted(a)[int(q * (len(a) - 1))] for q in (.025, .975)]
                  for a in zip(*draws)]
        records[name] = {
            "status": "CONDITIONAL_MARKOUT", "units": units, "contract": contract,
            "observed_margin_grid": tape["MarginGrid"].get(name),
            "median_entry_notional_eur": median(nominal) if nominal else None,
            "worst_sampled_peer_markout_eur": min(worst, default=None),
            "counts": {k: sum(w[k] for w in weeks) for k in
                       ("scheduled", "decision_missing", "path_missing", "priced", "peer_intents", "peer_priced")},
            "gross_central_adverse_eur": totals, "first_last_six_weeks": phases,
            "descriptive_95pct_3week_block_eur_per_clock_peer_and_increment": bounds,
            "followup": all(p["peer"][2] > 0 for p in phases)
            and totals["peer"][2] > max(totals[p][2] for p in POLICIES[1:]),
            "weekly": weeks,
        }
    coincident = 0
    for index in range(60):
        day = START + timedelta(weeks=index // 5, days=index % 5)
        for hour in range(10, 15):
            t = clock(day, hour)
            if all(t - i * M5 in quotes[s] for s in NAMES for i in (0, 6, 12)):
                moves = []
                for s in NAMES:
                    a, b, c = (midpoint(quotes[s][t - i * M5]) for i in (12, 6, 0))
                    moves.append(direction(log(c / b) - log(b / a)))
                coincident += int(all(moves))
    return records, coincident


def main():
    from .native_original_openapi_product_replay import collect_and_evaluate

    run = os.environ["GITHUB_RUN_ID"]
    key = checked_public(Path("new-recipient-output"), run)
    end = START + timedelta(weeks=12)
    utc = lambda d: int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 1000
    days = [(START + timedelta(weeks=i // 5, days=i % 5)).isoformat() for i in range(60)]
    cipher = Path("ger40-nas100-acceleration-source.v2.enc")

    def receive(raw):
        sealed = seal_new(raw, key, run)
        cipher.write_bytes(sealed)
        tape = json.loads(raw)
        targets, coincident = evaluate(tape)
        report = {
            "classification": "EXPOSED_CONDITIONAL_EUR_MINIMUM_SIZE",
            "source_plaintext_sha256": sha256(raw).hexdigest(),
            "source_cipher_sha256": sha256(sealed).hexdigest(),
            "protocol_sha256": sha256(Path(__file__).with_name("GER40_NAS100_ACCELERATION.md").read_bytes()).hexdigest(),
            "actual_broker_symbols": tape["BrokerSymbolNames"],
            "original_read_only_requests": tape["ReadOnlyRequests"],
            "excluded_optional_symbols": tape["ExcludedOptionalSymbols"],
            "combined_observed_minimum_margin_eur": (
                sum(max(float(tape["MarginGrid"][s][0][k])
                        for k in ("BuyMarginEur", "SellMarginEur")) for s in NAMES)
                if all(s in tape["MarginGrid"] and s in tape["BrokerSymbolNames"] for s in NAMES)
                else None
            ),
            "bars": {x["Symbol"]: len(x["M5"]) for x in tape["Bars"]},
            "marks": {s: sum(x["Symbol"] == s for x in tape["Marks"]) for s in tape["BrokerSymbolNames"]},
            "coincident_peer_intents": coincident, "targets": targets,
            "funded_round_trips": 0, "funded_net_eur": None, "independent_confirmation": False,
            "continuous_drawdown": None, "orders_submitted": 0, "cloud_activated": False,
        }
        Path("ger40-nas100-acceleration-public.json").write_text(json.dumps(report, indent=2) + "\n")

    collect_and_evaluate({
        "symbols": (*NAMES, "EURUSD"), "optional_symbols": NAMES,
        "source_symbol_aliases": {"GER40": ("GER40.cash", "DE40"), "NAS100": ("NAS100.cash", "US100")},
        "source_start": utc(START), "start": utc(START), "end": utc(end),
        "event_days": days, "bar_ranges": ((utc(START), utc(end)),),
        "quote_hour_start": 12, "quote_hour_end": 20,
        "quote_interval_ms": M5, "quote_age_ms": 30000, "quote_chunk_minutes": 120,
        "bar_chunk_hours": 72, "extended_sessions": True, "session_map": True,
        "ordered_tick_history": True, "two_sided_targets": NAMES,
        "margin_grid_targets": NAMES, "capture_only": True, "tape_consumer": receive,
        "label": "ORIGINAL_PEPPERSTONE_GER40_NAS100_ACCELERATION", "report_source_progress": True,
    })


if __name__ == "__main__":
    main()
