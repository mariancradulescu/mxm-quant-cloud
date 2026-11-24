"""A second bounded read-only tranche, consumed by the same native gross comparison."""
from collections import Counter, deque
from decimal import Decimal
import json
import os
from pathlib import Path
import sys

from . import owner_source_history_use as use
from . import source_history_universe as source
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as models
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport


MARKER = "OWNER_NEXT_SOURCE_HISTORY_TRANCHE_20261124"
MARKER_NAME = "ops/source-history-extension-once.txt"
OUT = Path("owner-source-extension")
START, END = source.END - 4 * source.WEEK, source.END
DAYS_PER_PAGE = {"M1": 4, "M5": 7, "M15": 14, "M30": 14, "H1": 28, "H4": 28, "D1": 28}
P05_RECEIPT_SHA = "939715d03f903979ef63df645a6fcffcdcd663c74d185d4849b27649d9a2faf5"


def inputs():
    path = Path("original-source-history/receipt.json")
    raw = path.read_bytes()
    need(source.digest(raw) == use.RECEIPT_SHA, "EXTENSION_ORIGINAL_RECEIPT")
    original = json.loads(raw)
    prior = Path("p05-public/receipt.json").read_bytes()
    need(source.digest(prior) == P05_RECEIPT_SHA, "EXTENSION_P05_HASH")
    previous = json.loads(prior)
    need(str(previous["runId"]) == "45134137836" and bool(previous["marketCoverage"]), "EXTENSION_P05_RECEIPT")
    return original, set(previous["marketCoverage"])


def plan(previous, prior_market_names, excluded_ids=()):
    examined = set(previous["timeframeProbeIds"]) | set(excluded_ids)
    annual = json.loads(Path("research/portfolio_discovery_protocol.json").read_text())["universe"]
    covered_names = set(annual) | prior_market_names
    roster = {r["symbolId"]: r for r in previous["contractRoster"]
              if r["symbolId"] not in examined and r["name"] not in covered_names and r["name"]
              and r["contractStatus"] == source.VERIFIED and r["tradingMode"] == 0
              and (r.get("minVolume") or 0) > 0}
    return [roster[sid] for sid in source.selected_ids(roster)]


def page_pair(q, r):
    return source.matching(r, m.ProtoOAGetTrendbarsRes, q.ctidTraderAccountId) and r.period == q.period and (
        not r.HasField("symbolId") or r.symbolId == q.symbolId)


def timeframe(journal, account, symbol, period):
    enum = models.ProtoOATrendbarPeriod.Value(period)
    span = DAYS_PER_PAGE[period] * source.DAY
    windows = deque((lo, min(lo + span, END) - 1) for lo in range(START, END, span))
    rows, coverage, diagnostics = {}, [], Counter()
    while windows:
        lo, hi = windows.popleft()
        request = m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=symbol,
                    period=enum, fromTimestamp=lo, toTimestamp=hi)
        response, at, status = journal.query(request)
        entry = dict(fromTime=lo, toTime=hi, status=status)
        coverage.append(entry)
        if response is None:
            diagnostics[status] += 1
            continue
        if page_pair(request, response) and response.HasField("hasMore") and response.hasMore:
            if hi - lo >= 2 * source.PERIODS[period] * 60_000:
                windows.extendleft(reversed(source.split_window(lo, hi)))
                entry["status"] = "PAGINATION_SPLIT"
                diagnostics[entry["status"]] += 1
                continue
        description, bars = use.inspect_bars(request, response, at, closed_through=END)
        entry.update(description)
        diagnostics[entry["status"]] += 1
        for bar in bars:
            need(bar[0] not in rows, "EXTENSION_DUPLICATE_ACCEPTED_BAR")
            rows[bar[0]] = bar
    return sorted(rows.values()), dict(pages=coverage, counts=dict(diagnostics), closedRows=len(rows))


