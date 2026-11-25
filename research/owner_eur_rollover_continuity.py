"""Targeted rollover evidence, separate from the frozen EUR economic original.

Read-only; raw protocol messages stay in existing sealed custody. Historical
ticks are retrieved now, not asserted to be known by the original policy.
Neither a nearby tick nor present-day contract terms certify historical swap.
"""
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from . import owner_official_eur_source as wire
from . import owner_eur_gap_evidence as gap
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need, decode_side
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .owner_readonly_auth import authenticate

src = wire.source
OUT = Path("eur-rollover-continuity")
SYMBOLS = ("EURUSD", "US500")
DAYS = (4, 10, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15)
RADIUS = 2 * 60 * 60_000
M5_START, M5_END = 1794873600000, 1795478400000
MAX_TICK_PAGES = 380


def clock(day):
    return int(datetime(2026, 11, day, 22, tzinfo=timezone.utc).timestamp()*1000)


def tick_window(request, account, sid, side, lo, hi, budget):
    pending = deque([(lo, hi)])
    accepted, leaves = [], []
    while pending:
        a, b = pending.popleft()
        if budget[0] <= 0:
            leaves.append([a,b,"PENDING_BUDGET",None,0])
            continue
        q = m.ProtoOAGetTickDataReq(ctidTraderAccountId=account, symbolId=sid,
                                    type=side, fromTimestamp=a, toTimestamp=b)
        res, at, status = request(q)
        if status != src.UNCOLLECTED:
            budget[0] -= 1
        if res is None:
            leaves.append([a,b,status,at,0])
            continue
        if (type(res) is not m.ProtoOAGetTickDataRes or not res.IsInitialized()
                or res.ctidTraderAccountId != account or not res.HasField("hasMore")):
            reason = ("PROVIDER_NO_QUOTES" if isinstance(res,m.ProtoOAErrorRes)
                      and res.errorCode=="NO_QUOTES" else "UNVERIFIED_RESPONSE")
            leaves.append([a,b,reason,at,0])
            continue
        if res.hasMore:
            if a == b:
                leaves.append([a,b,"TRUNCATED_SINGLE_MILLISECOND",at,0])
            else:
                mid = (a+b)//2
                pending.appendleft((mid+1,b))
                pending.appendleft((a,mid))
            continue
        rows = decode_side(res.tickData,a,b)
        accepted.extend(rows)
        leaves.append([a,b,"VERIFIED_COMPLETE_PAGE",at,len(rows)])
    accepted.sort(key=lambda row:row[0])
    return accepted, leaves


def describe(rows, leaves, at):
    before = [row for row in rows if row[0] <= at]
    after = [row for row in rows if row[0] > at]
    complete = bool(leaves) and all(p[2]=="VERIFIED_COMPLETE_PAGE" for p in leaves)
    return dict(complete=complete, count=len(rows),
                lastAtOrBefore=before[-1][0] if before else None,
                firstAfter=after[0][0] if after else None,
                fresh30s=bool(complete and before and at-before[-1][0]<=30_000),
                availableAt=max((p[3] for p in leaves if p[3] is not None),default=None),
                leaves=leaves)


def plan(ids, account, request):
    budget=[MAX_TICK_PAGES]
    tick_results=[]
    for day in DAYS:
        at=clock(day)
        for symbol in SYMBOLS:
            result=dict(symbol=symbol,rollover=at,fromInclusive=at-RADIUS,
                        throughInclusive=at+RADIUS,sides={})
            for side, name in ((e.BID,"BID"),(e.ASK,"ASK")):
                rows, leaves=tick_window(request,account,ids[symbol],side,
                                         at-RADIUS,at+RADIUS,budget)
                result["sides"][name]=describe(rows,leaves,at)
            tick_results.append(result)
    return tick_results


def bound_roster():
    original=wire.public_original()
    ids={row["name"]:row["symbolId"] for row in original["contractRoster"]
         if row["name"] in (*SYMBOLS,"USDJPY")}
    need(set(ids)==set((*SYMBOLS,"USDJPY")),"ROLLOVER_ORIGINAL_ROSTER")
    return ids


def bars_plan(ids,account,request):
    return gap.collect_cells([dict(symbol="USDJPY",id=ids["USDJPY"],periods=["M5"],
                            fromUtc=M5_START,throughExclusive=M5_END)],account,request)


