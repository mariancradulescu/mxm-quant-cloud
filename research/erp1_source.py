"""ERP1 bounded authentic SpotCrude/SpotBrent H1 predictor: encrypted raw custody.

No closed studies or models invoked; no orders, clouds or new credentials.
All forecast scoring runs AFTER source decryption and independent raw binding.
"""
import base64,hashlib,json,os,sys
from pathlib import Path
from decimal import Decimal as D
from .collect import authenticate,HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars,decode_side
from .custody import seal_new,unseal_new
from .custody_new import checked_public
from .full_inventory_pipeline import _raw_record
from .csp1_cost_preflight import asof_spread
from .erp1_research import evaluate,HOUR,WEEK

P=Path('research/erp1_protocol.json')
SCHEMA='mxm-erp1-authenticated-source-v1'
def need(ok,code):
    if not ok:raise ValueError(code)
def sha(data):return hashlib.sha256(data).hexdigest()
def protocol():return json.loads(P.read_text())
def windows(p):
    return [(p['startUtcMs']+i*WEEK,p['startUtcMs']+(i+1)*WEEK)
       for i in range(p['sourceWindowsWeeks'])]
def clocks(p):
    return [p['startUtcMs']+i*WEEK+(24+h)*HOUR
       for i in range(26) for h in (12,16)]
CLASSES={
 'ProtoOATraderReq':m.ProtoOATraderRes,
 'ProtoOAAssetListReq':m.ProtoOAAssetListRes,
 'ProtoOASymbolsListReq':m.ProtoOASymbolsListRes,
 'ProtoOASymbolByIdReq':m.ProtoOASymbolByIdRes,
 'ProtoOAExpectedMarginReq':m.ProtoOAExpectedMarginRes,
 'ProtoOAGetTrendbarsReq':m.ProtoOAGetTrendbarsRes,
 'ProtoOAGetTickDataReq':m.ProtoOAGetTickDataRes}

def decode(raw):
    pairs=[]
    for item in raw:
        need(set(item)=={'requestType','requestProtobuf','type','protobuf'} and
           item['requestType'] in CLASSES,'ERP1_RAW_SHAPE')
        q=getattr(m,item['requestType'])()
        r=CLASSES[item['requestType']]()
        need(item['type']==type(r).__name__,'ERP1_RAW_RESPONSE_TYPE')
        q.ParseFromString(base64.b64decode(item['requestProtobuf'],validate=True))
        r.ParseFromString(base64.b64decode(item['protobuf'],validate=True))
        require_read_only_request(q)
        need(q.IsInitialized() and r.IsInitialized() and
             q.ctidTraderAccountId==r.ctidTraderAccountId,'ERP1_RAW_ACCOUNT')
        pairs.append((q,r))
    return pairs

