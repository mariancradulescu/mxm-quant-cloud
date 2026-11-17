"""DVI1-A1: NEW chronological economic action-value learning on original CXL1 SOURCE ONLY.

Never executes CXL1's historical rule/policies or its economic scorer. Source reader
verifies untouched original protobuf/ciphertext. The DVI1 policy, targets, fixed
calendar and evaluators were frozen separately at ffd7284f BEFORE this code.
All 13 weeks are globally exposed development. No orders, no Cloud.
"""
from __future__ import annotations
import json,math,os,statistics,subprocess,tempfile
from collections import Counter,defaultdict
from datetime import date,datetime,timezone
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path

from .decode import need
from .cxl1_original_feasibility import calendar,DECISION_DELAY,EXIT_DELAY
# Authenticate ORIGINAL source geometry only; never import/call closed CXL1 scoring.
from .cxl1_original_native_eur_readback import (
    read_archive,reconstruct,no_swap,quote_one,dec,q10,SOURCE50,
    RECEIPT50,SOURCE275,RECEIPT275,PILOT_RUN)
from .cxl1_original_275_source import earlier

PROTOCOL=Path("research/DVI1_A1_FROZEN_ACTION_VALUE_PROTOCOL_20261117.md")
OUT=Path("dvi1-a1-original-new-action-value-native-eur300.public.json")
ORIGINAL_275_RUN=43947388854
START=date(2026,8,17)
WEEK=7*86400000
HALF_HOUR=30*60000
EMBARGO=60*60000
SCENARIOS={"central":D("0.5"),"adverse":D("2.0")}
VARIANTS=("FULL","OWN","POOLED","CASH")

def f(x):return float(x)
def sign(x):return (1 if x>0 else -1 if x<0 else 0)
def iso_day_ms(t):return datetime.fromtimestamp(t/1000,timezone.utc).date()
def index_of(t):
    return (iso_day_ms(t)-START).days//7

def load_authentic_source():
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"DVI1_PROTECTED_CUSTODY_SECRET_REQUIRED")
    # Read original stored receipts with original run IDs. This is not an older
    # evaluator run; the source has no DVI1 labels or policy scores.
    p275,r275,h275=read_archive(SOURCE275,RECEIPT275,private,ORIGINAL_275_RUN,
        "MXM_CXL1_ORIGINAL_275_EARLIER_CLOSED_BAR_AND_QUOTE_SOURCE_V1",
        "MXM_CXL1_ORIGINAL_275_SOURCE_ONLY_V1",2757,275)
    p50,r50,h50=read_archive(SOURCE50,RECEIPT50,private,PILOT_RUN,
        "MXM_CXL1_ORIGINAL_FIRST_ONLY_PILOT_RAW_PROTOBUF_V1",
        "MXM_CXL1_ORIGINAL_PRESOURCE_PILOT_FEASIBILITY_V1",507,50)
    first,c0,m0,trader,counts0=reconstruct(p275,earlier())
    rest,c1,m1,trader1,counts1=reconstruct(
        p50,[(d,t) for d,t in calendar() if d>=date(2026,11,2)])
    need(c0["ETHUSD"].SerializeToString()==c1["ETHUSD"].SerializeToString()
         and m0==m1,"DVI1_ORIGINAL_CONTRACTS_NOT_IDENTICAL")
    rows=first+rest
    need(len(rows)==325 and all(x["t"]==t for x,(_,t) in zip(rows,calendar())),
         "DVI1_EXACT_325_SOURCE_CLOCKS_NOT_RECONSTRUCTED")
    return rows,c0["ETHUSD"],m0,trader,dict(
        sourceRunIds=[ORIGINAL_275_RUN,PILOT_RUN],
        sourceCiphertextSha256=[h275["cipherSha256"],h50["cipherSha256"]],
        sourcePlaintextSha256=[h275["plainSha256"],h50["plainSha256"]],
        originalReadOnlyProtobufRequests=3264,
        authenticatedM5=dict(BTCUSD=counts0["m5_BTCUSD_complete"]+counts1["m5_BTCUSD_complete"],
                             ETHUSD=counts0["m5_ETHUSD_complete"]+counts1["m5_ETHUSD_complete"]),
        authenticEntryExitPairs=dict(ETHUSD=counts0["quote_ETHUSD_valid"]+counts1["quote_ETHUSD_valid"],
                                     EURUSD=counts0["quote_EURUSD_valid"]+counts1["quote_EURUSD_valid"]))

def usd_eur(usd,quote):
    return usd*dec(quote["EurCredit"] if usd>=0 else quote["EurDebit"])

