"""A distinct causal lifecycle study; preserved archives are read, never replayed.

One source reconstruction is byte-bound to the original geometry experiment.
Public summaries contain conditional financial evidence, never raw source tapes.
"""
import argparse
from collections import Counter
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess

from . import owner_monetary_geometry_breadth as prior
from . import source_history_universe as src
from . import owner_eur_recent_archive as archive
from .decode import need
from .merge_eur_scenarios import exact_json, read

REGISTRY=Path('research/monetary_causal_lifecycle_1.json')
ORIGINAL=Path('original-geometry-result')
REPLAY='src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll'


def registered():
    raw=REGISTRY.read_bytes(); p=json.loads(raw)
    old,_=prior.registered()
    need(p['Study']=='MONETARY_CAUSAL_LIFECYCLE_1' and p['OriginalGeometryRun']==45798422394 and
         p['OriginalGeometryArtifact']==15107985666 and p['Instruments']==old['Instruments'] and
         all(p[k]==old[k] for k in ('Exposure','Start','SelectionFrom','EvaluationFrom','End','Stresses','SamplingIntervalMs')) and
         p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'CAUSAL_LIFECYCLE_REGISTRY')
    variants=p['Variants']
    need(len(variants)==len({v['Id'] for v in variants})==31 and
         {v['Mechanism'] for v in variants}=={v['Mechanism'] for v in old['Variants']} and
         all(v['MonetaryTraining'] and v['Profile']['KeepAdmissionRiskAtFill'] and
             v['Profile']['ResizeWithinAdmissionRiskAtFill'] and
             not v['Profile'].get('ModelFundingAtPriorClosedSessionQuote') for v in variants),
         'CAUSAL_LIFECYCLE_VARIANTS')
    for mechanism in {v['Mechanism'] for v in variants}:
        rows=[v for v in variants if v['Mechanism']==mechanism]
        need(len(rows)==(7 if mechanism=='PAV1_LOCAL_TRANSITION' else 4) and
             sum(v['Reference'] for v in rows)==1,'CAUSAL_LIFECYCLE_PARTITION')
    return p,src.digest(raw)


def download(p):
    old,_=prior.registered(); prior.download(old)
    archive.download_archive(p['OriginalGeometryArtifact'],p['OriginalGeometryRun'],
        p['OriginalGeometrySha256'],ORIGINAL)
    original=read(ORIGINAL/'economic-opportunities.json')
    need(original['Study']=='MONETARY_GEOMETRY_BREADTH_1' and len(original['Results'])==7 and
         all(r['SelectedDecision']=='WAIT' for r in original['Results']),'CAUSAL_LIFECYCLE_ORIGINAL')


