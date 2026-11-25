"""Recent official read-only history: adjacent windows and additional instruments.

The registered selection is independent of trading results. Raw requests and
responses remain encrypted. Current contract terms are scenarios, not proof
of their historical continuity. No orders or Cloud activation.
"""
import argparse
from collections import Counter, deque
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from . import owner_eer1_source as eer
from . import owner_official_eur_source as wire
from . import owner_source_history_expand as extension
from . import owner_source_history_use as history
from . import owner_eur_rollover_continuity as rollover
from . import owner_eur_conditional_source as conditional
from . import integrated_market_readback as marks
from . import source_history_universe as src
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

PROTOCOL=Path("research/eur_recent_continuous_source_1.json")
DAY=86_400_000
HOUR=3_600_000
META=Path("recent-metadata")
OUT=Path("recent-source")


def utc(day):
    return int(datetime.strptime(day,"%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())*1000


def registered():
    raw=PROTOCOL.read_bytes()
    p=json.loads(raw)
    need(p["Study"]=="EUR_RECENT_CONTINUOUS_SOURCE_1" and
         p["Exposure"]=="DEVELOPMENT_ONLY_NO_INDEPENDENT_CLAIM" and
         len(p["Base"])==17 and len(p["New"])==4 and
         len(set(p["Base"]+p["New"]))==21 and p["PageHours"]==4 and
         p["PerPartitionMaxRequests"]<=1000 and p["PerPartitionSeconds"]<=1080 and
         p["PerSidePageBudget"]<=450,"RECENT_PROTOCOL")
    census_raw=Path("eer1-economic/source-census.json").read_bytes()
    need(src.digest(census_raw)==p["PriorCensusSha256"],"RECENT_CENSUS_HASH")
    census=json.loads(census_raw)
    need(p["Base"]==census["selected"]+[p["ExistingAdditional"]] and
         p["New"]==census["pending"][:4],"RECENT_SELECTION")
    prior={x["symbol"]:x for x in census["universe"]}
    need(all(prior.get(n,{}).get("currentEnabled") is True for n in p["Base"]+p["New"]),
         "RECENT_PRIOR_ROSTER")
    windows=p["Windows"]
    need(len(windows)==5 and len({w["Id"] for w in windows})==5 and
         utc(windows[0]["From"])==eer.START and utc(windows[-1]["From"])==eer.END and
         all(a["To"]==b["From"] for a,b in zip(windows,windows[1:])) and
         all(0<utc(w["To"])-utc(w["From"])<=7*DAY for w in windows) and
         utc(windows[-1]["To"])<=int(time.time()*1000) and utc(p["WarmFrom"])==eer.WARM,
         "RECENT_WINDOW_CHRONOLOGY")
    return p,src.digest(raw)


def metadata_summary(p,digest,meta,rid):
    chosen=p["Base"]+p["New"]
    targets=[]
    states={}
    route_names=sorted({v["Symbol"] for route in meta["routes"].values() for v in route})
    for name in list(dict.fromkeys(chosen+route_names)):
        row=meta["roster"].get(name)
        if row is None or not row["enabled"]:
            states[name]="NOT_ENABLED_IN_AUTHENTIC_CURRENT_ROSTER"
            continue
        roles=[]
        if name in chosen:roles.append("ECONOMIC")
        if name in route_names:roles.append("CONVERSION")
        # Route legs need the overlap even when they are also existing markets.
        # Already captured base route history is retained rather than recollected.
        prior=name in p["Base"] or name in ("USDJPY",)
        windows=p["Windows"][-1:] if prior and name not in p["New"] else p["Windows"]
        for w in windows:
            targets.append(dict(symbol=name,symbolId=row["id"],window=w["Id"],
                roles=roles,bars=name in chosen,fromInclusive=utc(w["From"]),throughExclusive=utc(w["To"]),
                barFrom=utc(p["WarmFrom"]) if name in p["New"] and w==p["Windows"][0] else utc(w["From"])))
        states[name]="REGISTERED_PENDING_COLLECTION"
    return dict(runId=rid,protocolSha256=digest,chosen=chosen,states=states,
                currentRosterCount=len(meta["roster"]),currentTermsCount=len(meta["terms"]),
                marginCount=sum(bool(v) for v in meta["margin"].values()),routes=meta["routes"],
                chargeMinutes=eer.charge_clocks(meta["terms"]),partitions=targets,
                historicalTermsCertified=False,orders=0,cloudActivated=False)


def bars(journal,account,target,period):
    start,end=target["barFrom"],target["throughExclusive"]
    step=extension.DAYS_PER_PAGE[period]*DAY
    pending=deque((lo,min(lo+step,end)-1) for lo in range(start,end,step))
    values={}; counts=Counter()
    while pending:
        lo,hi=pending.popleft()
        q=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=target["symbolId"],
            period=e.ProtoOATrendbarPeriod.Value(period),fromTimestamp=lo,toTimestamp=hi)
        reply,at,status=journal.query(q)
        if reply is None:
            counts[status]+=1
            continue
        if extension.page_pair(q,reply) and reply.HasField("hasMore") and reply.hasMore and hi-lo>=2*src.PERIODS[period]*60000:
            pending.extendleft(reversed(src.split_window(lo,hi)))
            counts["PAGINATION_SPLIT"]+=1
            continue
        report,rows=history.inspect_bars(q,reply,at,closed_through=end)
        counts[report["status"]]+=1
        for row in rows:
            need(row[0] not in values,"RECENT_DUPLICATE_BAR")
            values[row[0]]=row
    return sorted(values.values()),dict(closedRows=len(values),statuses=dict(counts))


def collect(journal,account,p,target,charge_minutes,tick_sink=None,keep=False):
    name=target["symbol"]; sid=target["symbolId"]
    values={}; bar_report={}
    if target["bars"]:
        for period in src.PERIODS:
            rows,report=bars(journal,account,target,period)
            if keep:values[period]=rows
            bar_report[period]=report
    budget={side:[p["PerSidePageBudget"]] for side in (e.BID,e.ASK)}
    days=[]; quotes=[]; funding=[]
    tail={e.BID:[],e.ASK:[]}; tail_leaves={e.BID:[],e.ASK:[]}
    for day in range(target["fromInclusive"],target["throughExclusive"],DAY):
        sides={e.BID:[],e.ASK:[]}; leaves={e.BID:[],e.ASK:[]}
        for lo in range(day,day+DAY,p["PageHours"]*HOUR):
            hi=lo+p["PageHours"]*HOUR-1
            for side in sides:
                rows,pages=rollover.tick_window(journal.query,account,sid,side,lo,hi,budget[side])
                sides[side].extend(rows)
                leaves[side].extend(pages)
        for side in sides:
            sides[side].sort(key=lambda x:x[0])
            if tick_sink is not None:
                tick_sink(name,side,sides[side],[(a,b) for a,b,status,_,_ in leaves[side]
                    if status in ("VERIFIED_COMPLETE_PAGE","PROVIDER_NO_QUOTES")])
        daily_marks=[q for q in marks.minute_marks(day,sides[e.BID],sides[e.ASK],interval=eer.STEP)
            if all(eer.covered(leaves[s],max(day,q["At"]-30_000),q["At"]) for s in sides)]
        daily_funding=[]
        for minute in charge_minutes:
            at=day+minute*60_000; lo=at-2*HOUR
            q={"At":at,"RequestedCoverage":all(eer.covered(tail_leaves[s]+leaves[s],lo,at) for s in sides)}
            if q["RequestedCoverage"]:
                for side,label in ((e.BID,"Bid"),(e.ASK,"Ask")):
                    boundary=conditional.boundary([r for r in tail[side]+sides[side] if lo<=r[0]<=at],at,True)
                    if boundary and not boundary["conflict"]:
                        q[label+"At"]=boundary["at"]
                        q[label]=str(Decimal(boundary["rawPrices"][0]).scaleb(-5))
            daily_funding.append(q)
        if keep:
            quotes.extend(daily_marks)
            funding.extend(daily_funding)
        days.append(dict(day=day,monetaryMarks=len(daily_marks),fundingMarks=sum(
            "Bid" in q and "Ask" in q for q in daily_funding),
            sides={e.ProtoOAQuoteType.Name(s):dict(rows=len(sides[s]),
                coverage=eer.covered(leaves[s],day,day+DAY-1),
                statuses=dict(Counter(x[2] for x in leaves[s]))) for s in sides}))
        for s in sides:
            tail[s]=[x for x in sides[s] if x[0]>=day+DAY-2*HOUR]
            tail_leaves[s]=[x for x in leaves[s] if x[1]>=day+DAY-2*HOUR]
        print("RECENT_SOURCE_DAY",name,target["window"],day,len(daily_marks),flush=True)
    report=dict(target=target,barCoverage=bar_report,days=days,
        monetaryMarks=sum(x["monetaryMarks"] for x in days),
        fundingMarks=sum(x["fundingMarks"] for x in days),
        historicalTariffContinuityCertified=False,orders=0,cloudActivated=False)
    return report,values,quotes,funding


def metadata_readback(p,digest,key,rid):
    receipt=json.loads((META/"receipt.json").read_bytes())
    payload=eer.unpack(META,receipt["sealed"],key,rid)
    need(payload["runId"]==rid and payload["protocolSha256"]==digest and payload["packets"],"RECENT_METADATA_SCOPE")
    account=src.decode(payload["packets"][0]["reqType"],payload["packets"][0]["req"]).ctidTraderAccountId
    meta=eer.metadata_read(payload["packets"],p["Base"]+p["New"],account)
    summary=metadata_summary(p,digest,meta,rid)
    need(summary==receipt["summary"],"RECENT_METADATA_PARITY")
    return receipt,meta,account


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("stage",choices=("plan","metadata","verify-metadata","capture","verify"))
    cli.add_argument("--index",type=int)
    args=cli.parse_args()
    p,digest=registered()
    if args.stage=="plan":
        print(p["Study"],digest,p["Base"],p["New"])
        return
    rid=os.environ["GITHUB_RUN_ID"]
    capture=args.stage in ("metadata","capture")
    if capture:
        need(os.environ["GITHUB_EVENT_NAME"]=="push" and os.environ["GITHUB_REF"]=="refs/heads/main" and
             os.environ["GITHUB_RUN_ATTEMPT"]=="1","RECENT_READ_ONLY_SCOPE")
        recipient=checked_public(Path("new-recipient-output"),rid)
    else:
        key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    if args.stage=="metadata":
        t=wire.OfficialEvidenceTransport()
        try:
            account=authenticate(t);t.bind(account)
            meta=eer.metadata(t,account,p["Base"]+p["New"],None)
            summary=metadata_summary(p,digest,meta,rid)
            META.mkdir(exist_ok=False)
            sealed=eer.seal(META/"metadata.sealed",dict(runId=rid,protocolSha256=digest,packets=t.journal),recipient,rid)
            (META/"receipt.json").write_bytes(src.canonical(dict(summary=summary,sealed=sealed)))
        finally:
            t.close()
        return
    if args.stage=="verify-metadata":
        receipt,_,_=metadata_readback(p,digest,key,rid)
        Path("recent-plan.json").write_bytes(src.canonical(receipt["summary"]))
        with open(os.environ["GITHUB_OUTPUT"],"a") as output:
            output.write("partitions="+json.dumps(list(range(len(receipt["summary"]["partitions"]))),separators=(",",":"))+"\n")
        return
    summary=json.loads(Path("recent-plan.json").read_bytes())
    need(summary["runId"]==rid and summary["protocolSha256"]==digest and
         args.index is not None and 0<=args.index<len(summary["partitions"]),"RECENT_PARTITION_SCOPE")
    target=summary["partitions"][args.index]
    if args.stage=="capture":
        t=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(t)
            need(src.original_account(account),"RECENT_ACCOUNT")
            src.MAX_REQUESTS=p["PerPartitionMaxRequests"]
            journal=src.Journal(t,account)
            journal.deadline=time.monotonic()+p["PerPartitionSeconds"]
            report,_,_,_=collect(journal,account,p,target,summary["chargeMinutes"])
        finally:
            t.close()
        report.update(runId=rid,protocolSha256=digest,index=args.index,requests=len(journal.packets))
        OUT.mkdir(exist_ok=False)
        sealed=eer.seal(OUT/"packets.sealed",dict(report=report,packets=journal.packets),recipient,rid)
        (OUT/"receipt.json").write_bytes(src.canonical(dict(report=report,sealed=sealed)))
        return
    receipt=json.loads((OUT/"receipt.json").read_bytes())
    payload=eer.unpack(OUT,receipt["sealed"],key,rid)
    packets=payload["packets"]
    need(bool(packets),"RECENT_NO_REQUESTS")
    account=src.decode(packets[0]["reqType"],packets[0]["req"]).ctidTraderAccountId
    need(src.original_account(account),"RECENT_ACCOUNT")
    j=src.ReadbackJournal(packets)
    report,_,_,_=collect(j,account,p,target,summary["chargeMinutes"])
    report.update(runId=rid,protocolSha256=digest,index=args.index,requests=len(packets))
    need(j.index==len(packets) and report==payload["report"]==receipt["report"],"RECENT_PACKET_PARITY")
    Path("recent-verified.json").write_bytes(src.canonical(dict(report=report,sealed=receipt["sealed"],
        packetsReconciled=j.index,readbackBrokerRequests=0)))


if __name__=="__main__":
    main()
