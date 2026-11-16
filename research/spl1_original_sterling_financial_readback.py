"""SPL1 original BDP1+EURGBP/GBPUSD/EURUSD signed EUR economic readback.

All 52 weeks, 520 causal clocks and every ORIGINAL source/quote. No retired
predictor, order, Cloud, opportunistic score selection, fake fills or resets.
"""
from __future__ import annotations
import base64,json,math,os
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .custody import unseal_new
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .portfolio_discovery_source import audit as bdp_source_audit
from .guard import require_read_only_request
from .decode import decode_side,decode_bars
from .spl1_original_eurgbp_source import (
    PROTO,calendar,event_clocks,chunks,START,WEEKS,PERIOD_MS,
    LOOKBACK,MAX_AGE,sampled,stamp,SYMBOLS,ENTRY_OFFSET,EXIT_OFFSET)

OLD_RUN="41724643418"
OLD_SHA="e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370"
OLD_SOURCE=Path("bdp1-original/source.envelope.json")
OLD_PUBLIC=Path("bdp1-original/receipt.public.json")
NEW_SOURCE=Path("spl1-original/spl1-original-source.v2.enc")
NEW_PUBLIC=Path("spl1-public/spl1-original-source-public.json")
OUTPUT=Path("spl1-original-annual-sterling-eur-money.public.json")
SCENARIOS={"central":D("0.5"),"adverse":D("2.0"),"stress":D("4.0")}
POLICIES=("spl1","ownMomentum","crossAlways","long","short","cash")
PAIRED=("spl1","ownMomentum","crossAlways","long","short","cash")
SCALE=D(100000)


class MoneyUnknown(ValueError):
    pass


def need(test,reason):
    if not test:raise MoneyUnknown(reason)


def wire(x):
    q=getattr(m,x["requestType"])()
    a=getattr(m,x["responseType"])()
    q.ParseFromString(base64.b64decode(x["request"],validate=True))
    a.ParseFromString(base64.b64decode(x["response"],validate=True))
    require_read_only_request(q)
    need(q.IsInitialized() and a.IsInitialized(),"ORIGINAL_PROTOBUF_INVALID")
    return q,a


def source_bdp(private):
    raw=OLD_SOURCE.read_bytes()
    need(sha256(raw).hexdigest()==OLD_SHA,"BDP1_ORIGINAL_CIPHER_CHANGED")
    receipt=json.loads(OLD_PUBLIC.read_text())
    need(receipt["sha256"]==OLD_SHA and receipt["complete"]
         and str(receipt["runId"])==OLD_RUN,"BDP1_ORIGINAL_CUSTODY_NOT_BOUND")
    plain=unseal_new(raw,private,OLD_RUN)
    blob=json.loads(plain)
    plan=json.loads(Path("research/portfolio_discovery_protocol.json").read_text())
    audit=bdp_source_audit(blob,plan)
    need(blob["auditReceipt"]==audit and blob["pilotPassed"],
         "BDP1_ORIGINAL_RAW_READBACK_FAILED")
    prices={}
    for sym in ("GBPUSD","EURUSD"):
        rows=blob["bars"][sym]
        need(len(rows)>65000,"BDP1_AUTHENTIC_FX_M5_MISSING")
        priced={}
        for start,end,op,hi,lo,close,vol in rows:
            start=int(start);end=int(end);close=int(close)
            need(close>0 and end-start==PERIOD_MS and end not in priced,"BDP1_BAR_TIME_PRICE")
            priced[end]=close
        prices[sym]=priced
    return prices,sha256(plain).hexdigest(),audit


