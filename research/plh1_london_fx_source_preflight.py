"""PLH1: portfolio-first causal London G10 interbank session source/support only.

Strictly no PLH1 post-entry returns, prices past endpoint in a feature,
closed economic models, currency trades, broker requests, or Cloud activation.
"""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo
from pathlib import Path
from math import isfinite
import json
import os

from .custody import unseal_new
from .decode import need
from .hxc1_historical_readback import validate

HXC_RUN = "43817213663"
PROTO=Path("research/PLH1_PORTFOLIO_LONDON_FX_HANDOFF_PRESOURCE.md")
SEALED=Path("plh1-source/source.envelope.json")
HXC_RECEIPT=Path("plh1-source/receipt.public.json")
COST=Path("docs/OWNER_EXECUTED_MULTI_ASSET_COST_CAPITAL_SCREEN_20261108.json")
OUTPUT=Path("plh1-original-exposed-fx-handoff-support-only.public.json")
LONDON=ZoneInfo("Europe/London")
START=date(2026,8,17)
SYMBOLS=("EURUSD","GBPUSD","AUDUSD","USDJPY")
USD_ORIENTATION={"EURUSD":-1,"GBPUSD":-1,"AUDUSD":-1,"USDJPY":1}
CLOCKS=((8,15),(8,45),(9,15))
EXPECTED_COST={"EURUSD":(33.33,0.06),"GBPUSD":(39.91,0.06),
               "AUDUSD":(30.97,0.06),"USDJPY":(29.64,0.06)}
M15=900000


def stamp(day:date,h:int,m:int)->int:
    return int(datetime(day.year,day.month,day.day,h,m,tzinfo=LONDON).timestamp()*1000)


def signal(v:int)->int:
    return (v>0)-(v<0)


def local_feature(day:date,h:int,m:int,bars:dict)->dict:
    """Immutable causal prefix; only M15 closes at or BEFORE T."""
    t=stamp(day,h,m)
    start=stamp(day,4,0)
    anchor=stamp(day,8,0)
    if t<=anchor or (t-anchor)%M15 or (anchor-start)%M15:
        raise ValueError("PLH1_CALENDAR_GEOMETRY")
    stamps=list(range(start,t+M15,M15))
    paths={}
    for s in SYMBOLS:
        prices=[bars[s].get(x) for x in stamps]
        if any(x is None or x<=0 for x in prices):
            return {"state":"SOURCE_UNKNOWN"}
        paths[s]=prices
    j=(anchor-start)//M15
    older={s:signal(USD_ORIENTATION[s]*(v[j]-v[0])) for s,v in paths.items()}
    yes=sum(x>0 for x in older.values())
    no=sum(x<0 for x in older.values())
    if max(yes,no)<3:
        return {"state":"NO_COMMON_ASIA"}
    S=1 if yes>=3 else -1
    flips={s:signal(USD_ORIENTATION[s]*(v[-1]-v[-2]))==-S
           for s,v in paths.items()}
    count=sum(flips.values())
    if count<3:
        return {"state":"COMMON_NO_TRANSFER","asiaUsdSide":S}
    return {"state":"TRANSFER","asiaUsdSide":S,
            "individualIntents":count,
            "perSymbol":{s:int(flips[s]) for s in SYMBOLS}}


def original_source():
    need(PROTO.is_file() and "PRE-OUTCOME support" in PROTO.read_text(),
         "PLH1_PRE_FROZEN_PROTOCOL_MISSING")
    cipher=SEALED.read_bytes()
    receipt=json.loads(HXC_RECEIPT.read_text())
    need(sha256(cipher).hexdigest()==receipt["ciphertextSha256"],
         "PLH1_ORIGINAL_CIPHERTEXT_CHANGED")
    private=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"PLH1_ORIGINAL_CUSTODY_UNAVAILABLE")
    plaintext=unseal_new(cipher,private,HXC_RUN)
    source=json.loads(plaintext)
    certified=validate(source,receipt,HXC_RUN)
    need(certified["rawRequestsRebuilt"]==1444
         and certified["brokerOrders"]==0
         and certified["cloudActivated"] is False,
         "PLH1_ORIGINAL_PROTOBUF_SCOPE_FAILED")
    prices={}
    for s in SYMBOLS:
        key=s+"/M15"
        rows=source["bars"][key]
        prices[s]={int(x[1]):int(x[5]) for x in rows}
        need(len(prices[s])==len(rows)
             and len(rows)>=6200
             and certified["sourceCounts"][key]==len(rows),
             "PLH1_ORIGINAL_M15_CENSUS_MISSING")
    return prices,sha256(cipher).hexdigest(),sha256(plaintext).hexdigest(),certified


