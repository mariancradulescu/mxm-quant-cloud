"""OSA1: prespecified exploratory US cash-open oil-to-producer transmission."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from math import log
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, need
from .guard import require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate

START = date(2026, 5, 4)
WEEKS = 26
SYMBOLS = ("SpotCrude", "US500", "XOM.US", "CVX.US")
TARGETS = SYMBOLS[2:]
ET = ZoneInfo("America/New_York")
BAR = 900_000


def clock(day, hour, minute=0):
    return int(datetime.combine(day, time(hour, minute), ET).timestamp() * 1000)


def move(bars, start, end):
    if any(t not in bars for t in range(start, end + BAR, BAR)):
        return None
    return 10_000 * log(bars[end] / bars[start])


def analyze(weeks):
    complete = [(week, outcomes) for week, outcomes in weeks.items() if outcomes]
    result = []
    for week, outcomes in complete:
        n = len(outcomes)
        gross = mean(side * stock for side, stock, _ in outcomes)
        relative = mean(side * (stock - market) for side, stock, market in outcomes)
        long = mean(stock for _, stock, _ in outcomes)
        result.append(dict(week=week, sessions=n, grossBps=gross,
                           marketAdjustedBps=relative, longBps=long, shortBps=-long))
    return result


def main():
    t = StdlibCTraderTransport()
    requests = 0
    missing = []
    tape = {}
    terms = {}
    try:
        account = authenticate(t)

        def request(q, result_type):
            nonlocal requests
            need(requests < 130, "OSA1_READ_ONLY_BUDGET")
            require_read_only_request(q)
            r = t.request(q)
            requests += 1
            need(type(r) is result_type and r.IsInitialized()
                 and r.ctidTraderAccountId == account, "OSA1_RESPONSE_ACCOUNT_OR_TYPE")
            return r

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                         includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        currencies = {a.assetId: a.name for a in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and currencies.get(trader.trader.depositAssetId) == "EUR", "OSA1_BROKER_OR_EUR")
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
                     "OSA1_SYMBOL_CONTRACT")
                c = details.symbol[0]
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
                lo, hi = clock(monday, 8), clock(monday + timedelta(days=4), 11)
                r = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                            symbolId=light.symbolId, period=e.M15, fromTimestamp=lo,
                            toTimestamp=hi), m.ProtoOAGetTrendbarsRes)
                need(r.period == e.M15 and not r.hasMore
                     and (not r.HasField("symbolId") or r.symbolId == light.symbolId), "OSA1_BAR_RESPONSE")
                bars.update((close, price) for _, close, _, _, _, price, _
                            in decode_bars(r.trendbar, lo - BAR, hi + BAR, 15) if close <= hi)
            tape[symbol] = bars
    finally:
        t.close()

    gate = all(
        symbol in terms and terms[symbol]["tradingMode"] == 0
        and terms[symbol]["currentMinimumMarginEur"] is not None
        and 0 < min(terms[symbol]["currentMinimumMarginEur"].values())
        and max(terms[symbol]["currentMinimumMarginEur"].values()) <= 300
        for symbol in TARGETS
    )
    by_week = defaultdict(list)
    counts = dict(completeSignalWindows=0, aboveOilThreshold=0, missingOutcome=0)
    if not missing and gate:
        for i in range(7 * WEEKS):
            day = START + timedelta(days=i)
            if day.weekday() >= 5:
                continue
            oil = move(tape["SpotCrude"], clock(day, 9), clock(day, 9, 30))
            if oil is None:
                continue
            counts["completeSignalWindows"] += 1
            if abs(oil) < 40:
                continue
            counts["aboveOilThreshold"] += 1
            start, end = clock(day, 10), clock(day, 10, 30)
            returns = [move(tape[symbol], start, end) for symbol in (*TARGETS, "US500")]
            if any(x is None for x in returns):
                counts["missingOutcome"] += 1
                continue
            by_week[str(day - timedelta(days=day.weekday()))].append(
                (1 if oil > 0 else -1, mean(returns[:2]), returns[2]))
    weekly = analyze(by_week)
    split = str(START + timedelta(weeks=13))
    halves = []
    for rows in ([x for x in weekly if x["week"] < split],
                 [x for x in weekly if x["week"] >= split]):
        averages = {k: mean(x[k] for x in rows) if rows else None
                    for k in ("grossBps", "marketAdjustedBps", "longBps", "shortBps")}
        halves.append(dict(activeWeeks=len(rows), **averages))
    complete_sessions = sum(x["sessions"] for x in weekly)
    passes = complete_sessions >= 30 and len(weekly) >= 12 and all(
        x["activeWeeks"] and x["grossBps"] > max(x["longBps"], x["shortBps"])
        and x["marketAdjustedBps"] > 0 for x in halves)
    payload = dict(protocolSha256=sha256(Path("research/OSA1.md").read_bytes()).hexdigest(),
                   contractTerms=terms, missingEnabledSymbols=missing, currentMarginGate=gate,
                   barCounts={symbol: len(bars) for symbol, bars in tape.items()},
                   readOnlyRequestsAfterAuth=requests, counts=counts, weekly=weekly, halves=halves,
                   completeSessions=complete_sessions, predictiveGate=passes,
                   independentConfirmation=False, fundedNetEur=None, orders=0, cloudActivated=False)
    Path("osa1-public.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    print("OSA1_RECEIPT " + json.dumps(payload, separators=(",", ":"), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
