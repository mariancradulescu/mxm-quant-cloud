"""Comparative causal mechanisms on the preserved authentic recent archive.

Only missing financing marks are requested. Raw packets and active source tapes
stay encrypted in existing custody. Present contract terms remain conditional.
"""
import argparse
from bisect import bisect_left
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path

from . import owner_eur_archive_funding_2 as previous
from . import owner_eur_recent_archive as archive
from . import owner_eer1_source as eer
from . import source_history_universe as src
from . import owner_official_eur_source as wire
from .ctrader_proto import OpenApiMessages_pb2 as m
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate

REGISTRY=Path("research/economic_mechanisms_1.json")
OUT=Path("mechanism-funding")
OLD_RUN="45759378427"
DAY=86_400_000

def canonical(value):return src.canonical(value)
def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    need(p["Study"]=="ECONOMIC_MECHANISMS_1" and p["OriginalEconomicArtifact"]==15090893748 and
         p["Orders"]==0 and p["CloudActivated"] is p["IndependentConfirmationCertified"] is False,
         "MECHANISM_REGISTRATION")
    return p,src.digest(raw)

def original(work,receipt):
    p,digest=previous.registered()
    previous.materialize(p,digest,work,receipt,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),OLD_RUN)

def valid_mark(q,at,both):
    if not q or q.get("RequestedCoverage") is not True:return False
    for side in ("Bid","Ask") if both else ("Bid",):
        if q.get(side) is None or Decimal(str(q[side]))<=0 or not 0<q.get(side+"At",0)<=at or at-q[side+"At"]>7200000:
            return False
    return not both or Decimal(str(q["Ask"]))>=Decimal(str(q["Bid"]))

def closed_session_mark(entry,tape,at):
    if at not in set(entry.get("ClosedRolloverClocks",[])):return None
    clocks=entry.get("ScheduledClocks") or []
    i=bisect_left(clocks,at)
    if i==0 or i<len(clocks) and clocks[i]==at:return None
    prior=clocks[i-1]
    if any(prior<=x<=at for x in entry.get("AmbiguousCalendarClocks") or []):return None
    q=next((q for q in tape["Quotes"] if q["At"]==prior),None)
    if not q:return None
    return dict(q,RequestedCoverage=True) if valid_mark(dict(q,RequestedCoverage=True),prior,True) and \
        prior-q["BidAt"]<=30000 and prior-q["AskAt"]<=30000 else None

def financing_plan(source):
    entries={x["Market"]["Name"]:x for x in source["Markets"]}
    tapes={x["Name"]:x for x in source["Tapes"]}
    indexed={name:{q["At"]:q for q in tape["FundingQuotes"]} for name,tape in tapes.items()}
    targets=set();audits=[]
    for name,entry in entries.items():
        terms=entry["Market"]["DatedDevelopment"];c=terms["Contract"]
        minute=c.get("SwapTimeUtcMinute")
        if not (c.get("SwapPeriodHours")==24 and isinstance(c.get("ChargeSwapAtWeekends"),bool) and
                terms.get("AccountSwapFree") is False and c.get("SkipSwapPeriods") is not None and
                isinstance(minute,int) and 0<=minute<1440):
            audits.append(dict(Symbol=name,Status="CONTRACT_SCHEDULE_UNRESOLVED",Requirements=[]))
            continue # Preserve the exact gap; common C# guards decide this market.
        # All eligible clocks are audited preventively, regardless of old trades.
        # Skip periods depend on entry time; collecting this superset is safe.
        for day in range(source["Start"],source["End"],DAY):
            at=day+minute*60000
            if not c["ChargeSwapAtWeekends"] and datetime.fromtimestamp(at/1000,timezone.utc).weekday()>=5:continue
            if all(c.get(k) is not None and Decimal(str(c[k]))==0 for k in ("LongSwap","ShortSwap")):continue
            needs=[(name,False)] if c["SwapCalculationType"]==1 else []
            currency=c["QuoteAsset"]
            if currency!="EUR" and currency not in source["Routes"]:
                audits.append(dict(Symbol=name,ChargeAt=at,Status="CONVERSION_ROUTE_UNCOLLECTED",Requirements=[]))
                continue
            needs += [(hop["Symbol"],True) for hop in source["Routes"].get(currency,[])]
            status=[]
            for symbol,both in needs:
                if valid_mark(indexed[symbol].get(at),at,both):state="AUTHENTIC_ROLLOVER_MARK"
                elif closed_session_mark(entries[symbol],tapes[symbol],at):state="CONDITIONAL_VERIFIED_CLOSED_SESSION_MARK"
                else:targets.add((symbol,at));state="TARGETED_RECOVERY_REQUIRED"
                status.append(dict(Symbol=symbol,Role="FX_BOTH_SIDES" if both else "PERCENTAGE_SWAP_BID",Status=state))
            audits.append(dict(Symbol=name,ChargeAt=at,Requirements=status))
    return dict(Targets=[dict(Symbol=n,At=t) for n,t in sorted(targets)],Audit=audits,
                LookbackMs=7200000,PageBudgetPerSide=64,Orders=0,CloudActivated=False)

