"""AIP1 source pilot and pooled cash-opening research; no closed-study replay."""
import base64,hashlib,json,os,sys,time
from pathlib import Path
from decimal import Decimal as D
from .collect import authenticate,HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import need
from .custody import seal_new,unseal_new
from .custody_new import checked_public
from .portfolio_economic_source import contract_snapshot
from .portfolio_discovery_source import bars,cost_contexts
from .portfolio_economic_replay import native

P=Path('research/auction_inventory_protocol.json');SCHEMA='mxm-aip1-source-v1'
def digest(x):return hashlib.sha256(x).hexdigest()
def normalized_input(b,p):
    return dict(Bars=[dict(Symbol=s,Start=x[0],End=x[1],Open=x[2],High=x[3],Low=x[4],Close=x[5],Volume=x[6]) for s,rows in b['bars'].items() for x in rows],
        Costs=[c for c in b.get('costContexts',[]) if c['RoundTripBps'] is not None and c['MinimumNotionalEur'] is not None],Sessions=b['sessionSpecs'],Start=p['start'],DevelopmentEnd=p['developmentEnd'],SelectionEnd=p['selectionEnd'],End=p['end'])

def audit(b,p):
    need(b['schema']==SCHEMA and b['readOnly'] and b['protocolSha256']==digest(P.read_bytes()),'AIP1_PROTOCOL')
    decoded=[]
    for row in b['raw']:
        q=getattr(m,row['requestType'])();q.ParseFromString(base64.b64decode(row['requestProtobuf']));require_read_only_request(q)
        r=getattr(m,row['type'])();r.ParseFromString(base64.b64decode(row['protobuf']));need(r.IsInitialized() and r.ctidTraderAccountId==q.ctidTraderAccountId,'AIP1_RESPONSE');decoded.append((q,r))
    account=decoded[0][1].ctidTraderAccountId
    fp=digest(f'ctrader-account:{account}'.encode());need(digest(fp.encode())==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and all(q.ctidTraderAccountId==account for q,r in decoded),'AIP1_ACCOUNT')
    trader=decoded[0][1].trader;assets={a.assetId:a.name for a in decoded[1][1].asset};listed={s.symbolName:s for s in decoded[2][1].symbol}
    need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR' and b['accountSwapFreeEffective']==trader.swapFree,'AIP1_BROKER')
    for s,row in b['symbols'].items():
        q,r=decoded[row['contractRawIndex']];light=listed[s]
        need(row['symbolId']==light.symbolId and list(q.symbolId)==[light.symbolId] and len(r.symbol)==1 and row['contract']==contract_snapshot(r.symbol[0]) and row['quoteAsset']==assets[light.quoteAssetId],'AIP1_CONTRACT')
        q,r=decoded[row['marginRawIndex']];need(q.symbolId==light.symbolId and list(q.volume)==[row['contract']['minVolume']] and r.HasField('moneyDigits') and len(r.margin)==1 and r.margin[0].volume==q.volume[0],'AIP1_MARGIN_BINDING')
        need(D(row['currentMinMarginEur'])==D(max(r.margin[0].buyMargin,r.margin[0].sellMargin))/D(10)**r.moneyDigits,'AIP1_MARGIN_VALUE')
    expected_universe=[];expected_specs=[]
    for spec in p['sessionSpecs']:
        name=next((n for n in spec['aliases'] if n in listed and listed[n].enabled),None)
        if name is None:continue
        need(name in b['symbols'],'AIP1_ALL_DECLARED_METADATA')
        row=b['symbols'][name]
        if D(row['currentMinMarginEur'])<200 and row['quoteAsset'] in ['USD','EUR','GBP','AUD','JPY']:
            expected_universe.append(name)
            expected_specs.append(dict(Symbol=name,**{k:v for k,v in spec.items() if k not in ['canonical','aliases']}))
    need(b['universe']==expected_universe and b['sessionSpecs']==expected_specs,'AIP1_PROSPECTIVE_UNIVERSE_AND_SCHEDULE')
    rebuilt={s:{} for s in b['universe']}
    for w in b['windows']:
        lo,hi=w['range'];s=w['symbol'];q,r=decoded[w['rawIndex']]
        need([lo,hi] in p['sourceChunks'] and q.symbolId==b['symbols'][s]['symbolId'] and q.fromTimestamp==lo and q.toTimestamp==hi and q.period==e.M5 and r.period==e.M5,'AIP1_M5_GEOMETRY')
        for x in bars(r,lo,hi):need(x[0] not in rebuilt[s] or rebuilt[s][x[0]]==x,'AIP1_BAR_CONFLICT');rebuilt[s][x[0]]=x
    need({s:sorted(rows.values()) for s,rows in rebuilt.items()}==b['bars'],'AIP1_RAW_BARS')
    for t,indices in b['costIndices'].items():
        need(int(t) in p['costClocks'],'AIP1_COST_CLOCK')
        for s,ixs in indices.items():
            for side,ix in zip((e.BID,e.ASK),ixs):
                q,r=decoded[ix];need(q.symbolId==b['symbols'][s]['symbolId'] and q.type==side and q.fromTimestamp==int(t)-2000 and q.toTimestamp==int(t)+58000 and r.HasField('hasMore'),'AIP1_COST_REQUEST')
    # Rebuild the outcome-blind expansion decision from the original pilot replies.
    import copy
    pilot=copy.deepcopy(b);pilot['bars']={s:[] for s in b['universe']}
    for w in b['windows']:
        if w['range'] not in [p['sourceChunks'][i] for i in p['pilotChunkIndices']]:continue
        q,r=decoded[w['rawIndex']];pilot['bars'][w['symbol']].extend(bars(r,*w['range']))
    for rows in pilot['bars'].values():rows.sort()
    pilot['costIndices']={t:v for t,v in b['costIndices'].items() if int(t) in p['pilotCostClocks']}
    contexts=cost_contexts(pilot,dict(universe=b['universe'])) if pilot['costIndices'] else []
    useful=[c for c in contexts if c['Samples']>=2 and c['CurrentFundingScheduleKnown']]
    support=native(normalized_input(dict(pilot,costContexts=contexts),p),'--auction-source-support') if len(useful)>=2 else []
    passed=sum(x['FeatureEpisodes']>=3 and x['KnownLabels']>=3 and x['Symbol'] in [c['Symbol'] for c in useful] for x in support)>=2
    need(passed==b['pilotPassed'] and support==b['pilotSummary']['support'] and b['pilotSummary']['netScoresComputed'] is False,'AIP1_RAW_PILOT_EXPANSION_RECONSTRUCTION')
    need(json.dumps(contexts,sort_keys=True,default=str)==json.dumps(b['pilotSummary']['costContexts'],sort_keys=True,default=str),'AIP1_RAW_PILOT_COST_RECONSTRUCTION')
    need(len(decoded)<=p['maxEvidenceRequests'],'AIP1_BUDGET')
    if b['pilotPassed']:need(len(b['windows'])==len(p['sourceChunks'])*len(b['universe']),'AIP1_COMPLETE_SOURCE')
    return dict(originalAccountBindingRechecked=True,requests=len(decoded),bars={s:len(v) for s,v in b['bars'].items()},sourceWindows=len(b['windows']),pilotPassed=b['pilotPassed'])


