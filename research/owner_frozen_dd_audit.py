"""Audit a sealed original book without replaying its trading policy."""
import os,subprocess,argparse
from pathlib import Path
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_held_equity_recovery import restore_final_books
from .owner_monetary_reduce_common_book import REPLAY
from .merge_eur_scenarios import read
from .decode import need
RUN=46033578807
REPORT=(15220467722,RUN,'fc40a05b83c6a7652a2268f90f779649612040dc129d77736e2a216c151a773a')
SEALED=(15221256968,RUN,'b6e1eb4a68ec3c09e9e7291b287b149fab25c0a4bface4c17a4ca876c5e755e1')

def main():
    a=argparse.ArgumentParser();a.add_argument('--work',type=Path,required=True);args=a.parse_args()
    work=args.work;work.mkdir(mode=0o700)
    verified_download(*REPORT,work/'original')
    report=work/'original/S1-result.json';r=read(report)
    need(r['Study']=='MONETARY_MANAGEMENT_FACTORIAL_1' and r['Stress']==__import__('decimal').Decimal('.5') and r['Orders']==0 and not r['CloudActivated'],'FROZEN_DD_REPORT')
    out=Path('frozen-dd-audit-report');out.mkdir()
    paths=list(restore_final_books(SEALED,work/'sealed',work/'books',os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),
        r['SourceSha256'],wanted={('S1','CENTERED_CONTROL')},protocol_sha=r['ProtocolSha256']))
    need(len(paths)==1,'FROZEN_DD_BOOK_SCOPE')
    subprocess.run(['dotnet',REPLAY,'--owner-frozen-dd-audit',str(paths[0]),str(report),'CENTERED_CONTROL',str(out/'audit.json')],check=True)
    result=read(out/'audit.json');need(result['CurveAndEventChainVerified'] and result['OriginalPoliciesReplayed']==result['Orders']==0 and
        not result['CloudActivated'] and not result['ContinuousDrawdownCertified'],'FROZEN_DD_AUDIT_RESULT')
if __name__=='__main__':main()
