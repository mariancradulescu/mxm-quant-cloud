"""New paired seven-family common-book research; reuse the sealed authentic source.

This is exposed development, not independent annual confirmation. Each new
variant has ONE 300 EUR book across all 25 markets. The original PAV1
economic runs and their source/checkpoint bytes are never changed or replayed.
"""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import subprocess
import time

from .decode import need
from .merge_eur_scenarios import read, exact_json
from .owner_eur_recent_archive import download_archive
from .owner_pav1_market_time import restore_checkpoint, select, REPLAY
from .custody import seal_new
from .custody_new import derive_recipient

STUDY = 'MONETARY_REDUCE_COMMON_BOOK_1'
SOURCE_RUN = 45837796648
SOURCE_ARTIFACT = 15125624461
SOURCE_ARCHIVE_SHA = '455d204b97c1df36908d55e905aaa893b66d0e12dadbdfb2114201334bed4b9b'
SOURCE_SHA = 'ff5b79b00f9a42778671c0cba849c689ba52f8ccbd1a6f0e8a84a26c87ab5eaf'
ORIGINAL_PLAN_SHA = '280dd54c1c441789f56692a782755727707329c13b9574d0a4dffa7f328247e9'
FAMILIES = ('EQUILIBRIUM_REVERSION', 'INTERMARKET_DISLOCATION', 'M5_FOLLOW',
            'M5_REVERSE', 'PAV1_LOCAL_TRANSITION', 'RANGE_CONTINUATION', 'V33_MULTISCALE_ACTIVITY')
STRESSES = ('0', '0.5', '1')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, obj):
    path.write_text(exact_json(obj)+'\n')


def variants():
    old = read(Path('research/monetary_causal_lifecycle_1.json'))
    profiles = {v['Profile']['EconomicMechanism']:v['Profile'] for v in old['Variants']
                if v['Id'].endswith('__RISK_CONTROL')}
    need(tuple(sorted(profiles)) == FAMILIES, 'REDUCE_REGISTERED_FAMILY_SCOPE')
    rows=[]
    for family in FAMILIES:
        base=dict(profiles[family], MinimumContractVolumeOnly=False,
                  MatchEconomicTransitionHorizonAtFill=True, UseMarketTimeFxValuation=True)
        # Distinct market-time and volume development profiles, not frozen
        # original variants. All candidate volume offers remain broker-bound.
        if family=='PAV1_LOCAL_TRANSITION':
            base['OptimizeTransitionNetVolume']=True
        else:
            base['OptimizeEconomicOpportunityVolume']=True
        for management in ('TRANSITION_VALUE','MONETARY_REDUCE'):
            rows.append(dict(Id=family+'__'+management, UniverseCount=25,
                             Profile=dict(base,EconomicManagement=management)))
    return rows


def restore(work):
    begin=time.monotonic()
    archive=work.parent/'reduce-source-archive'
    download_archive(SOURCE_ARTIFACT,SOURCE_RUN,SOURCE_ARCHIVE_SHA,archive)
    downloaded=time.monotonic()
    restore_checkpoint(archive,work,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),
                       str(SOURCE_RUN),SOURCE_SHA)
    need(file_digest(work/'pav-market-protocol.json')==ORIGINAL_PLAN_SHA,
         'REDUCE_ORIGINAL_PROTOCOL_IDENTITY')
    receipt=read(archive/'checkpoint-receipt.json')
    need(receipt['Complete'] and len(receipt['Files'])==130,'REDUCE_CHECKPOINT_SCOPE')
    elapsed=time.monotonic()
    report=Path('reduce-report');report.mkdir(exist_ok=False)
    write(report/'source-reuse.json',dict(Study=STUDY,SourceRun=SOURCE_RUN,
        SourceArtifact=SOURCE_ARTIFACT,SourceArchiveSha256=SOURCE_ARCHIVE_SHA,
        SourceSha256=SOURCE_SHA,OriginalPlanSha256=ORIGINAL_PLAN_SHA,
        VerifiedCheckpointFiles=130,DownloadSeconds=round(downloaded-begin,3),
        VerifyAndRestoreSeconds=round(elapsed-downloaded,3),ReconstructionExecutions=0,
        SourceBrokerRequests=0,OriginalResultsModified=False,Orders=0,CloudActivated=False))
    print('REDUCE_SOURCE_REUSED',round(elapsed-begin,3),'seconds',flush=True)


