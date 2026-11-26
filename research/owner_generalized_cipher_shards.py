"""General ciphertext-only shard publication, including post-upload reconstruction.
The only cap is GitHub Actions' documented 500 artifacts per job; larger
collections can be partitioned into independent publication jobs.
"""
import argparse,json,os,re,shutil
from pathlib import Path
from . import owner_causal_source_shards as cipher

RUN=45885931266
ARTIFACT=15150477614
BYTES=688803495
SHA='d909c7aa4641fe31982f17b3cf49ea028778631baa1710dfdc91542634be35fc'
UPLOAD='actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
ROOT=Path('general-cipher-shards')
ACTION=Path('.generated-shard-upload')
def publication_action(plan,root,action):
    """Generate a local composite using the existing pinned official action.
    No data from ciphertext or external metadata is interpreted as code.
    """
    groups=plan['Shards']
    cipher.need(len(groups)>0 and [r['Index'] for r in groups]==list(range(len(groups))),
        'GENERAL_SHARD_CONTIGUOUS_INDEX')
    cipher.need(len(groups)+1<=500,'GITHUB_ARTIFACTS_PER_JOB_LIMIT')
    action.mkdir(exist_ok=False)
    steps=[]
    for row in groups:
        i=row['Index']
        cipher.need(isinstance(i,int) and 0<row['Bytes']<=plan['TargetMaximumCipherBytes'],'GENERAL_SHARD_SIZE')
        steps.append(dict(id=f'part{i}',uses=UPLOAD,with_={}))
        step=steps[-1];del step['with_'];step['with']=dict(name=f'lifecycle-general-data-{i}',
            path=f'{root}/parts{i}/',**{'compression-level':0,'retention-days':90,'if-no-files-found':'error'})
    env={}
    for i in range(len(groups)):
        env[f'PART{i}_ID']='${{ steps.part'+str(i)+'.outputs.artifact-id }}'
        env[f'PART{i}_SHA']='${{ steps.part'+str(i)+'.outputs.artifact-digest }}'
    steps.append(dict(name='Bind all published artifacts',shell='bash',
        run='python -m research.owner_generalized_cipher_shards receipt',env=env))
    # JSON is valid YAML; all step IDs and paths are deterministic local literals.
    (action/'action.yml').write_text(json.dumps(dict(name='Publish verified cipher shards',
        description='Publish all bounded ciphertext groups with official artifact action',
        runs=dict(using='composite',steps=steps)),indent=2)+'\n')
    return steps

def prepare():
    cipher.download_artifact(ARTIFACT,RUN,SHA,Path('general-original-cipher'),BYTES)
    plan=cipher.partition_checkpoint('general-original-cipher',ROOT)
    cipher.need(plan['SourceRunId']==str(RUN),'GENERAL_ORIGINAL_RUN')
    publication_action(plan,ROOT,ACTION)
    print('GENERAL_SHARDS_READY',len(plan['Shards']),flush=True)

def receipt():
    meta=ROOT/'metadata';plan=json.loads((meta/'shard-plan.json').read_bytes())
    ids=set()
    for row in plan['Shards']:
        i=row['Index'];row['ArtifactId']=int(os.environ[f'PART{i}_ID'])
        row['ArchiveSha256']=os.environ[f'PART{i}_SHA'].removeprefix('sha256:')
        cipher.need(row['ArtifactId']>0 and row['ArtifactId'] not in ids and
            re.fullmatch('[0-9a-f]{64}',row['ArchiveSha256']),'GENERAL_OUTPUT_IDENTITY')
        ids.add(row['ArtifactId'])
    plan.update(Study='GENERAL_LIFECYCLE_CIPHERTEXT_SHARDS_1',
        RepackRunId=os.environ['GITHUB_RUN_ID'],OriginalSourceArtifact=ARTIFACT,
        OriginalSourceRun=RUN,OriginalArchiveSha256=SHA,OriginalResultsModified=False,
        AllOriginalEncryptedBytesPreserved=True)
    cipher.write(meta/'repack-receipt.json',plan)

def verify():
    # Download EVERY uploaded part again; compare exact files, hashes and
    # offsets against the original manifest, without decrypting.
    meta=ROOT/'metadata';target=Path('general-reconstructed');shutil.copytree(meta,target)
    plan=json.loads((target/'repack-receipt.json').read_bytes())
    cipher.download_shards(plan,target)
    original,parts=cipher.verify_checkpoint('general-original-cipher')
    rebuilt,rebuilt_parts=cipher.verify_checkpoint(target)
    cipher.need(original==rebuilt and parts==rebuilt_parts and
        (target/'checkpoint-receipt.json').read_bytes()==(Path('general-original-cipher')/'checkpoint-receipt.json').read_bytes()
        and (target/'manifest.sealed').read_bytes()==(Path('general-original-cipher')/'manifest.sealed').read_bytes(),
        'GENERAL_FULL_RECONSTRUCTION')
    plan.update(FullCipherReconstructionVerified=True,VerifiedParts=len(parts),
        VerifiedShards=len(plan['Shards']))
    cipher.write(meta/'repack-receipt.json',plan)
    print('GENERAL_FULL_RECONSTRUCTION_VERIFIED',len(parts),len(plan['Shards']),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','receipt','verify'));a=p.parse_args()
    dict(prepare=prepare,receipt=receipt,verify=verify)[a.stage]()
if __name__=='__main__':main()
