"""CXL1 protected independently authenticated source and native EUR300 matched replay.

Never replays a closed exact strategy. Reconstructs the original CXL1
50-clock pilot and 275 new earlier source ONLY (all 325 fixed endpoints).
Sealed original prices before scoring; C# ledger on same-counterfactual clocks.
"""
from __future__ import annotations
import base64,json,os,math,subprocess,tempfile
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal as D,ROUND_HALF_EVEN
from hashlib import sha256
from pathlib import Path

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .custody import unseal_new
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars,decode_side,need
from .cxl1_original_feasibility import (
    PROTOCOL,calendar,crypto_features,classification,fresh,minimum_contract,
    M5,DAY,DECISION_DELAY,EXIT_DELAY,AGE,BACK,SYMS)
from .cxl1_original_275_source import earlier
from .rne1_source_financial_preflight import fee_usd,Unpriced

PILOT_RUN=43945139889
PILOT_SHA="6e662beec28f0fc0aa987f394a3116d6db004059622cc2b374128af84b45277e"
SOURCE50=Path("cxl1-pilot-encrypted/cxl1-original-feasibility.v2.enc")
RECEIPT50=Path("cxl1-pilot-public/cxl1-original-feasibility-public.json")
SOURCE275=Path("cxl1-new-encrypted/cxl1-earlier-275-authentic.v2.enc")
RECEIPT275=Path("cxl1-new-public/cxl1-original-275-source-public.json")
OUT=Path("cxl1-original-authentic-13week-native-eur300.public.json")
SLIP={"central":D("0.5"),"adverse":D("2.0"),"stress":D("4.0")}
POLICIES=("cxl1","ownEth15","btcAlways","long","short","cash")
SCALE=D(100000)

def dec(v):return D(str(v))
def num(v):return str(v)
def q10(v):return v.quantize(D("0.0000000001"),rounding=ROUND_HALF_EVEN)

def read_archive(cipher_file,receipt_file,private,expected_run,expected_schema,
                 expected_receipt_schema,expected_raw,expected_rows):
    receipt=json.loads(receipt_file.read_text())
    need(receipt["schema"]==expected_receipt_schema,
         "CXL1_CUSTODY_RECEIPT_SCHEMA")
    rid=int(receipt.get("originalRunId",receipt.get("runId")))
    need(rid==expected_run,"CXL1_ORIGINAL_RUN_NOT_BOUND")
    cipher=cipher_file.read_bytes()
    cipherhash=sha256(cipher).hexdigest()
    declared=receipt.get("rawEncryptedSourceSha256",receipt.get("sourceCipherSha256"))
    need(cipherhash==declared,"CXL1_ORIGINAL_CIPHER_HASH_CHANGED")
    plain=unseal_new(cipher,private,str(expected_run))
    plainsha=sha256(plain).hexdigest()
    need(plainsha==receipt.get("rawPlaintextSourceSha256",
                               receipt.get("sourcePlainSha256")),
         "CXL1_ORIGINAL_PLAIN_HASH_CHANGED")
    bound=receipt.get("protocolSha256",receipt.get("sourceProtocolSha256"))
    need(bound==sha256(PROTOCOL.read_bytes()).hexdigest(),
         "CXL1_ORIGINAL_FROZEN_PROTOCOL_CHANGED")
    raw=json.loads(plain)
    need(raw["schema"]==expected_schema
         and str(raw["runId"])==str(expected_run)
         and raw.get("readOnly") is True
         and raw.get("brokerOrders",0)==0
         and raw.get("cloudActivated") is False
         and len(raw["raw"])==expected_raw and len(raw["rows"])==expected_rows,
         "CXL1_ORIGINAL_SOURCE_GEOMETRY")
    if expected_rows==50:
        need(raw["sourcePilotVerdict"]=="CXL1_PILOT_SOURCE_GATES_PASS_NO_OUTCOME_SCORING"
             and all(receipt["sourceGates"].values())
             and receipt["futureLabelUsedInSourceGate"] is False
             and cipherhash==PILOT_SHA,"CXL1_PILOT_IS_NOT_AUTHORIZED_PASS")
    else:
        need(raw["pilotRunReused"]==PILOT_RUN and
             raw["noNewFinanceScoring"] is True,
             "CXL1_NEW_SOURCE_FINANCE_BEFORE_CUSTODY")
    return raw,receipt,dict(cipherSha256=cipherhash,plainSha256=plainsha)

