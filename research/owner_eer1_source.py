"""EER1 bounded official read-only source; protected packet shards, no decisions."""
from collections import defaultdict, deque, Counter
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
import json, os, sys, time, bisect

from . import owner_official_eur_source as wire
from . import owner_eur_rollover_continuity as roll
from . import owner_source_history_expand as extension
from . import owner_source_history_use as history
from . import integrated_market_readback as marks
from . import integrated_market_source as integrated
from . import owner_eur_conditional_source as conditional
from . import source_history_universe as src
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate

DAY=86400000
STEP=300000
START=int(datetime(2026,10,26,tzinfo=timezone.utc).timestamp()*1000)
FIT_END=START+14*DAY
END=START+28*DAY
WARM=START-21*DAY
OUT=Path("eer1-source")
MATRIX=Path("pilot-source/integrated-coverage-matrix.json")
MATRIX_SHA="6ffbe6d6bda9c57fde3ce92f3d851edc14e3930c79552bf31093ad27fd2b0d1c"
PROTOCOL=Path("research/OWNER_EER1_EXTENDED_20261125.md")
ANCHORS=("EURUSD","GBPUSD","XAUUSD","US500")
PRIOR_FULL=set((*ANCHORS,"SpotBrent","AAPL.US","AAPL"))
PRIOR_ROLL_START=int(datetime(2026,11,4,tzinfo=timezone.utc).timestamp()*1000)
PER_SYMBOL=1450
HORIZON_SECONDS=180*60

def matrix():
    raw=MATRIX.read_bytes()
    need(src.digest(raw)==MATRIX_SHA,"EER1_MATRIX_HASH")
    return json.loads(raw)

def group(row):
    v=(row.get("assetClass") or "UNMAPPED").lower()
    if "equities" in v or "stock" in v:return "equities"
    if "forward" in v or "perpetual" in v:return "other_contracts"
    if "indice" in v or "index" in v:return "indices"
    if "crypto" in v:return "crypto"
    if "metal" in v:return "metals"
    if "energ" in v:return "energy"
    if "commodit" in v:return "commodities"
    if "etf" in v:return "etf"
    if "forex" in v:return "forex"
    return v

def selection(mat,original):
    by_name={r["name"]:r for r in original["contractRoster"]}
    rows={r["symbol"]:r for r in mat["matrix"]}
    need(set(ANCHORS)<=set(rows),"EER1_ANCHORS")
    known=[n for n,r in rows.items() if any(r["timeframes"].values())]
    def ranked(names,existing_groups):
        groups=defaultdict(deque)
        for n in sorted(names,key=lambda x:by_name[x]["symbolId"]):
            if by_name[n].get("visible") is True:groups[group(rows[n])].append(n)
        order=sorted(groups,key=lambda g:(g in existing_groups,g))
        result=[]
        while any(groups.values()):
            for g in order:
                if groups[g]:result.append(groups[g].popleft())
        return result
    anchor_groups={group(rows[n]) for n in ANCHORS}
    more=ranked([n for n in known if n not in ANCHORS],anchor_groups)
    new=ranked([n for n in rows if n not in set(known)],anchor_groups)
    chosen=list(ANCHORS)+more[:8]+new[:4]
    need(len(chosen)==len(set(chosen))==16,"EER1_TRANCHE")
    return chosen,more[8:]+new[4:]

def schedule(fields,start=WARM,end=END+7*DAY):
    """UTC M5 decision grid from documented Sunday-based local schedule.
    Current broker snapshot is a scenario, never a historical calendar proof."""
    try:
        zone=ZoneInfo(fields["scheduleTimeZone"])
        sessions=[(s["startSecond"],s["endSecond"]) for s in fields["schedule"]]
        if not sessions or any(not 0<=a<b<=604800 for a,b in sessions):return None
        holidays=[]
        for h in fields.get("holiday",[]):
            d=date(1970,1,1)+timedelta(days=h["holidayDate"])
            lo,hi=h.get("startSecond",0),h.get("endSecond",86400)
            if not 0<=lo<hi<=86400:return None
            holidays.append((d,h["isRecurring"],ZoneInfo(h["scheduleTimeZone"]),lo,hi))
        out=[]
        for at in range(start+15000,end,STEP):
            dt=datetime.fromtimestamp(at/1000,timezone.utc)
            local=dt.astimezone(zone)
            sec=((local.weekday()+1)%7)*86400+local.hour*3600+local.minute*60+local.second
            if not any(a<=sec<b for a,b in sessions):continue
            closed=False
            for d,rec,hz,lo,hi in holidays:
                h=dt.astimezone(hz)
                ss=h.hour*3600+h.minute*60+h.second
                if (h.date()==d or rec and (h.month,h.day)==(d.month,d.day)) and lo<=ss<hi:
                    closed=True;break
            if not closed:out.append(at)
        return out
    except (KeyError,ValueError,TypeError,OverflowError):return None

