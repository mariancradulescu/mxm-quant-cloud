"""LQR1 protected signed EUR financial scoring, native EUR300 single ledger, NO orders.

Only original sealed QPI1 individual BID/ASK revisions + independently sealed
new original EURUSD conversion BID/ASK and current broker terms. Exposed
development history, not broker fill or independent validation.
"""
from __future__ import annotations
import base64,json,os,subprocess,tempfile
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D, ROUND_HALF_EVEN
from hashlib import sha256
from pathlib import Path

from .bti1_temporal_burstiness import authenticated_tape,pair,mid
from .lqr1_original_presignal_support import decide_predecision, PROTOCOL as PROTO, TARGETS
from .lqr1_original_financial_source import FX_MAX_AGE_MS,fresh_pair,MAX_REQUESTS,clocks
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import need,decode_side
from .custody import unseal_new
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .rne1_source_financial_preflight import fee_usd,Unpriced

SOURCE=Path("lqr1-new-source/lqr1-original-financial-source.v2.enc")
SOURCE_RECEIPT=Path("lqr1-new-public/lqr1-original-fx-source-coverage.public.json")
OUTPUT=Path("lqr1-original-authentic-eur300-native-financial.public.json")
SLIP={"central":D("0.5"),"adverse":D("2.0"),"stress":D("4.0")}
POLICIES=("lqr1","ownMomentum","long","short","cash")
SCALE=D(100000)
ZERO_HASH="0"*64

def dec(value):
    return D(str(value))
def q12(x):
    return x.quantize(D("0.000000000001"),rounding=ROUND_HALF_EVEN)
def q10(x):
    return x.quantize(D("0.0000000001"),rounding=ROUND_HALF_EVEN)
def num(x):
    return str(x)

def decode_wire(item):
    req=getattr(m,item["requestType"])()
    ans=getattr(m,item["responseType"])()
    req.ParseFromString(base64.b64decode(item["request"],validate=True))
    ans.ParseFromString(base64.b64decode(item["response"],validate=True))
    require_read_only_request(req)
    need(req.IsInitialized() and ans.IsInitialized(),"LQR1_FINANCE_PROTOBUF_INVALID")
    return req,ans

