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
    assert bcf['status'] == 'SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS'
    assert bcf['sourceResultRunId'] == 42172375939 and bcf['sourceRunAttempts'] == 2
    assert bcf['originalApplicationAuthSuccessBothAttempts']
    assert bcf['accountTokenViewScopeValidated'] is False
    assert bcf['sourceReadbackAvailable'] is False and bcf['sourceCiphertextSha256'] is None
    assert bcf['predictiveOutcomesInspected'] is False and bcf['sourceOnly'] is True
    assert bcf['newHistoricalOrPostExposureSourceCaptured'] is False
    assert bcf['readOnlySourceRequestsSucceeded'] == 0
    assert bcf['historicalPriceReturnsInspected'] is False
    assert bcf['proposedEconomicScoreAvailable'] is False
    assert bcf['protocolRetuned'] is False
    assert not Path('docs/BCF1_AUTHENTIC_SOURCE_GATE.json').exists()
    assert 'APPLICATION_AUTH_VERIFIED' in Path('docs/BCF1_AUTH_AND_EUR300_CAPACITY_20261106.md').read_text()
    assert '1b15d08fa14bf67239acf31109b1f0f11093df7fe5c1b04fcbf1bff893040c5a' in Path('docs/BCF1_AUTH_AND_EUR300_CAPACITY_20261106.md').read_text()
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

    # Auth-only original public receipt: no invented expiry, no source capture.
    auth_rec = json.loads(Path('docs/AUTH_SCOPE_DIAGNOSTIC_AUTHENTIC_RESULT_20261106.json').read_text())
    auth_reg = next(x for x in r['authenticationDiagnostics'] if x['id'] == 'AUTH_SCOPE_20261106')
    assert auth_reg['diagnosticRunId'] == 42178238508
    assert auth_rec['source']['originalPublicJsonSha256'] == auth_reg['originalPublicJsonSha256']
    assert auth_rec['source']['originalPublicArtifactId'] == auth_reg['originalArtifactId'] == 13483574579
    assert auth_rec['result']['category'] == 'AUTH_CAUSE_UNDETERMINED'
    assert auth_rec['result']['stage'] == 'access_token_scope'
    assert auth_rec['result']['applicationAuthenticationVerified'] is True
    assert auth_rec['result']['authenticationRequestsSent'] == 2
    assert auth_rec['result']['explicitSCOPE_VIEWVerified'] is False
    assert auth_rec['result']['originalAccountAuthenticationVerified'] is False
    assert auth_rec['result']['brokerAccountDataOrHistoryRequests'] == 0
    assert auth_rec['interpretation']['authCauseDemonstrated'] is False
    assert auth_rec['interpretation']['safeRefreshAndAtomicPairPersistenceInExistingWorkflow'] is False
    assert auth_rec['scopeBoundary']['BCF1SourceCaptureRecovered'] is False
    assert auth_rec['scopeBoundary']['newChronologicallyUnexposedDataCollected'] is False
    assert auth_rec['result']['tradingOrders'] == 0 and auth_rec['result']['cloudActivated'] is False

    # OWNER Nov7: real original-environment fingerprint-name audit; a
    # mismatch does not certify a valid OAuth refresh or change any identity.
    fp_secret = json.loads(Path('docs/ORIGINAL_FINGERPRINT_SECRET_AUTHENTIC_RESULT_20261107.json').read_text())
    fsreg = r['originalFingerprintSecretAudit'][0]
    assert fp_secret['originalProtectedEvidence']['runId'] == fsreg['sourceRunId'] == 42347155803
    assert fp_secret['originalProtectedEvidence']['sourceArtifactId'] == fsreg['sourceArtifactId'] == 13563777822
    assert fp_secret['originalProtectedEvidence']['publicFileSha256'] == fsreg['publicReceiptSha256']
    assert fp_secret['result']['comparison'] == 'DOES_NOT_MATCH_ORIGINAL_FINGERPRINT_VALUE_TYPE_UNKNOWN'
    assert fp_secret['result']['unknownValueMayBeRefreshTokenButNotProven'] is True
    assert fp_secret['result']['refreshTokenValidityConfirmed'] is False
    assert fp_secret['result']['matchedHistoricalOriginalFingerprint'] is False
    assert fp_secret['result']['historicalOriginalLiveAccountBindingChanged'] is False
    assert fp_secret['result']['originalSecretChanged'] is False
    assert fp_secret['result']['refreshRotatedOrConsumed'] is False
    assert fp_secret['result']['brokerRequests'] == 0 and fp_secret['result']['ordersSubmitted'] == 0
    assert fp_secret['reconciliation']['BCF1Status'] == 'SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS'
    assert fp_secret['reconciliation']['viewScopeNowProven'] is False
    assert fp_secret['nextSecureStep']['authenticatedEnvironmentSecretsDualTokenWritebackAvailableThroughConnector'] is False

    # OWNER Nov7: corrected secret names are present, but SCOPE_VIEW not proved.
    # Conserve the post-reconfiguration receipt separately from the Nov6 error
    # and from the misnamed-fingerprint secret comparison.
    recovery = json.loads(Path('docs/OWNER_RECONFIGURED_OAUTH_AUTHENTIC_RESULT_20261107.json').read_text())
    ar = next(x for x in r['authenticationDiagnostics'] if x['id'] == 'OWNER_RECONFIGURED_OAUTH_20261107')
    pr = next(x for x in r['oauthSecretPresenceChecks'] if x['id'] == 'FOUR_CORRECTED_20261107')
    assert recovery['source']['workflowRunId'] == ar['diagnosticRunId'] == pr['originalRunId'] == 42374757850
    assert recovery['source']['publicArtifactId'] == ar['originalArtifactId'] == pr['originalArtifactId'] == 13575056596
    assert recovery['source']['authFileSha256'] == ar['originalPublicJsonSha256']
    assert recovery['source']['presenceFileSha256'] == pr['originalPublicJsonSha256']
    assert recovery['secretAvailability']['allFourAvailable'] is True
    assert set(k for k in recovery['secretAvailability'] if k.startswith('R3_CTRADER_')) == {
        'R3_CTRADER_CLIENT_ID', 'R3_CTRADER_CLIENT_SECRET',
        'R3_CTRADER_ACCESS_TOKEN', 'R3_CTRADER_REFRESH_TOKEN'}
    assert all(recovery['secretAvailability'][k] == 'AVAILABLE_IN_PROTECTED_JOB'
               for k in recovery['secretAvailability'] if k.startswith('R3_CTRADER_'))
    assert recovery['authentication']['category'] == 'AUTH_SCOPE_INCOMPATIBLE_OR_MISSING'
    assert recovery['authentication']['stage'] == 'access_token_scope'
    assert recovery['authentication']['applicationAuthenticationVerified'] is True
    assert recovery['authentication']['tokenAccountListResponseReceived'] is True
    assert recovery['authentication']['explicitSCOPE_VIEWVerified'] is False
    assert recovery['authentication']['originalAccountAuthenticationVerified'] is False
    assert recovery['authentication']['authenticationRequestsSent'] == 2
    assert recovery['authentication']['brokerMarketHistoryContractOrQuoteRequests'] == 0
    assert recovery['boundary']['BCF1Status'] == 'SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS'
    assert recovery['boundary']['BCF1RecoveryTriggered'] is False
    assert recovery['boundary']['refreshTokenConsumed'] is False
    assert recovery['boundary']['tokenRotationPerformed'] is False
    assert recovery['boundary']['liveOrDemoOrders'] == 0
    assert recovery['boundary']['cTraderCloudActivated'] is False
    assert ar['BCF1Recovered'] is False and ar['closedModelRescored'] is False
    assert pr['safePairRotationCompleted'] is False

    # Nov 7 OWNER BCF1 recovery is a new event, NOT a rewrite of Nov 6.
    bcf_recovery = json.loads(Path('docs/BCF1_AUTHENTIC_RECOVERY_RESULT_20261107.json').read_text())
    brec = next(x for x in r['bcf1RecoveryReadbacks'] if x['id'] == 'BCF1_OWNER_SCOPE_RECOVERY_20261107')
    auth_new = next(x for x in r['authenticationDiagnostics'] if x['id'] == 'OWNER_SCOPE_ADAPTER_BCF1_20261107')
    assert bcf['status'] == 'SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS'
    assert bcf['sourceResultRunId'] == 42172375939
    assert bcf_recovery['source']['runId'] == brec['sourceRunId'] == auth_new['sourceRunId'] == 42377775316
    assert bcf_recovery['source']['publicReadbackArtifactId'] == brec['originalPublicArtifactId'] == 13576272572
    assert bcf_recovery['source']['publicReadbackFileSha256'] == brec['originalPublicJsonSha256'] == 'd7d4ea67fffdee99832067fec568b20176d67b3b46df74011554903d7198c85b'
    assert bcf_recovery['source']['protocolSha256'] == '18e415a766fd7e2ba0583f914c29b04804b8867065ed429b52568254884064dc'
    assert bcf_recovery['authentication']['observedScope'] == auth_new['scopeAttested'] == 'SCOPE_TRADE'
    assert bcf_recovery['authentication']['originalLiveAccountCryptographicallyBound']
    assert bcf_recovery['authentication']['originalAccountAuthenticated']
    assert bcf_recovery['sourceReadback']['sourceRequests'] == 165
    assert bcf_recovery['sourceReadback']['completeEncryptedCustodyReadback']
    assert bcf_recovery['sourceReadback']['historicalSourceWeeksWithJointH1'] == 52
    assert bcf_recovery['sourceReadback']['newUnscoredChronologicalH1Times'] == {'EUBobl-F':83,'EUBund-F':83}
    bidask = bcf_recovery['sourceReadback']['bidAskCostPreflight']
    assert bidask['requiredFreshPairedClocksEach'] == 8
    assert bidask['EUBobl-F']['validFreshPaired'] == 0
    assert bidask['EUBund-F']['validFreshPaired'] == 1
    assert bcf_recovery['sourceReadback']['sumMinimumMarginEur'] == 47.36
    assert bcf_recovery['verdict']['onlyBlockingReason'] == 'AUTHENTIC_PAIRED_QUOTES_BELOW_MINIMUM'
    assert bcf_recovery['verdict']['observableSourcePreflightPass'] is False
    assert bcf_recovery['verdict']['economicCostOrNetScoringPermitted'] is False
    assert bcf_recovery['verdict']['brokerFundedNetEur'] is None
    assert bcf_recovery['verdict']['nativeCSharpRoundTripsProven'] == 0
    assert bcf_recovery['authentication']['refreshTokenConsumed'] is False
    assert bcf_recovery['authentication']['ordersSent'] == 0
    assert bcf_recovery['authentication']['cloudActivated'] is False
    assert auth_new['ownerTradingAuthorized'] is False and brec['ordersSubmitted'] == 0

    # Nov 7 FLS1: an actually executed NEW predeclared economic hypothesis,
    # not a rescore/ablation or a broker-certified EUR NET.
    fls = next(x for x in r['prospectiveStudies'] if x['id'] == 'FLS1')
    fls_receipt = json.loads(Path('docs/FLS1_AUTHENTIC_RESULT_20261107.json').read_text())
    fls_protocol_raw = Path('research/fls1_protocol.json').read_bytes()
    fls_proto = json.loads(fls_protocol_raw)
    assert fls_proto['locked'] and fls_proto['status'] == 'PREDECLARED_UNSCORED'
    assert fls_proto['prospectiveInitialCapitalEur'] == 300
    assert fls_proto['originalSource']['fullyGloballyExposedWeeks'] == 52
    assert fls_proto['restrictions']['noLiveDemoOrders'] is True
    assert fls['status'] == fls_receipt['verdict']['status'] == 'CLOSED_EXACT_DEVELOPMENT_F2_FUTILE_BEFORE_SELECTION'
    assert fls['originalResultRunId'] == fls_receipt['provenance']['originalMainRunId'] == 42380699704
    assert fls['originalPublicArtifactId'] == fls_receipt['provenance']['originalPublicArtifactId'] == 13576868959
    assert fls['originalPublicSha256'] == fls_receipt['provenance']['originalPublicSha256'] == 'e92757d3d068a73c7d9eda44687119f2d4cee218a9f4c6ac958efe1fc635aa77'
    assert fls_receipt['provenance']['originalLockedProtocolSha256'] == hashlib.sha256(fls_protocol_raw).hexdigest()
    assert fls_receipt['provenance']['sourceM5BarsAuthenticated'] == 836087
    assert fls_receipt['provenance']['sourceCurrentTermQuoteCostContextsAuthenticated'] == 166
    assert fls_receipt['targetCostAndFinance']['sourceQuoteCostSamples'] == 18
    assert fls_receipt['targetCostAndFinance']['currentMinimumMarginEur'] == 39.96
    assert fls_receipt['sourceCoverage']['developmentCompleteSourceSignals'] == 90
    assert fls_receipt['sourceCoverage']['selectionSourceCompleteSignalsButOutcomesUninspected'] == 54
    assert fls_receipt['developmentSignalMeanBps']['gross'] == -0.4881905457386368
    assert fls_receipt['developmentSignalMeanBps']['adverseNet'] == -2.9159106051839943
    assert fls_receipt['existingF2DevelopmentFutility']['upperAdverseNetBps'] == -0.8181108515695379
    assert fls_receipt['existingF2DevelopmentFutility']['status'] == 'FUTILE_STOP_BEFORE_SELECTION'
    assert fls_receipt['existingF2DevelopmentFutility']['selectionScoringAllowed'] is False
    assert fls_receipt['verdict']['selectionOutcomesInspected'] is False
    assert fls_receipt['verdict']['exposedAuditWeeksScored'] == 0
    assert fls_receipt['verdict']['brokerFundedNetEur'] is None
    assert fls_receipt['verdict']['nativeCSharpFundedRoundTrips'] == 0
    assert fls_receipt['verdict']['ordersSubmitted'] == 0
    assert fls_receipt['verdict']['cloudActivated'] is False
    assert fls_receipt['verdict']['refreshTokenConsumed'] is False
    assert fls['exactClosedNoRetuning'] and fls['closedStudiesRescored'] is False

    # Nov 7 CPF1: genuine original Pepperstone source 3-family H1 Cloud
    # screen, six Bonferroni contrasts, one nonqualified selection; the
    # previously exposed 13 audit weeks are NEVER scored or reclassified.
    cpf = next(x for x in r['prospectiveStudies'] if x['id'] == 'CPF1')
    cpfr = json.loads(Path('docs/CPF1_AUTHENTIC_RESULT_20261107.json').read_text())
    cp_raw = Path('research/cpf1_protocol.json').read_bytes()
    cpp = json.loads(cp_raw)
    cp_evidence = r['cpf1AuthenticResearch']
    assert cpp['locked'] and cpp['status'] == 'PREDECLARED_UNSCORED'
    assert cpp['finance']['prospectiveInitialCapitalEur'] == 300
    assert len(cpp['source']['sourceSymbols']) == 12
    assert len(cpp['families']) == 3 and cpp['statistics']['wholeProgramOneSidedComparisons'] == 6
    assert cpp['clock']['exposedAuditWeeksUnscored'] == 13
    assert cpp['security']['prohibitedLiveDemoOrders'] and cpp['security']['noTokenRefresh']
    assert cpfr['provenance']['originalLockedProtocolSha256'] == hashlib.sha256(cp_raw).hexdigest()
    assert cpfr['provenance']['genuineGitHubActionsRunId'] == cpf['originalResultRunId'] == cp_evidence['originalRunId'] == 42383853064
    assert cpfr['provenance']['publicArtifactId'] == cpf['originalPublicArtifactId'] == cp_evidence['originalPublicArtifactId'] == 13579215807
    assert cpfr['provenance']['originalPublicJsonSha256'] == cpf['originalPublicSha256'] == cp_evidence['originalPublicFileSha256'] == 'a72ee698649967a9a998ba04c474ac8c3cafed62608c769d5aed9a0f4c2b1723'
    assert cpfr['provenance']['originalAuthenticatedM5Bars'] == 836087
    assert cpfr['provenance']['originalAuthenticatedQuoteCostContexts'] == 166
    assert cpfr['finance']['symbolCountCostAndMinimumMarginEligible'] == 12
    assert cpfr['finance']['symbolsWithCompleteStrategySignalsInDevelopment'] == 5
    assert cpfr['chronology']['independentChronologicalConfirmation'] is False
    assert cpfr['chronology']['comparisonsFamilywiseBonferroni'] == 6
    results_cpf = cpfr['results']
    trend_cpf=results_cpf['DONCHIAN_TREND_VOLUME']
    boll_cpf=results_cpf['BOLLINGER_OVEREXTENSION_REVERSION']
    sweep_cpf=results_cpf['H1_FALSE_BREAK_LIQUIDITY_SWEEP']
    assert trend_cpf['developmentSignals'] == 166 and trend_cpf['selectionResults'] is None
    assert trend_cpf['developmentF2'] == 'NOT_INFORMATIVE_NO_ECONOMIC_PROMOTION'
    assert boll_cpf['developmentSignals'] == 361 and boll_cpf['selectionSignals'] == 171
    assert boll_cpf['developmentF2'] == 'UPPER_BOUND_ALLOWS_PLAUSIBILITY_NOT_EVIDENCE'
    assert boll_cpf['selectionAdjustedOneSidedBonferroniHAC3LowerAdverseNetBps'] == -5.9269704229415705
    assert boll_cpf['selectionAdjustedOneSidedBonferroniHAC3LowerIncrementalBenchmarkBps'] == -6.9026160215803225
    assert boll_cpf['selectionSupportsFunding'] is False
    assert sweep_cpf['developmentSignals'] == 138 and sweep_cpf['selectionResults'] is None
    assert sweep_cpf['developmentF2'] == 'FUTILE_STOP_BEFORE_SELECTION'
    assert cpfr['verdict']['status'] == cpf['status'] == 'ALL_THREE_EXACT_FAMILIES_CLOSED_WITHOUT_CSHARP_PROMOTION'
    assert cpfr['verdict']['selectionPromotableGroups'] == cp_evidence['selectionQualifiedFamilies'] == []
    assert cpfr['verdict']['auditOutcomesScored'] is False
    assert cpfr['verdict']['nativeCsharpFundedCompleteTrips'] == 0
    assert cpfr['verdict']['independentlyConfirmedNetAdvantage'] is False
    assert cpfr['verdict']['liveOrDemoOrdersSubmitted'] == 0
    assert cpfr['verdict']['nativeCloudCbotActivated'] is False
    assert cpfr['verdict']['refreshTokenConsumed'] is False
    assert cpf['closedStudiesRerun'] == 0 and cpf['protocolRetuned'] is False

    # MFA1 is one authentic six-hypothesis PROGRAM, not five retuned trials.
    # Assert original sealed source, native parity and economic NON-qualification.
    mfa = next(x for x in r['prospectiveStudies'] if x['id']=='MFA1')
    mr = json.loads(Path('docs/MFA1_AUTHENTIC_RESULT_20261107.json').read_text())
    ma = r['mfa1AuthenticResearch']
    mp_raw = Path('research/mfa1_protocol.json').read_bytes()
    mp = json.loads(mp_raw)
    assert mp['locked'] and mp['status']=='PREDECLARED_UNSCORED'
    assert mp['economicAdmission']['capitalProspectiveEur']==300
    assert mp['product']['oneCapitalEUR300'] and mp['product']['noLiveOrDemoOrders']
    assert mp['statistical']['programmedGroups']==6
    assert mp['statistical']['totalOneSidedComparisons']==12
    assert mp['calendar']['globallyExposedAuditWeeksUnscored']==13
    assert [f['id'] for f in mp['families']]==[
        'SQUEEZE_RELEASE_30','H4_M30_PULLBACK_120',
        'TICK_CLIMAX_FADE_15','REOPEN_GAP_FADE_60',
        'INDEX_RELATIVE_DISPERSION_90']
    assert mr['provenance']['originalLockedProtocolSha256']==hashlib.sha256(mp_raw).hexdigest()
    assert mr['provenance']['originalMainRunId']==mfa['originalResultMainRunId']==ma['originalRunId']==42410064919
    assert mr['provenance']['originalPublicArtifactId']==ma['originalArtifactId']==mfa['originalPublicArtifactId']==13589436204
    assert mr['provenance']['originalPublicJsonSha256']==ma['originalPublicJsonSha256']==mfa['originalPublicArtifactJsonSha256']=='366ce1e8f20cfebfbad2e61a23892cf8446554c33ec7c6a142769a4824e2506b'
    assert mr['provenance']['originalM5Bars']==836087
    assert mr['provenance']['originalCurrentTermBidAskCostContexts']==166
    assert mr['results']['nativeParity']['exactSignAgreement'] is True
    assert mr['results']['nativeParity']['cases']==864
    assert mr['results']['nativeParity']['featureComparisonCount']==4320
    assert mr['results']['nativeParity']['observedNonzeroByMechanism']=={
        'IndexDispersion':66,'Pullback':88,'ReopenGap':61,'Squeeze':113,'VolumeClimax':60}
    assert len(mr['results']['eligibleSymbols'])==12
    assert len(mr['results']['familyVerdicts'])==5
    assert len(mr['method']['variableHoldingMinutes'])==5
    assert mr['results']['familyVerdicts']['REOPEN_GAP_FADE_60']['selection']['signalCount']==250
    assert mr['results']['familyVerdicts']['REOPEN_GAP_FADE_60']['selection']['bonferroniHac3AdverseNetLowerBps']==-10.950417183303696
    assert mr['results']['familyVerdicts']['SQUEEZE_RELEASE_30']['selection'] is None
    assert mr['results']['familyVerdicts']['H4_M30_PULLBACK_120']['selection'] is None
    assert mr['results']['familyVerdicts']['TICK_CLIMAX_FADE_15']['selection'] is None
    assert mr['results']['familyVerdicts']['INDEX_RELATIVE_DISPERSION_90']['selection'] is None
    assert mr['results']['adaptive']['development']['activeCalendarWeeks']==2
    assert mr['results']['adaptive']['selection'] is None
    assert mr['results']['adaptive']['developmentF2']['status']=='NOT_INFORMATIVE_NO_ECONOMIC_PROMOTION'
    assert mr['results']['qualified']==[] and mr['results']['adaptiveQualified'] is False
    assert mr['verdict']['newNativeCSharpFundedRoundTrips']==0
    assert mr['verdict']['admittedBrokerFundedNetEur'] is None
    assert mr['verdict']['independentConfirmation'] is False
    assert mr['verdict']['unscoredAuditViewed'] is False
    assert mr['verdict']['ordersSubmitted']==0
    assert mr['verdict']['cloudActivated'] is False
    assert mr['verdict']['refreshTokenUsed'] is False
    assert mfa['status']=='CLOSED_EXACT_COORDINATED_NATIVE_FIVE_FAMILIES_AND_ADAPTIVE_NO_QUALIFICATION'
    assert mfa['closedStudyReruns']==0 and mfa['exactClosedNoRetuning'] is True
    assert 'MultiFamilyNativeFeatures.Evaluate(' in Path('src/Mxm.Cloud/MxmCloud.cs').read_text()
    assert '--native-mfa1-feature-parity' in Path('src/Mxm.Replay/Program.cs').read_text()
    assert Path('src/Mxm.Core/MultiFamilyNativeFeatures.cs').is_file()
    
    # Original six NON-LEGACY asset classes, genuine historical H1/quote source:
    # first source attempt pre-score technical failure is separately disclosed;
    # the exact original XUA1 protocol never changed. Never use original
    # ERP1/MBF1 already-closed predictor, nor score globally exposed audit.
    xua = next(x for x in r['prospectiveStudies'] if x['id']=='XUA1')
    xur = json.loads(Path('docs/XUA1_AUTHENTIC_RESULT_20261108.json').read_text())
    xue = r['xua1AuthenticExpandedUniverseResult']
    xup_raw = Path('research/xua1_protocol.json').read_bytes()
    xup = json.loads(xup_raw)
    xur_proof = xur['provenance']
    assert xup['id']=='XUA1' and xup['locked'] is True and xup['status']=='PREDECLARED_UNSCORED'
    assert xup['fundedContinuation']['capitalOneWalletEur']==300
    assert xup['source']['additionalBrokerRequests']==0
    assert len(xup['families'])==4 and xup['uncertainty']['comparisonsAcrossProgramme']==8
    assert xur_proof['lockedProtocolSha256'] == xue['lockedProtocolSha256'] == hashlib.sha256(xup_raw).hexdigest()
    assert xur_proof['runId'] == xua['sourceResearchRunId'] == xue['sourceRun'] == 42421515437
    assert xur_proof['originalPublicArtifactId'] == xue['originalPublicArtifactId'] == 13593647547
    assert xur_proof['originalPublicJsonSha256'] == xue['originalPublicJsonSha256'] == '16da046cac6923c6ac284324d3060a4a15be790e71258d5bf6a2d09107359f7a'
    assert xur_proof['firstAttemptPreScoreTechnicalFailureRunId']==42420879815
    assert xur_proof['technicalRecoveryPRs']==[137,138]
    assert xur_proof['originalSourceRunIds']==[41948500095,41971150620]
    assert xur_proof['originalSourceBrokerRequests']==[319,531]
    assert xur['sourceAndCurrentTerms']['totalH1']==36341
    assert len(xur['sourceAndCurrentTerms']['technicallyEligibleSixMarkets'])==6
    assert all(c['pairedBidAsk']>=6 and 0<c['currentMinimumMarginEur']<300
               for c in xur['sourceAndCurrentTerms']['contractAndCostByMarket'].values())
    assert xur['nativeParity']['realOriginalMarketFrames']==960
    assert xur['nativeParity']['exactSignAgreement'] is True
    assert xur['nativeParity']['nativeCloudLibrary']=='Mxm.Core.XuaNativeFeatureSigns'
    families_xua=xur['originalEvaluatedFamilies']
    assert len(families_xua)==4
    energy_xua=families_xua['ENERGY_NEWS_IMPULSE_PERSISTENCE_4H']
    crypto_xua=families_xua['CRYPTO_PANIC_REBOUND_6H']
    asian_xua=families_xua['ASIAN_INDEX_RISK_SYNCHRONY_3H']
    gbpjpy_xua=families_xua['GBPJPY_REJECTION_WICK_2H']
    assert energy_xua['development']['signalCount']==921
    assert energy_xua['f2']['status']=='UPPER_BOUND_ALLOWS_PLAUSIBILITY_NOT_EVIDENCE'
    assert energy_xua['selection']['signalCount']==474
    assert energy_xua['selection']['perSignalMeanBps']['adverse']==-27.514357705895044
    assert energy_xua['selection']['adjustedAdverseNetLowerBps']==-51.21300734587574
    assert energy_xua['selection']['adjustedMatchedBenchmarkIncrementalLowerBps']==-35.377450722418764
    assert energy_xua['exactVerdict']=='EXACT_SELECTION_REJECTED_ADVERSE_OR_BENCHMARK'
    assert crypto_xua['development']['signalCount']==579 and crypto_xua['selection'] is None
    assert crypto_xua['f2']['status']=='NOT_INFORMATIVE_NO_ECONOMIC_PROMOTION'
    assert asian_xua['development']['signalCount']==478 and asian_xua['selection'] is None
    assert asian_xua['f2']['status']=='FUTILE_STOP_BEFORE_SELECTION'
    assert gbpjpy_xua['development']['signalCount']==135 and gbpjpy_xua['selection'] is None
    assert gbpjpy_xua['f2']['status']=='FUTILE_STOP_BEFORE_SELECTION'
    assert xur['method']['all52WeeksGloballyExposed'] is True
    assert xur['verdict']['status']==xua['status']=='CLOSED_EXACT_XUA1_SIX_NONLEGACY_H1_FOUR_FAMILIES_NO_SELECTION_PROMOTION'
    assert xur['verdict']['conditionalGroupIds']==[]
    assert xur['verdict']['auditWeeksScored']==0
    assert xur['verdict']['newNativeFundedClosedRoundTrips']==0
    assert xur['verdict']['originalBrokerFundedNetEur'] is None
    assert xur['verdict']['independentChronologicalConfirmation'] is False
    assert xur['verdict']['ordersSubmitted']==0
    assert xur['verdict']['cloudActivated'] is False
    assert xur['verdict']['tokenRefresh'] is False
    assert xue['closedOriginalERP1MBF1PredictorsReplayed'] is False
    assert xua['closedStudiesRerun']==0 and xua['exactClosedNoRetune'] is True
    assert Path('src/Mxm.Core/XuaNativeFeatureSigns.cs').exists()
    assert '--xua1-native-signs' in Path('src/Mxm.Replay/Program.cs').read_text()
    assert 'XuaNativeFeatureSigns' in Path('tests/Mxm.Checks/Program.cs').read_text()

    print('PASS OWNER v2.0 contract, frozen evidence, native funding and no-order boundary; no NET qualification')


