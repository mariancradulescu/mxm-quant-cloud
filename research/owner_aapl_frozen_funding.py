"""Recover the single missing AAPL.US rollover BID in frozen MT25_H1_24.
Reuse official authentication, latest-prefix decoding and existing sealed source.
No other quote requests, no old economic replay, no mutation of original bytes.
"""
import argparse,json,os,subprocess
from pathlib import Path
from . import source_history_universe as src
from . import owner_eer1_source as eer
from . import owner_funding_prefix_settlement as prefix
from . import owner_monetary_reduce_common_book as cache
from .owner_eur_recent_archive import download_archive
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

PLAN=dict(Study='AAPL_FROZEN_FUNDING_RECOVERY_1',LookbackMs=345600000,
          Targets=[dict(Symbol='AAPL.US',Side='BID',At=1793656800000)],
          EconomicPolicyReruns=0,Orders=0,CloudActivated=False)
OUT=Path('aapl-funding-protected')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('capture','verify'))
    parser.add_argument('--work',type=Path)
    args=parser.parse_args()
    rid=os.environ['GITHUB_RUN_ID'];digest=src.digest(src.canonical(PLAN))
    if args.stage=='capture':
        need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main'
             and os.environ['GITHUB_RUN_ATTEMPT']=='1','AAPL_CAPTURE_CONTEXT')
        t=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(t);need(src.original_account(account),'AAPL_ACCOUNT')
            journal=src.Journal(t,account);rows=prefix.collect(journal,account,PLAN)
        finally:t.close()
        need(len(journal.packets)==len(rows)==1,'AAPL_ONE_NEW_REQUEST')
        OUT.mkdir()
        sealed=eer.seal(OUT/'packets.sealed',dict(runId=rid,protocolSha256=digest,packets=journal.packets,rows=rows),
                        checked_public(Path('new-recipient-output'),rid),rid)
        (OUT/'receipt.json').write_bytes(src.canonical(dict(sealed=sealed,requests=1,Orders=0,CloudActivated=False)))
        print('AAPL_CAPTURE',rows[0]['Witness']['Status'],flush=True)
        return
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    receipt=json.loads((OUT/'receipt.json').read_bytes())
    data=eer.unpack(OUT,receipt['sealed'],key,rid)
    need(data['runId']==rid and data['protocolSha256']==digest and receipt['requests']==1,'AAPL_CAPTURE_BINDING')
    packets=data['packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'AAPL_READBACK_ACCOUNT')
    journal=src.ReadbackJournal(packets);rows=prefix.collect(journal,account,PLAN)
    need(rows==data['rows'] and journal.index==len(packets)==1,'AAPL_EXACT_READBACK')
    print('AAPL_READBACK',rows[0]['Witness']['Status'],flush=True)
    cache.restore(args.work)
    original=Path('aapl-original')
    download_archive(15126531887,45835675932,'61449060de450d61f01652bae012a66ef6d187fbc078b97046562ff619db06b5',original)
    report=Path('aapl-funding-report');report.mkdir()
    private_witness=args.work/'aapl-witness.json'
    private_witness.write_bytes(src.canonical(rows[0]))
    subprocess.run(['dotnet',cache.REPLAY,'--owner-aapl-frozen-funding',str(args.work/'source.json'),
                    str(args.work/'verified-protection'),str(original/'economic-market-time.json'),
                    str(private_witness),str(report/'settlement.json')],check=True)
    (report/'source-reuse.json').write_bytes((Path('reduce-report')/'source-reuse.json').read_bytes())
    print('AAPL_SETTLEMENT',json.loads((report/'settlement.json').read_bytes())['Status'],flush=True)

if __name__=='__main__':main()
