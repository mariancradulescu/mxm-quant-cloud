"""New exposed-development study on the verified earlier 13-week source.
Restore exact original archives once, normalize and conserve the child source.
Never execute the old V3 policy or claim independent annual qualification.
"""
import argparse,os,shutil,subprocess,time
from pathlib import Path
from . import owner_eur_recent_archive as archive
from . import owner_eur_archive_funding_2 as funding
from .owner_lifecycle_estimation import variants as estimator_variants,corrected_selection
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import seal_files,sha
from .custody_new import derive_recipient
from .decode import need
from . import source_history_universe as src

STUDY='MONETARY_EARLIER_LIFECYCLE_ESTIMATION_1'
FUNDING_RUN=45759378427
CENSUS_ARTIFACT=15000539686
CENSUS_SHA='fec40efb292ebc71ccb26e82ea063b448f80d17b7330812e8f7ec3b1f6b15da8'
CENSUS_CONTENT_SHA='0fece43b54d788666fa139141adbf3f9cd07d708b3665adc704cafd39cdf0882'

def write(path,obj):Path(path).write_text(exact_json(obj)+'\n')
def variants():
    return [dict(v,UniverseCount=7) for v in estimator_variants()]

def prepare(work):
    start=time.monotonic()
    plan=read(archive.REGISTRY)
    archive.download_archive(plan['OriginalArtifact'],plan['OriginalRun'],plan['OriginalArchiveSha256'],archive.CIPHER_DIR)
    archive.download_archive(plan['RecoveryArtifact'],plan['RecoveryRun'],plan['RecoveryArchiveSha256'],archive.prior.RECOVERY_DIR)
    archive.download_archive(14681397091,44824462289,'06c0181ba732c8fcf70ffe554d532522daa2e5af6e83336baad665028aeae5ed',archive.PUBLIC_DIR)
    archive.download_archive(15089595339,FUNDING_RUN,'262d22935f6f6dbea29d3f8c99982500165047739cb7b055df8f6d35232085e9',Path('earlier-target-input'))
    shutil.copytree('earlier-target-input/original-source-history','original-source-history')
    archive.download_archive(15088981784,FUNDING_RUN,'7b91a8319bcd228298f4748635b23db5f90eddb70f1b4a12e9b644b1c4236147',funding.OUT)
    archive.download_archive(15088689993,FUNDING_RUN,'fb6ed9e5662914bd5269a1ee439062b40d86a1d1eb237219e5ecb616835ddba2',Path('earlier-target-verified'))
    shutil.copyfile('earlier-target-verified/targeted-funding-verified.json','targeted-funding-verified.json')
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    p,digest=funding.registered()
    funding.materialize(p,digest,work,Path('earlier-parent-source.json'),key,str(FUNDING_RUN))
    parent=read(Path('earlier-parent-source.json'))
    need(sha(work/'source.json')==parent['SourceSha256'],'EARLIER_PARENT_SOURCE_BINDING')
    # Pin official class identities from the original census; no inferred class.
    archive.download_archive(CENSUS_ARTIFACT,45568679560,CENSUS_SHA,Path('earlier-census'))
    census=Path('earlier-census/source-census.json')
    need(sha(census)==CENSUS_CONTENT_SHA,'EARLIER_CENSUS_CONTENT')
    classes={x['symbol']:x['officialClass'] for x in read(census)['universe']}
    source=read(work/'source.json')
    need(sorted(m['Market']['Name'] for m in source['Markets'])==sorted(plan['Instruments'])
         and len(source['Markets'])==7,'EARLIER_AUTHENTIC_MARKET_SCOPE')
    for m in source['Markets']:
        name=m['Market']['Name']
        m['Market']['OfficialAssetClass']=classes.get(name)
    source['ExtendedEconomicContext']=True
    proof=dict(ParentNormalizedReceipt=parent,CensusArtifact=CENSUS_ARTIFACT,CensusContentSha256=CENSUS_CONTENT_SHA,
               SourceBrokerRequests=0,OriginalPolicyReruns=0,SourceReconstructionExecutions=1,
               PriorHistoryExposed=True,AnnualConfirmationCertified=False)
    evidence=src.digest(exact_json(proof).encode())
    study=dict(Study=STUDY,Exposure='PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT',
               Start=source['Start'],SelectionFrom=plan['TestBoundaries'][0],
               EvaluationFrom=plan['TestBoundaries'][2],End=source['End'],
               Stresses=[0,0.5,1],OriginalInstruments=plan['Instruments'],Variants=variants())
    registration=src.digest(exact_json(study).encode())
    source.update(ProtocolSha256=registration,EvidenceManifestSha256=evidence)
    study.update(SourceProtocolSha256=registration,EvidenceManifestSha256=evidence)
    write(work/'earlier-source.json',source);write(work/'earlier-plan.json',study)
    report=Path('earlier-report');report.mkdir()
    write(report/'source-receipt.json',dict(Study=STUDY,SourceSha256=sha(work/'earlier-source.json'),
        ProtocolSha256=sha(work/'earlier-plan.json'),Proof=proof,PreparationSeconds=round(time.monotonic()-start,3),
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False))
    (report/'registered-plan.json').write_bytes((work/'earlier-plan.json').read_bytes())
    # Remove local temporary copies only after source verification. Remote
    # original artifacts and their checksums remain untouched.
    for folder in (archive.CIPHER_DIR,archive.prior.RECOVERY_DIR):
        if folder.is_dir():shutil.rmtree(folder)