def new_original(private):
    raw=SOURCE.read_bytes()
    receipt=json.loads(SOURCE_RECEIPT.read_text())
    need(receipt["schema"]=="MXM_LQR1_ORIGINAL_PRESOURCE_FX_COVERAGE_V1"
         and receipt["frozenProtocolSha256"]==sha256(PROTO.read_bytes()).hexdigest()
         and receipt["cipherSha256"]==sha256(raw).hexdigest()
         and receipt["sourceSealedBeforeAnyLqr1EconomicScoring"] is True
         and receipt["ordersSubmitted"]==0,"LQR1_NEW_SEALED_SOURCE_OR_PROTOCOL")
    run=str(receipt["runId"])
    plaintext=unseal_new(raw,private,run)
    need(sha256(plaintext).hexdigest()==receipt["plainSha256"],"LQR1_NEW_PLAINTEXT_HASH")
    source=json.loads(plaintext)
    need(source["schema"]=="MXM_LQR1_ORIGINAL_PEPPERSTONE_EURUSD_FX_FINANCIAL_SOURCE_V1"
         and source["originalRunId"]==run and source["originalPepperstoneEurAccount"]
         and source["originalSourceSealedBeforeLqr1EconomicScoring"]
         and source["fixedEurUsdFxClockCount"]==80
         and len(source["originalRawProtobuf"])<=MAX_REQUESTS,"LQR1_ORIGINAL_PRESCORE_FINANCE")
    proof=source["originalRawProtobuf"]
    need(len(proof)==328,"LQR1_EXACT_FINANCE_CALL_CENSUS")
    pairs=[decode_wire(x) for x in proof]
    tr=pairs[0][1]
    ac=pairs[0][0].ctidTraderAccountId
    fp=sha256(("ctrader-account:"+str(ac)).encode()).hexdigest()
    need(sha256(fp.encode()).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and type(tr) is m.ProtoOATraderRes and tr.ctidTraderAccountId==ac
         and "pepperstone" in tr.trader.brokerName.casefold(),"LQR1_NEW_EUR_ACCOUNT")
    assets={x.assetId:x.name for x in pairs[1][1].asset}
    need(type(pairs[1][1]) is m.ProtoOAAssetListRes
         and assets.get(tr.trader.depositAssetId)=="EUR","LQR1_EUR_DEPOSIT")
    roster=pairs[2][1]
    need(type(roster) is m.ProtoOASymbolsListRes,"LQR1_ROSTER_TYPE")
    ids={x.symbolName:x.symbolId for x in roster.symbol if x.enabled}
    need(all(x in ids for x in ("USDCHF","EURGBP","EURUSD")),"LQR1_FX_SYMBOL_IDS")
    contracts={}
    for n,sym in enumerate(("USDCHF","EURGBP","EURUSD"),3):
        req,ans=pairs[n]
        need(type(req) is m.ProtoOASymbolByIdReq
             and type(ans) is m.ProtoOASymbolByIdRes
             and list(req.symbolId)==[ids[sym]]
             and len(ans.symbol)==1 and ans.symbol[0].symbolId==ids[sym],
             "LQR1_SYMBOL_CONTRACT_PROTOBUF")
        contracts[sym]=ans.symbol[0]
    margins={}
    for n,sym in enumerate(TARGETS,6):
        req,ans=pairs[n]
        need(type(req) is m.ProtoOAExpectedMarginReq
             and type(ans) is m.ProtoOAExpectedMarginRes
             and req.symbolId==ids[sym] and
             list(req.volume)==[contracts[sym].minVolume]
             and ans.HasField("moneyDigits")
             and len(ans.margin)==1
             and ans.margin[0].volume==contracts[sym].minVolume,
             "LQR1_CURRENT_BROKER_MARGIN")
        scale=D(10)**ans.moneyDigits
        margins[sym]=[D(ans.margin[0].buyMargin)/scale,
                      D(ans.margin[0].sellMargin)/scale]
    checks=Counter()
    i=8
    for t,w in clocks():
        row=source["quotes"][str(t)]
        need(row["week"]==w,"LQR1_NEW_SOURCE_CLOCK")
        for tag,at in (("entry",t+60000),("exit",t+1800000)):
            side_rows=[]
            truncated=False
            for side in (e.BID,e.ASK):
                req,ans=pairs[i];i+=1
                need(type(req) is m.ProtoOAGetTickDataReq and req.ctidTraderAccountId==ac
                     and req.symbolId==ids["EURUSD"] and req.type==side
                     and req.fromTimestamp==at-60000 and req.toTimestamp==at,
                     "LQR1_EXACT_PRELISTED_HISTORICAL_TICKS")
                if type(ans) is m.ProtoOAErrorRes:
                    need(ans.errorCode=="NO_QUOTES" and ans.ctidTraderAccountId==ac,
                         "LQR1_UNEXPECTED_BROKER_TICK_ERROR")
                    data=[]
                else:
                    need(type(ans) is m.ProtoOAGetTickDataRes
                         and ans.ctidTraderAccountId==ac,
                         "LQR1_TICK_REPLY_IDENTITY")
                    truncated=not ans.HasField("hasMore") or ans.hasMore
                    data=[] if truncated else decode_side(ans.tickData,at-60000,at)
                side_rows.append(data)
            mark=row["quotes"][tag]
            q=None if truncated else fresh_pair(*side_rows,at)
            need(mark["at"]==at and mark["truncated"]==truncated and
                 mark["pair"]==(None if q is None else [list(x) for x in q]),
                 "LQR1_PRICE_SOURCE_RECONSTRUCTION")
            checks["valid" if q is not None else "unknown"]+=1
    need(i==len(pairs) and len(source["quotes"])==80,
         "LQR1_SOURCE_REQUEST_COUNT_NOT_RECONCILED")
    for sym in TARGETS:
        c=contracts[sym]
        need(c.HasField("minVolume") and c.minVolume>0
             and c.HasField("pnlConversionFeeRate")
             and c.HasField("swapTime") and c.HasField("swapPeriod")
             and c.swapPeriod==24 and 0<=c.swapTime<1440
             and c.commissionType==2,"LQR1_CURRENT_TARIFF_OR_FINANCE_UNSUPPORTED")
    return source,contracts,margins,checks,receipt, bool(source["accountSwapFree"])

