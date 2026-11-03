import copy,unittest
from pathlib import Path
from .intraday_net import native

class NeighbourNativeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists():raise unittest.SkipTest('native required')
        start=1735689600000
        bars={}
        for symbol,base,delta in [('USDJPY',15000000,2000),('USDCAD',130000,20),('EURUSD',110000,20)]:
            bars[symbol]=[{'t':start+i*3600000,'o':base,'h':base+delta*1.5,'l':base-delta*.5,'c':base+delta} for i in range(370*24)]
        common={'minVolume':100000,'stepVolume':100000,'maxVolume':100000000,'lotSize':10000000,'preciseTradingCommissionRate':3500000000,'preciseMinCommission':0,
            'commissionType':1,'minCommissionType':1,'minCommissionAsset':'USD','pnlConversionFeeRate':0,'swapLong':-1,'swapShort':-2,'swapCalculationType':0,'swapPeriod':24,'swapTime':1320,
            'slDistance':0,'tpDistance':0,'distanceSetIn':1}
        cls.root={'schema':'mxm-neighbour-net-v1','source':'Pepperstone-cTrader-OpenAPI','readOnly':True,'start':start,'end':start+370*86400000,
            'bars':bars,'contracts':{'USDJPY':dict(common,digits=3,pipPosition=2),'USDCAD':dict(common,digits=5,pipPosition=4)},
            'margins':{'USDJPY':31,'USDCAD':31},'leverage':{'USDJPY':30,'USDCAD':30},'screenEurAsk':1.1,'eurShock':.01,'minutes':{},'quotes':{},
            'calibration':{'USDJPY':{'gap':.001,'spread':.002,'spreadStress':.004,'move':.001,'shock':.01},'USDCAD':{'gap':.00001,'spread':.00002,'spreadStress':.00004,'move':.00001,'shock':.01}}}
    def test_holdout_price_changes_do_not_change_selection_forecasts(self):
        a=native(self.root,'--neighbour-plan');self.assertGreater(len(a),0)
        other=copy.deepcopy(self.root);cut=self.root['start']+(self.root['end']-self.root['start'])*8//10
        for rows in other['bars'].values():
            for b in rows:
                if b['t']>=cut:
                    for k in ('o','h','l','c'):b[k]*=1.5
        self.assertEqual(a,native(other,'--neighbour-plan'))
    def test_missing_minute_paths_cannot_be_zero_cost_trades(self):
        a=native(self.root,'--neighbour-selection');self.assertEqual(a['selectionSurvivors'],[])
        for result in a['results']:
            for scenario in result['scenarios']:
                self.assertEqual(scenario['completeModeledRoundTrips'],0)
                self.assertGreater(scenario['dataMissing'],0)
    def test_usd_base_money_and_adaptive_scenario_boundaries(self):
        r=copy.deepcopy(self.root);p=native(r,'--neighbour-plan')[0];s=p['Symbol'];base=15002000 if s=='USDJPY' else 130020;tick=100 if s=='USDJPY' else 1
        r['minutes'][s+':'+str(p['Entry'])]=[{'t':p['Entry']+j*60000,'o':base,'h':base+tick*10,'l':base-tick*10,'c':base} for j in range(120)]
        r['quotes'][s+':'+str(p['Entry'])]={'time':p['Entry']+10,'bid':base,'ask':base+tick}
        r['quotes'][s+':'+str(p['Horizon'])]={'time':p['Horizon']+10,'bid':base+tick*20,'ask':base+tick*21}
        for t in (p['Entry'],p['Horizon']):r['quotes']['EURUSD:'+str(t)]={'time':t+10,'bid':110000,'ask':110002}
        out=native(r,'--neighbour-selection');case=next(v for v in out['results'] if v['symbol']==s)['scenarios'][0]
        self.assertEqual(case['completeModeledRoundTrips'],1)
        self.assertAlmostEqual(case['grossEur']-case['totalCostEur'],case['netEur'],places=8)
        self.assertLessEqual(case['maxAggregateReservedRiskRatio'],.30)
        self.assertLessEqual(case['maxAggregateMarginRatio'],1)
        self.assertGreaterEqual(case['minFreeReserveRatio'],0)
