"""RNV1 2025 predevelopment blind backcast of exact frozen RNE1.

No adjustment of 2026 RNE1 event decision, targets or exit. All original
Pepperstone source protobuf data are sealed BEFORE 2025 outcome scoring.
Older historical stress is not postdevelopment independent confirmation.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import date,timedelta
from decimal import Decimal as D
from hashlib import sha256
import json,os
from pathlib import Path
from statistics import mean

from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars,decode_side
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody_new import checked_public
from .custody import seal_new
from .rne1_eia_gas_release import (
    event_decision,score_one,stamp,paired,bps,sign)
from .rne1_eur_protected_exact_reconciliation import current_eur,no_swap,Unpriced

START=date(2025,2,3)
WEEKS=39
EXCLUDE=date(2025,6,16)
TARGETS=("NatGas","EQT.US")
MARKETS=("NatGas","EQT.US","EURUSD")
DAYS=(1,3)
CLOCKS=(("10:50",10,50),("11:20",11,20),("12:05",12,5))
M5=300000
MAX_CALLS=1800
POLICIES=("eia","gasSameSideFixed","ownMomentum","long","short","cash")


def dates():
    answer=[]
    for i in range(WEEKS):
        monday=START+timedelta(weeks=i)
        if monday==EXCLUDE:continue
        for wd in DAYS:
            answer.append({"week":i-(i>=19),"rank":i-(i>=19),
                           "day":monday+timedelta(days=wd),
                           "kind":"TUESDAY_CONTROL" if wd==1 else "THURSDAY_EIA"})
    assert len(answer)==76
    return answer


def calc(rows):
    priced=[r for r in rows if r["state"]=="ADAPTIVE_PRICED"]
    matched=[r for r in priced if "paired" in r]
    money=[r for r in matched if "money" in r]
    return {
        "scheduled":len(rows),
        "states":dict(Counter(r["state"] for r in rows)),
        "pricedAdaptive":len(priced),
        "pricedMatchedGross":len(matched),
        "pricedMatchedConditionalEur":len(money),
        "weeksWithPriced":len({r["week"] for r in priced}),
        "meanAdaptiveMidpointGrossBps":mean(r["markoutAdaptive"][0] for r in priced) if priced else None,
        "meanAdaptiveQuotedCrossingBpsBeforeFees":mean(r["markoutAdaptive"][1] for r in priced) if priced else None,
        "pairedMidpointGrossBps":{
            p:mean(r["paired"][p][0] for r in matched) if matched else None
            for p in POLICIES},
        "pairedCrossingBeforeFeesBps":{
            p:mean(r["paired"][p][1] for r in matched) if matched else None
            for p in POLICIES},
        "currentContractConditionalEur":{
            scenario:{p:round(sum(r["money"][scenario][p]["netEur"] for r in money),6)
                      for p in POLICIES}
            for scenario in ("central","adverse")},
        "conditionalAdverseIncrementVsFixedEur":round(
            sum(r["money"]["adverse"]["eia"]["netEur"]-
                r["money"]["adverse"]["gasSameSideFixed"]["netEur"]
                for r in money),6),
    }


def score(tape,contracts):
    out={}
    schedules=dates()
    for target in TARGETS:
        rows=[]
        for rec in schedules:
            day=rec["day"];key=day.isoformat()
            source=tape[key]
            gas=source["targets"]["NatGas"]
            t=source["targets"][target]
            basic={"week":rec["rank"],"kind":rec["kind"]}
            if gas["bars"] is None or gas["truncated"]:
                rows.append({**basic,"state":"MISSING_OR_TRUNCATED_GAS_M5_SOURCE"})
                continue
            if t["bars"] is None or t["truncated"]:
                rows.append({**basic,"state":"MISSING_OR_TRUNCATED_TARGET_M5_SOURCE"})
                continue
            event={"kind":rec["kind"],"week":rec["rank"],"day":day,
                   "gasBars":gas["bars"]}
            result=score_one(event,t)
            row={**basic,**result}
            if row["state"]=="ADAPTIVE_PRICED" and "paired" in row:
                sig=event_decision(day,gas["bars"])
                side=sig["side"]
                q=t["quote"]
                fx=source["fxQuotes"]
                base_q=q.get("10:50");fx0=fx.get("10:50")
                prices={
                    "eia":(side,sig["exitAt"]),
                    "gasSameSideFixed":(side,"12:05"),
                    "ownMomentum":(sign(bps(t["bars"],stamp(day,10,15),
                                            stamp(day,10,45))),"12:05"),
                    "long":(1,"12:05"),
                    "short":(-1,"12:05"),
                    "cash":(0,"12:05")}
                if base_q is not None and fx0 is not None and all(
                    q.get(v[1]) is not None and fx.get(v[1]) is not None
                    for v in prices.values()):
                    try:
                        current={}
                        for scenario,slip in (("central",0.5),("adverse",2.0)):
                            current[scenario]={}
                            for name,(direction,exit_key) in prices.items():
                                hh,mm=(int(a) for a in exit_key.split(":"))
                                if direction:
                                    no_swap(contracts[target],
                                            stamp(day,10,50),stamp(day,hh,mm))
                                start=tuple(D(x)/D(100000) for x in base_q)
                                end=tuple(D(x)/D(100000) for x in q[exit_key])
                                a=tuple(D(x)/D(100000) for x in fx0)
                                z=tuple(D(x)/D(100000) for x in fx[exit_key])
                                current[scenario][name]=current_eur(
                                    contracts[target],start,end,a,z,direction,slip)
                        row["money"]=current
                    except (Unpriced,ValueError) as ex:
                        row["moneyUnpricedReason"]=str(ex)[:100]
                else:
                    row["moneyUnpricedReason"]="MISSING_ASOF_ORIGINAL_EURUSD"
            rows.append(row)
        out[target]={
            "release":calc([x for x in rows if x["kind"]=="THURSDAY_EIA"]),
            "control":calc([x for x in rows if x["kind"]=="TUESDAY_CONTROL"]),
            "first19Released":calc([x for x in rows if x["kind"]=="THURSDAY_EIA" and x["week"]<19]),
            "last19Released":calc([x for x in rows if x["kind"]=="THURSDAY_EIA" and x["week"]>=19]),
            "independent":False,"qualification":False}
    return out


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    transport=StdlibCTraderTransport()
    calls=[];count=0
    tape={}
    details={}
    status={}

    def req(q,klass,empty=False):
        nonlocal count
        if count>=MAX_CALLS:
            raise RuntimeError("RNV1_2025_READ_ONLY_LIMIT")
        require_read_only_request(q)
        response=transport.request(q)
        count+=1
        if empty and type(response) is m.ProtoOAErrorRes and (
            response.errorCode=="NO_QUOTES" and
            response.ctidTraderAccountId==account):
            x=None
        elif (type(response) is klass and response.IsInitialized() and
              response.ctidTraderAccountId==account):
            x=response
        else:
            raise RuntimeError("RNV1_ORIGINAL_ACCOUNT_OR_SOURCE_ERROR")
        calls.append({"requestType":type(q).__name__,
            "request":base64.b64encode(q.SerializeToString()).decode(),
            "responseType":type(response).__name__,
            "response":base64.b64encode(response.SerializeToString()).decode()})
        return x

    def take_quote(symbol,day,hh,mm):
        at=stamp(day,hh,mm)
        points=[];truncated=False
        for side in (e.BID,e.ASK):
            resp=req(m.ProtoOAGetTickDataReq(
                ctidTraderAccountId=account,symbolId=ids[symbol],
                type=side,fromTimestamp=at-60000,toTimestamp=at),
                m.ProtoOAGetTickDataRes,True)
            if resp is None:
                points.append([])
            elif resp.hasMore:
                points.append([]);truncated=True
            else:
                points.append(decode_side(resp.tickData,at-60000,at))
        return None if truncated else paired(*points,at)

    try:
        account=authenticate(transport)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),
                   m.ProtoOATraderRes)
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                   m.ProtoOAAssetListRes)
        currency={a.assetId:a.name for a in assets.asset}
        if ("pepperstone" not in trader.trader.brokerName.casefold()
            or currency.get(trader.trader.depositAssetId)!="EUR"):
            raise RuntimeError("RNV1_NOT_ORIGINAL_PEPPERSTONE_EUR_ACCOUNT")
        roster=req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        active={x.symbolName:x for x in roster.symbol if x.enabled}
        if not all(x in active for x in MARKETS):
            raise RuntimeError("RNV1_ORIGINAL_FROZEN_MARKETS_MISSING")
        ids={}
        for name in MARKETS:
            light=active[name]
            if currency.get(light.quoteAssetId)!="USD":
                raise RuntimeError("RNV1_ORIGINAL_QUOTE_ASSET_UNKNOWN")
            ids[name]=light.symbolId
            detail=req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[light.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=ids[name]:
                raise RuntimeError("RNV1_ORIGINAL_CONTRACT_UNMATCHED")
            c=detail.symbol[0]
            details[name]=c
            status[name]={"currentMinimumVolumeWire":int(c.minVolume),
                          "currentMarginBuyEur":None,
                          "currentMarginSellEur":None,
                          "currentContractOnly":True}
            if c.minVolume>0:
                mrg=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                    symbolId=ids[name],volume=[c.minVolume]),
                    m.ProtoOAExpectedMarginRes)
                if mrg.HasField("moneyDigits") and len(mrg.margin)==1 and (
                    mrg.margin[0].volume==c.minVolume):
                    status[name]["currentMarginBuyEur"]=(
                        mrg.margin[0].buyMargin/10**mrg.moneyDigits)
                    status[name]["currentMarginSellEur"]=(
                        mrg.margin[0].sellMargin/10**mrg.moneyDigits)
        for rank,dayrec in enumerate(dates()):
            day=dayrec["day"]
            begin,end=stamp(day,9,25),stamp(day,12,10)
            rec={"rank":dayrec["rank"],"kind":dayrec["kind"],
                 "targets":{},"fxQuotes":{}}
            tape[day.isoformat()]=rec
            for target in TARGETS:
                answer=req(m.ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account,symbolId=ids[target],
                    period=e.M5,fromTimestamp=begin,toTimestamp=end),
                    m.ProtoOAGetTrendbarsRes,True)
                if answer is None:
                    bars=None;truncated=False
                elif answer.hasMore:
                    bars=None;truncated=True
                elif answer.period!=e.M5 or (answer.HasField("symbolId") and
                    answer.symbolId!=ids[target]):
                    raise RuntimeError("RNV1_ORIGINAL_M5_SOURCE_MISMATCH")
                else:
                    bars={t:close for _,t,_,_,_,close,_ in decode_bars(
                        answer.trendbar,begin-2*M5,end+2*M5,5)}
                    truncated=False
                rec["targets"][target]={"bars":bars,"truncated":truncated,"quote":{}}
            # All frozen clocks on ALL weekdays regardless of 2025 signal.
            for label,hh,mm in CLOCKS:
                rec["fxQuotes"][label]=take_quote("EURUSD",day,hh,mm)
                for target in TARGETS:
                    rec["targets"][target]["quote"][label]=take_quote(
                        target,day,hh,mm)
            if rank%18==17:
                print("RNV1_READONLY_NO_SCORING_DATE_PROGRESS",
                      rank+1,"OF",76,"ORIGINAL_CALLS",count,flush=True)
    finally:
        transport.close()

    # Source ALWAYS first, no outcomes evaluated before protected
    # original-account plaintext has been sealed on disk.
    original=json.dumps({
        "schema":"MXM_RNV1_ORIGINAL_2025_RESEARCH_SOURCE_PRIVATE",
        "run":run,"originalAccountVerified":True,
        "priorRNE1Frozen2026Run":43468457518,
        "requestResponseOriginalProtobuf":calls,
        "source":tape,
        "currentContractSnapshot":status,
        "postEntryOutcomesNotEvaluated":True,
    },sort_keys=True,separators=(",",":")).encode()
    cipher=seal_new(original,recipient,run)
    Path("rnv1-blind-2025-original-protected.v2.enc").write_bytes(cipher)

    # The EXACT previous RNE1 decision and outcome handlers are now used,
    # without editing or rerunning their original 2026 data.
    for rec in tape.values():
        for item in rec["targets"].values():
            if item["bars"] is not None:
                item["bars"]={int(k):int(v) for k,v in item["bars"].items()}
    result=score(tape,details)
    public={
        "schema":"MXM_RNV1_FROZEN_RNE1_2025_BLIND_PREDEVELOPMENT_STRESS",
        "run":int(run),"originalPepperstoneEurAccountVerified":True,
        "protocolSha256":sha256(Path(
            "research/RNV1_RNE1_2025_BLIND_HISTORY.md").read_bytes()).hexdigest(),
        "originalCipherSha256":sha256(cipher).hexdigest(),
        "originalPlaintextSha256":sha256(original).hexdigest(),
        "originalReadOnlyRequestsAfterAuth":count,
        "preselected39Weeks":WEEKS,"omittedEiaHolidayWeek":EXCLUDE.isoformat(),
        "releaseClocks":38,"tuesdayControlClocks":38,
        "originalRNE1EventExitExact":True,
        "previousOriginalRne1SourceUntouched":True,
        "twoFrozenOriginalTargets":list(TARGETS),
        "currentContractAsOf2026NotHistoric2025":True,
        "targetResults":result,
        "predevelopmentHistoricBackcastNotIndependentChronological":True,
        "registeredUnknownExposureTreatedAsExposed":True,
        "nativeFundedEur300Net":None,
        "brokerRealizedNetEur":None,
        "continuousFloatingDrawdownVerified":False,
        "hard21Proven":False,
        "ordersSubmitted":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Exact old RNE1 policy on blind EARLIER 2025 calendar, not 2026 holdout. Gross bid/ask crossing and current-tariff conditional EUR outcomes ONLY, missing quotes/fees reported. No independent postdevelopment confirmation, no real fills, no C# admitted ledger."
    }
    Path("rnv1-original-public-2025-stress.json").write_text(
        json.dumps(public,indent=2,allow_nan=False)+"\n")
    print("RNV1_PREDEVELOPMENT_HISTORIC_STRESS_DONE",
          json.dumps({"requests":count,"targets":{
            k:{"release":v["release"]["states"],
               "priced":v["release"]["pricedMatchedConditionalEur"],
               "adverse":v["release"]["currentContractConditionalEur"]["adverse"]["eia"]}
            for k,v in result.items()}}),flush=True)


if __name__=="__main__":
    main()