def wire(item):
    q=getattr(m,item["requestType"])()
    a=getattr(m,item["responseType"])()
    q.ParseFromString(base64.b64decode(item["request"],validate=True))
    a.ParseFromString(base64.b64decode(item["response"],validate=True))
    need(q.IsInitialized() and a.IsInitialized(),"CXL1_RAW_PROTO_INVALID")
    require_read_only_request(q)
    return q,a

def reconstruct(body,expect):
    proto=[wire(x) for x in body["raw"]]
    acct=proto[0][0].ctidTraderAccountId
    fp=sha256(("ctrader-account:"+str(acct)).encode()).hexdigest()
    need(sha256(fp.encode()).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and all(getattr(q,"ctidTraderAccountId",acct)==acct
                 and getattr(a,"ctidTraderAccountId",acct)==acct for q,a in proto),
         "CXL1_AUTHENTIC_ACCOUNT_FINGERPRINT_OR_RESPONSE")
    tr=proto[0][1]
    assets={x.assetId:x.name for x in proto[1][1].asset}
    roster=proto[2][1]
    need(type(tr) is m.ProtoOATraderRes
         and type(proto[1][1]) is m.ProtoOAAssetListRes
         and type(roster) is m.ProtoOASymbolsListRes
         and assets.get(tr.trader.depositAssetId)=="EUR"
         and "pepperstone" in tr.trader.brokerName.casefold(),
         "CXL1_RAW_EUR_PEPPERSTONE_NOT_CERTIFIED")
    named={x.symbolName:x for x in roster.symbol if x.enabled}
    need(all(s in named for s in SYMS),"CXL1_ORIGINAL_SYMBOL_DISABLED")
    need(all(assets.get(named[s].quoteAssetId)=="USD" for s in SYMS)
         and assets.get(named["EURUSD"].baseAssetId)=="EUR",
         "CXL1_PNL_CURRENCY_BINDING_UNKNOWN")
    ids={x:named[x].symbolId for x in SYMS}
    contracts={}
    for i,sym in enumerate(SYMS,3):
        req,ans=proto[i]
        need(type(req) is m.ProtoOASymbolByIdReq
             and list(req.symbolId)==[ids[sym]]
             and type(ans) is m.ProtoOASymbolByIdRes
             and len(ans.symbol)==1 and ans.symbol[0].symbolId==ids[sym],
             "CXL1_RAW_CONTRACT_PROTO_INVALID")
        contracts[sym]=ans.symbol[0]
    target=contracts["ETHUSD"]
    minimum_contract(target)
    margin_req,margin=proto[6]
    need(type(margin_req) is m.ProtoOAExpectedMarginReq
         and margin_req.symbolId==ids["ETHUSD"]
         and list(margin_req.volume)==[target.minVolume]
         and type(margin) is m.ProtoOAExpectedMarginRes
         and margin.HasField("moneyDigits") and len(margin.margin)==1
         and margin.margin[0].volume==target.minVolume,
         "CXL1_RAW_CURRENT_TARGET_MARGIN")
    div=D(10)**margin.moneyDigits
    margins=[D(margin.margin[0].buyMargin)/div,
             D(margin.margin[0].sellMargin)/div]
    declared=body.get("currentMinimumMarginEur",body.get("currentBuySellMarginEur"))
    need(margins==[dec(x) for x in declared]
         and target.minVolume==body["currentMinimumVolumeRaw"]
         and all(0<x<=D(210) for x in margins),
         "CXL1_ORIGINAL_MARGIN_NOT_RECONCILED")
    rows=[];idx=7;counts=Counter()
    need(len(body["rows"])==len(expect),"CXL1_INCORRECT_DATES")
    for stored,(day,t) in zip(body["rows"],expect):
        need(stored["day"]==day.isoformat()
             and stored["t"]==t
             and set(stored["bar"])=={"BTCUSD","ETHUSD"}
             and set(stored["quotes"])=={"entry","exit"},
             "CXL1_ORIGINAL_FULL_FIXED_CALENDAR")
        pre={}
        for sym in ("BTCUSD","ETHUSD"):
            req,ans=proto[idx];idx+=1
            note=stored["bar"][sym]
            need(type(req) is m.ProtoOAGetTrendbarsReq
                 and req.symbolId==ids[sym] and req.period==e.M5
                 and req.fromTimestamp==t-DAY-M5 and req.toTimestamp==t
                 and note["rawIndex"]==idx-1,"CXL1_ORIGINAL_RAW_M5_REQUEST")
            trunc=False;closes=None
            if type(ans) is m.ProtoOAErrorRes:
                need(ans.errorCode=="NO_QUOTES","CXL1_HISTORICAL_BAR_ERROR")
            else:
                need(type(ans) is m.ProtoOAGetTrendbarsRes,"CXL1_HISTORICAL_BAR_TYPE")
                trunc=not ans.HasField("hasMore") or ans.hasMore
                if not trunc:
                    got=decode_bars(ans.trendbar,t-DAY-M5,t,5)
                    m5={int(x[1]):int(x[5]) for x in got}
                    times=[t-DAY+j*M5 for j in range(289)]
                    if all(x in m5 and m5[x]>0 for x in times):
                        closes=[m5[x] for x in times]
            need(note["complete"]==(closes is not None)
                 and note["truncated"]==trunc,
                 "CXL1_ORIGINAL_M5_CUSTODY_CONFLICT")
            pre[sym]=crypto_features(closes) if closes else None
            counts["m5_"+sym+"_complete" if closes else "m5_"+sym+"_missing"]+=1
        feat=pre["BTCUSD"] is not None and pre["ETHUSD"] is not None
        direction=classification(pre["BTCUSD"],pre["ETHUSD"])
        own=(1 if pre["ETHUSD"][0]>0 else -1 if pre["ETHUSD"][0]<0 else 0) if pre["ETHUSD"] else None
        need(feat==stored["featureComplete"]
             and direction==stored["leadDirection"]
             and own==stored["ownEthSign"],
             "CXL1_PRESIGNAL_NOT_REPRODUCED_FROM_RAW")
        quote_groups={}
        for kind,at in (("entry",t+DECISION_DELAY),
                        ("exit",t+EXIT_DELAY+DECISION_DELAY)):
            quote_groups[kind]={}
            for sym in ("ETHUSD","EURUSD"):
                note=stored["quotes"][kind][sym]
                need(note["rawIndices"]==[idx,idx+1],"CXL1_RAW_QUOTE_INDICES_CHANGED")
                sides=[];trunc=False
                for typ in (e.BID,e.ASK):
                    req,ans=proto[idx];idx+=1
                    need(type(req) is m.ProtoOAGetTickDataReq
                         and req.symbolId==ids[sym] and req.type==typ
                         and req.fromTimestamp==at-BACK and req.toTimestamp==at,
                         "CXL1_ORIGINAL_QUOTE_REQUEST_CLOCK_OR_SIDE")
                    if type(ans) is m.ProtoOAErrorRes:
                        need(ans.errorCode=="NO_QUOTES","CXL1_ORIGINAL_TICK_ERROR")
                        values=[]
                    else:
                        need(type(ans) is m.ProtoOAGetTickDataRes,
                             "CXL1_RAW_TICK_REPLY_INVALID")
                        trunc|=not ans.HasField("hasMore") or ans.hasMore
                        values=[] if trunc else decode_side(ans.tickData,at-BACK,at)
                    sides.append(values)
                market=None if trunc else fresh(*sides,at)
                need(note["valid"]==(market is not None)
                     and note["truncated"]==trunc,
                     "CXL1_RAW_BIDASK_SIDES_NOT_RECONCILED")
                quote_groups[kind][sym]=market
                counts["quote_"+sym+"_valid" if market else "quote_"+sym+"_unknown"]+=1
        rows.append(dict(day=day.isoformat(),t=t,pre=pre,
                         signal=direction,own=own,marks=quote_groups))
    need(idx==len(proto),"CXL1_RAW_REQUEST_CENSUS_NOT_CONSUMED")
    return rows,contracts,margins,tr.trader,counts