def cache(work):
    receipt=read(Path('earlier-report/source-receipt.json'))
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    files=[(work/'earlier-source.json','source.json'),(work/'earlier-plan.json','pav-market-protocol.json')]
    files.extend((p,str(p.relative_to(work))) for p in sorted((work/'verified-protection').iterdir()) if p.is_file())
    seal_files(files,'earlier-normalized-source',public,os.environ['GITHUB_RUN_ID'],STUDY,
        receipt['SourceSha256'],protocol_sha=receipt['ProtocolSha256'])

def evaluate(work):
    receipt=read(Path('earlier-report/source-receipt.json'));report=Path('earlier-report')
    need(sha(work/'earlier-source.json')==receipt['SourceSha256'] and
         sha(work/'earlier-plan.json')==receipt['ProtocolSha256'],'EARLIER_SOURCE_BINDING')
    results=[];start=time.monotonic()
    for i,stress in enumerate(STRESSES):
        out=Path('earlier-partitions')/('S'+str(i));out.mkdir(parents=True,exist_ok=False)
        subprocess.run(['dotnet',REPLAY,'--owner-earlier-lifecycle-estimation',str(work/'earlier-plan.json'),
                        str(work/'earlier-source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==6 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256']
             and result['Orders']==0 and not result['CloudActivated'],'EARLIER_RESULT_BINDING')
        results.append(result);(report/('S'+str(i)+'.json')).write_bytes((out/'result.json').read_bytes())
        print('EARLIER_SCENARIO_COMPLETE',i,flush=True)
    write(report/'summary.json',dict(Study=STUDY,SharedPortfolioEvaluations=18,
        Selection=corrected_selection([r for x in results for r in x['Selection']]),
        SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
        EvaluationSeconds=round(time.monotonic()-start,3),PriorHistoryExposed=True,
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    root=Path('earlier-partitions');files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:return
    receipt=read(Path('earlier-report/source-receipt.json'))
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(p,str(p.relative_to(root))) for p in files],'earlier-sealed-books',public,os.environ['GITHUB_RUN_ID'],
        STUDY,receipt['SourceSha256'],complete=Path('earlier-report/summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','prepare','cache','evaluate','conserve'))
    p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':need(len(variants())==5 and all(v['UniverseCount']==7 for v in variants()),'EARLIER_VARIANTS')
    elif a.stage=='prepare':prepare(a.work)
    elif a.stage=='cache':cache(a.work)
    elif a.stage=='evaluate':evaluate(a.work)
    else:conserve()
if __name__=='__main__':main()
