"""WCR1 independent authenticated original readback + native C# EUR300 replay.
One new WCR1 policy only, never replays any closed research policy.
Original raw protobuf is authenticated, redecoded, feature-first then finance.
"""
from __future__ import annotations
import base64,json,os,subprocess,tempfile
from collections import Counter
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D, ROUND_HALF_EVEN
from hashlib import sha256
from pathlib import Path

from .wcr1_original_reopen_source import PROTO,calendar,MAX_CALLS,BAR_MS,BACK,last_pair
from .custody import unseal_new
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .decode import decode_bars,decode_side,need
from .guard import require_read_only_request
from .rne1_source_financial_preflight import fee_usd,Unpriced

SRC=Path("wcr1-original/wcr1-original-reopen-source.v2.enc")
REC=Path("wcr1-source-public/wcr1-original-source-public.json")
OUT=Path("wcr1-original-native-financed-eur300-result.public.json")
SCENARIOS={"central":D("0.5"),"adverse":D("2.0"),"stress":D("4.0")}
POLICIES=("wcr1","ownMomentum","long","short","cash","oppositeBtcDiagnostic")
SCALE=D(100000)
def dec(v):return D(str(v))
def num(v):return str(v)
def q10(v):return v.quantize(D("0.0000000001"),rounding=ROUND_HALF_EVEN)

def wire(x):
    need(x["requestType"].startswith("ProtoOA")
         and x["responseType"].startswith("ProtoOA"),"WCR1_PROTO_TYPE_NOT_ALLOWED")
    req=getattr(m,x["requestType"])()
    ans=getattr(m,x["responseType"])()
    req.ParseFromString(base64.b64decode(x["request"],validate=True))
    ans.ParseFromString(base64.b64decode(x["response"],validate=True))
    need(req.IsInitialized() and ans.IsInitialized(),"WCR1_RAW_PROTO_INVALID")
    require_read_only_request(req)
    return req,ans

