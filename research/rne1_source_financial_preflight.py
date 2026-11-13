"""RNE1-FEE original source-only conditional USD cost preflight.

Read-once sealed RNE1 2026-11-13 source. No new broker access, new predictor,
review of favorable subgroups, historical tariff certification or trading.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import mean

from .custody import unseal_new
from .ctrader_proto import OpenApiMessages_pb2 as m
from .rne1_eia_gas_release import (START,WEEKS,stamp,event_decision,
                                   score_one,markout,sign,evaluate)

RUN="43468457518"
CIPHER_SHA="3da628356a40679442d65a048f37b278356cda6060afe85510195e3131bcac14"
PLAIN_SHA="5a14486c71997f29c8a6c2ffbfa24d1380ba09a862f10f75916d5d2512d8b01c"
PUBLIC_SHA="7ac85fb30374cfe20a3dad722e50aedebcfdc3ac68d23614539c8d002e5c1dd8"
SCALAR=D(10)**8
POLICIES=("rne1","fixed","ownMomentum","long","short","cash")


class Unpriced(ValueError):
    pass


def fee_usd(c,units,price):
    """Native matching contract commission categories, quote asset USD only."""
    for field in ("minVolume","stepVolume","maxVolume","lotSize",
                  "preciseTradingCommissionRate","preciseMinCommission",
                  "commissionType","minCommissionType"):
        if not c.HasField(field):
            raise Unpriced("MISSING_CURRENT_CONTRACT_"+field)
    min_units=D(c.minVolume)/100
    step=D(c.stepVolume)/100
    max_units=D(c.maxVolume)/100
    lot=D(c.lotSize)/100
    if (units<min_units or units>max_units or step<=0 or lot<=0 or
        (units-min_units)%step!=0 or int(c.tradingMode)!=0):
        raise Unpriced("INVALID_CURRENT_MINIMUM_TRADE_GRID")
    rate=D(c.preciseTradingCommissionRate)/SCALAR
    typ=int(c.commissionType)
    if typ==1: # USD per million USD notional
        base=rate*units*price / D(1000000)
    elif typ==2: # USD per lot
        base=rate*units/lot
    elif typ==3: # percent of USD notional, wire scaled x1e5
        base=(D(c.preciseTradingCommissionRate)/D(100000))/100 *units*price
    elif typ==4: # quote currency per lot, NatGas USD quote
        base=rate*units/lot
    else:
        raise Unpriced("UNKNOWN_CURRENT_COMMISSION_TYPE")
    if int(c.minCommissionType)==1:
        if not c.HasField("minCommissionAsset") or not c.minCommissionAsset:
            raise Unpriced("FLOOR_CURRENCY_UNKNOWN")
        floor_asset=c.minCommissionAsset
    elif int(c.minCommissionType)==2:
        floor_asset="USD"
    else:
        raise Unpriced("UNKNOWN_CURRENT_MINIMUM_FEE_TYPE")
    floor=D(c.preciseMinCommission)/SCALAR
    if floor and floor_asset!="USD":
        raise Unpriced("MIN_FEE_NOT_USD_NO_AUTHENTIC_FX")
    if rate<0 or floor<0:
        raise Unpriced("NEGATIVE_CURRENT_FEE")
    return max(base,floor)


def outcome(c, entry, ending, side, slippage_roundtrip_bps):
    if side==0:
        return {"grossUSD":0.0,"currentCommissionUSD":0.0,
                "modelSlippageUSD":0.0,"conversionFeeUSD":0.0,
                "conditionalCostUSD":0.0,"conditionalNetUSD":0.0,
                "notionalUSD":0.0}
    if not c.HasField("pnlConversionFeeRate"):
        raise Unpriced("P_AND_L_CONVERSION_RATE_MISSING")
    start=[D(x)/D(100000) for x in entry]
    exit_=[D(x)/D(100000) for x in ending]
    if min(*start,*exit_)<=0 or start[0]>start[1] or exit_[0]>exit_[1]:
        raise Unpriced("INVALID_ORIGINAL_BIDASK")
    units=D(c.minVolume)/100
    mid=(start[0]+start[1])/2
    opening=start[1] if side>0 else start[0]
    closing=exit_[0] if side>0 else exit_[1]
    gross=D(side)*(closing-opening)*units
    entry_fee=fee_usd(c,units,opening)
    exit_fee=fee_usd(c,units,closing)
    commission=entry_fee+exit_fee
    slip=units*mid*D(str(slippage_roundtrip_bps))/D(10000)
    conv=abs(gross)*D(c.pnlConversionFeeRate)/D(10000)
    # Each component is native USD only; no EUR account currency credited.
    return {
        "grossUSD":float(gross),
        "currentCommissionUSD":float(commission),
        "modelSlippageUSD":float(slip),
        "conversionFeeUSD":float(conv),
        "conditionalCostUSD":float(commission+slip+conv),
        "conditionalNetUSD":float(gross-commission-slip-conv),
        "notionalUSD":float(units*mid),
    }


def unpack_original():
    cipher=Path("original-source/rne1-eia-protected-original.v2.enc").read_bytes()
    public=Path("original-public/rne1-eia-public.json").read_bytes()
    if sha256(cipher).hexdigest()!=CIPHER_SHA or sha256(public).hexdigest()!=PUBLIC_SHA:
        raise ValueError("ORIGINAL_RNE1_SOURCE_OR_PUBLIC_DIGEST_CHANGED")
    private=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    raw=unseal_new(cipher,private,RUN)
    if sha256(raw).hexdigest()!=PLAIN_SHA:
        raise ValueError("ORIGINAL_RNE1_PLAINTEXT_DIGEST_CHANGED")
    tape=json.loads(raw)
    receipt=json.loads(public)
    if (tape["schema"]!="MXM_ORIGINAL_RNE1_SOURCE_PRIVATE" or
        tape["run"]!=RUN or
        receipt["originalRun"]!=int(RUN) or
        receipt["sourcePlainSha256"]!=PLAIN_SHA or
        receipt["sealedSourceSha256"]!=CIPHER_SHA or
        not tape["originalAccountVerified"] or
        not receipt["originalPepperstoneEurAccountVerified"]):
        raise ValueError("RNE1_ORIGINAL_AUTHORITY_OR_ACCOUNT_MISMATCH")
    return tape,receipt


def get_terms(raw):
    market=None
    for item in raw["requests"]:
        typ=item["responseType"]
        if typ=="ProtoOASymbolsListRes":
            reply=m.ProtoOASymbolsListRes()
            reply.ParseFromString(base64.b64decode(item["response"],validate=True))
            ids=[s.symbolId for s in reply.symbol if s.symbolName=="NatGas" and s.enabled]
            if len(ids)!=1:raise Unpriced("NATGAS_ORIGINAL_ROSTER_INVALID")
            market=ids[0]
    if market is None:raise Unpriced("ORIGINAL_NATGAS_ROSTER_NOT_SEEN")
    found=[]
    for item in raw["requests"]:
        if item["responseType"]!="ProtoOASymbolByIdRes":
            continue
        reply=m.ProtoOASymbolByIdRes()
        reply.ParseFromString(base64.b64decode(item["response"],validate=True))
        found += [s for s in reply.symbol if s.symbolId==market]
    if len(found)!=1:
        raise Unpriced("ORIGINAL_NATGAS_CONTRACT_NOT_UNIQUE")
    return found[0]


def summarize(rows):
    answer={"priced":len(rows),"weeks":len({x["week"] for x in rows})}
    for scenario in ("central","adverse"):
        answer[scenario]={}
        for policy in POLICIES:
            policy_rows=[x[scenario][policy] for x in rows]
            answer[scenario][policy]={
                "conditionalNetUsdSum":round(sum(v["conditionalNetUSD"] for v in policy_rows),6),
                "conditionalNetUsdMean":round(mean(v["conditionalNetUSD"] for v in policy_rows),6) if rows else None,
                "commissionUsdSum":round(sum(v["currentCommissionUSD"] for v in policy_rows),6),
                "slippageModelUsdSum":round(sum(v["modelSlippageUSD"] for v in policy_rows),6)
            }
    return answer


def main():
    original,receipt=unpack_original()
    source=original["source"]
    for symbol,days in source.items():
        for day,tape in days.items():
            tape["bars"]={int(k):int(v) for k,v in tape["bars"].items()}
    repeated=evaluate(source,original["currentContract"])
    for symbol in ("NatGas","EQT.US"):
        for cohort in ("release","placebo"):
            rec=repeated[symbol][cohort]
            initial=receipt["targets"][symbol][cohort]
            if (rec["decisionCounts"]!=initial["decisionCounts"] or
                rec["adaptivePriced"]!=initial["adaptivePriced"] or
                rec["pairedPriced"]!=initial["pairedPriced"]):
                raise ValueError("RNE1_AUTHENTIC_ORIGINAL_COVERAGE_CHANGED")
    c=get_terms(original)
    fee_status="PRICED_CURRENT_ONLY"
    rows=[]
    costs=Counter()
    for week in range(WEEKS):
        day=START+timedelta(weeks=week,days=3)
        source_day=source["NatGas"][day.isoformat()]
        decision=event_decision(day,source_day["bars"])
        if decision["state"]!="RELEASE_SHOCK_CANDIDATE":
            continue
        row=score_one({"kind":"THURSDAY_OFFICIAL_EIA_SCHEDULE",
                       "week":week,"day":day,"gasBars":source_day["bars"]},source_day)
        if row["state"]!="ADAPTIVE_PRICED":
            costs[row["state"]]+=1
            continue
        q=source_day["quote"]
        entry=q["10:50"]
        end=q[row["exitAt"]]
        fixed=q["12:05"]
        if fixed is None:
            costs["NO_MATCHED_FIXED_QUOTE"]+=1
            continue
        target_bars=source_day["bars"]
        from_ = stamp(day,10,15)
        to = stamp(day,10,45)
        from .rne1_eia_gas_release import bps
        own=sign(bps(target_bars,from_,to))
        policies={"rne1":(decision["side"],end),
                  "fixed":(decision["side"],fixed),
                  "ownMomentum":(own,fixed),
                  "long":(1,fixed),"short":(-1,fixed),
                  "cash":(0,fixed)}
        try:
            priced={
                scenario:{p:outcome(c,entry,v[1],v[0],slip)
                          for p,v in policies.items()}
                for scenario,slip in (("central",0.5),("adverse",2.0))
            }
            rows.append({"week":week,**priced})
        except Unpriced as ex:
            costs[str(ex)]+=1
    out={
        "schema":"MXM_RNE1_ORIGINAL_SOURCE_ONLY_CURRENT_COST_USD_PREFLIGHT",
        "originalRunId":int(RUN),
        "originalEncryptedArtifactId":14059473739,
        "originalPublicArtifactId":14059488784,
        "originalEncryptedSha256":CIPHER_SHA,
        "originalPlainSha256":PLAIN_SHA,
        "originalPublicSha256":PUBLIC_SHA,
        "financialProtocolSha256":sha256(Path(
            "research/RNE1_SOURCE_FINANCIAL_PREFLIGHT.md").read_bytes()).hexdigest(),
        "originalRne1CausalEventsUnchanged":True,
        "newPepperstoneRequests":0,
        "NatGasQuoteCurrency":"USD",
        "currentMinimumUnits":float(D(c.minVolume)/100),
        "currentCommissionType":int(c.commissionType),
        "currentCommissionMinimumType":int(c.minCommissionType),
        "currentTermsNotHistorical":True,
        "matchedOriginalReleaseCandidates":receipt["targets"]["NatGas"]["release"]["pairedPriced"],
        "financiallyPricedRows":len(rows),
        "unknownFinanceReasons":dict(costs),
        "first13":summarize([x for x in rows if x["week"]<13]),
        "last13":summarize([x for x in rows if x["week"]>=13]),
        "allMatched":summarize(rows),
        "eurNet":None,"fundedEur300Trades":0,
        "historicalTariffContinuityCertified":False,
        "independentConfirmation":False,
        "ordersSubmitted":0,"oauthReauthorized":False,
        "disclosure":"USD conditional current-tariff cost screen, NOT original account EUR NET; no USD/EUR historical conversion, no full open equity, no native funded ledger, no actual fills or certified historical commission continuity."}
    Path("rne1-current-contract-usd-cost-screen.json").write_text(
        json.dumps(out,indent=2,allow_nan=False)+"\n")
    print("RNE1_AUTHENTIC_SOURCE_PRICE_WITHOUT_BROKER_REAUTH",
          json.dumps({"priced":len(rows),"unknown":dict(costs),
                      "outcome":out["allMatched"]["adverse"].get("rne1")}),flush=True)

if __name__=="__main__":
    main()
