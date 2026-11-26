"""Target remaining ETHUSD cash liabilities of preserved common PAV1 books.

Recover exact required official prefixes; do not rerun any policy or replace
unknown cash by zero. The unchanged native cost method assesses settlement.
"""
import argparse,json,os
from pathlib import Path
from datetime import datetime,timezone

from . import source_history_universe as src
from . import owner_eur_recent_archive as archive
from . import owner_eur_recent_continuous as recent
from . import owner_eer1_source as eer
from . import owner_funding_prefix_settlement as prefix
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport
from .merge_eur_scenarios import read,exact_json

REGISTRY=Path('research/pav1_closed_funding_recovery_1.json')
OUT=Path('pav1-funding-protected')


def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    need(p['Study']=='PAV1_CLOSED_FUNDING_RECOVERY_1' and p['Symbol']=='ETHUSD' and
         p['OriginalEconomicRun']==45806288995 and p['OriginalEconomicArtifact']==15110537502 and
         p['LookbackMs']==345600000 and p['MaximumFxAgeMs']==7200000 and
         p['EconomicPolicyReruns']==p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'PAV1_FUNDING_REGISTRY')
    return p,src.digest(raw)


def charge_clocks(contract,window):
    need(contract['SwapPeriodHours']==24 and isinstance(contract['ChargeSwapAtWeekends'],bool) and
         isinstance(contract['SkipSwapPeriods'],int) and contract['SkipSwapPeriods']>=0,'PAV1_FUNDING_SCHEDULE')
    minute=contract['SwapTimeUtcMinute'];need(isinstance(minute,int) and 0<=minute<1440,'PAV1_FUNDING_MINUTE')
    start,end=window['FromExclusive'],window['ClosedAt'];out=[]
    for day in range(start//recent.DAY*recent.DAY,end//recent.DAY*recent.DAY+recent.DAY,recent.DAY):
        at=day+minute*60000
        if start<at<=end and (contract['ChargeSwapAtWeekends'] or datetime.fromtimestamp(at/1000,timezone.utc).weekday()<5):
            out.append(at)
    return out


def prepare(p,digest):
    prior=Path('research/eur_recent_continuous_source_1.json').read_bytes()
    receipt,meta,_=recent.metadata_readback(json.loads(prior),src.digest(prior),
        os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),str(p['OriginalMetadataRun']))
    need(receipt['sealed']['cipherSha256']==p['OriginalMetadataCipherSha256'],'PAV1_FUNDING_EXACT_TERMS_SEAL')
    archive.download_archive(p['OriginalEconomicArtifact'],p['OriginalEconomicRun'],p['OriginalEconomicSha256'],Path('original-pav1'))
    original=read(Path('original-pav1/opportunity-result.json'))
    need(original['Study']=='MONETARY_CAUSAL_LIFECYCLE_1' and original['Mechanism']=='PAV1_LOCAL_TRANSITION',
         'PAV1_FUNDING_ORIGINAL_BINDING')
    books=[];clocks=set();c=meta['terms'][p['Symbol']]
    for b in original['CommonBooks']:
        windows=b['UnresolvedFunding']
        if len(windows)!=1 or windows[0]['Symbol']!=p['Symbol']:continue
        w=windows[0];r=b['Result']
        need(w['ClosedAt'] is not None and r['OpenPositions']==r['PendingIntents']==0 and
             r['ClosedNetEur'] is None and r['UnknownFundingWindows']==1,'PAV1_FUNDING_CLOSED_ONLY')
        clocks.update(charge_clocks(c,w));books.append(dict(Id=b['Id'],Stress=b['Stress'],Window=w,
            OriginalCashEur=r['CashEur'],KnownOtherNetEur=b['KnownClosedNetSubtotalEur'],
            OriginalEventChainHash=r['EventChainHash'],OriginalSampledDrawdown=r['SampledDrawdown'],
            OriginalUnknownEquityClocks=r['UnknownEquityClocks']))
    need(bool(books) and c['QuoteAsset']=='USD','PAV1_FUNDING_WINDOWS_AND_ROUTE')
    need(meta['routes'].get('USD')==[dict(Symbol='EURUSD',BaseAsset='EUR',QuoteAsset='USD')],
         'PAV1_FUNDING_OFFICIAL_CONVERSION_ROUTE')
    targets=[dict(Symbol=name,Side=side,At=at) for at in sorted(clocks) for name,side in
        [('ETHUSD','BID'),('EURUSD','BID'),('EURUSD','ASK')]]
    plan=dict(Study=p['Study'],RegistrySha256=digest,RunId=os.environ['GITHUB_RUN_ID'],
        OriginalRun=p['OriginalEconomicRun'],OriginalArtifact=p['OriginalEconomicArtifact'],
        OriginalArchiveSha256=p['OriginalEconomicSha256'],OriginalProtocolSha256=original['ProtocolSha256'],
        OriginalSourceSha256=original['SourceSha256'],OriginalMetadataSeal=receipt['sealed'],
        Contract=c,Account=dict(accountSwapFree=meta['accountSwapFree'],accountType=meta['accountType'],moneyDigits=meta['moneyDigits']),
        PriceDigits=meta['info']['ETHUSD']['priceDigits'],ScenarioObservedAtUtcMs=original['Start']-1,
        Books=books,Targets=targets,LookbackMs=p['LookbackMs'],EconomicPolicyReruns=0,Orders=0,CloudActivated=False)
    Path('pav1-funding-plan.json').write_text(exact_json(plan)+'\n')
    print('PAV1_CLOSED_FUNDING_PLAN',len(books),'BOOKS',len(targets),'OFFICIAL_PREFIX_TARGETS',flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('prepare','capture','verify'));a=ap.parse_args()
    p,digest=registered();rid=os.environ['GITHUB_RUN_ID']
    if a.stage=='prepare':prepare(p,digest);return
    plan=read(Path('pav1-funding-plan.json'))
    need(plan['RegistrySha256']==digest and plan['RunId']==rid,'PAV1_FUNDING_PLAN_BINDING')
    if a.stage=='capture':
        need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main' and
             os.environ['GITHUB_RUN_ATTEMPT']=='1','PAV1_FUNDING_READONLY_SCOPE')
        transport=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(transport);need(src.original_account(account),'PAV1_FUNDING_ACCOUNT')
            journal=src.Journal(transport,account);rows=prefix.collect(journal,account,plan)
        finally:transport.close()
        OUT.mkdir(exist_ok=False)
        sealed=eer.seal(OUT/'packets.sealed',dict(runId=rid,protocolSha256=digest,rows=rows,packets=journal.packets),
            checked_public(Path('new-recipient-output'),rid),rid)
        (OUT/'receipt.json').write_bytes(src.canonical(dict(sealed=sealed,requests=len(journal.packets),Orders=0,CloudActivated=False)))
        return
    receipt=json.loads((OUT/'receipt.json').read_bytes())
    payload=eer.unpack(OUT,receipt['sealed'],os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),rid)
    packets=payload['packets'];need(bool(packets) and payload['protocolSha256']==digest and payload['runId']==rid,'PAV1_FUNDING_SOURCE')
    account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'PAV1_FUNDING_READBACK_ACCOUNT')
    journal=src.ReadbackJournal(packets);rows=prefix.collect(journal,account,plan)
    need(rows==payload['rows'] and journal.index==len(packets)==receipt['requests'],'PAV1_FUNDING_PACKET_PARITY')
    Path('pav1-funding-native-input.json').write_text(exact_json(dict(plan,Witnesses=rows,SourceReceipt=receipt,
        PacketsReconciled=journal.index,ReadbackBrokerRequests=0))+'\n')


if __name__=='__main__':main()
