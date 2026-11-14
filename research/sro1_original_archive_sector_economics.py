"""SRO1 source-reuse-only U.S. sector rotation vs ETF opening auction.
Original ECA1 encrypted Pepperstone 2026 M5 archive; NO broker calls.

Two pre-frozen hypotheses and same-clock comparator baskets; no NET EUR.
"""
from __future__ import annotations

from collections import Counter
from datetime import date,datetime,time,timedelta
from hashlib import sha256
from math import log
from pathlib import Path
from statistics import mean,median
from zoneinfo import ZoneInfo
import json,os

from .custody import unseal_new

SOURCE_RUN="43498785771"
SOURCE_SHA="68b45ba2cc4a85bed53617a612384da5115d479f5fedf0abc7eec24f29653aa3"
SOURCE_PLAIN="e1f6a1c89b5617a1bbf9261c3a911e24aa3e602737fa45b0b35ec49f03bc33c8"
SOURCE_PUBLIC="22d008a84e8781dbf1f6710cfc5131a3062676675fe66102b7e4ca77850e0b07"
START=date(2026,5,4)
WEEKS=26
NY=ZoneInfo("America/New_York")
FIVE=300000
# Study: label, higher-tech name, broad name, anticipated relative trend sign.
PAIRS=(("INDEX_SECTOR_ROTATION_CONTINUATION","NAS100","US500",1),
       ("ETF_AUCTION_DISLOCATION_REVERSION","QQQ.US","SPY.US",-1))
STUDIES=("primary","fixedHighMinusBroad","fixedBroadMinusHigh",
         "reversePrimary","cash")


def stamp(day,hh,mm):
    return int(datetime.combine(day,time(hh,mm),NY).timestamp()*1000)


def m5_at(bars,t):
    x=[bar for bar in bars if bar[0]==t and bar[1]==t+FIVE]
    if len(x)!=1:return None
    return x[0]


def sign(v):
    return (v>0)-(v<0)


def feature(day,high,broad):
    """The only pre-entry feature is two completed first M5 bars at 09:35."""
    t=stamp(day,9,30)
    a=m5_at(high,t);b=m5_at(broad,t)
    if a is None or b is None:
        return {"state":"FIRST_OPENING_BAR_MISSING"}
    if min(a[2],a[5],b[2],b[5])<=0:
        return {"state":"SOURCE_BAR_NONPOSITIVE"}
    ah=sign(a[5]-a[2]);bb=sign(b[5]-b[2])
    if ah==0 or bb==0 or ah==bb:
        return {"state":"NO_CROSS_SECTOR_OPPOSITION"}
    return {"state":"CAUSAL_OPPOSITION","higherFirstSide":ah,
            "broadFirstSide":bb}


def scored(day,high,broad,primary_multiplier):
    if high is None or broad is None:
        return {"state":"ORIGINAL_M5_SOURCE_MISSING"}
    x=feature(day,high,broad)
    if x["state"]!="CAUSAL_OPPOSITION":return x
    t0=stamp(day,9,30)
    # Readout of the complete ORIGINAL M5 path; none may be inferred.
    all_high=[m5_at(high,t0+i*FIVE) for i in range(13)]
    all_broad=[m5_at(broad,t0+i*FIVE) for i in range(13)]
    if any(z is None for z in all_high+all_broad):
        return {"state":"CAUSAL_EVENT_INCOMPLETE_OUTCOME_PATH"}
    entry_high,entry_broad=all_high[2][2],all_broad[2][2]
    exit_high,exit_broad=all_high[12][2],all_broad[12][2]
    if min(entry_high,entry_broad,exit_high,exit_broad)<=0:
        return {"state":"CAUSAL_EVENT_NONPOSITIVE_MARK"}
    rh=10000*log(exit_high/entry_high)
    rb=10000*log(exit_broad/entry_broad)
    idxsign=x["higherFirstSide"]
    # Opposing first-bar movements guarantee broad sign = -idxsign.
    # Primary index route: continuation; ETF route: reversion.
    primary=primary_multiplier*idxsign*(rh-rb)/2
    fixed=(rh-rb)/2
    return {"state":"MATCHED_GROSS_BAR_OPEN_PROXY",
            "grossBps":{
                "primary":primary,
                "fixedHighMinusBroad":fixed,
                "fixedBroadMinusHigh":-fixed,
                "reversePrimary":-primary,
                "cash":0.0},
            "firstSign":idxsign,
            "proxyEntryClock":"09:40",
            "proxyExitClock":"10:30"}


