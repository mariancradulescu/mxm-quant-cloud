"""FCP1 distinct finance-before-FIRST comparator. Python is custody ONLY.
Reuse authentic original HXC1/CXL1/OEI1 sources but DO NOT rerun SCP1-A1.
Frozen original public fitted model is read, not fitted again. All new
selection, shared capital and full lifecycle are executed in native C#.
"""
from __future__ import annotations
import base64, bisect, hashlib, json, os, subprocess, tempfile
from decimal import Decimal
from pathlib import Path
from datetime import date
from .cxl1_original_native_eur_readback import read_archive,reconstruct,wire
from .cxl1_original_275_source import earlier
from .cxl1_original_feasibility import calendar
from .ctrader_proto import OpenApiMessages_pb2 as pm
from .decode import decode_bars
from .custody import unseal_new
from .hxc1_historical_readback import validate
from .decode import need
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .native_original_openapi_product_replay import contract

HXC_RUN="43817213663"
OEI_RUN="44247979857"
HXC=Path("scp1a1-hxc1-original-source")
OEI=Path("scp1a1-oei1-original-source")
PUBLIC=Path("scp1a1-oei1-original-public")
OUT=Path("fcp1-public")
POLICY="research/FCP1_FROZEN_FIRST_FINANCE_SCORE_PORTFOLIO_20261119.md"
UNIVERSE=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD",
          "US500","NAS100","GER40","UK100","AUS200","JPN225")
LIMIT=100000
DAY_MINUTES_START=810
DAY_MINUTES_END=930
MINUTE=60000

