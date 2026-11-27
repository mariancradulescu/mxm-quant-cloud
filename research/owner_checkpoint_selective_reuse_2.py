"""Repack two pinned completed book checkpoints without replay or decryption.

Selective restoration downloads only the shards containing requested files.
The caller must pin the metadata archive and authenticate the sealed manifest
before using any restored plaintext.
"""
import argparse,json,os,re,shutil
from pathlib import Path
from . import owner_causal_source_shards as cipher
from . import owner_generalized_cipher_shards as general

SOURCES={
    'earlier':(45902423354,15158321576,3193675495,
        '3a200a66b3cea067f7c4891f7d729cb80c3cfb5184cd209e58ec75e8407e8482'),
    'geometry':(45902750757,15156973526,1264946073,
        'ce93e3edc1e98f71573086d966f91bd70d017f89567c9ee51ac0f0dd32371839'),
}

def configure(key):
    general.RUN,general.ARTIFACT,general.BYTES,general.SHA=SOURCES[key]

def prepare(key):
    configure(key)
    general.prepare()
    path=general.ACTION/'action.yml'
    action=json.loads(path.read_bytes())
    for step in action['runs']['steps']:
        if 'with' in step:
            step['with']['name']=key+'-'+step['with']['name']
        if step.get('run')=='python -m research.owner_generalized_cipher_shards receipt':
            step['run']='python -m research.owner_checkpoint_selective_reuse_2 receipt'
    path.write_text(json.dumps(action,indent=2)+'\n')

def selection(receipt,plan,paths):
    requested=set(paths)
    rows=receipt['Files']
    by_path={row['Path']:row for row in rows}
    cipher.need(bool(requested) and len(by_path)==len(rows)==receipt['ExpectedFiles']
        and requested<=by_path.keys(),'SELECTIVE_FILE_SCOPE')
    wanted={}
    all_parts={}
    for row in rows:
        relative=Path(row['Path'])
        cipher.need(not relative.is_absolute() and '..' not in relative.parts
            and relative.as_posix()==row['Path'],'SELECTIVE_SAFE_PATH')
        offset=0
        for p in row['Parts']:
            name=p['File']
            cipher.need(re.fullmatch(r'part-\d+\.sealed',name) and name not in all_parts
                and p['Offset']==offset and p['Bytes']>0,'SELECTIVE_PART_SCOPE')
            all_parts[name]=p['CipherSha256']
            if row['Path'] in requested:wanted[name]=p['CipherSha256']
            offset+=p['Bytes']
        cipher.need(offset==row['Bytes'],'SELECTIVE_FILE_SIZE')
    covered={}
    chosen=[]
    indices=set()
    for group in plan['Shards']:
        index=group['Index']
        cipher.need(type(index) is int and index>=0 and index not in indices,'SELECTIVE_GROUP_INDEX')
        indices.add(index)
        names=set()
        for p in group['Files']:
            name=p['File']
            cipher.need(name in all_parts and name not in covered
                and all_parts[name]==p['CipherSha256'],'SELECTIVE_GROUP_BINDING')
            covered[name]=p['CipherSha256'];names.add(name)
        if names&wanted.keys():chosen.append(group)
    cipher.need(covered==all_parts,'SELECTIVE_MANIFEST_COVERAGE')
    return wanted,chosen

def download_selected(folder,paths,expected_source,expected_manifest):
    """Folder is a previously downloaded, SHA-pinned metadata artifact."""
    folder=Path(folder)
    receipt=json.loads((folder/'checkpoint-receipt.json').read_bytes())
    plan=json.loads((folder/'repack-receipt.json').read_bytes())
    cipher.need(receipt['Complete'] and receipt['Orders']==0 and not receipt['CloudActivated']
        and plan['FullCipherReconstructionVerified']
        and receipt['RunId']==plan['SourceRunId']
        and receipt['SourceSha256']==plan['SourceSha256']==expected_source
        and receipt['ManifestCipherSha256']==plan['ManifestCipherSha256']==expected_manifest
        and cipher.sha(folder/'manifest.sealed')==expected_manifest,'SELECTIVE_SOURCE_BINDING')
    wanted,groups=selection(receipt,plan,paths)
    for row in groups:
        tmp=folder.parent/('selected-shard-'+str(row['Index']))
        cipher.download_artifact(row['ArtifactId'],int(plan['RepackRunId']),row['ArchiveSha256'],tmp)
        cipher.need({p.name for p in tmp.iterdir()}=={p['File'] for p in row['Files']},
            'SELECTIVE_SHARD_MEMBERS')
        for p in row['Files']:
            path=tmp/p['File']
            cipher.need(cipher.sha(path)==p['CipherSha256'],'SELECTIVE_SHARD_HASH')
            if path.name in wanted:
                target=folder/path.name
                cipher.need(not target.exists(),'SELECTIVE_DUPLICATE')
                path.rename(target)
        shutil.rmtree(tmp)
    cipher.need(all(cipher.sha(folder/n)==h for n,h in wanted.items()),'SELECTIVE_COMPLETE')
    return dict(Files=sorted(set(paths)),SelectedShards=len(groups),TotalShards=len(plan['Shards']),
                VerifiedCipherParts=len(wanted),Orders=0,CloudActivated=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','receipt','verify'))
    a=p.parse_args();key=os.environ['MXM_CHECKPOINT_SCOPE']
    configure(key)
    if a.stage=='prepare':prepare(key)
    elif a.stage=='receipt':general.receipt()
    else:general.verify()

if __name__=='__main__':main()