def collect():
    p=json.loads(P.read_text());need(not Path('docs/AIP1_AUTHENTIC_RESULT.json').exists(),'AIP1_CLOSED')
    run=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run);transport=StdlibCTraderTransport();raw=[];b=None
    def req(q,kind):
        require_read_only_request(q);need(len(raw)<p['maxEvidenceRequests'],'AIP1_BUDGET');r=transport.request(q)
        need(isinstance(r,kind) and r.IsInitialized() and r.ctidTraderAccountId==account,'AIP1_READONLY_RESPONSE')
        raw.append(dict(requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode(),type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode()));return r,len(raw)-1
    def seal(final=False):
        if b is None:return
        data=seal_new(json.dumps(b,sort_keys=True,default=str).encode(),recipient,run);out=Path('sealed-output');out.mkdir(exist_ok=True)
        (out/'source.envelope.json').write_bytes(data);(out/'receipt.public.json').write_text(json.dumps(dict(schema=SCHEMA,runId=run,sha256=digest(data),complete=final,ordersSubmitted=0)))
    try:
        account=authenticate(transport);trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)[0].trader
        assets={a.assetId:a.name for a in req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)[0].asset}
        listing={s.symbolName:s for s in req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)[0].symbol if s.enabled}
        need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR','AIP1_BROKER_CURRENCY')
        b=dict(schema=SCHEMA,readOnly=True,depositCurrency='EUR',protocolSha256=digest(P.read_bytes()),raw=raw,symbols={},windows=[],costIndices={},bars={},universe=[],sessionSpecs=[],pilotPassed=False,accountSwapFreeEffective=trader.swapFree,accountSwapFreeExplicitInWire=trader.HasField('swapFree'))
        mapped=[];admission=[]
        for spec in p['sessionSpecs']:
            name=next((n for n in spec['aliases'] if n in listing),None)
            admission.append(dict(canonical=spec['canonical'],symbol=name,status='MISSING_SYMBOL' if name is None else 'METADATA_PENDING'))
            if name:mapped.append((name,spec))
        for s in sorted(set(p['conversionSymbols']+[s for s,spec in mapped])):
            if s not in listing:continue
            light=listing[s];r,ci=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[light.symbolId]),m.ProtoOASymbolByIdRes)
            need(len(r.symbol)==1 and r.symbol[0].HasField('minVolume') and r.symbol[0].minVolume>0,'AIP1_MINIMUM_VOLUME');contract=contract_snapshot(r.symbol[0])
            r,mi=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=light.symbolId,volume=[contract['minVolume']]),m.ProtoOAExpectedMarginRes)
            need(r.HasField('moneyDigits') and len(r.margin)==1,'AIP1_CURRENT_MARGIN');margin=D(max(r.margin[0].buyMargin,r.margin[0].sellMargin))/D(10)**r.moneyDigits
            b['symbols'][s]=dict(symbolId=light.symbolId,baseAsset=assets[light.baseAssetId],quoteAsset=assets[light.quoteAssetId],contract=contract,contractRawIndex=ci,marginRawIndex=mi,currentMinMarginEur=str(margin))
        for s,spec in mapped:
            row=b['symbols'][s];a=next(x for x in admission if x['canonical']==spec['canonical']);a.update(minimumUnits=str(D(row['contract']['minVolume'])/100),currentMinimumMarginEur=row['currentMinMarginEur'])
            if D(row['currentMinMarginEur'])>=200:a['status']='CURRENT_MINIMUM_MARGIN_NOT_INITIAL_CAPITAL_FINANCEABLE';continue
            if row['quoteAsset'] not in ['USD','EUR','GBP','AUD','JPY']:a['status']='CURRENCY_ROUTE_UNSUPPORTED';continue
            a['status']='CURRENT_MARGIN_CAPACITY_ONLY';b['universe'].append(s);b['bars'][s]=[]
            b['sessionSpecs'].append(dict(Symbol=s,**{k:v for k,v in spec.items() if k not in ['canonical','aliases']}))
        b['instrumentAdmission']=admission;done=set()
        def window(i,s):
            if (i,s) in done:return
            lo,hi=p['sourceChunks'][i];r,ix=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=b['symbols'][s]['symbolId'],period=e.M5,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
            need(r.HasField('hasMore') and not r.hasMore,'AIP1_M5_PAGE');rows=bars(r,lo,hi);b['bars'][s].extend(rows);b['bars'][s].sort();b['windows'].append(dict(symbol=s,range=[lo,hi],rawIndex=ix));done.add((i,s))
        def quotes(t):
            b['costIndices'][str(t)]={}
            for s in sorted(set(b['universe']+p['conversionSymbols'])):
                if s not in b['symbols']:continue
                indices=[]
                for side in (e.BID,e.ASK):
                    r,ix=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=b['symbols'][s]['symbolId'],type=side,fromTimestamp=t-2000,toTimestamp=t+58000),m.ProtoOAGetTickDataRes);need(r.HasField('hasMore'),'AIP1_TICK_PAGE');indices.append(ix)
                b['costIndices'][str(t)][s]=indices
        if len(b['universe'])>=2:
            for t in p['pilotCostClocks']:quotes(t)
            b['costContexts']=cost_contexts(b,dict(universe=b['universe']))
            useful=[c for c in b['costContexts'] if c['Samples']>=2 and c['CurrentFundingScheduleKnown']]
            if len(useful)>=2:
                for i in p['pilotChunkIndices']:
                    for s in b['universe']:window(i,s)
                support=native(normalized_input(b,p),'--auction-source-support');b['pilotSupport']=support
                b['pilotPassed']=sum(x['FeatureEpisodes']>=3 and x['KnownLabels']>=3 and x['Symbol'] in [c['Symbol'] for c in useful] for x in support)>=2
        b['pilotSummary']=dict(passed=b['pilotPassed'],instrumentAdmission=admission,costContexts=b.get('costContexts',[]),support=b.get('pilotSupport',[]),netScoresComputed=False)
        seal();print('AIP1_PREVENTIVE_SUPPORT '+json.dumps(b['pilotSummary'],sort_keys=True,default=str),flush=True)
        if b['pilotPassed']:
            for i in range(len(p['sourceChunks'])):
                for s in b['universe']:window(i,s)
                if i%10==0:seal();print('AIP1_SOURCE_PROGRESS '+str(i),flush=True)
            for t in p['costClocks']:
                if str(t) not in b['costIndices']:quotes(t)
        b['auditReceipt']=audit(b,p);seal(True);print('AIP1_SOURCE_SEALED '+json.dumps(b['auditReceipt'],sort_keys=True),flush=True)
    except Exception:
        seal(False)
        raise
    finally:transport.close()