def group(rows):
    complete=[r for r in rows if r["state"]=="MATCHED_GROSS_BAR_OPEN_PROXY"]
    return {
        "scheduledDays":len(rows),
        "states":dict(Counter(r["state"] for r in rows)),
        "eventIntents":sum(r["state"] in (
            "MATCHED_GROSS_BAR_OPEN_PROXY",
            "CAUSAL_EVENT_INCOMPLETE_OUTCOME_PATH",
            "CAUSAL_EVENT_NONPOSITIVE_MARK") for r in rows),
        "scoredMatched":len(complete),
        "weeksWithScored":len({r["week"] for r in complete}),
        "primaryCausalLongHigherCount":sum(r["firstSign"]==1 for r in complete),
        "primaryCausalShortHigherCount":sum(r["firstSign"]==-1 for r in complete),
        "grossSumBpsByPolicy":{
            p:round(sum(r["grossBps"][p] for r in complete),6)
            for p in STUDIES},
        "grossMeanBpsByPolicy":{
            p:round(mean(r["grossBps"][p] for r in complete),6) if complete else None
            for p in STUDIES},
        "primaryMedianGrossBps":round(median(
            r["grossBps"]["primary"] for r in complete),6) if complete else None,
        "primaryPositiveOutcomes":sum(
            r["grossBps"]["primary"]>0 for r in complete),
        "primaryNegativeOutcomes":sum(
            r["grossBps"]["primary"]<0 for r in complete),
        "grossIncrementVsConstantHighMinusBroadMeanBps":round(mean(
            r["grossBps"]["primary"]-r["grossBps"]["fixedHighMinusBroad"]
            for r in complete),6) if complete else None,
        "grossIncrementVsConstantBroadMinusHighMeanBps":round(mean(
            r["grossBps"]["primary"]-r["grossBps"]["fixedBroadMinusHigh"]
            for r in complete),6) if complete else None,
    }


def analyze(raw):
    data=raw["originalDecodedSource"]["dates"]
    if len(data)!=130:
        raise ValueError("SRO1_ORIGINAL_ECA1_130_DAYS_REQUIRED")
    for day in (START+timedelta(days=7*i+wd)
                for i in range(WEEKS) for wd in range(5)):
        if day.isoformat() not in data:
            raise ValueError("SRO1_ECA1_CALENDAR_SOURCE_MISSING")
    result={}
    for label,high,broad,mul in PAIRS:
        rows=[]
        for w in range(WEEKS):
            for wd in range(5):
                day=START+timedelta(weeks=w,days=wd)
                rec=data[day.isoformat()]
                if rec.get("week")!=w:
                    raise ValueError("SRO1_ECA1_WEEK_MISMATCH")
                if rec["barTruncated"].get(high) or rec["barTruncated"].get(broad):
                    state={"state":"ORIGINAL_M5_SOURCE_TRUNCATED"}
                else:
                    state=scored(day,rec["bars"].get(high),
                                 rec["bars"].get(broad),mul)
                rows.append({"week":w,**state})
        overall=group(rows)
        early=group([r for r in rows if r["week"]<13])
        late=group([r for r in rows if r["week"]>=13])
        # No favorable route selection after seeing the original outcomes.
        def eligible(g):
            n=g["scoredMatched"]
            if n==0:return False
            means=g["grossMeanBpsByPolicy"]
            return (means["primary"]>0
                    and means["primary"]>means["fixedHighMinusBroad"]
                    and means["primary"]>means["fixedBroadMinusHigh"])
        result[label]={
            "highTechMarket":high,"broadMarket":broad,
            "economicPremise":"continuation" if mul==1 else "reversion",
            "all":overall,"first13":early,"last13":late,
            "grossFollowupWorthFurtherIndependentCostObservation":(
                eligible(overall) and eligible(early) and eligible(late)),
            "originalGrossM5Only":True,"qualifiedForCbot":False}
    return result


