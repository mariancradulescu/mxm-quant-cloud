"""LPM1 authentic read-only M1/tick custody and native lifecycle research."""
import base64, hashlib, json, os, subprocess, tempfile, time
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal as D
from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars, decode_side
from .native_original_openapi_product_replay import contract
from .custody import seal_new
from .custody_new import checked_public

DAY=86400000
START=int(datetime(2026,8,17,tzinfo=timezone.utc).timestamp()*1000)
END=START+84*DAY
PROTOCOL=Path('research/LPM1_FROZEN_LIFECYCLE_20261117.md')
def need(ok, code):
    if not ok: raise ValueError('LPM1_'+code)
def main():
    run=os.environ['GITHUB_RUN_ID']
    recipient=checked_public(Path('new-recipient-output'),run)
    out=Path('lpm1-encrypted');out.mkdir(exist_ok=True)
    public=Path('lpm1-public');public.mkdir(exist_ok=True)
    receipt=dict(Study='LPM1',OriginalRun=run,ProtocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        OrdersSubmitted=0,CloudActivated=False,IndependentConfirmation=False,Qualified=False,
        CostClass='CONDITIONAL_COST_MODEL',Requests=0,SourceChunks=[])
    raw=[]; transport=StdlibCTraderTransport();counter=0
    def save_receipt():
        receipt['Requests']=counter
        (public/'source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def preserve(name):
        payload=json.dumps(raw,separators=(',',':')).encode()
        sealed=seal_new(payload,recipient,run)
        (out/(name+'.enc')).write_bytes(sealed)
        receipt['SourceChunks'].append(dict(Name=name,PlainSha256=hashlib.sha256(payload).hexdigest(),
            CipherSha256=hashlib.sha256(sealed).hexdigest(),Responses=len(raw)))
        raw.clear();save_receipt()
    try:
        account=authenticate(transport)
        def req(q,klass,historical=False):
            nonlocal counter
            need(counter<7000,'REQUEST_BUDGET')
            require_read_only_request(q)
            if historical:time.sleep(.22)
            res=transport.request(q);counter+=1
            raw.append(dict(RequestType=type(q).__name__,ResponseType=type(res).__name__,
                Request=base64.b64encode(q.SerializeToString()).decode(),
                Response=base64.b64encode(res.SerializeToString()).decode()))
            if klass is m.ProtoOAGetTickDataRes and type(res) is m.ProtoOAErrorRes and res.errorCode=='NO_QUOTES' and res.ctidTraderAccountId==account:
                return klass(ctidTraderAccountId=account,hasMore=False)
            need(type(res) is klass and res.IsInitialized() and res.ctidTraderAccountId==account,'RESPONSE_BINDING')
            return res
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        asset={x.assetId:x.name for x in assets.asset}
        need('pepperstone' in trader.trader.brokerName.lower() and asset[trader.trader.depositAssetId]=='EUR','BROKER_EUR')
        roster=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        names=[x for x in roster.symbol if x.symbolName=='EURUSD' and x.enabled]
        need(len(names)==1 and asset[names[0].quoteAssetId]=='USD','SYMBOL')
        sid=names[0].symbolId
        terms=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[sid]),m.ProtoOASymbolByIdRes).symbol
        need(len(terms)==1 and terms[0].symbolId==sid,'CONTRACT')
        c=terms[0]
        need(c.tradingMode==0 and c.enableShortSelling and c.HasField('preciseTradingCommissionRate') and c.HasField('preciseMinCommission'),'TARIFF')
        margin=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
        need(len(margin.margin)==1 and margin.margin[0].volume==c.minVolume and margin.HasField('moneyDigits'),'MARGIN')
        mar=D(max(margin.margin[0].buyMargin,margin.margin[0].sellMargin))/D(10)**margin.moneyDigits
        need(0<mar<300,'MINIMUM_FINANCING')
        terms=contract('EURUSD',c,'USD',int(time.time()*1000))
        # Known current intraday funding boundary, never inferred from midnight.
        need(terms['SwapTimeUtcMinute'] is not None and terms['SwapPeriodHours'] is not None and terms['SwapPeriodHours']>=24 and not 479<=terms['SwapTimeUtcMinute']<=725,'FUNDING_WINDOW_UNATTESTED')
        tape=dict(Start=START,End=END,Contract=terms,MinMargin=str(mar),TickSize=str(D(10)**-c.digits),Bars=[],Days=[])
        preserve('contract')
        for period,minutes in [(e.M1,1),(e.M5,5)]:
            history={}
            for lo in range(START-3*DAY,END,6*3600000):
                hi=min(lo+6*3600000,END)
                res=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=sid,period=period,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes,True)
                need(res.period==period and not res.hasMore,'BARS_TRUNCATED')
                for row in decode_bars(res.trendbar,lo-300000,hi,minutes):
                    need(row[0] not in history or history[row[0]]==row,'BAR_CONFLICT')
                    history[row[0]]=row
            values=sorted(history.values())
            receipt['M'+str(minutes)+'Count']=len(values)
            if minutes==5:tape['Bars']=values
            preserve('m'+str(minutes))
            print('LPM1_BARS',minutes,len(values),flush=True)
        def ticks(side,lo,hi):
            res=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=side,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTickDataRes,True)
            if res.hasMore:
                need(hi>lo,'TRUNCATED_SINGLE_MILLISECOND')
                mid=(lo+hi)//2
                return ticks(side,lo,mid)+ticks(side,mid+1,hi)
            return decode_side(res.tickData,lo,hi)
        for d in range(START,END,DAY):
            if datetime.fromtimestamp(d/1000,timezone.utc).weekday()>=5:continue
            day=dict(Start=d,Bid=[],Ask=[])
            for lo in range(d+479*60000,d+725*60000,30*60000):
                hi=min(lo+30*60000-1,d+725*60000-1)
                day['Bid']+=ticks(e.BID,lo,hi)
                day['Ask']+=ticks(e.ASK,lo,hi)
            tape['Days'].append(day)
            preserve('ticks-'+str(d))
            print('LPM1_TICKS_DAY',len(tape['Days']),len(day['Bid']),len(day['Ask']),flush=True)
        encoded=json.dumps(tape,separators=(',',':')).encode()
        (out/'native-tape.enc').write_bytes(seal_new(encoded,recipient,run))
        receipt['NativeTapeSha256']=hashlib.sha256(encoded).hexdigest()
        receipt['NativeCipherSha256']=hashlib.sha256((out/'native-tape.enc').read_bytes()).hexdigest()
        receipt['BidTicks']=sum(len(d['Bid']) for d in tape['Days'])
        receipt['AskTicks']=sum(len(d['Ask']) for d in tape['Days'])
        save_receipt()
        with tempfile.TemporaryDirectory(prefix='lpm1-protected-') as tmp:
            p=Path(tmp)/'input.json';p.write_bytes(encoded);p.chmod(0o600)
            proc=subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(p),str(public/'economic.json'),'--native-lpm1'],capture_output=True,text=True,timeout=3600)
            if proc.returncode: print('LPM1_NATIVE_FAILURE',proc.stderr[-2000:],flush=True)
            need(proc.returncode==0,'NATIVE_REPLAY_FAILURE_'+str(proc.returncode))
        receipt['Completed']=True;save_receipt()
    except Exception as exc:
        receipt['FailureType']=type(exc).__name__
        if raw:preserve('failure-checkpoint')
        save_receipt()
        raise
    finally:
        transport.close()
if __name__=='__main__':main()
