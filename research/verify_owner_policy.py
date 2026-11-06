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
    assert 'Prospective initial capital EUR 300' in Path('README.md').read_text(), 'STALE_README_PROSPECTIVE_CAPITAL'
    assert 'continuous EUR 300 prospective initial capital' in Path('docs/ACCEPTANCE.md').read_text(), 'STALE_ACCEPTANCE_PROSPECTIVE_CAPITAL'

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
    assert 'IPF1_MULTI_HORIZON_CONDITIONAL_RESEARCH_NOT_CERTIFIED' in Path('src/Mxm.Core/ResearchScopeContract.cs').read_text()
    assert 'ResearchScopeContract.Require(' in Path('src/Mxm.Core/OpportunityOrchestrator.cs').read_text()
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
    assert 'RCP1_GLOBAL_RISK_DELAYED_FILL_CONDITIONAL_NOT_CERTIFIED' in Path('src/Mxm.Core/ResearchScopeContract.cs').read_text()
    assert 'ResearchScopeContract.Require(' in Path('src/Mxm.Core/OpportunityOrchestrator.cs').read_text()
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


    # New PVE1 authentically executed after its fixed prospective protocol had
    # already been committed; no reoptimization or promotion of exposed source.
    pve = next(s for s in r['prospectiveStudies'] if s['id']=='PVE1')
    pve_receipt = json.loads(Path('docs/PVE1_AUTHENTIC_RESULT.json').read_text())
    pve_protocol = Path('research/pve1_protocol.json').read_bytes()
    assert pve['status'].startswith('CLOSED_EXACT_') and pve['selectionSupportedGroups']==0
    assert pve['independent'] is False and pve['qualification'] is False
    assert pve['fundedNetEur'] is None and pve['followupCandidates']==[]
    assert hashlib.sha256(pve_protocol).hexdigest()==pve['protocolSha256']==pve_receipt['protocolSha256']
    assert pve_receipt['originalPublicJsonSha256']==pve['originalPublicJsonSha256']
    assert pve_receipt['executionWorkflowRunId']==pve['sourceResultRunId']==42022439033
    assert pve_receipt['authenticM5Bars']==pve['originalM5Bars']==836087
    assert pve_receipt['candidateHypotheses']==pve['preregisteredGroups']==48
    assert pve_receipt['phases']['selection']['passedCompleteAdmission']==0
    assert pve_receipt['economicBook']['initialModelCapitalEur']==300
    assert pve_receipt['economicBook']['endingModelCashEur']==300
    assert pve_receipt['economicBook']['closedConditionalNetEur']==0
    assert pve_receipt['economicBook']['completeModelRoundTrips']==0
    assert pve_receipt['economicBook']['nativeAllocations']==0
    assert pve_receipt['economicBook']['actualBrokerFundedNetEur'] is None
    assert pve_receipt['disclosure']['independentConfirmation'] is False
    assert pve_receipt['disclosure']['tradingQualification'] is False
    assert pve_receipt['disclosure']['ordersSubmitted']==0
    assert pve_receipt['disclosure']['brokerRequestsThisRun']==0
    assert pve_receipt['disclosure']['originallyClosedModelsReexecuted'] is False

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

    # HRC1 original authenticated pilot: fail-closed before selection,
    # exactly preserved artifact, no retrospective change to rejected methods.
    hrc = json.loads(Path('docs/HRC1_AUTHENTIC_PILOT.json').read_text())
    hrc_record = next(s for s in r['prospectiveStudies'] if s['id'] == 'HRC1')
    assert hashlib.sha256(Path('docs/HRC1_AUTHENTIC_PILOT.json').read_bytes()).hexdigest() == '87ecb79c14094b91a143d2f2a9235277abacb577374b632054ed4a055db3dc97'
    assert hashlib.sha256(Path('research/hrc1_protocol.json').read_bytes()).hexdigest() == hrc['prescoringProtocolSha256'] == hrc_record['protocolSha256']
    assert hrc['workflowRunId'] == hrc_record['sourceResultRunId'] == 42049772731
    assert hrc['sourceAuthenticated'] and hrc['rawSourceBars'] == 836087 and hrc['sourceAssets'] == 12 and hrc['originalCostContexts'] == 166
    assert hrc['development']['knownCompleteLabels'] == 11465 and hrc['development']['activeSignals'] == 4650
    assert hrc['development']['missingFutureOutcomes'] == 1062
    assert hrc['development']['completeAssetWeeks'] == 0 and hrc['development']['informativeActiveWeeks'] == 0
    assert not hrc['developmentPilotPassed'] and hrc['developmentWeeklyStdBps'] is None and hrc['detectableEffectBps'] is None
    assert hrc['selection'] is None and hrc['selectionNotViewedUnlessPilotPassed'] and hrc['globallyExposedAuditNotScored']
    assert hrc['fundedNetEur'] is None and not hrc['independentConfirmation'] and not hrc['hard21Proven']
    assert hrc_record['status'].startswith('CLOSED_EXACT_') and not hrc_record['qualification'] and hrc_record['followupCandidates'] == []
    assert hrc['brokerRequests'] == 0 and hrc['ordersSubmitted'] == 0 and not hrc['cloudActivated']


    # OWNER PR101–103 receipts: the existing single SHA-256 gate pins both
    # ORIGINAL durable JSON byte streams; these checks bind their protocol
    # identity, original Actions artifacts and strictly non-funded conclusions.
    # Neither historical research code nor original receipts are re-executed.
    import subprocess
    def original_blob_sha(path):
        return subprocess.check_output(['git', 'hash-object', path], text=True).strip()

    assert original_blob_sha('research/hrc1_protocol.json') == '183c69fd036cc08820ec900bfcad3ba08313f78b'
    assert original_blob_sha('research/pve2_protocol.json') == '47344c3361b894c07998efdea02462a12075514d'
    assert original_blob_sha('research/lfx1_protocol.json') == '496cd108ab482f70950344ede8ad4889eb99d338'
    coverage = json.loads(Path('docs/AUTHENTIC_TEMPORAL_COVERAGE_20261105.json').read_text())
    assert coverage['resultRunId'] == 42101938832 and coverage['resultArtifactId'] == 13450665489
    assert coverage['sourceRunIds'] == [41724643418, 41735441128]
    assert coverage['sourceBars'] == 836087 and coverage['sourceSymbols'] == 12 and coverage['sourceWeeks'] == 52
    assert coverage['actualAllWeeksWith8EligibleSymbols'] == 0
    assert coverage['week21hEligibleSymbols'] == 5 and coverage['week4hEligibleSymbols'] == 12
    assert coverage['allExposed'] and not coverage['independentConfirmation'] and not coverage['returnsScored']
    assert coverage['brokerRequests'] == 0 and coverage['ordersSubmitted'] == 0 and not coverage['cloudActivated']
    lfx = json.loads(Path('docs/LFX1_AUTHENTIC_RESULT.json').read_text())
    lfx_record = next(s for s in r['prospectiveStudies'] if s['id'] == 'LFX1')
    assert lfx['protocol'] == lfx_record['protocolFile'] == 'research/lfx1_protocol.json'
    assert lfx['originalResultRunId'] == lfx_record['originalResultRunId'] == 42103291209
    assert lfx['originalPublicArtifactId'] == lfx_record['originalPublicArtifactId'] == 13451340066
    assert lfx['sourceAuthenticated'] and lfx['originalM5Bars'] == 836087 and lfx['sourceCostContexts'] == 166
    assert lfx['exAntePowerScreen']['pilot']['noiseModelCaveat'].find('NOT') >= 0
    assert lfx['exAntePowerScreen']['pilot']['mdeProxyBps'] > 0
    assert lfx['conditionalEconomicScore']['phases']['selection']['meanBps']['adverse'] < 0
    assert not lfx['conditionalEconomicScore']['positiveAfterAdverseAndBothBenchmarks']
    assert lfx_record['status'].startswith('CLOSED_EXACT_') and not lfx_record['selectionSupport']
    assert lfx['allSourceWeeksGloballyExposed'] and not lfx['independentConfirmation']
    assert lfx['conditionalEconomicScore']['fundedNetEur'] is None
    assert not lfx['nativeFundedLedgerExecuted'] and not lfx['hard21Proven']
    assert lfx['closedStudyReruns'] == 0 and lfx['brokerRequests'] == 0
    assert lfx['ordersSubmitted'] == 0 and not lfx['cloudActivated']

    # GEP1 was prospectively frozen before a single protected authentic run.
    # Pin the original public Action artifact identity AND this precise durable
    # verdict; the closed protocol cannot be silently rescored or promoted.
    gep = next(s for s in r['prospectiveStudies'] if s['id'] == 'GEP1')
    protocol_raw = Path('research/gep1_protocol.json').read_bytes()
    protocol = json.loads(protocol_raw)
    receipt = json.loads(Path('docs/GEP1_AUTHENTIC_RESULT.json').read_text())
    assert gep['status'] == 'CLOSED_EXACT_TWO_GROUPS_NEGATIVE_ONE_MECHANISM_POWER_FAIL_NO_PROMOTION'
    assert gep['independent'] is False and gep['qualification'] is False
    assert gep['selectionViewed'] is True and gep['selectionViewedByGroup'] == dict(
        goldJPY=True,usdUS500=True,usdNAS100=False)
    assert gep['selectionSupportedGroups'] == 0 and gep['followupCandidates'] == []
    assert gep['brokerFundedNetEur'] is None and gep['hard21Proven'] is False
    assert gep['closedExactReruns'] == 0 and gep['ordersSubmitted'] == 0
    assert gep['cloudActivated'] is False and gep['brokerRequests'] == 0
    assert protocol['id'] == 'GEP1' and protocol['proof']['locked']
    assert protocol['ownerProspectiveInitialCashEur'] == 300
    assert len(protocol['families']) == 2 and sum(x['groups'] for x in protocol['families']) == 3
    assert protocol['scientific']['groups'] * protocol['scientific']['oneSidedComparisonsPerGroup'] == 6
    assert not protocol['proof']['cloudActivated'] and protocol['proof']['noOrders']
    assert protocol['source']['all52WeeksGloballyExposed'] and not protocol['calendar']['independentConfirmation']
    assert hashlib.sha256(protocol_raw).hexdigest() == gep['originalProtocolSha256'] == receipt['originalProtocolSha256']
    assert receipt['originalResultRunId'] == gep['sourceResultRunId'] == 42164589258
    assert receipt['originalPublicArtifactId'] == gep['originalPublicArtifactId'] == 13478557626
    assert receipt['originalPublicJsonSha256'] == gep['originalPublicJsonSha256'] == 'b7790ffdf5d89fb8742af303e99faf65de109d4a98614226cb72ee76e8bf5411'
    assert receipt['alreadyGloballyExposedHistoricalWeeks'] == 52 and receipt['originalSealedAuthenticM5Bars'] == 836087
    assert receipt['originalCostContexts'] == 166 and receipt['sourcePricedProposals52Weeks'] == 2398
    assert receipt['sourceWeeksWith21OrMoreSourcePricedProposals'] == 52
    assert receipt['sourcePricedProposalsNotBrokerFinancedRoundTrips']
    assert receipt['threeTargetStaticMarginFits300'] and receipt['threeTargetsCurrentMinimumStaticMarginSumEur'] == 190.18
    assert receipt['fundingAndProduct']['nativeCSharpFinancedRoundTrips'] == 0
    assert receipt['fundingAndProduct']['brokerConfirmedNetEur'] is None
    assert not receipt['fundingAndProduct']['hard21Certified']
    assert not receipt['fundingAndProduct']['continuousGlobalDrawdownWithin30PctCertified']
    assert not receipt['fundingAndProduct']['independentHoldoutAvailable']
    assert not receipt['fundingAndProduct']['CloudActivated'] and receipt['fundingAndProduct']['ordersLiveOrDemoSubmitted'] == 0
    groups = {g['id']:g for g in receipt['economicGroups']}
    assert set(groups) == {'GOLD_RISK_TO_JPY/USDJPY','USD_FUNDING_TO_US_INDEX/US500','USD_FUNDING_TO_US_INDEX/NAS100'}
    assert all(groups[x]['pilotPass'] and groups[x]['selectionScored'] and
               groups[x]['selectionConditionalAdverseBps'] < 0 and not groups[x]['admittedForNativeFunding']
               for x in ('GOLD_RISK_TO_JPY/USDJPY','USD_FUNDING_TO_US_INDEX/US500'))
    nas = groups['USD_FUNDING_TO_US_INDEX/NAS100']
    assert not nas['pilotPass'] and not nas['selectionScored'] and nas['selectionConditionalAdverseBps'] is None
    assert nas['developmentMechanismMdeBps'] > nas['developmentRelevantEffectBps']
    assert receipt['rerunProhibition']['closedStudiesRerun'] == 0 and not receipt['rerunProhibition']['selectionOutcomeForFailedPowerGroupViewed']

    # Original Action JSON SHA-256 must retain exact identities independently
    # of the distinct compact durable summaries (which are pinned above).
    original_pins = r['originalActionArtifactSha256']
    assert original_pins['actions/42101938832/artifacts/13450665489/authentic-temporal-coverage-public.json'] == 'ab5593710ade013c9a24e7431d311e0c71979e71ba48c2fa6b5d61f40dc3914d'
    assert original_pins['actions/42103291209/artifacts/13451340066/lfx1-authentic-public.json'] == '0a57d1e7b1cbce4461ea8af45ab16005655deaa96f5ae17ddd204b3734013816'
    assert original_pins['actions/42164589258/artifacts/13478557626/gep1-authentic-public.json'] == 'b7790ffdf5d89fb8742af303e99faf65de109d4a98614226cb72ee76e8bf5411'

    # One new exact SOURCE-only bond-rate curve gate; never reclassify old
    # 52 weeks or unscored new post-exposure bars as independent confirmation.
    bcf = next(s for s in r['prospectiveStudies'] if s['id'] == 'BCF1')
    proto = json.loads(Path('research/bcf1_protocol.json').read_text())
    assert bcf['status'] == 'REGISTERED_UNSCORED_SOURCE_ONLY'
    assert bcf['independent'] is False and bcf['qualification'] is False
    assert bcf['brokerFundedNetEur'] is None and bcf['cloudActivated'] is False
    assert proto['locked'] and proto['ownerCapitalProspectiveEur'] == 300
    assert proto['instruments'] == ['EUBobl-F','EUBund-F']
    assert proto['historicalSource']['allHistoricalCalendarWeeksGloballyExposed']
    assert proto['newChronologicalSource']['notToBeScoredOrUnsealedForPredictionWithoutPriorIndependentProtocol']
    assert proto['sourceFeasibility']['noScoredReturns']
    assert proto['operations']['expectedBrokerReadOnlyRequests'] == 165
    assert proto['operations']['noLiveOrDemoOrders'] and proto['operations']['noCloudActivation']
    assert 'def prospective_economic_futility(' in Path('research/f2_preflight.py').read_text()

    print('PASS OWNER v2.0 contract, frozen evidence, native funding and no-order boundary; no NET qualification')


if __name__ == '__main__':
    check()
