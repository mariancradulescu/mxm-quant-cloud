"""Latest-first official ticks for the two remaining financing marks.

This is source recovery and a closed-result financial receipt. No policy replay.
"""
import argparse,json,os,subprocess
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile
from . import source_history_universe as src
from . import owner_eer1_source as eer
from . import owner_eur_recent_archive as archive
from . import owner_eur_archive_funding_2 as funding
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .custody_new import checked_public
from .decode import need,decode_side
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

PLAN=Path('research/funding_latest_prefix_settlement_1.json')
OUT=Path('latest-prefix-protected')

def latest(response,account,lo,hi):
    if type(response) is not m.ProtoOAGetTickDataRes or not response.IsInitialized() or \
            response.ctidTraderAccountId!=account or not response.HasField('hasMore'):
        return dict(Status='UNRESOLVED_RESPONSE',SearchFrom=lo,SearchThrough=hi)
    rows=decode_side(response.tickData,lo,hi)
    if not rows:return dict(Status='NO_RETURNED_TICK',SearchFrom=lo,SearchThrough=hi)
    stamp=max(x[0] for x in rows);prices={x[1] for x in rows if x[0]==stamp}
    need(response.tickData[0].timestamp==stamp,'PREFIX_NEWEST_FIRST')
    complete=not response.hasMore or min(x[0] for x in rows)<stamp
    if len(prices)!=1 or not complete:return dict(Status='LATEST_TIMESTAMP_AMBIGUOUS',SearchFrom=lo,SearchThrough=hi)
    return dict(Status='AUTHENTIC_LATEST_PREFIX',SearchFrom=lo,SearchThrough=hi,At=stamp,
        Price=str(Decimal(next(iter(prices))).scaleb(-5)),ReturnedTicks=len(rows),HasOlderOmittedTicks=response.hasMore,
        PrefixNewestFirst=True,LeadingTimestampComplete=True)

