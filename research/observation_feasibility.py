"""CEF1: economic observation support, not EPA2 replacement or policy replay.

Reuses authenticated exposed events solely to test the new native observation
clock and design feasibility. No return, signal ranking or allocation is scored.
"""
import base64,hashlib,json,os
from pathlib import Path
from decimal import Decimal as D
from .causal_observation import first_observation
from .custody import unseal_new
from .decode import need,decode_side
from .ctrader_proto import OpenApiMessages_pb2 as m
from .portfolio_economic_source import audit
from .portfolio_economic_replay import native


def windows(b,p):
    items=[]
    for nominal,indices in sorted(b['eventIndices'].items(),key=lambda x:int(x[0])):
        nominal=int(nominal);events=[];complete={}
        for symbol,rows in indices.items():
            complete[symbol]=True
            for side,ix in enumerate(rows):
                response=m.ProtoOAGetTickDataRes()
                response.ParseFromString(base64.b64decode(b['raw'][ix]['protobuf']))
                complete[symbol] &= not response.hasMore
                if not response.hasMore:
                    events.extend(dict(At=t,Symbol=symbol,Side=side,Price=price)
                        for t,price in decode_side(response.tickData,nominal+1000,nominal+41000))
        routes={s:{s,'EURUSD'} for s in p['universe']}
        for s in p['universe']:
            c=b['symbols'][s]['quoteAsset']
            if c=='JPY':routes[s].add('USDJPY')
            elif c=='CAD':routes[s].add('USDCAD')
        routes['ALL']=set(p['universe'])
        for offset in (0,30000):
            for name,route in sorted(routes.items()):
                items.append((name,dict(Nominal=nominal+offset,LatencyMs=1000,
                    SearchMs=10000,MaximumAgeMs=2000,Route=sorted(route),
                    Events=[e for e in events if e['Symbol'] in route and
                            nominal+1000<=e['At']<=nominal+offset+11000],
                    Complete=all(complete[s] for s in route))))
    return items


