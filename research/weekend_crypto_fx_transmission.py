"""Read-only preregistered weekend crypto to Asia FX screening."""
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
import json
from math import comb
from pathlib import Path
from statistics import mean

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, need
from .economic_coverage_and_small_cap_open import paired, priced
from .guard import require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate
from .regional_equity_and_bond_transmission import BAR, clock, move, no_financing, session_ok, sign

TARGETS = ("AUDUSD", "NZDUSD")
CONTEXT = ("BTCUSD", "ETHUSD")
FX = "EURUSD"
MONDAYS = tuple(date(2025, 11, 17) + timedelta(weeks=i) for i in range(52))


def bars(request, account, sid, start, end):
    response = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=sid,
                       period=e.M5, fromTimestamp=start, toTimestamp=end), m.ProtoOAGetTrendbarsRes)
    need(response.period == e.M5 and not response.hasMore and
         (not response.HasField("symbolId") or response.symbolId == sid), "WEEKEND_BAR_RESPONSE")
    return {row[0]: row for row in decode_bars(response.trendbar, start, end, 5)}


def quote_window(request, account, ids, terms, day, counts, quotes, preflight=False):
    entry, exit_at = (clock(day,t,UTC) for t in (time(1,5),time(2,5)))
    if not all(session_ok(c,entry,exit_at) and no_financing(c,entry,exit_at) for c in terms.values()):
        counts["sessionOrFundingUnavailable"] += 1
        return None
    fx = [paired(request,account,ids[FX],at,quotes[FX]) for at in (entry,exit_at)]
    result = {}
    for symbol in TARGETS:
        opening, closing = (paired(request,account,ids[symbol],at,quotes[symbol])
                            for at in (entry,exit_at))
        if preflight:
            # Validate each endpoint independently, with no cross-clock return.
            result[symbol] = all(priced(terms[symbol],"USD",q,q,[rate,rate],counts) is not None
                                 for q,rate in zip((opening,closing),fx))
        else:
            result[symbol] = priced(terms[symbol],"USD",opening,closing,fx,counts)
    if not all(result.values()):
        counts["incompleteJointQuoteWeek"] += 1
        return None
    return result


def positive_sign_p(values):
    wins = sum(v > 0 for v in values)
    trials = wins + sum(v < 0 for v in values)
    return sum(comb(trials,k) for k in range(wins,trials+1)) / 2**trials


def aggregate(rows):
    return {key:mean(r[key] for r in rows) for key in rows[0]} if rows else {}


def screen(request, account, ids, terms):
    halves = []
    for half in (MONDAYS[:26],MONDAYS[26:]):
        counts, quotes = Counter(), defaultdict(Counter)
        gross, central, adverse = [], [], []
        by_leg = defaultdict(list)
        for day in half:
            counts["scheduled"] += 1
            start = clock(day-timedelta(days=2),time(4),UTC)
            end = clock(day-timedelta(days=1),time(16),UTC)
            context = []
            for name in CONTEXT:
                a = bars(request,account,ids[name],start,start+BAR).get(start)
                b = bars(request,account,ids[name],end-BAR,end).get(end-BAR)
                if a is not None and b is not None:
                    context.append(sign(b[5]-a[2]))
            if len(context) != 2:
                counts["missingCryptoEndpoints"] += 1
                continue
            direction = context[0]
            if not direction or direction != context[1]:
                counts["cryptoNotAligned"] += 1
                continue
            at = clock(day,time(1),UTC)
            entry, exit_at = at+BAR, at+13*BAR
            states = {}
            for name in TARGETS:
                fx_bars = bars(request,account,ids[name],at-12*BAR,exit_at)
                own = move(fx_bars,at-12*BAR,at)
                label = move(fx_bars,entry,exit_at)
                if own is not None and label is not None:
                    states[name] = (dict(model=direction,ownFx=sign(own),long=1,short=-1,cash=0),label)
            if len(states) != len(TARGETS):
                counts["missingFxBarPath"] += 1
                continue
            counts["signals"] += 1
            gross.append(aggregate([{k:float(label*10_000*side) for k,side in sides.items()}
                                    for sides,label in states.values()]))
            valued = quote_window(request,account,ids,terms,day,counts,quotes)
            if valued is None:
                continue
            counts["priced"] += 1
            central_legs, adverse_legs = [], []
            for name,(sides,_) in states.items():
                outcomes,_ = valued[name]
                central_legs.append({k:outcomes[v]-.5*abs(v) for k,v in sides.items()})
                adverse_legs.append({k:outcomes[v]-2*abs(v) for k,v in sides.items()})
                by_leg[name].append(adverse_legs[-1])
            central.append(aggregate(central_legs))
            adverse.append(aggregate(adverse_legs))
        adv = aggregate(adverse)
        covered = counts["priced"] >= 12 and 4*counts["priced"] >= 3*counts["signals"]
        sign_p = {key:positive_sign_p([row["model"]-row[key] for row in adverse])
                  for key in ("cash","ownFx")} if adverse else {}
        passed = (covered and all(adv["model"] > v for key,v in adv.items() if key != "model")
                  and all(p <= .10 for p in sign_p.values()))
        halves.append(dict(counts=dict(counts), quoteCounts={s:dict(c) for s,c in quotes.items()},
                           grossBps=aggregate(gross), centralBps=aggregate(central), adverseBps=adv,
                           perLegAdverseBps={s:aggregate(rows) for s,rows in by_leg.items()},
                           positiveSignP=sign_p, coverageGate=covered, passed=passed))
    verdict = "ADMIT_COMMON_REPLAY" if all(h["passed"] for h in halves) else (
        "REJECT_EXACT_RULE" if any(h["coverageGate"] and not h["passed"] for h in halves)
        else "INSUFFICIENT_COVERAGE")
    return dict(verdict=verdict, halves=halves)


