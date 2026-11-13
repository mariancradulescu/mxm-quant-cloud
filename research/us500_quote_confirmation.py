"""Score a new US500 diagnostic using the sealed original NXE1 observations."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import ceil
import os
from pathlib import Path
from random import Random
from statistics import mean
from zoneinfo import ZoneInfo

from .custody import unseal_new

RUN = "43377275493"
CIPHER_SHA = "3e6ac925da0eaf686ff1b2cf3aae860fae1ef06813e97b2f4a88d90849c8c441"
SOURCE_SHA = "9a1c980230049103cc3713451622ab7c2b566816cbabc3c382e1b83ec5cc028f"
RECEIPT_SHA = "2ca870ac72869543c132eee12ae8f5b1e87ca76716e4060b458a5fa559e05db5"
M5 = 300000
START = date(2026, 7, 13)
NY = ZoneInfo("America/New_York")
POLICIES = ("cash", "long", "short", "bars", "own_quotes", "both_indices")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def original_tape():
    cipher = Path("original-nxe1/nxe1-original-native-tape.v2.enc").read_bytes()
    public = Path("original-nxe1-public/nxe1-public.json").read_bytes()
    need(sha256(cipher).hexdigest() == CIPHER_SHA, "CIPHER_SHA_MISMATCH")
    need(sha256(public).hexdigest() == RECEIPT_SHA, "PUBLIC_SHA_MISMATCH")
    receipt = json.loads(public)
    need(receipt["SourceCiphertextSha256"] == CIPHER_SHA and
         receipt["OriginalBrokerSourceSha256"] == SOURCE_SHA and
         receipt["OriginalPepperstoneAccountAuthenticated"], "SOURCE_RECEIPT_BINDING")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    plaintext = unseal_new(cipher, key, RUN)
    need(sha256(plaintext).hexdigest() == SOURCE_SHA, "SOURCE_SHA_MISMATCH")
    tape = json.loads(plaintext)
    need(tape["SourceLabel"] == receipt["SourceLabel"] and
         len(tape["Marks"]) == receipt["OriginalBidAskAsOfMarks"] and
         {x["Symbol"]: len(x["M5"]) for x in tape["Bars"]} == receipt["OriginalBarsBySymbol"],
         "SOURCE_CONTENT_BINDING")
    return tape, receipt


def quote_confirm(before, now, direction):
    return direction != 0 and all(
        direction * (float(now[side]) - float(before[side])) > 0
        for side in ("Bid", "Ask")
    )


def midpoint(mark):
    return (float(mark["Bid"]) + float(mark["Ask"])) / 2


def convert(amount, mark):
    return amount * float(mark["QuoteCreditToEur" if amount >= 0 else "QuoteDebitToEur"])


def markout(path, side, units):
    entry = path[0]
    entry_spread = float(entry["Ask"]) - float(entry["Bid"])
    entry_slip = float(entry["SlippagePerSideQuote"])
    start = float(entry["Ask" if side == 1 else "Bid"]) + side * entry_slip
    adverse_path = []
    for mark in path:
        end_slip = float(mark["SlippagePerSideQuote"])
        end = float(mark["Bid" if side == 1 else "Ask"]) - side * end_slip
        central = convert((end - start) * side * units, mark)
        spread = float(mark["Ask"]) - float(mark["Bid"])
        fx_mid = (float(mark["QuoteCreditToEur"]) + float(mark["QuoteDebitToEur"])) / 2
        adverse = central - (entry_spread + spread + 2 * (entry_slip + end_slip)) * units * fx_mid
        adverse_path.append(adverse)
    gross = convert((midpoint(path[-1]) - midpoint(entry)) * side * units, path[-1])
    return gross, central, adverse, min(adverse_path)


def panel(tape, receipt):
    indices = ("US500", "US30")
    quotes = {symbol: {} for symbol in indices}
    for mark in tape["Marks"]:
        symbol = mark["Symbol"]
        if symbol not in quotes:
            continue
        at = mark["At"]
        need(at % M5 == 1500 and at not in quotes[symbol] and
             0 < float(mark["Bid"]) <= float(mark["Ask"]), "INVALID_PAIRED_MARK")
        quotes[symbol][at] = mark

    bars = next(row["M5"] for row in tape["Bars"] if row["Symbol"] == "US500")
    closes = {row["CloseAt"]: row for row in bars if row["OpenAt"] + M5 == row["CloseAt"]}
    need(len(closes) == len(bars), "INVALID_US500_M5_CLOCK")
    contract = receipt["CurrentContractsBySymbol"]["US500"]
    need(contract["OriginalBrokerAuthenticated"] and not contract["HistoricalTariffContinuityCertified"]
         and contract["QuoteAsset"] == "USD" and contract["PreciseRateWire"] == 0
         and contract["PreciseMinimumWire"] == 0 and contract["PnlConversionFeeBps"] == 0,
         "US500_CONTRACT_OUTSIDE_FROZEN_COST_PROFILE")
    terms = {key: value for key, value in contract.items() if key != "ObservedAtUtcMs"}
    units = float(contract["MinimumUnits"])
    rollover = int(contract["SwapTimeUtcMinute"])
    need(units > 0 and 0 <= rollover < 1440, "US500_MINIMUM_OR_ROLLOVER_UNKNOWN")
    weeks = []
    for week in range(17):
        result = {"week": (START + timedelta(weeks=week)).isoformat(), "eligible": 0,
                  "missing_decision": 0, "missing_path": 0,
                  "unpriced_by_policy": dict.fromkeys(POLICIES, 0),
                  "rows": []}
        for day in range(5):
            current = START + timedelta(weeks=week, days=day)
            for minute in range(600, 811, 30):
                decision = datetime(current.year, current.month, current.day,
                                    minute // 60, minute % 60, tzinfo=NY)
                clock = int(decision.timestamp()) * 1000
                at = clock + 1500
                history = [closes.get(clock - offset * M5) for offset in (2, 1, 0)]
                if (any(bar is None for bar in history) or
                        any(t not in quotes[s] for s in indices for t in (at - 3 * M5, at))):
                    result["missing_decision"] += 1
                    continue
                result["eligible"] += 1
                movement = float(history[-1]["Close"]) - float(history[0]["Open"])
                side = (movement > 0) - (movement < 0)
                own, peer = (quote_confirm(quotes[s][at - 3 * M5], quotes[s][at], side)
                             for s in indices)
                sides = dict(zip(POLICIES, (0, 1, -1, side, side if own else 0,
                                             side if own and peer else 0)))
                entry_at, exit_at = at + M5, at + 6 * M5
                entry_day = datetime.fromtimestamp(entry_at / 1000, timezone.utc)
                rollover_at = entry_day.replace(hour=rollover // 60, minute=rollover % 60,
                                                second=0, microsecond=0).timestamp() * 1000
                need(entry_day.date() == datetime.fromtimestamp(exit_at / 1000, timezone.utc).date(),
                     "UNEXPECTED_CROSS_DATE_HOLD")
                path = [quotes["US500"].get(t) for t in range(entry_at, exit_at + 1, M5)]
                if any(m is None for m in path) or entry_at < rollover_at <= exit_at:
                    result["missing_path"] += 1
                    for policy, direction in sides.items():
                        result["unpriced_by_policy"][policy] += int(direction != 0)
                    continue
                for mark in path:
                    observed = mark["Contract"]
                    need({key: value for key, value in observed.items() if key != "ObservedAtUtcMs"} == terms
                         and observed["ObservedAtUtcMs"] > mark["At"] and
                         0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
                         and float(mark["SlippagePerSideQuote"]) >= 0,
                         "US500_COST_OR_CONVERSION_MISMATCH")
                priced = {direction: markout(path, direction, units) for direction in (1, -1)}
                result["rows"].append({
                    policy: priced[direction] if direction else None
                    for policy, direction in sides.items()
                })
        weeks.append(result)
    return weeks


def quantile(values, p):
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    low = int(rank)
    return ordered[low] + (rank - low) * (ordered[ceil(rank)] - ordered[low])


def summarize(weeks):
    rows = [row for week in weeks for row in week["rows"]]
    totals = {}
    for policy in POLICIES:
        active = [row[policy] for row in rows if row[policy] is not None]
        aggregates = [sum(row[i] for row in active) for i in range(3)]
        totals[policy] = dict(
            priced_markouts=len(active), gross_eur_sum=aggregates[0],
            central_eur_sum=aggregates[1], adverse_eur_sum=aggregates[2],
            adverse_eur_per_clock=aggregates[2] / len(rows) if rows else None,
            adverse_eur_per_active=aggregates[2] / len(active) if active else None,
            adverse_loss_fraction=mean(row[2] < 0 for row in active) if active else None,
            adverse_p05_eur=quantile([row[2] for row in active], .05) if active else None,
            worst_sampled_holding_markout_eur=min((row[3] for row in active), default=None),
        )
    return {"common_complete_clocks": len(rows), "policies": totals}


def incremental_intervals(weeks):
    pairs = []
    for week in weeks:
        rows = week["rows"]
        values = [((row["both_indices"] or (0, 0, 0))[2],
                   (row["own_quotes"] or (0, 0, 0))[2]) for row in rows]
        pairs.append((len(rows), sum(a for a, _ in values), sum(a - b for a, b in values)))
    rng = Random(20261113)
    samples = []
    for _ in range(5000):
        indexes = [index for _ in range(ceil(len(weeks) / 4))
                   for start in [rng.randrange(len(weeks) - 3)]
                   for index in range(start, start + 4)][:len(weeks)]
        count = sum(pairs[index][0] for index in indexes)
        samples.append(tuple(sum(pairs[index][column] for index in indexes) / count for column in (1, 2)))
    return {name: [quantile(values, .025), quantile(values, .975)] for name, values in
            zip(("both_indices_absolute", "both_indices_minus_own"), zip(*samples))}


def main():
    tape, receipt = original_tape()
    weeks = panel(tape, receipt)
    overall = summarize(weeks)
    phases = [summarize(weeks[:8]), summarize(weeks[8:])]
    policies = overall["policies"]
    value = policies["both_indices"]["adverse_eur_per_clock"]
    output = {
        "classification": "EXPOSED_DEVELOPMENT_CONDITIONAL_MINIMUM_SIZE_MARKOUT",
        "source_run": int(RUN), "source_cipher_artifact": 14015883688,
        "source_receipt_artifact": 14016671008, "source_cipher_sha256": CIPHER_SHA,
        "source_receipt_sha256": RECEIPT_SHA, "source_plaintext_sha256": SOURCE_SHA,
        "protocol_sha256": sha256(Path(__file__).with_name("US500_QUOTE_CONFIRMATION.md").read_bytes()).hexdigest(),
        "scheduled_clocks": 680, "holding_minutes": 25,
        "current_minimum_margin_eur": receipt["ObservedMarginGridBySymbol"]["US500"][0],
        "weekly": [dict({k: v for k, v in week.items() if k != "rows"}, **summarize([week]))
                   for week in weeks],
        "overall": overall, "first_8_and_last_9_weeks": phases,
        "descriptive_95pct_moving_block_eur_per_clock": incremental_intervals(weeks),
        "primary_increment_adverse_eur_per_clock": value - policies["own_quotes"]["adverse_eur_per_clock"],
        "economic_followup_screen_passed": (
            value > max(policies[k]["adverse_eur_per_clock"] for k in POLICIES[:-1])
            and all(phase["policies"]["both_indices"]["adverse_eur_per_clock"] > 0
                    for phase in phases)
        ),
        "new_broker_requests": 0, "funded_round_trips": 0, "funded_net_eur": None,
        "continuous_floating_drawdown": None, "independent_confirmation": False,
        "orders_submitted": 0, "cloud_activated": False,
    }
    Path("us500-quote-confirmation-public.json").write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print("US500_QUOTE_CONFIRMATION_COMPLETE", overall["common_complete_clocks"],
          output["economic_followup_screen_passed"])


if __name__ == "__main__":
    main()
