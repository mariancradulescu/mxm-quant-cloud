"""GCL1 genuine ORIGINAL EURUSD BID/ASK release-vs-placebo conditional EUR economics.

Protected GCL1 source sealed BEFORE any future scoring. All 86 dates checked;
never call BDP1 closed model, optimize, invert, or perform broker orders.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
from statistics import mean
import base64,json,os,math

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .custody import unseal_new
from .portfolio_discovery_source import audit as audit_bdp
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_side,need
from .rne1_source_financial_preflight import fee_usd,Unpriced
from .gcl1_claims_quote_source import (
    day_schedule,ts,pair,START,WEEKS,SAMPLES,PROTO,MAX_AGE,LOOKBACK
)

BDP_RUN="41724643418"
BDP_CIPHER="e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370"
OLD=Path("bdp1-original-source/source.envelope.json")
OLD_RECEIPT=Path("bdp1-original-source/receipt.public.json")
NEW=Path("gcl1-original-source/gcl1-original-source.v2.enc")
NEW_RECEIPT=Path("gcl1-source-public/gcl1-original-source-coverage.public.json")
OUTPUT=Path("gcl1-authentic-claims-gold-eurusd-conditional-money.public.json")
SCALE=D(100000)
POLICIES=("gcl1","ownMomentum","goldAlways","long","short","cash")
SLIP={"central":D("0.5"),"adverse":D("2.0")}


def wire(item):
    req=getattr(m,item["requestType"])()
    res=getattr(m,item["responseType"])()
    req.ParseFromString(base64.b64decode(item["request"],validate=True))
    res.ParseFromString(base64.b64decode(item["response"],validate=True))
    require_read_only_request(req)
    need(req.IsInitialized() and res.IsInitialized(),"GCL1_ORIGINAL_PROTOBUF_INVALID")
    return req,res


def original_annual_bars(private):
    raw=OLD.read_bytes()
    need(sha256(raw).hexdigest()==BDP_CIPHER,"GCL1_BDP1_ORIGINAL_SOURCE_CHANGED")
    receipt=json.loads(OLD_RECEIPT.read_text())
    need(receipt["sha256"]==BDP_CIPHER and receipt["runId"]==BDP_RUN and receipt["complete"] is True,
         "GCL1_BDP1_CUSTODY_RECEIPT")
    plaintext=unseal_new(raw,private,BDP_RUN)
    original=json.loads(plaintext)
    protocol=json.loads(Path("research/portfolio_discovery_protocol.json").read_text())
    verify=audit_bdp(original,protocol)
    need(original["auditReceipt"]==verify and original["pilotPassed"],
         "GCL1_BDP1_AUTHENTIC_SOURCE_NOT_REBUILT")
    bars={}
    for name in ("XAUUSD","EURUSD"):
        rows=original["bars"][name]
        need(len(rows)>=65000,"GCL1_BDP1_ANNUAL_SOURCE_INSUFFICIENT")
        bars[name]={int(row[1]):int(row[5]) for row in rows}
        need(len(bars[name])==len(rows),"GCL1_BDP1_DUPLICATE_BAR")
    return bars,sha256(plaintext).hexdigest(),verify


def original_broker_quotes(private):
    raw=NEW.read_bytes()
    public=json.loads(NEW_RECEIPT.read_text())
    need(public["schema"]=="MXM_GCL1_ORIGINAL_READONLY_QUOTE_SOURCE_ONLY_V1"
         and public["preFrozenProtocolSha256"]==sha256(PROTO.read_bytes()).hexdigest()
         and public["originalSourceCipherSha256"]==sha256(raw).hexdigest()
         and public["sourceSealedBeforeOutcomeEvaluation"] is True
         and public["sourceNoBrokerOrders"] is True
         and public["fixedDays"]==86,
         "GCL1_NEW_SOURCE_RECEIPT")
    run=str(public["runId"])
    plain=unseal_new(raw,private,run)
    need(sha256(plain).hexdigest()==public["originalSourcePlainSha256"],
         "GCL1_NEW_SOURCE_DECRYPTION_MISMATCH")
    payload=json.loads(plain)
    original_calls=payload["originalRawProtobuf"]
    need(payload["schema"]=="MXM_GCL1_ORIGINAL_PEPPERSTONE_EURUSD_BIDASK_SOURCE_V1"
         and payload["run"]==run
         and payload["originalPepperstoneEurBound"]
         and payload["sourceOnlyBeforeAllGcl1EconomicScoring"]
         and len(original_calls)==payload["originalReadOnlyCallsAfterAuth"]
         and len(original_calls)==5+86*3*2,
         "GCL1_SOURCE_CALENDAR_OR_RAW_COUNT")
    decoded=[wire(x) for x in original_calls]
    trader=decoded[0][1]
    assets=decoded[1][1]
    listing=decoded[2][1]
    detail_req,detail_res=decoded[3]
    margin_req,margin_res=decoded[4]
    account=trader.ctidTraderAccountId
    fp=sha256(f"ctrader-account:{account}".encode("ascii")).hexdigest()
    need(sha256(fp.encode("ascii")).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and "pepperstone" in trader.trader.brokerName.casefold(),"GCL1_PEPPERSTONE_ACCOUNT")
    asset_map={a.assetId:a.name for a in assets.asset}
    enabled={s.symbolName:s for s in listing.symbol if s.enabled}
    need("EURUSD" in enabled and asset_map[trader.trader.depositAssetId]=="EUR" and
         asset_map[enabled["EURUSD"].baseAssetId]=="EUR" and asset_map[enabled["EURUSD"].quoteAssetId]=="USD",
         "GCL1_DEPOSIT_AND_FX_QUOTE")
    sym=enabled["EURUSD"].symbolId
    need(list(detail_req.symbolId)==[sym] and len(detail_res.symbol)==1
         and detail_res.symbol[0].symbolId==sym
         and margin_req.symbolId==sym
         and list(margin_req.volume)==[detail_res.symbol[0].minVolume]
         and len(margin_res.margin)==1 and margin_res.margin[0].volume==detail_res.symbol[0].minVolume
         and margin_res.HasField("moneyDigits"),"GCL1_ORIGINAL_CONTRACT_MARGIN")
    c=detail_res.symbol[0]
    margin_buy=D(margin_res.margin[0].buyMargin)/D(10)**margin_res.moneyDigits
    margin_sell=D(margin_res.margin[0].sellMargin)/D(10)**margin_res.moneyDigits
    need(margin_buy>0 and margin_sell>0
         and D(str(payload["currentMarginBuyEur"]))==margin_buy
         and D(str(payload["currentMarginSellEur"]))==margin_sell
         and payload["accountSwapFreeEffective"]==trader.trader.swapFree
         and int(payload["currentMinVolume"])==c.minVolume,
         "GCL1_ORIGINAL_FINANCIAL_METADATA")
    if not (0<max(margin_buy,margin_sell)<=300):
        raise Unpriced("GCL1_MINIMUM_VOLUME_UNFINANCEABLE")
    want=day_schedule()
    need(set(payload["monthCalendar"])=={day.isoformat() for day,_,_ in want},
         "GCL1_FIXED_86_DAY_CALENDAR")
    idx=5
    validated={}
    for day,arm,week in want:
        original=payload["monthCalendar"][day.isoformat()]
        need(original["week"]==week and original["arm"]==arm,"GCL1_ARM_WEEK_CONFLICT")
        panel={}
        for h,mm in SAMPLES:
            nominal=ts(day,h,mm)
            old=original["quotes"][str(nominal)]
            sides=[];truncated=False
            for side in (e.BID,e.ASK):
                q,ans=decoded[idx];idx+=1
                need(type(q) is m.ProtoOAGetTickDataReq
                    and q.ctidTraderAccountId==account
                    and q.symbolId==sym and q.type==side
                    and q.fromTimestamp==nominal-LOOKBACK
                    and q.toTimestamp==nominal,
                    "GCL1_QUOTE_ORIGINAL_REQUEST_DIFFERENT")
                if isinstance(ans,m.ProtoOAErrorRes):
                    need(ans.errorCode=="NO_QUOTES","GCL1_UNEXPECTED_SOURCE_ERROR")
                    sides.append([])
                else:
                    need(isinstance(ans,m.ProtoOAGetTickDataRes)
                         and ans.ctidTraderAccountId==account
                         and ans.HasField("hasMore"),"GCL1_QUOTE_WRONG_REPLY")
                    if ans.hasMore:
                        truncated=True
                        sides.append([])
                    else:
                        sides.append(decode_side(ans.tickData,nominal-LOOKBACK,nominal))
            rebuilt=None if truncated else pair(*sides,nominal)
            need(rebuilt==old["pair"] and truncated==old["truncated"],
                 "GCL1_RAW_PRICE_PAIR_RECONSTRUCTION")
            panel[nominal]=rebuilt
        validated[day.isoformat()]={"arm":arm,"week":week,"quotes":panel}
    need(idx==len(decoded) and all(q.ctidTraderAccountId==account
         and hasattr(ans,"ctidTraderAccountId") and ans.ctidTraderAccountId==account
         for q,ans in decoded),
         "GCL1_ORIGINAL_REPLY_ACCOUNT_OR_COUNT_MISMATCH")
    return validated,c,margin_buy,margin_sell,bool(trader.trader.swapFree),public,sha256(raw).hexdigest()


def feature(bars,day):
    clocks=[ts(day,8,0)+i*300000 for i in range(10)]
    data={}
    for symbol in ("XAUUSD","EURUSD"):
        vals=[bars[symbol].get(t) for t in clocks]
        if any(x is None or x<=0 for x in vals):
            return dict(state="SOURCE_UNKNOWN")
        data[symbol]=vals
    g=math.log(data["XAUUSD"][9]/data["XAUUSD"][6])
    eur=math.log(data["EURUSD"][9]/data["EURUSD"][6])
    if not (math.isfinite(g) and math.isfinite(eur)):
        return dict(state="SOURCE_UNKNOWN")
    gside=(g>0)-(g<0)
    eside=(eur>0)-(eur<0)
    state="CONFLICT" if g*eur<0 else "NO_CONFLICT"
    return dict(state=state,goldSide=gside,eurSide=eside)


def quote(panel,clock):
    x=panel["quotes"][clock]
    if x is None:return None
    b,a=x["bid"],x["ask"]
    need(b["raw"]>0 and a["raw"]>=b["raw"] and
         0<=clock-b["at"]<=MAX_AGE and 0<=clock-a["at"]<=MAX_AGE and
         b["ageMs"]==clock-b["at"] and a["ageMs"]==clock-a["at"],
         "GCL1_QUOTE_AGE_PRICE_OR_FUTURE_INVALID")
    return D(b["raw"])/SCALE,D(a["raw"])/SCALE


def funding_check(contract,swapfree,entry,exit):
    if swapfree:return True
    if not contract.HasField("swapTime") or not contract.HasField("swapPeriod"):
        raise Unpriced("GCL1_CURRENT_SWAP_SCHEDULE_UNKNOWN")
    if contract.swapPeriod!=24 or not 0<=contract.swapTime<1440:
        raise Unpriced("GCL1_CURRENT_SWAP_FORMAT_UNKNOWN")
    # No cross of 24h UTC daily charge, no swap assumption required.
    first=datetime.fromtimestamp(entry/1000,timezone.utc).date()
    last=datetime.fromtimestamp(exit/1000,timezone.utc).date()
    from datetime import timedelta
    d=first
    while d<=last:
        z=int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp()*1000)+contract.swapTime*60000
        if entry<z<=exit:
            raise Unpriced("GCL1_EXPOSURE_CROSSES_SWAP_WITHOUT_EXACT_FINANCE")
        d+=timedelta(days=1)
    return True


def money(contract,swapfree,entryq,exitq,entryclk,exitclk,side,slipbps):
    if side==0:return dict(grossEur=0.0,conditionalNetEur=0.0,feeEur=0.0,slipEur=0.0,conversionFeeEur=0.0)
    if entryq is None or exitq is None:raise Unpriced("GCL1_MISSING_FX_BIDASK")
    funding_check(contract,swapfree,entryclk,exitclk)
    if not contract.HasField("pnlConversionFeeRate"):
        raise Unpriced("GCL1_PNL_CONVERSION_RATE_UNKNOWN")
    volume=D(contract.minVolume)/100
    opening=entryq[1] if side>0 else entryq[0]
    closing=exitq[0] if side>0 else exitq[1]
    grossusd=D(side)*(closing-opening)*volume
    # Signed conversion of JPY-free USD P&L into EUR using original EURUSD.
    gross=grossusd/(exitq[1] if grossusd>=0 else exitq[0])
    fee=(fee_usd(contract,volume,opening)/entryq[0]
         +fee_usd(contract,volume,closing)/exitq[0])
    rate=D(contract.pnlConversionFeeRate)/D(10000)
    if rate<0 or rate>=1:raise Unpriced("GCL1_CURRENT_CONVERSION_FEE_INVALID")
    conversion=abs(grossusd)*rate/exitq[0]
    mid=(entryq[0]+entryq[1])/2
    slip_usd=volume*mid*slipbps/D(10000)
    slip=slip_usd/D(2)/entryq[0]+slip_usd/D(2)/exitq[0]
    net=gross-fee-conversion-slip
    return dict(grossEur=float(gross),conditionalNetEur=float(net),
                feeEur=float(fee),slipEur=float(slip),conversionFeeEur=float(conversion))


def direction(feature,policy):
    if feature["state"]=="SOURCE_UNKNOWN":return None
    if policy=="cash":return 0
    if policy=="gcl1":
        return feature["goldSide"] if feature["state"]=="CONFLICT" else 0
    if policy=="ownMomentum":return feature["eurSide"]
    if policy=="goldAlways":return feature["goldSide"]
    if policy=="long":return 1
    if policy=="short":return -1
    raise ValueError("GCL1_UNKNOWN_POLICY")


def evaluate(bars,source,contract,buy_margin,sell_margin,swapfree):
    result={}
    for arm in ("DOL_THURSDAY","PLACEBO_TUE"):
        allrows=[]
        for day,ident,week in day_schedule():
            if ident!=arm:continue
            feat=feature(bars,day)
            panel=source[day.isoformat()]
            q={str(t):quote(panel,t) for h,m in SAMPLES for t in (ts(day,h,m),)}
            allrows.append(dict(day=day.isoformat(),week=week,feature=feat,quotes=q))
        counters=Counter(r["feature"]["state"] for r in allrows)
        cases={}
        for policy in POLICIES:
            book={}
            for scenario,slip in SLIP.items():
                cash=D(300);high=D(300);sampled_dd=D(0)
                open_count=0;missing_entry=0;missing_exit=0;source_unknown=0
                risk_unknown=0;intent_count=0;unpriced_cost=0;underfunded=0
                closed=defaultdict(int);sum_gross=D(0);sum_fees=D(0)
                sum_slip=D(0);sum_conv=D(0)
                suspended=False
                for row in allrows:
                    side=direction(row["feature"],policy)
                    if side is None:
                        source_unknown+=1
                        continue
                    if side==0:continue
                    intent_count+=1
                    dayrow=row["day"]
                    # Datetimes reflect predeclared NY local clocks, no future-feature leakage.
                    from datetime import date
                    day=date.fromisoformat(dayrow)
                    t0=ts(day,8,50);tm=ts(day,9,10);tz=ts(day,9,35)
                    q0=row["quotes"][str(t0)]
                    qmid=row["quotes"][str(tm)]
                    qz=row["quotes"][str(tz)]
                    if q0 is None:
                        missing_entry+=1;continue
                    if qz is None:
                        missing_exit+=1;suspended=True;continue
                    margin=buy_margin if side>0 else sell_margin
                    if cash<=margin or cash<=0:
                        underfunded+=1;continue
                    try:
                        m=money(contract,swapfree,q0,qz,t0,tz,side,slip)
                    except (Unpriced,ValueError):
                        unpriced_cost+=1;continue
                    if suspended:continue
                    if qmid is None:
                        risk_unknown+=1
                    else:
                        try:
                            mid=money(contract,swapfree,q0,qmid,t0,tm,side,slip)
                            floating=cash+D(str(mid["conditionalNetEur"]))
                            high=max(high,floating)
                            sampled_dd=max(sampled_dd,high-floating)
                        except (Unpriced,ValueError):
                            risk_unknown+=1
                    cash+=D(str(m["conditionalNetEur"]))
                    high=max(high,cash)
                    sampled_dd=max(sampled_dd,high-cash)
                    open_count+=1;closed[row["week"]]+=1
                    sum_gross+=D(str(m["grossEur"]))
                    sum_fees+=D(str(m["feeEur"]))
                    sum_slip+=D(str(m["slipEur"]))
                    sum_conv+=D(str(m["conversionFeeEur"]))
                    if cash<high-D(90):suspended=True
                book[scenario]=dict(
                    initialEur=300,conditionalEndEur=(round(float(cash),6) if not suspended else None),
                    conditionalNetEur=(round(float(cash-D(300)),6) if not suspended else None),
                    observedPricedTrades=open_count,intents=intent_count,
                    predecisionSourceUnknown=source_unknown,
                    missingEntry=missing_entry,unresolvedExit=missing_exit,
                    unpricedCosts=unpriced_cost,underfunded=underfunded,
                    observedFloatMarkMissing=risk_unknown,
                    dynamicallySuspended=bool(suspended),
                    sampledDrawdownLowerBoundEur=round(float(sampled_dd),6),
                    pricedGrossEur=round(float(sum_gross),6),
                    pricedFeeEur=round(float(sum_fees),6),
                    modeledSlipEur=round(float(sum_slip),6),
                    pricedPnlConversionFeeEur=round(float(sum_conv),6),
                    weeklyClosedCounts=[closed[w] for w in range(WEEKS)],
                    weeklyCashEur300NoForcedTrips=True,
                    fullHistoricalNetEurCertified=False,
                    independentConfirmation=False)
            cases[policy]=book
        result[arm]=dict(calendar=43,
                         eventStates=dict(counters),
                         policy=cases,
                         economicProofClass="CONDITIONAL_CURRENT_TARIFF_BIDASK_EUR_NOT_HISTORICAL_EXECUTION")
    return result


def main():
    private=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"GCL1_PRIVATE_CUSTODY_UNAVAILABLE")
    source,plain_hash,cert=original_annual_bars(private)
    ticks,contract,margin_buy,margin_sell,swapfree,public,cipher_hash=original_broker_quotes(private)
    research=evaluate(source,ticks,contract,margin_buy,margin_sell,swapfree)
    receipt=dict(schema="MXM_GCL1_GENUINE_LABOR_GOLD_EURUSD_FINANCIAL_DEVELOPMENT_V1",
                 verdict="GCL1_ORIGINAL_RESULT_SCENARIO_ONLY_NO_PROMOTION",
                 immutableProtocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
                 oldBdp1SourceRunId=int(BDP_RUN),oldBdp1CipherSha256=BDP_CIPHER,
                 oldBdp1PlainSha256=plain_hash,oldBdp1RawAudit=cert,
                 newQuoteRunId=public["runId"],newQuoteCipherSha256=cipher_hash,
                 newQuotePlainSha256=public["originalSourcePlainSha256"],
                 newBrokerReadOnlyCalls=public["readOnlyCallsAfterAuth"],
                 quoteCoverage=public["quotes"],
                 sourceAccountVerified=True,originalClosedModelsReplayed=False,
                 newSourceSealedBeforeScoring=True,
                 currentMinMarginBuyEur=round(float(margin_buy),6),
                 currentMinMarginSellEur=round(float(margin_sell),6),
                 currentMinVolume=contract.minVolume,
                 conditionalEconomics=research,
                 netEurActuallyExecuted=None,nativeCommonPortfolioEurNetCertified=False,
                 fullContinuousFloatDDKnown=False,
                 chronologicalIndependentConfirmation=False,
                 historicalTariffContinuityConfirmed=False,
                 completePlatformCloudParityConfirmed=False,
                 liveDemoOrders=0,cloudTradingActivated=False,
                 disclaimer="Historical original BID/ASK+EURUSD signed money, exact initial EUR300 single-leg research book and original CURRENT commission, min-volume margin, conversion and funding schedule, plus modeled slip. NO actual order fills, full historical cost continuity, native C# funded ledger parity, 30% continuous floating risk proof, independent 12+ month confirmation or HARD21.")
    OUTPUT.write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("GCL1_GENUINE_ORIGINAL_DEVELOPMENT_FINANCIAL",
          json.dumps({arm:{p:research[arm]["policy"][p]["adverse"]["conditionalNetEur"]
              for p in POLICIES}
              for arm in ("DOL_THURSDAY","PLACEBO_TUE")}),flush=True)

if __name__=="__main__":
    main()
