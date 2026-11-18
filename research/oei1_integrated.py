"""OEI1 integrated source-first 3-phase research-only evaluation.

Original quotes, causal features, hindsight diagnostic, Bayesian / Markov /
nonlinear-depth2 models and conditional common EUR300 research book.
Never a LIVE/DEMO order, broker-fill certificate or Cloud final cBot.
"""
import base64, bisect, collections, hashlib, json, math, statistics
from datetime import datetime, timezone
from decimal import Decimal
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .contract_eur_cost import fee_at_current_contract, IncompleteCostEvidence

DAY=86400000
MIN=60000
WEEK=7*DAY
START=int(datetime(2026,8,17,tzinfo=timezone.utc).timestamp()*1000)
WEEKS=12
CLOCKS=list(range(830,911,5))  # 13:50 through 15:10, after 20m genuine warmup.
POSITIONS_LIMIT=2
MAX_RISK=90.
FORECAST_MIN_PROB=.55

def require(x,reason):
    if not x: raise ValueError("OEI1_"+reason)

def mean(xs):
    return statistics.mean(xs) if xs else 0.

def clip(x,lo,hi):
    return max(lo,min(hi,x))

def iso(t):
    w=datetime.fromtimestamp(t/1000,timezone.utc).isocalendar()
    return f"{w.year}-W{w.week:02d}"

def combine(bid,ask):
    """Join original side ticks preserving same-ms ambiguity; never invent quote."""
    if not bid or not ask: return [],[]
    b=a=0
    last_b=last_a=None
    pb=pa=0
    rows=[]
    while b<len(bid) or a<len(ask):
        now=min(bid[b][0] if b<len(bid) else 10**25,
                ask[a][0] if a<len(ask) else 10**25)
        uncertain=False
        while b<len(bid) and bid[b][0]==now:
            price=bid[b][1]/100000.
            if last_b==now and pb!=price: uncertain=True
            pb=price; last_b=now;b+=1
        while a<len(ask) and ask[a][0]==now:
            price=ask[a][1]/100000.
            if last_a==now and pa!=price: uncertain=True
            pa=price; last_a=now;a+=1
        if last_b is None or last_a is None:continue
        if now-last_b>10000 or now-last_a>10000 or not(0<pb<=pa):continue
        rows.append((now,pb,pa,uncertain))
    return rows,[x[0] for x in rows]

def asof(rows,times,t,maxage=10000):
    j=bisect.bisect_right(times,t)-1
    if j<0 or t-rows[j][0]>maxage:return None
    return rows[j]

def nextquote(rows,times,t):
    j=bisect.bisect_left(times,t)
    return rows[j] if j<len(rows) else None

def causal_terms(day,fxday,market,past,clock,scenario):
    """Only information available as-of clock. Never use exit fees or outcome."""
    q=asof(*day,clock)
    fx=asof(*fxday,clock)
    if q is None or q[3] or fx is None or fx[3]:
        return None,"DECISION_QUOTE_OR_FX_MISSING"
    spread=q[2]-q[1]
    tick=market["TickSize"]
    units=market["Units"]
    dist=max(10*tick,statistics.median(past["steps"]))
    slip=max(tick,spread*(1 if scenario=="adverse" else .25))
    try:
        fee=fee_at_current_contract(market["Contract"],"USD",str(units),q[2],
                                    {"USD":1/fx[1],"EUR":1})
        one_fee=float(Decimal(fee["oneSideContractCommissionEur"]))
    except (IncompleteCostEvidence,ArithmeticError,ValueError):
        return None,"DECISION_CURRENT_COMMISSION_UNKNOWN"
    known_round_trip=2*one_fee
    quote_risk=dist+spread+2*slip
    pnl_fee_allowance=quote_risk*units/fx[1]*int(market["Contract"].pnlConversionFeeRate)/10000
    risk=quote_risk*units/fx[1]+known_round_trip+pnl_fee_allowance
    if not math.isfinite(risk) or risk<=0:
        return None,"DECISION_RISK_INVALID"
    return dict(risk=risk,entry_fee_budget=known_round_trip+pnl_fee_allowance),None

