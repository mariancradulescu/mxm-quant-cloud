"""HXC1: bounded original-account historical OHLCV source capture, no strategy scoring.

New research data acquisition only. Does not run RDE1, closed studies, or
any workflow. Invoke only from an independently authorized protected source
job with an existing v2 run-bound PUBLIC recipient. Broker private data stays
inside a sealed artifact; stdout contains public support counts only.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .decode import decode_bars, need
from .guard import CaptureContractError, require_read_only_request
from .custody import seal_new
from .custody_new import checked_public

PROTOCOL = Path("research/hxc1_historical_source_protocol.json")
OUTPUT = Path("sealed-output")
SCHEMA = "MXM_HXC1_BROKER_ORIGINAL_HISTORICAL_BARS_SOURCE_V1"
PERIOD_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}


def stamp(value: str) -> int:
    """Interpret a frozen UTC boundary; reject local/ambiguous timestamps."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    need(value.endswith("Z") and dt.tzinfo is not None and
         dt.utcoffset().total_seconds() == 0, "HXC1_NOT_UTC")
    return int(dt.timestamp() * 1000)


def planned_requests(plan: dict) -> list[tuple[str, str, int, int]]:
    """Price-outcome-blind request geometry; no discretionary gap repair."""
    need(plan.get("schema") == "MXM_HXC1_AUTHENTIC_HISTORICAL_OHLCV_SOURCE_ONLY_V1" and
         plan.get("status") == "SOURCE_PLAN_FROZEN_UNEXECUTED" and
         plan.get("research") == "NO_PREDICTOR_OR_RESULT_IS_EVALUATED_DURING_SOURCE_CAPTURE",
         "HXC1_PROTOCOL_INVALID")
    out = []
    known = set()
    for group in plan["symbolGroups"].values():
        need(all(isinstance(x, str) and x for x in group), "HXC1_SYMBOL_GROUP_INVALID")
        known.update(group)
    need(bool(known), "HXC1_UNIVERSE_EMPTY")
    for spec in plan["ranges"]:
        period = spec["period"]
        need(period in PERIOD_MINUTES, "HXC1_PERIOD_NOT_ALLOWED")
        symbols = plan["symbolGroups"].get(spec["symbolGroup"])
        need(symbols and len(set(symbols)) == len(symbols), "HXC1_SYMBOL_GROUP_INVALID")
        first, last = stamp(spec["fromUtc"]), stamp(spec["toUtc"])
        interval = int(spec["chunkHours"]) * 3_600_000
        step = PERIOD_MINUTES[period] * 60_000
        need(interval >= step and interval % step == 0 and first < last and
             first % step == last % step == 0 and
             last - first <= 730 * 86_400_000, "HXC1_CHUNK_GEOMETRY")
        for symbol in symbols:
            current = first
            while current < last:
                end = min(current + interval, last)
                out.append((symbol, period, current, end))
                current = end
    need(len(out) <= int(plan["maximumMarketDataRequests"]) and len(out) > 0,
         "HXC1_REQUEST_BUDGET")
    need(len(set(out)) == len(out), "HXC1_DUPLICATE_REQUEST")
    return out


def decode_response(response, first: int, last: int, minutes: int):
    """Keep only completed, original-clock bars; no synthetic OHLCV or gaps."""
    need(isinstance(response, m.ProtoOAGetTrendbarsRes) and
         response.IsInitialized() and response.HasField("hasMore") and
         not response.hasMore, "HXC1_TREND_BARS_INCOMPLETE")
    step = minutes * 60_000
    rows = decode_bars(response.trendbar, first-step, last+step, minutes)
    return [r for r in rows if first <= r[0] and r[1] <= last]