def bar_requests(row,period):
    width=src.PERIODS[period]*60000
    # Reuse prior dated observed days, preserving their within-day gaps.
    intervals=(row.get("timeframes",{}).get(period) or {}).get("observedIntervals",[])
    missing=[]
    for day in range(WARM,END,DAY):
        if not any(a<day+DAY and b>day for a,b in intervals):missing.append(day)
    blocks=[]
    page=extension.DAYS_PER_PAGE[period]*DAY
    for day in missing:
        if blocks and blocks[-1][1]==day and day+DAY-blocks[-1][0]<=page:
            blocks[-1][1]=day+DAY
        else:blocks.append([day,day+DAY])
    return [(a,b-1) for a,b in blocks]

def bars_for(j,account,sid,row):
    rows=defaultdict(dict); reports={}
    for period in src.PERIODS:
        pending=deque(bar_requests(row,period)); count=Counter()
        while pending:
            lo,hi=pending.popleft()
            q=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=sid,
                period=e.ProtoOATrendbarPeriod.Value(period),fromTimestamp=lo,toTimestamp=hi)
            a,at,status=j.query(q)
            if a is None:count[status]+=1;continue
            if extension.page_pair(q,a) and a.HasField("hasMore") and a.hasMore and hi-lo>=2*src.PERIODS[period]*60000:
                pending.extendleft(reversed(src.split_window(lo,hi)));count["SPLIT"]+=1;continue
            d,accepted=history.inspect_bars(q,a,at,closed_through=END)
            count[d["status"]]+=1
            for b in accepted:
                need(b[0] not in rows[period],"EER1_NEW_BAR_DUPLICATE")
                rows[period][b[0]]=b
        reports[period]=dict(counts=dict(count),closedRows=len(rows[period]))
    return rows,reports

def charge_clocks(contracts):
    minutes=set()
    for c in contracts.values():
        p=c.get("SwapPeriodHours");t=c.get("SwapTimeUtcMinute")
        if p and 24%p==0 and t is not None and 0<=t<1440:minutes.update(range(t,1440,60*p))
    return sorted(minutes)

def covered(leaves,lo,hi):
    cursor=lo
    for a,b,status,_,_ in sorted(leaves):
        if b<cursor:continue
        if a>cursor or status not in ("VERIFIED_COMPLETE_PAGE","PROVIDER_NO_QUOTES"):return False
        cursor=b+1
        if cursor>hi:return True
    return cursor>hi

def collect_market(j,account,sid,row,target,charges,keep,name):
    bars,bar_report=bars_for(j,account,sid,row) if target else ({},{})
    budget=[PER_SYMBOL-len(j.packets)] if hasattr(j,"t") else [PER_SYMBOL-j.index]
    windows=[]; quote_marks=[]; funding=[]; tail={e.BID:[],e.ASK:[]}; tail_leaves={e.BID:[],e.ASK:[]}
    for day in range(START,END,DAY):
        sides={e.BID:[],e.ASK:[]}; leaves={e.BID:[],e.ASK:[]}
        # Existing full-session custody already covers 26 Oct–16 Nov.
        # Only charge-time pages missing in that custody are requested here.
        roots=[(lo,lo+4*3600000-1) for lo in range(day,day+DAY,4*3600000)]
        if name in PRIOR_FULL and day<integrated.END:
            roots=[]
            if not (name in ("EURUSD","US500") and day>=PRIOR_ROLL_START):
                spans=[]
                for minute in charges:
                    at=day+minute*60000
                    spans.append((at-2*3600000,at))
                for lo,hi in sorted(spans):
                    if roots and lo<=roots[-1][1]+1:roots[-1]=(roots[-1][0],max(roots[-1][1],hi))
                    else:roots.append((lo,hi))
        for lo,hi in roots:
            for side in (e.BID,e.ASK):
                raw,pages=roll.tick_window(j.query,account,sid,side,lo,hi,budget)
                windows.append([lo,side,roll.describe(raw,pages,lo)])
                sides[side].extend(raw);leaves[side].extend(pages)
        if keep:
            for side in sides:
                # Merge same millisecond only if the original prices agree.
                # Conflicting endpoints remain unusable for funding.
                sides[side].sort(key=lambda r:r[0])
            for q in (() if name in PRIOR_FULL and day<integrated.END else marks.minute_marks(day,sides[e.BID],sides[e.ASK],interval=STEP)):
                at=q["At"]
                if all(covered(leaves[s],max(day,at-30000),at) for s in sides):
                    quote_marks.append(q)
            for minute in charges:
                at=day+minute*60000; lo=at-2*3600000
                q={"At":at,"RequestedCoverage":all(covered(tail_leaves[s]+leaves[s],lo,at) for s in sides)}
                if q["RequestedCoverage"]:
                    for s,name in ((e.BID,"Bid"),(e.ASK,"Ask")):
                        candidates=[v for v in tail[s]+sides[s] if lo<=v[0]<=at]
                        b=conditional.boundary(candidates,at,True)
                        if b and not b["conflict"]:
                            q[name+"At"]=b["at"];q[name]=str(Decimal(b["rawPrices"][0]).scaleb(-5))
                funding.append(q)
        for s in sides:
            tail[s]=[v for v in sides[s] if v[0]>=day+DAY-2*3600000] if keep else []
            tail_leaves[s]=[v for v in leaves[s] if v[1]>=day+DAY-2*3600000] if keep else []
    return dict(bars=bar_report,tickWindows=windows),bars,quote_marks,funding