def economic_label(q0,qz,u,side,bps):
    """Original bid/ask both legs; current-tariff + explicitly modeled slippage."""
    mid0=(dec(q0["Bid"])+dec(q0["Ask"]))/2
    midz=(dec(qz["Bid"])+dec(qz["Ask"]))/2
    slip0=mid0*bps/D(20000)
    slipz=midz*bps/D(20000)
    start=(dec(q0["Ask"])+slip0 if side>0 else dec(q0["Bid"])-slip0)
    end=(dec(qz["Bid"])-slipz if side>0 else dec(qz["Ask"])+slipz)
    dollars=(end-start)*u*D(side)
    commission=(dec(q0["ExitFeePerUnit"])+dec(qz["ExitFeePerUnit"]))*u
    net=usd_eur(dollars,qz)-commission
    mid_gross=usd_eur((midz-mid0)*u*D(side),qz)
    return dict(net=net,gross=mid_gross,friction=mid_gross-net,commission=commission)

def new_row(item,contract,margins,trader):
    t=item["t"];T=t+DECISION_DELAY;Z=t+EXIT_DELAY+DECISION_DELAY
    btc=item["pre"]["BTCUSD"];eth=item["pre"]["ETHUSD"]
    result=dict(day=item["day"],t=t,entryAt=T,exitAt=Z,
        week=index_of(t),E=None if eth is None else sign(eth[0]),
        B=None if btc is None else sign(btc[0]),
        sourceValid=False,unknown=None,quotes=None,labels={})
    if btc is None or eth is None:
        result["unknown"]="PREDICISION_COMPLETED_M5_UNKNOWN"
        return result
    if any(item["marks"][k][s] is None
           for k in ("entry","exit") for s in ("ETHUSD","EURUSD")):
        result["unknown"]="ORIGINAL_ENTRY_EXIT_BIDASK_OR_EUR_MISSING"
        return result
    try:
        no_swap(contract,trader,T,Z)
        quotes={}
        for k,at in (("entry",T),("exit",Z)):
            # Use quote-side original market only for labels and native fills,
            # never as a DVI1 predictive feature.
            quotes[k]={direction:quote_one(item["marks"][k],at,contract,
                            margins[0 if direction>0 else 1])
                       for direction in (1,-1)}
        u=D(contract.minVolume)/100
        for name,bps in SCENARIOS.items():
            result["labels"][name]={d:economic_label(quotes["entry"][d],
                                  quotes["exit"][d],u,d,bps) for d in (1,-1)}
        result["zeroPriceCostOnly"]={
            d:economic_label(quotes["entry"][d],quotes["entry"][d],
                             u,d,SCENARIOS["adverse"])["net"] for d in (1,-1)}
        result["sourceValid"]=True;result["quotes"]=quotes
    except Exception as exc:
        why=str(exc)
        result["unknown"]=why if why.isupper() and len(why)<130 else type(exc).__name__
    return result

def historical_pool(known,t,variant,E,B):
    """Matured labels only, exact 60-minute embargo and no future path gate."""
    pool=[]
    for x in known:
        if not x["sourceValid"] or not x["exitAt"]<t-EMBARGO:
            continue
        if variant in ("OWN","FULL") and x["E"]!=E:continue
        if variant=="FULL" and x["B"]!=B:continue
        pool.append(x)
    return pool

def score_side(pool,side):
    n=len(pool)
    weekly=defaultdict(list)
    for x in pool:weekly[x["week"]].append(float(x["labels"]["adverse"][side]["net"]))
    if n<20 or len(weekly)<4:
        return dict(n=n,blocks=len(weekly),mean=0.,se=None,score=None,positiveProbability=None,eligible=False)
    # Small sample weekly blocks, no independence or confidence claim.
    block_means=[statistics.mean(values) for _,values in sorted(weekly.items())]
    se=statistics.stdev(block_means)/math.sqrt(len(block_means)) if len(block_means)>1 else float("inf")
    mean=sum(float(x["labels"]["adverse"][side]["net"]) for x in pool)/(n+32)
    positive=(sum(x["labels"]["adverse"][side]["net"]>0 for x in pool)+1)/(n+2)
    return dict(n=n,blocks=len(weekly),mean=mean,se=se,score=mean-se,
                positiveProbability=positive,eligible=True)