def evaluate(work):
    need(file_digest(work/'source.json')==SOURCE_SHA and
         file_digest(work/'pav-market-protocol.json')==ORIGINAL_PLAN_SHA,'REDUCE_SOURCE_IDENTITY')
    original=read(work/'pav-market-protocol.json')
    plan=dict(original,Study=STUDY,Variants=variants())
    path=work.parent/'monetary-reduce-protocol.json'
    write(path,plan)
    report=Path('reduce-report')
    (report/'registered-plan.json').write_bytes(path.read_bytes())
    results=[]
    start=time.monotonic()
    # Each scenario has separate state; sequential processing avoids memory
    # contention while reusing one verified local source and tape.
    for index,stress in enumerate(STRESSES):
        out=Path('reduce-partitions')/('S'+str(index));out.mkdir(parents=True,exist_ok=False)
        began=time.monotonic()
        subprocess.run(['dotnet',REPLAY,'--owner-monetary-reduce-common-book',str(path),
                        str(work/'source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SourceSha256']==SOURCE_SHA and
             result['ProtocolSha256']==file_digest(path) and
             result['SharedPortfolioEvaluations']==15 and result['Orders']==0 and
             not result['CloudActivated'] and not result['IndependentConfirmationCertified'],
             'REDUCE_NATIVE_RESULT_BINDING')
        results.append(result)
        (report/('S'+str(index)+'.json')).write_bytes((out/'result.json').read_bytes())
        print('REDUCE_PARTITION_COMPLETE',index,round(time.monotonic()-began,3),'seconds',flush=True)
    selection=select([row for result in results for row in result['Selection']])
    write(report/'economic-summary.json',dict(Study=STUDY,SourceSha256=SOURCE_SHA,
        ProtocolSha256=file_digest(path),SharedPortfolioEvaluations=45,Families=list(FAMILIES),
        Selection=selection,EvaluationSeconds=round(time.monotonic()-start,3),
        OriginalResultsModified=False,SourceBrokerRequests=0,Orders=0,CloudActivated=False,
        IndependentConfirmationCertified=False,EconomicPromotionCertified=False,
        Scope='SEPARATE_PAIRED_FAMILY_BOOKS_NOT_JOINT_MULTI_FAMILY_SELECTION'))
    print('REDUCE_ECONOMIC_COMPLETE',selection['Decision'],flush=True)


def conserve():
    # Persist only NEW books, not another redundant encrypted source copy.
    # Each file is bound to the immutable source hash and authenticated run.
    root=Path('reduce-partitions')
    if not root.exists():
        return
    files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:
        return
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    rid=os.environ['GITHUB_RUN_ID']
    destination=Path('reduce-sealed-books');destination.mkdir(exist_ok=False)
    rows=[];counter=0
    for path in files:
        parts=[];offset=0
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(33554432),b''):
                cipher=seal_new(gzip.compress(chunk,compresslevel=1,mtime=0),public,rid)
                name=f'part-{counter:06d}.sealed';counter+=1
                (destination/name).write_bytes(cipher)
                parts.append(dict(File=name,Offset=offset,Bytes=len(chunk),
                                  PlainSha256=digest(chunk),CipherSha256=digest(cipher)))
                offset+=len(chunk)
        rows.append(dict(Path=str(path.relative_to(root)),Bytes=offset,
                         Sha256=file_digest(path),Parts=parts))
    manifest=dict(Study=STUDY,RunId=rid,SourceRun=SOURCE_RUN,SourceArtifact=SOURCE_ARTIFACT,
                  SourceSha256=SOURCE_SHA,Files=rows,Complete=len(rows)==90,
                  Orders=0,CloudActivated=False)
    raw=(exact_json(manifest)+'\n').encode()
    cipher=seal_new(gzip.compress(raw,compresslevel=1,mtime=0),public,rid)
    (destination/'manifest.sealed').write_bytes(cipher)
    write(destination/'receipt.json',dict(Study=STUDY,RunId=rid,SourceSha256=SOURCE_SHA,
        Files=len(rows),Complete=manifest['Complete'],ManifestCipherSha256=digest(cipher),
        OriginalSourceReencrypted=False,Orders=0,CloudActivated=False))
    print('REDUCE_BOOKS_CONSERVED',len(rows),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('check','restore','evaluate','conserve'))
    parser.add_argument('--work',type=Path)
    args=parser.parse_args()
    if args.stage=='check':
        rows=variants()
        need(len(rows)==14 and len({r['Id'] for r in rows})==14,'REDUCE_VARIANT_COUNT')
        print('REDUCE_NEW_VARIANTS',len(rows),flush=True)
    elif args.stage=='restore':restore(args.work)
    elif args.stage=='evaluate':evaluate(args.work)
    else:conserve()


if __name__=='__main__':main()
