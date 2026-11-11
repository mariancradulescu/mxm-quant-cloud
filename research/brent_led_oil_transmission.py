"""Preregistered Brent-to-WTI directional transmission, read-only."""
from collections import Counter, defaultdict
from datetime import UTC, datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, need
from .economic_coverage_and_small_cap_open import DIAGNOSTIC_DAYS, NY, paired, priced
from .guard import require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate
from .regional_equity_and_bond_transmission import (
    BAR, START, clock, move, no_financing, session_ok, sign, summary,
)

TARGET, CONTEXT, FX = "SpotCrude", "SpotBrent", "EURUSD"
HOURS = (10, 12)


def bars_for_week(request, account, sid, monday):
    bars = {}
    for first, last in ((0, 2), (3, 4)):
        start = clock(monday + timedelta(days=first), time(6), NY)
        end = clock(monday + timedelta(days=last), time(13), NY)
        response = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=sid,
                           period=e.M5, fromTimestamp=start, toTimestamp=end), m.ProtoOAGetTrendbarsRes)
        need(response.period == e.M5 and not response.hasMore and
             (not response.HasField("symbolId") or response.symbolId == sid), "OIL_TRANSMISSION_BAR_RESPONSE")
        bars.update((row[0], row) for row in decode_bars(response.trendbar, start, end, 5))
    return bars


def price_window(request, account, ids, terms, entry, exit_at, counts, quote_counts):
    if not session_ok(terms, entry, exit_at) or not no_financing(terms, entry, exit_at):
        counts["missingSessionOrFunding"] += 1
        return None
    sid, quote = ids[TARGET]
    opening, closing = (paired(request, account, sid, at, quote_counts[TARGET])
                        for at in (entry, exit_at))
    fx = ([paired(request, account, ids[FX][0], at, quote_counts[FX]) for at in (entry, exit_at)]
          if opening and closing else [None, None])
    return priced(terms, quote, opening, closing, fx, counts)


def preflight(request, account, ids, terms, margins):
    if (set(ids) != {TARGET, CONTEXT, FX} or terms is None or margins is None
            or ids[TARGET][1] != "USD" or not 0 < min(margins) <= max(margins) <= 300
            or not terms.HasField("enableShortSelling") or not terms.enableShortSelling):
        return dict(admitted=False, clocks=[], reason="SYMBOL_OR_CAPACITY_UNAVAILABLE")
    clocks = []
    for hour in HOURS:
        counts, quote_counts = Counter(), defaultdict(Counter)
        for day in DIAGNOSTIC_DAYS:
            entry = clock(day,time(hour,5),NY)
            exit_at = clock(day,time(hour+1),NY)
            if price_window(request, account, ids, terms, entry, exit_at, counts, quote_counts) is not None:
                counts["priced"] += 1
        clocks.append(dict(hourNy=hour, pricedDays=counts["priced"], counts=dict(counts),
                           quoteCounts={s: dict(c) for s,c in quote_counts.items()}))
    return dict(admitted=all(row["pricedDays"] >= 5 for row in clocks), clocks=clocks)


def screen(request, account, ids, terms):
    halves = []
    for start_week in (0, 13):
        counts, quote_counts = Counter(), defaultdict(Counter)
        gross, central, adverse = defaultdict(list), defaultdict(list), defaultdict(list)
        coverage = Counter()
        for week in range(start_week, start_week+13):
            monday = START + timedelta(weeks=week)
            target, context = (bars_for_week(request,account,ids[s][0],monday) for s in (TARGET,CONTEXT))
            for name,bars in ((TARGET,target),(CONTEXT,context)):
                coverage[name] += len(bars)
            for weekday in range(5):
                day = monday + timedelta(days=weekday)
                for hour in HOURS:
                    if weekday == 2 and hour == 10:
                        continue
                    at = clock(day,time(hour),NY)
                    entry, exit_at = at+BAR, at+12*BAR
                    h4, h1 = (move(context,at-n*BAR,at) for n in (48,12))
                    own, last = (move(target,at-n*BAR,at) for n in (12,3))
                    label = move(target,entry,exit_at)
                    counts["scheduled"] += 1
                    if None in (h4,h1,own,last,label):
                        counts["missingBars"] += 1
                        continue
                    direction = sign(h1)
                    if direction == 0 or sign(h4) != direction or sign(own) != -direction:
                        continue
                    counts["signals"] += 1
                    sides = dict(model=direction,ownH1=sign(own),ownM15=sign(last),long=1,short=-1,cash=0)
                    gross[week].append({k:float(10_000*label*v) for k,v in sides.items()})
                    result = price_window(request,account,ids,terms,entry,exit_at,counts,quote_counts)
                    if result is None:
                        continue
                    counts["priced"] += 1
                    outcomes,_ = result
                    central[week].append({k:outcomes[v]-.5*abs(v) for k,v in sides.items()})
                    adverse[week].append({k:outcomes[v]-2*abs(v) for k,v in sides.items()})
        adv = summary(list(adverse.values()))
        covered = counts["priced"] >= 12 and len(adverse) >= 6 and 4*counts["priced"] >= 3*counts["signals"]
        passed = covered and all(adv["model"] > value for key,value in adv.items() if key != "model")
        halves.append(dict(counts=dict(counts), bars=dict(coverage), pricedWeeks=len(adverse),
                           coverageGate=covered, passed=passed,
                           quoteCounts={s:dict(c) for s,c in quote_counts.items()},
                           grossBps=summary(list(gross.values())), centralBps=summary(list(central.values())),
                           adverseBps=adv))
    verdict = "ADMIT_COMMON_REPLAY" if all(h["passed"] for h in halves) else (
        "REJECT_EXACT_RULE" if any(h["coverageGate"] and not h["passed"] for h in halves)
        else "INSUFFICIENT_COVERAGE")
    return dict(verdict=verdict, halves=halves)


