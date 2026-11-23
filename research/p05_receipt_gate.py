"""P0.5 public-receipt screening; no broker access, token, decryption or trading."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import zipfile

TIMEFRAMES = ("M15", "M30", "H1", "H4", "D1")
SCHEMA = "P05_NEW_PEPPERSTONE_AUTHENTIC_READ_ONLY_SOURCE"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def load_public_receipt(path):
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != ["receipt.json"]:
            raise ValueError("Unexpected public archive contents")
        return json.loads(archive.read("receipt.json"))


def verify_ciphertext(receipt, sealed_zip):
    source_rows = receipt["sources"]
    names = [item["name"] for item in source_rows]
    if len(names) != len(set(names)):
        raise ValueError("Duplicated encrypted source name")
    with zipfile.ZipFile(sealed_zip) as archive:
        if set(archive.namelist()) != set(names):
            raise ValueError("Missing or extra encrypted source")
        for item in source_rows:
            got = hashlib.sha256(archive.read(item["name"])).hexdigest()
            if got != item["ciphertextSha256"]:
                raise ValueError("Encrypted source SHA mismatch")
    return len(source_rows)


def epoch_ms(iso_utc):
    return int(datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).timestamp() * 1000)


def summarize(receipt):
    if receipt.get("schema") != SCHEMA:
        raise ValueError("Unexpected source schema")
    if receipt.get("ordersSubmitted") != 0 or receipt.get("cloudActivated") is not False:
        raise ValueError("Research safety flags failed")
    if receipt.get("resultsDevelopmentOnly") is not True:
        raise ValueError("Confirmation source flag invalid")
    coverage = receipt["marketCoverage"]
    if len(coverage) != receipt["marketProbesCompleted"] or len(coverage) > receipt["marketProbeTargets"]:
        raise ValueError("Probed-symbol count inconsistency")
    if not 0 <= receipt["visibleSymbols"] <= receipt["totalNonArchivedSymbols"]:
        raise ValueError("Broker inventory inconsistency")
    if not 0 <= receipt["marginsBelow300EUR"] <= receipt["marginsObserved"] <= receipt["contractDetailsExamined"]:
        raise ValueError("Margin count inconsistency")
    start = epoch_ms(receipt["historicalStart"])
    end = epoch_ms(receipt["endExclusive"])
    if start >= end:
        raise ValueError("Invalid historical window")
    horizons = {}
    for tf in TIMEFRAMES:
        bar_total = seen = failures = gap_unknown = 0
        ratios = []
        for symbol, market in coverage.items():
            row = market["timeframes"][tf]
            n = row["bars"]
            if type(n) is not int or n < 0:
                raise ValueError("Invalid bars: " + symbol + "/" + tf)
            if n:
                lo, hi = row["firstUTC"], row["lastUTC"]
                if lo is None or hi is None or not start <= lo <= hi < end:
                    raise ValueError("Bar timestamp outside study window: " + symbol + "/" + tf)
                bar_total += n
                seen += 1
            failures += row["rejectedOrFailedPages"]
            gap_unknown += int(not row["sessionGapsReconciled"])
            ratio = (row.get("sampledSpreadOnlyToMedianRangePercentByMultiplier") or {}).get("1.5")
            if n and ratio is not None and ratio > 0:
                ratios.append(ratio)
        horizons[tf] = {
            "reportedBars": bar_total,
            "symbolsWithBars": seen,
            "failedOrRejectedPages": failures,
            "unreconciledCalendarSymbols": gap_unknown,
            "positiveSpreadRatioSamples": len(ratios),
            "medianSampledSpreadToMedianRangePercentX15": round(statistics.median(ratios), 4) if ratios else None,
            "positiveRatioAtLeast100Percent": sum(v >= 100 for v in ratios),
        }
    pairs = {
        symbol: sum(window["validAsOfPairs"] for window in market["bidAsk"].values())
        for symbol, market in coverage.items()
    }
    suspicious_zero = [
        symbol for symbol, market in coverage.items()
        if pairs[symbol] and market["observedFixedClockMedianSpreadBps"] == 0
    ]
    return {
        "runId": receipt["runId"],
        "sourceWindow": [receipt["historicalStart"], receipt["endExclusive"]],
        "nonArchivedSymbols": receipt["totalNonArchivedSymbols"],
        "visibleSymbols": receipt["visibleSymbols"],
        "contractsExamined": receipt["contractDetailsExamined"],
        "marginsObserved": receipt["marginsObserved"],
        "minimumMarginsUnder300EUR": receipt["marginsBelow300EUR"],
        "sampledSymbols": len(coverage),
        "symbolsWithBidAskPairs": sum(v > 0 for v in pairs.values()),
        "validAsOfBidAskPairs": sum(pairs.values()),
        "zeroSpreadSamplesRequiringReview": suspicious_zero,
        "allInCostMissingSymbols": sum(market["allInCostEur"] is None for market in coverage.values()),
        "horizons": horizons,
        "NET_EUR": None,
        "HARD21": "UNKNOWN",
        "DD_equity_percent": None,
        "VERDICT": "P0.5_INCONCLUSIVE_SOURCE_AND_COST_GAPS",
        "notAProfitabilityClaim": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-zip", type=Path, required=True)
    parser.add_argument("--expected-zip-sha256")
    parser.add_argument("--sealed-zip", type=Path)
    args = parser.parse_args()
    public_hash = sha256_file(args.public_zip)
    if args.expected_zip_sha256 and public_hash != args.expected_zip_sha256:
        raise SystemExit("Public artifact SHA-256 mismatch")
    receipt = load_public_receipt(args.public_zip)
    result = summarize(receipt)
    result["publicZipSha256"] = public_hash
    if args.sealed_zip:
        result["sealedCiphertextHashesVerified"] = verify_ciphertext(receipt, args.sealed_zip)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
