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
TICK_PAGE_MODEL = "BINARY_PREORDER_V1"
HISTORICAL_REQUEST_SPACING_SECONDS = 0.25


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
    deadline_minutes: int | None = None


ORIGINAL = CaptureScope("INTEGRATED_ECONOMIC_DISCOVERY", WARMUP, START, END, UNIVERSE, NATIVE_PERIODS,
                        PROTOCOL, Path("ops/integrated-full-session-source-once.txt"), MARKER, 10_000)


def utc_ms(month, day):
    return int(datetime(2026, month, day, tzinfo=timezone.utc).timestamp()) * 1000


FUNDED_HISTORY = CaptureScope(
    "FUNDED_ACTION_HISTORY", utc_ms(7, 13), utc_ms(7, 27), utc_ms(10, 26),
    UNIVERSE + (("FX", ("AUDUSD",)), ("INDEX", ("NAS100",))),
    {**NATIVE_PERIODS, "M1": (1, DAY), "M30": (30, 4 * DAY)},
    Path("research/FUNDED_ACTION_VALUE_HISTORICAL.md"), Path("ops/funded-action-history-source-once.txt"),
    "OWNER_FUNDED_ACTION_HISTORY_READ_ONLY_SOURCE_ONCE", 64_000, 315,
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


def tick_windows(day, active_hours):
    """Root intervals have inclusive millisecond boundaries and no overlap."""
    for at in range(day, day + DAY, 2 * HOUR):
        hours = [hour for hour in (at, at + HOUR) if hour in active_hours]
        if hours:
            yield hours[0], hours[-1] + HOUR - 1


def divided_tick_window(first, last):
    need(last > first, "INTEGRATED_TICK_SAME_MS_SERVER_TRUNCATION")
    midpoint = (first + last) // 2
    return (first, midpoint), (midpoint + 1, last)


def collect_tick_window(account, symbol_id, side, first, last, request):
    """Request in preorder. The request callback retains every original response."""
    response = request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account, symbolId=symbol_id,
        type=side, fromTimestamp=first, toTimestamp=last))
    if isinstance(response, m.ProtoOAErrorRes):
        need(response.errorCode == "NO_QUOTES", "INTEGRATED_TICK_SOURCE_ERROR")
        return 0
    if response.hasMore:
        return sum(collect_tick_window(account, symbol_id, side, lo, hi, request)
                   for lo, hi in divided_tick_window(first, last))
    return len(decode_side(response.tickData, first, last))


def minimum_volume_grid(terms):
    need_grid = 0 < terms.minVolume <= terms.maxVolume and terms.stepVolume > 0
    if not need_grid:
        return []
    return [v for v in (terms.minVolume, terms.minVolume + terms.stepVolume,
                       terms.minVolume + 3 * terms.stepVolume) if v <= terms.maxVolume]


def funding_snapshot(terms, quote_asset, enabled, grid, margin_status):
    """Current finance metadata is recorded separately from market data availability."""
    restrictions = []
    if not enabled:
        restrictions.append("SYMBOL_DISABLED_AT_CAPTURE")
    if terms.tradingMode != 0:
        restrictions.append("CURRENT_TRADING_MODE_RESTRICTED")
    if quote_asset != "USD":
        restrictions.append("USD_EUR_CONVERSION_ROUTE_NOT_APPLICABLE")
    affordable = any(0 < Decimal(row[side]) < 300 for row in grid[:1]
                     for side in ("BuyMargin", "SellMargin"))
    if not affordable:
        restrictions.append("MINIMUM_MARGIN_NOT_PROVEN_BELOW_EUR300")
    return {"EnabledAtCapture": enabled, "ExpectedMarginStatus": margin_status,
            "MinimumMarginBelowEur300AtCapture": affordable, "Restrictions": restrictions,
            "HistoricalFundingCertified": False}


def expected_margin_evidence(terms, response):
    if not (volumes := minimum_volume_grid(terms)):
        return [], "BROKER_VOLUME_GRID_UNAVAILABLE"
    if isinstance(response, m.ProtoOAErrorRes) or response is None:
        return [], "BROKER_EXPECTED_MARGIN_UNAVAILABLE"
    try:
        return margin_snapshot(response, volumes), "BROKER_EXPECTED_MARGIN_OBSERVED"
    except CaptureContractError as exc:
        # Preserve the original response and treat an unusable grid as a financial
        # evidence gap. It has no authority over which market data are requested.
        return [], str(exc)


