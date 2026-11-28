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

FAILED_RUN=45898672019
FAILED_REVISION='699e590c6a6e055940f74807c8dd0f4b6977acc2'

def normalized_run_id(value):
    # GitHub REST returns an integer; Actions environment variables are strings.
    # Reject bool, floats, noncanonical text and nonpositive IDs rather than
    # coercing arbitrary values into a valid identity.
    need(type(value) is int or (type(value) is str and value.isascii() and
         value.isdecimal() and not value.startswith('0')), 'EARLIER_RECOVERY_RUN_ID')
    number=int(value)
    need(number>0,'EARLIER_RECOVERY_RUN_ID')
    return number

def verified_download(artifact_id,run_id,expected_hash,destination):
    run_id=normalized_run_id(run_id)
    repo=os.environ['GITHUB_REPOSITORY']
    endpoint=f'repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100'
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',endpoint]))
    matches=[a for page in pages for a in page['artifacts'] if a['id']==artifact_id]
    need(len(matches)==1,'EARLIER_RECOVERY_ARTIFACT_UNIQUE_IN_RUN')
    a=matches[0]
    need(normalized_run_id(a['workflow_run']['id'])==run_id,'EARLIER_RECOVERY_RUN_ID')
    need(a['expired'] is False,'EARLIER_RECOVERY_ARTIFACT_EXPIRED')
    need(a['digest']=='sha256:'+expected_hash,
         f"EARLIER_RECOVERY_DIGEST_MISMATCH artifact={artifact_id} expected={expected_hash} actual={a['digest']}")
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
