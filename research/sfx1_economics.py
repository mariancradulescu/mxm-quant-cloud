"""SFX1 frozen market-economics programme.

ONE outcome-blind native C# parity run before accessing any forward returns.
Authentic M15 OHLCV drives gross predictive economics even if BID/ASK is
sparse. All broker tariff values are as-observed current CMA1 terms; modeled
slippage/conversion buffers are separate, never certified broker executions.
"""
from __future__ import annotations
import json,math,subprocess,tempfile
from collections import Counter
from pathlib import Path
from statistics import mean,median,NormalDist
from .csp1_cost_preflight import asof_spread

Q=900000;H=3600000;DAY=86400000;WEEK=7*DAY
JPY="JPY_BASKET_0815_DISPERSION_RECOMPRESSION_M15_H4"
NZD="NZDUSD_0700_H4_TO_M15_INTRASESSION_REVERSAL"

def need(ok,code):
    if not ok:raise ValueError("SFX1_"+code)

def sign(x):return 1 if x>0 else -1 if x<0 else 0
def ret(a,b):return 10000*math.log(a/b)
def quantile(xs,q):
    v=sorted(xs)
    if not v:return None
    i=(len(v)-1)*q
    k=int(i)
    return v[k]+(v[min(k+1,len(v)-1)]-v[k])*(i-k)

def path(series,t,n):
    """The final close is t; ALL n prior real M15 closes required."""
    if any(t-i*Q not in series for i in range(n+1)):return None
    return [series[t-i*Q] for i in range(n,-1,-1)]

def datum(rows):
    return [{"CloseAt":x[0],"Close":float(x[4]),"TickVolume":int(x[5])} for x in rows]

def frames_for_day(bars,p):
    """Before labels: at most 3 JPY + 1 NZD fixed clock per eligible weekday."""
    start=p["source"]["startUtcMs"];end=p["source"]["endHistoricalUtcMs"]
    frames=[];contexts=[]
    for day in range(start,end,DAY):
        weekday=((day//DAY)+3)%7  # Monday=0, 1970-01-01 Thursday
        if weekday>=5:continue
        for sym in p["candidates"]:
            name=JPY if sym!="NZDUSD" else NZD
            t=day+(8*60+15)*60000 if name==JPY else day+7*H
            if name==JPY:
                other=[v for v in ("EURJPY","AUDJPY","NZDJPY") if v!=sym]
                target=path(bars[sym],t-Q,16)
                peer1=path(bars[other[0]],t-Q,16)
                peer2=path(bars[other[1]],t-Q,16)
            else:
                target=path(bars[sym],t,28)
                peer1=peer2=None
            if any(x is None for x in ((target,peer1,peer2) if name==JPY else (target,))):
                continue
            frames.append({"Mechanism":name,"Symbol":sym,"Clock":t,
                "Target":datum(target),
                "PeerA":None if peer1 is None else datum(peer1),
                "PeerB":None if peer2 is None else datum(peer2)})
            contexts.append((name,sym,t))
    return frames,contexts

def python_decide(x):
    name=x["Mechanism"];sym=x["Symbol"];t=x["Clock"]
    bars={v["CloseAt"]:v for v in x["Target"]}
    if name==JPY:
        pa={v["CloseAt"]:v for v in x["PeerA"]}
        pb={v["CloseAt"]:v for v in x["PeerB"]}
        z=t-Q
        self=ret(bars[z]["Close"],bars[z-16*Q]["Close"])
        a=ret(pa[z]["Close"],pa[z-16*Q]["Close"])
        b=ret(pb[z]["Close"],pb[z-16*Q]["Close"])
        middle=(a+b)/2
        delta=self-middle
        side=-sign(delta) if sign(a)==sign(b) and abs(middle)>=8 and abs(delta)>=12 else 0
        return {"Side":side,"MomentumBenchmarkSide":sign(self),"HistoryComplete":True}
    close=lambda i:bars[t-i*Q]["Close"]
    h4=ret(close(12),close(28))
    micro=ret(close(0),close(2))
    vol=lambda i:bars[t-i*Q]["TickVolume"]
    recent=(vol(0)+vol(1))/2
    old=(vol(2)+vol(3)+vol(4)+vol(5))/4
    side=sign(micro) if abs(h4)>=8 and abs(micro)>=4 and sign(h4)*sign(micro)==-1 and old>0 and recent>=1.1*old else 0
    return {"Side":side,"MomentumBenchmarkSide":sign(h4),"HistoryComplete":True}

def native_parity(frames):
    if not frames:return [],{"cases":0,"matching":True}
    with tempfile.TemporaryDirectory(prefix="sfx-native-") as d:
        i=Path(d)/"in.json";o=Path(d)/"out.json"
        i.write_text(json.dumps(frames))
        run=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                            str(i),str(o),"--sfx1-native-signs"],
                           capture_output=True,text=True,timeout=180)
        need(run.returncode==0 and o.exists(),"NATIVE_PARITY_COMMAND_FAILED")
        native=json.loads(o.read_text())
    expected=[python_decide(f) for f in frames]
    need(native==expected,"ACTUAL_MARKET_PYTHON_CSHARP_SIGN_MISMATCH")
    return native,{"cases":len(frames),"matching":True,
                   "nonzeroSignals":sum(x["Side"]!=0 for x in native)}

