"""Collect original quotes and evaluate the frozen EURJPY parity hypothesis."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from .custody import seal_new
from .custody_new import checked_public
from .signed_variation_payoff import valuation
from .us500_quote_confirmation import M5, midpoint, need

START = date(2026, 8, 31)
SYMBOLS = ("EURJPY", "EURUSD", "USDJPY")
POLICIES = ("parity", "own_reversal", "long", "short", "cash")


def utc(day):
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()) * 1000


def jpy_to_eur(mark):
    """Use the sealed reverse USDJPY then reverse EURUSD route."""
    route = mark["OriginalFxRoute"]
    need(len(route) == 2, "JPY_CONVERSION_ROUTE_LENGTH")
    credit = debit = 1.0
    for hop, (symbol, base, quote) in zip(
            route, (("USDJPY", "USD", "JPY"), ("EURUSD", "EUR", "USD"))):
        bid, ask = float(hop["Bid"]), float(hop["Ask"])
        need((hop["Symbol"], hop["BaseAsset"], hop["QuoteAsset"]) == (symbol, base, quote)
             and hop["OriginalBrokerAuthenticated"] and 0 <= mark["At"] - hop["AtUtcMs"] <= 2000
             and 0 < bid <= ask, "JPY_CONVERSION_ROUTE_INVALID")
        credit /= ask
        debit /= bid
    return dict(mark, QuoteCreditToEur=credit, QuoteDebitToEur=debit)


def evaluate(tape):
    marks = {symbol: {} for symbol in SYMBOLS}
    for mark in tape["Marks"]:
        series = marks[mark["Symbol"]]
        need(mark["At"] not in series and 0 < float(mark["Bid"]) <= float(mark["Ask"])
             and 0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
             and float(mark["UsdToEur"]) > 0 and float(mark["SlippagePerSideQuote"]) >= 0,
             "INVALID_MARK")
        series[mark["At"]] = jpy_to_eur(mark) if mark["Symbol"] == "EURJPY" else mark
    target = marks["EURJPY"]
    need(bool(target), "EURJPY_MARKS_UNAVAILABLE")
    terms = next(iter(target.values()))["Contract"]
    units = float(terms["MinimumUnits"])
    margin = tape["MarginGrid"]["EURJPY"][0]
    rollover = terms["SwapTimeUtcMinute"]
    need(terms["OriginalBrokerAuthenticated"] and not terms["HistoricalTariffContinuityCertified"]
         and terms["QuoteAsset"] == "JPY" and terms["CommissionType"] == 2
         and terms["PreciseMinimumWire"] == terms["PnlConversionFeeBps"] == 0
         and isinstance(rollover, int) and 0 <= rollover < 1440
         and units == float(margin["VolumeUnits"]) > 0
         and all(m["Contract"] == terms and m["At"] < terms["ObservedAtUtcMs"] for m in target.values()),
         "CONTRACT_UNPRICED")
    commission = float(terms["PreciseRateWire"]) / 1e8 * units / float(terms["LotUnits"])
    weeks = []
    for i in range(10):
        start = START + timedelta(weeks=i)
        result = dict(week=start.isoformat(), scheduled=60, missing_decision=0,
                      intents=0, missing_path=0, priced=0, long_intents=0,
                      worst_sampled_eur=None, eur={p: [0.] * 3 for p in POLICIES})
        for d in range(5):
            midnight = utc(start + timedelta(days=d))
            for minute in range(360, 526, 15):
                t = midnight + minute * 60000 + 1500
                current, eur, yen = [marks[s].get(t) for s in SYMBOLS]
                prior = target.get(t - 3 * M5)
                if None in (current, eur, yen, prior):
                    result["missing_decision"] += 1
                    continue
                high = float(current["Bid"]) > float(eur["Ask"]) * float(yen["Ask"])
                low = float(current["Ask"]) < float(eur["Bid"]) * float(yen["Bid"])
                side = int(low) - int(high)
                if not side:
                    continue
                result["intents"] += 1
                result["long_intents"] += int(side > 0)
                path = [target.get(t + j * M5) for j in range(1, 5)]
                if None in path or t + M5 < midnight + rollover * 60000 <= t + 4 * M5:
                    result["missing_path"] += 1
                    continue
                result["priced"] += 1
                change = midpoint(prior) - midpoint(current)
                own = (change > 0) - (change < 0)
                priced = {direction: valuation(path, direction, units, commission) for direction in (-1, 1)}
                for policy, direction in zip(POLICIES, (side, own, 1, -1, 0)):
                    if direction:
                        for k, amount in enumerate(priced[direction][:3]):
                            result["eur"][policy][k] += amount
                worst = priced[side][3]
                old = result["worst_sampled_eur"]
                result["worst_sampled_eur"] = worst if old is None else min(old, worst)
        weeks.append(result)

    def sums(window):
        return {p: [sum(w["eur"][p][i] for w in window) for i in range(3)] for p in POLICIES}

    total = sums(weeks)
    halves = [sums(weeks[:5]), sums(weeks[5:])]
    return {
        "counts": {k: sum(w[k] for w in weeks)
                   for k in ("scheduled", "missing_decision", "intents", "missing_path", "priced", "long_intents")},
        "weekly": weeks, "total": total, "halves": halves, "margin": margin,
        "commission_usd_per_side": commission, "contract": terms,
        "followup": all(h["parity"][2] > 0 for h in halves)
        and total["parity"][2] > max(total[p][2] for p in POLICIES[1:]),
    }


def main():
    from .native_original_openapi_product_replay import collect_and_evaluate

    run = os.environ["GITHUB_RUN_ID"]
    key = checked_public(Path("new-recipient-output"), run)
    end = START + timedelta(weeks=10)
    days = [(START + timedelta(weeks=i // 5, days=i % 5)).isoformat() for i in range(50)]

    def receive(raw):
        sealed = seal_new(raw, key, run)
        Path("eurjpy-quote-parity-source.v2.enc").write_bytes(sealed)
        tape = json.loads(raw)
        result = evaluate(tape)
        result.update(
            classification="EXPOSED_CONDITIONAL_EUR_SINGLE_LEG",
            protocol_sha256=sha256(Path(__file__).with_name("EURJPY_QUOTE_PARITY.md").read_bytes()).hexdigest(),
            source_cipher_sha256=sha256(sealed).hexdigest(),
            source_plain_sha256=sha256(raw).hexdigest(), source_run=int(run),
            bars={x["Symbol"]: len(x["M5"]) for x in tape["Bars"]},
            marks={s: sum(m["Symbol"] == s for m in tape["Marks"]) for s in SYMBOLS},
            read_only_requests=tape["ReadOnlyRequests"], amount_order=["gross", "central", "adverse"],
            hold_minutes=15, funded_round_trips=0, funded_net_eur=None,
            independent_confirmation=False, orders_submitted=0, cloud_activated=False,
        )
        Path("eurjpy-quote-parity-public.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")

    collect_and_evaluate({
        "symbols": SYMBOLS, "source_start": utc(START), "start": utc(START), "end": utc(end),
        "event_days": days, "bar_ranges": ((utc(START), utc(end)),),
        "quote_hour_start": 5, "quote_hour_end": 10, "quote_interval_ms": M5,
        "quote_age_ms": 2000, "quote_chunk_minutes": 60, "bar_chunk_hours": 72,
        "extended_sessions": True, "session_map": True, "ordered_tick_history": True,
        "jpy_route": True, "two_sided_targets": ("EURJPY",), "margin_grid_targets": ("EURJPY",),
        "capture_only": True, "tape_consumer": receive, "report_source_progress": True,
        "label": "ORIGINAL_PEPPERSTONE_EURJPY_QUOTE_PARITY",
    })


if __name__ == "__main__":
    main()
