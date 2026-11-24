"""Immutable artifact readback only: no simulation, no broker requests."""
import hashlib
import json
import sys
import zipfile
from decimal import Decimal

ZIP_SHA = "f23fb4616f044086b130343cc8a52adeb20bdbe82c9976020208d71e7d1e8318"
RESULT_SHA = "d08da1b4b907b82b93f172340e42bb3d749d5d7512880d2d27b0d21b4097a052"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def readback(path):
    if sha(path.read_bytes()) != ZIP_SHA:
        raise ValueError("ORIGINAL_ZIP_MISMATCH")
    with zipfile.ZipFile(path) as z:
        raw = z.read("cpe1-recovery-1-economic.json")
    if sha(raw) != RESULT_SHA:
        raise ValueError("ORIGINAL_RESULT_MISMATCH")
    books = json.loads(raw, parse_float=Decimal)["BookSummaries"]
    def key(e):
        return (e["Symbol"],e["Family"],e["Side"],e["EconomicEntry"]["DecisionAt"],
                e["OpenAt"],e["Units"])
    out = []
    for stress in (Decimal("1"),Decimal("1.5"),Decimal("2")):
        econ,simple = [next(b for b in books if b["Stress"] == stress and
                           b["Policy"] == "CPE1_"+p) for p in ("ECONOMIC","SIMPLE")]
        def eligible(e):
            return e["EconomicEvidence"]["ConditionalNetKnown"] and not e["CrossedUnknownHistory"]
        sm = {key(e):e for e in simple["IndividualEpisodes"] if eligible(e)}
        pairs = []
        for e in econ["IndividualEpisodes"]:
            s = sm.get(key(e))
            if not eligible(e) or s is None:
                continue
            pairs.append(dict(symbol=e["Symbol"],side=e["Side"],fillAt=e["OpenAt"],
                 economicCloseAt=e["CloseAt"],simpleCloseAt=s["CloseAt"],
                 economicExit=e["ExitReason"],simpleExit=s["ExitReason"],
                 differenceEur=e["NetEur"]-s["NetEur"]))
        out.append(dict(stress=stress,pairCount=len(pairs),
                        pairDifferenceEur=sum(p["differenceEur"] for p in pairs),pairs=pairs))
    book = next(b for b in books if b["Policy"]=="CPE1_ECONOMIC" and b["Stress"]==Decimal("1.5"))
    episode = next(e for e in book["IndividualEpisodes"] if
                   e["PositionId"]=="UCP1/CPE1_ECONOMIC/NAS100/EQUILIBRIUM_REPAIR/1763338800000")
    entry = episode["EconomicEntry"]
    return dict(evidenceClass="DEVELOPMENT_IMMUTABLE_ARTIFACT_READBACK",
        originalZipSha256=ZIP_SHA,originalResultSha256=RESULT_SHA,
        episode=episode,netToAdmissionRisk=episode["NetEur"]/entry["AdmissionReservedRiskEur"],
        netToFillRisk=episode["NetEur"]/entry["ReservedRiskEur"],
        fillToAdmissionRisk=entry["ReservedRiskEur"]/entry["AdmissionReservedRiskEur"],
        stopAndTargetPriceLevels=None,independentValidation=False,
        pairedAttribution=out,economicEvaluations=0,brokerRequests=0,ordersSubmitted=0)

if __name__ == "__main__":
    from pathlib import Path
    print(json.dumps(readback(Path(sys.argv[1])),default=str,indent=2))
