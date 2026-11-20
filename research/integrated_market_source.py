"""Read-only full-active-session captures for the frozen integrated program."""

import base64
import gzip
import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .custody import seal_new
from .custody_new import checked_public
from .decode import decode_bars, decode_side, need
from .guard import CaptureContractError, require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate

MINUTE = 60_000
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WARMUP, START, END = (
    int(datetime(2026, month, day, tzinfo=timezone.utc).timestamp()) * 1000
    for month, day in ((10, 12), (10, 26), (11, 16))
)
UNIVERSE = (
    ("FX", ("EURUSD",)), ("FX", ("GBPUSD",)), ("METAL", ("XAUUSD",)),
    ("ENERGY", ("SpotBrent",)), ("INDEX", ("US500",)), ("SHARE", ("AAPL", "AAPL.US")),
)
NATIVE_PERIODS = {"M5": (5, DAY), "M15": (15, 2 * DAY), "H1": (60, 7 * DAY)}
PROTOCOL = Path("research/INTEGRATED_ECONOMIC_DISCOVERY_20261120.md")
CIPHER_DIR = Path("integrated-sealed-source")
PUBLIC_DIR = Path("integrated-source-public")
MARKER = "OWNER_INTEGRATED_FULL_SESSION_READ_ONLY_SOURCE_ONCE"


@dataclass(frozen=True)
class CaptureScope:
    study: str
    warmup: int
    start: int
    end: int
    universe: tuple
    periods: dict
    protocol: Path
    marker_file: Path
    marker: str
    request_limit: int


ORIGINAL = CaptureScope("INTEGRATED_ECONOMIC_DISCOVERY", WARMUP, START, END, UNIVERSE, NATIVE_PERIODS,
                        PROTOCOL, Path("ops/integrated-full-session-source-once.txt"), MARKER, 10_000)


def utc_ms(month, day):
    return int(datetime(2026, month, day, tzinfo=timezone.utc).timestamp()) * 1000


