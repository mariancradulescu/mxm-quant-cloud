"""BCF1: once-only EUR bond curve source-only coverage, contract and quote preflight.

Reuse existing Pepperstone SCOPE_VIEW authentication, transport, protobuf read-only
allowlist and installed RSA custody. NEVER construct signals or inspect returns.
Older 52-week calendar is globally exposed; post-Nov-2 rows remain sealed and
are not confirmation without a separately preregistered candidate/protocol.
"""
import hashlib, json, os, sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import median
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars, decode_side
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .full_inventory_pipeline import _raw_record
from .csp1_cost_preflight import asof_spread
from .mbf1_source import wire_pairs

P=Path("research/bcf1_protocol.json")
W=604800000
H=3600000
SCHEMA="MXM_BCF1_SEALED_SOURCE_V1"

def need(v,code):
    if not v: raise ValueError("BCF1_"+code)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def p_read():
    p=json.loads(P.read_text())
    need(p["id"]=="BCF1" and p["locked"] and p["status"]=="PREDECLARED_UNSCORED_SOURCE_GATE", "PROTOCOL")
    need(p["instruments"]==["EUBobl-F","EUBund-F"] and p["ownerCapitalProspectiveEur"]==300,"LOCKED_UNIVERSE")
    need(p["historicalSource"]["weeks"]==52 and p["quoteCostPreflight"]["developmentWeeks"]==13,"CALENDAR")
    need(p["operations"]["expectedBrokerReadOnlyRequests"]==165,"BUDGET")
    need(p["newChronologicalSource"]["endUtcMs"]==1793937600000,"NEW_CALENDAR")
    return p

def periods(p):
    s=p["historicalSource"]["startUtcMs"]
    arr=[(s+i*W,s+(i+1)*W,"historical_exposed") for i in range(52)]
    f=p["newChronologicalSource"]
    arr.append((f["startUtcMs"],f["endUtcMs"],"chronological_new_unscored"))
    return arr

def clocks(p):
    base=p["historicalSource"]["startUtcMs"]
    o=p["quoteCostPreflight"]["quoteClockHourUtcWeeklyOffset"]*H
    return [base+w*W+o for w in range(13)]

