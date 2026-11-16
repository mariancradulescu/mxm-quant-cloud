"""CXL1 source-only ex-ante weekday crypto liquidity feasibility, NO future payoff.
50 prespecified timestamps, raw encrypted original account protobuf, public counters.
No live/demo orders, no cloud, no prior closed strategy execution.
"""
from __future__ import annotations
import base64,json,os,math,statistics
from collections import Counter
from datetime import date,datetime,time,timedelta,timezone
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

PROTOCOL=Path("research/CXL1_BTC_ETH_CAUSAL_PRICE_DISCOVERY_PRESOURCE_20261116.md")
START=date(2026,8,17)
PILOT_START=date(2026,11,2)
HOURS=((8,30),(10,30),(12,30),(14,30),(16,30))
M5=300000
DAY=86400000
DECISION_DELAY=1500
EXIT_DELAY=1800000
AGE=20000
BACK=60000
SYMS=("BTCUSD","ETHUSD","EURUSD")
MAX_CALLS=507

def clock(d,h,m):
    return int(datetime.combine(d,time(h,m),timezone.utc).timestamp()*1000)

def calendar(start=START,days=65):
    for day_offset in range(days):
        d=start+timedelta(days=day_offset)
        if d.weekday()>=5:continue
        for h,mi in HOURS:
            yield d,clock(d,h,mi)

def pilot_calendar():
    return list(calendar(PILOT_START,12))

def fresh(bids,asks,at):
    b=[x for x in bids if x[0]<=at and x[1]>0]
    a=[x for x in asks if x[0]<=at and x[1]>0]
    if not b or not a:return None
    bid=b[-1];ask=a[-1]
    if bid[0]<at-AGE or ask[0]<at-AGE or bid[1]>ask[1]:return None
    return [list(bid),list(ask)]

def crypto_features(closes):
    if len(closes)!=289 or any(v is None or v<=0 for v in closes):return None
    ret=[math.log(closes[i]/closes[i-3]) for i in range(3,len(closes),3)]
    if len(ret)!=96:return None
    scale=statistics.median(abs(x) for x in ret)
    if not math.isfinite(scale) or scale<=0:return None
    return (ret[-1]/scale,abs(ret[-1])*10000)

def classification(btc,eth):
    if btc is None or eth is None:return None
    b=btc[0];z=eth[0]
    if abs(b)<=abs(z) or b==0:return 0
    return 1 if b>0 else -1

def minimum_contract(c):
    require=("minVolume","stepVolume","maxVolume","lotSize",
             "preciseTradingCommissionRate","preciseMinCommission",
             "commissionType","minCommissionType","pnlConversionFeeRate",
             "swapTime","swapPeriod")
    need(all(c.HasField(k) for k in require),"CXL1_CONTRACT_FIELD_UNKNOWN")
    need(c.minVolume>0 and c.stepVolume>0 and c.maxVolume>=c.minVolume
         and c.lotSize>0 and c.tradingMode==0 and c.swapPeriod==24
         and 0<=c.swapTime<1440,"CXL1_CURRENT_CONTRACT_NOT_ELIGIBLE")
    need(0<=c.pnlConversionFeeRate<10000,
         "CXL1_CONVERSION_FEE_UNKNOWN")
    # Do not assume a zero current commission if metadata is incomplete.
    u=D(c.minVolume)/100
    try:
        f=fee_usd(c,u,D(2500))
    except Unpriced as exc:
        raise ValueError("CXL1_CURRENT_FEE_NOT_CERTIFIED") from exc
    need(f>=0,"CXL1_CURRENT_FEE_NEGATIVE")
    return u

