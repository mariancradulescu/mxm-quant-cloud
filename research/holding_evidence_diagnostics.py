"""Broker-free diagnosis of frozen EPA2 evidence gates; no policy or cash rerun."""
import hashlib,json,os,copy
from pathlib import Path
from decimal import Decimal as D
from .custody import unseal_new
from .decode import need
from .portfolio_economic_source import audit
from .decode import decode_side
from .ctrader_proto import OpenApiMessages_pb2 as m
import base64
from itertools import groupby
from .portfolio_economic_replay import native,valued_quote
from .portfolio_holding_replay import calibration,episode_funding,pre_margin_bounds,study_clock,audit_epa1


def route_window_availability(b,p):
    """Availability-only causal stopping times; NEVER replacement EPA2 fills."""
    result={}
    for key,indices in b['eventIndices'].items():
        nominal=int(key);events=[]
        for symbol,rows in indices.items():
            for side,ix in enumerate(rows):
                response=m.ProtoOAGetTickDataRes();response.ParseFromString(base64.b64decode(b['raw'][ix]['protobuf']))
                if not response.hasMore:
                    events.extend((t,symbol,side,price) for t,price in decode_side(response.tickData,nominal+1000,nominal+41000))
        state={};found={0:{},30000:{}}
        for at,group in groupby(sorted(events,key=lambda x:x[0]),key=lambda x:x[0]):
            for t,symbol,side,price in group:state[symbol,side]=(t,price)
            for offset in (0,30000):
                if not nominal+offset+1000<=at<=nominal+offset+11000:continue
                for symbol in p['universe']:
                    if symbol in found[offset]:continue
                    route={symbol,'EURUSD'};quote=b['symbols'][symbol]['quoteAsset']
                    if quote=='JPY':route.add('USDJPY')
                    if quote=='CAD':route.add('USDCAD')
                    if all((x,k) in state and 0<=at-state[x,k][0]<=p['maximumSideAgeMs'] for x in route for k in (0,1)) and all(state[x,0][1]>0 and state[x,1][1]>=state[x,0][1] for x in route):found[offset][symbol]=at
        for offset in (0,30000):result[str(nominal+offset)]=found[offset]
    return result


