"""SQP1 bounded source, pilot-before-expansion and protected independent readback."""
import base64,hashlib,json,os,sys
from pathlib import Path
from decimal import Decimal as D
from .collect import authenticate,HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .decode import need,decode_bars,decode_side
from .custody import seal_new,unseal_new
from .custody_new import checked_public
from .guard import require_read_only_request
from .portfolio_economic_source import contract_snapshot,risk_terms,day_clock

PROTOCOL=Path('research/sequence_portfolio_protocol.json')
SCHEMA='mxm-sqp1-source-v1'


def protocol():return json.loads(PROTOCOL.read_text())
def clock(p,day):return day_clock(day,p['nominalHourUtc'])
def bar_range(tf,at):return at-(7 if tf=='M15' else 14)*86400000,at
def bar_rows(response,lo,hi,minutes):
    if not response.HasField('hasMore') or response.hasMore:return []
    rows=decode_bars(response.trendbar,lo-minutes*60000,hi+minutes*60000,minutes)
    return [r for r in rows if lo<=r[0] and r[1]<=hi]


def window_events(b,nominal,p):
    events=[];complete={}
    for s,indices in b['eventIndices'][str(nominal)].items():
        complete[s]=True
        for side,ix in enumerate(indices):
            r=m.ProtoOAGetTickDataRes();r.ParseFromString(base64.b64decode(b['raw'][ix]['protobuf']))
            complete[s] &= r.HasField('hasMore') and not r.hasMore
            if r.HasField('hasMore') and not r.hasMore:
                events.extend(dict(At=t,Symbol=s,Side=side,Price=px) for t,px in
                    decode_side(r.tickData,nominal+p['requestFromOffsetMs'],nominal+p['requestToOffsetMs']))
    return events,complete


def audit(b,p):
    need(b['schema']==SCHEMA and b['readOnly'] is True and b['depositCurrency']=='EUR' and
         b['protocolSha256']==hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),'SQP1_PROTOCOL')
    raw=b['raw'];need(len(raw)<=p['maxEvidenceRequests'],'SQP1_BUDGET')
    decoded=[]
    for row in raw:
        q=getattr(m,row['requestType'])();q.ParseFromString(base64.b64decode(row['requestProtobuf']));require_read_only_request(q)
        r=getattr(m,row['type'])();r.ParseFromString(base64.b64decode(row['protobuf']))
        need(r.IsInitialized() and r.ctidTraderAccountId==q.ctidTraderAccountId,'SQP1_ACCOUNT_RESPONSE')
        decoded.append((q,r))
    trader=decoded[0][1].trader;account=decoded[0][1].ctidTraderAccountId
    need(all(q.ctidTraderAccountId==account for q,r in decoded),'SQP1_SINGLE_ACCOUNT')
    fingerprint=hashlib.sha256(f'ctrader-account:{int(account)}'.encode('ascii')).hexdigest()
    need(hashlib.sha256(fingerprint.encode('ascii')).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT,'SQP1_ORIGINAL_ACCOUNT_COMMITMENT')
    assets={a.assetId:a.name for a in decoded[1][1].asset}
    listing={s.symbolName:s for s in decoded[2][1].symbol}
    need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR' and
         b['accountSwapFreeEffective']==trader.swapFree and b['accountSwapFreeExplicitInWire']==trader.HasField('swapFree') and b['riskTerms']==risk_terms(trader),'SQP1_BROKER_TERMS')
    need(sorted(b['symbols'])==sorted(p['universe']),'SQP1_UNIVERSE')
    for s,row in b['symbols'].items():
        light=listing[s];q,r=decoded[row['contractRawIndex']]
        need(row['symbolId']==light.symbolId and assets[light.baseAssetId]==row['baseAsset'] and
             assets[light.quoteAssetId]==row['quoteAsset'] and list(q.symbolId)==[light.symbolId] and
             len(r.symbol)==1 and contract_snapshot(r.symbol[0])==row['contract'],'SQP1_CONTRACT')
        q,r=decoded[row['marginProfileRawIndex']];c=row['contract']
        volumes=[c['minVolume']+i*c['stepVolume'] for i in range(p['volumeQueryPoints']) if c['minVolume']+i*c['stepVolume']<=c['maxVolume']]
        need(q.symbolId==light.symbolId and list(q.volume)==volumes and r.HasField('moneyDigits') and
             sorted(x.volume for x in r.margin)==volumes,'SQP1_MARGIN_GRID')
        bounds=[D(max(x.buyMargin,x.sellMargin))/D(10)**r.moneyDigits/(D(x.volume)/100) for x in r.margin]
        minimum=max(x.buyMargin for x in r.margin if x.volume==volumes[0])
        minimum=max(minimum,max(x.sellMargin for x in r.margin if x.volume==volumes[0]))
        need(D(row['currentMarginPerUnitBoundEur'])==max(bounds) and row['maxQueriedUnits']==max(volumes)//100 and
             D(row['currentMinMarginEur'])==D(minimum)/D(10)**r.moneyDigits,'SQP1_MARGIN_RECONCILIATION')
        q,r=decoded[row['dynamicLeverageRawIndex']]
        need(q.leverageId==c['leverageId'] and r.leverage.leverageId==c['leverageId'] and
             row['dynamicLeverage']==[dict(volume=x.volume,leverage=x.leverage) for x in r.leverage.tiers],'SQP1_LEVERAGE')
    expected_days=(p['calibrationDays']+p['replayDays']) if b['pilotPassed'] else p['calibrationDays'][:p['pilotDays']]
    need(b['completedDays']==expected_days,'SQP1_CALENDAR_NO_REPLACEMENT')
    blocks=[];expected_ticks=[]
    for day in expected_days:
        at=clock(p,day)
        for s in p['universe']:
            for tf,minutes in p['timeframes'].items():
                ix=b['featureIndices'][day][s][tf];q,r=decoded[ix];lo,hi=bar_range(tf,at)
                need(q.symbolId==b['symbols'][s]['symbolId'] and q.period==getattr(e,tf) and
                     q.fromTimestamp==lo and q.toTimestamp==hi and r.period==getattr(e,tf),'SQP1_BAR_REQUEST')
                blocks.append(dict(Day=day,Symbol=s,Timeframe=tf,Clock=at,Bars=bar_rows(r,lo,hi,minutes)))
        for minute in range(0,p['horizonMinutes']+1,p['markStepMinutes']):
            t=at+minute*60000;expected_ticks.append(str(t))
            for s,indices in b['eventIndices'][str(t)].items():
                need(len(indices)==2,'SQP1_SIDES')
                for side,ix in zip((e.BID,e.ASK),indices):
                    q,r=decoded[ix]
                    need(q.symbolId==b['symbols'][s]['symbolId'] and q.type==side and
                         q.fromTimestamp==t+p['requestFromOffsetMs'] and q.toTimestamp==t+p['requestToOffsetMs'] and
                         r.HasField('hasMore'),'SQP1_EVENT_WINDOW')
    need(blocks==b['featureBlocks'] and sorted(expected_ticks)==sorted(b['eventIndices']) and
         all(sorted(v)==sorted(p['universe']) for v in b['eventIndices'].values()),'SQP1_INDEPENDENT_RAW_RECONSTRUCTION')
    return dict(originalAccountBindingRechecked=True,evidenceRequests=len(raw),completedDays=len(expected_days),featureBlocks=len(blocks),
                requestWindows=len(expected_ticks),pilotPassed=b['pilotPassed'],protocolSha256=b['protocolSha256'])


