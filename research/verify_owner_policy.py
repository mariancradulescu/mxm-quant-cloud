"""Focused policy wiring/evidence integrity CI, not economic validation."""
import hashlib,json
from pathlib import Path


def check():
    r=json.loads(Path('research/evidence_registry.json').read_text())
    assert r['authority']=='docs/OWNER_SPEC.md'
    assert r['independenceDefault']=='NOT_ESTABLISHED'
    assert all(not s['independent'] for s in r['sources'])
    for name,expected in r['frozenFileSha256'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected, 'FROZEN_EVIDENCE_CHANGED: '+name
    for name in ['README.md','docs/ARCHITECTURE.md','docs/ACCEPTANCE.md']:
        assert 'OWNER_SPEC.md' in Path(name).read_text(), 'MISSING_ACTIVE_AUTHORITY: '+name
    # Legacy sizing is allowed only in the preserved exact historical study and
    # regression checks; new integrated decisions must use the shared allocator.
    for name in ['src/Mxm.Core/OpportunityOrchestrator.cs','src/Mxm.Core/JointOpportunityResearch.cs']:
        s=Path(name).read_text()
        assert 'HistoricalPr16Risk' not in s and 'PreventiveExecutionRisk.Size' not in s
    assert 'AdaptivePortfolioRisk.Choose' in Path('src/Mxm.Core/OpportunityOrchestrator.cs').read_text()
    assert '--orchestrate-opportunities' in Path('research/orchestrated_replay.py').read_text()
    print('PASS active authority wiring and frozen-evidence hashes; not economic qualification')


if __name__=='__main__':
    check()
