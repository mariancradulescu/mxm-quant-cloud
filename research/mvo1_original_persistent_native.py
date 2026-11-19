"""MVO1: ORIGINAL XMH2+HXC1 authenticated source REUSE, new C# persistent marginal-value economic policy.

No Pepperstone connection, no new API request, no closed study scoring,
no Python prediction or economic arithmetic, no full source on public artifact.
"""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
from .mde1_cumulative_original_native import (
    _one_original,XMH_RUN,HXC_RUN,SYMBOLS,CAPTURED)
from .decode import need

OUT=Path("mvo1-public")
PROTOCOL=Path("research/MVO1_FROZEN_PERSISTENT_MARGIN_OPPORTUNITY_20261119.md")


def execute():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_REF")=="refs/heads/main" and
         os.environ.get("GITHUB_ACTOR")=="mariancradulescu" and
         os.environ.get("GITHUB_RUN_ATTEMPT")=="1",
         "MVO1_OWNER_MAIN_PROTECTED_ORIGINAL_ONLY")
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"MVO1_ORIGINAL_CUSTODY_KEY_REQUIRED")
    earlier,b1,v1,x1=_one_original(XMH_RUN,private)
    later,b2,v2,x2=_one_original(HXC_RUN,private)
    need(x1==CAPTURED[XMH_RUN][3] and x2==CAPTURED[HXC_RUN][3],
         "MVO1_IMMUTABLE_SOURCE_DIGEST_MISMATCH")
    streams=[]
    for symbol in SYMBOLS:
        rows=earlier[symbol]+later[symbol]
        need(all(rows[i][0]>=rows[i-1][1] for i in range(1,len(rows))),
             "MVO1_GENUINE_M15_NONCAUSAL_OVERLAP")
        streams.append({"Symbol":symbol,"Period":"M15",
            "Bars":[dict(Start=r[0],End=r[1],Open=r[2],High=r[3],
                         Low=r[4],Close=r[5],Volume=r[6]) for r in rows]})
    need(sum(len(s["Bars"]) for s in streams)==279491,
         "MVO1_EXPECTED_279491_GENUINE_ROWS")
    digest=lambda values: hashlib.sha256("|".join(values).encode()).hexdigest()
    source=dict(SourceRunId="MVO1_SOURCE_REUSE_XMH2_44352570167_HXC1_43817213663",
                ProtocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
                CiphertextSha256=digest([x1,x2]), Streams=streams)
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mvo1-protected-CSharp-") as tmp:
        input_path=Path(tmp)/"source-private.json"
        input_path.write_text(json.dumps(source,separators=(",",":")))
        output_path=OUT/"mvo1-native-persistent-marginal-price-only.json"
        p=subprocess.run(["dotnet","run","--no-build","--project",
                          "src/Mxm.Replay","-c","Release","--",
                          str(input_path),str(output_path),
                          "--mvo1-original-persistent-marginal-portfolio"],
                         capture_output=True,text=True,timeout=2400)
        need(p.returncode==0,"SPE1_NATIVE_CSHARP_UNRECOVERABLE")
        result=json.loads(output_path.read_text())
        need(result["Study"]=="MVO1_FROZEN_PERSISTENT_CAUSAL_MARGINAL_VALUE_PRICE_ONLY" and
             result["SourceBars"]==279491 and len(result["SourceSymbols"])==12 and
             result["OrdersSubmitted"]==0 and result["CloudActivated"] is False and
             result["EconomicQualification"] is False and result["RealizedBrokerNetEur"] is None and
             result["AdverseEurNet"] is None and
             not result["SystemicHard21Certified"] and
             not result["NativeEur300FundedLedgerEvaluated"] and
             result["SourceGapsNeverReleaseCapacity"] is True and
             all(r["MaxModelSimultaneousPositions"]<=2 for r in result["Results"]) and
             len(result["Results"])==3 and all(len(b["Stages"])==3 for b in result["Results"]) and all(b["FinancialNetEur"] is None for b in result["Results"]),
             "MVO1_ORIGINAL_NATIVE_RESULT_SCHEMA_OR_FINANCE_OVERCLAIM")
        receipt=dict(
            study="MVO1_NEW_PERSISTENT_ECONOMIC_OPPORTUNITY_GLOBAL_EXPOSED",
            originalXmh2Run=int(XMH_RUN),originalHxc1Run=int(HXC_RUN),
            originalXmh2CipherSha256=x1,originalHxc1CipherSha256=x2,
            originalRawRequestsReverified=3088,
            originalSourceBars=279491, originalSymbols=list(SYMBOLS),
            nativeEconomicResultSha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            protocolSha256=source["ProtocolSha256"],
            originalSourceRecollected=False,closedStudyReruns=0,
            genuineEur300Net=None,genuineFundedHARD21=None,
            independentlyValidated=False,orders=0,cloudActivated=False)
        (OUT/"mvo1-original-source-native-custody.public.json").write_text(
            json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("MVO1_ORIGINAL_IMMUTABLE_279491_BARS_NEW_CSHARP_CAUSAL_PERSISTENT_ECONOMICS_COMPLETE",flush=True)


if __name__=="__main__":
    try:execute()
    except Exception:
        print("MVO1_GUARDED_PRIVATE_SOURCE_OR_NATIVE_SCORING_FAILED",flush=True)
        raise SystemExit(1)
