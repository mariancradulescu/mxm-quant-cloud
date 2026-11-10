"""LMA1: prespecified exploratory London metals auction price-pressure screen."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from math import log
from pathlib import Path
from statistics import mean
from decimal import Decimal

from .contract_eur_cost import fee_at_current_contract, IncompleteCostEvidence
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, need
from .guard import require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate

START = date(2026, 5, 4)
WEEKS = 26
TARGETS = {"XAGUSD": 12, "XPTUSD": 14}
SYMBOLS = (*TARGETS, "EURUSD")
ET = ZoneInfo("Europe/London")
BAR = 300_000
HOLIDAYS = {date(2026, 5, 4), date(2026, 5, 25), date(2026, 8, 31)}


def clock(day, hour, minute=0):
    return int(datetime.combine(day, time(hour, minute), ET).timestamp() * 1000)


def move(bars, start, end):
    if any(t not in bars for t in range(start, end + BAR, BAR)):
        return None
    return 10_000 * log(bars[end] / bars[start])


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
            need(requests < 175, "LMA1_READ_ONLY_BUDGET")
            require_read_only_request(q)
            r = t.request(q)
            requests += 1
            need(type(r) is result_type and r.IsInitialized()
                 and r.ctidTraderAccountId == account, "LMA1_RESPONSE_ACCOUNT_OR_TYPE")
            return r

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                         includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        currencies = {a.assetId: a.name for a in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and currencies.get(trader.trader.depositAssetId) == "EUR", "LMA1_BROKER_OR_EUR")
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
                     "LMA1_SYMBOL_CONTRACT")
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
            bars = {}
            for week in range(WEEKS):
                monday = START + timedelta(weeks=week)
                for first, last in ((0, 2), (3, 4)):
                    lo = clock(monday + timedelta(days=first), 10)
                    hi = clock(monday + timedelta(days=last), 15)
                    r = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                                symbolId=light.symbolId, period=e.M5, fromTimestamp=lo,
                                toTimestamp=hi), m.ProtoOAGetTrendbarsRes)
                    need(r.period == e.M5 and not r.hasMore
                         and (not r.HasField("symbolId") or r.symbolId == light.symbolId), "LMA1_BAR_RESPONSE")
                    bars.update((close, price) for _, close, _, _, _, price, _
                                in decode_bars(r.trendbar, lo - BAR, hi + BAR, 5) if close <= hi)
            tape[symbol] = bars
    finally:
        t.close()

    results = {}
    for symbol, hour in TARGETS.items():
        margin = terms.get(symbol, {}).get("currentMinimumMarginEur")
        gate = bool(margin and 0 < min(margin.values()) <= max(margin.values()) <= 300)
        weekly = [defaultdict(list), defaultdict(list)]
        missing_prices = missing_cost = 0
        examples = []
        for i in range(7 * WEEKS):
            day = START + timedelta(days=i)
            if day.weekday() >= 5 or day in HOLIDAYS or not gate or "EURUSD" not in tape:
                continue
            bars = tape[symbol]
            fx = tape["EURUSD"]
            for offset, buckets in enumerate(weekly):
                event = clock(day, hour - offset)
                start, end = event + BAR, event + 7 * BAR
                impulse = move(bars, event - 6 * BAR, event)
                if impulse is None:
                    missing_prices += 1
                    continue
                if abs(impulse) < 25:
                    continue
                if move(bars, start, end) is None or start not in fx or end not in fx:
                    missing_prices += 1
                    continue
                side = -1 if impulse > 0 else 1
                contract_info = contracts[symbol]
                quote = terms[symbol]["currentContract"]["QuoteAsset"]
                units = Decimal(contract_info.minVolume) / 100
                fee = Decimal(0)
                notional = None
                min_fee = Decimal(0)
                try:
                    for stamp in (start, end):
                        price = Decimal(bars[stamp]) / 100_000
                        usd = Decimal(100_000) / fx[stamp]
                        rates = {"USD": usd, "EUR": Decimal(1)}
                        leg = fee_at_current_contract(contract_info, quote, units, price, rates)
                        if notional is None:
                            notional = units * price * rates[quote]
                        fee += Decimal(leg["oneSideContractCommissionEur"])
                        min_fee += Decimal(leg["minimumCommissionEur"])
                except (IncompleteCostEvidence, KeyError):
                    missing_cost += 1
                    continue
                gross = 10_000 * (bars[end] / bars[start] - 1)
                cost = float(10_000 * fee / notional)
                buckets[i // 7].append((side * gross, gross, cost))
                if offset == 0 and not examples:
                    examples.append(dict(minUnits=float(units), entryNotionalEur=float(notional),
                                         twoSideMinFeeEur=float(min_fee), twoSideFeeEur=float(fee),
                                         breakEvenBps=cost, entryUtcMs=start))
        halves = []
        for lo, hi in ((0, 13), (13, 26)):
            def summary(buckets):
                rows = [buckets[w] for w in range(lo, hi) if buckets[w]]
                return dict(sessions=sum(map(len, rows)), activeWeeks=len(rows),
                            grossBps=mean(mean(x[0] for x in row) for row in rows) if rows else None,
                            longBps=mean(mean(x[1] for x in row) for row in rows) if rows else None,
                            feeBps=mean(mean(x[2] for x in row) for row in rows) if rows else None)
            halves.append(dict(auction=summary(weekly[0]), placebo=summary(weekly[1])))
        passes = all(
            (a := h["auction"])["sessions"] >= 15 and a["activeWeeks"] >= 6
            and (p := h["placebo"])["sessions"] >= 10 and p["activeWeeks"] >= 6
            and a["grossBps"] > max(abs(a["longBps"]), p["grossBps"], a["feeBps"])
            for h in halves)
        results[symbol] = dict(currentMarginGate=gate, halves=halves,
                               missingPriceWindows=missing_prices, missingCostWindows=missing_cost,
                               minSizeFeeExample=examples[0] if examples else None,
                               screenPassed=passes)
    payload = dict(protocolSha256=sha256(Path("research/LMA1.md").read_bytes()).hexdigest(),
                   contractTerms=terms, missingEnabledSymbols=missing,
                   barCounts={symbol: len(bars) for symbol, bars in tape.items()},
                   readOnlyRequestsAfterAuth=requests, results=results,
                   independentConfirmation=False, fundedNetEur=None, orders=0, cloudActivated=False)
    Path("lma1-public.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    print("LMA1_RECEIPT " + json.dumps(payload, separators=(",", ":"), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