def future_path(day, fxday, market, past, clock, side, scenario, terms):
    """Barrier exit from genuine timestamped quotes with >=100ms request delay."""
    quotes,times=day
    eurqt,eurts=fxday
    request=asof(quotes,times,clock)
    if request is None or request[3]: return None,"ENTRY_QUOTE_UNAVAILABLE"
    entry=nextquote(quotes,times,clock+100)
    if entry is None or entry[0]-clock>30000 or entry[3]:
        return None,"ENTRY_LATENCY_QUOTE_UNAVAILABLE"
    px0=(entry[1]+entry[2])/2
    spread0=entry[2]-entry[1]
    tick=market["TickSize"]
    distance=max(10*tick,statistics.median(past["steps"]))
    units=market["Units"]
    stop=px0-side*distance
    target=px0+side*distance*1.5
    slip0=max(tick, spread0*(1 if scenario=="adverse" else .25))
    entry_exec=(entry[2]+slip0) if side==1 else (entry[1]-slip0)
    if (side==1 and stop>=entry_exec) or (side==-1 and stop<=entry_exec):
        return None,"STOP_INVALID_AT_ENTRY"
    fx0=asof(eurqt,eurts,entry[0])
    if fx0 is None:return None,"ENTRY_FX_ROUTE_MISSING"
    cutoff=entry[0]+20*MIN
    start=bisect.bisect_left(times,entry[0])
    triggered=None;cause="SESSION_SAFETY"
    previous=entry[0]
    max_mfe=-1e100; min_mae=1e100
    localpeak=-1e100;worstdd=0.
    for j in range(start,len(quotes)):
        q=quotes[j]
        if q[0]>cutoff:
            triggered=cutoff
            cause="TIME_SAFETY"
            break
        if q[0]-previous>30000 or q[3]:
            return None,"UNKNOWN_TICK_PATH_OR_EQUAL_MS_ORDER"
        previous=q[0]
        mid=(q[1]+q[2])/2
        delta=side*(mid-px0)
        max_mfe=max(max_mfe,delta)
        min_mae=min(min_mae,delta)
        localpeak=max(localpeak,delta)
        worstdd=max(worstdd,localpeak-delta)
        executable=q[1] if side==1 else q[2]
        if side*(executable-stop)<=0:
            triggered=q[0];cause="OBSERVED_STOP";break
        if side*(executable-target)>=0:
            triggered=q[0];cause="OBSERVED_TARGET";break
    if triggered is None:
        return None,"INCOMPLETE_SESSION_PATH"
    exitq=nextquote(quotes,times,triggered+100)
    if exitq is None or exitq[0] > entry[0]+21*MIN or exitq[3]:
        return None,"EXIT_FILL_QUOTE_UNAVAILABLE"
    if exitq[0]-triggered>30000:return None,"EXIT_LATENCY_GAP"
    fx1=asof(eurqt,eurts,exitq[0])
    if fx1 is None:return None,"EXIT_FX_ROUTE_MISSING"
    spread1=exitq[2]-exitq[1]
    slip1=max(tick,spread1*(1 if scenario=="adverse" else .25))
    exit_exec=(exitq[1]-slip1) if side==1 else (exitq[2]+slip1)
    gross_usd=side*( (exitq[1]+exitq[2])/2 - px0)*units
    gross=gross_usd/(fx1[2] if gross_usd>=0 else fx1[1])
    fxdebit=(1/fx0[1]+1/fx1[1])/2
    spread=(spread0+spread1)*.5*units*fxdebit
    slippage=(slip0+slip1)*units*fxdebit
    c=market["Contract"]
    try:
        r0=fee_at_current_contract(c,"USD",str(units),entry[2],
                                   {"USD":1/fx0[1],"EUR":1})
        r1=fee_at_current_contract(c,"USD",str(units),exitq[2],
                                   {"USD":1/fx1[1],"EUR":1})
        commissions=float(Decimal(r0["oneSideContractCommissionEur"])+Decimal(r1["oneSideContractCommissionEur"]))
    except (IncompleteCostEvidence,ArithmeticError,ValueError):
        return None,"CURRENT_COMMISSION_OR_FX_UNKNOWN"
    conversion=abs(gross-spread-slippage)*int(c.pnlConversionFeeRate)/10000.
    net=gross-spread-slippage-commissions-conversion
    risk=terms["risk"]
    observed_worst=(min_mae-spread0-2*slip0)*units*(1/fx0[1])-commissions
    peaktrough=worstdd*units*(1/fx0[1])
    if not math.isfinite(net) or not math.isfinite(risk) or risk<=0:
        return None,"MONETARY_ARITHMETIC_INVALID"
    return dict(t=clock,entry_at=entry[0],exit_at=exitq[0],side=side,
                entry_exec=entry_exec,exit_exec=exit_exec,
                net=net,gross=gross,spread=spread,slippage=slippage,
                commissions=commissions,conversion=conversion,financing=0.,
                risk=risk,entry_fee_budget=terms["entry_fee_budget"],margin=market["Margin"],units=units,stop=stop,
                target=target,cause=cause,mfe=max_mfe*units/fx0[1],
                mae=min_mae*units/fx0[1],worst_float=observed_worst,
                intrapath_peak_to_trough=peaktrough),None

