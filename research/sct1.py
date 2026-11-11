"""Evaluate a new policy on the verified, unchanged PRR1 input tape."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new

SOURCE_RUN = "43031103899"
SOURCE_ARTIFACT = 13861254511
SOURCE_ENVELOPE_SHA = "072184ff6c2a67222d9901826f576e8eb2c2070cf2214d9eeffc20afb64367bb"
SOURCE_TAPE_SHA = "8893c3348a306c05680f427c79d8f0829a76221783378303f540116b0be0b116"


def main():
    sealed = Path("original-source/prr1-native-tape.v2.enc").read_bytes()
    if sha256(sealed).hexdigest() != SOURCE_ENVELOPE_SHA:
        raise ValueError("SCT1_ORIGINAL_ENVELOPE_HASH_MISMATCH")
    secret = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(sealed, secret, SOURCE_RUN)
    del secret
    if sha256(tape).hexdigest() != SOURCE_TAPE_SHA:
        raise ValueError("SCT1_ORIGINAL_TAPE_HASH_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="mxm-sct1-custody-") as folder:
        source, output = Path(folder) / "tape.json", Path(folder) / "result.json"
        source.write_bytes(tape)
        source.chmod(0o600)
        del tape
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source), str(output), "--native-sct1"],
                       check=True, timeout=600)
        report = json.loads(output.read_text())
    if report["SourceSha256"] != SOURCE_TAPE_SHA:
        raise ValueError("SCT1_NATIVE_INPUT_HASH_MISMATCH")
    for old, new in {
        "OnlyFx": "OnlyIndex", "OnlyCommodity": "OnlyOil",
        "FxMarginalCentralEur": "IndexMarginalCentralEur",
        "FxMarginalAdverseEur": "IndexMarginalAdverseEur",
        "CommodityMarginalCentralEur": "OilMarginalCentralEur",
        "CommodityMarginalAdverseEur": "OilMarginalAdverseEur",
        "RequiredClosedTradeHeldMinuteMarks": "RequiredClosedTradeHeldFiveMinuteMarks",
        "MissingClosedTradeHeldMinuteMarks": "MissingClosedTradeHeldFiveMinuteMarks",
    }.items():
        report[new] = report.pop(old)
    report.update(ProtocolSha256=sha256(Path("research/SCT1.md").read_bytes()).hexdigest(),
                  SourceRunId=int(SOURCE_RUN), SourceArtifactId=SOURCE_ARTIFACT,
                  SourceCiphertextSha256=SOURCE_ENVELOPE_SHA,
                  SourceClassification="ORIGINAL_PEPPERSTONE_REUSED_EXPOSED_DEVELOPMENT",
                  ExpectedFiveMinuteClocks=1440, MarkIntervalSeconds=300,
                  BrokerRequests=0, OrdersSubmitted=0, CloudActivated=False,
                  IndependentConfirmation=False, InitialModelCapitalEur=300)
    Path("sct1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    r = report["Receipt"]
    print(json.dumps({"Study": "SCT1", "Closures": r["CompletedModelRoundTrips"],
                      "AdverseEur": r["ModelClosedAdverseNetEur"],
                      "DifferentiatedDecisions": r["DistinctHistoricalStressDecisions"]}))


if __name__ == "__main__":
    main()