def costs():
    obj=json.loads(COST.read_text())
    need(obj["sourceMarketCount"]==18 and
         obj["sourceAuthentication"]=="ORIGINAL_PUBLISHED_CMA1_CMA2_XUA1_RAW_READBACK_PRIORLY_VERIFIED",
         "PLH1_PRIOR_AUTHENTIC_COST_SURFACE")
    prices={}
    for s in SYMBOLS:
        row=obj["sourceMarkets"][s]
        expected_margin,expected_fee=EXPECTED_COST[s]
        need(row["asof"]=="CMA1-2026-11-04" and
             row["minimumUnits"]==1000 and
             row["minMarginEUR"]==expected_margin and
             row["commissionRoundTripUSD"]==expected_fee,
             "PLH1_FX_CONTRACT_REFERENCE_CHANGED")
        prices[s]={"asof":row["asof"],"minimumUnits":row["minimumUnits"],
                   "minimumMarginEUR":row["minMarginEUR"],
                   "priorMinRoundtripCommissionUSD":row["commissionRoundTripUSD"],
                   "historicalSpreadBps":None}
    joint=sum(x["minimumMarginEUR"] for x in prices.values())
    return {"snapshot":prices,"allFourStaticMarginEur":round(joint,2),
            "illustrativeReserveFromInitialCapitalEur":90,
            "startingStaticEquityMinusReserveEur":210,
            "staticMarginAllowed":joint<=210 and all(
                0<x["minimumMarginEUR"]<210 for x in prices.values()),
            "historicalContractValidityCertified":False,
            "allInHistoricalFxCostKnown":False}


