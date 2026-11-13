"""RNE1 EIA weekly gas-storage information arrival, original Pepperstone evidence.

Only scheduled public release vs Tuesday placebo; no old closed studies
replayed. Broker ticks are for executable-side quote-crossing, NOT prediction.
Source capture is RSA sealed before any economic outcome scoring.
"""
from __future__ import annotations
import base64
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from math import log
import os
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, decode_side
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody_new import checked_public
from .custody import seal_new

NY = ZoneInfo("America/New_York")
START = date(2026, 5, 4)
WEEKS = 26
TARGETS = ("NatGas", "EQT.US")
RELEASE = "THURSDAY_OFFICIAL_EIA_SCHEDULE"
PLACEBO = "TUESDAY_NON_EIA"
MAX_REQUESTS = 1200
AGE_MS = 20000
M5_MS = 300000


def stamp(day, hh, mm):
    return int(datetime.combine(day, time(hh, mm), NY).timestamp() * 1000)


def sign(value):
    return (value > 0) - (value < 0)


def at_quote(rows, at, age=AGE_MS):
    if not rows:
        return None
    idx = bisect_right([r[0] for r in rows], at) - 1
    if idx < 0 or not 0 <= at - rows[idx][0] <= age:
        return None
    return rows[idx][1]


def paired(bids, asks, at):
    b, a = at_quote(bids, at), at_quote(asks, at)
    return [b, a] if b is not None and a is not None and 0 < b <= a else None


def closed_price(bars, at):
    return bars.get(at)


def bps(bars, start, end):
    # M5 continuity at EVERY intervening close, not just endpoint.
    if any(t not in bars for t in range(start, end + M5_MS, M5_MS)):
        return None
    if bars[start] <= 0 or bars[end] <= 0:
        return None
    return 10000 * log(bars[end] / bars[start])


def event_decision(day, gas):
    base = stamp(day, 9, 30)
    published = stamp(day, 10, 30)
    decided = stamp(day, 10, 45)
    prior = [bps(gas, base + 15*60000*i,
                 base + 15*60000*(i+1)) for i in range(4)]
    shock = bps(gas, published, decided)
    if shock is None or any(x is None for x in prior):
        return {"state": "MISSING_COMPLETED_M5_FEATURES"}
    ambient = max(abs(x) for x in prior)
    if abs(shock) <= ambient or shock == 0:
        return {"state": "NO_EVENT_ANOMALY", "shockGrossBps": shock,
                "ambientMax15mBps": ambient}
    post = bps(gas, decided, stamp(day,11,15))
    if post is None:
        return {"state": "EVENT_MISSING_POST_DECISION_MONITOR",
                "shockGrossBps": shock, "ambientMax15mBps": ambient}
    direction = sign(shock)
    reversal = (post * direction < 0)
    return {"state": "RELEASE_SHOCK_CANDIDATE", "side": direction,
            "shockGrossBps": shock, "ambientMax15mBps": ambient,
            "post30mGrossBps": post, "invalidatedAt1115": reversal,
            "exitAt": "11:20" if reversal else "12:05"}


def markout(entry, exit_quote, side):
    m = (entry[0]+entry[1])/2
    delta = ((exit_quote[0]+exit_quote[1])/2-m) / m * 10000
    if side == 0:
        return [0.0,0.0]
    crossed_in = entry[1] if side > 0 else entry[0]
    crossed_out = exit_quote[0] if side > 0 else exit_quote[1]
    return [side*delta, side*(crossed_out-crossed_in)/m*10000]


