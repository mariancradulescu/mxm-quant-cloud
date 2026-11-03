"""Causal five-FX USD-relative H4 dispersion reversal: authentic gross diagnostic.

No real/hypothetical fills, no funded NET, no orders. Frozen rank rule and
60/20/20 calendar, final 20% never scored. Historical bars are BID OHLC.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import log, sqrt, isfinite
from pathlib import Path
import hashlib, json, os, subprocess, sys, tempfile

PAIRS=("EURUSD","GBPUSD","AUDUSD","USDCAD","USDJPY")
SIGN={"EURUSD":1,"GBPUSD":1,"AUDUSD":1,"USDCAD":-1,"USDJPY":-1}
SOURCE_RUN="41476636915"
H4=14400000
DAY=86400000
WINDOW=72

class Inadmissible(ValueError):
    pass

def require(ok, reason):
    if not ok: raise Inadmissible(reason)

def weeks_fully_in_selection(lo,hi):
    current=datetime.fromtimestamp(lo/1000,timezone.utc)
    monday=(current-timedelta(days=current.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
    if int(monday.timestamp()*1000)<lo: monday+=timedelta(days=7)
    result=[]
    while int((monday+timedelta(days=5)).timestamp()*1000)<=hi:
        result.append(int(monday.timestamp()*1000))
        monday+=timedelta(days=7)
    return result

def score(tape):
    require(tape.get("schema")=="mxm-econ-source-v2" and tape.get("readOnly") is True,"SOURCE_SCHEMA")
    end=tape.get("captureEnd")
    require(isinstance(end,int) and end>0,"SOURCE_END")
    start=end-370*DAY; sel_lo=start+222*DAY; sel_hi=start+296*DAY
    series={s:{} for s in PAIRS}
    for b in tape.get("bars",[]):
        s=b.get("symbol")
        if s not in series or b.get("resolution")!="H4": continue
        t=b.get("openTime");a=b.get("availableTime");p=b.get("close")
        require(isinstance(t,int) and a==t+H4 and isinstance(p,(int,float)) and
                p>0 and isfinite(p),"INVALID_BAR")
        require(t not in series[s],"DUPLICATE_BAR")
        series[s][t]=float(p)
    for s in PAIRS:
        ts=series[s]
        require(len(ts)>=1100 and max(ts)+H4-min(ts)>=365*DAY,"INSUFFICIENT_YEAR")
    common=set.intersection(*(set(x) for x in series.values()))
    require(len(common)>=1050,"INSUFFICIENT_ALIGNED_HISTORY")
    ordered={s:sorted(series[s]) for s in PAIRS}
    indices={s:{t:i for i,t in enumerate(ordered[s])} for s in PAIRS}
    timestamps=sorted(t for t in common if sel_lo<=t+H4 and t+2*H4<=sel_hi)
    require(len(timestamps)>=200,"INSUFFICIENT_DECISION_WINDOWS")
    observations=[];missing=0
    for t in timestamps:
        z={}; future={}
        for s in PAIRS:
            ts=ordered[s]; ix=indices[s][t]
            if ix<WINDOW+1 or t+H4 not in series[s]: break
            history=[log(series[s][ts[j]]/series[s][ts[j-1]]) for j in range(ix-WINDOW,ix)]
            scale=sqrt(sum(v*v for v in history)/len(history))
            if scale<=0: break
            z[s]=SIGN[s]*log(series[s][t]/series[s][ts[ix-1]])/scale
            future[s]=SIGN[s]*log(series[s][t+H4]/series[s][t])
        if len(z)!=len(PAIRS):
            missing+=1
            continue
        middle=sorted(z.values())[2]
        residual={s:z[s]-middle for s in PAIRS}
        low=min(PAIRS,key=lambda s:(residual[s],s))
        high=max(PAIRS,key=lambda s:(residual[s],s))
        require(low!=high,"DEGENERATE_DISPERSION")
        # Equal-notional two-leg BID-bar close-to-close gross diagnostic.
        # Never call this a broker execution or an EUR return.
        bps=(future[low]-future[high])*5000
        observations.append((t+H4,bps,low,high))
    require(len(observations)>=30,"INSUFFICIENT_COMPLETE_GROSS_OBSERVATIONS")
    weeks=weeks_fully_in_selection(sel_lo,sel_hi)
    require(len(weeks)>=8,"INSUFFICIENT_FULL_SELECTION_WEEKS")
    vals=[v for _,v,_,_ in observations];mean=sum(vals)/len(vals)
    gross_week=[sum(v for t,v,_,_ in observations if w<=t<w+5*DAY) for w in weeks]
    mean_week=sum(gross_week)/len(gross_week)
    variance=sum((v-mean_week)**2 for v in gross_week)/(len(gross_week)-1)
    lower=mean_week-2.6*sqrt(variance/len(gross_week))
    weekly=[{"weekMondayUTC":datetime.fromtimestamp(w/1000,timezone.utc).strftime("%Y-%m-%d"),
             "completePlannedPairSignals":sum(1 for t,_,_,_ in observations if w<=t<w+5*DAY),
             "grossBpsPerLegNotionalSum":round(gross_week[i],6)}
            for i,w in enumerate(weeks)]
    chosen={s:{"relativeLong":0,"relativeShort":0} for s in PAIRS}
    for t,v,low,high in observations:
        chosen[low]["relativeLong"]+=1;chosen[high]["relativeShort"]+=1
    costs={}
    for b in (0,1,3,10):
        avg_turnover=sum(w["completePlannedPairSignals"] for w in weekly)/len(weekly)
        costs[str(b)]={"assumedRoundTripBpsPerLegNotBroker":b,
           "averagePairGrossLessAssumptionBpsPerLeg":round(mean-b,8),
           "weeklyLowerAfterAssumptionBps":round(lower-b*avg_turnover,8)}
    return {
      "schema":"mxm.usd-relative-dispersion-h4-gross.v1",
      "hypothesis":"USD_ALIGNED_FIVE_FX_H4_CROSS_SECTIONAL_RESIDUAL_REVERSAL_V1",
      "sourceRunId":int(SOURCE_RUN),
      "sourceAuthenticity":"ORIGINAL_SEALED_PEPPERSTONE_AND_NATIVE_CSHARP_PARITY",
      "phase":"DEVELOPMENT_SELECTION_NOT_UNTOUCHED_CONFIRMATION",
      "selectionStartUtc":datetime.fromtimestamp(sel_lo/1000,timezone.utc).isoformat(),
      "selectionEndUtc":datetime.fromtimestamp(sel_hi/1000,timezone.utc).isoformat(),
      "final20PctNotScored":True,
      "historicalH4BarsBySymbol":{s:len(series[s]) for s in PAIRS},
      "alignedH4Timestamps":len(common),"potentialDecisionWindows":len(timestamps),
      "missingSourceOrHistoryWindows":missing,
      "completeGrossPairObservations":len(observations),
      "plannedRoundTripLegsNOTExecuted":2*len(observations),
      "meanGrossBpsPerLeg":round(mean,8),
      "positiveGrossPairFraction":round(sum(v>0 for v in vals)/len(vals),8),
      "eligibleFullWeeks":len(weeks),
      "weeksWith21OrMorePlannedLegsNOTBrokerCompletions":sum(2*w["completePlannedPairSignals"]>=21 for w in weekly),
      "meanWeeklyGrossBpsPerLegNotional":round(mean_week,8),
      "approx95LowerWeeklyGrossBpsPerLegNotional":round(lower,8),
      "costSensitivityHypotheticalOnly":costs,
      "relativeSymbolSelectionDescriptiveOnly":chosen,
      "weeklyGrossDescriptive":weekly,
      "zeroCostGrossSupportGate":bool(lower>0),
      "brokerHistoricalBidAskEventExecution":False,"brokerActualFills":False,
      "historicalTrueCommissionAndSlippage":False,"fundedEur200Net":None,
      "fundedDrawdownPct":None,"realBrokerHard21":False,
      "independentConfirmation":False,"ordersSubmitted":0,
      "limitations":"Genuine H4 BID historical closes; label is forward BID-close movement, not an executable entry, midpoint, EUR funded return or fill. No contemporaneous event BID/ASK, quote-currency conversions, historic tariff, financing or real slippage. Selection dates development-exposed; no future data used to choose positions."
    }

def run():
    from .custody import unseal_new
    raw=Path("sealed-output/source.envelope.json").read_bytes()
    pub=json.loads(Path("sealed-output/receipt.public.json").read_text())
    require(pub.get("status")=="NEW_ECONOMIC_SOURCE_V2_SEALED" and
            hashlib.sha256(raw).hexdigest()==pub.get("ciphertextSha256"),"SEALED_DIGEST")
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    require(bool(key.strip()),"EXISTING_CUSTODY_PRIVATE_MISSING")
    tape=json.loads(unseal_new(raw,key,SOURCE_RUN))
    original=tape.pop("csharpReceipt",None)
    require(isinstance(original,dict),"NATIVE_SOURCE_RECEIPT_MISSING")
    with tempfile.TemporaryDirectory(prefix="mxm-usd-relative-") as d:
        inp=Path(d)/"source.json";out=Path(d)/"receipt.json"
        inp.write_text(json.dumps(tape,sort_keys=True));inp.chmod(0o600)
        env={k:v for k,v in os.environ.items() if not k.startswith(("R3_","CTRADER_","MXM_V4_"))}
        p=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                 str(inp),str(out),"--economic-source"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        require(p.returncode==0 and out.exists() and json.loads(out.read_text())==original,"ORIGINAL_CSHARP_PARITY")
    result=score(tape)
    result["originalNativeCSharpSourceParity"]=True
    result["sourceCiphertextSha256"]=pub["ciphertextSha256"]
    Path("relative-gross.public.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("AUTHENTIC_RELATIVE_GROSS_RESULT "+json.dumps({k:v for k,v in result.items() if k not in
          ("weeklyGrossDescriptive","relativeSymbolSelectionDescriptiveOnly")},sort_keys=True),flush=True)

if __name__=="__main__":
    try: run()
    except Exception:
        print("RELATIVE_GROSS_STUDY_FAILED_DETAIL_WITHHELD",flush=True)
        sys.exit(1)
