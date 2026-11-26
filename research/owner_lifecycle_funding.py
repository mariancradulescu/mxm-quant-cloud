"""Recover missing lifecycle financing; reuse exact GOOG witness and retain verified registry."""
import argparse,json,os,subprocess,time
from pathlib import Path
from . import source_history_universe as src
from . import owner_eer1_source as eer
from . import owner_funding_prefix_settlement as prefix
from .owner_causal_source_shards import download_artifact,download_shards
from .owner_pav1_market_time import restore_checkpoint
from .owner_eur_recent_archive import download_archive
from .owner_monetary_reduce_common_book import REPLAY
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

PLAN=dict(Study='LIFECYCLE_FUNDING_RECOVERY_1',LookbackMs=345600000,
          Targets=[dict(Symbol='AAPL.US',Side='BID',At=1793743200000)]+[
              dict(Symbol='EURUSD',Side=side,At=at) for at in (1794088800000,1794175200000) for side in ('BID','ASK')],
          EconomicPolicyReruns=0,Orders=0,CloudActivated=False)
OUT=Path('lifecycle-funding-protected')
SOURCE='4336a525ad897bee1a280e2baff07dcd399606e25f9536d4a202bc2676d73b15'

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('capture','verify'))
    p.add_argument('--work',type=Path);a=p.parse_args()
    rid=os.environ['GITHUB_RUN_ID'];digest=src.digest(src.canonical(PLAN))
    if a.stage=='capture':
        need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main'
             and os.environ['GITHUB_RUN_ATTEMPT']=='1','GOOG_CAPTURE_CONTEXT')
        t=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(t);need(src.original_account(account),'GOOG_ACCOUNT')
            journal=src.Journal(t,account);rows=prefix.collect(journal,account,PLAN)
        finally:t.close()
        need(len(journal.packets)==len(rows)==5,'GOOG_ONE_REQUEST')
        OUT.mkdir()
        sealed=eer.seal(OUT/'packets.sealed',dict(runId=rid,protocolSha256=digest,packets=journal.packets,rows=rows),
                        checked_public(Path('new-recipient-output'),rid),rid)
        (OUT/'receipt.json').write_bytes(src.canonical(dict(sealed=sealed,requests=5,Orders=0,CloudActivated=False)))
        print('GOOG_CAPTURE',rows[0]['Witness']['Status'],flush=True)
        return
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    receipt=json.loads((OUT/'receipt.json').read_bytes())
    data=eer.unpack(OUT,receipt['sealed'],key,rid)
    need(data['runId']==rid and data['protocolSha256']==digest and receipt['requests']==5,'GOOG_CAPTURE_BINDING')
    packets=data['packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'GOOG_READBACK_ACCOUNT')
    journal=src.ReadbackJournal(packets);rows=prefix.collect(journal,account,PLAN)
    need(rows==data['rows'] and journal.index==len(packets)==5,'GOOG_EXACT_READBACK')
    # Exact readback of the existing GOOG packet; never request it again.
    from .owner_goog_open_funding import PLAN as goog_plan
    prior=Path('prior-goog-funding')
    download_archive(15149312791,45885204524,'0afa55db9f924de0552080624d0f3c5bcfe55d2e9045d3c14479101883563625',prior)
    receipt=json.loads((prior/'receipt.json').read_bytes())
    data=eer.unpack(prior,receipt['sealed'],key,'45885204524')
    need(data['runId']=='45885204524' and data['protocolSha256']==src.digest(src.canonical(goog_plan))
         and receipt['requests']==1,'GOOG_REUSE_BINDING')
    packets=data['packets'];old_account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(old_account==account and src.original_account(old_account),'GOOG_REUSE_ACCOUNT')
    replay=src.ReadbackJournal(packets);old=prefix.collect(replay,old_account,goog_plan)
    need(old==data['rows'] and replay.index==len(packets)==1,'GOOG_REUSE_READBACK')
    rows+=old
    folder=a.work.parent/'lifecycle-funding-cipher'
    download_artifact(15143963668,45875663964,'a62909c52f02fa037ee96c61b1c9b09b7506882a2a6897c22aae0b9c0c3d9e42',folder)
    shard=json.loads((folder/'repack-receipt.json').read_bytes())
    need(shard['SourceSha256']==SOURCE and shard['OriginalSourceRun']==45874059214,'LIFECYCLE_SHARD_BINDING')
    download_shards(shard,folder)
    restore_checkpoint(folder,a.work,key,str(shard['SourceRunId']),SOURCE,source_only=True)
    original=Path('lifecycle-original')
    download_archive(15149404567,45885931266,'b3490ed9f10e77dd80969d69f3e6492237cbacf9fcc47c4a112ae49a2cca0b02',original)
    report=Path('lifecycle-funding-report');report.mkdir()
    witness=a.work/'lifecycle-witness.json';witness.write_bytes(src.canonical(rows))
    subprocess.run(['dotnet',REPLAY,'--owner-lifecycle-funding',str(a.work/'source.json'),
                    str(a.work/'verified-protection'),str(original),str(witness),
                    str(report/'settlement.json')],check=True)
    # Reusable, provenance-bound exact prefix registry, no economic labels.
    (report/'verified-prefix-registry.json').write_bytes(src.canonical(dict(Study=PLAN['Study'],
        SourceSha256=SOURCE,NewRunId=rid,ReusedGoogArtifact=15149312791,ReusedGoogRun=45885204524,
        NewRequests=5,ReusedRequests=1,Rows=rows,Orders=0,CloudActivated=False)))
    print('LIFECYCLE_SETTLEMENT',json.loads((report/'settlement.json').read_bytes())['ReconciledWindows'],flush=True)
if __name__=='__main__':main()
