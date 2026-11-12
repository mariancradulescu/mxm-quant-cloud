"""Bounded original-account read-only recovery of the exact SEM1 ETHEUR exit.

Only historical tick BID/ASK at the original registered as-of clock, within
the exact original 30-second age. Never send an order or a refresh request.
Keep raw price evidence inside the existing run-bound encrypted custody.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import decode_side
from .owner_readonly_auth import authenticate
from .guard import require_read_only_request
from .custody import seal_new
from .custody_new import checked_public

CLOCK_UTC_MS = 1788075001500  # 2026-08-30 07:30:01.500 UTC
MAX_AGE_MS = 30000
SYMBOLS = ("ETHEUR", "EURUSD")
MAX_PAGES_PER_SIDE = 8


def main():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    transport = StdlibCTraderTransport()
    requests = 0

    try:
        account = authenticate(transport)

        def request(msg, klass):
            nonlocal requests
            if requests >= 32:
                raise ValueError("SEM1_PROBE_READONLY_REQUEST_BUDGET")
            require_read_only_request(msg)
            response = transport.request(msg)
            requests += 1
            if (klass is m.ProtoOAGetTickDataRes
                    and type(response) is m.ProtoOAErrorRes
                    and response.errorCode == "NO_QUOTES"
                    and response.ctidTraderAccountId == account):
                return None
            if (type(response) is not klass or not response.IsInitialized()
                    or response.ctidTraderAccountId != account):
                raise ValueError("SEM1_PROBE_ORIGINAL_ACCOUNT_RESPONSE_MISMATCH")
            return response

        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes)
        assets_reply = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        assets = {a.assetId: a.name for a in assets_reply.asset}
        if (not trader.trader.HasField("brokerName")
                or "pepperstone" not in trader.trader.brokerName.casefold()
                or assets.get(trader.trader.depositAssetId) != "EUR"):
            raise ValueError("SEM1_PROBE_ORIGINAL_PEPPERSTONE_EUR_MISMATCH")

        roster_reply = request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        roster = {s.symbolName:s for s in roster_reply.symbol if s.enabled}
        if any(s not in roster for s in SYMBOLS):
            raise ValueError("SEM1_PROBE_SOURCE_SYMBOL_UNAVAILABLE")

        full = {}
        published = {}
        for symbol in SYMBOLS:
            instrument_id = int(roster[symbol].symbolId)
            side_data = {}
            side_stats = {}
            for side_name, side in (("BID",e.BID),("ASK",e.ASK)):
                lo = CLOCK_UTC_MS - MAX_AGE_MS
                hi = CLOCK_UTC_MS
                pages = []
                page_count = 0
                while hi >= lo:
                    page_count += 1
                    if page_count > MAX_PAGES_PER_SIDE:
                        raise ValueError("SEM1_PROBE_TICK_PAGINATION_INCOMPLETE")
                    response = request(m.ProtoOAGetTickDataReq(
                        ctidTraderAccountId=account, symbolId=instrument_id,
                        type=side, fromTimestamp=lo, toTimestamp=hi), m.ProtoOAGetTickDataRes)
                    if response is None:
                        break
                    points = decode_side(response.tickData, lo, hi)
                    pages.append(points)
                    if not response.hasMore:
                        break
                    if not points:
                        raise ValueError("SEM1_PROBE_TICK_PAGINATION_EMPTY")
                    earliest = points[0][0]
                    if earliest <= lo:
                        raise ValueError("SEM1_PROBE_TICK_PAGINATION_BOUNDARY")
                    hi = earliest - 1
                chronological = [p for page in reversed(pages) for p in page]
                eligible = [(int(t),int(price)) for t,price in chronological
                            if CLOCK_UTC_MS-MAX_AGE_MS <= int(t) <= CLOCK_UTC_MS]
                selected = eligible[-1] if eligible else None
                side_data[side_name] = {
                    "AllAsOfTicks": eligible,
                    "SelectedAsOfTick": selected,
                    "PageCount": page_count,
                }
                side_stats[side_name] = {
                    "EligibleRawTicks": len(eligible),
                    "LastAsOfTickUtcMs": selected[0] if selected else None,
                    "AsOfAgeMs": CLOCK_UTC_MS-selected[0] if selected else None,
                    "Present": selected is not None,
                }
            full[symbol] = side_data
            published[symbol] = dict(side_stats, PairedBidAskAsOf=(
                side_stats["BID"]["Present"] and side_stats["ASK"]["Present"]))

    finally:
        transport.close()

    original = {
        "Schema": "SEM1_ORIGINAL_EXIT_TICK_BIDASK_RECOVERY_V1",
        "Source": "ORIGINAL_PEPPERSTONE_ACCOUNT_READONLY_OPENAPI",
        "ClockUtcMs": CLOCK_UTC_MS, "MaximumAsOfAgeMs": MAX_AGE_MS,
        "Symbols": full, "NoFutureTickPermitted": True,
    }
    raw = json.dumps(original,separators=(",",":")).encode()
    envelope = seal_new(raw,recipient,run)
    Path("sem1-exact-exit-source.v2.enc").write_bytes(envelope)
    result = {
        "Study": "SEM1_EXACT_ETHEUR_EXIT_RECOVERY",
        "Classification": "EXPOSED_POSTCLOSURE_SOURCE_RECOVERY",
        "FixedExitClockUtcMs": CLOCK_UTC_MS, "MaximumAsOfAgeMs": MAX_AGE_MS,
        "OriginalPepperstoneEurAccountAuthenticated": True,
        "OriginalOpenApiReadOnlyRequests": requests,
        "SourcePlaintextSha256": sha256(raw).hexdigest(),
        "SourceCiphertextSha256": sha256(envelope).hexdigest(),
        "QuoteCoverage": published,
        "AllAffectedPoliciesMustUseOneIdenticalClock": True,
        "NoNewIndependentConfirmation": True,
        "OrdersSubmitted": 0, "CloudActivated": False,
        "ProtocolSha256": sha256(Path("research/SEM1_EXACT_EXIT_RECOVERY.md").read_bytes()).hexdigest(),
    }
    Path("sem1-exact-exit-recovery-public.json").write_text(json.dumps(result,indent=2)+"\n")


if __name__ == "__main__":
    main()
