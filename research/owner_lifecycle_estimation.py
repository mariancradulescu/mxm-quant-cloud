"""New pre-registered estimator, support, geometry and management ablations.
Reuse the complete authenticated 29-market source; no original economic run.
"""
import argparse,os,subprocess,time,math
from pathlib import Path
from decimal import Decimal
from .owner_causal_source_shards import download_artifact,download_shards
from .owner_pav1_market_time import restore_checkpoint,select
from .owner_causal_management_choice import variants as old_variants
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import seal_files,sha
from .custody_new import derive_recipient
from .decode import need

STUDY='MONETARY_LIFECYCLE_ESTIMATION_1'
SOURCE='4336a525ad897bee1a280e2baff07dcd399606e25f9536d4a202bc2676d73b15'
PARENT_PROTOCOL='a82d6689163233b3f9c7c044c8767525453b0daa7aa06cbe954514036123d958'
SHARD_RUN=45875663964
SHARD_META=15143963668
SHARD_SHA='a62909c52f02fa037ee96c61b1c9b09b7506882a2a6897c22aae0b9c0c3d9e42'

def write(path,value):Path(path).write_text(exact_json(value)+'\n')

def variants():
    base=old_variants()[0]['Profile']
    out=[]
    for name,estimator,n,penalty,tf,management in (
        ('CENTER_LOCAL','CENTERED_LOCAL',20,'1.645','H1','TRANSITION_VALUE'),
        ('CENTER_TRANSFER','CENTERED_TRANSFER',20,'1.645','H1','TRANSITION_VALUE'),
        ('TRANSFER_SUPPORT_SENSITIVITY','CENTERED_TRANSFER',8,'.75','H1','TRANSITION_VALUE'),
        ('TRANSFER_M15','CENTERED_TRANSFER',8,'.75','M15','TRANSITION_VALUE'),
        ('TRANSFER_REDUCE','CENTERED_TRANSFER',8,'.75','H1','MONETARY_REDUCE')):
        out.append(dict(Id=name,UniverseCount=29,Profile=dict(base,LifecycleEstimator=estimator,
            MinimumEpisodes=n,MinimumDays=3,DayPenalty=Decimal(penalty),EconomicGeometryTimeframe=tf,
            EconomicManagement=management)))
    return out

def restore(work):
    started=time.monotonic()
    folder=work.parent/'estimator-cipher'
    download_artifact(SHARD_META,SHARD_RUN,SHARD_SHA,folder)
    receipt=read(folder/'repack-receipt.json')
    need(receipt['SourceSha256']==SOURCE and receipt['ProtocolSha256']==PARENT_PROTOCOL
         and receipt['OriginalSourceRun']==45874059214 and receipt['RepackRunId']==str(SHARD_RUN)
         and receipt['AllOriginalEncryptedBytesPreserved'] and len(receipt['Shards'])==3,
         'ESTIMATOR_SHARD_BINDING')
    download_shards(receipt,folder)
    downloaded=time.monotonic()
    restore_checkpoint(folder,work,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),
                       str(receipt['SourceRunId']),SOURCE,source_only=True)
    need(sha(work/'pav-market-protocol.json')==PARENT_PROTOCOL,'ESTIMATOR_PARENT_PROTOCOL')
    report=Path('estimator-report');report.mkdir()
    plan=read(work/'pav-market-protocol.json')
    need(plan['Study']=='MONETARY_CAUSAL_MANAGEMENT_1','ESTIMATOR_PARENT_STUDY')
    plan.update(Study=STUDY,Variants=variants())
    write(work/'estimator-plan.json',plan)
    (report/'registered-plan.json').write_bytes((work/'estimator-plan.json').read_bytes())
    write(report/'source-receipt.json',dict(Study=STUDY,SourceSha256=SOURCE,ParentProtocolSha256=PARENT_PROTOCOL,
        ProtocolSha256=sha(work/'estimator-plan.json'),ShardMetadataArtifact=SHARD_META,ShardMetadataSha256=SHARD_SHA,
        DownloadAndCipherVerifySeconds=round(downloaded-started,3),RestoreSeconds=round(time.monotonic()-downloaded,3),
        SourceReconstructionExecutions=0,SourceBrokerRequests=0,Orders=0,CloudActivated=False))

def corrected_selection(rows,penalty=Decimal('2.72')):
    # Predeclared conservative one-sided normal Bonferroni diagnostic across
    # five variants and three cost stresses; not an independence certificate.
    # Keep original HARD21/risk constraints; selection sees no held-out results.
    from copy import deepcopy
    rows=deepcopy(rows)
    for row in rows:
        m=row['Monetary']
        days=[x['NetEur'] for x in m['Daily']]
        if m['Score'] is not None and len(days)>1 and all(x is not None for x in days):
            mean=sum(days)/len(days)
            sem=Decimal(str(math.sqrt(float(sum((x-mean)**2 for x in days)/(len(days)*(len(days)-1))))))
            m['Score']=min(m['Score'],mean-penalty*sem)
    return select(rows)

def evaluate(work):
    report=Path('estimator-report');receipt=read(report/'source-receipt.json')
    need(sha(work/'source.json')==SOURCE and sha(work/'estimator-plan.json')==receipt['ProtocolSha256'],
         'ESTIMATOR_SOURCE_BINDING')
    start=time.monotonic();results=[]
    for i,stress in enumerate(STRESSES):
        out=Path('estimator-partitions')/('S'+str(i));out.mkdir(parents=True)
        subprocess.run(['dotnet',REPLAY,'--owner-lifecycle-estimation',str(work/'estimator-plan.json'),
                        str(work/'source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==6 and
             result['SourceSha256']==SOURCE and result['ProtocolSha256']==receipt['ProtocolSha256']
             and result['Orders']==0 and not result['CloudActivated'],'ESTIMATOR_RESULT_BINDING')
        results.append(result);(report/('S'+str(i)+'.json')).write_bytes((out/'result.json').read_bytes())
        print('ESTIMATOR_SCENARIO_COMPLETE',i,flush=True)
    rows=[row for result in results for row in result['Selection']]
    write(report/'summary.json',dict(Study=STUDY,SharedPortfolioEvaluations=18,
        Selection=corrected_selection(rows),UnadjustedSelection=select(rows),
        SelectionMultiplicity=15,SelectionPenalty=Decimal('2.72'),EvaluationSeconds=round(time.monotonic()-start,3),
        SourceSha256=SOURCE,ProtocolSha256=receipt['ProtocolSha256'],Orders=0,CloudActivated=False,
        IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    root=Path('estimator-partitions');files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:return
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    receipt=read(Path('estimator-report/source-receipt.json'))
    seal_files([(p,str(p.relative_to(root))) for p in files],'estimator-sealed-books',public,
        os.environ['GITHUB_RUN_ID'],STUDY,SOURCE,complete=Path('estimator-report/summary.json').exists(),
        protocol_sha=receipt['ProtocolSha256'])

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','restore','evaluate','conserve'))
    p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':
        v=variants();need(len(v)==5 and len({x['Id'] for x in v})==5,'ESTIMATOR_REGISTERED')
        print('ESTIMATOR_REGISTERED',len(v))
    elif a.stage=='restore':restore(a.work)
    elif a.stage=='evaluate':evaluate(a.work)
    else:conserve()
if __name__=='__main__':main()