def reconstruct(raw,p):
    pairs=wire_pairs(raw)  # unchanged read-only protobuf identity checks
    need(len(pairs)==165,"RAW_COUNT")
    (tq,tr),(aq,ar),(lq,lr)=pairs[:3]
    need(type(tq) is m.ProtoOATraderReq and type(aq) is m.ProtoOAAssetListReq
         and type(lq) is m.ProtoOASymbolsListReq,"HEADER")
    account=int(tr.ctidTraderAccountId)
    fp=sha(("ctrader-account:"+str(account)).encode())
    need(sha(fp.encode())==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and
         all(q.ctidTraderAccountId==account for q,r in pairs),"EXACT_ORIGINAL_ACCOUNT")
    assets={x.assetId:x.name for x in ar.asset}
    need("pepperstone" in tr.trader.brokerName.casefold() and
         assets.get(tr.trader.depositAssetId)=="EUR" and
         lq.HasField("includeArchivedSymbols") and not lq.includeArchivedSymbols,
         "PEPPERSTONE_EUR")
    listed={x.symbolName:x for x in lr.symbol if x.enabled}
    need(all(s in listed for s in p["instruments"]),"INSTRUMENT_NOT_VISIBLE")
    terms,ids={},{}
    ix=3
    for name in p["instruments"]:
        sid=listed[name].symbolId
        ids[name]=sid
        cq,cr=pairs[ix];mq,mr=pairs[ix+1];ix+=2
        need(type(cq) is m.ProtoOASymbolByIdReq and list(cq.symbolId)==[sid] and
             len(cr.symbol)==1 and cr.symbol[0].symbolId==sid,"CONTRACT_REPLY")
        contract=cr.symbol[0]
        need(contract.HasField("minVolume") and contract.minVolume>0 and
             contract.HasField("stepVolume") and contract.stepVolume>0 and
             contract.HasField("maxVolume") and contract.maxVolume>=contract.minVolume and
             int(contract.tradingMode)==0,"CURRENT_TRADING_CONTRACT")
        need(type(mq) is m.ProtoOAExpectedMarginReq and mq.symbolId==sid and
             list(mq.volume)==[contract.minVolume] and mr.HasField("moneyDigits") and
             len(mr.margin)==1 and mr.margin[0].volume==contract.minVolume,"MARGIN_BINDING")
        mar=mr.margin[0]
        need(mar.buyMargin>=0 and mar.sellMargin>=0 and 0<=mr.moneyDigits<=12,"MARGIN_WIRE")
        margin=max(Decimal(mar.buyMargin),Decimal(mar.sellMargin))/(Decimal(10)**mr.moneyDigits)
        terms[name]=dict(currentMinimumMarginEur=str(margin),
            minVolumeUnits=str(Decimal(contract.minVolume)/100),
            stepVolumeUnits=str(Decimal(contract.stepVolume)/100),
            maxVolumeUnits=str(Decimal(contract.maxVolume)/100),
            openingTradingModeObserved=True,
            commissionRateWirePresent=contract.HasField("preciseTradingCommissionRate"),
            minimumCommissionWirePresent=contract.HasField("minCommission"),
            fundingSwapLongWirePresent=contract.HasField("swapLong"),
            fundingSwapShortWirePresent=contract.HasField("swapShort"))
    hist={s:set() for s in p["instruments"]}
    newer={s:set() for s in p["instruments"]}
    trunc=[]
    for a,b,phase in periods(p):
        for name in p["instruments"]:
            q,r=pairs[ix];ix+=1
            need(type(q) is m.ProtoOAGetTrendbarsReq and q.symbolId==ids[name] and
                 q.period==e.H1 and q.fromTimestamp==a and q.toTimestamp==b and
                 r.period==e.H1 and r.HasField("hasMore"),"H1_PERIOD_AND_ACCOUNT")
            if r.hasMore:
                trunc.append(dict(symbol=name,beginUtcMs=a,phase=phase))
                continue
            dest=hist if phase=="historical_exposed" else newer
            for row in decode_bars(r.trendbar,a-H,b+H,60):
                if a<=row[0] and row[1]<=b:
                    dest[name].add(int(row[1]))  # no prices/signals/returns
    qstat={s:Counter() for s in p["instruments"]}
    spread={s:[] for s in p["instruments"]}
    pre=p["quoteCostPreflight"]
    for clock in clocks(p):
        for name in p["instruments"]:
            values={};complete=True
            for side in (e.BID,e.ASK):
                q,r=pairs[ix];ix+=1
                need(type(q) is m.ProtoOAGetTickDataReq and q.symbolId==ids[name] and
                     q.type==side and q.fromTimestamp==clock-pre["lookbackMs"] and
                     q.toTimestamp==clock and r.HasField("hasMore"),"QUOTE_CLOCK_BINDING")
                complete &= not r.hasMore
                values[side]=[] if r.hasMore else decode_side(r.tickData,clock-pre["lookbackMs"],clock)
            x=asof_spread(values[e.BID],values[e.ASK],clock,
                          pre["maxQuoteAgeMs"],pre["maxSideSkewMs"],complete)
            qstat[name][x["status"]]+=1
            if x["status"]=="CAUSAL_PAIRED_SPREAD_OBSERVED":
                spread[name].append(float(x["spreadBps"]))
    need(ix==len(pairs),"TRAILING_RAW_UNREAD")
    start=p["historicalSource"]["startUtcMs"]
    joint_by_week=[]
    for w in range(52):
        a,b=start+w*W,start+(w+1)*W
        joint=hist[p["instruments"][0]] & hist[p["instruments"][1]]
        joint_by_week.append(sum(a<=t<b for t in joint))
    cost_rows={}
    for s in p["instruments"]:
        xs=sorted(spread[s])
        cost_rows[s]=dict(validFreshPairedBidAsk=len(xs),
             costClockSlots=len(clocks(p)),
             missingCostObservationStatuses=dict(qstat[s]),
             observedSpreadMedianBps=median(xs) if xs else None,
             observedSpreadP90Bps=xs[max(0,(9*len(xs)+9)//10-1)] if xs else None,
             fullHistoricalRoundTripCostCertified=False)
    minimum=sum(Decimal(terms[s]["currentMinimumMarginEur"]) for s in p["instruments"])
    reasons=[]
    if any(z["validFreshPairedBidAsk"]<pre["minimumValidPairedQuoteClocksEach"] for z in cost_rows.values()):
        reasons.append("AUTHENTIC_PAIRED_QUOTES_BELOW_MINIMUM")
    if sum(x>0 for x in joint_by_week)<p["sourceFeasibility"]["minimumJointWeeklyHistoricalCoverage"]:
        reasons.append("JOINT_H1_WEEK_COVERAGE_BELOW_MINIMUM")
    if sum(joint_by_week)<p["sourceFeasibility"]["minimumJointHistoryH1Closes"]:
        reasons.append("JOINT_H1_OBSERVATIONS_BELOW_MINIMUM")
    if trunc:
        reasons.append("SOURCE_PAGE_TRUNCATED_OR_INCOMPLETE")
    if minimum>=300:
        reasons.append("CURRENT_STATIC_MINIMUM_MARGIN_EXCEEDS_CAPITAL")
    # Even with excellent quoted cost and technical coverage, physical funded
    # evaluation remains prohibited without future fully locked economic protocol.
    return dict(schema="MXM_BCF1_AUTHENTIC_UNSCORED_BOND_CURVE_PREFLIGHT_V1",
         originalAccountAndProtobufReauthenticated=True,readOnlyRequestCount=len(pairs),
         sourceHistorical52WeekGloballyExposed=True,
         historicalH1TimestampCountBySymbol={s:len(hist[s]) for s in p["instruments"]},
         chronologicalNewSourceStartUtcMs=p["newChronologicalSource"]["startUtcMs"],
         chronologicalNewSourceEndUtcMs=p["newChronologicalSource"]["endUtcMs"],
         newChronologicalH1TimestampCountBySymbol={s:len(newer[s]) for s in p["instruments"]},
         newChronologicalPriceOutcomesUnobservedByResearch=True,
         jointCompletedH1TimesPerExposedWeek=joint_by_week,
         numberExposedWeeksWithJointHistory=sum(v>0 for v in joint_by_week),
         sourceTruncations=trunc,contractCurrentTerms=terms,
         sumCurrentMinimumMarginEur=str(minimum),
         currentStaticMinimumMarginFits300=minimum<300,
         quoteCostObservations=cost_rows,
         observableSourcePreflightPass=not reasons,
         blockingReasons=reasons,
         economicallyDistinctPotential="EUR_BOND_DURATION_CURVE_POLICY_RATE_TERM_PREMISE_NOT_SCORED",
         predictorOrReturnsScored=False,conditionalGrossBps=None,
         conditionalCentralNetBps=None,conditionalAdverseNetBps=None,
         commonCSharpFinancedRoundTrips=0,brokerFundedNetEur=None,
         technicalObservationCountIsNotHard21=True,
         hard21Certified=False,drawdown30Certified=False,
         independentConfirmation=False,cloudActivated=False,ordersSubmitted=0)

def collect():
    p=p_read()
    need(not Path("docs/BCF1_AUTHENTIC_SOURCE_GATE.json").exists(),"CLOSED_GATE")
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-source-recipient"),run)
    t=StdlibCTraderTransport()
    raw=[]
    def req(q,klass,account):
        need(len(raw)<p["operations"]["maxBrokerReadOnlyRequests"],"REQUEST_BUDGET")
        require_read_only_request(q)
        r=t.request(q)
        need(type(r) is klass and r.IsInitialized() and
             r.ctidTraderAccountId==account,"BROKER_RESPONSE_AND_ACCOUNT")
        raw.append(_raw_record(q,r));return r
    try:
        account=authenticate(t)
        req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes,account)
        req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes,account)
        listing=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                     includeArchivedSymbols=False),m.ProtoOASymbolsListRes,account)
        visible={s.symbolName:s for s in listing.symbol if s.enabled}
        need(all(s in visible for s in p["instruments"]),"UNIVERSE_NOT_VISIBLE")
        for s in p["instruments"]:
            sid=visible[s].symbolId
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                             symbolId=[sid]),m.ProtoOASymbolByIdRes,account)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==sid and
                 detail.symbol[0].minVolume>0,"CONTRACT_NOT_AVAILABLE")
            req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                       symbolId=sid,volume=[detail.symbol[0].minVolume]),
                       m.ProtoOAExpectedMarginRes,account)
        for a,b,phase in periods(p):
            for s in p["instruments"]:
                req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                    symbolId=visible[s].symbolId,period=e.H1,
                    fromTimestamp=a,toTimestamp=b),m.ProtoOAGetTrendbarsRes,account)
        for stamp in clocks(p):
            for s in p["instruments"]:
                for side in (e.BID,e.ASK):
                    req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                       symbolId=visible[s].symbolId,type=side,
                       fromTimestamp=stamp-p["quoteCostPreflight"]["lookbackMs"],
                       toTimestamp=stamp),m.ProtoOAGetTickDataRes,account)
        need(len(raw)==p["operations"]["expectedBrokerReadOnlyRequests"],"EXACT_REQUEST_COUNT")
        sealed=seal_new(json.dumps(dict(schema=SCHEMA,runId=run,
                         protocolSha256=sha(P.read_bytes()),raw=raw),
                         sort_keys=True).encode(),recipient,run)
        out=Path("sealed-output");out.mkdir(exist_ok=True)
        (out/"source.envelope.json").write_bytes(sealed)
        (out/"receipt.public.json").write_text(json.dumps(dict(
            schema=SCHEMA,runId=run,protocolSha256=sha(P.read_bytes()),
            ciphertextSha256=sha(sealed),complete=True,ordersSubmitted=0))+"\n")
        print("BCF1_READ_ONLY_ORIGINAL_ACCOUNT_SEALED_NO_PREDICTOR",flush=True)
    finally:
        t.close()