def read_original():
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"WCR1_ORIGINAL_CUSTODY_UNAVAILABLE")
    cipher=SRC.read_bytes()
    rec=json.loads(REC.read_text())
    need(rec["schema"]=="MXM_WCR1_ORIGINAL_SOURCE_PREOUTCOME_V1"
         and rec["frozenProtocolSha256"]==sha256(PROTO.read_bytes()).hexdigest()
         and rec["cipherSha256"]==sha256(cipher).hexdigest()
         and rec["sourceSealedBeforeEconomicScore"] and rec["brokerOrders"]==0,
         "WCR1_ORIGINAL_CIPHERTEXT_OR_PROTOCOL_MISMATCH")
    plain=unseal_new(cipher,private,str(rec["originalRunId"]))
    need(sha256(plain).hexdigest()==rec["plainSha256"],"WCR1_PLAIN_SHA_MISMATCH")
    data=json.loads(plain)
    need(data["schema"]=="MXM_WCR1_ORIGINAL_CRYPTO_US500_REOPEN_SOURCE_V1"
         and data["runId"]==str(rec["originalRunId"])
         and data["sourceSealedBeforeScore"]
         and data["scopeViewOnlyRequests"] and data["accountIsOriginalPepperstoneEur"]
         and not data["ordersSubmitted"] and not data["cloudActivated"]
         and len(data["rows"])==52 and len(data["raw"])==7+52*20
         and len(data["raw"])<=MAX_CALLS,"WCR1_SOURCE_CENSUS_MISMATCH")
    w=[wire(x) for x in data["raw"]]
    acct=w[0][0].ctidTraderAccountId
    fp=sha256(("ctrader-account:"+str(acct)).encode("ascii")).hexdigest()
    need(sha256(fp.encode()).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and all(getattr(r,"ctidTraderAccountId",acct)==acct
                 and getattr(a,"ctidTraderAccountId",acct)==acct for r,a in w),
         "WCR1_ORIGINAL_ACCOUNT_CUSTODY_BINDING")
    tr=w[0][1]
    need(type(tr) is m.ProtoOATraderRes
         and "pepperstone" in tr.trader.brokerName.casefold(),
         "WCR1_BROKER_NOT_ORIGINAL")
    fxids={x.assetId:x.name for x in w[1][1].asset}
    need(type(w[1][1]) is m.ProtoOAAssetListRes
         and fxids.get(tr.trader.depositAssetId)=="EUR","WCR1_EUR_ACCOUNT")
    roster=w[2][1]
    need(type(roster) is m.ProtoOASymbolsListRes,"WCR1_ROSTER_UNREADABLE")
    named={x.symbolName:x for x in roster.symbol if x.enabled}
    need(all(s in named for s in ("BTCUSD","US500","EURUSD"))
         and fxids.get(named["US500"].quoteAssetId)=="USD",
         "WCR1_BROKER_TARGET_NOT_USD")
    ids={s:named[s].symbolId for s in ("BTCUSD","US500","EURUSD")}
    contracts={}
    for i,s in enumerate(("BTCUSD","US500","EURUSD"),3):
        req,a=w[i]
        need(type(req) is m.ProtoOASymbolByIdReq
             and list(req.symbolId)==[ids[s]]
             and type(a) is m.ProtoOASymbolByIdRes
             and len(a.symbol)==1 and a.symbol[0].symbolId==ids[s],
             "WCR1_SOURCE_SYMBOL_CONTRACT_CHANGED")
        contracts[s]=a.symbol[0]
    q,margin=w[6]
    c=contracts["US500"]
    need(type(q) is m.ProtoOAExpectedMarginReq
         and q.symbolId==ids["US500"]
         and list(q.volume)==[c.minVolume]
         and type(margin) is m.ProtoOAExpectedMarginRes
         and margin.HasField("moneyDigits")
         and len(margin.margin)==1
         and margin.margin[0].volume==c.minVolume,
         "WCR1_SOURCE_US500_BROKER_MARGIN_INVALID")
    scale=D(10)**margin.moneyDigits
    mgn=[D(margin.margin[0].buyMargin)/scale,
         D(margin.margin[0].sellMargin)/scale]
    need(mgn==[dec(x) for x in data["currentBuySellMarginEur"]]
         and c.minVolume==data["originalMinVolume"],
         "WCR1_SOURCE_MARGIN_ECONOMIC_MISMATCH")
    idx=7;rows=[];checks=Counter()
    for (week,sun,barplan,marks),old in zip(calendar(),data["rows"]):
        need(old["week"]==week and old["day"]==sun.isoformat()
             and len(old["bars"])==4 and len(old["marks"])==4,
             "WCR1_FIXED_52_CALENDAR")
        pre=[]
        for (sym,end),stored in zip(barplan,old["bars"]):
            req,a=w[idx];idx+=1
            need(type(req) is m.ProtoOAGetTrendbarsReq
                 and req.period==e.M5 and req.symbolId==ids[sym]
                 and req.fromTimestamp==end-BAR_MS and req.toTimestamp==end
                 and stored["rawIndex"]==idx-1 and stored["symbol"]==sym
                 and stored["at"]==end,"WCR1_PRESIGNAL_SOURCE_MISMATCH")
            truncated=False;close=None
            if type(a) is m.ProtoOAErrorRes:
                need(a.errorCode=="NO_QUOTES","WCR1_UNEXPECTED_TRENDBAR_ERROR")
            else:
                need(type(a) is m.ProtoOAGetTrendbarsRes,"WCR1_ORIGINAL_BAR_TYPE")
                truncated=not a.HasField("hasMore") or a.hasMore
                if not truncated:
                    bars=decode_bars(a.trendbar,end-BAR_MS,end,5)
                    matching=[v for v in bars if v[1]==end]
                    need(len(matching)<=1,"WCR1_DUPLICATE_CLOSE")
                    if matching:close=int(matching[0][5])
            need(stored["closeRaw"]==close and stored["truncated"]==truncated,
                 "WCR1_BAR_NOT_GENUINE")
            pre.append(close)
            checks["sourceBarsGood" if close else "sourceBarsMissing"]+=1
        samples=[]
        for at,stored in zip(marks,old["marks"]):
            need(stored["at"]==at,"WCR1_SOURCE_TIMESTAMP_MISMATCH")
            quotes={}
            for sym in ("US500","EURUSD"):
                s=stored["symbols"][sym]
                need(s["rawIndices"]==[idx,idx+1],"WCR1_TICK_RAW_INDICES_CHANGED")
                values=[];truncated=False
                for side in (e.BID,e.ASK):
                    req,a=w[idx];idx+=1
                    need(type(req) is m.ProtoOAGetTickDataReq
                         and req.symbolId==ids[sym] and req.type==side
                         and req.fromTimestamp==at-BACK and req.toTimestamp==at,
                         "WCR1_ORIGINAL_MARK_CLOCK_CHANGED")
                    if type(a) is m.ProtoOAErrorRes:
                        need(a.errorCode=="NO_QUOTES","WCR1_ORIGINAL_QUOTE_ERROR")
                        ticks=[]
                    else:
                        need(type(a) is m.ProtoOAGetTickDataRes,"WCR1_TICK_REPLY_TYPE")
                        truncated|=not a.HasField("hasMore") or a.hasMore
                        ticks=[] if truncated else decode_side(a.tickData,at-BACK,at)
                    values.append(ticks)
                val=None if truncated else last_pair(values,at)
                need(s["pair"]==val and s["truncated"]==truncated,
                     "WCR1_BIDASK_REBUILD_MISMATCH")
                quotes[sym]=val
                checks["mark_"+sym+"_valid" if val else "mark_"+sym+"_missing"]+=1
            samples.append(dict(at=at,symbols=quotes))
        rows.append(dict(week=week,day=sun.isoformat(),pre=pre,marks=samples))
    need(idx==len(w),"WCR1_UNUSED_OR_MISSING_PROTOBUF")
    return rows,contracts,mgn,tr.trader,rec,dict(checks)

