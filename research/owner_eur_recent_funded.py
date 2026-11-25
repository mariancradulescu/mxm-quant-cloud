"""Bind completed recent official packets to the existing funded native Replay.

The new study is development-exposed. Existing dated contract scenarios remain
unchanged for prior markets; additional contracts use their authenticated
current snapshot as a conditional historical scenario. Raw sources remain in
private custody; no broker requests occur during materialization.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
import os
from pathlib import Path

from . import owner_eur_recent_continuous as recent
from . import owner_eur_authentic_expansion as expansion
from . import owner_eer1_readback as readback
from . import owner_eer1_source as eer
from . import integrated_market_readback as marks
from . import source_history_universe as src
from .decode import need
from .official_symbol_calendar import build_clock_grid

REGISTRY=Path("research/eur_recent_funded_1.json")
OLD_REGISTRY=Path("research/eur_authentic_expansion_1.json")


def numeric_equal(a,b,fields):
    return all(Decimal(str(a[f]))==Decimal(str(b[f])) for f in fields)


def merge_bars(old,new):
    by_at={b["OpenAt"]:b for b in old}
    conflicts=set()
    for b in new:
        at=b["OpenAt"]
        if at in conflicts:continue
        if at in by_at and not numeric_equal(by_at[at],b,
                ("CloseAt","Open","High","Low","Close","TickVolume")):
            by_at.pop(at)
            conflicts.add(at)
        else:by_at[at]=b
    return sorted(by_at.values(),key=lambda b:b["OpenAt"]),len(conflicts)


def merge_quotes(old,new,funding=False):
    by_at={q["At"]:q for q in old}
    conflicts=set()
    for q in new:
        at=q["At"]
        if at in conflicts:continue
        previous=by_at.get(at)
        if previous is None:
            by_at[at]=q
            continue
        def complete(v):return all(v.get(k) is not None for k in ("Bid","Ask","BidAt","AskAt")) and (
            not funding or v.get("RequestedCoverage") is True)
        if complete(previous) and complete(q):
            if not numeric_equal(previous,q,("BidAt","AskAt","Bid","Ask")):
                by_at.pop(at);conflicts.add(at)
            # Preserve already authenticated path record if same mark.
        elif complete(q):
            by_at[at]=q
        elif not complete(previous):
            # Missing is never transformed into a quote.
            by_at[at]=previous
    return sorted(by_at.values(),key=lambda q:q["At"]),len(conflicts)


def read_new(plan,digest,key,rid,work):
    receipt,meta,account=recent.metadata_readback(plan,digest,key,rid)
    summary=receipt["summary"]
    need(json.loads(Path("recent-plan.json").read_bytes())==summary,"RECENT_FUNDED_PLAN_PARITY")
    public=json.loads(Path("recent-source-summary.json").read_bytes())
    need(public["protocolSha256"]==digest and not public["pending"] and
        public["planned"]==public["verified"]==len(summary["partitions"]) and
        public["orders"]==0 and not public["cloudActivated"],"RECENT_FUNDED_COMPLETE_SOURCE")
    public_rows={x["report"]["index"]:x for x in public["receipts"]}
    need(len(public_rows)==len(summary["partitions"]),"RECENT_FUNDED_RECEIPT_SET")
    sink=readback.protection_tick_sink(work/"verified-protection","eer1")
    values=defaultdict(lambda:defaultdict(list)); quotes=defaultdict(list); funding=defaultdict(list)
    acquired=max(meta["actual"].values())
    receipts=[]
    for index,target in enumerate(summary["partitions"]):
        folder=Path("recent-protected")/f"recent-source-protected-{index}"
        row=json.loads((folder/"receipt.json").read_bytes())
        proof=json.loads((Path("recent-verified")/f"recent-source-verified-{index}"/"recent-verified.json").read_bytes())
        need(proof==public_rows[index] and proof["sealed"]==row["sealed"] and proof["report"]==row["report"],
             "RECENT_FUNDED_PUBLIC_RECEIPT")
        payload=eer.unpack(folder,row["sealed"],key,rid)
        packets=payload["packets"]
        need(bool(packets) and all(src.decode(x["reqType"],x["req"]).ctidTraderAccountId==account
             for x in packets),"RECENT_FUNDED_ACCOUNT")
        journal=src.ReadbackJournal(packets)
        report,bars,q,f=recent.collect(journal,account,plan,target,summary["chargeMinutes"],tick_sink=sink,keep=True)
        report.update(runId=rid,protocolSha256=digest,index=index,requests=len(packets))
        need(journal.index==len(packets)==proof["packetsReconciled"] and report==row["report"]==payload["report"],
            "RECENT_FUNDED_PACKET_PARITY")
        name=target["symbol"]
        for tf,series in bars.items():values[name][tf].extend(marks.normalized_bars(series))
        quotes[name].extend(q);funding[name].extend(f)
        acquired=max(acquired,max(x["availableAt"] for x in packets))
        receipts.append(dict(index=index,target=target,sealed=row["sealed"],requests=len(packets),
            marks=len(q),fundingMarks=report["fundingMarks"],barCoverage=report["barCoverage"]))
    return meta,values,quotes,funding,acquired,receipt,receipts


def materialize(work,public_path):
    registered_raw=REGISTRY.read_bytes()
    study=json.loads(registered_raw)
    rid=str(study["SourceRun"])
    p,digest=recent.registered()
    key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    # Reuse the previously authenticated 16-market book and AAPL.US lane.
    source,old_proof=expansion.breadth(json.loads(OLD_REGISTRY.read_bytes()),key,work)
    base_names=[m["Market"]["Name"] for m in source["Markets"]]
    need(set(base_names)==set(p["Base"]),"RECENT_FUNDED_BASE_UNIVERSE")
    meta,bars,quotes,funding,acquired,receipt,partitions=read_new(p,digest,key,rid,work)
    prior_end=source["End"]
    end=recent.utc(p["Windows"][-1]["To"])
    need(prior_end==recent.utc(p["Windows"][-1]["From"]) and study["TestBoundaries"][-1]==end,
         "RECENT_FUNDED_CONTINUITY")
    old={m["Market"]["Name"]:m for m in source["Markets"]}
    # New markets never displace any of the seventeen original markets.
    missing={}
    for name in p["New"]:
        info=meta["info"].get(name);terms=meta["terms"].get(name)
        if info is None or terms is None:
            missing[name]="CURRENT_OFFICIAL_TERMS_NOT_VERIFIED"
            continue
        row=meta["roster"][name]
        margin=meta["margin"].get(name,[])
        m=dict(Name=name,Class=row["assetClass"] or "UNMAPPED",OfficialAssetClass=row["assetClass"],
            Contract=terms,Margin=margin,TickSize=str(Decimal(1).scaleb(-info["priceDigits"])) if info["priceDigits"] is not None else "0",
            Quotes=[],M5=[],M15=[],H1=[],ShortAllowed=info["shortAllowed"],TradingMode=info["tradingMode"],
            CostTermsComplete=True,EnabledAtCapture=row["enabled"],AdditionalTimeframes={})
        entry=expansion.dated_market(name,m,terms,info,meta,margin,source["Start"],end,rid)
        source["Markets"].append(entry);old[name]=entry
    counts={};calendar_status={}
    for name,entry in old.items():
        m=entry["Market"]; counts[name]={}
        for tf in src.PERIODS:
            if tf in ("M5","M15","H1"):
                m[tf],conflicts=merge_bars(m.get(tf,[]),bars[name][tf])
                count=len(m[tf])
            else:
                prior=m.setdefault("AdditionalTimeframes",{}).get(tf,{})
                merged,conflicts=merge_bars(prior.get("Bars",[]),bars[name][tf])
                m["AdditionalTimeframes"][tf]=dict(Source="AUTHENTIC_RECENT_CUSTODY_UNION",Bars=merged)
                count=len(merged)
            counts[name][tf]=dict(rows=count,conflictingClocks=conflicts)
        if name in p["Base"]:
            # Before the extension, retain the original calendar scenario.
            info=meta["info"].get(name)
            if info is not None:
                grid=build_clock_grid(info["fields"],prior_end,end+7*recent.DAY)
                for field,grid_key in (("ScheduledClocks","openClocks"),("AmbiguousCalendarClocks","ambiguousClocks")):
                    previous=entry.get(field)
                    latest=grid[grid_key]
                    # If either interval is unknown, do not manufacture clocks.
                    if previous is None or latest is None:
                        entry[field]=None
                    else:
                        entry[field]=sorted(set(x for x in previous if x<prior_end)|set(latest))
                calendar_status[name]=grid["status"]
            else:
                entry["ScheduledClocks"]=[x for x in entry.get("ScheduledClocks") or [] if x<prior_end]
                entry["AmbiguousCalendarClocks"]=[x for x in entry.get("AmbiguousCalendarClocks") or [] if x<prior_end]
                calendar_status[name]="RECENT_CALENDAR_NOT_VERIFIED"
    tape={t["Name"]:t for t in source["Tapes"]}
    quote_counts={}
    for name in sorted(set(quotes)|set(funding)):
        t=tape.setdefault(name,dict(Name=name,Quotes=[],FundingQuotes=[]))
        t["Quotes"],conflicts=merge_quotes(t["Quotes"],quotes[name])
        t["FundingQuotes"],fund_conflicts=merge_quotes(t["FundingQuotes"],funding[name],funding=True)
        quote_counts[name]=dict(newMarks=len(quotes[name]),totalMarks=len(t["Quotes"]),conflictingClocks=conflicts,
            conflictingFundingClocks=fund_conflicts)
    source["Tapes"]=list(tape.values())
    # The prior route remains the scenario for previously represented assets;
    # add official routes for new assets without rewriting historic routes.
    route_differences={asset:route for asset,route in meta["routes"].items()
                       if asset in source["Routes"] and source["Routes"][asset]!=route}
    for asset,route in meta["routes"].items():source["Routes"].setdefault(asset,route)
    proof=dict(PriorBreadth=old_proof,RecentRun=rid,RecentProtocolSha256=digest,
        RecentMetadata=receipt["sealed"],Partitions=partitions,BarCoverage=counts,QuoteCoverage=quote_counts,
        MissingNewMarkets=missing,RecentCalendarStatus=calendar_status,CurrentRouteDifferences=route_differences,
        MarketCount=len(source["Markets"]),PriorMarketCount=len(base_names),
        TermsBasis="ORIGINAL_CURRENT_TERMS_FOR_BASE_AND_NEW_CURRENT_TERMS_FOR_ADDITIONS_CONDITIONAL_NO_TARIFF_CERTIFICATION")
    source["End"]=end
    source["SourceAcquiredAt"]=max(source["SourceAcquiredAt"],acquired)
    source["ProtocolSha256"]=src.digest(registered_raw)
    source["EvidenceManifestSha256"]=src.digest(src.canonical(proof))
    protocol={k:v for k,v in study.items() if k not in ("SourceRun","SourceRevision")}
    protocol.update(SourceProtocolSha256=source["ProtocolSha256"],EvidenceManifestSha256=source["EvidenceManifestSha256"])
    source_bytes=src.canonical(source); protocol_bytes=src.canonical(protocol)
    (work/"source.json").write_bytes(source_bytes)
    (work/"protocol.json").write_bytes(protocol_bytes)
    (work/"protocol.json").chmod(0o600)
    public_path.write_bytes(src.canonical(dict(Study=study["Study"],SourceSha256=src.digest(source_bytes),
        ProtocolSha256=src.digest(protocol_bytes),EvidenceManifestSha256=source["EvidenceManifestSha256"],
        Proof=proof,SourceBrokerRequests=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False)))
    print("RECENT_FUNDED_MATERIALIZED",len(source["Markets"]),len(partitions),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("work",type=Path)
    p.add_argument("public",type=Path)
    args=p.parse_args()
    materialize(args.work,args.public)
