"""BDP1: bounded annual discovery source with outcome-blind source/cost pilot."""
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
from .portfolio_economic_source import contract_snapshot,risk_terms
from .portfolio_economic_replay import native,fee

PROTOCOL=Path('research/portfolio_discovery_protocol.json')
SCHEMA='mxm-bdp1-source-v1'


def bars(r,lo,hi):
    if not r.HasField('hasMore') or r.hasMore:return []
    return [x for x in decode_bars(r.trendbar,lo-300000,hi+300000,5) if lo<=x[0] and x[1]<=hi]


def cost_contexts(b,p):
    windows=[];keys=[]
    def route(s):
        result={s,'EURUSD'}
        if b['symbols'][s]['quoteAsset']=='JPY':result.add('USDJPY')
        if b['symbols'][s]['quoteAsset']=='CAD':result.add('USDCAD')
        return sorted(result)
    for nominal,indices in b['costIndices'].items():
        nominal=int(nominal);events=[];complete={}
        for s,ixs in indices.items():
            complete[s]=True
            for side,ix in enumerate(ixs):
                r=m.ProtoOAGetTickDataRes();r.ParseFromString(base64.b64decode(b['raw'][ix]['protobuf']))
                complete[s] &= r.HasField('hasMore') and not r.hasMore
                if not r.hasMore:events.extend(dict(At=t,Symbol=s,Side=side,Price=price) for t,price in decode_side(r.tickData,nominal-2000,nominal+58000))
        for s in p['universe']:
            r=route(s);keys.append((s,nominal));windows.append(dict(Nominal=nominal,LatencyMs=1000,SearchMs=20000,MaximumAgeMs=2000,
                Route=r,Events=[x for x in events if x['Symbol'] in r],Complete=all(complete[x] for x in r)))
    observed=native(windows,'--causal-observation-windows');costs=[]
    for s in p['universe']:
        snapshots={str(t):dict(at=r['At'],quotes={q['Symbol']:dict(bid=q['Bid'],ask=q['Ask'],bidAt=q['BidAt'],askAt=q['AskAt']) for q in r['Quotes']})
            for (name,t),r in zip(keys,observed) if name==s and r['At'] is not None}
        valued=native(dict(schema=SCHEMA,readOnly=True,depositCurrency='EUR',symbols=b['symbols'],snapshots=snapshots),'--value-portfolio-source')['Snapshots']
        row=b['symbols'][s];units=row['contract']['minVolume']//100;values=[];notionals=[]
        for point in valued.values():
            q=point['Quotes'].get(s)
            if q is None:continue
            notional=units*D(q['Bid'])*(D(q['EurCreditPerQuote'])+D(q['EurDebitPerQuote']))/2
            friction=2*fee(q,units)+3*(D(q['Ask'])-D(q['Bid']))*units*D(q['EurDebitPerQuote'])
            if notional>0:values.append(10000*friction/notional);notionals.append(notional)
        c=row['contract'];costs.append(dict(Symbol=s,RoundTripBps=max(values) if values else None,MinimumNotionalEur=max(notionals) if notionals else None,
            CurrentMinimumMarginEur=row['currentMinMarginEur'],CurrentFundingScheduleKnown=(b['accountSwapFreeEffective'] is False and c.get('swapPeriod')==24 and isinstance(c.get('swapTime'),int)),SwapMinute=c.get('swapTime'),Samples=len(values)))
    return costs


