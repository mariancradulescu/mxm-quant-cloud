"""Recover the unexecuted 30-book earlier lifecycle registration.
The failed attempt never reached a policy evaluation; preserve its run and
registered plan. Cross-check the exact pinned artifact via run inventory and
archive SHA, independent of the individual artifact endpoint's metadata.
"""
import hashlib,json,os,subprocess,tempfile,zipfile
from pathlib import Path
from . import owner_earlier_lifecycle_estimation as earlier
from . import owner_eur_recent_archive as archive
from .decode import need

FAILED_RUN=45897899930
FAILED_REVISION='58f33710069636034e70106d6fe5557334f83c10'

def verified_download(artifact_id,run_id,expected_hash,destination):
    repo=os.environ['GITHUB_REPOSITORY']
    endpoint=f'repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100'
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',endpoint]))
    matches=[a for page in pages for a in page['artifacts'] if a['id']==artifact_id]
    need(len(matches)==1,'EARLIER_RECOVERY_ARTIFACT_UNIQUE_IN_RUN')
    a=matches[0]
    need(a['workflow_run']['id']==run_id and not a['expired'] and a['digest']=='sha256:'+expected_hash,
         'EARLIER_RECOVERY_RUN_INVENTORY_BINDING')
    with tempfile.TemporaryFile() as stream:
        subprocess.run(['gh','api',f'repos/{repo}/actions/artifacts/{artifact_id}/zip'],stdout=stream,check=True)
        stream.seek(0);need(hashlib.file_digest(stream,'sha256').hexdigest()==expected_hash,'EARLIER_RECOVERY_ARCHIVE_SHA')
        stream.seek(0);destination=Path(destination);destination.mkdir(mode=0o700)
        with zipfile.ZipFile(stream) as z:
            names=z.namelist()
            need(len(names)==len(set(names)) and all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names),
                 'EARLIER_RECOVERY_SAFE_ARCHIVE')
            z.extractall(destination)
    print('EARLIER_RECOVERY_VERIFIED_ARTIFACT',artifact_id,run_id,flush=True)

def main():
    # Limit the recovery to the same registered method, chronology and source.
    archive.download_archive=verified_download
    earlier.main()
if __name__=='__main__':main()
