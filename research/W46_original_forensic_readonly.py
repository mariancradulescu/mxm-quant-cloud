"""Read-only original W46 arithmetic audit. No broker, replay, fit or orders.

Usage: python research/W46_original_forensic_readonly.py original_artifact_14627239908.zip
This is diagnostic attribution, NOT a funded portfolio counterfactual.
"""
import hashlib
import json
import sys
import zipfile

EXPECTED = {
    "economic.json": "d77603ad36b989b4aa2c3a53dfa3c4323401c4553cb9ecc43793f541f17c45c9",
    "context.json": "7fd4fc6b90b1fe50c2616b3b8483d35fccb7746c3d4e89904ef2be894960b460",
    "receipt.json": "748a6f1739c9528d08faa8fae892a54d6f795d6eb7993b9176b192ac664df4b6",
}
with zipfile.ZipFile(sys.argv[1]) as archive:
    assert set(archive.namelist()) == set(EXPECTED), "Original ZIP entry mismatch"
    contents = {name: archive.read(name) for name in EXPECTED}
for name, expected in EXPECTED.items():
    assert hashlib.sha256(contents[name]).hexdigest() == expected, "Original SHA mismatch: " + name
receipt = json.loads(contents["receipt.json"])
assert receipt["EconomicSha256"] == EXPECTED["economic.json"]
assert receipt["ContextSha256"] == EXPECTED["context.json"]
assert receipt["DataExposed"] and not receipt["BrokerNetCertified"] and not receipt["IndependentConfirmation"]
assert receipt["Orders"] == 0 and not receipt["CloudActivated"]
result = json.loads(contents["economic.json"])["Result"]
assert result["ExposedHistory"] and not result["AssetFinancingAndDrawdownCertified"]
for scenario in ("Central", "Adverse"):
    print(scenario)
    for policy, book in result[scenario]["Books"].items():
        trades = book["Outcome"]["IndividualTrips"]
        net = sum(t["NetEur"] for t in trades)
        gross = sum(t["GrossEur"] for t in trades)
        costs = sum(sum(t["Integrated"][field] for t in trades) for field in (
            "CommissionsEur", "SpreadEur", "SlippageEur", "ConversionEur"))
        assert abs(net - (gross - costs)) < 1e-7, (scenario, policy, "costs")
        assert abs(net - book["Ledger"]["ClosedNetEur"]) < 1e-7, (scenario, policy, "ledger")
        assert abs(300 + net - book["Ledger"]["CashEur"]) < 1e-7, (scenario, policy, "cash")
        assert book["Ledger"]["CompleteRoundTrips"] == len(trades)
        assert book["Ledger"]["OpenPositions"] == 0 and book["Ledger"]["PendingIntents"] == 0
        kinds = [event["Kind"] for event in book["SettlementEvents"]]
        assert kinds.count("OPEN_FILL") == kinds.count("CLOSE_FILL") == len(trades)
        print(policy, len(trades), round(net, 6))
rank = result["Adverse"]["Books"]["RANK"]["Outcome"]["IndividualTrips"]
first = result["Adverse"]["Books"]["FIRST"]["Outcome"]["IndividualTrips"]
xau = [t for t in rank if t["Symbol"] == "XAUUSD"]
assert len(rank) == 86 and len(first) == 86 and len(xau) == 6
assert all(t["Integrated"]["CompletePolicy"]["Prediction"]["Mean"] < 0 for t in rank)
nov10 = [t for t in xau if t["CloseAt"] >= 1794268800000 and t["CloseAt"] < 1794355200000]
assert len(nov10) == 1 and nov10[0]["Side"] == -1
rn, fn = sum(t["NetEur"] for t in rank), sum(t["NetEur"] for t in first)
print("RANK adverse", rn, "XAU", sum(t["NetEur"] for t in xau),
      "other", rn - sum(t["NetEur"] for t in xau))
print("Nov10 short net", nov10[0]["NetEur"], "forecast", nov10[0]["Integrated"]["CompletePolicy"]["Prediction"]["Mean"])
print("RANK-FIRST", rn-fn, "minus Nov10 accounting only", rn-fn-nov10[0]["NetEur"])
print("PASS: original custody/accounting/forecast sign. NO independent economic confirmation.")
