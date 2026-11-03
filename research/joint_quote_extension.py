"""Bounded read-only execution-evidence extension, not a trading experiment.

Frozen before retrieval: ALL six existing assets, 2026-06-02 09/13 UTC,
1s modeled latency, <=10s search and <=2s bid/ask as-of age, no replacement
of absent quotes, max60 authenticated requests. Dates are development-exposed;
this collection cannot create independent confirmation or portfolio NET.
"""
import base64, hashlib, json, os, sys
from decimal import Decimal as D
from pathlib import Path
from .collect import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need, decode_side
from .economic_source import snapshot_contract, UNIVERSE
from .intraday_net import reconstruct
from .custody import seal_new, unseal_new
from .custody_new import checked_public

CLOCKS=(1780390800000,1780405200000)
SCHEMA='mxm-joint-quote-evidence-extension-v1'


def audit(b):
    need(b['schema']==SCHEMA and b['source']=='Pepperstone-cTrader-OpenAPI' and b['readOnly'] is True,
         'JOINT_QUOTE_SOURCE_BINDING')
    need(b['clocks']==list(CLOCKS) and sorted(b['symbols'])==sorted(UNIVERSE),'JOINT_QUOTE_FIXED_UNIVERSE_CLOCKS')
    rows=[]
    for symbol in UNIVERSE:
        c=b['symbols'][symbol]; quotes=[]
        for t in CLOCKS:
            event=c['quotes'][str(t)]
            sides=[]
            need(len(event['rawIndices'])==2,'JOINT_QUOTE_SIDE_COUNT')
            for side,i in zip((e.BID,e.ASK),event['rawIndices']):
                request=m.ProtoOAGetTickDataReq();request.ParseFromString(base64.b64decode(b['raw'][i]['requestProtobuf']))
                need(request.IsInitialized() and request.symbolId==c['symbolId'] and request.type==side and
                     request.fromTimestamp==t+1000 and request.toTimestamp==t+11000,'JOINT_QUOTE_REQUEST_BINDING')
                r=m.ProtoOAGetTickDataRes();r.ParseFromString(base64.b64decode(b['raw'][i]['protobuf']))
                need(r.IsInitialized() and r.HasField('hasMore'),'JOINT_TICK_PAGE_DECLARATION')
                sides.append(None if r.hasMore else decode_side(r.tickData,t+1000,t+11000))
            observed=reconstruct(*sides,t+1000) if all(x is not None for x in sides) else None
            need(observed==event['observed'],'JOINT_QUOTE_RAW_RECONCILIATION')
            quotes.append(observed)
        margin_request=m.ProtoOAExpectedMarginReq()
        margin_request.ParseFromString(base64.b64decode(b['raw'][c['marginRawIndex']]['requestProtobuf']))
        need(margin_request.symbolId==c['symbolId'] and list(margin_request.volume)==[c['contract']['minVolume']],
             'JOINT_MARGIN_REQUEST_BINDING')
        margin_raw=m.ProtoOAExpectedMarginRes()
        margin_raw.ParseFromString(base64.b64decode(b['raw'][c['marginRawIndex']]['protobuf']))
        need(margin_raw.HasField('moneyDigits') and len(margin_raw.margin)==1 and
             margin_raw.margin[0].volume==c['contract']['minVolume'],'JOINT_MARGIN_MIN_VOLUME_BINDING')
        margin=D(max(margin_raw.margin[0].buyMargin,margin_raw.margin[0].sellMargin))/D(10)**margin_raw.moneyDigits
        need(margin>0,'JOINT_MARGIN_POSITIVE')
        rows.append(dict(symbol=symbol,quoteEventsRequested=2,quoteEventsAvailable=sum(q is not None for q in quotes),
            entryExitQuotePairAvailable=all(q is not None for q in quotes),currentMinimumMarginEur=str(margin),
            currentMinimumMarginAloneBelowInitialCapital=margin<D(200),
            historicalMarginConfirmed=False,historicalTariffConfirmed=False,
            minVolumeAndStepKnown=all(c['contract'].get(k) is not None for k in ['minVolume','stepVolume','maxVolume']),
            missingJointRiskSamples=True))
    synchronization=[]
    for t in CLOCKS:
        qs=[b['symbols'][s]['quotes'][str(t)]['observed'] for s in UNIVERSE]
        synchronization.append(dict(clock=t,allSixPresent=all(q is not None for q in qs),
            maxObservedTimeSkewMs=max(q['time'] for q in qs)-min(q['time'] for q in qs) if all(q is not None for q in qs) else None))
    return dict(schema=SCHEMA,source='Pepperstone-cTrader-OpenAPI',readOnly=True,clocks=list(CLOCKS),
        universe=list(UNIVERSE),contracts=rows,synchronization=synchronization,
        brokerEvidenceRequestsExcludingOAuth=len(b['raw']),maxRequests=60,
        sourcePurpose='EXECUTION_EVIDENCE_ACCESS_FEASIBILITY_NOT_MODEL_SCORING',
        historicalCalendarIndependent=False,brokerNetEur=None,fundedReplay=False,hard21Proven=False,
        economicQualification=False,ordersSubmitted=0,
        remaining='Full opportunity calendar quotes and synchronized holding marks, historical costs/FX/financing, causal joint EUR-risk estimation and independent portfolio validation')


