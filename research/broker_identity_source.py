"""Read-only current inventory + bounded order/deal evidence. No trade requests."""
import base64,hashlib,json,os,sys,time
from pathlib import Path
from decimal import Decimal as D
from .collect import authenticate,HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import need
from .custody import seal_new,unseal_new
from .custody_new import checked_public
from .portfolio_economic_replay import native


def decode(b):
    decoded=[]
    for row in b['raw']:
        q=getattr(m,row['requestType'])();q.ParseFromString(base64.b64decode(row['requestProtobuf']));require_read_only_request(q)
        r=getattr(m,row['type'])();r.ParseFromString(base64.b64decode(row['protobuf']));need(r.IsInitialized() and r.ctidTraderAccountId==q.ctidTraderAccountId,'IDENTITY_RESPONSE');decoded.append((q,r))
    need(len(decoded)==5,'IDENTITY_REQUEST_COUNT');account=decoded[0][1].ctidTraderAccountId
    fp=hashlib.sha256(f'ctrader-account:{account}'.encode()).hexdigest();need(hashlib.sha256(fp.encode()).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and all(q.ctidTraderAccountId==account for q,r in decoded),'IDENTITY_ORIGINAL_ACCOUNT')
    trader,before,orders,deals,after=[r for q,r in decoded]
    need('pepperstone' in trader.trader.brokerName.lower(),'IDENTITY_BROKER')
    lo,hi=b['historyRange'];need(decoded[2][0].fromTimestamp==lo and decoded[2][0].toTimestamp==hi and decoded[3][0].fromTimestamp==lo and decoded[3][0].toTimestamp==hi and decoded[3][0].maxRows==1000,'IDENTITY_HISTORY_RANGE')
    statuses={1:'ACTIVE',2:'FILLED',3:'REJECTED',4:'EXPIRED',5:'CANCELLED'}
    orderRows=[]
    for o in list(orders.order)+list(after.order):
        orderRows.append(dict(OrderId=str(o.orderId),ClientIntentId=o.clientOrderId,PositionId=str(o.positionId) if o.HasField('positionId') else '',Symbol=str(o.tradeData.symbolId),Side=1 if o.tradeData.tradeSide==e.BUY else -1,
            RequestedUnits=str(D(o.tradeData.volume)/100),ExecutedUnits=str(D(o.executedVolume)/100),Closing=o.closingOrder if o.HasField('closingOrder') else None,Status=statuses.get(o.orderStatus,'UNKNOWN'),UpdatedAt=o.utcLastUpdateTimestamp if o.HasField('utcLastUpdateTimestamp') else hi))
    dealRows=[dict(DealId=str(d.dealId),OrderId=str(d.orderId),PositionId=str(d.positionId),Symbol=str(d.symbolId),Side=1 if d.tradeSide==e.BUY else -1,Units=str(D(d.filledVolume)/100),Closing=d.HasField('closePositionDetail'),At=d.executionTimestamp)
        for d in deals.deal if d.dealStatus in [e.FILLED,e.PARTIALLY_FILLED] and d.filledVolume>0]
    positions=[dict(PositionId=str(p.positionId),Symbol=str(p.tradeData.symbolId),Side=1 if p.tradeData.tradeSide==e.BUY else -1,Units=str(D(p.tradeData.volume)/100)) for p in after.position]
    snapshot=dict(AccountBinding=HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT,At=b['observedThrough'],HistoryFrom=lo,HistoryThrough=hi,
        InventoryStable=before.SerializeToString()==after.SerializeToString(),OrdersComplete=not orders.hasMore,DealsComplete=not deals.hasMore,Orders=orderRows,Deals=dealRows,Positions=positions)
    cash=str(D(trader.trader.balance)/D(10)**trader.trader.moneyDigits) if trader.trader.HasField('moneyDigits') else None
    return dict(Snapshot=snapshot,BrokerCashEur=cash)


def collect():
    run=os.environ['GITHUB_RUN_ID'];recipient=checked_public(Path('new-source-recipient'),run);t=StdlibCTraderTransport();raw=[]
    try:
        account=authenticate(t);hi=int(time.time()*1000);lo=hi-7*86400000
        requests=[m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOAReconcileReq(ctidTraderAccountId=account),m.ProtoOAOrderListReq(ctidTraderAccountId=account,fromTimestamp=lo,toTimestamp=hi),m.ProtoOADealListReq(ctidTraderAccountId=account,fromTimestamp=lo,toTimestamp=hi,maxRows=1000),m.ProtoOAReconcileReq(ctidTraderAccountId=account)]
        for q in requests:
            require_read_only_request(q);r=t.request(q);need(r.IsInitialized() and r.ctidTraderAccountId==account,'IDENTITY_AUTHENTIC_REPLY')
            raw.append(dict(requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode(),type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode()))
        b=dict(schema='mxm-broker-identity-source-v1',readOnly=True,raw=raw,historyRange=[lo,hi],observedThrough=int(time.time()*1000));decode(b)
        cipher=seal_new(json.dumps(b,sort_keys=True).encode(),recipient,run);out=Path('sealed-output');out.mkdir(exist_ok=True)
        (out/'broker-identity.envelope.json').write_bytes(cipher);(out/'broker-identity.receipt.public.json').write_text(json.dumps(dict(runId=run,sha256=hashlib.sha256(cipher).hexdigest(),requests=5,ordersSubmitted=0)))
        print('BROKER_IDENTITY_SOURCE_SEALED_REQUESTS5_ORDERS0',flush=True)
    finally:t.close()


def readback():
    run=os.environ['GITHUB_RUN_ID'];cipher=Path('sealed-output/broker-identity.envelope.json').read_bytes();receipt=json.loads(Path('sealed-output/broker-identity.receipt.public.json').read_text())
    need(receipt['runId']==run and receipt['sha256']==hashlib.sha256(cipher).hexdigest(),'IDENTITY_CUSTODY')
    b=json.loads(unseal_new(cipher,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),run));inp=decode(b)
    result=native(inp,'--broker-identity-reception');result.update(sourceRunId=int(run),sourceCiphertextSha256=receipt['sha256'],rawRepliesReconstructed=True,requestCount=5,historyRange=b['historyRange'],unfilledTerminalRecoveryProvenOnRealOrders=False,filledRecoveryProvenOnRealOrders=False,lifetimeHistoryCertified=False,cloudActivated=False)
    Path('broker-identity.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n');print('BROKER_IDENTITY_RECEIPT '+json.dumps(result,sort_keys=True,default=str),flush=True)

if __name__=='__main__':
    try:readback() if '--readback' in sys.argv else collect()
    except Exception as error:
        import traceback
        print('IDENTITY_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True);raise SystemExit(1)
