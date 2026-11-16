"""CXL1 275 earlier prespecified weekday clocks: first-only ORIGINAL broker source.

Reuse ORIGINAL sealed 50-clock pilot without recollection. This module only
collects additional older historical source and seals it BEFORE any EUR scoring.
No closing study, trading, new recipient key, internet backend, or cloud.
"""
from __future__ import annotations
import base64,json,os
from collections import Counter
from datetime import date
from hashlib import sha256
from pathlib import Path

from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .decode import decode_bars,decode_side,need
from .guard import require_read_only_request
from .custody_new import checked_public
from .custody import seal_new
from .cxl1_original_feasibility import (
    PROTOCOL,calendar,crypto_features,classification,fresh,DAY,M5,
    DECISION_DELAY,EXIT_DELAY,AGE,BACK,SYMS,minimum_contract)

PILOT_START=date(2026,11,2)
LIMIT=3000
def earlier():
    rows=[(d,t) for d,t in calendar() if d<PILOT_START]
    need(len(rows)==275 and len(list(calendar()))==325,
         "CXL1_EARLIER_SOURCE_CALENDAR_NOT_275_OF_325")
    return rows

def main():
    need(PROTOCOL.exists() and "FROZEN" in PROTOCOL.read_text(),
         "CXL1_FROZEN_PRESOURCE_PROTOCOL_NOT_FOUND")
    run=os.environ["GITHUB_RUN_ID"]
    public=checked_public(Path("new-recipient-output"),run)
    transport=StdlibCTraderTransport()
    raw=[]
    def query(req,kind,missing=False):
        need(len(raw)<LIMIT,"CXL1_275_SOURCE_CALL_CAP")
        require_read_only_request(req)
        res=transport.request(req)
        if type(res) is m.ProtoOAErrorRes and missing:
            need(res.errorCode=="NO_QUOTES" and res.ctidTraderAccountId==acct,
                 "CXL1_275_ORIGINAL_UNEXPECTED_ERROR")
            out=None
        else:
            need(type(res) is kind and res.IsInitialized()
                 and res.ctidTraderAccountId==acct,"CXL1_275_BROKER_RESPONSE_INVALID")
            out=res
        raw.append(dict(requestType=type(req).__name__,
            responseType=type(res).__name__,
            request=base64.b64encode(req.SerializeToString()).decode(),
            response=base64.b64encode(res.SerializeToString()).decode()))
        return out,len(raw)-1
    rows=[];counts=Counter()
    try:
        acct=authenticate(transport)
        trader,_=query(m.ProtoOATraderReq(ctidTraderAccountId=acct),m.ProtoOATraderRes)
        assets,_=query(m.ProtoOAAssetListReq(ctidTraderAccountId=acct),m.ProtoOAAssetListRes)
        roster,_=query(m.ProtoOASymbolsListReq(ctidTraderAccountId=acct,
            includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        assets_by_id={x.assetId:x.name for x in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and assets_by_id.get(trader.trader.depositAssetId)=="EUR",
             "CXL1_275_ORIGINAL_PEPERSTONE_EUR")
        enabled={x.symbolName:x for x in roster.symbol if x.enabled}
        need(all(x in enabled for x in SYMS),"CXL1_275_ORIGINAL_SYMBOL_MISSING")
        need(all(assets_by_id.get(enabled[s].quoteAssetId)=="USD"
                 for s in SYMS)
             and assets_by_id.get(enabled["EURUSD"].baseAssetId)=="EUR",
             "CXL1_275_USD_EUR_ROUTE_MISMATCH")
        ids={x:enabled[x].symbolId for x in SYMS}
        contracts={}
        for s in SYMS:
            ans,_=query(m.ProtoOASymbolByIdReq(ctidTraderAccountId=acct,
                symbolId=[ids[s]]),m.ProtoOASymbolByIdRes)
            need(len(ans.symbol)==1 and ans.symbol[0].symbolId==ids[s],
                 "CXL1_275_CONTRACT_INVALID")
            contracts[s]=ans.symbol[0]
        c=contracts["ETHUSD"]
        unit=minimum_contract(c)
        ans,_=query(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=acct,
            symbolId=ids["ETHUSD"],volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
        need(ans.HasField("moneyDigits") and len(ans.margin)==1
             and ans.margin[0].volume==c.minVolume,
             "CXL1_275_MARGIN_NOT_RECONCILABLE")
        div=10**ans.moneyDigits
        margins=[ans.margin[0].buyMargin/div,ans.margin[0].sellMargin/div]
        need(all(0<v<=210 for v in margins),"CXL1_275_MIN_MARGIN_GATE_FAILED")
        for n,(d,t) in enumerate(earlier()):
            entry=dict(day=d.isoformat(),t=t,bar={},quotes={})
            features={}
            for s in ("BTCUSD","ETHUSD"):
                start=t-DAY-M5
                ans,idx=query(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=acct,
                    symbolId=ids[s],period=e.M5,fromTimestamp=start,
                    toTimestamp=t),m.ProtoOAGetTrendbarsRes,True)
                trunc=ans is not None and (not ans.HasField("hasMore") or ans.hasMore)
                closes=None
                if ans is not None and not trunc:
                    got=decode_bars(ans.trendbar,start,t,5)
                    mapping={int(x[1]):int(x[5]) for x in got}
                    expected=[t-DAY+i*M5 for i in range(289)]
                    if all(k in mapping and mapping[k]>0 for k in expected):
                        closes=[mapping[k] for k in expected]
                features[s]=crypto_features(closes) if closes else None
                entry["bar"][s]=dict(rawIndex=idx,
                     complete=closes is not None,truncated=bool(trunc))
                counts["bars_"+s+"_complete" if closes else "bars_"+s+"_missing"]+=1
            side=classification(features["BTCUSD"],features["ETHUSD"])
            entry["featureComplete"]=all(x is not None for x in features.values())
            entry["leadDirection"]=side
            entry["ownEthSign"]=(1 if features["ETHUSD"][0]>0 else -1
                if features["ETHUSD"][0]<0 else 0) if features["ETHUSD"] else None
            if side:counts["btcLeadingSignals"]+=1
            if side and entry["ownEthSign"]!=side:counts["differentFromOwnEth"]+=1
            for name,at in (("entry",t+DECISION_DELAY),
                            ("exit",t+EXIT_DELAY+DECISION_DELAY)):
                entry["quotes"][name]={}
                for s in ("ETHUSD","EURUSD"):
                    sides=[];indices=[];trunc=False
                    for side_kind in (e.BID,e.ASK):
                        ans,idx=query(m.ProtoOAGetTickDataReq(ctidTraderAccountId=acct,
                            symbolId=ids[s],type=side_kind,
                            fromTimestamp=at-BACK,toTimestamp=at),
                            m.ProtoOAGetTickDataRes,True)
                        indices.append(idx)
                        if ans is None:values=[]
                        elif not ans.HasField("hasMore") or ans.hasMore:
                            trunc=True;values=[]
                        else:values=decode_side(ans.tickData,at-BACK,at)
                        sides.append(values)
                    pair=None if trunc else fresh(*sides,at)
                    entry["quotes"][name][s]=dict(valid=pair is not None,
                         truncated=trunc,rawIndices=indices)
                    counts["quote_"+s+"_valid" if pair else "quote_"+s+"_missing"]+=1
            rows.append(entry)
            if n%55==54:
                print("CXL1_275_ORIGINAL_PROGRESS",n+1,"OF_275",len(raw),flush=True)
    finally:
        transport.close()
    need(len(rows)==275 and len(raw)==2757,
         "CXL1_275_ORIGINAL_REQUEST_CENSUS_INVALID")
    raw_plain=json.dumps(dict(schema="MXM_CXL1_ORIGINAL_275_EARLIER_CLOSED_BAR_AND_QUOTE_SOURCE_V1",
        runId=run,pilotRunReused=43945139889,
        originalPepperstoneEurAccount=True,readOnly=True,
        noNewFinanceScoring=True,brokerOrders=0,cloudActivated=False,
        raw=raw,rows=rows,
        currentMinimumVolumeRaw=c.minVolume,
        currentBuySellMarginEur=margins),
        sort_keys=True,separators=(",",":")).encode()
    ciphertext=seal_new(raw_plain,public,run)
    Path("cxl1-earlier-275-authentic.v2.enc").write_bytes(ciphertext)
    receipt=dict(schema="MXM_CXL1_ORIGINAL_275_SOURCE_ONLY_V1",
        runId=int(run),immutablePilotRunId=43945139889,
        sourceProtocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),
        sourceCipherSha256=sha256(ciphertext).hexdigest(),
        sourcePlainSha256=sha256(raw_plain).hexdigest(),
        originalRequests=len(raw),remainingScheduledClocks=275,
        reusedPilotClocks=50,combinedCalendar=325,
        coverage=dict(counts),currentMinimumVolumeRaw=c.minVolume,
        currentBuySellMarginEur=margins,
        originalSourceSealedBeforeEconomicScoring=True,
        noHistoricalReturnsScored=True,noClosedStudyRerun=True,
        ordersSubmitted=0,cloudActivated=False)
    Path("cxl1-original-275-source-public.json").write_text(json.dumps(
        receipt,indent=2,sort_keys=True)+"\n")
    print("CXL1_ORIGINAL_275_EARLIER_SOURCE_SEALED_NO_MONEY_SCORE",
          json.dumps({"calls":len(raw),"features":counts["bars_BTCUSD_complete"],
            "ETH":counts["bars_ETHUSD_complete"],
            "signals":counts["btcLeadingSignals"]}),flush=True)

if __name__=="__main__":
    main()
