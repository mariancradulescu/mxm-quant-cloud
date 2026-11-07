"""MFA1: ONE coordinated causal five-mechanism + adaptive-family system pilot.

Research reuses the TWO original encrypted authentic Pepperstone sources.
Unscored audit weeks stay unscored. All indicators have an identical
observation-only implementation in Mxm.Core/MultiFamilyNativeFeatures.cs.
Actual bid/ask fills, EUR-funded NET, HARD21 and independence are NOT inferred.
"""
import bisect
import hashlib
import json
import math
import os
import subprocess
import tempfile
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev, NormalDist
from .multiscale_conditional_research import recover, extract_costs
from .integrated_predictive_funded import cost_context
from .f2_preflight import prospective_economic_futility

P=Path("research/mfa1_protocol.json")
M5=300000
M15=3*M5
H=12*M5
WEEK=7*24*H
FAMILY=("SQUEEZE_RELEASE_30","H4_M30_PULLBACK_120",
        "TICK_CLIMAX_FADE_15","REOPEN_GAP_FADE_60",
        "INDEX_RELATIVE_DISPERSION_90")
ROTATION="ASOF_FOUR_WEEK_FAMILY_ROTATION"
HOLD=dict(zip(FAMILY,(30,120,15,60,90)))
METRICS=("grossBps","centralNetBps","adverseNetBps","stressNetBps",
         "incrementalVersusMatchedBenchmarkAdverseBps")


def require(condition,why):
    if not condition:raise ValueError("MFA1_"+why)


def sign(x):
    return (x>0)-(x<0)


def evaluate(symbol,t,index,peers=None):
    """Return five signs using only completed M5 bars at <=t; no labels."""
    current=index.get(t)
    ans={family:0 for family in FAMILY}
    if current is None:return ans
    recent=[index.get(t-i*M5) for i in range(49)]
    if all(x is not None for x in recent):
        if t%M15==0:
            older=sum(abs(math.log(recent[i-1][5]/recent[i][5]))
                      for i in range(13,49))/36
            quiet=sum(abs(math.log(recent[i-1][5]/recent[i][5]))
                      for i in range(4,13))/9
            impulse=math.log(recent[0][5]/recent[3][5])
            if older>0 and quiet<=.75*older and abs(impulse)>=max(3*quiet,.0002):
                ans[FAMILY[0]]=sign(impulse)
        if t%H==0:
            trend=math.log(recent[6][5]/recent[48][5])
            correction=math.log(recent[0][5]/recent[6][5])
            if (abs(trend)>=.0006 and trend*correction<0 and
                .15*abs(trend)<=abs(correction)<=.60*abs(trend)):
                ans[FAMILY[1]]=sign(trend)
    vol=[index.get(t-i*M5) for i in range(25)] if t%M15==0 else []
    if vol and all(x is not None for x in vol):
        previous=sum(x[6] for x in vol[3:24])
        new=sum(x[6] for x in vol[0:3])
        prior_three=sum(abs(math.log(vol[i-3][5]/vol[i][5]))
                        for i in range(6,25,3))
        motion=math.log(vol[0][5]/vol[3][5])
        if previous>0 and new/3>=2.5*previous/21 and abs(motion)>=max(1.8*prior_three/7,.0003):
            ans[FAMILY[2]]=-sign(motion)
    # Reopen requires genuine source timestamp discontinuity; supplied predecessor
    # is the immediate previous OBSERVED bar, not a synthetic t-5m candle.
    previous_observed=None
    if peers is not None and isinstance(peers,dict):
        previous_observed=peers.get("previousObserved")
    if previous_observed is not None:
        delta=t-int(previous_observed[1])
        if H<=delta<=72*H:
            jump=math.log(current[2]/previous_observed[5])
            if abs(jump)>=.0008:ans[FAMILY[3]]=-sign(jump)
    if (t%H==0 and symbol in ("US500","NAS100")
        and peers is not None and isinstance(peers,dict)
        and isinstance(peers.get("other"),dict) and
        all(x is not None for x in recent)):
        other=peers["other"]
        p0=other.get(t)
        p48=other.get(t-48*M5)
        if p0 is not None and p48 is not None and all(other.get(t-i*M5) is not None for i in range(49)):
            diff=math.log(recent[0][5]/recent[48][5])-math.log(p0[5]/p48[5])
            if abs(diff)>=.0008:ans[FAMILY[4]]=-sign(diff)
    return ans