def no_swap(c,trader,entry,exit):
    if trader.HasField("swapFree") and trader.swapFree:return True
    need(c.HasField("swapPeriod") and c.swapPeriod==24 and
         c.HasField("swapTime") and 0<=c.swapTime<1440,
         "CXL1_FINANCING_ROLLOVER_UNSUPPORTED")
    for q in (datetime.fromtimestamp(entry/1000,timezone.utc).date(),
              datetime.fromtimestamp(exit/1000,timezone.utc).date()):
        at=int(datetime(q.year,q.month,q.day,tzinfo=timezone.utc).timestamp()*1000)+c.swapTime*60000
        need(not entry<at<=exit,"CXL1_CURRENT_ROLLOVER_CROSSES_UNPRICED")
    return True

def side(row,policy):
    if policy=="cash":return 0
    if policy=="long":return 1
    if policy=="short":return -1
    if row["signal"] is None:return None
    if policy=="cxl1":return row["signal"]
    if policy=="ownEth15":return row["own"]
    if policy=="btcAlways":
        x=row["pre"]["BTCUSD"]
        return None if x is None else (1 if x[0]>0 else -1 if x[0]<0 else 0)
    raise ValueError("CXL1_POLICY_NOT_FROZEN")

def quote_one(row,at,c,mgn):
    eth=row["ETHUSD"];fx=row["EURUSD"]
    need(eth is not None and fx is not None,
         "CXL1_AUTHENTIC_TARGET_OR_EUR_RATE_UNKNOWN")
    b,a=(D(eth[0][1])/SCALE,D(eth[1][1])/SCALE)
    eb,ea=(D(fx[0][1])/SCALE,D(fx[1][1])/SCALE)
    need(b>0 and a>=b and eb>0 and ea>=eb,"CXL1_INVALID_TICK_QUOTE")
    units=D(c.minVolume)/100
    need(c.HasField("pnlConversionFeeRate"),
         "CXL1_COMMISSION_CONVERSION_FEE_FIELD_UNKNOWN")
    fee_rate=D(c.pnlConversionFeeRate)/D(10000)
    need(0<=fee_rate<1,"CXL1_CONVERSION_FEE_BOUNDS")
    # Native ledger money domain: quote USD to original account EUR, signed.
    credit=(1-fee_rate)/ea
    debit=(1+fee_rate)/eb
    fee=fee_usd(c,units,(a+b)/2)
    need(fee>=0,"CXL1_BROKER_FEE_NEGATIVE")
    return dict(Symbol="ETHUSD",At=at,Bid=num(b),Ask=num(a),
        EurCredit=num(q10(credit)),EurDebit=num(q10(debit)),
        ExitFeePerUnit=num(q10(fee/eb/units)),
        ExitFeeFloor="0",MarginPerUnit=num(q10(mgn/units)))

