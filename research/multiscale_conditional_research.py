"""New MSP1 economics on immutable custody, no broker or closed model calls."""
import base64
from bisect import bisect_right
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from decimal import Decimal as D
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as enums
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .guard import require_read_only_request
from .decode import need,decode_bars,decode_side
from .custody import unseal_new
from .portfolio_economic_source import contract_snapshot
from .portfolio_economic_replay import native,fee
P=Path('research/multiscale_conditional_protocol.json')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def recover(folder,source_run,expected_hash,expected_schema,protocol_file):
    raw=(folder/'source.envelope.json').read_bytes();receipt=json.loads((folder/'receipt.public.json').read_text())
    need(sha(raw)==expected_hash and receipt['sha256']==expected_hash and str(receipt['runId'])==str(source_run) and receipt['complete'],'MSP1_ORIGINAL_CUSTODY')
    b=json.loads(unseal_new(raw,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),str(source_run)))
    need(b['readOnly'] and b['depositCurrency']=='EUR' and b['schema']==expected_schema and
         b['protocolSha256']==sha(Path(protocol_file).read_bytes()),'MSP1_ORIGINAL_PROTOCOL')
    decoded=[]
    for x in b['raw']:
        q=getattr(m,x['requestType'])();q.ParseFromString(base64.b64decode(x['requestProtobuf']));require_read_only_request(q)
        r=getattr(m,x['type'])();r.ParseFromString(base64.b64decode(x['protobuf']))
        need(r.IsInitialized() and r.ctidTraderAccountId==q.ctidTraderAccountId,'MSP1_SOURCE_RESPONSE_BINDING');decoded.append((q,r))
    account=decoded[0][1].ctidTraderAccountId;fp=sha(f'ctrader-account:{account}'.encode())
    need(sha(fp.encode())==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and all(q.ctidTraderAccountId==account for q,r in decoded),'MSP1_ORIGINAL_ACCOUNT')
    trader=decoded[0][1].trader;assets={a.assetId:a.name for a in decoded[1][1].asset}
    listed={s.symbolName:s for s in decoded[2][1].symbol}
    need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId]=='EUR','MSP1_BROKER_EUR')
    for symbol,x in b['symbols'].items():
        q,r=decoded[x['contractRawIndex']];light=listed[symbol]
        need(type(q) is m.ProtoOASymbolByIdReq and list(q.symbolId)==[light.symbolId] and len(r.symbol)==1 and
             contract_snapshot(r.symbol[0])==x['contract'] and x['quoteAsset']==assets[light.quoteAssetId],'MSP1_CONTRACT')
        q,r=decoded[x['marginRawIndex']]
        need(type(q) is m.ProtoOAExpectedMarginReq and q.symbolId==light.symbolId and list(q.volume)==[x['contract']['minVolume']] and
             len(r.margin)==1 and r.HasField('moneyDigits') and r.margin[0].volume==q.volume[0] and
             D(x['currentMinMarginEur'])==D(max(r.margin[0].buyMargin,r.margin[0].sellMargin))/D(10)**r.moneyDigits,'MSP1_CURRENT_MARGIN')
    original=json.loads(Path(protocol_file).read_text());rebuilt={s:{} for s in b['bars']}
    for w in b['windows']:
        q,r=decoded[w['rawIndex']];lo,hi=w['range'];symbol=w['symbol']
        need(type(q) is m.ProtoOAGetTrendbarsReq and [lo,hi] in original['sourceChunks'] and q.symbolId==b['symbols'][symbol]['symbolId'] and
             q.period==enums.M5 and q.fromTimestamp==lo and q.toTimestamp==hi and r.period==enums.M5 and r.HasField('hasMore') and not r.hasMore,'MSP1_RAW_BAR_REQUEST')
        rows=decode_bars(r.trendbar,lo-300000,hi+300000,5)
        for row in rows:
            if lo<=row[0] and row[1]<=hi:
                need(row[0] not in rebuilt[symbol] or rebuilt[symbol][row[0]]==row,'MSP1_RAW_CONFLICT');rebuilt[symbol][row[0]]=row
    need({s:sorted(rows.values()) for s,rows in rebuilt.items()}==b['bars'],'MSP1_RAW_BAR_RECONSTRUCTION')
    need(sorted(map(int,b['costIndices']))==sorted(original['costClocks']),'MSP1_ALL_ORIGINAL_COST_CLOCKS')
    for t,indices in b['costIndices'].items():
        for symbol,ixs in indices.items():
            for side,ix in zip((enums.BID,enums.ASK),ixs):
                q,r=decoded[ix]
                need(type(q) is m.ProtoOAGetTickDataReq and q.symbolId==b['symbols'][symbol]['symbolId'] and q.type==side and
                     q.fromTimestamp==int(t)-2000 and q.toTimestamp==int(t)+58000 and r.HasField('hasMore'),'MSP1_RAW_COST_REQUEST')
    return b,decoded,dict(sourceRunId=source_run,ciphertextSha256=expected_hash,rawBars={s:len(v) for s,v in b['bars'].items()},
        rawAccountAndBarsReconstructed=True,closedModelsCalled=0,newBrokerRequests=0)