def main():
    folder=Path("source-original")
    cipher=(folder/"eca1-original-protected.v2.enc").read_bytes()
    receipt=(Path("source-public")/"eca1-original-public-economic.json").read_bytes()
    if sha256(cipher).hexdigest()!=SOURCE_SHA or (
        sha256(receipt).hexdigest()!=SOURCE_PUBLIC):
        raise ValueError("SRO1_ECA1_ORIGINAL_CIPHERTEXT_OR_PUBLIC_HASH_MISMATCH")
    meta=json.loads(receipt)
    if (meta.get("originalRun")!=int(SOURCE_RUN) or
        meta.get("originalEncryptedSourceSha256")!=SOURCE_SHA or
        meta.get("originalPlaintextSourceSha256")!=SOURCE_PLAIN or
        meta.get("originalReadOnlyRequestsAfterAuthentication")!=929):
        raise ValueError("SRO1_ECA1_ORIGINAL_PUBLIC_PROVENANCE_MISMATCH")
    private=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    if not private.strip():raise ValueError("SRO1_CUSTODY_PRIVATE_MISSING")
    plain=unseal_new(cipher,private,SOURCE_RUN)
    if sha256(plain).hexdigest()!=SOURCE_PLAIN:
        raise ValueError("SRO1_ECA1_ORIGINAL_PLAINTEXT_HASH_MISMATCH")
    raw=json.loads(plain)
    if (raw.get("schema")!="MXM_ECA1_PRIVATE_ORIGINAL_BROKER_RESEARCH_SOURCE"
        or raw.get("run")!=SOURCE_RUN or
        raw.get("accountOriginalPepperstoneEurVerified") is not True
        or raw.get("sourceRequests")!=929
        or raw.get("barsFirstOnlyUsedToChooseFutureQuoteQueries") is not True):
        raise ValueError("SRO1_ECA1_AUTHENTIC_SOURCE_SCHEMA_MISMATCH")
    outcomes=analyze(raw)
    # Never output or reencrypt original private data or quote prices.
    out={
        "schema":"MXM_SRO1_ORIGINAL_ARCHIVED_U_S_SECTOR_RESPONSE_GROSS_ONLY",
        "frozenProtocolSha256":sha256(Path(
            "research/SRO1_US_SECTOR_ROTATION_BASKET.md").read_bytes()).hexdigest(),
        "originalEca1RunId":int(SOURCE_RUN),
        "originalEca1CipherSha256":SOURCE_SHA,
        "originalEca1PlaintextSha256":SOURCE_PLAIN,
        "originalEca1PublicSha256":SOURCE_PUBLIC,
        "originalOriginalPepperstoneAccountAuthenticated":True,
        "encryptedCustodyDecryptionValidated":True,
        "reusedOriginal2026FirstBarsAndFutureBars":True,
        "brokerRequestsDuringThisResearch":0,
        "sourceOriginalRewritten":False,
        "studyPeriod":"2026-05-04/2026-10-30",
        "alreadyGloballyExposed2026Development":True,
        "twoFrozenPrecommittedHypotheses":list(outcomes),
        "baskets":outcomes,
        "monetaryNetEur":None,
        "originalBidAskAtAllNewSignals":False,
        "actualFundedTrades":0,
        "nativeCSharpFinancedLedger":False,
        "floatingRiskDrawdownCertified":False,
        "full12MonthsIndependentConfirmed":False,
        "portfolioHard21Certified":False,
        "finalCloudCbotAdmission":False,
        "noHttpNewsOrAIInputNeeded":True,
        "ordersSubmitted":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Only previously authenticated ECA1 original M5 BAR OPEN proxies. Not as-of executable BID/ASK, historical fills, net after costs, funded EUR300 book, independent holdout, or actual cBot risk."
    }
    Path("sro1-archived-original-economic-gross.json").write_text(
        json.dumps(out,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("SRO1_GROSS_ECONOMIC_ORIGINAL_ARCHIVE_REUSE",
          json.dumps({name:{
              "all":v["all"]["states"],
              "n":v["all"]["scoredMatched"],
              "firstMean":v["first13"]["grossMeanBpsByPolicy"]["primary"],
              "lastMean":v["last13"]["grossMeanBpsByPolicy"]["primary"],
              "primaryMean":v["all"]["grossMeanBpsByPolicy"]["primary"],
              "continueToCost":v["grossFollowupWorthFurtherIndependentCostObservation"]}
              for name,v in outcomes.items()},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