def predict(known,t,variant,E,B):
    if variant=="CASH":return dict(action=0,reason="CASH_REFERENCE",sideForecasts={})
    if E is None or B is None or E==0 or B==0:
        return dict(action=0,reason="PREDECISION_SIGN_UNKNOWN_OR_ZERO",sideForecasts={})
    pool=historical_pool(known,t,variant,E,B)
    values={d:score_side(pool,d) for d in (1,-1)}
    if any(not x["eligible"] for x in values.values()):
        return dict(action=0,reason="MATURED_BLOCK_SUPPORT_LOW",sideForecasts=values)
    lo,sh=values[1]["score"],values[-1]["score"]
    choice=(1 if lo>0 and lo>sh else -1 if sh>0 and sh>lo else 0)
    return dict(action=choice,reason="POSITIVE_INCREMENTAL_VALUE" if choice else "CASH_BETTER_OR_TIE",
                sideForecasts=values)

def fact(tag,at,kind,quote=None,position="",side=0,u=D(0),price=D(0),fee=D(0),
         margin=D(0),slip=D(0)):
    return dict(EventId=tag,At=at,Kind=kind,PositionId=position,
        Symbol="ETHUSD",Side=side,Units=str(u),ExecutionPrice=str(price),
        FeeEur=str(fee),MarginPerUnit=str(margin),SlippagePerSide=str(slip),
        AvailableAt=at-1,CalibratedThrough=at-600000,LatencyMs=1,
        Reason="DVI1_A1_CONDITIONAL_SOURCE_REPLAY",EvidenceHash=sha256(tag.encode()).hexdigest(),
        Quotes=([quote] if quote is not None else []))

def native_events(selected,u,scenario,variant):
    events=[]
    for x,side in selected:
        t,z=x["entryAt"],x["exitAt"]
        q0=x["quotes"]["entry"][side];qz=x["quotes"]["exit"][side]
        bps=SCENARIOS[scenario]
        mid0=(dec(q0["Bid"])+dec(q0["Ask"]))/2
        midz=(dec(qz["Bid"])+dec(qz["Ask"]))/2
        slip0=q10(mid0*bps/D(20000));slipz=q10(midz*bps/D(20000))
        pos=f"DVI1/{variant}/{scenario}/{t}"
        events.append(fact(pos+"/mark0",t,"MARK",quote=q0))
        events.append(fact(pos+"/request0",t+1,"REQUEST_OPEN",position=pos,
            side=side,u=u,margin=dec(q0["MarginPerUnit"]),slip=slip0))
        opening=dec(q0["Ask"])+slip0 if side>0 else dec(q0["Bid"])-slip0
        events.append(fact(pos+"/openfill",t+2,"OPEN_FILL",position=pos,
            side=side,u=u,price=opening,fee=dec(q0["ExitFeePerUnit"])*u,
            margin=dec(q0["MarginPerUnit"]),slip=slip0))
        events.append(fact(pos+"/markz",z,"MARK",quote=qz))
        events.append(fact(pos+"/requestz",z+1,"REQUEST_CLOSE",position=pos,
            side=side,u=u,margin=dec(qz["MarginPerUnit"]),slip=slipz))
        ending=dec(qz["Bid"])-slipz if side>0 else dec(qz["Ask"])+slipz
        events.append(fact(pos+"/closefill",z+2,"CLOSE_FILL",position=pos,
            side=side,u=u,price=ending,fee=dec(qz["ExitFeePerUnit"])*u,
            margin=dec(qz["MarginPerUnit"]),slip=slipz))
    return events

def run_native(events):
    if not events:
        return dict(nativeInvoked=False,netEur=0.,finalCashEur=300.,roundTrips=0,
                    sampledDrawdown=None,weeklyCompletions=[0]*8,
                    nativeRestartParity=None,historyEvidenceIncomplete=None)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td);source=p/"events.json";out=p/"native.json"
        source.write_text(json.dumps(events,separators=(",",":")))
        command=["dotnet","run","--no-build","-c","Release","--project",
                 "src/Mxm.Replay","--",str(source),str(out),"--native-funded-facts"]
        proc=subprocess.run(command,capture_output=True,text=True,timeout=240)
        need(proc.returncode==0 and out.exists(),
             "DVI1_NATIVE_FINANCIAL_REPLAY_FAILED")
        data=json.loads(out.read_text())
        need(data["OrdersSubmitted"]==0 and data["CloudActivated"] is False
             and data["RestartEveryEventMatched"] is True
             and data["DuplicatesIdempotent"] is True,"DVI1_NATIVE_LEDGER_IDEMPOTENCY_FAILED")
        summary=data["Summary"]
        weeks=[0]*8
        for x in data["Trades"]:
            idx=(iso_day_ms(int(x["OpenedAt"]))-START).days//7-5
            need(0<=idx<8,"DVI1_NATIVE_TRADE_OUT_OF_EVALUATION")
            weeks[idx]+=1
        need(sum(weeks)==int(summary["CompleteRoundTrips"]),
             "DVI1_NATIVE_COMPLETED_TRADE_MISMATCH")
        return dict(nativeInvoked=True,netEur=float(summary["ClosedNetEur"]),
            finalCashEur=float(summary["CashEur"]),
            roundTrips=int(summary["CompleteRoundTrips"]),
            sampledDrawdown=float(summary["MaximumSampledDrawdown"]),
            historyEvidenceIncomplete=bool(summary["HistoryEvidenceIncomplete"]),
            weeklyCompletions=weeks,
            nativeRestartParity=True,duplicateIdempotency=True,
            sourceIsGenuineQuoteAndCurrentTermsModel=True,
            historicalBrokerFillsCertified=False,continuousDDCertified=False)

