"""CCP1 bounded current-term portfolio funding preflight, no price-return study."""
import base64,hashlib,json,os,sys,time
from pathlib import Path
from decimal import Decimal as D
from .collect import authenticate,HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import need,decode_side
from .custody import seal_new,unseal_new
from .custody_new import checked_public
from .portfolio_economic_source import contract_snapshot
from .portfolio_economic_replay import native
P=Path('research/carry_cycle_preflight_protocol.json');SCHEMA='mxm-carry-cycle-source-v1'
def sha(raw):return hashlib.sha256(raw).hexdigest()

def audit(b,p):
    need(b['schema']==SCHEMA and b['readOnly'] and b['protocolSha256']==sha(P.read_bytes()),'CCP1_PROTOCOL')
    rows=[]
    for x in b['raw']:
        q=getattr(m,x['requestType'])();q.ParseFromString(base64.b64decode(x['requestProtobuf']));require_read_only_request(q)
        r=getattr(m,x['type'])();r.ParseFromString(base64.b64decode(x['protobuf']));need(r.IsInitialized() and r.ctidTraderAccountId==q.ctidTraderAccountId,'CCP1_RAW_REPLY');rows.append((q,r))
    account=rows[0][1].ctidTraderAccountId;fp=sha(f'ctrader-account:{account}'.encode())
    need(sha(fp.encode())==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and all(q.ctidTraderAccountId==account for q,r in rows),'CCP1_ORIGINAL_ACCOUNT')
    trader=rows[0][1].trader;assets={a.assetId:a.name for a in rows[1][1].asset};listed={s.symbolName:s for s in rows[2][1].symbol if s.enabled}
    need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR' and b['normalAccountEffective']==(not trader.swapFree),'CCP1_ACCOUNT_SCOPE')
    need(b['moneyDigits']==(trader.moneyDigits if trader.HasField('moneyDigits') else None) and b['swapFreeExplicitInWire']==trader.HasField('swapFree'),'CCP1_MONEY_PRECISION')
    need(sorted(b['symbols'])==sorted(s for s in p['universe'] if s in listed),'CCP1_FIXED_UNIVERSE')
    for s,x in b['symbols'].items():
        light=listed[s];q,r=rows[x['contractIndex']]
        need(list(q.symbolId)==[light.symbolId] and len(r.symbol)==1 and x['contract']==contract_snapshot(r.symbol[0]) and x['symbolId']==light.symbolId and x['baseAsset']==assets[light.baseAssetId] and x['quoteAsset']==assets[light.quoteAssetId],'CCP1_CONTRACT')
        detail=r.symbol[0];q,r=rows[x['marginIndex']]
        expected=[x['contract']['minVolume']*k for k in p['gridMultiples'] if x['contract']['minVolume']*k<=x['contract']['maxVolume'] and (x['contract']['minVolume']*k-x['contract']['minVolume'])%x['contract']['stepVolume']==0]
        need(q.symbolId==light.symbolId and list(q.volume)==expected and r.HasField('moneyDigits') and sorted(v.volume for v in r.margin)==sorted(expected),'CCP1_MARGIN_GRID')
        rebuilt=[dict(Units=str(D(v.volume)/100),BuyEur=str(D(v.buyMargin)/D(10)**r.moneyDigits),SellEur=str(D(v.sellMargin)/D(10)**r.moneyDigits)) for v in r.margin]
        need(rebuilt==x['marginGrid'],'CCP1_MARGIN_VALUES')
        need(x['swapTypeExplicit']==detail.HasField('swapCalculationType'),'CCP1_SWAP_UNIT_PRESENCE')
        for side,ix in zip((e.BID,e.ASK),x['tickIndices']):
            q,r=rows[ix];need(q.symbolId==light.symbolId and q.type==side and q.fromTimestamp==b['nominal']-2000 and q.toTimestamp==b['nominal']+58000 and r.HasField('hasMore'),'CCP1_CLOCK_ROUTE')
    need(len(rows)<=p['budget'] and b['nominal']==b['captureStarted']//900000*900000-900000 and b['nominal']+58000<b['captureStarted'],'CCP1_PROSPECTIVE_CALENDAR')
    return dict(requests=len(rows),symbols=len(b['symbols']),originalAccountBindingRechecked=True,annualBarsRequested=0)

def evaluate(b,p):
    events=[];complete={}
    for s,x in b['symbols'].items():
        complete[s]=True
        for side,ix in enumerate(x['tickIndices']):
            r=m.ProtoOAGetTickDataRes();r.ParseFromString(base64.b64decode(b['raw'][ix]['protobuf']));complete[s]&=not r.hasMore
            if not r.hasMore:events.extend(dict(At=t,Symbol=s,Side=side,Price=v) for t,v in decode_side(r.tickData,b['nominal']-2000,b['nominal']+58000))
    windows=[];cycles=[]
    for c in p['cycles']:
        route=sorted(set([c['BaseUsd'],c['BaseJpy'],'USDJPY','EURUSD']));cycles.append(c)
        windows.append(dict(Nominal=b['nominal'],LatencyMs=1000,SearchMs=20000,MaximumAgeMs=2000,Route=route,Events=[x for x in events if x['Symbol'] in route],Complete=all(complete.get(s,False) for s in route)))
    clocks=native(windows,'--causal-observation-windows');contexts=[]
    for c,r in zip(cycles,clocks):
        if r['At'] is None:contexts.append(dict(**c,QuoteAt=0,Quotes=[]));continue
        snapshot=dict(at=r['At'],quotes={q['Symbol']:dict(bid=q['Bid'],ask=q['Ask'],bidAt=q['BidAt'],askAt=q['AskAt']) for q in r['Quotes']})
        valued=native(dict(schema=SCHEMA,readOnly=True,depositCurrency='EUR',symbols=b['symbols'],snapshots={str(b['nominal']):snapshot}),'--value-portfolio-source')['Snapshots'][str(b['nominal'])]['Quotes']
        contexts.append(dict(**c,QuoteAt=r['At'],Quotes=[dict(Symbol=s,**q) for s,q in valued.items()]))
    terms=[]
    for s,x in b['symbols'].items():
        c=x['contract'];terms.append(dict(Symbol=s,BaseAsset=x['baseAsset'],QuoteAsset=x['quoteAsset'],MinUnits=str(D(c['minVolume'])/100),StepUnits=str(D(c['stepVolume'])/100),MaxUnits=str(D(c['maxVolume'])/100),PipPosition=c['pipPosition'],SwapType=c['swapCalculationType'] if x['swapTypeExplicit'] else None,SwapLong=c['swapLong'],SwapShort=c['swapShort'],SwapPeriod=c['swapPeriod'],SwapMinute=c['swapTime'],Margins=x['marginGrid']))
    if b['moneyDigits'] is None:return dict(Schema='mxm-carry-cycle-preflight-v1',Verdict='ACCOUNT_MONEY_PRECISION_UNKNOWN',FullStudyAdmitted=False,FundedNetEur=None)
    return native(dict(Terms=terms,Contexts=contexts,NormalAccountEffective=b['normalAccountEffective'],MoneyDigits=b['moneyDigits']),'--carry-cycle-preflight')

def collect():
    p=json.loads(P.read_text());need(not Path('docs/CCP1_AUTHENTIC_PREFLIGHT.json').exists(),'CCP1_CLOSED_PROFILE')
    run=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run);raw=[];t=StdlibCTraderTransport();b=None
    def request(q,kind):
        require_read_only_request(q);need(len(raw)<p['budget'],'CCP1_BUDGET');r=t.request(q);need(isinstance(r,kind) and r.IsInitialized() and r.ctidTraderAccountId==account,'CCP1_RESPONSE')
        raw.append(dict(requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode(),type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode()));return r,len(raw)-1
    def seal(final=False):
        if b is None:return
        data=seal_new(json.dumps(b,sort_keys=True,default=str).encode(),recipient,run);out=Path('sealed-output');out.mkdir(exist_ok=True)
        (out/'source.envelope.json').write_bytes(data);(out/'receipt.public.json').write_text(json.dumps(dict(runId=run,sha256=sha(data),complete=final,ordersSubmitted=0)))
    try:
        account=authenticate(t);started=int(time.time()*1000);trader=request(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)[0].trader
        assets={a.assetId:a.name for a in request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)[0].asset}
        listing={s.symbolName:s for s in request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)[0].symbol if s.enabled}
        need(assets[trader.depositAssetId]=='EUR' and 'pepperstone' in trader.brokerName.lower(),'CCP1_ACCOUNT')
        b=dict(schema=SCHEMA,readOnly=True,depositCurrency='EUR',protocolSha256=sha(P.read_bytes()),captureStarted=started,nominal=started//900000*900000-900000,normalAccountEffective=not trader.swapFree,swapFreeExplicitInWire=trader.HasField('swapFree'),moneyDigits=trader.moneyDigits if trader.HasField('moneyDigits') else None,symbols={},raw=raw)
        for s in p['universe']:
            if s not in listing:continue
            light=listing[s];r,ci=request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[light.symbolId]),m.ProtoOASymbolByIdRes);need(len(r.symbol)==1,'CCP1_CONTRACT')
            c=r.symbol[0];contract=contract_snapshot(c);need(all(contract[k] is not None and contract[k]>0 for k in ['minVolume','stepVolume','maxVolume']),'CCP1_VOLUME')
            volumes=[c.minVolume*k for k in p['gridMultiples'] if c.minVolume*k<=c.maxVolume and (c.minVolume*k-c.minVolume)%c.stepVolume==0]
            r,mi=request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=light.symbolId,volume=volumes),m.ProtoOAExpectedMarginRes);need(r.HasField('moneyDigits'),'CCP1_MARGIN')
            b['symbols'][s]=dict(symbolId=light.symbolId,baseAsset=assets[light.baseAssetId],quoteAsset=assets[light.quoteAssetId],contract=contract,contractIndex=ci,marginIndex=mi,swapTypeExplicit=c.HasField('swapCalculationType'),marginGrid=[dict(Units=str(D(v.volume)/100),BuyEur=str(D(v.buyMargin)/D(10)**r.moneyDigits),SellEur=str(D(v.sellMargin)/D(10)**r.moneyDigits)) for v in r.margin])
        seal()
        for s,x in b['symbols'].items():
            x['tickIndices']=[]
            for side in (e.BID,e.ASK):
                r,ix=request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=x['symbolId'],type=side,fromTimestamp=b['nominal']-2000,toTimestamp=b['nominal']+58000),m.ProtoOAGetTickDataRes);need(r.HasField('hasMore'),'CCP1_TICK_PAGE');x['tickIndices'].append(ix)
        b['auditReceipt']=audit(b,p);seal(True);print('CCP1_SOURCE_SEALED '+json.dumps(b['auditReceipt'],sort_keys=True),flush=True)
    except Exception:seal();raise
    finally:t.close()

def readback():
    need(not Path('docs/CCP1_AUTHENTIC_PREFLIGHT.json').exists(),'CCP1_CLOSED_PROFILE');p=json.loads(P.read_text());run=os.environ['GITHUB_RUN_ID']
    raw=Path('sealed-output/source.envelope.json').read_bytes();r=json.loads(Path('sealed-output/receipt.public.json').read_text());need(r['complete'] and r['runId']==run and r['sha256']==sha(raw),'CCP1_SEALED_BINDING')
    b=json.loads(unseal_new(raw,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run));need(audit(b,p)==b['auditReceipt'],'CCP1_RAW_READBACK')
    result=evaluate(b,p);result.update(Protocol=p,ProtocolSha256=sha(P.read_bytes()),SourceRunId=int(run),SourceCiphertextSha256=sha(raw),SourceAudit=b['auditReceipt'],TermsObservedAfterQuoteContext=True,IsHistoricalNetPerformance=False,RawReadbackMatched=True)
    Path('carry-cycle.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n');print('CCP1_PREFLIGHT_RESULT '+json.dumps(result,sort_keys=True,default=str),flush=True)
if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception as error:
        import traceback
        print('CCP1_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True);raise SystemExit(1)
