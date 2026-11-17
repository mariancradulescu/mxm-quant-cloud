"""IVP1 authentic source-only VIX→US500 temporally ordered presignal preflight.
50 frozen clocks. ZERO return scoring, zero orders, zero cloud activation.
"""
from __future__ import annotations
import base64,json,os,statistics
from collections import Counter
from datetime import date,datetime,timedelta,time,timezone
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path

from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .decode import decode_bars,decode_side,need
from .guard import require_read_only_request
from .custody_new import checked_public
from .custody import seal_new
from .rne1_source_financial_preflight import fee_usd,Unpriced

PROTO=Path("research/IVP1_VIX_US500_TEMPORAL_OPTIONS_RISK_PRESOURCE_20261117.md")
PILOT_START=date(2026,11,2)
FULL_START=date(2026,8,17)
CLOCK_HOURS=(14,15,16,17,18)
BAR=300000
MIN=60000
AGE=20000
MAX_CALLS=800
SYMS=("VIX","US500","EURUSD")

def utc(d,h):
    return int(datetime.combine(d,time(h),timezone.utc).timestamp()*1000)

def calendar(start=FULL_START,days=89):
    for delta in range(days):
        d=start+timedelta(days=delta)
        if d.weekday()<5:
            for h in CLOCK_HOURS:
                yield d,utc(d,h)

def pilot_calendar():
    return list(calendar(PILOT_START,12))

def pair(bids,asks,at):
    b=[x for x in bids if x[0]<=at and x[1]>0]
    a=[x for x in asks if x[0]<=at and x[1]>0]
    if not b or not a or b[-1][0]<at-AGE or a[-1][0]<at-AGE:
        return None
    if b[-1][1]>a[-1][1]:return None
    return [list(b[-1]),list(a[-1])]

def sign(a,b):
    return (a>b)-(a<b)

def expected_bar_ends(sym,t):
    if sym=="VIX":
        return [t-j*MIN for j in (35,30,25,20,15)]
    if sym=="US500":
        return [t-j*MIN for j in (15,10,5,0)]
    raise ValueError("IVP1_FIXED_SOURCE_ONLY")

def validate_current(c):
    fields=("minVolume","stepVolume","maxVolume","lotSize",
            "preciseTradingCommissionRate","preciseMinCommission",
            "commissionType","minCommissionType",
            "pnlConversionFeeRate","swapTime","swapPeriod")
    need(all(c.HasField(q) for q in fields),"IVP1_MISSING_CURRENT_TARGET_CONTRACT")
    need(c.tradingMode==0 and c.minVolume>0 and c.stepVolume>0 and
         c.maxVolume>=c.minVolume and c.lotSize>0
         and c.swapPeriod==24 and 0<=c.swapTime<1440
         and 0<=c.pnlConversionFeeRate<10000,
         "IVP1_INVALID_CURRENT_TARGET_CONTRACT")
    try:
        fee_usd(c,D(c.minVolume)/100,D(5000))
    except Unpriced as exc:
        raise ValueError("IVP1_ORIGINAL_TARGET_COST_UNKNOWN") from exc

