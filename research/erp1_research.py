"""ERP1 causal energy relative-ratio reversion; no fills or funded EUR."""
from __future__ import annotations
import math, statistics
from collections import Counter
HOUR=3600000
WEEK=7*24*HOUR

def percentile(values,q):
    if not values:return None
    s=sorted(float(x) for x in values)
    return s[math.ceil(q*len(s))-1]

def cost_envelopes(samples,p):
    """Historical fixed-clock spread; separate hypothetical commission/slippage/FX."""
    symbols=p['universe']
    if any(len(samples.get(s,[]))<p['minimumCostPairsPerAsset'] for s in symbols):
        return None
    spreads={'central':sum(statistics.median(samples[s]) for s in symbols),
        'adverse':sum(percentile(samples[s],.9) for s in symbols),
        'stress':sum(max(samples[s]) for s in symbols)}
    out={}
    for k,v in p['costScenarios'].items():
        out[k]=round(spreads[k]*(1+v['slippageSpreadMultiple'])+
            2*(v['assumedCommissionPerLegBps']+v['assumedConversionPerLegBps']),6)
    return out

def evaluate(price_closes,cost_samples,min_margins,p):
    """Completely specified as-of signal and next-hour-entry proxy.

    Gross bps assume equal-notional paired log exposure, not volume-rounded
    executable EUR200 fills. Never use missing bars, audit selections or future
    outcomes to choose a signal, threshold, side or market.
    """
    a,b=p['universe']; ca,cb=price_closes[a],price_closes[b]
    common=sorted(set(ca)&set(cb))
    ratio={t:math.log(cb[t]/ca[t]) for t in common if ca[t]>0 and cb[t]>0}
    timeline=sorted(ratio)
    weeks=(p['endUtcMs']-p['startUtcMs'])//WEEK
    events=[];omissions=Counter();clocks=0
    for t in range(p['startUtcMs'],p['endUtcMs'],4*HOUR):
        week=(t-p['startUtcMs'])//WEEK
        if not 0<=week<weeks or (t//HOUR)%24 not in p['decisionHoursUtc']:continue
        clocks+=1
        if t not in ratio:omissions['missingPairedDecision']+=1;continue
        past=[ratio[u] for u in timeline if t-p['lookbackHours']*HOUR<=u<t]
        if len(past)<p['minimumPastPairedHours']:
            omissions['insufficientPriorPairedHistory']+=1;continue
        mid=statistics.median(past)
        scale=statistics.median(abs(x-mid) for x in past)*1.4826
        if scale<p['minimumLogRatioScale']:omissions['zeroRelativeScale']+=1;continue
        z=(ratio[t]-mid)/scale
        if abs(z)<p['fixedAbsZThreshold']:omissions['belowFixedDeviation']+=1;continue
        if any(t+i*HOUR not in ratio for i in (1,2,3,4)):
            omissions['incompleteNextEntryOrHolding']+=1;continue
        side=1 if z>0 else -1
        gross=10000*side*(ratio[t+HOUR]-ratio[t+4*HOUR])
        momentum=ratio[t]-ratio.get(t-4*HOUR,ratio[t])
        bm=10000*(1 if momentum>0 else -1 if momentum<0 else 0)*(
            ratio[t+4*HOUR]-ratio[t+HOUR])
        events.append({'week':int(week),'gross':gross,'momentumBenchmark':bm})
    cost=cost_envelopes(cost_samples,p)
    complete=all(min_margins.get(x) is not None for x in p['universe'])
    pair_margin=sum(float(min_margins[x]) for x in p['universe']) if complete else None
    phase={}
    for label,start,end in [('development',0,26),('selection',26,39),('globallyExposedAudit',39,52)]:
        rows=[e for e in events if start<=e['week']<end]
        weekly=[sum(e['week']==w for e in rows) for w in range(start,end)]
        mean=sum(e['gross'] for e in rows)/len(rows) if rows else None
        phase[label]={
            'completeUnfundedPairedOpportunities':len(rows),
            'weeks':end-start,'weeksWithZeroOpportunities':weekly.count(0),
            'maximumOpportunitiesOneWeek':max(weekly),
            'weeksAtLeast21UnfundedSignals':sum(v>=21 for v in weekly),
            'allWeekUnfundedOpportunityCounts':weekly,
            'meanGrossPairedBps':round(mean,6) if mean is not None else None,
            'grossWinRate':round(sum(e['gross']>0 for e in rows)/len(rows),6) if rows else None,
            'priorMomentumBenchmarkMeanBps':round(sum(e['momentumBenchmark'] for e in rows)/len(rows),6) if rows else None,
            'conditionalBeforeFinancingMeanBps':{k:round(mean-v,6) if mean is not None else None
                for k,v in (cost or {}).items()}
        }
    return {'schema':'mxm-erp1-authentic-exposed-predictive-summary-v1',
        'study':'ERP1','sourceType':'AUTHENTIC_H1_SPOTCRUDE_SPOTBRENT_FIXED_DEVELOPMENT_BID_ASK',
        'observedPairedH1Closes':len(ratio),'scheduled4hDecisionClocks':clocks,
        'rejectedClocksByPredeclaredReason':dict(omissions),
        'grossReturnDefinition':'EQUAL_NOTIONAL_PAIRED_LOG_BPS_UNFUNDED_NOT_EUR_NET',
        'marginCurrentMinimumPairEur':round(pair_margin,6) if complete else None,
        'staticCurrentMarginBelowEUR200':pair_margin<200 if complete else None,
        'developmentQuotePairsByAsset':{s:len(cost_samples.get(s,[])) for s in p['universe']},
        'historicalSpreadPlusHypotheticalNonFundingCostCasesBps':cost,
        'historicalAllInCostsCertified':False,'phase':phase,
        'independentConfirmation':False,'globalExposedCalendar':True,
        'fundedNetEur':None,'nativeAllocatorInvoked':False,'fundedRoundTrips':0,
        'systemHard21Proven':False,'continuousDrawdown30Proven':False,
        'brokerFillsKnown':False,'historicalFundingKnown':False,
        'tradingQualification':False,'ordersSubmitted':0,'cloudActivated':False,
        'conclusion':'CONDITIONAL_EXPLORATION_NO_FUNDED_NET_OR_INDEPENDENT_HOLDOUT'}
