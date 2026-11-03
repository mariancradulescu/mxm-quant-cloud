"""Shared bounded economic source collection and encrypted raw readback.
EPA1 default semantics remain frozen; EPA2 adds route-local holding evidence.
Only predeclared economically used clocks are requested; no strategy selection.
"""
import base64, hashlib, json, os, sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path
from itertools import groupby
from .collect import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need, decode_side
from .economic_source import snapshot_contract
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .guard import require_read_only_request

PROTOCOL=Path('research/portfolio_economic_protocol.json')
SCHEMA='mxm-epa1-source-v1'


def protocol():return json.loads(PROTOCOL.read_text())
def protocol_file(p):return Path('research/portfolio_holding_protocol.json') if p['id']=='EPA2' else PROTOCOL
def day_clock(day,hour=9):return int(datetime.fromisoformat(day).replace(hour=hour,tzinfo=timezone.utc).timestamp()*1000)
def clocks(p,decision_clocks=None):
    result=[]
    for phase,step in [('calibrationDays',p['calibrationMarkStepMinutes']),('replayDays',p['replayMarkStepMinutes'])]:
        for day in p[phase]:
            start=decision_clocks[day] if decision_clocks is not None else day_clock(day)
            if start is None:continue
            if phase=='replayDays':result.append(start-p.get('preDecisionRequestSeconds',p['preDecisionQuoteSeconds'])*1000)
            result.extend(start+i*60000 for i in range(0,241,step))
    return sorted(set(result))


def synchronized_snapshot(sides,nominal,universe,max_age=2000):
    events=[]
    for s in universe:
        if any(sides[s][k] is None for k in (0,1)):return None
        for k in (0,1):events.extend((t,s,k,price) for t,price in sides[s][k])
    state={}
    for t,group in groupby(sorted(events,key=lambda x:x[0]),key=lambda x:x[0]):
        for stamp,s,k,price in group:state[s,k]=(stamp,price)
        if nominal+1000<=t<=nominal+11000 and len(state)==2*len(universe) and all(t-x[0]<=max_age for x in state.values()):
            if any(state[s,0][1]<=0 or state[s,1][1]<state[s,0][1] for s in universe):continue
            return dict(at=t,quotes={s:dict(bid=state[s,0][1],ask=state[s,1][1],bidAt=state[s,0][0],askAt=state[s,1][0]) for s in universe})
    return None


def partial_snapshot(sides,at,universe,max_age=2000):
    # Fixed as-of clock; no future tick can improve this snapshot. Missing
    # unrelated assets do not erase available price/FX routes.
    quotes={}
    for symbol in universe:
        state=[]
        for side in (0,1):
            rows=sides[symbol][side]
            prior=[r for r in rows or [] if r[0]<=at]
            state.append(prior[-1] if prior else None)
        if any(x is None or at-x[0]>max_age for x in state):continue
        bid,ask=state
        if bid[1]>0 and ask[1]>=bid[1]:quotes[symbol]=dict(bid=bid[1],ask=ask[1],bidAt=bid[0],askAt=ask[0])
    return dict(at=at,quotes=quotes)


def contract_snapshot(c):
    out=snapshot_contract(c)
    # These defaults are explicit in the official protobuf, not invented costs.
    for name in ['commissionType','minCommissionType','minCommissionAsset']:
        out[name]=getattr(c,name)
    out['effectiveProtobufDefaults']=[name for name in ['commissionType','minCommissionType','minCommissionAsset'] if not c.HasField(name)]
    return out


