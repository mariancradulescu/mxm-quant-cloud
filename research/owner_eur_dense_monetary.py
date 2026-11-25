"""OWNER registered dense historical quotes, protected per market/day and independently read back."""
import argparse
from bisect import bisect_right
from collections import Counter
import json
import os
from pathlib import Path

from . import owner_eur_universe_next as prior
from . import owner_eur_rollover_continuity as rollover
from . import owner_history_continuation as continuation
from . import owner_source_history_use as history
from . import source_history_universe as source
from .ctrader_proto import OpenApiModelMessages_pb2 as model
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

PROTOCOL = Path("research/official_eur_dense_monetary_2.json")
OUT = Path("dense-monetary-protected")
HOUR = 3600000


def registered(symbol, window, protocol=PROTOCOL):
    raw = protocol.read_bytes()
    plan = json.loads(raw)
    need(plan["study"] in ("OFFICIAL_EUR_DENSE_MONETARY_2", "OFFICIAL_EUR_DENSE_MONETARY_3") and
         plan["scope"] == "READ_ONLY_HISTORICAL_QUOTES_NOT_HISTORICAL_TARIFF_CERTIFICATION" and
         plan["symbols"] == list(continuation.TEMPORAL_SYMBOLS[:1]) + ["US500", "XAUUSD", "SpotBrent"] and
         plan["partitionHours"] == 24 and plan["requestBlockHours"] == 1 and
         1 <= plan["perSidePageBudget"] <= 512 and plan["markFreshnessMs"] == 30000 and
         plan["markIntervalMs"] == 300000 and plan["markOffsetMs"] == 15000,
         "DENSE_MONETARY_REGISTERED_SCOPE")
    need(symbol in plan["symbols"], "DENSE_MONETARY_SYMBOL")
    windows = {w["id"]: w for w in plan["windows"]}
    need(len(windows) == len(plan["windows"]) and window in windows,
         "DENSE_MONETARY_WINDOW")
    item = windows[window]
    need(0 <= item["weekIndex"] < continuation.WEEKS and
         0 <= item["weekdayOffset"] < 5, "DENSE_MONETARY_WINDOW_CLOCK")
    start = (continuation.START + item["weekIndex"] * continuation.WEEK +
             item["weekdayOffset"] * continuation.DAY)
    receipt = prior.verified(Path("original-source-history/receipt.json"), history.RECEIPT_SHA)
    roster = [r for r in receipt["contractRoster"] if r["name"] == symbol and
              r["contractStatus"] == source.VERIFIED]
    need(len(roster) == 1, "DENSE_MONETARY_ORIGINAL_ROSTER")
    return plan, source.digest(raw), roster[0]["symbolId"], start


def latest(rows, clocks, at, freshness):
    i = bisect_right(clocks, at) - 1
    if i < 0 or at - clocks[i] > freshness:
        return None
    ts, price = rows[i][:2]
    while i > 0 and rows[i-1][0] == ts:
        i -= 1
        if rows[i][1] != price:
            return None
    return price