def money_quote(sym,target,fx,contract,margin,slip):
    """Broker native LedgerQuote with signed CHF/GBP->EUR conversions."""
    b,a=(D(target[0])/SCALE,D(target[1])/SCALE)
    eb,ea=(D(fx[0][1])/SCALE,D(fx[1][1])/SCALE)
    need(b>0 and a>=b and eb>0 and ea>=eb,"LQR1_VALID_BIDASK")
    if sym=="USDCHF":
        credit=1/(a*ea)
        debit=1/(b*eb)
    else:
        credit=1/a
        debit=1/b
    c=contract
    unit=D(c.minVolume)/100
    broker_fee=fee_usd(c,unit,(a+b)/2)
    fee_per=q12(broker_fee/eb/unit)
    return {
        "Symbol":sym,"At":0,"Bid":num(b),"Ask":num(a),
        "EurCredit":num(q12(credit)),"EurDebit":num(q12(debit)),
        "ExitFeePerUnit":num(fee_per),"ExitFeeFloor":"0",
        "MarginPerUnit":num(q12(margin/unit))
    }

def source_rows(tape,financial,contracts,margins,swapfree):
    rows=[]
    for i,(t,w) in enumerate(clocks()):
        converted=financial["quotes"][str(t)]["quotes"]
        fx={}
        for tag in ("entry","exit"):
            v=converted[tag]["pair"]
            fx[tag]=v if v is not None and not converted[tag]["truncated"] else None
        per={}
        for sym in TARGETS:
            o=tape["targets"][sym][i]
            need(o["week"]==w and o["decision"]==t,"LQR1_QPI1_ORIGINAL_CLOCK")
            feature={"state":"SOURCE_UNKNOWN","side":None,"own":None} if o["truncated"] else decide_predecision(o["before"],t)
            for side,raw in enumerate(o["before"]):
                need(all(x[0]<=t for x in raw),"LQR1_PREDECISION_EVENT_AFTER_T")
            # Prices are read from original after-T sealed source, NEVER used to produce feature.
            q0=pair(*o["after"],t+60000)
            qz=pair(*o["after"],t+1800000)
            per[sym]=dict(feature=feature,entry=q0,exit=qz,
                          margin=margins[sym],contract=contracts[sym])
        rows.append(dict(t=t,w=w,fx=fx,symbols=per))
    need(len(rows)==80,"LQR1_DECISIONS_UNIVERSE")
    return rows

def side(policy,feature):
    if policy=="cash":return 0
    if policy=="long":return 1
    if policy=="short":return -1
    if feature["state"]=="SOURCE_UNKNOWN":
        return None
    if policy=="ownMomentum":
        return feature["own"]
    if policy=="lqr1":
        return feature["side"] if feature["state"]=="SIDE_SPECIFIC_SIGNAL" else (
            0 if feature["state"]=="ABSTAIN_SIMULTANEOUS" else None)
    raise ValueError("LQR1_POLICY_UNKNOWN")

def make_event(event_id,t,kind,sym="",direction=0,units=D(0),execution=D(0),
               fee=D(0),margin_per=D(0),slipprice=D(0),quotes=()):
    position_id=event_id.split("/")[0] if "/" in event_id else "NONE"
    return dict(EventId=event_id,At=t,Kind=kind,PositionId=position_id,Symbol=sym,
                Side=direction,Units=num(units),ExecutionPrice=num(execution),
                FeeEur=num(fee),MarginPerUnit=num(margin_per),
                SlippagePerSide=num(slipprice),AvailableAt=max(0,t-1),
                CalibratedThrough=max(0,t-600000),LatencyMs=1,Reason=kind,
                EvidenceHash=sha256(event_id.encode()).hexdigest(),Quotes=list(quotes))