def source_spl1(private):
    encrypted=NEW_SOURCE.read_bytes()
    receipt=json.loads(NEW_PUBLIC.read_text())
    need(receipt["schema"]=="MXM_SPL1_ORIGINAL_SOURCE_ONLY_NO_FINANCIAL_SCORE"
         and receipt["protocolSha256"]==sha256(PROTO.read_bytes()).hexdigest()
         and receipt["sourceSealedBeforeScoring"] is True
         and receipt["originalSourceCipherSha256"]==sha256(encrypted).hexdigest(),
         "SPL1_ORIGINAL_NEW_SOURCE_PUBLIC_CUSTODY")
    run=str(receipt["originalRunId"])
    plain=unseal_new(encrypted,private,run)
    need(sha256(plain).hexdigest()==receipt["originalSourcePlainSha256"],
         "SPL1_ORIGINAL_PLAINTEXT_SHA_MISMATCH")
    body=json.loads(plain)
    need(body["schema"]=="MXM_SPL1_STERLING_ORIGINAL_ANNUAL_M5_BIDASK_V1"
         and body["sourceRun"]==run and body["readOnly"] is True
         and body["originalPepperstoneEur"] is True
         and body["brokerOrders"]==0 and body["cloudActivated"] is False
         and body["scopeBeforeFinance"] is True
         and len(body["rawCalls"])==receipt["originalReadOnlyCalls"]
         and body["fullOriginalCalendar"]==520,"SPL1_ORIGINAL_SOURCE_SCHEMA")
    decoded=[wire(x) for x in body["rawCalls"]]
    account=decoded[0][1].ctidTraderAccountId
    fp=sha256(f"ctrader-account:{account}".encode("ascii")).hexdigest()
    need(sha256(fp.encode("ascii")).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and all(getattr(q,"ctidTraderAccountId",account)==account and
                 getattr(a,"ctidTraderAccountId",account)==account
                 for q,a in decoded)
         and "pepperstone" in decoded[0][1].trader.brokerName.casefold(),
         "SPL1_ACCOUNT_BINDING_INVALID")
    currency={x.assetId:x.name for x in decoded[1][1].asset}
    trader=decoded[0][1].trader
    named={x.symbolName:x for x in decoded[2][1].symbol if x.enabled}
    need(currency[trader.depositAssetId]=="EUR"
         and all(s in named for s in SYMBOLS)
         and currency[named["GBPUSD"].quoteAssetId]=="USD"
         and currency[named["EURUSD"].baseAssetId]=="EUR"
         and currency[named["EURUSD"].quoteAssetId]=="USD"
         and currency[named["EURGBP"].quoteAssetId]=="GBP",
         "SPL1_CURRENCY_OR_ROSTER_NOT_ORIGINAL")
    symbols={}
    for sym,i in zip(SYMBOLS,(3,4,5)):
        q,a=decoded[i]
        need(type(q) is m.ProtoOASymbolByIdReq
             and list(q.symbolId)==[named[sym].symbolId]
             and len(a.symbol)==1 and a.symbol[0].symbolId==named[sym].symbolId,
             "SPL1_FIXED_SYMBOL_DETAIL_MISMATCH")
        symbols[sym]=a.symbol[0]
    q,margin=decoded[6]
    gbp=symbols["GBPUSD"]
    need(type(q) is m.ProtoOAExpectedMarginReq
         and q.symbolId==named["GBPUSD"].symbolId
         and list(q.volume)==[gbp.minVolume]
         and len(margin.margin)==1 and margin.margin[0].volume==gbp.minVolume
         and margin.HasField("moneyDigits"),"SPL1_INVALID_MONEY_WIRE")
    buy=D(margin.margin[0].buyMargin)/D(10)**margin.moneyDigits
    sell=D(margin.margin[0].sellMargin)/D(10)**margin.moneyDigits
    need(0<buy<=300 and 0<sell<=300
         and buy==D(str(body["buyMarginEur"]))
         and sell==D(str(body["sellMarginEur"]))
         and gbp.minVolume==body["contractVolume"],
         "SPL1_MINIMUM_CANNOT_BE_FINANCED")
    bars={}
    raw_index=7
    original_bars=[]
    for first,last in chunks():
        q,a=decoded[raw_index];raw_index+=1
        need(type(q) is m.ProtoOAGetTrendbarsReq
             and q.symbolId==named["EURGBP"].symbolId and q.period==e.M5
             and q.fromTimestamp==first and q.toTimestamp==last
             and isinstance(a,m.ProtoOAGetTrendbarsRes)
             and a.period==e.M5 and a.HasField("hasMore") and not a.hasMore,
             "SPL1_ORIGINAL_EURGBP_BAR_WIRE_INVALID")
        rows=decode_bars(a.trendbar,first-PERIOD_MS,last+PERIOD_MS,5)
        for row in rows:
            if first<=row[0] and row[1]<=last:original_bars.append(row)
    original_bars.sort()
    need(original_bars==body["originalEURGBPBars"],
         "SPL1_ORIGINAL_EURGBP_RAW_RECONSTRUCTION_CONFLICT")
    for x in original_bars:
        need(x[5]>0 and x[1] not in bars,"SPL1_DUPLICATE_EURGBP_BAR")
        bars[int(x[1])]=int(x[5])
    need(len(bars)==receipt["sourceCausalM5EURGBPRows"],
         "SPL1_EURGBP_CENSUS_CONFLICT")
    need(set(body["calendar"])==
         {f"{day.isoformat()}|{t}" for day,w,t in calendar()},"SPL1_EXACT_CALENDAR_MISMATCH")
    quotes={}
    pairs=Counter()
    for day,w,decision,entry,exit in event_clocks():
        k=f"{day.isoformat()}|{decision}"
        panel=body["calendar"][k]
        need(panel["decision"]==decision and panel["week"]==w
             and set(panel["quoteTimes"])==
                {f"{at}|{sym}" for at in (entry,exit) for sym in ("GBPUSD","EURUSD")},
             "SPL1_QUOTE_CLOCKS_NOT_CANONICAL")
        grouped={}
        for at in (entry,exit):
            for sym in ("GBPUSD","EURUSD"):
                note=panel["quoteTimes"][f"{at}|{sym}"]
                original=[]
                incomplete=False
                for side in (e.BID,e.ASK):
                    ix=raw_index;raw_index+=1
                    req,ans=decoded[ix]
                    need(note["rawIndices"]==[ix-1,ix] if side==e.ASK else True,
                         "SPL1_SOURCE_RAW_INDICES_CHANGED")
                    need(type(req) is m.ProtoOAGetTickDataReq
                         and req.ctidTraderAccountId==account
                         and req.symbolId==named[sym].symbolId
                         and req.type==side
                         and req.fromTimestamp==at-LOOKBACK
                         and req.toTimestamp==at,"SPL1_ORIGINAL_TICK_REQUEST_WRONG")
                    if isinstance(ans,m.ProtoOAErrorRes):
                        need(ans.errorCode=="NO_QUOTES","SPL1_BROKER_QUOTE_UNEXPECTED_ERROR")
                        values=[]
                    else:
                        need(type(ans) is m.ProtoOAGetTickDataRes
                             and ans.HasField("hasMore"),"SPL1_INCOMPLETE_QUOTE_PROTOBUF")
                        incomplete|=bool(ans.hasMore)
                        values=[] if ans.hasMore else decode_side(ans.tickData,at-LOOKBACK,at)
                    original.append(values)
                rebuilt=None if incomplete else sampled(*original,at)
                need(rebuilt==note["pair"] and incomplete==note["truncated"],
                     "SPL1_ORIGINAL_BIDASK_MISMATCH")
                grouped[(at,sym)]=rebuilt
                pairs["COMPLETE_"+sym if rebuilt else "UNKNOWN_"+sym]+=1
        quotes[(day.isoformat(),decision)]=grouped
    need(raw_index==len(decoded),"SPL1_ORIGINAL_REQUEST_COUNT_DIFFERENT")
    if body["swapFreeKnown"]:
        need(trader.HasField("swapFree") and bool(trader.swapFree)==body["swapFree"],
             "SPL1_ORIGINAL_SWAPFREE_ACCOUNT_CHANGED")
    return bars,quotes,gbp,buy,sell,trader,receipt,sha256(encrypted).hexdigest(),sha256(plain).hexdigest(),dict(pairs)


