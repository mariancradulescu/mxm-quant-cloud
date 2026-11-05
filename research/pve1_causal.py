"""PVE1 preregistered authentic OHLCV test, not a rerun of frozen models.

Immutable original Pepperstone raw responses are reauthenticated using the
existing custody verification, with no new broker requests and no orders.
A source close is NEVER a broker fill; costs use current contract scenarios.
"""
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean,median
from .multiscale_conditional_research import recover,extract_costs
from .integrated_predictive_funded import market_view,cost_context

P=Path("research/pve1_protocol.json")
M5=300000
H=3600000
WEEK=7*24*H
FAMILIES=("VOLUME_EFFICIENT_ACCEPTANCE","VOLUME_ABSORPTION_REVERSAL")
HORIZONS=(60,240)

def need(x,why):
    if not x:raise ValueError("PVE1_"+why)
def phase(t,p):
    q=p["phase"]
    if t<q["developmentEnd"]:return "development",q["developmentEnd"]
    if t<q["selectionEnd"]:return "selection",q["selectionEnd"]
    if t<q["end"]:return "exposed_audit",q["end"]
    return None,None

def feature(rows,t,p):
    """49 exact completed M5 closes, prior complete hourly activity baseline."""
    f=p["features"]
    end=[rows.get(t-i*M5) for i in range(48,-1,-1)]
    if any(x is None for x in end):return {}
    values=[x[5] for x in end]
    if min(values)<=0:return {}
    returns=[math.log(values[i]/values[i-1]) for i in range(1,49)]
    r4=sum(returns)
    total=sum(abs(x) for x in returns)
    if total<=0:return {}
    efficiency=abs(r4)/total
    hourvol=sum(x[6] for x in end[-12:])
    history=[]
    # Every baseline hour ends BEFORE the four-hour feature interval.
    # Missing market hours are absent, not falsely assigned zero activity.
    for old in range(t-5*H,t-7*24*H-1,-H):
        past=[rows.get(old-i*M5) for i in range(12)]
        if all(x is not None for x in past):
            history.append(sum(x[6] for x in past))
        if len(history)==f["priorCompletedHourlyBaseline"]:break
    if len(history)<f["priorCompletedHourlyBaseline"] or median(history)<=0:return {}
    ratio=hourvol/median(history)
    r1=sum(returns[-12:])
    # M15 is the last three complete M5 returns, retained as a causal input
    # integrity diagnostic even though the fixed signs are H1/H4 based.
    m15=sum(returns[-3:])
    out={}
    if abs(r4)*10000>=f["fourHourReturnBpsMin"] and efficiency>=f["trendEfficiencyMin"] and ratio>=f["trendLastHourActivityRatioMin"]:
        out[FAMILIES[0]]=dict(side=1 if r4>0 else -1,momentum=1 if r4>0 else -1,
            activity=ratio,efficiency=efficiency,m15Bps=10000*m15)
    if abs(r4)*10000>=f["fourHourReturnBpsMin"] and efficiency<=f["absorptionEfficiencyMax"] and ratio>=f["absorptionLastHourActivityRatioMin"] and abs(r1)*10000>=f["oneHourDisplacementBpsMin"]:
        out[FAMILIES[1]]=dict(side=-1 if r1>0 else 1,momentum=1 if r4>0 else -1,
            activity=ratio,efficiency=efficiency,m15Bps=10000*m15)
    return out

def pvalue_from_weeks(x):
    if len(x)<8:return 1.
    a=mean(x);v=sum((z-a)**2 for z in x)/(len(x)-1)
    if v<=0:return 1. # no fabricated certainty from constant blocks
    t=a/math.sqrt(v/len(x))
    return .5*math.erfc(t/math.sqrt(2))

