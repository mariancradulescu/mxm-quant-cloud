"""Prepared, OWNER-gated NAS100 leaf-only Open API recovery, no LIVE/DEMO orders.

Never invoked by ordinary CI or by the consumed original/readback markers.
Original shards are not modified; every new response is independently sealed.
"""
import gzip
import json
import os
import time
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import decode_side, need
from .funded_history_gap_plan import bounded_read_only_request, verify_plan_receipt
from .funded_history_economic_development import (
    RECOVERY_RUN, SOURCE_RECEIPT_SHA256, RECOVERY_RECEIPT_SHA256, MANIFEST_SHA256,
    GAP_SHA256, sha256, verify_recovery_binding,
)
from .integrated_market_source import (
    DAY, FUNDED_HISTORY, HOUR, PUBLIC_DIR, digest, divided_tick_window, pack, unpack,
)
from .owner_readonly_auth import authenticate

RECOVERY_DIR = Path("funded-history-recovery")
CIPHER_OUT = Path("funded-nas100-gap-sealed")
PUBLIC_OUT = Path("funded-nas100-gap-public")
MARKER_PATH = Path("ops/funded-history-nas100-gap-only-once.txt")
MARKER = "OWNER_FUNDED_HISTORY_NAS100_GAP_ONLY_READ_ONLY_BACKFILL_ONCE_44824462289_44910122403"
MAX_MARKET_REQUESTS = 2048
MAX_DEPTH = 24
DEADLINE_SECONDS = 50 * 60


def protected_owner_gate():
    need(os.environ.get("GITHUB_EVENT_NAME") == "push"
         and os.environ.get("GITHUB_REF") == "refs/heads/main"
         and os.environ.get("GITHUB_ACTOR") == "mariancradulescu"
         and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
         and MARKER_PATH.read_bytes() == (MARKER + "\n").encode(),
         "NAS100_GAP_OWNER_MARKER_NOT_AUTHORIZED")


def planned_gaps():
    original, manifest, selected = verify_recovery_binding(
        (PUBLIC_DIR / "source.json").read_bytes(),
        (RECOVERY_DIR / "recovery-receipt.json").read_bytes(),
        (RECOVERY_DIR / "coverage-manifest.json").read_bytes(),
        (RECOVERY_DIR / "gap-requests.json").read_bytes())
    plan = json.loads((RECOVERY_DIR / "gap-requests.json").read_bytes())
    executable, blocked = verify_plan_receipt(
        (RECOVERY_DIR / "gap-requests.json").read_bytes(),
        json.loads((RECOVERY_DIR / "recovery-receipt.json").read_bytes()))
    need(len(executable) == 263 and not blocked and not any(row["Market"] != "NAS100" or
         row["Timeframe"] != "TICKS" or row["Side"] not in ("BID", "ASK") for row in executable)
         and original["Markets"]["NAS100"]["Name"] == "NAS100",
         "NAS100_GAP_FROZEN_ONLY_263_LEAVES")
    return executable


def collect():
    protected_owner_gate()
    gaps = planned_gaps()
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-source-recipient"), run)
    CIPHER_OUT.mkdir(exist_ok=True)
    PUBLIC_OUT.mkdir(exist_ok=True)
    transport = StdlibCTraderTransport()
    started = time.monotonic()
    last_started = 0.
    request_count = 0
    evidence = {"Status": "COLLECTING", "ParentOriginalRun": "44824462289",
                "ParentRecoveryRun": RECOVERY_RUN, "RunId": run,
                "GapPlanSha256": GAP_SHA256, "OriginalSourceReceiptSha256": SOURCE_RECEIPT_SHA256,
                "RequestedLeaves": len(gaps), "NewMarketRequests": 0, "SealedShards": [],
                "OrdersSubmitted": 0, "CloudActivated": False,
                "IndividualGapOutcomes": []}

    def publish():
        (PUBLIC_OUT / "source.json").write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")

    def send(req):
        nonlocal request_count, last_started
        need(request_count < MAX_MARKET_REQUESTS and
             time.monotonic() - started < DEADLINE_SECONDS,
             "NAS100_GAP_BOUNDED_REQUEST_BUDGET")
        time.sleep(max(0., last_started + .25 - time.monotonic()))
        last_started = time.monotonic()
        request_count += 1
        evidence["NewMarketRequests"] = request_count
        return transport.request(req)

    try:
        account = authenticate(transport)
        identity = m.ProtoOASymbolsListReq(ctidTraderAccountId=account, includeArchivedSymbols=False)
        roster = transport.request(identity)
        need(isinstance(roster, m.ProtoOASymbolsListRes) and roster.ctidTraderAccountId == account,
             "NAS100_GAP_PROVIDER_ROSTER")
        matches = [s for s in roster.symbol if s.symbolName == "NAS100"]
        need(len(matches) == 1, "NAS100_GAP_PROVIDER_SYMBOL")
        symbol = matches[0].symbolId
        for i, gap in enumerate(gaps):
            raw = []
            state = "VERIFIED_LEAF_RESPONSES"
            first, last = gap["From"], gap["ToExclusive"] - 1
            side = e.BID if gap["Side"] == "BID" else e.ASK

            def walk(lo, hi, depth):
                need(depth <= MAX_DEPTH, "NAS100_GAP_SPLIT_DEPTH")
                req = m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                    symbolId=symbol, type=side, fromTimestamp=lo, toTimestamp=hi)
                res = bounded_read_only_request(req, send, raw.append, authorized=True)
                if isinstance(res, m.ProtoOAErrorRes):
                    need(res.errorCode == "NO_QUOTES", "NAS100_GAP_UNEXPECTED_PROVIDER_ERROR")
                    return
                if res.hasMore:
                    need(lo < hi, "NAS100_GAP_SINGLE_MS_HAS_MORE")
                    for x, y in divided_tick_window(lo, hi):
                        walk(x, y, depth + 1)
                    return
                decode_side(res.tickData, lo, hi)  # Original genuine tick units only

            try:
                walk(first, last, 0)
            except Exception:
                state = "UNRESOLVED_GAP_PRESERVED"
            # Every transport attempt is retained inside protected recipient-sealed custody.
            body = {"PlanIndex": i, "Plan": gap, "Account": account, "SymbolId": symbol,
                    "Status": state, "RawAttempts": raw}
            compressed = gzip.compress(json.dumps(body, separators=(",", ":")).encode(), mtime=0)
            ciphertext = seal_new(compressed, recipient, run)
            filename = f"nas100-gap-{i:04d}.enc"
            (CIPHER_OUT / filename).write_bytes(ciphertext)
            evidence["SealedShards"].append({
                "File": filename, "CipherSha256": digest(ciphertext),
                "CompressedPlainSha256": digest(compressed)})
            evidence["IndividualGapOutcomes"].append({"Index": i, "Status": state,
                                                      "Side": gap["Side"]})
            publish()
        evidence["Status"] = "GAP_CAPTURE_ENCRYPTED_UNVERIFIED_BY_CUSTODY"
        publish()
    finally:
        transport.close()