def metadata(t,account,selected,mat):
    def read(q,cls,tag):
        return t.read(q,cls,tag)
    tr=read(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes,"trader")
    ar=read(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes,"assets")
    rr=read(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes,"roster")
    cr=read(m.ProtoOASymbolCategoryListReq(ctidTraderAccountId=account),m.ProtoOASymbolCategoryListRes,"categories")
    cl=read(m.ProtoOAAssetClassListReq(ctidTraderAccountId=account),m.ProtoOAAssetClassListRes,"classes")
    need(all(x is not None for x in (tr,ar,rr,cr,cl)),"EER1_METADATA")
    assets={x.assetId:x.name for x in ar.asset}
    need("pepperstone" in tr.trader.brokerName.lower() and assets.get(tr.trader.depositAssetId)=="EUR","EER1_ACCOUNT")
    live={x.symbolName:x for x in rr.symbol}
    ids=[live[n].symbolId for n in selected if n in live and live[n].enabled]
    r=read(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=ids),m.ProtoOASymbolByIdRes,"terms")
    need(r is not None,"EER1_TERMS")
    terms={c.symbolId:c for c in r.symbol}; lights={x.symbolId:x for x in rr.symbol}
    requested={lights[s].quoteAssetId for s in terms}
    requested|={i for i,n in assets.items() if n=="USD" or n in {c.minCommissionAsset for c in terms.values()}}
    for asset in sorted(requested-{tr.trader.depositAssetId}):
        read(m.ProtoOASymbolsForConversionReq(ctidTraderAccountId=account,firstAssetId=asset,lastAssetId=tr.trader.depositAssetId),
             m.ProtoOASymbolsForConversionRes,"route")
    for lev in sorted({c.leverageId for c in terms.values() if c.HasField("leverageId") and c.leverageId>0}):
        read(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=account,leverageId=lev),m.ProtoOAGetDynamicLeverageByIDRes,"leverage")
    for sid,c in terms.items():
        volumes=wire.quoted_volumes(c)
        if volumes:read(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=volumes),m.ProtoOAExpectedMarginRes,"margin")
    return metadata_read(t.journal,selected,account)

