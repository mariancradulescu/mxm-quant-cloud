"""Recover ETP1 finances from its exact original encrypted Pepperstone tape.

No Open API requests, tokens, client IDs, order endpoints or cloud activation.
Original failed source and original ETP1 frozen rules are never overwritten.
"""
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new
from .native_original_openapi_product_replay import require_native_profile_result

ORIGINAL_RUN = "43242754053"
ORIGINAL_ARTIFACT = 13956980229
ORIGINAL_ZIP_SHA = "42e5876e43fa68b441b924d4341508cde90c301ff25b28963c747bc31c2416ea"
ORIGINAL_ENVELOPE_SHA = "d7e28d2d2a22cd78353fd85c8b2a383b5d43cd6d976448340e6075687b29528b"
SOURCE_LABEL = "ORIGINAL_PEPPERSTONE_ETP1_TECH_2026"
SYMBOLS = ("AAPL.US-24", "EURUSD", "GOOG.US-24")
FIXED = "FROZEN_LEGACY_TIME"


def _need(flag, code):
    if not flag:
        raise ValueError("ETP1_RECOVERY_" + code)


def main():
    sealed = Path("failed-original-source/etp1-native-tape.v2.enc").read_bytes()
    _need(sha256(sealed).hexdigest() == ORIGINAL_ENVELOPE_SHA,
          "ORIGINAL_ENVELOPE_SHA256_MISMATCH")
    # Private custody key is only read in the protected custodian job.
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    raw = unseal_new(sealed, key, ORIGINAL_RUN)
    del key, sealed
    tape_sha = sha256(raw).hexdigest()
    tape = json.loads(raw)
    _need(tape.get("SourceLabel") == SOURCE_LABEL, "SOURCE_LABEL_INVALID")
    _need(isinstance(tape.get("Bars"), list) and
          sorted(x["Symbol"] for x in tape["Bars"]) == list(SYMBOLS),
          "BARS_UNIVERSE_MISMATCH")
    _need(isinstance(tape.get("Marks"), list) and
          all(x.get("Symbol") in SYMBOLS for x in tape["Marks"]),
          "MARKS_UNIVERSE_MISMATCH")
    marks_by_symbol = Counter(x["Symbol"] for x in tape["Marks"])
    bars_by_symbol = {x["Symbol"]: len(x["M5"]) for x in tape["Bars"]}
    _need(all(marks_by_symbol[x] > 0 and bars_by_symbol[x] > 0 for x in SYMBOLS),
          "ORIGINAL_MARKS_OR_BARS_ABSENT")
    _need(all(x.get("Contract", {}).get("OriginalBrokerAuthenticated") is True
              and x["Contract"].get("HistoricalTariffContinuityCertified") is False
              for x in tape["Marks"]), "ORIGINAL_CURRENT_TARIFF_PROVENANCE_INVALID")
    # Original source C# replay succeeded in failed #43242754053;
    # the only failing code was its Python Receipt adapter. Reproduce
    # the exact immutable C# evaluation, not a recollection or parameter search.
    with tempfile.TemporaryDirectory(prefix="mxm-etp1-closed-custody-recovery-") as folder:
        inp, out = Path(folder) / "original.json", Path(folder) / "native.json"
        inp.write_bytes(raw)
        inp.chmod(0o600)
        del tape, raw
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(inp), str(out), "--native-etp1"],
                       stdin=subprocess.DEVNULL, check=True, timeout=1000)
        _need(out.is_file(), "NATIVE_RESULT_ABSENT")
        native_bytes = out.read_bytes()
        evaluated = json.loads(native_bytes)
    require_native_profile_result(evaluated, "--native-etp1")
    _need(evaluated.get("SourceSha256") == tape_sha, "NATIVE_TAPE_SHA256_MISMATCH")
    _need(evaluated.get("OriginalInputLabel") == SOURCE_LABEL,
          "NATIVE_ACCOUNT_SOURCE_LABEL_MISMATCH")
    _need(evaluated.get("OriginalInputMarks") ==
          sum(marks_by_symbol.values()), "NATIVE_MARK_COUNT_MISMATCH")
    _need(evaluated.get("OriginalInputBars") ==
          sum(bars_by_symbol.values()), "NATIVE_BAR_COUNT_MISMATCH")
    for book in ("Joint", "LeaderOnly", "FollowerOnly",
                 "Long", "Short", "Fixed90", "Cash"):
        r = evaluated[book]
        _need(isinstance(r.get("CompletedModelRoundTrips"), int),
              "BOOK_ROUNDTRIPS_INVALID")
        _need(r.get("ModelClosedCentralNetEur") is not None and
              r.get("ModelClosedAdverseNetEur") is not None,
              "BOOK_NET_UNPRICED")
    fixed = evaluated["Fixed90"].get("ExitReasonCounts") or {}
    _need(all(x == FIXED for x, count in fixed.items() if count),
          "FIXED_EXIT_COMPARATOR_STILL_ADAPTIVE")
    evaluated.update({
        "RecoveryClassification":"POSTCLOSURE_SCHEMA_RECOVERY_ONLY",
        "OriginalFailedRunId":int(ORIGINAL_RUN),
        "OriginalFailedArtifactId":ORIGINAL_ARTIFACT,
        "OriginalFailedArchiveZipSha256":ORIGINAL_ZIP_SHA,
        "OriginalSourceCiphertextSha256":ORIGINAL_ENVELOPE_SHA,
        "OriginalSourcePlaintextSha256":tape_sha,
        "RecoveredNativeResultSha256":sha256(native_bytes).hexdigest(),
        "OriginalSourceMarksBySymbol":dict(marks_by_symbol),
        "OriginalSourceM5BySymbol":bars_by_symbol,
        "OriginalProtocolSha256":sha256(Path("research/ETP1.md").read_bytes()).hexdigest(),
        "RecoveryProtocolSha256":sha256(Path("research/ETP1_CUSTODY_RECOVERY.md").read_bytes()).hexdigest(),
        "RecoveryRunId":int(os.environ["GITHUB_RUN_ID"]),
        "BrokerRequests":0,
        "OrdersSubmitted":0,
        "CloudActivated":False,
        "IndependentConfirmation":False,
        "OriginalSourceUnchanged":True,
        "OriginalFailedRunStillFailed":True,
        "ResultsAreExposedDevelopment":True,
        "TradingQualified":False,
    })
    Path("etp1-recovered-financial-public.json").write_text(json.dumps(
        evaluated, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "Study":"ETP1",
        "OriginalRunId":int(ORIGINAL_RUN),
        "OriginalArtifactId":ORIGINAL_ARTIFACT,
        "OriginalSourceAuthenticated":True,
        "BrokerRequests":0,
        "JointClosures":evaluated["Joint"]["CompletedModelRoundTrips"],
        "JointCentralNetEur":evaluated["Joint"]["ModelClosedCentralNetEur"],
        "JointAdverseNetEur":evaluated["Joint"]["ModelClosedAdverseNetEur"],
        "FixedControlClosures":evaluated["Fixed90"]["CompletedModelRoundTrips"],
        "IndependentConfirmation":False,
    }), flush=True)


if __name__ == "__main__":
    main()
