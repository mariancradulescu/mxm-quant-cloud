"""DLR1: cold original 52-week BDP1 bars, coherent USD FX/gold opening shock.

Original source read only in custody. No broker calls, no OHLC-to-BIDASK fraud.
Rational hypothesis and rejection comparisons frozen BEFORE scoring.
"""
from __future__ import annotations

from collections import Counter
from datetime import date,datetime,time,timedelta
from hashlib import sha256
from math import log
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo
import json,os

from .custody import unseal_new

SOURCE_RUN="41724643418"
SOURCE_CIPHER="e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370"
ORIGINAL_READBACK_PUBLIC_SHA="180838d4cd9f428e219db27de436e1304bf9f55fdc53d052f28d9bd4a7885bd9"
ORIGINAL_BARCOUNTS={"EURUSD":74195,"USDJPY":74031,"XAUUSD":70550}
START=date(2025,11,3)
WEEKS=52
M5=300000
NY=ZoneInfo("America/New_York")
SYMBOLS=("EURUSD","USDJPY","XAUUSD")
POLICIES=("coherentUsdOpening","dollarFirstBarUnfiltered",
          "fixedLongUsd","fixedShortUsd","cash")


def stamp(d,hh,mm):
    return int(datetime.combine(d,time(hh,mm),NY).timestamp()*1000)


def sign(x):
    return (x>0)-(x<0)


def source_day(d,marks):
    """No scoring yet: all 3 M5 mark arrays from frozen original source."""
    t=stamp(d,9,30)
    first={}
    for name in SYMBOLS:
        x=marks[name].get(t)
        if x is None or x[1]!=t+M5 or min(x[2],x[5])<=0:
            return {"state":"MISSING_OR_INVALID_CAUSAL_FIRST_M5"}
        first[name]=sign(x[5]-x[2])
    dollar=-first["EURUSD"]
    if dollar==0 or first["USDJPY"]!=dollar or first["XAUUSD"]!=-dollar:
        coherent=False
    else:
        coherent=True
    # Need full 09:30...10:30 M5 rows across all 3 markets,
    # irrespective of initial coherent source state, for matched
    # fully unconditional comparator on same original weekdays.
    rows={}
    for name in SYMBOLS:
        seq=[marks[name].get(t+i*M5) for i in range(13)]
        if any(r is None or r[1]!=t+(i+1)*M5 for i,r in enumerate(seq)):
            return {"state":"MISSING_FUTURE_M5_PATH",
                    "causalCoherentIntent":coherent}
        if min(seq[2][2],seq[12][2])<=0:
            return {"state":"INVALID_GROSS_PROXY",
                    "causalCoherentIntent":coherent}
        rows[name]=(seq[2][2],seq[12][2])
    returns={
        sym:10000*log(rows[sym][1]/rows[sym][0])
        for sym in SYMBOLS
    }
    def triplet(dir_usd):
        return (dir_usd*(-returns["EURUSD"]+
                         returns["USDJPY"]-
                         returns["XAUUSD"]))/3
    gr={
        "coherentUsdOpening":triplet(dollar) if coherent else 0.0,
        "dollarFirstBarUnfiltered":triplet(dollar) if dollar else 0.0,
        "fixedLongUsd":triplet(1),
        "fixedShortUsd":triplet(-1),
        "cash":0.0
    }
    return {"state":"MATCHED_COMPLETE_M5_OPEN_PROXY",
            "coherentEvent":coherent,
            "usdDirection":dollar,
            "grossBps":gr}