FUNDED_HISTORY = CaptureScope(
    "FUNDED_ACTION_HISTORY", utc_ms(7, 13), utc_ms(7, 27), utc_ms(10, 26),
    UNIVERSE + (("FX", ("AUDUSD",)), ("INDEX", ("NAS100",))),
    {**NATIVE_PERIODS, "M1": (1, DAY), "M30": (30, 4 * DAY)},
    Path("research/FUNDED_ACTION_VALUE_HISTORICAL.md"), Path("ops/funded-action-history-source-once.txt"),
    "OWNER_FUNDED_ACTION_HISTORY_READ_ONLY_SOURCE_ONCE", 40_000,
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pack(request, response):
    return [type(request).__name__, base64.b64encode(request.SerializeToString()).decode(),
            type(response).__name__, base64.b64encode(response.SerializeToString()).decode()]


def unpack(row):
    request_type, request_data, response_type, response_data = row
    request = getattr(m, request_type).FromString(base64.b64decode(request_data, validate=True))
    response = getattr(m, response_type).FromString(base64.b64decode(response_data, validate=True))
    require_read_only_request(request)
    need(response.IsInitialized() and response.ctidTraderAccountId == request.ctidTraderAccountId,
         "INTEGRATED_ORIGINAL_ACCOUNT_BINDING")
    return request, response


def validate_environment(scope=ORIGINAL):
    need(os.environ.get("GITHUB_EVENT_NAME") == "push"
         and os.environ.get("GITHUB_REF") == "refs/heads/main"
         and os.environ.get("GITHUB_ACTOR") == "mariancradulescu"
         and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
         and scope.marker_file.read_text().strip() == scope.marker,
         "INTEGRATED_OWNER_MAIN_FIRST_ATTEMPT_ONLY")


def bars_from_page(response, period, first, last, periods=NATIVE_PERIODS):
    if isinstance(response, m.ProtoOAErrorRes):
        need(response.errorCode == "NO_QUOTES", "INTEGRATED_BAR_SOURCE_ERROR")
        return []
    minutes = periods[period][0]
    step = minutes * MINUTE
    need(response.period == getattr(e, period) and not response.hasMore, "INTEGRATED_BAR_PAGE_INVALID")
    rows = decode_bars(response.trendbar, first - step, last + step, minutes)
    return [row for row in rows if first <= row[0] and row[1] <= last]


def margin_snapshot(response, volumes):
    need(response.HasField("moneyDigits") and 0 <= response.moneyDigits <= 8,
         "INTEGRATED_EXPECTED_MARGIN_SCALE_UNKNOWN")
    scale = Decimal(10) ** response.moneyDigits
    need([r.volume for r in response.margin] == volumes, "INTEGRATED_EXPECTED_MARGIN_VOLUME_MISMATCH")
    return [{"Units": str(Decimal(r.volume) / 100), "BuyMargin": str(Decimal(r.buyMargin) / scale),
             "SellMargin": str(Decimal(r.sellMargin) / scale)} for r in response.margin]


def collect(scope=ORIGINAL):
    validate_environment(scope)
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-source-recipient"), run)
    PUBLIC_DIR.mkdir(exist_ok=True)
    CIPHER_DIR.mkdir(exist_ok=True)
    transport = StdlibCTraderTransport()
    status = {
        "Study": scope.study, "Status": "COLLECTING", "RunId": run,
        "ProtocolSha256": digest(scope.protocol.read_bytes()), "Requests": 0, "Shards": [],
        "Warmup": scope.warmup, "Start": scope.start, "End": scope.end, "Markets": {}, "Unavailable": {},
        "NewOrders": 0, "CloudActivated": False, "EconomicEvaluations": 0,
    }
    next_historical = 0.0

    def publish():
        (PUBLIC_DIR / "source.json").write_text(json.dumps(status, indent=2) + "\n")

    def seal(name, body):
        plain = gzip.compress(json.dumps(body, separators=(",", ":")).encode(), mtime=0)
        cipher = seal_new(plain, recipient, run)
        (CIPHER_DIR / name).write_bytes(cipher)
        status["Shards"].append({"File": name, "CompressedPlainSha256": digest(plain),
                                 "CipherSha256": digest(cipher)})
        publish()

    def observe(request, response_type, raw, historical=False):
        nonlocal next_historical
        require_read_only_request(request)
        need(status["Requests"] < scope.request_limit, "INTEGRATED_HISTORICAL_REQUEST_BUDGET")
        if historical:
            time.sleep(max(0, next_historical - time.monotonic()))
            next_historical = time.monotonic() + .25
        status["Requests"] += 1
        result = transport.request(request)
        raw.append(pack(request, result))
        need(result.IsInitialized() and result.ctidTraderAccountId == request.ctidTraderAccountId,
             "INTEGRATED_ACCOUNT_RESPONSE_MISMATCH")
        if historical and isinstance(result, m.ProtoOAErrorRes):
            need(result.errorCode == "NO_QUOTES", "INTEGRATED_HISTORICAL_REQUEST_REJECTED")
            return result
        if response_type is m.ProtoOAExpectedMarginRes and isinstance(result, m.ProtoOAErrorRes):
            return None
        need(type(result) is response_type, "INTEGRATED_READ_ONLY_RESPONSE_MISMATCH")
        return result

    try:
        account = authenticate(transport)
        identity = []
        trader = observe(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes, identity)
        assets = observe(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes, identity)
        names = {asset.assetId: asset.name for asset in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and names[trader.trader.depositAssetId] == "EUR", "INTEGRATED_PEPPERSTONE_EUR_BINDING")
        roster = observe(m.ProtoOASymbolsListReq(ctidTraderAccountId=account, includeArchivedSymbols=False),
                         m.ProtoOASymbolsListRes, identity)
        available = {row.symbolName: row for row in roster.symbol if row.enabled}
        status["EnabledSymbols"] = len(available)
        captured = []
        for asset_class, aliases in scope.universe:
            name = next((alias for alias in aliases if alias in available), aliases[0])
            if name not in available:
                status["Unavailable"][name] = "ENABLED_ALIAS_NOT_PRESENT"
                continue
            symbol = available[name]
            if names.get(symbol.quoteAssetId) != "USD":
                status["Unavailable"][name] = "USD_EUR_CONVERSION_ROUTE_NOT_APPLICABLE"
                continue
            details = observe(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account, symbolId=[symbol.symbolId]),
                              m.ProtoOASymbolByIdRes, identity)
            need(len(details.symbol) == 1 and details.symbol[0].symbolId == symbol.symbolId,
                 "INTEGRATED_CONTRACT_IDENTITY")
            terms = details.symbol[0]
            if not 0 < terms.minVolume <= terms.maxVolume or terms.stepVolume <= 0:
                status["Unavailable"][name] = "BROKER_VOLUME_GRID_UNAVAILABLE"
                continue
            volumes = [v for v in (terms.minVolume, terms.minVolume + terms.stepVolume,
                                   terms.minVolume + 3 * terms.stepVolume) if v <= terms.maxVolume]
            margin = observe(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account, symbolId=symbol.symbolId,
                                                       volume=volumes),
                             m.ProtoOAExpectedMarginRes, identity)
            grid = margin_snapshot(margin, volumes) if margin is not None else []
            if not grid:
                status["Unavailable"][name] = "BROKER_EXPECTED_MARGIN_UNAVAILABLE"
            metadata = {"Name": name, "Class": asset_class,
                        "Contract": contract(name, terms, "USD", int(time.time() * 1000)),
                        "TickSize": str(Decimal(10) ** -terms.digits),
                        "TradingMode": terms.tradingMode, "ShortAllowed": terms.enableShortSelling,
                        "Schedule": [[i.startSecond, i.endSecond] for i in terms.schedule],
                        "ScheduleTimeZone": terms.scheduleTimeZone, "Margin": grid}
            captured.append((symbol.symbolId, metadata))
            status["Markets"][name] = {**metadata, "Bars": {}, "ActiveHours": 0,
                                       "SourceTickHours": 0, "Bid": 0, "Ask": 0}
        need(any(info["Name"] == "EURUSD" for _, info in captured), "INTEGRATED_EURUSD_SOURCE_MISSING")
        seal("account-contracts.enc", {"Identity": identity, "Markets": [v for _, v in captured]})

        for symbol_id, meta in captured:
            name = meta["Name"]
            info = status["Markets"][name]
            raw = []
            active_m5 = []
            for period, (_, chunk) in scope.periods.items():
                count = 0
                for first in range(scope.warmup, scope.end, chunk):
                    last = min(scope.end, first + chunk)
                    response = observe(
                        m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=symbol_id,
                            period=getattr(e, period), fromTimestamp=first, toTimestamp=last),
                        m.ProtoOAGetTrendbarsRes, raw, historical=True)
                    rows = bars_from_page(response, period, first, last, scope.periods)
                    count += len(rows)
                    if period == "M5":
                        active_m5.extend(row[0] for row in rows if row[0] >= scope.start)
                info["Bars"][period] = count
            seal(f"{name}-bars.enc", {"Name": name, "Raw": raw})
            active_hours = {t // HOUR * HOUR for t in active_m5}
            info["ActiveHours"] = len(active_hours)
            have_margin = any(0 < Decimal(step[key]) < 300 for step in meta["Margin"][:1]
                              for key in ("BuyMargin", "SellMargin"))
            if name != "EURUSD" and (not have_margin or meta["TradingMode"] != 0):
                status["Unavailable"][name] = ("CURRENT_TRADING_MODE_RESTRICTED" if meta["TradingMode"] != 0
                                               else "MINIMUM_MARGIN_NOT_PROVEN_BELOW_EUR300")
                publish()
                continue

            def ticks(side, first, last, records):
                response = observe(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account, symbolId=symbol_id,
                                       type=side, fromTimestamp=first, toTimestamp=last),
                                   m.ProtoOAGetTickDataRes, records, historical=True)
                if isinstance(response, m.ProtoOAErrorRes):
                    return 0
                if response.hasMore:
                    need(last > first, "INTEGRATED_TICK_SAME_MS_SERVER_TRUNCATION")
                    midpoint = (first + last) // 2
                    return ticks(side, first, midpoint, records) + ticks(side, midpoint + 1, last, records)
                return len(decode_side(response.tickData, first, last))

            for day in range(scope.start, scope.end, DAY):
                raw = []
                for time_at in range(day, day + DAY, 2 * HOUR):
                    covered = [t for t in (time_at, time_at + HOUR) if t in active_hours]
                    if not covered:
                        continue
                    first, last = min(covered), max(covered) + HOUR - 1
                    info["Bid"] += ticks(e.BID, first, last, raw)
                    info["Ask"] += ticks(e.ASK, first, last, raw)
                    info["SourceTickHours"] += len(covered)
                if raw:
                    seal(f"{name}-{day}-ticks.enc", {"Name": name, "Day": day, "Raw": raw})
            print("INTEGRATED_MARKET_CAPTURED", name, info["Bars"], info["SourceTickHours"],
                  info["Bid"], info["Ask"], flush=True)
        status["Status"] = "AUTHENTIC_READ_ONLY_SOURCE_CAPTURED"
        publish()
    except Exception as exc:
        status["Status"] = "SOURCE_FAILED_CLOSED"
        status["Failure"] = (str(exc) if isinstance(exc, CaptureContractError)
                             and str(exc).replace("_", "").isalnum() and str(exc).isupper()
                             else type(exc).__name__)
        publish()
        print("INTEGRATED_SOURCE_FAILURE", status["Failure"], flush=True)
        raise SystemExit(1) from None
    finally:
        transport.close()


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--funded-action-history"]:
        collect(FUNDED_HISTORY)
    elif len(sys.argv) == 1:
        collect()
    else:
        raise SystemExit("Unsupported source scope")
