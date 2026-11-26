"""Target only the outstanding funding clocks of the immutable 13-week study."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json, os, time
from pathlib import Path

from . import owner_eur_recent_archive as archive
from . import owner_eer1_source as eer
from . import owner_eur_rollover_continuity as roll
from . import owner_eur_conditional_source as conditional
from . import owner_official_eur_source as wire
from . import source_history_universe as src
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport
from .official_symbol_calendar import build_clock_grid

REGISTRY=Path("research/eur_recent_archive_funding_2.json")
OUT=Path("targeted-funding")
DAY=86400000

def registered():
    raw=REGISTRY.read_bytes()
    p=json.loads(raw)
    need(p["Study"]=="EUR_RECENT_ARCHIVE_FUNDING_2" and p["LookbackMs"]==7200000 and
         0<p["PageBudgetPerSide"]<=64 and len(p["Targets"])==5 and
         len({(x["Symbol"],x["At"]) for x in p["Targets"]})==5,"TARGET_FUNDING_SCOPE")
    old=json.loads(archive.REGISTRY.read_bytes())
    need(all(x["Symbol"] in old["Instruments"] and old["InitialFitFrom"]<=x["At"]<old["TestBoundaries"][-1]
             and datetime.fromtimestamp(x["At"]/1000,timezone.utc).weekday()<5 for x in p["Targets"]),
         "TARGET_FUNDING_CLOCK")
    return p,src.digest(raw)

def plan_ids(p):
    original=wire.public_original()
    roster={x["name"]:x["symbolId"] for x in original["contractRoster"]}
    names={x["Symbol"] for x in p["Targets"]}
    need(names<=set(roster),"TARGET_FUNDING_ROSTER")
    return {n:roster[n] for n in sorted(names)}

def collect(journal,account,p,ids):
    result=[]
    for target in p["Targets"]:
        name,at=target["Symbol"],target["At"]
        lo=at-p["LookbackMs"]
        quote={"At":at,"RequestedCoverage":True}
        sides={}
        for side,label in ((e.BID,"Bid"),(e.ASK,"Ask")):
            rows,leaves=roll.tick_window(journal.query,account,ids[name],side,lo,at,[p["PageBudgetPerSide"]])
            complete=eer.covered(leaves,lo,at)
            sides[label]=dict(complete=complete,rows=len(rows),leaves=leaves)
            quote["RequestedCoverage"] &= complete
            boundary=conditional.boundary(rows,at,True)
            if complete and boundary and not boundary["conflict"] and lo<=boundary["at"]<=at:
                quote[label+"At"]=boundary["at"]
                quote[label]=str(Decimal(boundary["rawPrices"][0]).scaleb(-5))
        if not quote["RequestedCoverage"] or ("Bid" in quote and "Ask" in quote and Decimal(quote["Bid"])>Decimal(quote["Ask"])):
            quote={"At":at,"RequestedCoverage":False}
        result.append(dict(Target=target,Quote=quote,Sides=sides))
    return result

def verify(p,digest,key,rid):
    receipt=json.loads((OUT/"receipt.json").read_bytes())
    data=eer.unpack(OUT,receipt["sealed"],key,rid)
    packets=data["packets"]
    need(data["protocolSha256"]==digest and data["runId"]==rid and packets,"TARGET_FUNDING_BINDING")
    account=src.decode(packets[0]["reqType"],packets[0]["req"]).ctidTraderAccountId
    need(src.original_account(account),"TARGET_FUNDING_ACCOUNT")
    journal=src.ReadbackJournal(packets)
    rows=collect(journal,account,p,plan_ids(p))
    need(rows==data["rows"]==receipt["rows"] and journal.index==len(packets)==receipt["requests"],
         "TARGET_FUNDING_READBACK")
    return receipt,max(x["availableAt"] for x in packets)

def attach_closed_clocks(entry,fields,start,end,minutes):
    closed=[]
    for minute in minutes:
        offset=minute*60000
        grid=build_clock_grid(fields,start,end,step=DAY,offset=offset)
        if grid["openClocks"] is not None:
            known=set(grid["openClocks"])|set(grid["ambiguousClocks"])
            closed.extend(at for at in range(start+offset,end,DAY) if at not in known)
    entry["ClosedRolloverClocks"]=sorted(set(closed))

def merge_rollover(old,new):
    by_clock={x["At"]:x for x in old}
    conflicts=[]
    for q in new:
        at=q["At"]; prior=by_clock.get(at,{})
        if not q["RequestedCoverage"]:continue
        if prior.get("RequestedCoverage") and any(k in prior and k in q and Decimal(str(prior[k]))!=Decimal(str(q[k]))
            for k in ("Bid","Ask","BidAt","AskAt")):
            conflicts.append(at);by_clock[at]={"At":at,"RequestedCoverage":False};continue
        by_clock[at]=dict(prior,**q) if prior.get("RequestedCoverage") else q
    return sorted(by_clock.values(),key=lambda x:x["At"]),conflicts

def materialize(p,digest,work,receipt_path,key,rid):
    # Reconstruct original evidence, not the original strategy result.
    archive.materialize(archive.REGISTRY.read_bytes(),work,receipt_path)
    source=json.loads((work/"source.json").read_bytes())
    protocol=json.loads((work/"protocol.json").read_bytes())
    old_receipt=json.loads(receipt_path.read_bytes())
    old_plan=json.loads(archive.REGISTRY.read_bytes())
    original=json.loads((archive.PUBLIC_DIR/"source.json").read_bytes())
    names=old_plan["Instruments"]
    terms,account=archive.official_terms(original,names,key)
    receipt,acquired=verify(p,digest,key,rid)
    verified=json.loads(Path("targeted-funding-verified.json").read_bytes())
    need(verified==receipt,"TARGET_FUNDING_PUBLIC_READBACK")
    need(terms["EURUSD"][0]["ChargeSwapAtWeekends"] is False,"TARGET_FUNDING_ARCHIVED_WEEKEND_POLICY")
    minutes=eer.charge_clocks({n:v[0] for n,v in terms.items()})
    for entry in source["Markets"]:
        name=entry["Market"]["Name"]
        attach_closed_clocks(entry,terms[name][1]["fields"],source["Start"],source["End"],minutes)
    conflicts={}
    for tape in source["Tapes"]:
        name=tape["Name"]
        tape["FundingQuotes"],clash=merge_rollover(tape["FundingQuotes"],
            [x["Quote"] for x in receipt["rows"] if x["Target"]["Symbol"]==name])
        if clash:conflicts[name]=clash
    # Do not use historical observed outcomes for selection. Witnesses are
    # diagnostic settlement comparisons only, never labels or decisions.
    witnesses=[
        dict(PositionId="UCP1/EUR_GENERAL_PROBE/AAPL.US/GENERAL_BIDIRECTIONAL_DISTRIBUTION/1785786915000",Symbol="AAPL.US",Side=1,Units=0.1,FromExclusive=1785786915151,ClosedAt=1785857415899),
        dict(PositionId="UCP1/EUR_GENERAL_SELECT/US500/RANGE_TRANSITION/1785873615000",Symbol="US500",Side=-1,Units=0.2,FromExclusive=1785873615339,ClosedAt=1785888919554),
        dict(PositionId="UCP1/EUR_GENERAL_SELECT/EURUSD/RANGE_TRANSITION/1787326515000",Symbol="EURUSD",Side=1,Units=3000,FromExclusive=1787328016373,ClosedAt=1787522504938)]
    for cal in protocol["Calibrations"]:
        cal["Profile"]["ModelFundingAtPriorClosedSessionQuote"]=True
    joint=dict(next(t for t in protocol["Trials"] if t["Id"]=="V3_RANKED_RISK_RESIZE"),
               Id="V3_JOINT_ALLOCATION_MANAGEMENT",UseAdaptiveAllocation=True,UseAdaptiveManagement=True,UseJointMonetaryAllocation=True)
    protocol["Trials"].append(joint)
    need([t["Id"] for t in protocol["Trials"]]==p["Trials"],"TARGET_FUNDING_TRIALS")
    protocol["Study"]=p["Study"]
    protocol["TrialGroups"]={"CONTROL":p["Trials"][:3],"RISK_JOINT":p["Trials"][3:]}
    protocol["FundingWitnesses"]=witnesses
    proof=dict(Original=old_receipt["Proof"],TargetedReceipt=receipt,ConflictingMarks=conflicts,
               FundingBasis="CONDITIONAL_ORIGINAL_CONTRACT_AND_AUTHENTIC_PRIOR_CLOSED_SESSION_QUOTE_NOT_BROKER_SETTLEMENT")
    source["ProtocolSha256"]=digest
    source["EvidenceManifestSha256"]=src.digest(src.canonical(proof))
    source["SourceAcquiredAt"]=max(source["SourceAcquiredAt"],acquired)
    protocol.update(SourceProtocolSha256=digest,EvidenceManifestSha256=source["EvidenceManifestSha256"])
    source_bytes,protocol_bytes=src.canonical(source),src.canonical(protocol)
    (work/"source.json").write_bytes(source_bytes)
    (work/"protocol.json").write_bytes(protocol_bytes)
    receipt_path.write_bytes(src.canonical(dict(Study=p["Study"],Proof=proof,SourceSha256=src.digest(source_bytes),
        ProtocolSha256=src.digest(protocol_bytes),EvidenceManifestSha256=source["EvidenceManifestSha256"],
        Orders=0,SourceBrokerRequests=0,CloudActivated=False,IndependentConfirmationCertified=False)))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=("capture","verify","materialize"))
    parser.add_argument("--work",type=Path)
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args()
    p,digest=registered()
    rid=os.environ["GITHUB_RUN_ID"]
    if args.stage=="capture":
        need(os.environ["GITHUB_EVENT_NAME"]=="push" and os.environ["GITHUB_REF"]=="refs/heads/main" and
             os.environ["GITHUB_RUN_ATTEMPT"]=="1","TARGET_FUNDING_CAPTURE")
        t=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(t)
            need(src.original_account(account),"TARGET_FUNDING_ACCOUNT")
            journal=src.Journal(t,account)
            rows=collect(journal,account,p,plan_ids(p))
        finally:t.close()
        OUT.mkdir(exist_ok=False)
        sealed=eer.seal(OUT/"packets.sealed",dict(runId=rid,protocolSha256=digest,packets=journal.packets,rows=rows),
                        checked_public(Path("new-recipient-output"),rid),rid)
        (OUT/"receipt.json").write_bytes(src.canonical(dict(sealed=sealed,rows=rows,requests=len(journal.packets),
            orders=0,cloudActivated=False,historicalTariffContinuityCertified=False)))
    else:
        key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
        if args.stage=="verify":
            receipt,_=verify(p,digest,key,rid)
            Path("targeted-funding-verified.json").write_bytes(src.canonical(receipt))
        else:
            materialize(p,digest,args.work,args.receipt,key,rid)

if __name__=="__main__":
    main()
