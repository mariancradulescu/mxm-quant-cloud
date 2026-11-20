"""Reconcile original rows in Decimal without running any frozen strategy."""
import argparse
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

NATIVE = "514848c4df4061dca7461f269f5836dcf7cf2a263c3a0d85445f4ca8431bd95c"
FORENSICS = "c961d1ec34050a88f5f30a994a2c731530aa5a087c2fc3477e7fbe03e835118b"
COMPONENTS = ("CommissionsEur", "SpreadEur", "SlippageEur", "ConversionEur")
TOLERANCE = Decimal("1e-18")


def audit(economic_path, forensics_path):
    with ZipFile(economic_path) as z:
        body = z.read("economic.json")
        receipt = json.loads(z.read("receipt.json"))
    with ZipFile(forensics_path) as z:
        diagnostic = z.read("forensics.json")
    assert hashlib.sha256(body).hexdigest() == receipt["NativeOutputSha256"] == NATIVE
    assert hashlib.sha256(diagnostic).hexdigest() == FORENSICS
    economic = json.loads(body, parse_float=Decimal)

    def amounts(rows):
        gross = sum(row["GrossEur"] for row in rows)
        net = sum(row["NetEur"] for row in rows)
        costs = {key: sum(row["Integrated"][key] for row in rows) for key in COMPONENTS}
        assert abs(gross-net-sum(costs.values())) < TOLERANCE
        return dict(Trades=len(rows), GrossEur=gross, NetEur=net, **costs)

    first = economic["Policies"]["INTEGRATED_COHERENT_FIRST"]
    trips = first["Outcome"]["IndividualTrips"]
    groups = defaultdict(list)
    for event in first["NonMarkEvents"]:
        groups[event["PositionId"]].append(event)
    nonbracket, overruns = [], []
    for trip in trips:
        events = groups[trip["PositionId"]]
        entry = next(e for e in events if e["Kind"] == "OPEN_FILL")
        exit_fill = next(e for e in events if e["Kind"] == "CLOSE_FILL")
        request = next(e for e in reversed(events) if e["Kind"] == "REQUEST_CLOSE" and e["At"] < trip["CloseAt"])
        assert entry["At"] == trip["OpenAt"] and exit_fill["At"] == trip["CloseAt"] > request["At"]
        assert abs(entry["FeeEur"]+exit_fill["FeeEur"]-trip["Integrated"]["CommissionsEur"]) < TOLERANCE
        if any(term in trip["ExitReason"] for term in ("ADAPTIVE_PATH", "PROTECT_ACCUMULATED", "M15_THESIS")):
            nonbracket.append(trip)
        if trip["NetEur"] < -trip["EntryRiskEur"]:
            overruns.append(dict(Symbol=trip["Symbol"], PositionId=trip["PositionId"], R=trip["R"],
                                 NetEur=trip["NetEur"], DelayMs=exit_fill["At"]-request["At"],
                                 InitialRiskEur=trip["EntryRiskEur"], UnknownPath=trip["CrossedUnknownHistory"]))
    assert len(nonbracket) == 132 and len(overruns) == 98
    return dict(Source=NATIVE, Forensics=FORENSICS, NonBracket=amounts(nonbracket), RiskOverruns=overruns,
        ByPolicy={name: amounts(book["Outcome"]["IndividualTrips"]) for name, book in economic["Policies"].items()},
        ClosedStudyReruns=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("economic", type=Path)
    parser.add_argument("forensics", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.economic, args.forensics), default=str, indent=2)+"\n")