def feature(d,t,original,new):
    times=range(t-30*60000,t+1,PERIOD_MS)
    cross=[new.get(x) for x in times]
    own=[original.get(x) for x in times]
    if any(x is None or x<=0 for x in cross+own):
        return dict(state="SOURCE_UNKNOWN",sideL=None,sideM=None)
    # Two SEPARATE adjacent causal 15-minute intervals. t has closed M5 only.
    sign=lambda x:(x>0)-(x<0)
    leader=-sign(cross[3]-cross[0])
    momentum=sign(own[6]-own[3])
    state="SPL1_LEAD_CONFLICT" if leader and momentum and leader==-momentum else "NO_LEAD_CONFLICT"
    return dict(state=state,sideL=leader,sideM=momentum)


def direction(feat,policy):
    if feat["state"]=="SOURCE_UNKNOWN":return None
    if policy=="cash":return 0
    if policy=="spl1":return feat["sideL"] if feat["state"]=="SPL1_LEAD_CONFLICT" else 0
    if policy=="ownMomentum":return feat["sideM"]
    if policy=="crossAlways":return feat["sideL"]
    if policy=="long":return 1
    if policy=="short":return -1
    raise MoneyUnknown("SPL1_UNKNOWN_FIXED_POLICY")


def broker_fee_usd(c,units,px):
    fields=("minVolume","stepVolume","maxVolume","lotSize","preciseTradingCommissionRate",
            "preciseMinCommission","commissionType","minCommissionType")
    if not all(c.HasField(x) for x in fields):raise MoneyUnknown("CURRENT_TARIFF_NOT_ALL_FIELDS")
    min_units=D(c.minVolume)/100
    step=D(c.stepVolume)/100
    max_units=D(c.maxVolume)/100
    lot=D(c.lotSize)/100
    if not min_units<=units<=max_units or step<=0 or (units-min_units)%step!=0 or lot<=0:
        raise MoneyUnknown("BROKER_VOLUME_GRID_INVALID")
    rate=D(c.preciseTradingCommissionRate)/D(100000000)
    kind=int(c.commissionType)
    if kind==1:fee=rate*units*px/D(1000000)
    elif kind==2:fee=rate*units/lot
    elif kind==3:fee=D(c.preciseTradingCommissionRate)/D(100000)/D(100)*units*px
    elif kind==4:fee=rate*units/lot
    else:raise MoneyUnknown("CURRENT_COMMISSION_TYPE_NOT_USD")
    if int(c.minCommissionType)==1:
        if not c.HasField("minCommissionAsset") or c.minCommissionAsset!="USD":
            raise MoneyUnknown("COMMISSION_FLOOR_ASSET_NOT_USD")
    elif int(c.minCommissionType)!=2:raise MoneyUnknown("MIN_COMMISSION_TYPE_UNKNOWN")
    floor=D(c.preciseMinCommission)/D(100000000)
    if rate<0 or floor<0:raise MoneyUnknown("NEGATIVE_BROKER_FEE")
    return max(fee,floor)