def groupfeat(s):
    return (s["market"],int(s["x"][3]>.5),int(s["x"][1]>0),s["side"])

class Bayes:
    def __init__(self,samples):
        self.globalavg=mean([s["y"] for s in samples])
        self.globalp=mean([s["y"]>0 for s in samples])
        self.gstats={}
        d=collections.defaultdict(list)
        for s in samples:d[groupfeat(s)].append(s["y"])
        for k,v in d.items():self.gstats[k]=v
    def predict(self,s):
        v=self.gstats.get(groupfeat(s),[])
        strength=12
        y=(sum(v)+strength*self.globalavg)/(len(v)+strength)
        p=(sum(x>0 for x in v)+strength*self.globalp)/(len(v)+strength)
        dispersion=math.sqrt((sum((x-y)**2 for x in v)+strength*.4)/(len(v)+strength))
        return (clip(p,.001,.999),y,y-dispersion/math.sqrt(len(v)+strength))

class Markov:
    def __init__(self,samples):
        self.g=collections.defaultdict(list)
        self.trans=collections.Counter()
        self.statefreq=collections.Counter()
        seen=collections.defaultdict(list)
        for s in samples:
            self.g[(s["market"],s["side"],s["state"])].append(s["y"])
            if s["side"]==1:seen[s["market"]].append((s["t"],s["state"]))
        for market,rows in seen.items():
            rows.sort()
            for (t,a),(u,b) in zip(rows,rows[1:]):
                if 0<u-t<=5*MIN:
                    self.trans[(market,a,b)]+=1
                    self.statefreq[(market,a)]+=1
        self.globaly=mean([s["y"] for s in samples])
        self.globalp=mean([s["y"]>0 for s in samples])
    def predict(self,s):
        m=s["market"];cur=s["state"];side=s["side"]
        total=self.statefreq[(m,cur)]
        probs=[(self.trans[(m,cur,z)]+1)/(total+2) for z in (0,1)]
        vals=[];wins=[];count=0
        for z in (0,1):
            v=self.g[(m,side,z)]
            count+=len(v)
            vals.append((sum(v)+12*self.globaly)/(len(v)+12))
            wins.append((sum(x>0 for x in v)+12*self.globalp)/(len(v)+12))
        y=sum(p*z for p,z in zip(probs,vals))
        p=sum(a*b for a,b in zip(probs,wins))
        return clip(p,.001,.999),y,y-1/math.sqrt(max(12,count))

class Tree:
    """Depth2 squared-error CART with explicitly fixed min leaf and candidate cuts."""
    def __init__(self,samples):
        self.forest={}
        self.glob=mean([s["y"] for s in samples])
        self.globp=mean([s["y"]>0 for s in samples])
        for name in sorted({s["market"] for s in samples}):
            self.forest[name]=self._node([s for s in samples if s["market"]==name],2)
    def _node(self,rows,depth):
        v=[x["y"] for x in rows]
        base=dict(y=(sum(v)+12*self.glob)/(len(v)+12),
                  p=(sum(x>0 for x in v)+12*self.globp)/(len(v)+12),
                  n=len(v),disp=math.sqrt(mean([(x-mean(v))**2 for x in v]) if v else 1))
        if depth==0 or len(rows)<80:return base
        best=None
        for feature in range(4):
            for cut in (-1.,0.,1.,.5):
                left=[x for x in rows if x["x"][feature]<=cut]
                right=[x for x in rows if x["x"][feature]>cut]
                if min(len(left),len(right))<40:continue
                lm=sum(x["y"] for x in left)/len(left)
                rm=sum(x["y"] for x in right)/len(right)
                err=sum((x["y"]-lm)**2 for x in left)
                err+=sum((x["y"]-rm)**2 for x in right)
                key=(err,feature,cut)
                if best is None or key<best[0]:best=(key,feature,cut,left,right)
        if best is None:return base
        _,f,c,left,right=best
        base.update(feature=f,cut=c,
                    left=self._node(left,depth-1),right=self._node(right,depth-1))
        return base
    def predict(self,s):
        node=self.forest.get(s["market"],dict(y=self.glob,p=self.globp,n=0,disp=1))
        while "feature" in node:
            node=node["left" if s["x"][node["feature"]]<=node["cut"] else "right"]
        y=node["y"];n=node["n"]
        return clip(node["p"],.001,.999),y,y-node["disp"]/math.sqrt(n+12)

