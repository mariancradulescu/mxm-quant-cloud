"""Two preregistered distinct causal mechanisms, selection then untouched holdout.
Reuses original OAuth, broker-only transport, event quote reconstruction, custody.
"""
import base64,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from .collect import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .decode import need,decode_side
from .economic_source import _windows,_bounded_server_window
from .intraday_net import reconstruct,native
from .custody_new import checked_public
from .custody import seal_new,unseal_new

MAX_REQUESTS=9000
UNIVERSE=('GBPUSD','AUDUSD')

def run():
    run_id=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run_id)
    t=StdlibCTraderTransport();raw=[]
    def req(q,cls):
        need(len(raw)<MAX_REQUESTS,'FLOW_REQUEST_BUDGET')
        r=t.request(q)
        need(isinstance(r,cls) and r.IsInitialized() and r.ctidTraderAccountId==account,'FLOW_RESPONSE_BINDING')
        raw.append({'type':type(r).__name__,'protobuf':base64.b64encode(r.SerializeToString()).decode()})
        return r
    try:
        account=authenticate(t)
        tr=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes).trader
        need(tr.HasField('brokerName') and 'pepperstone' in tr.brokerName.casefold(),'FLOW_PEPPERSTONE')
        al=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        assets={a.assetId:a.name for a in al.asset}
        need(assets.get(tr.depositAssetId)=='EUR' and tr.HasField('leverageInCents') and tr.leverageInCents>0,'FLOW_EUR_ACCOUNT_LEVERAGE')
        sy=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        lookup={s.symbolName:s for s in sy.symbol if s.enabled}
        need(all(s in lookup for s in (*UNIVERSE,'EURUSD')),'FLOW_FIXED_UNIVERSE_UNAVAILABLE')
        contracts={};margins={};leverage={};bars={}
        end_dt=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        end=int(end_dt.timestamp()*1000);start=end-370*86400000
        for name in UNIVERSE:
            symbol=lookup[name]
            need(assets.get(symbol.quoteAssetId)=='USD' and assets.get(symbol.baseAssetId)==name[:3],'FLOW_ASSET_BINDING')
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[symbol.symbolId]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==symbol.symbolId,'FLOW_SYMBOL_BINDING')
            c=detail.symbol[0]
            fields=('minVolume','stepVolume','maxVolume','lotSize','preciseTradingCommissionRate','preciseMinCommission','pnlConversionFeeRate','swapLong','swapShort','swapCalculationType','slDistance','tpDistance','distanceSetIn','digits','pipPosition')
            for f in fields:need(c.HasField(f),'FLOW_BROKER_FIELD_MISSING_'+f.upper())
            contracts[name]={f:getattr(c,f) for f in fields}
            for f in ('commissionType','minCommissionType','minCommissionAsset'):contracts[name][f]=getattr(c,f)
            for f in ('swapPeriod','swapTime'):
                contracts[name][f]=getattr(c,f) if c.HasField(f) else None
            need(c.HasField('leverageId'),'FLOW_LEVERAGE_ID_MISSING')
            margin=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=symbol.symbolId,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
            need(margin.HasField('moneyDigits') and len(margin.margin)==1 and margin.margin[0].volume==c.minVolume,'FLOW_MARGIN_BINDING')
            margins[name]=max(margin.margin[0].buyMargin,margin.margin[0].sellMargin)/(10**margin.moneyDigits)
            dyn=req(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=account,leverageId=c.leverageId),m.ProtoOAGetDynamicLeverageByIDRes)
            need(dyn.leverage.leverageId==c.leverageId and len(dyn.leverage.tiers)>0,'FLOW_DYNAMIC_LEVERAGE_BINDING')
            leverage[name]=min(tr.leverageInCents/100,dyn.leverage.tiers[0].leverage)
            def window(lo,hi,depth=0):
                need(depth<20,'FLOW_PAGE_DEPTH')
                r=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=symbol.symbolId,period=e.M15,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
                need(r.period==e.M15 and (not r.HasField('symbolId') or r.symbolId==symbol.symbolId) and r.HasField('hasMore'),'FLOW_BAR_BINDING')
                if r.hasMore:
                    need(hi>lo,'FLOW_PAGE_UNRESOLVABLE');mid=(lo+hi)//2
                    return window(lo,mid,depth+1)+window(mid+1,hi,depth+1)
                return _bounded_server_window(r.trendbar,lo,hi,15)
            rows={}
            for lo,hi in _windows(start,end,4):
                for row in window(lo,hi):
                    need(row[0] not in rows,'FLOW_DUPLICATE_BAR')
                    if row[0]+900000<=end:rows[row[0]]={'t':row[0],'o':row[2],'h':row[3],'l':row[4],'c':row[5]}
            need(len(rows)>20000 and max(rows)+900000-min(rows)>=365*86400000,'FLOW_TWELVE_MONTH_SOURCE_INSUFFICIENT')
            bars[name]=[rows[k] for k in sorted(rows)]
        need(assets.get(lookup['EURUSD'].baseAssetId)=='EUR' and assets.get(lookup['EURUSD'].quoteAssetId)=='USD','FLOW_EURUSD_ASSETS')
        def quote(symbol,time):
            sides=[]
            for side in (e.BID,e.ASK):
                r=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=lookup[symbol].symbolId,type=side,fromTimestamp=time,toTimestamp=time+10000),m.ProtoOAGetTickDataRes)
                need(r.HasField('hasMore'),'FLOW_TICK_COMPLETENESS')
                sides.append(None if r.hasMore else decode_side(r.tickData,time,time+10000))
            return reconstruct(*sides,time) if all(x is not None for x in sides) else None
        screen_dt=end_dt-timedelta(days=1)
        while screen_dt.weekday()>4:screen_dt-=timedelta(days=1)
        screen_time=int(screen_dt.replace(hour=12).timestamp()*1000)
        screen=quote('EURUSD',screen_time);need(screen is not None,'FLOW_SCREEN_FX_UNAVAILABLE')
        bundle={'schema':'mxm-flow-net-v1','source':'Pepperstone-cTrader-OpenAPI','readOnly':True,'start':start,'end':end,
                'bars':bars,'contracts':contracts,'margins':margins,'leverage':leverage,'screenEurAsk':screen['ask']/100000,'quotes':{}}
        def collect_plan(plan,phase):
            events=sorted({(sym,p[k]) for p in plan for k in ('Entry','Exit') for sym in (p['Symbol'],'EURUSD')})
            events=[(s,tm) for s,tm in events if s+':'+str(tm) not in bundle['quotes']]
            need(len(raw)+len(events)*2<MAX_REQUESTS,'FLOW_FROZEN_PLAN_BUDGET')
            print('FLOW_PLAN_FROZEN '+json.dumps({'phase':phase,'proposals':len(plan),'quoteEvents':len(events)}),flush=True)
            for index,(s,tm) in enumerate(events):
                bundle['quotes'][s+':'+str(tm)]=quote(s,tm)
                if index%100==0:print('FLOW_EVENT_PROGRESS '+phase+' '+str(index)+'/'+str(len(events)),flush=True)
        plan=native(bundle,'--flow-plan');collect_plan(plan,'SELECTION')
        selection=native(bundle,'--flow-selection');bundle['selectionSurvivors']=selection['selectionSurvivors']
        print('AUTHENTIC_FLOW_SELECTION '+json.dumps(selection,sort_keys=True),flush=True)
        confirmation=None
        if bundle['selectionSurvivors']:
            plans=native(bundle,'--flow-confirm-plan')
            collect_plan([p for p in plans if p['Model'] in bundle['selectionSurvivors']],'CONFIRMATION')
            confirmation=native(bundle,'--flow-confirmation')
            print('AUTHENTIC_FLOW_CONFIRMATION '+json.dumps(confirmation,sort_keys=True),flush=True)
        receipt={'selection':selection,'confirmation':confirmation,'ordersSubmitted':0,'closedModels':[x['model'] for x in selection['results'] if not x['eligibleForUntouchedHoldout']]}
        bundle['raw']=raw;bundle['nativeReceipt']=receipt
        cipher=seal_new(json.dumps(bundle,sort_keys=True).encode(),recipient,run_id)
        out=Path('sealed-output');out.mkdir(exist_ok=True)
        (out/'source.envelope.json').write_bytes(cipher)
        (out/'receipt.public.json').write_text(json.dumps({'schema':'flow-net-v1','runId':run_id,'ciphertextSha256':hashlib.sha256(cipher).hexdigest(),'ordersSubmitted':0}))
        Path('flow-net.public.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print('FLOW_NET_COMPLETED_AND_SEALED',flush=True)
    finally:t.close()

def readback():
    run_id=os.environ['GITHUB_RUN_ID'];data=Path('sealed-output/source.envelope.json').read_bytes()
    pub=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(pub['runId']==run_id and hashlib.sha256(data).hexdigest()==pub['ciphertextSha256'],'FLOW_CUSTODY_SHA')
    b=json.loads(unseal_new(data,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run_id));original=b.pop('nativeReceipt')
    selection=native(b,'--flow-selection')
    need(selection['selectionSurvivors']==b['selectionSurvivors'],'FLOW_SURVIVORS_PARITY')
    confirm=native(b,'--flow-confirmation') if selection['selectionSurvivors'] else None
    current={'selection':selection,'confirmation':confirm,'ordersSubmitted':0,'closedModels':[x['model'] for x in selection['results'] if not x['eligibleForUntouchedHoldout']]}
    need(current==original,'FLOW_NATIVE_PARITY')
    current.update({'custodyParity':True,'runId':run_id,'ciphertextSha256':pub['ciphertextSha256']})
    Path('flow-net.public.json').write_text(json.dumps(current,indent=2)+'\n')
    print('AUTHENTIC_FLOW_CUSTODY_PARITY '+json.dumps(current,sort_keys=True))

if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else run()
    except Exception as exc:
        from .guard import CaptureContractError
        print(str(exc) if isinstance(exc,CaptureContractError) and str(exc).isupper() and str(exc).replace('_','').isalnum() else 'FLOW_NET_FAILED_DETAIL_WITHHELD')
        sys.exit(1)
