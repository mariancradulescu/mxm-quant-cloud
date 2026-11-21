"""Protected authenticated 13-week C# funded economic development, zero broker access.

Original ciphertext stays immutable. The only plaintext Replay input lives inside
a permission-restricted TemporaryDirectory on the protected custody runner.
Public artifacts contain modeled aggregate finance, coverage and SHA-256 only.
"""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .decode import need
from .guard import CaptureContractError
from .funded_history_gap_plan import verify_plan_receipt
from .funded_history_recovery import ORIGINAL_RUN, scan
from .integrated_market_readback import readback
from .integrated_market_source import CIPHER_DIR, DAY, FUNDED_HISTORY, PUBLIC_DIR

RECOVERY_RUN = "44910122403"
SOURCE_RECEIPT_SHA256 = "35172df63e3e9c147139b836dea5eac989fad3ab8f267d42677c9de5162cf952"
RECOVERY_RECEIPT_SHA256 = "877955b29edf208210ea04748422ea18a00e40723b2759366e45078ea02389dd"
MANIFEST_SHA256 = "e35cfc1d9988f6dc166a7f27349fefedb64fc1f251358761a69dd44e72ae8dbd"
GAP_SHA256 = "03ea1a9d06bdcb7e028c77fa9e360ab36e1dae2b451dc8cc76c16c57091af8b0"
RECOVERY_DIR = Path("funded-history-recovery")
PUBLIC_OUT = Path("funded-history-economic-public")
PROTOCOL = Path("research/FUNDED_ACTION_VALUE_HISTORICAL.md")
EVALUATOR = Path("src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll")
VARIANTS = ("VALUE_CASH", "VALUE_FIRST", "VALUE_HASH", "VALUE_POOLED", "VALUE_PLACEBO",
            "VALUE_ENTRY", "VALUE_CONTEXT", "VALUE_NO_EXHAUSTION")
FIRST = "VALUE_FIRST"
CASH = "VALUE_CASH"
CONTEXT = "VALUE_CONTEXT"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_recovery_binding(original_bytes, receipt_bytes, manifest_bytes, gap_bytes, *,
                            expected_hashes=None):
    """Fail closed BEFORE ciphertext decoding. Overrides only for offline fixtures."""
    hashes = expected_hashes or (SOURCE_RECEIPT_SHA256, RECOVERY_RECEIPT_SHA256,
                                 MANIFEST_SHA256, GAP_SHA256)
    need(tuple(sha256(blob) for blob in (original_bytes, receipt_bytes, manifest_bytes, gap_bytes))
         == tuple(hashes), "FUNDED_DEVELOPMENT_IMMUTABLE_HASH_BINDING")
    original, receipt, manifest, gap = (json.loads(blob) for blob in
                                        (original_bytes, receipt_bytes, manifest_bytes, gap_bytes))
    need(receipt.get("Status") == manifest.get("Status") == "CUSTODY_VERIFIED_PARTIAL_SOURCE"
         and original.get("Status") == receipt.get("OriginalStatus") == "SOURCE_FAILED_CLOSED"
         and original.get("RunId") == receipt.get("OriginalRun") == manifest.get("OriginalRun") == ORIGINAL_RUN
         and receipt.get("RecoveryRun") == RECOVERY_RUN
         and receipt.get("SourceReceiptSha256") == sha256(original_bytes)
         and receipt.get("ManifestSha256") == sha256(manifest_bytes)
         and receipt.get("GapRequestsSha256") == sha256(gap_bytes)
         and receipt.get("OriginalRequestsVerified") == manifest.get("OriginalRequestsVerified") == original["Requests"]
         and receipt.get("OriginalShardsVerified") == manifest.get("OriginalShardsVerified") == len(original["Shards"])
         and manifest["OriginalCipherShards"] == original["Shards"]
         and manifest["ProtocolSha256"] == original["ProtocolSha256"]
         and not original["NewOrders"] and not original["CloudActivated"] and not original["EconomicEvaluations"]
         and not receipt["NewOpenApiRequests"] and not receipt["OrdersSubmitted"] and not receipt["CloudActivated"]
         and not receipt["EconomicEvaluations"], "FUNDED_DEVELOPMENT_RECOVERY_PROVENANCE")
    need(original["Study"] == FUNDED_HISTORY.study and
         (original["Warmup"], original["Start"], original["End"]) ==
         (FUNDED_HISTORY.warmup, FUNDED_HISTORY.start, FUNDED_HISTORY.end),
         "FUNDED_DEVELOPMENT_ORIGINAL_WINDOW")
    need(gap["Requests"] and len(gap["Requests"]) == 263,
         "FUNDED_DEVELOPMENT_GAP_PLAN_SCOPE")
    executable, blocked = verify_plan_receipt(gap_bytes, receipt)
    need(not blocked and len(executable) == len(gap["Requests"]),
         "FUNDED_DEVELOPMENT_UNSUPPORTED_GAPS")
    markets = manifest["Markets"]
    selected = sorted(receipt["CompleteMarketNames"])
    need(set(selected) == set(manifest["CompleteMarketNames"]) and
         set(selected) <= set(markets) and "EURUSD" in selected and
         set(selected).isdisjoint({name for name, state in markets.items() if state["Status"] != "COMPLETE"}),
         "FUNDED_DEVELOPMENT_SELECTED_COVERAGE")
    for name in selected:
        info = markets[name]
        need(info["ActiveHours"] == info["ResponseCompleteHours"]
             and info["ReplayUsableCompletePathMarks"] > 0
             and all(p["Status"] == "COMPLETE" for p in info["Timeframes"].values())
             and info["VerifiedPairedTickHours"] == info["ActiveHours"],
             "FUNDED_DEVELOPMENT_SELECTED_MARKET_NOT_VERIFIED")
    need(markets["NAS100"]["Status"] == "PARTIAL" and "NAS100" not in selected,
         "FUNDED_DEVELOPMENT_NAS100_MUST_STAY_PARTIAL")
    return original, manifest, selected


