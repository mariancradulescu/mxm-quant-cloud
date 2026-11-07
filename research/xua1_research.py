"""XUA1: economic research on SIX authentic non-legacy H1 Pepperstone symbols.

Read back original encrypted MBF1 and ERP1 *wire source* only. NEVER call their
closed evaluators or reopen their hypotheses. C# parity is checked on actual
market features before ANY predictive forward returns are accessed.
"""
import hashlib
import json
import math
import os
import subprocess
import tempfile
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import mean,median,stdev,NormalDist

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .custody import unseal_new
from .mbf1_source import wire_pairs
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import decode_bars,decode_side
from .csp1_cost_preflight import asof_spread
from .f2_preflight import prospective_economic_futility

P=Path("research/xua1_protocol.json")
H=3_600_000;W=7*24*H
NAMES=("ENERGY_NEWS_IMPULSE_PERSISTENCE_4H",
       "CRYPTO_PANIC_REBOUND_6H",
       "ASIAN_INDEX_RISK_SYNCHRONY_3H",
       "GBPJPY_REJECTION_WICK_2H")
TYPES=("SpotCrude","SpotBrent","GBPJPY","ETHUSD","HK50","JPN225-F")
METRICS=("gross","central","adverse","stress","incremental")


def need(ok,code):
    if not ok:raise ValueError("XUA1_"+code)

def sha(content):return hashlib.sha256(content).hexdigest()

def asof_index(h1,t):
    """Last twenty-five real, completed H1 observations, never forward-filled."""
    timeline=sorted(h1)
    ix=bisect_right(timeline,t)
    if ix==0 or timeline[ix-1]!=t or ix<25:return None
    return [h1[k] for k in timeline[ix-25:ix]]

def valid(hist):
    if hist is None or len(hist)!=25:return False
    for i,b in enumerate(hist):
        at,o,hi,lo,close,v=b
        if at<=0 or o<=0 or close<=0 or lo<=0 or hi<o or hi<close or lo>o or lo>close or v<0:return False
        if i and hist[i-1][0]>=at:return False
    return True

def decide(name,symbol,h,peer=None):
    """Exact feature mirror of Mxm.Core.XuaNativeFeatureSigns, only closed H1."""
    if not valid(h):return 0
    at,o,high,low,close,vol=h[-1]
    idx={x[0]:x for x in h}
    sign=lambda x:1 if x>0 else -1 if x<0 else 0
    if name==NAMES[0] and symbol in ("SpotCrude","SpotBrent"):
        old=idx.get(at-4*H)
        if old is None:return 0
        move=10000*math.log(close/old[4])
        ret=[10000*abs(math.log(h[i][4]/h[i-1][4]))
             for i in range(1,24) if h[i][0]-h[i-1][0]==H]
        if len(ret)<12:return 0
        past=median(ret)
        activity=median(x[5] for x in h[4:24])
        return sign(move) if abs(move)>=max(15,3*past) and activity>0 and vol>=1.10*activity else 0
    if name==NAMES[1] and symbol=="ETHUSD":
        past=idx.get(at-24*H);prior=idx.get(at-H)
        if past is None or prior is None:return 0
        day=10000*math.log(close/past[4])
        bounce=10000*math.log(close/prior[4])
        return sign(bounce) if abs(day)>=180 and abs(bounce)>=10 and sign(day)*sign(bounce)==-1 else 0
    if name==NAMES[2] and symbol in ("HK50","JPN225-F") and valid(peer):
        if peer[-1][0]!=at:return 0
        pidx={z[0]:z for z in peer}
        a=idx.get(at-4*H);b=pidx.get(at-4*H)
        if a is None or b is None:return 0
        r1=10000*math.log(close/a[4]);r2=10000*math.log(peer[-1][4]/b[4])
        if abs(r1)<20 or abs(r2)<20 or sign(r1)!=sign(r2):return 0
        activity=median(x[5] for x in h[12:24])
        return sign(r1) if activity>0 and vol>=activity else 0
    if name==NAMES[3] and symbol=="GBPJPY":
        rng=high-low
        if rng<=0:return 0
        activity=median(x[5] for x in h[12:24])
        if activity<=0 or vol<activity:return 0
        up=high-max(o,close);down=min(o,close)-low
        if up>=.6*rng and close<o:return -1
        if down>=.6*rng and close>o:return 1
    return 0

