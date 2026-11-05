"""MBF1: predeclared causal multi-family predictive screen, no simulated fills or funded EUR."""
from __future__ import annotations
import math
import statistics
from collections import Counter
HOUR=3_600_000
WEEK=168*HOUR


def quantile(v, q):
    a=sorted(float(x) for x in v)
    if not a:return None
    return a[max(0,math.ceil(len(a)*q)-1)]


def cost_bps(samples,p):
    """Conservative separate per-target conditional round trip proxy; missing != 0."""
    out={}
    for s in p['universe']:
        a=samples.get(s,[])
        if len(a)<p['minimumCostPairsPerTarget']:
            out[s]=None;continue
        refs={'median':statistics.median(a),'p90':quantile(a,.9),'max':max(a)}
        out[s]={}
        for k,v in p['costScenarios'].items():
            out[s][k]=round(refs[v['spreadReference']]*(1+v['slippageSpreadMultiple'])+
                2*(v['hypotheticalCommissionPerSideBps']+v['hypotheticalConversionPerSideBps']),6)
    return out


def _return(closes,s,t,lag):
    """Require every intermediate completed close: never leap across a market shutdown."""
    rows=closes.get(s,{})
    if any(t-i*HOUR not in rows or rows[t-i*HOUR]<=0 for i in range(lag+1)):
        return None
    return 10000*math.log(rows[t]/rows[t-lag*HOUR])