def sign(x):
    return int(x>0)-int(x<0)

def sides(pre):
    if any(v is None or v<=0 for v in pre):return None
    return dict(wcr1=sign(pre[1]-pre[0]),
                ownMomentum=sign(pre[3]-pre[2]),
                long=1,short=-1,cash=0,
                oppositeBtcDiagnostic=-sign(pre[1]-pre[0]))

def valid_interval(c,trader,entry,exit):
    if trader.HasField("swapFree") and trader.swapFree:return
    need(c.HasField("swapPeriod") and c.swapPeriod==24
         and c.HasField("swapTime") and 0<=c.swapTime<1440,
         "WCR1_SWAP_FINANCING_SCHEDULE_UNKNOWN")
    start=datetime.fromtimestamp(entry/1000,timezone.utc).date()
    end=datetime.fromtimestamp(exit/1000,timezone.utc).date()
    d=start
    while d<=end:
        charge=int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp()*1000)+c.swapTime*60000
        need(not entry<charge<=exit,"WCR1_UNPRICED_SWAP_CHARGE_CROSSING")
        d+=timedelta(days=1)

def quote(sample,c,margin,slip):
    market=sample["symbols"]["US500"]
    fx=sample["symbols"]["EURUSD"]
    need(market is not None and fx is not None,"WCR1_BROKER_MARK_OR_EUR_RATE_MISSING")
    b,a=[D(x[1])/SCALE for x in market]
    eb,ea=[D(x[1])/SCALE for x in fx]
    need(b>0 and a>=b and eb>0 and ea>=eb,"WCR1_CROSSED_OR_INVALID_MARK")
    need(c.HasField("pnlConversionFeeRate"),"WCR1_PNL_CONVERSION_FEE_MISSING")
    rate=D(c.pnlConversionFeeRate)/D(10000)
    need(0<=rate<D(1),"WCR1_PNL_CONVERSION_FEE_INVALID")
    unit=D(c.minVolume)/100
    commission=fee_usd(c,unit,(a+b)/2)
    ratecredit=(D(1)-rate)/ea
    ratedebit=(D(1)+rate)/eb
    need(ratecredit>0 and ratedebit>=ratecredit,"WCR1_SIGNED_FX_CONVERSION")
    q=dict(Symbol="US500",At=sample["at"],Bid=num(b),Ask=num(a),
           EurCredit=num(q10(ratecredit)),EurDebit=num(q10(ratedebit)),
           ExitFeePerUnit=num(q10(commission/eb/unit)),ExitFeeFloor="0",
           MarginPerUnit=num(q10(margin/unit)))
    return q

def event(id,at,kind,position="NONE",direction=0,units=D(0),
          execution=D(0),fee=D(0),margin=D(0),slip=D(0),quotes=()):
    return dict(EventId=id,At=at,Kind=kind,PositionId=position,Symbol="US500",
        Side=direction,Units=num(units),ExecutionPrice=num(execution),
        FeeEur=num(fee),MarginPerUnit=num(margin),SlippagePerSide=num(slip),
        AvailableAt=max(0,at-1),CalibratedThrough=max(0,at-600000),
        LatencyMs=1,Reason=kind,EvidenceHash=sha256(id.encode()).hexdigest(),
        Quotes=list(quotes))

