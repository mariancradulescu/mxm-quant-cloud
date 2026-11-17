"""PVE3 ORIGINAL: new multiscale price-innovation / tail-regret decisions.

Separately frozen exact protocol, no old study predictor/evaluator executed.
Use only original protected BDP1+AIP1 SOURCE reader, legitimate prior cost context,
and existing native C# execution/risk/ledger. All calendar globally exposed.
"""
from __future__ import annotations
from bisect import bisect_right
from collections import Counter,defaultdict
from hashlib import sha256
from pathlib import Path
from datetime import datetime,timezone
import json,math,os,subprocess,tempfile
import numpy as np

M5=300000
H=3600000
DAY=24*H
WEEK=7*DAY
START=1762128000000
END=START+52*WEEK
FIRST=START+26*WEEK
PROTOCOL=Path("research/PVE3_FROZEN_DISTRIBUTIONAL_DECISION_PROTOCOL_20261117.md")
VARIANTS={"FULL":list(range(17)),"OWN":[1,2,4,5,11,12]}
ORIGINAL_RUNS=(41724643418,41735441128)

def need(value,reason):
    if not value:raise ValueError("PVE3_"+reason)
def clip(x):
    return max(-4.,min(4.,float(x)))
def rms(v):
    return float(np.sqrt(np.mean(np.asarray(v,float)**2)))
