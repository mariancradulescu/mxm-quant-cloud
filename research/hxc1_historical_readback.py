"""HXC1 independent raw-broker readback for a NEW source-only capture.

Called only after a properly authorized original account source acquisition.
Neither imports model outcomes nor runs any closed study. Never writes private
OHLCV, account IDs, auth material or tick events to a public artifact.
"""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need
from .guard import require_read_only_request
from .hxc1_historical_source import (PERIOD_MINUTES, PROTOCOL, SCHEMA,
                                     planned_requests, decode_response)


def _source_account_matches(account: int) -> bool:
    fp = hashlib.sha256(f"ctrader-account:{account}".encode("ascii")).hexdigest()
    return hashlib.sha256(fp.encode("ascii")).hexdigest() == HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT


def validate(bundle: dict, receipt: dict, run_id: str) -> dict:
    plan_raw = PROTOCOL.read_bytes()
    plan = json.loads(plan_raw)
    expected = planned_requests(plan)
    need(bundle.get("schema") == SCHEMA and bundle.get("sourceRunId") == run_id and
         receipt.get("sourceRunId") == run_id and bundle.get("readOnly") is True and
         bundle.get("brokerOrders") == 0 and bundle.get("cloudActivated") is False and
         bundle.get("researchScored") is False and receipt.get("researchScored") is False,
         "HXC1_CUSTODY_AND_SCOPE")
    digest = hashlib.sha256(plan_raw).hexdigest()
    need(bundle.get("protocolSha256") == digest and
         receipt.get("protocolSha256") == digest, "HXC1_SOURCE_PROTOCOL")
    windows = bundle.get("windows", [])
    raw = bundle.get("raw", [])
    need(len(windows) == len(raw) == len(expected) and
         receipt.get("windowRequests") == len(expected), "HXC1_MISSING_REQUESTS")
    built = {}
    symbol_ids = {}
    account_id = None
    for i, (entry, blob, case) in enumerate(zip(windows, raw, expected)):
        symbol, period, first, last = case
        need(entry["symbol"] == symbol and entry["period"] == period and
             entry["first"] == first and entry["last"] == last and
             entry["rawIndex"] == i, "HXC1_WINDOW_BINDING")
        need(blob["requestType"] == "ProtoOAGetTrendbarsReq" and
             blob["responseType"] == "ProtoOAGetTrendbarsRes", "HXC1_WIRE_TYPE")
        req = m.ProtoOAGetTrendbarsReq()
        res = m.ProtoOAGetTrendbarsRes()
        req.ParseFromString(base64.b64decode(blob["requestProtobuf"], validate=True))
        res.ParseFromString(base64.b64decode(blob["responseProtobuf"], validate=True))
        require_read_only_request(req)
        need(res.IsInitialized() and res.ctidTraderAccountId == req.ctidTraderAccountId,
             "HXC1_WIRE_ACCOUNT")
        if account_id is None:
            account_id = req.ctidTraderAccountId
            need(_source_account_matches(account_id), "HXC1_ORIGINAL_ACCOUNT")
        need(req.ctidTraderAccountId == account_id and
             req.period == res.period == getattr(e, period) and
             req.fromTimestamp == first and req.toTimestamp == last,
             "HXC1_REQUEST_RESPONSE_BINDING")
        previous_symbol_id = symbol_ids.setdefault(symbol, req.symbolId)
        need(previous_symbol_id == req.symbolId, "HXC1_SYMBOL_BINDING")
        rows = decode_response(res, first, last, PERIOD_MINUTES[period])
        need(entry["barCount"] == len(rows), "HXC1_WINDOW_BAR_COUNT")
        built.setdefault(symbol + "/" + period, []).extend(rows)
    summary = {}
    for tag, rows in built.items():
        rows.sort(key=lambda row: row[0])
        need(all(rows[i][0] > rows[i-1][0] for i in range(1, len(rows))),
             "HXC1_DUPLICATE_BAR")
        need(bundle["bars"].get(tag) == rows, "HXC1_RAW_DECODE_MISMATCH")
        summary[tag] = len(rows)
    need(summary == bundle.get("decodedRows") == receipt.get("sourceCounts"),
         "HXC1_SOURCE_CENSUS")
    return {
        "status": "HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT",
        "sourceRunId": run_id,
        "protocolSha256": digest,
        "sourceCounts": summary,
        "rawRequestsRebuilt": len(raw),
        "newIndependentPredictiveResults": False,
        "historicalEURCostVerified": False,
        "netEur": None,
        "economicQualification": False,
        "brokerOrders": 0,
        "cloudActivated": False
    }