def evaluate(b,original,p):
    valued=native({k:v for k,v in b.items() if k not in ['raw','eventIndices','auditReceipt']},'--value-portfolio-source')['Snapshots']
    base={k:v for k,v in original.items() if k not in ['raw','traderRaw','csharpReceipt']}
    plan={(x['Candidate'],x['Symbol'],x['Clock']):x for x in native(base,'--economic-portfolio-plan')}
    bounds=pre_margin_bounds(b,valued,p)
    feasible=route_window_availability(b,p)
    rows=[]
    for cohort in p['cohorts']:
        for horizon in p['commonHorizonMinutes']:
            for candidate in p['families']:
                for symbol in p['universe']:
                    days=[]
                    for day in cohort['calibrationDays']:
                        clock=study_clock(b,day);keys=[]
                        if clock is not None:
                            for minute in range(0,horizon+1,60):
                                keys.append(str(clock+minute*60000))
                                if minute<horizon:keys.append(str(clock+minute*60000+30000))
                        missing=[dict(nominal=int(t),rawSymbolPresent=symbol in b['snapshots'][t]['quotes'],rawEurUsdPresent='EURUSD' in b['snapshots'][t]['quotes'],valuationReason=valued[t]['Missing'].get(symbol)) for t in keys if valued_quote(valued[t],symbol) is None]
                        available=clock is not None and (candidate,symbol,clock) in plan
                        valid=clock is not None and calibration(plan,day,symbol,candidate,valued,horizon,D(1),clock) is not None
                        days.append(dict(day=day,proposalAvailable=available,missingValuationAsOf=missing,completeCalibrationPath=valid,availabilityOnlyAllRequiredWindowsHaveSomeCausalRoute=(available and all(symbol in feasible.get(t,{}) for t in keys)),
                            fundingCondition=clock is not None and episode_funding(b['symbols'][symbol]['contract'],clock,horizon)))
                    replay=[]
                    for day in cohort['replayDays']:
                        clock=study_clock(b,day);pre=valued.get(str(clock-20000)) if clock is not None else None
                        replay.append(dict(day=day,proposalAvailable=clock is not None and (candidate,symbol,clock) in plan,
                            predecisionValuationAvailable=valued_quote(pre,symbol) is not None,marginBoundAvailable=(day,symbol) in bounds,
                            fundingCondition=clock is not None and episode_funding(b['symbols'][symbol]['contract'],clock,horizon)))
                    rows.append(dict(cohort=cohort['id'],horizon=horizon,candidate=candidate,symbol=symbol,
                        completeCalibrationBlocks=sum(d['completeCalibrationPath'] for d in days),requiredBlocks=p['minimumCompleteCalibrationBlocks'],calibration=days,replay=replay))
    coverage={s:dict(rawSnapshots=sum(s in x['quotes'] for x in b['snapshots'].values()),valuedSnapshots=sum(s in x['Quotes'] for x in valued.values())) for s in p['universe']}
    return dict(schema='mxm-epa2-frozen-evidence-gate-diagnosis-v1',sourceRunId=41648280262,protocolSha256=b['protocolSha256'],
        rawReadbackMatched=True,sourceAudit=b['auditReceipt'],routeCoverage=coverage,evidenceGates=rows,preMarginBoundCount=len(bounds),
        availabilityOnlyWindowRouteCounts={s:sum(s in x for x in feasible.values()) for s in p['universe']},
        availabilityComparisonNotUsedForAllocationOrGapRepair=True,accountSwapFreeEffective=b['accountSwapFreeEffective'],fundingTerms={s:{k:b['symbols'][s]['contract'].get(k) for k in ['swapPeriod','swapTime']} for s in p['universe']},
        allocationOrPolicyRerun=False,sourceGapsFilled=False,parametersRetuned=False,independentConfirmation=False,
        qualification=False,ordersSubmitted=0,cloudActivated=False)


def readback():
    p=json.loads(Path('research/portfolio_holding_protocol.json').read_text())
    frozen=json.loads(Path('docs/EPA2_AUTHENTIC_HOLDING_RESULT.json').read_text());run=str(frozen['sourceRunId'])
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    def read(path,sha,source_run):
        data=Path(path).read_bytes();need(hashlib.sha256(data).hexdigest()==sha,'EPA2_DIAG_SOURCE_HASH');return json.loads(unseal_new(data,key,str(source_run)))
    b=read('sealed-output/source.envelope.json',frozen['sourceCiphertextSha256'],run)
    need(audit(b,p)==b['auditReceipt'],'EPA2_DIAG_RAW_AUDIT')
    original=read('baseline-source/source.envelope.json',p['sourceSha256'],p['sourceRunId'])
    old=read('epa1-source/source.envelope.json',p['oldEpa1SourceSha256'],p['oldEpa1Run'])
    result=evaluate(b,original,p)
    normalized=copy.deepcopy(b)
    for row in normalized['symbols'].values():
        for tier in row['dynamicLeverage']:tier['leverage']=float(D(tier['leverage'])/100)
    result['conservativeHundredthsTierSensitivity']=dict(rawTiers={s:r['dynamicLeverage'] for s,r in b['symbols'].items()},
        interpretation='OBSERVED_2000_3000_AS20_30_CONSERVATIVE_MARGIN_SENSITIVITY_NOT_HISTORICAL_MARGIN_CERTIFICATION',
        fixedOriginalEpa1BookAudit=audit_epa1(old,normalized),originalEpa2BookReallocated=False)
    result['executionRunId']=int(os.environ['GITHUB_RUN_ID'])
    result['sourceCiphertextSha256']=frozen['sourceCiphertextSha256']
    Path('holding-diagnostics.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    print('EPA2_EXECUTION_DIAGNOSTICS '+json.dumps(result,sort_keys=True,default=str),flush=True)


if __name__=='__main__':
    try:readback()
    except Exception as error:
        import traceback
        print('EPA2_DIAG_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True)
        raise SystemExit(1)
