"""Source-only CPE1 forensics over the existing sealed originals and public result."""
import hashlib
import json
import os
import subprocess
import tempfile
from base64 import b64decode
from pathlib import Path

from .cpe1_one_integrated_original_execute import recover_original_contract_swap
from .ctrader_proto import OpenApiMessages_pb2 as messages
from .mde1_cumulative_original_native import HXC_RUN, XMH_RUN, _one_original
from .multiscale_conditional_research import recover
from .p05_source_economic_gate import RUN as P05_RUN, _load_sealed, _roster
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


def snapshot(run, contract):
    values = {key: getattr(contract, key) if contract.HasField(key) else None
              for key in SWAP_FIELDS}
    return dict(
        SourceRun=int(run), ContractSymbolId=contract.symbolId,
        AsObservedFields=values,
        MissingRawFields=[key for key, value in values.items() if value is None],
        HistoricalTariffContinuityCertified=False,
    )


def archive_contracts():
    protocol = json.loads(Path("research/hrc1_protocol.json").read_text())
    fields = {symbol: [] for symbol in SYMBOLS}
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
            fields[symbol].append(snapshot(proof["sourceRunId"], raw))
    if not all(fields.values()):
        raise ValueError("CPE1_FUNDING_AUDIT_MISSING_ORIGINAL_CONTRACT")

    key = os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    for run in (HXC_RUN, XMH_RUN):
        _, bundle, _, _ = _one_original(run, key)
        roster = messages.ProtoOASymbolsListRes.FromString(
            b64decode(bundle["identityRaw"][1]["responseProtobuf"], validate=True))
        names = {row.symbolId: row.symbolName for row in roster.symbol if row.symbolName in SYMBOLS}
        for packet in bundle["identityRaw"][2:]:
            detail = messages.ProtoOASymbolByIdRes.FromString(
                b64decode(packet["responseProtobuf"], validate=True))
            for contract in detail.symbol:
                if contract.symbolId in names:
                    fields[names[contract.symbolId]].append(snapshot(run, contract))

    p05 = json.loads(Path("p05-public/receipt.json").read_text())
    sealed = Path("p05-sealed")
    roster_entry = next(row for row in p05["sources"] if row["kind"] == "ROSTER")
    names = _roster(_load_sealed(roster_entry, sealed, key))
    for shard in p05["sources"]:
        if shard["kind"] != "CONTRACTS":
            continue
        for packet in _load_sealed(shard, sealed, key):
            if packet.get("resType") != "ProtoOASymbolByIdRes":
                continue
            detail = messages.ProtoOASymbolByIdRes.FromString(b64decode(packet["res"], validate=True))
            for contract in detail.symbol:
                symbol = names.get(contract.symbolId)
                if symbol in fields:
                    fields[symbol].append(snapshot(P05_RUN, contract))
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