def verify_original_against_manifest(original, manifest, scanned, gap_bytes):
    """Recalculate all source hashes + page tree; no summary-only authorization."""
    need(scanned["Status"] == manifest["Status"] and
         scanned["Markets"] == manifest["Markets"] and
         scanned["OriginalCipherShards"] == manifest["OriginalCipherShards"] and
         scanned["ActiveHourCoverage"] == manifest["ActiveHourCoverage"] and
         scanned["OriginalRequestsVerified"] == original["Requests"] and
         scanned["OriginalShardsVerified"] == len(original["Shards"]) and
         scanned["OriginalStatus"] == "SOURCE_FAILED_CLOSED",
         "FUNDED_DEVELOPMENT_FRESH_CUSTODY_RECONCILIATION")
    need(json.loads(gap_bytes)["Requests"] == scanned["MissingRequests"],
         "FUNDED_DEVELOPMENT_EXACT_GAP_RECONCILIATION")


def _as_number(row, key):
    value = row.get(key)
    return value if isinstance(value, (int, float, str)) or value is None else None


def extract_safe_economics(private_output, input_sha, selected, original, manifest):
    """Whitelist only group-level economic fields, never snapshots or trade events."""
    need(private_output["SourceRun"] == ORIGINAL_RUN
         and private_output["InputSha256"].lower() == input_sha.lower()
         and private_output["CostEvidence"] == "CONDITIONAL_COST_MODEL_FIXED_ORIGINAL_BROKER_SNAPSHOT"
         and private_output["BrokerNetCertified"] is False
         and private_output["IndependentConfirmation"] is False
         and (private_output["Start"], private_output["End"]) ==
         (FUNDED_HISTORY.start, FUNDED_HISTORY.end),
         "FUNDED_DEVELOPMENT_CSHARP_SOURCE_BINDING")
    result = private_output.get("Result")
    status = private_output.get("Status")
    need(status in ("FINANCED_POLICY_DEVELOPMENT", "NO_CAUSALLY_FINANCEABLE_INPUT"),
         "FUNDED_DEVELOPMENT_CSHARP_RESULT_STATUS")
    output = {
        "Status": status,
        "Evidence": "AUTHENTIC_BID_ASK_HISTORICAL_PRICE_CONDITIONAL_CAPTURE_DATE_FINANCE",
        "Qualification": "DEVELOPMENT_NOT_INDEPENDENT_OR_BROKER_CERTIFIED",
        "OriginalRun": ORIGINAL_RUN, "RecoveryRun": RECOVERY_RUN,
        "InputSha256": input_sha,
        "OriginalSourceReceiptSha256": SOURCE_RECEIPT_SHA256,
        "RecoveryManifestSha256": MANIFEST_SHA256,
        "SelectedMarkets": selected,
        "NAS100": "PARTIAL_EXCLUDED_FROM_FINANCED_RUN_LOCAL_GENUINE_MARKS_NOT_ERASED",
        "Start": FUNDED_HISTORY.start, "End": FUNDED_HISTORY.end,
        "InitialCommonCapitalEurPerPolicy": 300,
        "HistoricalFundingContinuityCertified": False,
        "CaptureDateTermsBackdatedAsConditionalAssumption": True,
        "OrdersSubmitted": 0, "CloudActivated": False,
        "IndependentConfirmation": False, "BrokerNetCertified": False,
        "Scenarios": {}
    }
    if status != "FINANCED_POLICY_DEVELOPMENT":
        need(result is None, "FUNDED_DEVELOPMENT_UNEXPECTED_NONFINANCED_RESULT")
        return output
    need(result is not None and result["Evidence"] == "HISTORICAL_DEVELOPMENT"
         and result["IndependentConfirmation"] is False
         and result["Orders"] == 0 and result["CloudActivation"] is False,
         "FUNDED_DEVELOPMENT_CSHARP_HISTORICAL_REPORT")
    output["EvaluationStart"] = result["EvaluationStart"]
    output["EvaluationEnd"] = result["End"]
    for scenario in ("Central", "Adverse"):
        source = result[scenario]
        books = source["Books"]
        net = source["CompleteModeledNetEur"]
        weekly = source["CompleteComparableWeeklyNetEur"]
        need(set(books) == set(VARIANTS) == set(net) == set(weekly),
             "FUNDED_DEVELOPMENT_FINANCED_CONTROLS_MISSING")
        policies = {}
        for variant in VARIANTS:
            book = books[variant]["Book"]
            fin = book["Financial"]
            boundary = fin["Boundary"]
            cash = boundary["CashEur"]
            final = cash if not boundary["RightCensored"] else None
            modeled = net[variant]
            need(modeled == fin["CompleteModeledNetEur"] and
                 ((modeled is None) == boundary["RightCensored"]),
                 "FUNDED_DEVELOPMENT_PORTFOLIO_CENSURE")
            policies[variant] = {
                "CapitalInitialEur": 300, "CapitalFinalEur": final,
                "ModeledNetEurAfterCosts": modeled,
                "RealizedLedgerNetEur": fin["RealizedLedgerNetEur"],
                "GrossEur": fin["GrossEur"],
                "CostsEur": {key: fin["Costs"][key] for key in
                             ("Commission", "Spread", "Slippage", "Conversion", "Financing")},
                "CompletedTradesByWeek": book["CompletedTradesByWeek"],
                "Hard21ByWeek": book["Hard21ByWeek"],
                "WeeksWithHard21": book["WeeksWithHard21"],
                "AllWeeksHard21": book["BothWeeksHard21"],
                "RightCensored": boundary["RightCensored"],
                "UnverifiedFinancingTrips": fin["FinancingUnverifiedTrips"],
                "UnknownPathTrips": fin["UnknownPathTrips"],
                "UnknownEquityClocks": fin["UnknownEquityClocks"],
                "PeakMarginEur": fin["MaxMarginEur"],
                "PeakPlannedRiskEur": fin["MaxPlannedRiskEur"],
                "SampledFloatingDrawdownPercent": fin["SampledFloatingDrawdownPercent"],
                "KnownSampledEquityClocks": fin["KnownSampledEquityClocks"],
                "ContinuousFloatingDrawdownCertified": fin["ContinuousFloatingDrawdownCertified"],
                "MaximumConcurrentPositions": fin["MaxConcurrent"],
                "StopRiskOverruns": fin["StopRiskOverruns"],
                "ByFamily": book["ByFamily"],
                "BySymbolAggregate": books[variant]["BySymbol"],
                "ComparableWeeklyNetEur": weekly[variant],
                "DeltaVsCashEur": None if modeled is None or net[CASH] is None else
                                  float(modeled) - float(net[CASH]),
                "DeltaVsFirstEur": None if modeled is None or net[FIRST] is None else
                                   float(modeled) - float(net[FIRST]),
            }
        output["Scenarios"][scenario] = {
            "Policies": policies,
            "ContextMinusControlsEur": source["ContextMinusControlsEur"],
            "CalibrationMetrics": source["CalibrationMetrics"],
            "MatchedForecastRows": source["MatchedForecastRows"],
            "LabelCoverage": source["LabelCoverage"],
            "ModelCohorts": source["ModelCohorts"],
            "EvaluationCoverage": result["EvaluationCoverage"],
            "PrimaryAdverseComparisons": source["PrimaryAdverseComparisons"],
        }
    return output