def older_clocks(pr,source):
    start=pr["chronology"]["startUtcMs"]
    if source["id"].startswith("ERP"):
        return [start+w*W+(24+offset)*H for w in range(26) for offset in (12,16)]
    return [start+w*W+offset*H for w in range(13) for offset in (3,51,156)]

def decrypt_source(source,global_p):
    ciphertext=(Path(source["folder"])/"source.envelope.json").read_bytes()
    receipt=json.loads((Path(source["folder"])/"receipt.public.json").read_text())
    original=json.loads(Path(source["protocol"]).read_text())
    need(sha(ciphertext)==source["ciphertextSha256"],"ORIGINAL_CIPHERTEXT_HASH")
    need(sha(Path(source["protocol"]).read_bytes())==source["protocolSha256"],"ORIGINAL_PROTOCOL_HASH")
    need(int(receipt["runId"])==source["runId"] and receipt["complete"]
         and receipt["ciphertextSha256"]==source["ciphertextSha256"]
         and receipt["protocolSha256"]==source["protocolSha256"],"ORIGINAL_PUBLIC_RECEIPT")
    raw=json.loads(unseal_new(ciphertext,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),str(source["runId"])))
    need(raw["schema"]==receipt["schema"] and
         int(raw["runId"])==source["runId"] and
         raw["protocolSha256"]==source["protocolSha256"],"ORIGINAL_DECRYPTION")
    pairs=wire_pairs(raw["raw"])  # raw allowlist, protobuf roundtrip and account identities ONLY
    need(len(pairs)==source["expectedBrokerReadOnlyRequests"],"EXACT_RAW_REQUEST_GRID")
    (tq,tr),(aq,ar),(lq,lr)=pairs[:3]
    need(type(tq) is m.ProtoOATraderReq and type(aq) is m.ProtoOAAssetListReq and
         type(lq) is m.ProtoOASymbolsListReq and not lq.includeArchivedSymbols,
         "ORIGINAL_HEADER")
    account=int(tr.ctidTraderAccountId)
    fp=sha(("ctrader-account:"+str(account)).encode("ascii"))
    need(sha(fp.encode("ascii"))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and all(q.ctidTraderAccountId==account for q,r in pairs),
         "ORIGINAL_CRYPTOGRAPHIC_ACCOUNT")
    assets={a.assetId:a.name for a in ar.asset}
    need("pepperstone" in tr.trader.brokerName.lower()
         and assets.get(tr.trader.depositAssetId)=="EUR","ORIGINAL_PEPPERSTONE_EUR")
    listed={x.symbolName:x for x in lr.symbol if x.enabled}
    need(source["instruments"]==original["universe"]
         and all(s in listed for s in source["instruments"]),"FIXED_ORIGINAL_UNIVERSE")
    ids={};contracts={};ix=3
    for symbol in source["instruments"]:
        light=listed[symbol];sid=int(light.symbolId);ids[symbol]=sid
        dq,dr=pairs[ix];mq,mr=pairs[ix+1];ix+=2
        need(type(dq) is m.ProtoOASymbolByIdReq and list(dq.symbolId)==[sid]
             and len(dr.symbol)==1 and dr.symbol[0].symbolId==sid
             and type(mq) is m.ProtoOAExpectedMarginReq and mq.symbolId==sid,
             "CONTRACT_AND_VOLUME_ID")
        c=dr.symbol[0]
        need(c.HasField("minVolume") and c.HasField("stepVolume") and
             c.HasField("maxVolume") and 0<c.minVolume<=c.maxVolume and
             c.stepVolume>0 and int(c.tradingMode)==0 and
             list(mq.volume)==[c.minVolume] and mr.HasField("moneyDigits") and
             0<=mr.moneyDigits<=12 and len(mr.margin)==1 and
             mr.margin[0].volume==c.minVolume,"CONTRACT_MARGIN_GRID")
        value=Decimal(max(mr.margin[0].buyMargin,mr.margin[0].sellMargin))/(Decimal(10)**mr.moneyDigits)
        need(value>=0,"MARGIN_VALUE")
        contracts[symbol]=dict(currentMinMarginEur=float(value),
            minUnits=str(Decimal(c.minVolume)/100),
            stepUnits=str(Decimal(c.stepVolume)/100),
            tradingModeOpening=True,
            currentCommissionWirePresent=c.HasField("preciseTradingCommissionRate"),
            swapLongWirePresent=c.HasField("swapLong"),
            swapShortWirePresent=c.HasField("swapShort"))
    bars={s:{} for s in source["instruments"]}
    trunc={s:[] for s in source["instruments"]}
    start=global_p["chronology"]["startUtcMs"]
    for w in range(52):
        lo=start+w*W;hi=lo+W
        for symbol in source["instruments"]:
            q,r=pairs[ix];ix+=1
            need(type(q) is m.ProtoOAGetTrendbarsReq and q.symbolId==ids[symbol]
                 and q.period==e.H1 and q.fromTimestamp==lo and q.toTimestamp==hi
                 and r.period==e.H1 and r.HasField("hasMore"),"ORIGINAL_H1_GRID")
            if r.hasMore:
                trunc[symbol].append(w)
                continue
            for row in decode_bars(r.trendbar,lo-H,hi+H,60):
                if lo<=row[0] and row[1]<=hi:
                    at=int(row[1]);item=(at,float(row[2]),float(row[3]),
                                         float(row[4]),float(row[5]),int(row[6]))
                    need(at not in bars[symbol] or bars[symbol][at]==item,
                         "ORIGINAL_H1_CONFLICT")
                    bars[symbol][at]=item
    costs={s:[] for s in source["instruments"]}
    failures={s:Counter() for s in source["instruments"]}
    window=original["tickWindowBeforeClockMs"]
    for clock in older_clocks(global_p,source):
        for symbol in source["instruments"]:
            sides={};complete=True
            for side in (e.BID,e.ASK):
                q,r=pairs[ix];ix+=1
                need(type(q) is m.ProtoOAGetTickDataReq and
                     q.symbolId==ids[symbol] and q.type==side and
                     q.fromTimestamp==clock-window and q.toTimestamp==clock and
                     r.HasField("hasMore"),"ORIGINAL_QUOTE_CLOCK")
                if r.hasMore:
                    complete=False;sides[side]=[]
                else:sides[side]=decode_side(r.tickData,clock-window,clock)
            x=asof_spread(sides[e.BID],sides[e.ASK],clock,
                original["maximumQuoteAgeAtClockMs"],original["maximumBidAskTimeSkewMs"],complete)
            if x["status"]=="CAUSAL_PAIRED_SPREAD_OBSERVED":
                costs[symbol].append(float(x["spreadBps"]))
            else:failures[symbol][x["status"]]+=1
    need(ix==len(pairs),"RAW_REQUEST_UNUSED")
    return dict(bars=bars,quoteCosts=costs,quoteRejections=failures,
                contracts=contracts,truncations=trunc,
                proof=dict(runId=source["runId"],originalBound=True,
                    rawSourceRequests=len(pairs),
                    decryptedAccountDoubleSHA256Verified=True))

