"""Verify sealed original data and decode it for the shared C# evaluator."""

import bisect
import gzip
import hashlib
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
from .guard import CaptureContractError
from .integrated_market_source import (
    CIPHER_DIR, DAY, END, FUNDED_HISTORY, HOUR, MINUTE, ORIGINAL, PROTOCOL, PUBLIC_DIR, START,
    TICK_PAGE_MODEL, WARMUP, bars_from_page, digest, divided_tick_window, expected_margin_evidence,
    funding_snapshot, minimum_volume_grid, provider_error_code, request_capacity, tick_windows, unpack,
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

def witnessed_rollover_quotes(clocks, covered_hours, bids, asks):
    """Exact as-of sides at requested clocks, with no interpolation."""
    if not clocks:
        return
    timestamps = tuple([r[0] for r in side] for side in (bids, asks))
    for at in clocks:
        covered = all(hour in covered_hours for hour in
                      range((at - MAX_SIDE_AGE) // HOUR * HOUR, at // HOUR * HOUR + HOUR, HOUR))
        quote = {"At": at, "RequestedCoverage": covered}
        if covered:
            for name, side, stamps in zip(("Bid", "Ask"), (bids, asks), timestamps):
                i = bisect.bisect_right(stamps, at) - 1
                if i < 0 or at - stamps[i] > MAX_SIDE_AGE:
                    continue
                same = bisect.bisect_left(stamps, stamps[i], 0, i)
                if any(side[j][1] != side[i][1] for j in range(same, i)):
                    continue
                quote[name + "At"] = stamps[i]
                quote[name] = str(Decimal(side[i][1]) / PRICE_SCALE)
        yield quote


class TickPageIntegrityError(CaptureContractError):
    def __init__(self, code, side, first, last, **details):
        super().__init__(code)
        self.context = {"Side": e.ProtoOAQuoteType.Name(side), "From": first, "To": last, **details}


def reconcile_tick_pages(raw, account, symbol_id, windows):
    """Verify each planned BID/ASK root and exactly the children proven by hasMore."""
    pages = iter(raw)
    side_names = {e.BID: "Bid", e.ASK: "Ask"}
    ticks = {side: [] for side in side_names}
    stats = {side: dict.fromkeys(
        ("Requests", "TruncatedParents", "TerminalPages", "NoQuotesPages", "EmptyTerminalPages",
         "TerminalMilliseconds", "NoQuotesMilliseconds"), 0) for side in side_names}

    def read(side, first, last):
        page = next(pages, None)
        if page is None:
            raise TickPageIntegrityError("INTEGRATED_TICK_PAGE_MISSING", side, first, last)
        req, res = unpack(page)
        if (not isinstance(req, m.ProtoOAGetTickDataReq) or req.ctidTraderAccountId != account or
                req.symbolId != symbol_id or not req.HasField("fromTimestamp") or not req.HasField("toTimestamp")):
            raise TickPageIntegrityError("INTEGRATED_TICK_SOURCE_BINDING", side, first, last)
        if (req.type, req.fromTimestamp, req.toTimestamp) != (side, first, last):
            raise TickPageIntegrityError("INTEGRATED_TICK_PAGE_ORDER_OR_INTERVAL", side, first, last,
                                         ObservedSide=e.ProtoOAQuoteType.Name(req.type),
                                         ObservedFrom=req.fromTimestamp, ObservedTo=req.toTimestamp)
        stat = stats[side]
        stat["Requests"] += 1
        terminal_rows = []
        if isinstance(res, m.ProtoOAErrorRes):
            if res.errorCode != "NO_QUOTES":
                raise TickPageIntegrityError("INTEGRATED_TICK_SOURCE_ERROR", side, first, last,
                                             ProviderCode=provider_error_code(res))
            stat["NoQuotesPages"] += 1
            stat["NoQuotesMilliseconds"] += last + 1 - first
        elif not isinstance(res, m.ProtoOAGetTickDataRes):
            raise TickPageIntegrityError("INTEGRATED_TICK_RESPONSE_TYPE", side, first, last)
        elif res.hasMore:
            if first == last:
                raise TickPageIntegrityError("INTEGRATED_TICK_SAME_MS_SERVER_TRUNCATION", side, first, last)
            stat["TruncatedParents"] += 1
            for lo, hi in divided_tick_window(first, last):
                read(side, lo, hi)
            return
        else:
            terminal_rows = decode_side(res.tickData, first, last)
            stat["EmptyTerminalPages"] += not terminal_rows
        stat["TerminalPages"] += 1
        stat["TerminalMilliseconds"] += last + 1 - first
        ticks[side].extend(terminal_rows)

    for first, last in windows:
        for side in side_names:
            read(side, first, last)
    need(next(pages, None) is None, "INTEGRATED_TICK_UNEXPECTED_EXTRA_PAGE")
    return ticks, {side_names[side]: summary for side, summary in stats.items()}


def readback(receipt, private_key, interval=MINUTE, scope=ORIGINAL, include_markets=None, rollover_clocks=None):
    """Original full readback or recovery-proven, explicitly selected complete subset.

    Caller MUST validate all original shards with funded_history_recovery.scan
    and the exact hash-checked recovery receipt before using the subset option.
    The all-market original behavior remains unchanged.
    """
    need(interval in (30_000, MINUTE), "INTEGRATED_MARK_INTERVAL_UNSUPPORTED")
    run = receipt["RunId"]
    page_model = receipt.get("TickPageModel")
    need(page_model in (None, TICK_PAGE_MODEL), "INTEGRATED_TICK_PAGE_MODEL")
    legacy = page_model is None
    raw_request_count = 0
    clocks_by_day = {}
    if rollover_clocks is not None:
        for clock in sorted(set(rollover_clocks)):
            need(scope.start <= clock < scope.end, "INTEGRATED_ROLLOVER_WITNESS_RANGE")
            clocks_by_day.setdefault(clock // DAY * DAY, []).append(clock)
    opened_shards = set()
    shard_metadata = {v["File"]: v for v in receipt["Shards"]}
    need(len(shard_metadata) == len(receipt["Shards"]) and
         {f.name for f in CIPHER_DIR.glob("*.enc")} == set(shard_metadata),
         "INTEGRATED_CUSTODY_INVENTORY_MISMATCH")

    def open_shard(name):
        need(name in shard_metadata, "INTEGRATED_CUSTODY_SHARD_MISSING")
        file = CIPHER_DIR / name
        ciphertext = file.read_bytes()
        opened_shards.add(name)
        need(digest(ciphertext) == shard_metadata[name]["CipherSha256"], "INTEGRATED_ENCRYPTED_HASH")
        plain = unseal_new(ciphertext, private_key, run)
        need(digest(plain) == shard_metadata[name]["CompressedPlainSha256"], "INTEGRATED_PLAIN_HASH")
        return json.loads(gzip.decompress(plain))

    source = open_shard("account-contracts.enc")
    pairs = [unpack(record) for record in source["Identity"]]
    raw_request_count += len(pairs)
    account = pairs[0][0].ctidTraderAccountId
    need(all(q.ctidTraderAccountId == account for q, _ in pairs), "INTEGRATED_ACCOUNT_INVENTORY_MISMATCH")
    trader, assets, roster = (r for _, r in pairs[:3])
    asset_names = {a.assetId: a.name for a in assets.asset}
    available = {symbol.symbolName: symbol for symbol in roster.symbol if symbol.enabled or not legacy}
    need("pepperstone" in trader.trader.brokerName.casefold() and
         asset_names[trader.trader.depositAssetId] == "EUR" and
         sum(bool(symbol.enabled) for symbol in roster.symbol) == receipt["EnabledSymbols"],
         "INTEGRATED_ORIGINAL_PEPPERSTONE_EUR_INVENTORY")
    details = {r.symbol[0].symbolId: r.symbol[0] for q, r in pairs[3:]
               if isinstance(q, m.ProtoOASymbolByIdReq) and isinstance(r, m.ProtoOASymbolByIdRes)}
    margins = {q.symbolId: (q, r) for q, r in pairs[3:] if isinstance(q, m.ProtoOAExpectedMarginReq)}
    market_records = []
    selected_names = None if include_markets is None else frozenset(include_markets)
    if selected_names is not None:
        need(bool(selected_names) and selected_names <= set(receipt["Markets"]),
             "INTEGRATED_RECOVERY_SELECTED_MARKET_SCOPE")
    if not legacy:
        expected_names = {next((name for name in aliases if name in available), None)
                          for _, aliases in scope.universe} - {None}
        need(expected_names == {v["Name"] for v in source["Markets"]} == set(receipt["Markets"]) and
             len(expected_names) == len(source["Markets"]), "INTEGRATED_SOURCE_ROSTER_COVERAGE")
    for metadata in source["Markets"]:
        name = metadata["Name"]
        if selected_names is not None and name not in selected_names:
            continue
        aliases = next((alias for cls, alias in scope.universe if cls == metadata["Class"] and name in alias), ())
        need(name == next((n for n in aliases if n in available), None), "INTEGRATED_FROZEN_SYMBOL_ALIAS")
        symbol = available[name]
        true_contract = details[symbol.symbolId]
        observed = receipt["Markets"][name]
        quote_asset = asset_names.get(symbol.quoteAssetId, "UNKNOWN")
        need(not legacy or quote_asset == "USD", "INTEGRATED_ORIGINAL_QUOTE_ASSET")
        request, response = margins.get(symbol.symbolId, (None, None))
        volumes = minimum_volume_grid(true_contract)
        need((request is None and not volumes) or (request is not None and list(request.volume) == volumes),
             "INTEGRATED_ORIGINAL_MARGIN_REQUEST_GRID")
        grid, margin_status = expected_margin_evidence(true_contract, response)
        need(metadata["Contract"] == contract(name, true_contract, quote_asset, metadata["Contract"]["ObservedAtUtcMs"])
             and metadata["Margin"] == grid
             and metadata["ShortAllowed"] == true_contract.enableShortSelling
             and metadata["TradingMode"] == true_contract.tradingMode
             and metadata["TickSize"] == str(Decimal(10) ** -true_contract.digits)
             and metadata["ScheduleTimeZone"] == true_contract.scheduleTimeZone
             and metadata["Schedule"] == [[i.startSecond, i.endSecond] for i in true_contract.schedule],
             "INTEGRATED_ORIGINAL_TERM_READBACK")
        funding = funding_snapshot(true_contract, quote_asset, symbol.enabled, grid, margin_status)
        if isinstance(response, m.ProtoOAErrorRes):
            funding["ExpectedMarginProviderCode"] = provider_error_code(response)
        if not legacy:
            need(funding == metadata["Funding"] == observed["Funding"], "INTEGRATED_CURRENT_FUNDING_READBACK")
        bars = {p: [] for p in scope.periods}
        requests = {p: [] for p in scope.periods}
        bar_no_quotes = dict.fromkeys(scope.periods, 0)
        shard = open_shard(f"{name}-bars.enc")
        need(shard["Name"] == name, "INTEGRATED_BAR_SHARD_LABEL")
        raw_request_count += len(shard["Raw"])
        for record in shard["Raw"]:
            req, res = unpack(record)
            need(isinstance(req, m.ProtoOAGetTrendbarsReq) and req.ctidTraderAccountId == account and
                 req.symbolId == symbol.symbolId, "INTEGRATED_BAR_SOURCE_BINDING")
            period = e.ProtoOATrendbarPeriod.Name(req.period)
            requests[period].append((req.fromTimestamp, req.toTimestamp))
            bar_no_quotes[period] += isinstance(res, m.ProtoOAErrorRes)
            bars[period].extend(bars_from_page(res, period, req.fromTimestamp, req.toTimestamp, scope.periods))
        for period, (_, chunk) in scope.periods.items():
            need(requests[period] == [(y, min(scope.end, y + chunk)) for y in range(scope.warmup, scope.end, chunk)]
                 and len(bars[period]) == observed["Bars"][period], "INTEGRATED_BAR_WINDOW_COVERAGE")

        if not legacy:
            need(bar_no_quotes == observed["BarNoQuotesPages"], "INTEGRATED_BAR_NO_QUOTES_COUNT")
        marks = []
        rollovers = []
        count = {e.BID: 0, e.ASK: 0}
        prior_tail = {e.BID: [], e.ASK: []}
        activity_periods = ("M5",) if legacy else scope.periods
        active = {r[0] // HOUR * HOUR for p in activity_periods for r in bars[p] if r[0] >= scope.start}
        # Old collected evidence can have an intentional funding exclusion. Every
        # new registered market instead earns the same activity-based tick coverage.
        old_funding_exclusion = legacy and name != "EURUSD" and (
            not funding["MinimumMarginBelowEur300AtCapture"] or true_contract.tradingMode != 0)
        expected_hours = set() if old_funding_exclusion else active
        hours = 0
        _, tick_stats = reconcile_tick_pages([], account, symbol.symbolId, ())
        for day in range(scope.start, scope.end, DAY):
            key = f"{name}-{day}-ticks.enc"
            windows = list(tick_windows(day, expected_hours))
            if not windows:
                need(key not in shard_metadata, "INTEGRATED_TICK_UNPLANNED_SHARD")
                rollovers.extend(dict(At=at, RequestedCoverage=False) for at in clocks_by_day.get(day, ()))
                prior_tail = {e.BID: [], e.ASK: []}
                continue
            shard = open_shard(key)
            need(shard["Name"] == name and shard["Day"] == day, "INTEGRATED_TICK_SHARD_LABEL")
            raw_request_count += len(shard["Raw"])
            try:
                sides, summary = reconcile_tick_pages(shard["Raw"], account, symbol.symbolId, windows)
            except TickPageIntegrityError as exc:
                exc.context.update(Market=name, Day=day, Shard=key)
                raise
            milliseconds = sum(last + 1 - first for first, last in windows)
            for side, daily in summary.items():
                need(daily["TerminalMilliseconds"] == milliseconds, "INTEGRATED_TICK_SIDE_COVERAGE")
                for metric, value in daily.items():
                    tick_stats[side][metric] += value
            hours += milliseconds // HOUR
            for side, side_ticks in sides.items():
                count[side] += len(side_ticks)
            bids, asks = prior_tail[e.BID] + sides[e.BID], prior_tail[e.ASK] + sides[e.ASK]
            marks.extend(minute_marks(day, bids, asks, interval))
            rollovers.extend(witnessed_rollover_quotes(clocks_by_day.get(day, ()), expected_hours, bids, asks))
            prior_tail = {side: [row for row in side_ticks if row[0] >= day + DAY - 90_000]
                          for side, side_ticks in sides.items()}
        need(hours == observed["SourceTickHours"] and count[e.BID] == observed["Bid"] and
             count[e.ASK] == observed["Ask"] and len(active) == observed["ActiveHours"],
             "INTEGRATED_TICK_COUNT_READBACK")
        known_fields = ("commissionType", "minCommissionType", "preciseTradingCommissionRate",
                        "preciseMinCommission", "pnlConversionFeeRate")
        market_records.append({**metadata,
            "CostTermsComplete": all(true_contract.HasField(f) for f in known_fields),
            "M5": normalized_bars(bars["M5"]), "M15": normalized_bars(bars["M15"]),
            "H1": normalized_bars(bars["H1"]), "Quotes": marks,
            "ActiveHours": len(active), "RequestedTickHours": hours})
        if rollover_clocks is not None:
            market_records[-1]["RolloverQuotes"] = rollovers
        if not legacy:
            market_records[-1].update(EnabledAtCapture=symbol.enabled, TickPages=tick_stats,
                                      BarNoQuotesPages=bar_no_quotes)
        additional = {p: {"Source": "PEPPERSTONE_OPEN_API_NATIVE_" + p, "Bars": normalized_bars(rows)}
                      for p, rows in bars.items() if p not in ("M5", "M15", "H1")}
        if additional:
            market_records[-1]["AdditionalTimeframes"] = additional
        if interval != MINUTE and all(true_contract.HasField(field) for field in ("slDistance", "tpDistance")):
            percentage = true_contract.distanceSetIn == e.SYMBOL_DISTANCE_IN_PERCENTAGE
            scale = Decimal(".01") if percentage else Decimal(metadata["TickSize"])
            market_records[-1]["Protection"] = {
                "Stop": str(true_contract.slDistance * scale), "Target": str(true_contract.tpDistance * scale),
                "Percentage": percentage,
            }
    if selected_names is None:
        need(opened_shards == set(shard_metadata) and raw_request_count == receipt["Requests"],
             "INTEGRATED_CUSTODY_REQUEST_INVENTORY")
    else:
        expected = {"account-contracts.enc"}
        for name in selected_names:
            expected.add(f"{name}-bars.enc")
            expected.update(s for s in shard_metadata
                            if s.startswith(f"{name}-") and s.endswith("-ticks.enc"))
        need(opened_shards == expected and
             {m["Name"] for m in market_records} == selected_names,
             "INTEGRATED_CUSTODY_SELECTED_SHARD_INVENTORY")
    return market_records


def funded_history_source(receipt, private_key, expected_run):
    """Build a verified, private Replay input. The original ciphertext stays in custody."""
    scope = FUNDED_HISTORY
    need(receipt["Study"] == scope.study and receipt["RunId"] == expected_run and expected_run.isascii() and
         expected_run.isdecimal() and receipt["NewOrders"] == 0 and not receipt["CloudActivated"] and
         receipt["EconomicEvaluations"] == 0 and receipt["Status"] == "AUTHENTIC_READ_ONLY_SOURCE_CAPTURED" and
         receipt.get("TickPageModel") == TICK_PAGE_MODEL and receipt.get("RequestCapacity") == request_capacity(scope) and
         receipt["ProtocolSha256"] == digest(scope.protocol.read_bytes()) and
         (receipt["Warmup"], receipt["Start"], receipt["End"]) == (scope.warmup, scope.start, scope.end),
         "FUNDED_ACTION_HISTORY_SOURCE_RECEIPT_BINDING")
    return {"Start": scope.start, "End": scope.end, "SourceRun": expected_run,
            "ProtocolSha256": receipt["ProtocolSha256"], "ManagementIntervalMs": 30_000,
            "Markets": readback(receipt, private_key, interval=30_000, scope=scope)}


def funded_history_coverage():
    receipt = json.loads((PUBLIC_DIR / "source.json").read_text())
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "INTEGRATED_PROTECTED_CUSTODY_KEY_MISSING")
    output = Path("funded-history-coverage")
    output.mkdir(exist_ok=True)
    try:
        verified = funded_history_source(receipt, key, os.environ["GITHUB_RUN_ID"])
    except CaptureContractError as exc:
        (output / "coverage-failure.json").write_text(json.dumps({
            "SourceRun": os.environ["GITHUB_RUN_ID"], "Status": "ORIGINAL_READBACK_FAILED",
            "Failure": str(exc), "Context": getattr(exc, "context", {}), "EconomicEvaluations": 0,
        }, indent=2) + "\n")
        raise
    report = output / "coverage.json"
    with tempfile.TemporaryDirectory(prefix="funded-history-") as directory:
        source = Path(directory) / "verified-input.json"
        with source.open("w") as handle:
            json.dump(verified, handle, separators=(",", ":"))
        input_sha = hashlib_file(source)
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        "--closed-market-context-audit", str(source), str(report)], check=True)
    (output / "receipt.json").write_text(json.dumps({
        "SourceRun": receipt["RunId"], "ProtocolSha256": receipt["ProtocolSha256"],
        "OriginalEncryptedShards": receipt["Shards"], "OriginalReadOnlyRequests": receipt["Requests"],
        "VerifiedInputSha256": input_sha, "CoverageSha256": hashlib_file(report),
        "TickPageModel": TICK_PAGE_MODEL, "RequestCapacity": request_capacity(FUNDED_HISTORY),
        "SourceReceiptSha256": hashlib_file(PUBLIC_DIR / "source.json"),
        "NotInBrokerRoster": receipt["Unavailable"],
        "Markets": {v["Name"]: {"Bars": receipt["Markets"][v["Name"]]["Bars"],
                                "BarNoQuotesPages": v["BarNoQuotesPages"], "TickPages": v["TickPages"],
                                "BidTicks": receipt["Markets"][v["Name"]]["Bid"],
                                "AskTicks": receipt["Markets"][v["Name"]]["Ask"],
                                "Funding": v["Funding"]} for v in verified["Markets"]},
        "EconomicEvaluations": 0, "OrdersSubmitted": 0, "CloudActivated": False,
    }, indent=2) + "\n")


def hashlib_file(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


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
    import sys
    if sys.argv[1:] == ["--funded-action-history-coverage"]:
        funded_history_coverage()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("Unsupported readback mode")
