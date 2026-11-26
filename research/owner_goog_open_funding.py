"""One targeted official historical price request for frozen GOOG.US-24 financing."""
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

PLAN=dict(Study='GOOG_OPEN_FUNDING_RECOVERY_1',LookbackMs=345600000,
          Targets=[dict(Symbol='GOOG.US-24',Side='BID',At=1795644000000)],
          EconomicPolicyReruns=0,Orders=0,CloudActivated=False)
OUT=Path('goog-funding-protected')
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
        need(len(journal.packets)==len(rows)==1,'GOOG_ONE_REQUEST')
        OUT.mkdir()
        sealed=eer.seal(OUT/'packets.sealed',dict(runId=rid,protocolSha256=digest,packets=journal.packets,rows=rows),
                        checked_public(Path('new-recipient-output'),rid),rid)
        (OUT/'receipt.json').write_bytes(src.canonical(dict(sealed=sealed,requests=1,Orders=0,CloudActivated=False)))
        print('GOOG_CAPTURE',rows[0]['Witness']['Status'],flush=True)
        return
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    receipt=json.loads((OUT/'receipt.json').read_bytes())
    data=eer.unpack(OUT,receipt['sealed'],key,rid)
    need(data['runId']==rid and data['protocolSha256']==digest and receipt['requests']==1,'GOOG_CAPTURE_BINDING')
    packets=data['packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'GOOG_READBACK_ACCOUNT')
    journal=src.ReadbackJournal(packets);rows=prefix.collect(journal,account,PLAN)
    need(rows==data['rows'] and journal.index==len(packets)==1,'GOOG_EXACT_READBACK')
    folder=a.work.parent/'goog-cipher'
    download_artifact(15143963668,45875663964,'a62909c52f02fa037ee96c61b1c9b09b7506882a2a6897c22aae0b9c0c3d9e42',folder)
    shard=json.loads((folder/'repack-receipt.json').read_bytes())
    need(shard['SourceSha256']==SOURCE and shard['OriginalSourceRun']==45874059214,'GOOG_SHARD_BINDING')
    download_shards(shard,folder)
    restore_checkpoint(folder,a.work,key,str(shard['SourceRunId']),SOURCE,source_only=True)
    original=Path('goog-original')
    download_archive(15143664128,45874059214,'ae2dbd07cd5e201826cc3eb056660a8586cb0d9a782079405b6b4b390d1eb526',original)
    report=Path('goog-funding-report');report.mkdir()
    witness=a.work/'goog-witness.json';witness.write_bytes(src.canonical(rows[0]))
    subprocess.run(['dotnet',REPLAY,'--owner-goog-open-funding',str(a.work/'source.json'),
                    str(a.work/'verified-protection'),str(original/'S0.json'),str(witness),
                    str(report/'settlement.json')],check=True)
    print('GOOG_SETTLEMENT',json.loads((report/'settlement.json').read_bytes())['Status'],flush=True)
if __name__=='__main__':main()
