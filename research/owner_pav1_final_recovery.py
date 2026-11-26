"""Verify completed economic outputs without rerunning a single policy.
Rebuild exact source bytes solely for a reusable bounded custody checkpoint.
"""
import argparse,json,os,subprocess,zipfile
from pathlib import Path
from . import owner_pav1_market_time as study
from . import owner_eur_recent_archive as archive
from . import source_history_universe as src
from .merge_eur_scenarios import read
from .decode import need

REGISTRY=Path('research/pav1_market_time_final_recovery_1.json')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('download','materialize','finalize'));parser.add_argument('--work',type=Path);a=parser.parse_args()
    p=json.loads(REGISTRY.read_bytes());base,digest=study.registered()
    need(p['Study']=='PAV1_MARKET_TIME_FX_1_FINAL_RECOVERY' and p['OriginalEconomicRun']==45835675932 and
         digest==p['OriginalRegistrySha256'] and p['EconomicPolicyExecutions']==p['SourceBrokerRequests']==p['Orders']==0 and
         not p['CloudActivated'],'PAV_FINAL_RECOVERY_SCOPE')
    if a.stage=='download':
        repo=os.environ['GITHUB_REPOSITORY'];run=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{p["OriginalEconomicRun"]}']))
        need(run['head_sha']==p['OriginalEconomicRevision'] and run['run_attempt']==1 and run['status']=='completed',
             'PAV_FINAL_ORIGINAL_REVISION')
        artifacts=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{p["OriginalEconomicRun"]}/artifacts?per_page=100']))['artifacts']
        selected=[r for r in artifacts if r['name']=='pav1-market-time-fx-1-complete' and not r['expired']]
        need(len(selected)==1,'PAV_FINAL_ORIGINAL_COMPLETE_ARTIFACT')
        item=selected[0];sha=item['digest'].removeprefix('sha256:')
        archive.download_archive(item['id'],p['OriginalEconomicRun'],sha,Path('verified-original-result'))
        Path('verified-original-artifact.json').write_bytes(src.canonical(dict(Id=item['id'],Run=p['OriginalEconomicRun'],Sha256=sha,
            OriginalRunConclusion=run['conclusion'],OriginalRevision=run['head_sha'])))
        r=read(Path('verified-original-result/economic-market-time.json'))
        need(r['SharedPortfolioEvaluations']==45 and len(r['Results'])==3 and all(len(x['CommonBooks'])==15 for x in r['Results']) and
             r['Orders']==0 and not r['CloudActivated'] and not r['EconomicPromotionCertified'],'PAV_FINAL_ORIGINAL_ECONOMIC_OUTPUT')
        study.download(base);return
    if a.stage=='materialize':
        revision=os.environ['GITHUB_SHA'];os.environ['GITHUB_SHA']=p['OriginalEconomicRevision']
        try:study.materialize(base,digest,a.work,Path('pav-market-source.json'))
        finally:os.environ['GITHUB_SHA']=revision
        expected=read(Path('verified-original-result/pav-market-source.json'))
        need(read(Path('pav-market-source.json'))==expected,'PAV_FINAL_EXACT_ORIGINAL_SOURCE_RECEIPT')
        return
    report=read(Path('verified-original-result/economic-market-time.json'));checkpoint=read(Path('market-checkpoint/checkpoint-receipt.json'))
    need(checkpoint['Complete'] and checkpoint['SourceSha256']==report['Results'][0]['SourceSha256'] and
         len({r['SourceSha256'] for r in report['Results']})==1,'PAV_FINAL_CHECKPOINT_AND_ORIGINAL_SOURCE_IDENTITY')
    out=Path('final-recovered-report');out.mkdir()
    for source in Path('verified-original-result').iterdir():
        if source.is_file():(out/source.name).write_bytes(source.read_bytes())
    (out/'recovery-receipt.json').write_bytes(src.canonical(dict(Study=p['Study'],OriginalArtifact=read(Path('verified-original-artifact.json')),
        OriginalEconomicJsonSha256=src.digest((out/'economic-market-time.json').read_bytes()),
        SourceSha256=checkpoint['SourceSha256'],CheckpointRun=os.environ['GITHUB_RUN_ID'],CheckpointSchema=checkpoint['Schema'],
        CheckpointFiles=len(checkpoint['Files']),OriginalResultsByteUnchanged=True,ReconstructedSourceByteIdentity=True,
        EconomicPolicyExecutions=0,SourceBrokerRequests=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False)))

if __name__=='__main__':main()