def quote(pair,at):
    if pair is None:return None
    b,a=pair["bid"],pair["ask"]
    need(b["raw"]>0 and a["raw"]>=b["raw"]
         and 0<=at-b["at"]<=MAX_AGE and 0<=at-a["at"]<=MAX_AGE
         and b["ageMs"]==at-b["at"] and a["ageMs"]==at-a["at"],
         "ORIGINAL_PRICE_AGE_BIDASK_CROSSED")
    return D(b["raw"])/SCALE,D(a["raw"])/SCALE


def no_swap(c,trader,entry,exit):
    if trader.HasField("swapFree") and trader.swapFree:return True
    if not c.HasField("swapPeriod") or not c.HasField("swapTime"):
        raise MoneyUnknown("SWAP_CHARGE_CLOCK_UNKNOWN")
    if c.swapPeriod!=24 or not 0<=c.swapTime<1440:
        raise MoneyUnknown("SWAP_SCHEDULE_UNKNOWN")
    start=datetime.fromtimestamp(entry/1000,timezone.utc).date()
    end=datetime.fromtimestamp(exit/1000,timezone.utc).date()
    d=start
    while d<=end:
        t=int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp()*1000)+c.swapTime*60000
        if entry<t<=exit:raise MoneyUnknown("UNPRICED_SWAP_CHARGE_CROSSING")
        d+=timedelta(days=1)
    return True


