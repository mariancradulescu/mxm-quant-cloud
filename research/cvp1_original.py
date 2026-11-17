"""CVP1 distinct original multi-asset/multiframe source; no closed policy calls."""
import base64,hashlib,json,os,subprocess,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars,decode_side
from .native_original_openapi_product_replay import contract
from .custody import seal_new
from .custody_new import checked_public
DAY=86400000
START=int(datetime(2026,5,4,tzinfo=timezone.utc).timestamp()*1000)
END=START+84*DAY
FRAMES=[('M1',1,3),('M5',5,4),('M15',15,5),('M30',30,8),('H1',60,12),('H4',240,80),('D1',1440,100)]
PROTOCOL=Path('research/CVP1_FROZEN_CONTEXT_CONTINUATION_20261117.md')
def need(ok,code):
    if not ok:raise ValueError('CVP1_'+code)
def main():
    run=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-recipient-output'),run)
    out=Path('cvp1-encrypted');out.mkdir(exist_ok=True)
    public=Path('cvp1-public');public.mkdir(exist_ok=True)
    report=dict(Study='CVP1',OriginalRun=run,ProtocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        Requests=0,SourceChunks=[],Counts={},OrdersSubmitted=0,CloudActivated=False,Qualified=False,IndependentConfirmation=False)
    counter=0;raw=[];transport=StdlibCTraderTransport()
    def save():
        report['Requests']=counter;(public/'source.json').write_text(json.dumps(report,indent=2)+'\n')
    def seal(name):
        payload=json.dumps(raw,separators=(',',':')).encode();cipher=seal_new(payload,recipient,run)
        (out/(name+'.enc')).write_bytes(cipher)
        report['SourceChunks'].append(dict(Name=name,PlainSha256=hashlib.sha256(payload).hexdigest(),CipherSha256=hashlib.sha256(cipher).hexdigest(),Responses=len(raw)))
        raw.clear();save()
    try:
        account=authenticate(transport)
        def req(q,klass,historical=False):
            nonlocal counter
            need(counter<10000,'REQUEST_BUDGET');require_read_only_request(q)
            if historical:time.sleep(.22)
            res=transport.request(q);counter+=1
            raw.append(dict(RequestType=type(q).__name__,ResponseType=type(res).__name__,Request=base64.b64encode(q.SerializeToString()).decode(),Response=base64.b64encode(res.SerializeToString()).decode()))
            if klass is m.ProtoOAGetTickDataRes and type(res) is m.ProtoOAErrorRes and res.errorCode=='NO_QUOTES' and res.ctidTraderAccountId==account:return klass(ctidTraderAccountId=account,hasMore=False)
            need(type(res) is klass and res.IsInitialized() and res.ctidTraderAccountId==account,'ORIGINAL_RESPONSE_BINDING');return res
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes);assets={x.assetId:x.name for x in assets.asset}
        need('pepperstone' in trader.trader.brokerName.lower() and assets[trader.trader.depositAssetId]=='EUR','BROKER_EUR')
        roster=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        roster={x.symbolName:x for x in roster.symbol if x.enabled}
        tape=dict(Start=START,End=END,Markets=[])
        for name in ('EURUSD','GBPUSD','AUDUSD'):
            need(name in roster and assets[roster[name].quoteAssetId]=='USD','SOURCE_ROLE_MISSING_'+name)
            sid=roster[name].symbolId
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==sid,'CONTRACT_BINDING')
            c=detail.symbol[0]
            need(c.tradingMode==0 and c.enableShortSelling and c.HasField('preciseTradingCommissionRate') and c.HasField('preciseMinCommission'),'CURRENT_COST_TERMS')
            mr=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
            need(len(mr.margin)==1 and mr.margin[0].volume==c.minVolume and mr.HasField('moneyDigits'),'DIRECTION_MARGIN')
            margin=D(max(mr.margin[0].buyMargin,mr.margin[0].sellMargin))/D(10)**mr.moneyDigits
            need(0<margin<300,'MINIMUM_FUNDING_'+name)
            terms=contract(name,c,'USD',int(time.time()*1000))
            need(terms['SwapTimeUtcMinute'] is not None and terms['SwapPeriodHours'] is not None and terms['SwapPeriodHours']>=24 and not 479<=terms['SwapTimeUtcMinute']<=665,'FUNDING_SCHEDULE_'+name)
            market=dict(Name=name,Contract=terms,MinMargin=str(margin),TickSize=str(D(10)**-c.digits),Frames={},Days=[])
            report['Counts'][name]={};seal(name+'-terms')
            for frame,minutes,warmup in FRAMES:
                rows={};step=minutes*60000*500
                for lo in range(START-warmup*DAY,END,step):
                    hi=min(lo+step,END)
                    res=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=sid,period=getattr(e,frame),fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes,True)
                    need(res.period==getattr(e,frame) and not res.hasMore,'BAR_TRUNCATION_'+name+'_'+frame)
                    for row in decode_bars(res.trendbar,lo-minutes*60000,hi,minutes):
                        need(row[0] not in rows or rows[row[0]]==row,'BAR_CONFLICT');rows[row[0]]=row
                market['Frames'][frame]=sorted(rows.values());report['Counts'][name][frame]=len(rows)
                need(len(rows)>=64,'FEATURE_WARMUP_'+name+'_'+frame)
                seal(name+'-'+frame);print('CVP1_BARS',name,frame,len(rows),flush=True)
            def ticks(side,lo,hi):
                res=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=side,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTickDataRes,True)
                if res.hasMore:
                    need(hi>lo,'SINGLE_MILLISECOND_TRUNCATED');mid=(lo+hi)//2
                    return ticks(side,lo,mid)+ticks(side,mid+1,hi)
                return decode_side(res.tickData,lo,hi)
            for d in range(START,END,DAY):
                if datetime.fromtimestamp(d/1000,timezone.utc).weekday()>=5:continue
                day=dict(Start=d,Bid=[],Ask=[])
                for lo in range(d+479*60000,d+665*60000,30*60000):
                    hi=min(lo+30*60000-1,d+665*60000-1)
                    day['Bid']+=ticks(e.BID,lo,hi);day['Ask']+=ticks(e.ASK,lo,hi)
                market['Days'].append(day);seal(name+'-'+str(d))
                print('CVP1_TICKS_DAY',name,len(market['Days']),len(day['Bid']),len(day['Ask']),flush=True)
            report['Counts'][name]['BidTicks']=sum(len(d['Bid']) for d in market['Days'])
            report['Counts'][name]['AskTicks']=sum(len(d['Ask']) for d in market['Days'])
            tape['Markets'].append(market)
        encoded=json.dumps(tape,separators=(',',':')).encode();cipher=seal_new(encoded,recipient,run)
        (out/'native-tape.enc').write_bytes(cipher)
        report['NativeTapeSha256']=hashlib.sha256(encoded).hexdigest();report['NativeCipherSha256']=hashlib.sha256(cipher).hexdigest();save()
        with tempfile.TemporaryDirectory(prefix='cvp1-protected-') as td:
            inp=Path(td)/'native.json';inp.write_bytes(encoded);inp.chmod(0o600)
            proc=subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(inp),str(public/'economic.json'),'--native-cvp1'],capture_output=True,text=True,timeout=3600)
            if proc.returncode:print('CVP1_NATIVE_FAILURE',proc.stderr[-2500:],flush=True)
            need(proc.returncode==0,'NATIVE_FINANCE_FAILURE')
        report['Completed']=True;save()
    except Exception as exc:
        report['FailureType']=type(exc).__name__
        if raw:seal('failure-checkpoint')
        save();raise
    finally:transport.close()
if __name__=='__main__':main()