def collect():
    p=protocol();need(not Path('docs/SQP1_AUTHENTIC_RESULT.json').exists(),'SQP1_CLOSED')
    run=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run)
    raw=[];transport=StdlibCTraderTransport()
    def req(q,kind):
        need(len(raw)<p['maxEvidenceRequests'],'SQP1_BUDGET');require_read_only_request(q)
        r=transport.request(q);need(isinstance(r,kind) and r.IsInitialized() and r.ctidTraderAccountId==account,'SQP1_RESPONSE')
        raw.append(dict(requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode(),
            type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode()))
        return r,len(raw)-1
    try:
        account=authenticate(transport)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)[0].trader
        assets={a.assetId:a.name for a in req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)[0].asset}
        need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR','SQP1_PEPPERSTONE_EUR')
        listing={s.symbolName:s for s in req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)[0].symbol if s.enabled}
        b=dict(schema=SCHEMA,readOnly=True,depositCurrency='EUR',accountSwapFreeEffective=trader.swapFree,
            accountSwapFreeExplicitInWire=trader.HasField('swapFree'),riskTerms=risk_terms(trader),protocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
            symbols={},featureBlocks=[],featureIndices={},eventIndices={},completedDays=[],pilotPassed=False,raw=raw)
        for s in p['universe']:
            light=listing[s];detail,di=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[light.symbolId]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1,'SQP1_CONTRACT_COUNT');c=detail.symbol[0];contract=contract_snapshot(c)
            need(all(contract[k] is not None and contract[k]>0 for k in ('minVolume','stepVolume','maxVolume')) and
                 c.minVolume%100==0 and c.stepVolume%100==0,'SQP1_VOLUME_ENCODING')
            volumes=[c.minVolume+i*c.stepVolume for i in range(p['volumeQueryPoints']) if c.minVolume+i*c.stepVolume<=c.maxVolume]
            margin,mi=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=light.symbolId,volume=volumes),m.ProtoOAExpectedMarginRes)
            need(margin.HasField('moneyDigits') and sorted(x.volume for x in margin.margin)==volumes,'SQP1_MARGIN_FIELDS')
            leverage,li=req(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=account,leverageId=c.leverageId),m.ProtoOAGetDynamicLeverageByIDRes)
            amounts={x.volume:D(max(x.buyMargin,x.sellMargin))/D(10)**margin.moneyDigits for x in margin.margin}
            b['symbols'][s]=dict(symbolId=light.symbolId,baseAsset=assets[light.baseAssetId],quoteAsset=assets[light.quoteAssetId],
                contract=contract,contractRawIndex=di,marginProfileRawIndex=mi,dynamicLeverageRawIndex=li,
                dynamicLeverage=[dict(volume=x.volume,leverage=x.leverage) for x in leverage.leverage.tiers],
                currentMinMarginEur=str(amounts[c.minVolume]),currentMarginPerUnitBoundEur=str(max(v/(D(k)/100) for k,v in amounts.items())),maxQueriedUnits=max(volumes)//100)
        days=p['calibrationDays']+p['replayDays']
        for n,day in enumerate(days):
            at=clock(p,day);b['featureIndices'][day]={}
            for s in p['universe']:
                b['featureIndices'][day][s]={}
                for tf,minutes in p['timeframes'].items():
                    lo,hi=bar_range(tf,at)
                    r,ix=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=b['symbols'][s]['symbolId'],period=getattr(e,tf),fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
                    b['featureIndices'][day][s][tf]=ix
                    b['featureBlocks'].append(dict(Day=day,Symbol=s,Timeframe=tf,Clock=at,Bars=bar_rows(r,lo,hi,minutes)))
            for minute in range(0,p['horizonMinutes']+1,p['markStepMinutes']):
                t=at+minute*60000;b['eventIndices'][str(t)]={}
                for s in p['universe']:
                    indices=[]
                    for side in (e.BID,e.ASK):
                        r,ix=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=b['symbols'][s]['symbolId'],type=side,
                            fromTimestamp=t+p['requestFromOffsetMs'],toTimestamp=t+p['requestToOffsetMs']),m.ProtoOAGetTickDataRes)
                        need(r.HasField('hasMore'),'SQP1_PAGINATION_FIELD');indices.append(ix)
                    b['eventIndices'][str(t)][s]=indices
            b['completedDays'].append(day)
            print('SQP1_SOURCE_DAY '+str(n+1)+'/'+str(len(days)),flush=True)
            if n+1==p['pilotDays']:
                from .sequence_portfolio_replay import preflight
                support=preflight(b,p);b['pilotSupport']=support;b['pilotPassed']=support['passed']
                print('SQP1_PREVENTIVE_SUPPORT '+json.dumps(support,sort_keys=True),flush=True)
                if not b['pilotPassed']:break
        b['auditReceipt']=audit(b,p)
        cipher=seal_new(json.dumps(b,sort_keys=True).encode(),recipient,run);dest=Path('sealed-output');dest.mkdir(exist_ok=True)
        (dest/'source.envelope.json').write_bytes(cipher)
        (dest/'receipt.public.json').write_text(json.dumps(dict(schema=SCHEMA,runId=run,sha256=hashlib.sha256(cipher).hexdigest(),protocolSha256=b['protocolSha256'],ordersSubmitted=0)))
        print('SQP1_SOURCE_SEALED '+json.dumps(b['auditReceipt'],sort_keys=True),flush=True)
    finally:transport.close()