def event(tag,at,kind,position="NONE",direction=0,units=D(0),price=D(0),
          fee=D(0),margin=D(0),slip=D(0),quotes=()):
    return dict(EventId=tag,At=at,Kind=kind,PositionId=position,
        Symbol="ETHUSD",Side=direction,Units=num(units),
        ExecutionPrice=num(price),FeeEur=num(fee),MarginPerUnit=num(margin),
        SlippagePerSide=num(slip),
        AvailableAt=max(0,at-1),CalibratedThrough=max(0,at-600000),
        LatencyMs=1,Reason=kind,EvidenceHash=sha256(tag.encode()).hexdigest(),
        Quotes=list(quotes))

def make_facts(rows,c,mgn,trader,policy,slippage):
    ev=[];missing=Counter();intents=0;week_intents=[0]*13
    for row in rows:
        trade_side=side(row,policy)
        if trade_side is None:
            missing["CXL1_PREDECISION_FEATURE_UNKNOWN"]+=1
            continue
        if trade_side==0:continue
        intents+=1
        ix=(date.fromisoformat(row["day"])-date(2026,8,17)).days//7
        week_intents[ix]+=1
        T=row["t"]+DECISION_DELAY
        Z=row["t"]+EXIT_DELAY+DECISION_DELAY
        if any(row["marks"][tag][s] is None
               for tag in ("entry","exit") for s in ("ETHUSD","EURUSD")):
            missing["ORIGINAL_BIDASK_ENTRY_EXIT_OR_EUR_UNKNOWN"]+=1
            continue
        if min(mgn)<=0 or max(mgn)>D(210):
            missing["CURRENT_CONTRACT_MARGINS_UNFINANCEABLE"]+=1
            continue
        try:
            no_swap(c,trader,T,Z)
            margin=mgn[0 if trade_side>0 else 1]
            q0=quote_one(row["marks"]["entry"],T,c,margin)
            qz=quote_one(row["marks"]["exit"],Z,c,margin)
        except (ValueError,Unpriced) as ex:
            missing[str(ex)[:90]]+=1
            continue
        u=D(c.minVolume)/100
        sp=q10((dec(q0["Bid"])+dec(q0["Ask"]))/2*slippage/D(20000))
        pos=f"cxl1-{policy}-{row['day']}-{row['t']}"
        ev.append(event(pos+"/atentry",T,"MARK",quotes=[q0]))
        ev.append(event(pos+"/requestopen",T+1,"REQUEST_OPEN",pos,
                        trade_side,u,margin=dec(q0["MarginPerUnit"]),slip=sp))
        opening=dec(q0["Ask"])+sp if trade_side>0 else dec(q0["Bid"])-sp
        ev.append(event(pos+"/openfill",T+2,"OPEN_FILL",pos,trade_side,u,opening,
                        fee=dec(q0["ExitFeePerUnit"])*u,
                        margin=dec(q0["MarginPerUnit"]),slip=sp))
        ev.append(event(pos+"/atexit",Z,"MARK",quotes=[qz]))
        ev.append(event(pos+"/requestclose",Z+1,"REQUEST_CLOSE",pos,
                        trade_side,u,margin=dec(qz["MarginPerUnit"]),slip=sp))
        ending=dec(qz["Bid"])-sp if trade_side>0 else dec(qz["Ask"])+sp
        ev.append(event(pos+"/closefill",Z+2,"CLOSE_FILL",pos,trade_side,u,ending,
                        fee=dec(qz["ExitFeePerUnit"])*u,
                        margin=dec(qz["MarginPerUnit"]),slip=sp))
    return ev,dict(missing),intents,week_intents

