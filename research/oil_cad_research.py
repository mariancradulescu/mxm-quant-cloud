"""OCE1 immutable rule. Pure as-of research on historical cTrader close observations.

No re-execution of BDP1 or ERP1's frozen predictions. Historical closes are not fills.
"""
from __future__ import annotations
import math
import statistics
from collections import Counter
from decimal import Decimal

MINUTE=60000
HOUR=60*MINUTE
WEEK=7*24*HOUR
TCRIT_ONE_SIDED_95=(0,6.314,2.920,2.353,2.132,2.015,1.943,1.895,1.860,1.833,1.812,1.796,1.782)

def _quantile(values, fraction):
    v=sorted(float(x) for x in values)
    return v[max(0,math.ceil(len(v)*fraction)-1)] if v else None

def first_causal_spread(bid,ask,nominal,window_ms=20000,maximum_age=2000,maximum_skew=2000):
    """Earliest jointly fresh valid event, not most favorable observed spread."""
    bid=sorted((int(t),int(price)) for t,price in bid if t<=nominal+window_ms)
    ask=sorted((int(t),int(price)) for t,price in ask if t<=nominal+window_ms)
    clocks=sorted({t for t,_ in bid+ask if nominal<=t<=nominal+window_ms})
    ib=ia=0;last_b=last_a=None
    for t in clocks:
        while ib<len(bid) and bid[ib][0]<=t:
            last_b=bid[ib];ib+=1
        while ia<len(ask) and ask[ia][0]<=t:
            last_a=ask[ia];ia+=1
        if last_b is None or last_a is None:continue
        bt,bp=last_b;at,ap=last_a
        if t-bt>maximum_age or t-at>maximum_age or abs(bt-at)>maximum_skew or bp<=0 or ap<=bp:continue
        return 20000*(ap-bp)/(ap+bp)
    return None

def cost_scenarios(spreads,protocol):
    c=protocol['quoteCost']
    if len(spreads)<c['minDevelopmentSamples']:return None
    bases={'central':statistics.median(spreads),'adverse':_quantile(spreads,.9),'stress':max(spreads)}
    result={}
    for case in bases:
        q=c[case]
        result[case]=round(bases[case]*(1+q['slippageSpreadMultiple'])+2*(q['commissionPerSideBpsHypothesis']+q['conversionPerSideBpsHypothesis']),6)
    return result

def _week_lower(rows,casecost):
    if len(rows)<2 or casecost is None:return None
    weekly=[statistics.mean(x['grossBps']-casecost for x in week) for week in rows if week]
    if len(weekly)<2:return None
    n=len(weekly)
    t=TCRIT_ONE_SIDED_95[min(n-1,12)]
    return round(statistics.mean(weekly)-t*statistics.stdev(weekly)/math.sqrt(n),6)

