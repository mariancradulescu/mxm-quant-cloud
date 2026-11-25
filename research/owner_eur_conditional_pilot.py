"""Distinct OWNER scenario continuity pilot; no original economic replay."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from . import owner_eur_historical_development as dated
from . import closed_market_context_readback as context
from . import integrated_market_readback as integrated
from .decode import need

PROTOCOL=Path("research/OWNER_EUR_CONDITIONAL_CONTINUITY_PILOT_20261125.md")
OUT=Path("owner-eur-conditional-pilot-public")
SOURCE=Path("eur-conditional-source")

def main():
    receipt=json.loads((SOURCE/"receipt.json").read_bytes())
    values=(SOURCE/"rollover-values.json").read_bytes()
    matrix=(SOURCE/"integrated-coverage-matrix.json").read_bytes()
    need(receipt["sourceRun"]=="45549613144" and
        dated.sha(values)==receipt["rolloverValuesSha256"] and
        dated.sha(matrix)==receipt["matrixSha256"],"CONDITIONAL_RECEIPT_HASH")
    v=json.loads(values)
    need(v["plaintextSha256"]==receipt["originalPlaintextSha256"] and
        not v["settlementPriceConventionCertified"] and not v["historicalTariffContinuityCertified"] and
        receipt["brokerRequests"]==0 and receipt["orders"]==0,"CONDITIONAL_RECEIPT_SCOPE")
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(key),"CONDITIONAL_EXISTING_CUSTODY_KEY")
    terms, old_bars=dated.preceding_terms()
    roster={r["symbol"]:r for r in json.loads(matrix)["matrix"]}
    markets, extra=context.sources(key,dated.SUPPLEMENTARY,native_boundaries=True,
        rollover_clocks=dated.rollover_clocks(terms))
    notes=[]
    for market in markets:
        symbol=market["Name"]
        row=roster.get(symbol,{})
        market["OfficialAssetClass"]=row.get("assetClass")
        earlier=terms.get(symbol)
        if earlier and earlier["Contract"]["QuoteAsset"]==market["Contract"]["QuoteAsset"]:
            market["DatedDevelopment"]=earlier
        boundary=market["M5"][0]["OpenAt"] if market["M5"] else integrated.START
        prior=[r for r in old_bars.get(symbol,[]) if r[1]<=boundary]
        market["M5"]=integrated.normalized_bars(prior)+market["M5"]
        notes.append(dict(Symbol=symbol,RawQuoteMarks=len(market["Quotes"]),
            PrecedingTerms=symbol in terms,AssetClass=row.get("assetClass")))
    need(bool(markets) and any("DatedDevelopment" in m for m in markets),"CONDITIONAL_SOURCE_EMPTY")
    protocol_hash=dated.sha(PROTOCOL.read_bytes())
    OUT.mkdir(exist_ok=False)
    result=OUT/"economic.json"
    calibration=OUT/"calibration.json"
    with tempfile.TemporaryDirectory(prefix="mxm-conditional-eur-") as folder:
        materialized=Path(folder)/"source.json"
        with materialized.open("x") as f:
            materialized.chmod(0o600)
            json.dump(dict(Start=integrated.START,End=integrated.END,
                SourceRun=context.INTEGRATED_RUN,ProtocolSha256=protocol_hash,
                ManagementIntervalMs=30_000,Markets=markets),f,separators=(",",":"))
        input_hash=integrated.hashlib_file(materialized)
        env={k:v for k,v in os.environ.items() if k!="R3_CUSTODY_PRIVATE_KEY_PEM"}
        print("CONDITIONAL_PILOT_PREFLIGHT_AND_NATIVE_EUR",len(markets),flush=True)
        subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
            "--owner-eur-conditional-continuity-pilot",str(materialized),str(result),
            str(calibration),str(SOURCE/"rollover-values.json")],check=True,env=env)
    (OUT/"receipt.json").write_text(json.dumps(dict(ProtocolSha256=protocol_hash,InputSha256=input_hash,
        ArchiveRun=context.INTEGRATED_RUN,SupplementaryRun=dated.SUPPLEMENTARY,
        OriginalSupplementaryHash=extra["CipherSha256"],RolloverRun="45549613144",
        RolloverValuesSha256=receipt["rolloverValuesSha256"],RolloverAcquiredAt=receipt["acquiredAt"],
        UpdatedMatrixSha256=receipt["matrixSha256"],ResultSha256=dated.sha(result.read_bytes()),
        CalibrationSha256=dated.sha(calibration.read_bytes()),MarketSources=notes,
        ExposedDevelopment=True,IndependentConfirmation=False,BrokerNetCertified=False,
        BrokerRequests=0,Orders=0,CloudActivated=False),indent=2)+"\n")
    print("CONDITIONAL_PILOT_PUBLISHED",flush=True)

if __name__=="__main__":main()