def evaluate(prices,original_hash,plain_hash,proof):
    c=Counter(); weekly=[]; all_intents=0; states=[]
    for w in range(13):
        counts=Counter()
        original_days=set()
        sign_transfer=Counter()
        for d in range(5):
            day=START+timedelta(weeks=w,days=d)
            all_complete_day=True
            for hh,mm in CLOCKS:
                f=local_feature(day,hh,mm,prices)
                state=f["state"]
                counts[state]+=1
                if state=="SOURCE_UNKNOWN":
                    all_complete_day=False
                if state=="TRANSFER":
                    intents=f["individualIntents"]
                    counts["RAW_INTENTS"]+=intents
                    counts["TRANSFER_POS_USD" if f["asiaUsdSide"]>0
                           else "TRANSFER_NEG_USD"]+=1
                    for name,present in f["perSymbol"].items():
                        counts["INTENT_"+name]+=present
            if all_complete_day:
                original_days.add(day.isoformat())
        counts["FULL_THREE_CLOCK_DAYS"]=len(original_days)
        counts["COMPLETE_CLOCKS"]=15-counts["SOURCE_UNKNOWN"]
        counts["WEEKLY_RAW_INTENTS_GE21"]=int(counts["RAW_INTENTS"]>=21)
        weekly.append({"week":w+1,"start":(START+timedelta(weeks=w)).isoformat(),
                       "counts":dict(counts)})
        c.update(counts)
        states.append(counts)
        all_intents+=counts["RAW_INTENTS"]
    transferred=sum(z["TRANSFER"] for z in states)
    plain=sum(z["COMMON_NO_TRANSFER"] for z in states)
    usable=c["COMPLETE_CLOCKS"]
    first_complete=sum(z["COMPLETE_CLOCKS"] for z in states[:6])
    late_complete=sum(z["COMPLETE_CLOCKS"] for z in states[6:])
    availability=(usable>=170 and first_complete>=68 and late_complete>=79
                  and sum(z["FULL_THREE_CLOCK_DAYS"]>=4 for z in states)>=11)
    each_half=lambda name: (sum(z[name]>0 for z in states[:6])>=4 and
                             sum(z[name]>0 for z in states[6:])>=4)
    two_sides=(each_half("TRANSFER_POS_USD") and
               each_half("TRANSFER_NEG_USD") and
               c["TRANSFER_POS_USD"]>=10 and c["TRANSFER_NEG_USD"]>=10)
    state_gate=(transferred>=20 and plain>=20 and
                each_half("TRANSFER") and each_half("COMMON_NO_TRANSFER")
                and two_sides)
    freq=sum(z["RAW_INTENTS"]>=21 for z in states)>=8 and all(
        z["RAW_INTENTS"]>=10 for z in states)
    finance=costs()
    complete=availability and state_gate and freq and finance["staticMarginAllowed"]
    return {
       "schema":"MXM_PLH1_FX_LONDON_PORTFOLIO_FIRST_EXPOSED_PREOUTCOME_CENSUS_V1",
       "status":("PLH1_PRESOURCE_SUPPORT_ONLY_NOT_ECONOMIC_QUALIFICATION"
                 if complete else "PLH1_PRESOURCE_STOP_NO_OUTCOME_SCORING"),
       "frozenPreSourceProtocolSha256":sha256(PROTO.read_bytes()).hexdigest(),
       "originalHxc1RunId":int(HXC_RUN),
       "originalHxc1CipherSha256":original_hash,
       "originalHxc1PlaintextSha256":plain_hash,
       "originalRawBarRequestsRebuilt":proof["rawRequestsRebuilt"],
       "sourceBarCounts":{s:proof["sourceCounts"][s+"/M15"] for s in SYMBOLS},
       "capitalEur":300,
       "floatingDrawdownTargetEur":90,
       "hard21PortfolioNotIndividual":21,
       "scheduledCrossMarketClocks":195,
       "scheduledPotentialPairClocks":780,
       "observedCompleteCrossMarketClocks":usable,
       "predecisionStates":{k:c[k] for k in
          ("TRANSFER","COMMON_NO_TRANSFER","NO_COMMON_ASIA","SOURCE_UNKNOWN")},
       "rawPotentialIntents":all_intents,
       "predecisionTransferUsdSigns":{
           "positive":c["TRANSFER_POS_USD"],
           "negative":c["TRANSFER_NEG_USD"]},
       "perMarketRawIntentCounts":{s:c["INTENT_"+s] for s in SYMBOLS},
       "weekly":weekly,
       "availabilitySupportGate":availability,
       "nonredundantObservableStateGate":state_gate,
       "portfolioResearchFrequencyHeuristicGate":freq,
       "staticMarginSnapshotGate":finance["staticMarginAllowed"],
       "priorOriginalCostAndCapacitySnapshot":finance,
       "futureOutcomesScored":False,
       "newBrokerRequests":0,
       "closedStudiesRerun":False,
       "brokerOrders":0,
       "cloudActivated":False,
       "financialActualEurNet":None,
       "conditionalEurNet":None,
       "historicalCompleteCostKnown":False,
       "nativeCloudRestartParityProved":False,
       "independentChronologyProved":False,
       "comment":"Cross-market opening features and raw intents are not 21 financable completed trips; prior commissions and margin are snapshots; no future trade results or quote crossing inspected. S3 is portfolio research efficiency heuristic, not mathematical impossibility."
    }


def main():
    prices,cipher,plain,proof=original_source()
    result=evaluate(prices,cipher,plain,proof)
    OUTPUT.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("PLH1_AUTHENTIC_PRESOURCE_LONDON_FX_PORTFOLIO_SUPPORT",
          result["status"],
          json.dumps({"states":result["predecisionStates"],
                      "rawIntentCount":result["rawPotentialIntents"],
                      "availability":result["availabilitySupportGate"],
                      "stateGate":result["nonredundantObservableStateGate"],
                      "frequency":result["portfolioResearchFrequencyHeuristicGate"],
                      "staticMargin":result["staticMarginSnapshotGate"]}),
          flush=True)

if __name__=="__main__":
    main()
