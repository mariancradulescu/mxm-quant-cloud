"""Reuse immutable authenticated breadth-8 annual data; no broker request."""
import argparse,json,os,subprocess
from pathlib import Path
from . import owner_eur_recent_continuous as recent
from . import owner_official_breadth_extension_8 as breadth
from . import owner_eer1_source as eer
from . import source_history_universe as src
from .decode import need
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .verified_research_cache import sha
RUN=45954516978
INPUTS={
    'input':(15178266804,'05595f02f2fe73cbc3519ec99c7cb14d734ecc60452b17302c7b5ccf7c3118d9'),
    'plan':(15177923116,'cf6eb49ba0000831382ba36585ae972d3d13c02e81eb84a5d29ebcf5f7416fc2'),
    'summary':(15180115705,'3174db9c8b0c81e14054ed05b3e6010ee1dee29b6d5edccede3741734ac85add')}
PARTS={
    0:(15178556753,'37a4c5dea2427b6ef69a7e967624a7cd3a79a9a427f1e299075a3e738579f54a'),
    3:(15178323127,'733b34c80cb0e98b41a9ff5a39f7bb4a080209fbaf4be8ef6e0a9ec6e032238f'),
    6:(15178946261,'fb9840d83ea3b5f5d435c20e4c491b78bdd8e0d0c4aeb55a21217e00d3f21a76'),
    9:(15178508872,'a168a44e6a0d2c598bbce98198eedc0f97e077af4e1496ff634dc0f3d90fedd8')}
NAMES={'AUS200','III.GB','USDCAD','USTN2YR-F'}
def read(p):return json.loads(p.read_bytes())
def fetch(spec,dest):
    verified_download(spec[0],RUN,spec[1],dest)
def main():
    a=argparse.ArgumentParser();a.add_argument('--work',type=Path,required=True);v=a.parse_args()
    work=v.work;work.mkdir(mode=0o700)
    for name,spec in INPUTS.items():fetch(spec,work/name)
    plan=read(work/'plan/recent-plan.json')
    summary=read(work/'summary/breadth-extension-8-source-summary.json')
    need(plan['runId']==str(RUN) and summary['protocolSha256']==plan['protocolSha256'] and
        summary['planned']==summary['verified']==24 and not summary['pending'] and
        set(plan['chosen'])==NAMES and plan['orders']==summary['orders']==0 and
        not plan['cloudActivated'] and not summary['cloudActivated'],'BREADTH_PATH_PLAN')
    # The archived census and prior receipt independently bind the collector parameters.
    import shutil
    for folder in ('eer1-economic','prior-breadth-verified'):
        shutil.copytree(work/'input'/folder,Path(folder))
    p,digest=breadth.registered()
    need(digest==plan['protocolSha256'],'BREADTH_PATH_PROTOCOL')
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    rows=[];proof=[]
    for i,spec in PARTS.items():
        dest=work/f'part-{i}';fetch(spec,dest)
        t=plan['partitions'][i]
        need(t['window']=='NOV24_26_ANNUAL_CONTEXT' and t['bars'] and t['symbol'] in NAMES,'BREADTH_PATH_TARGET')
        receipt=read(dest/'receipt.json')
        payload=eer.unpack(dest,receipt['sealed'],key,str(RUN))
        packets=payload['packets']
        need(bool(packets),'BREADTH_PATH_PACKETS')
        account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
        need(src.original_account(account),'BREADTH_PATH_ACCOUNT')
        journal=src.ReadbackJournal(packets)
        report,bars,_,_=recent.collect(journal,account,p,t,plan['chargeMinutes'],keep=True)
        report.update(runId=str(RUN),protocolSha256=digest,index=i,requests=len(packets))
        prior=summary['receipts'][i]
        need(journal.index==len(packets) and report==payload['report']==receipt['report']==prior['report'] and
            receipt['sealed']==prior['sealed'] and prior['packetsReconciled']==journal.index,
            'BREADTH_PATH_PACKET_PARITY')
        rows.append(dict(Symbol=t['symbol'],Bars={k:bars[k] for k in ('M5','M15','H1')}))
        proof.append(dict(Symbol=t['symbol'],Artifact=spec[0],ArchiveSha256=spec[1],
            PacketCount=journal.index,BarCounts={k:len(bars[k]) for k in ('M5','M15','H1')}))
    source=work/'annual-private.json';source.write_text(json.dumps(rows,separators=(',',':')))
    out=Path('annual-path-report');out.mkdir()
    subprocess.run(['dotnet','run','--project','src/Mxm.PathResearch','-c','Release','--',str(source),str(out/'information.json')],check=True)
    result=read(out/'information.json')
    need(result['SourceSha256']==sha(source) and set(result['Markets'])==NAMES and result['PriceInformationOnly']
        and not result['PortfolioEvaluated'] and not result['IndependentConfirmationCertified']
        and result['Orders']==0 and not result['CloudActivated'],'BREADTH_PATH_RESULT')
    (out/'source-receipt.json').write_text(json.dumps(dict(OriginalRun=RUN,ProtocolSha256=digest,SourceSha256=sha(source),
        ReconciledPartitions=proof,SourceBrokerRequests=0,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False),indent=2))
if __name__=='__main__':main()
