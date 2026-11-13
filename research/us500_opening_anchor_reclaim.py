"""Evaluate the frozen opening-anchor reclaim using the original NXE1 tape."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

from . import us500_quote_confirmation as source


def evaluate(tape, receipt):
    quotes = {mark["At"]: mark for mark in tape["Marks"] if mark["Symbol"] == "US500"}
    contract = receipt["CurrentContractsBySymbol"]["US500"]
    terms = {k: v for k, v in contract.items() if k != "ObservedAtUtcMs"}
    units = float(contract["MinimumUnits"])
    rollover = int(contract["SwapTimeUtcMinute"])
    source.need(units == .1 and 0 <= rollover < 1440 and contract["QuoteAsset"] == "USD"
                and contract["OriginalBrokerAuthenticated"]
                and not contract["HistoricalTariffContinuityCertified"]
                and all(contract[k] == 0 for k in ("PreciseRateWire", "PreciseMinimumWire",
                                                   "PnlConversionFeeBps")),
                "ORIGINAL_US500_COST_PROFILE_MISMATCH")
    names = ("reclaim", "momentum", "long", "short", "cash")
    weeks = []
    notionals = []
    excursions = []
    for week in range(17):
        start = source.START + timedelta(weeks=week)
        values = {name: [0., 0., 0.] for name in names}
        record = dict(week=start.isoformat(), scheduled=15, missing_decision=0,
                      selected=0, missing_path=0, priced=0, eur=values)
        for day in range(5):
            d = start + timedelta(days=day)
            opening = int(datetime(d.year, d.month, d.day, 9, 30,
                                   tzinfo=source.NY).timestamp()) * 1000 + 1500
            for offset in (90, 180, 270):
                at = opening + offset * 60000
                history = [quotes.get(clock) for clock in range(opening, at + 1, source.M5)]
                if None in history:
                    record["missing_decision"] += 1
                    continue
                mids = [source.midpoint(m) for m in history]
                anchor = mids[0]
                if min(mids[:-1]) <= .998 * anchor and mids[-2] < anchor <= mids[-1]:
                    side = 1
                elif max(mids[:-1]) >= 1.002 * anchor and mids[-2] > anchor >= mids[-1]:
                    side = -1
                else:
                    continue
                record["selected"] += 1
                entry = at + source.M5
                end = entry + 60 * 60000
                path = [quotes.get(clock) for clock in range(entry, end + 1, source.M5)]
                start_dt = datetime.fromtimestamp(entry / 1000, timezone.utc)
                charge = start_dt.replace(hour=rollover // 60, minute=rollover % 60,
                                          second=0, microsecond=0)
                if None in path or entry < charge.timestamp() * 1000 <= end:
                    record["missing_path"] += 1
                    continue
                for mark in path:
                    observed = mark["Contract"]
                    source.need({k: v for k, v in observed.items() if k != "ObservedAtUtcMs"} == terms
                                and observed["ObservedAtUtcMs"] > mark["At"]
                                and 0 < float(mark["Bid"]) <= float(mark["Ask"])
                                and 0 < float(mark["QuoteCreditToEur"]) <= float(mark["QuoteDebitToEur"])
                                and float(mark["SlippagePerSideQuote"]) >= 0,
                                "SOURCE_COST_MISMATCH")
                record["priced"] += 1
                own = (mids[-1] > mids[-7]) - (mids[-1] < mids[-7])
                priced = {s: source.markout(path, s, units) for s in (-1, 1)}
                for name, direction in zip(names, (side, own, 1, -1, 0)):
                    if direction:
                        for j, amount in enumerate(priced[direction][:3]):
                            values[name][j] += amount
                notionals.append(source.convert(source.midpoint(path[0]) * units, path[0]))
                entry_mid = source.midpoint(path[0])
                moves = [source.convert((source.midpoint(m) - entry_mid) * units * side, m)
                         for m in path]
                excursions.append((max(moves), min(moves), priced[side][3]))
        weeks.append(record)

    def aggregate(segment):
        return {name: [sum(w["eur"][name][i] for w in segment) for i in range(3)]
                for name in names}

    totals = aggregate(weeks)
    phases = [aggregate(weeks[:8]), aggregate(weeks[8:])]
    return {
        "source_run": int(source.RUN), "source_cipher_artifact": 14015883688,
        "source_cipher_sha256": source.CIPHER_SHA, "source_plaintext_sha256": source.SOURCE_SHA,
        "source_receipt_sha256": source.RECEIPT_SHA,
        "protocol_sha256": sha256(Path(__file__).with_name("US500_OPENING_ANCHOR_RECLAIM.md").read_bytes()).hexdigest(),
        "classification": "EXPOSED_CONDITIONAL_EUR_MINIMUM_SIZE_NO_FUNDING",
        "hold_minutes": 60, "cost_order": ["gross", "central", "adverse"],
        "counts": {k: sum(w[k] for w in weeks)
                   for k in ("scheduled", "missing_decision", "selected", "missing_path", "priced")},
        "minimum_units": units, "observed_margin_grid_row": receipt["ObservedMarginGridBySymbol"]["US500"][0],
        "median_entry_notional_eur_credit_basis": median(notionals) if notionals else None,
        "median_favorable_adverse_gross_excursion_eur":
            [median(x[i] for x in excursions) for i in (0, 1)] if excursions else None,
        "worst_sampled_adverse_markout_eur": min((x[2] for x in excursions), default=None),
        "totals": totals, "first_8_last_9_weeks": phases, "weekly": weeks,
        "funded_followup_screen_passed":
            all(p["reclaim"][2] > 0 for p in phases)
            and totals["reclaim"][2] > max(totals[n][2] for n in names[1:]),
        "funded_round_trips": 0, "funded_net_eur": None, "continuous_floating_drawdown": None,
        "new_broker_requests": 0, "orders_submitted": 0, "cloud_activated": False,
        "independent_confirmation": False,
    }


def main():
    tape, receipt = source.original_tape()
    result = evaluate(tape, receipt)
    Path("us500-opening-anchor-reclaim-public.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
