"""One-shot immutable-source SEM1 missing fixed-exit provenance diagnostic.

This creates an additional postclosure public receipt; it does not amend SEM1
or its original correction receipts and does not contact the broker.
"""
from hashlib import sha256
import json
from pathlib import Path

from .session_benchmark_correction import main as verify_and_replay


def main():
    # The existing custody runner checks all original plaintext/ciphertext
    # source and public-receipt hashes before invoking the unchanged ledger.
    verify_and_replay()
    enhanced_path = Path("session-benchmark-correction-public.json")
    enhanced = json.loads(enhanced_path.read_bytes())
    if enhanced.get("Classification") != "EXPOSED_RETROSPECTIVE_CORRECTION":
        raise ValueError("SEM1_EXIT_DIAGNOSTIC_CLASSIFICATION")
    scenarios = ("CausalCentral", "CausalAdverse", "CompleteEndpointsCentral",
                 "CompleteEndpointsAdverse")
    families = {}
    for horizon in ("30m", "90m"):
        book = enhanced["SEM1"][horizon]
        families[horizon] = {}
        for scope in ("Joint", "Individual", "Without"):
            cases = {"Joint": book["Joint"]} if scope == "Joint" else book[scope]
            families[horizon][scope] = {}
            for name, case in cases.items():
                families[horizon][scope][name] = {}
                for scenario in scenarios:
                    families[horizon][scope][name][scenario] = {
                        policy: {
                            field: policy_result[field]
                            for field in ("CompleteTrips", "OpenPositions",
                                          "UnobservedFixedExits",
                                          "MissingFixedExitObservations",
                                          "ClosedNetEur", "Rejections",
                                          "TripsByWeek", "MarkClocksWithoutFullEquity")
                        }
                        for policy, policy_result in case[scenario].items()
                    }
    original_joint = families["30m"]["Joint"]["Joint"]["CausalAdverse"]["Filtered"]
    if original_joint["UnobservedFixedExits"] != 1 or len(original_joint["MissingFixedExitObservations"]) != 1:
        raise ValueError("SEM1_EXIT_DIAGNOSTIC_ORIGINAL_COUNT_MISMATCH")
    receipt = {
        "Study": "SEM1_FIXED_EXIT_OBSERVATION_DIAGNOSTIC",
        "Classification": "EXPOSED_POSTCLOSURE_TECHNICAL_DIAGNOSTIC",
        "Originals": enhanced["Originals"],
        "CapitalEur": 300,
        "SemSourceSha256": enhanced["SEM1SourceSha256"],
        "EnhancedOutputSha256": sha256(enhanced_path.read_bytes()).hexdigest(),
        "Purpose": "Locate missing fixed exits without changing clocks, positions, quotes or ledger",
        "SameUnchangedPolicyAppliedToAllCases": True,
        "UnresolvedPositionsRemainUnpriced": True,
        "RawPairMeansOriginalAsOfTickPairNotAnExecutableBrokerFill": True,
        "AbsenceRootCauseRequiresTargetedAuthenticatedSourceCheck": True,
        "Comparisons": families,
        "IndependentConfirmation": False,
        "OrdersSubmitted": 0, "CloudActivated": False, "BrokerRequests": 0,
    }
    Path("sem1-exit-gap-diagnostic-public.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
