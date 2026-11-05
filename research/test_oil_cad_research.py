"""Precise OCE1 causal integration tests; no old model or source replay."""
from pathlib import Path
import json
import math
import unittest
from .oil_cad_research import evaluate,first_causal_spread,cost_scenarios,MINUTE,HOUR,WEEK

class OCE1Checks(unittest.TestCase):
    def setUp(self):self.p=json.loads(Path('research/oil_cad_protocol.json').read_text())
    def test_earliest_causal_quote_not_cheapest_future(self):
        bid=[(1000,10000),(4000,9900)];ask=[(1100,10020),(4100,9901)]
        q=first_causal_spread(bid,ask,1000,window_ms=5000)
        self.assertAlmostEqual(q,20000*20/20020)
    def test_missing_quote_does_not_mean_free(self):
        self.assertIsNone(first_causal_spread([(1000,10000)],[],1000))
        self.assertIsNone(cost_scenarios([1]*7,self.p))
        self.assertGreater(cost_scenarios([1]*8,self.p)['adverse'],0)
    def test_empty_historical_clocks_never_create_financed_net(self):
        result=evaluate({},{},[],None,self.p)
        self.assertEqual(result['phase']['selection']['completeUnfundedSignals'],0)
        self.assertIsNone(result['fundedNetEur'])
        self.assertFalse(result['selectionSupportedConditionalFollowupOnly'])
    def test_price_lookahead_and_incomplete_m5_missing_not_filled(self):
        p=self.p;start=p['decisionCalendar']['startUtcMs']
        # Calendar starts Monday. Tuesday noon is the first decision.
        oil={start+i*HOUR:math.exp(.0001*i) for i in range(0,60)}
        t=start+36*HOUR
        fx={t+i*MINUTE:1.30 for i in range(5,126,5)}
        x=evaluate(oil,fx,[1]*8,30,p)
        self.assertGreaterEqual(x['preflightComplete']['scheduledClocks'],1)
        self.assertTrue(x['preflightComplete']['incompleteFxEntryHoldingMarks']>0)
        self.assertEqual(x['phase']['selection']['completeUnfundedSignals'],0)
    def test_financial_limit_is_not_volume_validity(self):
        x=evaluate({},{},[2]*8,'29.79',self.p)
        self.assertTrue(x['staticSingleUsdCadMinMarginBelowInitial200Eur'])
        self.assertFalse(x['brokerExecutionCostProven'])
        self.assertFalse(x['independentConfirmation'])
        self.assertFalse(x['hard21Proven'])

if __name__=='__main__':unittest.main()