def run_native(events):
    if not events:
        return dict(netEur=0.,finalCashEur=300.,roundTrips=0,
            maximumSampledDrawdown=0.,nativeRestartParity=True,
            duplicateIdempotent=True,weeklyFundedTrips=[0]*13)
    with tempfile.TemporaryDirectory() as p:
        infile=Path(p)/"input.json";outfile=Path(p)/"native.json"
        infile.write_text(json.dumps(events,separators=(",",":")))
        result=subprocess.run(["dotnet","run","--no-build","-c","Release",
            "--project","src/Mxm.Replay","--",str(infile),str(outfile),
            "--native-funded-facts"],capture_output=True,text=True,timeout=240)
        need(result.returncode==0 and outfile.exists(),"CXL1_NATIVE_REPLAY_REJECTED")
        original=json.loads(outfile.read_text())
        need(original["OrdersSubmitted"]==0 and
             original["CloudActivated"] is False and
             original["RestartEveryEventMatched"] is True and
             original["DuplicatesIdempotent"] is True,
             "CXL1_NATIVE_EUR300_RESTART_NOT_RECONCILED")
        summary=original["Summary"]
        weeks=[0]*13;weekly_net=[D(0)]*13
        for fill in original["Trades"]:
            when=int(fill["OpenedAt"])
            d=datetime.fromtimestamp(when/1000,timezone.utc).date()
            i=(d-date(2026,8,17)).days//7
            need(0<=i<13,"CXL1_NATIVE_TRADE_OUT_OF_CALENDAR")
            weeks[i]+=1
            weekly_net[i]+=dec(fill["NetEur"])
        need(sum(weeks)==int(summary["CompleteRoundTrips"]),
             "CXL1_NATIVE_TRADE_WEEK_CENSUS")
        return dict(netEur=float(summary["ClosedNetEur"]),
            finalCashEur=float(summary["CashEur"]),
            roundTrips=int(summary["CompleteRoundTrips"]),
            maximumSampledDrawdown=float(summary["MaximumSampledDrawdown"]),
            historyEvidenceIncomplete=bool(summary["HistoryEvidenceIncomplete"]),
            weeklyFundedTrips=weeks,
            weeklyNetEur=[float(x) for x in weekly_net],
            nativeRestartParity=True,duplicateIdempotent=True,
            realBrokerFills=False,continuousFloatingDrawdownCertified=False)