def audit(b,p=None):
    p=p or protocol();holding=p['id']=='EPA2';expected_schema='mxm-epa2-source-v1' if holding else SCHEMA
    need(b['schema']==expected_schema and b['readOnly'] is True and b['protocolSha256']==hashlib.sha256(protocol_file(p).read_bytes()).hexdigest(),'EPA1_PROTOCOL_BINDING')
    raw=b['raw'];need(len(raw)<=p['maxEvidenceRequests'],'EPA1_REQUEST_BUDGET')
    trader=m.ProtoOATraderRes();trader.ParseFromString(base64.b64decode(raw[0]['protobuf']))
    assets=m.ProtoOAAssetListRes();assets.ParseFromString(base64.b64decode(raw[1]['protobuf']))
    currencies={a.assetId:a.name for a in assets.asset};account=trader.ctidTraderAccountId
    listed=m.ProtoOASymbolsListRes();listed.ParseFromString(base64.b64decode(raw[2]['protobuf']))
    listed_by_name={x.symbolName:x for x in listed.symbol}
    need('pepperstone' in trader.trader.brokerName.lower() and currencies.get(trader.trader.depositAssetId)=='EUR' and b['depositCurrency']=='EUR','EPA1_BROKER_DEPOSIT_BINDING')
    need(b['accountSwapFreeEffective']==trader.trader.swapFree and b['accountSwapFreeExplicitInWire']==trader.trader.HasField('swapFree'),'EPA1_ACCOUNT_FUNDING_FLAG_BINDING')
    for item in raw:
        q=getattr(m,item['requestType'])();q.ParseFromString(base64.b64decode(item['requestProtobuf']));require_read_only_request(q)
        r=getattr(m,item['type'])();r.ParseFromString(base64.b64decode(item['protobuf']))
        need(r.IsInitialized() and r.ctidTraderAccountId==account and q.ctidTraderAccountId==account,'EPA1_RAW_ACCOUNT_BINDING')
    expected_keys=sorted(set(t+offset for t in clocks(p,b.get('decisionClocks')) for offset in ([0,30000] if holding else [0])))
    need(sorted(b['symbols'])==sorted(p['universe']) and sorted(map(int,b['snapshots']))==expected_keys,'EPA1_FIXED_GRID_UNIVERSE')
    if holding:
        need(b['riskTerms']==risk_terms(trader.trader),'EPA2_TRADER_RISK_TERMS_BINDING')
    for s,row in b['symbols'].items():
        light=listed_by_name[s]
        need(light.symbolId==row['symbolId'] and currencies.get(light.baseAssetId)==row['baseAsset'] and
             currencies.get(light.quoteAssetId)==row['quoteAsset'],'EPA1_RAW_ASSET_ROUTE_BINDING')
        r=m.ProtoOASymbolByIdRes();r.ParseFromString(base64.b64decode(raw[row['contractRawIndex']]['protobuf']))
        need(len(r.symbol)==1 and r.symbol[0].symbolId==row['symbolId'] and contract_snapshot(r.symbol[0])==row['contract'],'EPA1_RAW_CONTRACT_BINDING')
        req=m.ProtoOAExpectedMarginReq();req.ParseFromString(base64.b64decode(raw[row['marginRawIndex']]['requestProtobuf']))
        res=m.ProtoOAExpectedMarginRes();res.ParseFromString(base64.b64decode(raw[row['marginRawIndex']]['protobuf']))
        need(req.symbolId==row['symbolId'] and list(req.volume)==[row['contract']['minVolume']] and res.HasField('moneyDigits') and len(res.margin)==1 and res.margin[0].volume==req.volume[0],'EPA1_RAW_MARGIN_BINDING')
        margin=D(max(res.margin[0].buyMargin,res.margin[0].sellMargin))/D(10)**res.moneyDigits
        need(margin>0 and str(margin)==row['currentMinMarginEur'],'EPA1_MARGIN_RECONCILIATION')
        profile_req=m.ProtoOAExpectedMarginReq();profile_req.ParseFromString(base64.b64decode(raw[row['marginProfileRawIndex']]['requestProtobuf']))
        profile_res=m.ProtoOAExpectedMarginRes();profile_res.ParseFromString(base64.b64decode(raw[row['marginProfileRawIndex']]['protobuf']))
        need(profile_req.symbolId==row['symbolId'] and profile_res.HasField('moneyDigits') and
             set(x.volume for x in profile_res.margin)==set(profile_req.volume),'EPA1_MARGIN_PROFILE_BINDING')
        bound=max(D(max(x.buyMargin,x.sellMargin))/D(10)**profile_res.moneyDigits/(D(x.volume)/100) for x in profile_res.margin)
        bound=max(bound,margin/(D(row['contract']['minVolume'])/100))
        need(str(bound)==row['currentMarginPerUnitBoundEur'] and row['maxQueriedUnits']==max(profile_req.volume)//100,
             'EPA1_MARGIN_CURVE_BOUND_RECONCILIATION')
        if holding:
            lev=m.ProtoOAGetDynamicLeverageByIDRes();lev.ParseFromString(base64.b64decode(raw[row['dynamicLeverageRawIndex']]['protobuf']))
            need(lev.leverage.leverageId==row['contract']['leverageId'] and row['dynamicLeverage']==
                 [dict(volume=x.volume,leverage=x.leverage) for x in lev.leverage.tiers],'EPA2_LEVERAGE_RAW_BINDING')
    if holding:
        need(sorted(b['decisionClocks'])==sorted(set(p['calibrationDays']+p['replayDays'])),'EPA2_CALENDAR_COVERAGE')
        need(sorted(b['calendarRawIndices'])==sorted(b['decisionClocks']),'EPA2_CALENDAR_RAW_COVERAGE')
        for day,ix in b['calendarRawIndices'].items():
            q=m.ProtoOAGetTrendbarsReq();q.ParseFromString(base64.b64decode(raw[ix]['requestProtobuf']))
            r=m.ProtoOAGetTrendbarsRes();r.ParseFromString(base64.b64decode(raw[ix]['protobuf']))
            midnight=day_clock(day,0)
            need(q.symbolId==b['symbols']['EURUSD']['symbolId'] and q.period==e.H4 and q.fromTimestamp==midnight and q.toTimestamp==midnight+13*3600000 and r.HasField('hasMore') and not r.hasMore and r.period==e.H4,'EPA2_CALENDAR_REQUEST_BINDING')
            possible=[x.utcTimestampInMinutes*60000+14400000 for x in r.trendbar if x.HasField('utcTimestampInMinutes')]
            possible=[t for t in possible if midnight+9*3600000<=t<=midnight+13*3600000]
            need(b['decisionClocks'][day]==(min(possible) if possible else None),'EPA2_PRICE_INDEPENDENT_CLOCK_BINDING')
    for t in clocks(p,b.get('decisionClocks')):
        sides={}
        for s in p['universe']:
            sides[s]=[];row=b['symbols'][s]
            for side,i in zip((e.BID,e.ASK),b['eventIndices'][str(t)][s]):
                req=m.ProtoOAGetTickDataReq();req.ParseFromString(base64.b64decode(raw[i]['requestProtobuf']))
                res=m.ProtoOAGetTickDataRes();res.ParseFromString(base64.b64decode(raw[i]['protobuf']))
                need(req.symbolId==row['symbolId'] and req.type==side and req.fromTimestamp==t+1000 and req.toTimestamp==t+1000+p['quoteSearchMs'] and res.HasField('hasMore'),'EPA1_EVENT_REQUEST_BINDING')
                sides[s].append(None if res.hasMore else decode_side(res.tickData,t+1000,t+1000+p['quoteSearchMs']))
        if holding:
            for offset in [0,30000]:
                need(partial_snapshot(sides,t+offset+11000,p['universe'],p['maximumSideAgeMs'])==b['snapshots'][str(t+offset)],'EPA2_RAW_PARTIAL_ASOF_RECONCILIATION')
        else:need(synchronized_snapshot(sides,t,p['universe'],p['maximumSideAgeMs'])==b['snapshots'][str(t)],'EPA1_RAW_SNAPSHOT_RECONCILIATION')
    if holding:return dict(evidenceRequests=len(raw),requestWindows=len(clocks(p,b['decisionClocks'])),requestedSnapshots=len(expected_keys),fullUniverseSnapshots=sum(len(x['quotes'])==len(p['universe']) for x in b['snapshots'].values()),partialOrFullSnapshots=sum(bool(x['quotes']) for x in b['snapshots'].values()),protocolSha256=b['protocolSha256'])
    return dict(evidenceRequests=len(raw),requestedSnapshots=len(clocks(p)),completeSnapshots=sum(x is not None for x in b['snapshots'].values()),protocolSha256=b['protocolSha256'])


