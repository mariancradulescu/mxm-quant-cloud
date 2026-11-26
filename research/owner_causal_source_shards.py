"""Repackage an existing encrypted source without decrypting or replaying it.

Small independently pinned artifact archives avoid the 512 MiB transfer limit.
The original authenticated checkpoint manifest and every cipher byte survive.
"""
import argparse,hashlib,json,os,re,shutil,subprocess,zipfile
from pathlib import Path

SOURCE_RUN=45874059214
SOURCE_ARTIFACT=15144417351
SOURCE_BYTES=537429578
SOURCE_SHA='75e0b966f5ba3571b6235ac840adddbb00f498b080f766f2ddd3e95cd678c7e4'
LIMIT=268435456

def need(condition,message):
    if not condition:raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def write(path,value):Path(path).write_text(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n')

def download_artifact(artifact,run,digest,destination,expected_size=None):
    repo=os.environ['GITHUB_REPOSITORY'];base=f'repos/{repo}/actions/artifacts/{artifact}'
    meta=json.loads(subprocess.check_output(['gh','api',base]))
    need(meta['id']==artifact and meta['workflow_run']['id']==run and not meta['expired'] and
         meta['digest']=='sha256:'+digest and (expected_size is None or meta['size_in_bytes']==expected_size),
         'SHARD_INPUT_ARTIFACT_IDENTITY')
    destination=Path(destination);destination.mkdir(exist_ok=False)
    archive=destination.with_suffix('.zip')
    with archive.open('xb') as stream:subprocess.run(['gh','api',base+'/zip'],stdout=stream,check=True)
    need(sha(archive)==digest,'SHARD_INPUT_ARCHIVE_HASH')
    with zipfile.ZipFile(archive) as zipped:
        names=zipped.namelist()
        need(len(names)==len(set(names)) and all(Path(name).name==name and
            (name in ('checkpoint-receipt.json','manifest.sealed','shard-plan.json','repack-receipt.json') or
             re.fullmatch(r'part-\d+\.sealed',name)) for name in names),'SHARD_ARCHIVE_SAFE_MEMBERS')
        for name in names:
            with zipped.open(name) as stream,(destination/name).open('xb') as out:shutil.copyfileobj(stream,out,1048576)
    archive.unlink()

def verify_checkpoint(folder):
    folder=Path(folder);receipt=json.loads((folder/'checkpoint-receipt.json').read_bytes())
    need(receipt['Complete'] and receipt['ExpectedFiles']==len(receipt['Files']) and
         receipt['Orders']==0 and not receipt['CloudActivated'] and
         sha(folder/'manifest.sealed')==receipt['ManifestCipherSha256'],'SHARD_ORIGINAL_MANIFEST')
    parts={}
    for row in receipt['Files']:
        offset=0
        for part in row['Parts']:
            name=part['File'];need(re.fullmatch(r'part-\d+\.sealed',name) and name not in parts,
                                 'SHARD_UNIQUE_SAFE_PART')
            need(part['Offset']==offset and part['Bytes']>0 and sha(folder/name)==part['CipherSha256'],
                 'SHARD_ORIGINAL_PART_INTEGRITY')
            offset+=part['Bytes'];parts[name]=part['CipherSha256']
        need(offset==row['Bytes'],'SHARD_ORIGINAL_PART_OFFSETS')
    return receipt,parts

def partition_checkpoint(folder,destination,limit=LIMIT):
    folder=Path(folder);destination=Path(destination);receipt,parts=verify_checkpoint(folder)
    destination.mkdir(exist_ok=False);metadata=destination/'metadata';metadata.mkdir()
    for name in ('checkpoint-receipt.json','manifest.sealed'):shutil.copyfile(folder/name,metadata/name)
    groups=[];current=[];size=0
    for name in sorted(parts):
        length=(folder/name).stat().st_size
        need(0<length<=limit,'SHARD_SINGLE_FILE_LIMIT')
        if current and size+length>limit:groups.append((current,size));current=[];size=0
        current.append(dict(File=name,CipherSha256=parts[name],Bytes=length));size+=length
    if current:groups.append((current,size))
    rows=[]
    for index,(files,total) in enumerate(groups):
        target=destination/f'parts{index}';target.mkdir()
        for file in files:os.link(folder/file['File'],target/file['File'])
        rows.append(dict(Index=index,Bytes=total,Files=files))
    plan=dict(SourceRunId=receipt['RunId'],SourceSha256=receipt['SourceSha256'],
        ProtocolSha256=receipt['ProtocolSha256'],ManifestCipherSha256=receipt['ManifestCipherSha256'],
        TargetMaximumCipherBytes=limit,Shards=rows,OriginalEncryptedParts=len(parts),
        Decryptions=0,EconomicPolicyExecutions=0,SourceBrokerRequests=0,Orders=0,CloudActivated=False)
    write(metadata/'shard-plan.json',plan)
    return plan

def download_shards(receipt,metadata_folder):
    """After pinning/downloading the metadata artifact, assemble for restore_checkpoint."""
    folder=Path(metadata_folder)
    for row in receipt['Shards']:
        temporary=folder.parent/f"cipher-shard-{row['Index']}"
        download_artifact(row['ArtifactId'],int(receipt['RepackRunId']),row['ArchiveSha256'],temporary)
        need({p.name for p in temporary.iterdir()}=={p['File'] for p in row['Files']},'SHARD_EXACT_FILE_SET')
        for part in row['Files']:
            path=temporary/part['File']
            need(sha(path)==part['CipherSha256'] and not (folder/path.name).exists(),'SHARD_RESTORE_INTEGRITY')
            path.rename(folder/path.name)
        temporary.rmdir()
    manifest,_=verify_checkpoint(folder)
    need(manifest['SourceSha256']==receipt['SourceSha256'] and
         manifest['ManifestCipherSha256']==receipt['ManifestCipherSha256'],'SHARD_RESTORED_SOURCE_BINDING')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','receipt'));args=parser.parse_args()
    if args.stage=='prepare':
        download_artifact(SOURCE_ARTIFACT,SOURCE_RUN,SOURCE_SHA,Path('original-encrypted-cache'),SOURCE_BYTES)
        plan=partition_checkpoint('original-encrypted-cache','source-shards')
        need(0<len(plan['Shards'])<=3 and plan['SourceRunId']==str(SOURCE_RUN),'SHARD_FIXED_ORIGINAL_SCOPE')
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write(f"groups={len(plan['Shards'])}\n")
        print('ORIGINAL_CIPHER_SOURCE_VERIFIED_AND_SHARDED',len(plan['Shards']),flush=True)
    else:
        path=Path('source-shards/metadata');plan=json.loads((path/'shard-plan.json').read_bytes())
        for row in plan['Shards']:
            row['ArtifactId']=int(os.environ[f"PART{row['Index']}_ID"])
            row['ArchiveSha256']=os.environ[f"PART{row['Index']}_SHA"].removeprefix('sha256:')
            need(re.fullmatch('[0-9a-f]{64}',row['ArchiveSha256']),'SHARD_OUTPUT_ARCHIVE_HASH')
        plan.update(Study='CAUSAL_SOURCE_CIPHERTEXT_SHARDS_1',RepackRunId=os.environ['GITHUB_RUN_ID'],
            OriginalSourceArtifact=SOURCE_ARTIFACT,OriginalSourceRun=SOURCE_RUN,OriginalArchiveSha256=SOURCE_SHA,
            OriginalResultsModified=False,AllOriginalEncryptedBytesPreserved=True)
        write(path/'repack-receipt.json',plan)

if __name__=='__main__':main()
