"""Independent arithmetic/event audit of completed original persistent-risk books."""
import argparse,json,os,subprocess,time
from pathlib import Path
from .owner_estate_monetary_competition import artifact_specs
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_held_equity_recovery import restore_final_books
from .owner_monetary_reduce_common_book import REPLAY
from .merge_eur_scenarios import read,exact_json
from .decode import need
RUN=46138292231

def audit(work):
    work.mkdir(parents=True,mode=0o700);out=Path('persistent-risk-fact-report');out.mkdir()
    repo=os.environ['GITHUB_REPOSITORY'];started=time.monotonic()
    while True:
        run=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{RUN}']))
        if run['status']=='completed':break
        need(time.monotonic()-started<18000,'PERSISTENT_RISK_AUDIT_SOURCE_TIMEOUT')
        print('WAITING_FOR_ORIGINAL_PERSISTENT_RISK_COMPLETION',RUN,flush=True);time.sleep(30)
    need(run['conclusion']=='success','PERSISTENT_RISK_ORIGINAL_NOT_COMPLETE')
    items={a['Name']:a for a in artifact_specs(RUN)};receipts=[];rows=[]
    for scope in ('earlier','recent'):
        prefix='persistent-risk-recovery-'+scope
        result=items[prefix+'-economic'];books=items[prefix+'-sealed-books']
        original=work/(scope+'-original');verified_download(result['Id'],RUN,result['Sha256'],original)
        receipt=read(original/'source-receipt.json');receipts.append(dict(Scope=scope,Original=result,Books=books,Receipt=receipt))
        key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
        count=0
        models=[v['Id'] for v in read(original/'registered-plan.json')['Variants']]+['CASH_MARKET_TIME']
        wanted={(f'S{i}',name) for i in range(3) for name in models}
        for path in restore_final_books((books['Id'],RUN,books['Sha256']),work/(scope+'-cipher'),work/(scope+'-books'),key,
                receipt['SourceSha256'],wanted=wanted,protocol_sha=receipt['ProtocolSha256']):
            stress=path.parts[-4];name=path.stem;target=out/(scope+'-'+stress+'-'+name+'.json')
            subprocess.run(['dotnet',REPLAY,'--owner-persistent-risk-audit',str(path),name,str(target)],check=True)
            r=read(target);need(r['EventChainVerified'] and r['Orders']==r['OriginalPoliciesReplayed']==0,'PERSISTENT_RISK_FACT_CHAIN')
            facts=r['Facts'];positions=facts['Positions'];book=next(b for b in read(original/(stress+'-result.json'))['CommonBooks'] if b['Id']==name)
            rows.append(dict(Scope=scope,Stress=stress,Id=name,EventChainHash=r['EventChainHash'],Original=book['Result'],
                FirstPreventiveAt=facts['FirstPreventiveAt'],FirstHardAt=facts['FirstHardAt'],PreventiveToHardMs=facts['PreventiveToHardMs'],
                MaximumSampledDrawdown=facts['MaximumSampledDrawdown'],UnknownWithExposure=facts['UnknownWithExposure'],
                CloseDiagnoses={k:sum(p['Diagnosis']==k for p in positions) for k in sorted({p['Diagnosis'] for p in positions})},
                AtPreventive=[p for p in positions if p['ExposedAtFirstPreventive']],AuditFile=target.name))
            count+=1;path.unlink()
        need(count==27,'PERSISTENT_RISK_27_FINAL_BOOKS_PER_SCOPE')
        (out/(scope+'-summary.json')).write_bytes((original/'summary.json').read_bytes())
        benchmark=original/'full-engine-benchmark.json'
        if benchmark.exists():(out/'full-engine-benchmark.json').write_bytes(benchmark.read_bytes())
    (out/'summary.json').write_text(exact_json(dict(Study='OWNER_PERSISTENT_RISK_FACT_AUDIT_1',OriginalRun=RUN,Books=len(rows),
        SourceReceipts=receipts,Results=rows,OriginalPoliciesReplayed=0,OriginalResultsModified=False,
        ContinuousDrawdownCertified=False,IndependentConfirmationCertified=False,Orders=0,CloudActivated=False))+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);audit(p.parse_args().work)