def run_policy(rows,variant,scenario,u):
    known=[];selection=[];reasons=Counter();predictions=[];sampledCash=D(300);peak=D(300)
    marginDeclines=0;costOnlyError=0.;valueError=0.;predictCount=0
    for x in rows:
        if x["week"]<5:
            known.append(x)
            continue
        need(5<=x["week"]<13,"DVI1_UNKNOWN_EVALUATION_WEEK")
        forecast=predict(known,x["t"],variant,x["E"],x["B"])
        side=forecast["action"];reason=forecast["reason"]
        # Update history only AFTER constructing this clock's prediction.
        eligible=historical_pool(known,x["t"],variant,x["E"],x["B"]) if variant!="CASH" else []
        if eligible:need(max(y["exitAt"] for y in eligible)<x["t"]-EMBARGO,
                         "DVI1_FUTURE_LABEL_LEAKAGE")
        if x["sourceValid"] and variant!="CASH":
            for d in (1,-1):
                model=forecast["sideForecasts"].get(d,{}).get("mean")
                if model is not None:
                    actual=float(x["labels"]["adverse"][d]["net"])
                    valueError+=(model-actual)**2
                    costOnlyError+=(float(x["zeroPriceCostOnly"][d])-actual)**2
                    predictCount+=1
        if side and not x["sourceValid"]:
            reasons["PROPOSED_BUT_ORIGINAL_ENTRY_OR_EXIT_UNPRICED"]+=1
        elif side:
            pool=historical_pool(known,x["t"],variant,x["E"],x["B"])
            losses=[-y["labels"]["adverse"][d]["net"] for y in pool
                    for d in (1,-1) if y["labels"]["adverse"][d]["net"]<0]
            stress=max(D("0.01"),max(losses,default=D(0))*3)
            if stress>D(".30")*sampledCash or sampledCash<=peak*D(".70"):
                reasons["CAUSAL_STRESS_OR_DRAWDOWN_BLOCK"]+=1
            elif sampledCash<=D(0):
                reasons["COMMON_BOOK_NO_EQUITY"]+=1
            else:
                selection.append((x,side))
                sampledCash+=x["labels"][scenario][side]["net"]
                peak=max(peak,sampledCash)
                reasons["SOURCE_PRICED_RISK_PREFILTER_ACCEPT"]+=1
        else:
            reasons[reason]+=1
        # Keep public forecast examples aggregated, never disclose raw historical prices.
        predictions.append(dict(week=x["week"]+1,action=side,
            admissibleAfterPrefilter=bool(selection and selection[-1][0] is x),
            sourceValid=x["sourceValid"],reason=reason,
            forecastLong=forecast["sideForecasts"].get(1,{}).get("mean"),
            forecastShort=forecast["sideForecasts"].get(-1,{}).get("mean")))
        known.append(x)
    events=native_events(selection,u,scenario,variant)
    try:
        # A proposed action with an unavailable postentry quote has UNKNOWN net,
        # never a silent dropped loss or a retrospective CASH decision.
        need(reasons["PROPOSED_BUT_ORIGINAL_ENTRY_OR_EXIT_UNPRICED"]==0,
             "DVI1_POSTENTRY_UNPRICED_POLICY_NET_UNKNOWN")
        native=run_native(events)
        modeledNet=sum((x["labels"][scenario][side]["net"] for x,side in selection),D(0))
        need(abs(D(str(native["netEur"]))-modeledNet)<D("0.01") and
             abs(D(str(native["finalCashEur"]))-(D(300)+modeledNet))<D("0.01")
             and native["roundTrips"]==len(selection),
             "DVI1_NATIVE_LABEL_AND_CAPITAL_RECONCILIATION_FAILED")
        failure=None
    except Exception as ex:
        native=None;failure=str(ex)[:160]
    chosen=[x["labels"][scenario][d] for x,d in selection]
    weeklySelected=[sum(x["week"]==w for x,_ in selection) for w in range(5,13)]
    return dict(variant=variant,scenario=scenario,evaluationScheduled=200,
        rawProposedActions=sum(x["action"]!=0 for x in predictions),
        cashChoices=sum(x["action"]==0 for x in predictions),
        prefundedSelected=len(selection),
        counterfactualSelectedPayoffEur=float(sum((x["net"] for x in chosen),D(0))),
        grossMidpointEur=float(sum((x["gross"] for x in chosen),D(0))),
        modeledTradingFrictionEur=float(sum((x["friction"] for x in chosen),D(0))),
        weeklySelected=weeklySelected,
        reasons=dict(reasons),native=native,nativeFailure=failure,
        pairedAdverseMse=None if predictCount==0 else valueError/predictCount,
        zeroPriceMoveKnownCostMse=None if predictCount==0 else costOnlyError/predictCount,
        predictiveLabelsCompared=predictCount,
        independentConfirmation=False,qualified=False)

