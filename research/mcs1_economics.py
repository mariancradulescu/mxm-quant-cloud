"""MCS1 — genuinely new original Pepperstone cross-class H1 predictive research.

Read original completed H1 OHLCV from encrypted custody, produce Mxm.Core C#
native signs and compare Python signs BEFORE accessing a single forward price
label. Then report chronological gross/matched benchmark and the SEPARATE
absolute-cash and incremental-benchmark adverse HAC gates. No old studies run.
"""
from __future__ import annotations
import json, math, subprocess, tempfile
from pathlib import Path
from collections import Counter
from statistics import median
from .prospective_joint_stat_gate import assess_prospective_weekly,public_dict

H=3600000;DAY=24*H;WEEK=7*DAY
GAS="NATGAS_H4_EXHAUSTION_USDX_QUIET_REVERSAL"
DOLLAR="USDX_OVERLAP_TWO_HOUR_DRIFT"
EQUITY="AMD_US_INTRADAY_TICK_ACTIVITY_EXHAUSTION"
NAME={GAS:"NatGas",DOLLAR:"USDX",EQUITY:"AMD.US"}
HOURS={GAS:list(range(12,20)),DOLLAR:list(range(12,20)),
       EQUITY:list(range(15,20))}

def need(ok,tag):
    if not ok:raise ValueError("MCS1_"+tag)
def sign(x):return 1 if x>0 else -1 if x<0 else 0
def bps(a,b):return 10000*math.log(a/b)

def path(series,t,n):
    if any(t-i*H not in series for i in range(n+1)):return None
    return [series[t-i*H] for i in range(n,-1,-1)]

def native_format(series):
    return [{"CloseAt":x[0],"Open":float(x[1]),"High":float(x[2]),
             "Low":float(x[3]),"Close":float(x[4]),"TickVolume":int(x[5])}
            for x in series]

def frames_and_context(bars,p):
    """All genuine completed H1 frames; purely causal no forward labels."""
    start=p["source"]["startUtcMs"];end=p["source"]["exposedAuditEndUtcMs"]
    frames=[];contexts=[];missing=Counter();slots=Counter()
    for day in range(start,end,DAY):
        if ((day//DAY)+3)%7>=5:continue
        for name,sym in NAME.items():
            for hour in HOURS[name]:
                t=day+hour*H
                slots[name]+=1
                n=2 if name==DOLLAR else 4
                own=path(bars[sym],t,n)
                other=path(bars["USDX"],t,2) if name==GAS else None
                if own is None or name==GAS and other is None:
                    missing[name]+=1;continue
                frames.append({"Mechanism":name,"Symbol":sym,
                     "Peer":"USDX" if name==GAS else None,"Clock":t,
                     "Target":native_format(own),
                     "PeerBars":native_format(other) if other is not None else None})
                contexts.append((name,sym,t))
    return frames,contexts,dict(slots),dict(missing)

def python_decide(frame):
    name=frame["Mechanism"];t=frame["Clock"];sym=frame["Symbol"]
    rows={x["CloseAt"]:x for x in frame["Target"]}
    a=lambda n:rows[t-n*H]
    if name==GAS:
        other={x["CloseAt"]:x for x in frame["PeerBars"]}
        four=bps(a(0)["Close"],a(4)["Close"])
        last=bps(a(0)["Close"],a(1)["Close"])
        usd=bps(other[t]["Close"],other[t-2*H]["Close"])
        older=(a(1)["TickVolume"]+a(2)["TickVolume"]+a(3)["TickVolume"])/3.
        side=sign(last) if older>0 and abs(four)>=35 and abs(usd)<10 and \
            last*four<0 and a(0)["TickVolume"]>=1.10*older else 0
        bench=sign(four)
    elif name==DOLLAR:
        drift=bps(a(0)["Close"],a(2)["Close"])
        last=bps(a(0)["Close"],a(1)["Close"])
        side=sign(drift) if abs(drift)>=4 and sign(drift)==sign(last) and \
             a(0)["TickVolume"]>0 else 0
        bench=1
    elif name==EQUITY:
        last=bps(a(0)["Close"],a(1)["Close"])
        old=sum(a(i)["TickVolume"] for i in range(1,5))/4.
        side=-sign(last) if old>0 and abs(last)>=80 and \
             a(0)["TickVolume"]>=1.25*old else 0
        bench=sign(last)
    else:raise ValueError("MCS1_UNKNOWN_RULE")
    return {"Side":side,"BenchmarkSide":bench,"Complete":True}

def native_parity(frames):
    if not frames:return [],{"cases":0,"same":True}
    with tempfile.TemporaryDirectory(prefix="mcs-native-") as d:
        a=Path(d)/"cases.json";z=Path(d)/"native.json"
        a.write_text(json.dumps(frames))
        run=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                            str(a),str(z),"--mcs1-native-h1-signs"],
                           capture_output=True,text=True,timeout=240)
        need(run.returncode==0 and z.exists(),"NATIVE_H1_CSHARP_FAILED")
        out=json.loads(z.read_text())
    mirror=[python_decide(x) for x in frames]
    need(out==mirror,"ACTUAL_H1_PYTHON_CSHARP_PARITY_FAILED")
    return out,{"cases":len(frames),"same":True,"positiveSignals":
                  sum(x["Side"]!=0 for x in out)}

