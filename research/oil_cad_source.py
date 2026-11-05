"""OCE1: read existing encrypted BDP1 M5 and ERP1 H1 *sources*, never rerun old scores.

This action requires the EXISTING protected custody private key solely to read
original archived source. No Open API transport, token, orders, or other source.
Public outputs aggregate original-bound price clocks and conditional bps only.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .custody import unseal_new
from .decode import decode_bars,decode_side
from .guard import require_read_only_request
from .oil_cad_research import evaluate,first_causal_spread,HOUR,MINUTE

P=Path('research/oil_cad_protocol.json')
B=Path('research/portfolio_discovery_protocol.json')
E=Path('research/erp1_protocol.json')

def need(ok,code):
    if not ok:raise ValueError(code)

def sha(data):return hashlib.sha256(data).hexdigest()

def _unseal(folder,source,pem):
    sealed=(Path(folder)/'source.envelope.json').read_bytes()
    need(sha(sealed)==source['sealedSha256'],'OCE1_SOURCE_CIPHER_SHA_MISMATCH')
    blob=json.loads(unseal_new(sealed,pem,str(source['runId'])))
    need(blob.get('schema') in ('mxm-erp1-authenticated-source-v1','mxm-bdp1-source-v1'), 'OCE1_SOURCE_SCHEMA_MISMATCH')
    return blob

def _pairs(raw):
    pairs=[]
    cls={
      'ProtoOATraderReq':m.ProtoOATraderRes,
      'ProtoOAAssetListReq':m.ProtoOAAssetListRes,
      'ProtoOASymbolsListReq':m.ProtoOASymbolsListRes,
      'ProtoOASymbolByIdReq':m.ProtoOASymbolByIdRes,
      'ProtoOAExpectedMarginReq':m.ProtoOAExpectedMarginRes,
      'ProtoOAGetTrendbarsReq':m.ProtoOAGetTrendbarsRes,
      'ProtoOAGetTickDataReq':m.ProtoOAGetTickDataRes
    }
    for item in raw:
        need(set(item)=={'requestType','requestProtobuf','type','protobuf'} and item['requestType'] in cls,'OCE1_RAW_SHAPE')
        q=getattr(m,item['requestType'])();r=cls[item['requestType']]()
        need(item['type']==type(r).__name__,'OCE1_RAW_TYPE')
        q.ParseFromString(base64.b64decode(item['requestProtobuf'],validate=True))
        r.ParseFromString(base64.b64decode(item['protobuf'],validate=True))
        require_read_only_request(q)
        need(q.IsInitialized() and r.IsInitialized() and q.ctidTraderAccountId==r.ctidTraderAccountId,'OCE1_RAW_ACCOUNT_ID')
        pairs.append((q,r))
    need(len(pairs)>3 and type(pairs[0][1]) is m.ProtoOATraderRes and type(pairs[2][1]) is m.ProtoOASymbolsListRes,'OCE1_RAW_HEADER')
    account=int(pairs[0][0].ctidTraderAccountId)
    fp=sha(f'ctrader-account:{account}'.encode('ascii'))
    need(sha(fp.encode('ascii'))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and all(q.ctidTraderAccountId==account for q,r in pairs),'OCE1_ORIGINAL_BINDING')
    need('pepperstone' in pairs[0][1].trader.brokerName.lower(),'OCE1_PEPPERSTONE_BROKER')
    names={a.assetId:a.name for a in pairs[1][1].asset}
    need(names.get(pairs[0][1].trader.depositAssetId)=='EUR','OCE1_DEPOSIT_NOT_EUR')
    return account,pairs

def _fx_bdp1(bundle,proto):
    need(bundle['schema']=='mxm-bdp1-source-v1' and bundle['protocolSha256']==sha(B.read_bytes()) and bundle['readOnly'] is True,'OCE1_BDP1_PROTOCOL')
    account,pairs=_pairs(bundle['raw'])
    listed={s.symbolName:s for s in pairs[2][1].symbol}
    need('USDCAD' in listed and proto['sources']['fx']['instrument']=='USDCAD' and 'USDCAD' in bundle['bars'],'OCE1_BDP1_TARGET')
    sid=listed['USDCAD'].symbolId
    latest={}
    # A source integrity spot-check is insufficient. Reconstruct EVERY USDCAD
    # source M5 row directly from its original authenticated raw protobuf.
    for q,r in pairs:
        if type(q) is m.ProtoOAGetTrendbarsReq and q.symbolId==sid:
            need(q.period==e.M5 and r.period==e.M5 and r.HasField('hasMore') and not r.hasMore,'OCE1_FX_PAGE_INCOMPLETE')
            lo,hi=int(q.fromTimestamp),int(q.toTimestamp)
            for row in decode_bars(r.trendbar,lo-5*MINUTE,hi+5*MINUTE,5):
                if lo<=row[0] and row[1]<=hi:
                    t=row[0]
                    need(t not in latest or latest[t]==row,'OCE1_FX_BAR_CONFLICT')
                    latest[t]=row
    observed=sorted(latest.values())
    need(observed==bundle['bars']['USDCAD'] and len(observed)>10000,'OCE1_FX_RAW_RECONSTRUCTION_FAILED')
    prices={int(x[1]):int(x[5]) for x in observed if int(x[5])>0}
    samples=[];fail=Counter()
    for clock, mapping in sorted(bundle['costIndices'].items(),key=lambda x:int(x[0])):
        t=int(clock)
        # Historical source calibration clocks were frozen by BDP1, and belong
        # to the first 26 development weeks; never resample by outcomes.
        need(t<proto['decisionCalendar']['developmentEndUtcMs'],'OCE1_COST_TRAIN_LEAK')
        indices=mapping.get('USDCAD')
        if not indices or len(indices)!=2:
            fail['MISSING_FX_QUOTE_SIDES']+=1;continue
        side_events=[];complete=True
        for kind,ix in zip((e.BID,e.ASK),indices):
            q,r=pairs[ix]
            need(type(q) is m.ProtoOAGetTickDataReq and q.symbolId==sid and q.type==kind and
                 q.fromTimestamp==t-2000 and q.toTimestamp==t+58000 and r.HasField('hasMore'),'OCE1_FX_COST_RAW_BINDING')
            if r.hasMore:complete=False;side_events.append([])
            else:side_events.append(decode_side(r.tickData,t-2000,t+58000))
        if not complete:
            fail['TRUNCATED']+=1;continue
        spread=first_causal_spread(*side_events,t,**{
           'window_ms':proto['quoteCost']['windowMaxMs'],
           'maximum_age':proto['quoteCost']['maxAgeMs'],
           'maximum_skew':proto['quoteCost']['maxBidAskSkewMs']})
        if spread is None:fail['NO_FRESH_SYNCHRONIZED_BID_ASK']+=1
        else:samples.append(spread)
    return account,prices,samples,fail,bundle['symbols']['USDCAD']['currentMinMarginEur']

def _oil_erp1(bundle,proto):
    need(bundle['schema']=='mxm-erp1-authenticated-source-v1' and bundle['protocolSha256']==sha(E.read_bytes()),'OCE1_ERP1_PROTOCOL')
    account,pairs=_pairs(bundle['raw'])
    listed={s.symbolName:s for s in pairs[2][1].symbol}
    need('SpotCrude' in listed and proto['sources']['oil']['instrument']=='SpotCrude','OCE1_OIL_SOURCE_SYMBOL')
    sid=listed['SpotCrude'].symbolId;rows={}
    for q,r in pairs:
        if type(q) is m.ProtoOAGetTrendbarsReq and q.symbolId==sid:
            need(q.period==e.H1 and r.period==e.H1 and r.HasField('hasMore') and not r.hasMore,'OCE1_OIL_INCOMPLETE_PAGE')
            lo,hi=q.fromTimestamp,q.toTimestamp
            for row in decode_bars(r.trendbar,lo-HOUR,hi+HOUR,60):
                if lo<=row[0] and row[1]<=hi:
                    t=int(row[1]);price=int(row[5])
                    need(t not in rows or rows[t]==price,'OCE1_OIL_BAR_CONFLICT')
                    rows[t]=price
    need(len(rows)>3000,'OCE1_OIL_SOURCE_INCOMPLETE')
    return account,rows

def run():
    p=json.loads(P.read_text())
    need(p['id']=='OCE1' and p['status']=='PREDECLARED_UNSCORED' and p['newBrokerRequests']==0,'OCE1_PROTOCOL_INVALID')
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    fx=_unseal('oce1-bdp1-source',p['sources']['fx'],key)
    oil=_unseal('oce1-erp1-source',p['sources']['oil'],key)
    a,fxprices,samples,fail,margin=_fx_bdp1(fx,p)
    b,oilprices=_oil_erp1(oil,p)
    need(a==b,'OCE1_SOURCE_CROSS_ACCOUNT_MISMATCH')
    result=evaluate(oilprices,fxprices,samples,margin,p)
    result.update(
      sourceRuns={'oil':p['sources']['oil']['runId'],'fx':p['sources']['fx']['runId']},
      originalSourceCiphertextHashesVerified=True,
      bothOriginalReadOnlySourcesBoundToSameAccount=True,
      originalFxM5BarsReconstructedFromRaw=len(fxprices),
      originalCrudeH1BarsReconstructedFromRaw=len(oilprices),
      developmentCostRejectReasons=dict(fail),
      protocolSha256=sha(P.read_bytes()),
      originalCurrencyDepositEurVerified=True,
      originalResearchCodesNotExecuted=True)
    dest=Path('oce1.public.json')
    dest.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('OCE1_ARCHIVED_SOURCE_RAW_ACCOUNT_BOUND_EXPOSED_ONLY_NO_TRADE',flush=True)
    print('OCE1_PUBLIC_RESULT_JSON_SHA256='+sha(dest.read_bytes()),flush=True)

if __name__=='__main__':
    try:run()
    except Exception:
        print('OCE1_RESEARCH_FAILED_CLOSED_DETAIL_WITHHELD',flush=True)
        sys.exit(1)
