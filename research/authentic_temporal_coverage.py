"""Authenticated original M5/H1 temporal coverage only; no closed score or returns."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os
from .multiscale_conditional_research import recover
M5=300000;H=3600000;W=604800000;WINDOWS=(4,8,21)
def fmt(t):return datetime.fromtimestamp(t/1000,timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
def measure(bars,cal):
    start,end=cal["start"],cal["end"]
    if start>=end or (end-start)%W:raise ValueError("COVERAGE_CALENDAR")
    weeks=[dict(week=i,starts=fmt(start+i*W),symbols={},concurrent={str(h):0 for h in WINDOWS},concurrentClocksAt8={str(h):0 for h in WINDOWS}) for i in range((end-start)//W)]
    sync=defaultdict(lambda:defaultdict(set));assets={}
    for symbol,rows in sorted(bars.items()):
        stamps=set()
        for r in rows:
            if len(r)<7 or r[1]-r[0]!=M5 or r[0]<0 or r[1] in stamps:raise ValueError("COVERAGE_DUPLICATE_OR_CLOCK")
            if r[2]<=0 or r[4]<=0 or r[5]<=0 or r[3]<max(r[2],r[5]) or r[4]>min(r[2],r[5]) or r[6]<0:raise ValueError("COVERAGE_GEOMETRY")
            stamps.add(int(r[1]))
        ordered=sorted(stamps)
        if not ordered:raise ValueError("COVERAGE_EMPTY_SOURCE")
        gaps=Counter();largest=[]
        for a,b in zip(ordered,ordered[1:]):
            d=b-a
            if d%M5:raise ValueError("COVERAGE_OFF_GRID")
            absent=d//M5-1
            if absent:
                wkend=any(datetime.fromtimestamp(z/1000,timezone.utc).weekday()>=5 for z in (a+M5,(a+b)//2,b-M5))
                category="crossesWeekend" if wkend else "hourPlusSessionLikeUnverified" if absent>=12 else "shortUnclassified"
                gaps[category]+=1;gaps["missingM5Slots"]+=absent;largest.append((absent,a,b))
        bucket=[dict(m5=0,fullH1=0,**{f"feature{h}h":0 for h in WINDOWS},**{f"label{h}h":0 for h in WINDOWS}) for _ in weeks]
        for t in ordered:
            if t<start or t>=end:continue
            w=(t-start)//W;bucket[w]["m5"]+=1
            if t%H:continue
            if all(t-j*M5 in stamps for j in range(12)):bucket[w]["fullH1"]+=1
            for h in WINDOWS:
                if t<start+h*H or not all(t-j*M5 in stamps for j in range(12*h+1)):continue
                bucket[w][f"feature{h}h"]+=1
                phase_end=cal["developmentEnd"] if t<cal["developmentEnd"] else cal["selectionEnd"] if t<cal["selectionEnd"] else end
                if t<phase_end-65*60000 and all(t+j*M5 in stamps for j in range(1,14)):
                    bucket[w][f"label{h}h"]+=1;sync[(w,h)][t].add(symbol)
        for w in range(len(weeks)):weeks[w]["symbols"][symbol]=bucket[w]
        assets[symbol]=dict(m5=len(rows),first=fmt(ordered[0]),last=fmt(ordered[-1]),
            fullH1=sum(x["fullH1"] for x in bucket),
            feature21h=sum(x["feature21h"] for x in bucket),
            label21h=sum(x["label21h"] for x in bucket),
            label8h=sum(x["label8h"] for x in bucket),label4h=sum(x["label4h"] for x in bucket),
            gaps=dict(gaps),largestGaps=[dict(missingM5=m,a=fmt(a),b=fmt(b)) for m,a,b in sorted(largest,reverse=True)[:4]])
    for w,week in enumerate(weeks):
        for h in WINDOWS:
            lengths=[len(s) for s in sync[(w,h)].values()]
            week["concurrent"][str(h)]=max(lengths,default=0)
            week["concurrentClocksAt8"][str(h)]=sum(k>=8 for k in lengths)
            week[f"symbolsLabel{h}h"]=sum(v[f"label{h}h"]>0 for v in week["symbols"].values())
    return dict(schema="MXM_AUTHENTIC_TEMPORAL_COVERAGE_V1",metadataOnlyNoSignalOrReturnScoring=True,
        hrc1Exact253M5For21h=True,closedStudyRerun=False,sourceBars=sum(x["m5"] for x in assets.values()),
        assets=assets,weekly=weeks,
        hrc1DevelopmentWeeksWith8Assets=sum(x["symbolsLabel21h"]>=8 for x in weeks[:cal["developmentWeeks"]]),
        hrc1DevelopmentConcurrentClocksAt8=sum(x["concurrentClocksAt8"]["21"] for x in weeks[:cal["developmentWeeks"]]),
        allExposed=True,independentConfirmation=False,fundedNetEur=None,ordersSubmitted=0,cloudActivated=False,
        longGapsNotProvenSessionHours=True)
def run():
    p=json.loads(Path("research/hrc1_protocol.json").read_text())
    frozen_bytes=Path("docs/HRC1_AUTHENTIC_PILOT.json").read_bytes()
    frozen=json.loads(frozen_bytes)
    if frozen["developmentPilotPassed"] or frozen["selection"] is not None:raise ValueError("COVERAGE_HRC1_FREEZE")
    bars={}
    for item in p["source"]:
        b,_,authenticated=recover(Path(item["folder"]),item["run"],item["hash"],item["schema"],item["protocol"])
        if not authenticated or set(b["bars"]) & set(bars):raise ValueError("COVERAGE_SOURCE_ID")
        bars.update(b["bars"])
    if set(bars)!=set(p["sourceSymbols"]) or sum(map(len,bars.values()))!=frozen["rawSourceBars"]:raise ValueError("COVERAGE_SOURCE_SIZE")
    z=measure(bars,p["calendar"])
    z.update(workflowRunId=int(os.environ.get("GITHUB_RUN_ID","0")),
             sourceRuns=[x["run"] for x in p["source"]],authenticated=True,
             originalHrc1Sha256=hashlib.sha256(frozen_bytes).hexdigest(),
             originalHrc1CompleteLabels=frozen["development"]["knownCompleteLabels"],
             originalHrc1ActiveSignals=frozen["development"]["activeSignals"])
    Path("authentic-temporal-coverage-public.json").write_text(json.dumps(z,sort_keys=True,separators=(",",":"))+"\n")
    print("COVERAGE_GLOBAL "+json.dumps({k:v for k,v in z.items() if k in ("workflowRunId","sourceBars","authenticated","hrc1DevelopmentWeeksWith8Assets","hrc1DevelopmentConcurrentClocksAt8")}))
    for s,a in z["assets"].items():print("COVERAGE_ASSET "+json.dumps(dict(symbol=s,**a),sort_keys=True))
    for v in z["weekly"]:
        print("COVERAGE_WEEK "+json.dumps(dict(week=v["week"],start=v["starts"],assets21=v["symbolsLabel21h"],
             assets8=v["symbolsLabel8h"],assets4=v["symbolsLabel4h"],maxConcurrent=v["concurrent"],
             labels21={s:x["label21h"] for s,x in v["symbols"].items()},
             labels8={s:x["label8h"] for s,x in v["symbols"].items()}),sort_keys=True))
    if z["hrc1DevelopmentWeeksWith8Assets"]:raise ValueError("COVERAGE_HRC1_FROZEN_CONFLICT")
if __name__=="__main__":run()
