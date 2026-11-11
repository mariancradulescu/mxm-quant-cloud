"""SQIC1: preregistered pooled dealer-quote-impulse economic screen.

Three fixed markets. All closed research stays untouched. Original authenticated
Pepperstone access is READ-ONLY; no orders, Cloud or historical fill certification.
"""
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_side, need
from .guard import require_read_only_request
from .mef1 import latest
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate
from .regional_equity_and_bond_transmission import (
    no_financing, priced_sides, session_ok,
)

NY = ZoneInfo("America/New_York")
START = date(2026, 5, 4)
SYMBOLS = ("AUDUSD", "US2000", "SpotCrude")
DECISION_HOURS = ((10, 0), (10, 30), (11, 0))
PRIOR = (-120, -60, 0)
ENTRY = 30
EXIT = 1230
MAX_REQUESTS = 10000


def clock(day, hour, minute):
    return int(datetime.combine(day, time(hour, minute), NY).timestamp() * 1000)


def point_at(rows, stamp, age=20000):
    if not rows:
        return None
    idx = bisect_right([row[0] for row in rows], stamp) - 1
    if idx < 0 or not 0 <= stamp - rows[idx][0] <= age:
        return None
    return rows[idx][1]


def at_pair(bids, asks, stamp):
    b, a = point_at(bids, stamp), point_at(asks, stamp)
    if b is None or a is None or b <= 0 or a < b:
        return None
    return b, a


def quote_impulse(prior):
    """Causal, fixed direction; raw integer ticks, so no float timing/bps noise."""
    if any(s not in prior or prior[s] is None for s in PRIOR):
        return 0
    bids = [prior[s][0] for s in PRIOR]
    asks = [prior[s][1] for s in PRIOR]
    directions = []
    for i in (0, 1):
        db, da = bids[i+1] - bids[i], asks[i+1] - asks[i]
        if db == 0 or da == 0 or db * da <= 0:
            return 0
        directions.append(1 if db > 0 else -1)
    if directions[0] != directions[1]:
        return 0
    earlier_spread = max(asks[i] - bids[i] for i in (0, 1))
    if asks[2] - bids[2] > earlier_spread:
        return 0
    # Midpoint expressed as BID+ASK. Two times spread for MID change
    # becomes four times raw spread in BID+ASK units.
    if abs((bids[2] + asks[2]) - (bids[0] + asks[0])) < 4 * earlier_spread:
        return 0
    return directions[0]


def quote_window(request, account, symbol_id, decision, counts):
    start, stop = decision - 140000, decision + ENTRY * 1000
    sides = []
    for side in (e.BID, e.ASK):
        reply = request(m.ProtoOAGetTickDataReq(
            ctidTraderAccountId=account, symbolId=symbol_id, type=side,
            fromTimestamp=start, toTimestamp=stop), m.ProtoOAGetTickDataRes)
        if reply.hasMore:
            counts["truncatedQuoteWindows"] += 1
            return {}
        sides.append(decode_side(reply.tickData, start, stop))
    return {s: at_pair(sides[0], sides[1], decision + s * 1000)
            for s in (*PRIOR, ENTRY)}


def priced_weekly(rows, mode):
    if not rows:
        return {}
    names = ("model", "long", "short", "cash")
    return {name: mean(mean(item[mode][name] for item in week)
                       for week in rows.values())
            for name in names}


def summarise(weeks, first, market_results):
    counts = Counter()
    booked = defaultdict(list)
    for symbol in SYMBOLS:
        block = market_results.get(symbol, {})
        part = block.get(first, {})
        counts.update(part.get("counts", {}))
        for w, vals in part.get("pricedByWeek", {}).items():
            booked[w].extend(vals)
    total_signals = counts["causalSignals"]
    priced = counts["pricedWithExactCost"]
    coverage = (priced >= 30 and len(booked) >= 8 and
                4 * priced >= 3 * total_signals)
    adverse = priced_weekly(booked, "adverse")
    pass_gate = (coverage and all(adverse["model"] > adverse[k]
                                 for k in ("long", "short", "cash")))
    return {
        "scheduled": counts["scheduled"],
        "sourceAndMarketEligibilityUnknown": counts["ineligibleMarketOrSession"],
        "missingPriorQuote": counts["missingCausalPriorQuote"],
        "causalSignals": total_signals,
        "missingPricedQuoteOrFx": counts["missingPricedQuoteOrFx"],
        "missingCostOrFx": counts["missingCostOrFx"],
        "priced": priced, "activeWeeks": len(booked),
        "counts": dict(counts),
        "centralBps": priced_weekly(booked, "central"),
        "adverseBps": adverse,
        "coverageGate": bool(coverage), "passed": bool(pass_gate)
    }