def report(rows):
    priced=[x for x in rows if x["state"]=="MATCHED_COMPLETE_M5_OPEN_PROXY"]
    event=[x for x in priced if x["coherentEvent"]]
    def mean_all(key,items):
        return round(mean(x["grossBps"][key] for x in items),6) if items else None
    def sum_all(key,items):
        return round(sum(x["grossBps"][key] for x in items),6)
    return {
        "scheduledDays":len(rows),
        "sourceStates":dict(Counter(x["state"] for x in rows)),
        "causalCoherenceIntents":sum(
            x.get("coherentEvent",x.get("causalCoherentIntent",False))
            for x in rows),
        "sourceCompleteComparisonDays":len(priced),
        "coherentEventsScored":len(event),
        "weeksWithCoherentEvents":len({x["week"] for x in event}),
        "coherentUsdLongDays":sum(
            x["usdDirection"]==1 for x in event),
        "coherentUsdShortDays":sum(
            x["usdDirection"]==-1 for x in event),
        "positiveCoherentGrossDays":sum(
            x["grossBps"]["coherentUsdOpening"]>0 for x in event),
        "negativeCoherentGrossDays":sum(
            x["grossBps"]["coherentUsdOpening"]<0 for x in event),
        "sameDenominatorGrossMeanBps":{
            p:mean_all(p,priced) for p in POLICIES},
        "sameDenominatorGrossCumulativeBps":{
            p:sum_all(p,priced) for p in POLICIES},
        "activeEventGrossMeanBps":{
            p:mean_all(p,event) for p in POLICIES},
        "activeEventGrossCumulativeBps":{
            p:sum_all(p,event) for p in POLICIES},
        "scheduledDayMeanPrimaryBpsWithMissingNotImputed":(
            None if len(priced)!=len(rows) else
            mean_all("coherentUsdOpening",priced)),
        "incrementVsUnfilteredMeanBps":round(mean(
            x["grossBps"]["coherentUsdOpening"]-
            x["grossBps"]["dollarFirstBarUnfiltered"]
            for x in priced),6) if priced else None,
    }


def analyze(source):
    symbols=source["bars"]
    assert set(SYMBOLS).issubset(symbols)
    maps={}
    for s in SYMBOLS:
        rows=symbols[s]
        if len(rows)!=ORIGINAL_BARCOUNTS[s]:
            raise ValueError("DLR1_ORIGINAL_BAR_COUNTS_CHANGED")
        d={}
        for r in rows:
            if len(r)!=7 or r[0] in d or r[1]-r[0]!=M5:
                raise ValueError("DLR1_INVALID_OR_DUPLICATE_M5_ORIGINAL")
            d[r[0]]=r
        maps[s]=d
    rows=[]
    for week in range(WEEKS):
        for wd in range(5):
            day=START+timedelta(weeks=week,days=wd)
            if day>date(2026,10,30):
                raise ValueError("DLR1_FROZEN_52_WEEK_CALENDAR_OVERSHOT")
            v=source_day(day,maps)
            rows.append({"week":week,**v})
    all_=report(rows)
    first=report([x for x in rows if x["week"]<26])
    last=report([x for x in rows if x["week"]>=26])
    def wins(a):
        c=a["sameDenominatorGrossCumulativeBps"]
        return (a["sourceCompleteComparisonDays"]>0 and
                c["coherentUsdOpening"]>0 and
                c["coherentUsdOpening"]>c["dollarFirstBarUnfiltered"])
    return {
        "all52Weeks":all_,
        "first26Weeks":first,
        "last26Weeks":last,
        "passesGrossPrerequisiteBeforeNewBidAskResearch":(
            wins(all_) and wins(first) and wins(last)),
        "original2026HistoryGloballyExposed":True,
        "historicalSourceYearsAdequateForIndependentConfirmation":False
    }


def original_files():
    source=list(Path("bdp1-original").rglob("source.envelope.json"))
    receipt=list(Path("bdp1-original").rglob("receipt.public.json"))
    if len(source)!=1 or len(receipt)!=1 or source[0].parent!=receipt[0].parent:
        raise ValueError("DLR1_ORIGINAL_BDP1_SOURCE_ZIP_INCOMPLETE")
    return source[0],receipt[0]


