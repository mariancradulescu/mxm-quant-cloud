"""Reconcile the frozen rollover acquisition without any broker connection."""
from collections import defaultdict
from itertools import groupby
import hashlib
import json
import os
from pathlib import Path

from . import owner_eur_rollover_continuity as original
from . import owner_eur_gap_evidence as gap
from . import owner_official_eur_source as wire
from .decode import need, decode_side, decode_bars
from .custody import unseal_new
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e

RUN="45549613144"
MATRIX_SHA="144a1cf549f0648d6b7152cdbe22fd40673e3f1fe5dc491ca668979b610b9e42"
src=wire.source
OUT=Path("eur-conditional-source")


def boundary(rows, at, before):
    eligible=[r for r in rows if (r[0]<=at if before else r[0]>at)]
    if not eligible:
        return None
    stamp=(max if before else min)(r[0] for r in eligible)
    prices=sorted({r[1] for r in eligible if r[0]==stamp})
    return dict(at=stamp,rawPrices=prices,conflict=len(prices)!=1)


def matrix_update(base, opens):
    width=300_000
    row=next(r for r in base["matrix"] if r["symbol"]=="USDJPY")
    old=row["timeframes"]["M5"]
    previous={t for a,b in old["observedIntervals"] for t in range(a,b,width)}
    need(len(previous)==old["closedBars"],"USDJPY_PREVIOUS_CLOCK_COUNT")
    merged=previous|opens
    added=len(merged)-len(previous)
    row["timeframes"]["M5"]=dict(wire.observed_bar_span("M5",merged),
        evidenceRuns=[base["integratedGapRun"],RUN])
    row["warmup"]["M5"]=len(merged)
    start,end=base["window"]
    counts=defaultdict(int)
    edges=[]
    for item in base["matrix"]:
        frames=item["timeframes"]
        if not any(frames.values()):continue
        counts["marketsWithBars"]+=1
        if all(frames.values()):counts["marketsWithSevenTimeframes"]+=1
        simultaneous=[(start,end)]
        prior={}
        missing=[]
        for period, frame in frames.items():
            intervals=frame["observedIntervals"] if frame else []
            w=src.PERIODS[period]*60_000
            prior[period]=sum(max(0,(min(start,b)-a)//w) for a,b in intervals)
            if not gap.intersect([(start,end)],intervals):missing.append(period)
            simultaneous=gap.intersect(simultaneous,gap.coalesced(intervals))
        if simultaneous:
            counts["marketsWithSevenTimeframesInWindow"]+=1
            for a,b in simultaneous:edges.extend(((a,1),(b,-1)))
        item["registeredWindow"]=dict(previousClosedBars=prior,missingTimeframes=missing,
            simultaneousObservedBarIntervals=simultaneous)
    duration=active=0
    last=start
    for stamp,group in groupby(sorted(edges),key=lambda x:x[0]):
        if active>=2:duration+=stamp-last
        active+=sum(delta for _,delta in group)
        last=stamp
    return dict(base,previousIntegratedMatrixSha256=MATRIX_SHA,rolloverSourceRun=RUN,
        USDJPY_M5=dict(recovered=len(opens),duplicates=len(opens&previous),added=added,
            historicalOHLCValueParityWithPriorArchiveCertified=False),
        overlapSummary=dict(counts),coverageWithClocks=counts["marketsWithBars"],
        simultaneousSevenTimeframePriceMinutesAtLeastTwoMarkets=duration//60_000,
        pricedPortfolioEligibilityCertified=False,economicEvaluations=0,orders=0,cloudActivated=False)


def main():
    folder=Path("eur-rollover-continuity")
    receipt=json.loads((folder/"receipt.json").read_bytes())
    sealed=(folder/"original.sealed").read_bytes()
    need(receipt["runId"]==RUN and src.digest(sealed)==receipt["ciphertextSha256"],"SOURCE_CIPHERTEXT")
    raw=unseal_new(sealed,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),RUN)
    need(src.digest(raw)==receipt["plaintextSha256"],"SOURCE_PLAINTEXT")
    data=json.loads(raw)
    ids=original.bound_roster()
    need(data["runId"]==RUN and data["ids"]==ids,"SOURCE_SCOPE")
    account=list(wire.decoded_packets(dict(requests=data["contracts"])))[0][1].ctidTraderAccountId
    need(src.original_account(account),"SOURCE_ACCOUNT")
    tj=src.ReadbackJournal(data["tickPackets"])
    need(original.plan(ids,account,tj.query)==data["tickResults"] and tj.index==len(tj.packets),"SOURCE_TICK_REPLAY")
    bj=src.ReadbackJournal(data["barPackets"])
    bars,requests=original.bars_plan(ids,account,bj.query)
    need(bars==data["barResults"] and requests==data["barRequests"] and bj.index==len(bj.packets),"SOURCE_BAR_REPLAY")
    collected=defaultdict(list)
    available=defaultdict(list)
    for packet in data["tickPackets"]:
        q=src.decode(packet["reqType"],packet["req"])
        if not packet["res"]:continue
        a=src.decode(packet["resType"],packet["res"])
        if type(a) is not m.ProtoOAGetTickDataRes or a.hasMore:continue
        key=next(( (w["symbol"],w["rollover"],"BID" if q.type==e.BID else "ASK")
            for w in data["tickResults"] if ids[w["symbol"]]==q.symbolId and
            w["fromInclusive"]<=q.fromTimestamp<=q.toTimestamp<=w["throughInclusive"]),None)
        need(key is not None,"SOURCE_TICK_WINDOW_BINDING")
        collected[key].extend(decode_side(a.tickData,q.fromTimestamp,q.toTimestamp))
        available[key].append(packet["availableAt"])
    windows=[]
    for w in data["tickResults"]:
        result=dict(symbol=w["symbol"],rollover=w["rollover"],sides={})
        for side,desc in w["sides"].items():
            key=(w["symbol"],w["rollover"],side)
            rows=collected[key]
            need(len(rows)==desc["count"],"SOURCE_TICK_COUNT")
            conflicts=sum(len({r[1] for r in g})>1 for _,g in groupby(sorted(rows),key=lambda x:x[0]))
            result["sides"][side]=dict(complete=desc["complete"],count=len(rows),
                sameTimestampConflictGroups=conflicts,lastBefore=boundary(rows,w["rollover"],True),
                firstAfter=boundary(rows,w["rollover"],False),
                acquiredAt=max(available[key],default=None))
        windows.append(result)
    by_open={}
    for packet in data["barPackets"]:
        q=src.decode(packet["reqType"],packet["req"])
        if not packet["res"]:continue
        a=src.decode(packet["resType"],packet["res"])
        if type(a) is not m.ProtoOAGetTrendbarsRes or a.hasMore:continue
        need(q.symbolId==ids["USDJPY"] and q.period==e.ProtoOATrendbarPeriod.Value("M5"),"SOURCE_BAR_SCOPE")
        description, rows=wire.history.inspect_bars(q,a,packet['availableAt'],closed_through=original.M5_END)
        need(description['status'] in ('CLOSED_ROWS_VERIFIED','NO_CLOSED_ROWS_WITHIN_WINDOW','EXPECTED_RESPONSE_WITH_EMPTY_SERIES'), 'SOURCE_BAR_INVALID')
        for row in rows:
            need(row[0] not in by_open or by_open[row[0]]==row,"SOURCE_BAR_CONFLICT")
            by_open[row[0]]=row
    need(len(by_open)==bars["USDJPY"]["M5"]["closedBars"],"SOURCE_BAR_COUNT")
    matrix_raw=Path("prior-eur-matrix/integrated-coverage-matrix.json").read_bytes()
    need(src.digest(matrix_raw)==MATRIX_SHA,"SOURCE_MATRIX_HASH")
    matrix=matrix_update(json.loads(matrix_raw),set(by_open))
    OUT.mkdir(exist_ok=False)
    (OUT/"rollover-values.json").write_bytes(src.canonical(dict(sourceRun=RUN,
        plaintextSha256=receipt["plaintextSha256"],priceScale=100000,windows=windows,
        settlementPriceConventionCertified=False,historicalTariffContinuityCertified=False,
        originalDecisionRewritten=False,brokerRequests=0,economicEvaluations=0,orders=0,cloudActivated=False)))
    (OUT/"integrated-coverage-matrix.json").write_bytes(src.canonical(matrix))
    (OUT/"receipt.json").write_bytes(src.canonical(dict(sourceRun=RUN,
        originalPlaintextSha256=receipt["plaintextSha256"],
        rolloverValuesSha256=src.digest((OUT/"rollover-values.json").read_bytes()),
        matrixSha256=src.digest((OUT/"integrated-coverage-matrix.json").read_bytes()),
        acquiredAt=max(a for stamps in available.values() for a in stamps),
        tickRows=sum(len(rows) for rows in collected.values()), USDJPY_M5=matrix["USDJPY_M5"],
        brokerRequests=0,economicEvaluations=0,orders=0,cloudActivated=False)))
    print("CONDITIONAL_SOURCE_READBACK",len(windows),len(by_open),matrix["USDJPY_M5"],flush=True)


if __name__=="__main__":main()
