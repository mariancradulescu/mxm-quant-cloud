"""Frozen EURUSD quote-event NET study; original OAuth/custody; no orders."""
import base64, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone
from .collect import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need, decode_side
from .economic_source import _windows, _bounded_server_window
from .custody_new import checked_public
from .custody import seal_new, unseal_new

MAX_REQUESTS=8000

def reconstruct(bid,ask,t):
    """No prior unseen side imputed. Both sides must update within 2s of state."""
    from itertools import groupby
    events=sorted([(s,0,p) for s,p in bid]+[(s,1,p) for s,p in ask],key=lambda x:x[0])
    state={}
    for stamp,group in groupby(events,key=lambda x:x[0]):
        # Preserve original same-side feed ordering at equal milliseconds;
        # evaluate only after all updates at that millisecond, never by price sort.
        for _,side,p in group:state[side]=(stamp,p)
        if len(state)==2 and t<=stamp<=t+10000:
            if stamp-min(state[0][0],state[1][0])<=2000 and state[1][1]>=state[0][1]:
                return {'time':stamp,'bid':state[0][1],'ask':state[1][1]}
    return None

def native(bundle,mode):
    with tempfile.TemporaryDirectory(prefix='mxm-net-private-') as tmp:
        inp=Path(tmp)/'in.json';out=Path(tmp)/'out.json'
        inp.write_text(json.dumps(bundle,sort_keys=True));inp.chmod(0o600)
        env={k:v for k,v in os.environ.items() if not k.startswith(('R3_','CTRADER_','MXM_V4_'))}
        r=subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(inp),str(out),mode],
                         env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        need(r.returncode==0 and out.exists(),'INTRADAY_NATIVE_FAILED')
        return json.loads(out.read_text())