def metadata_read(packets,selected,account):
    items=list(wire.decoded_packets(dict(requests=packets)))
    tr=next(r.trader for _,_,r in items if type(r) is m.ProtoOATraderRes)
    assets=next({x.assetId:x.name for x in r.asset} for _,_,r in items if type(r) is m.ProtoOAAssetListRes)
    live=next({x.symbolId:x for x in r.symbol} for _,_,r in items if type(r) is m.ProtoOASymbolsListRes)
    cats=next({c.id:(c.name,c.assetClassId) for c in r.symbolCategory} for _,_,r in items if type(r) is m.ProtoOASymbolCategoryListRes)
    classes=next({c.id:c.name for c in r.assetClass} for _,_,r in items if type(r) is m.ProtoOAAssetClassListRes)
    need(src.original_account(account) and assets.get(tr.depositAssetId)=="EUR" and "pepperstone" in tr.brokerName.lower(),"EER1_METADATA_ACCOUNT")
    routes={"EUR":[]}; margins={}; terms={}; schedules={}; actual={}; info={}
    for row,q,r in items:
        if type(r) is m.ProtoOASymbolsForConversionRes:
            routes[assets[q.firstAssetId]]=[dict(Symbol=x.symbolName,BaseAsset=assets.get(x.baseAssetId),QuoteAsset=assets.get(x.quoteAssetId)) for x in r.symbol]
        if type(r) is m.ProtoOAExpectedMarginRes:
            try:margins[q.symbolId]=integrated.margin_snapshot(r,list(q.volume))
            except Exception:margins[q.symbolId]=[]
        if type(r) is m.ProtoOASymbolByIdRes:
            for c in r.symbol:
                need(c.symbolId in q.symbolId and c.symbolId in live,"EER1_TERMS_BINDING")
                name=live[c.symbolId].symbolName
                if name not in selected:continue
                decoded=wire.terms_input(c,name,assets.get(live[c.symbolId].quoteAssetId),row["at"])
                if decoded is None:continue
                contract,fields,_,_=decoded
                actual[name]=row["at"];terms[name]=contract;schedules[name]=schedule(fields)
                info[name]=dict(id=c.symbolId,fields=fields,digest=src.digest(c.SerializeToString()),
                    priceDigits=src.field(c,"digits"),tradingMode=src.field(c,"tradingMode"),
                    shortAllowed=src.field(c,"enableShortSelling") is True)
    roster={x.symbolName:dict(id=x.symbolId,enabled=x.enabled,category=cats.get(x.symbolCategoryId,[None,None])[0],
        assetClass=classes.get(cats.get(x.symbolCategoryId,[None,None])[1])) for x in live.values()}
    names=[n for n in selected if n in roster and roster[n]["enabled"]]
    route_names=sorted({x["Symbol"] for hops in routes.values() for x in hops if x["Symbol"] in roster})
    return dict(terms=terms,actual=actual,schedules=schedules,info=info,margin={n:margins.get(v["id"],[]) for n,v in info.items()},
        routes=routes,roster=roster,sourceNames=list(dict.fromkeys(names+route_names)),
        accountSwapFree=src.field(tr,"swapFree"),accountType=src.field(tr,"accountType"),moneyDigits=src.field(tr,"moneyDigits"))

def seal(path,obj,recipient,rid):
    clear=src.canonical(obj); encrypted=seal_new(clear,recipient,rid)
    path.write_bytes(encrypted)
    return dict(file=path.name,plainSha256=src.digest(clear),cipherSha256=src.digest(encrypted))

def capture():
    need(os.environ["GITHUB_EVENT_NAME"]=="push" and os.environ["GITHUB_REF"]=="refs/heads/main" and os.environ["GITHUB_RUN_ATTEMPT"]=="1","EER1_OWNER_CONTEXT")
    rid=os.environ["GITHUB_RUN_ID"]; mat=matrix(); chosen,pending=selection(mat,wire.public_original())
    receiver=checked_public(Path("eer1-recipient"),rid)
    OUT.mkdir(exist_ok=False); t=wire.OfficialEvidenceTransport(); receipt=None
    try:
        account=authenticate(t);t.bind(account)
        meta=metadata(t,account,chosen,mat)
        receipt=dict(runId=rid,protocolSha256=src.digest(PROTOCOL.read_bytes()),matrixSha256=MATRIX_SHA,
            selected=chosen,pending= pending,officialRosterCount=len(meta["roster"]),sources=[],
            metadata=seal(OUT/"metadata.sealed",dict(runId=rid,packets=t.journal,chosen=chosen),receiver,rid),
            orders=0,cloudActivated=False)
        rows={x["symbol"]:x for x in mat["matrix"]}
        start=time.monotonic(); src.MAX_REQUESTS=PER_SYMBOL
        for name in meta["sourceNames"]:
            if not t.connected or time.monotonic()-start>HORIZON_SECONDS:break
            j=src.Journal(t,account);j.deadline=time.monotonic()+min(1200,max(1,HORIZON_SECONDS-(time.monotonic()-start)))
            sid=meta["roster"][name]["id"]
            summary,_,_,_=collect_market(j,account,sid,rows.get(name,{}),name in chosen,charge_clocks(meta["terms"]),False,name)
            ref=seal(OUT/(str(sid)+".sealed"),dict(runId=rid,name=name,id=sid,packets=j.packets,summary=summary),receiver,rid)
            receipt["sources"].append(dict(ref,name=name,id=sid,requests=len(j.packets),summary=summary))
            (OUT/"receipt.json").write_bytes(src.canonical(receipt))
            print("EER1_SOURCE_SHARD",name,len(j.packets),len(receipt["sources"]),"/",len(meta["sourceNames"]),flush=True)
            if j.halted:break
    finally:
        t.close()
        if receipt is not None:(OUT/"receipt.json").write_bytes(src.canonical(receipt))

def unpack(folder,ref,key,run):
    cipher=(folder/ref["file"]).read_bytes()
    need(src.digest(cipher)==ref["cipherSha256"],"EER1_CIPHER_HASH")
    raw=unseal_new(cipher,key,run)
    need(src.digest(raw)==ref["plainSha256"],"EER1_PLAIN_HASH")
    return json.loads(raw)

if __name__=="__main__":capture()