def main():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_REF")=="refs/heads/main" and
         os.environ.get("GITHUB_ACTOR")=="mariancradulescu" and
         os.environ.get("GITHUB_RUN_ATTEMPT")=="1",
         "FCP1_MAIN_OWNER_ONCE_ONLY")
    secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(secret.strip()),"SCP1_PROTECTED_CUSTODY_KEY_MISSING")
    OUT.mkdir(exist_ok=True)
    receipt=dict(Study="FCP1_DISTINCT_FINANCED_FIRST_VS_FROZEN_NEGATIVE_SCORE",
        OriginalHxc1Run=int(HXC_RUN),OriginalOei1Run=int(OEI_RUN),
        ClosedStudiesRerun=0,NewBrokerRequests=0,OrdersSubmitted=0,
        CloudActivated=False,GlobalExposureDisclosed=True,
        HistoricalFundingContinuityCertified=False,
        ActualBrokerExecutionCertified=False,Status="SOURCE_NOT_VERIFIED")
    def publish():
        (OUT/"receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    try:
        envelope=(HXC/"source.envelope.json").read_bytes()
        original=json.loads((HXC/"receipt.public.json").read_text())
        hxc_cipher=hashlib.sha256(envelope).hexdigest()
        need(hxc_cipher==original["ciphertextSha256"],
             "HXC1_ORIGINAL_CIPHER_HASH")
        clear=unseal_new(envelope,secret,HXC_RUN)
        hxc_clear=hashlib.sha256(clear).hexdigest()
        bundle=json.loads(clear)
        status=validate(bundle,original,HXC_RUN)
        need(status["status"]==
             "HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT",
             "HXC1_PROVENANCE_NOT_AUTHENTIC")
        need(not any(sym+"/M5" in bundle["bars"] for sym in UNIVERSE),
             "HXC1_M5_MISREPRESENTED")
        sources=[
          ("scp1a1-cxl1-earlier-encrypted/cxl1-earlier-275-authentic.v2.enc",
           "scp1a1-cxl1-earlier-public/cxl1-original-275-source-public.json",
           43947388854,"MXM_CXL1_ORIGINAL_275_EARLIER_CLOSED_BAR_AND_QUOTE_SOURCE_V1",
           "MXM_CXL1_ORIGINAL_275_SOURCE_ONLY_V1",2757,275,earlier()),
          ("scp1a1-cxl1-pilot-encrypted/cxl1-original-feasibility.v2.enc",
           "scp1a1-cxl1-pilot-public/cxl1-original-feasibility-public.json",
           43945139889,"MXM_CXL1_ORIGINAL_FIRST_ONLY_PILOT_RAW_PROTOBUF_V1",
           "MXM_CXL1_ORIGINAL_PRESOURCE_PILOT_FEASIBILITY_V1",507,50,
           [(d,t) for d,t in calendar() if d>=date(2026,11,2)])
        ]
        raw_crypto={"BTCUSD":{}, "ETHUSD":{}}
        cxl_hashes=[]
        for sealed_path,public_path,rid,kind,receipt_kind,nraw,nrows,clocks in sources:
            body,original_receipt,proof=read_archive(
                Path(sealed_path),Path(public_path),secret,rid,
                kind,receipt_kind,nraw,nrows)
            validated,contracts,margins,trader,coverage=reconstruct(body,clocks)
            need(len(validated)==nrows and all(k in contracts for k in raw_crypto),
                 "CXL1_ORIGINAL_RAW_ACCOUNT_AUTHENTICATION")
            cxl_hashes.append(proof["cipherSha256"])
            for record in body["rows"]:
                for sym in raw_crypto:
                    q,ans=wire(body["raw"][record["bar"][sym]["rawIndex"]])
                    need(isinstance(q,pm.ProtoOAGetTrendbarsReq) and
                         q.period==e.M5 and
                         q.fromTimestamp==record["t"]-86400000-300000 and
                         q.toTimestamp==record["t"],"CXL1_M5_ORIGINAL_REQUEST")
                    if isinstance(ans,pm.ProtoOAErrorRes):
                        need(ans.errorCode=="NO_QUOTES","CXL1_NO_QUOTES_ONLY")
                        continue
                    need(isinstance(ans,pm.ProtoOAGetTrendbarsRes),
                         "CXL1_RAW_SOURCE_RESPONSE_INVALID")
                    if not ans.HasField("hasMore") or ans.hasMore:continue
                    for row in decode_bars(ans.trendbar,q.fromTimestamp,q.toTimestamp,5):
                        start,end=row[:2]
                        if end-start!=300000 or start<q.fromTimestamp or end>q.toTimestamp:continue
                        earlier_row=raw_crypto[sym].get(start)
                        need(earlier_row is None or earlier_row==row,
                             "CXL1_DUPLICATED_M5_CONFLICT")
                        raw_crypto[sym][start]=row

        def strict_ohlcv(rows,from_minutes,to_minutes):
            need(to_minutes%from_minutes==0,"SOURCE_UPSAMPLING_FORBIDDEN")
            n=to_minutes//from_minutes
            span=to_minutes*60000
            groups={}
            for x in rows:groups.setdefault(x[0]//span,[]).append(x)
            out=[]
            for k,items in sorted(groups.items()):
                v=sorted(items,key=lambda x:x[0])
                start=k*span
                if (len(v)!=n or v[0][0]!=start or v[-1][1]!=start+span or
                    any(a[1]!=b[0] for a,b in zip(v,v[1:]))):continue
                out.append([start,start+span,v[0][2],
                            max(x[3] for x in v),min(x[4] for x in v),
                            v[-1][5],sum(x[6] for x in v)])
            return out

        def normalized(rows):
            return [dict(OpenAt=x[0],CloseAt=x[1],
                  Open=str(Decimal(x[2])/LIMIT),
                  High=str(Decimal(x[3])/LIMIT),
                  Low=str(Decimal(x[4])/LIMIT),
                  Close=str(Decimal(x[5])/LIMIT),
                  TickVolume=x[6]) for x in rows]

        streams=[]
        counts={}
        for sym in raw_crypto:
            m5=sorted(raw_crypto[sym].values(),key=lambda x:x[0])
            m15=strict_ohlcv(m5,5,15)
            need(len(m5)>3000 and len(m15)>1000,
                 "CXL1_GENUINE_M5_M15_TOO_SPARSE_"+sym)
            streams.append(dict(Symbol=sym,M5=normalized(m5),M15=normalized(m15)))
            counts[sym+"/M5"]=len(m5)
            counts[sym+"/M15"]=len(m15)
        for sym in ("EURUSD","US500","XAUUSD","NAS100"):
            m1=bundle["bars"].get(sym+"/M1")
            m15=bundle["bars"].get(sym+"/M15")
            need(m1 is not None and m15 is not None and
                 len(m1)>1000 and len(m15)>1000,
                 "HXC1_GENUINE_M1_M15_TOO_SPARSE_"+sym)
            m5=strict_ohlcv(m1,1,5)
            need(len(m5)>3000,"HXC1_M1_GENUINE_M5_TOO_SPARSE_"+sym)
            streams.append(dict(Symbol=sym,M5=normalized(m5),M15=normalized(m15)))
            counts[sym+"/M5"]=len(m5)
            counts[sym+"/M15"]=len(m15)
        sealed=list(OEI.rglob("oei1-native-tape.enc"))
        sources=list(PUBLIC.rglob("source.json"))
        need(len(sealed)==1 and len(sources)==1,
             "OEI1_ORIGINAL_SEALED_TAPE_OR_PUBLIC_SOURCE_MISSING")
        cipher=sealed[0].read_bytes()
        oeic=hashlib.sha256(cipher).hexdigest()
        oeireceipt=json.loads(sources[0].read_text())
        need(oeic==oeireceipt["SourceCipherSha256"],
             "OEI1_SOURCE_CIPHER_SHA")
        oeiclear=unseal_new(cipher,secret,OEI_RUN)
        oei_sha=hashlib.sha256(oeiclear).hexdigest()
        need(oei_sha==oeireceipt["SourceSha256"],"OEI1_SOURCE_SHA")
        tape=json.loads(oeiclear)
        need(set(x["Name"] for x in tape["Symbols"])==
             {"EURUSD","ETHUSD","SpotBrent","US500"},
             "OEI1_EXACT_ORIGINAL_FOUR_SYMBOL_SOURCE")
        market_quotes=[]
        mark_counts={}
        for source in tape["Symbols"]:
            if source["Name"] not in ("EURUSD","US500","ETHUSD"):
                continue
            name=source["Name"]
            c=e.ProtoOASymbol()
            c.ParseFromString(base64.b64decode(source["ContractProto"]))
            terms=contract(name,c,"USD",source["ContractObservedAt"])
            sample=[]
            for day in source["Days"]:
                bids,asks=day["Bid"],day["Ask"]
                tb=[v[0] for v in bids]
                ta=[v[0] for v in asks]
                for t in range(day["Start"]+DAY_MINUTES_START*MINUTE,
                               day["Start"]+DAY_MINUTES_END*MINUTE,MINUTE):
                    bi=bisect.bisect_right(tb,t)-1
                    ai=bisect.bisect_right(ta,t)-1
                    if bi<0 or ai<0:continue
                    bt,bv=bids[bi];at,av=asks[ai]
                    if (bt>t or at>t or t-bt>30000 or t-at>30000 or
                        bv<=0 or av<bv):continue
                    if bi>0 and bids[bi-1][0]==bt and bids[bi-1][1]!=bv:continue
                    if ai>0 and asks[ai-1][0]==at and asks[ai-1][1]!=av:continue
                    sample.append(dict(At=t,Bid=str(Decimal(bv)/LIMIT),
                                       Ask=str(Decimal(av)/LIMIT),
                                       BidAt=bt,AskAt=at))
            need(all(sample[i]["At"]<sample[i+1]["At"]
                     for i in range(len(sample)-1)),"OEI1_TIME_ORDER")
            mark_counts[name]=len(sample)
            market_quotes.append(dict(Symbol=name,Contract=terms,
                 MinMarginEur=source["MinMarginEur"],
                 TickSize=source["TickSize"],Quotes=sample))
        need(len(market_quotes)==3 and all(v>=5000 for v in mark_counts.values()),
             "SCP1_MINIMUM_ORIGINAL_QUOTE_COVERAGE_NOT_VERIFIED")
        payload=dict(SourceGeometry="SCP1_A1_REAL_CXL1_M5_AND_HXC1_M1_TO_M5",
            OriginalCxl1CipherHashes=cxl_hashes,
            OriginalHxc1SourceSha256=hxc_clear,
            OriginalOei1SourceSha256=oei_sha,Streams=streams,
            QuoteMarkets=market_quotes)
        with tempfile.TemporaryDirectory(prefix="fcp1-protected-native-") as temp:
            original_input=Path(temp)/"hxc1-m5-m15-and-oei1-quote-protected.json"
            original_input.write_text(json.dumps(payload,separators=(",",":")))
            original_input.chmod(0o600)
            # Frozen SCP1-A1 PUBLIC artifact, never its source scorer. Verify
            # the immutable receipt hash before the distinct FCP1 C# runner.
            old_root=Path("fcp1-scp1-original-public")
            originals=list(old_root.rglob("scp1-economic-scores-and-common-eur300-books.json"))
            need(len(originals)==1,"FCP1_IMMUTABLE_SCP1_PUBLIC_REPORT_NOT_FOUND")
            original_report=originals[0]
            old_hash=hashlib.sha256(original_report.read_bytes()).hexdigest()
            need(old_hash=="64350a59aad0c3e272b935d96a9ce1f274f4b26ea7e984b8ad884c4148f5da5d",
                 "FCP1_ORIGINAL_SCP1_A1_NATIVE_REPORT_HASH_MISMATCH")
            output=OUT/"fcp1-native-financed-first-score-eur300.json"
            result=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                str(original_input),str(original_report),str(output),
                "--fcp1-financed-original-source-exploratory"],
                capture_output=True,text=True,timeout=5100)
            need(result.returncode==0,
                 "FCP1_NATIVE_FINANCE_FIRST_RUNNER_FAILED_"+
                 str(result.returncode)+"_"+result.stderr[-800:].replace("\n"," "))
        published=json.loads(output.read_text())
        need(published["Study"]=="FCP1_NATIVE_FINANCED_FIRST_VS_SCORED_ECONOMICS" and
             published["OriginalHxc1SourceSha256"]==hxc_clear and
             published["OriginalOei1SourceSha256"]==oei_sha and
             published["OrdersSubmitted"]==0 and
             published["CloudActivated"] is False and
             published["BrokerNetCertified"] is False,
             "SCP1_NEW_NATIVE_RESULT_FAIL_CLOSED")
        receipt.update(Status="FCP1_GLOBALLY_EXPOSED_FINANCED_COMPARISON_AVAILABLE",
             Hxc1OriginalCipherSha256=hxc_cipher,
             Hxc1OriginalSourceSha256=hxc_clear,
             Oei1OriginalCipherSha256=oeic,
             Oei1OriginalSourceSha256=oei_sha,
             HistoricalGenuineM5M15Counts=counts,
             GenuineQuoteEvaluableMarks=mark_counts,
             SourceGeometry="SCP1_A1_REAL_CXL1_M5_AND_HXC1_M1_TO_M5",
             OriginalCxl1CipherHashes=cxl_hashes,
             FrozenProtocolSha256=hashlib.sha256(Path(POLICY).read_bytes()).hexdigest(),
             NativeOutputSha256=hashlib.sha256(output.read_bytes()).hexdigest(),
             FrozenSCP1A1ModelMethod=published["Model"]["Method"],
             OriginalSCP1A1ReportSha256=old_hash,
             ClosedOriginalScp1Rerun=False,
             FullyIndependent=False)
        publish()
        print("FCP1_DISTINCT_NATIVE_FINANCED_FIRST_COMPARISON_AVAILABLE",
              json.dumps(dict(FrozenNegativeControlModel=published["Model"]["Method"],
                 NativeOutputSha256=receipt["NativeOutputSha256"],
                 SourcePriceBars=sum(counts.values()),
                 Orders=0),sort_keys=True),flush=True)
    except Exception as exc:
        receipt.update(Status="FCP1_NEW_RESEARCH_FAILED_NO_ECONOMIC_PROMOTION",
                       FailureType=type(exc).__name__,
                       FailureCode=str(exc)[:850])
        publish()
        raise

if __name__=="__main__":
    main()
