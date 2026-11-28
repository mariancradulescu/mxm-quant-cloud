"""Trace all recovery entries to actual conserved protocols, code and public results.
This is an evidence review, not a requalification of any historic result.
"""
import hashlib,json,re,subprocess
from pathlib import Path
CATALOG=Path('research/owner_recovery_catalog_20261128.json')
REGISTRY=Path('research/evidence_registry.json')
PRIORITIES={
 'RCP1':dict(Priority=1,Evidence='docs/RCP1_RESULT.md',Finding='FULL +12.239475 EUR on3 modeled trips; removing compression leaves the result unchanged, removing relative dispersion leaves+0.988275;0/26 HARD21 weeks.',Action='Recover relative dispersion and tail unwinding as well as compression in native shared-book competition; do not attribute profit to compression.'),
 'VIA1':dict(Priority=2,Evidence='docs/VIA1_AUTHENTIC_ECONOMIC_CLOSURE_20261113.md',Finding='EURUSD adverse+10.2286 EUR, but-2.1506 versus matched fixed reversion; US500 adverse-10.2359. Paths were unfunded and overlapping.',Action='Recover impulse-failure entry with common-book monetary selection and management; compare against broad original families, no automatic EURUSD promotion.'),
 'TWC1':dict(Priority=3,Evidence='research/twc1_protocol.json',Finding='Calendar hypothesis registered unscored; weekday and4h UTC slot, causal matured labels and zero prior.',Action='Implement shared native calendar state learned from reconciled older and newer H1 information; actual economic exit uses funded lifecycle rather than the forecast horizon.'),
 'HRC1':dict(Priority=4,Evidence='research/hrc1_protocol.json',Finding='Original21-return local lag-one correlation and exact adjacent-hour coverage; pilot lacked informative coverage.',Action='Preserve correlation-sign mechanism, compare4/8/21 on M15 in the funded engine, abstain on gaps; no range-midpoint substitute.'),
 'BDP1':dict(Priority=5,Evidence='docs/BDP1_EXECUTION_REVIEW.md',Finding='Original calendar overflow was corrected without economic improvement; maximum pre-cost bounds0.234732/0.208831 bps below minimum base cost1.039699 bps; financed NET unknown.',Action='Reuse authentic raw context and current terms; require actual funded lifecycle value, not relaxing the original price screen or claiming the calendar repair creates edge.'),
 'AIP1':dict(Priority=6,Evidence='docs/AIP1_AUTHENTIC_RESULT.json',Finding='No primary uncertainty admissions; zero financed round trips does not constitute a complete monetary comparison of all alternative mechanisms.',Action='Reuse original source as causal history; retain activity family in competition. Original auction-inventory economic redevelopment remains separately open.'),
 'SQP1':dict(Priority=7,Evidence='docs/SQP1_AUTHENTIC_RESULT.json',Finding='Original primary configuration nonpositive; native reception confirms seven model round trips per source journal, not independent edge.',Action='Matured same-symbol run-state forecast with day-balanced estimates, shared funded lifecycle and strict predecision label availability.'),
 'PAV1':dict(Priority=8,Evidence='docs/research/PAV1_MARKET_TIME_FX_1_RESULTS.md',Finding='Earlier conditional positives coexist with exposure, risk and financing limitations.',Action='Continue persistent protection, reserve and management controls; keep all original outcomes and do not limit the recovered system to PAV1.')}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def metric_leaves(value,path=''):
    result=[]
    if isinstance(value,dict):
        for key,item in value.items():result+=metric_leaves(item,path+'/'+str(key))
    elif isinstance(value,list):
        if len(value)<10:
            for i,item in enumerate(value):result+=metric_leaves(item,path+'/'+str(i))
    elif re.search(r'net|gross|trade|episode|admission|drawdown|unpriced|missing|week|forecast|support',path,re.I) and (value is None or type(value) in (int,float)):
        result.append(dict(Field=path,OriginalValue=value))
    return result

def main():
    catalog=json.loads(CATALOG.read_bytes());registry=json.loads(REGISTRY.read_bytes())
    original={x['id']:x for x in registry['prospectiveStudies']}
    tracked=subprocess.check_output(['git','ls-files','docs','research','src'],text=True).splitlines()
    rows=[]
    for item in catalog['Rows']:
        name=item['Study'];pattern=re.compile(r'(^|[/_])'+re.escape(name)+r'(?=[_/.-]|$)',re.I)
        candidates={p for p in tracked if pattern.search(p) and Path(p).suffix in ('.json','.md','.cs','.py')}
        for key in ('OriginalProtocol','OriginalEvidence'):
            if item.get(key) and Path(item[key]).is_file():candidates.add(item[key])
        entry=original.get(name,{})
        if entry.get('protocol') and Path(entry['protocol']).is_file():candidates.add(entry['protocol'])
        evidence=[];metrics=metric_leaves(entry)
        for p in sorted(candidates):
            path=Path(p);raw=path.read_text();kind='RESULT' if 'RESULT' in path.name.upper() or 'CLOSURE' in path.name.upper() else 'IMPLEMENTATION' if path.suffix in ('.cs','.py') else 'PROTOCOL_OR_REVIEW'
            evidence.append(dict(Path=p,Sha256=sha(path),Kind=kind,Bytes=path.stat().st_size))
            if path.suffix=='.json' and kind=='RESULT':
                try:metrics.extend(dict(x,File=p) for x in metric_leaves(json.loads(raw)))
                except json.JSONDecodeError:pass
        rows.append(dict(Study=name,OriginalStatus=item.get('OriginalStatus',entry.get('status')),
            OriginalRegistryEntry=entry or None,LocalEvidence=evidence,OriginalNumericFacts=metrics,
            TargetedReview=PRIORITIES.get(name),
            ReviewCoverage=dict(LocalFilesInspected=len(evidence),OriginalRegistryInspected=bool(entry),
                ArchivedBinaryResultIndependentlyRestoredByThisReview=False,
                Unresolved='Archived result, methodology or funded redevelopment remains open where absent from conserved local evidence'),
            QualificationChanged=False,RecoveryAuthorized=True))
    report=dict(Study='OWNER_ALL_STUDY_EVIDENCE_REVIEW_1',CatalogSha256=sha(CATALOG),RegistrySha256=sha(REGISTRY),
        Entries=len(rows),OriginalRegistryEntries=len(original),Rows=rows,
        NewMonetaryStudy='research/full_estate_monetary_competition_1.json',Orders=0,CloudActivated=False,
        OriginalResultsModified=False,IndependentConfirmationCertified=False)
    out=Path('docs/OWNER_ALL_STUDY_EVIDENCE_REVIEW_20261128.json');out.write_text(json.dumps(report,indent=2)+'\n')
    print('RECOVERY_EVIDENCE_REVIEW',len(rows),'entries',sum(x['ReviewCoverage']['LocalFilesInspected'] for x in rows),'file references',sum(bool(x['TargetedReview']) for x in rows),'targeted economic reviews')
if __name__=='__main__':main()