def reconstruct(raw,p):
    need(p['id']=='ERP1' and p['status']=='REGISTERED_UNSCORED' and
      p['universe']==['SpotCrude','SpotBrent'] and
      p['endUtcMs']-p['startUtcMs']==52*WEEK and
      p['decisionHoursUtc']==[0,4,8,12,16],'ERP1_PROTOCOL_FIXED')
    pairs=decode(raw)
    expected=3+2*len(p['universe'])+len(windows(p))*len(p['universe'])+len(clocks(p))*len(p['universe'])*2
    need(len(pairs)==expected and len(pairs)<=p['maxRequests'],'ERP1_REQUEST_GRID')
    (tq,tr),(aq,ar),(lq,lr)=pairs[:3]
    need(type(tq) is m.ProtoOATraderReq and type(tr) is m.ProtoOATraderRes and
       type(aq) is m.ProtoOAAssetListReq and type(ar) is m.ProtoOAAssetListRes and
       type(lq) is m.ProtoOASymbolsListReq and type(lr) is m.ProtoOASymbolsListRes,
       'ERP1_HEADER')
    aid=int(tr.ctidTraderAccountId)
    fp=sha(('ctrader-account:'+str(aid)).encode('ascii'))
    need(sha(fp.encode('ascii'))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and
       all(q.ctidTraderAccountId==aid for q,r in pairs),'ERP1_ORIGINAL_ACCOUNT')
    assets={a.assetId:a.name for a in ar.asset}
    need(tr.trader.HasField('brokerName') and
       'pepperstone' in tr.trader.brokerName.lower() and
       assets.get(tr.trader.depositAssetId)=='EUR','ERP1_PEPPERSTONE_EUR')
    listing={s.symbolName:s for s in lr.symbol if s.enabled}
    need(all(s in listing for s in p['universe']),'ERP1_ACTIVE_SYMBOL')
    sid={};margins={};contracts={};idx=3
    for name in p['universe']:
        light=listing[name];sid[name]=int(light.symbolId)
        need(assets.get(light.quoteAssetId)=='USD','ERP1_ENERGY_USD_REQUIRED')
        dq,dr=pairs[idx];mq,mr=pairs[idx+1];idx+=2
        need(type(dq) is m.ProtoOASymbolByIdReq and
             list(dq.symbolId)==[sid[name]] and len(dr.symbol)==1 and
             dr.symbol[0].symbolId==sid[name],'ERP1_CONTRACT_BINDING')
        c=dr.symbol[0]
        need(c.HasField('minVolume') and c.minVolume>0 and
             c.HasField('stepVolume') and c.stepVolume>0 and
             c.HasField('maxVolume') and c.maxVolume>=c.minVolume and
             int(c.tradingMode)==0,'ERP1_CONTRACT_NOT_OPEN')
        need(type(mq) is m.ProtoOAExpectedMarginReq and
             mq.symbolId==sid[name] and list(mq.volume)==[c.minVolume] and
             mr.HasField('moneyDigits') and mr.moneyDigits<=12 and
             len(mr.margin)==1 and mr.margin[0].volume==c.minVolume and
             mr.margin[0].buyMargin>=0 and mr.margin[0].sellMargin>=0,
             'ERP1_MARGIN_BINDING')
        margins[name]=float(D(max(mr.margin[0].buyMargin,mr.margin[0].sellMargin))/
                            (D(10)**mr.moneyDigits))
        contracts[name]={'minUnits':str(D(c.minVolume)/100),
             'commissionWirePresent':c.HasField('preciseTradingCommissionRate'),
             'swapPeriodWirePresent':c.HasField('swapPeriod'),
             'swapTimeWirePresent':c.HasField('swapTime')}
    prices={name:{} for name in p['universe']}
    for lo,hi in windows(p):
        for name in p['universe']:
            q,r=pairs[idx];idx+=1
            need(type(q) is m.ProtoOAGetTrendbarsReq and
                 q.symbolId==sid[name] and q.period==e.H1 and
                 q.fromTimestamp==lo and q.toTimestamp==hi and
                 r.period==e.H1 and r.HasField('hasMore') and not r.hasMore and
                 (not r.HasField('symbolId') or r.symbolId==sid[name]),
                 'ERP1_H1_WINDOW_UNVERIFIED')
            rows=decode_bars(r.trendbar,lo-HOUR,hi+HOUR,60)
            for row in rows:
                if lo<=row[0] and row[1]<=hi:
                    t=int(row[1]);close=int(row[5])
                    need(t not in prices[name] or prices[name][t]==close,
                         'ERP1_DUPLICATE_CONFLICT')
                    prices[name][t]=close
    samples={name:[] for name in p['universe']};failures={}
    for clock in clocks(p):
        for name in p['universe']:
            sides={};complete=True
            for side in (e.BID,e.ASK):
                q,r=pairs[idx];idx+=1
                need(type(q) is m.ProtoOAGetTickDataReq and
                     q.symbolId==sid[name] and q.type==side and
                     q.fromTimestamp==clock-p['tickWindowBeforeClockMs'] and
                     q.toTimestamp==clock and r.HasField('hasMore'),
                     'ERP1_COST_QUOTE_WINDOW')
                if r.hasMore:complete=False;sides[side]=[]
                else:sides[side]=decode_side(r.tickData,
                       clock-p['tickWindowBeforeClockMs'],clock)
            quote=asof_spread(sides[e.BID],sides[e.ASK],clock,
                   p['maximumQuoteAgeAtClockMs'],p['maximumBidAskTimeSkewMs'],complete)
            if quote['status']=='CAUSAL_PAIRED_SPREAD_OBSERVED':
                samples[name].append(float(quote['spreadBps']))
            else: failures[quote['status']]=failures.get(quote['status'],0)+1
    need(idx==len(pairs),'ERP1_TRAILING_RAW')
    result=evaluate(prices,samples,margins,p)
    result.update(originalAccountBindingVerified=True,rawReadOnlyRequestCount=len(pairs),
        sourceH1CompleteBarsByInstrument={k:len(v) for k,v in prices.items()},
        developmentRejectedQuotePairsByReason=failures,
        currentContractWireFields=contracts,
        historicalCostsNotCertified=True,
        closedStudiesRescored=False)
    return result

