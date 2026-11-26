"""Source-only annual coverage and normalized reuse of completed custody packets.
No authentication, broker request, policy execution or altered source report.
"""
import argparse
import json,os,base64
from pathlib import Path
from datetime import datetime,timezone
from . import owner_eur_recent_continuous as recent
from . import owner_eer1_source as eer
from . import owner_eer1_readback as readback
from . import owner_eur_recent_archive as archive
from . import integrated_market_readback as marks
from . import source_history_universe as src
from .custody_new import checked_public
from .decode import need

REGISTRY=Path('research/official_breadth_extension_3_spans.json')


def bounds(rows,period,end):
    clocks=[r[0] for r in rows];width=src.PERIODS[period]*60000
    need(clocks==sorted(set(clocks)) and all(t+width<=end for t in clocks),'BREADTH_SPAN_CLOSED_UNIQUE_BARS')
    months={}
    for t in clocks:
        key=datetime.fromtimestamp(t/1000,timezone.utc).strftime('%Y-%m');months[key]=months.get(key,0)+1
    first=min(clocks) if clocks else None;last=max(clocks)+width if clocks else None
    return dict(Rows=len(rows),FirstOpenAt=first,LastCloseAt=last,Months=months,
        CalendarSpanDays=(last-first)/recent.DAY if first is not None else None,
        ReachesTwelveMonthStart=first is not None and first<=end-365*recent.DAY,
        ContinuousCoverageCertified=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('download','verify'));a=parser.parse_args()
    p=json.loads(REGISTRY.read_bytes())
    need(p['Study']=='OFFICIAL_BREADTH_EXTENSION_3_SPANS' and p['SourceRun']==45829391256 and
         p['Orders']==p['SourceBrokerRequests']==0 and not p['CloudActivated'],'BREADTH_SPAN_SCOPE')
    root=Path('span-archives')
    if a.stage=='download':
        root.mkdir(mode=0o700)
        for item in p['Artifacts']:
            archive.download_archive(item['Id'],p['SourceRun'],item['Sha256'],root/item['Name'])
        return
    plan_raw=Path('research/official_breadth_extension_3.json').read_bytes();plan=json.loads(plan_raw)
    need(src.digest(plan_raw)==p['SourceRegistrySha256'],'BREADTH_SPAN_ORIGINAL_REGISTRATION')
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode();run=str(p['SourceRun']);old_meta=recent.META
    recent.META=root/'breadth-extension-3-source-metadata'
    try:receipt,meta,account=recent.metadata_readback(plan,src.digest(plan_raw),key,run)
    finally:recent.META=old_meta
    summary=json.loads((root/'breadth-extension-3-source-verified-summary/breadth-extension-3-source-summary.json').read_bytes())
    need(summary['Study']=='OFFICIAL_BREADTH_EXTENSION_3' and not summary['pending'] and
         summary['planned']==summary['verified']==len(receipt['summary']['partitions']), 'BREADTH_SPAN_ALL_ORIGINAL_PARTITIONS')
    proof={r['report']['index']:r for r in summary['receipts']};out=Path('span-output');out.mkdir()
    private=Path(os.environ['RUNNER_TEMP'])/'breadth-span-private';private.mkdir(mode=0o700)
    tapes=private/'verified-protection';tapes.mkdir(mode=0o700)
    sink=readback.protection_tick_sink(tapes,'eer1');data={};quotes={};funding={};reports=[]
    for i,t in enumerate(receipt['summary']['partitions']):
        folder=root/f'breadth-extension-3-source-protected-{i}';row=json.loads((folder/'receipt.json').read_bytes())
        need(row['sealed']==proof[i]['sealed'],'BREADTH_SPAN_SEAL_BINDING')
        payload=eer.unpack(folder,row['sealed'],key,run);packets=payload['packets']
        need(packets and all(src.decode(x['reqType'],x['req']).ctidTraderAccountId==account for x in packets),'BREADTH_SPAN_ACCOUNT')
        journal=src.ReadbackJournal(packets)
        report,bars,q,f=recent.collect(journal,account,plan,t,receipt['summary']['chargeMinutes'],tick_sink=sink,keep=True)
        report.update(runId=run,protocolSha256=src.digest(plan_raw),index=i,requests=len(packets))
        need(journal.index==len(packets)==proof[i]['packetsReconciled'] and report==payload['report']==row['report']==proof[i]['report'],
             'BREADTH_SPAN_EXACT_ORIGINAL_PACKET_PARITY')
        name=t['symbol'];data[name]={tf:marks.normalized_bars(series) for tf,series in bars.items()};quotes[name]=q;funding[name]=f
        reports.append(dict(Symbol=name,Packets=journal.index,MonetaryMarks=len(q),FundingMarks=len(f),
            TickFrom=t['fromInclusive'],TickThrough=t['throughExclusive'],
            BarCoverage={tf:bounds(series,tf,t['throughExclusive']) for tf,series in bars.items()}))
        print('BREADTH_SPAN_VERIFIED',i+1,len(receipt['summary']['partitions']),name,flush=True)
    normalized=dict(Study=p['Study'],SourceRun=p['SourceRun'],SourceRegistrySha256=src.digest(plan_raw),
        Metadata=meta,Bars=data,Quotes=quotes,Funding=funding,Proof=reports,
        ProtectionFiles={f.name:base64.b64encode(f.read_bytes()).decode() for f in sorted(tapes.iterdir())},SourceBrokerRequests=0,Orders=0,CloudActivated=False)
    seal=eer.seal(out/'normalized-source.sealed',normalized,checked_public(Path('new-recipient-output'),os.environ['GITHUB_RUN_ID']),os.environ['GITHUB_RUN_ID'])
    # Binary protection tapes stay encrypted with normalized bars and metadata.
    # Future materialization does not have to decode the raw packet corpus again.
    report=dict(Study=p['Study'],SourceRun=p['SourceRun'],SourceRegistrySha256=src.digest(plan_raw),
        Reports=reports,NormalizedSourceSeal=seal,RawArchivesPreserved=True,SourceBrokerRequests=0,EconomicPolicyExecutions=0,
        AnnualBarHistoryIsNotAnnualEconomicConfirmation=True,IndependentConfirmationCertified=False,
        HistoricalTariffsCertified=False,Orders=0,CloudActivated=False)
    (out/'official-annual-bar-spans.json').write_bytes(src.canonical(report))

if __name__=='__main__':main()