def readback():
    """Verify the new protected encrypted gap capture, never replace original shards."""
    protected_owner_gate()
    gaps = planned_gaps()
    run = os.environ["GITHUB_RUN_ID"]
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "NAS100_GAP_CUSTODY_KEY_MISSING")
    evidence = json.loads((PUBLIC_OUT / "source.json").read_bytes())
    need(evidence["RunId"] == run and evidence["ParentOriginalRun"] == "44824462289"
         and evidence["ParentRecoveryRun"] == RECOVERY_RUN
         and evidence["GapPlanSha256"] == GAP_SHA256
         and len(evidence["SealedShards"]) == len(gaps)
         and evidence["OrdersSubmitted"] == 0 and evidence["CloudActivated"] is False,
         "NAS100_GAP_ORIGINAL_LINKAGE")
    complete = []
    missing = []
    account = None
    symbol = None
    for i, meta in enumerate(evidence["SealedShards"]):
        file = CIPHER_OUT / f"nas100-gap-{i:04d}.enc"
        need(meta["File"] == file.name, "NAS100_GAP_SHARD_ORDER")
        ciphertext = file.read_bytes()
        need(digest(ciphertext) == meta["CipherSha256"], "NAS100_GAP_CIPHER_SHA")
        compressed = unseal_new(ciphertext, key, run)
        need(digest(compressed) == meta["CompressedPlainSha256"], "NAS100_GAP_PLAIN_SHA")
        row = json.loads(gzip.decompress(compressed))
        need(row["PlanIndex"] == i and row["Plan"] == gaps[i],
             "NAS100_GAP_PROVENANCE")
        if account is None:
            account, symbol = row["Account"], row["SymbolId"]
        need((row["Account"], row["SymbolId"]) == (account, symbol),
             "NAS100_GAP_ACCOUNT_SYMBOL_INCONSISTENT")
        # No raw prices or account identifiers are exported. Each recorded
        # request is checked before claiming its terminal source evidence.
        for attempt in row["RawAttempts"]:
            if "OriginalPacket" not in attempt:
                continue
            req, res = unpack(attempt["OriginalPacket"])
            need(req.ctidTraderAccountId == account and req.symbolId == symbol and
                 isinstance(req, m.ProtoOAGetTickDataReq) and
                 req.type == (e.BID if gaps[i]["Side"] == "BID" else e.ASK) and
                 req.fromTimestamp >= gaps[i]["From"] and
                 req.toTimestamp < gaps[i]["ToExclusive"],
                 "NAS100_GAP_PACKET_SCOPE")
            if isinstance(res, m.ProtoOAGetTickDataRes) and not res.hasMore:
                decode_side(res.tickData, req.fromTimestamp, req.toTimestamp)
        if row["Status"] == "VERIFIED_LEAF_RESPONSES":
            complete.append(i)
        else:
            missing.append(i)
    result = {"Status": "NAS100_GAP_CUSTODY_VERIFIED_PARTIAL_OR_COMPLETE",
              "SourceRun": run, "OriginalRun": "44824462289",
              "RecoveryRun": RECOVERY_RUN, "OriginalGapPlanSha256": GAP_SHA256,
              "GapsCoveredWithNewOriginalResponses": complete,
              "GapsStillUnresolved": missing, "VerifiedEncryptedShards": len(gaps),
              "MarketRequests": evidence["NewMarketRequests"],
              "OrdersSubmitted": 0, "CloudActivated": False,
              "MergedIntoOriginal": False}
    (PUBLIC_OUT / "readback.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("NAS100_GAP_READBACK_COMPLETE", len(complete), len(missing))


if __name__ == "__main__":
    import sys
    try:
        if sys.argv[1:] == ["--collect"]:
            collect()
        elif sys.argv[1:] == ["--readback"]:
            readback()
        else:
            raise CaptureContractError("NAS100_GAP_INVALID_MODE")
    except Exception:
        PUBLIC_OUT.mkdir(exist_ok=True)
        (PUBLIC_OUT / "failure.json").write_text(json.dumps({
            "Status": "NAS100_GAP_FAILED_CLOSED", "OriginalRun": "44824462289",
            "OrdersSubmitted": 0, "CloudActivated": False,
        }, indent=2) + "\n")
        print("NAS100_GAP_FAILED_CLOSED", flush=True)
        raise SystemExit(1) from None