def main():
    src,rec=original_files()
    cipher=src.read_bytes()
    receipt=json.loads(rec.read_text())
    if (sha256(cipher).hexdigest()!=SOURCE_CIPHER or
        receipt.get("sha256")!=SOURCE_CIPHER or
        receipt.get("runId")!=SOURCE_RUN or
        not receipt.get("complete") or
        receipt.get("schema")!="mxm-bdp1-source-v1"):
        raise ValueError("DLR1_ORIGINAL_BDP1_SOURCE_CUSTODY_INVALID")
    public_bytes=(Path("bdp1-public")/"portfolio-discovery.public.json").read_bytes()
    if sha256(public_bytes).hexdigest()!=ORIGINAL_READBACK_PUBLIC_SHA:
        raise ValueError("DLR1_PREVIOUS_AUTHENTIC_READBACK_PUBLIC_HASH_CHANGED")
    previous=json.loads(public_bytes)
    audit=previous.get("SourceAudit",{})
    if (previous.get("SourceRunId")!=int(SOURCE_RUN)
        or previous.get("SourceCiphertextSha256")!=SOURCE_CIPHER
        or previous.get("RawReadbackMatched") is not True
        or audit.get("originalAccountBindingRechecked") is not True
        or any(audit.get("bars",{}).get(s)!=ORIGINAL_BARCOUNTS[s]
               for s in SYMBOLS)):
        raise ValueError("DLR1_ORIGINAL_ACCOUNT_OR_SOURCE_RECEIPT_RECONCILIATION")
    private=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    if not private.strip():
        raise ValueError("DLR1_ORIGINAL_CUSTODY_PRIVATE_MISSING")
    payload=json.loads(unseal_new(cipher,private,SOURCE_RUN))
    if (payload.get("schema")!="mxm-bdp1-source-v1" or
        payload.get("readOnly") is not True or
        payload.get("depositCurrency")!="EUR" or
        payload.get("auditReceipt")!=audit):
        raise ValueError("DLR1_ORIGINAL_BDP1_PROTECTED_SOURCE_AUDIT_MISMATCH")
    result=analyze(payload)
    output={
        "schema":"MXM_DLR1_BDP1_52_WEEK_ORIGINAL_USD_FUNDING_M5_GROSS_ONLY",
        "frozenProtocolSha256":sha256(Path(
            "research/DLR1_USD_FUNDING_COHERENT_OPEN.md").read_bytes()).hexdigest(),
        "originalBrokerSourceRunId":int(SOURCE_RUN),
        "originalSourceCipherSha256":SOURCE_CIPHER,
        "previousOriginalAuditVerified":True,
        "originalSourceCustodyUnsealed":True,
        "originalRawBrokerSourceNotRepublished":True,
        "sourceOriginalBars":{s:ORIGINAL_BARCOUNTS[s] for s in SYMBOLS},
        "newBrokerRequests":0,
        "closedBDP1EconomicProgramReexecuted":False,
        "sameHistoricalPricesReusedForDistinctEconomics":True,
        "economics":result,
        "netEur":None,"bidAskAtNewDecisions":False,
        "nativeFundedCSharpLedgerExecuted":False,
        "continuousOpenEquityDrawdownCertified":False,
        "independentChronologyCertified":False,
        "portfolioHard21Certified":False,
        "currentVsHistoricTradingTermsValidated":False,
        "brokerOrdersSubmitted":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Genuine previously authenticated original Pepperstone EUR source for M5 bars. Only proxy open-to-open multiasset basket gross bps, no contract min volume, actual order fills, executable quotes, fees, financing, EUR conversion, native capital or independent confirmation."
    }
    Path("dlr1-original-authenticated-52week-gross.json").write_text(
        json.dumps(output,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("DLR1_ORIGINAL_52W_ECONOMIC_GROSS_REUSE",json.dumps({
        "zeroNewBrokerCalls":True,
        "all":{k:result["all52Weeks"][k] for k in (
            "sourceStates","coherentEventsScored",
            "sameDenominatorGrossMeanBps","incrementVsUnfilteredMeanBps")},
        "firstGross":result["first26Weeks"]["sameDenominatorGrossMeanBps"]["coherentUsdOpening"],
        "lastGross":result["last26Weeks"]["sameDenominatorGrossMeanBps"]["coherentUsdOpening"],
        "costFollowup":result["passesGrossPrerequisiteBeforeNewBidAskResearch"]},
        sort_keys=True),flush=True)

if __name__=="__main__":
    main()