def readback():
    need(not Path('docs/AIP1_AUTHENTIC_RESULT.json').exists(),'AIP1_CLOSED');p=json.loads(P.read_text());run=os.environ['GITHUB_RUN_ID']
    data=Path('sealed-output/source.envelope.json').read_bytes();r=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(r['complete'] and r['runId']==run and r['sha256']==digest(data),'AIP1_SEALED_BINDING')
    b=json.loads(unseal_new(data,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run));need(audit(b,p)==b['auditReceipt'],'AIP1_RAW_RECONSTRUCTION')
    b['costContexts']=cost_contexts(b,dict(universe=b['universe'])) if b['costIndices'] else []
    result=native(normalized_input(b,p),'--auction-inventory-program') if b['pilotPassed'] else dict(Schema='mxm-auction-inventory-v1',Verdict='INFORMATIONAL_OR_FINANCIAL_PILOT_BLOCKED_NO_EXPANSION',FundedNetEur=None,EconomicQualification=False,OrdersSubmitted=0)
    result.update(Protocol=p,ProtocolSha256=digest(P.read_bytes()),SourceRunId=int(run),SourceCiphertextSha256=digest(data),SourceAudit=b['auditReceipt'],Pilot=b['pilotSummary'],CostContexts=b['costContexts'],RawReadbackMatched=True)
    Path('auction-inventory.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n');print('AIP1_RESULT '+json.dumps(result,sort_keys=True,default=str),flush=True)

if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception as error:
        import traceback
        print('AIP1_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True);raise SystemExit(1)