def collect(journal, account, plan, symbol, sid, window, start, digest):
    # Partition and report independently; no extrapolation across missing pages.
    budget = {model.BID: [plan["perSidePageBudget"]], model.ASK: [plan["perSidePageBudget"]]}
    hours = []
    for hour in range(plan["partitionHours"]):
        lo = start + hour * HOUR
        hi = lo + HOUR - 1
        decoded = {}
        evidence = {}
        for side in (model.BID, model.ASK):
            rows, leaves = rollover.tick_window(journal.query, account, sid, side, lo, hi, budget[side])
            name = model.ProtoOAQuoteType.Name(side)
            cursor = lo
            fully = True
            for leaf in sorted(leaves):
                a, b, status = leaf[:3]
                if a != cursor or b < a or status != "VERIFIED_COMPLETE_PAGE":
                    fully = False
                cursor = b + 1
            fully = fully and cursor == hi + 1
            decoded[name] = rows
            evidence[name] = dict(rows=len(rows), completeResponseCoverage=fully,
                                  pageStatuses=dict(Counter(p[2] for p in leaves)),
                                  leaves=leaves, remainingPageBudget=budget[side][0])
        mark_count = 0
        clock_count = 0
        if all(side["completeResponseCoverage"] for side in evidence.values()):
            bid, ask = decoded["BID"], decoded["ASK"]
            bid_times, ask_times = [r[0] for r in bid], [r[0] for r in ask]
            for at in range(lo + plan["markOffsetMs"], hi + 1, plan["markIntervalMs"]):
                clock_count += 1
                b = latest(bid, bid_times, at, plan["markFreshnessMs"])
                a = latest(ask, ask_times, at, plan["markFreshnessMs"])
                if b is not None and a is not None and 0 < b <= a:
                    mark_count += 1
        hours.append(dict(fromInclusive=lo, throughInclusive=hi, sides=evidence,
                          verifiedTwoSidedMarkCount=mark_count, evaluatedClocks=clock_count))
        print("DENSE_MONETARY", symbol, window, hour+1, plan["partitionHours"], mark_count, flush=True)
    return dict(study=plan["study"], protocolSha256=digest, symbol=symbol, symbolId=sid, window=window,
                fromInclusive=start, throughExclusive=start+plan["partitionHours"]*HOUR,
                verifiedTwoSidedMarks=sum(h["verifiedTwoSidedMarkCount"] for h in hours),
                completeResponseHours=sum(all(x["completeResponseCoverage"] for x in h["sides"].values())
                                          for h in hours), hours=hours,
                executionContinuityCertified=False, historicalTariffContinuityCertified=False,
                historicalMarginCertified=False, economicEvaluations=0, orders=0, cloudActivated=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("plan", "capture", "verify"))
    parser.add_argument("symbol")
    parser.add_argument("window")
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = parser.parse_args()
    plan, digest, sid, start = registered(args.symbol, args.window, args.protocol)
    if args.stage == "plan":
        print(plan["study"], args.symbol, args.window, start, digest)
        return
    rid = os.environ["GITHUB_RUN_ID"]
    def evaluate(journal, account):
        return collect(journal, account, plan, args.symbol, sid, args.window, start, digest)
    if args.stage == "capture":
        need(os.environ["GITHUB_REF"] == "refs/heads/main" and
             os.environ["GITHUB_EVENT_NAME"] == "push", "DENSE_MONETARY_CAPTURE_SCOPE")
        transport = P05ReadOnlyTransport(response_timeout=20)
        try:
            account = authenticate(transport)
            journal = source.Journal(transport, account)
            report = evaluate(journal, account)
        finally:
            transport.close()
        report.update(runId=rid, requests=len(journal.packets))
        raw = source.canonical(dict(report=report, packets=journal.packets))
        cipher = seal_new(raw, checked_public(Path("new-recipient-output"), rid), rid)
        OUT.mkdir(exist_ok=False)
        (OUT/"packets.sealed").write_bytes(cipher)
        (OUT/"receipt.json").write_bytes(source.canonical(dict(report,
            ciphertextSha256=source.digest(cipher), plaintextSha256=source.digest(raw))))
        return
    receipt = json.loads((OUT/"receipt.json").read_bytes())
    cipher = (OUT/"packets.sealed").read_bytes()
    need(receipt["runId"] == rid and receipt["ciphertextSha256"] == source.digest(cipher),
         "DENSE_MONETARY_CIPHER")
    raw = unseal_new(cipher, os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(), rid)
    need(source.digest(raw) == receipt["plaintextSha256"], "DENSE_MONETARY_PLAINTEXT")
    recovered = json.loads(raw)
    packets = recovered["packets"]
    need(bool(packets), "DENSE_MONETARY_NO_ATTEMPTED_REQUESTS")
    account = source.decode(packets[0]["reqType"], packets[0]["req"]).ctidTraderAccountId
    need(source.original_account(account), "DENSE_MONETARY_ORIGINAL_ACCOUNT")
    journal = source.ReadbackJournal(packets)
    report = evaluate(journal, account)
    report.update(runId=rid, requests=len(packets))
    need(journal.index == len(packets) and report == recovered["report"] and
         receipt == dict(report, ciphertextSha256=source.digest(cipher), plaintextSha256=source.digest(raw)),
         "DENSE_MONETARY_READBACK_PARITY")
    receipt.update(packetsReconciled=journal.index, readbackBrokerRequests=0)
    Path("dense-monetary-verified.json").write_bytes(source.canonical(receipt))


if __name__ == "__main__":
    main()
