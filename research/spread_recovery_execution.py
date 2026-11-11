"""Matched read-only quote replay for spread-conditioned entry timing."""
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import UTC, datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_side, need
from .guard import require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate
from .regional_equity_and_bond_transmission import START, clock, session_ok, summary

NY = ZoneInfo("America/New_York")
ROUTES = {"AUDUSD": (time(8,5),UTC), "US2000": (time(9,35),NY), "SpotCrude": (time(10,5),NY)}
BEFORE = (-90,-60,-30)
AFTER = (30,60,90)
STRESS_BPS = .25


def quote_window(request, account, sid, at, counts):
    start, stop = at-110_000,at+90_000
    sides = []
    for side in (e.BID,e.ASK):
        response = request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                           symbolId=sid,type=side,fromTimestamp=start,toTimestamp=stop),
                           m.ProtoOAGetTickDataRes)
        if response.hasMore:
            counts["truncatedQuoteWindow"] += 1
            return {}
        rows = decode_side(response.tickData,start,stop)
        sides.append(([row[0] for row in rows],[row[1] for row in rows]))
    marks = {}
    for seconds in (*BEFORE,0,*AFTER):
        stamp = at+seconds*1000
        pair = []
        for times,prices in sides:
            index = bisect_right(times,stamp)-1
            if index >= 0 and stamp-times[index] <= 20_000:
                pair.append(prices[index])
        if len(pair)==2 and 0<pair[0]<=pair[1]:
            marks[seconds] = tuple(pair)
    return marks


def spread(pair):
    return pair[1]-pair[0]


def compare(marks):
    """Return the causal delay and signed matched entry improvements."""
    base = median(spread(marks[seconds]) for seconds in BEFORE)
    delay = next((seconds for seconds in AFTER[:-1] if spread(marks[seconds])<=base),AFTER[-1])
    now, adaptive, fixed = marks[0],marks[delay],marks[AFTER[-1]]
    scale = 20_000/sum(now)
    half_spread = (spread(now)-spread(adaptive))*scale/2
    mid_buy = (sum(now)-sum(adaptive))*scale/2
    return delay,dict(buyVsImmediate=(now[1]-adaptive[1])*scale,
                      sellVsImmediate=(adaptive[0]-now[0])*scale,
                      buyVsFixed=(fixed[1]-adaptive[1])*scale,
                      sellVsFixed=(adaptive[0]-fixed[0])*scale,
                      buyMidpointVsImmediate=mid_buy,sellMidpointVsImmediate=-mid_buy,
                      halfSpreadImprovementVsImmediate=half_spread)


def score(request, account, sid, symbol, terms):
    halves = []
    local_time,zone = ROUTES[symbol]
    for first_week in (0,13):
        counts, delays = Counter(),Counter()
        results = defaultdict(list)
        for week in range(first_week,first_week+13):
            monday = START+timedelta(weeks=week)
            for weekday in range(5):
                counts["scheduled"] += 1
                at = clock(monday+timedelta(days=weekday),local_time,zone)
                if not session_ok(terms,at-110_000,at+90_000):
                    counts["sessionUnavailable"] += 1
                    continue
                marks = quote_window(request,account,sid,at,counts)
                if not all(seconds in marks for seconds in (*BEFORE,0)):
                    counts["missingBaseline"] += 1
                    continue
                counts["baselineComplete"] += 1
                if spread(marks[0])<=max(spread(marks[seconds]) for seconds in BEFORE):
                    continue
                counts["selected"] += 1
                if not all(seconds in marks for seconds in AFTER):
                    counts["missingAfterSelection"] += 1
                    continue
                counts["compared"] += 1
                delay,row = compare(marks)
                delays[delay] += 1
                results[week].append(row)
        means = summary(list(results.values()))
        adverse = {key:means[key]-STRESS_BPS for key in
                   ("buyVsImmediate","sellVsImmediate","buyVsFixed","sellVsFixed")} if means else {}
        covered = (counts["compared"]>=12 and len(results)>=8
                   and 10*counts["compared"]>=9*counts["selected"])
        passed = covered and all(value>0 for value in adverse.values())
        halves.append(dict(counts=dict(counts),activeWeeks=len(results),adaptiveDelaysSeconds=dict(delays),
                           improvementsBps=means,adverseImprovementsBps=adverse,
                           coverageGate=covered,passed=passed))
    verdict = "SUPPORTS_EXECUTION_FOLLOWUP" if all(h["passed"] for h in halves) else (
        "REJECT_EXECUTION_RULE" if any(h["coverageGate"] and not h["passed"] for h in halves)
        else "INSUFFICIENT_COMPARABLE_EVENTS")
    return dict(verdict=verdict,halves=halves)