def audit(b,p):
    need(b['schema']==SCHEMA and b['protocolSha256']==hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() and b['readOnly'] is True,'BDP1_PROTOCOL')
    decoded=[]
    for row in b['raw']:
        q=getattr(m,row['requestType'])();q.ParseFromString(base64.b64decode(row['requestProtobuf']));require_read_only_request(q)
        r=getattr(m,row['type'])();r.ParseFromString(base64.b64decode(row['protobuf']))
        need(r.IsInitialized() and r.ctidTraderAccountId==q.ctidTraderAccountId,'BDP1_RAW_RESPONSE');decoded.append((q,r))
    account=decoded[0][1].ctidTraderAccountId
    fingerprint=hashlib.sha256(f'ctrader-account:{int(account)}'.encode('ascii')).hexdigest()
    need(hashlib.sha256(fingerprint.encode('ascii')).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and all(q.ctidTraderAccountId==account for q,r in decoded),'BDP1_ORIGINAL_ACCOUNT')
    trader=decoded[0][1].trader;assets={a.assetId:a.name for a in decoded[1][1].asset};listing={s.symbolName:s for s in decoded[2][1].symbol}
    need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR' and b['accountSwapFreeEffective']==trader.swapFree,'BDP1_BROKER_CURRENCY')
    for s,row in b['symbols'].items():
        q,r=decoded[row['contractRawIndex']];light=listing[s]
        need(row['symbolId']==light.symbolId and list(q.symbolId)==[light.symbolId] and len(r.symbol)==1 and contract_snapshot(r.symbol[0])==row['contract'] and
             row['baseAsset']==assets[light.baseAssetId] and row['quoteAsset']==assets[light.quoteAssetId],'BDP1_CONTRACT_BINDING')
        q,r=decoded[row['marginRawIndex']]
        need(q.symbolId==light.symbolId and list(q.volume)==[row['contract']['minVolume']] and len(r.margin)==1 and r.HasField('moneyDigits'),'BDP1_MARGIN_REQUEST')
        amount=D(max(r.margin[0].buyMargin,r.margin[0].sellMargin))/D(10)**r.moneyDigits
        need(D(row['currentMinMarginEur'])==amount and r.margin[0].volume==q.volume[0],'BDP1_CURRENT_MARGIN')
    rebuilt={s:{} for s in p['universe']}
    for window in b['windows']:
        lo,hi=window['range'];s=window['symbol'];q,r=decoded[window['rawIndex']]
        need([lo,hi] in p['sourceChunks'] and q.symbolId==b['symbols'][s]['symbolId'] and q.period==e.M5 and q.fromTimestamp==lo and q.toTimestamp==hi and r.period==e.M5,'BDP1_BAR_REQUEST')
        for x in bars(r,lo,hi):
            need(x[0] not in rebuilt[s] or rebuilt[s][x[0]]==x,'BDP1_CONFLICTING_BARS');rebuilt[s][x[0]]=x
    need({s:sorted(v.values()) for s,v in rebuilt.items()}==b['bars'],'BDP1_RAW_BAR_RECONSTRUCTION')
    expected_costs=p['costClocks'] if b['pilotPassed'] else p['pilotCostClocks']
    need(sorted(map(int,b['costIndices']))==sorted(expected_costs),'BDP1_COST_CALENDAR')
    for t,indices in b['costIndices'].items():
        need(sorted(indices)==sorted(p['universe']),'BDP1_COST_UNIVERSE')
        for s,ixs in indices.items():
            for side,ix in zip((e.BID,e.ASK),ixs):
                q,r=decoded[ix];need(q.symbolId==b['symbols'][s]['symbolId'] and q.type==side and q.fromTimestamp==int(t)-2000 and q.toTimestamp==int(t)+58000 and r.HasField('hasMore'),'BDP1_COST_REQUEST')
    need(len(decoded)<=p['maxEvidenceRequests'],'BDP1_BUDGET')
    if b['pilotPassed']:need(len(b['windows'])==len(p['sourceChunks'])*len(p['universe']),'BDP1_COMPLETE_CALENDAR')
    return dict(originalAccountBindingRechecked=True,evidenceRequests=len(decoded),sourceWindows=len(b['windows']),
        bars={s:len(x) for s,x in b['bars'].items()},pilotPassed=b['pilotPassed'],protocolSha256=b['protocolSha256'])