def outcome_path(series,entry,hold):
    n=hold//15
    if any(entry+i*Q not in series for i in range(n+1)):return None
    return series[entry][4],series[entry+n*Q][4]

def source_event_cost(symbol,entry,source,spreads,terms,scenario):
    samples=spreads.get(symbol,[])
    if len(samples)<3 or len({t//DAY for t,s in samples})<3:return None
    vals=[v for _,v in samples]
    measured=median(vals) if scenario=="central" else quantile(vals,.90)
    spread=measured
    slipFactor=.5 if scenario=="central" else 1
    fxBuffer=.25 if scenario=="central" else .75
    # No manufactured USD2EUR/JPY2EUR historical account conversion fill.
    # Completed same-clock EURUSD and EURJPY M15 CLOSE are mid-price proxies.
    converter=source.get("EURUSD",{}).get(entry)
    eurjpy=source.get("EURJPY",{}).get(entry)
    target=source.get(symbol,{}).get(entry)
    if not converter or not eurjpy or not target:return None
    eurusd_price=float(converter[4])/10**terms["EURUSD"]["digits"]
    eurjpy_price=float(eurjpy[4])/10**terms["EURJPY"]["digits"]
    target_price=float(target[4])/10**terms[symbol]["digits"]
    if eurusd_price<=0 or eurjpy_price<=0 or target_price<=0:return None
    usd_eur=1/eurusd_price
    quote_eur=usd_eur if symbol=="NZDUSD" else 1/eurjpy_price
    units=float(terms[symbol]["minimumUnits"])
    notional=units*target_price*quote_eur
    if notional<=0 or usd_eur<=0:return None
    info=terms[symbol]
    # Exact CURRENT tariff: USD_PER_LOT, explicit zero floor, as-of source.
    if not (info["commissionType"]==2 and info["rateWire"]==300000000 and
            info["minimumWire"]==0 and info["pnlConversionBps"]==0 and
            info["lotSizeUnits"]>0):return None
    fee_one=(info["rateWire"]/1e8)*(units/info["lotSizeUnits"])*usd_eur
    commission=20000*fee_one/notional
    return {"spreadBps":spread,"slippageBps":spread*slipFactor,
            "currentTermTwoSideCommissionBps":commission,
            "fxRouteModelUncertaintyBps":fxBuffer,
            "fundingBpsConditionalIntraday":0.0,
            "totalCostBps":spread*(1+slipFactor)+commission+fxBuffer,
            "tariffHistoricallyCertified":False,
            "executionFillCertified":False,
            "fxConversionMidPriceNotActualFill":True}

def hac_lower(values,confidence=0.975,lag=3):
    # Newey-West on ALL calendar weeks, including zero-signal weeks.
    if len(values)<8:return None
    n=len(values);m=sum(values)/n
    u=[x-m for x in values]
    var=sum(x*x for x in u)/n
    for k in range(1,min(lag,n-1)+1):
        cov=sum(u[i]*u[i-k] for i in range(k,n))/n
        var+=2*(1-k/(lag+1))*cov
    se=math.sqrt(max(var,0)/n)
    return m-NormalDist().inv_cdf(confidence)*se

def phase_summary(events,lo,hi):
    rows=[x for x in events if lo<=x["week"]<hi]
    weeks=[ [x for x in rows if x["week"]==w] for w in range(lo,hi)]
    active=sum(bool(a) for a in weeks)
    def avg(name):
        vals=[x[name] for x in rows if x[name] is not None]
        return round(mean(vals),6) if len(vals)==len(rows) and rows else None
    return {
      "modelSignals":len(rows),"activeWeeks":active,
      "emptyWeeks":hi-lo-active,
      "weeklyCount":[len(w) for w in weeks],
      "grossMeanBps":avg("gross"),"grossMomentumBenchmarkBps":avg("benchmarkGross"),
      "grossIncrementalVsMomentumBps":avg("incrementalGross"),
      "netCentralMeanBpsConditional":avg("central"),
      "netAdverseMeanBpsConditional":avg("adverse"),
      "momentumNetAdverseMeanBpsConditional":avg("benchmarkAdverse"),
      "incrementalNetAdverseMeanBpsConditional":avg("incrementalAdverse"),
      "adverseWeeklyHacBonferroniLower":round(z,6) if (z:=hac_lower([
        sum(x["incrementalAdverse"] for x in w)/len(w) if w and all(x["incrementalAdverse"] is not None for x in w) else 0
        for w in weeks])) is not None and all(x["incrementalAdverse"] is not None for x in rows) and rows else None
    }

def evaluate(bars,spreads,terms,p):
    need(p["id"]=="SFX1" and p["locked"] is True and
         p["universe"]==["EURJPY","AUDJPY","NZDJPY","NZDUSD","EURUSD"],
         "ECONOMIC_PROTOCOL_DRIFT")
    frames,contexts=frames_for_day(bars,p)
    sides,parity=native_parity(frames) # verified BEFORE accessing future labels
    events=[];missing=Counter()
    for (name,sym,t),d in zip(contexts,sides):
        if d["Side"]==0:continue
        hold=45 if name==JPY else 60
        enter=t+15*60000
        path_ok=outcome_path(bars[sym],enter,hold)
        if path_ok is None:
            missing[sym+"/EXIT_PROXY_M15_MISSING"]+=1;continue
        a,b=path_ok
        gross=d["Side"]*ret(b,a)
        bench=d["MomentumBenchmarkSide"]*ret(b,a)
        central=source_event_cost(sym,enter,bars,spreads,terms,"central")
        adverse=source_event_cost(sym,enter,bars,spreads,terms,"adverse")
        c=None if central is None else gross-central["totalCostBps"]
        a_net=None if adverse is None else gross-adverse["totalCostBps"]
        b_net=None if adverse is None else bench-(adverse["totalCostBps"] if d["MomentumBenchmarkSide"]!=0 else 0)
        events.append({"mechanism":name,"symbol":sym,"at":t,
             "week":(t-p["source"]["startUtcMs"])//WEEK,
             "gross":gross,"benchmarkGross":bench,"incrementalGross":gross-bench,
             "central":c,"adverse":a_net,"benchmarkAdverse":b_net,
             "incrementalAdverse":None if a_net is None else a_net-b_net})
    results={}
    for name in (JPY,NZD):
        cases=[x for x in events if x["mechanism"]==name]
        res={phase:phase_summary(cases,lo,hi) for phase,lo,hi in
              [("development",0,26),("selection",26,39),("previouslyExposedAudit",39,52)]}
        sel=res["selection"];costOK=all(x["adverse"] is not None for x in cases)
        passed=bool(costOK and sel["modelSignals"]>=40 and
            sel["activeWeeks"]>=8 and
            sel["adverseWeeklyHacBonferroniLower"] is not None and
            sel["adverseWeeklyHacBonferroniLower"]>0 and
            sel["netAdverseMeanBpsConditional"] is not None and
            sel["netAdverseMeanBpsConditional"]>0)
        results[name]={"instruments":sorted({x["symbol"] for x in cases}),
          "totalSignalsWithCompleteForward":len(cases),
          "allForwardOutcomesHistoricalPreviouslyExposed":True,
          "sections":res,"selectionAdverseEvidenceGatePassed":passed,
          "recommendation":"EXPLORATORY_ONLY_NOT_FUNDED" if passed else
              "NOT_PROMOTED_CURRENT_EXACT_CONFIGURATION",
          "reason":"INDEPENDENT_CONFIRMATION_AND_REAL_FILL_EVIDENCE_MISSING" if passed else
                "ADVERSE_INCREMENTAL_OR_QUOTE_COST_OR_SAMPLE_GATE_UNMET"}
    return {"id":"SFX1","source":"PEPPERSTONE_ORIGINAL_LIVE_READ_ONLY_M15",
      "actualNativeCsharpFeatureParity":parity,
      "observedM15BarsBySymbol":{s:len(v) for s,v in bars.items()},
      "observedCurrentTermPairedQuoteSamples":{s:len(spreads.get(s,[])) for s in p["candidates"]},
      "missingExactForwardSource":dict(missing),
      "results":results,"fundedBrokerEurNet":None,
      "admittedFundedRoundTrips":0,"systemHard21Proven":False,
      "maximumDrawdown30Proven":False,"independentConfirmation":False,
      "slippageMeasured":False,"historicalTariffsCertified":False,
      "closedStudiesReexecuted":False,"ordersSubmitted":0,"cloudActivated":False}
