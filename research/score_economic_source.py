"""Score frozen, original authentic economic source without new broker API calls.

One pass through untouched sealed v2 source; C# native source receipt must
match first before any price-only signal research output is admitted.
"""
import hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
from .custody import unseal_new

FROZEN_SOURCE_RUN="41476636915"

def run():
    if os.environ.get("MXM_FROZEN_ECONOMIC_RUN_ID")!=FROZEN_SOURCE_RUN:
        raise ValueError("ECONOMIC_SCREEN_DIFFERENT_SOURCE_BLOCKED")
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    sealed=Path("sealed-output/source.envelope.json").read_bytes()
    receipt=json.loads(Path("sealed-output/receipt.public.json").read_text())
    if not private.strip() or receipt.get("status")!="NEW_ECONOMIC_SOURCE_V2_SEALED":
        raise ValueError("ECONOMIC_SCREEN_CUSTODY_NOT_AUTHORIZED")
    if hashlib.sha256(sealed).hexdigest()!=receipt.get("ciphertextSha256"):
        raise ValueError("ECONOMIC_SCREEN_CIPHER_HASH_MISMATCH")
    source=json.loads(unseal_new(sealed,private,FROZEN_SOURCE_RUN))
    original=source.pop("csharpReceipt")
    with tempfile.TemporaryDirectory(prefix="mxm-original-econ-") as tmp:
        inp=Path(tmp)/"private-input.json"
        check=Path(tmp)/"source-parity.json"
        output=Path(tmp)/"new-screen.json"
        inp.write_text(json.dumps(source,sort_keys=True))
        inp.chmod(0o600)
        env={k:v for k,v in os.environ.items() if not k.startswith(
            ("R3_","CTRADER_","MXM_V4_"))}
        dll="src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
        for result_path,mode in ((check,"--economic-source"),(output,"--economic-screen")):
            p=subprocess.run(["dotnet",dll,str(inp),str(result_path),mode],
                             env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if p.returncode!=0 or not result_path.exists():
                raise ValueError("ECONOMIC_SCREEN_NATIVE_CSHARP_FAILURE")
        if json.loads(check.read_text())!=original:
            raise ValueError("ECONOMIC_SCREEN_ORIGINAL_PARITY_FAILED")
        scored=json.loads(output.read_text())
    if (scored.get("netInEur") is not None or scored.get("ordersSubmitted")!=0 or
        scored.get("sourceRunId")!=int(FROZEN_SOURCE_RUN) or
        scored.get("independentConfirmation") is not False):
        raise ValueError("ECONOMIC_SCREEN_PROHIBITED_QUALIFICATION")
    public={
        "schema":"mxm.fixed-breakout-economic-development-public.v1",
        "sourceRunId":int(FROZEN_SOURCE_RUN),
        "originalCsharpSourceReceiptReconciled":True,
        "newMechanism":"Prior12BarHighLowBreakout; enter next OHLC bar open; exit fourth OHLC close; no parameters fitted",
        "temporalSlices":"60% development / 20% selection / 20% descriptive late slice; all previously exposed development historical dates",
        "results":scored["results"],
        "historicalExAnteSourceNotIndependentConfirmation":True,
        "brokerExecutionNetEur":None,
        "hard21BrokerCompletionsConfirmed":False,
        "fundedEUR200Verified":False,
        "tradingAuthority":False,
        "ordersSubmitted":0
    }
    Path("economic-breakout.public.json").write_text(
        json.dumps(public,sort_keys=True,indent=2)+"\n")
    print("AUTHENTIC_NEW_FIXED_BREAKOUT_PUBLIC_AGGREGATE "+json.dumps({
        "sourceRunId":public["sourceRunId"],
        "results":public["results"],
        "brokerExecutionNetEur":None
    },sort_keys=True))
    print("ECONOMIC_BREAKOUT_COLD_SCORE_COMPLETE_NO_NET_QUALIFICATION")

if __name__=="__main__":
    try: run()
    except Exception:
        print("ECONOMIC_BREAKOUT_PROTECTED_SCORE_FAILED_DETAIL_WITHHELD")
        sys.exit(1)