class Placebo:
    def __init__(self,samples):
        self.inner=Bayes(self._shuffle(samples))
    @staticmethod
    def _shuffle(samples):
        # Circular 5-session block displacement within each market/side. Never shuffle eval.
        grouped=collections.defaultdict(list)
        for s in samples:grouped[(s["market"],s["side"])].append(s)
        out=[]
        for rows in grouped.values():
            rows.sort(key=lambda x:x["t"])
            labels=[s["y"] for s in rows]
            shift=min(len(rows)-1,5*len(CLOCKS)) if len(rows)>1 else 0
            for i,s in enumerate(rows):
                r=dict(s);r["y"]=labels[(i+shift)%len(rows)]
                out.append(r)
        return out
    def predict(self,s):return self.inner.predict(s)

def evaluate_predictive(model,samples,bias=0.):
    if not samples:return dict(N=0,Brier=None,MeanAbsRError=None,PositiveRate=None)
    preds=[model.predict(s) for s in samples]
    prob=[clip(p[0]+bias,.001,.999) for p in preds]
    return dict(N=len(samples),Brier=mean([(p-(s["y"]>0))**2 for p,s in zip(prob,samples)]),
                MeanAbsRError=mean([abs(p[1]-s["y"]) for p,s in zip(preds,samples)]),
                PositiveRate=mean([s["y"]>0 for s in samples]),
                PredictedPositiveRate=mean(prob),MeanPredictedR=mean([p[1] for p in preds]))

def interval_oracle(candidates):
    # Best of both directional outcomes when mutually exclusive as overlapping intervals.
    rows=sorted([s for s in candidates if s.get("complete") and s["net"]>0 and s["risk"]<=MAX_RISK
                 and s["margin"]+s["commissions"]<=300 and
                 s["intrapath_peak_to_trough"]<=90 and s["worst_float"]>=-90],
                key=lambda s:(s["exit_at"],s["entry_at"],s["market"],s["side"]))
    ends=[s["exit_at"] for s in rows]
    dp=[0.]*(len(rows)+1);back=[0]*(len(rows)+1);take=[False]*(len(rows)+1)
    for i,s in enumerate(rows,1):
        prev=bisect.bisect_right(ends,s["entry_at"],0,i-1)
        selected=dp[prev]+s["net"]
        if selected>dp[i-1]+1e-10:
            dp[i]=selected;back[i]=prev;take[i]=True
        else:
            dp[i]=dp[i-1];back[i]=i-1
    chosen=[];i=len(rows)
    while i:
        if take[i]:chosen.append(rows[i-1])
        i=back[i]
    chosen.reverse()
    require(all(x["exit_at"]<=y["entry_at"] for x,y in zip(chosen,chosen[1:])),
            "HINDSIGHT_INTERVAL_OVERLAP")
    require(abs(sum(x["net"] for x in chosen)-dp[-1])<1e-6,"ORACLE_RECONCILIATION")
    count_by_week=collections.Counter(iso(x["exit_at"]) for x in chosen)
    pool_by_week=collections.Counter(iso(x["exit_at"]) for x in rows)
    return dict(AllRecordedCandidates=len(candidates),EligiblePositiveCandidates=len(rows),
                RelaxedPositiveNetUpperEur=sum(x["net"] for x in rows),
                ExactOneSlotFixedOutcomeHindsightNetEur=dp[-1],
                OneSlotSelectedTrips=len(chosen),
                OneSlotSelectedWeeklyTrips={iso(START+w*WEEK):count_by_week[iso(START+w*WEEK)]
                                           for w in range(WEEKS)},
                OverlapRelaxedEligiblePositiveWeeklyCount={iso(START+w*WEEK):pool_by_week[iso(START+w*WEEK)]
                                           for w in range(WEEKS)},
                IsMarketWideUpperBound=False,IsCausalPolicy=False,
                ExactOnlyForRecordedIntervals=True,ContinuousDDCertified=False)

