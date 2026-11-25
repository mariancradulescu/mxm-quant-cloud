"""Protected EER1 archive reuse and execution of the common C# portfolio."""
import json, os, sys, tempfile, subprocess
from pathlib import Path
from collections import defaultdict
from . import owner_eer1_source as eer
from . import owner_official_eur_source as wire
from . import owner_source_history_use as history
from . import source_history_universe as src
from . import integrated_market_readback as normalized
from . import v32_unified_source_adapter as annual
from . import owner_eur_gap_evidence as gap
from . import closed_market_context_readback as context
from . import integrated_market_source as integrated
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .custody import unseal_new
from .decode import need

OUT=Path("eer1-economic-public")

def read_archives(key,work):
    bars=defaultdict(lambda:defaultdict(dict)); conflicts=set(); counts=defaultdict(int)
    def add(name,tf,rows):
        width=src.PERIODS[tf]*60000
        for b in rows:
            if isinstance(b,dict):
                at=b["OpenAt"]; row=dict(b,CloseAt=b.get("CloseAt",at+width))
            else:
                at=b[0];row=normalized.normalized_bars([b])[0]
            if row["CloseAt"]>eer.END:continue
            k=(name,tf,at)
            if k in conflicts:continue
            old=bars[name][tf].get(at)
            if old is not None:
                from decimal import Decimal
                if any(Decimal(str(old[f]))!=Decimal(str(row[f])) for f in ("Open","High","Low","Close","TickVolume")) or old["CloseAt"]!=row["CloseAt"]:
                    conflicts.add(k);bars[name][tf].pop(at);continue
            bars[name][tf][at]=row
    path=work/"annual.json"
    proof=annual.execute(path)
    data=json.loads(path.read_bytes());path.unlink()
    for market in data["Markets"]:
        for tf,rows in market["Bars"].items():add(market["Symbol"],tf,rows)
    del data
    packets,receipt=history.verified_original(Path("original-source-history"),key)
    _,_,tape=history.extract(packets,receipt)
    ext,_=wire.extension_history(key)
    for archive in (tape,ext):
        for market in archive["Markets"]:
            for tf,rows in market["Bars"].items():add(market["Symbol"],tf,rows)
    # Already independently verified protected gap/rollover packets. Preserve
    # actual closed bar values rather than treat matrix clocks as a price tape.
    ids={r["symbolId"]:r["name"] for r in wire.public_original()["contractRoster"]}
    for folder,run,field in ((Path("prior-gap"),"45541671931","historical"),(Path("prior-rollover"),"45549613144","barPackets")):
        receipt=json.loads((folder/"receipt.json").read_bytes());cipher=(folder/"original.sealed").read_bytes()
        need(receipt["runId"]==run and src.digest(cipher)==receipt["ciphertextSha256"],"EER1_ARCHIVE_CIPHER")
        raw=unseal_new(cipher,key,run)
        need(src.digest(raw)==receipt["plaintextSha256"],"EER1_ARCHIVE_PLAIN")
        data=json.loads(raw);need(data["runId"]==run,"EER1_ARCHIVE_RUN")
        for packet in data[field]:
            if not packet["res"]:continue
            q=src.decode(packet["reqType"],packet["req"]);a=src.decode(packet["resType"],packet["res"])
            need(src.original_account(q.ctidTraderAccountId),"EER1_ARCHIVE_ACCOUNT")
            if type(a) is not m.ProtoOAGetTrendbarsRes or a.hasMore:continue
            tf=e.ProtoOATrendbarPeriod.Name(q.period)
            _,rows=history.inspect_bars(q,a,packet["availableAt"],closed_through=eer.END)
            add(ids[q.symbolId],tf,rows)
    return bars,add,conflicts,proof

