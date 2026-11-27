"""Verify and publish small public receipt facts without decrypting or rerunning.
Exact run/ZIP identities from completed custody publications.
"""
import argparse,json,os
from pathlib import Path
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .decode import need

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','read'));a=p.parse_args()
    if a.stage=='check':return
    verified_download(15157255658,45903702321,
        'a0f21325a66901eb5082d909d51699b3bf2ddae918154ec7a2f4baad70e37d5f',Path('public-residual'))
    d=json.loads(Path('public-residual/diagnostic.json').read_bytes())
    need(d['Study']=='COST_RESIDUAL_CONTEXT_DIAGNOSTIC_1' and d['OriginalPoliciesReplayed']==0 and
        d['CommonBookEvaluations']==d['Orders']==0 and not d['CloudActivated'] and len(d['Results'])==3,
        'PUBLIC_RESIDUAL_BINDING')
    print('VERIFIED_CONTEXT_RESIDUAL_DIAGNOSTIC',json.dumps(d,separators=(',',':')),flush=True)
    verified_download(15156872074,45902423354,
        '0a24aa5f98949f49dbeadf6f2c1eb76c101eda979190074320db5d79c58d34f3',Path('public-earlier-cache'))
    m=json.loads(Path('public-earlier-cache/checkpoint-receipt.json').read_bytes())
    need(m['RunId']=='45902423354' and m['Study']=='MONETARY_EARLIER_LIFECYCLE_ESTIMATION_1' and
        m['Complete'] and m['Orders']==0 and not m['CloudActivated'] and len(m['Files'])==m['ExpectedFiles'],
        'PUBLIC_EARLIER_CACHE_BINDING')
    print('VERIFIED_EARLIER_NORMALIZED_RECEIPT',json.dumps(dict(RunId=m['RunId'],Study=m['Study'],
        SourceSha256=m['SourceSha256'],ProtocolSha256=m['ProtocolSha256'],ManifestCipherSha256=m['ManifestCipherSha256'],
        Files=m['ExpectedFiles'],CipherParts=sum(len(f['Parts']) for f in m['Files']),
        OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False),separators=(',',':')),flush=True)
if __name__=='__main__':main()