def collect(journal, account, selection, run_id):
    receipts, markets, margins = {}, {}, {}
    for instrument in selection:
        sid, name = instrument["symbolId"], instrument["name"]
        margin, at, status = journal.query(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                           symbolId=sid, volume=[instrument["minVolume"]]))
        if source.matching(margin, m.ProtoOAExpectedMarginRes, account) and margin.HasField("moneyDigits") and (
                len(margin.margin) == 1 and 0 <= margin.moneyDigits <= 12):
            row = margin.margin[0]
            if row.volume == instrument["minVolume"] and min(row.buyMargin, row.sellMargin) >= 0:
                margins[sid] = dict(BuyEur=str(Decimal(row.buyMargin).scaleb(-margin.moneyDigits)),
                    SellEur=str(Decimal(row.sellMargin).scaleb(-margin.moneyDigits)), AvailableAt=at,
                    VolumeUnits=str(Decimal(row.volume).scaleb(-2)))
                status = source.VERIFIED
        receipts[name] = dict(symbolId=sid, category=instrument["category"], marginStatus=status, timeframes={})
        for period in DAYS_PER_PAGE:
            rows, diagnostics = timeframe(journal, account, sid, period)
            receipts[name]["timeframes"][period] = diagnostics
            if rows:
                markets.setdefault(name, {})[period] = rows
    categories = {row["name"]: str(row["category"]) for row in selection}
    archive = use.archive_input(run_id, markets, categories)
    return receipts, archive, margins


def capture():
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and os.environ.get("GITHUB_REF") == "refs/heads/main"
         and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
         and Path(MARKER_NAME).read_text() == MARKER + "\n", "EXTENSION_AUTHORIZATION")
    rid = os.environ["GITHUB_RUN_ID"]
    original, prior = inputs()
    selection = plan(original, prior)
    need(bool(selection), "EXTENSION_NO_NEW_SYMBOLS")
    recipient = checked_public(Path("extension-recipient"), rid)
    transport = P05ReadOnlyTransport(response_timeout=20)
    try:
        account = authenticate(transport)
        journal = source.Journal(transport, account)
        coverage, _, _ = collect(journal, account, selection, rid)
    finally:
        transport.close()
    summary = dict(runId=rid, sourceBaseRunId=use.SOURCE_RUN, start=START, endExclusive=END,
        coverage=coverage, capturedRequests=len(journal.packets),
        responses=sum(packet["res"] is not None for packet in journal.packets), orders=0, cloudActivated=False)
    raw = source.canonical(dict(summary=summary, packets=journal.packets))
    cipher = seal_new(raw, recipient, rid)
    OUT.mkdir(exist_ok=False)
    (OUT / "extension.sealed").write_bytes(cipher)
    summary.update(ciphertextSha256=source.digest(cipher), plaintextSha256=source.digest(raw))
    (OUT / "receipt.json").write_bytes(source.canonical(summary) + b"\n")
    print("EXTENSION_SEALED_REQUESTS", len(journal.packets), flush=True)


def readback():
    rid = os.environ["GITHUB_RUN_ID"]
    key = os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    validated, prior = inputs()
    selection = plan(validated, prior)
    receipt = json.loads((OUT / "receipt.json").read_text())
    cipher = (OUT / "extension.sealed").read_bytes()
    raw = unseal_new(cipher, key, rid)
    original = json.loads(raw)
    need(receipt == dict(original["summary"], ciphertextSha256=source.digest(cipher),
         plaintextSha256=source.digest(raw)) and receipt["runId"] == rid, "EXTENSION_CUSTODY")
    packets = original["packets"]
    request = source.decode(packets[0]["reqType"], packets[0]["req"])
    account = request.ctidTraderAccountId
    need(source.original_account(account), "EXTENSION_ACCOUNT_BINDING")
    journal = source.ReadbackJournal(packets)
    covers, tape, margins = collect(journal, account, selection, rid)
    need(covers == receipt["coverage"] and journal.index == len(packets)
         and len(packets) == receipt["capturedRequests"], "EXTENSION_RAW_RECONCILIATION")
    base_packets, base_receipt = use.verified_original(Path("original-source-history"), key)
    contracts, _, _ = use.extract(base_packets, base_receipt)
    selected_names = {row["name"]: row["symbolId"] for row in selection}
    selected = [c for c in contracts if c["Symbol"] in selected_names]
    for contract in selected:
        new_margin = margins.get(selected_names[contract["Symbol"]])
        if new_margin is not None:
            contract["Margin"] = new_margin
    report = use.run_native(selected, [tape])
    report.update(receipt, nativeConsumedSymbols=len(tape["Markets"]), historicalTariffsCertified=False)
    (OUT / "extension-gross-public.json").write_bytes(source.canonical(report) + b"\n")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--readback"]:
            readback()
        else:
            need(not sys.argv[1:], "EXTENSION_MODE")
            capture()
    except Exception as error:
        print("OWNER_HISTORY_EXTENSION_FAILED", type(error).__name__, flush=True)
        raise SystemExit(1) from None
