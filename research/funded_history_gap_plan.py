"""Offline gap-plan validator and bounded read-only retry primitive.

No connections are created. Caller must supply a previously authorized transport,
durably retain attempts, and separately validate returned pagination leaves.
"""
import hashlib
import json
import time
from collections import defaultdict

from .ctrader_proto import OpenApiMessages_pb2 as m
from .decode import need
from .guard import CaptureContractError, require_read_only_request
from .integrated_market_source import FUNDED_HISTORY, HOUR, pack

RETRYABLE = frozenset((
    "UNKNOWN_ERROR", "REQUEST_FREQUENCY_EXCEEDED", "CH_SERVER_NOT_REACHABLE",
    "SERVER_IS_UNDER_MAINTENANCE",
))
MAX_ATTEMPTS = 3
MIN_HISTORICAL_SPACING_SECONDS = 0.25


def validate_plan(plan, scope=FUNDED_HISTORY):
    """Validate precise missing intervals. Return executable and blocked items separately."""
    need(plan.get("Status") == "PREPARED_NOT_AUTHORIZED_FOR_BROKER_ACCESS" and
         plan.get("OriginalRun") == "44824462289" and
         plan.get("NewOpenApiRequests") == 0 and
         isinstance(plan.get("Requests"), list), "RECOVERY_GAP_PLAN_BINDING")
    allowed = {alias for _, aliases in scope.universe for alias in aliases}
    executable = []
    blocked = []
    ranges = defaultdict(list)
    identities = set()
    for row in plan["Requests"]:
        market, period, side, reason = (row.get(k) for k in
                                          ("Market", "Timeframe", "Side", "Reason"))
        first, last = row.get("From"), row.get("ToExclusive")
        need(market in allowed and type(first) is int and type(last) is int and first < last,
             "RECOVERY_GAP_INVALID_TARGET")
        if reason == "BAR_ACTIVITY_UNVERIFIED":
            need(period == "TICKS" and side == "BID_ASK" and
                 first == scope.start and last == scope.end,
                 "RECOVERY_GAP_BLOCKED_ACTIVITY")
            blocked.append(row)
            continue
        need(reason in ("MISSING", "PROVIDER_ERROR"), "RECOVERY_GAP_INVALID_REASON")
        if side == "BARS":
            need(period in scope.periods and scope.warmup <= first < last <= scope.end,
                 "RECOVERY_GAP_BAR_BOUNDS")
            chunk = scope.periods[period][1]
            need((first - scope.warmup) % chunk == 0 and
                 last == min(first + chunk, scope.end), "RECOVERY_GAP_BAR_GRID")
        else:
            need(period == "TICKS" and side in ("BID", "ASK") and
                 scope.start <= first < last <= scope.end and last - first <= 2 * HOUR,
                 "RECOVERY_GAP_TICK_BOUNDS")
        if reason == "PROVIDER_ERROR":
            code = row.get("ProviderCode")
            need(isinstance(code, str) and code.isascii() and
                 code.replace("_", "").isalnum(), "RECOVERY_GAP_PROVIDER_CODE")
        identity = (market, period, side, first, last)
        need(identity not in identities, "RECOVERY_GAP_DUPLICATE")
        identities.add(identity)
        ranges[(market, period, side)].append((first, last))
        executable.append(row)
    for values in ranges.values():
        values.sort()
        need(all(a[1] <= b[0] for a, b in zip(values, values[1:])),
             "RECOVERY_GAP_OVERLAP")
    need(not any(row["Market"] in {b["Market"] for b in blocked} and row["Timeframe"] == "TICKS"
                 for row in executable), "RECOVERY_GAP_ACTIVITY_MUST_PRECEDE_TICKS")
    return sorted(executable, key=lambda x: (x["Market"], x["Timeframe"], x["Side"], x["From"])), blocked


def verify_plan_receipt(gap_bytes, recovery_receipt):
    need(recovery_receipt.get("Status") == "CUSTODY_VERIFIED_PARTIAL_SOURCE" and
         recovery_receipt.get("OriginalRun") == "44824462289" and
         recovery_receipt.get("GapRequestsSha256") == hashlib.sha256(gap_bytes).hexdigest() and
         recovery_receipt.get("NewOpenApiRequests") == 0,
         "RECOVERY_GAP_RECEIPT_HASH")
    return validate_plan(json.loads(gap_bytes))


def bounded_read_only_request(request, send, retain, *, authorized=False, sleep=time.sleep):
    """Future-only primitive: retain EVERY attempt and never reinterpret errors as quotes.

    This function cannot authenticate or open a connection. It also does not make a
    hasMore response terminal; the caller must recursively acquire its child leaves.
    """
    need(authorized is True, "RECOVERY_NEW_OPEN_API_NOT_AUTHORIZED")
    require_read_only_request(request)
    need(isinstance(request, (m.ProtoOAGetTickDataReq, m.ProtoOAGetTrendbarsReq)),
         "RECOVERY_ONLY_HISTORICAL_MARKET_REQUESTS")
    expected = (m.ProtoOAGetTickDataRes if isinstance(request, m.ProtoOAGetTickDataReq)
                else m.ProtoOAGetTrendbarsRes)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            sleep(max(MIN_HISTORICAL_SPACING_SECONDS, float(2 ** (attempt - 2))))
        try:
            result = send(request)
        except (TimeoutError, ConnectionError, OSError) as exc:
            retain({"Attempt": attempt, "TransportFailure": type(exc).__name__,
                    "HasProviderResponse": False})
            if attempt < MAX_ATTEMPTS:
                continue
            raise CaptureContractError("RECOVERY_TRANSPORT_RETRIES_EXHAUSTED") from None
        need(result.IsInitialized() and result.ctidTraderAccountId == request.ctidTraderAccountId,
             "RECOVERY_RESPONSE_ACCOUNT_BINDING")
        retain({"Attempt": attempt, "OriginalPacket": pack(request, result),
                "HasProviderResponse": True})
        if isinstance(result, m.ProtoOAErrorRes):
            if result.errorCode == "NO_QUOTES":
                return result
            if result.errorCode in RETRYABLE and attempt < MAX_ATTEMPTS:
                continue
            raise CaptureContractError("RECOVERY_PROVIDER_REQUEST_REJECTED")
        need(type(result) is expected, "RECOVERY_RESPONSE_TYPE")
        return result
    raise CaptureContractError("RECOVERY_RETRIES_EXHAUSTED")