def main():
    run=os.environ["GITHUB_RUN_ID"]
    key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    receipt=json.loads((eer.OUT/"receipt.json").read_bytes())
    need(receipt["runId"]==run and receipt["protocolSha256"]==src.digest(eer.PROTOCOL.read_bytes()) and receipt["matrixSha256"]==eer.MATRIX_SHA,"EER1_READBACK_SCOPE")
    mat=eer.matrix();chosen,pending=eer.selection(mat,wire.public_original())
    need(receipt["selected"]==chosen and receipt["pending"]==pending,"EER1_SELECTION_BINDING")
    original=eer.unpack(eer.OUT,receipt["metadata"],key,run)
    need(original["runId"]==run and original["chosen"]==chosen,"EER1_METADATA_BINDING")
    account=src.decode(original["packets"][0]["reqType"],original["packets"][0]["req"]).ctidTraderAccountId
    meta=eer.metadata_read(original["packets"],chosen,account)
    source_acquired=max(p["at"] for p in original["packets"])
    rows={x["symbol"]:x for x in mat["matrix"]}
    OUT.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="eer1-custody-") as temp:
        work=Path(temp);bars,add,conflicts,proof=read_archives(key,work)
        # Recover the already observed 21-day full-session quote tape,
        # including the authenticated multiframe supplement; no recollection.
        archived,extra=context.sources(key,"44733062339",native_boundaries=True)
        old_quotes={}
        for m in archived:
            n=m["Name"]
            for tf in ("M5","M15","H1"):add(n,tf,m[tf])
            for tf,b in m["AdditionalTimeframes"].items():add(n,tf,b["Bars"])
            old_quotes[n]=[q for q in m["Quotes"] if q["At"]%eer.STEP==15000]
        del archived
        rollover=json.loads(Path("pilot-source/rollover-values.json").read_bytes())
        pilot_receipt=json.loads(Path("pilot-source/receipt.json").read_bytes())
        need(src.digest(Path("pilot-source/rollover-values.json").read_bytes())==pilot_receipt["rolloverValuesSha256"],"EER1_PRIOR_ROLLOVER_HASH")
        old_funding=defaultdict(dict)
        from decimal import Decimal
        for w in rollover["windows"]:
            at=w["rollover"];q={"At":at,"RequestedCoverage":all(x["complete"] for x in w["sides"].values())}
            for side in ("BID","ASK"):
                b=w["sides"][side]["lastBefore"]
                if b and not b["conflict"]:
                    q[side.title()+"At"]=b["at"];q[side.title()]=str(Decimal(b["rawPrices"][0]).scaleb(-5))
            old_funding[w["symbol"]][at]=q
        tapes=[];source_notes={}
        for ref in receipt["sources"]:
            data=eer.unpack(eer.OUT,ref,key,run)
            name=ref["name"];sid=ref["id"]
            need(data["runId"]==run and data["name"]==name and data["id"]==sid and meta["roster"][name]["id"]==sid and name in meta["sourceNames"],"EER1_SHARD_BINDING")
            j=src.ReadbackJournal(data["packets"])
            summary,series,quotes,funding=eer.collect_market(j,account,sid,rows.get(name,{}),name in chosen,eer.charge_clocks(meta["terms"]),True,name)
            need(summary==ref["summary"]==data["summary"] and j.index==len(j.packets)==ref["requests"],"EER1_SHARD_REPLAY")
            for tf,values in series.items():add(name,tf,values.values())
            if j.packets:source_acquired=max(source_acquired,max(p["availableAt"] for p in j.packets))
            original_quotes=old_quotes.get(name,[])
            qmap={q["At"]:q for q in original_quotes}
            for q in quotes:
                need(q["At"] not in qmap,"EER1_REPEATED_QUOTE_CLOCK")
                qmap[q["At"]]=q
            fmap={q["At"]:q for q in funding}
            fmap.update(old_funding.get(name,{}))
            tapes.append(dict(Name=name,Quotes=sorted(qmap.values(),key=lambda q:q["At"]),
                FundingQuotes=sorted(fmap.values(),key=lambda q:q["At"])))
            source_notes[name]=dict(requests=len(j.packets),newMarks=len(quotes),reusedMarks=len(original_quotes),marks=len(qmap),fundingMarks=len(fmap),
                completeRoots=sum(w[2]["complete"] for w in summary["tickWindows"]),barCells=summary["bars"])
            print("EER1_SHARD_VERIFIED",name,len(quotes),flush=True)
        # Archived observations remain available even if a new tranche shard
        # was not reached. They are not called newly collected.
        for name,quotes in old_quotes.items():
            if name in meta["sourceNames"] and name not in {x["Name"] for x in tapes}:
                tapes.append(dict(Name=name,Quotes=quotes,FundingQuotes=list(old_funding.get(name,{}).values())))
                source_notes[name]=dict(requests=0,newMarks=0,reusedMarks=len(quotes),marks=len(quotes),fundingMarks=len(old_funding.get(name,{})))
        tape_names={x["Name"] for x in tapes}
        markets=[];eligibility={}
        for name in chosen:
            info=meta["info"].get(name);t=meta["terms"].get(name)
            reason=[]
            if name not in meta["roster"]:reason.append("NOT_IN_CURRENT_OFFICIAL_ROSTER")
            elif not meta["roster"][name]["enabled"]:reason.append("DISABLED_AT_CAPTURE")
            if t is None or info is None:reason.append("CONTRACT_NOT_OBSERVED_OR_UNSUPPORTED")
            elif info["tradingMode"]!=0:reason.append("TRADING_MODE_RESTRICTED_AT_CAPTURE")
            if name not in tape_names:reason.append("SOURCE_PENDING_OR_NOT_CAPTURED")
            if not meta["margin"].get(name):reason.append("MARGIN_NOT_OBSERVED")
            if meta["schedules"].get(name) is None:reason.append("SCHEDULE_NOT_OBSERVED_OR_UNSUPPORTED")
            if t is not None and t["QuoteAsset"] not in meta["routes"]:reason.append("OFFICIAL_CONVERSION_ROUTE_MISSING")
            eligibility[name]=reason
            # Keep all observations; per-clock C# eligibility remains causal.
            if t is None or info is None:continue
            contract=dict(t,ObservedAtUtcMs=eer.START-1)
            volume=meta["margin"].get(name,[])
            def series(tf):return [v for _,v in sorted(bars[name][tf].items())]
            market=dict(Name=name,Class=meta["roster"][name]["assetClass"] or "UNMAPPED",
                OfficialAssetClass=meta["roster"][name]["assetClass"],Contract=contract,TickSize="0.00001",
                ShortAllowed=info["shortAllowed"],TradingMode=info["tradingMode"] if info["tradingMode"] is not None else -1,
                CostTermsComplete=True,Margin=volume,M5=series("M5"),M15=series("M15"),H1=series("H1"),Quotes=[],
                ActiveHours=0,RequestedTickHours=0,Schedule=[],ScheduleTimeZone=info["fields"].get("scheduleTimeZone",""),
                Protection=None,EnabledAtCapture=meta["roster"][name]["enabled"],
                AdditionalTimeframes={tf:dict(Source="AUTHENTIC_CUSTODY_UNION",Bars=series(tf)) for tf in ("M1","M30","H4","D1")},
                DatedDevelopment=dict(Contract=contract,Margin=volume,ShortAllowed=info["shortAllowed"],
                    TradingMode=info["tradingMode"] if info["tradingMode"] is not None else -1,
                    AccountSwapFree=meta["accountSwapFree"],Digest=info["digest"],SourceRun=run,AccountType=meta["accountType"],
                    MoneyDigits=meta["moneyDigits"],PriceDigits=info["priceDigits"]))
            # TickSize is not used by the EER1 execution model; preserve the
            # broker field where present and refuse to invent it otherwise.
            market["TickSize"]=str(10**(-info["priceDigits"])) if info["priceDigits"] is not None else "0"
            markets.append(dict(Market=market,TermsAcquiredAt=meta["actual"][name],ScheduledClocks=meta["schedules"].get(name)))
        census=dict(sourceRun=run,priorMatrixSha256=eer.MATRIX_SHA,officialRosterCount=len(meta["roster"]),
            historicalMarkets=sum(any(v.values()) for v in bars.values()),archiveProof=proof,integratedFullSessionReused="44687919474",conflictingBarClocks=len(conflicts),
            historicalCoverage={n:{tf:len(v) for tf,v in b.items()} for n,b in bars.items()},
            selected=chosen,pending=pending,eligibility=eligibility,sourceNotes=source_notes,
            orders=0,cloudActivated=False)
        (OUT/"source-census.json").write_bytes(src.canonical(census))
        if len([x for x in markets if x["Market"]["Name"] in tape_names])<2:
            print("EER1_FEWER_THAN_TWO_CAPTURED_MARKETS",flush=True);return
        path=work/"native-input.json"
        payload=dict(Start=eer.START,FitEnd=eer.FIT_END,End=eer.END,ProtocolSha256=receipt["protocolSha256"],
            EngineRevision=os.environ["GITHUB_SHA"],SourceAcquiredAt=source_acquired,Markets=markets,Tapes=tapes,Routes=meta["routes"])
        path.write_bytes(src.canonical(payload));path.chmod(0o600)
        env={k:v for k,v in os.environ.items() if k!="R3_CUSTODY_PRIVATE_KEY_PEM"}
        subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll","--owner-eer1-extended",
            str(path),str(OUT/"economic.json"),str(OUT)],check=True,env=env)
        (OUT/"receipt.json").write_bytes(src.canonical(dict(inputSha256=src.digest(path.read_bytes()),
            engineRevision=os.environ["GITHUB_SHA"],protocolSha256=receipt["protocolSha256"],
            economicSha256=src.digest((OUT/"economic.json").read_bytes()),sourceAcquiredAt=source_acquired,
            calibrationHashes={p.name:src.digest(p.read_bytes()) for p in OUT.glob("*-calibration.json")},
            originalPilotRun="45552716026",originalPilotReplayed=False,orders=0,cloudActivated=False,
            independentConfirmation=False,brokerNetCertified=False)))
    print("EER1_NATIVE_EXTENDED_PUBLISHED",flush=True)

if __name__=="__main__":main()