def main():
    need(PROTOCOL.exists() and "FROZEN" in PROTOCOL.read_text(),
         "CXL1_PRESOURCE_PROTOCOL_ABSENT")
    run=os.environ["GITHUB_RUN_ID"]
    public=checked_public(Path("new-recipient-output"),run)
    transport=StdlibCTraderTransport()
    raw=[]
    def query(req,kind,missing=False):
        need(len(raw)<MAX_CALLS,"CXL1_PILOT_ORIGINAL_BROKER_CALL_CAP")
        require_read_only_request(req)
        res=transport.request(req)
        if type(res) is m.ProtoOAErrorRes and missing:
            need(res.errorCode=="NO_QUOTES" and res.ctidTraderAccountId==acct,
                 "CXL1_ORIGINAL_UNEXPECTED_BROKER_ERROR")
            out=None
        else:
            need(type(res) is kind and res.IsInitialized()
                 and res.ctidTraderAccountId==acct,
                 "CXL1_SOURCE_ACCOUNT_OR_PROTOBUF_INVALID")
            out=res
        raw.append(dict(requestType=type(req).__name__,
            responseType=type(res).__name__,
            request=base64.b64encode(req.SerializeToString()).decode(),
            response=base64.b64encode(res.SerializeToString()).decode()))
        return out,len(raw)-1
    obs=Counter()
    valid_signal_by_half=Counter()
    valid_quote_by_half=Counter()
    valid_pre_by_half=Counter()
    distinct_by_half=Counter()
    eth_abs=[]
    spreads=[]
    fee_bps=[]
    rows=[]
    try:
        acct=authenticate(transport)
        tr,_=query(m.ProtoOATraderReq(ctidTraderAccountId=acct),m.ProtoOATraderRes)
        asset,_=query(m.ProtoOAAssetListReq(ctidTraderAccountId=acct),m.ProtoOAAssetListRes)
        roster,_=query(m.ProtoOASymbolsListReq(ctidTraderAccountId=acct,
            includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        names={x.assetId:x.name for x in asset.asset}
        need("pepperstone" in tr.trader.brokerName.casefold()
             and names.get(tr.trader.depositAssetId)=="EUR",
             "CXL1_NOT_ORIGINAL_EUR_PEPPERSTONE")
        fixed={x.symbolName:x for x in roster.symbol if x.enabled}
        need(all(s in fixed for s in SYMS),"CXL1_FIXED_ROSTER_UNAVAILABLE")
        need(all(names.get(fixed[x].quoteAssetId)=="USD" for x in ("BTCUSD","ETHUSD"))
             and names.get(fixed["EURUSD"].quoteAssetId)=="USD"
             and names.get(fixed["EURUSD"].baseAssetId)=="EUR",
             "CXL1_FIXED_QUOTE_CURRENCY")
        ids={name:fixed[name].symbolId for name in SYMS}
        contracts={}
        for sym in SYMS:
            z,_=query(m.ProtoOASymbolByIdReq(ctidTraderAccountId=acct,
                symbolId=[ids[sym]]),m.ProtoOASymbolByIdRes)
            need(len(z.symbol)==1 and z.symbol[0].symbolId==ids[sym],
                 "CXL1_BROKER_CONTRACT_CHANGED")
            contracts[sym]=z.symbol[0]
        unit=minimum_contract(contracts["ETHUSD"])
        z,_=query(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=acct,
            symbolId=ids["ETHUSD"],volume=[contracts["ETHUSD"].minVolume]),
            m.ProtoOAExpectedMarginRes)
        need(z.HasField("moneyDigits") and len(z.margin)==1
             and z.margin[0].volume==contracts["ETHUSD"].minVolume,
             "CXL1_CURRENT_USD_ETH_MARGIN_UNKNOWN")
        scale=D(10)**z.moneyDigits
        margins=[D(z.margin[0].buyMargin)/scale,
                 D(z.margin[0].sellMargin)/scale]
        terms_ok=(min(margins)>0 and max(margins)<=D(210))
        c=contracts["ETHUSD"]
        for d,t in pilot_calendar():
            j=0 if d<date(2026,11,9) else 1
            row=dict(day=d.isoformat(),t=t,bar={},quotes={})
            features={}
            for sym in ("BTCUSD","ETHUSD"):
                start=t-DAY-M5
                ans,idx=query(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=acct,
                    symbolId=ids[sym],period=e.M5,fromTimestamp=start,
                    toTimestamp=t),m.ProtoOAGetTrendbarsRes,True)
                truncated=ans is not None and (not ans.HasField("hasMore") or ans.hasMore)
                closes=None
                if ans is not None and not truncated:
                    data=decode_bars(ans.trendbar,start,t,5)
                    by_end={int(a[1]):int(a[5]) for a in data}
                    expected=[t-DAY+i*M5 for i in range(289)]
                    if all(q in by_end and by_end[q]>0 for q in expected):
                        closes=[by_end[q] for q in expected]
                feature=crypto_features(closes) if closes else None
                row["bar"][sym]=dict(rawIndex=idx,complete=closes is not None,
                                     truncated=bool(truncated))
                features[sym]=feature
                obs["completeBars_"+sym if closes is not None else "missingBars_"+sym]+=1
            pre=all(features[s] is not None for s in ("BTCUSD","ETHUSD"))
            side=classification(features["BTCUSD"],features["ETHUSD"])
            row["featureComplete"]=pre
            row["leadDirection"]=side
            row["ownEthSign"]=None if not pre else (
                1 if features["ETHUSD"][0]>0 else -1 if features["ETHUSD"][0]<0 else 0)
            if pre:
                valid_pre_by_half[j]+=1
                eth_abs.append(features["ETHUSD"][1])
                if side:
                    valid_signal_by_half[j]+=1
                    if row["ownEthSign"]!=side:distinct_by_half[j]+=1
            # Predeclared future mark availability is inspected ONLY as source
            # support, never as P&L; the sealed raw may contain quote prices.
            for kind,at in (("entry",t+DECISION_DELAY),
                            ("exit",t+EXIT_DELAY+DECISION_DELAY)):
                row["quotes"][kind]={}
                for sym in ("ETHUSD","EURUSD"):
                    values=[];indices=[];truncated=False
                    for side_kind in (e.BID,e.ASK):
                        ans,idx=query(m.ProtoOAGetTickDataReq(ctidTraderAccountId=acct,
                            symbolId=ids[sym],type=side_kind,
                            fromTimestamp=at-BACK,toTimestamp=at),
                            m.ProtoOAGetTickDataRes,True)
                        indices.append(idx)
                        if ans is None:side_values=[]
                        elif not ans.HasField("hasMore") or ans.hasMore:
                            truncated=True;side_values=[]
                        else:side_values=decode_side(ans.tickData,at-BACK,at)
                        values.append(side_values)
                    mark=None if truncated else fresh(*values,at)
                    row["quotes"][kind][sym]=dict(valid=mark is not None,
                                                  truncated=truncated,rawIndices=indices)
                    obs["quote_"+sym+"_valid" if mark else "quote_"+sym+"_missing"]+=1
                    if kind=="entry" and sym=="ETHUSD" and mark:
                        bid=D(mark[0][1])/100000
                        ask=D(mark[1][1])/100000
                        mid=(bid+ask)/2
                        s=(ask-bid)/mid*D(10000)
                        try:
                            fee=fee_usd(c,unit,mid)
                            fee_bps.append(float(2*fee/(unit*mid)*D(10000)))
                            spreads.append(float(s))
                        except Unpriced:
                            obs["unpricedFee"]+=1
            if all(row["quotes"][kind][sym]["valid"]
                   for kind in ("entry","exit") for sym in ("ETHUSD","EURUSD")):
                valid_quote_by_half[j]+=1
            rows.append(row)
    finally:
        transport.close()
    need(len(rows)==50 and len(raw)==507,"CXL1_PILOT_FIXED_REQUEST_COUNT")
    cost_scale=None
    if eth_abs and spreads and fee_bps:
        cost_scale=dict(priorMedianEth15mBps=statistics.median(eth_abs),
                        originalMedianEthQuoteSpreadBps=statistics.median(spreads),
                        originalMedianMinFeeRoundtripBps=statistics.median(fee_bps),
                        adverseSlippageBps=2)
        cost_scale["passes"]=(cost_scale["priorMedianEth15mBps"] >
            cost_scale["originalMedianEthQuoteSpreadBps"]+
            cost_scale["originalMedianMinFeeRoundtripBps"]+2)
    gates=dict(
        currentOriginalContractAndMargin=bool(terms_ok and
            all(c.HasField(k) for k in ("pnlConversionFeeRate","swapPeriod","swapTime"))),
        predecisionCausalBars=sum(valid_pre_by_half.values())>=44
            and all(valid_pre_by_half[i]>=20 for i in (0,1)),
        genuineFinancingEndpoints=sum(valid_quote_by_half.values())>=42
            and all(valid_quote_by_half[i]>=19 for i in (0,1)),
        rawNondegenerateLeadership=sum(valid_signal_by_half.values())>=12
            and sum(distinct_by_half.values())>=4,
        predecisionPriceMovementExceedsActualIndicativeCost=bool(
            cost_scale and cost_scale["passes"])
    )
    verdict="CXL1_PILOT_SOURCE_GATES_PASS_NO_OUTCOME_SCORING" if all(gates.values()) else (
        "CXL1_PRESOURCE_STOP_NO_OUTCOME_SCORING")
    plain=json.dumps(dict(schema="MXM_CXL1_ORIGINAL_FIRST_ONLY_PILOT_RAW_PROTOBUF_V1",
        runId=run,readOnly=True,brokerOrders=0,cloudActivated=False,
        noEconomicOutcomeScored=True,raw=raw,rows=rows,
        sourcePilotVerdict=verdict,currentMinimumVolumeRaw=c.minVolume,
        currentMinimumMarginEur=[str(x) for x in margins]),sort_keys=True,
        separators=(",",":")).encode()
    cipher=seal_new(plain,public,run)
    Path("cxl1-original-feasibility.v2.enc").write_bytes(cipher)
    out=dict(schema="MXM_CXL1_ORIGINAL_PRESOURCE_PILOT_FEASIBILITY_V1",
        originalRunId=int(run),protocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),
        rawEncryptedSourceSha256=sha256(cipher).hexdigest(),
        rawPlaintextSourceSha256=sha256(plain).hexdigest(),
        originalAuthenticatedReadOnlyRequests=len(raw),
        scheduledClocks=50,weekdays=10,candidateClocksPerFullWeek=25,
        coverage=dict(obs),causalFeatureComplete=sum(valid_pre_by_half.values()),
        pairedPriceAndEurConversionComplete=sum(valid_quote_by_half.values()),
        weeklyHalfCausalFeature=[valid_pre_by_half[i] for i in (0,1)],
        weeklyHalfPairedFinancial=[valid_quote_by_half[i] for i in (0,1)],
        btcLeadsIntents=sum(valid_signal_by_half.values()),
        againstOwnEthDifferentIntents=sum(distinct_by_half.values()),
        costScale=cost_scale,originalCurrentMinimumVolumeRaw=c.minVolume,
        originalCurrentBuySellMinimumMarginEur=[float(x) for x in margins],
        sourceGates=gates,verdict=verdict,
        sourceSealedBeforeFutureOutcomeScore=True,rawPricesPublic=False,
        futureLabelUsedInSourceGate=False,brokerOrders=0,cloudActivated=False,
        realizedTradeNetEur=None,capitalFundedNetEur=None,
        independentFutureConfirmation=False)
    Path("cxl1-original-feasibility-public.json").write_text(
        json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("CXL1_ORIGINAL_PRESOURCE_ONLY",json.dumps(dict(
        verdict=verdict,gates=gates,pre=out["causalFeatureComplete"],
        priced=out["pairedPriceAndEurConversionComplete"],
        intents=out["btcLeadsIntents"],costScale=cost_scale)),flush=True)

if __name__=="__main__":
    main()