def evaluate(oil_h1,fx_m5,cost_samples,current_margin,p):
    """Calendar-first preflight, exactly one fixed causal signal, full 52-week account.

    Oil H1 close at t is known at decision t. FX entry at t+5m, exit at
    t+125m; every intervening M5 close is required, never forward-filled.
    """
    cal=p['decisionCalendar'];sig=p['causalSignal'];target=p['targetObservation']
    start=cal['startUtcMs'];end=cal['endUtcMs'];weeks=cal['weeks']
    if end-start!=weeks*WEEK or cal['selectionEndUtcMs']-start!=39*WEEK or cal['developmentEndUtcMs']-start!=26*WEEK:
        raise ValueError('OCE1_CALENDAR_INVALID')
    if target['exitLagMinutes']!=target['entryLagMinutes']+target['holdingMinutes']:
        raise ValueError('OCE1_EXIT_CLOCK_INVALID')
    selected=[];preflight=Counter();signal_counts=Counter();opportunities=[]
    history=[]
    for t in range(start,end,HOUR):
        # Past shock references are updated strictly after observing the current
        # clock, even if no trade is proposed at this time.
        if t in oil_h1 and all(t-i*HOUR in oil_h1 for i in range(1,sig['oilCompletedHourlyLookbackHours']+1)):
            ref=10000*math.log(oil_h1[t]/oil_h1[t-sig['oilCompletedHourlyLookbackHours']*HOUR])
        else:ref=None
        week=(t-start)//WEEK;day=(t//(24*HOUR)+3)%7;hour=(t//HOUR)%24
        if day in cal['weekdaysUtc'] and hour in cal['decisionHoursUtc']:
            preflight['scheduledClocks']+=1
            if ref is None:
                preflight['missingEnergyFeature']+=1
            else:
                timeline=[t+i*MINUTE for i in range(target['entryLagMinutes'],target['exitLagMinutes']+1,5)]
                if len(timeline)!=1+target['holdingMinutes']//5 or any(x not in fx_m5 for x in timeline):
                    preflight['incompleteFxEntryHoldingMarks']+=1
                else:
                    preflight['completeDecisionAndHoldingData']+=1
                    if len(history)<sig['priorReferenceDecisionClocks']:
                        signal_counts['warmupReferenceIncomplete']+=1
                    elif abs(ref)<sig['oilShockAbsVsPastMedian']*statistics.median(history[-sig['priorReferenceDecisionClocks']:]):
                        signal_counts['belowCausalVolatilityNormalizedShock']+=1
                    else:
                        side=-1 if ref>0 else 1 if ref<0 else 0
                        if side:
                            gross=10000*side*math.log(fx_m5[t+target['exitLagMinutes']*MINUTE]/fx_m5[t+target['entryLagMinutes']*MINUTE])
                            opportunities.append({'week':week,'decision':t,'entry':timeline[0],'exit':timeline[-1], 'grossBps':gross})
                            signal_counts['completeSignal']+=1
                        else:signal_counts['zeroShock']+=1
            if ref is not None:
                history.append(abs(ref))
    costs=cost_scenarios(cost_samples,p)
    phases={}
    for name,lo,hi in [('development',0,26),('selection',26,39),('globallyExposedAudit',39,52)]:
        fullweeks=[[x for x in opportunities if x['week']==w] for w in range(lo,hi)]
        rows=[x for week in fullweeks for x in week]
        n=len(rows);gross=statistics.mean(x['grossBps'] for x in rows) if n else None
        active=sum(bool(w) for w in fullweeks)
        # Non-overlap is opportunity capacity, NOT admitted positions/trades.
        nonoverlap=[]
        for week in fullweeks:
            last=-1;count=0
            for event in sorted(week,key=lambda x:x['exit']):
                if event['entry']>=last:count+=1;last=event['exit']
            nonoverlap.append(count)
        phases[name]={
          'allWeekUnfundedSignalCounts':[len(w) for w in fullweeks],
          'allWeekNonoverlapUpperOpportunityCounts':nonoverlap,
          'completeUnfundedSignals':n,'activeWeeks':active,'emptyWeeks':(hi-lo)-active,
          'meanGrossDirectionalBps':round(gross,6) if gross is not None else None,
          'grossPositiveRate':round(sum(x['grossBps']>0 for x in rows)/n,6) if n else None,
          'conditionalBeforeFinancingMeanBps':{k:round(gross-v,6) if gross is not None else None for k,v in (costs or {}).items()},
          'adverseOneSided95LowerActiveWeeklyNetBps':_week_lower(fullweeks,costs['adverse']) if costs is not None else None,
          'fundedRoundTrips':None
        }
    s=phases['selection'];th=p['promotionFromSelectionOnly']
    condition=bool(costs and s['activeWeeks']>=th['minActiveWeeks'] and s['completeUnfundedSignals']>=th['minCompleteSignals'] and
                 s['adverseOneSided95LowerActiveWeeklyNetBps'] is not None and s['adverseOneSided95LowerActiveWeeklyNetBps']>0)
    return {
      'schema':'mxm-oce1-source-bound-exposed-economic-result-v1',
      'study':'OCE1','premise':'CRUDE_SHOCK_CAUSAL_DELAYED_CAD_REPRICING',
      'originalAccountBoundSourcesOnly':True,'newBrokerRequests':0,
      'preflightComplete':dict(preflight),'causalSignalStatusCounts':dict(signal_counts),
      'quoteCostDevelopmentSampleCount':len(cost_samples),
      'historicalObservedSpreadPlusHypotheticalCostBps':costs,
      'currentMinimumUsdCadMarginEur':float(current_margin) if current_margin is not None else None,
      'staticSingleUsdCadMinMarginBelowInitial200Eur':current_margin is not None and Decimal(str(current_margin))<200,
      'phase':phases,'selectionSupportedConditionalFollowupOnly':condition,
      'economicallyRejectedOrUnqualified':not condition,
      'grossNotFundedNetEur':True,'fundedNetEur':None,'nativeAllocatorInvoked':False,
      'brokerExecutionCostProven':False,'historicalFundingProven':False,
      'eligibleSystemWeeksProven':False,'hard21Proven':False,'continuousDrawdown30Proven':False,
      'originalSourcesAndCalendarGloballyExposed':True,'independentConfirmation':False,
      'ordersSubmitted':0,'cloudActivated':False,'closedStudiesRescored':False,
      'financialInterpretation':'Directional log-bps only, costs are observed development spreads plus hypothetical slippage/commission/FX; gross and conditional proxies are NOT shared EUR200 financed net.'
    }