def eligible(terms, margins):
    fields = ("tradingMode","commissionType","minCommissionType","minCommissionAsset",
              "preciseTradingCommissionRate","preciseMinCommission","enableShortSelling",
              "minVolume","stepVolume","maxVolume","lotSize")
    return (all(terms.HasField(field) for field in fields)
            and terms.tradingMode==0 and terms.enableShortSelling and terms.commissionType==2
            and terms.minCommissionType==1 and terms.minCommissionAsset=="USD"
            and min(terms.preciseTradingCommissionRate,terms.preciseMinCommission)>=0
            and terms.maxVolume>=terms.minVolume>0 and min(terms.stepVolume,terms.lotSize)>0
            and margins is not None and 0<min(margins)<=max(margins)<=300)


def main():
    transport = StdlibCTraderTransport()
    calls = 0
    results = {}
    try:
        account = authenticate(transport)

        def request(query, expected):
            nonlocal calls
            need(calls<900,"SPREAD_RECOVERY_REQUEST_BUDGET")
            require_read_only_request(query)
            response = transport.request(query)
            calls += 1
            if (expected is m.ProtoOAGetTickDataRes and type(response) is m.ProtoOAErrorRes
                    and response.errorCode=="NO_QUOTES" and response.ctidTraderAccountId==account):
                return expected(ctidTraderAccountId=account,hasMore=False)
            need(type(response) is expected and response.IsInitialized()
                 and response.ctidTraderAccountId==account,"SPREAD_RECOVERY_RESPONSE_BINDING")
            return response

        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes).trader
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        currencies = {asset.assetId:asset.name for asset in assets.asset}
        need("pepperstone" in trader.brokerName.casefold() and currencies.get(trader.depositAssetId)=="EUR",
             "SPREAD_RECOVERY_PEPPERSTONE_EUR")
        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account),m.ProtoOASymbolsListRes)
        ids = {s.symbolName.casefold():s.symbolId for s in roster.symbol
               if s.enabled and currencies.get(s.quoteAssetId)=="USD"}
        for symbol in ROUTES:
            sid = ids.get(symbol.casefold())
            if sid is None:
                results[symbol] = dict(verdict="MISSING_ENABLED_USD_SYMBOL")
                continue
            response = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[sid]),
                               m.ProtoOASymbolByIdRes)
            need(len(response.symbol)==1 and response.symbol[0].symbolId==sid,"SPREAD_RECOVERY_CONTRACT")
            terms = response.symbol[0]
            observed = int(datetime.now(UTC).timestamp()*1000)
            margins = None
            if terms.minVolume>0 and terms.tradingMode==0:
                reply = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,
                                volume=[terms.minVolume]),m.ProtoOAExpectedMarginRes)
                if reply.HasField("moneyDigits") and len(reply.margin)==1 and reply.margin[0].volume==terms.minVolume:
                    row = reply.margin[0]
                    margins = [v/10**reply.moneyDigits for v in (row.buyMargin,row.sellMargin)]
            row = (score(request,account,sid,symbol,terms) if eligible(terms,margins)
                   else dict(verdict="UNVERIFIED_FEE_OR_MARGIN"))
            results[symbol] = dict(row,currentTerms=contract(symbol,terms,"USD",observed),
                                   currentMinimumMarginEurBuySell=margins)
            print(f"{symbol}: {row['verdict']}",flush=True)
    finally:
        transport.close()
    protocol = Path("research/spread_recovery_execution.md")
    receipt = dict(protocolSha256=sha256(protocol.read_bytes()).hexdigest(),
                   readOnlyRequestsAfterAuth=calls,results=results,fundedNetEur=None,
                   independentConfirmation=False,orders=0,cloudActivated=False)
    Path("spread-recovery-execution-public.json").write_text(json.dumps(receipt,indent=2,allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