if __name__ == '__main__':
    check()

    # COL1: recompute published exposed-source outcome arithmetic in existing CI.
    # No new broker request, workflow, protected credential, old strategy rerun,
    # confidential source read, orders, cloud, or holdout evaluation.
    from research.col1_exposed_session_premium import calculate
    import math
    calculated = calculate(json.loads(Path('docs/AIP1_AUTHENTIC_RESULT.json').read_text()))
    published = json.loads(Path('docs/COL1_EXPOSED_AUTHENTIC_RESULT_20261108.json').read_text())
    def same(a,b):
        if isinstance(a,dict) and isinstance(b,dict):
            return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
        if isinstance(a,list) and isinstance(b,list):
            return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
        if isinstance(a,float) and isinstance(b,(float,int)):
            return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
        return a==b
    assert same(calculated,published),'COL1_REPORT_MISMATCH'
    assert calculated['selectionEvents']==287 and calculated['missing']==0
    assert calculated['otherPhaseSourceRowsNotScored']==359
    assert sum(v>=21 for v in calculated['maxPotentialSignalSlotsByWeek'])==5
    assert calculated['jointHac3BonferroniDescriptive']['adverseVsCash']['meanBps'] < 0
    assert calculated['jointHac3BonferroniDescriptive']['adverseIncrementalVsFrozenAip1SideBenchmark']['meanBps'] < 0
    assert calculated['financedRoundTrips']==0 and calculated['conditionalNetEur'] is None
    assert not calculated['independentConfirmation'] and not calculated['tradingQualification']
    print('PASS COL1 historical price proxy, negative two adverse endpoints; no funded qualification')