def measure(rows):
    if not rows:return dict(n=0,activeWeeks=0,grossMeanBps=None,incrementalVsMomentumBps=None,
        grossP=None,incrementalP=None,hitRate=None,brierSkillVsNeutral=None)
    by=defaultdict(list)
    for x in rows:by[x["week"]].append(x)
    weeks=sorted(by)
    gross=[mean(z["signedBps"] for z in by[w]) for w in weeks]
    delta=[mean(z["signedBps"]-z["momentumBps"] for z in by[w]) for w in weeks]
    # Non-fitted, conservative 0.55/0.45 probability with neutral Brier .25.
    br=mean(((.55 if z["side"]>0 else .45)-(1 if z["returnBps"]>0 else 0))**2 for z in rows)
    return dict(n=len(rows),activeWeeks=len(weeks),grossMeanBps=round(mean(z["signedBps"] for z in rows),6),
        incrementalVsMomentumBps=round(mean(z["signedBps"]-z["momentumBps"] for z in rows),6),
        grossP=round(pvalue_from_weeks(gross),9),incrementalP=round(pvalue_from_weeks(delta),9),
        hitRate=round(mean(1 if z["signedBps"]>0 else 0 for z in rows),6),
        brierSkillVsNeutral=round(1-br/.25,6),
        weeklyMinimumSamples=min(len(by[w]) for w in weeks))

def score(bars,p,cost):
    series={s:{x[1]:x for x in data} for s,data in bars.items()}
    views={s:market_view(data) for s,data in bars.items()}
    records=defaultdict(list)
    misses=defaultdict(int)
    rawCoverage={}
    for s in p["symbols"]:
        rows=series[s];v=views[s]
        candidates=[
            t for t in v["observed"] if t%(p["features"]["decisionMinutes"]*60000)==0 and p["phase"]["start"]<=t<p["phase"]["end"]]
        rawCoverage[s]=dict(m5Bars=len(rows),decisionClocks=len(candidates),
            h1Observed=sum(x[5]==12 for x in v["h"].values()))
        for t in candidates:
            signals=feature(rows,t,p)
            if not signals:
                misses[s,"FEATURE_OR_THRESHOLD_NOT_SUPPORTED"]+=1
                continue
            part,boundary=phase(t,p)
            if part is None:continue
            entry=t+p["features"]["entryDelayMinutes"]*60000
            if entry not in rows:
                misses[s,"NEXT_M5_ENTRY_MISSING"]+=len(signals)*len(HORIZONS);continue
            for family,signal in signals.items():
                for h in HORIZONS:
                    due=entry+h*60000
                    if due>=boundary:
                        misses[s,"PHASE_BOUNDARY_OR_FUTURE_MISSING"]+=1;continue
                    if due not in rows:
                        misses[s,"EXACT_EXIT_M5_MISSING"]+=1;continue
                    # Gross bid-close proxy only; not actual Pepperstone fills.
                    signed=10000*math.log(rows[due][5]/rows[entry][5])
                    week=(t-p["phase"]["start"])//WEEK
                    records[part,s,family,h].append(dict(t=t,entry=entry,due=due,week=week,
                        family=family,symbol=s,horizon=h,side=signal["side"],
                        signedBps=signal["side"]*signed,momentumBps=signal["momentum"]*signed,
                        returnBps=signed,activity=round(signal["activity"],4),
                        efficiency=round(signal["efficiency"],4)))
    tests=[]
    selected=set()
    threshold=.05/(len(p["symbols"])*len(FAMILIES)*len(HORIZONS))
    for symbol in p["symbols"]:
        for family in FAMILIES:
            for h in HORIZONS:
                dev=measure(records["development",symbol,family,h])
                sel=measure(records["selection",symbol,family,h])
                audit=measure(records["exposed_audit",symbol,family,h])
                c=cost.get(symbol)
                friction=c["adverseBps"] if c else None
                supported=(sel["n"]>0 and sel["activeWeeks"]>=8 and
                    sel["grossMeanBps"]>0 and sel["incrementalVsMomentumBps"]>0 and
                    sel["grossP"]<=threshold and sel["incrementalP"]<=threshold and
                    friction is not None and sel["grossMeanBps"]>friction)
                if supported:selected.add((symbol,family,h))
                tests.append(dict(symbol=symbol,family=family,horizonMinutes=h,
                    development=dev,selection=sel,globallyExposedAudit=audit,
                    currentAdverseCostBps=round(friction,6) if friction is not None else None,
                    selectionPass=supported,
                    historicallyIndependent=False))
    offers=defaultdict(list)
    for (phaseName,s,fam,h),rows in records.items():
        if phaseName!="exposed_audit" or (s,fam,h) not in selected:continue
        for z in rows:
            offers[z["t"]].append(dict(symbol=s,family=fam,horizon=h,side=z["side"],
                predBps=0.,knownAt=z["t"]))
    # Pre-audit selection expected value ONLY, not the future realized label.
    means={(z["symbol"],z["family"],z["horizonMinutes"]):z["selection"]["grossMeanBps"]
        for z in tests if z["selectionPass"]}
    for t,groups in offers.items():
        for o in groups:o["predBps"]=o["side"]*means[(o["symbol"],o["family"],o["horizon"])]
    return dict(tests=tests,selected=sorted(map(list,selected)),offers=offers,
        coverage=rawCoverage,omissions={str(k):v for k,v in sorted(misses.items())},
        multiplicityAlpha=threshold,sourceRows=sum(len(x) for x in bars.values()))

