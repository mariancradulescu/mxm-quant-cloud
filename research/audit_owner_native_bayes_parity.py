"""Independent structural/hash audit of the C#-emitted same-event parity receipt.

Never trains, selects trades, forecasts or computes authoritative NET.
This verifies recorded fields and absence of spurious qualification only.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path


def verify(input_path: str, receipt_path: str) -> None:
    raw = Path(input_path).read_bytes()
    inputs = json.loads(raw)
    result = json.loads(Path(receipt_path).read_text())
    assert result["Protocol"] == "OWNER_PROSPECTIVE_BAYES_TRANSITION_V1"
    assert result["OriginalInputSha256"] == hashlib.sha256(raw).hexdigest()
    assert result["SourceClass"] == "SYNTHETIC_NO_ORIGINAL_BROKER_FILL"
    assert result["EventsCompared"] == len(inputs) == len(result["Steps"])
    assert result["MaterialMismatches"] == 0
    assert result["OneSidedMutationRejected"] is True
    assert result["CloudOrderActions"] == 0
    assert result["CloudActivated"] is False
    assert result["NativeSharedCore"] is True
    assert result["InitialOneBookCapitalEur"] == 300
    for field in ("ContinuousFloatingDrawdownCertified", "Hard21SystemCertified",
                  "HistoricalCostsCertified", "IndependentTwelveMonths",
                  "PositiveEconomicEdgeCertified"):
        assert result[field] is False, field
    for i, (observed, row) in enumerate(zip(inputs, result["Steps"])):
        assert observed["At"] == row["Time"] and row["Index"] == i
        assert row["ReplayStepSha256"] == row["CloudAdapterStepSha256"]
        assert len(row["ReplayStepSha256"]) == 64
        assert len(row["LedgerEventChainSha256"]) == 64
        assert row["MaxNumericAbsDifference"] == 0
        assert row["CompletedTrips"] >= 0
        assert row["MarginEur"] is None or row["MarginEur"] >= 0
        assert row["CashEur"] > 0 and row["FloatingEquityEur"] > 0
        for event in row["IntentAndFillFacts"]:
            assert event["Kind"] in {
                "MARK", "REQUEST_OPEN", "OPEN_FILL", "FINANCING",
                "REQUEST_CLOSE", "CLOSE_FILL",
            }
    assert result["FinalCashEur"] == result["Steps"][-1]["CashEur"]
    assert result["FinalClosedNetEur"] == result["Steps"][-1]["ClosedNetEur"]
    assert result["CompleteTrips"] == result["Steps"][-1]["CompletedTrips"]
    assert result["MaximumSampledDrawdown"] >= 0
    print("OWNER_CSHARP_SAME_EVENT_RECEIPT_HASH_AND_SCHEMA_PASS;"
          " SYNTHETIC_ONLY; NO_ECONOMIC_CLAIM")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m research.audit_owner_native_bayes_parity input.json receipt.json")
    verify(sys.argv[1], sys.argv[2])
