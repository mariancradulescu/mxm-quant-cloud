"""NEW OWNER P0.5 LIVE read-only authenticated economic source (not a strategy).

Queries only the original fingerprint-bound Pepperstone account through the
separate P05ReadOnlyTransport. No token refresh, orders, or Cloud operation.
Original protobuf is stored in per-shard private custody; public data is aggregates.
"""
import base64
import gzip
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import median

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport
from .guard import CaptureContractError, require_read_only_request
from .decode import need, decode_side
from .full_inventory_core import normalize_account_inventory
from .economic_source import snapshot_contract, _bounded_server_window
from .custody import seal_new
from .custody_new import checked_public

START = int(datetime(2026,8,24,tzinfo=timezone.utc).timestamp()*1000)
END = int(datetime(2026,11,23,tzinfo=timezone.utc).timestamp()*1000)
PERIODS = {"M15":(e.M15,15,5),"M30":(e.M30,30,10),
           "H1":(e.H1,60,14),"H4":(e.H4,240,28),"D1":(e.D1,1440,28)}
SAMPLES = [(int(datetime(2026,10,26,12,tzinfo=timezone.utc).timestamp()*1000),10*60000),
           (int(datetime(2026,11,9,16,tzinfo=timezone.utc).timestamp()*1000),10*60000)]
MAX_MARKETS=48
MAX_REQ=14000
MAX_SECONDS=140*60
MARKER="OWNER_P05_LIVE_READ_ONLY_SOURCE_AFTER_WIRE_GUARD_20261123"
PUB=Path("p05-new-live-public")
SEALED=Path("p05-new-live-sealed")

def gate():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push"
         and os.environ.get("GITHUB_REF")=="refs/heads/research/p0-inventory-20261123"
         and os.environ.get("GITHUB_RUN_ATTEMPT")=="1"
         and Path("ops/p05-live-readonly-authorized-once.txt").read_text()==MARKER+"\n",
         "P05_NOT_OWNER_AUTHORIZED_EXACT_EVENT")
    rid=os.environ.get("GITHUB_RUN_ID","")
    need(rid.isdigit() and int(rid)>0 and int(time.time()*1000)>=END,
         "P05_RUN_ID_OR_TIME_INVALID")
    return rid

def choose_visible(rows):
    return [r for r in rows if r["visible"] is True and r["symbolName"]]

def choose_market_sample(rows,limit=MAX_MARKETS):
    # Only broker-reported category and *minimum margin*; never historical P&L.
    groups=defaultdict(list)
    for row in rows:
        margin=row.get("currentMinMarginEur")
        if margin is not None and Decimal(margin)<Decimal(300) and row.get("contractStatus")=="MARGIN_OBSERVED":
            groups[str(row["symbolCategoryId"])].append(row)
    for rows in groups.values():
        rows.sort(key=lambda r:(Decimal(r["currentMinMarginEur"]),r["symbolId"]))
    out=[]
    cats=sorted(groups)
    while len(out)<limit and any(groups.values()):
        for cat in cats:
            if groups[cat] and len(out)<limit:
                out.append(groups[cat].pop(0))
    return out

def spread_bps(bids,asks,lag=2000):
    bids=sorted(bids);asks=sorted(asks)
    out=[];i=0;last=None
    for at,ask in asks:
        while i<len(bids) and bids[i][0]<=at:
            last=bids[i];i+=1
        if last is None or at-last[0]>lag or last[1]<=0 or ask<last[1]:
            continue
        out.append(20000*(ask-last[1])/(ask+last[1]))
    return out

