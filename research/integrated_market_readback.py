"""Verify sealed original data and decode it for the shared C# evaluator."""

import bisect
import gzip
import json
import os
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .custody import unseal_new
from .decode import decode_side, need
from .integrated_market_source import (
    CIPHER_DIR, DAY, END, HOUR, MINUTE, NATIVE_PERIODS, PROTOCOL, PUBLIC_DIR, START, WARMUP,
    UNIVERSE, bars_from_page, digest, margin_snapshot, unpack,
)
from .native_original_openapi_product_replay import contract

OUTPUT = Path("integrated-economic-public")
REPORT = OUTPUT / "economic.json"
PRICE_SCALE = Decimal(100_000)
MAX_SIDE_AGE = 30_000
FRAME_OFFSET = 15_000


def normalized_bars(rows):
    need(all(a[1] <= b[0] for a, b in zip(rows, rows[1:])), "INTEGRATED_OVERLAPPING_ORIGINAL_BARS")
    return [{"OpenAt": r[0], "CloseAt": r[1], "Open": str(Decimal(r[2]) / PRICE_SCALE),
             "High": str(Decimal(r[3]) / PRICE_SCALE), "Low": str(Decimal(r[4]) / PRICE_SCALE),
             "Close": str(Decimal(r[5]) / PRICE_SCALE), "TickVolume": r[6]} for r in rows]


def minute_marks(day, bids, asks, interval=MINUTE):
    """Deterministic as-of paired marks and genuine side extrema, no market decisions."""
    side_samples = (bids, asks)
    timestamps = ([r[0] for r in bids], [r[0] for r in asks])
    need(all(all(a <= b for a, b in zip(ts, ts[1:])) for ts in timestamps),
         "INTEGRATED_TICK_CHRONOLOGY")
    for at in range(day + FRAME_OFFSET, day + DAY, interval):
        now = [bisect.bisect_right(ts, at) - 1 for ts in timestamps]
        if any(i < 0 or at - ts[i] > MAX_SIDE_AGE for i, ts in zip(now, timestamps)):
            continue
        when = [ts[i] for ts, i in zip(timestamps, now)]
        latest = [rows[i][1] for rows, i in zip(side_samples, now)]
        if latest[0] <= 0 or latest[1] < latest[0]:
            continue
        if any(i > 0 and ts[i - 1] == ts[i] and rows[i - 1][1] != rows[i][1]
               for i, ts, rows in zip(now, timestamps, side_samples)):
            continue
        extrema = []
        complete = True
        for ts, rows, i in zip(timestamps, side_samples, now):
            start = bisect.bisect_right(ts, at - interval) - 1
            effective_start = max(0, start)
            considered = rows[effective_start:i + 1]
            prices = [r[1] for r in considered]
            extrema.extend((str(Decimal(min(prices)) / PRICE_SCALE),
                            str(Decimal(max(prices)) / PRICE_SCALE)))
            complete &= (start >= 0 and at - interval - ts[effective_start] <= MAX_SIDE_AGE and
                         all(b[0] - a[0] <= MAX_SIDE_AGE for a, b in zip(considered, considered[1:])))
        yield {"At": at, "BidAt": when[0], "AskAt": when[1],
               "Bid": str(Decimal(latest[0]) / PRICE_SCALE), "Ask": str(Decimal(latest[1]) / PRICE_SCALE),
               "Path": dict(zip(("BidLow", "BidHigh", "AskLow", "AskHigh", "Complete"),
                                (*extrema, complete)))}


