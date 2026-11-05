"""ERP1 frozen protocol and causal research regression; no broker requests."""
import json,unittest,math
from pathlib import Path
from .erp1_research import cost_envelopes,evaluate,HOUR,WEEK
from .erp1_source import windows,clocks
class ERP1Checks(unittest.TestCase):
    def setUp(self):self.p=json.loads(Path('research/erp1_protocol.json').read_text())
    def test_exact_protocol_and_readonly_budget(self):
        p=self.p
        self.assertEqual(len(windows(p)),52)
        self.assertEqual(len(clocks(p)),52)
        self.assertEqual(3+4+104+208,319)
        self.assertGreaterEqual(p['maxRequests'],319)
        self.assertEqual(p['endUtcMs']-p['selectionEndUtcMs'],13*WEEK)
        self.assertEqual(p['selectionEndUtcMs']-p['developmentEndUtcMs'],13*WEEK)
        self.assertEqual(p['decisionHoursUtc'],[0,4,8,12,16])
    def test_missing_spread_is_not_free(self):
        p=self.p
        self.assertIsNone(cost_envelopes({'SpotCrude':[2],'SpotBrent':[]},p))
        c=cost_envelopes({'SpotCrude':[2]*8,'SpotBrent':[3]*8},p)
        self.assertEqual(c,{'central':13.5,'adverse':22.0,'stress':39.0})
    def test_unknown_data_not_cash(self):
        p=self.p
        x=evaluate({'SpotCrude':{},'SpotBrent':{}},{},{},p)
        self.assertIsNone(x['fundedNetEur'])
        self.assertIsNone(x['historicalSpreadPlusHypotheticalNonFundingCostCasesBps'])
        self.assertEqual(x['phase']['selection']['allWeekUnfundedOpportunityCounts'],[0]*13)
        self.assertEqual(x['phase']['globallyExposedAudit']['weeksWithZeroOpportunities'],13)
        self.assertFalse(x['systemHard21Proven'])
        self.assertFalse(x['independentConfirmation'])
    def test_known_cost_margins_never_finance_net(self):
        p=self.p;start=p['startUtcMs']
        a={start+i*HOUR:10000000 for i in range(1,350)}
        b={start+i*HOUR:int(10500000*(1+.001*math.sin(i/7))) for i in range(1,350)}
        inputs={'SpotCrude':[2]*8,'SpotBrent':[3]*8}
        x=evaluate({'SpotCrude':a,'SpotBrent':b},inputs,
            {'SpotCrude':7.87,'SpotBrent':8.76},p)
        self.assertAlmostEqual(x['marginCurrentMinimumPairEur'],16.63)
        self.assertTrue(x['staticCurrentMarginBelowEUR200'])
        self.assertIsNone(x['fundedNetEur'])
        self.assertFalse(x['nativeAllocatorInvoked'])
        self.assertFalse(x['historicalAllInCostsCertified'])
if __name__=='__main__':unittest.main()
