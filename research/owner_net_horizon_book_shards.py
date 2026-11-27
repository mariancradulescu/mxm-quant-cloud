"""Ciphertext-only preservation of both completed net-horizon archives."""
import argparse,json
from pathlib import Path
from . import owner_generalized_cipher_shards as general
from . import owner_causal_source_shards as cipher

RUN=45948572291
SOURCES={
    'earlier':(15175968965,2647582101,'931dc4ea074f79b124dcaf0b627b05589a1667b7cf3a178da726309ddd45333b',
        'e9c33073ad1a1af4f4d9e388a40230607479d46ddff4091a1f9089b6b17aeb0c',
        '56dbfb5bc07408a5bda6de39d59fac90061b5600e1cae795e16414b4bc224ac7'),
    'recent':(15176756226,903804325,'2acf2a4a45f9da7aee4ab14399db2af42ae5a50adc82034b9c3d6f732c72587f',
        '6917f5050aa18794488c717251f763aec2fce53f649a0b32da2de9b15db882cd',
        '3fac43b409ae72288f6469b1fbbd64fcf7623ca7c78205db8bdbc94fac50a715')}

def configure(scope):
    general.ARTIFACT,general.BYTES,general.SHA,_,_=SOURCES[scope]
    general.RUN=RUN

def rewrite_publication(path,scope):
    cipher.need(scope in SOURCES,'NET_BOOK_SCOPE')
    action=json.loads(path.read_bytes());bound=0
    for step in action['runs']['steps']:
        if 'with' in step:
            step['with']['name']=step['with']['name'].replace('lifecycle-general-data-',f'net-horizon-{scope}-books-data-')
        if step.get('run')=='python -m research.owner_generalized_cipher_shards receipt':
            step['run']=f'python -m research.owner_net_horizon_book_shards receipt --scope {scope}';bound+=1
    cipher.need(bound==1,'NET_BOOK_RECEIPT_BINDING')
    path.write_text(json.dumps(action,indent=2)+'\n')

def validate(p,scope):
    _,_,_,source,protocol=SOURCES[scope]
    cipher.need(p['SourceRunId']==str(RUN) and p['SourceSha256']==source and p['ProtocolSha256']==protocol,
        'NET_BOOK_SOURCE_BINDING')

def annotate(scope):
    path=general.ROOT/'metadata/repack-receipt.json';p=json.loads(path.read_bytes())
    validate(p,scope)
    p.update(RepackScope='MONETARY_NET_HORIZON_CROSS_CONTEXT_1/'+scope,
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
