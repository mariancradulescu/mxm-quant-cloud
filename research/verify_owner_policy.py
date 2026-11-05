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
    assert 'OWNER decision 2026-11-04' in owner and 'OWNER prospective initial-capital amendment — 2026-11-05' in owner
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
    rcp = next(s for s in r['prospectiveStudies'] if s['id'] == 'RCP1')
    rcp_result = json.loads(Path('docs/RCP1_RESULT.json').read_text())
    assert rcp['status'].startswith('CLOSED_EXACT_') and rcp['closedExactNoRetuning']
    assert rcp['independent'] is False and rcp['qualification'] is False
    assert rcp['hard21Proven'] is False and rcp['weeksPassingHard21'] == 0
    assert rcp['actualBrokerFundedNetEur'] is None and rcp['followupCandidates'] == []
    assert rcp_result['originalPublicResult']['innerJsonSha256'] == rcp['originalPublicJsonSha256']
    assert rcp_result['preregisteredProtocolSha256'] == rcp['protocolSha256']
    assert rcp_result['modeledCommonCapital']['full']['modeledCompleteRoundTrips'] == 3
    assert rcp_result['modeledCommonCapital']['full']['weeksPassingSystemHARD21'] == 0
    assert rcp_result['modeledCommonCapital']['full']['maximumConcurrentPositions'] == 1
    assert rcp_result['economicVerdict']['genuineBrokerFundedNetEur'] is None
    assert rcp_result['economicVerdict']['qualifiedForOrders'] is False
    assert rcp_result['economicVerdict']['noIndependentHoldout'] is True
    assert 'RCP1_GLOBAL_RISK_DELAYED_FILL_CONDITIONAL_NOT_CERTIFIED' in Path('src/Mxm.Core/OpportunityOrchestrator.cs').read_text()
    new_replay = Path('research/rcp1_portfolio.py').read_text()
    assert 'entryAt=t+MS' in new_replay and 'openCurves[pid]=records' in new_replay
    assert rcp_result['modeledCommonCapital']['full']['originalCapitalReconciled']
    assert 'LocalStorage.' not in Path('src/Mxm.Cloud/MxmCloud.cs').read_text()
    assert msp.get('ordersSubmitted', 0) == 0, 'UNAUTHORIZED_MSP1_TRADING_CLAIM'

    # These values belong to the single native system, not to each candidate.
    risk = Path('src/Mxm.Core/OwnerRiskLimits.cs').read_text()
    ledger = Path('src/Mxm.Core/NativeFundedLedger.cs').read_text()
    assert 'InitialCapitalEur=300m' in risk and 'MaximumSystemDrawdown=.30m' in risk
    assert 'MinimumSystemRoundTripsPerEligibleWeek=21' in risk
    assert 'new(Version,OwnerRiskAuthority.InitialCapitalEur,OwnerRiskAuthority.InitialCapitalEur,-1,OwnerRiskAuthority.InitialCapitalEur' in ledger
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
    # Semantic receipt assertions: distinguish account inventory, quote observations
    # and unsupported predictive/financial qualification. Original receipts remain
    # immutable; byte-for-byte SHA256 validation is performed above for each.
    account_inventory = json.loads(Path('docs/FULL_CTRADER_ACCOUNT_INVENTORY_AUTHENTIC_20261105.json').read_text())
    csp = json.loads(Path('docs/CSP1_AUTHENTIC_SPREAD_RESULT_20261105.json').read_text())
    mbf = json.loads(Path('docs/MBF1_AUTHENTIC_RESULT.json').read_text())
    for name, obj in [('INVENTORY', account_inventory), ('CSP1', csp), ('MBF1', mbf)]:
        assert obj['ordersSubmitted'] == 0 and obj['cloudActivated'] is False, name + '_ORDER_OR_CLOUD_CLAIM'
    assert account_inventory['authenticated'] is True and account_inventory['fullRawReadbackMatched'] is True
    assert account_inventory['completeNonArchivedAccountSymbolRoster'] == 5339
    assert account_inventory['visibleAccountSymbols'] == 1755
    assert account_inventory['contractProbeCount'] == 96 and account_inventory['contractCurrentMinMarginObserved'] == 89
    assert account_inventory['currentStaticMinimumMarginBelow200EurCount'] == 74
    assert account_inventory['notQueriedIsNotUnavailable'] is True and account_inventory['costOrHistoricalMarginProven'] is False
    assert account_inventory['systemFundedNetEur'] is None and account_inventory['independentConfirmation'] is False
    assert csp['authenticatedRawReadback'] is True and csp['originalSourceRunId'] == 41940740480
    assert csp['linkedInventoryRunId'] == account_inventory['sourceRunId']
    assert csp['instrumentClockOpportunities'] == csp['validFreshPairedBidAsk'] + csp['unknownOrInvalidQuotes']
    assert csp['unknownOrInvalidQuotes'] == sum(csp['observationStatuses'].values())
    assert csp['historicalAllInCostCertified'] is False and csp['fundedNetEur'] is None
    assert csp['independentConfirmation'] is False and csp['hard21Established'] is False
    assert mbf['authenticatedCryptoRawReadback'] is True and mbf['sourceRunId'] == 41971150620
    assert mbf['candidateGroups'] == len(mbf['families']) == 8
    assert mbf['selectionOnlyConditionalFollowupCandidates'] == []
    asian = [x for x in mbf['families'] if x['family'] == 'ASIA_INDEX_RISK_HANDOFF']
    assert len(asian) == 2 and all(x['phases']['selection']['completeModelledOpportunities'] == 0 for x in asian)
    assert mbf['omissions']['ASIA_INDEX_RISK_HANDOFF/FEATURE_MISSING'] == 260
    assert mbf['allInHistoricalCostsCertified'] is False and mbf['fundedNetEur'] is None
    assert mbf['nativeAllocatorInvoked'] is False and mbf['independentConfirmation'] is False
    assert mbf['systemHard21Proven'] is False and mbf['continuousDrawdown30Proven'] is False
    assert mbf['closedStudiesRescored'] is False

    oce = json.loads(Path('docs/OCE1_AUTHENTIC_EXPOSED_RESULT.json').read_text())
    oce_study = next(s for s in r['prospectiveStudies'] if s['id'] == 'OCE1')
    assert oce_study['status'].startswith('CLOSED_EXACT_') and oce_study['followupCandidates'] == []
    assert oce_study['originalResultSha256'] == r['frozenFileSha256']['docs/OCE1_AUTHENTIC_EXPOSED_RESULT.json']
    assert oce['originalSourceCiphertextHashesVerified'] and oce['bothOriginalReadOnlySourcesBoundToSameAccount']
    assert oce['sourceRuns'] == {'fx': 41724643418, 'oil': 41948500095}
    assert oce['originalFxM5BarsReconstructedFromRaw'] == 74161
    assert oce['originalCrudeH1BarsReconstructedFromRaw'] == 5877
    assert oce['preflightComplete']['scheduledClocks'] == 624
    assert oce['preflightComplete']['completeDecisionAndHoldingData'] == 614
    assert oce['quoteCostDevelopmentSampleCount'] == 18
    assert oce['phase']['selection']['completeUnfundedSignals'] == 46
    assert oce['phase']['selection']['conditionalBeforeFinancingMeanBps']['adverse'] < 0
    assert oce['selectionSupportedConditionalFollowupOnly'] is False
    assert oce['closedStudiesRescored'] is False and oce['newBrokerRequests'] == 0
    assert oce['fundedNetEur'] is None and oce['independentConfirmation'] is False
    assert oce['hard21Proven'] is False and oce['continuousDrawdown30Proven'] is False
    assert oce['nativeAllocatorInvoked'] is False and oce['ordersSubmitted'] == 0 and oce['cloudActivated'] is False

    # IES1's authentic exposed original is retained in Actions; this compact
    # immutable receipt is SHA-pinned by the SAME gate, not re-scored as a
    # prospective strategy or a historical brokerage cost certificate.
    ies1 = json.loads(Path('docs/IES1_AUTHENTIC_EXPOSED_RECEIPT.json').read_text())
    study = next(s for s in r['prospectiveStudies'] if s['id'] == 'IES1')
    assert study['summaryFileSha256'] == r['frozenFileSha256']['docs/IES1_AUTHENTIC_EXPOSED_RECEIPT.json']
    assert study['originalPublicJsonSha256'] == ies1['originalPublicResultSha256']
    assert ies1['resultRunId'] == 41991415344 and ies1['originalSourceRunId'] == 41724643418
    assert ies1['originalAuthenticatedSourceAudited'] and ies1['originalClosedModelsReexecuted'] is False
    assert ies1['sourceM5CompleteBars'] == 441240 and len(ies1['instruments']) == 6
    assert sum(x['m5Bars'] for x in ies1['instruments']) == 441240
    assert sum(x['selectionCompletePairs'] for x in ies1['instruments']) == ies1['selectionTotalCompleteCausalPairs'] == 8747
    assert sum(x['validDevelopmentQuoteAndFxSamples'] for x in ies1['instruments']) == ies1['pairedWithSynchronousEurRouteAndContract'] == 78
    assert ies1['pairedWithSynchronousEurRouteAndContract'] + ies1['unknownCostClockCount'] == ies1['possibleQuoteInstrumentClocks'] == 108
    assert all(x['selectionMeanDirectionalGrossBps'] < 0 and x['selectionBrierSkillVsNeutral'] < 0 for x in ies1['instruments'])
    assert all(x['positiveDirectionalGrossEvidence'] is False and x['fundedNetEur'] is None for x in ies1['instruments'])
    assert all(0 < x['currentMinimumMarginEur'] < 200 for x in ies1['instruments'])
    assert study['independent'] is False and study['qualification'] is False
    assert study['fundedNetEur'] is None and ies1['economicAdmission']['knownConditionalIncrementalEURNet'] is None
    assert ies1['economicAdmission']['qualifiedCandidates'] == [] and ies1['economicAdmission']['actualFinancedRoundTrips'] == 0
    assert not ies1['economicAdmission']['nativeFundedLedgerReplayPerformed']
    assert ies1['brokerNewReadOnlyRequests'] == 0 and ies1['ordersSubmitted'] == 0 and ies1['cloudActivated'] is False
    assert not ies1['economicAdmission']['noIndependentConfirmation'] is False
    assert 'ResearchSpecialistAdmission.Estimate' in Path('src/Mxm.Core/NativeFundedDecisionCycle.cs').read_text()

    print('PASS OWNER v2.0 contract, frozen evidence, native funding and no-order boundary; no NET qualification')


if __name__ == '__main__':
    check()
