"""Acquire and rebuild the missing native timeframes. Public output is aggregate only."""

import gzip
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import decode_bars, need
from .guard import require_read_only_request
from .hxc1_historical_readback import _source_account_matches
from .hxc1_historical_source import decode_response, stamp
from .integrated_market_source import digest, pack, unpack
from .owner_readonly_auth import authenticate


PROTOCOL = Path("research/closed_market_bar_source_protocol.json")
OUTPUT = Path("closed-market-source")
INTENT = "OWNER_CLOSED_MARKET_CONTEXT_SOURCE_ONCE"
MINUTES = {"M1": 1, "M30": 30, "H4": 240, "D1": 1440}


def requests(plan, enabled):
    end = stamp(plan["end"])
    names = {label: next((name for name in aliases if name in enabled), None)
             for label, aliases in plan["universe"].items()}
    windows = []
    for label, name in names.items():
        if name is None:
            continue
        for period, minutes in MINUTES.items():
            chunk = plan["chunkHours"][period] * 3_600_000
            first = stamp(plan["minuteWarmupFrom"] if period == "M1" else plan["warmupFrom"])
            last = stamp(plan["coveredByHxc1From"]) if period == "M1" and label in plan["coveredByHxc1"] else end
            width = minutes * 60_000
            need(first < last and chunk > 0 and first % width == last % width == chunk % width == 0,
                 "CLOSED_CONTEXT_BROKER_WINDOW_INVALID")
            windows.extend((name, period, at, min(at + chunk, last)) for at in range(first, last, chunk))
    need(0 < len(windows) <= plan["maximumTrendbarRequests"] and len(windows) == len(set(windows)),
         "CLOSED_CONTEXT_BROKER_REQUEST_BUDGET")
    return names, windows


def identity(records):
    pairs = [unpack(row) for row in records]
    expected = [(m.ProtoOATraderReq, m.ProtoOATraderRes),
                (m.ProtoOAAssetListReq, m.ProtoOAAssetListRes),
                (m.ProtoOASymbolsListReq, m.ProtoOASymbolsListRes)]
    need([(type(q), type(r)) for q, r in pairs] == expected, "CLOSED_CONTEXT_BROKER_IDENTITY_WIRE")
    trader, assets, roster = [r for _, r in pairs]
    account = trader.ctidTraderAccountId
    need(_source_account_matches(account) and all(q.ctidTraderAccountId == account for q, _ in pairs)
         and "pepperstone" in trader.trader.brokerName.casefold()
         and any(a.assetId == trader.trader.depositAssetId and a.name == "EUR" for a in assets.asset),
         "CLOSED_CONTEXT_BROKER_ACCOUNT")
    return account, {x.symbolName: x.symbolId for x in roster.symbol if x.enabled}


def rebuild(bundle, plan, run, protocol_hash):
    need(bundle["RunId"] == run and bundle["ProtocolSha256"] == protocol_hash, "CLOSED_CONTEXT_SOURCE_BINDING")
    account, enabled = identity(bundle["Identity"])
    names, windows = requests(plan, enabled)
    need(len(windows) == len(bundle["Pages"]), "CLOSED_CONTEXT_BROKER_PAGES_MISSING")
    bars = defaultdict(list)
    unavailable = Counter()
    for (name, period, first, last), wire in zip(windows, bundle["Pages"]):
        req, res = unpack(wire)
        need(isinstance(req, m.ProtoOAGetTrendbarsReq) and req.ctidTraderAccountId == account
             and req.symbolId == enabled[name] and req.period == getattr(e, period)
             and req.fromTimestamp == first and req.toTimestamp == last, "CLOSED_CONTEXT_BROKER_PAGE_BINDING")
        rows = bars[(name, period)]
        if isinstance(res, m.ProtoOAErrorRes) and res.errorCode == "NO_QUOTES":
            unavailable[(name, period, "NO_QUOTES")] += 1
            continue
        need(isinstance(res, m.ProtoOAGetTrendbarsRes) and res.period == req.period,
             "CLOSED_CONTEXT_BROKER_RESPONSE_TYPE")
        if not res.HasField("hasMore") or res.hasMore:
            unavailable[(name, period, "UNVERIFIED_PAGINATION")] += 1
            continue
        decoded = decode_response(res, first, last, MINUTES[period])
        if not decoded:
            unavailable[(name, period, "EMPTY")] += 1
        need(not rows or not decoded or rows[-1][1] <= decoded[0][0], "CLOSED_CONTEXT_BROKER_BAR_OVERLAP")
        rows.extend(decoded)
    coverage = [{"Symbol": name, "Timeframe": period, "Bars": len(rows),
                 "FirstOpenAt": rows[0][0] if rows else None, "LastCloseAt": rows[-1][1] if rows else None,
                 "PageStatusCounts": {status: n for (s, p, status), n in unavailable.items() if (s, p) == (name, period)}}
                for (name, period), rows in bars.items()]
    return bars, dict(SourceRun=run, ProtocolSha256=protocol_hash, NativeTrendbarRequests=len(windows),
                      AliasResolution=names, Coverage=coverage, OriginalPepperstoneEurAccount=True,
                      BrokerOrders=0, CloudActivated=False, EconomicEvaluations=0)