def collect(journal,account,p):
    ids=funding.plan_ids(dict(Targets=p['Targets']))
    rows=[]
    for target in p['Targets']:
        hi=target['At'];lo=hi-p['LookbackMs']
        side=e.BID if target['Side']=='BID' else e.ASK
        response,_,_=journal.query(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=ids[target['Symbol']],
            type=side,fromTimestamp=lo,toTimestamp=hi))
        rows.append(dict(Target=target,Witness=latest(response,account,lo,hi)))
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('capture','verify'));a=ap.parse_args()
    raw=PLAN.read_bytes();p=json.loads(raw);digest=src.digest(raw);rid=os.environ['GITHUB_RUN_ID']
    need(p['Study']=='FUNDING_LATEST_PREFIX_SETTLEMENT_1' and p['LookbackMs']==345600000 and
         len(p['Targets'])==7 and p['EconomicPolicyReruns']==0,'PREFIX_SCOPE')
    if a.stage=='capture':
        need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main' and
             os.environ['GITHUB_RUN_ATTEMPT']=='1','PREFIX_CAPTURE_CONTEXT')
        t=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(t);need(src.original_account(account),'PREFIX_ACCOUNT')
            journal=src.Journal(t,account);rows=collect(journal,account,p)
        finally:t.close()
        OUT.mkdir()
        sealed=eer.seal(OUT/'packets.sealed',dict(runId=rid,protocolSha256=digest,packets=journal.packets,rows=rows),
            checked_public(Path('new-recipient-output'),rid),rid)
        (OUT/'receipt.json').write_bytes(src.canonical(dict(sealed=sealed,requests=len(journal.packets),Orders=0,CloudActivated=False)))
        return
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    receipt=json.loads((OUT/'receipt.json').read_bytes());data=eer.unpack(OUT,receipt['sealed'],key,rid)
    need(data['runId']==rid and data['protocolSha256']==digest,'PREFIX_BINDING')
    packets=data['packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'PREFIX_READBACK_ACCOUNT')
    journal=src.ReadbackJournal(packets);rows=collect(journal,account,p)
    need(rows==data['rows'] and journal.index==len(packets)==receipt['requests'],'PREFIX_READBACK')
    need(all(x['Witness']['Status']=='AUTHENTIC_LATEST_PREFIX' for x in rows),'PREFIX_STILL_UNRESOLVED')
    # Recover only the archived account/contract shard; no market-history replay.
    old=json.loads(archive.REGISTRY.read_bytes())
    archive.download_archive(old['OriginalArtifact'],old['OriginalRun'],old['OriginalArchiveSha256'],archive.CIPHER_DIR)
    original=json.loads((archive.PUBLIC_DIR/'source.json').read_bytes())
    terms,account_terms=archive.official_terms(original,['AAPL.US','US500'],key)
    archive.download_archive(p['EconomicArtifact'],p['EconomicRun'],p['EconomicSha256'],Path('original-mechanism-result'))
    original_report=json.loads(Path('original-mechanism-result/economic.json').read_bytes(),parse_float=Decimal)
    s=original_report['Summary']['Results'][0]
    trial=next(x for x in s['Trials'] if x['Id']==p['Trial'])
    details=next(x for x in s['TrialDetails'] if x['Id']==p['Trial'])['Details']
    need(len(details['OutstandingFunding'])==1 and trial['Result']['UnknownFundingWindows']==1 and
         trial['Result']['OpenPositions']==trial['Result']['PendingIntents']==0,'PREFIX_ORIGINAL_WINDOW')
    window=details['OutstandingFunding'][0]
    episode=next(x for x in details['Episodes'] if x['PositionId']==window['PositionId'])
    need(window['Symbol']=='AAPL.US' and episode['NetEur'] is None and window['FromExclusive']==episode['OpenAt'] and
         window['ClosedAt']==episode['CloseAt'] and window['Units']==episode['Units'],'PREFIX_CLOSED_EPISODE')
    def witness(symbol,side,at):return next(x['Witness'] for x in rows if x['Target']==dict(Symbol=symbol,Side=side,At=at))
    charges=[]
    for at in p['ChargeClocks']:
        charges.append(dict(At=at,Bid=witness('AAPL.US','BID',at),FxBid=witness('EURUSD','BID',at),FxAsk=witness('EURUSD','ASK',at)))
    contract=dict(terms['AAPL.US'][0],ObservedAtUtcMs=original_report['Summary']['InitialFitFrom']-1)
    prepared=dict(Study=p['Study'],RegistrySha256=digest,OriginalRun=p['EconomicRun'],OriginalArtifact=p['EconomicArtifact'],
        OriginalArchiveSha256=p['EconomicSha256'],OriginalProtocolSha256=original_report['Summary']['ProtocolSha256'],
        OriginalSourceSha256=original_report['Summary']['SourceSha256'],Contract=contract,Account=account_terms,
        PriceDigits=terms['AAPL.US'][1]['priceDigits'],Window=window,Episode=episode,Charges=charges,
        OriginalCashEur=trial['Result']['CashEur'],KnownOtherNetEur=sum(x['NetEur'] for x in details['Episodes'] if x['NetEur'] is not None),
        RecoveredWitnesses=rows,Receipt=receipt,EconomicPolicyReruns=0,Orders=0,CloudActivated=False)
    # Decimal-safe serialization of immutable monetary facts.
    from .merge_eur_scenarios import exact_json
    Path('prefix-native-input.json').write_text(exact_json(prepared)+'\n')
    overlay={}
    for row in rows:
        target=row['Target'];key=(target['Symbol'],target['At'])
        quote=overlay.setdefault(key,dict(At=target['At'],RequestedCoverage=False,BidAt=None,AskAt=None,Bid=None,Ask=None))
        quote['LatestBidPrefix' if target['Side']=='BID' else 'LatestAskPrefix']=row['Witness']
    Path('prefix-funding-overlay.json').write_bytes(src.canonical(dict(RegistrySha256=digest,Receipt=receipt,
        QuotesBySymbol={name:[q for (symbol,_),q in overlay.items() if symbol==name] for name in sorted({x[0] for x in overlay})},
        OriginalInputModified=False,EconomicPolicyReruns=0,Orders=0,CloudActivated=False)))
    print('PREFIX_VERIFIED',len(rows),'LATEST',[(x['Target']['Symbol'],x['Target']['Side'],x['Witness']['At']) for x in rows],flush=True)

if __name__=='__main__':main()