def collect():
    p=json.loads(PROTOCOL.read_text());need(not Path('docs/BDP1_AUTHENTIC_RESULT.json').exists(),'BDP1_CLOSED')
    run=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run);raw=[];transport=StdlibCTraderTransport();b=None
    def req(q,kind):
        require_read_only_request(q);need(len(raw)<p['maxEvidenceRequests'],'BDP1_BUDGET')
        r=transport.request(q);need(isinstance(r,kind) and r.IsInitialized() and r.ctidTraderAccountId==account,'BDP1_AUTHENTIC_RESPONSE')
        raw.append(dict(requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode(),type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode()))
        return r,len(raw)-1
    def seal(final=False):
        if b is None:return
        data=seal_new(json.dumps(b,sort_keys=True).encode(),recipient,run);out=Path('sealed-output');out.mkdir(exist_ok=True)
        (out/'source.envelope.json').write_bytes(data)
        (out/'receipt.public.json').write_text(json.dumps(dict(schema=SCHEMA,runId=run,sha256=hashlib.sha256(data).hexdigest(),complete=final,ordersSubmitted=0)))
    try:
        account=authenticate(transport);trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)[0].trader
        assets={a.assetId:a.name for a in req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)[0].asset}
        listed={s.symbolName:s for s in req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)[0].symbol if s.enabled}
        need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR','BDP1_PEPPERSTONE_EUR')
        b=dict(schema=SCHEMA,readOnly=True,depositCurrency='EUR',accountSwapFreeEffective=trader.swapFree,
            accountSwapFreeExplicitInWire=trader.HasField('swapFree'),protocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
            symbols={},raw=raw,windows=[],bars={s:[] for s in p['universe']},costIndices={},pilotPassed=False)
        for s in p['universe']:
            light=listed[s];r,ci=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[light.symbolId]),m.ProtoOASymbolByIdRes)
            need(len(r.symbol)==1,'BDP1_SYMBOL');c=r.symbol[0];contract=contract_snapshot(c)
            need(c.HasField('minVolume') and c.minVolume>0 and c.minVolume%100==0,'BDP1_MINIMUM_VOLUME')
            r,mi=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=light.symbolId,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
            need(r.HasField('moneyDigits') and len(r.margin)==1,'BDP1_MARGIN')
            margin=D(max(r.margin[0].buyMargin,r.margin[0].sellMargin))/D(10)**r.moneyDigits
            b['symbols'][s]=dict(symbolId=light.symbolId,baseAsset=assets[light.baseAssetId],quoteAsset=assets[light.quoteAssetId],contract=contract,
                contractRawIndex=ci,marginRawIndex=mi,currentMinMarginEur=str(margin),currentMarginPerUnitBoundEur=str(margin/(D(c.minVolume)/100)),maxQueriedUnits=c.minVolume//100)
        done=set()
        def window(index,s):
            if (index,s) in done:return
            lo,hi=p['sourceChunks'][index];r,ix=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=b['symbols'][s]['symbolId'],period=e.M5,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
            need(r.HasField('hasMore') and not r.hasMore,'BDP1_BOUNDED_BAR_PAGE')
            rows=bars(r,lo,hi);b['bars'][s].extend(rows);b['bars'][s].sort()
            b['windows'].append(dict(symbol=s,range=[lo,hi],rawIndex=ix,bars=len(rows)));done.add((index,s))
        def quotes(t):
            b['costIndices'][str(t)]={}
            for s in p['universe']:
                indices=[]
                for side in (e.BID,e.ASK):
                    r,ix=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=b['symbols'][s]['symbolId'],type=side,fromTimestamp=t-2000,toTimestamp=t+58000),m.ProtoOAGetTickDataRes)
                    need(r.HasField('hasMore'),'BDP1_TICK_PAGINATION');indices.append(ix)
                b['costIndices'][str(t)][s]=indices
        for index in p['pilotChunkIndices']:
            for s in p['universe']:window(index,s)
        for t in p['pilotCostClocks']:quotes(t)
        contexts=cost_contexts(b,p)
        pilot=dict(minimumBarsPerRequestedWindow=min(w['bars'] for w in b['windows']),costSamples={c['Symbol']:c['Samples'] for c in contexts},
            currentMinimumCapacityAssets=[c['Symbol'] for c in contexts if c['Samples']>=2 and D(c['CurrentMinimumMarginEur'])<200],netScoresComputed=False)
        b['pilotPassed']=pilot['minimumBarsPerRequestedWindow']>=p['minimumPilotBarsPerSymbolWindow'] and all(c['Samples']>=2 for c in contexts) and len(pilot['currentMinimumCapacityAssets'])>=3
        pilot['passed']=b['pilotPassed'];b['pilot']=pilot;seal()
        print('BDP1_PREVENTIVE_SUPPORT '+json.dumps(pilot,sort_keys=True),flush=True)
        if b['pilotPassed']:
            for i in range(len(p['sourceChunks'])):
                for s in p['universe']:window(i,s)
                if i%10==0:seal();print('BDP1_ANNUAL_SOURCE_PROGRESS '+str(i)+'/'+str(len(p['sourceChunks'])),flush=True)
            for t in p['costClocks']:
                if str(t) not in b['costIndices']:quotes(t)
        b['auditReceipt']=audit(b,p);seal(True);print('BDP1_AUTHENTIC_SOURCE_SEALED '+json.dumps(b['auditReceipt'],sort_keys=True),flush=True)
    finally:transport.close()


