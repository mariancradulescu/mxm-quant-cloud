"""Causal full native book regression and preservation of the original controls."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from .test_owner_eur_checkpoint import fixture,START,END,DAY
from .owner_monetary_causal_lifecycle import registered,REPLAY,diagnose
from .owner_monetary_geometry_breadth import registered as prior_registered


class CausalLifecycle(unittest.TestCase):
    def test_registered_controls_and_risk_are_preserved(self):
        plan,_=registered();prior,_=prior_registered()
        for v in plan['Variants']:
            if v['Reference']:
                original=next(x for x in prior['Variants'] if x['Id']==v['Mechanism']+'__FILL_RISK')
                self.assertEqual(v['Profile'],original['Profile'])
            if v['Profile'].get('OptimizeTransitionNetVolume'):
                self.assertEqual(v['Mechanism'],'PAV1_LOCAL_TRANSITION')
                self.assertTrue(v['Profile']['MatchEconomicTransitionHorizonAtFill'])
        self.assertEqual(len(plan['Variants'])*3,93)

    def test_pav1_native_isolated_and_common_books(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work)
            source=json.loads((work/'source.json').read_bytes())
            p,_=registered();mechanism='PAV1_LOCAL_TRANSITION'
            plan={k:p[k] for k in ('Study','Exposure','SamplingIntervalMs','Stresses')}
            plan.update(SourceProtocolSha256=source['ProtocolSha256'],EvidenceManifestSha256=source['EvidenceManifestSha256'],
                Start=START,SelectionFrom=START+3*DAY,EvaluationFrom=START+6*DAY,End=END,
                Variants=[v for v in p['Variants'] if v['Mechanism']==mechanism])
            protocol=work/'lifecycle.json';protocol.write_text(json.dumps(plan));report=work/'result.json'
            subprocess.run(['dotnet',REPLAY,'--owner-opportunity-screen',str(protocol),str(work/'source.json'),
                str(report),str(work/'verified-protection')],check=True,stdout=subprocess.DEVNULL,
                env=dict(os.environ,MXM_OPPORTUNITY_MECHANISM=mechanism,MXM_ECONOMIC_REUSE_FRAMES='1'))
            r=json.loads(report.read_bytes())
            self.assertEqual((len(r['HeldOut']),r['SharedPortfolioEvaluations']),(21,24))
            self.assertEqual((r['Orders'],r['CloudActivated']),(0,False))
            for row in r['HeldOut']:
                self.assertEqual(row['BreadthQuality']['All']['RiskGrowthAtFill'],0)
                self.assertTrue(all(x['Quality']['CausalReasons'] for x in row['BreadthQuality']['Instruments']))
            for book in r['CommonBooks']:
                self.assertEqual(book['Result']['InitialCapitalEur'],300)
                self.assertEqual(len(book['Result']['Folds']),2)
                self.assertEqual(book['Result']['Folds'][0]['Through'],plan['EvaluationFrom'])
                self.assertEqual(book['Result']['Folds'][1]['From'],plan['EvaluationFrom'])
                if book['Id']=='CASH_CONTROL':
                    self.assertEqual((book['Result']['CashEur'],book['Result']['Closed']),(300,0))
            self.assertGreater(sum(b['Result']['Closed'] for b in r['CommonBooks']),0)

    def test_recalculation_never_fills_unknown_cash(self):
        episodes=[dict(Symbol='SYNTH',NetEur=None,Status='UNKNOWN_CLOSED',FillReasons=None),
            dict(Symbol='SYNTH',NetEur=-2,Status='RECONCILED',FillReasons=None,OpenAt=100,CloseAt=110,
                CostRiskFraction=.25)]
        p=dict(Results=[dict(Mechanism='TEST',HeldOut=[dict(Stress=0,Id='TEST__BASE',Episodes=episodes)])])
        result=diagnose(p)['Results'][0]
        self.assertEqual((result['Known'],result['KnownNetSubtotalEur'],len(result['Unresolved'])),(1,-2,1))


if __name__=='__main__':unittest.main()