def collect():
    p=protocol();run=os.environ['GITHUB_RUN_ID']
    need(not Path('docs/ERP1_AUTHENTIC_RESULT.json').exists(),'ERP1_CLOSED')
    recipient=checked_public(Path('new-source-recipient'),run)
    t=StdlibCTraderTransport();raw=[]
    try:
        aid=authenticate(t)
        def req(q,res_cls):
            need(len(raw)<p['maxRequests'],'ERP1_BROKER_REQUEST_BUDGET')
            require_read_only_request(q)
            r=t.request(q)
            need(type(r) is res_cls and r.IsInitialized() and
                r.ctidTraderAccountId==q.ctidTraderAccountId==aid,
                'ERP1_SOURCE_RESPONSE')
            raw.append(_raw_record(q,r));return r
        req(m.ProtoOATraderReq(ctidTraderAccountId=aid),m.ProtoOATraderRes)
        req(m.ProtoOAAssetListReq(ctidTraderAccountId=aid),m.ProtoOAAssetListRes)
        listed=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=aid,
             includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        listing={s.symbolName:s for s in listed.symbol if s.enabled}
        need(all(s in listing for s in p['universe']),'ERP1_MISSING_ACTIVE_SYMBOL')
        for name in p['universe']:
            sid=listing[name].symbolId
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=aid,
                 symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==sid and
                 detail.symbol[0].HasField('minVolume'),'ERP1_MIN_VOLUME')
            req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=aid,
                symbolId=sid,volume=[detail.symbol[0].minVolume]),m.ProtoOAExpectedMarginRes)
        for lo,hi in windows(p):
            for name in p['universe']:
                req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid,
                    symbolId=listing[name].symbolId,period=e.H1,
                    fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
        for clock in clocks(p):
            for name in p['universe']:
                for side in (e.BID,e.ASK):
                    req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=aid,
                        symbolId=listing[name].symbolId,type=side,
                        fromTimestamp=clock-p['tickWindowBeforeClockMs'],
                        toTimestamp=clock),m.ProtoOAGetTickDataRes)
        envelope=seal_new(json.dumps({'schema':SCHEMA,'runId':run,
             'protocolSha256':sha(P.read_bytes()),'raw':raw},
             sort_keys=True).encode(),recipient,run)
        dest=Path('sealed-output');dest.mkdir(exist_ok=True)
        (dest/'source.envelope.json').write_bytes(envelope)
        (dest/'receipt.public.json').write_text(json.dumps({
            'schema':SCHEMA,'runId':run,'protocolSha256':sha(P.read_bytes()),
            'ciphertextSha256':sha(envelope),'complete':True,'ordersSubmitted':0},
             sort_keys=True))
        print('ERP1_AUTHENTIC_SOURCE_SEALED_UNSCORED',flush=True)
    finally:t.close()

def readback():
    p=protocol();run=os.environ['GITHUB_RUN_ID']
    ciphertext=Path('sealed-output/source.envelope.json').read_bytes()
    receipt=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(receipt['schema']==SCHEMA and receipt['runId']==run and
         receipt['protocolSha256']==sha(P.read_bytes()) and
         receipt['ciphertextSha256']==sha(ciphertext) and
         receipt['complete'] is True,'ERP1_SEALED_RECEIPT')
    plaintext=json.loads(unseal_new(ciphertext,
          os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run))
    need(plaintext['schema']==SCHEMA and plaintext['runId']==run and
         plaintext['protocolSha256']==sha(P.read_bytes()),
         'ERP1_DECRYPTED_PROTOCOL')
    result=reconstruct(plaintext['raw'],p)
    result.update(sourceRunId=int(run),sourceCiphertextSha256=sha(ciphertext),
       protocolSha256=sha(P.read_bytes()),authenticatedCryptoRawReadback=True,
       readOnly=True)
    Path('erp1.public.json').write_text(json.dumps(result,sort_keys=True,indent=2))
    print('ERP1_CAUSAL_PREDICTIVE_READBACK_COMPLETE_NO_FINANCED_NET',flush=True)

if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception:
        print('ERP1_FAILED_CLOSED_DETAIL_WITHHELD',flush=True)
        raise SystemExit(1)