def readback():
    p=json.loads(PROTOCOL.read_text());need(not Path('docs/BDP1_AUTHENTIC_RESULT.json').exists(),'BDP1_CLOSED')
    run='41724643418' if '--bound-source-reception' in sys.argv else os.environ['GITHUB_RUN_ID'];raw=Path('sealed-output/source.envelope.json').read_bytes();receipt=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(receipt['complete'] and receipt['runId']==run and receipt['sha256']==hashlib.sha256(raw).hexdigest(),'BDP1_CUSTODY')
    b=json.loads(unseal_new(raw,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run));need(audit(b,p)==b['auditReceipt'],'BDP1_INDEPENDENT_RAW_READBACK')
    contexts=cost_contexts(b,p)
    if b['pilotPassed']:
        inp=dict(Bars=[dict(Symbol=s,Start=x[0],End=x[1],Open=x[2],High=x[3],Low=x[4],Close=x[5],Volume=x[6]) for s,rows in b['bars'].items() for x in rows],
            Costs=[c for c in contexts if c['RoundTripBps'] is not None],Start=p['start'],DevelopmentEnd=p['developmentEnd'],SelectionEnd=p['selectionEnd'],End=p['end'])
        result=native(inp,'--portfolio-discovery-program')
    else:result=dict(Schema='mxm-integrated-discovery-program-v1',Verdict='SOURCE_PILOT_FAILED_NO_EXPANSION',FundedNetEur=None,EconomicQualification=False)
    result.update(Protocol=p,SourceRunId=int(run),ExecutionRunId=int(os.environ['GITHUB_RUN_ID']),SourceRecollected=False if '--bound-source-reception' in sys.argv else True,SourceCiphertextSha256=receipt['sha256'],RawReadbackMatched=True,SourceAudit=b['auditReceipt'],Pilot=b['pilot'],CostContexts=contexts,
        AccountSwapFreeEffective=b['accountSwapFreeEffective'],AccountSwapFreeExplicitInWire=b['accountSwapFreeExplicitInWire'])
    Path('portfolio-discovery.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    print('BDP1_AUTHENTIC_DISCOVERY_RESULT '+json.dumps(result,sort_keys=True,default=str),flush=True)


if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception as error:
        import traceback
        print('BDP1_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True)
        raise SystemExit(1)
