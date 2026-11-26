"""Test recoverability of an official conversion leg without trading it."""
import argparse
import json
import os
from pathlib import Path
import time

from . import owner_eur_recent_continuous as recent
from . import owner_eer1_source as eer
from . import source_history_universe as src
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

REGISTRY=Path('research/disabled_conversion_history_1.json')
OUT=Path('conversion-history')


def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    need(p['Study']=='OFFICIAL_DISABLED_CONVERSION_HISTORY_1' and p['Symbol']=='USDHKD' and
         p['RequiredBy']=='HK50-F' and p['OriginalMetadataRun']==45806558835 and
         p['From']=='2026-11-23' and p['To']=='2026-11-25' and
         p['PageHours']==4 and p['PerPartitionMaxRequests']==1000 and
         p['PerPartitionSeconds']==1080 and p['PerSidePageBudget']==450 and
         p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'CONVERSION_HISTORY_REGISTRY')
    return p,src.digest(raw)


def target(meta,p):
    name=p['Symbol'];row=meta['roster'].get(name)
    need(row is not None and row['id']>0 and
         any(h['Symbol']==name for route in meta['routes'].values() for h in route),
         'CONVERSION_HISTORY_OFFICIAL_ROUTE_IDENTITY')
    return dict(symbol=name,symbolId=row['id'],window='NOV23_25',roles=['CONVERSION'],bars=False,
        fromInclusive=recent.utc(p['From']),throughExclusive=recent.utc(p['To']),barFrom=recent.utc(p['From']))


def prepare(p,digest):
    prior_raw=Path('research/official_breadth_extension_2.json').read_bytes()
    need(src.digest(prior_raw)==p['OriginalMetadataProtocolSha256'],'CONVERSION_HISTORY_PRIOR_PROTOCOL')
    receipt,meta,_=recent.metadata_readback(json.loads(prior_raw),src.digest(prior_raw),
        os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),str(p['OriginalMetadataRun']))
    t=target(meta,p)
    plan=dict(Study=p['Study'],RunId=os.environ['GITHUB_RUN_ID'],RegistrySha256=digest,Target=t,
        OriginalMetadataRun=p['OriginalMetadataRun'],OriginalMetadataSeal=receipt['sealed'],
        EnabledAtCapture=meta['roster'][p['Symbol']]['enabled'],Purpose='HISTORICAL_CONVERSION_OBSERVATION_ONLY',
        ChargeMinutes=eer.charge_clocks(meta['terms']),Orders=0,CloudActivated=False)
    Path('conversion-plan.json').write_bytes(src.canonical(plan))
    print('CONVERSION_HISTORY_TARGET',p['Symbol'],'enabled=',plan['EnabledAtCapture'],flush=True)


def main():
    cli=argparse.ArgumentParser();cli.add_argument('stage',choices=('prepare','capture','verify'));a=cli.parse_args()
    p,digest=registered();rid=os.environ['GITHUB_RUN_ID']
    if a.stage=='prepare':prepare(p,digest);return
    plan=json.loads(Path('conversion-plan.json').read_bytes())
    need(plan['RegistrySha256']==digest and plan['RunId']==rid and plan['Target']['symbol']==p['Symbol'],
         'CONVERSION_HISTORY_PLAN_BINDING')
    if a.stage=='capture':
        need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main' and
             os.environ['GITHUB_RUN_ATTEMPT']=='1','CONVERSION_HISTORY_READ_ONLY_SCOPE')
        transport=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(transport);need(src.original_account(account),'CONVERSION_HISTORY_ACCOUNT')
            src.MAX_REQUESTS=p['PerPartitionMaxRequests'];journal=src.Journal(transport,account)
            journal.deadline=time.monotonic()+p['PerPartitionSeconds']
            report,_,_,_=recent.collect(journal,account,p,plan['Target'],plan['ChargeMinutes'])
        finally:transport.close()
        OUT.mkdir(exist_ok=False)
        report.update(runId=rid,protocolSha256=digest,requests=len(journal.packets))
        sealed=eer.seal(OUT/'packets.sealed',dict(plan=plan,report=report,packets=journal.packets),
            checked_public(Path('new-recipient-output'),rid),rid)
        (OUT/'receipt.json').write_bytes(src.canonical(dict(report=report,sealed=sealed)))
        return
    receipt=json.loads((OUT/'receipt.json').read_bytes())
    payload=eer.unpack(OUT,receipt['sealed'],os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),rid)
    packets=payload['packets'];need(bool(packets) and payload['plan']==plan,'CONVERSION_HISTORY_SOURCE_BINDING')
    account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'CONVERSION_HISTORY_READBACK_ACCOUNT')
    journal=src.ReadbackJournal(packets)
    report,_,_,_=recent.collect(journal,account,p,plan['Target'],plan['ChargeMinutes'])
    report.update(runId=rid,protocolSha256=digest,requests=len(packets))
    need(journal.index==len(packets) and report==payload['report']==receipt['report'],
         'CONVERSION_HISTORY_FULL_PACKET_READBACK')
    Path('conversion-history-verified.json').write_bytes(src.canonical(dict(Study=p['Study'],Plan=plan,
        Report=report,Sealed=receipt['sealed'],PacketsReconciled=journal.index,ReadbackBrokerRequests=0,
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,
        HistoryStatus='AUTHENTIC_MONETARY_MARKS_RECOVERED' if report['monetaryMarks']>0 else
            'VERIFIED_OFFICIAL_RESPONSE_WITHOUT_MONETARY_MARKS_NO_UNAVAILABILITY_INFERENCE')))


if __name__=='__main__':main()
