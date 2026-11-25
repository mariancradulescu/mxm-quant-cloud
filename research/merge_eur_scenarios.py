"""Join isolated historical EUR scenario reports without rounding monetary decimals."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_bytes(), parse_float=Decimal)


def exact_json(value):
    if isinstance(value, Decimal):
        require(value.is_finite(), "NONFINITE_DECIMAL")
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k) + ":" + exact_json(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(exact_json(v) for v in value) + "]"
    return json.dumps(value, allow_nan=False)


def combine(protocol_path, paths):
    protocol_path = Path(protocol_path)
    protocol = read(protocol_path)
    protocol_hash = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    stresses = protocol["Stresses"]
    trial_ids = {t["Id"] for t in protocol["Trials"]}
    fit_count = len(protocol["TestBoundaries"]) - 1
    require(len(paths) == len(stresses) and len(set(stresses)) == len(stresses), "SCENARIO_COUNT")
    combined = None
    common = None
    by_stress = {}
    for path in paths:
        document = read(path)
        summary = document["Summary"]
        rows = summary["Results"]
        require(summary["Study"] == protocol["Study"] and summary["ProtocolSha256"] == protocol_hash
                and summary["EvidenceManifestSha256"] == protocol["EvidenceManifestSha256"]
                and summary["TestBoundaries"] == protocol["TestBoundaries"]
                and summary["InitialFitFrom"] == protocol["InitialFitFrom"]
                and summary["DeclaredScenarioTrialCount"] == len(stresses) * len(trial_ids), "PROTOCOL_BINDING")
        require(summary["SourceBrokerRequests"] == summary["Orders"] == 0
                and summary["CloudActivated"] is False
                and summary["IndependentConfirmationCertified"] is False
                and summary["DistilledWinnerForPromotion"] is False
                and document["BrokerFillEvidence"] is False, "RESEARCH_SCOPE")
        require(len(rows) == 1, "NOT_ISOLATED")
        row = rows[0]
        stress = row["SpreadMultiplier"]
        require(stress in stresses and stress not in by_stress
                and row["CommissionAndDebitMultiplier"] == 1 + stress, "SCENARIO_IDENTITY")
        require(len(row["Fits"]) == fit_count
                and [x["AvailableBefore"] for x in row["Fits"]] == protocol["TestBoundaries"][:-1]
                and len(row["Trials"]) == len(trial_ids)
                and {t["Id"] for t in row["Trials"]} == trial_ids
                and all(t["Result"]["InitialCapitalEur"] == 300 for t in row["Trials"]), "TRIAL_OR_FOLD_COMPLETENESS")
        if protocol["Study"] == "EUR_CONTEXTUAL_NET_1":
            require(len(row["OpportunityObservations"]) == 2
                    and len(row["TrialDetails"]) == len(trial_ids), "CONTEXTUAL_DETAILS")
        by_stress[stress] = row
        summary_without_results = {k: v for k, v in summary.items() if k != "Results"}
        fingerprint = {**document, "Summary": summary_without_results}
        if common is None:
            common = fingerprint
            combined = document
        else:
            require(fingerprint == common, "SCENARIO_CUSTODY_OR_WITNESS_MISMATCH")
    require(set(by_stress) == set(stresses), "MISSING_SCENARIO")
    combined["Summary"]["Results"] = [by_stress[s] for s in stresses]
    return combined


def main():
    p = argparse.ArgumentParser()
    p.add_argument("protocol")
    p.add_argument("output")
    p.add_argument("reports", nargs="+")
    args = p.parse_args()
    result = combine(args.protocol, args.reports)
    with Path(args.output).open("x", encoding="utf-8") as stream:
        stream.write(exact_json(result) + "\n")
    print("MERGED_SCENARIOS", len(result["Summary"]["Results"]),
          "TRIALS", result["Summary"]["DeclaredScenarioTrialCount"])


if __name__ == "__main__":
    main()