def risk_terms(trader):
    return {k:(getattr(trader,k) if trader.HasField(k) else None) for k in
            ['leverageInCents','totalMarginCalculationType','fairStopOut','stopOutStrategy','accountType']}


def collect(p=None):
    p=p or protocol();holding=p['id']=='EPA2'
    run=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run)
    raw=[];transport=StdlibCTraderTransport()
    def req(q,kind):
        need(len(raw)<p['maxEvidenceRequests'],'EPA1_REQUEST_BUDGET')
        r=transport.request(q);need(isinstance(r,kind) and r.IsInitialized() and r.ctidTraderAccountId==account,'EPA1_RESPONSE_BINDING')
        raw.append(dict(type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode(),requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode()))
        return r,len(raw)-1
    try:
        account=authenticate(transport)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)[0].trader
        assets={a.assetId:a.name for a in req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)[0].asset}
        need(trader.HasField('brokerName') and 'pepperstone' in trader.brokerName.lower() and assets.get(trader.depositAssetId)=='EUR','EPA1_PEPPERSTONE_EUR')
        symbols={s.symbolName:s for s in req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)[0].symbol if s.enabled}
        b=dict(schema='mxm-epa2-source-v1' if holding else SCHEMA,source='Pepperstone-cTrader-OpenAPI',readOnly=True,depositCurrency='EUR',accountSwapFreeEffective=trader.swapFree,accountSwapFreeExplicitInWire=trader.HasField('swapFree'),protocolSha256=hashlib.sha256(protocol_file(p).read_bytes()).hexdigest(),symbols={},snapshots={},eventIndices={},raw=raw)
        need(all(s in symbols for s in p['universe']),'EPA1_UNIVERSE_INCOMPLETE')
        for name in p['universe']:
            s=symbols[name];detail,di=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[s.symbolId]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==s.symbolId,'EPA1_SYMBOL_DETAIL')
            c=detail.symbol[0];need(c.HasField('minVolume'),'EPA1_BROKER_MINIMUM_MISSING')
            margin,mi=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=s.symbolId,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
            need(margin.HasField('moneyDigits') and len(margin.margin)==1 and margin.margin[0].volume==c.minVolume,'EPA1_MARGIN_FIELDS')
            min_margin=D(max(margin.margin[0].buyMargin,margin.margin[0].sellMargin))/D(10)**margin.moneyDigits
            need(min_margin>0 and c.HasField('stepVolume') and c.stepVolume>0 and c.HasField('maxVolume'),'EPA1_VOLUME_GRID_FIELDS')
            count=min(p['maxVolumeQueryPoints'],max(1,int(D(p['volumeQueryMarginReferenceEur'])/min_margin))+p['extraVolumeStepsForReinvestment'])
            volumes=[c.minVolume+i*c.stepVolume for i in range(count) if c.minVolume+i*c.stepVolume<=c.maxVolume]
            profile,pi=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=s.symbolId,volume=volumes),m.ProtoOAExpectedMarginRes)
            need(profile.HasField('moneyDigits') and set(x.volume for x in profile.margin)==set(volumes),'EPA1_CURRENT_MARGIN_GRID')
            bound=max(D(max(x.buyMargin,x.sellMargin))/D(10)**profile.moneyDigits/(D(x.volume)/100) for x in profile.margin)
            bound=max(bound,min_margin/(D(c.minVolume)/100))
            b['symbols'][name]=dict(symbolId=s.symbolId,baseAsset=assets[s.baseAssetId],quoteAsset=assets[s.quoteAssetId],contractRawIndex=di,marginRawIndex=mi,marginProfileRawIndex=pi,
                contract=contract_snapshot(c),currentMinMarginEur=str(min_margin),currentMarginPerUnitBoundEur=str(bound),maxQueriedUnits=max(volumes)//100)
        if holding:
            b['riskTerms']=risk_terms(trader)
            need(trader.HasField('leverageInCents') and trader.leverageInCents>0,'EPA2_ACCOUNT_LEVERAGE_REQUIRED')
            cached={}
            for name in p['universe']:
                row=b['symbols'][name];lid=row['contract']['leverageId'];need(lid is not None,'EPA2_LEVERAGE_ID_REQUIRED')
                if lid not in cached:
                    lev,li=req(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=account,leverageId=lid),m.ProtoOAGetDynamicLeverageByIDRes)
                    need(lev.leverage.leverageId==lid and len(lev.leverage.tiers)>0,'EPA2_LEVERAGE_PROFILE_REQUIRED')
                    cached[lid]=(li,[dict(volume=x.volume,leverage=x.leverage) for x in lev.leverage.tiers])
                row['dynamicLeverageRawIndex'],row['dynamicLeverage']=cached[lid]
        if holding:
            b['decisionClocks']={};b['calendarRawIndices']={}
            for day in sorted(set(p['calibrationDays']+p['replayDays'])):
                midnight=day_clock(day,0)
                response,ix=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=symbols['EURUSD'].symbolId,period=e.H4,fromTimestamp=midnight,toTimestamp=midnight+13*3600000),m.ProtoOAGetTrendbarsRes)
                need(response.HasField('hasMore') and not response.hasMore and response.period==e.H4,'EPA2_CALENDAR_PAGE_COMPLETE')
                possible=[x.utcTimestampInMinutes*60000+14400000 for x in response.trendbar if x.HasField('utcTimestampInMinutes')]
                possible=[t for t in possible if midnight+9*3600000<=t<=midnight+13*3600000]
                b['decisionClocks'][day]=min(possible) if possible else None;b['calendarRawIndices'][day]=ix
        request_clocks=clocks(p,b.get('decisionClocks'))
        for index,t in enumerate(request_clocks):
            sides={};indices={}
            for name in p['universe']:
                sides[name]=[];indices[name]=[]
                for side in (e.BID,e.ASK):
                    r,i=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=symbols[name].symbolId,type=side,fromTimestamp=t+1000,toTimestamp=t+1000+p['quoteSearchMs']),m.ProtoOAGetTickDataRes)
                    need(r.HasField('hasMore'),'EPA1_TICK_PAGE_DECLARATION');indices[name].append(i)
                    sides[name].append(None if r.hasMore else decode_side(r.tickData,t+1000,t+1000+p['quoteSearchMs']))
            if holding:
                for offset in [0,30000]:b['snapshots'][str(t+offset)]=partial_snapshot(sides,t+offset+11000,p['universe'],p['maximumSideAgeMs'])
            else:b['snapshots'][str(t)]=synchronized_snapshot(sides,t,p['universe'],p['maximumSideAgeMs'])
            b['eventIndices'][str(t)]=indices
            if index%15==0:print(p['id']+'_FIXED_ECONOMIC_GRID_PROGRESS '+str(index)+'/'+str(len(request_clocks)),flush=True)
        b['auditReceipt']=audit(b,p)
        cipher=seal_new(json.dumps(b,sort_keys=True).encode(),recipient,run)
        dest=Path('sealed-output');dest.mkdir(exist_ok=True)
        (dest/'source.envelope.json').write_bytes(cipher)
        (dest/'receipt.public.json').write_text(json.dumps(dict(schema=b['schema'],runId=run,sha256=hashlib.sha256(cipher).hexdigest(),protocolSha256=b['protocolSha256'],ordersSubmitted=0)))
        print(p['id']+'_AUTHENTIC_ECONOMIC_SOURCE_SEALED '+json.dumps(b['auditReceipt'],sort_keys=True),flush=True)
    finally:transport.close()


