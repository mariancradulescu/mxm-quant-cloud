"""EPA2 workflow entrypoint: shared source collector, encrypted audit and replay."""
import hashlib,json,os,sys
from pathlib import Path
from .portfolio_economic_source import collect,audit
from .custody import unseal_new
from .decode import need

PROTOCOL=Path('research/portfolio_holding_protocol.json')


def readback(p):
    run=os.environ['GITHUB_RUN_ID'];key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    raw=Path('sealed-output/source.envelope.json').read_bytes();pub=json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(pub['schema']=='mxm-epa2-source-v1' and pub['runId']==run and hashlib.sha256(raw).hexdigest()==pub['sha256'],'EPA2_CUSTODY_BINDING')
    b=json.loads(unseal_new(raw,key,run));need(audit(b,p)==b['auditReceipt'],'EPA2_INDEPENDENT_RAW_RECONCILIATION')
    baseline=Path('baseline-source/source.envelope.json').read_bytes();need(hashlib.sha256(baseline).hexdigest()==p['sourceSha256'],'EPA2_ORIGINAL_H4_BINDING')
    old=Path('epa1-source/source.envelope.json').read_bytes();need(hashlib.sha256(old).hexdigest()==p['oldEpa1SourceSha256'],'EPA2_ORIGINAL_EPA1_SOURCE_BINDING')
    need(hashlib.sha256(Path('docs/EPA1_AUTHENTIC_PORTFOLIO_RESULT.json').read_bytes()).hexdigest()==p['oldEpa1PublicSha256'],'EPA2_EPA1_PUBLIC_RESULT_UNCHANGED')
    original=json.loads(unseal_new(baseline,key,str(p['sourceRunId'])));epa1=json.loads(unseal_new(old,key,str(p['oldEpa1Run'])))
    print('EPA2_RAW_CUSTODY_AND_FROZEN_EPA1_SOURCE_VERIFIED',flush=True)
    from .portfolio_holding_replay import evaluate
    result=evaluate(b,original,epa1,p)
    result.update(sourceRunId=int(run),sourceCiphertextSha256=pub['sha256'],sourceAudit=b['auditReceipt'],
                  rawCustodyReadbackMatched=True,oldEpa1PublicSha256=p['oldEpa1PublicSha256'])
    Path('portfolio-holding.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    print('AUTHENTIC_PORTFOLIO_HOLDING_RESULT '+json.dumps(result,sort_keys=True,default=str),flush=True)


if __name__=='__main__':
    try:
        p=json.loads(PROTOCOL.read_text())
        need(not Path('docs/EPA2_AUTHENTIC_HOLDING_RESULT.json').exists(),'EPA2_CLOSED_USE_FROZEN_RECEIPT_AND_BROKER_FREE_DIAGNOSIS')
        readback(p) if '--readback' in sys.argv else collect(p)
    except Exception:
        print('EPA2_FAILED_CLOSED_DETAILS_WITHHELD',flush=True);raise SystemExit(1)