def score_one(event, target):
    kind, gas, rows, quote = event["kind"], event["gasBars"], target["bars"], target["quote"]
    decision = event_decision(event["day"], gas)
    if decision["state"] != "RELEASE_SHOCK_CANDIDATE":
        return {"state": decision["state"], "kind": kind, "week": event["week"],
                "shockBps": decision.get("shockGrossBps")}
    side = decision["side"]
    first = stamp(event["day"],10,50)
    needed = stamp(event["day"],11,20) if decision["invalidatedAt1115"] else stamp(event["day"],12,5)
    entry = quote.get("10:50")
    exit_quote = quote.get(decision["exitAt"])
    fixed = quote.get("12:05")
    if entry is None:
        return {"state":"MISSING_ENTRY_QUOTE","kind":kind,"week":event["week"]}
    if exit_quote is None:
        return {"state":"MISSING_EXIT_QUOTE","kind":kind,"week":event["week"]}
    own = bps(rows,stamp(event["day"],10,15),stamp(event["day"],10,45))
    if own is None:
        return {"state":"MISSING_TARGET_OWN_MOMENTUM","kind":kind,"week":event["week"]}
    policy = markout(entry, exit_quote, side)
    result = {"state":"ADAPTIVE_PRICED","kind":kind,"week":event["week"],
              "side":side,"exitAt":decision["exitAt"],
              "eventShockBps":decision["shockGrossBps"],
              "preReleaseAmbientMax15mBps":decision["ambientMax15mBps"],
              "postDecisionGasMovementBps":decision["post30mGrossBps"],
              "markoutAdaptive":policy, "fixedQuoteAvailable":fixed is not None}
    if fixed is not None:
        peers = {"eia":side,"gasSameSideFixed":side,
                 "ownMomentum":sign(own),"long":1,"short":-1,"cash":0}
        result["paired"] = {k:markout(entry,
              exit_quote if k=="eia" else fixed, v) for k,v in peers.items()}
    return result


def avg(rows, field, which):
    v = [r[field][which] for r in rows if field in r]
    return mean(v) if v else None


def priced_summary(rows):
    adaptive = [r for r in rows if r["state"]=="ADAPTIVE_PRICED"]
    paired = [r for r in adaptive if "paired" in r]
    names = ("eia","gasSameSideFixed","ownMomentum","long","short","cash")
    return {
        "decisionCounts":dict(Counter(r["state"] for r in rows)),
        "shockSignals":sum(r["state"] in ("ADAPTIVE_PRICED",
                       "MISSING_ENTRY_QUOTE","MISSING_EXIT_QUOTE",
                       "MISSING_TARGET_OWN_MOMENTUM") for r in rows),
        "adaptivePriced":len(adaptive),
        "pairedPriced":len(paired),
        "activeWeeks":len({r["week"] for r in paired}),
        "adaptiveGrossBpsMean":avg(adaptive,"markoutAdaptive",0),
        "adaptiveCrossingBeforeFeeBpsMean":avg(adaptive,"markoutAdaptive",1),
        "pairedGrossBps": {s:mean(r["paired"][s][0] for r in paired)
                             if paired else None for s in names},
        "pairedCrossingBeforeFeeBps":{s:mean(r["paired"][s][1] for r in paired)
                             if paired else None for s in names},
        "grossIncrementVsOwn":mean(r["paired"]["eia"][0]-
                r["paired"]["ownMomentum"][0] for r in paired) if paired else None,
        "exitReasons": dict(Counter(r["exitAt"] for r in adaptive)),
    }