def signals(closes,p):
    """All independent family rules fixed without any target return outcomes."""
    omissions=Counter();events=[]
    end=p['endUtcMs'];start=p['startUtcMs']
    for t in range(start,end,4*HOUR):
        weekday=((t//HOUR)//24+3)%7  # 1970-01-01 Thursday => Python Monday index 3
        hour=(t//HOUR)%24
        for family in p['candidateFamilies']:
            name=family['id'];target=family['target']
            if hour not in family['decisionUtcHours'] or weekday not in family['weekdays']:
                continue
            side=None
            if name=='ASIA_INDEX_RISK_HANDOFF':
                j=_return(closes,'JPN225-F',t,4)
                h=_return(closes,'HK50',t,4)
                if j is None or h is None:omissions[name+'/FEATURE_MISSING']+=1;continue
                if abs(j)>=family['source4hAbsBpsMin'] and abs(h)<=abs(j)*family['target4hAbsRatioMax']:
                    side=1 if j>0 else -1
            elif name=='TOKYO_LONDON_FX_POSITION_UNWIND':
                prior=_return(closes,'GBPJPY',t,8)
                if prior is None:omissions[name+'/FEATURE_MISSING']+=1;continue
                if abs(prior)>=family['overnightAbsBpsMin']:
                    side=-1 if prior>0 else 1
            elif name=='CRYPTO_WEEKEND_SHOCK_DRIFT':
                prior=_return(closes,'ETHUSD',t,4)
                if prior is None:omissions[name+'/FEATURE_MISSING']+=1;continue
                if abs(prior)>=family['source4hAbsBpsMin']:
                    side=1 if prior>0 else -1
            elif name=='CRYPTO_TO_FX_RISK_DELEVERAGING':
                eth=_return(closes,'ETHUSD',t,4)
                fx=_return(closes,'GBPJPY',t,4)
                if eth is None or fx is None:omissions[name+'/FEATURE_MISSING']+=1;continue
                if eth<=family['eth4hBpsMax'] and fx>=family['gbpjpy4hBpsMin']:
                    side=-1
            else:raise ValueError('UNREGISTERED_FAMILY')
            if side is None:
                omissions[name+'/NO_SIGNAL']+=1;continue
            for horizon in p['holdingHorizonsHours']:
                # Signal is known at t; proxy entry next hour and end at t+1+horizon.
                entry=t+p['entryLagHours']*HOUR
                exit_time=entry+horizon*HOUR
                if exit_time>=end or _return(closes,target,exit_time,horizon) is None:
                    omissions[name+'/FORWARD_MISSING']+=1;continue
                value=10000*side*math.log(closes[target][exit_time]/closes[target][entry])
                events.append(dict(family=name,target=target,horizon=horizon,
                    week=(t-start)//WEEK,at=t,side=side,grossBps=value))
    return events,dict(omissions)


def _phase(rows,lo,hi,cost):
    per_week=[[x for x in rows if x['week']==w] for w in range(lo,hi)]
    r=[x for x in rows if lo<=x['week']<hi]
    active=[sum(x['grossBps'] for x in w)/len(w) for w in per_week if w]
    gross=statistics.mean(x['grossBps'] for x in r) if r else None
    lower=None
    if len(active)>=2:
        lower=statistics.mean(active)-3.0*statistics.stdev(active)/math.sqrt(len(active))
    return {'completeModelledOpportunities':len(r),'activeWeeks':len(active),
        'emptyWeeks':(hi-lo)-len(active),'allWeeklyCounts':[len(x) for x in per_week],
        'grossMeanBps':round(gross,6) if gross is not None else None,
        'grossWinRate':round(sum(x['grossBps']>0 for x in r)/len(r),6) if r else None,
        'conservativeWeeklyLowerBps':round(lower,6) if lower is not None else None,
        'conditionalBeforeFinancingMeanBps':{k:round(gross-v,6) if gross is not None else None
            for k,v in (cost or {}).items()},
        'adverseWeeklyLowerAfterCostBps':round(lower-cost['adverse'],6)
            if lower is not None and cost is not None else None}


def evaluate(closes,samples,margins,p):
    if p['id']!='MBF1' or p['status']!='REGISTERED_UNSCORED' or len(p['candidateFamilies'])!=4 or \
        p['holdingHorizonsHours']!=[2,4] or \
        p['endUtcMs']-p['startUtcMs']!=52*WEEK:
        raise ValueError('MBF1_PROTOCOL_DRIFT')
    events,omissions=signals(closes,p)
    costs=cost_bps(samples,p)
    results=[];favorable=[]
    for family in p['candidateFamilies']:
        for h in p['holdingHorizonsHours']:
            name=family['id'];target=family['target'];arr=[x for x in events if x['family']==name and x['horizon']==h]
            c=costs[target]
            sections={ph:_phase(arr,lo,hi,c) for ph,lo,hi in
                      [('development',0,26),('selection',26,39),('globallyExposedAudit',39,52)]}
            selection=sections['selection'];test=p['promotionScreenSelectionOnly']
            passed=bool(c is not None and len(samples[target])>=test['minimumTargetCostSamples'] and
                selection['completeModelledOpportunities']>=test['minimumCompleteEpisodes'] and
                selection['activeWeeks']>=test['minimumActiveSelectionWeeks'] and
                selection['adverseWeeklyLowerAfterCostBps'] is not None and
                selection['adverseWeeklyLowerAfterCostBps']>test['adverseWeeklyLowerBoundMustExceedBps'])
            if passed:favorable.append(name+'/'+str(h))
            results.append({'family':name,'target':target,'horizonHours':h,
                'historicalDevelopmentQuotePairs':len(samples.get(target,[])),
                'costBps':c,'currentMinMarginEur':margins.get(target),
                'currentStaticMinMarginBelow200Eur':margins.get(target) is not None and margins[target]<200,
                'phases':sections,'selectionOnlyConditionalFollowupGate':passed})
    return {'schema':'mxm-mbf1-authentic-multifamily-exposed-predictive-v1',
       'study':'MBF1','universe':p['universe'],'candidateGroups':len(results),
       'authenticPriceClosesPerSymbol':{s:len(closes.get(s,{})) for s in p['universe']},
       'observedHistoricalDevelopmentCostQuotesPerSymbol':{s:len(samples.get(s,[])) for s in p['universe']},
       'omissions':omissions,'families':results,
       'selectionOnlyConditionalFollowupCandidates':favorable,
       'grossDefinition':'H1_CLOSE_NEXT_HOUR_PROXY_BPS_NOT_EXECUTABLE_BID_ASK_FILLS',
       'costDefinition':'OBSERVED_FIXED_DEVELOPMENT_SPREAD_PLUS_HYPOTHETICAL_COMMISSION_SLIPPAGE_CONVERSION_NO_FUNDING',
       'multiplicity':'8_FIXED_GROUPS_CONSERVATIVE_3_SE_WEEK_BLOCKS_NO_AUDIT_WINNER',
       'allInHistoricalCostsCertified':False,'nativeAllocatorInvoked':False,
       'fundedNetEur':None,'fundedRoundTrips':0,'systemHard21Proven':False,
       'continuousDrawdown30Proven':False,'independentConfirmation':False,
       'globallyExposedCalendar':True,'brokerFillsKnown':False,
       'ordersSubmitted':0,'cloudActivated':False,'tradingQualification':False,
       'economicVerdict':'FUNDING_REVIEW_POSSIBLE_ONLY_FOR_SELECTION_GATE_GROUPS' if favorable else 'NO_SELECTION_GROUP_CLEARS_ADVERSE_COST_AND_MULTIPLICITY_GATE'}