def collect():
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and os.environ.get("GITHUB_REF") == "refs/heads/main"
         and os.environ.get("GITHUB_ACTOR") == "mariancradulescu" and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
         and Path("ops/closed-market-context-source-once.txt").read_text().strip() == INTENT,
         "CLOSED_CONTEXT_SOURCE_INTENT_REQUIRED")
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-source-recipient"), run)
    raw = PROTOCOL.read_bytes()
    plan = json.loads(raw)
    transport = StdlibCTraderTransport()

    def observe(req):
        require_read_only_request(req)
        return pack(req, transport.request(req))

    try:
        account = authenticate(transport)
        roster = [observe(request) for request in (
            m.ProtoOATraderReq(ctidTraderAccountId=account),
            m.ProtoOAAssetListReq(ctidTraderAccountId=account),
            m.ProtoOASymbolsListReq(ctidTraderAccountId=account, includeArchivedSymbols=False))]
        _, enabled = identity(roster)
        _, windows = requests(plan, enabled)
        pages = []
        next_request = 0.0
        for symbol, period, first, last in windows:
            time.sleep(max(0.0, next_request - time.monotonic()))
            next_request = time.monotonic() + 0.25
            pages.append(observe(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=enabled[symbol],
                                 period=getattr(e, period), fromTimestamp=first, toTimestamp=last)))
    finally:
        transport.close()
    bundle = dict(RunId=run, ProtocolSha256=digest(raw), Identity=roster, Pages=pages)
    plain = gzip.compress(json.dumps(bundle, separators=(",", ":")).encode(), mtime=0)
    cipher = seal_new(plain, recipient, run)
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "source.enc").write_bytes(cipher)
    _, report = rebuild(bundle, plan, run, digest(raw))
    report.update(CipherSha256=digest(cipher), CompressedPlainSha256=digest(plain))
    (OUTPUT / "source.public.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Native closed market source collected and sealed.", flush=True)


def readback(private_key, run, native_boundaries=False):
    protocol = PROTOCOL.read_bytes()
    receipt = json.loads((OUTPUT / "source.public.json").read_text())
    cipher = (OUTPUT / "source.enc").read_bytes()
    need(receipt["SourceRun"] == run and digest(cipher) == receipt["CipherSha256"], "CLOSED_CONTEXT_CIPHER_HASH")
    plain = unseal_new(cipher, private_key, run)
    need(digest(plain) == receipt["CompressedPlainSha256"], "CLOSED_CONTEXT_PLAIN_HASH")
    bundle, plan = json.loads(gzip.decompress(plain)), json.loads(protocol)
    bars, report = rebuild(bundle, plan, run, digest(protocol))
    need(all(receipt[key] == value for key, value in report.items()), "CLOSED_CONTEXT_SOURCE_RECONCILIATION")
    if native_boundaries:
        # The original UTC page cut may cross an H4 or D1 bar. Once the raw
        # complete page is authenticated, retain by source open time and the
        # overall source boundary, rather than by the arbitrary chunk close.
        _, enabled = identity(bundle["Identity"])
        _, windows = requests(plan, enabled)
        end = stamp(plan["end"])
        long_bars = defaultdict(list)
        for (name, period, first, last), wire in zip(windows, bundle["Pages"]):
            if period not in ("H4", "D1"):
                continue
            _, res = unpack(wire)
            if not isinstance(res, m.ProtoOAGetTrendbarsRes) or not res.HasField("hasMore") or res.hasMore:
                continue
            minutes = MINUTES[period]
            width = minutes * 60_000
            long_bars[(name, period)].extend(row for row in decode_bars(res.trendbar, first - width, last + width, minutes)
                                                   if first <= row[0] < last and row[1] <= end)
        bars.update(long_bars)
    return bars, receipt


if __name__ == "__main__":
    try:
        collect()
    except Exception as exc:
        from .guard import CaptureContractError
        code = str(exc)
        print(code if isinstance(exc, CaptureContractError) and code.isupper() and code.replace("_", "").isalnum()
              else "CLOSED_CONTEXT_SOURCE_FAILED_CLOSED", flush=True)
        raise SystemExit(1)
