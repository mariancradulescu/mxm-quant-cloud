"""MBF1: single bounded authenticated cTrader Open API multi-family source and readback.

Only historical H1 + selected BID/ASK and current contract margins. Original
account-bound SCOPE_VIEW OAuth, repository transport and v2 crypto reused.
No model selection at collection time and no orders.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from .collect import authenticate, HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars, decode_side
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .full_inventory_pipeline import _raw_record
from .csp1_cost_preflight import asof_spread
from .mbf1_research import evaluate, HOUR, WEEK

P=Path('research/mbf1_protocol.json')
SCHEMA='mxm-mbf1-authenticated-bounded-source-v1'


def need(ok,code):
    if not ok:raise ValueError(code)


def sha(data):return hashlib.sha256(data).hexdigest()


def protocol():return json.loads(P.read_text())


def windows(p):
    return [(p['startUtcMs']+i*WEEK,p['startUtcMs']+(i+1)*WEEK)
        for i in range(p['sourceWindowsWeeks'])]


def cost_clocks(p):
    return [p['startUtcMs']+w*WEEK+h*HOUR
        for w in range(p['costDevelopmentWeeks'])
        for h in p['developmentQuoteUtcWeeklyHourOffsets']]


CLASSES={
 'ProtoOATraderReq':m.ProtoOATraderRes,
 'ProtoOAAssetListReq':m.ProtoOAAssetListRes,
 'ProtoOASymbolsListReq':m.ProtoOASymbolsListRes,
 'ProtoOASymbolByIdReq':m.ProtoOASymbolByIdRes,
 'ProtoOAExpectedMarginReq':m.ProtoOAExpectedMarginRes,
 'ProtoOAGetTrendbarsReq':m.ProtoOAGetTrendbarsRes,
 'ProtoOAGetTickDataReq':m.ProtoOAGetTickDataRes
}


def wire_pairs(raw):
    pairs=[]
    for item in raw:
        need(set(item)=={'requestType','requestProtobuf','type','protobuf'} and
            item['requestType'] in CLASSES,'MBF1_RAW_RECORD_SHAPE')
        q=getattr(m,item['requestType'])();r=CLASSES[item['requestType']]()
        need(item['type']==type(r).__name__,'MBF1_RESPONSE_TYPE')
        q.ParseFromString(base64.b64decode(item['requestProtobuf'],validate=True))
        r.ParseFromString(base64.b64decode(item['protobuf'],validate=True))
        require_read_only_request(q)
        need(q.IsInitialized() and r.IsInitialized() and
             q.ctidTraderAccountId==r.ctidTraderAccountId,'MBF1_RAW_ACCOUNT')
        pairs.append((q,r))
    return pairs


def reconstruct(raw,p):
    """Independent deterministic recomputation from original paired protobuf bytes."""
    need(p['id']=='MBF1' and p['status']=='REGISTERED_UNSCORED' and
         p['universe']==['GBPJPY','ETHUSD','HK50','JPN225-F'] and
         p['holdingHorizonsHours']==[2,4] and
         p['sourceWindowsWeeks']==52 and p['costDevelopmentWeeks']==13 and
         p['developmentQuoteUtcWeeklyHourOffsets']==[3,51,156] and
         p['endUtcMs']-p['startUtcMs']==52*WEEK,'MBF1_PROTOCOL_DRIFT')
    pairs=wire_pairs(raw)
    expected=(3+2*len(p['universe'])+len(windows(p))*len(p['universe'])+
        len(cost_clocks(p))*len(p['universe'])*2)
    need(expected==p['sourceRequestCount']==531 and len(pairs)==expected and
         len(pairs)<=p['maxRequests'],'MBF1_REQUEST_GRID')
    (tq,tr),(aq,ar),(lq,lr)=pairs[:3]
    need(type(tq) is m.ProtoOATraderReq and type(tr) is m.ProtoOATraderRes and
         type(aq) is m.ProtoOAAssetListReq and type(ar) is m.ProtoOAAssetListRes and
         type(lq) is m.ProtoOASymbolsListReq and type(lr) is m.ProtoOASymbolsListRes,
         'MBF1_HEADER')
    account=int(tr.ctidTraderAccountId)
    fp=sha(('ctrader-account:'+str(account)).encode('ascii'))
    need(sha(fp.encode('ascii'))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and
         all(q.ctidTraderAccountId==account for q,r in pairs),'MBF1_ORIGINAL_ACCOUNT')
    assets={a.assetId:a.name for a in ar.asset}
    need(tr.trader.HasField('brokerName') and
         'pepperstone' in tr.trader.brokerName.casefold() and
         assets.get(tr.trader.depositAssetId)=='EUR','MBF1_PEPPERSTONE_EUR')
    need(lq.HasField('includeArchivedSymbols') and not lq.includeArchivedSymbols,
         'MBF1_ARCHIVED_ROSTER')
    listing={s.symbolName:s for s in lr.symbol if s.enabled}
    need(all(s in listing for s in p['universe']),'MBF1_NOT_CURRENTLY_VISIBLE')
    ids={};margins={};terms={};idx=3
    for symbol in p['universe']:
        sid=int(listing[symbol].symbolId);ids[symbol]=sid
        dq,dr=pairs[idx];mq,mr=pairs[idx+1];idx+=2
        need(type(dq) is m.ProtoOASymbolByIdReq and
            list(dq.symbolId)==[sid] and len(dr.symbol)==1 and
            dr.symbol[0].symbolId==sid,'MBF1_CONTRACT_ID')
        c=dr.symbol[0]
        need(c.HasField('minVolume') and c.minVolume>0 and
             c.HasField('stepVolume') and c.stepVolume>0 and
             c.HasField('maxVolume') and c.maxVolume>=c.minVolume and
             int(c.tradingMode)==0,'MBF1_CONTRACT_INVALID')
        need(type(mq) is m.ProtoOAExpectedMarginReq and
             mq.symbolId==sid and list(mq.volume)==[c.minVolume] and
             mr.HasField('moneyDigits') and mr.moneyDigits<=12 and
             len(mr.margin)==1 and mr.margin[0].volume==c.minVolume,
             'MBF1_MARGIN_REQUEST_BINDING')
        buy=int(mr.margin[0].buyMargin);sell=int(mr.margin[0].sellMargin)
        need(buy>=0 and sell>=0,'MBF1_MARGIN_INVALID')
        margins[symbol]=float(Decimal(max(buy,sell))/(Decimal(10)**mr.moneyDigits))
        terms[symbol]={'minUnits':str(Decimal(c.minVolume)/100),
            'currentMinimumMarginEur':str(margins[symbol]),
            'preciseCommissionWirePresent':c.HasField('preciseTradingCommissionRate'),
            'swapLongWirePresent':c.HasField('swapLong'),
            'swapShortWirePresent':c.HasField('swapShort'),
            'swapPeriodWirePresent':c.HasField('swapPeriod'),
            'swapTimeWirePresent':c.HasField('swapTime')}
    bars={s:{} for s in p['universe']};unusable=[]
    for lo,hi in windows(p):
        for symbol in p['universe']:
            q,r=pairs[idx];idx+=1
            need(type(q) is m.ProtoOAGetTrendbarsReq and
                 q.symbolId==ids[symbol] and q.period==e.H1 and
                 q.fromTimestamp==lo and q.toTimestamp==hi and
                 r.period==e.H1 and r.HasField('hasMore') and
                 (not r.HasField('symbolId') or r.symbolId==ids[symbol]),
                 'MBF1_BAR_WINDOW_BINDING')
            if r.hasMore:
                unusable.append({'symbol':symbol,'start':lo,'reason':'HISTORY_PAGE_TRUNCATED'})
                continue
            for row in decode_bars(r.trendbar,lo-HOUR,hi+HOUR,60):
                if lo<=row[0] and row[1]<=hi:
                    timestamp=int(row[1]);close=int(row[5])
                    need(timestamp not in bars[symbol] or bars[symbol][timestamp]==close,
                         'MBF1_CONFLICTING_BAR')
                    bars[symbol][timestamp]=close
    samples={s:[] for s in p['universe']};failures={s:{} for s in p['universe']}
    for clock in cost_clocks(p):
        for symbol in p['universe']:
            sides={};complete=True
            for side in (e.BID,e.ASK):
                q,r=pairs[idx];idx+=1
                need(type(q) is m.ProtoOAGetTickDataReq and
                    q.symbolId==ids[symbol] and q.type==side and
                    q.fromTimestamp==clock-p['tickWindowBeforeClockMs'] and
                    q.toTimestamp==clock and r.HasField('hasMore'),
                    'MBF1_QUOTE_WINDOW_BINDING')
                if r.hasMore:
                    complete=False;sides[side]=[]
                else:
                    sides[side]=decode_side(r.tickData,
                        clock-p['tickWindowBeforeClockMs'],clock)
            q=asof_spread(sides[e.BID],sides[e.ASK],clock,
                p['maximumQuoteAgeAtClockMs'],p['maximumBidAskTimeSkewMs'],complete)
            if q['status']=='CAUSAL_PAIRED_SPREAD_OBSERVED':
                samples[symbol].append(float(q['spreadBps']))
            else:
                failures[symbol][q['status']]=failures[symbol].get(q['status'],0)+1
    need(idx==len(pairs),'MBF1_TRAILING_RAW')
    out=evaluate(bars,samples,margins,p)
    out.update(originalAccountBindingVerified=True,rawReadOnlyRequestCount=len(pairs),
        historicH1SourceWindowsTruncated=unusable,
        sourceH1CompleteBarsByInstrument={s:len(v) for s,v in bars.items()},
        rejectedQuotePairsBySymbolAndReason=failures,
        currentContractWireEvidence=terms,closedStudiesRescored=False)
    return out


def collect():
    p=protocol();run=os.environ['GITHUB_RUN_ID']
    need(not Path('docs/MBF1_AUTHENTIC_RESULT.json').exists(),'MBF1_FROZEN_RESULT_EXISTS')
    recipient=checked_public(Path('new-source-recipient'),run)
    t=StdlibCTraderTransport();raw=[]
    try:
        account=authenticate(t)
        def req(q,kind):
            need(len(raw)<p['maxRequests'],'MBF1_BROKER_BUDGET')
            require_read_only_request(q)
            r=t.request(q)
            need(type(r) is kind and r.IsInitialized() and
                 r.ctidTraderAccountId==q.ctidTraderAccountId==account,
                 'MBF1_BROKER_RESPONSE_INVALID')
            raw.append(_raw_record(q,r));return r
        req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        listed=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
            includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        listing={s.symbolName:s for s in listed.symbol if s.enabled}
        need(all(s in listing for s in p['universe']),'MBF1_MISSING_LIST_SYMBOL')
        for symbol in p['universe']:
            sid=listing[symbol].symbolId
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==sid and
                detail.symbol[0].HasField('minVolume') and
                detail.symbol[0].minVolume>0,'MBF1_CURRENT_VOLUME_MISSING')
            req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                symbolId=sid,volume=[detail.symbol[0].minVolume]),
                m.ProtoOAExpectedMarginRes)
        for lo,hi in windows(p):
            for symbol in p['universe']:
                req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                    symbolId=listing[symbol].symbolId,period=e.H1,
                    fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
        for clock in cost_clocks(p):
            for symbol in p['universe']:
                for side in (e.BID,e.ASK):
                    req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                        symbolId=listing[symbol].symbolId,type=side,
                        fromTimestamp=clock-p['tickWindowBeforeClockMs'],
                        toTimestamp=clock),m.ProtoOAGetTickDataRes)
        need(len(raw)==p['sourceRequestCount'],'MBF1_FULL_REQUEST_GRID')
        envelope=seal_new(json.dumps({'schema':SCHEMA,'runId':run,
            'protocolSha256':sha(P.read_bytes()),'raw':raw},
            sort_keys=True).encode(),recipient,run)
        dest=Path('sealed-output');dest.mkdir(exist_ok=True)
        (dest/'source.envelope.json').write_bytes(envelope)
        (dest/'receipt.public.json').write_text(json.dumps({
            'schema':SCHEMA,'runId':run,'protocolSha256':sha(P.read_bytes()),
            'ciphertextSha256':sha(envelope),'complete':True,'ordersSubmitted':0},
            sort_keys=True)+'\n')
        print('MBF1_AUTHENTIC_MULTIFAMILY_SOURCE_SEALED_UNSCORED',flush=True)
    finally:t.close()


def readback():
    p=protocol();run=os.environ['GITHUB_RUN_ID']
    ciphertext=Path('sealed-output/source.envelope.json').read_bytes()
    receipt=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(receipt['schema']==SCHEMA and receipt['runId']==run and
         receipt['protocolSha256']==sha(P.read_bytes()) and
         receipt['ciphertextSha256']==sha(ciphertext) and
         receipt['complete'] is True,'MBF1_SEALED_BINDING')
    bundle=json.loads(unseal_new(ciphertext,
        os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run))
    need(bundle['schema']==SCHEMA and bundle['runId']==run and
         bundle['protocolSha256']==sha(P.read_bytes()),'MBF1_DECRYPTED_PROTOCOL')
    result=reconstruct(bundle['raw'],p)
    result.update(sourceRunId=int(run),sourceCiphertextSha256=sha(ciphertext),
        protocolSha256=sha(P.read_bytes()),authenticatedCryptoRawReadback=True,
        readOnly=True)
    Path('mbf1.public.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('MBF1_MULTIFAMILY_AUTHENTIC_READBACK_NO_FINANCED_NET',flush=True)

if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception:
        print('MBF1_FAILED_CLOSED_DETAIL_WITHHELD',flush=True)
        raise SystemExit(1)
