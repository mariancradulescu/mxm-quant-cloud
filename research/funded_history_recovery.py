"""Custody-only, fail-closed recovery inventory for an interrupted authentic source.

Never calls Open API, creates orders, or treats missing leaves as NO_QUOTES.
Only the protected GitHub custody job may unseal the original original-run shards.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .custody import unseal_new
from .decode import decode_side, need
from .guard import CaptureContractError
from .integrated_market_source import (
    CIPHER_DIR, PUBLIC_DIR, DAY, HOUR, FUNDED_HISTORY, TICK_PAGE_MODEL,
    bars_from_page, digest, divided_tick_window, request_capacity, tick_windows, unpack,
)

OUT = Path("funded-history-recovery")
ORIGINAL_RUN = "44824462289"


def _fingerprint(record):
    return hashlib.sha256(json.dumps(record, separators=(",", ":")).encode()).hexdigest()


def scan(receipt, key, expected_run=ORIGINAL_RUN, scope=FUNDED_HISTORY, cipher_dir=None):
    """Verify every ciphertext and every original packet; emit only safe coverage metadata."""
    cipher_dir = Path(cipher_dir) if cipher_dir is not None else CIPHER_DIR
    need(receipt.get("Study") == scope.study and receipt.get("RunId") == str(expected_run) and
         receipt.get("Status") == "SOURCE_FAILED_CLOSED" and
         receipt.get("NewOrders") == 0 and receipt.get("CloudActivated") is False and
         receipt.get("EconomicEvaluations") == 0 and receipt.get("TickPageModel") == TICK_PAGE_MODEL and
         receipt.get("RequestCapacity") == request_capacity(scope) and
         receipt.get("ProtocolSha256") == digest(scope.protocol.read_bytes()) and
         (receipt.get("Warmup"), receipt.get("Start"), receipt.get("End")) ==
         (scope.warmup, scope.start, scope.end), "RECOVERY_ORIGINAL_RECEIPT_BINDING")
    shards = {v["File"]: v for v in receipt["Shards"]}
    need(len(shards) == len(receipt["Shards"]) and
         set(shards) == {f.name for f in cipher_dir.glob("*.enc")} and
         "account-contracts.enc" in shards, "RECOVERY_ORIGINAL_SHARD_INVENTORY")
    decoded = set()
    request_count = 0

    def open_shard(name):
        nonlocal request_count
        need(name in shards and name not in decoded, "RECOVERY_SHARD_DUPLICATE_OR_ABSENT")
        raw = (cipher_dir / name).read_bytes()
        need(digest(raw) == shards[name]["CipherSha256"], "RECOVERY_CIPHERTEXT_HASH")
        compressed = unseal_new(raw, key, str(expected_run))
        need(digest(compressed) == shards[name]["CompressedPlainSha256"],
             "RECOVERY_COMPRESSED_PLAIN_HASH")
        body = json.loads(gzip.decompress(compressed))
        decoded.add(name)
        request_count += len(body.get("Raw", body.get("Identity", ())))
        return body

    contracts = open_shard("account-contracts.enc")
    identities = [unpack(p) for p in contracts["Identity"]]
    need(len(identities) >= 3 and
         isinstance(identities[0][1], m.ProtoOATraderRes) and
         isinstance(identities[1][1], m.ProtoOAAssetListRes) and
         isinstance(identities[2][1], m.ProtoOASymbolsListRes),
         "RECOVERY_ORIGINAL_ACCOUNT_IDENTITY")
    account = identities[0][0].ctidTraderAccountId
    trader, assets, roster = (row[1] for row in identities[:3])
    asset_by_id = {a.assetId: a.name for a in assets.asset}
    need("pepperstone" in trader.trader.brokerName.casefold() and
         asset_by_id.get(trader.trader.depositAssetId) == "EUR" and
         all(q.ctidTraderAccountId == account for q, _ in identities) and
         receipt["EnabledSymbols"] == sum(bool(s.enabled) for s in roster.symbol),
         "RECOVERY_ORIGINAL_PROVIDER_ACCOUNT")
    available = {s.symbolName: s for s in roster.symbol}
    names = {record["Name"] for record in contracts["Markets"]}
    need(names == set(receipt["Markets"]) and len(names) == len(contracts["Markets"]) and
         names == {next((n for n in aliases if n in available), None)
                   for _, aliases in scope.universe} - {None},
         "RECOVERY_ORIGINAL_MARKET_ROSTER")
    verified = {}
    gaps = []
    hour_rows = []
    for meta in contracts["Markets"]:
        name = meta["Name"]
        symbol = available[name]
        observed = receipt["Markets"][name]
        periods = {}
        active = set()
        bar_file = f"{name}-bars.enc"
        need(bar_file in shards, "RECOVERY_MISSING_BAR_SHARD")
        bar_body = open_shard(bar_file)
        need(bar_body["Name"] == name, "RECOVERY_BAR_SHARD_BINDING")
        packets = iter(bar_body["Raw"])
        bar_complete = True
        for period, (_, chunk) in scope.periods.items():
            counts = {"Status": "COMPLETE", "Requests": 0, "Bars": 0, "NoQuotesPages": 0}
            for first in range(scope.warmup, scope.end, chunk):
                last = min(scope.end, first + chunk)
                row = next(packets, None)
                if row is None:
                    bar_complete = False
                    counts["Status"] = "INCOMPLETE"
                    gaps.append(dict(Market=name, Timeframe=period, Side="BARS",
                                     From=first, ToExclusive=last, Reason="MISSING"))
                    continue
                req, res = unpack(row)
                need(isinstance(req, m.ProtoOAGetTrendbarsReq) and
                     req.ctidTraderAccountId == account and req.symbolId == symbol.symbolId and
                     e.ProtoOATrendbarPeriod.Name(req.period) == period and
                     (req.fromTimestamp, req.toTimestamp) == (first, last),
                     "RECOVERY_BAR_REQUEST_ORDER")
                counts["Requests"] += 1
                if isinstance(res, m.ProtoOAErrorRes) and res.errorCode != "NO_QUOTES":
                    bar_complete = False
                    counts["Status"] = "INCOMPLETE"
                    gaps.append(dict(Market=name, Timeframe=period, Side="BARS",
                                     From=first, ToExclusive=last, Reason="PROVIDER_ERROR",
                                     ProviderCode=res.errorCode))
                    continue
                counts["NoQuotesPages"] += isinstance(res, m.ProtoOAErrorRes)
                rows = bars_from_page(res, period, first, last, scope.periods)
                counts["Bars"] += len(rows)
                active.update(r[0] // HOUR * HOUR for r in rows if r[0] >= scope.start)
            periods[period] = counts
            if counts["Status"] == "COMPLETE":
                need(counts["Bars"] == observed["Bars"].get(period) and
                     counts["NoQuotesPages"] == observed["BarNoQuotesPages"].get(period),
                     "RECOVERY_BAR_COUNTER_MISMATCH")
        need(next(packets, None) is None, "RECOVERY_EXTRA_BAR_PACKET")
        if bar_complete:
            need(len(active) == observed["ActiveHours"], "RECOVERY_ACTIVE_HOUR_COUNTER")
        bid_ticks = ask_ticks = 0
        completed_hours = 0
        root_requests = 0
        partial_roots = 0
        if bar_complete:
            for day in range(scope.start, scope.end, DAY):
                windows = list(tick_windows(day, active))
                key_name = f"{name}-{day}-ticks.enc"
                if not windows:
                    need(key_name not in shards, "RECOVERY_UNPLANNED_TICK_SHARD")
                    continue
                if key_name in shards:
                    body = open_shard(key_name)
                    need(body["Name"] == name and body["Day"] == day,
                         "RECOVERY_TICK_SHARD_BINDING")
                    raw = body["Raw"]
                else:
                    raw = []
                offset = 0
                segments = {e.BID: [], e.ASK: []}

                def walk(side, first, last):
                    nonlocal offset, root_requests, bid_ticks, ask_ticks
                    if offset == len(raw):
                        segments[side].append((first, last, "MISSING"))
                        return
                    req, res = unpack(raw[offset])
                    # A missing subtree can be followed by a later sibling/root.
                    # Never consume that later packet as evidence for this interval.
                    if (not isinstance(req, m.ProtoOAGetTickDataReq) or
                            (req.type, req.fromTimestamp, req.toTimestamp) !=
                            (side, first, last)):
                        segments[side].append((first, last, "MISSING"))
                        return
                    need(req.ctidTraderAccountId == account and req.symbolId == symbol.symbolId,
                         "RECOVERY_TICK_ACCOUNT_SYMBOL")
                    offset += 1
                    root_requests += 1
                    if isinstance(res, m.ProtoOAErrorRes):
                        if res.errorCode == "NO_QUOTES":
                            segments[side].append((first, last, "NO_QUOTES"))
                        else:
                            code = res.errorCode if res.errorCode.isascii() and res.errorCode.replace("_", "").isalnum() else "UNCLASSIFIED"
                            segments[side].append((first, last, "PROVIDER_ERROR", code))
                        return
                    need(isinstance(res, m.ProtoOAGetTickDataRes), "RECOVERY_TICK_RESPONSE_TYPE")
                    if res.hasMore:
                        need(first < last, "RECOVERY_UNSPLITTABLE_TRUNCATED_TICK")
                        for lo, hi in divided_tick_window(first, last):
                            walk(side, lo, hi)
                    else:
                        rows = decode_side(res.tickData, first, last)
                        if side == e.BID:
                            bid_ticks += len(rows)
                        else:
                            ask_ticks += len(rows)
                        segments[side].append((first, last, "TERMINAL"))

                for first, last in windows:
                    for side in (e.BID, e.ASK):
                        walk(side, first, last)
                    for hour in (first // HOUR * HOUR, (first // HOUR + 1) * HOUR):
                        if hour not in active or hour > last:
                            continue
                        by_side = {}
                        for side, side_name in ((e.BID, "BID"), (e.ASK, "ASK")):
                            leaves = [r for r in segments[side] if r[1] >= hour and r[0] < hour + HOUR]
                            covered = sum(min(r[1], hour + HOUR-1) - max(r[0], hour) + 1
                                          for r in leaves if r[2] in ("TERMINAL", "NO_QUOTES"))
                            need(covered <= HOUR, "RECOVERY_TICK_LEAF_OVERLAP")
                            errors = [r for r in leaves if r[2] == "PROVIDER_ERROR"]
                            by_side[side_name] = ("COMPLETE" if covered == HOUR else
                                                 "PROVIDER_ERROR" if errors else
                                                 "PARTIAL" if covered else "MISSING")
                        status = ("COMPLETE" if all(v == "COMPLETE" for v in by_side.values()) else "INCOMPLETE")
                        completed_hours += status == "COMPLETE"
                        hour_rows.append(dict(Market=name, Timeframe="TICKS", HourUtcMs=hour,
                                              Status=status, **by_side))
                    if any(r[2] not in ("TERMINAL", "NO_QUOTES") and first <= r[0] <= last
                           for side in segments for r in segments[side]):
                        partial_roots += 1
                need(offset == len(raw), "RECOVERY_UNEXPECTED_TICK_PACKET")
                for side, side_name in ((e.BID, "BID"), (e.ASK, "ASK")):
                    for r in segments[side]:
                        if r[2] not in ("TERMINAL", "NO_QUOTES"):
                            gaps.append(dict(Market=name, Timeframe="TICKS", Side=side_name,
                                             From=r[0], ToExclusive=r[1]+1, Reason=r[2],
                                             **({"ProviderCode": r[3]} if len(r) > 3 else {})))
        else:
            # No safe activity-hour roster can be derived from incomplete native bars.
            for key_name in sorted(k for k in shards if k.startswith(f"{name}-") and k.endswith("-ticks.enc")):
                body = open_shard(key_name)
                need(body.get("Name") == name and isinstance(body.get("Raw"), list),
                     "RECOVERY_ORPHAN_TICK_SHARD")
                for row in body["Raw"]:
                    unpack(row)
            gaps.append(dict(Market=name, Timeframe="TICKS", Side="BID_ASK",
                             From=scope.start, ToExclusive=scope.end,
                             Reason="BAR_ACTIVITY_UNVERIFIED"))
        complete = (bar_complete and completed_hours == len(active))
        if complete:
            need(observed["SourceTickHours"] == completed_hours and
                 observed["Bid"] == bid_ticks and observed["Ask"] == ask_ticks,
                 "RECOVERY_COMPLETE_MARKET_COUNTER_MISMATCH")
        verified[name] = {"Status": "COMPLETE" if complete else "PARTIAL",
                          "Timeframes": periods, "ActiveHours": len(active) if bar_complete else None,
                          "VerifiedPairedTickHours": completed_hours,
                          "ReceiptSourceTickHours": observed["SourceTickHours"],
                          "VerifiedBidTicks": bid_ticks if bar_complete else None,
                          "VerifiedAskTicks": ask_ticks if bar_complete else None,
                          "TickRequests": root_requests, "PartialRoots": partial_roots}
    need(decoded == set(shards), "RECOVERY_ORPHAN_ENCRYPTED_SHARD")
    need(request_count == receipt["Requests"], "RECOVERY_ORIGINAL_REQUEST_COUNT")
    return {
        "Status": "CUSTODY_VERIFIED_PARTIAL_SOURCE", "OriginalStatus": receipt["Status"],
        "OriginalFailure": receipt.get("Failure"), "OriginalFailureAt": receipt.get("FailureAt"),
        "OriginalRun": str(expected_run), "Study": scope.study,
        "ProtocolSha256": receipt["ProtocolSha256"],
        "OriginalRequestsVerified": request_count, "OriginalShardsVerified": len(decoded),
        "OriginalCipherShards": receipt["Shards"], "Markets": verified,
        "ActiveHourCoverage": hour_rows, "MissingRequests": gaps,
        "CompleteMarketNames": sorted(k for k, v in verified.items() if v["Status"] == "COMPLETE"),
        "NewOpenApiRequests": 0, "EconomicEvaluations": 0,
        "OrdersSubmitted": 0, "CloudActivated": False,
    }


def main():
    original = json.loads((PUBLIC_DIR / "source.json").read_text())
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "RECOVERY_PROTECTED_KEY_MISSING")
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and
         os.environ.get("GITHUB_REF") == "refs/heads/main" and
         os.environ.get("GITHUB_ACTOR") == "mariancradulescu" and
         os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
         "RECOVERY_OWNER_READBACK_FIRST_ATTEMPT_ONLY")
    OUT.mkdir(exist_ok=True)
    try:
        result = scan(original, key)
        manifest = OUT / "coverage-manifest.json"
        manifest.write_text(json.dumps({k: v for k, v in result.items() if k != "MissingRequests"},
                                        indent=2, sort_keys=True) + "\n")
        requests = OUT / "gap-requests.json"
        requests.write_text(json.dumps({"OriginalRun": ORIGINAL_RUN,
                                         "Status": "PREPARED_NOT_AUTHORIZED_FOR_BROKER_ACCESS",
                                         "Requests": result["MissingRequests"],
                                         "NewOpenApiRequests": 0}, indent=2, sort_keys=True) + "\n")
        (OUT / "recovery-receipt.json").write_text(json.dumps({
            "Status": result["Status"], "OriginalStatus": original["Status"],
            "OriginalRun": ORIGINAL_RUN, "RecoveryRun": os.environ["GITHUB_RUN_ID"],
            "SourceReceiptSha256": digest((PUBLIC_DIR / "source.json").read_bytes()),
            "ManifestSha256": digest(manifest.read_bytes()),
            "GapRequestsSha256": digest(requests.read_bytes()),
            "OriginalRequestsVerified": result["OriginalRequestsVerified"],
            "OriginalShardsVerified": result["OriginalShardsVerified"],
            "CompleteMarketNames": result["CompleteMarketNames"],
            "NewOpenApiRequests": 0, "OrdersSubmitted": 0,
            "EconomicEvaluations": 0, "CloudActivated": False,
        }, indent=2, sort_keys=True) + "\n")
        print("CUSTODY_RECOVERY_VERIFIED", result["OriginalRequestsVerified"],
              result["OriginalShardsVerified"], result["CompleteMarketNames"])
    except Exception as exc:
        (OUT / "recovery-failure.json").write_text(json.dumps({
            "OriginalRun": ORIGINAL_RUN, "Status": "CUSTODY_RECOVERY_FAILED_CLOSED",
            "FailureType": type(exc).__name__, "FailureCode": str(exc) if isinstance(exc, CaptureContractError) else "INTERNAL_ERROR",
            "NewOpenApiRequests": 0, "OrdersSubmitted": 0, "EconomicEvaluations": 0,
        }, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
