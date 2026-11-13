"""RNE1-EUR original-account 5-minute historical EURUSD / NatGas BID ASK.

Extension of frozen RNE1 source: NO changes to decision, entry or exit.
Exactly 26 prelisted Thursday panels; original protobuf sealed before
any financial scoring; no ORDER, LIVE/DEMO execution or OAuth refresh.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import date,timedelta,datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_side
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody_new import checked_public
from .custody import seal_new
from .native_original_openapi_product_replay import contract
from .rne1_eia_gas_release import START,WEEKS,stamp

SYMBOLS=("NatGas","EURUSD")
SAMPLES=tuple((hh,mm) for hh,mm in
              ((10,50),(10,55),(11,0),(11,5),(11,10),(11,15),
               (11,20),(11,25),(11,30),(11,35),(11,40),
               (11,45),(11,50),(11,55),(12,0),(12,5)))
MAX_REQUESTS=2100
MAX_AGE=20000
QUERY_LOOKBACK=60000


def sampled_side(rows,t):
    prior=[r for r in rows if r[0]<=t]
    if not prior:
        return None
    at,price=prior[-1]
    if price<=0 or t-at>MAX_AGE:
        return None
    return {"at":at,"raw":price,"ageMs":t-at}


def sampled_pair(bids,asks,t):
    b,a=sampled_side(bids,t),sampled_side(asks,t)
    if b is None or a is None:
        return None
    if b["raw"]>a["raw"]:
        return None
    return {"bid":b,"ask":a}


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    t=StdlibCTraderTransport()
    calls=[]
    requests=0
    tape={}
    statuses={}
    ids={}

    def req(q,klass,empty_ok=False):
        nonlocal requests
        if requests>=MAX_REQUESTS:
            raise RuntimeError("RNE1_EUR_ORIGINAL_BROKER_CALL_CEILING")
        require_read_only_request(q)
        reply=t.request(q)
        requests+=1
        if (empty_ok and type(reply) is m.ProtoOAErrorRes and
            reply.errorCode=="NO_QUOTES" and reply.ctidTraderAccountId==account):
            result=None
        elif (type(reply) is klass and reply.IsInitialized() and
              reply.ctidTraderAccountId==account):
            result=reply
        else:
            raise RuntimeError("RNE1_EUR_ORIGINAL_IDENTITY_OR_RESPONSE_MISMATCH")
        calls.append({
            "requestType":type(q).__name__,
            "request":base64.b64encode(q.SerializeToString()).decode(),
            "responseType":type(reply).__name__,
            "response":base64.b64encode(reply.SerializeToString()).decode(),
        })
        return result

    try:
        account=authenticate(t)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        currency={a.assetId:a.name for a in assets.asset}
        if ("pepperstone" not in trader.trader.brokerName.casefold()
            or currency.get(trader.trader.depositAssetId)!="EUR"):
            raise RuntimeError("RNE1_EUR_NOT_ORIGINAL_PEPPERSTONE_EUR")
        roster=req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        available={x.symbolName:x for x in roster.symbol if x.enabled}
        if not all(s in available for s in SYMBOLS):
            raise RuntimeError("RNE1_EUR_FROZEN_TWO_SYMBOL_ROSTER_UNAVAILABLE")
        for symbol in SYMBOLS:
            item=available[symbol]
            ids[symbol]=item.symbolId
            if currency.get(item.quoteAssetId)!="USD":
                raise RuntimeError("RNE1_EUR_QUOTE_ASSET_NOT_USD")
            detail=req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[item.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=item.symbolId:
                raise RuntimeError("RNE1_EUR_CURRENT_CONTRACT_IDENTITY_MISMATCH")
            c=detail.symbol[0]
            statuses[symbol]={"currentContract":contract(symbol,c,"USD",int(datetime.now(timezone.utc).timestamp()*1000)),
               "originalAccountAuthenticated":True,
               "historicalTradingEligibilityCertified":False,
               "currentMarginEur":None}
            if c.minVolume>0:
                mr=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                    symbolId=item.symbolId,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
                if mr.HasField("moneyDigits") and len(mr.margin)==1 and mr.margin[0].volume==c.minVolume:
                    statuses[symbol]["currentMarginEur"]={
                        "buy":mr.margin[0].buyMargin/10**mr.moneyDigits,
                        "sell":mr.margin[0].sellMargin/10**mr.moneyDigits}
        panel=Counter()
        for week in range(WEEKS):
            day=START+timedelta(weeks=week,days=3)
            d=day.isoformat()
            tape[d]={"week":week,"symbols":{}}
            for symbol in SYMBOLS:
                record={}
                for hh,mm in SAMPLES:
                    at=stamp(day,hh,mm)
                    sides=[]
                    truncated=False
                    for side in (e.BID,e.ASK):
                        reply=req(m.ProtoOAGetTickDataReq(
                            ctidTraderAccountId=account,symbolId=ids[symbol],
                            type=side,fromTimestamp=at-QUERY_LOOKBACK,
                            toTimestamp=at),m.ProtoOAGetTickDataRes,True)
                        if reply is None:
                            rows=[]
                        elif reply.hasMore:
                            truncated=True
                            rows=[]
                        else:
                            rows=decode_side(reply.tickData,at-QUERY_LOOKBACK,at)
                        sides.append(rows)
                    q=None if truncated else sampled_pair(*sides,at)
                    if truncated:
                        panel["TRUNCATED_"+symbol]+=1
                    elif q is None:
                        panel["MISSING_OR_STALE_"+symbol]+=1
                    else:
                        panel["FRESH_PAIR_"+symbol]+=1
                    record[str(at)]={"clock":at,"pair":q,
                        "truncated":truncated}
                tape[d]["symbols"][symbol]=record
            # Avoid account-identifying, broker-price, or symbol ID logging.
            if week%4==3:
                print("RNE1_EUR_READONLY_WEEK_PROGRESS",week+1,
                      "OF",WEEKS,"REQUESTS",requests,flush=True)
    finally:
        t.close()
    if requests>MAX_REQUESTS:
        raise RuntimeError("RNE1_EUR_BROKER_CALL_HARD_LIMIT")
    source=json.dumps({
        "schema":"MXM_RNE1_EUR_ORIGINAL_HISTORICAL_DENSE_BID_ASK",
        "run":run,"originalAccountVerified":True,
        "fixedOriginalRne1Run":43468457518,
        "originalPepperstoneReadOnlyMessages":calls,
        "currencies":statuses,"fixedThursdayPanel":tape,
        "requestsAfterAuth":requests,
        "forecastPolicyUnchanged":True,
    },sort_keys=True,separators=(",",":")).encode()
    enc=seal_new(source,recipient,run)
    Path("rne1-eur-original-dense-quote-source.v2.enc").write_bytes(enc)
    report={
        "schema":"MXM_RNE1_EUR_ORIGINAL_QUOTE_ACQUISITION_ONLY",
        "runId":int(run),
        "immutableProtocolSha256":sha256(Path(
            "research/RNE1_EUR_DENSE_QUOTE_ORIGINAL.md").read_bytes()).hexdigest(),
        "originalPepperstoneEurBound":True,
        "fixedPriorRne1Run":43468457518,
        "firstWeek":START.isoformat(),"weeks":WEEKS,
        "fixedThursdayCount":len(tape),
        "perThursdayClocks":len(SAMPLES),
        "symbols":SYMBOLS,
        "readOnlyOriginalRequestsAfterAuthentication":requests,
        "panelCoverage":dict(panel),
        "protectedCipherSha256":sha256(enc).hexdigest(),
        "protectedPlaintextSha256":sha256(source).hexdigest(),
        "rawOriginalPricePublication":False,
        "originalHistoryNotIndependent":True,
        "sourceSealedBeforeOutcomeScoring":True,
        "historicalContractEligibilityCertified":False,
        "modelFundedNetEur":None,"liveOrDemoOrders":0,
        "cloudTradingActivated":False,"oauthReauthorized":False,
        "disclosure":"Only new original EURUSD+NatGas as-of quotes at predetermined Thursday clocks; no economic scoring or investment approval in this source-only run."
    }
    Path("rne1-eur-original-source-coverage.json").write_text(
        json.dumps(report,indent=2,allow_nan=False)+"\n")
    print("RNE1_EUR_AUTHENTIC_SEALED_COVERAGE",json.dumps({
        "requests":requests,"days":len(tape),"coverage":dict(panel)}),flush=True)


if __name__=="__main__":
    main()