def readback():
    p=protocol();need(not Path('docs/SQP1_AUTHENTIC_RESULT.json').exists(),'SQP1_CLOSED')
    run=os.environ['GITHUB_RUN_ID'];data=Path('sealed-output/source.envelope.json').read_bytes()
    public=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(public['schema']==SCHEMA and public['runId']==run and public['sha256']==hashlib.sha256(data).hexdigest(),'SQP1_CUSTODY')
    b=json.loads(unseal_new(data,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run))
    need(audit(b,p)==b['auditReceipt'],'SQP1_RAW_READBACK')
    from .sequence_portfolio_replay import evaluate,preflight
    need(preflight(b,p,p['pilotDays'])==b['pilotSupport'],'SQP1_PILOT_RECONCILIATION')
    result=evaluate(b,p)
    result.update(sourceRunId=int(run),sourceCiphertextSha256=public['sha256'],rawReadbackMatched=True,sourceAudit=b['auditReceipt'],accountSwapFreeEffective=b['accountSwapFreeEffective'],
        accountSwapFreeExplicitInWire=b['accountSwapFreeExplicitInWire'],historicalFinancingVerified=False,
        financingAssumption='CURRENT_EFFECTIVE_PROTOBUF_NORMAL_ACCOUNT_AND_CURRENT_DAILY_SWAP_OUTSIDE_HOLDING;HISTORICAL_TERMS_UNVERIFIED')
    Path('sequence-portfolio.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    print('SQP1_AUTHENTIC_ECONOMIC_RESULT '+json.dumps(result,sort_keys=True,default=str),flush=True)


if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception as error:
        import traceback
        print('SQP1_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True)
        raise SystemExit(1)