def events_for(rows,c,margins,trader,policy,slippage):
    events=[];missing=[];weeks=Counter();signal=Counter()
    for row in rows:
        dirs=sides(row["pre"])
        if dirs is None:
            missing.append(dict(week=row["week"],why="PRESIGNAL_UNKNOWN"))
            continue
        direction=dirs[policy]
        if direction==0:
            signal["cashAbstain"]+=1;continue
        signal["predecisionIntents"]+=1
        marks=row["marks"];entry=marks[0]["at"];exit=marks[-1]["at"]
        try:
            valid_interval(c,trader,entry,exit)
            margin=margins[0 if direction>0 else 1]
            need(0<margin<=D(300),"WCR1_UNFINANCEABLE_CURRENT_MINIMUM")
            quoted=[quote(v,c,margin,slippage) for v in marks]
        except (Unpriced,Exception) as error:
            # Preserve ALL missing source, funding and costs; never turn
            # an already chosen intent into a CASH trade.
            missing.append(dict(week=row["week"],why=str(error)[:100]))
            continue
        units=D(c.minVolume)/100
        sp=q10((dec(quoted[0]["Bid"])+dec(quoted[0]["Ask"]))/2*slippage/D(20000))
        pos="wcr1-"+policy+"-"+str(row["week"])
        T=entry;Z=exit
        mq=quoted[0]
        events.append(event(pos+"-mark-entry",T,"MARK",quotes=[mq]))
        events.append(event(pos+"-open-intent",T+1,"REQUEST_OPEN",pos,
                            direction,units,margin=dec(mq["MarginPerUnit"]),slip=sp))
        px=dec(mq["Ask"])+sp if direction>0 else dec(mq["Bid"])-sp
        events.append(event(pos+"-openfill",T+2,"OPEN_FILL",pos,direction,units,px,
                            fee=dec(mq["ExitFeePerUnit"])*units,
                            margin=dec(mq["MarginPerUnit"]),slip=sp))
        for j in (1,2,3):
            mv=quoted[j]
            events.append(event(pos+"-mark-"+str(j),marks[j]["at"],"MARK",
                                quotes=[mv]))
        qend=quoted[-1]
        events.append(event(pos+"-close-intent",Z+1,"REQUEST_CLOSE",pos,direction,units,
                            margin=dec(qend["MarginPerUnit"]),slip=sp))
        px=dec(qend["Bid"])-sp if direction>0 else dec(qend["Ask"])+sp
        events.append(event(pos+"-closefill",Z+2,"CLOSE_FILL",pos,direction,units,px,
                            fee=dec(qend["ExitFeePerUnit"])*units,
                            margin=dec(qend["MarginPerUnit"]),slip=sp))
        weeks[row["week"]]+=1
    return events,missing,dict(signal),[weeks[i] for i in range(52)]

def native_replay(events):
    if not events:
        return dict(netEur=0.,finalCashEur=300.,roundTrips=0,
                    sampledDrawdownFraction=0.,nativeRestartParity=True,
                    duplicateIdempotent=True)
    with tempfile.TemporaryDirectory() as d:
        facts=Path(d)/"facts.json";out=Path(d)/"native.json"
        facts.write_text(json.dumps(events,separators=(",",":")))
        result=subprocess.run(["dotnet","run","--no-build","-c","Release",
             "--project","src/Mxm.Replay","--",str(facts),str(out),
             "--native-funded-facts"],capture_output=True,text=True,timeout=240)
        need(result.returncode==0 and out.exists(),"WCR1_NATIVE_FINANCED_REPLAY_FAILED")
        obj=json.loads(out.read_text())
        need(obj["OrdersSubmitted"]==0 and obj["CloudActivated"] is False
             and obj["RestartEveryEventMatched"] and obj["DuplicatesIdempotent"],
             "WCR1_NATIVE_RESTART_OR_TRADE_AUTHORITY_FAILURE")
        summ=obj["Summary"]
        return dict(netEur=float(summ["ClosedNetEur"]),
                    finalCashEur=float(summ["CashEur"]),
                    roundTrips=int(summ["CompleteRoundTrips"]),
                    sampledDrawdownFraction=float(summ["MaximumSampledDrawdown"]),
                    incompleteHistory=bool(summ["HistoryEvidenceIncomplete"]),
                    nativeRestartParity=True,duplicateIdempotent=True)

