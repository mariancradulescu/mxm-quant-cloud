"""LQR1 original QPI1 encrypted-source, genuinely NEW as-of last-side update feature.

SOURCE SUPPORT ONLY, NO old QPI1/BTI1 prediction, outcome or policy replay.
No future label, broker request, EUR profit or trading claim is made here.
"""
from __future__ import annotations
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

# This source-only verifier reconstructs ALL ORIGINAL 645 protected protobuf
# requests. It does not invoke the closed BTI1 timing/policy/financial scorer.
from .bti1_temporal_burstiness import authenticated_tape, pair, mid
from .decode import need

PROTOCOL = Path("research/LQR1_ASYNC_BIDASK_REFRESH_PRESOURCE_20261116.md")
OUTPUT = Path("lqr1-original-past-only-source-support.public.json")
START = date(2026, 9, 14)
TARGETS = ("USDCHF", "EURGBP")
CLOCKS = (9, 14)
BACK_MS = 600_000


def clock(day, hour):
    return int(datetime(day.year, day.month, day.day, hour,
                        tzinfo=timezone.utc).timestamp()*1000)


def last_price_change(side, earliest, latest):
    """Latest truly changed price, with its sign; never inspect after T."""
    previous = None
    last = None
    for row in side:
        at, price = row
        need(isinstance(at,int) and isinstance(price,int) and price>0,
             "LQR1_INVALID_ORIGINAL_TICK")
        if at>latest:
            break
        if previous is not None and earliest<=at<=latest and price!=previous:
            last = (at, (price>previous)-(price<previous))
        previous = price
    return last


def decide_predecision(before, t):
    """Exactly the frozen causal feature, with no future-result admission."""
    need(len(before)==2,"LQR1_SOURCE_SIDE_PAIR")
    bids,asks=before
    q0=pair(bids,asks,t-BACK_MS)
    q=pair(bids,asks,t)
    if q0 is None or q is None:
        return {"state":"SOURCE_UNKNOWN", "side":None, "own":None}
    b=last_price_change(bids,t-BACK_MS,t)
    a=last_price_change(asks,t-BACK_MS,t)
    own=(mid(q)>mid(q0))-(mid(q)<mid(q0))
    if b is None or a is None:
        return {"state":"FEATURE_UNKNOWN","side":None,"own":own}
    if b[0]==a[0]:
        return {"state":"ABSTAIN_SIMULTANEOUS","side":0,"own":own}
    x=b if b[0]>a[0] else a
    need(x[1] in (-1,1),"LQR1_LAST_CHANGE_ZERO")
    return {"state":"SIDE_SPECIFIC_SIGNAL","side":x[1],"own":own,
            "laterSide":"BID" if b[0]>a[0] else "ASK"}


def evaluate(tape, protocol_sha):
    need(PROTOCOL.is_file() and "PRESOURCE_FROZEN_UNSCORED" in PROTOCOL.read_text(),
         "LQR1_FROZEN_PROTOCOL_MISSING")
    result={}
    total_changes=0
    for symbol in TARGETS:
        observations=tape["targets"][symbol]
        need(len(observations)==80,"LQR1_ORIGINAL_CLOCK_POPULATION")
        states=Counter()
        weekly=[]
        varied=0
        for w in range(8):
            wc=Counter()
            for d in range(5):
                day=START+timedelta(weeks=w,days=d)
                for h in CLOCKS:
                    index=w*10+d*2+(1 if h==14 else 0)
                    o=observations[index]
                    t=clock(day,h)
                    need(o["week"]==w and o["decision"]==t,
                         "LQR1_ORIGINAL_CALENDAR_NOT_MATCHED")
                    if o["truncated"]:
                        x={"state":"SOURCE_UNKNOWN","side":None,"own":None}
                    else:
                        # The future 'after' array is NEVER passed to the signal.
                        x=decide_predecision(o["before"],t)
                    wc[x["state"]]+=1
                    if x["state"]=="SIDE_SPECIFIC_SIGNAL":
                        wc["long" if x["side"]>0 else "short"]+=1
                        if x["own"]!=x["side"]:
                            varied+=1
                            wc["differsFromOwnMomentum"]+=1
                    elif x["state"]=="ABSTAIN_SIMULTANEOUS":
                        wc["explicitCash"]+=1
            need(sum(wc[s] for s in ("SOURCE_UNKNOWN","FEATURE_UNKNOWN",
                    "ABSTAIN_SIMULTANEOUS","SIDE_SPECIFIC_SIGNAL"))==10,
                 "LQR1_WEEK_NOT_EXHAUSTIVE")
            weekly.append({"week":w+1,"count":dict(wc)})
            states.update({k:v for k,v in wc.items()})
        result[symbol]={
            "scheduled":80,
            "fullSourceObservationCount":len(observations),
            "counts":dict(states),
            "firstFourWeeks":{k:sum(x["count"].get(k,0) for x in weekly[:4]) for k in states},
            "lastFourWeeks":{k:sum(x["count"].get(k,0) for x in weekly[4:]) for k in states},
            "weekly":weekly,
            "validSideOrderDiffersFromOwnMomentum":varied
        }
        total_changes+=varied
    return {
        "schema":"MXM_LQR1_AUTHENTIC_SOURCE_ONLY_NEW_INFORMATION_SUPPORT_V1",
        "sourceRunId":43458050084,
        "sourceCipherSha256":
            "853ddd0951f23f6c59efd45f775a8092a4f8a00e2d3766fef944efbd121b9236",
        "sourcePlainSha256":
            "d554e47205e53473fbe49f80fb5b1fd0d0a2c094efa17d37825e62d8de5c2c3b",
        "sourceOnlyRawOriginalPacketsIndependentlyVerified":645,
        "frozenProtocolSha256":protocol_sha,
        "alreadyGloballyExposedHistory":True,
        "results":result,
        "totalScheduled":160,
        "newFeatureDecisionsDifferFromOwnMomentum":total_changes,
        "economicStudyGate":"SOURCE_VARIATION_ONLY" if total_changes else
            "SOURCE_NO_DECISION_VARIATION",
        "futureOutcomesScored":False,
        "brokerReadOnlyRequestsNew":0,
        "financialEurNet":None,
        "singleEur300NativeLedgerNet":None,
        "continuousFloatingDDAttested":False,
        "independentConfirmation":False,
        "tradingOrders":0,
        "cloudActivation":False
    }


def main():
    need(PROTOCOL.is_file(),"LQR1_PROTOCOL_NOT_FOUND")
    tape,_=authenticated_tape()
    receipt=evaluate(tape,sha256(PROTOCOL.read_bytes()).hexdigest())
    OUTPUT.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("LQR1_AUTHENTIC_SOURCE_SUPPORT_ONLY_NO_PRICE_OR_EUR_RESULT",flush=True)


if __name__=="__main__":
    main()