def past_vol(rows,at):
    ends=[x[1] for x in rows];ix=bisect_right(ends,at)
    if ix<33:return 0
    data=rows[ix-33:ix]
    return math.sqrt(sum(math.log(data[j][5]/data[j-1][5])**2 for j in range(1,33))/32)*10000


def extract_costs(b,decoded):
    windows=[];keys=[]
    def route(symbol):
        result={symbol,'EURUSD'};ccy=b['symbols'][symbol]['quoteAsset']
        if ccy in ('JPY','CAD'):result.add('USD'+ccy)
        if ccy in ('GBP','AUD'):result.add(ccy+'USD')
        return sorted(result)
    for stamp,indices in b['costIndices'].items():
        stamp=int(stamp);events=[];complete={}
        for symbol,ixs in indices.items():
            complete[symbol]=True
            for side,ix in enumerate(ixs):
                r=decoded[ix][1];complete[symbol]&=not r.hasMore
                if not r.hasMore:
                    events.extend(dict(At=t,Symbol=symbol,Side=side,Price=price) for t,price in decode_side(r.tickData,stamp-2000,stamp+58000))
        for symbol in b['bars']:
            r=route(symbol);keys.append((symbol,stamp))
            windows.append(dict(Nominal=stamp,LatencyMs=1000,SearchMs=20000,MaximumAgeMs=2000,Route=r,
                Events=[e for e in events if e['Symbol'] in r],Complete=all(complete.get(s,False) for s in r)))
    observed=native(windows,'--causal-observation-windows');output=[];coverage=[]
    for symbol in b['bars']:
        snapshots={str(t):dict(at=r['At'],quotes={q['Symbol']:dict(bid=q['Bid'],ask=q['Ask'],bidAt=q['BidAt'],askAt=q['AskAt']) for q in r['Quotes']})
                   for (s,t),r in zip(keys,observed) if s==symbol and r['At'] is not None}
        value=native(dict(schema=b['schema'],readOnly=True,depositCurrency='EUR',symbols=b['symbols'],snapshots=snapshots),'--value-portfolio-source')['Snapshots']
        x=b['symbols'][symbol];c=x['contract'];units=D(c['minVolume'])/100
        real=decoded[x['contractRawIndex']][1].symbol[0]
        trader=decoded[0][1].trader
        funding=(trader.HasField('swapFree') and not trader.swapFree and c['swapPeriod']==24 and c['swapTime'] is not None and
                 c['swapLong'] is not None and c['swapShort'] is not None and real.swapCalculationType in (0,1))
        count=0
        for nominal,point in value.items():
            if symbol not in point['Quotes']:continue
            q=point['Quotes'][symbol];bid=D(q['Bid']);ask=D(q['Ask'])
            credit=D(q['EurCreditPerQuote']);debit=D(q['EurDebitPerQuote']);reference=(credit+debit)/2
            notional=units*bid*reference
            if notional<=0:continue
            def daily_debit(swap):
                if not funding:return D(0)  # FundingKnown=false blocks cost admission; not an assumed zero.
                if real.swapCalculationType==0:
                    return max(D(0),-D(str(swap)))*D(10)**(-c['pipPosition'])*units*debit/notional*10000
                return max(D(0),-D(str(swap)))*100/D(365)
            output.append(dict(Symbol=symbol,At=point['At'],SpreadBps=(ask-bid)/bid*10000,
                CommissionBps=2*fee(q,units)/notional*10000,PastVolBps=past_vol(b['bars'][symbol],int(nominal)),
                MinimumNotionalEur=notional,CurrentMinimumMarginEur=x['currentMinMarginEur'],
                DailyFundingKnown=funding,SwapMinute=c['swapTime'] or 0,
                LongDailyDebitBps=daily_debit(c['swapLong']),ShortDailyDebitBps=daily_debit(c['swapShort']),
                ProfitConversionRate=(debit-credit)/reference))
            count+=1
        coverage.append(dict(Symbol=symbol,PlannedCostWindows=len(b['costIndices']),ObservedCompleteCostWindows=count,
            MissingCostWindows=len(b['costIndices'])-count,HistoricalTariffsVerified=False,
            StatisticalCostEstimationRequiredAtOtherClocks=True))
    return output,coverage