def main():
    rows,contracts,margins,trader,receipt,coverage=read_original()
    c=contracts["US500"]
    state=Counter("MISSING_PRESIGNAL" if sides(row["pre"]) is None
                  else "BTC_UP" if sides(row["pre"])["wcr1"]>0
                  else "BTC_DOWN" if sides(row["pre"])["wcr1"]<0
                  else "ZERO_BTC" for row in rows)
    outcome={}
    for name,slip in SCENARIOS.items():
        outcome[name]={}
        for pol in POLICIES:
            if pol=="cash":
                outcome[name][pol]=dict(causalCalendar=52,
                    originalCausalIntentCount=sum(sides(x["pre"]) is not None for x in rows),
                    matchedObservedSubsetNative=dict(netEur=0,roundTrips=0,finalCashEur=300),
                    entirePredecisionCalendarNetEur=0,
                    unknownIntents=0,missingReasons=[],weeklyRoundTrips=[0]*52)
                continue
            events,missing,signal,weekly=events_for(rows,c,margins,trader,pol,slip)
            # This subset is selected by historical *source coverage*, not P&L.
            # It is diagnostically useful but NEVER independent/comparably full.
            try:
                replay=native_replay(events)
                error=None
            except Exception as ex:
                replay=None;error="NATIVE_REPLAY_FAILURE:"+str(ex)[:100]
            outcome[name][pol]=dict(causalCalendar=52,
                originalCausalIntentCount=signal.get("predecisionIntents",0),
                matchedObservedSubsetNative=replay,
                entirePredecisionCalendarNetEur=(replay["netEur"] if not missing and error is None else None),
                unknownIntents=len(missing),missingReasons=missing,
                nativeError=error,weeklyRoundTrips=weekly,
                continuousFloatingDrawdownCertified=False)
    for label in SCENARIOS:
        # Only if both policies have identical covered weeks can a numerical
        # matched incremental claim be made; otherwise explicitly UNKNOWN.
        for ctrl in ("ownMomentum","long","short","cash"):
            p=outcome[label]["wcr1"]
            q=outcome[label][ctrl]
            same=(p["weeklyRoundTrips"]==q["weeklyRoundTrips"])
            outcome[label]["wcr1"]["incrementalVs_"+ctrl+"_Eur"]=(
                round(p["matchedObservedSubsetNative"]["netEur"]
                -q["matchedObservedSubsetNative"]["netEur"],6)
                if same and p["matchedObservedSubsetNative"]
                    and q["matchedObservedSubsetNative"] else None)
    result=dict(schema="MXM_WCR1_AUTHENTIC_ORIGINAL_US500_REOPEN_NATIVE_EUR300_V1",
       frozenProtocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
       originalPepperstoneRunId=receipt["originalRunId"],
       originalSourceCipherSha256=receipt["cipherSha256"],
       originalSourcePlainSha256=receipt["plainSha256"],
       originalSourceRawRequestCount=receipt["originalReadOnlyRequests"],
       originalProtobufIndependentlyReconstructed=True,
       originalSourceSealedBeforeScore=True,
       sourceBarsAndMarks=coverage,
       sampleChronology=52,
       featureCounts=dict(state),currentMinimumUnits=c.minVolume/100,
       currentMarginBuySellEur=[float(x) for x in margins],
       nativeEUR300ConditionalOutcomes=outcome,
       historicalTariffContinuityCertified=False,
       brokerExecutionFills=False,
       continuousFloatingDrawdown30Certified=False,
       systemHard21Certified=False,
       independentChronologyCertified=False,
       oldStudiesRerun=False,
       cloudActivated=False,ordersSubmitted=0)
    OUT.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    report=outcome["adverse"]["wcr1"]
    print("WCR1_AUTHENTIC_ORIGINAL_NATIVE_FINANCE_RECEIPT",
          json.dumps(dict(source=coverage,states=dict(state),
             adverseFull=report["entirePredecisionCalendarNetEur"],
             adverseSubset=report["matchedObservedSubsetNative"],
             unknownIntents=report["unknownIntents"])),flush=True)

if __name__=="__main__":
    main()
