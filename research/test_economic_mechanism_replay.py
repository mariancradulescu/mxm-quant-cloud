"""Full shared replay and partition reconciliation on synthetic source only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from .test_owner_eur_checkpoint import fixture
from .owner_eur_checkpoint import REPLAY
from .merge_economic_mechanisms import merge,comparison

class MechanismReplay(unittest.TestCase):
    def test_registered_mechanisms_share_causal_replay_and_exact_partition_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work)
            baseline=json.loads((work/'protocol.json').read_bytes())
            p=json.loads(Path('research/economic_mechanisms_1.json').read_bytes())
            for key in ('InitialFitFrom','TestBoundaries','SourceProtocolSha256','EvidenceManifestSha256'):
                p[key]=baseline[key]
            p.update(Stresses=[0],ArchivedSampledQuotes=True,EconomicMechanismComparison=True)
            for c in p['Calibrations']:c['Profile']['ModelFundingAtPriorClosedSessionQuote']=False
            protocol=work/'protocol.json';protocol.write_text(json.dumps(p));reports=[]
            for group in p['TrialGroups']:
                path=work/(group+'.json')
                env=dict(os.environ,MXM_ECONOMIC_SCENARIO_INDEX='0',MXM_ECONOMIC_TRIAL_GROUP=group,
                    MXM_ECONOMIC_REUSE_FRAMES='1',MXM_ECONOMIC_PAIRED_DISTRIBUTION='1')
                subprocess.run(['dotnet',REPLAY,'--owner-eur-historical-study',str(protocol),
                    str(work/'source.json'),str(path),str(work/'verified-protection')],
                    env=env,check=True,stdout=subprocess.DEVNULL)
                reports.append(path)
            result=merge(protocol,reports);scenario=result['Summary']['Results'][0]
            self.assertEqual(len(scenario['Trials']),19)
            self.assertEqual(len(scenario['MechanismEvidence']),19)
            self.assertEqual(result['Summary']['Orders'],0)
            self.assertFalse(result['Summary']['IndependentConfirmationCertified'])
            cash=next(t for t in scenario['Trials'] if t['Id']=='CASH_CONTROL')['Result']
            self.assertEqual((cash['CashEur'],cash['Closed']),(300,0))
            self.assertTrue(any(t['Result']['Closed']>0 for t in scenario['Trials']))
            self.assertEqual(len(comparison(result)['ManagementComparisons']),9)