def run():
    run_id=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run_id)
    transport=StdlibCTraderTransport();raw=[]
    def request(q,cls):
        need(len(raw)<MAX_REQUESTS,'INTRADAY_REQUEST_BUDGET')
        r=transport.request(q)
        need(isinstance(r,cls) and r.IsInitialized() and r.ctidTraderAccountId==account,'INTRADAY_RESPONSE_BINDING')
        raw.append({'type':type(r).__name__,'protobuf':base64.b64encode(r.SerializeToString()).decode()})
        return r
    try:
        account=authenticate(transport)
        trader=request(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes).trader
        need(trader.HasField('brokerName') and 'pepperstone' in trader.brokerName.casefold(),'BROKER_BINDING')
        assets=request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        currencies={a.assetId:a.name for a in assets.asset}
        need(currencies.get(trader.depositAssetId)=='EUR','EUR_ACCOUNT_REQUIRED')
        symbols=request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        candidates=[s for s in symbols.symbol if s.symbolName=='EURUSD' and s.enabled]
        need(len(candidates)==1,'EURUSD_NOT_UNIQUE_ENABLED');s=candidates[0]
        need(currencies.get(s.baseAssetId)=='EUR' and currencies.get(s.quoteAssetId)=='USD','EURUSD_ASSETS')
        detail=request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[s.symbolId]),m.ProtoOASymbolByIdRes)
        need(len(detail.symbol)==1 and detail.symbol[0].symbolId==s.symbolId,'SYMBOL_BINDING');contract=detail.symbol[0]
        required=('minVolume','stepVolume','maxVolume','lotSize','preciseTradingCommissionRate','preciseMinCommission','pnlConversionFeeRate','swapLong','swapShort','swapCalculationType')
        need(all(contract.HasField(f) for f in required),'NET_CONTRACT_FIELDS_MISSING')
        c={f:getattr(contract,f) for f in required}
        # Enum/currency defaults below are official protobuf-defined defaults, not cost zero assumptions.
        for f in ('commissionType','minCommissionType','minCommissionAsset'):c[f]=getattr(contract,f)
        for f in ('swapPeriod','swapTime','skipSWAPPeriods'):
            c[f]=getattr(contract,f) if contract.HasField(f) else None
        margin=request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=s.symbolId,volume=[contract.minVolume]),m.ProtoOAExpectedMarginRes)
        need(margin.HasField('moneyDigits') and len(margin.margin)==1 and margin.margin[0].volume==contract.minVolume,'EXPECTED_MARGIN_BINDING')
        current_margin=max(margin.margin[0].buyMargin,margin.margin[0].sellMargin)/(10**margin.moneyDigits)
        need(trader.HasField('leverageInCents') and trader.leverageInCents>0 and contract.HasField('leverageId'),'LEVERAGE_MISSING')
        dynamic=request(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=account,leverageId=contract.leverageId),m.ProtoOAGetDynamicLeverageByIDRes)
        need(dynamic.leverage.leverageId==contract.leverageId and len(dynamic.leverage.tiers)>0,'DYNAMIC_LEVERAGE_BINDING')
        leverage=min(trader.leverageInCents/100,dynamic.leverage.tiers[0].leverage)
        # Current expected margin includes broker tiering; the account leverage
        # supplies a separate historical scenario floor, not an invented schedule.
        stop=int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000)
        start=stop-370*86400000;rows={}
        def window(lo,hi,depth=0):
            need(depth<20,'INTRADAY_PAGE_DEPTH')
            r=request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=s.symbolId,period=e.M15,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
            need(r.period==e.M15 and (not r.HasField('symbolId') or r.symbolId==s.symbolId) and r.HasField('hasMore'),'BAR_RESPONSE_BINDING')
            if r.hasMore:
                need(hi>lo,'INTRADAY_PAGE_UNRESOLVABLE');mid=(hi+lo)//2
                return window(lo,mid,depth+1)+window(mid+1,hi,depth+1)
            return _bounded_server_window(r.trendbar,lo,hi,15)
        for lo,hi in _windows(start,stop,4):
            for row in window(lo,hi):
                need(row[0] not in rows,'INTRADAY_DUPLICATE_BAR')
                if row[0]+900000<=stop:rows[row[0]]={'t':row[0],'o':row[2],'h':row[3],'l':row[4],'c':row[5]}
        bundle={'schema':'mxm-intraday-net-v1','source':'Pepperstone-cTrader-OpenAPI','readOnly':True,
                'start':start,'end':stop,'contract':c,'currentMarginEur':current_margin,
                'conservativeLeverage':leverage,'bars':[rows[k] for k in sorted(rows)],'quotes':{}}
        plan=native(bundle,'--intraday-plan')
        times=sorted({p[k] for p in plan for k in ('Entry','Exit')})
        need(2*len(times)+len(raw)<MAX_REQUESTS,'INTRADAY_PLAN_EXCEEDS_BUDGET')
        print('INTRADAY_SOURCE_ADMITTED_AND_NATIVE_PLAN_FROZEN '+json.dumps({'bars':len(rows),'proposals':len(plan),'quoteEvents':len(times)}),flush=True)
        for index,t in enumerate(times):
            sides=[]
            for side in (e.BID,e.ASK):
                r=request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=s.symbolId,type=side,fromTimestamp=t,toTimestamp=t+10000),m.ProtoOAGetTickDataRes)
                need(r.HasField('hasMore'),'TICK_PAGE_UNKNOWN')
                sides.append(None if r.hasMore else decode_side(r.tickData,t,t+10000))
            bundle['quotes'][str(t)]=reconstruct(*sides,t) if all(x is not None for x in sides) else None
            if index%100==0:print('INTRADAY_AUTHENTIC_QUOTE_PROGRESS '+str(index)+'/'+str(len(times)),flush=True)
        result=native(bundle,'--intraday-net')
        bundle['raw']=raw;bundle['nativeReceipt']=result
        data=json.dumps(bundle,sort_keys=True).encode();cipher=seal_new(data,recipient,run_id)
        output=Path('sealed-output');output.mkdir(exist_ok=True)
        (output/'source.envelope.json').write_bytes(cipher)
        (output/'receipt.public.json').write_text(json.dumps({'schema':'intraday-net-v1','runId':run_id,'ciphertextSha256':hashlib.sha256(cipher).hexdigest(),'ordersSubmitted':0}))
        Path('intraday-net.public.json').write_text(json.dumps(result,indent=2)+'\n')
        print('AUTHENTIC_CONDITIONAL_NET_RESULT '+json.dumps(result,sort_keys=True),flush=True)
    finally:transport.close()

def readback():
    run_id=os.environ['GITHUB_RUN_ID'];cipher=Path('sealed-output/source.envelope.json').read_bytes()
    public=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(hashlib.sha256(cipher).hexdigest()==public['ciphertextSha256'] and public['runId']==run_id,'NET_SOURCE_DIGEST')
    bundle=json.loads(unseal_new(cipher,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run_id))
    original=bundle.pop('nativeReceipt');result=native(bundle,'--intraday-net')
    need(result==original and result['ordersSubmitted']==0,'NET_NATIVE_PARITY')
    result['custodyParity']=True;result['ciphertextSha256']=public['ciphertextSha256'];result['runId']=run_id
    Path('intraday-net.public.json').write_text(json.dumps(result,indent=2)+'\n')
    print('AUTHENTIC_NET_CUSTODY_PARITY '+json.dumps(result,sort_keys=True))

if __name__=='__main__':
    try:
        readback() if '--readback' in sys.argv else run()
    except Exception as exc:
        from .guard import CaptureContractError
        print(str(exc) if isinstance(exc,CaptureContractError) and str(exc).isupper() and str(exc).replace('_','').isalnum() else 'INTRADAY_NET_FAILED_DETAIL_WITHHELD')
        sys.exit(1)