def cost_models(xs):
    need(xs and min(xs)>0,"INVALID_SPREAD_QUOTE")
    s=sorted(xs)
    q90=s[math.ceil(.9*len(s))-1]
    return dict(observed=len(xs),medianSpreadBps=median(s),p90SpreadBps=q90,
                centralBps=1.5*median(s)+6,
                adverseBps=2*q90+12,
                stressBps=3*max(s)+24)

def build_eligible(pr,sources):
    bars={};quotes={};contracts={};trunc={}
    for pack in sources:
        need(not set(pack["bars"]).intersection(bars),"SOURCE_SYMBOL_DUPLICATION")
        bars.update(pack["bars"]);quotes.update(pack["quoteCosts"])
        contracts.update(pack["contracts"]);trunc.update(pack["truncations"])
    need(sorted(bars)==sorted(pr["universe"]),"EXPLICIT_NEW_SIX_ASSET_UNIVERSE")
    eligible={};status={}
    for symbol in pr["universe"]:
        x=contracts[symbol];sample=quotes[symbol]
        why=[]
        if len(bars[symbol])<pr["eligibility"]["requiredHistoricalH1ClosesAtLeast"]:
            why.append("H1_COVERAGE_TOO_SMALL")
        if len(sample)<pr["eligibility"]["requiredFreshPairedBidAskCostClocksAtLeast"]:
            why.append("COST_CLOCK_OBSERVATIONS_INSUFFICIENT")
        if x["currentMinMarginEur"]<=0 or x["currentMinMarginEur"]>=300:
            why.append("CURRENT_MINIMUM_MARGIN_NOT_FINANCEABLE_EUR300")
        if not x["tradingModeOpening"]:why.append("NOT_OPENING_MODE")
        if trunc[symbol]:why.append("TRUNCATED_SOURCE_H1_WEEK")
        model=cost_models(sample) if sample else None
        if model is not None and (model["adverseBps"]<=0 or
                    not math.isfinite(model["adverseBps"])):
            why.append("MODEL_COST_NOT_FINITE")
        status[symbol]=dict(reason=why,H1=len(bars[symbol]),
            pairedQuoteCount=len(sample),contract=x,cost=model,
            truncations=trunc[symbol])
        if not why:eligible[symbol]=model
    return bars,eligible,status