def quantile(values,p):
    s=sorted(values)
    if not s:return None
    ix=(len(s)-1)*p
    i=int(ix)
    return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(ix-i)

def conditional_cost_bps(symbol,at,bars,quotes,terms,scenario):
    obs=quotes.get(symbol,[])
    if len(obs)<8 or len({t//DAY for t,_ in obs})<8:
        return None
    info=terms[symbol]
    # Current original-account contract per minimum trade, as-of source.
    if info["quoteAsset"]!="USD" or info["commissionType"]!=2 or \
       info["pnlConversionBps"]!=0 or info["minCommissionType"]!=1 or \
       info["minimumCommissionAsset"]!="USD":
        return None
    entry=bars[symbol].get(at)
    if entry is None or entry[4]<=0 or info["digits"]<0:return None
    price=entry[4]/10**info["digits"]
    unit=info["minimumUnits"]
    lot=info["lotSizeUnits"]
    notional=price*unit
    if min(notional,lot,unit)<=0:return None
    one_side=max(info["rateWire"]/1e8*unit/lot,info["minimumWire"]/1e8)
    fee_bps=20000*one_side/notional
    s=[v for _,v in obs]
    spread=median(s) if scenario=="central" else quantile(s,.9)
    slippage=spread*(.5 if scenario=="central" else 1.0)
    fx_uncertainty=.5 if scenario=="central" else 1.0
    return {"totalBps":spread+slippage+fee_bps+fx_uncertainty,
            "spreadBps":spread,"modelSlippageBps":slippage,
            "currentContractRoundTripCommissionBps":fee_bps,
            "routeUncertaintyBps":fx_uncertainty,
            "sourceTimeTariffNotHistorical":True,
            "actualBrokerFillEur":None}

def outcome(series,clock):
    # Decision at completed t; modeled entry next completed H1 close at t+1h
    # and next H1 exit at t+2h, never the current known close as fill.
    t=clock+H;u=t+H
    if t not in series or u not in series:return None
    if series[t][4]<=0 or series[u][4]<=0:return None
    return series[t][4],series[u][4],t

def evaluate(bars,quotes,terms,p):
    need(p["id"]=="MCS1" and p["locked"] is True and
         p["source"]["readOnlyBrokerRequestsExact"]==324 and
         set(bars)=={"NatGas","USDX","AMD.US"} and
         len(p["families"])==3,"FROZEN_PROTOCOL_OR_SYMBOL_DRIFT")
    frames,contexts,slots,missing=frames_and_context(bars,p)
    native,parity=native_parity(frames) # *BEFORE* forward prices are accessed
    weeks=p["source"]["historicalWeeks"]
    signedWeekly=[0]*weeks
    for (_,_,t),signs in zip(contexts,native):
        if signs["Side"]!=0:
            wk=(t-p["source"]["startUtcMs"])//WEEK
            if 0<=wk<weeks:signedWeekly[wk]+=1
    activeGross=sum(x>0 for x in signedWeekly)
    eligibleOver21=sum(x>=21 for x in signedWeekly)
    candidates=sum(signedWeekly)
    freq={"combinedClockCapacityPerNominalWeek":
             p["frequencyPrescreen"]["combinedUpperBound"],
          "testedCompletedNativeH1Windows":len(frames),
          "registeredFamilyClockSlots":slots,"sourceHistoryMissingSlots":missing,
          "actualCausalSignalsBeforeForwardLabels":candidates,
          "weeklyRawNativeSignalCounts":signedWeekly,
          "historicalWeeksWithAtLeast21RawSignals":eligibleOver21,
          "historicalWeeksWithAtLeastOneRawSignal":activeGross,
          "weekMedianRawSignals":median(signedWeekly),
          "notFinancedAndNotEligibleBrokerRoundTrips":True}
    events=[];gaps=Counter()
    for (name,sym,t),signs in zip(contexts,native):
        if signs["Side"]==0:continue
        o=outcome(bars[sym],t)
        if o is None:
            gaps[sym+"/FORWARD_H1_MISSING"]+=1;continue
        open_px,close_px,entry=o
        gross=signs["Side"]*bps(close_px,open_px)
        bench=signs["BenchmarkSide"]*bps(close_px,open_px)
        central=conditional_cost_bps(sym,entry,bars,quotes,terms,"central")
        adverse=conditional_cost_bps(sym,entry,bars,quotes,terms,"adverse")
        c=None if central is None else gross-central["totalBps"]
        a=None if adverse is None else gross-adverse["totalBps"]
        bb=None if adverse is None else bench-(adverse["totalBps"] if signs["BenchmarkSide"] else 0)
        events.append({"family":name,"symbol":sym,"clock":t,
             "week":(t-p["source"]["startUtcMs"])//WEEK,
             "grossBps":gross,"benchmarkGrossBps":bench,
             "centralNetBps":c,"adverseNetBps":a,
             "adverseBenchmarkNetBps":bb})
    results={}
    for family in p["families"]:
        name=family["id"]
        subset=[{k:v for k,v in event.items() if k not in ("symbol","clock","family")}
                for event in events if event["family"]==name]
        phases={}
        for label,lo,hi in (("development",0,26),("selection",26,39),
                            ("globallyExposedAudit",39,52)):
            phases[label]=public_dict(assess_prospective_weekly(
                subset,lo,hi,3,minimum_complete_events=40,
                minimum_active_weeks=8))
        sel=phases["selection"]
        passes=sel["passesBothProspectiveStatGates"] and \
           phases["development"]["adverseNetMeanBps"] is not None and \
           phases["development"]["adverseNetMeanBps"]>0
        results[name]={"symbol":family["symbol"],
          "actualCompletedForwardModelEpisodes":
            sum(x["family"]==name for x in events),
          "phase":phases,
          "prospectiveSelectionEvidence":passes,
          "qualification":"EXPLORATORY_CANDIDATE_REQUIRES_BROKER_FILLED_COST_AND_INDEPENDENT_CONFIRMATION"
             if passes else "NOT_PROMOTED_FROZEN_EXACT_CONFIGURATION",
          "fundedNetEur":None}
    return {
      "schema":"MXM_MCS1_AUTHENTIC_H1_CROSS_CLASS_ECONOMICS_V1",
      "originalAccountReadOnlyH1":True,
      "realOriginalSourceM15NotReusedAsH1":True,
      "barCounts":{s:len(x) for s,x in bars.items()},
      "developmentPairedQuoteCounts":{s:len(x) for s,x in quotes.items()},
      "nativeH1PythonCsharpParity":parity,
      "frequencyBeforeForwardReturns":freq,
      "forwardCompleteSignalsByFamily":{
         n:sum(x["family"]==n for x in events) for n in NAME},
      "missingForwardReasons":dict(gaps),
      "families":results,
      "sourceTariffTermOnly":True,"historicalTariffsIndependentlyProven":False,
      "bookedBrokerFillOrders":0,"fundedEurNet":None,
      "nativeFundedCompleteRoundTrips":0,
      "systemicHard21Proven":False,"globalFloatDrawdown30Proven":False,
      "independentConfirmation":False,"ordersSubmitted":0,"cloudActivated":False,
      "closedStudiesReevaluated":False,
      "newerFiveDaysUsedForPrediction":False}