def readback():
    p=protocol();run=os.environ['GITHUB_RUN_ID'];key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    raw=Path('sealed-output/source.envelope.json').read_bytes();pub=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(pub['runId']==run and pub['schema']==SCHEMA and pub['sha256']==hashlib.sha256(raw).hexdigest(),'EPA1_CUSTODY_HASH')
    b=json.loads(unseal_new(raw,key,run));need(audit(b)==b['auditReceipt'],'EPA1_INDEPENDENT_RAW_READBACK')
    old=Path('baseline-source/source.envelope.json').read_bytes();need(hashlib.sha256(old).hexdigest()==p['sourceSha256'],'EPA1_ORIGINAL_H4_SOURCE_HASH')
    original=json.loads(unseal_new(old,key,str(p['sourceRunId'])))
    print('EPA1_INDEPENDENT_RAW_CUSTODY_VERIFIED',flush=True)
    from .portfolio_economic_replay import evaluate
    result=evaluate(b,original)
    result.update(sourceRunId=int(run),sourceCiphertextSha256=pub['sha256'],originalSourceCiphertextSha256=p['sourceSha256'],independentRawCustodyReadbackMatched=True,sourceAudit=b['auditReceipt'])
    Path('portfolio-economic.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    print('AUTHENTIC_PORTFOLIO_ECONOMIC_RESULT '+json.dumps(result,sort_keys=True,default=str),flush=True)


if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception:
        print('EPA1_FAILED_CLOSED_DETAILS_WITHHELD',flush=True);raise SystemExit(1)
