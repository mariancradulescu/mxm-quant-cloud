"""NPI1 original OEI1 read-only source bridge. NO forecast, execution or economic scoring.

The encrypted tape is only opened within the existing original custody environment.
This program does NOT invoke the closed OEI1/OEI1-A1 economic runner.
"""
import bisect, base64, hashlib, json, os, subprocess, tempfile
from pathlib import Path
from decimal import Decimal
from .custody import unseal_new
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .native_original_openapi_product_replay import contract

RUN = "44247979857"
SOURCE = Path("npi1-original-source")
PUBLIC = Path("npi1-original-public")
OUT = Path("npi1-public")
SHA = "sha256"
MINUTE = 60000
WINDOW_START_MINUTE = 810
WINDOW_END_MINUTE = 930

def need(ok, why):
    if not ok:
        raise RuntimeError("NPI1_SOURCE_"+why)

def main():
    OUT.mkdir(exist_ok=True)
    receipt = dict(Study="NPI1_SOURCE_BOUND_NEW_NATIVE", SourceRun=int(RUN),
                   OriginalStudiesRerun=0, NewBrokerRequests=0,
                   OrdersSubmitted=0, CloudActivated=False,
                   OriginalOutcomesReplaced=False, Status="SOURCE_NOT_VERIFIED")
    def publish():
        (OUT/"receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    try:
        p = list(SOURCE.rglob("oei1-native-tape.enc"))
        q = list(PUBLIC.rglob("source.json"))
        need(len(p)==1 and len(q)==1,"ORIGINAL_TAPE_OR_RECEIPT_MISSING")
        original = json.loads(q[0].read_text())
        cipher = p[0].read_bytes()
        cipher_hash = hashlib.sha256(cipher).hexdigest()
        need(original["SourceCipherSha256"]==cipher_hash,"CIPHERTEXT_SHA_MISMATCH")
        key = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
        need(bool(key.strip()),"ORIGINAL_CUSTODY_KEY_MISSING")
        clear = unseal_new(cipher,key,RUN)
        source_hash = hashlib.sha256(clear).hexdigest()
        need(original["SourceSha256"]==source_hash,"PLAINTEXT_SHA_MISMATCH")
        tape = json.loads(clear)
        need(tape["Start"]==original["SourceStartUtc"] and tape["End"]==original["SourceEndUtc"],"WINDOW_MISMATCH")
        need(set(x["Name"] for x in tape["Symbols"])=={"EURUSD","ETHUSD","SpotBrent","US500"},"FOUR_CLASS_SOURCE_MISMATCH")
        markets=[]; counts={}
        for source in tape["Symbols"]:
            name=source["Name"]
            c=e.ProtoOASymbol()
            c.ParseFromString(base64.b64decode(source["ContractProto"]))
            terms=contract(name,c,"USD",source["ContractObservedAt"])
            sample=[]
            for day in source["Days"]:
                bid,ask=day["Bid"],day["Ask"]
                # Keep ALL raw same-ms events in custody; ambiguous same-ms conflicts are excluded.
                times_b=[x[0] for x in bid];times_a=[x[0] for x in ask]
                for t in range(day["Start"]+WINDOW_START_MINUTE*MINUTE,
                               day["Start"]+WINDOW_END_MINUTE*MINUTE,MINUTE):
                    bi=bisect.bisect_right(times_b,t)-1
                    ai=bisect.bisect_right(times_a,t)-1
                    if bi<0 or ai<0:continue
                    bt,bv=bid[bi];at,av=ask[ai]
                    if t-bt>30000 or t-at>30000 or t<bt or t<at or bv<=0 or av<bv:continue
                    if bi>0 and bid[bi-1][0]==bt and bid[bi-1][1]!=bv:continue
                    if ai>0 and ask[ai-1][0]==at and ask[ai-1][1]!=av:continue
                    sample.append(dict(At=t,Bid=str(Decimal(bv)/100000),
                                       Ask=str(Decimal(av)/100000),BidAt=bt,AskAt=at))
            need(all(sample[i]["At"]<sample[i+1]["At"] for i in range(len(sample)-1)),
                 "OBSERVATION_ORDER")
            counts[name]=dict(GenuineAsOfMinuteMarks=len(sample),SourceRecordedDays=len(source["Days"]))
            markets.append(dict(Name=name,Contract=terms,MinMarginEur=source["MinMarginEur"],
                                TickSize=source["TickSize"],Quotes=sample))
        native=dict(OriginalSourceSha256=source_hash,Start=tape["Start"],
                    End=tape["End"],Markets=markets)
        with tempfile.TemporaryDirectory(prefix="npi1-original-native-") as folder:
            source_file=Path(folder)/"verified-original-quote-bridge.json"
            source_file.write_text(json.dumps(native,separators=(",",":")))
            source_file.chmod(0o600)
            result=OUT/"native-economic.json"
            proc=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                                str(source_file),str(result),"--npi1-original-integrated"],
                                capture_output=True,text=True,timeout=2700)
            need(proc.returncode==0,"NATIVE_CSHARP_RESULT_FAILED_"+str(proc.returncode)+
                 "_"+proc.stderr[-900:].replace("\n"," "))
        receipt.update(Status="ORIGINAL_SOURCE_NATIVE_RESULT_AVAILABLE",
                       SourceSha256=source_hash,SourceCipherSha256=cipher_hash,
                       Counts=counts,NativeReportSha256=hashlib.sha256(result.read_bytes()).hexdigest(),
                       SourceQuoteBridge="ASOF_1MINUTE_BOTH_SIDES_NOT_OLDER_THAN_30SEC",
                       HistoricalTariffContinuityCertified=False,
                       HistoricalBrokerFillsCertified=False,
                       ContinuousFloatingDdCertified=False)
        publish()
    except Exception as ex:
        receipt.update(Status="NPI1_NEW_NATIVE_SOURCE_STOP",
                       FailureType=type(ex).__name__,
                       FailureCode=str(ex)[:900])
        publish()
        raise

if __name__=="__main__":
    main()