def source():
    p=json.loads(P.read_text())
    need(p["id"]=="PVE1" and p["status"]=="PREDECLARED_UNSCORED" and
         p["economics"]["initialCapitalEur"]==300,"PROSPECTIVE_PROTOCOL")
    need(not Path("docs/PVE1_AUTHENTIC_RESULT.json").exists(),"EXACT_RESULT_ALREADY_FROZEN")
    bars={};costs=[];audit=[]
    for row in p["sources"]:
        b,decoded,a=recover(Path(row["folder"]),row["run"],row["hash"],row["schema"],row["protocol"])
        for s,values in b["bars"].items():
            need(s not in bars,"DUPLICATED_ORIGINAL_ASSET")
            bars[s]=values
        c,cov=extract_costs(b,decoded)
        costs.extend(c)
        audit.append(dict(sourceRunId=row["run"],originalAuthenticated=a,
            costSamples=len(c),coverage=cov))
    need(set(bars)==set(p["symbols"]) and len(costs)==166,"EXACT_AUTHENTIC_UNIVERSE_OR_CONTEXTS")
    ctx=cost_context(costs)
    need(set(ctx)==set(bars),"BROKER_CONTRACT_COST_UNAVAILABLE")
    return p,bars,ctx,audit

def main():
    p,bars,cost,audits=source()
    result=score(bars,p,cost)
    # The same native C# allocator is invoked only on a preregistered
    # statistically supported and conditionally cost-positive selection.
    from .pve1_portfolio import evaluate
    economy=evaluate({s:market_view(x) for s,x in bars.items()},result["offers"],cost,p)
    data=dict(schema="PVE1_AUTHENTIC_12_ASSET_CAUSAL_OHLCV_V1",
        authority=p["authority"],runId=int(os.environ["GITHUB_RUN_ID"]),
        protocolSha256=hashlib.sha256(P.read_bytes()).hexdigest(),originalRuns=[x["run"] for x in p["sources"]],
        originalEvidence=audits,authenticM5Bars=result["sourceRows"],coverage=result["coverage"],
        preregisteredTestCount=len(result["tests"]),bonferroniAlpha=result["multiplicityAlpha"],
        tests=result["tests"],selectionSupported=result["selected"],
        omissions=result["omissions"],modelledCommon300Eur=economy,
        allDatesAlreadyGloballyExposed=True,independentConfirmation=False,
        costScenarioCertifiedHistorical=False,brokerFundedNetEur=None,
        maxContinuousDrawdownCertified=False,closedStudiesRescored=False,
        ordersSubmitted=0,cloudActivated=False,brokerRequests=0,tradingQualified=False)
    dest=Path("pve1-authentic-public.json")
    dest.write_text(json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    print("PVE1_AUTHENTIC_OHLCV_ECONOMICS "+json.dumps(dict(
        runId=data["runId"],bars=data["authenticM5Bars"],testCount=len(data["tests"]),
        supported=len(data["selectionSupported"]),cash=economy.get("FULL",{}).get("cashEur"),
        trades=economy.get("FULL",{}).get("modeledRoundTrips"),
        net=economy.get("FULL",{}).get("netClosedEur"),
        noBrokerNet=True,noIndependentHoldout=True),sort_keys=True),flush=True)

if __name__=="__main__":
    main()