def request_capacity(scope):
    days = (scope.end - scope.start) // DAY
    markets = len(scope.universe)
    warmup_span = scope.end - scope.warmup
    bar_pages = markets * sum((warmup_span + chunk - 1) // chunk for _, chunk in scope.periods.values())
    roots = days * 12 * 2 * markets
    identity = 3 + 2 * markets
    return {"BarPages": bar_pages, "TickRoots": roots, "IdentityRequests": identity,
            "RequestsIfEveryRootSplitsOnce": identity + bar_pages + 3 * roots,
            "RequestLimit": scope.request_limit, "DeadlineMinutes": scope.deadline_minutes}


def provider_error_code(response):
    code = response.errorCode
    return code if code.isascii() and code.replace("_", "").isalnum() else "UNCLASSIFIED"


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

    status["TickPageModel"] = TICK_PAGE_MODEL
    status["RequestCapacity"] = request_capacity(scope)
    next_historical = 0.0
    deadline = time.monotonic() + scope.deadline_minutes * 60 if scope.deadline_minutes else None
    position = {}

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
        if historical:
            if isinstance(request, m.ProtoOAGetTickDataReq):
                position.update(Side=e.ProtoOAQuoteType.Name(request.type),
                                From=request.fromTimestamp, To=request.toTimestamp)
            else:
                position.update(Period=e.ProtoOATrendbarPeriod.Name(request.period),
                                From=request.fromTimestamp, To=request.toTimestamp)
        need(status["Requests"] < scope.request_limit, "INTEGRATED_HISTORICAL_REQUEST_BUDGET")
        need(deadline is None or time.monotonic() < deadline, "INTEGRATED_HISTORICAL_TIME_BUDGET")
        if historical:
            time.sleep(max(0, next_historical - time.monotonic()))
            next_historical = time.monotonic() + HISTORICAL_REQUEST_SPACING_SECONDS
        status["Requests"] += 1
        result = transport.request(request)
        raw.append(pack(request, result))
        need(result.IsInitialized() and result.ctidTraderAccountId == request.ctidTraderAccountId,
             "INTEGRATED_ACCOUNT_RESPONSE_MISMATCH")
        if historical and isinstance(result, m.ProtoOAErrorRes):
            if result.errorCode != "NO_QUOTES":
                position["ProviderCode"] = provider_error_code(result)
            need(result.errorCode == "NO_QUOTES", "INTEGRATED_HISTORICAL_REQUEST_REJECTED")
            return result
        if response_type is m.ProtoOAExpectedMarginRes and isinstance(result, m.ProtoOAErrorRes):
            return result
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
        available = {row.symbolName: row for row in roster.symbol}
        status["EnabledSymbols"] = sum(bool(row.enabled) for row in roster.symbol)
        captured = []
        try:
            for asset_class, aliases in scope.universe:
                name = next((alias for alias in aliases if alias in available), aliases[0])
                position = {"Market": name, "Stage": "CONTRACT"}
                if name not in available:
                    status["Unavailable"][name] = "ALIAS_NOT_PRESENT_IN_BROKER_ROSTER"
                    continue
                symbol = available[name]
                quote_asset = names.get(symbol.quoteAssetId, "UNKNOWN")
                details = observe(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account, symbolId=[symbol.symbolId]),
                                  m.ProtoOASymbolByIdRes, identity)
                need(len(details.symbol) == 1 and details.symbol[0].symbolId == symbol.symbolId,
                     "INTEGRATED_CONTRACT_IDENTITY")
                terms = details.symbol[0]
                volumes = minimum_volume_grid(terms)
                margin = observe(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account, symbolId=symbol.symbolId,
                                 volume=volumes), m.ProtoOAExpectedMarginRes, identity) if volumes else None
                grid, margin_status = expected_margin_evidence(terms, margin)
                metadata = {"Name": name, "Class": asset_class,
                            "Contract": contract(name, terms, quote_asset, int(time.time() * 1000)),
                            "TickSize": str(Decimal(10) ** -terms.digits),
                            "TradingMode": terms.tradingMode, "ShortAllowed": terms.enableShortSelling,
                            "Schedule": [[i.startSecond, i.endSecond] for i in terms.schedule],
                            "ScheduleTimeZone": terms.scheduleTimeZone, "Margin": grid,
                            "Funding": funding_snapshot(terms, quote_asset, symbol.enabled, grid, margin_status)}
                if isinstance(margin, m.ProtoOAErrorRes):
                    metadata["Funding"]["ExpectedMarginProviderCode"] = provider_error_code(margin)
                captured.append((symbol.symbolId, metadata))
                status["Markets"][name] = {**metadata, "Bars": {}, "ActiveHours": 0, "BarNoQuotesPages": {},
                                           "SourceTickHours": 0, "Bid": 0, "Ask": 0}
        finally:
            if identity:
                seal("account-contracts.enc", {"Identity": identity, "Markets": [v for _, v in captured]})

        for symbol_id, meta in captured:
            name = meta["Name"]
            info = status["Markets"][name]
            raw = []
            active_hours = set()
            position = {"Market": name, "Stage": "BARS"}
            try:
                for period, (_, chunk) in scope.periods.items():
                    info["Bars"][period] = 0
                    info["BarNoQuotesPages"][period] = 0
                    for first in range(scope.warmup, scope.end, chunk):
                        last = min(scope.end, first + chunk)
                        response = observe(
                            m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=symbol_id,
                                period=getattr(e, period), fromTimestamp=first, toTimestamp=last),
                            m.ProtoOAGetTrendbarsRes, raw, historical=True)
                        info["BarNoQuotesPages"][period] += isinstance(response, m.ProtoOAErrorRes)
                        rows = bars_from_page(response, period, first, last, scope.periods)
                        info["Bars"][period] += len(rows)
                        active_hours.update(row[0] // HOUR * HOUR for row in rows if row[0] >= scope.start)
            finally:
                if raw:
                    seal(f"{name}-bars.enc", {"Name": name, "Raw": raw})
            info["ActiveHours"] = len(active_hours)

            for day in range(scope.start, scope.end, DAY):
                raw = []
                position = {"Market": name, "Stage": "TICKS", "Day": day}
                try:
                    for first, last in tick_windows(day, active_hours):
                        for side, side_name in ((e.BID, "Bid"), (e.ASK, "Ask")):
                            info[side_name] += collect_tick_window(account, symbol_id, side, first, last,
                                lambda req: observe(req, m.ProtoOAGetTickDataRes, raw, historical=True))
                        info["SourceTickHours"] += (last + 1 - first) // HOUR
                finally:
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
        status["FailureAt"] = position
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
