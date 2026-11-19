"""SCP1: original HXC1 native M5/M15 + OEI1 original quote custody ONLY.
All training, model selection, trade policies, sizing, accounting, and
economic scorecard calculations are executed inside shared C# Mxm.Core.
No closed HXC1/OEI1/SIR1/NPI1/UCP1 study method is invoked or rescored.
"""
from __future__ import annotations
import base64, bisect, hashlib, json, os, subprocess, tempfile
from decimal import Decimal
from pathlib import Path
from .custody import unseal_new
from .hxc1_historical_readback import validate
from .decode import need
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .native_original_openapi_product_replay import contract

HXC_RUN="43817213663"
OEI_RUN="44247979857"
HXC=Path("scp1-hxc1-original-source")
OEI=Path("scp1-oei1-original-source")
PUBLIC=Path("scp1-oei1-original-public")
OUT=Path("scp1-public")
POLICY="research/SCP1_FROZEN_CAUSAL_ECONOMIC_RANKING_20261119.md"
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
         "SCP1_ORIGINAL_OWNER_ONCE_ONLY")
    secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(secret.strip()),"SCP1_PROTECTED_CUSTODY_KEY_MISSING")
    OUT.mkdir(exist_ok=True)
    receipt=dict(Study="SCP1_AUTHENTIC_M5_M15_TRAINED_ECONOMIC_SELECTION",
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
        streams=[]
        counts={}
        for symbol in UNIVERSE:
            rows={}
            for period in ("M5","M15"):
                tag=symbol+"/"+period
                need(tag in bundle["bars"],"HXC1_"+tag+"_MISSING")
                original_bars=bundle["bars"][tag]
                need(len(original_bars)>=100,"HXC1_M5_M15_HISTORY_INCOMPLETE")
                bars=[dict(OpenAt=row[0],CloseAt=row[1],
                    Open=str(Decimal(row[2])/LIMIT),
                    High=str(Decimal(row[3])/LIMIT),
                    Low=str(Decimal(row[4])/LIMIT),
                    Close=str(Decimal(row[5])/LIMIT),
                    TickVolume=row[6]) for row in original_bars]
                need(all(bars[i]["OpenAt"]>bars[i-1]["OpenAt"]
                         for i in range(1,len(bars))),
                     "HXC1_NONCAUSAL_COMPLETED_BAR")
                rows[period]=bars
                counts[tag]=len(bars)
            streams.append(dict(Symbol=symbol,M5=rows["M5"],M15=rows["M15"]))

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
            if source["Name"] not in ("EURUSD","US500"):
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
        need(len(market_quotes)==2 and all(v>=5000 for v in mark_counts.values()),
             "SCP1_MINIMUM_ORIGINAL_QUOTE_COVERAGE_NOT_VERIFIED")
        payload=dict(OriginalHxc1SourceSha256=hxc_clear,
            OriginalOei1SourceSha256=oei_sha,Streams=streams,
            QuoteMarkets=market_quotes)
        with tempfile.TemporaryDirectory(prefix="scp1-protected-native-") as temp:
            original_input=Path(temp)/"hxc1-m5-m15-and-oei1-quote-protected.json"
            original_input.write_text(json.dumps(payload,separators=(",",":")))
            original_input.chmod(0o600)
            output=OUT/"scp1-economic-scores-and-common-eur300-books.json"
            result=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                str(original_input),str(output),"--scp1-original-scored-economics"],
                capture_output=True,text=True,timeout=5100)
            need(result.returncode==0,
                 "SCP1_NATIVE_CSHARP_ECONOMIC_SCORER_FAILED_"+
                 str(result.returncode)+"_"+result.stderr[-800:].replace("\n"," "))
        published=json.loads(output.read_text())
        need(published["Study"]=="SCP1_NATIVE_CAUSAL_ECONOMIC_RANKING" and
             published["OriginalHxc1SourceSha256"]==hxc_clear and
             published["OriginalOei1SourceSha256"]==oei_sha and
             published["OrdersSubmitted"]==0 and
             published["CloudActivated"] is False and
             published["BrokerNetCertified"] is False,
             "SCP1_NEW_NATIVE_RESULT_FAIL_CLOSED")
        receipt.update(Status="SCP1_NEW_CAUSAL_FINANCIAL_ECONOMIC_RESULT_AVAILABLE",
             Hxc1OriginalCipherSha256=hxc_cipher,
             Hxc1OriginalSourceSha256=hxc_clear,
             Oei1OriginalCipherSha256=oeic,
             Oei1OriginalSourceSha256=oei_sha,
             HistoricalGenuineM5M15Counts=counts,
             GenuineQuoteEvaluableMarks=mark_counts,
             FrozenProtocolSha256=hashlib.sha256(Path(POLICY).read_bytes()).hexdigest(),
             NativeOutputSha256=hashlib.sha256(output.read_bytes()).hexdigest(),
             ModelChosenBeforeEvaluation=published["Model"]["Method"],
             FullyIndependent=False)
        publish()
        print("SCP1_SOURCE_AUTHENTIC_MODEL_SELECTION_CSHARP_RESULT_AVAILABLE",
              json.dumps(dict(Model=published["Model"]["Method"],
                 NativeOutputSha256=receipt["NativeOutputSha256"],
                 SourcePriceBars=sum(counts.values()),
                 Orders=0),sort_keys=True),flush=True)
    except Exception as exc:
        receipt.update(Status="SCP1_ORIGINAL_RESEARCH_FAILED_NO_ECONOMIC_PROMOTION",
                       FailureType=type(exc).__name__,
                       FailureCode=str(exc)[:850])
        publish()
        raise

if __name__=="__main__":
    main()