def collect() -> None:
    plan_bytes = PROTOCOL.read_bytes()
    plan = json.loads(plan_bytes)
    requests = planned_requests(plan)
    run = os.environ.get("GITHUB_RUN_ID", "")
    need(run.isdigit() and int(run) > 0, "HXC1_RUN_NOT_BOUND")
    # The public recipient was created by the project's existing protected
    # custody recipient job; no private key is read by the broker collector.
    recipient = checked_public(Path("new-source-recipient"), run)
    transport = StdlibCTraderTransport()
    raw = []
    original_roster = []
    bars: dict[str, list[list[int]]] = {}
    windows = []
    provenance = hashlib.sha256(plan_bytes).hexdigest()

    def observe(req, expected_type):
        require_read_only_request(req)
        result = transport.request(req)
        need(isinstance(result, expected_type) and result.IsInitialized(),
             "HXC1_RESPONSE_TYPE")
        return result

    try:
        account = authenticate(transport)
        trader_request = m.ProtoOATraderReq(ctidTraderAccountId=account)
        trader = observe(trader_request, m.ProtoOATraderRes)
        original_roster.append((trader_request, trader))
        need(trader.ctidTraderAccountId == account and
             "pepperstone" in trader.trader.brokerName.casefold(),
             "HXC1_BROKER_IDENTITY")
        roster_request = m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False)
        roster = observe(roster_request, m.ProtoOASymbolsListRes)
        original_roster.append((roster_request, roster))
        need(roster.ctidTraderAccountId == account, "HXC1_ROSTER_IDENTITY")
        available = {row.symbolName: row.symbolId
                     for row in roster.symbol if row.enabled}
        desired = {name for name, _, _, _ in requests}
        need(desired.issubset(available), "HXC1_BROKER_SYMBOL_MISSING")
        for name in sorted(desired):
            detail_request = m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account, symbolId=[available[name]])
            detail = observe(detail_request, m.ProtoOASymbolByIdRes)
            original_roster.append((detail_request, detail))
            need(detail.ctidTraderAccountId == account and len(detail.symbol) == 1
                 and detail.symbol[0].symbolId == available[name],
                 "HXC1_CONTRACT_BINDING")

        for symbol, period, first, last in requests:
            message = m.ProtoOAGetTrendbarsReq(
                ctidTraderAccountId=account,
                symbolId=available[symbol],
                period=getattr(e, period),
                fromTimestamp=first,
                toTimestamp=last
            )
            response = observe(message, m.ProtoOAGetTrendbarsRes)
            need(response.ctidTraderAccountId == account and
                 response.period == getattr(e, period), "HXC1_RESPONSE_BINDING")
            rows = decode_response(response, first, last, PERIOD_MINUTES[period])
            tag = symbol + "/" + period
            bars.setdefault(tag, []).extend(rows)
            windows.append({"symbol": symbol, "period": period,
                            "first": first, "last": last, "barCount": len(rows),
                            "rawIndex": len(raw)})
            raw.append({
                "requestType": "ProtoOAGetTrendbarsReq",
                "requestProtobuf": base64.b64encode(message.SerializeToString()).decode("ascii"),
                "responseType": "ProtoOAGetTrendbarsRes",
                "responseProtobuf": base64.b64encode(response.SerializeToString()).decode("ascii")
            })

        # Reject overlaps, invalid observation times, inconsistent OHLC;
        # missing market sessions remain missing, never forward-filled.
        summary = {}
        for tag, rows in bars.items():
            minutes = PERIOD_MINUTES[tag.split("/")[-1]]
            rows.sort(key=lambda v: v[0])
            need(all(len(row) == 7 and row[1] - row[0] == minutes * 60_000
                     and row[4] > 0 and row[4] <= min(row[2], row[5])
                     and max(row[2], row[5]) <= row[3] and row[6] >= 0
                     for row in rows), "HXC1_SOURCE_GEOMETRY")
            need(all(rows[i][0] > rows[i-1][0] for i in range(1, len(rows))),
                 "HXC1_REPEATED_OR_UNSORTED_BAR")
            summary[tag] = len(rows)
        for period, minimum in plan["minimumBarsToAcceptPerPeriod"].items():
            need(all(count >= int(minimum) for tag, count in summary.items()
                     if tag.endswith("/"+period)) and
                 any(tag.endswith("/"+period) for tag in summary),
                 "HXC1_SOURCE_SUPPORT_FAILED")

        bundle = {
            "schema": SCHEMA,
            "readOnly": True,
            "source": "original-account-Pepperstone-cTrader-OpenAPI",
            "sourceRunId": run,
            "protocolSha256": provenance,
            "raw": raw,
            "identityRaw": [
                {"requestType": type(req).__name__,
                 "requestProtobuf": base64.b64encode(req.SerializeToString()).decode("ascii"),
                 "responseType": type(res).__name__,
                 "responseProtobuf": base64.b64encode(res.SerializeToString()).decode("ascii")}
                for req, res in original_roster
            ],
            "windows": windows,
            "bars": bars,
            "decodedRows": summary,
            "originalProviderAccountBindingVerified": True,
            "researchScored": False,
            "brokerOrders": 0,
            "cloudActivated": False
        }
        sealed = seal_new(json.dumps(bundle, sort_keys=True,
                                     separators=(",", ":")).encode(), recipient, run)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "source.envelope.json").write_bytes(sealed)
        public = {
            "schema": "MXM_HXC1_PUBLIC_SOURCE_CUSTODY_RECEIPT_V1",
            "sourceRunId": run,
            "protocolSha256": provenance,
            "ciphertextSha256": hashlib.sha256(sealed).hexdigest(),
            "windowRequests": len(requests),
            "sourceCounts": summary,
            "emptyWindows": sum(w["barCount"] == 0 for w in windows),
            "researchScored": False,
            "netEur": None,
            "economicQualification": False,
            "ordersSubmitted": 0,
            "cloudActivated": False
        }
        (OUTPUT / "receipt.public.json").write_text(
            json.dumps(public, sort_keys=True, indent=2) + "\n")
        print("HXC1_AUTHENTIC_HISTORICAL_SOURCE_SEALED_NO_ECONOMIC_SCORE", flush=True)
    finally:
        transport.close()


if __name__ == "__main__":
    try:
        collect()
    except Exception as exc:
        code = str(exc)
        if not isinstance(exc, CaptureContractError) or not code.isupper() or not code.replace("_", "").isalnum():
            code = "HXC1_SOURCE_FAILED_CLOSED"
        print(code, flush=True)
        raise SystemExit(1)