def asset_classes(journal,account,ids):
    def read(q,kind):
        r,_,_=journal.query(q);need(type(r) is kind,"MECHANISM_OFFICIAL_CLASS_RESPONSE");return r
    symbols=read(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
    categories=read(m.ProtoOASymbolCategoryListReq(ctidTraderAccountId=account),m.ProtoOASymbolCategoryListRes)
    classes=read(m.ProtoOAAssetClassListReq(ctidTraderAccountId=account),m.ProtoOAAssetClassListRes)
    roster={s.symbolName:s for s in symbols.symbol};cats={c.id:c.assetClassId for c in categories.symbolCategory}
    names={c.id:c.name for c in classes.assetClass}
    need(all(n in roster and roster[n].symbolId==sid for n,sid in ids.items()),"MECHANISM_ORIGINAL_SYMBOL_ID")
    return {n:names.get(cats.get(roster[n].symbolCategoryId)) for n in ids}

class ClassJournal(src.Journal):
    def query(self,q):
        if type(q) not in (m.ProtoOASymbolCategoryListReq,m.ProtoOAAssetClassListReq):
            return super().query(q)
        # Reuse the existing account-bound official metadata transport. Its
        # outbound guard authorizes these two documented read-only operations.
        need(q.ctidTraderAccountId==self.account and self.t.bound==self.account,"MECHANISM_CLASS_ACCOUNT")
        response=self.t.read(q,wire.EXTRA[type(q)],"mechanism-official-class")
        packet=self.t.journal[-1]
        self.packets.append(dict(reqType=packet['reqType'],req=packet['req'],resType=packet['resType'],
            res=packet['res'],requestAt=packet['sent'],availableAt=packet['at']))
        return response,packet['at'],src.ATTEMPTED

def capture(plan,digest):
    rid=os.environ["GITHUB_RUN_ID"]
    ids=previous.plan_ids(dict(Targets=[dict(Symbol=n) for n in plan["Instruments"]]))
    target=json.loads(Path("funding-plan.json").read_bytes())
    need(target["RegistrySha256"]==digest,"MECHANISM_FUNDING_PLAN_BINDING")
    t=wire.OfficialEvidenceTransport()
    try:
        account=authenticate(t);need(src.original_account(account),"MECHANISM_ACCOUNT")
        t.bind(account)
        journal=ClassJournal(t,account)
        classes=asset_classes(journal,account,ids)
        packets=list(journal.packets);rows=[]
        for i,item in enumerate(target['Targets']):
            # A fresh bounded read journal per exact missing window prevents a
            # tranche-wide administrative request ceiling from skipping later
            # instruments. Per-side pagination remains registered and bounded.
            window=src.Journal(t,account)
            rows.extend(previous.collect(window,account,dict(target,Targets=[item]),ids))
            packets.extend(window.packets)
            print('MECHANISM_FUNDING_PROGRESS',i+1,len(target['Targets']),item['Symbol'],item['At'],flush=True)
    finally:t.close()
    OUT.mkdir(exist_ok=False)
    sealed=eer.seal(OUT/"packets.sealed",dict(runId=rid,protocolSha256=digest,packets=packets,
        rows=rows,classes=classes,plan=target),checked_public(Path("new-recipient-output"),rid),rid)
    (OUT/"receipt.json").write_bytes(canonical(dict(sealed=sealed,requests=len(packets),
        targetCount=len(target["Targets"]),Orders=0,CloudActivated=False)))

def readback(plan,digest):
    rid=os.environ["GITHUB_RUN_ID"];key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    receipt=json.loads((OUT/"receipt.json").read_bytes());data=eer.unpack(OUT,receipt["sealed"],key,rid)
    need(data["runId"]==rid and data["protocolSha256"]==digest,"MECHANISM_PACKETS_BINDING")
    packets=data["packets"];account=src.decode(packets[0]["reqType"],packets[0]["req"]).ctidTraderAccountId
    need(src.original_account(account),"MECHANISM_READBACK_ACCOUNT")
    journal=src.ReadbackJournal(packets)
    ids=previous.plan_ids(dict(Targets=[dict(Symbol=n) for n in plan["Instruments"]]))
    classes=asset_classes(journal,account,ids)
    rows=previous.collect(journal,account,data["plan"],ids)
    need(rows==data["rows"] and classes==data["classes"] and journal.index==len(packets)==receipt["requests"],
         "MECHANISM_FULL_PACKET_READBACK")
    return data,max(x["availableAt"] for x in packets)

def materialize(work,receipt_path,plan,digest):
    original(work,receipt_path)
    source=json.loads((work/"source.json").read_bytes())
    previous_proof=json.loads(receipt_path.read_bytes())
    data,acquired=readback(plan,digest)
    before=financing_plan(source)
    need(before=={k:v for k,v in data["plan"].items() if k!="RegistrySha256"},"MECHANISM_PREVENTIVE_SCOPE")
    clashes={}
    for tape in source["Tapes"]:
        name=tape["Name"]
        tape["FundingQuotes"],conflicts=previous.merge_rollover(tape["FundingQuotes"],
            [x["Quote"] for x in data["rows"] if x["Target"]["Symbol"]==name])
        if conflicts:clashes[name]=conflicts
    for entry in source["Markets"]:
        entry["Market"]["OfficialAssetClass"]=data["classes"].get(entry["Market"]["Name"])
    after=financing_plan(source)
    proof=dict(Previous=previous_proof,RegistrySha256=digest,TargetedReceipt=json.loads((OUT/"receipt.json").read_bytes()),
        OfficialAssetClasses=data["classes"],PreventiveBefore=before,PreventiveAfter=after,Conflicts=clashes,
        TermsBasis="CONDITIONAL_ARCHIVED_CURRENT_CONTRACT_NOT_HISTORICAL_TARIFF_OR_BROKER_SETTLEMENT")
    source.update(ProtocolSha256=digest,EvidenceManifestSha256=src.digest(canonical(proof)),
        SourceAcquiredAt=max(source["SourceAcquiredAt"],acquired))
    protocol=dict(Study=plan["Study"],Exposure=plan["Exposure"],SourceProtocolSha256=digest,
        EvidenceManifestSha256=source["EvidenceManifestSha256"],InitialFitFrom=plan["InitialFitFrom"],
        TestBoundaries=plan["TestBoundaries"],Stresses=plan["Stresses"],Calibrations=plan["Calibrations"],
        Trials=plan["Trials"],TrialGroups=plan["TrialGroups"],EconomicMechanismComparison=True,
        ArchivedSampledQuotes=True,FundingWitnesses=json.loads((work/"protocol.json").read_bytes())["FundingWitnesses"])
    source_raw,protocol_raw=canonical(source),canonical(protocol)
    (work/"source.json").write_bytes(source_raw);(work/"protocol.json").write_bytes(protocol_raw)
    receipt_path.write_bytes(canonical(dict(Study=plan["Study"],Proof=proof,SourceSha256=src.digest(source_raw),
        ProtocolSha256=src.digest(protocol_raw),EvidenceManifestSha256=source["EvidenceManifestSha256"],
        Orders=0,SourceBrokerRequests=0,CloudActivated=False,IndependentConfirmationCertified=False)))
    print("MECHANISM_PREVENTIVE_FUNDING",len(before["Targets"]),len(after["Targets"]),"conflicts",len(clashes),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("stage",choices=("plan","capture","materialize"))
    ap.add_argument("--work",type=Path);ap.add_argument("--receipt",type=Path);a=ap.parse_args()
    p,digest=registered()
    if a.stage=="capture":
        need(os.environ["GITHUB_EVENT_NAME"]=="push" and os.environ["GITHUB_REF"]=="refs/heads/main" and
             os.environ["GITHUB_RUN_ATTEMPT"]=="1","MECHANISM_CAPTURE_CONTEXT")
        capture(p,digest)
    elif a.stage=="plan":
        original(a.work,a.receipt)
        result=financing_plan(json.loads((a.work/"source.json").read_bytes()))
        Path("funding-plan.json").write_bytes(canonical(dict(result,RegistrySha256=digest)))
        print("MECHANISM_PREVENTIVE_TARGETS",len(result["Targets"]),flush=True)
    else:materialize(a.work,a.receipt,p,digest)

if __name__=="__main__":main()