def evaluate(b,p):
    items=windows(b,p);requests=[w for _,w in items]
    reference=[first_observation(w) for w in requests]
    actual=native(requests,'--causal-observation-windows')
    need(actual==reference,'CEF1_NATIVE_PYTHON_FULL_EVENT_PARITY')
    observed={(name,w['Nominal']):r for (name,w),r in zip(items,actual)}
    valued={}
    for symbol in p['universe']:
        snapshots={str(t):dict(at=r['At'],quotes={q['Symbol']:dict(bid=q['Bid'],ask=q['Ask'],
            bidAt=q['BidAt'],askAt=q['AskAt']) for q in r['Quotes']})
            for (s,t),r in observed.items() if s==symbol and r['At'] is not None}
        source=dict(schema=b['schema'],readOnly=True,depositCurrency='EUR',symbols=b['symbols'],snapshots=snapshots)
        valued[symbol]=native(source,'--value-portfolio-source')['Snapshots']
    margin_cache={}
    def capacity(s,t):
        if (s,t) in margin_cache:return margin_cache[s,t]
        observation=observed.get((s,t))
        if observation is None or observation['At'] is None:return None
        row=b['symbols'][s];units=D(row['contract']['minVolume'])/100
        raw={q['Symbol']:dict(bid=q['Bid'],ask=q['Ask']) for q in observation['Quotes']}
        result=native(dict(EquityEur=200,PeakReferenceEur=200,DataComplete=True,
            Positions=[dict(Id='CEF1_MINIMUM_CAPACITY/'+s,Symbol=s,Units=units,
                EntryMarginPerUnitEur=D(row['currentMarginPerUnitBoundEur']),StressLossEur=0)],
            SourceSymbols=b['symbols'],RawQuotes=raw,
            AccountLeverage=D(b['riskTerms']['leverageInCents'])/100,
            DocumentedReferenceStopoutRatio=D('.5'),TierLeverageDivisor=100),'--assess-holding-risk')
        margin_cache[s,t]=result['UsedMarginEnvelopeEur']
        return margin_cache[s,t]
    def support(s,t):
        return s in valued.get(s,{}).get(str(t),{}).get('Quotes',{})
    def path(s,day,horizon,replay=False):
        start=b['decisionClocks'][day]
        if start is None:return dict(day=day,complete=False,reason='CALENDAR_SOURCE_ABSENT')
        keys=[]
        for minute in range(0,horizon+1,15 if replay else 60):
            keys.append(start+minute*60000)
            if minute<horizon:keys.append(start+minute*60000+30000)
        if replay:keys.insert(0,start-50000)
        missing=[t for t in keys if not support(s,t)]
        c=b['symbols'][s]['contract']
        entry=observed[s,start]['At'];exit_at=observed[s,start+horizon*60000]['At']
        # Include the actual stopping delay, not just the nominal bar interval.
        funding=False
        if entry is not None and exit_at is not None and c.get('swapPeriod')==24 and isinstance(c.get('swapTime'),int):
            day0=(entry//86400000)*86400000
            funding=b['accountSwapFreeEffective'] is False and not any(
                entry<=day0+d*86400000+c['swapTime']*60000<=exit_at for d in (0,1))
        current_min=D(b['symbols'][s]['currentMinMarginEur'])
        envelopes=[capacity(s,t) for t in keys]
        margin_complete=all(x is not None for x in envelopes)
        maximum_margin=max(envelopes) if margin_complete else None
        q=valued.get(s,{}).get(str(start),{}).get('Quotes',{}).get(s)
        cost=None
        if q is not None:
            units=D(c['minVolume'])/100
            commission=max(D(q['FeeLinearEurPerUnit'])*units,D(q['FeeFloorEur']))
            # A source capacity screen at one minimum lot, not modeled P/L.
            # Spread + 1x entry-spread hypothetical slippage on each side.
            cost=2*commission+3*(D(q['Ask'])-D(q['Bid']))*units*D(q['EurDebitPerQuote'])
        return dict(day=day,complete=(not missing and funding and margin_complete and cost is not None
                    and maximum_margin+cost<200),missingWindowCount=len(missing),
            windowCount=len(keys),fundingCondition=funding,
            currentMinimumMarginEur=str(current_min),currentMinMarginBelowInitial200=current_min<=200,
            historicalMarginCertified=False,actualFillOrDepthProven=False,
            minimumVolumeCurrentRuleMarginComplete=margin_complete,
            maximumMinimumVolumeMarginScenarioEur=str(maximum_margin) if maximum_margin is not None else None,
            minimumVolumeMarginScenarioBelowInitial200=maximum_margin is not None and maximum_margin<200,
            entryCurrentTariffFrictionAtMinimumVolumeEur=str(cost) if cost is not None else None)
    groups=[]
    for cohort in p['cohorts']:
        for horizon in p['commonHorizonMinutes']:
            for symbol in p['universe']:
                calibration=[path(symbol,d,horizon) for d in cohort['calibrationDays']]
                replay=[path(symbol,d,horizon,True) for d in cohort['replayDays']]
                groups.append(dict(cohort=cohort['id'],horizonMinutes=horizon,symbol=symbol,
                    calibration=calibration,replay=replay,
                    completeCalibrationEpisodes=sum(x['complete'] for x in calibration),
                    requiredCalibrationEpisodes=p['minimumCompleteCalibrationBlocks'],
                    allReplayPathsComplete=all(x['complete'] for x in replay)))
    # Coverage counts are unique route/horizon/cohort groups, not multiplied by
    # strategy families. No pseudo-replication into predictive sample size.
    usable=sum(g['completeCalibrationEpisodes']>=g['requiredCalibrationEpisodes'] and
               g['allReplayPathsComplete'] for g in groups)
    return dict(schema='mxm-causal-observation-feasibility-v1',id='CEF1',
        nativePythonEventParity=True,testedWindows=len(items),
        clockRule='FIRST_ATOMIC_VALID_EVENT_AFTER_LATENCY_WITHIN_FIXED_WINDOW_NO_PRICE_RANKING',
        routeWindowCounts={s:sum(name==s and r['At'] is not None for (name,_),r in zip(items,actual))
                           for s in p['universe']+['ALL']},
        uniqueEconomicSupportGroups=groups,completeGroups=usable,totalGroups=len(groups),
        sourceSupportDemonstratedOnExposedCalendarOnly=True,
        sourceAudit=b['auditReceipt'],newBrokerRequests=0,
        fullStudyAdmission=False,
        admissionBlockers=['NEW_PROTOCOL_FEATURE_LABEL_SAMPLE_AND_SPLIT_PLAN_NOT_YET_REGISTERED',
            'NEW_EPISODE_SOURCE_COVERAGE_NOT_YET_PILOTED',
            'JOINT_FLOATING_EQUITY_AND_TOTAL_MARGIN_NOT_PROVEN_BY_SINGLE_MINIMUM_VOLUME_SCREENS',
            'HISTORICAL_COSTS_DEPTH_STOP_OUT_AND_BETWEEN_MARK_RISK_UNCERTIFIED'],
        scoresComputed=False,allocationsComputed=False,epa2Replayed=False,
        sourceGapsRepaired=False,independentConfirmation=False,
        netEdgeDemonstrated=False,ordersSubmitted=0,cloudActivated=False)


def main():
    p=json.loads(Path('research/portfolio_holding_protocol.json').read_text())
    frozen=json.loads(Path('docs/EPA2_AUTHENTIC_HOLDING_RESULT.json').read_text())
    data=Path('sealed-output/source.envelope.json').read_bytes()
    need(hashlib.sha256(data).hexdigest()==frozen['sourceCiphertextSha256'],'CEF1_SOURCE_HASH')
    b=json.loads(unseal_new(data,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),str(frozen['sourceRunId'])))
    need(audit(b,p)==b['auditReceipt'],'CEF1_AUTHENTIC_RAW_READBACK')
    result=evaluate(b,p)
    result.update(executionRunId=int(os.environ['GITHUB_RUN_ID']),sourceRunId=frozen['sourceRunId'],
        sourceCiphertextSha256=frozen['sourceCiphertextSha256'])
    Path('observation-feasibility.public.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('CEF1_AUTHENTIC_FEASIBILITY '+json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        print('CEF1_FAILED_CLOSED_DETAILS_WITHHELD',flush=True)
        raise SystemExit(1)