def calculate(rows,contract,margins,trader):
    out={}
    for name,s in SLIP.items():
        score={}
        for policy in POLICIES:
            if policy=="cash":
                score[policy]=dict(sourceCompleteSubsetNetEur=0.,
                    fullCalendarNativeNetEur=0.,sourceUnknownIntents=0,
                    native=dict(netEur=0.,finalCashEur=300.,roundTrips=0,
                                weeklyFundedTrips=[0]*13,weeklyNetEur=[0.]*13))
                continue
            facts,missing,n,week_intents=make_facts(rows,contract,margins,
                                                    trader,policy,s)
            try:
                native=run_native(facts)
                runtime_error=None
            except Exception as err:
                native=None;runtime_error="CXL1_NATIVE_FAILURE:"+str(err)[:120]
            score[policy]=dict(
                causalIntents=n,weeklyRawIntents=week_intents,
                sourceCompleteSubsetNetEur=native["netEur"] if native else None,
                fullCalendarNativeNetEur=(native["netEur"] if
                    native is not None and not missing else None),
                sourceUnknownIntents=sum(missing.values()),
                missingSourceReasons=missing,
                nativeFailure=runtime_error,native=native)
        out[name]=score
    return out

def main():
    secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(secret.strip()),"CXL1_PROTECTED_CUSTODY_SECRET_REQUIRED")
    earlier_data,earlier_receipt,earlier_hash=read_archive(
        SOURCE275,RECEIPT275,secret,int(os.environ["GITHUB_RUN_ID"]),
        "MXM_CXL1_ORIGINAL_275_EARLIER_CLOSED_BAR_AND_QUOTE_SOURCE_V1",
        "MXM_CXL1_ORIGINAL_275_SOURCE_ONLY_V1",2757,275)
    pilot,pilot_receipt,pilot_hash=read_archive(
        SOURCE50,RECEIPT50,secret,PILOT_RUN,
        "MXM_CXL1_ORIGINAL_FIRST_ONLY_PILOT_RAW_PROTOBUF_V1",
        "MXM_CXL1_ORIGINAL_PRESOURCE_PILOT_FEASIBILITY_V1",507,50)
    first,contracts,margin,trader,counts0=reconstruct(earlier_data,earlier())
    rest,old_contracts,old_margin,old_trader,counts1=reconstruct(
        pilot,[(d,t) for d,t in calendar() if d>=date(2026,11,2)])
    need(contracts["ETHUSD"].SerializeToString()==
         old_contracts["ETHUSD"].SerializeToString()
         and margins_equal(margin,old_margin),
         "CXL1_BROKER_TERMS_DIFFER_PILOT_VERSUS_FULL_SOURCE")
    rows=first+rest
    need(len(rows)==325 and [x["t"] for x in rows]==[t for _,t in calendar()],
         "CXL1_FULL_NATIVE_CALENDAR_NOT_325")
    # New sealed original outcome readback begins HERE after both
    # source archives were independently proven from raw protobuf.
    outcomes=calculate(rows,contracts["ETHUSD"],margin,trader)
    strictly_complete=[x for x in rows if
        x["signal"] is not None and
        all(x["marks"][tag][s] is not None
            for tag in ("entry","exit") for s in ("ETHUSD","EURUSD"))]
    matched=calculate(strictly_complete,contracts["ETHUSD"],margin,trader)
    summary=dict(schema="MXM_CXL1_ORIGINAL_13WEEK_NATIVE_EUR300_MATCHED_V1",
        originalPilotRunId=PILOT_RUN,
        pilotOriginalCiphers=pilot_hash,
        newOriginalSourceRunId=earlier_receipt["runId"],
        newOriginalSourceCiphers=earlier_hash,
        frozenProtocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),
        allOriginalRawProtobufReconstructed=True,
        onePepperstoneOriginalEurAccount=True,
        sourceSealedBeforeOutcome=True,
        oldStudiesRerun=False,
        originalSourceReadOnlyRequests=507+2757,
        originalSourceClocks=325,originalPilotClocksReused=50,
        authenticCausalBarCoverage={
            "BTCUSD":counts0["m5_BTCUSD_complete"]+counts1["m5_BTCUSD_complete"],
            "ETHUSD":counts0["m5_ETHUSD_complete"]+counts1["m5_ETHUSD_complete"]},
        originalQuoteCoverage={
            s:counts0["quote_"+s+"_valid"]+counts1["quote_"+s+"_valid"]
            for s in ("ETHUSD","EURUSD")},
        featureComplete=sum(x["signal"] is not None for x in rows),
        rawCausalBtcLeadsIntents=sum(x["signal"] not in (0,None) for x in rows),
        strictlyMatchedOriginalCompleteClocks=len(strictly_complete),
        currentVolumeUnits=contracts["ETHUSD"].minVolume/100,
        currentBuySellMinimumMarginEur=[float(x) for x in margin],
        slippageScenariosBps={x:str(y) for x,y in SLIP.items()},
        fullCalendarPolicyOutcomes=outcomes,
        matchedAllPoliciesOnSameSourceCompleteClocks=matched,
        fullCalendarCostUncertainty=True,
        noBrokerActualFills=True,noHistoricalTariffCertification=True,
        noContinuousFloatDdCertificate=True,
        hard21SystemicNotProven=True,
        noIndependentChronology=True,
        noNativeCloudColdStartParityCertificate=True,
        brokerOrders=0,cloudActivated=False)
    OUT.write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("CXL1_ORIGINAL_AUTHENTIC_NATIVE_EUR300",json.dumps(dict(
        clocks=325,priced=len(strictly_complete),
        signal=summary["rawCausalBtcLeadsIntents"],
        netAdverseFull=outcomes["adverse"]["cxl1"]["fullCalendarNativeNetEur"],
        netAdverseMatched=matched["adverse"]["cxl1"]["sourceCompleteSubsetNetEur"],
        matchingOwnAdverse=matched["adverse"]["ownEth15"]["sourceCompleteSubsetNetEur"])),flush=True)

def margins_equal(a,b):
    return len(a)==len(b) and all(x==y for x,y in zip(a,b))

if __name__=="__main__":
    main()