def capture():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_REF")=="refs/heads/main"
         and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","ROLLOVER_CONTEXT")
    run=os.environ["GITHUB_RUN_ID"]
    public=checked_public(Path("eur-rollover-recipient"),run)
    ids=bound_roster()
    t=wire.OfficialEvidenceTransport()
    try:
        account=authenticate(t)
        t.bind(account)
        trader=t.read(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes,"trader")
        assets=t.read(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes,"assets")
        roster=t.read(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),
                      m.ProtoOASymbolsListRes,"roster")
        need(trader is not None and assets is not None and roster is not None,"ROLLOVER_ACCOUNT_ROSTER")
        codes={x.assetId:x.name for x in assets.asset}
        need("pepperstone" in trader.trader.brokerName.lower() and
             codes.get(trader.trader.depositAssetId)=="EUR","ROLLOVER_BROKER_CURRENCY")
        live={x.symbolName:x.symbolId for x in roster.symbol}
        need(all(live.get(n)==sid for n,sid in ids.items()),"ROLLOVER_SYMBOL_IDENTITY")
        details=t.read(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=sorted(ids.values())),
                       m.ProtoOASymbolByIdRes,"current-contracts-not-historical")
        need(details is not None and {x.symbolId for x in details.symbol}==set(ids.values()),
             "ROLLOVER_CURRENT_TERMS")
        # Fix the explicit common-window M5 gap first, independently of tick budget.
        bars=src.Journal(t,account)
        bar_results,bar_requests=bars_plan(ids,account,bars.query)
        journal=src.Journal(t,account)
        results=plan(ids,account,journal.query)
    finally:
        t.close()
    OUT.mkdir(exist_ok=False)
    raw=src.canonical(dict(runId=run,ids=ids,contracts=t.journal,barPackets=bars.packets,
                  barResults=bar_results,barRequests=bar_requests,tickPackets=journal.packets,
                  tickResults=results))
    sealed=seal_new(raw,public,run)
    (OUT/"original.sealed").write_bytes(sealed)
    (OUT/"receipt.json").write_bytes(src.canonical(dict(runId=run,plaintextSha256=src.digest(raw),
                  ciphertextSha256=src.digest(sealed),tickRequests=len(journal.packets),
                  barRequests=bar_requests,orders=0,cloudActivated=False)))
    print("ROLLOVER_RAW_CUSTODY_PRESERVED",len(journal.packets),bar_requests,flush=True)


def readback():
    run=os.environ["GITHUB_RUN_ID"]
    receipt=json.loads((OUT/"receipt.json").read_bytes())
    sealed=(OUT/"original.sealed").read_bytes()
    need(receipt["runId"]==run and src.digest(sealed)==receipt["ciphertextSha256"],"ROLLOVER_CIPHERTEXT")
    raw=unseal_new(sealed,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),run)
    need(src.digest(raw)==receipt["plaintextSha256"],"ROLLOVER_PLAINTEXT")
    data=json.loads(raw)
    ids=bound_roster()
    need(data["runId"]==run and data["ids"]==ids,"ROLLOVER_CUSTODY_SCOPE")
    contracts=list(wire.decoded_packets(dict(requests=data["contracts"])))
    account=contracts[0][1].ctidTraderAccountId
    need(src.original_account(account),"ROLLOVER_ACCOUNT_BIND")
    bj=src.ReadbackJournal(data["barPackets"])
    bar_results,bar_requests=bars_plan(ids,account,bj.query)
    need(bj.index==len(bj.packets) and bar_results==data["barResults"]
         and bar_requests==data["barRequests"],"ROLLOVER_BAR_READBACK")
    tj=src.ReadbackJournal(data["tickPackets"])
    results=plan(ids,account,tj.query)
    need(tj.index==len(tj.packets) and results==data["tickResults"],"ROLLOVER_TICK_READBACK")
    report=dict(runId=run,sourceOriginalEconomicRun="45540439094",tickRequests=len(tj.packets),
                sourceReceipt=receipt,rolloverWindows=results,USDJPY_M5=bar_results,
                currentTermsOnly=True,historicalTariffContinuityCertified=False,
                settlementPriceConventionCertified=False,exactSwapReconciled=False,
                economicEvaluations=0,orders=0,cloudActivated=False)
    (OUT/"verified-evidence.json").write_bytes(src.canonical(report))
    print("ROLLOVER_VERIFIED_WINDOWS",len(results),flush=True)


if __name__=="__main__":
    if sys.argv[1:]==["--readback"]:
        readback()
    else:
        need(not sys.argv[1:],"ROLLOVER_MODE")
        capture()