def main():
    need(not Path('docs/MSP1_AUTHENTIC_CONDITIONAL_RESULT.json').exists(),'MSP1_FROZEN_NO_RERUN')
    p=json.loads(P.read_text());bars=[];costs=[];audits=[];coverage=[]
    specs=[('bdp-source','mxm-bdp1-source-v1','research/portfolio_discovery_protocol.json'),
           ('aip-source','mxm-aip1-source-v1','research/auction_inventory_protocol.json')]
    for i,(folder,schema,original_protocol) in enumerate(specs):
        b,decoded,audit=recover(Path(folder),p['sourceRuns'][i],p['sourceCiphertextSha256'][i],schema,original_protocol)
        need(set(b['bars']).issubset(set(p['universe'])),'MSP1_UNIVERSE')
        bars.extend(dict(Symbol=s,Start=x[0],End=x[1],Open=x[2],High=x[3],Low=x[4],Close=x[5],Volume=x[6]) for s,rows in b['bars'].items() for x in rows)
        c,cov=extract_costs(b,decoded);costs.extend(c);coverage.extend(cov);audits.append(audit)
        print('MSP1_ORIGINAL_SOURCE_RECONSTRUCTED '+json.dumps(audit,sort_keys=True),flush=True)
    need(set(x['Symbol'] for x in bars)==set(p['universe']) and set(x['Symbol'] for x in costs)==set(p['universe']),'MSP1_ALL12_SOURCE_AND_COST_SUPPORT')
    result=native(dict(Bars=bars,Costs=costs,Start=p['start'],DevelopmentEnd=p['developmentEnd'],SelectionEnd=p['selectionEnd'],End=p['end']),'--multiscale-conditional-program')
    result.update(Protocol=p,ProtocolSha256=sha(P.read_bytes()),ExecutionRunId=int(os.environ['GITHUB_RUN_ID']),
        SourceAudit=audits,ObservedCostCoverage=coverage,RawReadbackMatched=True,NewBrokerRequests=0,
        OriginalReceiptsOrModelsChanged=False,OriginalCostObservationCount=len(costs))
    # Exact source cost observations are aggregated public context statistics,
    # not raw prices, account IDs or a claim of actual costs at other clocks.
    Path('multiscale-conditional.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    primary=[g for g in result['Groups'] if g['Variant']=='PRIMARY_ALL']
    summary=dict(ExecutionRunId=result['ExecutionRunId'],SourceBars=len(bars),Groups=result['PredictiveGroupCount'],
        ObservedCostContexts=len(costs),FollowupCandidates=result['PrimaryFollowupCandidateIds'],
        PrimaryPositiveCompleteSelectionProxyGroupsByCase=[sum(g['Selection'][c]['ConditionalNetBpsSum'] is not None and D(str(g['Selection'][c]['ConditionalNetBpsSum']))>0 for g in primary) for c in range(3)],
        GroupsAreUnfundedOverlappingDiagnostics=True,FundedNetEur=None,OrdersSubmitted=0,IndependentConfirmation=False)
    print('MSP1_CONDITIONAL_RESULT '+json.dumps(summary,sort_keys=True,default=str),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        print('MSP1_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True)
        raise SystemExit(1)