def frames(h1,family,symbol,t):
    current=asof_index(h1[symbol],t)
    peer=None
    if family==NAMES[2]:
        other="JPN225-F" if symbol=="HK50" else "HK50"
        peer=asof_index(h1[other],t)
    return current,peer

def feature_cases(p,bars,eligible):
    """No future outcome prices are read to precompute signed decisions."""
    case_events={f:{"development":[],"selection":[]} for f in NAMES}
    counters={f:Counter() for f in NAMES}
    parity=defaultdict(list)
    start=p["chronology"]["startUtcMs"];dev=p["chronology"]["developmentEndUtcMs"]
    select=p["chronology"]["selectionEndUtcMs"]
    for spec in p["families"]:
        name=spec["id"];n=spec["horizonHours"]
        for symbol in spec["universe"]:
            if symbol not in eligible:
                counters[name]["excludedCostOrContract"]+=1
                continue
            ts=sorted(t for t in bars[symbol] if start<=t<select)
            for t in ts:
                h,peer=frames(bars,name,symbol,t)
                if not valid(h):
                    counters[name]["insufficientExactPastObservedH1"]+=1
                    continue
                side=decide(name,symbol,h,peer)
                # Valid H1 of peer absent -> causal abstention.
                # Stratify original-market parity cases by class BEFORE returns.
                if len(parity[name])<120 or (side and len(parity[name])<240):
                    parity[name].append((name,symbol,t,h,peer,side))
                if not side:
                    counters[name]["noAsOfEconomicFeature"]+=1
                    continue
                entry=t+H;exit_at=t+(n+1)*H
                phase="development" if t<dev else "selection"
                cut=dev if phase=="development" else select
                if exit_at>=cut:
                    counters[name]["crossesPhase"]+=1;continue
                if datetime.fromtimestamp(entry/1000,timezone.utc).date()!=datetime.fromtimestamp(exit_at/1000,timezone.utc).date():
                    counters[name]["overnightRolloverUnpriced"]+=1;continue
                if any(z not in bars[symbol] for z in range(entry,exit_at+H,H)):
                    counters[name]["futureBarGapUnknown"]+=1;continue
                prev=bars[symbol].get(t-H)
                benchmark=0 if prev is None else (1 if h[-1][4]>prev[4] else -1 if h[-1][4]<prev[4] else 0)
                case_events[name][phase].append(dict(symbol=symbol,week=(t-start)//W,
                    entry=entry,exit=exit_at,side=side,benchmark=benchmark))
                counters[name]["completeSourceEvents"]+=1
    return case_events,counters,[row for name in NAMES for row in parity[name]]

