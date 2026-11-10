"""ESP1: two predeclared, distinct economic mechanisms on original Pepperstone data."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, need
from .guard import require_read_only_request
from .contract_eur_cost import fee_at_current_contract, IncompleteCostEvidence
from .mef1 import latest
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate

START = date(2026, 5, 4)
WEEKS = 26
ET = ZoneInfo("America/New_York")
M5 = 300_000
TARGETS = ("US2000", "SpotCrude")
SYMBOLS = (*TARGETS, "US500")
EIA_EXCLUDED_WEEKS = {date(2026, 5, 25), date(2026, 9, 7), date(2026, 10, 12)}


def clock(day, hour, minute=0):
    return int(datetime.combine(day, time(hour, minute), ET).timestamp() * 1000)


def move(rows, start, end):
    if any(t not in rows for t in range(start, end + M5, M5)):
        return None
    return 10_000 * (rows[end] / rows[start] - 1)


def collect_bars(request, account, tape):
    output = {}
    for symbol, (sid, _) in tape.items():
        rows = {}
        for week in range(WEEKS):
            monday = START + timedelta(weeks=week)
            for first, last in ((0, 2), (3, 4)):
                lo = clock(monday + timedelta(days=first), 10)
                hi = clock(monday + timedelta(days=last), 15)
                r = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                            symbolId=sid, period=e.M5, fromTimestamp=lo, toTimestamp=hi),
                            m.ProtoOAGetTrendbarsRes)
                need(r.period == e.M5 and not r.hasMore
                     and (not r.HasField("symbolId") or r.symbolId == sid), "ESP1_BAR_RESPONSE")
                rows.update((close, price) for _, close, _, _, _, price, _
                            in decode_bars(r.trendbar, lo - M5, hi + M5, 5) if close <= hi)
        output[symbol] = rows
    return output


def signal(symbol, bars, day, weekday):
    if symbol == "US2000":
        t = clock(day, 12)
        target = move(bars[symbol], t - 12 * M5, t)
        broad = move(bars.get("US500", {}), t - 12 * M5, t)
        if target is None or broad is None:
            return None
        relative = target - broad
        side = (1 if relative > 0 else -1) if abs(relative) >= 20 else 0
        return side, t + M5, t + 24 * M5 + M5, "main"
    if weekday not in (1, 2):
        return None
    t = clock(day, 10, 40)
    impulse = move(bars[symbol], t - 2 * M5, t)
    if impulse is None:
        return None
    side = (-1 if impulse > 0 else 1) if abs(impulse) >= 35 else 0
    return side, t + M5, t + 9 * M5, "main" if weekday == 2 else "control"


def priced(c, side, opening, closing):
    # All priced terms must be USD or USD-notional. The conversion factor
    # cancels in the normalized fee; use USD as unit of account, never EUR P&L.
    if c.minCommissionType == 1 and c.minCommissionAsset != "USD":
        raise IncompleteCostEvidence("ESP1_FEE_CURRENCY")
    units = Decimal(c.minVolume) / 100
    notional = units * (sum(opening) / 2)
    entry = opening[1] if side == 1 else opening[0]
    exit_price = closing[0] if side == 1 else closing[1]
    fees = sum(Decimal(fee_at_current_contract(c, "USD", units, p, {"USD": 1})
                       ["oneSideContractCommissionEur"]) for p in (entry, exit_price))
    pnl = side * units * (exit_price - entry)
    if not c.HasField("pnlConversionFeeRate"):
        raise IncompleteCostEvidence("ESP1_PNL_CONVERSION_UNKNOWN")
    conversion = abs(pnl) * Decimal(c.pnlConversionFeeRate) / 10_000
    return float(10_000 * (pnl - fees - conversion) / notional)


def summarize(buckets, start, end):
    rows = [buckets[i] for i in range(start, end) if buckets[i]]
    return dict(sessions=sum(map(len, rows)), activeWeeks=len(rows),
                **{k: mean(mean(x[k] for x in w) for w in rows) if rows else None
                   for k in ("gross", "central", "adverse", "longAdverse", "shortAdverse")})


def compare(request, account, tape, bars, contracts, terms):
    results = {}
    for symbol in TARGETS:
        if symbol not in bars:
            continue
        sid, quote = tape[symbol]
        c = contracts[symbol]
        margin = terms[symbol]["currentMinimumMarginEur"]
        funding_gate = bool(margin and min(margin.values()) > 0 and max(margin.values()) <= 300)
        groups = {"main": defaultdict(list), "control": defaultdict(list)}
        gross_groups = {"main": defaultdict(list), "control": defaultdict(list)}
        counts = defaultdict(int)
        for i in range(WEEKS * 7):
            day = START + timedelta(days=i)
            if day.weekday() >= 5:
                continue
            if symbol == "SpotCrude" and day - timedelta(days=day.weekday()) in EIA_EXCLUDED_WEEKS:
                continue
            state = signal(symbol, bars, day, day.weekday())
            if state is None:
                continue
            side, start, end, group = state
            if not side:
                continue
            counts[group + "Signals"] += 1
            gross = move(bars[symbol], start, end)
            if gross is None:
                counts[group + "MissingMark"] += 1
                continue
            gross_groups[group][i // 7].append(side * gross)
            if not funding_gate or quote != "USD":
                continue
            opening = latest(request, account, sid, start)
            closing = latest(request, account, sid, end)
            if opening is None or closing is None:
                counts[group + "MissingQuotes"] += 1
                continue
            try:
                long = priced(c, 1, opening, closing)
                short = priced(c, -1, opening, closing)
            except IncompleteCostEvidence:
                counts[group + "MissingCost"] += 1
                continue
            adjusted = long if side == 1 else short
            groups[group][i // 7].append(dict(gross=side * gross, central=adjusted - .5,
                adverse=adjusted - 2, longAdverse=long - 2, shortAdverse=short - 2))
        halves = []
        for lo, hi in ((0, 13), (13, WEEKS)):
            half = {k: summarize(v, lo, hi) for k, v in groups.items()}
            for group, buckets in gross_groups.items():
                rows = [buckets[w] for w in range(lo, hi) if buckets[w]]
                half[group]["barOnlySessions"] = sum(map(len, rows))
                half[group]["barOnlyGrossBps"] = mean(map(mean, rows)) if rows else None
            halves.append(half)
        min_sessions = 10 if symbol == "US2000" else 5
        passed = all(
            (a := h["main"])["sessions"] >= min_sessions and a["activeWeeks"] >= 4
            and a["adverse"] > max(0, a["longAdverse"], a["shortAdverse"])
            and (symbol != "SpotCrude" or (h["control"]["sessions"] >= 5
                 and a["adverse"] > h["control"]["adverse"]))
            for h in halves)
        results[symbol] = dict(counts=dict(counts), terms=terms[symbol],
                               currentIndividualMarginGate=funding_gate, halves=halves,
                               passedConditionalGate=passed)
    return results


def main():
    t = StdlibCTraderTransport()
    requests = 0
    missing = []
    tape = {}
    terms = {}
    contracts = {}
    try:
        account = authenticate(t)

        def request(q, result_type):
            nonlocal requests
            need(requests < 2600, "ESP1_READ_ONLY_BUDGET")
            require_read_only_request(q)
            r = t.request(q)
            requests += 1
            need(type(r) is result_type and r.IsInitialized()
                 and r.ctidTraderAccountId == account, "ESP1_RESPONSE_ACCOUNT_OR_TYPE")
            return r

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                         includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        currencies = {a.assetId: a.name for a in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and currencies.get(trader.trader.depositAssetId) == "EUR", "ESP1_BROKER_OR_EUR")
        available = {x.symbolName.casefold(): x for x in roster.symbol if x.enabled}
        for symbol in SYMBOLS:
            light = available.get(symbol.casefold())
            if light is None:
                missing.append(symbol)
                continue
            if symbol in TARGETS:
                details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                                  symbolId=[light.symbolId]), m.ProtoOASymbolByIdRes)
                need(len(details.symbol) == 1 and details.symbol[0].symbolId == light.symbolId,
                     "ESP1_SYMBOL_CONTRACT")
                c = details.symbol[0]
                contracts[symbol] = c
                terms[symbol] = dict(
                    tradingMode=int(c.tradingMode),
                    currentContract=contract(symbol, c, currencies.get(light.quoteAssetId),
                                             int(datetime.now(ET).timestamp() * 1000)),
                    currentMinimumMarginEur=None,
                )
                if c.tradingMode == 0 and c.minVolume > 0:
                    r = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                                symbolId=light.symbolId, volume=[c.minVolume]),
                                m.ProtoOAExpectedMarginRes)
                    if r.HasField("moneyDigits") and len(r.margin) == 1 and r.margin[0].volume == c.minVolume:
                        margin = r.margin[0]
                        terms[symbol]["currentMinimumMarginEur"] = {
                            "buy": margin.buyMargin / 10**r.moneyDigits,
                            "sell": margin.sellMargin / 10**r.moneyDigits,
                        }
            tape[symbol] = (light.symbolId, currencies.get(light.quoteAssetId))
        bars = collect_bars(request, account, tape)
        receipts = compare(request, account, tape, bars, contracts, terms)
    finally:
        t.close()
    payload = dict(protocolSha256=sha256(Path("research/ESP1.md").read_bytes()).hexdigest(),
                   missingEnabledSymbols=missing, readOnlyRequestsAfterAuth=requests,
                   barCounts={symbol: len(rows) for symbol, rows in bars.items()}, candidates=receipts, fundedNetEur=None, orders=0, cloudActivated=False)
    Path("esp1-public.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    print("ESP1_RECEIPT " + json.dumps(payload, separators=(",", ":"), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