def main():
    rid=gate()
    PUB.mkdir(exist_ok=True); SEALED.mkdir(exist_ok=True)
    report=dict(schema="P05_NEW_PEPPERSTONE_AUTHENTIC_READ_ONLY_SOURCE",
                runId=rid,status="STARTED",capitalEUR=300,
                historicalStart="2026-08-24T00:00:00Z",
                endExclusive="2026-11-23T00:00:00Z",
                requests=0,ordersSubmitted=0,cloudActivated=False,
                netEUR=None,hard21="UNKNOWN",drawdownPercent=None,
                fullBrokerCostCertified=False,
                eligibleWeekFundingCertified=False,
                resultsDevelopmentOnly=True,
                sources=[],marketCoverage={})
    def publish():
        (PUB/"receipt.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    publish()
    start_clock=time.monotonic()
    t=P05ReadOnlyTransport(response_timeout=30)
    recipient=checked_public(Path("new-source-recipient"),rid)
    def capture(label,records,meta):
        # Identity and original market packets may NEVER enter public output.
        raw=gzip.compress(json.dumps(records,separators=(",",":"),sort_keys=True).encode(),mtime=0)
        cipher=seal_new(raw,recipient,rid)
        f=label+".sealed"
        (SEALED/f).write_bytes(cipher)
        report["sources"].append(dict(name=f,ciphertextSha256=hashlib.sha256(cipher).hexdigest(),
                                      originalGzipSha256=hashlib.sha256(raw).hexdigest(),**meta))
    def packet(q,r):
        enc=lambda msg:base64.b64encode(msg.SerializeToString()).decode()
        return {"reqType":type(q).__name__,"req":enc(q),"resType":type(r).__name__,"res":enc(r)}
    def query(req,expected=None,allow_error=False):
        require_read_only_request(req)
        need(report["requests"]<MAX_REQ and time.monotonic()-start_clock<MAX_SECONDS,
             "P05_BROKER_REQUEST_BUDGET")
        report["requests"]+=1
        res=t.request(req)
        if allow_error and type(res) is m.ProtoOAErrorRes:
            return res
        need(type(res) is expected and res.IsInitialized() and
             res.ctidTraderAccountId==req.ctidTraderAccountId,
             "P05_BROKER_RESPONSE_INVALID")
        return res
    def get_bars(account,sid,period_name,spec,raw):
        enum,minutes,span=spec
        seen=set();bars=[];fail=0
        def page(a,b,depth=0):
            nonlocal fail
            need(depth<20 and a<=b,"P05_BAR_PAGE_LIMIT")
            req=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                symbolId=sid,period=enum,fromTimestamp=a,toTimestamp=b)
            res=query(req,m.ProtoOAGetTrendbarsRes,allow_error=True)
            raw.append(packet(req,res))
            if type(res) is m.ProtoOAErrorRes:
                fail+=1;return []
            need(res.HasField("hasMore") and res.period==enum
                 and (not res.HasField("symbolId") or res.symbolId==sid),
                 "P05_BAR_REPLY_UNBOUND")
            if res.hasMore:
                need(b-a>=60000,"P05_BAR_MORE_NOT_RESOLVABLE")
                mid=(a+b)//2
                return page(a,mid,depth+1)+page(mid+1,b,depth+1)
            return _bounded_server_window(res.trendbar,a,b,minutes)
        day=86400000
        for lo in range(START,END,span*day):
            for item in page(lo,min(END,lo+span*day)-1):
                if item[0] not in seen and item[1]<=END:
                    seen.add(item[0]);bars.append(item)
                else:
                    fail+=1
        bars.sort()
        ranges=[10000*(b[3]-b[4])/b[5] for b in bars if b[5]>0]
        return dict(bars=len(bars),firstUTC=bars[0][0] if bars else None,
                    lastUTC=bars[-1][0] if bars else None,
                    medianIntrabarRangeBpsNotRealizedProfit=round(median(ranges),5) if ranges else None,
                    rejectedOrFailedPages=fail,
                    sessionGapsReconciled=False,netEUR=None)
    def get_side(account,sid,side,lo,hi,raw):
        side_enum=e.BID if side=="BID" else e.ASK
        def page(a,b,d=0):
            need(d<20 and a<=b and b-a<=604800000,"P05_TICK_PAGE_LIMIT")
            req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,
                                       type=side_enum,fromTimestamp=a,toTimestamp=b)
            res=query(req,m.ProtoOAGetTickDataRes,allow_error=True)
            raw.append(packet(req,res))
            if type(res) is m.ProtoOAErrorRes:
                return []
            need(res.HasField("hasMore"),"P05_TICK_MORE_UNKNOWN")
            if res.hasMore:
                need(b-a>=1000,"P05_TICK_MORE_NOT_RESOLVABLE")
                mid=(a+b)//2
                return page(a,mid,d+1)+page(mid+1,b,d+1)
            return decode_side(res.tickData,a,b)
        return page(lo,hi)
    try:
        account=authenticate(t) # bound original Pepperstone account; SCOPE_TRADE READ ONLY
        identity=[]
        queries=[
          (m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes),
          (m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes),
          (m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                                  includeArchivedSymbols=False),m.ProtoOASymbolsListRes)]
        bound=[]
        for req,typ in queries:
            res=query(req,typ);identity.append(packet(req,res));bound.append(res)
        trader,asset_list,listing=bound
        assets={a.assetId:a.name for a in asset_list.asset}
        need(trader.trader.HasField("brokerName") and
             "pepperstone" in trader.trader.brokerName.casefold() and
             assets.get(trader.trader.depositAssetId)=="EUR",
             "P05_BROKER_OR_EUR_ACCOUNT_MISMATCH")
        rows=normalize_account_inventory(listing,asset_list,account)
        report.update(totalNonArchivedSymbols=len(rows),visibleSymbols=len(choose_visible(rows)))
        capture("p05-original-roster",identity,{"kind":"ROSTER"})
        report["status"]="ROSTER_CAPTURED";publish()
        examined=0;raw=[];fields={}
        for row in choose_visible(rows):
            sid=row["symbolId"]
            req=m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[sid])
            res=query(req,m.ProtoOASymbolByIdRes,allow_error=True)
            raw.append(packet(req,res));examined+=1
            if type(res) is m.ProtoOAErrorRes or len(res.symbol)!=1 or res.symbol[0].symbolId!=sid:
                row["contractStatus"]="DETAIL_UNKNOWN";continue
            contract=res.symbol[0]
            if int(contract.tradingMode)!=0:
                row["contractStatus"]="NOT_OPENABLE";continue
            if any(not contract.HasField(x) for x in ("minVolume","stepVolume","maxVolume")) or not (
                 0<contract.minVolume<=contract.maxVolume and contract.stepVolume>0):
                row["contractStatus"]="INVALID_OR_MISSING_VOLUME";continue
            fields[sid]=snapshot_contract(contract)
            mq=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                                          symbolId=sid,volume=[contract.minVolume])
            mr=query(mq,m.ProtoOAExpectedMarginRes,allow_error=True)
            raw.append(packet(mq,mr))
            if type(mr) is m.ProtoOAExpectedMarginRes and mr.HasField("moneyDigits") and (
                len(mr.margin)==1 and mr.margin[0].volume==contract.minVolume):
                unit=Decimal(10)**mr.moneyDigits
                cost=max(Decimal(mr.margin[0].buyMargin)/unit,
                         Decimal(mr.margin[0].sellMargin)/unit)
                row["currentMinMarginEur"]=str(cost)
                row["contractStatus"]="MARGIN_OBSERVED"
            else:
                row["contractStatus"]="MARGIN_UNKNOWN"
            if examined%64==0:
                capture(f"p05-contracts-{examined:05d}",raw,{"kind":"CONTRACTS","through":examined})
                raw=[]
                report["contractDetailsExamined"]=examined
                report["marginsObserved"]=sum(r.get("currentMinMarginEur") is not None for r in rows)
                report["status"]="CONTRACT_PROBES_PARTIAL";publish()
        if raw:
            capture("p05-contracts-last",raw,{"kind":"CONTRACTS","through":examined})
        report["contractDetailsExamined"]=examined
        report["marginsObserved"]=sum(r.get("currentMinMarginEur") is not None for r in rows)
        report["marginsBelow300EUR"]=sum(r.get("currentMinMarginEur") is not None and
                                       Decimal(r["currentMinMarginEur"])<300 for r in rows)
        choices=choose_market_sample(rows)
        report["sampleSelection"]="round_robin_account_categories_min_margin_not_pnl"
        report["candidateSamplingNotFinalUniverse"]=True
        report["marketProbeTargets"]=len(choices)
        report["status"]="CONTRACTS_CAPTURED";publish()
        for idx,row in enumerate(choices,1):
            sid=row["symbolId"];source=[{"contract":fields.get(sid)}]
            stats=dict(categoryId=row["symbolCategoryId"],
                       currentMinMarginEur=row["currentMinMarginEur"],timeframes={},bidAsk={},
                       allInCostEur=None,netEur=None)
            for name,spec in PERIODS.items():
                stats["timeframes"][name]=get_bars(account,sid,name,spec,source)
            for k,(at,span) in enumerate(SAMPLES):
                bid=get_side(account,sid,"BID",at,at+span-1,source)
                ask=get_side(account,sid,"ASK",at,at+span-1,source)
                paired=spread_bps(bid,ask)
                stats["bidAsk"][f"window{k}"]={
                    "validAsOfPairs":len(paired),
                    "medianSpreadBps":round(median(paired),6) if paired else None,
                    "spreadAllInCertified":False}
            capture(f"p05-market-{idx:03d}",source,{"kind":"MARKET","ordinal":idx})
            report["marketCoverage"][row["symbolName"]]=stats
            report["marketProbesCompleted"]=idx
            report["status"]="MARKET_HISTORY_PARTIAL";publish()
        report["status"]="AUTHENTIC_READ_ONLY_SOURCE_COMPLETE_NO_TRADING_QUALIFICATION"
        report["P0"]="INCOMPLETE_PENDING_COST_AND_BACKTEST"
        report["P0_5"]="PENDING_ALL_IN_FINANCEABILITY_AND_HARD21"
        publish()
        print("P05_READ_ONLY_MARKET_COLLECTION_COMPLETE",report["totalNonArchivedSymbols"],
              report["contractDetailsExamined"],report.get("marketProbesCompleted",0),flush=True)
    finally:
        t.close()

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        msg=str(exc)
        if isinstance(exc,CaptureContractError) and msg.isupper() and msg.replace("_","").isalnum():
            print(msg,flush=True)
        else:
            print("P05_SOURCE_FAILED_DETAIL_WITHHELD",flush=True)
        sys.exit(1)