def main():
    need(os.environ.get("GITHUB_EVENT_NAME") == "push"
         and os.environ.get("GITHUB_REF") == "refs/heads/main"
         and os.environ.get("GITHUB_ACTOR") == "mariancradulescu"
         and os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
         "FUNDED_DEVELOPMENT_OWNER_FIRST_ATTEMPT")
    original_bytes = (PUBLIC_DIR / "source.json").read_bytes()
    receipt_bytes = (RECOVERY_DIR / "recovery-receipt.json").read_bytes()
    manifest_bytes = (RECOVERY_DIR / "coverage-manifest.json").read_bytes()
    gap_bytes = (RECOVERY_DIR / "gap-requests.json").read_bytes()
    original, manifest, selected = verify_recovery_binding(
        original_bytes, receipt_bytes, manifest_bytes, gap_bytes)
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "FUNDED_DEVELOPMENT_CUSTODY_KEY_MISSING")
    PUBLIC_OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="funded-private-economic-") as directory:
        private = Path(directory)
        scanned = scan(original, key)
        verify_original_against_manifest(original, manifest, scanned, gap_bytes)
        del scanned
        # Reuse strict original page decoder for only the seven source-complete
        # symbols; partial NAS100 is not silently treated as all-day market data.
        markets = readback(original, key, interval=30_000,
                           scope=FUNDED_HISTORY, include_markets=selected)
        need({m["Name"] for m in markets} == set(selected),
             "FUNDED_DEVELOPMENT_MATERIALIZED_MARKET_COVERAGE")
        for item in markets:
            ref = manifest["Markets"][item["Name"]]
            need(item["RequestedTickHours"] == ref["ActiveHours"] and
                 item["ActiveHours"] == ref["ActiveHours"] and
                 sum(bool(q["Path"]["Complete"]) for q in item["Quotes"]) ==
                 ref["ReplayUsableCompletePathMarks"],
                 "FUNDED_DEVELOPMENT_PRIVATE_REPLAY_MARK_PARITY")
        src = private / "authenticated-replay.json"
        with src.open("w") as handle:
            json.dump({"Start": FUNDED_HISTORY.start, "End": FUNDED_HISTORY.end,
                       "SourceRun": ORIGINAL_RUN,
                       "ProtocolSha256": original["ProtocolSha256"],
                       "ManagementIntervalMs": 30_000,
                       "Markets": markets}, handle, separators=(",", ":"))
        input_sha = sha256(src.read_bytes()) if src.stat().st_size < 500_000_000 else file_sha(src)
        output_file = private / "full-funded-economics.json"
        with (private / "private-run-log").open("w") as logs:
            completed = subprocess.run(
                ["dotnet", str(EVALUATOR), "--funded-action-value-historical-conditional",
                 str(src), str(output_file)], stdout=logs, stderr=subprocess.STDOUT,
                check=False, timeout=19_500)
        need(completed.returncode == 0 and output_file.is_file(),
             "FUNDED_DEVELOPMENT_CSHARP_EVALUATION_FAILURE")
        with output_file.open() as handle:
            economics = json.load(handle)
        public = extract_safe_economics(economics, input_sha, selected, original, manifest)
        out = PUBLIC_OUT / "economic.json"
        out.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
        (PUBLIC_OUT / "receipt.json").write_text(json.dumps({
            "Status": "AUTHENTIC_FUNDED_HISTORICAL_CONDITIONAL_CSHARP_DEVELOPMENT",
            "OriginalSourceRun": ORIGINAL_RUN, "RecoveryRun": RECOVERY_RUN,
            "EvaluationRun": os.environ["GITHUB_RUN_ID"],
            "InputSha256": input_sha,
            "OutputSha256": file_sha(out),
            "OriginalSourceReceiptSha256": SOURCE_RECEIPT_SHA256,
            "RecoveryReceiptSha256": RECOVERY_RECEIPT_SHA256,
            "RecoveryManifestSha256": MANIFEST_SHA256,
            "GapPlanSha256": GAP_SHA256,
            "SelectedMarkets": selected, "CapitalEurPerBook": 300,
            "FinancialTerms": "HISTORICAL_CONDITIONAL_NOT_DATE_CERTIFIED",
            "OrdersSubmitted": 0, "CloudActivated": False,
            "IndependentConfirmation": False, "BrokerNetCertified": False,
        }, indent=2, sort_keys=True) + "\n")
    print("FUNDED_HISTORICAL_CSHARP_COMPLETE", len(selected), "PRIVATE_INPUT_AND_AGGREGATE_RECEIPTS_ONLY")


def file_sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        PUBLIC_OUT.mkdir(exist_ok=True)
        code = str(exc) if isinstance(exc, CaptureContractError) and str(exc).startswith("FUNDED_") else type(exc).__name__
        (PUBLIC_OUT / "failure.json").write_text(json.dumps({
            "Status": "FUNDED_HISTORICAL_DEVELOPMENT_FAILED_CLOSED",
            "FailureCode": code, "OriginalRun": ORIGINAL_RUN,
            "NewOpenApiRequests": 0, "OrdersSubmitted": 0, "CloudActivated": False,
            "EconomicResultsCertified": False
        }, indent=2) + "\n")
        print("FUNDED_HISTORICAL_DEVELOPMENT_FAILED_CLOSED", flush=True)
        raise SystemExit(1) from None