def main():
    transport = StdlibCTraderTransport()
    calls = 0
    terms, margins = None,None
    try:
        account = authenticate(transport)

        def request(query, expected):
            nonlocal calls
            need(calls < 2250,"OIL_TRANSMISSION_REQUEST_BUDGET")
            require_read_only_request(query)
            response = transport.request(query)
            calls += 1
            if (expected is m.ProtoOAGetTickDataRes and type(response) is m.ProtoOAErrorRes
                    and response.errorCode == "NO_QUOTES" and response.ctidTraderAccountId == account):
                return expected(ctidTraderAccountId=account,hasMore=False)
            need(type(response) is expected and response.IsInitialized()
                 and response.ctidTraderAccountId == account,"OIL_TRANSMISSION_RESPONSE_BINDING")
            return response

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account), m.ProtoOASymbolsListRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes).trader
        currencies = {asset.assetId: asset.name for asset in assets.asset}
        need("pepperstone" in trader.brokerName.casefold() and currencies.get(trader.depositAssetId) == "EUR",
             "OIL_TRANSMISSION_PEPPERSTONE_EUR")
        available = {s.symbolName.casefold():s for s in roster.symbol if s.enabled}
        ids = {name:(available[name.casefold()].symbolId,
                     currencies.get(available[name.casefold()].quoteAssetId))
               for name in (TARGET,CONTEXT,FX) if name.casefold() in available}
        if TARGET in ids:
            sid,quote = ids[TARGET]
            details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[sid]),
                              m.ProtoOASymbolByIdRes)
            need(len(details.symbol)==1 and details.symbol[0].symbolId==sid,"OIL_TRANSMISSION_CONTRACT_SYMBOL")
            terms = details.symbol[0]
            if terms.HasField("tradingMode") and terms.tradingMode==0 and terms.minVolume>0:
                result = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,
                                 volume=[terms.minVolume]), m.ProtoOAExpectedMarginRes)
                if result.HasField("moneyDigits") and len(result.margin)==1 and result.margin[0].volume==terms.minVolume:
                    row = result.margin[0]
                    margins = [v/10**result.moneyDigits for v in (row.buyMargin,row.sellMargin)]
        source = preflight(request,account,ids,terms,margins)
        print(f"Oil preflight admitted: {source['admitted']}",flush=True)
        result = (screen(request,account,ids,terms) if source["admitted"]
                  else dict(verdict="SOURCE_GATE_NOT_MET",halves=[]))
    finally:
        transport.close()
    protocol = Path("research/brent_led_oil_transmission.md")
    receipt = dict(protocolSha256=sha256(protocol.read_bytes()).hexdigest(),
                   readOnlyRequestsAfterAuth=calls, currentMinimumMarginEurBuySell=margins,
                   currentTerms=contract(TARGET,terms,ids[TARGET][1],int(datetime.now(UTC).timestamp()*1000))
                   if terms else None,
                   source=source,predictive=result,fundedNetEur=None,independentConfirmation=False,
                   orders=0,cloudActivated=False)
    Path("brent-led-oil-transmission-public.json").write_text(json.dumps(receipt,indent=2,allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
