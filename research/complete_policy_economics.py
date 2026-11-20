"""Pass the immutable original CVP1 source tape to the new native policy research."""
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .custody import unseal_new
from .decode import need
from .integrated_market_readback import minute_marks, normalized_bars
from .integrated_market_source import digest, margin_snapshot, unpack

SOURCE_RUN = "44162043538"
NATIVE_SHA = "ccd0cd7b4c659a24045023475c51680b2c8800d6879f6f74430ed429dcc2fee9"
ENC = Path("complete-source-encrypted")
PUB = Path("complete-source-public")
OUTPUT = Path("complete-policy-original")
PROTOCOL = Path("research/COMPLETE_POLICY_DISCOVERY_20261120.md")


def readback():
    receipt = json.loads((PUB / "source.json").read_text())
    need(str(receipt["OriginalRun"]) == SOURCE_RUN and receipt["Completed"] and
         receipt["NativeTapeSha256"] == NATIVE_SHA and receipt["OrdersSubmitted"] == 0
         and not receipt["CloudActivated"], "COMPLETE_POLICY_SOURCE_RECEIPT_BINDING")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "COMPLETE_POLICY_CUSTODY_KEY_MISSING")
    cipher = (ENC / "native-tape.enc").read_bytes()
    need(digest(cipher) == receipt["NativeCipherSha256"], "COMPLETE_POLICY_TAPE_CIPHER_HASH")
    plain = unseal_new(cipher, key, SOURCE_RUN)
    need(digest(plain) == NATIVE_SHA, "COMPLETE_POLICY_TAPE_BYTES_HASH")
    del cipher
    tape = json.loads(plain)
    del plain
    start = int(datetime(2026, 5, 4, tzinfo=timezone.utc).timestamp() * 1000)
    need(tape["Start"] == start and tape["End"] - start == 84 * 86400000,
         "COMPLETE_POLICY_FROZEN_SOURCE_WINDOW")
    need([market["Name"] for market in tape["Markets"]] == ["EURUSD", "GBPUSD", "AUDUSD"],
         "COMPLETE_POLICY_FROZEN_SOURCE_UNIVERSE")
    hashes = {part["Name"]: part for part in receipt["SourceChunks"]}
    markets = []
    for market in tape["Markets"]:
        name = market["Name"]
        terms = hashes[name + "-terms"]
        cipher = (ENC / (name + "-terms.enc")).read_bytes()
        need(digest(cipher) == terms["CipherSha256"], "COMPLETE_POLICY_TERMS_CIPHER_HASH")
        plain = unseal_new(cipher, key, SOURCE_RUN)
        need(digest(plain) == terms["PlainSha256"], "COMPLETE_POLICY_TERMS_PLAIN_HASH")
        messages = [unpack([x["RequestType"], x["Request"], x["ResponseType"], x["Response"]])
                    for x in json.loads(plain)]
        symbol_request, symbols = next(pair for pair in messages if isinstance(pair[0], m.ProtoOASymbolByIdReq))
        margin_request, margin_reply = next(pair for pair in messages if isinstance(pair[0], m.ProtoOAExpectedMarginReq))
        terms = symbols.symbol[0]
        need(terms.symbolId == margin_request.symbolId == symbol_request.symbolId[0] and
             terms.tradingMode == 0 and terms.enableShortSelling and
             Decimal(market["Contract"]["MinimumUnits"]) == Decimal(terms.minVolume)/100,
             "COMPLETE_POLICY_CURRENT_VOLUME_OR_SYMBOL_BINDING")
        margin = margin_snapshot(margin_reply, list(margin_request.volume))
        need(len(margin) == 1 and max(Decimal(margin[0]["BuyMargin"]), Decimal(margin[0]["SellMargin"]))
             == Decimal(market["MinMargin"]), "COMPLETE_POLICY_MIN_MARGIN_BINDING")
        tick = Decimal(market["TickSize"])
        protection = None
        if terms.HasField("slDistance") and terms.HasField("tpDistance"):
            percent = terms.distanceSetIn == e.SYMBOL_DISTANCE_IN_PERCENTAGE
            unit = Decimal(".01") if percent else tick
            protection = {"Stop": str(unit * terms.slDistance), "Target": str(unit * terms.tpDistance),
                          "Percentage": percent}
        quotes = [q for day in market["Days"] for q in minute_marks(day["Start"], day["Bid"], day["Ask"], 30_000)]
        # The sealed source ends before 11:05, and the last seen pair may not be
        # extrapolated beyond that archive's coverage to manufacture a fill.
        quotes = [q for q in quotes if 479 <= (q["At"] % 86_400_000) // 60_000 < 665]
        need(len(quotes) > 0, "COMPLETE_POLICY_NO_AUTHENTIC_QUOTE_CLOCKS")
        for key in ("M5", "M15", "H1"):
            need(len(market["Frames"][key]) == receipt["Counts"][name][key], "COMPLETE_POLICY_BAR_COUNT_BINDING")
        markets.append({"Name": name, "Class": "FX", "Contract": market["Contract"], "TickSize": str(tick),
            "Margin": margin, "ShortAllowed": True, "TradingMode": 0, "CostTermsComplete": True,
            "M5": normalized_bars(market["Frames"]["M5"]), "M15": normalized_bars(market["Frames"]["M15"]),
            "H1": normalized_bars(market["Frames"]["H1"]), "Quotes": quotes, "Protection": protection,
            "ActiveHours": len({row["At"] // 3_600_000 for row in quotes}),
            "RequestedTickHours": len({row["At"] // 3_600_000 for row in quotes}), "Schedule": [],
            "ScheduleTimeZone": "UTC_SOURCE_WINDOW"})
    return {"Start": tape["Start"], "End": tape["End"], "SourceRun": SOURCE_RUN,
            "ManagementIntervalMs": 30_000, "Markets": markets, "ProtocolSha256": digest(PROTOCOL.read_bytes())}, receipt


def main():
    authenticated, receipt = readback()
    OUTPUT.mkdir(exist_ok=True)
    print("COMPLETE_POLICY_SOURCE_CLOCKS", [(m["Name"], len(m["Quotes"])) for m in authenticated["Markets"]], flush=True)
    with tempfile.TemporaryDirectory(prefix="complete-policy-original-") as directory:
        path = Path(directory) / "native.json"
        path.write_text(json.dumps(authenticated, separators=(",", ":")))
        path.chmod(0o600)
        result = subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                    "--complete-policy-economics", str(path), str(OUTPUT)], check=False)
        need(result.returncode == 0, "COMPLETE_POLICY_NATIVE_FAILURE")
    report = OUTPUT / "economic.json"
    metadata = dict(SourceRun=SOURCE_RUN, SourceCipherArtifact=14366230834, SourcePlainSha256=NATIVE_SHA,
        ProtocolSha256=authenticated["ProtocolSha256"], NativeOutputSha256=digest(report.read_bytes()),
        PriorReadOnlySourceRequests=receipt["Requests"], NewRequests=0, NewOrders=0, CloudActivated=False,
        BrokerNetCertified=False, IndependentConfirmation=False, ContinuousDrawdownCertified=False)
    (OUTPUT / "receipt.json").write_text(json.dumps(metadata, indent=2)+"\n")
    source = json.loads(report.read_text())
    for scenario, body in source["Result"]["Scenarios"].items():
        for policy, board in body["Policies"].items():
            print("COMPLETE_BOARD "+scenario+" "+policy+" "+json.dumps(board["Summary"], separators=(",", ":")), flush=True)
        information = {k:v for k,v in body.items() if k not in ("Policies", "FrozenObservationModel")}
        print("COMPLETE_INFORMATION "+scenario+" "+json.dumps(information, separators=(",", ":")), flush=True)
    print("COMPLETE_RECEIPT "+json.dumps(metadata, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