def money(c,trader,quoted,entry,exit,side,slippage_bps):
    if side==0:return dict(netEur=0.0,grossEur=0.0,commissionEur=0.0,slippageEur=0.0,conversionFeeEur=0.0)
    no_swap(c,trader,entry,exit)
    p0=quote(quoted.get((entry,"GBPUSD")),entry)
    p1=quote(quoted.get((exit,"GBPUSD")),exit)
    f0=quote(quoted.get((entry,"EURUSD")),entry)
    f1=quote(quoted.get((exit,"EURUSD")),exit)
    if any(x is None for x in (p0,p1,f0,f1)):
        raise MoneyUnknown("MISSING_ORIGINAL_PRICE_OR_EUR_CONVERSION")
    if not c.HasField("pnlConversionFeeRate"):
        raise MoneyUnknown("P_AND_L_CONVERSION_FEE_UNKNOWN")
    volume=D(c.minVolume)/100
    px0=p0[1] if side>0 else p0[0]
    px1=p1[0] if side>0 else p1[1]
    usd=volume*D(side)*(px1-px0)
    gross=usd/(f1[1] if usd>=0 else f1[0])
    cost_fee=broker_fee_usd(c,volume,px0)/f0[0]+broker_fee_usd(c,volume,px1)/f1[0]
    rate=D(c.pnlConversionFeeRate)/D(10000)
    if rate<0 or rate>=1:raise MoneyUnknown("P_AND_L_CONVERSION_FEE_OUT_OF_RANGE")
    conv=abs(usd)*rate/f1[0]
    mid=(p0[0]+p0[1])/2
    slip_usd=volume*mid*slippage_bps/D(10000)
    slip=slip_usd/(D(2)*f0[0])+slip_usd/(D(2)*f1[0])
    net=gross-cost_fee-conv-slip
    return dict(netEur=float(net),grossEur=float(gross),
                commissionEur=float(cost_fee),slippageEur=float(slip),conversionFeeEur=float(conv))


