"""New H1 conditional-return neighbours, calibrated execution and latest OWNER caps."""
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

UNIVERSE=('USDJPY','USDCAD')
MAX_REQUESTS=14000

def quantile(values,p):
    v=sorted(values);need(bool(v),'CALIBRATION_EMPTY')
    return v[min(len(v)-1,int((len(v)-1)*p))]

def run():
    run_id=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run_id)
    transport=StdlibCTraderTransport();raw=[]
    def request(q,cls):
        need(len(raw)<MAX_REQUESTS,'NEIGHBOUR_REQUEST_BUDGET')
        r=transport.request(q)
        need(isinstance(r,cls) and r.IsInitialized() and r.ctidTraderAccountId==account,'NEIGHBOUR_RESPONSE_BINDING')
        raw.append({'type':type(r).__name__,'protobuf':base64.b64encode(r.SerializeToString()).decode()})
        return r
    try:
        account=authenticate(transport)
        trader=request(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes).trader
        need(trader.HasField('brokerName') and 'pepperstone' in trader.brokerName.casefold() and trader.HasField('leverageInCents'),'NEIGHBOUR_TRADER')
        assets={a.assetId:a.name for a in request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes).asset}
        need(assets.get(trader.depositAssetId)=='EUR','NEIGHBOUR_EUR_ACCOUNT')
        listed=request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        lookup={s.symbolName:s for s in listed.symbol if s.enabled}
        need(all(s in lookup for s in (*UNIVERSE,'EURUSD')),'NEIGHBOUR_UNIVERSE')
        end_dt=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        end=int(end_dt.timestamp()*1000);start=end-370*86400000;cut=start+(end-start)*6//10
        contracts={};margins={};leverage={};bars={};calibration={};cal_minutes={}
        def history(symbol,lo,hi,period,minutes,depth=0):
            need(depth<20,'NEIGHBOUR_PAGE_DEPTH')
            r=request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=lookup[symbol].symbolId,period=period,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
            need(r.period==period and (not r.HasField('symbolId') or r.symbolId==lookup[symbol].symbolId) and r.HasField('hasMore'),'NEIGHBOUR_BAR_BINDING')
            if r.hasMore:
                need(hi>lo,'NEIGHBOUR_PAGE_TRUNCATED');mid=(hi+lo)//2
                return history(symbol,lo,mid,period,minutes,depth+1)+history(symbol,mid+1,hi,period,minutes,depth+1)
            return _bounded_server_window(r.trendbar,lo,hi,minutes)
        def rows_json(rows):return [{'t':x[0],'o':x[2],'h':x[3],'l':x[4],'c':x[5]} for x in rows]
        def quote(symbol,tm,with_sides=False):
            sides=[]
            for side in (e.BID,e.ASK):
                r=request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=lookup[symbol].symbolId,type=side,fromTimestamp=tm,toTimestamp=tm+10000),m.ProtoOAGetTickDataRes)
                need(r.HasField('hasMore'),'NEIGHBOUR_TICK_COMPLETE')
                sides.append(None if r.hasMore else decode_side(r.tickData,tm,tm+10000))
            q=reconstruct(*sides,tm) if all(x is not None for x in sides) else None
            return (q,sides) if with_sides else q
        for symbol in (*UNIVERSE,'EURUSD'):
            s=lookup[symbol]
            need(assets.get(s.baseAssetId)==symbol[:3] and assets.get(s.quoteAssetId)==symbol[3:],'NEIGHBOUR_ASSET_BINDING')
            if symbol in UNIVERSE:
                detail=request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[s.symbolId]),m.ProtoOASymbolByIdRes)
                need(len(detail.symbol)==1 and detail.symbol[0].symbolId==s.symbolId,'NEIGHBOUR_SYMBOL_BINDING');c=detail.symbol[0]
                fields=('minVolume','stepVolume','maxVolume','lotSize','preciseTradingCommissionRate','preciseMinCommission','pnlConversionFeeRate','swapLong','swapShort','swapCalculationType','slDistance','tpDistance','distanceSetIn','digits','pipPosition')
                for f in fields:need(c.HasField(f),'NEIGHBOUR_BROKER_FIELD_'+f.upper())
                contracts[symbol]={f:getattr(c,f) for f in fields}
                for f in ('commissionType','minCommissionType','minCommissionAsset'):contracts[symbol][f]=getattr(c,f)
                for f in ('swapPeriod','swapTime'):contracts[symbol][f]=getattr(c,f) if c.HasField(f) else None
                need(c.HasField('leverageId'),'NEIGHBOUR_LEVERAGE_ID')
                mr=request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=s.symbolId,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
                need(mr.HasField('moneyDigits') and len(mr.margin)==1 and mr.margin[0].volume==c.minVolume,'NEIGHBOUR_MARGIN')
                margins[symbol]=max(mr.margin[0].buyMargin,mr.margin[0].sellMargin)/(10**mr.moneyDigits)
                lr=request(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=account,leverageId=c.leverageId),m.ProtoOAGetDynamicLeverageByIDRes)
                need(lr.leverage.leverageId==c.leverageId and len(lr.leverage.tiers)>0,'NEIGHBOUR_LEVERAGE_BINDING')
                leverage[symbol]=min(trader.leverageInCents/100,lr.leverage.tiers[0].leverage)
            allrows={}
            for lo,hi in _windows(start,end,28):
                for row in history(symbol,lo,hi,e.H1,60):
                    need(row[0] not in allrows,'NEIGHBOUR_BAR_DUPLICATE')
                    if row[0]+3600000<=end:allrows[row[0]]=row
            need(len(allrows)>=3000 and max(allrows)+3600000-min(allrows)>=365*86400000,'NEIGHBOUR_YEAR_SUPPORT')
            bars[symbol]=rows_json([allrows[k] for k in sorted(allrows)])
        # Calibration dates are fixed fractions of TRAIN only, never selected by outcomes.
        screen=None
        for symbol in UNIVERSE:
            gaps=[];spreads=[];moves=[];point=10**(-contracts[symbol]['digits'])
            for j in range(1,9):
                tm=start+(cut-start)*j//9
                day=datetime.fromtimestamp(tm/1000,timezone.utc).replace(hour=12,minute=0,second=0,microsecond=0)
                while day.weekday()>4:day-=timedelta(days=1)
                tm=int(day.timestamp()*1000);need(start<=tm-7200000 and tm+7200000<cut,'NEIGHBOUR_TRAIN_CALIBRATION_RANGE')
                sample=history(symbol,tm-7200000,tm+7200000-1,e.M1,1)
                cal_minutes[symbol+':'+str(tm)]=rows_json(sample)
                gaps.extend(abs(sample[i][2]-sample[i-1][5])/100000 for i in range(1,len(sample)) if sample[i][0]-sample[i-1][0]==60000)
                q,sides=quote(symbol,tm,True);need(q is not None,'NEIGHBOUR_TRAIN_QUOTE_MISSING')
                spreads.append((q['ask']-q['bid'])/100000)
                moves.append(max((max(v for _,v in side)-min(v for _,v in side))/100000 for side in sides))
                if symbol==UNIVERSE[0]:screen=quote('EURUSD',tm)
            h=[x for x in bars[symbol] if x['t']<cut]
            changes=[abs(h[i]['c']/h[i-1]['c']-1) for i in range(1,len(h))]
            calibration[symbol]={'gap':2*quantile(gaps,.995)+point,'spread':max(spreads)+point,'spreadStress':2*max(spreads)+point,
                                 'move':max(point,max(moves)/2),'shock':2*quantile(changes,.999)+point/(h[-1]['c']/100000),'minuteSamples':sum(len(v) for k,v in cal_minutes.items() if k.startswith(symbol+':')),'quoteSamples':8}
        need(screen is not None,'NEIGHBOUR_SCREEN_FX')
        h=[x for x in bars['EURUSD'] if x['t']<cut]
        eur_shock=2*quantile([abs(h[i]['c']/h[i-1]['c']-1) for i in range(1,len(h))],.999)+.00001/(h[-1]['c']/100000)
        need(eur_shock<.8 and all(x['shock']<.8 for x in calibration.values()),'NEIGHBOUR_FX_STRESS_UNRESOLVED')
        b={'schema':'mxm-neighbour-net-v1','source':'Pepperstone-cTrader-OpenAPI','readOnly':True,'start':start,'end':end,
           'contracts':contracts,'margins':margins,'leverage':leverage,'bars':bars,'calibration':calibration,'calibrationMinutes':cal_minutes,
           'screenEurAsk':screen['ask']/100000,'eurShock':eur_shock,'minutes':{},'quotes':{}}
        def gather(confirmation=False,survivors=None):
            mode='--neighbour-confirm-plan' if confirmation else '--neighbour-plan'
            plans=native(b,mode)
            if survivors is not None:plans=[p for p in plans if p['Symbol'] in survivors]
            print('NEIGHBOUR_PREQUOTE_PLAN '+json.dumps({'phase':'CONFIRMATION' if confirmation else 'SELECTION','proposals':len(plans)}),flush=True)
            for p in plans:
                key=p['Symbol']+':'+str(p['Entry'])
                if key not in b['minutes']:b['minutes'][key]=rows_json(history(p['Symbol'],p['Entry'],p['Horizon']-1,e.M1,1))
            final=native(b,mode)
            if survivors is not None:final=[p for p in final if p['Symbol'] in survivors]
            events=sorted({(s,p[k]) for p in final if p['MinuteComplete'] for k in ('Entry','Exit') for s in (p['Symbol'],'EURUSD')})
            events=[(s,tm) for s,tm in events if s+':'+str(tm) not in b['quotes']]
            need(len(raw)+2*len(events)<MAX_REQUESTS,'NEIGHBOUR_QUOTE_BUDGET')
            print('NEIGHBOUR_EVENT_PLAN_FROZEN '+json.dumps({'proposals':len(final),'quoteEvents':len(events),'phase':'CONFIRMATION' if confirmation else 'SELECTION'}),flush=True)
            for index,(s,tm) in enumerate(events):
                b['quotes'][s+':'+str(tm)]=quote(s,tm)
                if index%100==0:print('NEIGHBOUR_QUOTE_PROGRESS '+str(index)+'/'+str(len(events)),flush=True)
        gather();selection=native(b,'--neighbour-selection');b['selectionSurvivors']=selection['selectionSurvivors']
        print('AUTHENTIC_NEIGHBOUR_SELECTION '+json.dumps(selection,sort_keys=True),flush=True)
        confirmation=None
        if b['selectionSurvivors']:
            gather(True,b['selectionSurvivors']);confirmation=native(b,'--neighbour-confirmation')
            print('AUTHENTIC_NEIGHBOUR_CONFIRMATION '+json.dumps(confirmation,sort_keys=True),flush=True)
        receipt={'selection':selection,'confirmation':confirmation,'ordersSubmitted':0,'closedConfigurations':[x['symbol'] for x in selection['results'] if not x['eligibleForConfirmation']]}
        b['raw']=raw;b['nativeReceipt']=receipt
        cipher=seal_new(json.dumps(b,sort_keys=True).encode(),recipient,run_id)
        out=Path('sealed-output');out.mkdir(exist_ok=True)
        (out/'source.envelope.json').write_bytes(cipher)
        (out/'receipt.public.json').write_text(json.dumps({'schema':'neighbour-net-v1','runId':run_id,'ciphertextSha256':hashlib.sha256(cipher).hexdigest(),'ordersSubmitted':0}))
        Path('neighbour-net.public.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print('NEIGHBOUR_SOURCE_AND_NATIVE_RECEIPT_SEALED',flush=True)
    finally:transport.close()

def readback():
    run_id=os.environ['GITHUB_RUN_ID'];cipher=Path('sealed-output/source.envelope.json').read_bytes();p=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(p['runId']==run_id and hashlib.sha256(cipher).hexdigest()==p['ciphertextSha256'],'NEIGHBOUR_CUSTODY_SHA')
    b=json.loads(unseal_new(cipher,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run_id));original=b.pop('nativeReceipt')
    selection=native(b,'--neighbour-selection');need(selection['selectionSurvivors']==b['selectionSurvivors'],'NEIGHBOUR_SURVIVOR_PARITY')
    confirmation=native(b,'--neighbour-confirmation') if b['selectionSurvivors'] else None
    result={'selection':selection,'confirmation':confirmation,'ordersSubmitted':0,'closedConfigurations':[x['symbol'] for x in selection['results'] if not x['eligibleForConfirmation']]}
    need(result==original,'NEIGHBOUR_NATIVE_PARITY')
    result.update({'custodyParity':True,'runId':run_id,'ciphertextSha256':p['ciphertextSha256']})
    Path('neighbour-net.public.json').write_text(json.dumps(result,indent=2)+'\n')
    print('AUTHENTIC_NEIGHBOUR_CUSTODY_PARITY '+json.dumps(result,sort_keys=True))

if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else run()
    except Exception as exc:
        from .guard import CaptureContractError
        print(str(exc) if isinstance(exc,CaptureContractError) and str(exc).isupper() and str(exc).replace('_','').isalnum() else 'NEIGHBOUR_NET_FAILED_DETAIL_WITHHELD')
        sys.exit(1)