def main():
    need(PROTOCOL.exists() and "FROZEN" in PROTOCOL.read_text(),
         "DVI1_EXACT_FROZEN_PROTOCOL_MISSING")
    source,c,m,trader,source_meta=load_authentic_source()
    converted=[new_row(x,c,m,trader) for x in source]
    need(len(converted)==325 and [x["week"] for x in converted]==[
             (date.fromisoformat(x["day"])-START).days//7 for x in source],
         "DVI1_CALENDAR_DENOMINATOR_INCORRECT")
    unknown=dict(Counter(x["unknown"] for x in converted if not x["sourceValid"]))
    print("DVI1_SOURCE_PROVENANCE_AUTHENTIC",json.dumps(dict(
        source=source_meta,scheduled=325,known=325-sum(unknown.values()),unknown=unknown)),
        flush=True)
    u=D(c.minVolume)/100
    result={scenario:{v:run_policy(converted,v,scenario,u) for v in VARIANTS}
            for scenario in SCENARIOS}
    deltas={}
    for name,books in result.items():
        n=lambda v:None if books[v]["native"] is None else books[v]["native"]["netEur"]
        full=n("FULL")
        deltas[name]={v:(None if full is None or n(v) is None else full-n(v))
                     for v in ("OWN","POOLED","CASH")}
    summary=dict(schema="MXM_DVI1_A1_NEW_ORIGINAL_EXPOSED_ACTION_VALUE_EUR300_V1",
        verdict="DVI1_A1_NEW_EXPOSED_CHRONOLOGICAL_ACTION_VALUE_UNQUALIFIED",
        executionRunId=int(os.environ.get("GITHUB_RUN_ID","0")),
        frozenProtocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),
        codeSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        untouchedSourceProvenance=source_meta,
        sourceAuthenticatedOriginalProtobuf=True,
        oldCxl1StrategiesAndEconomicScorerRerun=False,
        noNewBrokerRequests=True,originalSourceScheduled=325,
        trainingScheduled=125,evaluationScheduled=200,
        sourceFullyPricedClocks=sum(x["sourceValid"] for x in converted),
        sourceUnpricedReasons=unknown,
        evaluationLabelKnown=sum(x["sourceValid"] and x["week"]>=5 for x in converted),
        heldKeepExitFinanciallyIdentifiable=False,
        heldKeepExitReason="NO_AUTHENTIC_INTERMEDIATE_30_MIN_HOLDING_BIDASK_AND_MARKS",
        matchedCounterfactualBooks=result,fullIncrementalNetEur=deltas,
        historicalTariffCertified=False,realBrokerExecutionNetEur=None,
        continuousFloatingDrawdownCertified=False,independentConfirmation=False,
        systematicHARD21Certified=False,ordersSubmitted=0,cloudActivated=False)
    OUT.write_text(json.dumps(summary,sort_keys=True,indent=2,default=str)+"\n")
    for s in SCENARIOS:
        for v in VARIANTS:
            x=result[s][v]
            print("DVI1_NEW_ACTION_FINANCIAL",s,v,"NET",
                  x["native"]["netEur"] if x["native"] else "UNKNOWN",
                  "TRIPS",x["native"]["roundTrips"] if x["native"] else "UNKNOWN",
                  "FAIL",x["nativeFailure"],flush=True)
    need(all(result[s][v]["nativeFailure"] is None for s in SCENARIOS for v in VARIANTS),
         "DVI1_NATIVE_FINANCIAL_REPLAY_OR_PARITY_FAILURE")
    print("DVI1_A1_NEW_EXPOSED_RESULT_CONSERVED_UNQUALIFIED",flush=True)

if __name__=="__main__":main()