def build_native(rows,policy,slippage):
    """Predecision intents fixed BEFORE finding any future-source availability."""
    counts=Counter()
    planned=[]
    missing=[]
    for row in rows:
        intents={}
        for sym in TARGETS:
            d=side(policy,row["symbols"][sym]["feature"])
            if d is None:
                counts["predecisionUnknown"]+=1
                continue
            if d!=0:
                counts["predecisionIntent"]+=1
                intents[sym]=d
        planned.append((row,intents))
    for row,intents in planned:
        if not intents:continue
        for sym in intents:
            x=row["symbols"][sym]
            if x["entry"] is None or x["exit"] is None or row["fx"]["entry"] is None or row["fx"]["exit"] is None:
                missing.append(dict(t=row["t"],symbol=sym,why="ORIGINAL_EXIT_ENTRY_OR_FX_UNKNOWN"))
            # A missing future source must NEVER transform a prior trade into CASH.
    if missing or counts["predecisionUnknown"]:
        return None,dict(counts),missing
    events=[]
    for ix,(row,intents) in enumerate(planned):
        if not intents:continue
        t=row["t"]
        T0=t+60000
        TZ=t+1800000
        q={}
        for tag,at in (("entry",T0),("exit",TZ)):
            for sym in intents:
                data=row["symbols"][sym]
                margin=data["margin"][0 if intents[sym]>0 else 1]
                z=money_quote(sym,data[tag],row["fx"][tag],data["contract"],margin,slippage)
                z["At"]=at
                q[(tag,sym)]=z
        ordered=sorted(intents)
        # First refresh all original as-of price marks together to avoid stale held marks.
        events.append(make_event(f"mark/{ix}/entry",T0,"MARK",quotes=[q[("entry",s)] for s in ordered]))
        for j,sym in enumerate(ordered):
            d=intents[sym]
            quote=q[("entry",sym)]
            c=row["symbols"][sym]["contract"]
            units=D(c.minVolume)/100
            sp=q10((D(quote["Bid"])+D(quote["Ask"]))/2*slippage/D(20000))
            price=(D(quote["Ask"])+sp if d>0 else D(quote["Bid"])-sp)
            fee=D(quote["ExitFeePerUnit"])*units
            margin_per=D(quote["MarginPerUnit"])
            pos=f"lqr1-{ix}-{sym}"
            events.append(make_event(f"{pos}/openintent",T0+j*2+1,"REQUEST_OPEN",
                         sym,d,units,D(0),D(0),margin_per,sp))
            events.append(make_event(f"{pos}/openfill",T0+j*2+2,"OPEN_FILL",
                         sym,d,units,price,fee,margin_per,sp))
        events.append(make_event(f"mark/{ix}/exit",TZ,"MARK",quotes=[q[("exit",s)] for s in ordered]))
        for j,sym in enumerate(ordered):
            d=intents[sym]
            quote=q[("exit",sym)]
            c=row["symbols"][sym]["contract"]
            units=D(c.minVolume)/100
            margin_per=D(quote["MarginPerUnit"])
            # The entry slippage price is fixed over the whole position lifespan.
            old=q[("entry",sym)]
            sp=q10((D(old["Bid"])+D(old["Ask"]))/2*slippage/D(20000))
            price=(D(quote["Bid"])-sp if d>0 else D(quote["Ask"])+sp)
            fee=D(quote["ExitFeePerUnit"])*units
            pos=f"lqr1-{ix}-{sym}"
            events.append(make_event(f"{pos}/closeintent",TZ+j*2+1,"REQUEST_CLOSE",
                         sym,d,units,D(0),D(0),margin_per,sp))
            events.append(make_event(f"{pos}/closefill",TZ+j*2+2,"CLOSE_FILL",
                         sym,d,units,price,fee,margin_per,sp))
    return events,dict(counts),missing

