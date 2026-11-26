"""New paired-management selection and shared 29-market EUR300 research.

Reuse normalized sources, exact-readback AAPL evidence and bounded checkpoints.
Frozen studies remain immutable. New trades belong only to this registration.
"""
import argparse,json,os,subprocess
from decimal import Decimal
from pathlib import Path
from . import owner_competitive_families as common
from . import owner_aapl_frozen_funding as aapl
from . import source_history_universe as src
from . import owner_eer1_source as eer
from . import owner_funding_prefix_settlement as prefix
from .owner_eur_recent_archive import download_archive
from .merge_eur_scenarios import read,exact_json
from .custody_new import derive_recipient
from .verified_research_cache import seal_files,sha
from .decode import need

STUDY='MONETARY_CAUSAL_MANAGEMENT_1'
AAPL_RUN=45870893197
AAPL_ARTIFACT=15141978544
AAPL_SHA='a34919b09ce263562660ea427c62ae75fa27e298e6ff34000ed36c5ddcc6172a'

def write(path,value):Path(path).write_text(exact_json(value)+'\n')

def variants():
    rows=common.variants()
    for row in rows:row['Profile']['OptimizeEconomicOpportunityVolume']=True
    rows.append(dict(Id='JOINT_CAUSAL_MANAGEMENT',UniverseCount=29,
        Profile=dict(rows[0]['Profile'],SelectEconomicManagementCausally=True)))
    return rows

def apply_overlay(source,rows):
    need(len(rows)==2 and sorted(r['Target']['At'] for r in rows)==[1793656800000,1794434400000],
         'CAUSAL_AAPL_TARGETS')
    tape=next(t for t in source['Tapes'] if t['Name']=='AAPL.US')
    for row in rows:
        target=row['Target'];witness=row['Witness']
        need(target['Symbol']=='AAPL.US' and target['Side']=='BID' and
             witness['Status']=='AUTHENTIC_LATEST_PREFIX' and witness['SearchThrough']==target['At'] and
             witness['SearchFrom']==target['At']-345600000 and
             0<witness['At']<=target['At'] and target['At']-witness['At']<=345600000 and
             witness['PrefixNewestFirst'] and witness['LeadingTimestampComplete'] and Decimal(witness['Price'])>0,
             'CAUSAL_AAPL_PREFIX')
        matching=[q for q in tape['FundingQuotes'] if q['At']==target['At']]
        need(len(matching)<=1,'CAUSAL_DUPLICATE_FUNDING_CLOCK')
        if matching:q=matching[0]
        else:
            q=dict(At=target['At'],RequestedCoverage=False,BidAt=None,AskAt=None,Bid=None,Ask=None)
            tape['FundingQuotes'].append(q)
        need(q.get('LatestBidPrefix') is None and q.get('Bid') is None,'CAUSAL_OVERLAY_MUST_FILL_MISSING_ONLY')
        q['LatestBidPrefix']=witness
    tape['FundingQuotes'].sort(key=lambda q:q['At'])

