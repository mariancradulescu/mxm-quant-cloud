"""Normalize all independently verified breadth-4 windows separately.
Retain every original custody packet, overlapping bar quarantine and partition
clock; never flatten disjoint dates into fabricated continuous coverage.
"""
import argparse,base64,json,os,shutil
from pathlib import Path
from . import owner_eur_recent_continuous as recent
from . import owner_eer1_source as eer
from . import owner_eer1_readback as readback
from . import owner_eur_recent_archive as archive
from . import source_history_universe as src
from .owner_official_breadth_spans import bounds,normalize_with_quarantine,fast_seal
from .custody_new import checked_public
from .decode import need

REGISTRY=Path('research/official_breadth4_normalized_windows_1.json')
PREFIX='breadth-extension-4-source-'
def registered():
    p=json.loads(REGISTRY.read_bytes())
    need(p['Study']=='OFFICIAL_BREADTH4_NORMALIZED_WINDOWS_1' and p['SourceRun']==45886285070
         and p['ExpectedPartitions']==30 and len(p['Artifacts'])==32
         and {x['Name'] for x in p['Artifacts']}=={PREFIX+'metadata',PREFIX+'verified-summary'}|{
             PREFIX+'protected-'+str(i) for i in range(30)}
         and len({x['Id'] for x in p['Artifacts']})==32 and
         p['Orders']==p['EconomicPolicyExecutions']==p['SourceBrokerRequests']==0 and
         not p['CloudActivated'] and not p['IndependentConfirmationCertified'],'BREADTH4_CACHE_SCOPE')
    return p

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('check','download','verify'));args=parser.parse_args()
    p=registered();root=Path('breadth4-window-archives')
    if args.stage=='check':return
    if args.stage=='download':
        root.mkdir(mode=0o700)
        for a in p['Artifacts']:
            archive.download_archive(a['Id'],p['SourceRun'],a['Sha256'],root/a['Name'])
        return
    run=str(p['SourceRun']);new_run=os.environ['GITHUB_RUN_ID']
    plan_raw=Path('research/official_breadth_extension_4.json').read_bytes();plan=json.loads(plan_raw)
    digest=src.digest(plan_raw);need(digest==p['SourceRegistrySha256'],'BREADTH4_REGISTRATION_IDENTITY')
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode();recipient=checked_public(Path('new-recipient-output'),new_run)
    previous=recent.META;recent.META=root/(PREFIX+'metadata')
    try:receipt,meta,account=recent.metadata_readback(plan,digest,key,run)
    finally:recent.META=previous
    summary=json.loads((root/(PREFIX+'verified-summary')/'breadth-extension-4-source-summary.json').read_bytes())
    targets=receipt['summary']['partitions']
    need(summary['Study']==plan['Study'] and summary['protocolSha256']==digest and not summary['pending'] and
         summary['planned']==summary['verified']==len(targets)==p['ExpectedPartitions'],'BREADTH4_ORIGINAL_VERIFIED_SCOPE')
    proof={x['report']['index']:x for x in summary['receipts']}
    need(set(proof)==set(range(len(targets))),'BREADTH4_ALL_PARTITIONS')
    out=Path('breadth4-window-cache');out.mkdir(mode=0o700)
    metadata_seal=fast_seal(out/'metadata.sealed',dict(SourceRun=run,SourceRegistrySha256=digest,Metadata=meta),
                           recipient,new_run)
    private=Path(os.environ['RUNNER_TEMP'])/'breadth4-window-private';private.mkdir(mode=0o700)
    reports=[]
    for i,t in enumerate(targets):
        folder=root/(PREFIX+'protected-'+str(i));row=json.loads((folder/'receipt.json').read_bytes())
        need(row['sealed']==proof[i]['sealed'],'BREADTH4_PACKET_SEAL')
        payload=eer.unpack(folder,row['sealed'],key,run);packets=payload['packets']
        need(packets and all(src.decode(x['reqType'],x['req']).ctidTraderAccountId==account for x in packets),
             'BREADTH4_ACCOUNT_BINDING')
        journal=src.ReadbackJournal(packets);tape=private/str(i);tape.mkdir()
        sink=readback.protection_tick_sink(tape,'eer1')
        report,bars,q,f=recent.collect(journal,account,plan,t,receipt['summary']['chargeMinutes'],tick_sink=sink,keep=True)
        report.update(runId=run,protocolSha256=digest,index=i,requests=len(packets))
        need(journal.index==len(packets)==proof[i]['packetsReconciled'] and
             report==payload['report']==row['report']==proof[i]['report'],'BREADTH4_EXACT_PACKET_PARITY')
        normalized={};quality={}
        for tf,series in bars.items():
            normalized[tf],quarantine=normalize_with_quarantine(series)
            quality[tf]=dict(bounds(series,tf,t['throughExclusive']),ReusableRows=len(normalized[tf]),
                NominalIntervalQuality=quarantine)
        record=dict(Index=i,Target=t,Packets=journal.index,MonetaryMarks=len(q),FundingMarks=len(f),BarCoverage=quality)
        artifact=fast_seal(out/f'window-{i:03d}.sealed',dict(SourceRun=run,SourceRegistrySha256=digest,
            Index=i,Target=t,OriginalNominalClosedRows=bars,Bars=normalized,Quotes=q,Funding=f,
            ProtectionFiles={x.name:base64.b64encode(x.read_bytes()).decode() for x in sorted(tape.iterdir())},
            Proof=record,SourceBrokerRequests=0,Orders=0,CloudActivated=False),recipient,new_run)
        reports.append(dict(record,NormalizedSeal=artifact))
        shutil.rmtree(tape)
        print('BREADTH4_NORMALIZED_PARTITION',i+1,len(targets),t['symbol'],t['window'],flush=True)
    public=dict(Study=p['Study'],SourceRun=p['SourceRun'],SourceRegistrySha256=digest,
        MetadataSeal=metadata_seal,Reports=reports,PartitionsNormalized=len(reports),
        RawArchivesPreserved=True,DisjointWindowsPreserved=True,SourceBrokerRequests=0,EconomicPolicyExecutions=0,
        HistoricalTariffsCertified=False,IndependentConfirmationCertified=False,Orders=0,CloudActivated=False)
    (out/'normalized-window-receipt.json').write_bytes(src.canonical(public))
    print('BREADTH4_NORMALIZED_COMPLETE',len(reports),flush=True)
if __name__=='__main__':main()
