"""Preserve exact completed boundary book ciphertext in reusable bounded shards."""
import argparse,json
from pathlib import Path
from . import owner_generalized_cipher_shards as general
from . import owner_causal_source_shards as cipher

RUN=45940604347
ARTIFACT=15173869173
BYTES=2009231816
SHA='16e31f28983b3e26aacfbf4186fd215b0533be8cd93f0f6a9d72953b3d4643a4'
SOURCE='d983f522be2561f1b6dcda6a8e7cefb4d2820971aedd474d8c5ebd39cb8b9def'
PROTOCOL='c8774fc0d7ecf0376dc529150f6342309be2a33445935c625caca1baf1a28e68'

def configure():
    general.RUN,general.ARTIFACT,general.BYTES,general.SHA=RUN,ARTIFACT,BYTES,SHA

def rewrite_publication(path):
    action=json.loads(path.read_bytes());bound=0
    for step in action['runs']['steps']:
        if 'with' in step:
            step['with']['name']=step['with']['name'].replace('lifecycle-general-data-','boundary-books-data-')
        if step.get('run')=='python -m research.owner_generalized_cipher_shards receipt':
            step['run']='python -m research.owner_boundary_book_shards_1 receipt';bound+=1
    cipher.need(bound==1,'BOUNDARY_BOOK_RECEIPT_PROCESS_BINDING')
    path.write_text(json.dumps(action,indent=2)+'\n')

def annotate():
    path=general.ROOT/'metadata/repack-receipt.json';p=json.loads(path.read_bytes())
    cipher.need(p['SourceRunId']==str(RUN) and p['SourceSha256']==SOURCE and p['ProtocolSha256']==PROTOCOL,
        'BOUNDARY_BOOK_EXACT_COMPLETED_SOURCE')
    p.update(RepackScope='MONETARY_BOUNDARY_LIFECYCLE_1_COMPLETED_BOOKS',
        EconomicPoliciesExecuted=0,SourceBrokerRequests=0,Orders=0,CloudActivated=False)
    cipher.write(path,p)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','receipt','verify'));a=p.parse_args()
    configure()
    if a.stage=='prepare':
        general.prepare()
        plan=json.loads((general.ROOT/'metadata/shard-plan.json').read_bytes())
        cipher.need(plan['SourceSha256']==SOURCE and plan['ProtocolSha256']==PROTOCOL,
            'BOUNDARY_BOOK_REGISTERED_INPUT')
        rewrite_publication(general.ACTION/'action.yml')
    elif a.stage=='receipt':general.receipt();annotate()
    else:general.verify();annotate()

if __name__=='__main__':main()
