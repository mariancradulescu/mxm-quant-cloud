"""Focused active OWNER/ledger/evidence boundary checks, not economic validation."""
import hashlib
import json
import re
from pathlib import Path


def check():
    r = json.loads(Path('research/evidence_registry.json').read_text())
    assert r['authority'] == 'docs/OWNER_SPEC.md'
    assert r['independenceDefault'] == 'NOT_ESTABLISHED'
    assert all(s.get('independent') is False for s in r['sources'])
    for name, expected in r['frozenFileSha256'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, 'FROZEN_EVIDENCE_CHANGED: ' + name

    owner = Path('docs/OWNER_SPEC.md').read_text()
    assert owner.startswith('# Active OWNER specification v2.0')
    assert 'OWNER decision 2026-11-04' in owner
    for name in ('README.md', 'docs/ARCHITECTURE.md', 'docs/ACCEPTANCE.md'):
        s = Path(name).read_text()
        assert 'OWNER_SPEC.md' in s, 'MISSING_ACTIVE_AUTHORITY: ' + name
        assert 'OWNER v3.0' not in s, 'CONCURRENT_NORMATIVE_AUTHORITY: ' + name

    # Closed experiments cannot silently become an independent/funded certificate.
    # A future genuinely new prospectively registered study is not pre-rejected.
    for s in r['prospectiveStudies']:
        if s.get('status', '').startswith('CLOSED_'):
            assert s.get('independent') is False, 'CLOSED_STUDY_FALSE_INDEPENDENCE: ' + s['id']
            assert s.get('qualification') is not True, 'CLOSED_STUDY_SILENT_PROMOTION: ' + s['id']
        if s.get('costClass') == 'CONDITIONAL_COST_MODEL':
            assert s.get('fundedNetEur') is None, 'PROXY_PROMOTED_TO_FUNDED_NET: ' + s['id']
            assert s.get('qualification') is not True, 'PROXY_PROMOTED_TO_CERTIFICATE: ' + s['id']
    msp = next(s for s in r['prospectiveStudies'] if s['id'] == 'MSP1')
    assert msp['status'].startswith('CLOSED_EXACT_') and msp['followupCandidates'] == []
    imt = next(s for s in r['prospectiveStudies'] if s['id'] == 'IMT1')
    imt_receipt = json.loads(Path('docs/IMT1_CONDITIONAL_RESULT.json').read_text())
    assert imt['status'] == 'CLOSED_EXACT_NO_SELECTION_SUPPORT'
    assert imt['selectionSupport'] == [] and imt['fundedNetEur'] is None
    assert imt['independent'] is False and imt['qualification'] is False
    assert imt_receipt['selectionFollowupCandidateIds'] == []
    assert imt_receipt['fundedNetEur'] is None and imt_receipt['independentConfirmation'] is False
    assert imt_receipt['originalResult']['protocolSha256'] == imt['protocolSha256']
    ipf = next(s for s in r['prospectiveStudies'] if s['id'] == 'IPF1')
    ipf_receipt = json.loads(Path('docs/IPF1_RESULT.json').read_text())
    assert ipf['status'].startswith('CLOSED_EXACT_')
    assert ipf['qualification'] is False and ipf['independent'] is False
    assert ipf['followupCandidates'] == [] and ipf['brokerFundedNetCertified'] is False
    assert ipf_receipt['modeledCommonCapital']['scenarios']['FULL']['closedNetEur'] < 0
    assert ipf_receipt['sourceAndRiskLimitations']['fundingNetEurCertified'] is False
    assert ipf_receipt['sourceAndRiskLimitations']['tradingQualification'] is False
    assert ipf_receipt['originalArtifact']['originalJsonSha256'] == ipf['originalPublicJsonSha256']
    assert ipf_receipt['protocolSha256'] == ipf['protocolSha256']
    assert ipf_receipt['followupCandidates'] == []
    assert not ipf_receipt['modeledCommonCapital']['nativeFundedLedgerReplayParityCertified']
    assert 'IPF1_MULTI_HORIZON_CONDITIONAL_RESEARCH_NOT_CERTIFIED' in Path('src/Mxm.Core/OpportunityOrchestrator.cs').read_text()
    assert 'LocalStorage.' not in Path('src/Mxm.Cloud/MxmCloud.cs').read_text()
    assert msp.get('ordersSubmitted', 0) == 0, 'UNAUTHORIZED_MSP1_TRADING_CLAIM'

    # These values belong to the single native system, not to each candidate.
    risk = Path('src/Mxm.Core/OwnerRiskLimits.cs').read_text()
    ledger = Path('src/Mxm.Core/NativeFundedLedger.cs').read_text()
    assert 'InitialCapitalEur=200m' in risk and 'MaximumSystemDrawdown=.30m' in risk
    assert 'MinimumSystemRoundTripsPerEligibleWeek=21' in risk
    assert 'state=new(Version,200,200,-1,200' in ledger
    for name in ('src/Mxm.Core/OpportunityOrchestrator.cs',
                 'src/Mxm.Core/JointOpportunityResearch.cs'):
        s = Path(name).read_text()
        assert 'HistoricalPr16Risk' not in s and 'PreventiveExecutionRisk.Size' not in s
    assert 'AdaptivePortfolioRisk.Choose' in Path('src/Mxm.Core/OpportunityOrchestrator.cs').read_text()
    assert '--orchestrate-opportunities' in Path('research/orchestrated_replay.py').read_text()

    # Delivered Cloud adapter remains strictly observation-only pending OWNER consent.
    cloud = Path('src/Mxm.Cloud/MxmCloud.cs').read_text()
    forbidden = ('ExecuteMarketOrder', 'ExecuteMarketRangeOrder', 'PlaceLimitOrder',
                 'PlaceStopOrder', 'PlaceStopLimitOrder', 'ModifyPosition',
                 'ClosePosition', 'CancelPendingOrder', 'ReversePosition')
    assert all(not re.search(r'\b' + call + r'\s*\(', cloud)
               for call in forbidden), 'UNAUTHORIZED_CLOUD_TRADING_CALL'
    assert 'LocalStorage.' not in cloud, 'CLOUD_LOCAL_STORAGE_NOT_DURABLE_RESTART_SOURCE'
    print('PASS OWNER v2.0 contract, frozen evidence, native funding and no-order boundary; no NET qualification')


if __name__ == '__main__':
    check()
