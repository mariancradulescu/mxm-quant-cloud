"""Source-only CPE1 forensics over the existing sealed originals and public result."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from .cpe1_one_integrated_original_execute import recover_original_contract_swap
from .multiscale_conditional_research import recover
from .v32_unified_source_adapter import execute as build_source_tape


PUBLIC_ORIGINAL = Path("cpe1-immutable-original")
PUBLIC_AUDIT = Path("cpe1-funding-source-audit")
SYMBOLS = ("AUDUSD", "EURUSD", "GBPUSD", "NAS100", "US500")
SWAP_FIELDS = (
    "swapPeriod", "swapTime", "swapCalculationType", "swapLong", "swapShort",
    "pipPosition", "swapRollover3Days", "chargeSwapAtWeekends", "skipSWAPPeriods",
    "scheduleTimeZone",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_contracts():
    protocol = json.loads(Path("research/hrc1_protocol.json").read_text())
    fields = {}
    for source in protocol["source"]:
        bundle, decoded, proof = recover(
            Path(source["folder"]), source["run"], source["hash"],
            source["schema"], source["protocol"],
        )
        for symbol in SYMBOLS:
            if symbol not in bundle["symbols"]:
                continue
            metadata = bundle["symbols"][symbol]
            raw = decoded[metadata["contractRawIndex"]][1].symbol[0]
            if raw.symbolId != metadata["symbolId"]:
                raise ValueError("CPE1_FUNDING_AUDIT_WRONG_CONTRACT_IDENTITY")
            values = {key: getattr(raw, key) if raw.HasField(key) else None
                      for key in SWAP_FIELDS}
            fields[symbol] = dict(
                SourceRun=proof["sourceRunId"], ContractSymbolId=raw.symbolId,
                QuoteAsset=metadata["quoteAsset"], AsObservedFields=values,
                MissingRawFields=[key for key, value in values.items() if value is None],
                HistoricalTariffContinuityCertified=False,
            )
    if set(fields) != set(SYMBOLS):
        raise ValueError("CPE1_FUNDING_AUDIT_MISSING_ORIGINAL_CONTRACT")
    return fields


def main():
    original = PUBLIC_ORIGINAL / "cpe1-recovery-1-economic.json"
    receipt = PUBLIC_ORIGINAL / "cpe1-source-and-funding-receipt.json"
    if (digest(original) != "d08da1b4b907b82b93f172340e42bb3d749d5d7512880d2d27b0d21b4097a052"
            or digest(receipt) != "ff728031a93182928c5127c88c83186b313c538cf7314c922e818eab583c804d"):
        raise ValueError("CPE1_FUNDING_AUDIT_ORIGINAL_ARTIFACT_CHANGED")
    frozen_receipt = json.loads(receipt.read_text())
    with tempfile.TemporaryDirectory(prefix="cpe1-funding-source-audit-") as tmp:
        scratch = Path(tmp)
        tape_path = scratch / "private-tape.json"
        if build_source_tape(tape_path) != frozen_receipt["OriginalSourceReceipt"]:
            raise ValueError("CPE1_FUNDING_AUDIT_ORIGINAL_SOURCE_RECEIPT_MISMATCH")
        tape = json.loads(tape_path.read_text())
        archive = archive_contracts()
        funding, bdp_receipt = recover_original_contract_swap(tape)
        if bdp_receipt != frozen_receipt["OriginalBdp1FundingFieldAudit"]:
            raise ValueError("CPE1_FUNDING_AUDIT_ORIGINAL_BDP1_OVERLAY_MISMATCH")
        tape_path.write_text(json.dumps(dict(Tape=tape, Funding=funding), separators=(",", ":")))
        del tape
        output = scratch / "audit.json"
        subprocess.run(
            ["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
             str(tape_path), str(original), str(output), "--cpe1-funding-source-audit"],
            check=True,
        )
        report = json.loads(output.read_text())
    report.update(
        OriginalRun=45370323302, OriginalArtifact=14909305890,
        OriginalResultSha256=digest(original), OriginalReceiptSha256=digest(receipt),
        RawContractSnapshots=archive,
        HistoricalRateSeriesInOriginalSources=False, HistoricalFundingBoundEur=None,
    )
    PUBLIC_AUDIT.mkdir(exist_ok=True)
    (PUBLIC_AUDIT / "cpe1-funding-source-audit.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