def diagnose(original):
    """Recalculate the original conditional result without manufacturing NET."""
    output=[]
    for result in original['Results']:
        for row in result['HeldOut']:
            if row['Stress']!=0:continue
            episodes=row['Episodes']; known=[e for e in episodes if e['NetEur'] is not None]
            risk=sorted(e['CostRiskFraction'] for e in known if e['CostRiskFraction'] is not None)
            output.append(dict(Mechanism=result['Mechanism'],Id=row['Id'],Known=len(known),
                KnownNetSubtotalEur=sum((e['NetEur'] for e in known),Decimal(0)),
                FastClosures=sum(e['CloseAt']-e['OpenAt']<300000 for e in known),
                MedianCostRiskFraction=risk[len(risk)//2] if risk else None,
                UnfilledReasons=dict(Counter(e['FillReasons'] for e in episodes if e['Status']=='UNFILLED')),
                BySymbol=[dict(Symbol=n,Known=sum(e['Symbol']==n for e in known),
                    KnownNetSubtotalEur=sum((e['NetEur'] for e in known if e['Symbol']==n),Decimal(0)))
                    for n in sorted({e['Symbol'] for e in known})],
                Unresolved=[e for e in episodes if e['Status'] in ('UNKNOWN_CLOSED','RIGHT_CENSORED')]))
    return dict(Study='MONETARY_GEOMETRY_BREADTH_1_SOURCE_ONLY_RECALCULATION',Results=output,
        OriginalResultsModified=False,SourceBrokerRequests=0,Orders=0,CloudActivated=False)


def materialize(p,digest,work,receipt_path):
    old,old_digest=prior.registered()
    revision=os.environ['GITHUB_SHA']
    # Exact historical revision reconstructs exactly the prior source bytes.
    # No economic engine invocation is part of this operation.
    os.environ['GITHUB_SHA']=p['OriginalGeometryRevision']
    try: prior.materialize(old,old_digest,work,receipt_path)
    finally: os.environ['GITHUB_SHA']=revision
    original_receipt=read(ORIGINAL/'opportunity-source.json')
    reconstructed=read(receipt_path)
    raw=(work/'source.json').read_bytes()
    need(src.digest(raw)==original_receipt['SourceSha256']==reconstructed['SourceSha256'] and
         reconstructed==original_receipt,'CAUSAL_LIFECYCLE_EXACT_ORIGINAL_SOURCE')
    source=json.loads(raw)
    proof=dict(OriginalGeometryRun=p['OriginalGeometryRun'],OriginalGeometryArtifact=p['OriginalGeometryArtifact'],
        OriginalGeometrySha256=p['OriginalGeometrySha256'],OriginalGeometrySourceSha256=src.digest(raw),
        SourceByteIdentity=True,PriorProof=original_receipt['Proof'],MarketCount=len(source['Markets']),
        OriginalResultsModified=False,SourceBrokerRequests=0)
    source.update(ProtocolSha256=digest,EvidenceManifestSha256=src.digest(src.canonical(proof)),EngineRevision=revision)
    plan={k:p[k] for k in ('Study','Exposure','Start','SelectionFrom','EvaluationFrom','End','SamplingIntervalMs','Stresses','Variants')}
    plan.update(SourceProtocolSha256=digest,EvidenceManifestSha256=source['EvidenceManifestSha256'])
    raw,pr=src.canonical(source),src.canonical(plan)
    (work/'source.json').write_bytes(raw); (work/'opportunity-protocol.json').write_bytes(pr)
    receipt_path.write_bytes(src.canonical(dict(Study=p['Study'],Proof=proof,SourceSha256=src.digest(raw),
        ProtocolSha256=src.digest(pr),EvidenceManifestSha256=source['EvidenceManifestSha256'],
        SourceBrokerRequests=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False)))
    Path('original-geometry-diagnosis.json').write_text(exact_json(diagnose(read(ORIGINAL/'economic-opportunities.json')))+'\n')
    print('CAUSAL_LIFECYCLE_SOURCE_VERIFIED',len(source['Markets']),'MARKETS',flush=True)


def partition(p,work,receipt,mechanism):
    variants=[v for v in p['Variants'] if v['Mechanism']==mechanism]
    need(bool(variants),'CAUSAL_LIFECYCLE_PARTITION_SCOPE')
    out=Path('partitions')/mechanism; out.mkdir(parents=True,exist_ok=False)
    subprocess.run(['dotnet',REPLAY,'--owner-opportunity-screen',str(work/'opportunity-protocol.json'),
        str(work/'source.json'),str(out/'opportunity-result.json'),str(work/'verified-protection')],
        env=dict(os.environ,MXM_OPPORTUNITY_MECHANISM=mechanism),check=True)
    result=read(out/'opportunity-result.json'); source=read(receipt)
    need(all(result[k]==source[k] for k in ('SourceSha256','ProtocolSha256','EvidenceManifestSha256')) and
         result['RegisteredMarketCount']==21 and len(result['HeldOut'])==len(variants)*3 and
         result['SharedPortfolioEvaluations']==(len(variants)+1)*3 and
         result['Orders']==result['SourceBrokerRequests']==0 and not result['CloudActivated'],
         'CAUSAL_LIFECYCLE_PARTITION_RESULT')
    for book in result['CommonBooks']:
        if book['Id']=='CASH_CONTROL':
            need(book['Result']['CashEur']==300 and book['Result']['Closed']==0,'CAUSAL_LIFECYCLE_CASH')
    (out/'opportunity-source.json').write_bytes(receipt.read_bytes())
    (out/'opportunity-protocol.json').write_bytes((work/'opportunity-protocol.json').read_bytes())
    print('CAUSAL_LIFECYCLE_PARTITION_COMPLETE',mechanism,result['SelectedDecision'],flush=True)


def combine(p):
    roots=sorted(Path('partitions').glob('*/opportunity-result.json'))
    need(len(roots)==7,'CAUSAL_LIFECYCLE_ALL_PARTITIONS')
    first=roots[0].parent; results=[]
    for path in roots:
        for name in ('opportunity-protocol.json','opportunity-source.json'):
            need((path.parent/name).read_bytes()==(first/name).read_bytes(),'CAUSAL_LIFECYCLE_PARTITION_IDENTITY')
        results.append(read(path))
    need({r['Mechanism'] for r in results}=={v['Mechanism'] for v in p['Variants']} and
         sum(len(r['HeldOut']) for r in results)==93 and
         sum(r['SharedPortfolioEvaluations'] for r in results)==114,'CAUSAL_LIFECYCLE_COMPLETE')
    out=Path('lifecycle-report');out.mkdir(exist_ok=False)
    for name in ('opportunity-protocol.json','opportunity-source.json'):
        (out/name).write_bytes((first/name).read_bytes())
    (out/'economic-lifecycle.json').write_text(exact_json(dict(Study=p['Study'],Results=results,
        IsolatedCombinations=93,SharedPortfolioEvaluations=114,IndependentConfirmationCertified=False,
        Orders=0,CloudActivated=False))+'\n')
    for r in results: print(r['Mechanism'],r['SelectedDecision'],flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('download','materialize','partition','combine'))
    parser.add_argument('--work',type=Path);parser.add_argument('--receipt',type=Path);parser.add_argument('--mechanism')
    a=parser.parse_args();p,digest=registered()
    if a.stage=='download':download(p)
    elif a.stage=='materialize':materialize(p,digest,a.work,a.receipt)
    elif a.stage=='partition':partition(p,a.work,a.receipt,a.mechanism)
    else:combine(p)


if __name__=='__main__':main()