def evaluate(tape, statuses):
    result = {}
    # One NatGas decision per scheduled release/control, regardless of
    # which target's execution quote happens to be complete.
    events = []
    for week in range(WEEKS):
        monday = START + timedelta(weeks=week)
        for wd,kind in ((1,PLACEBO),(3,RELEASE)):
            day=monday+timedelta(days=wd)
            key=day.isoformat()
            gas=tape.get("NatGas",{}).get(key)
            if gas is None or gas["truncated"]:
                events.append({"kind":kind,"week":week,"day":day,
                               "missingGas":"NO_ORIGINAL_COMPLETE_GAS_SOURCE"})
                continue
            bars=gas["bars"]
            events.append({"kind":kind,"week":week,"day":day,"gasBars":bars,
                           "decision":event_decision(day,bars)})
    for name in TARGETS:
        info={"brokerStatus":statuses.get(name,"UNAVAILABLE"),"scheduled":WEEKS*2}
        if name not in tape:
            info["evaluated"]=False
            result[name]=info
            continue
        rows=[]
        for event in events:
            kind,week,day=event["kind"],event["week"],event["day"]
            if "missingGas" in event:
                rows.append({"state":"MISSING_GAS_SOURCE","kind":kind,"week":week})
                continue
            target=tape[name].get(day.isoformat())
            if target is None or target["truncated"]:
                rows.append({"state":"MISSING_TARGET_SOURCE","kind":kind,"week":week})
                continue
            rows.append(score_one(event,target))
        info["evaluated"]=True
        info["release"]=priced_summary([x for x in rows if x["kind"]==RELEASE])
        info["placebo"]=priced_summary([x for x in rows if x["kind"]==PLACEBO])
        info["releaseFirst13Weeks"]=priced_summary([x for x in rows
                       if x["kind"]==RELEASE and x["week"]<13])
        info["releaseLast13Weeks"]=priced_summary([x for x in rows
                       if x["kind"]==RELEASE and x["week"]>=13])
        result[name]=info
    return result


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    t=StdlibCTraderTransport()
    records=[]
    tape={s:{} for s in TARGETS}
    statuses={}
    requests=0

    def request(q,klass,allow_no_quotes=False):
        nonlocal requests
        if requests>=MAX_REQUESTS:raise RuntimeError("RNE1_READONLY_REQUEST_BUDGET")
        require_read_only_request(q)
        response=t.request(q)
        requests+=1
        if (allow_no_quotes and type(response) is m.ProtoOAErrorRes and
            response.errorCode=="NO_QUOTES" and response.ctidTraderAccountId==account):
            r=None
        elif (type(response) is klass and response.IsInitialized() and
              response.ctidTraderAccountId==account):
            r=response
        else:
            raise RuntimeError("RNE1_ACCOUNT_OR_MESSAGE_MISMATCH")
        records.append({"requestType":type(q).__name__,
            "request":base64.b64encode(q.SerializeToString()).decode(),
            "responseType":type(response).__name__,
            "response":base64.b64encode(response.SerializeToString()).decode()})
        return r

    try:
        account=authenticate(t)
        trader=request(m.ProtoOATraderReq(ctidTraderAccountId=account),
                       m.ProtoOATraderRes)
        assets=request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                       m.ProtoOAAssetListRes)
        currencies={a.assetId:a.name for a in assets.asset}
        if ("pepperstone" not in trader.trader.brokerName.casefold()
            or currencies.get(trader.trader.depositAssetId)!="EUR"):
            raise RuntimeError("RNE1_NOT_ORIGINAL_PEPPERSTONE_EUR_ACCOUNT")
        roster=request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                       includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        live={s.symbolName:s for s in roster.symbol if s.enabled}
        if "NatGas" not in live:
            raise RuntimeError("RNE1_MANDATORY_NATGAS_ABSENT")
        for name in TARGETS:
            light=live.get(name)
            if light is None:
                statuses[name]="EXACT_SYMBOL_UNAVAILABLE_NO_SUBSTITUTION"
                tape.pop(name,None)
                continue
            detail=request(m.ProtoOASymbolByIdReq(
                       ctidTraderAccountId=account,symbolId=[light.symbolId]),
                       m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=light.symbolId:
                raise RuntimeError("RNE1_CONTRACT_IDENTITY")
            contract=detail.symbol[0]
            status={"enabledOriginalAccount":True,
                "currentTradingMode":int(contract.tradingMode),
                "currentMinVolume":int(contract.minVolume),
                "currentStepVolume":int(contract.stepVolume),
                "quoteCurrency":currencies.get(light.quoteAssetId),
                "currentMarginBuyEur":None,"currentMarginSellEur":None,
                "historicalTradingEligibilityCertified":False}
            if contract.minVolume>0:
                margin=request(m.ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account,symbolId=light.symbolId,
                    volume=[contract.minVolume]),m.ProtoOAExpectedMarginRes)
                if margin.HasField("moneyDigits") and len(margin.margin)==1:
                    mr=margin.margin[0]
                    if mr.volume==contract.minVolume:
                        status["currentMarginBuyEur"]=mr.buyMargin/(10**margin.moneyDigits)
                        status["currentMarginSellEur"]=mr.sellMargin/(10**margin.moneyDigits)
            statuses[name]=status
            for week in range(WEEKS):
                monday=START+timedelta(weeks=week)
                for wd in (1,3):
                    day=monday+timedelta(days=wd)
                    lo,hi=stamp(day,9,25),stamp(day,12,10)
                    barresponse=request(m.ProtoOAGetTrendbarsReq(
                        ctidTraderAccountId=account,symbolId=light.symbolId,
                        period=e.M5,fromTimestamp=lo,toTimestamp=hi),
                        m.ProtoOAGetTrendbarsRes,True)
                    truncated=(barresponse is None or barresponse.hasMore)
                    bars={}
                    if not truncated:
                        if barresponse.period!=e.M5 or (barresponse.HasField("symbolId") and
                            barresponse.symbolId!=light.symbolId):
                            raise RuntimeError("RNE1_BAR_RESPONSE_MISMATCH")
                        bars={closed:close for _,closed,_,_,_,close,_ in decode_bars(
                            barresponse.trendbar,lo-2*M5_MS,hi+2*M5_MS,5)}
                    quote={}
                    for label,hh,minute in (("10:50",10,50),("11:20",11,20),("12:05",12,5)):
                        moment=stamp(day,hh,minute)
                        sides=[]
                        for side in (e.BID,e.ASK):
                            tick=request(m.ProtoOAGetTickDataReq(
                                ctidTraderAccountId=account,symbolId=light.symbolId,
                                type=side,fromTimestamp=moment-25000,toTimestamp=moment),
                                m.ProtoOAGetTickDataRes,True)
                            if tick is None:
                                sides.append([])
                            elif tick.hasMore:
                                truncated=True
                                sides.append([])
                            else:
                                sides.append(decode_side(tick.tickData,moment-25000,moment))
                        quote[label]=paired(*sides,moment)
                    tape[name][day.isoformat()]={"bars":bars,
                         "quote":quote,"truncated":truncated}
    finally:
        t.close()

    # All authenticated broker request/response bytes and decoded source are
    # sealed FIRST, before any outcome scoring.
    payload=json.dumps({"schema":"MXM_ORIGINAL_RNE1_SOURCE_PRIVATE",
        "originalAccountVerified":True,"run":run,"requests":records,
        "source":tape,"currentContract":statuses},
        sort_keys=True,separators=(",",":")).encode()
    ciphertext=seal_new(payload,recipient,run)
    Path("rne1-eia-protected-original.v2.enc").write_bytes(ciphertext)

    result=evaluate(tape,statuses)
    out={"schema":"MXM_RNE1_EIA_FUNDAMENTAL_ANNOUNCEMENT_GROSS_SCREEN",
        "protocolSha256":sha256(Path("research/RNE1_EIA_GAS_RELEASE.md").read_bytes()).hexdigest(),
        "originalRun":int(run),"originalRequestsAfterAuth":requests,
        "sealedSourceSha256":sha256(ciphertext).hexdigest(),
        "sourcePlainSha256":sha256(payload).hexdigest(),
        "originalPepperstoneEurAccountVerified":True,
        "officialEiaScheduleUrl":"https://ir.eia.gov/ngs/schedule.html",
        "notAsPublishedEiaData":True,
        "calendarReleaseTimestampHistoricalContinuityCertified":False,
        "targets":result,
        "brokerOrders":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,"fundedTrades":0,
        "fundedNetEur":None,"independentConfirmation":False,
        "all2026CalendarExposed":True,
        "disclosure":"Scheduled EIA release is a causal external event; measured post-release NatGas reaction, not observed inventory surprise. Hypothetical sampled BID/ASK quote markouts before commission/slippage/FX are NOT EUR NET or actual fills. Tuesday is a placebo, not an execution rule."}
    Path("rne1-eia-public.json").write_text(json.dumps(out,indent=2,allow_nan=False)+"\n")
    print("RNE1_GENUINE_EIA_EVENT_ECONOMICS",
        json.dumps({"requests":requests,
                    "markets":{k:v.get("brokerStatus") for k,v in result.items()},
                    "release":{k:(v.get("release") or {}).get("decisionCounts")
                               for k,v in result.items()}}),flush=True)


if __name__=="__main__":
    main()
