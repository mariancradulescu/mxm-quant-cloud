"""Exact-source held valuation preflight. Reuse archived evidence, never query broker."""
import argparse,subprocess
from pathlib import Path
from . import owner_controlled_recency as preparation
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_monetary_reduce_common_book import REPLAY
from .verified_research_cache import sha
from .merge_eur_scenarios import read,exact_json
from .decode import need

REGISTRY=Path('research/held_valuation_preflight_1.json')
REPORT=Path('held-preflight-report')
DEMAND_SHA='576df0e4662e70ad8fb9d9cd8f2720ef71d67aa1936f6503680d92d496044155'
ORIGINALS={
    'earlier':(15176413393,45948572291,'12553a26e1b2ae9b587baa7443fac7c2e5cf71082965a73092fed50a2848348c'),
    'recent':(15175739827,45948572291,'1a68b4f0de7a2accb20cecfd7b776b3d8fa6d2e1c8be18939de85fec691a7839')}

def check():
    p=read(REGISTRY)
    need(p['Study']=='OWNER_HELD_VALUATION_PREFLIGHT_1' and p['RegistrySha256']==DEMAND_SHA
         and p['OriginalEngineRevision']=='50bd43f3025f23f031014f27cc53ea4186283b5b'
         and p['Orders']==0 and not p['CloudActivated'] and not p['EquityRecovered'],'HELD_PREFLIGHT_REGISTRATION')
    return p

def evaluate(work,scope):
    p=check()
    verified_download(*ORIGINALS[scope],Path('original-held-report'))
    original=read(Path('original-held-report/source-receipt.json'))
    planfile=Path('original-held-report/registered-plan.json')
    plan=read(planfile)
    need(sha(planfile)==original['ProtocolSha256'],'HELD_PREFLIGHT_ORIGINAL_PROTOCOL')
    # Restore existing evidence only. The newer recipe changes study metadata;
    # restore the immutable original protocol/evidence identities and compare
    # exact bytes. If the original cannot be reconstructed, stop locally.
    preparation.prepare(work,scope)
    source=read(work/'net-source.json')
    source.update(ProtocolSha256=plan['SourceProtocolSha256'],
        EvidenceManifestSha256=plan['EvidenceManifestSha256'],EngineRevision=p['OriginalEngineRevision'])
    path=work/'original-held-source.json'
    path.write_text(exact_json(source)+'\n')
    need(sha(path)==original['SourceSha256'],'HELD_PREFLIGHT_EXACT_ORIGINAL_RECONSTRUCTION')
    registry=Path('held-demand/held-valuation-demand.json')
    need(sha(registry)==DEMAND_SHA,'HELD_PREFLIGHT_DEMAND_REGISTRY')
    REPORT.mkdir()
    out=REPORT/'held-mark-registry.json'
    subprocess.run(['dotnet',REPLAY,'--owner-held-valuation-preflight',str(path),
        str(work/'verified-protection'),str(registry),scope,str(out)],check=True)
    r=read(out)
    need(r['Study']=='OWNER_HELD_VALUATION_PREFLIGHT_1' and r['OriginalSourceSha256']==original['SourceSha256']
         and r['RegistrySha256']==DEMAND_SHA and r['ResolvedConditionalMarks']+r['Unresolved']==r['DistinctSymbolClocks']
         and r['Orders']==0 and not r['CloudActivated'] and not r['EquityRecovered'],'HELD_PREFLIGHT_RESULT')
    print('HELD_PREFLIGHT_RESOLVED_CONDITIONAL_MARKS',scope,r['ResolvedConditionalMarks'],
        'UNRESOLVED',r['Unresolved'],flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','evaluate'])
    p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':check()
    else:
        need(a.scope is not None and a.work is not None,'HELD_PREFLIGHT_SCOPE')
        evaluate(a.work,a.scope)
if __name__=='__main__':main()