def readback(receipt, private_key, interval=MINUTE):
    need(interval in (30_000, MINUTE), "INTEGRATED_MARK_INTERVAL_UNSUPPORTED")
    run = receipt["RunId"]
    shard_metadata = {v["File"]: v for v in receipt["Shards"]}
    need(len(shard_metadata) == len(receipt["Shards"]) and
         {f.name for f in CIPHER_DIR.glob("*.enc")} == set(shard_metadata),
         "INTEGRATED_CUSTODY_INVENTORY_MISMATCH")

    def open_shard(name):
        file = CIPHER_DIR / name
        ciphertext = file.read_bytes()
        need(digest(ciphertext) == shard_metadata[name]["CipherSha256"], "INTEGRATED_ENCRYPTED_HASH")
        plain = unseal_new(ciphertext, private_key, run)
        need(digest(plain) == shard_metadata[name]["CompressedPlainSha256"], "INTEGRATED_PLAIN_HASH")
        return json.loads(gzip.decompress(plain))

    source = open_shard("account-contracts.enc")
    pairs = [unpack(record) for record in source["Identity"]]
    account = pairs[0][0].ctidTraderAccountId
    need(all(q.ctidTraderAccountId == account for q, _ in pairs), "INTEGRATED_ACCOUNT_INVENTORY_MISMATCH")
    trader, assets, roster = (r for _, r in pairs[:3])
    asset_names = {a.assetId: a.name for a in assets.asset}
    enabled = {s.symbolName: s for s in roster.symbol if s.enabled}
    need("pepperstone" in trader.trader.brokerName.casefold() and
         asset_names[trader.trader.depositAssetId] == "EUR" and len(enabled) == receipt["EnabledSymbols"],
         "INTEGRATED_ORIGINAL_PEPPERSTONE_EUR_INVENTORY")
    details = {r.symbol[0].symbolId: r.symbol[0] for q, r in pairs[3:]
               if isinstance(q, m.ProtoOASymbolByIdReq) and isinstance(r, m.ProtoOASymbolByIdRes)}
    margins = {q.symbolId: margin_snapshot(r, list(q.volume)) for q, r in pairs[3:]
               if isinstance(q, m.ProtoOAExpectedMarginReq) and isinstance(r, m.ProtoOAExpectedMarginRes)}
    market_records = []
    for metadata in source["Markets"]:
        name = metadata["Name"]
        aliases = next((alias for cls, alias in UNIVERSE if cls == metadata["Class"] and name in alias), ())
        need(name == next((n for n in aliases if n in enabled), None), "INTEGRATED_FROZEN_SYMBOL_ALIAS")
        symbol = enabled[name]
        true_contract = details[symbol.symbolId]
        observed = receipt["Markets"][name]
        need(asset_names[symbol.quoteAssetId] == "USD" and
             metadata["Contract"] == contract(name, true_contract, "USD", metadata["Contract"]["ObservedAtUtcMs"])
             and metadata["Margin"] == margins.get(symbol.symbolId, [])
             and metadata["ShortAllowed"] == true_contract.enableShortSelling
             and metadata["TradingMode"] == true_contract.tradingMode
             and metadata["Schedule"] == [[i.startSecond, i.endSecond] for i in true_contract.schedule],
             "INTEGRATED_ORIGINAL_TERM_READBACK")
        bars = {p: [] for p in NATIVE_PERIODS}
        requests = {p: [] for p in NATIVE_PERIODS}
        shard = open_shard(f"{name}-bars.enc")
        need(shard["Name"] == name, "INTEGRATED_BAR_SHARD_LABEL")
        for record in shard["Raw"]:
            req, res = unpack(record)
            need(isinstance(req, m.ProtoOAGetTrendbarsReq) and req.ctidTraderAccountId == account and
                 req.symbolId == symbol.symbolId, "INTEGRATED_BAR_SOURCE_BINDING")
            period = e.ProtoOATrendbarPeriod.Name(req.period)
            requests[period].append((req.fromTimestamp, req.toTimestamp))
            bars[period].extend(bars_from_page(res, period, req.fromTimestamp, req.toTimestamp))
        for period, (_, chunk) in NATIVE_PERIODS.items():
            need(requests[period] == [(y, min(END, y + chunk)) for y in range(WARMUP, END, chunk)]
                 and len(bars[period]) == observed["Bars"][period], "INTEGRATED_BAR_WINDOW_COVERAGE")

        marks = []
        count = {e.BID: 0, e.ASK: 0}
        prior_tail = {e.BID: [], e.ASK: []}
        active = {r[0] // HOUR * HOUR for r in bars["M5"] if r[0] >= START}
        hours = set()
        for day in range(START, END, DAY):
            key = f"{name}-{day}-ticks.enc"
            if key not in shard_metadata:
                prior_tail = {e.BID: [], e.ASK: []}
                continue
            shard = open_shard(key)
            need(shard["Name"] == name and shard["Day"] == day, "INTEGRATED_TICK_SHARD_LABEL")
            sides = {e.BID: [], e.ASK: []}
            intervals = {e.BID: [], e.ASK: []}
            for record in shard["Raw"]:
                req, res = unpack(record)
                need(isinstance(req, m.ProtoOAGetTickDataReq) and req.ctidTraderAccountId == account and
                     req.symbolId == symbol.symbolId and day <= req.fromTimestamp <= req.toTimestamp < day + DAY,
                     "INTEGRATED_TICK_SOURCE_BINDING")
                if isinstance(res, m.ProtoOAErrorRes):
                    need(res.errorCode == "NO_QUOTES", "INTEGRATED_TICK_SOURCE_ERROR")
                elif res.hasMore:
                    continue
                else:
                    sides[req.type].extend(decode_side(res.tickData, req.fromTimestamp, req.toTimestamp))
                intervals[req.type].append((req.fromTimestamp, req.toTimestamp))
            need(intervals[e.BID] == intervals[e.ASK] or all(
                {lo // HOUR * HOUR for lo, _ in intervals[side]} <= active for side in intervals),
                "INTEGRATED_TICK_PAGINATION_SCOPE")
            # Expanded sides must each cover each originally requested hour
            # without overlap or an unacknowledged truncated terminal page.
            def covered(rows):
                joined = []
                for lo, hi in rows:
                    need(not joined or lo > joined[-1][1], "INTEGRATED_TICK_PAGE_OVERLAP")
                    if joined and lo == joined[-1][1] + 1:
                        joined[-1][1] = hi
                    else:
                        joined.append([lo, hi])
                need(all(lo % HOUR == 0 and (hi + 1) % HOUR == 0 for lo, hi in joined),
                     "INTEGRATED_TICK_PAGE_DURATION")
                return {hour for lo, hi in joined for hour in range(lo, hi + 1, HOUR)}
            requested = covered(intervals[e.BID])
            need(requested == covered(intervals[e.ASK]) and requested <= active,
                 "INTEGRATED_TICK_PAGE_MISSING")
            hours.update(requested)
            for side in sides:
                count[side] += len(sides[side])
            marks.extend(minute_marks(day, prior_tail[e.BID] + sides[e.BID],
                                     prior_tail[e.ASK] + sides[e.ASK], interval))
            prior_tail = {side: [row for row in ticks if row[0] >= day + DAY - 90_000]
                          for side, ticks in sides.items()}
        need(len(hours) == observed["SourceTickHours"] and count[e.BID] == observed["Bid"] and
             count[e.ASK] == observed["Ask"] and len(active) == observed["ActiveHours"],
             "INTEGRATED_TICK_COUNT_READBACK")
        known_fields = ("commissionType", "minCommissionType", "preciseTradingCommissionRate",
                        "preciseMinCommission", "pnlConversionFeeRate")
        market_records.append({**metadata,
            "CostTermsComplete": all(true_contract.HasField(f) for f in known_fields),
            "M5": normalized_bars(bars["M5"]), "M15": normalized_bars(bars["M15"]),
            "H1": normalized_bars(bars["H1"]), "Quotes": marks,
            "ActiveHours": len(active), "RequestedTickHours": len(hours)})
        if interval != MINUTE and all(true_contract.HasField(field) for field in ("slDistance", "tpDistance")):
            percentage = true_contract.distanceSetIn == e.SYMBOL_DISTANCE_IN_PERCENTAGE
            scale = Decimal(".01") if percentage else Decimal(metadata["TickSize"])
            market_records[-1]["Protection"] = {
                "Stop": str(true_contract.slDistance * scale), "Target": str(true_contract.tpDistance * scale),
                "Percentage": percentage,
            }
    return market_records


def main():
    OUTPUT.mkdir(exist_ok=True)
    receipt = json.loads((PUBLIC_DIR / "source.json").read_text())
    need(receipt["RunId"] == os.environ["INTEGRATED_SOURCE_RUN"] and receipt["NewOrders"] == 0 and
         not receipt["CloudActivated"] and receipt["Status"] == "AUTHENTIC_READ_ONLY_SOURCE_CAPTURED" and
         receipt["ProtocolSha256"] == digest(PROTOCOL.read_bytes()) and
         (receipt["Warmup"], receipt["Start"], receipt["End"]) == (WARMUP, START, END),
         "INTEGRATED_SOURCE_RECEIPT_BINDING")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "INTEGRATED_PROTECTED_CUSTODY_KEY_MISSING")
    markets = readback(receipt, key)
    print("INTEGRATED_ORIGINAL_READBACK", [(r["Name"], len(r["Quotes"])) for r in markets], flush=True)
    with tempfile.TemporaryDirectory(prefix="integrated-original-") as directory:
        source = Path(directory) / "verified-input.json"
        source.write_text(json.dumps({"Start": START, "End": END, "SourceRun": receipt["RunId"],
            "ProtocolSha256": receipt["ProtocolSha256"], "Markets": markets}, separators=(",", ":")))
        result = subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                                 "--integrated-original", str(source), str(OUTPUT)], check=False)
        need(result.returncode == 0 and REPORT.is_file(), "INTEGRATED_NATIVE_EVALUATION_FAILED")
    (OUTPUT / "receipt.json").write_text(json.dumps({
        "Status": "INTEGRATED_EXPOSED_NATIVE_EVALUATION_AVAILABLE",
        "SourceRun": receipt["RunId"], "OriginalReadOnlyRequests": receipt["Requests"],
        "OriginalEncryptedShards": receipt["Shards"], "ProtocolSha256": receipt["ProtocolSha256"],
        "NativeOutputSha256": digest(REPORT.read_bytes()), "OrdersSubmitted": 0, "CloudActivated": False,
        "BrokerNetCertified": False, "IndependentConfirmation": False,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