def hash_json(v):
    return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def aggregate(closed_m5,minutes):
    span=minutes*60000;expected=span//M5;out=[];group=[]
    for r in closed_m5:
        boundary=((r[1]-1)//span+1)*span
        if group and ((group[0][1]-1)//span+1)*span!=boundary:
            if len(group)==expected and group[0][0]==old-span and group[-1][1]==old and all(a[1]==b[0] for a,b in zip(group,group[1:])):
                out.append([old-span,old,group[0][2],max(v[3] for v in group),min(v[4] for v in group),group[-1][5],sum(v[6] for v in group)])
            group=[]
        group.append(r);old=boundary
    if group and len(group)==expected and group[0][0]==old-span and group[-1][1]==old and all(a[1]==b[0] for a,b in zip(group,group[1:])):
        out.append([old-span,old,group[0][2],max(v[3] for v in group),min(v[4] for v in group),group[-1][5],sum(v[6] for v in group)])
    return out

def features(m15,h1,h4,clock,peer_breadth=0.,peer_coverage=0.):
    """All passed candles fully completed <= clock; no training-data dependent bins."""
    if len(m15)!=8 or len(h1)!=16 or len(h4)!=8:return None
    if (clock-m15[-1][1]>15*60000 or
        clock-h1[-1][1]>H or clock-h4[-1][1]>4*H or
        m15[0][0]<clock-DAY or h1[0][0]<clock-7*DAY or
        h4[0][0]<clock-10*DAY):return None
    samples=[m15,h1,h4]
    for seq in samples:
        if any(a[1]>clock or a[3]<=a[4] or min(a[2],a[3],a[4],a[5])<=0 or a[6]<=0 for a in seq):return None
    rb=[[math.log(x[5]/x[2]) for x in seq] for seq in samples]
    sig=[max(.0001,rms(y)) for y in rb]
    m15_4=clip(sum(rb[0][-4:])/(4*sig[0]))
    h1_last=clip(rb[1][-1]/sig[1])
    h1_trend=clip(sum(rb[1][-4:])/(4*sig[1]))
    h4_slope=clip(sum(rb[2][-4:])/(4*sig[2]))
    eff=clip(abs(sum(rb[1][-8:]))/max(.0000001,sum(abs(v) for v in rb[1][-8:])))
    logvol=clip(math.log(sig[1]*10000))
    accel=clip(rms(rb[1][-4:])/max(.0001,rms(rb[1][-12:-4]))-1)
    activity=clip(h1[-1][6]/(sum(x[6] for x in h1[-8:-1])/7)-1)
    ranges=[x[3]-x[4] for x in h4]
    compression=clip(ranges[-1]/max(.0000001,float(np.median(ranges[:-1])))-1)
    breadth=clip(peer_breadth);coverage=clip(peer_coverage)
    hour=(clock%DAY)/H
    core=[m15_4,h1_last,h1_trend,h4_slope,eff,logvol,accel,activity,
          compression,breadth,coverage,math.sin(2*math.pi*hour/24),
          math.cos(2*math.pi*hour/24)]
    return core+[clip(m15_4*h4_slope),clip(accel*activity),
                 clip(eff*breadth),clip(compression*h1_trend)]

def panel(bars):
    bysymbol={};closes={};names=sorted(bars);rows=[];census=Counter()
    for s,rr in bars.items():
        closes[s]={int(x[1]):float(x[5]) for x in rr}
        bysymbol[s]={}
        for minutes in (15,60,240):
            a=aggregate(rr,minutes)
            bysymbol[s][minutes]=(a,[int(x[1]) for x in a])
    for t in range(START,END,H):
        if datetime.fromtimestamp(t/1000,timezone.utc).weekday()>=5:continue
        at={}
        for s in names:
            census["scheduled"]+=1
            stages=[]
            for mins,n in ((15,8),(60,16),(240,8)):
                data,ends=bysymbol[s][mins];i=bisect_right(ends,t)
                stages.append(data[max(0,i-n):i])
            f=features(*stages,clock=t)
            if f is None or t not in closes[s]:
                census["featureUnknown"]+=1;continue
            at[s]=(f,stages)
        breadth={}
        for s in at:
            peers=[math.log(stages[1][-1][5]/stages[1][-1][2])
                   for k,(_,stages) in at.items() if k!=s]
            breadth[s]=(float(np.mean(np.sign(peers))) if peers else 0.,
                        len(peers)/max(1,len(names)-1))
        for s,(core,stages) in sorted(at.items()):
            b,c=breadth[s]
            x=features(*stages,clock=t,peer_breadth=b,peer_coverage=c)
            sig=max(.0001,rms([math.log(y[5]/y[2]) for y in stages[1]]))
            rows.append(dict(t=t,s=s,x=x,sig=sig,at=t+M5,due=t+M5+H,
                             week=int((t-START)//WEEK)))
            census["featureKnown"]+=1
    return rows,closes,dict(census,originalBars=sum(map(len,bars.values())),sourceSymbols=names)

def conversion(s,t,prices,terms):
    ccy=terms[s]["quoteAsset"]
    def p(n):return prices.get(n,{}).get(t)
    eu=p("EURUSD")
    if ccy=="EUR":return 1.
    if not eu:return None
    if ccy=="USD":return 1/eu
    if ccy in ("JPY","CAD"):
        v=p("USD"+ccy)
        return 1/(eu*v) if v else None
    if ccy in ("GBP","AUD"):
        v=p(ccy+"USD")
        return v/eu if v else None
    return None

def cross(a,b,minute):
    return max(0,(b-minute*60000)//DAY-(a-minute*60000)//DAY)

def source_label(r,prices,terms,costs):
    s=r["s"];p=prices.get(s,{});t=r["t"];at=r["at"];z=r["due"]
    c=costs.get(s)
    if c is None or t not in p or any(k not in p for k in range(at,z+1,M5)):return None
    fx0=conversion(s,t,prices,terms);fxa=conversion(s,at,prices,terms);fxz=conversion(s,z,prices,terms)
    if any(v is None for v in (fx0,fxa,fxz)):return None
    if cross(at,z,c["swapMinute"]) and not c["fundingKnown"]:return None
    net={}
    u=terms[s]["units"]
    # Source price increase normalized by previous complete H1 body RMS.
    d=math.log(p[z]/p[at])/r["sig"]
    scale=p[t]*u*fx0*r["sig"]
    for scenario in ("central","adverse"):
        spread=c["spreadMeanBps"] if scenario=="central" else c["observedSpreadP90Bps"]
        feeRate=max(0.,c[scenario+"Bps"]-spread)/20000
        for side in (1,-1):
            entry=p[at]*(1+spread/10000) if side>0 else p[at]
            exit=p[z] if side>0 else p[z]*(1+spread/10000)
            gross=side*u*(exit-entry)
            conv=gross*fxz*(1-c["conversionRate"]/2 if gross>=0 else 1+c["conversionRate"]/2)
            charges=(p[at]*fxa+p[z]*fxz)*u*feeRate
            swap=0.
            for k in range(at+M5,z+1,M5):
                if cross(k-M5,k,c["swapMinute"]):
                    fx=conversion(s,k,prices,terms)
                    if fx is None:return None
                    daily=c["longDailyDebitBps"] if side>0 else c["shortDailyDebitBps"]
                    swap+=3*daily*u*p[k]*fx*(1+c["conversionRate"]/2)/10000
            net[(scenario,side)]=conv-charges-swap
    return dict(price=d,scale=scale,net=net)

def train_ridge(x,y,weights,cols):
    a=np.column_stack((np.ones(len(x)),x[:,cols]))
    w=np.asarray(weights,float)
    normal=a.T@(a*w[:,None])
    normal[1:,1:]+=64*np.eye(len(cols))
    return np.linalg.solve(normal,a.T@(w*y))
def predict(x,cols,beta):
    return np.column_stack((np.ones(len(x)),x[:,cols]))@beta

def fixed_quantiles(errors):
    return np.quantile(errors,(np.arange(16)+.5)/16)

def positive_probability(forecast,quantiles,cost,scale,side):
    scenarios=((forecast+quantiles)*scale if side>0 else (-forecast-quantiles)*scale)+cost
    return float(np.mean(scenarios>0))

def offer_for(r,forecast,quantiles,prices,terms,costs,variant,calibrated):
    s=r["s"];c=costs.get(s);t=r["t"];p=prices[s].get(t)
    if c is None or p is None:return None
    fx=conversion(s,t,prices,terms)
    if fx is None:return None
    u=terms[s]["units"];scale=p*u*fx*r["sig"]
    hold=cross(t+M5,t+M5+H,c["swapMinute"])
    if hold and not c["fundingKnown"]:return None
    # All negative costs are a CAUSAL current-contract cost estimate at T.
    # Future original quote/path labels NEVER influence these estimates.
    def costs_for(side,scenario):
        allBps=c[scenario+"Bps"]
        debit=3*hold*(c["longDailyDebitBps"] if side>0 else c["shortDailyDebitBps"])
        return -(allBps+debit)*p*u*fx/10000
    actions=[];scores=[];risks=[];scens=[]
    for side in (1,-1):
        future=(forecast+quantiles)*scale*(1 if side>0 else -1)
        future=future+costs_for(side,"adverse")
        adverseMean=forecast*scale*(1 if side>0 else -1)+costs_for(side,"adverse")
        # Worst fifth of sixteen frozen residual quantiles, not a risk limit.
        worst=np.sort(future)[:4]
        es=max(0.,-float(np.mean(worst)))
        score=adverseMean-.5*es
        risk=max(.01,3*es)
        actions.append((costs_for(side,"central"),adverseMean))
        scores.append(score);risks.append(risk);scens.append(future.tolist())
    return dict(At=t+1,Symbol=s,Variant=variant,CalibratedThrough=int(calibrated),
        CentralLong=float(forecast*scale+actions[0][0]),
        CentralShort=float(-forecast*scale+actions[1][0]),
        AdverseLong=float(actions[0][1]),AdverseShort=float(actions[1][1]),
        RiskEur=risks,ScenarioNetEur=scens,ActionScore=scores)

def model_evaluation(rows,labels,prices,terms,costs):
    X=np.asarray([r["x"] for r in rows],float)
    y=np.asarray([lab["price"] if lab is not None else 0. for lab in labels],float)
    known=np.asarray([lab is not None for lab in labels])
    weeks=np.asarray([r["week"] for r in rows]);due=np.asarray([r["due"] for r in rows])
    t=np.asarray([r["t"] for r in rows]);symbol=np.asarray([r["s"] for r in rows])
    metrics=[];offers=[];modelReceipt=[];forecastHash=sha256();weeklyByVariant=defaultdict(list)
    chosen=Counter();scored=Counter();parity=[]
    for w in range(26,52):
        boundary=START+w*WEEK
        train=known&(due<boundary-4*WEEK-4*H)
        calibration=known&(due<boundary-4*H)&(t>=boundary-4*WEEK)
        test=np.flatnonzero(weeks==w)
        need(train.sum()>256 and calibration.sum()>64 and len(test)>0,"TRAIN_CAL_EVAL_SUPPORT")
        available=sorted(set(symbol[train]))
        weights=np.asarray([1/sum(symbol[train]==s) for s in symbol[train]])
        weights*=len(train[train])/len(available)
        for variant,cols in VARIANTS.items():
            beta=train_ridge(X[train],y[train],weights,cols)
            calpred=predict(X[calibration],cols,beta)
            residual=y[calibration]-calpred
            calblocks=sorted(set(weeks[calibration]))
            need(len(calblocks)>=4,"FOUR_CALIBRATION_WEEKS_UNKNOWN")
            q=fixed_quantiles(residual)
            calibrated=int(max(due[calibration]))
            preds=predict(X[test],cols,beta)
            valid=known[test];actual=y[test[valid]]
            mse=float(np.mean((preds[valid]-actual)**2))
            zeromse=float(np.mean(actual**2))
            meanError=float(np.mean(np.abs(preds[valid]-actual)))
            metric=dict(week=w+1,variant=variant,featureKnown=len(test),
                labelKnown=int(valid.sum()),labelUnknown=int((~valid).sum()),
                trainKnown=int(train.sum()),calibrationKnown=int(calibration.sum()),
                meanPriceForecast=float(np.mean(preds)),
                normalizedPriceMse=mse,zeroPriceMse=zeromse,
                normalizedPriceMae=meanError,
                beneficialPriceVsZero=zeromse-mse,
                nonzeroForecasts=int(np.count_nonzero(preds)),
                calibratedThrough=calibrated)
            metrics.append(metric)
            weeklyByVariant[variant].append(metric)
            modelReceipt.append(dict(week=w+1,variant=variant,coefficients=beta.tolist(),
                columns=cols,calibrationResidualQuantiles=q.tolist(),
                calibratedThrough=calibrated,calibrationWeekBlocks=[int(z+1) for z in calblocks]))
            if len(parity)<24:
                for k in range(min(2,len(test))):
                    idx=test[k]
                    parity.append(dict(beta=beta.tolist(),features=X[idx].tolist(),columns=cols,
                            expected=float(preds[k]),week=w+1,variant=variant))
            for j,i in enumerate(test):
                r=rows[i];forecast=float(preds[j])
                # Score every forecast before inspecting its forward economic label.
                sig=json.dumps(dict(t=r["t"],s=r["s"],variant=variant,
                                    forecast=forecast),sort_keys=True)
                forecastHash.update(sig.encode())
                offer=offer_for(r,forecast,q,prices,terms,costs,variant,calibrated)
                if offer is None:continue
                offers.append(offer)
                chosen[(variant,"proposedPositive")] +=int(max(offer["ActionScore"])>0)
                if labels[i] is not None:
                    scored[(variant,"knownAfterForecast")]+=1
                    candidate=1 if offer["ActionScore"][0]>0 and offer["ActionScore"][0]>offer["ActionScore"][1] else -1 if offer["ActionScore"][1]>0 and offer["ActionScore"][1]>offer["ActionScore"][0] else 0
                    if candidate!=0:chosen[(variant,"knownActionCounterfactualEuroCumulative")]+=float(labels[i]["net"][("adverse",candidate)])
        print("PVE3_WEEK_FROZEN_CHRONOLOGY",w+1,flush=True)
    paired=[]
    for w in range(26):
        full=weeklyByVariant["FULL"][w]
        own=weeklyByVariant["OWN"][w]
        need(full["week"]==own["week"],"PAIRED_WEEK_MISMATCH")
        paired.append(dict(week=full["week"],fullMinusOwnPriceMseBenefit=own["normalizedPriceMse"]-full["normalizedPriceMse"],
                           fullMinusZeroPriceMseBenefit=full["zeroPriceMse"]-full["normalizedPriceMse"]))
    return dict(weekly=metrics,pairedWeekly=paired,
        models=modelReceipt,forecastHash=forecastHash.hexdigest(),
        actionDiagnostics={str(k):v for k,v in chosen.items()},
        labelSupport={str(k):v for k,v in scored.items()},
        parity=parity),offers

def build_native_input(prices,terms,costs,offers,scenario):
    # Only causally OFFERED-positive assets need marks for a possible
    # allocation, but all available native holdings then get M5 marks.
    needed=defaultdict(set)
    for o in offers:
        if max(o["ActionScore"])<=0:continue
        t=o["At"]-1
        for mark in range(t,t+H+M5+1,M5):needed[o["Symbol"]].add(mark)
    quotes=[]
    for s,dates in sorted(needed.items()):
        c=costs[s];u=terms[s]["units"]
        spread=c["observedSpreadP90Bps"] if scenario=="adverse" else c["spreadMeanBps"]
        for at in sorted(dates):
            p=prices[s].get(at)
            fx=conversion(s,at,prices,terms)
            if p is None or fx is None:continue
            quotes.append(dict(Symbol=s,At=at,Bid=p,Ask=p*(1+spread/10000),
                EurCredit=fx*(1-c["conversionRate"]/2),
                EurDebit=fx*(1+c["conversionRate"]/2),
                ExitFeePerUnit=p*fx*max(0,c[scenario+"Bps"]-spread)/20000,
                ExitFeeFloor=0,MarginPerUnit=c["minimumMarginEur"]/u))
    contracts=[dict(Symbol=s,MinimumUnits=terms[s]["units"],
        StepUnits=terms[s]["step"],SwapMinute=c["swapMinute"],
        FundingKnown=c["fundingKnown"],LongDailyDebitBps=c["longDailyDebitBps"],
        ShortDailyDebitBps=c["shortDailyDebitBps"])
        for s,c in sorted(costs.items()) if s in terms]
    return dict(Start=FIRST,End=END,Scenario=scenario,Quotes=quotes,
                Offers=offers,Contracts=contracts)

def main():
    from .multiscale_conditional_research import recover,extract_costs
    from .integrated_predictive_funded import cost_context
    frozen=json.loads(Path("research/spde1_protocol.json").read_text())
    bars={};terms={};costsamples=[];audits=[]
    for spec,folder in zip(frozen["source"],("bdp-source","aip-source")):
        b,original,audit=recover(Path(folder),spec["run"],spec["sha256"],spec["schema"],spec["protocol"])
        need(set(b["bars"]).isdisjoint(bars),"ORIGINAL_SOURCE_OVERLAP")
        for sym,items in b["bars"].items():
            # Spotware original 1e5 integer-price arithmetic, never alter source.
            bars[sym]=[[z[0],z[1],*[float(v)/100000 for v in z[2:6]],z[6]] for z in items]
        audits.append(audit)
        for s,v in b["symbols"].items():
            if s in b["bars"]:
                terms[s]=dict(quoteAsset=v["quoteAsset"],
                   units=float(v["contract"]["minVolume"])/100,
                   step=float(v["contract"]["stepVolume"])/100)
        costrows,_=extract_costs(b,original)
        costsamples.extend(z for z in costrows if int(z["At"])<FIRST)
    need(len(bars)==12 and sum(map(len,bars.values()))==836087,"CANONICAL_AUTHENTIC_BARS_CHANGED")
    costs=cost_context(costsamples)
    for s,c in costs.items():
        records=[z for z in costsamples if z["Symbol"]==s]
        c["spreadMeanBps"]=float(np.mean([float(z["SpreadBps"]) for z in records]))
        c["conversionRate"]=max(float(z["ProfitConversionRate"]) for z in records)
        need(0<=c["conversionRate"]<2,"INVALID_COST_CONVERSION")
    rows,prices,census=panel(bars)
    label=[source_label(r,prices,terms,costs) for r in rows]
    need(sum(x is not None for x in label)>1000,"SOURCE_LABEL_COVERAGE_INSUFFICIENT")
    report,offers=model_evaluation(rows,label,prices,terms,costs)
    known_by_week=[dict(week=w+1,scheduled=120*len(bars),
            featureKnown=sum(x["week"]==w for x in rows),
            labelKnown=sum(x["week"]==w and y is not None for x,y in zip(rows,label)))
                   for w in range(52)]
    pub=dict(schema="MXM_PVE3_NEW_ORIGINAL_DISTRIBUTIONAL_PRICE_AND_ECONOMIC_RESEARCH_V1",
        executionRunId=os.environ.get("GITHUB_RUN_ID"),
        protocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),
        codeSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        sourceAudit=audits,originalSourceReadOnlyRequests=0,
        sourceBars=sum(map(len,bars.values())),sourceSymbols=sorted(bars),
        sourceCensus=census,weekCensus=known_by_week,
        globallyExposedDevelopment=True,independentConfirmation=False,
        predictive=report,economicDomain="AUTHENTIC_M5_BAR_PLUS_CURRENT_TERM_COST_CONDITIONAL_NOT_REAL_EXECUTION",
        historicalBrokerFillsCertified=False,continuousFloatingDrawdownCertified=False,
        ordersSubmitted=0,cloudActivated=False,qualified=False)
    # Persist predictive evidence BEFORE attempting C# funding; any native
    # failure must not erase successful original price-prediction scores.
    Path("pve3-original-predictive.json").write_text(json.dumps(pub,sort_keys=True,allow_nan=False)+"\n")
    dotnet=os.environ.get("PVE3_DOTNET","dotnet")
    dll="src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
    with tempfile.TemporaryDirectory(prefix="pve3-private-") as folder:
        a=Path(folder)/"input.json";z=Path(folder)/"result.json"
        a.write_text(json.dumps(report["parity"],allow_nan=False,separators=(",",":")))
        parityProc=subprocess.run([dotnet,dll,str(a),str(z),"--pve3-parity"],
            capture_output=True,text=True,timeout=180)
        need(parityProc.returncode==0,"EXPORTED_CSHARP_MODEL_PARITY_FAILED")
        pub["nativePredictiveParity"]=json.loads(z.read_text())
        for scenario in ("central","adverse"):
            inp=build_native_input(prices,terms,costs,offers,scenario)
            a.write_text(json.dumps(inp,allow_nan=False,separators=(",",":")))
            proc=subprocess.run([dotnet,dll,str(a),str(z),"--native-pve3"],
                text=True,capture_output=True,timeout=1800)
            if proc.returncode!=0:
                pub["native_"+scenario]=dict(status="UNKNOWN_NATIVE_EXECUTION_FAILURE",
                    stderr=proc.stderr[-600:],returnCode=proc.returncode)
                Path("pve3-original-public.json").write_text(json.dumps(pub,sort_keys=True,allow_nan=False)+"\n")
                raise RuntimeError("PVE3_NATIVE_"+scenario+"_FAILURE")
            pub["native_"+scenario]=json.loads(z.read_text())
            pub["native_"+scenario+"InputSha256"]=sha256(a.read_bytes()).hexdigest()
            Path("pve3-original-native-"+scenario+".json").write_text(z.read_text())
    # Prefix ex ante risk is not an observed worst loss; scorecard flags
    # keep R-multiples null until at least 20 complete trades with risks.
    pub["nativeCodeSha256"]=sha256(Path("src/Mxm.Replay/Pve3NativeActionResearch.cs").read_bytes()).hexdigest()
    Path("pve3-original-public.json").write_text(json.dumps(pub,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("PVE3_ORIGINAL_NEW_PREDICTIVE_PRICE_RESULT",json.dumps(dict(
        sourceBars=pub["sourceBars"],featureKnown=len(rows),labelKnown=sum(z is not None for z in label),
        pairedFirstThree=report["pairedWeekly"][:3])),flush=True)
    for scenario in ("central","adverse"):
        for variant in ("FULL","OWN","CASH"):
            book=pub["native_"+scenario][variant]
            print("PVE3_NATIVE_ECONOMIC",scenario,variant,
                  "NET",book["Scorecard"]["NetEur"],"TRIPS",book["Completed"],
                  "HARD21",book["Scorecard"]["Hard21AllEligibleWeeks"],flush=True)

if __name__=="__main__":main()
