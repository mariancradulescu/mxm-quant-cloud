"""SIR1 source-bound fixed-clock native lifecycle witness.

OEI1 original encrypted SOURCE ONLY. Never invoke OEI1/NPI1 scores/models,
never call broker/API. Python custody, parsing and as-of only; all model,
decision and financial facts are produced by the native C# Core.
"""
import bisect
import base64
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

from .custody import unseal_new
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .native_original_openapi_product_replay import contract

RUN="44247979857"
CIPHER=Path("sir1-original-source")
PUBLIC=Path("sir1-original-public")
OUT=Path("sir1-source-public")
NAMES={"EURUSD","US500","ETHUSD","SpotBrent"}
TIMES=[int(datetime(2026,8,21,15,m,tzinfo=timezone.utc).timestamp()*1000) for m in (27,28,29)]+[
    int(datetime(2026,8,24,13,m,tzinfo=timezone.utc).timestamp()*1000) for m in (30,31,32)]
MINUTE=60000

def need(x,why):
    if not x:raise RuntimeError("SIR1_SOURCE_"+why)

def read_asof(day,t):
    bids=day["Bid"];asks=day["Ask"]
    def side(rows):
        times=[x[0] for x in rows]
        i=bisect.bisect_right(times,t)-1
        if i<0:return None
        stamp,v=rows[i]
        if t-stamp>30000 or stamp>t or v<=0:return None
        first=bisect.bisect_left(times,stamp)
        if any(rows[j][1]!=v for j in range(first,i)):return None
        return stamp,Decimal(v)/100000
    b=side(bids);a=side(asks)
    if b is None or a is None or a[1]<b[1]:return None
    return dict(At=t,Bid=str(b[1]),Ask=str(a[1]),BidAt=b[0],AskAt=a[0])

def main():
    OUT.mkdir(exist_ok=True)
    receipt=dict(Study="SIR1_SOURCE_FROZEN_TECHNICAL_WITNESS",
        SourceRun=int(RUN),OriginalStudiesRerun=0,
        BrokerRequests=0,OrdersSubmitted=0,CloudActivated=False,
        SourceFreshCollection=False,
        Config="FIXED_FRI_20260821_MON_20260824_ORIGINAL_4_CLASS",
        Status="SOURCE_NOT_YET_VERIFIED")
    def save():
        (OUT/"receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    try:
        p=list(CIPHER.rglob("oei1-native-tape.enc"))
        q=list(PUBLIC.rglob("source.json"))
        need(len(p)==1 and len(q)==1,"SOURCE_AND_RECEIPT_UNAVAILABLE")
        receipt0=json.loads(q[0].read_text())
        need(int(receipt0["OriginalRun"])==int(RUN),"SOURCE_RUN_ID")
        cipher=p[0].read_bytes()
        cipherhash=hashlib.sha256(cipher).hexdigest()
        need(cipherhash==receipt0["SourceCipherSha256"],"ORIGINAL_CIPHER_HASH")
        secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
        need(bool(secret.strip()),"PRIVATE_KEY_NOT_IN_CUSTODY")
        clear=unseal_new(cipher,secret,RUN)
        sha=hashlib.sha256(clear).hexdigest()
        need(sha==receipt0["SourceSha256"],"ORIGINAL_PLAINTEXT_HASH")
        tape=json.loads(clear)
        need(tape["Start"]==receipt0["SourceStartUtc"] and
             tape["End"]==receipt0["SourceEndUtc"],"ORIGINAL_SOURCE_WINDOW")
        need({m["Name"] for m in tape["Symbols"]}==NAMES,"SOURCE_FOUR_CLASS_SCOPE")
        markets=[];available={}
        for m in tape["Symbols"]:
            name=m["Name"]
            proto=e.ProtoOASymbol()
            proto.ParseFromString(base64.b64decode(m["ContractProto"],validate=True))
            term=contract(name,proto,"USD",m["ContractObservedAt"])
            daymap={d["Start"]:d for d in m["Days"]}
            quotations=[]
            for t in TIMES:
                day=t//86400000*86400000
                if day not in daymap:continue
                quote=read_asof(daymap[day],t)
                if quote is not None:quotations.append(quote)
            markets.append(dict(Name=name,Contract=term,
                MinMarginEur=m["MinMarginEur"],TickSize=m["TickSize"],
                Quotes=quotations))
            available[name]=len(quotations)
        witness=dict(SourceSha256=sha,Markets=markets)
        with tempfile.TemporaryDirectory(prefix="sir1-original-source-") as tmp:
            inp=Path(tmp)/"original-source-fixed-clocks.json"
            inp.write_text(json.dumps(witness,separators=(",",":")))
            inp.chmod(0o600)
            result=OUT/"native-original-lifecycle.json"
            process=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                str(inp),str(result),"--sir1-original-native-source-witness"],
                capture_output=True,text=True,timeout=900)
            need(process.returncode==0,"NATIVE_SOURCE_REPLAY_"+str(process.returncode)+
                 "_"+process.stderr[-1000:].replace("\n"," "))
        receipt.update(Status="SIR1_ORIGINAL_NATIVE_LIFECYCLE_RECORDED",
            OriginalSourcePlainSha256=sha,OriginalSourceCipherSha256=cipherhash,
            OriginalAsOfSourceMarks=available,
            NativeEconomicTraceSha256=hashlib.sha256(result.read_bytes()).hexdigest(),
            HistoricalTariffContinuous=False,HistoricFinancingCertified=False,
            FloatingDrawdownContinuous=False,BrokerNetCertified=False,
            SourceWindowIsOfficialBrokerClosure=False,
            IndependentConfirmation=False)
        save()
    except Exception as ex:
        receipt.update(Status="SIR1_SOURCE_TECHNICAL_STOP",
            FailureType=type(ex).__name__,FailureCode=str(ex)[:1000])
        save()
        raise

if __name__=="__main__":main()
