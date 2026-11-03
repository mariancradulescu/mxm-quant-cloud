import unittest
from pathlib import Path
from .intraday_net import native

class FlowNativeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists():raise unittest.SkipTest('native build required')
        start=1735689600000;days=370
        bars={s:[{'t':start+i*900000,'o':base,'h':base+60,'l':base-10,'c':base+50} for i in range(days*96)] for s,base in [('GBPUSD',125000),('AUDUSD',65000)]}
        c={'minVolume':100000,'stepVolume':100000,'maxVolume':100000000,'lotSize':10000000,'preciseTradingCommissionRate':3500000000,
           'preciseMinCommission':0,'commissionType':1,'minCommissionType':1,'minCommissionAsset':'USD','pnlConversionFeeRate':0,
           'swapLong':-1,'swapShort':-2,'swapCalculationType':0,'swapPeriod':24,'swapTime':1320,'slDistance':0,'tpDistance':0,'distanceSetIn':1,'digits':5,'pipPosition':4}
        cls.root={'schema':'mxm-flow-net-v1','source':'Pepperstone-cTrader-OpenAPI','readOnly':True,'start':start,'end':start+days*86400000,
                  'bars':bars,'contracts':{s:c.copy() for s in bars},'margins':{'GBPUSD':40,'AUDUSD':20},'leverage':{'GBPUSD':30,'AUDUSD':30},'screenEurAsk':1.1,'quotes':{}}
    def test_confirmation_changes_cannot_change_selection_plans(self):
        import copy
        a=native(self.root,'--flow-plan');self.assertGreater(len(a),0)
        other=copy.deepcopy(self.root);cut=self.root['start']+(self.root['end']-self.root['start'])*8//10
        for rows in other['bars'].values():
            for row in rows:
                if row['t']>=cut:
                    for k in ('o','h','l','c'):row[k]*=2
        self.assertEqual(a,native(other,'--flow-plan'))
    def test_missing_quotes_are_not_zero_cost_trades(self):
        r=native(self.root,'--flow-selection')
        self.assertEqual(r['selectionSurvivors'],[])
        for m in r['results']:
            for s in m['scenarios']:
                self.assertEqual(s['completeModeledRoundTrips'],0)
                self.assertGreater(s['missingQuotes'],0)
                self.assertFalse(s['passesPredeclaredSelection'])
    def test_native_net_conservation_and_preventive_capacity(self):
        import copy
        r=copy.deepcopy(self.root);p=native(r,'--flow-plan')[0]
        base=125000 if p['Symbol']=='GBPUSD' else 65000
        r['quotes']={p['Symbol']+':'+str(p['Entry']):{'time':p['Entry']+10,'bid':base+50,'ask':base+52},
                     p['Symbol']+':'+str(p['Exit']):{'time':p['Exit']+10,'bid':base+80,'ask':base+82}}
        for t in (p['Entry'],p['Exit']):r['quotes']['EURUSD:'+str(t)]={'time':t+10,'bid':110000,'ask':110002}
        out=native(r,'--flow-selection');s=next(x for x in out['results'] if x['model']==p['Model'])['scenarios'][0]
        self.assertEqual(s['completeModeledRoundTrips'],1)
        self.assertAlmostEqual(s['grossEur']-s['totalCostEur'],s['netEur'],places=8)
        self.assertLess(s['maxAdmittedScenarioDrawdown'],.3)
        self.assertGreater(s['commissionEur'],0)