def replay(samples,forecast,scenario,marketdays):
    """Causal admission, original paths for subsequent fills; common EUR300.
    Minute sampled marks are conditional and never asserted continuous."""
    weeks=[iso(START+w*WEEK) for w in range(8,12)]
    selected=collections.defaultdict(list)
    for s in samples:
        if s["scenario"]==scenario and s["week"]>=8:selected[s["t"]].append(s)
    positions=[];closed=[]
    cash=300.;peak=300.;maxdd=0.;max_margin=0.;max_concurrent=0
    rejections=collections.Counter();unknown_marks=0;breaches=0
    suspended=False;scoreweeks=collections.Counter();unknown_selected=0
    days=[START+d*DAY for d in range(84) if datetime.fromtimestamp((START+d*DAY)/1000,timezone.utc).weekday()<5 and d//7>=8]
    for day in days:
        for minute in range(810,931):
            t=day+minute*MIN
            for s in list(positions):
                if s["exit_at"]<=t:
                    cash+=s["net"];closed.append(s);scoreweeks[iso(s["exit_at"])]+=1
                    positions.remove(s)
            floating=0.;known=True
            for s in positions:
                market=marketdays[(s["market"],day)]
                data,times=market
                q=asof(data,times,t)
                eur,eurts=marketdays[("EURUSD",day)]
                fx=asof(eur,eurts,t)
                if q is None or fx is None:
                    known=False;break
                liquidation=(q[1]-max(s["tick"],(q[2]-q[1])*(1 if scenario=="adverse" else .25))) if s["side"]>0 else (q[2]+max(s["tick"],(q[2]-q[1])*(1 if scenario=="adverse" else .25)))
                unreal_usd=s["side"]*(liquidation-s["entry_exec"])*s["units"]
                eurval=unreal_usd/(fx[2] if unreal_usd>=0 else fx[1])
                floating+=eurval-s["commissions"]-s["conversion"]
            if not known:
                unknown_marks+=1
                rejections["CURRENT_POSITION_MARK_UNKNOWN"]+=1
                continue
            eq=cash+floating
            peak=max(peak,eq)
            maxdd=max(maxdd,(peak-eq)/peak)
            margin=sum(s["margin"] for s in positions)
            max_margin=max(max_margin,margin)
            if maxdd>=.30:
                breaches+=1;suspended=True
            if minute%5 or t not in selected or suspended:continue
            if len(positions)>=POSITIONS_LIMIT:continue
            proposals=[]
            for s in selected[t]:
                if any(p["market"]==s["market"] for p in positions):
                    rejections["HELD_SYMBOL"]+=1;continue
                if s["risk"]>MAX_RISK:
                    rejections["RISK_ABOVE_90_INITIAL"]+=1;continue
                if forecast in ("MOMENTUM","REVERSION","EVENT"):
                    momentum=s["x"][1]>0
                    ok=(momentum if forecast=="MOMENTUM" else not momentum
                        if forecast=="REVERSION" else momentum and s["x"][3]>.5)
                    if not ok:continue
                    score=s["x"][1] if forecast!="REVERSION" else -s["x"][1]
                elif forecast=="CASH":
                    continue
                else:
                    pred=forecast["model"].predict(s)
                    probability=clip(pred[0]+forecast["bias"],.001,.999)
                    if pred[2]<=0 or probability<FORECAST_MIN_PROB:
                        rejections["PREDICTIVE_UTILITY_NOT_POSITIVE"]+=1
                        continue
                    score=pred[2]*s["risk"]
                proposals.append((score,s))
            # Prespecified score and stable symbol tie break; no future outcome used.
            proposals.sort(key=lambda k:(-k[0],k[1]["market"],-k[1]["side"]))
            for _,s in proposals:
                if len(positions)>=POSITIONS_LIMIT:break
                if any(p["market"]==s["market"] for p in positions):continue
                margin=sum(p["margin"] for p in positions)
                reserved=sum(p["risk"] for p in positions)
                if (eq-margin < s["margin"]+s["entry_fee_budget"] or
                    reserved+s["risk"]>min(90.,.3*peak) or
                    eq-margin-s["margin"]-s["entry_fee_budget"]<=0):
                    rejections["JOINT_MARGIN_OR_RISK"]+=1;continue
                if not s.get("complete"):
                    unknown_selected+=1
                    rejections["SELECTED_FUTURE_PATH_UNKNOWN"]+=1
                    suspended=True
                    break
                positions.append(s)
                max_concurrent=max(max_concurrent,len(positions))
                max_margin=max(max_margin,margin+s["margin"])
        # End of day safety; all valid sources have exited by 15:30.
        if positions:
            rejections["UNSETTLED_DAY_PATH"]+=len(positions)
            # Do not manufacture closure or reset positions.
            suspended=True
    n=len(closed)
    nets=[s["net"] for s in closed]
    wins=[x for x in nets if x>0]
    losses=[x for x in nets if x<0]
    r=[s["net"]/s["risk"] for s in closed]
    summary=dict(Policy=(forecast if isinstance(forecast,str) else forecast["name"]),
                 Scenario=scenario,InitialCashEur=300,TerminalCashEur=cash,
                 ClosedNetEur=cash-300,CompletedTrades=n,
                 FullSettlementKnown=len(positions)==0 and unknown_selected==0,
                 OpenPositions=len(positions),SelectedUnknownFuturePaths=unknown_selected,
                 GrossEur=sum(s["gross"] for s in closed),
                 SpreadEur=sum(s["spread"] for s in closed),
                 SlippageEur=sum(s["slippage"] for s in closed),
                 CommissionEur=sum(s["commissions"] for s in closed),
                 ConversionEur=sum(s["conversion"] for s in closed),
                 FinancingEur=sum(s["financing"] for s in closed),
                 ExpectancyEur=mean(nets) if n else None,
                 MeanR=mean(r) if n else None,WinRate=len(wins)/n if n else None,
                 ProfitFactor=sum(wins)/(-sum(losses)) if losses else None,
                 PayoffRatio=mean(wins)/(-mean(losses)) if wins and losses else None,
                 WorstTradeEur=min(nets) if n else None,
                 ExpectedShortfall5PctEur=mean(sorted(nets)[:max(1,math.ceil(.05*n))]) if n else None,
                 ObservedMinuteDrawdown=maxdd,UnknownHoldingMinuteMarks=unknown_marks,
                 MaximumConcurrentPositions=max_concurrent,PeakMarginEur=max_margin,
                 DrawdownThresholdBreachObservations=breaches,
                 Rejections=dict(rejections),
                 CompletedTripsPerWeek={w:scoreweeks[w] for w in weeks},
                 SystemHard21AllFourWeeks=all(scoreweeks[w]>=21 for w in weeks),
                 FullContinuousFloatingDDCertified=False,
                 HistoricalTariffsAndFillsCertified=False,
                 NativeFundedLedgerReplayed=False,
                 IndependentConfirmation=False,
                 ModelReplayNotBrokerNet=True)
    if n:
        require(abs((summary["GrossEur"]-summary["SpreadEur"]-summary["SlippageEur"]-
                  summary["CommissionEur"]-summary["ConversionEur"])-summary["ClosedNetEur"])<1e-5,
                "PORTFOLIO_NET_COMPONENTS")
    return summary

def run(tape):
    require(tape["Start"]==START and tape["End"]==START+WEEKS*WEEK,"FROZEN_WINDOW")
    names={m["Name"]:m for m in tape["Symbols"]}
    require("EURUSD" in names and len(names)>=3 and
            set(names)<={"EURUSD","ETHUSD","SpotBrent","US500"},"PRESOURCE_CLASS_SCOPE")
    markets={}
    days={}
    for name,m in names.items():
        c=e.ProtoOASymbol()
        c.ParseFromString(base64.b64decode(m["ContractProto"]))
        require(c.minVolume/100>0 and m["MinMarginEur"] and c.HasField("swapTime"),
                "CONTRACT_NATIVE_ORIGINAL")
        markets[name]=dict(Name=name,Class=m["Class"],Units=c.minVolume/100.,
                           TickSize=float(m["TickSize"]),Margin=float(m["MinMarginEur"]),
                           Contract=c)
        for d in m["Days"]:
            days[(name,d["Start"])]=combine(d["Bid"],d["Ask"])
    require(all((name,day) in days for name in markets for day in range(START,START+84*DAY,DAY)
                if datetime.fromtimestamp(day/1000,timezone.utc).weekday()<5),
            "SOURCE_DAY_ALIGNMENT")
    sample=[];census=collections.Counter();unknown=collections.Counter()
    for day in range(START,START+84*DAY,DAY):
        if datetime.fromtimestamp(day/1000,timezone.utc).weekday()>=5:continue
        eurday=days[("EURUSD",day)]
        for name,market in markets.items():
            dayquotes=days[(name,day)]
            for clockmin in CLOCKS:
                clock=day+clockmin*MIN
                historical=[]
                for j in range(5):
                    q=asof(*dayquotes,clock-(4-j)*5*MIN)
                    if q is None or q[3]:break
                    historical.append((q[1]+q[2])/2)
                if len(historical)!=5:
                    unknown["CAUSAL_WARMUP_OR_SIDE_QUOTE_UNKNOWN"]+=2;continue
                changes=[historical[i+1]-historical[i] for i in range(4)]
                steps=[abs(v) for v in changes]
                vol=max(10*market["TickSize"],statistics.median(steps))
                trend=(historical[-1]-historical[0])/vol
                shock=abs(changes[-1])>1.5*vol
                regime=int(abs(changes[-1])>vol)
                for side in (1,-1):
                    census["ORIGINAL_CANDIDATE_SIDES"]+=1
                    x=(clip(trend*side,-3,3),
                       clip(changes[-1]*side/vol,-3,3),
                       clip((abs(changes[-1])+abs(changes[-2]))/max(1e-12,sum(steps))*4-2,-3,3),
                       float(shock))
                    past=dict(steps=steps)
                    for scenario in ("central","adverse"):
                        terms,causal_reason=causal_terms(dayquotes,eurday,market,past,clock,scenario)
                        if causal_reason:
                            unknown[scenario+"_"+causal_reason]+=1
                            continue
                        offer=dict(market=name,Class=market["Class"],t=clock,side=side,
                                   x=x,state=regime,week=(day-START)//WEEK,
                                   scenario=scenario,tick=market["TickSize"],
                                   risk=terms["risk"],entry_fee_budget=terms["entry_fee_budget"],
                                   margin=market["Margin"],units=market["Units"],complete=False)
                        path,reason=future_path(dayquotes,eurday,market,past,clock,side,scenario,terms)
                        if reason:
                            unknown[scenario+"_"+reason]+=1
                            offer["CensoredReason"]=reason
                        else:
                            offer.update(path)
                            offer["complete"]=True
                            offer["y"]=offer["net"]/offer["risk"]
                        sample.append(offer)
    adverse=[s for s in sample if s["scenario"]=="adverse"]
    central=[s for s in sample if s["scenario"]=="central"]
    require(len(adverse)==len(central),"SCENARIO_SAMPLE_CARDINALITY")
    adverse_complete=[s for s in adverse if s.get("complete")]
    central_complete=[s for s in central if s.get("complete")]
    source_by_class=collections.Counter(s["Class"] for s in adverse_complete)
    phase1=dict(ScorableOriginalSidesPerClass=dict(source_by_class),
                DeclaredClassCount=len(markets),
                ScorableClassCount=sum(n>=40 for n in source_by_class.values()),ScopeClasses=[markets[x]["Class"] for x in markets],
                ScopeSymbols=list(markets),OriginalWeeks=12,
                OriginalSessionUtc="13:30-15:30",DecisionClocks="13:50-15:10 every five minutes",
                CorpusCausalOfferedSides=len(adverse),
                CorpusFutureCompleteSides=len(adverse_complete),
                CorpusFutureCensoredSides=len(adverse)-len(adverse_complete),
                ProposedSides=dict(census),
                MissingOrUnscorableReasons=dict(unknown),
                OracleCentral=interval_oracle(central_complete),
                OracleAdverse=interval_oracle(adverse_complete),
                HistoricalTariffsCertified=False,ExecutablePolicyFalseForOracle=True)
    if sum(n>=40 for n in source_by_class.values())<3:
        return dict(Study="OEI1_INTEGRATED_3PHASE",
            Status="PRESOURCE_STOP_INSUFFICIENT_THREE_CLASS_PATH_COVERAGE",
            Phase1=phase1,
            Phase2=dict(Status="NOT_SCORED_THREE_ORIGINAL_CLASSES_REQUIRED"),
            Phase3=dict(Status="NOT_SCORED_ORIGINAL_CLASS_GATE"),
            Source="ORIGINAL_PEPPERSTONE_READ_ONLY",
            ScopeIsNotFullMarket=True,GlobalCalendarExposed=True,
            NotIndependentConfirmation=True,HistoricalTariffContinuityCertified=False,
            FinalCloudCbotQualified=False)
    train=[s for s in adverse_complete if s["week"]<6]
    calib=[s for s in adverse_complete if 6<=s["week"]<8]
    evals=[s for s in adverse_complete if 8<=s["week"]<12]
    if len(train)<120 or len(calib)<20 or len(evals)<20:
        return dict(Study="OEI1_INTEGRATED_3PHASE",
            Status="PREDICTIVE_SAMPLE_CHRONOLOGY_STOP_NO_OUTCOME_PROMOTION",
            Phase1=phase1,
            Phase2=dict(Status="INSUFFICIENT_CAUSAL_CHRONOLOGY",
                        TrainCount=len(train),CalibrationCount=len(calib),
                        EvaluationCount=len(evals)),
            Phase3=dict(Status="NOT_SCORED_PREDICTIVE_EVIDENCE_UNAVAILABLE"),
            Source="ORIGINAL_PEPPERSTONE_READ_ONLY",
            ScopeIsNotFullMarket=True,GlobalCalendarExposed=True,
            NotIndependentConfirmation=True,HistoricalTariffContinuityCertified=False,
            FinalCloudCbotQualified=False)
    models={"BAYES":Bayes(train),"MARKOV":Markov(train),
            "TREE":Tree(train),"PLACEBO":Placebo(train)}
    calibrations={}
    for n,model in models.items():
        # Applied only to prediction probability, never retrofitted eval.
        calibration_residual=mean([float(s["y"]>0)-model.predict(s)[0] for s in calib])
        calibrations[n]=clip(calibration_residual,-.05,.05)
    def diag(pop):
        constant=mean([x["y"]>0 for x in train])
        baseline=dict(N=len(pop),Brier=mean([(constant-float(s["y"]>0))**2 for s in pop]))
        modelscores={}
        for n,m in models.items():
            z=evaluate_predictive(m,pop,calibrations[n])
            z["BrierImprovementVsConstant"]=(baseline["Brier"]-z["Brier"]) if z["N"] else None
            modelscores[n]=z
        return dict(Constant=baseline,Models=modelscores)
    phase2=dict(TrainSampleCount=len(train),CalibrationSampleCount=len(calib),
                EvaluationSampleCount=len(evals),
                CensoredOutcomesByPhase={"train":sum(s["week"]<6 and not s.get("complete") for s in adverse),
                                         "calibration":sum(6<=s["week"]<8 and not s.get("complete") for s in adverse),
                                         "evaluation":sum(s["week"]>=8 and not s.get("complete") for s in adverse)},
                TrainingWeeks=[iso(START+x*WEEK) for x in range(6)],
                CalibrationWeeks=[iso(START+x*WEEK) for x in range(6,8)],
                EvaluationWeeks=[iso(START+x*WEEK) for x in range(8,12)],
                Calibration=diag(calib),Evaluation=diag(evals),
                ByClass={name:diag([s for s in evals if s["market"]==name])
                         for name in markets},
                PlaceboMethod="train-only circular whole-five-session shift per symbol/side",
                PrespecifiedFamilywiseAlpha=.05,
                BonferroniAlphaPerOfThree=.05/3,
                InferentialIndependentYearConfirmation=False,
                FitOnExposedDevelopment=True)
    phase3={}
    for scenario in ("central","adverse"):
        phase3[scenario]={}
        for name,m in models.items():
            phase3[scenario][name]=replay(sample,dict(name=name,model=m,bias=calibrations[name]),scenario,days)
        for name in ("MOMENTUM","REVERSION","EVENT","CASH"):
            phase3[scenario][name]=replay(sample,name,scenario,days)
    phase3["FundedNativeCSharpLedger"] = False
    phase3["CausalAdmissionOnlyUsesKnownDecisionRisk"] = True
    phase3["FutureCensoredOffersRetainedAndFailClosedIfSelected"] = True
    phase3["Reason"] = "Research-only conditional EUR300 book, C# NativeFundedLedger parity not executed"
    phase3["NoBrokerOrderOrFill"] = True
    return dict(Study="OEI1_INTEGRATED_3PHASE",Status="ORIGINAL_3PHASE_CONDITIONAL_RESEARCH",
                Phase1=phase1,Phase2=phase2,Phase3=phase3,
                ScopeIsNotFullMarket=True,GlobalCalendarExposed=True,
                NotIndependentConfirmation=True,NoLookaheadInExecutableDecisionModels=True,
                HindsightHasLookaheadDiagnosticOnly=True,Source="ORIGINAL_PEPPERSTONE_READ_ONLY",
                RiskLimitContinuouslyCertified=False,HistoricalTariffContinuityCertified=False,
                FinalCloudCbotQualified=False)
