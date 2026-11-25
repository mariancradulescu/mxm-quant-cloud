"""Read-only temporal coverage and additional-universe tranche on the original account."""
import argparse
from collections import Counter, deque
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path

from . import owner_eur_universe_next as prior
from . import owner_source_history_expand as extension
from . import owner_source_history_use as history
from . import source_history_universe as source
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as model
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_live_source import decode_side
from .p05_safe_transport import P05ReadOnlyTransport

WEEK = 604800000
DAY = 86400000
START = int(datetime(2023, 5, 29, tzinfo=timezone.utc).timestamp()) * 1000
WEEKS = 53
SAMPLES = (0, 13, 26, 39, 52)
TEMPORAL_SYMBOLS = ("EURUSD", "US500", "XAUUSD", "SpotBrent")
PREVIOUS_SHA = "cba7e1ad451c74a661e4e07f34e84ca914fbda95ed14e46365b4389136a3c5aa"
OUT = Path("owner-history-continuation")


def selection():
    original = prior.verified(Path("original-source-history/receipt.json"), history.RECEIPT_SHA)
    census = prior.verified(Path("eer1-economic/source-census.json"), prior.CENSUS_SHA)
    previous = prior.verified(Path("verified-tranche/universe-verified.json"), PREVIOUS_SHA)
    known = {n for n, frames in census["historicalCoverage"].items() if any(frames.values())}
    known.update(previous["newClosedBarSymbols"])
    roster = {r["name"]: r for r in original["contractRoster"] if r["contractStatus"] == source.VERIFIED}
    need(len(known) == previous["knownHistoricalAfter"], "HISTORY_CONTINUATION_REGISTRY")
    groups = {}
    for name, quote in sorted(previous["marginProbes"].items()):
        if name in known or name not in roster or "buyEur" not in quote or "sellEur" not in quote:
            continue
        sides = [Decimal(quote[k]) for k in ("buyEur", "sellEur") if Decimal(quote[k]) > 0]
        if sides and min(sides) < prior.MARGIN_CAP:
            row = roster[name]
            groups.setdefault(str(row["category"]), []).append(row)
    candidates = [row for group in sorted(groups) for row in groups[group][:1]]
    return known, [roster[k] for k in TEMPORAL_SYMBOLS], candidates[:8]


def historical_week(journal, account, sid, start, period):
    width = source.PERIODS[period] * 60000
    pending = deque([(start, start + WEEK - 1)])
    closes, counts = [], Counter()
    while pending:
        lo, hi = pending.popleft()
        q = m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=sid,
            period=model.ProtoOATrendbarPeriod.Value(period), fromTimestamp=lo, toTimestamp=hi)
        r, available, status = journal.query(q)
        if r is None:
            counts[status] += 1
            continue
        if extension.page_pair(q, r) and r.HasField("hasMore") and r.hasMore and hi-lo >= 2*width:
            pending.extendleft(reversed(source.split_window(lo, hi)))
            counts["PAGINATION_SPLIT"] += 1
            continue
        mark, bars = history.inspect_bars(q, r, available, closed_through=start+WEEK)
        counts[mark["status"]] += 1
        closes.extend(bar[0]+width for bar in bars)
    need(len(closes) == len(set(closes)), "HISTORY_CONTINUATION_DUPLICATE_CLOSE")
    return dict(rows=len(closes), firstClose=min(closes, default=None), lastClose=max(closes, default=None),
                statuses=dict(counts))


def tick_samples(journal, account, sid, at):
    result = {}
    for side in ("BID", "ASK"):
        q = m.ProtoOAGetTickDataReq(ctidTraderAccountId=account, symbolId=sid,
            type=model.ProtoOAQuoteType.Value(side), fromTimestamp=at, toTimestamp=at+299999)
        r, _, status = journal.query(q)
        if source.matching(r, m.ProtoOAGetTickDataRes, account) and r.HasField("hasMore") and not r.hasMore:
            decoded = decode_side(r.tickData, at, at+299999)
            result[side] = {"status": "VERIFIED_COMPLETE_PAGE", "ticks": len(decoded)}
        else:
            result[side] = {"status": "RESPONSE_WITHOUT_COMPLETE_TICKS" if r is not None else status}
    return result