def parity_real_original(cases):
    """Native actual H1 feature signs must match BEFORE forward label scoring."""
    # Positive and zero feature signs are both represented, strictly selected
    # by source time/name, not by future returns.
    selected=[]
    seen=set()
    for row in cases:
        k=(row[0],row[1])
        if len(selected)>=1024:break
        selected.append(row)
        if row[5]:seen.add(k)
    inputs=[]
    for name,s,t,h,peer,side in selected:
        def pack(xs):
            return None if xs is None else [
                dict(CloseAt=x[0],Open=x[1],High=x[2],Low=x[3],Close=x[4],Volume=x[5]) for x in xs]
        inputs.append(dict(Mechanism=name,Symbol=s,History=pack(h),PeerHistory=pack(peer)))
    with tempfile.TemporaryDirectory() as td:
        src=Path(td)/"frames.json";out=Path(td)/"signs.json"
        src.write_text(json.dumps(inputs,separators=(",",":")))
        env={k:v for k,v in os.environ.items() if not k.startswith(("R3_","CTRADER_"))}
        run=subprocess.run(["dotnet","run","--project","src/Mxm.Replay","-c","Release",
            "--no-build","--",str(src),str(out),"--xua1-native-signs"],
            env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        need(run.returncode==0 and out.is_file(),"NATIVE_PARITY_RUN")
        observed=json.loads(out.read_text())
    expected=[row[5] for row in selected]
    need(observed==expected,"GENUINE_H1_PYTHON_CSHARP_SIGN_MISMATCH")
    return dict(realOriginalMarketFrames=len(selected),
        exactSignAgreement=True,featuresChecked=len(selected),
        nativeCloudLibrary="Mxm.Core.XuaNativeFeatureSigns",
        nativeReplayFlag="--xua1-native-signs")

def score_events(events,bars,models,base,weeks):
    week_asset=defaultdict(list);data=[]
    for ev in events:
        s=ev["symbol"];c=models[s]
        a=bars[s][ev["entry"]][4];b=bars[s][ev["exit"]][4]
        need(a>0 and b>0,"NONPOSITIVE_H1_OUTCOME")
        move=10000*math.log(b/a);gross=move*ev["side"]
        bench=ev["benchmark"]*move
        bench_net=bench-(c["adverseBps"] if ev["benchmark"] else 0)
        m=dict(gross=gross,central=gross-c["centralBps"],
               adverse=gross-c["adverseBps"],stress=gross-c["stressBps"],
               incremental=gross-c["adverseBps"]-bench_net)
        data.append(m);week_asset[(ev["week"],s)].append(m)
    weekly={k:[] for k in METRICS}
    for w in range(base,base+weeks):
        groups=[v for (wk,s),v in week_asset.items() if wk==w]
        for k in METRICS:
            weekly[k].append(mean(mean(x[k] for x in g) for g in groups) if groups else 0.)
    return dict(signalCount=len(events),activeWeeks=len({x["week"] for x in events}),
        symbolsWithEvents=sorted({x["symbol"] for x in events}),
        perSignalMeanBps={k:mean(x[k] for x in data) if data else None for k in METRICS},
        equalCalendarWeekMeanBps={k:mean(xs) for k,xs in weekly.items()},weekly=weekly)

def hac_lower(xs,alpha=.05,comparisons=8,lags=3):
    n=len(xs)
    if n<3 or stdev(xs)<=0:return None
    mu=mean(xs);center=[x-mu for x in xs]
    lrv=sum(x*x for x in center)/n
    for k in range(1,lags+1):
        acov=sum(center[i]*center[i-k] for i in range(k,n))/n
        lrv+=2*(1-k/(lags+1))*acov
    se=max(stdev(xs)/math.sqrt(n),math.sqrt(max(0,lrv)/n))
    return mu-NormalDist().inv_cdf(1-alpha/comparisons)*se

def run():
    original=P.read_bytes();p=json.loads(original)
    need(p["id"]=="XUA1" and p["locked"] and
         p["status"]=="PREDECLARED_UNSCORED" and
         p["fundedContinuation"]["capitalOneWalletEur"]==300 and
         p["safety"]["noLiveOrDemoOrders"] and
         p["source"]["additionalBrokerRequests"]==0,"OWNER_AUTHORITY")
    c=p["chronology"]
    need(c["developmentEndUtcMs"]-c["startUtcMs"]==26*W and
         c["selectionEndUtcMs"]-c["developmentEndUtcMs"]==13*W and
         c["endUtcMs"]-c["selectionEndUtcMs"]==13*W and
         p["uncertainty"]["comparisonsAcrossProgramme"]==8 and
         [f["id"] for f in p["families"]]==list(NAMES),"ORIGINAL_PROGRAM_NOT_CHANGED")
    sources=[decrypt_source(x,p) for x in p["source"]["sourceRuns"]]
    bars,eligible,table=build_eligible(p,sources)
    result=dict(schema="MXM_XUA1_EXPANDED_SIX_ASSET_AUTHENTIC_H1_EXPLORATORY_ECONOMICS_V1",
        runId=int(os.environ.get("GITHUB_RUN_ID","0")),
        originalProtocolSha256=sha(original),sourceProofs=[x["proof"] for x in sources],
        originalSealedSourcesReused=True,originalBrokerReadOnlyRequestsThisRun=0,
        sourceInstruments=list(p["universe"]),sourceInstrumentCount=6,
        sourceH1CountByInstrument={s:len(bars[s]) for s in p["universe"]},
        exactEligibilityByInstrument=table,eligibleMarkets=sorted(eligible),
        families={},genuineNativeCSharpParity=None,
        previouslyExposedHistoryWeeks=52,selectionHistoricalIndependent=False,
        globallyExposedAuditOutcomeScored=False,noClosedPredictorExecuted=True,
        qualifiedGroupIds=[],CSharpNativeLedgerFundedNetEur=None,
        nativeFundedClosedRoundTrips=0,systemHard21Proven=False,
        continuousFloatingDrawdown30Certified=False,
        ordersSubmitted=0,cloudActivated=False,tokenRefreshAttempted=False)
    if eligible:
        events,counts,cases=feature_cases(p,bars,eligible)
        result["genuineNativeCSharpParity"]=parity_real_original(cases)
        for name in NAMES:
            dev=score_events(events[name]["development"],bars,eligible,0,26)
            f2=prospective_economic_futility(dev["weekly"]["adverse"],
                 dev["weekly"]["incremental"],
                 model_cost_context_complete=True,predeclared_comparisons=8,
                 active_development_weeks=dev["activeWeeks"],
                 required_incremental_surplus_bps=0.,alpha_family=.05,hac_lags=3)
            entry=dict(sourceCounters=dict(counts[name]),sourceProposalCounts={
                x:len(events[name][x]) for x in ("development","selection")},
                development={k:v for k,v in dev.items() if k!="weekly"},
                developmentF2=f2,selectionOutcomeScored=False,selection=None)
            if not f2.get("scoreSelectionAllowed",False):
                entry["verdict"]="EXACT_STOP_F2_FUTILE_OR_UNINFORMATIVE"
            else:
                sel=score_events(events[name]["selection"],bars,eligible,26,13)
                nlb=hac_lower(sel["weekly"]["adverse"]);blb=hac_lower(sel["weekly"]["incremental"])
                supported=nlb is not None and blb is not None and nlb>0 and blb>0
                entry["selection"]={k:v for k,v in sel.items() if k!="weekly"}
                entry["selection"].update(dict(adjustedAdverseNetLowerBps=nlb,
                   adjustedMatchedBenchmarkIncrementalLowerBps=blb,
                   supportedConditionally=supported,actualFundedNetEur=None))
                entry["selectionOutcomeScored"]=True
                entry["verdict"]="EXPLORATORY_SELECTION_SUPPORT_NOT_FUNDED" if supported else "EXACT_SELECTION_REJECTED_ADVERSE_OR_BENCHMARK"
                if supported:result["qualifiedGroupIds"].append(name)
            result["families"][name]=entry
    result["verdict"]=("EXPLORATORY_SUPPORT_CSHARP_LEDGER_NOT_YET_ADMITTED"
        if result["qualifiedGroupIds"] else
        "NO_NEW_FUNDED_CANDIDATE_FROM_EXPANDED_SIX_H1_MARKETS")
    Path("xua1-authentic-public.json").write_text(json.dumps(result,
         sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    print("XUA1_SOURCE_CONTRACT_AND_PARITY "+json.dumps(dict(
         runId=result["runId"],originalH1=result["sourceH1CountByInstrument"],
         eligible=result["eligibleMarkets"],parity=result["genuineNativeCSharpParity"],
         orders=0),sort_keys=True),flush=True)
    for name,r in result["families"].items():
        print("XUA1_FAMILY "+json.dumps(dict(name=name,development=r["development"],
            f2=r["developmentF2"],selection=r["selection"],
            verdict=r["verdict"]),sort_keys=True),flush=True)
    print("XUA1_FINAL "+json.dumps(dict(verdict=result["verdict"],
        conditionalGroupIds=result["qualifiedGroupIds"],
        genuinelyFundedRoundTrips=0),sort_keys=True),flush=True)

if __name__=="__main__":
    run()
