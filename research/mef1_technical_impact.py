"""Deterministic technical delta audit of TWO frozen, public MEF1 receipts.

No broker requests, no forecast/return labels, no funded replay or study promotion.
The original is not replaced by the later, incidental diagnostic observation.
"""
import argparse
import hashlib
import json
from pathlib import Path

ORIGINAL_SHA = "ce3a2079296dfe5e68688bbd0782ec5bcd492fc5a00b0c1b2df5555851b47068"
DIAGNOSTIC_SHA = "80e4a278c67cadadee4314019d784619ba412c6ac7a6954e747b3312bffea62b"
ORIGINAL_RUN = 42889124457
DIAGNOSTIC_RUN = 42999359354


def verified(path, sha):
    raw = Path(path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != sha:
        raise ValueError("MEF1_RECEIPT_SHA_MISMATCH")
    return json.loads(raw)


def compare(original, diagnostic):
    """Compare recorded observation fields; never infer cause from changed tariffs."""
    if (original["protocolSha256"] != diagnostic["protocolSha256"] or
        original["protocolSha256"] !=
        "0ae6bc874b6064d7e92495b4f870a75ab71ed94303f6750abb02bb18efb020bd"):
        raise ValueError("PROTOCOL_CHANGED")
    if (original["orders"] != 0 or diagnostic["orders"] != 0 or
        original["cloudActivated"] or diagnostic["cloudActivated"] or
        original["fundedNetEur"] is not None or diagnostic["fundedNetEur"] is not None):
        raise ValueError("UNSAFE_OR_FINANCED_MEASURE_UNEXPECTED")
    if set(original["candidates"]) != set(diagnostic["candidates"]):
        raise ValueError("UNIVERSE_CHANGED")
    results = {}
    for symbol in sorted(original["candidates"]):
        old, new = original["candidates"][symbol], diagnostic["candidates"][symbol]
        oa, ob = old["observations"], new["observations"]
        if [x["date"] for x in oa] != [x["date"] for x in ob]:
            raise ValueError("CALENDAR_CHANGED_" + symbol)
        old_by_date = {x["date"]: x for x in oa}
        newly_accepted, locked_accepted, previously_accepted_changed = [], [], []
        new_fee_with_previously_valid_quote = []
        for obs in ob:
            past = old_by_date[obs["date"]]
            old_spread, new_spread = past["spreadBps"], obs["spreadBps"]
            if old_spread is not None and new_spread != old_spread:
                previously_accepted_changed.append(obs["date"])
            if old_spread is None and new_spread is not None:
                newly_accepted.append(obs["date"])
                if new_spread == 0:
                    locked_accepted.append(obs["date"])
            if (old_spread is not None and new_spread == old_spread and
                past["commissionBps"] is None and obs["commissionBps"] is not None):
                new_fee_with_previously_valid_quote.append(obs["date"])
        margin = new["terms"]["currentMinimumMarginEur"]
        results[symbol] = {
            "observedQuotePairs": [old["validQuotePairs"], new["validQuotePairs"]],
            "costAttributedPairs": [old["costedQuotePairs"], new["costedQuotePairs"]],
            "newlyAcceptedQuoteDates": newly_accepted,
            "newlyAcceptedLockedQuoteDates": locked_accepted,
            "previouslyAcceptedSpreadChangedDates": previously_accepted_changed,
            "feeAttributionAddedToPreviouslyAcceptedQuoteDates":
                new_fee_with_previously_valid_quote,
            "asObservedMedianSpreadBpsDiagnostic": new["medianSpreadBps"],
            "currentFeePlusObservedSpreadMedianBpsDiagnostic":
                new["medianCurrentFeePlusSampledSpreadBps"],
            "individualCurrentMinMarginsEurDiagnostic": margin,
            "sourceEconomicLimitations": (
                "Not a fill, not historically certified tariff; no directional "
                "forecast or funded NET; joint margin and slippage not assessed.")
        }
    return {
        "kind": "TECHNICAL_IMPACT_DIAGNOSTIC_UNQUALIFIED",
        "originalRunId": ORIGINAL_RUN,
        "incidentalDiagnosticRunId": DIAGNOSTIC_RUN,
        "originalReceiptSha256": ORIGINAL_SHA,
        "incidentalReceiptSha256": DIAGNOSTIC_SHA,
        "originalProtocolSha256": original["protocolSha256"],
        "requestsAfterAuth": [original["readOnlyRequestsAfterAuth"],
                              diagnostic["readOnlyRequestsAfterAuth"]],
        "candidates": results,
        "originalEvidenceSuperseded": False,
        "independentEconomicConfirmation": False,
        "brokerFillCertified": False,
        "fundedNetEur": None,
        "economicPromotion": False,
        "interpretation": (
            "Locked quotes explain two AUDUSD quote admissions. Broader fee "
            "attribution changes are also affected by intervening cost/FX code "
            "fixes and current contract observations; do not infer all deltas "
            "come from the BID=ASK condition. Neither historical run has "
            "independently confirmed directional advantage.")
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--diagnostic", required=True)
    parser.add_argument("--output", default="mef1-technical-impact-public.json")
    args = parser.parse_args()
    a, b = verified(args.original, ORIGINAL_SHA), verified(args.diagnostic, DIAGNOSTIC_SHA)
    out = compare(a, b)
    Path(args.output).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(out["kind"], {k:v["costAttributedPairs"] for k,v in out["candidates"].items()})


if __name__ == "__main__":
    main()