def collect():
    run=os.environ['GITHUB_RUN_ID'];pub=checked_public(Path('new-source-recipient'),run)
    raw=[];transport=StdlibCTraderTransport()
    def req(q,kind):
        need(len(raw)<60,'JOINT_QUOTE_REQUEST_BUDGET')
        r=transport.request(q)
        need(isinstance(r,kind) and r.IsInitialized() and r.ctidTraderAccountId==account,'JOINT_QUOTE_RESPONSE_ACCOUNT_BINDING')
        raw.append(dict(type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode(),
                        requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode()))
        return r,len(raw)-1
    try:
        account=authenticate(transport)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)[0].trader
        need(trader.HasField('brokerName') and 'pepperstone' in trader.brokerName.lower(),'JOINT_QUOTE_PEPPERSTONE')
        assets={a.assetId:a.name for a in req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)[0].asset}
        need(assets.get(trader.depositAssetId)=='EUR','JOINT_QUOTE_EUR_ACCOUNT')
        symbols={s.symbolName:s for s in req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)[0].symbol if s.enabled}
        need(all(s in symbols for s in UNIVERSE),'JOINT_QUOTE_UNIVERSE_INCOMPLETE')
        bundle=dict(schema=SCHEMA,source='Pepperstone-cTrader-OpenAPI',readOnly=True,clocks=list(CLOCKS),symbols={},raw=raw)
        for name in UNIVERSE:
            symbol=symbols[name]
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[symbol.symbolId]),m.ProtoOASymbolByIdRes)[0]
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==symbol.symbolId and detail.symbol[0].HasField('minVolume'),'JOINT_QUOTE_SYMBOL_BINDING')
            contract=detail.symbol[0];margin,index=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=symbol.symbolId,volume=[contract.minVolume]),m.ProtoOAExpectedMarginRes)
            row=dict(symbolId=symbol.symbolId,contract=snapshot_contract(contract),marginRawIndex=index,quotes={})
            for t in CLOCKS:
                indices=[];sides=[]
                for side in (e.BID,e.ASK):
                    r,i=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=symbol.symbolId,type=side,fromTimestamp=t+1000,toTimestamp=t+11000),m.ProtoOAGetTickDataRes)
                    need(r.HasField('hasMore'),'JOINT_QUOTE_PAGINATION_MISSING')
                    indices.append(i);sides.append(None if r.hasMore else decode_side(r.tickData,t+1000,t+11000))
                observed=reconstruct(*sides,t+1000) if all(x is not None for x in sides) else None
                row['quotes'][str(t)]=dict(rawIndices=indices,observed=observed)
            bundle['symbols'][name]=row
        bundle['receipt']=audit(bundle)
        cipher=seal_new(json.dumps(bundle,sort_keys=True).encode(),pub,run)
        dest=Path('sealed-output');dest.mkdir(exist_ok=True)
        (dest/'source.envelope.json').write_bytes(cipher)
        (dest/'receipt.public.json').write_text(json.dumps(dict(schema=SCHEMA,runId=run,sha256=hashlib.sha256(cipher).hexdigest(),ordersSubmitted=0)))
        print('JOINT_QUOTE_EXTENSION_SEALED',flush=True)
    finally:
        transport.close()


def readback():
    run=os.environ['GITHUB_RUN_ID'];raw=Path('sealed-output/source.envelope.json').read_bytes()
    receipt=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(receipt['runId']==run and receipt['schema']==SCHEMA and receipt['sha256']==hashlib.sha256(raw).hexdigest(),'JOINT_QUOTE_CUSTODY_BINDING')
    b=json.loads(unseal_new(raw,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run))
    result=audit(b);need(result==b['receipt'],'JOINT_QUOTE_INDEPENDENT_READBACK_PARITY')
    baseline_raw=Path('baseline-source/source.envelope.json').read_bytes()
    baseline_pub=json.loads(Path('baseline-source/receipt.public.json').read_text())
    expected='50e40f62156f598d715d6052e466ae7ef77b9bc39117cad37472c7f0f505e61d'
    need(hashlib.sha256(baseline_raw).hexdigest()==expected and baseline_pub['ciphertextSha256']==expected,
         'JOINT_BASELINE_SOURCE_HASH')
    baseline=json.loads(unseal_new(baseline_raw,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),'41476636915'))
    result['originalH4IntervalGeometryMatchedSymbols']=[s for s in UNIVERSE if
        any(x['symbol']==s and x['resolution']=='H4' and x['availableTime']==CLOCKS[0] for x in baseline['bars']) and
        any(x['symbol']==s and x['resolution']=='H4' and x['openTime']==CLOCKS[0] and x['availableTime']==CLOCKS[1] for x in baseline['bars'])]
    result['originalSourceCiphertextSha256']=expected
    result['originalFrozenModelReplayed']=False
    result.update(sourceRunId=int(run),sourceCiphertextSha256=receipt['sha256'],independentCustodyReadbackMatched=True)
    Path('joint-quote-evidence.public.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('AUTHENTIC_JOINT_QUOTE_EXTENSION '+json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    try:
        readback() if '--readback' in sys.argv else collect()
    except Exception:
        print('JOINT_QUOTE_EXTENSION_FAILED_CLOSED_DETAILS_WITHHELD',flush=True)
        raise SystemExit(1)
