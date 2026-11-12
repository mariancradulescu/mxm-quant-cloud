"""MRE1: read a SHA-pinned original SEM1 funded-replay public receipt.

Economic comparison only, not a new signal, retuning, broker request,
independent sample or new funded ledger replay. Original source stays frozen.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import zipfile

EXPECTED_SOURCE_SHA256 = "44ca3cf8c2aeff9c46f47e7b0368af4b860ffc34c97459d3545a50655cf8309b"
MEMBER = "session-benchmark-correction-public.json"
POLICIES = ("Filtered", "Momentum", "Long", "Short", "Cash")
SCENARIOS = ("CausalCentral", "CausalAdverse", "CompleteEndpointsCentral", "CompleteEndpointsAdverse")


def load(path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(MEMBER)
    else:
        raw = Path(path).read_bytes()
    actual = sha256(raw).hexdigest()
    if actual != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"SOURCE_HASH_MISMATCH_{actual}")
    return json.loads(raw)


def evaluate(source):
    if source["CapitalEur"] != 300 or source["IndependentConfirmation"] is not False or not source["PortfolioReplayExecuted"]:
        raise ValueError("UNEXPECTED_SOURCE_EVIDENCE_CLASS")
    result = {}
    for horizon in ("30m", "90m"):
        joint = source["SEM1"][horizon]["Joint"]
        result[horizon] = {}
        for scenario in SCENARIOS:
            result[horizon][scenario] = {}
            for policy in POLICIES:
                x = joint[scenario][policy]
                missing = x["UnobservedFixedExits"]
                held = x["OpenPositions"]
                complete = missing == 0 and held == 0
                closed = float(x["ClosedNetEur"])
                margin = float(x["PeakMarginEur"])
                drawdown = float(x["MaxSampledDrawdown"])
                counts = list(x["TripsByWeek"].values())
                result[horizon][scenario][policy] = {
                    "EconomicResultComplete": complete,
                    "CompleteRoundTrips": x["CompleteTrips"],
                    "UnobservedFixedExits": missing,
                    "OpenPositions": held,
                    "ClosedFragmentNetEur": closed,
                    "PortfolioNetEur": closed if complete else None,
                    "PortfolioNetReturnPctOfInitialEur300": 100 * closed / 300 if complete else None,
                    "PeakSampledUsedMarginEur": margin,
                    "PeakSampledMarginPctInitialCapital": 100 * margin / 300,
                    "MaximumSampledDrawdownPct": 100 * drawdown,
                    "NetReturnToSampledDrawdown": (closed / 300 / drawdown if complete and drawdown else None),
                    "ObservedWeeks": len(counts),
                    "HighestObservedWeeklyClosures": max(counts) if counts else 0,
                    "AllObservedWeeksHard21Met": bool(counts) and all(n >= 21 for n in counts),
                }
    ninety = result["90m"]["CausalAdverse"]
    filtered = ninety["Filtered"]["PortfolioNetEur"]
    if filtered is None or filtered >= 0:
        raise ValueError("SEM1_90M_DECISION_CONTRADICTS_ORIGINAL")
    if result["30m"]["CausalAdverse"]["Filtered"]["EconomicResultComplete"]:
        raise ValueError("UNRESOLVED_30M_WAS_SILENTLY_REPLACED")
    return {
        "Study": "MRE1_SEM1_EXISTING_FUNDED_MATERIAL_RETURN_SCREEN",
        "Classification": "EXPOSED_HISTORICAL_NATIVE_BOOK_ECONOMIC_REASSESSMENT_ONLY",
        "ExistingCorrectionPublicJsonSha256": EXPECTED_SOURCE_SHA256,
        "ExistingCorrectionRunId": 43214539052,
        "ExistingCorrectionArtifactId": 13943645086,
        "CapitalInitialEur": 300,
        "SourceOriginalPepperstoneRunId": 43207629492,
        "PolicyAndMarketClocksChanged": False,
        "NewSignalScoringPerformed": False,
        "NewBrokerRequests": 0,
        "NewFundedLedgerReplayPerformed": False,
        "NoCrossStudyCapitalStacking": True,
        "IndependentConfirmation": False,
        "ContinuousDrawdownCertified": False,
        "HistorySampledNotContinuous": True,
        "NoOrdersOrCloudActivation": True,
        "JointPolicyResults": result,
        "Reconciliation": {
            "Sem1Filtered90mAdverseReturnPct": ninety["Filtered"]["PortfolioNetReturnPctOfInitialEur300"],
            "Sem1Long90mAdverseReturnPct": ninety["Long"]["PortfolioNetReturnPctOfInitialEur300"],
            "Sem1Filtered90mAdverseMarginFractionPct": ninety["Filtered"]["PeakSampledMarginPctInitialCapital"],
            "Sem1Filtered90mAdverseSampledDdPct": ninety["Filtered"]["MaximumSampledDrawdownPct"],
            "Sem1Filtered90mVsLongAdverseNetEur": filtered - ninety["Long"]["PortfolioNetEur"],
            "Sem1Filtered90mVsCashAdverseNetEur": filtered,
        },
        "Verdict": "NO_QUALIFIED_MATERIAL_NET_EDGE_FROM_THIS_EXISTING_BOOK",
        "Limitations": [
            "30m causal has unresolved ETHEUR exit: closed fragments not return on total capital",
            "30m complete-endpoint scenarios condition on future-known quote coverage",
            "90m only samples fixed event dates and UTC windows, not continuous weeks",
            "30 percent sampled drawdown cannot certify continuous floating equity risk",
            "Original source uses current observed contract terms for historical prices",
            "Cross-policy benchmark trade frequency and capital occupancy are different",
            "No new predictive mechanism, source collection, independence or cTrader Cloud parity",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_archive")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = evaluate(load(args.source_archive))
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