def index_bars(rows):
    return {int(x[1]):x for x in rows}


def family_source_records(p,all_rows,cost_eligible):
    """Make causal signed proposals; only check future clock existence, never outcome."""
    cal=p["calendar"];start=cal["start"];development=cal["developmentEnd"];end=cal["selectionEnd"]
    idx={s:index_bars(all_rows[s]) for s in cost_eligible}
    clocks={s:sorted(v) for s,v in idx.items()}
    proposals={f:defaultdict(list) for f in FAMILY}
    counts={f:defaultdict(Counter) for f in FAMILY}
    samples=[]
    sampled_signals=Counter()
    selected_total=0
    for symbol in sorted(idx):
        m=idx[symbol]
        ordered=clocks[symbol]
        peer_sym=("NAS100" if symbol=="US500" else "US500" if symbol=="NAS100" else "")
        peer=idx.get(peer_sym,{})
        peer_clocks=clocks.get(peer_sym,[])
        for i,t in enumerate(ordered):
            if not start<=t<end:continue
            previous_observed=m[ordered[i-1]] if i>0 else None
            true_gap=bool(previous_observed and H<=t-previous_observed[1]<=72*H)
            if t%M15 and not true_gap:continue
            phase="development" if t<development else "selection"
            aux={"previousObserved":previous_observed,"other":peer}
            sides=evaluate(symbol,t,m,aux)
            for f,side in sides.items():
                if side:counts[f][phase]["causalFeatureSignals"]+=1
            # Bounded, outcome-BLIND parity sample: fixed clock modulus or first
            # N causal nonzero family signals; source labels are not touched.
            eligible_for_parity=(phase=="development" and selected_total<1200 and
                ((t//M15)%251==0 or any(sides.values()) and
                  any(sampled_signals[k]<60 and sides[k] for k in FAMILY)))
            if eligible_for_parity:
                for k,value in sides.items():
                    if value:sampled_signals[k]+=1
                j=bisect.bisect_right(ordered,t)
                pv=bisect.bisect_right(peer_clocks,t)
                sl=ordered[max(0,j-96):j]
                ps=peer_clocks[max(0,pv-96):pv]
                def native_row(row):
                    return dict(EndAt=int(row[1]),Open=float(row[2]),High=float(row[3]),
                       Low=float(row[4]),Close=float(row[5]),TickVolume=int(row[6]))
                samples.append(dict(Symbol=symbol,Peer=peer_sym,Clock=t,
                   Bars=[native_row(m[x]) for x in sl],
                   PeerBars=[native_row(peer[x]) for x in ps],
                   Expected=dict(Squeeze=sides[FAMILY[0]],Pullback=sides[FAMILY[1]],
                                 VolumeClimax=sides[FAMILY[2]],ReopenGap=sides[FAMILY[3]],
                                 IndexDispersion=sides[FAMILY[4]])))
                selected_total+=1
            for family,side in sides.items():
                if side==0:continue
                horizon=HOLD[family]
                entry=t+M5
                exit_=entry+horizon*60000
                phase_end=development if phase=="development" else end
                if exit_>=phase_end:
                    counts[family][phase]["crossesPhase"]+=1
                    continue
                # UTC midnight crossing entails unpriced rollover/funding.
                if entry//(24*H)!=exit_//(24*H):
                    counts[family][phase]["uncostedRolloverExcluded"]+=1
                    continue
                if any(u not in m for u in range(entry,exit_+M5,M5)):
                    counts[family][phase]["incompleteFutureM5Marks"]+=1
                    continue
                if family==FAMILY[3]:
                    benchmark=0 # real reopen gap: cash-flat, no fabricated past H1
                else:
                    past=m.get(t-12*M5)
                    if past is None or any(t-z*M5 not in m for z in range(13)):
                        counts[family][phase]["benchmarkPriorH1Missing"]+=1
                        continue
                    benchmark=sign(math.log(m[t][5]/past[5]))
                proposals[family][phase].append(dict(
                    family=family,symbol=symbol,clock=t,week=(t-start)//WEEK,
                    side=side,benchmarkSide=benchmark,entry=entry,exit=exit_))
                counts[family][phase]["completeSourceProposals"]+=1
    return idx,proposals,counts,samples


def parity_actual_source(samples):
    """Genuine original source feature parity BEFORE return scoring."""
    require(samples,"NO_ACTUAL_SOURCE_PARITY_CASES")
    with tempfile.TemporaryDirectory(prefix="mfa1-parity-") as tmp:
        src=Path(tmp)/"native_cases.json"
        out=Path(tmp)/"native_signs.json"
        trimmed=[{k:v for k,v in x.items() if k!="Expected"} for x in samples]
        src.write_text(json.dumps(trimmed,separators=(",",":")))
        # Secrets do not pass to the pure C# replay subprocess.
        env={k:v for k,v in os.environ.items()
             if not k.startswith(("R3_","CTRADER_","MXM_"))}
        command=["dotnet","run","--no-build","--project","src/Mxm.Replay",
                 "-c","Release","--",str(src),str(out),
                 "--native-mfa1-feature-parity"]
        subprocess.run(command,check=True,capture_output=True,text=True,env=env)
        actual=json.loads(out.read_text())
    require(len(actual)==len(samples),"NATIVE_PARITY_CASE_COUNT")
    fields=("Squeeze","Pullback","VolumeClimax","ReopenGap","IndexDispersion")
    mismatches=[]
    nonzero=Counter()
    for i,(candidate,from_csharp) in enumerate(zip(samples,actual)):
        expected=candidate["Expected"]
        for key in fields:
            if expected[key]:nonzero[key]+=1
            if from_csharp.get(key)!=expected[key]:
                mismatches.append(dict(case=i,symbol=candidate["Symbol"],
                      clock=candidate["Clock"],feature=key,
                      python=expected[key],csharp=from_csharp.get(key)))
                if len(mismatches)>=8:break
        if len(mismatches)>=8:break
    require(not mismatches,"NATIVE_PYTHON_PARITY_MISMATCH_"+json.dumps(mismatches))
    return dict(actualOriginalMarketSource=True,cases=len(samples),
        featureComparisonCount=len(samples)*len(fields),
        exactSignAgreement=True,observedNonzeroByMechanism=dict(nonzero),
        csharpLibrary="src/Mxm.Core/MultiFamilyNativeFeatures.cs",
        nativeReplay="src/Mxm.Replay --native-mfa1-feature-parity",
        cTraderCloudBrokerOrderCalls=0)


def event_score(row,prices,costs):
    cost=costs[row["symbol"]]
    a=prices[row["symbol"]][row["entry"]][5]
    b=prices[row["symbol"]][row["exit"]][5]
    require(a>0 and b>0,"NONPOSITIVE_BROKER_BAR")
    jump=10000*math.log(b/a)
    gross=row["side"]*jump
    bench=row["benchmarkSide"]*jump
    if row["benchmarkSide"]:bench-=cost["adverseBps"]
    return dict(row,
        grossBps=gross,centralNetBps=gross-cost["centralBps"],
        adverseNetBps=gross-cost["adverseBps"],
        stressNetBps=gross-cost["stressBps"],
        incrementalVersusMatchedBenchmarkAdverseBps=gross-cost["adverseBps"]-bench)


def summarize(rows,first,n):
    """Calendar-week clusters + equal instrument weight, 0 genuine quiet weeks."""
    groups=defaultdict(list)
    for row in rows:groups[(row["week"],row["symbol"])].append(row)
    weeks={m:[] for m in METRICS}
    for week in range(first,first+n):
        assets=[v for (w,s),v in groups.items() if w==week]
        for m in METRICS:
            weeks[m].append(mean(mean(r[m] for r in asset) for asset in assets)
                            if assets else 0.)
    averages={m:mean(r[m] for r in rows) if rows else None for m in METRICS}
    return dict(signalCount=len(rows),activeCalendarWeeks=len(set(r["week"] for r in rows)),
      activeTargetSymbols=len(set(r["symbol"] for r in rows)),
      signalWeightedMeanBps=averages,
      equalCalendarWeekMeanBps={m:mean(xs) for m,xs in weeks.items()},
      weeks=weeks)


def hac_lower(values,comparisons=12,alpha=.05,lag=3):
    n=len(values)
    if n<3 or stdev(values)<=0 or any(not math.isfinite(x) for x in values):
        return None
    avg=mean(values)
    residual=[x-avg for x in values]
    longrun=sum(x*x for x in residual)/n
    for d in range(1,lag+1):
        lag_cov=sum(residual[i]*residual[i-d] for i in range(d,n))/n
        longrun+=2*(1-d/(lag+1))*lag_cov
    standard=max(stdev(values)/math.sqrt(n),math.sqrt(max(0,longrun)/n))
    return avg-NormalDist().inv_cdf(1-alpha/comparisons)*standard


def adaptive_rows(families,first,end,seen_end):
    """One causal family selection per original week using 4 PRIOR full weeks.

    'families' are predeclared source events. Past labels only count when their
    week has ended; no same-week profit may choose its own selection.
    """
    chosen=[];audit=[]
    available={f:defaultdict(list) for f in FAMILY}
    for f in FAMILY:
        for row in families[f]:
            if row["week"]<seen_end:
                available[f][row["week"]].append(row)
    for week in range(first,end):
        weights=[]
        for f in FAMILY:
            older=[row["adverseNetBps"]
                for w in range(week-4,week)
                for row in available[f].get(w,[])]
            if len(older)>=3 and mean(older)>0:
                weights.append((mean(older),-FAMILY.index(f),f,len(older)))
        picked=max(weights)[2] if weights else None
        count=0
        if picked:
            chosen.extend(available[picked].get(week,[]))
            count=len(available[picked].get(week,[]))
        audit.append(dict(week=week,chosenFamily=picked,
             completeSourceProposalsForChosenFamily=count,
             selectedUsingOnlyWeeksBefore=week))
    return chosen,audit


def admissible_costs(p,bars,costs):
    eligible={}
    reasons={}
    observed=cost_context(costs)
    for symbol in p["sources"]["universe"]:
        x=observed.get(symbol,{})
        failures=[]
        if x.get("observed",0)<p["economicAdmission"]["minAuthenticCostContextPerEligibleSymbol"]:
            failures.append("TOO_FEW_AUTHENTIC_CURRENT_TERM_QUOTES")
        for key in ("minimumMarginEur","minimumNotionalEur","centralBps","adverseBps","stressBps"):
            value=x.get(key)
            if not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:
                failures.append("MISSING_OR_INVALID_"+key)
        if isinstance(x.get("minimumMarginEur"),(float,int)) and x["minimumMarginEur"]>=300:
            failures.append("MINIMUM_VOLUME_MARGIN_ABOVE_EUR300")
        if not bars.get(symbol):failures.append("MISSING_AUTHENTIC_M5")
        reasons[symbol]=failures
        if not failures:eligible[symbol]=x
    return eligible,reasons


def preflight(name,dev,p):
    sc=p["statistical"]
    return prospective_economic_futility(
       dev["weeks"]["adverseNetBps"],
       dev["weeks"]["incrementalVersusMatchedBenchmarkAdverseBps"],
       model_cost_context_complete=True,
       predeclared_comparisons=sc["totalOneSidedComparisons"],
       active_development_weeks=dev["activeCalendarWeeks"],
       required_incremental_surplus_bps=0.0,
       alpha_family=sc["familywiseOneSidedAlpha"],
       hac_lags=sc["baseOneSidedHACWeeksLag"])


def evaluate_selection(rows,prices,costs):
    selected=[event_score(row,prices,costs) for row in rows]
    result=summarize(selected,26,13)
    net=hac_lower(result["weeks"]["adverseNetBps"])
    incremental=hac_lower(result["weeks"]["incrementalVersusMatchedBenchmarkAdverseBps"])
    support=bool(net is not None and incremental is not None and net>0 and incremental>0)
    return dict(**{k:v for k,v in result.items() if k!="weeks"},
      bonferroniHac3AdverseNetLowerBps=net,
      bonferroniHac3IncrementalVsBenchmarkLowerBps=incremental,
      sourceProxyPositiveBoth=support,independentlyConfirmed=False,
      nativeFundedNetEur=None)


def run():
    raw=P.read_bytes()
    p=json.loads(raw)
    require(p["id"]=="MFA1" and p["status"]=="PREDECLARED_UNSCORED"
       and p["locked"] and p["product"]["oneCapitalEUR300"]
       and p["product"]["noLiveOrDemoOrders"]
       and p["product"]["noCloudActivation"],"LOCKED_AUTHORITY")
    c=p["calendar"];src=p["sources"];sc=p["statistical"]
    require((c["developmentEnd"]-c["start"],c["selectionEnd"]-c["developmentEnd"],
       c["end"]-c["selectionEnd"])==(26*WEEK,13*WEEK,13*WEEK),"CALENDAR")
    require([x["id"] for x in p["families"]]==list(FAMILY) and
       [x["horizonMinutes"] for x in p["families"]]==list(HOLD.values())
       and sc["totalOneSidedComparisons"]==12 and
       p["adaptiveSystem"]["lookbackFullWeeks"]==4,"PARAMETERS_LOCKED")
    manifest=json.loads(Path(src["originalSealedManifest"]).read_text())
    require([x["run"] for x in manifest["source"]]==src["originalPepperstoneSealedRuns"],
       "SOURCE_IDENTITY")
    bars={};all_costs=[];authenticated=[]
    for line in manifest["source"]:
        proof_data,decoded,authentication=recover(Path(line["folder"]),line["run"],
            line["hash"],line["schema"],line["protocol"])
        require(authentication and not (set(proof_data["bars"]) & set(bars)),
           "CUSTODY_OR_DUPLICATE_SYMBOL")
        bars.update(proof_data["bars"])
        values,_=extract_costs(proof_data,decoded)
        all_costs.extend(values)
        authenticated.append(dict(sourceRunId=line["run"],originalAccountBound=True))
    require(sum(map(len,bars.values()))==src["authenticM5Bars"] and
            len(all_costs)==src["authenticQuoteCostContexts"] and
            set(bars)==set(src["universe"]),"AUTHENTIC_SOURCES")
    eligible,excluded=admissible_costs(p,bars,all_costs)
    require(eligible,"NO_VALID_SOURCE_COST_CONTRACT")
    prices,proposals,counts,cases=family_source_records(p,bars,eligible)
    parity=parity_actual_source(cases) # BEFORE scoring even development outcomes.
    results=dict(schema="MXM_MFA1_COORDINATED_AUTHENTIC_CLOUD_PARITY_ECONOMICS_V1",
        runId=int(os.environ.get("GITHUB_RUN_ID","0")),
        originalLockedProtocolSha256=hashlib.sha256(raw).hexdigest(),
        originalAuthenticatedPepperstoneSources=authenticated,
        originalAuthenticatedM5Bars=sum(map(len,bars.values())),
        originalAuthenticCurrentTermQuoteCostContexts=len(all_costs),
        originalSource52WeeksGloballyExposed=True,
        genuinelyNewBrokerRequests=0,
        originalLiveAccountCryptoBound=True,
        costEligibleSymbols=sorted(eligible),
        excludedSymbolsWithReasons={s:v for s,v in excluded.items() if v},
        costScenarios={s:{k:v.get(k) for k in
            ("observed","minimumMarginEur","minimumNotionalEur",
             "centralBps","adverseBps","stressBps","fundingKnown")}
            for s,v in eligible.items()},
        fixedFamilyCount=5,
        adaptiveSystemPredeclared=True,
        wholeProgramOneSidedComparisonCount=12,
        strictNativeCSharpPythonParity=parity,
        families={},adaptive=None,
        qualifiedFamilyIds=[],adaptiveQualified=False,
        independentlyConfirmed=False,originalUnscoredAuditWeeks=13,
        auditReturnsViewed=False,nativeFundedNetEur=None,
        nativeCSharpFundedClosedRoundTrips=0,
        hard21SystemProven=False,continuousGlobalFloatingDD30Proven=False,
        cloudActivated=False,ordersSent=0,tokenRefreshRequests=0)
    # Score only DEVELOPMENT first for all base mechanisms and causal adaptation.
    development={}
    for f in FAMILY:
        dev=[event_score(r,prices,eligible) for r in proposals[f]["development"]]
        development[f]=dev
        sm=summarize(dev,0,26)
        gate=preflight(f,sm,p)
        results["families"][f]=dict(
            horizonMinutes=HOLD[f],
            causalSourceProposalsByPhase={
               ph:dict(counts[f][ph]) for ph in ("development","selection")},
            selectionSourceCompleteCount=len(proposals[f]["selection"]),
            development={k:v for k,v in sm.items() if k!="weeks"},
            developmentF2=gate,selection=None,selectionOutcomeViewed=False,
            verdict=("PREFLIGHT_PLAUSIBLE_NOT_SUPPORTED" if gate.get("scoreSelectionAllowed")
                     else "EXACT_F2_NO_SELECTION"))
    adap_dev,history_dev=adaptive_rows(development,0,26,26)
    sm=summarize(adap_dev,0,26)
    adap_gate=preflight(ROTATION,sm,p)
    results["adaptive"]=dict(
      id=ROTATION,
      causalWeekPolicyDevelopment=history_dev,
      development={k:v for k,v in sm.items() if k!="weeks"},
      developmentF2=adap_gate,selection=None,
      selectionOutcomeViewed=False,selectionWeekPolicy=None,
      verdict="PREFLIGHT_PLAUSIBLE_NOT_SUPPORTED" if adap_gate.get("scoreSelectionAllowed")
              else "EXACT_F2_NO_SELECTION")
    # Selection results are ONLY examined after family-specific F2 admission.
    for f in FAMILY:
        record=results["families"][f]
        if not record["developmentF2"].get("scoreSelectionAllowed",False):
            continue
        scored=evaluate_selection(proposals[f]["selection"],prices,eligible)
        record["selection"]=scored;record["selectionOutcomeViewed"]=True
        if scored["sourceProxyPositiveBoth"]:
            results["qualifiedFamilyIds"].append(f)
            record["verdict"]="EXPLORATORY_SELECTION_SUPPORT_REQUIRES_NATIVE_EUR300"
        else:record["verdict"]="CLOSED_EXACT_SELECTION_NET_OR_BENCHMARK_UNSUPPORTED"
    if adap_gate.get("scoreSelectionAllowed",False):
        # Any selection-week training labels belong exclusively to PAST
        # completed weeks, including unselected shadow families; this is a
        # separately predeclared adaptive experiment, not a reopened base trial.
        all_events={f:list(development[f])+
            [event_score(r,prices,eligible) for r in proposals[f]["selection"]]
            for f in FAMILY}
        adap_sel,week_policy=adaptive_rows(all_events,26,39,39)
        selected=summarize(adap_sel,26,13)
        net=hac_lower(selected["weeks"]["adverseNetBps"])
        inc=hac_lower(selected["weeks"]["incrementalVersusMatchedBenchmarkAdverseBps"])
        good=bool(net is not None and inc is not None and net>0 and inc>0)
        results["adaptive"]["selection"]={
            **{k:v for k,v in selected.items() if k!="weeks"},
            "bonferroniHac3AdverseNetLowerBps":net,
            "bonferroniHac3IncrementalVsBenchmarkLowerBps":inc,
            "sourceProxyPositiveBoth":good,"brokerFundedNetEur":None,
            "independentConfirmation":False}
        results["adaptive"]["selectionWeekPolicy"]=week_policy
        results["adaptive"]["selectionOutcomeViewed"]=True
        results["adaptive"]["verdict"]=(
            "EXPLORATORY_SELECTION_SUPPORT_REQUIRES_NATIVE_EUR300"
            if good else "CLOSED_EXACT_SELECTION_NET_OR_BENCHMARK_UNSUPPORTED")
        results["adaptiveQualified"]=good
        results["adaptive"]["pastMaturedShadowOutcomesUsedForCausalFamilyRotation"]=True
    results["verdict"]=("EXPLORATORY_CANDIDATE_NEEDS_NATIVE_CSHARP_FUNDED_LEDGER_AND_INDEPENDENCE"
        if results["qualifiedFamilyIds"] or results["adaptiveQualified"] else
        "COORDINATED_FIVE_FAMILIES_PLUS_ADAPTIVE_NO_NET_QUALIFICATION")
    Path("mfa1-authentic-public.json").write_text(
        json.dumps(results,separators=(",",":"),sort_keys=True,allow_nan=False)+"\n")
    summary=dict(
      runId=results["runId"],sourceM5=results["originalAuthenticatedM5Bars"],
      eligibleSymbols=results["costEligibleSymbols"],
      nativeParity=results["strictNativeCSharpPythonParity"],
      familyVerdicts={f:dict(verdict=v["verdict"],horizon=v["horizonMinutes"],
         development=v["development"],f2=v["developmentF2"],selection=v["selection"])
         for f,v in results["families"].items()},
      adaptive={k:v for k,v in results["adaptive"].items()
           if k in ("verdict","development","developmentF2","selection","selectionWeekPolicy")},
      qualified=results["qualifiedFamilyIds"],adaptiveQualified=results["adaptiveQualified"],
      verdict=results["verdict"],orders=0)
    print("MFA1_AUTHENTIC_RESEARCH "+json.dumps(summary,
          separators=(",",":"),sort_keys=True),flush=True)


if __name__=="__main__":
    run()