def readback():
    p=p_read()
    run=os.environ["GITHUB_RUN_ID"]
    sealed=Path("sealed-output/source.envelope.json").read_bytes()
    receipt=json.loads(Path("sealed-output/receipt.public.json").read_text())
    need(receipt["schema"]==SCHEMA and receipt["runId"]==run and
         receipt["protocolSha256"]==sha(P.read_bytes()) and
         receipt["ciphertextSha256"]==sha(sealed) and receipt["complete"],"CUSTODY_BINDING")
    b=json.loads(unseal_new(sealed,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),run))
    need(b["schema"]==SCHEMA and b["runId"]==run and
         b["protocolSha256"]==sha(P.read_bytes()),"DECRYPTED_PROTOCOL_BINDING")
    result=reconstruct(b["raw"],p)
    result.update(sourceRunId=int(run),sourceEncryptedCiphertextSha256=sha(sealed),
                  protocolSha256=sha(P.read_bytes()),rawReadbackComplete=True)
    Path("bcf1.public.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("BCF1_COVERAGE_AND_COST_PREFLIGHT_ONLY "+
        json.dumps({k:result[k] for k in (
        "sourceRunId","readOnlyRequestCount","numberExposedWeeksWithJointHistory",
        "newChronologicalH1TimestampCountBySymbol","observableSourcePreflightPass",
        "blockingReasons","currentStaticMinimumMarginFits300")},sort_keys=True),flush=True)

if __name__=="__main__":
    try:
        readback() if "--readback" in sys.argv else collect()
    except Exception:
        print("BCF1_FAILED_CLOSED_NO_SENSITIVE_DETAIL",flush=True)
        raise SystemExit(1)