def assessment(bars,cross,quotes,c,buy,sell,trader):
    cases=[];state_counts=Counter()
    for day,w,t,entry,exit in event_clocks():
        feat=feature(day,t,bars["GBPUSD"],cross)
        state_counts[feat["state"]]+=1
        cases.append(dict(day=day.isoformat(),week=w,decision=t,entry=entry,exit=exit,
                          feat=feat,panel=quotes[(day.isoformat(),t)]))
    # Same source, same entry/exit: paired comparisons on exactly SPL1 events.
    matched={}
    for scenario,slip in SCENARIOS.items():
        rows=[];complete=Counter();unknown=Counter()
        for case in cases:
            f=case["feat"]
            if f["state"]!="SPL1_LEAD_CONFLICT":continue
            outs={}
            for policy in PAIRED:
                side=direction(f,policy)
                try:
                    # Each matched policy has identical source and one minimum volume.
                    outs[policy]=money(c,trader,case["panel"],case["entry"],case["exit"],side,slip)
                except MoneyUnknown as err:
                    unknown[str(err)]+=1;outs=None;break
            if outs is not None:
                rows.append(dict(week=case["week"],out=outs,leader=f["sideL"]))
        matched[scenario]=dict(causalIntents=state_counts["SPL1_LEAD_CONFLICT"],
            completeMatchedIntents=len(rows),
            quoteOrTermUnknown=dict(unknown),
            pairedMoneyEur={
               p:dict(totalNetEur=round(sum(x["out"][p]["netEur"] for x in rows),6),
                      meanNetEur=round(sum(x["out"][p]["netEur"] for x in rows)/len(rows),6) if rows else None)
               for p in PAIRED},
            pairedDifferenceVsOwnMomentumEur=round(sum(
              x["out"]["spl1"]["netEur"]-x["out"]["ownMomentum"]["netEur"] for x in rows),6),
            pairedDifferenceVsCashEur=round(sum(x["out"]["spl1"]["netEur"] for x in rows),6),
            consecutiveWeeksWithMatchedData=len(set(x["week"] for x in rows)))
    whole={}
    for p in POLICIES:
        scenarios={}
        for name,slip in SCENARIOS.items():
            cash=D(300);peak=D(300);sampled_dd=D(0);gross=0.0;fees=0.0;slippage=0.0
            conv=0.0;count=0;intents=0;unknown_source=0;unknown_quote=0
            unpriced=0;underfunded=0;unknown_attribution=False;prior_exit_unresolved=False
            weekly=defaultdict(int);longs=0;shorts=0;mincash=D(300);max_margin=D(0)
            for case in cases:
                f=case["feat"]
                side=direction(f,p)
                if side is None:
                    unknown_source+=1
                    unknown_attribution=True
                    continue
                if side==0:continue
                intents+=1
                if prior_exit_unresolved:continue
                margin=buy if side>0 else sell
                if cash<=margin or cash<=0:
                    underfunded+=1;continue
                try:
                    value=money(c,trader,case["panel"],case["entry"],case["exit"],side,slip)
                except MoneyUnknown as err:
                    unknown_quote+=1
                    unknown_attribution=True
                    if str(err)=="MISSING_ORIGINAL_PRICE_OR_EUR_CONVERSION":
                        # With no certifiable exit, an existing modeled position
                        # could remain open: suspend all later entries.
                        prior_exit_unresolved=True
                    else:unpriced+=1
                    continue
                before=cash
                cash+=D(str(value["netEur"]))
                mincash=min(mincash,cash)
                peak=max(peak,cash)
                sampled_dd=max(sampled_dd,peak-cash)
                max_margin=max(max_margin,margin)
                count+=1;weekly[case["week"]]+=1
                longs+=int(side>0);shorts+=int(side<0)
                gross+=value["grossEur"];fees+=value["commissionEur"]
                slippage+=value["slippageEur"];conv+=value["conversionFeeEur"]
                if peak-cash>D(90):prior_exit_unresolved=True
            scenarios[name]=dict(initialEur=300,
                scenarioFinalEur=round(float(cash),6) if not unknown_attribution and not prior_exit_unresolved else None,
                scenarioNetEur=round(float(cash-D(300)),6) if not unknown_attribution and not prior_exit_unresolved else None,
                observedPricedSubsetNetEur=round(float(cash-D(300)),6),
                originalGrossEur=round(gross,6),currentFeeEur=round(fees,6),
                extraModeledSlippageEur=round(slippage,6),originalCurrentConversionFeeEur=round(conv,6),
                actualClosedModelTrips=count,longs=longs,shorts=shorts,
                sourceUnknown=unknown_source,intents=intents,
                missingOrUnpricedOriginalQuotes=unknown_quote,unpricedContractTerms=unpriced,
                rejectedUnderCurrentMinMargin=underfunded,
                sourceUnknownPreventsEntireCalendarNet=unknown_attribution,
                suspendAfterUnresolvedExitOrRisk=prior_exit_unresolved,
                maxCurrentMinimumDirectionalMarginEur=round(float(max_margin),6),
                observedExitOnlyEquityDrawdownLowerBoundEur=round(float(sampled_dd),6),
                weeklyModelFundedTripCounts=[weekly[w] for w in range(WEEKS)],
                weeksWithAnyModelTrip=sum(weekly[w]>0 for w in range(WEEKS)),
                hard21QualifyingWeeks=sum(weekly[w]>=21 for w in range(WEEKS)),
                floatingDDContinuouslyCertified=False)
        whole[p]=scenarios
    return dict(calendarScheduledClocks=len(cases),scheduledWeeks=WEEKS,
        observationStates=dict(state_counts),matchedSameClock=matched,
        fullCalendarIndependentEUR300Books=whole,
        historicalCostContinuityCertified=False,realBrokerNetEur=None,
        independentFutureChronology=False,cloudRestartParityCertified=False,
        onePositionMaxSimultaneous=True,systemHard21NotFamilyGate=True)