def run_native(events):
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/"facts.json"
        out=Path(d)/"native.json"
        src.write_text(json.dumps(events,separators=(",",":")))
        proc=subprocess.run(["dotnet","run","--no-build","-c","Release",
             "--project","src/Mxm.Replay","--",str(src),str(out),
             "--native-funded-facts"],capture_output=True,text=True,timeout=150)
        need(proc.returncode==0 and out.exists(),
             "LQR1_NATIVE_LEDGER_REJECTED_FACTS")
        return json.loads(out.read_text())

def evaluate(tape,financial,contracts,margins,swapfree):
    data=source_rows(tape,financial,contracts,margins,swapfree)
    out={}
    for pol in POLICIES:
        model={}
        for scenario,slip in SLIP.items():
            events,counters,missing=build_native(data,pol,slip)
            if events is None:
                model[scenario]={"fullConditionalNativeNetEur":None,
                    "reason":"SOURCE_OR_FEATURE_UNKNOWN_NO_HINDSIGHT_PRUNING",
                    "originalPredecision":counters,"unpricedOrUnknownCount":len(missing)}
                continue
            if not events:
                model[scenario]={"fullConditionalNativeNetEur":0.0,
                    "originalPredecision":counters,"sourceCompleteness":True,
                    "fundedCompletedRoundTrips":0,"cashFinalEur":300.0}
                continue
            native=run_native(events)
            ledger=native["Summary"]
            trades=native["Trades"]
            w=Counter()
            for t in trades:
                start=datetime.fromisoformat(str(t["OpenedAt"])) if False else int(t["OpenedAt"])
                index=int(next((n for n,row in enumerate(data) if row["t"]+60000<=start<=row["t"]+60005),-1))
                if index>=0:w[data[index]["w"]]+=1
            model[scenario]={
                "fullConditionalNativeNetEur":float(D(str(ledger["ClosedNetEur"]))),
                "cashFinalEur":float(D(str(ledger["CashEur"]))),
                "fundedCompletedRoundTrips":ledger["CompleteRoundTrips"],
                "nativeSampledDrawdownFraction":float(ledger["MaximumSampledDrawdown"]),
                "nativeHistoryEvidenceIncomplete":ledger["HistoryEvidenceIncomplete"],
                "nativeRestartEveryEventMatched":native["RestartEveryEventMatched"],
                "nativeDuplicateIdempotent":native["DuplicatesIdempotent"],
                "originalPredecision":counters,
                "weeklyCompletedTrips":[w[i] for i in range(8)],
                "brokerActualFillNetEur":None,
                "continuousFloatingDdCertified":False
            }
        out[pol]=model
    return out

def main():
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"LQR1_PRIVATE_CUSTODY_MISSING")
    tape,_=authenticated_tape()  # authenticated source reconstruction only; NO BTI/QPI scoring
    financial,contracts,margins,checks,receipt,swapfree=new_original(private)
    outcome=evaluate(tape,financial,contracts,margins,swapfree)
    summary={"schema":"MXM_LQR1_ORIGINAL_PAIRED_EUR300_NATIVE_DEVELOPMENT_V1",
             "frozenProtocolSha256":sha256(PROTO.read_bytes()).hexdigest(),
             "sourceOriginalQpi1RunId":43458050084,
             "newOriginalPepperstoneFinancialRunId":receipt["runId"],
             "originalFinancialCipherSha256":receipt["cipherSha256"],
             "originalFinancialRawRequests":financial["originalReadOnlyRequestCount"],
             "originalFinancialFxQuoteCoverage":dict(checks),
             "sourceOriginalProtobufVerified":True,
             "slippageRoundTripBps":{s:str(v) for s,v in SLIP.items()},
             "singleInitialCapitalEur":300,
             "originalNativeFundedPolicies":outcome,
             "conditionalCurrentTariffNotHistoricalActualNet":True,
             "fullOriginalHistoricalBrokerFillsCertified":False,
             "independentLongChronologyCertified":False,
             "systemHard21Certified":False,
             "continuousFloating30PctDdCertified":False,
             "cloudActivated":False,"ordersSubmitted":0}
    OUTPUT.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print("LQR1_AUTHENTIC_ORIGINAL_CONDITIONAL_EUR300_NATIVE_NOT_BROKER_FILLS",flush=True)

if __name__=="__main__":
    main()