def evaluate(request, account, tape, contracts, margins, receipt):
    market_results = {}
    for name in SYMBOLS:
        market_results[name] = {}
        sid = tape.get(name)
        terms = contracts.get(name)
        margin = margins.get(name)
        if (sid is None or terms is None or margin is None or
            min(margin) <= 0 or max(margin) > 300 or
            not terms.HasField("enableShortSelling") or
            not terms.enableShortSelling):
            receipt["marketSourceEligibility"][name] = "UNKNOWN_OR_NOT_CURRENTLY_MARGIN_FEASIBLE"
            continue
        receipt["marketSourceEligibility"][name] = "CURRENT_INDIVIDUAL_MINIMUM_ELIGIBLE_ONLY"
        for first in (0, 13):
            counts = Counter()
            booked = defaultdict(list)
            for week in range(first, first + 13):
                monday = START + timedelta(weeks=week)
                for weekday in range(5):
                    day = monday + timedelta(days=weekday)
                    for hour, minute in DECISION_HOURS:
                        counts["scheduled"] += 1
                        t = clock(day, hour, minute)
                        entry, end = t + ENTRY * 1000, t + EXIT * 1000
                        if not session_ok(terms, t - 140000, end) or not no_financing(terms, entry, end):
                            counts["ineligibleMarketOrSession"] += 1
                            continue
                        sample = quote_window(request, account, sid, t, counts)
                        if any(sample.get(mark) is None for mark in PRIOR):
                            counts["missingCausalPriorQuote"] += 1
                            continue
                        direction = quote_impulse(sample)
                        if direction == 0:
                            counts["noQuotePressureSignal"] += 1
                            continue
                        counts["causalSignals"] += 1
                        if sample.get(ENTRY) is None:
                            counts["missingPricedQuoteOrFx"] += 1
                            continue
                        closing = latest(request, account, sid, end)
                        fxin = latest(request, account, tape["EURUSD"], entry)
                        fxout = latest(request, account, tape["EURUSD"], end)
                        if closing is None or fxin is None or fxout is None:
                            counts["missingPricedQuoteOrFx"] += 1
                            continue
                        opening = [D(v) / 100000 for v in sample[ENTRY]]
                        try:
                            net, _ = priced_sides(
                                terms, "USD", opening, closing, fxin, fxout)
                        except (ValueError, ZeroDivisionError, ArithmeticError):
                            counts["missingCostOrFx"] += 1
                            continue
                        counts["pricedWithExactCost"] += 1
                        directions = dict(model=direction, long=1, short=-1, cash=0)
                        booked[week].append({
                            case: {key: net[sign] - (penalty if sign else 0)
                                   for key, sign in directions.items()}
                            for case, penalty in (("central", .5), ("adverse", 2.0))
                        })
            market_results[name][first] = {
                "counts": dict(counts),
                "pricedByWeek": booked
            }
            print(name, "half", first // 13 + 1,
                  "signals", counts["causalSignals"],
                  "priced", counts["pricedWithExactCost"], flush=True)
    halves = [summarise(None, first, market_results) for first in (0, 13)]
    eligible_market_count = sum(1 for s in receipt["marketSourceEligibility"].values()
                                if s == "CURRENT_INDIVIDUAL_MINIMUM_ELIGIBLE_ONLY")
    if any(h["coverageGate"] and not h["passed"] for h in halves):
        verdict = "REJECT_EXACT_SQIC1_RULE"
    elif all(h["passed"] for h in halves) and eligible_market_count == len(SYMBOLS):
        verdict = "SUPPORTS_PROSPECTIVE_NATIVE_FINANCED_FOLLOWUP_ONLY"
    else:
        verdict = "INSUFFICIENT_COMPARABLE_EVIDENCE"
    return {
        "verdict": verdict,
        "halves": halves,
        "markets": {name: {str(first): {
            "counts": dict(s["counts"]),
            "pricedWeeks": len(s["pricedByWeek"]),
            "centralBps": priced_weekly(s["pricedByWeek"], "central"),
            "adverseBps": priced_weekly(s["pricedByWeek"], "adverse")
        } for first, s in blocks.items()} for name, blocks in market_results.items()}
    }


