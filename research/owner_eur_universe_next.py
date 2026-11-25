"""Extend verified official closed-bar custody through a new bounded tranche."""
import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

from . import owner_source_history_expand as extension
from . import owner_source_history_use as history
from . import source_history_universe as source
from .ctrader_proto import OpenApiMessages_pb2 as messages
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

CENSUS_SHA = "0fece43b54d788666fa139141adbf3f9cd07d708b3665adc704cafd39cdf0882"
PRIOR_SHA = "9096b0bdd1617abb11a2900231e3218b18d2699f503284629bb5a50dd2531b1f"
OUT = Path("owner-eur-universe-source")
MAX_PROBES = 32
MAX_SYMBOLS = 8
MARGIN_CAP = Decimal(210)


def verified(path, digest):
    raw = path.read_bytes()
    need(source.digest(raw) == digest, "UNIVERSE_MANIFEST_SHA256")
    return json.loads(raw)


def plan():
    original = verified(Path("original-source-history/receipt.json"), history.RECEIPT_SHA)
    census = verified(Path("eer1-economic/source-census.json"), CENSUS_SHA)
    prior = verified(Path("previous-extension/extension-gross-public.json"), PRIOR_SHA)
    known = {n for n, counts in census["historicalCoverage"].items() if any(counts.values())}
    already_probed = known | set(prior["coverage"]) | set(census["selected"])
    enabled = {r["symbol"] for r in census["universe"] if r["currentEnabled"]}
    roster = {r["symbolId"]: r for r in original["contractRoster"]
              if r["name"] in enabled and r["name"] not in already_probed and
              r["contractStatus"] == source.VERIFIED and r["tradingMode"] == 0 and (r.get("minVolume") or 0) > 0}
    ids = source.selected_ids(roster, limit=MAX_PROBES)
    return known, len(roster), [roster[sid] for sid in ids]


def reported_margin(journal, account, symbol):
    if symbol["marginStatus"] == source.VERIFIED:
        fraction = Decimal(1).scaleb(-symbol["marginMoneyDigits"])
        return dict(buyEur=str(Decimal(symbol["buyMarginRaw"]) * fraction),
                    sellEur=str(Decimal(symbol["sellMarginRaw"]) * fraction),
                    observedAt=symbol["marginAvailableAt"], source="VERIFIED_ARCHIVE")
    units = symbol["minVolume"]
    reply, at, status = journal.query(messages.ProtoOAExpectedMarginReq(
        ctidTraderAccountId=account, symbolId=symbol["symbolId"], volume=[units]))
    if not source.matching(reply, messages.ProtoOAExpectedMarginRes, account):
        return dict(source="REQUESTED_WITHOUT_VERIFIED_MARGIN" if at else status)
    if not reply.HasField("moneyDigits") or not 0 <= reply.moneyDigits <= 12 or (
            len(reply.margin) != 1 or reply.margin[0].volume != units):
        return dict(source="RESPONSE_WITHOUT_SINGLE_MATCHED_VOLUME")
    scale = Decimal(1).scaleb(-reply.moneyDigits)
    return dict(buyEur=str(reply.margin[0].buyMargin * scale), sellEur=str(reply.margin[0].sellMargin * scale),
                observedAt=at, source="VERIFIED_BROKER_RESPONSE")


def collect(journal, account, plan_data):
    known, pool_size, symbols = plan_data
    probes = {s["name"]: reported_margin(journal, account, s) for s in symbols}
    eligible = []
    for s in symbols:
        mark = probes[s["name"]]
        values = [Decimal(mark[key]) for key in ("buyEur", "sellEur") if key in mark and Decimal(mark[key]) > 0]
        if values and min(values) < MARGIN_CAP:
            eligible.append((min(values), s["symbolId"], s))
    count, coverage = len(eligible), {}
    for _, sid, s in sorted(eligible)[:MAX_SYMBOLS]:
        coverage[s["name"]] = {}
        for period in source.PERIODS:
            _, diagnostic = extension.timeframe(journal, account, sid, period)
            coverage[s["name"]][period] = diagnostic["closedRows"]
    captured = sorted(n for n, periods in coverage.items() if any(periods.values()))
    return dict(knownHistoricalBefore=len(known), newClosedBarSymbols=captured,
                knownHistoricalAfter=len(known | set(captured)), eligibleContractPool=pool_size,
                marginProbes=probes, compatibleMinimumMargins=count, coverage=coverage,
                eligibleContractPoolStillPending=pool_size-len(captured),
                start=extension.START, endExclusive=extension.END,
                economicRuns=0, orders=0, cloudActivated=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("plan", "capture", "verify"))
    stage = parser.parse_args().stage
    selection = plan()
    if stage == "plan":
        print(json.dumps(dict(known=len(selection[0]), eligibleContracts=selection[1],
                              probes=[x["name"] for x in selection[2]])))
        return
    rid = os.environ["GITHUB_RUN_ID"]
    if stage == "capture":
        need(os.environ["GITHUB_EVENT_NAME"] == "push" and os.environ["GITHUB_REF"] == "refs/heads/main" and
             os.environ["GITHUB_RUN_ATTEMPT"] == "1", "UNIVERSE_READ_ONLY_ACTIVATION")
        recipient = checked_public(Path("new-recipient-output"), rid)
        transport = P05ReadOnlyTransport(response_timeout=20)
        try:
            account = authenticate(transport)
            journal = source.Journal(transport, account)
            summary = collect(journal, account, selection)
        finally:
            transport.close()
        summary.update(runId=rid, brokerRequests=len(journal.packets))
        OUT.mkdir(exist_ok=False)
        raw = source.canonical(dict(summary=summary, packets=journal.packets))
        cipher = seal_new(raw, recipient, rid)
        (OUT / "packets.sealed").write_bytes(cipher)
        (OUT / "receipt.json").write_bytes(source.canonical(dict(summary,
            ciphertextSha256=source.digest(cipher), plaintextSha256=source.digest(raw))))
        print("OFFICIAL_UNIVERSE_CLOSED_BARS", len(summary["newClosedBarSymbols"]), flush=True)
        return
    receipt = json.loads((OUT / "receipt.json").read_bytes())
    cipher = (OUT / "packets.sealed").read_bytes()
    need(receipt["runId"] == rid and receipt["ciphertextSha256"] == source.digest(cipher), "UNIVERSE_CIPHER")
    raw = unseal_new(cipher, os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(), rid)
    need(receipt["plaintextSha256"] == source.digest(raw), "UNIVERSE_PLAINTEXT")
    data = json.loads(raw)
    packets = data["packets"]
    need(bool(packets), "UNIVERSE_NO_REQUESTS")
    account = source.decode(packets[0]["reqType"], packets[0]["req"]).ctidTraderAccountId
    need(source.original_account(account), "UNIVERSE_ORIGINAL_ACCOUNT")
    journal = source.ReadbackJournal(packets)
    replay = collect(journal, account, selection)
    replay.update(runId=rid, brokerRequests=len(packets))
    need(replay == data["summary"] and journal.index == len(packets) and
         receipt == dict(replay, ciphertextSha256=source.digest(cipher), plaintextSha256=source.digest(raw)),
         "UNIVERSE_PACKET_RECONCILIATION")
    receipt.update(packetsReconciled=journal.index, readbackBrokerRequests=0)
    Path("universe-verified.json").write_bytes(source.canonical(receipt))
    print("UNIVERSE_VERIFIED", receipt["newClosedBarSymbols"], flush=True)


if __name__ == "__main__":
    main()