def main():
    private=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"SPL1_CUSTODY_SECRET_REQUIRED")
    bdp,bdp_plain,bdp_audit=source_bdp(private)
    eur,quotes,c,buy,sell,trader,pub,cipher,plain,quote_counts=source_spl1(private)
    score=assessment(bdp,eur,quotes,c,buy,sell,trader)
    output=dict(schema="MXM_SPL1_ORIGINAL_STERLING_RECURRENT_CROSS_EUR_ECONOMICS_V1",
       originalProtocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
       oldBDP1RunId=int(OLD_RUN),oldBDP1SourceCipherSha256=OLD_SHA,
       oldBDP1SourcePlainSha256=bdp_plain,originalBDP1SourceAudit=bdp_audit,
       newSPL1RunId=pub["originalRunId"],newOriginalSourceCipherSha256=cipher,
       newOriginalSourcePlainSha256=plain,originalBrokerRequestCount=pub["originalReadOnlyCalls"],
       sourceCoverage=pub["quoteCoverage"],originalQuoteRebuiltCensus=quote_counts,
       sourceHistoryEURGBPBars=len(eur),oldGBPUSDM5=len(bdp["GBPUSD"]),
       oldEURUSDM5=len(bdp["EURUSD"]),
       onePepperstoneOriginalEURAccount=True,
       currentMinVolume=c.minVolume,
       currentGBPUSDBuyMarginEur=float(buy),currentGBPUSDSellMarginEur=float(sell),
       originalSourceSealedBeforeOutcomes=True,
       evaluated=score,
       resultClass="CONDITIONAL_AUTHENTIC_BIDASK_CURRENT_TARIFF_EUR_EXPOSED_DEVELOPMENT",
       noRealBrokerFills=True,noFullHistoricalTariffCertification=True,
       nativeCSharpFullFundedParity=False,orders=0,cloudActivated=False,
       fullYearOriginalFinancialDevelopment=True,
       independentPostDevelopmentConfirmation=False,
       disclosure="True original finance quote-matched signed EUR scenaria at broker current contract, no actual orders/fills; calendar source missingness and unfinished books shown; floating DD is sampled exit-only lower-bound, continuous unsettled equity unknown. Closed studies' source-only original audit does not execute any closed forecasting model.")
    OUTPUT.write_text(json.dumps(output,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("SPL1_ORIGINAL_EUR_FINANCIAL_SCORING_COMPLETE",
        json.dumps({"states":score["observationStates"],
                    "matchedAdverse":score["matchedSameClock"]["adverse"]["pairedMoneyEur"],
                    "fullCalendarAdverse":{
                      p:score["fullCalendarIndependentEUR300Books"][p]["adverse"]["scenarioNetEur"]
                      for p in POLICIES}}),flush=True)

if __name__=="__main__":
    main()
