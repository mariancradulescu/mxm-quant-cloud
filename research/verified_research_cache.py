"""Bounded encrypted files reusable by owner_pav1_market_time.restore_checkpoint.

The caller pins the complete artifact digest, run and source digest on restore.
Neither this cache nor its receipts grant execution or promotion authority.
"""
import gzip,hashlib
from pathlib import Path
from .custody import seal_new
from .merge_eur_scenarios import exact_json
from .decode import need

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def seal_files(files,destination,public,run,study,source_sha,complete=True,protocol_sha=None):
    destination=Path(destination);destination.mkdir(exist_ok=False)
    records=[];counter=0
    for path,relative in files:
        path=Path(path);relative=Path(relative)
        need(not path.is_symlink() and not relative.is_absolute() and '..' not in relative.parts,'CACHE_SAFE_FILE')
        parts=[];offset=0
        with path.open('rb') as stream:
            for raw in iter(lambda:stream.read(33554432),b''):
                cipher=seal_new(gzip.compress(raw,compresslevel=1,mtime=0),public,run)
                name=f'part-{counter:06d}.sealed';counter+=1;(destination/name).write_bytes(cipher)
                parts.append(dict(File=name,Offset=offset,Bytes=len(raw),PlainSha256=hashlib.sha256(raw).hexdigest(),
                                  CipherSha256=hashlib.sha256(cipher).hexdigest()))
                offset+=len(raw)
        records.append(dict(Path=relative.as_posix(),Bytes=offset,Sha256=sha(path),Parts=parts))
        print('VERIFIED_CACHE_FILE',relative.as_posix(),offset,flush=True)
    manifest=dict(Study=study,RunId=run,Schema='MXM_BOUNDED_FILE_CHECKPOINT_V1',Complete=complete,
        Files=records,ExpectedFiles=len(records),SourceSha256=source_sha,ProtocolSha256=protocol_sha,
        MaximumPlainChunkBytes=33554432,Orders=0,CloudActivated=False)
    raw=(exact_json(manifest)+'\n').encode()
    (destination/'manifest.sealed').write_bytes(seal_new(gzip.compress(raw,compresslevel=1,mtime=0),public,run))
    manifest['ManifestCipherSha256']=sha(destination/'manifest.sealed')
    (destination/'checkpoint-receipt.json').write_text(exact_json(manifest)+'\n')
    return manifest