def main():
    need(PROTO.is_file() and "PRESOURCE" in PROTO.read_text(),
         "IVP1_FROZEN_PROTOCOL_NOT_MERGED")
    run=os.environ["GITHUB_RUN_ID"]
    pub=checked_public(Path("new-recipient-output"),run)
    transport=StdlibCTraderTransport()
    raw=[]
    def query(q,kind,allow_no_quotes=False):
        need(len(raw)<MAX_CALLS,"IVP1_READONLY_REQUEST_CAP")
        require_read_only_request(q)
        ans=transport.request(q)
        if type(ans) is m.ProtoOAErrorRes and allow_no_quotes:
            need(ans.errorCode=="NO_QUOTES" and ans.ctidTraderAccountId==acct,
                 "IVP1_BROKER_UNEXPECTED_PRICE_ERROR")
            response=None
        else:
            need(type(ans) is kind and ans.IsInitialized()
                 and ans.ctidTraderAccountId==acct,
                 "IVP1_ORIGINAL_ACCOUNT_RESPONSE_INVALID")
            response=ans
        raw.append(dict(requestType=type(q).__name__,
                        responseType=type(ans).__name__,
                        request=base64.b64encode(q.SerializeToString()).decode(),
                        response=base64.b64encode(ans.SerializeToString()).decode()))
        return response,len(raw)-1
    counts=Counter()
    rows=[]
    goodbar=[0,0];goodquotes=[0,0];validdir=[0,0];different=[0,0]
    spreads=[];pastmoves=[];fees=[]
    try:
        acct=authenticate(transport)
        trader,_=query(m.ProtoOATraderReq(ctidTraderAccountId=acct),m.ProtoOATraderRes)
        assets,_=query(m.ProtoOAAssetListReq(ctidTraderAccountId=acct),m.ProtoOAAssetListRes)
        roster,_=query(m.ProtoOASymbolsListReq(ctidTraderAccountId=acct,
              includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        names={x.assetId:x.name for x in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and names.get(trader.trader.depositAssetId)=="EUR",
             "IVP1_WRONG_ORIGINAL_BROKER_OR_ACCOUNT")
        listed={x.symbolName:x for x in roster.symbol if x.enabled}
        need(all(s in listed for s in SYMS),
             "IVP1_VIX_OR_US500_OR_EURUSD_NOT_ENABLED")
        need(names.get(listed["US500"].quoteAssetId)=="USD"
             and names.get(listed["EURUSD"].baseAssetId)=="EUR"
             and names.get(listed["EURUSD"].quoteAssetId)=="USD",
             "IVP1_US500_TO_EUR_CONVERSION_UNKNOWN")
        ids={s:listed[s].symbolId for s in SYMS}
        contracts={}
        for s in SYMS:
            detail,_=query(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=acct,symbolId=[ids[s]]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==ids[s],
                 "IVP1_UNVERIFIED_ORIGINAL_CONTRACT")
            contracts[s]=detail.symbol[0]
        c=contracts["US500"]
        validate_current(c)
        unit=D(c.minVolume)/100
        rm,_=query(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=acct,
           symbolId=ids["US500"],volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
        need(rm.HasField("moneyDigits") and len(rm.margin)==1
             and rm.margin[0].volume==c.minVolume,
             "IVP1_TWO_SIDE_ORIGINAL_MARGIN_UNKNOWN")
        sc=D(10)**rm.moneyDigits
        margins=[D(rm.margin[0].buyMargin)/sc,D(rm.margin[0].sellMargin)/sc]
        feasible=all(D(0)<x<=D(210) for x in margins)
        for d,t in pilot_calendar():
            half=0 if d<date(2026,11,9) else 1
            rec=dict(day=d.isoformat(),decision=t,source={},futureCoverage={})
            past={}
            for s in ("VIX","US500"):
                ends=expected_bar_ends(s,t)
                beg=min(ends)-BAR;end=max(ends)
                ans,idx=query(m.ProtoOAGetTrendbarsReq(
                     ctidTraderAccountId=acct,symbolId=ids[s],period=e.M5,
                     fromTimestamp=beg,toTimestamp=end),
                     m.ProtoOAGetTrendbarsRes,True)
                truncated=ans is not None and (not ans.HasField("hasMore") or ans.hasMore)
                closes=None
                if ans is not None and not truncated:
                    decoded=decode_bars(ans.trendbar,beg,end,5)
                    byend={a[1]:a[5] for a in decoded}
                    if all(k in byend and byend[k]>0 for k in ends):
                        closes=[int(byend[k]) for k in ends]
                rec["source"][s]=dict(rawIndex=idx,
                    complete=closes is not None,truncated=bool(truncated))
                counts["bars_"+s+"_good" if closes else "bars_"+s+"_missing"]+=1
                past[s]=closes
            feature_known=all(past[s] is not None for s in ("VIX","US500"))
            rec["causalFeatureComplete"]=feature_known
            if feature_known:
                goodbar[half]+=1
                v=sign(past["VIX"][-1],past["VIX"][0])
                own=sign(past["US500"][-1],past["US500"][0])
                lead=-v
                rec["vixDirection"]=lead
                rec["ownDirection"]=own
                if lead and own:
                    validdir[half]+=1
                    if lead!=own:different[half]+=1
                pastmoves.append(10000*abs(
                    D(past["US500"][-1]-past["US500"][0])/D(past["US500"][0])))
            allgood=True
            for tag,at in (("entry",t+90000),
                           ("middle",t+16*MIN+30000),
                           ("exit",t+31*MIN+30000)):
                rec["futureCoverage"][tag]={}
                # 15min /30min holding marks at +90s,+15m90s,+30m90s
                # correct middle time is t+16m30s, exit t+31m30s
                for s in ("US500","EURUSD"):
                    values=[];indices=[];truncated=False
                    for typ in (e.BID,e.ASK):
                        ans,idx=query(m.ProtoOAGetTickDataReq(
                            ctidTraderAccountId=acct,symbolId=ids[s],type=typ,
                            fromTimestamp=at-60000,toTimestamp=at),
                            m.ProtoOAGetTickDataRes,True)
                        indices.append(idx)
                        if ans is None:vx=[]
                        elif not ans.HasField("hasMore") or ans.hasMore:
                            truncated=True;vx=[]
                        else:vx=decode_side(ans.tickData,at-60000,at)
                        values.append(vx)
                    z=None if truncated else pair(*values,at)
                    ok=z is not None
                    rec["futureCoverage"][tag][s]=dict(valid=ok,
                        truncated=truncated,rawIndices=indices)
                    counts["quote_"+s+"_valid" if ok else "quote_"+s+"_missing"]+=1
                    allgood&=ok
                    if tag=="entry" and s=="US500" and ok:
                        bid=D(z[0][1])/100000;ask=D(z[1][1])/100000
                        mid=(bid+ask)/2
                        spreads.append(10000*(ask-bid)/mid)
                        try:
                            fee=fee_usd(c,unit,mid)
                            fees.append(D(20000)*fee/(unit*mid))
                        except Unpriced:counts["unpricedCurrentFees"]+=1
            if allgood:goodquotes[half]+=1
            rows.append(rec)
    finally:
        transport.close()
    need(len(rows)==50 and len(raw)==707,
         "IVP1_FIXED_ORIGINAL_50_CLOCK_PROTOBUF_COUNT_MISMATCH")
    cost=None
    if spreads and fees and pastmoves:
        cost=dict(priorUs50015mAbsMedianBps=float(statistics.median(pastmoves)),
                  originalEntrySpreadMedianBps=float(statistics.median(spreads)),
                  currentMinimumTwoSideFeeBps=float(statistics.median(fees)),
                  adverseSlippageRoundtripBps=2.0)
        cost["passes"]=(cost["priorUs50015mAbsMedianBps"]>
                         cost["originalEntrySpreadMedianBps"]+
                         cost["currentMinimumTwoSideFeeBps"]+2)
    gates=dict(
        originalVixAndTargetContractAndMargins=feasible,
        causalStrictlyPriorBars=sum(goodbar)>=45 and min(goodbar)>=21,
        originalUs500EurAllThreeQuotes=sum(goodquotes)>=45 and min(goodquotes)>=21,
        nondegenerateVixVersusOwn=sum(validdir)>=40 and sum(different)>=10,
        pastPriceAmplitudeAboveIndicativeCost=bool(cost and cost["passes"])
    )
    verdict=("IVP1_PILOT_ALL_SOURCE_GATES_PASS_NO_PAYOFF"
        if all(gates.values()) else "IVP1_PRESOURCE_STOP_NO_OUTCOME_SCORING")
    plain=json.dumps(dict(schema="MXM_IVP1_FIRST_ORIGINAL_PILOT_RAW_PROTOS_V1",
       runId=run,originalPepperstoneEurScopeView=True,noForwardReturnsScored=True,
       ordersSubmitted=0,cloudActivated=False,raw=raw,rows=rows,
       currentTargetContractMinimumVolumeRaw=c.minVolume,
       currentTargetBuySellMarginEur=[str(x) for x in margins],
       actualPresignalSourceGateVerdict=verdict),
       sort_keys=True,separators=(",",":")).encode()
    sealed=seal_new(plain,pub,run)
    Path("ivp1-original-pilot-source.v2.enc").write_bytes(sealed)
    receipt=dict(schema="MXM_IVP1_ORIGINAL_PRESOURCE_NO_PAYOFF_PILOT_V1",
      runId=int(run),frozenProtocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
      sealedOriginalSourceSha256=sha256(sealed).hexdigest(),
      sealedOriginalPlainSha256=sha256(plain).hexdigest(),
      originalScopeViewRequests=len(raw),scheduledDecisionClocks=50,
      predecisionBarsComplete=sum(goodbar),predecisionByFiveDayHalf=goodbar,
      fullyPricedEntryMidExitClocks=sum(goodquotes),fullQuotesByFiveDayHalf=goodquotes,
      twoNonzeroPredictors=sum(validdir),discordantVixOwnDirections=sum(different),
      currentOriginalMinimumVolumeRaw=c.minVolume,
      currentOriginalBuySellMarginEur=[float(q) for q in margins],
      priceAvailability=dict(counts),costScale=cost,sourceGates=gates,
      verdict=verdict,noCausalFutureOutcomeOrTradeNetScored=True,
      actualExecutionNetEur=None,fundedNativeNetEur=None,
      sealedBeforeEconomicScoring=True,ordersSubmitted=0,cloudActivated=False)
    Path("ivp1-original-pilot-public.json").write_text(
       json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("IVP1_AUTHENTIC_ORIGINAL_PRESOURCE_ONLY",
      json.dumps(dict(verdict=verdict,gates=gates,coverage=goodbar,
      quotes=goodquotes,different=different,cost=cost)),flush=True)

if __name__=="__main__":
    main()