def prepare(work):
    common.prepare(work)
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    folder=work.parent/'causal-aapl-protected';download_archive(AAPL_ARTIFACT,AAPL_RUN,AAPL_SHA,folder)
    receipt=read(folder/'receipt.json');data=eer.unpack(folder,receipt['sealed'],key,str(AAPL_RUN))
    need(data['runId']==str(AAPL_RUN) and data['protocolSha256']==src.digest(src.canonical(aapl.PLAN))
         and receipt['requests']==2,'CAUSAL_AAPL_SEAL_BINDING')
    packets=data['packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'CAUSAL_AAPL_ACCOUNT')
    journal=src.ReadbackJournal(packets);rows=prefix.collect(journal,account,aapl.PLAN)
    need(rows==data['rows'] and journal.index==len(packets)==2,'CAUSAL_AAPL_EXACT_READBACK')
    source=read(work/'competitive-source.json');plan=read(work/'competitive-plan.json')
    apply_overlay(source,rows)
    plan.update(Study=STUDY,Variants=variants())
    old=read(Path('competitive-report/source-receipt.json'))
    proof=dict(ParentNormalizedSources=old,RecoveredAaplRun=AAPL_RUN,RecoveredAaplArtifact=AAPL_ARTIFACT,
        RecoveredAaplArchiveSha256=AAPL_SHA,RecoveredAaplExactPackets=2,
        FinancialWitnesses=rows,SourceBrokerRequests=0,RawSourceReconstructionExecutions=0,
        IndependentConfirmationCertified=False,AnnualBarsAreNotAnnualEconomicExecution=True)
    registration=src.digest(exact_json(plan).encode());evidence=src.digest(exact_json(proof).encode())
    source.update(ProtocolSha256=registration,EvidenceManifestSha256=evidence,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=registration,EvidenceManifestSha256=evidence)
    write(work/'causal-source.json',source);write(work/'causal-plan.json',plan)
    report=Path('causal-report');report.mkdir()
    write(report/'source-receipt.json',dict(Study=STUDY,SourceSha256=sha(work/'causal-source.json'),
        ProtocolSha256=sha(work/'causal-plan.json'),Proof=proof,Orders=0,CloudActivated=False))
    (report/'registered-plan.json').write_bytes((work/'causal-plan.json').read_bytes())

def cache_source(work):
    receipt=read(Path('causal-report/source-receipt.json'))
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    files=[(work/'causal-source.json','source.json'),(work/'causal-plan.json','pav-market-protocol.json')]
    files.extend((p,str(p.relative_to(work))) for p in sorted((work/'verified-protection').iterdir()) if p.is_file())
    seal_files(files,'causal-normalized-source',public,os.environ['GITHUB_RUN_ID'],STUDY,
        receipt['SourceSha256'],protocol_sha=receipt['ProtocolSha256'])

def evaluate(work):
    report=Path('causal-report');receipt=read(report/'source-receipt.json')
    need(sha(work/'causal-source.json')==receipt['SourceSha256'] and
         sha(work/'causal-plan.json')==receipt['ProtocolSha256'],'CAUSAL_SOURCE_BINDING')
    results=[]
    for i,stress in enumerate(common.STRESSES):
        out=Path('causal-partitions')/('S'+str(i));out.mkdir(parents=True,exist_ok=False)
        subprocess.run(['dotnet',common.REPLAY,'--owner-causal-management',str(work/'causal-plan.json'),
                        str(work/'causal-source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==4 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256']
             and result['Orders']==0 and not result['CloudActivated'],'CAUSAL_RESULT_BINDING')
        results.append(result);(report/('S'+str(i)+'.json')).write_bytes((out/'result.json').read_bytes())
        print('CAUSAL_MANAGEMENT_SCENARIO_COMPLETE',i,flush=True)
    write(report/'summary.json',dict(Study=STUDY,SharedPortfolioEvaluations=12,
        Selection=common.select([row for result in results for row in result['Selection']]),
        SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    root=Path('causal-partitions');files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:return
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    receipt=read(Path('causal-report/source-receipt.json'))
    seal_files([(p,str(p.relative_to(root))) for p in files],'causal-sealed-books',public,os.environ['GITHUB_RUN_ID'],
        STUDY,receipt['SourceSha256'],complete=Path('causal-report/summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('check','prepare','cache','evaluate','conserve'))
    parser.add_argument('--work',type=Path);args=parser.parse_args()
    if args.stage=='check':
        need(len(variants())==3 and sum(v['Profile'].get('SelectEconomicManagementCausally',False) for v in variants())==1,
             'CAUSAL_REGISTERED_VARIANTS')
        print('CAUSAL_MANAGEMENT_REGISTERED')
    elif args.stage=='prepare':prepare(args.work)
    elif args.stage=='cache':cache_source(args.work)
    elif args.stage=='evaluate':evaluate(args.work)
    else:conserve()

if __name__=='__main__':main()
