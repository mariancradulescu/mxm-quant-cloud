"""Ciphertext-only preservation of both completed controlled-recency archives."""
import argparse,json
from pathlib import Path
from . import owner_generalized_cipher_shards as general
from . import owner_causal_source_shards as cipher

RUN=45957472368
SOURCES={
    'earlier':(15180190673,1449755046,'91c56cb6ca3f09f4f7940c32e9817f775e6e9ac064e2ba2f3696e33d7d394d8b',
        '80aa042379ae3d6cf7efab647aca8a2971ff596c7b4a5b383c1c0456f1f252c5',
        '979037f674bc863991be2a9b4b364dad208142d2b08fee32bd28de520f08e042'),
    'recent':(15179639035,406901899,'d9ae5c40f2ec4e16976a052600a488e0a09a3029cba4b0178cc535f4778f38cc',
        '56be11c4e497ddd62b4d1ee94e60710fb67cc4ad4c8639bb450608f8ce6e2b02',
        '034a5b3e245d38daf979e5e1767c37d051a77622bf9a014060b388997f032632')}

def configure(scope):
    general.ARTIFACT,general.BYTES,general.SHA,_,_=SOURCES[scope]
    general.RUN=RUN

def rewrite_publication(path,scope):
    cipher.need(scope in SOURCES,'MEMORY_BOOK_SCOPE')
    action=json.loads(path.read_bytes());bound=0
    for step in action['runs']['steps']:
        if 'with' in step:
            step['with']['name']=step['with']['name'].replace('lifecycle-general-data-',f'controlled-recency-{scope}-books-data-')
        if step.get('run')=='python -m research.owner_generalized_cipher_shards receipt':
            step['run']=f'python -m research.owner_controlled_recency_book_shards receipt --scope {scope}';bound+=1
    cipher.need(bound==1,'MEMORY_BOOK_RECEIPT_BINDING')
    path.write_text(json.dumps(action,indent=2)+'\n')

def validate(p,scope):
    _,_,_,source,protocol=SOURCES[scope]
    cipher.need(p['SourceRunId']==str(RUN) and p['SourceSha256']==source and p['ProtocolSha256']==protocol,
        'MEMORY_BOOK_SOURCE_BINDING')

def annotate(scope):
    path=general.ROOT/'metadata/repack-receipt.json';p=json.loads(path.read_bytes())
    validate(p,scope)
    p.update(RepackScope='MONETARY_CONTROLLED_RECENCY_1/'+scope,
        EconomicPoliciesExecuted=0,SourceBrokerRequests=0,Orders=0,CloudActivated=False)
    cipher.write(path,p)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','receipt','verify'))
    p.add_argument('--scope',choices=tuple(SOURCES),required=True);a=p.parse_args()
    configure(a.scope)
    if a.stage=='prepare':
        general.prepare()
        validate(json.loads((general.ROOT/'metadata/shard-plan.json').read_bytes()),a.scope)
        rewrite_publication(general.ACTION/'action.yml',a.scope)
    elif a.stage=='receipt':general.receipt();annotate(a.scope)
    else:general.verify();annotate(a.scope)

if __name__=='__main__':main()