def main():
    transport = StdlibCTraderTransport()
    calls = 0
    terms, margins, snapshot = {}, {}, {}
    try:
        account = authenticate(transport)

        def request(query, expected):
            nonlocal calls
            need(calls < 1200,"WEEKEND_REQUEST_BUDGET")
            require_read_only_request(query)
            response = transport.request(query)
            calls += 1
            if (expected is m.ProtoOAGetTickDataRes and type(response) is m.ProtoOAErrorRes
                    and response.errorCode == "NO_QUOTES" and response.ctidTraderAccountId == account):
                return expected(ctidTraderAccountId=account,hasMore=False)
            need(type(response) is expected and response.IsInitialized()
                 and response.ctidTraderAccountId == account,"WEEKEND_RESPONSE_BINDING")
            return response

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account), m.ProtoOASymbolsListRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes).trader
        currencies = {asset.assetId:asset.name for asset in assets.asset}
        need("pepperstone" in trader.brokerName.casefold() and currencies.get(trader.depositAssetId) == "EUR",
             "WEEKEND_PEPPERSTONE_EUR")
        available = {s.symbolName.casefold():s for s in roster.symbol if s.enabled
                     and currencies.get(s.quoteAssetId)=="USD"}
        names = (*TARGETS,*CONTEXT,FX)
        ids = {name:available[name.casefold()].symbolId for name in names if name.casefold() in available}
        for name in TARGETS:
            if name not in ids:
                continue
            sid = ids[name]
            details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[sid]),
                              m.ProtoOASymbolByIdRes)
            need(len(details.symbol)==1 and details.symbol[0].symbolId==sid,"WEEKEND_CONTRACT_SYMBOL")
            c = details.symbol[0]
            if (not c.HasField("tradingMode") or c.tradingMode != 0 or not c.HasField("enableShortSelling")
                    or not c.enableShortSelling or c.minVolume <= 0):
                continue
            terms[name] = c
            snapshot[name] = contract(name,c,"USD",int(datetime.now(UTC).timestamp()*1000))
            result = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,
                             volume=[c.minVolume]), m.ProtoOAExpectedMarginRes)
            if result.HasField("moneyDigits") and len(result.margin)==1 and result.margin[0].volume==c.minVolume:
                row = result.margin[0]
                margins[name] = [v/10**result.moneyDigits for v in (row.buyMargin,row.sellMargin)]
        counts, quotes = Counter(), defaultdict(Counter)
        preflight = (len(ids)==len(names) and len(margins)==len(TARGETS)
                     and all(min(pair)>0 for pair in margins.values())
                     and sum(max(pair) for pair in margins.values())<=300)
        if preflight:
            for day in MONDAYS[-5:]:
                if quote_window(request,account,ids,terms,day,counts,quotes,preflight=True):
                    counts["priced"] += 1
        admitted = preflight and counts["priced"]>=4
        print(f"Weekend FX source gate: {admitted}",flush=True)
        predictive = (screen(request,account,ids,terms) if admitted
                      else dict(verdict="SOURCE_GATE_NOT_MET",halves=[]))
    finally:
        transport.close()
    protocol = Path("research/weekend_crypto_fx_transmission.md")
    receipt = dict(protocolSha256=sha256(protocol.read_bytes()).hexdigest(),
                   readOnlyRequestsAfterAuth=calls, missingEnabledSymbols=sorted(set(names)-ids.keys()),
                   currentTerms=snapshot, currentMinimumMarginEurBuySell=margins,
                   source=dict(admitted=admitted,counts=dict(counts),quoteCounts={s:dict(c) for s,c in quotes.items()}),
                   predictive=predictive, fundedNetEur=None, independentConfirmation=False,
                   orders=0, cloudActivated=False)
    Path("weekend-crypto-fx-transmission-public.json").write_text(json.dumps(receipt,indent=2,allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