def collect(journal, account, plan):
    known, temporal, candidates = plan
    expansion = {}
    # Reuse the previously attested margin. The next bar sample does not depend on an economic scoring gate.
    for row in candidates:
        expansion[row["name"]] = {}
        for period in source.PERIODS:
            _, receipt = extension.timeframe(journal, account, row["symbolId"], period)
            expansion[row["name"]][period] = receipt["closedRows"]
    dates = {}
    for row in temporal:
        sid = row["symbolId"]
        weeks = [historical_week(journal, account, sid, START+i*WEEK, "H1") for i in range(WEEKS)]
        samples = {str(i): dict(m5=historical_week(journal, account, sid, START+i*WEEK, "M5"),
            executions=tick_samples(journal, account, sid, START+i*WEEK+DAY+14*3600000))
            for i in SAMPLES}
        dates[row["name"]] = dict(h1=weeks, representedWeeks=sum(w["rows"]>0 for w in weeks), samples=samples)
    new = sorted(name for name, periods in expansion.items() if any(periods.values()))
    return dict(temporalStart=START, temporalEndExclusive=START+WEEKS*WEEK, temporal=dates,
                independentExposureStatus="UNATTESTED_PENDING_GLOBAL_AUDIT", executionContinuityCertified=False,
                coverage=expansion, newClosedBarSymbols=new, historyBefore=len(known),
                historyAfter=len(known | set(new)), orders=0, economicEvaluations=0, cloudActivated=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("plan", "capture", "verify"))
    stage = parser.parse_args().stage
    plan = selection()
    if stage == "plan":
        print(dict(known=len(plan[0]), temporal=[r["name"] for r in plan[1]], additional=[r["name"] for r in plan[2]]))
        return
    rid = os.environ["GITHUB_RUN_ID"]
    if stage == "capture":
        need(os.environ["GITHUB_REF"] == "refs/heads/main" and os.environ["GITHUB_EVENT_NAME"] == "push",
             "HISTORY_CONTINUATION_SCOPE")
        transport = P05ReadOnlyTransport(response_timeout=20)
        try:
            account = authenticate(transport)
            journal = source.Journal(transport, account)
            report = collect(journal, account, plan)
        finally:
            transport.close()
        report.update(runId=rid, requests=len(journal.packets))
        raw = source.canonical(dict(report=report, packets=journal.packets))
        cipher = seal_new(raw, checked_public(Path("new-recipient-output"), rid), rid)
        OUT.mkdir(exist_ok=False)
        (OUT/"packets.sealed").write_bytes(cipher)
        (OUT/"receipt.json").write_bytes(source.canonical(dict(report, ciphertextSha256=source.digest(cipher),
                                                        plaintextSha256=source.digest(raw))))
        print("HISTORY_CONTINUATION", report["historyAfter"], report["requests"], flush=True)
        return
    receipt = json.loads((OUT/"receipt.json").read_bytes())
    cipher = (OUT/"packets.sealed").read_bytes()
    need(receipt["runId"] == rid and receipt["ciphertextSha256"] == source.digest(cipher), "HISTORY_CONTINUATION_CIPHER")
    raw = unseal_new(cipher, os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(), rid)
    need(source.digest(raw) == receipt["plaintextSha256"], "HISTORY_CONTINUATION_PLAINTEXT")
    recovered = json.loads(raw)
    packets = recovered["packets"]
    need(bool(packets), "HISTORY_CONTINUATION_NO_REQUEST")
    account = source.decode(packets[0]["reqType"], packets[0]["req"]).ctidTraderAccountId
    need(source.original_account(account), "HISTORY_CONTINUATION_ACCOUNT")
    journal = source.ReadbackJournal(packets)
    result = collect(journal, account, plan)
    result.update(runId=rid, requests=len(packets))
    need(journal.index == len(packets) and result == recovered["report"] and
         receipt == dict(result, ciphertextSha256=source.digest(cipher), plaintextSha256=source.digest(raw)),
         "HISTORY_CONTINUATION_CUSTODY_PARITY")
    receipt.update(packetsReconciled=journal.index, readbackBrokerRequests=0)
    Path("history-continuation-verified.json").write_bytes(source.canonical(receipt))


if __name__ == "__main__":
    main()