def main():
    transport = StdlibCTraderTransport()
    calls = 0
    protocol = Path("research/sqic1_quote_impulse.md")
    receipt = {
        "study": "SQIC1_POOLED_SPREAD_STABLE_QUOTE_IMPULSE",
        "frozenProtocolSha256": sha256(protocol.read_bytes()).hexdigest(),
        "source": "ORIGINAL_PEPPERSTONE_READ_ONLY_EXPOSED_26_WEEKS",
        "initialProspectiveCapitalEur": 300,
        "marketSourceEligibility": {},
        "originalBrokerFillsCertified": False,
        "independentConfirmation": False,
        "orders": 0,
        "cloudActivated": False,
        "fundedNativeNetEur": None,
        "historicalTariffCertified": False,
    }
    tape, contracts, margins = {}, {}, {}
    try:
        account = authenticate(transport)

        def request(q, result_type):
            nonlocal calls
            need(calls < MAX_REQUESTS, "SQIC1_ORIGINAL_READONLY_REQUEST_BUDGET")
            require_read_only_request(q)
            answer = transport.request(q)
            calls += 1
            if (result_type is m.ProtoOAGetTickDataRes and
                type(answer) is m.ProtoOAErrorRes and
                answer.errorCode == "NO_QUOTES" and
                answer.ctidTraderAccountId == account):
                return result_type(ctidTraderAccountId=account, hasMore=False)
            need(type(answer) is result_type and answer.IsInitialized() and
                 answer.ctidTraderAccountId == account,
                 "SQIC1_ACCOUNT_OR_RESPONSE_MISMATCH")
            return answer

        symbols = request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                         m.ProtoOAAssetListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account),
                         m.ProtoOATraderRes).trader
        names = {v.assetId: v.name for v in assets.asset}
        need("pepperstone" in trader.brokerName.lower()
             and names.get(trader.depositAssetId) == "EUR",
             "SQIC1_ORIGINAL_PEPPERSTONE_EUR_ACCOUNT")
        roster = {s.symbolName.casefold(): s for s in symbols.symbol if s.enabled}
        for symbol in (*SYMBOLS, "EURUSD"):
            found = roster.get(symbol.casefold())
            if found is None:
                continue
            if names.get(found.quoteAssetId) != "USD":
                continue
            tape[symbol] = found.symbolId
            if symbol == "EURUSD":
                continue
            details = request(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account, symbolId=[found.symbolId]),
                m.ProtoOASymbolByIdRes)
            need(len(details.symbol) == 1 and
                 details.symbol[0].symbolId == found.symbolId,
                 "SQIC1_SYMBOL_CONTRACT_MISMATCH")
            s = details.symbol[0]
            contracts[symbol] = s
            if s.minVolume > 0 and s.HasField("tradingMode") and s.tradingMode == 0:
                x = request(m.ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account, symbolId=s.symbolId,
                    volume=[s.minVolume]), m.ProtoOAExpectedMarginRes)
                if x.HasField("moneyDigits") and len(x.margin) == 1 and x.margin[0].volume == s.minVolume:
                    v = x.margin[0]
                    margins[symbol] = [w / 10**x.moneyDigits
                                      for w in (v.buyMargin, v.sellMargin)]
            receipt.setdefault("currentTerms", {})[symbol] = contract(
                symbol, s, "USD", int(datetime.now(UTC).timestamp() * 1000))
        if "EURUSD" not in tape:
            receipt["results"] = dict(verdict="REQUIRED_CONVERSION_SOURCE_UNAVAILABLE")
        else:
            receipt["results"] = evaluate(request, account, tape, contracts, margins, receipt)
    finally:
        transport.close()
    receipt["readOnlyRequestsAfterAuth"] = calls
    receipt["currentIndividualMinimumMarginsEur"] = margins
    Path("sqic1-public.json").write_text(json.dumps(
        receipt, indent=2, allow_nan=False) + "\n")
    print("SQIC1", receipt["results"]["verdict"], calls, flush=True)


if __name__ == "__main__":
    main()
