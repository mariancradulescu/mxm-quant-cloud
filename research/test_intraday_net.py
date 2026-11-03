import unittest
from .intraday_net import reconstruct
from .guard import require_read_only_request, CaptureContractError
from .ctrader_proto import OpenApiMessages_pb2 as m

class IntradayNetChecks(unittest.TestCase):
    def test_observed_sides_and_stale_rejection(self):
        self.assertEqual(reconstruct([[1001,110000]],[[1002,110002]],1000),
            {'time':1002,'bid':110000,'ask':110002})
        self.assertEqual(reconstruct([[1001,110005],[1001,110000]],[[1001,110002]],1000),
            {'time':1001,'bid':110000,'ask':110002})
        self.assertIsNone(reconstruct([[1001,110000]],[],1000))
        self.assertIsNone(reconstruct([[1001,110000]],[[5000,110002]],1000))
        self.assertIsNone(reconstruct([[1001,110003]],[[1002,110002]],1000))
        self.assertIsNone(reconstruct([[12000,110000]],[[12001,110002]],1000))
    def test_margin_reads_not_orders(self):
        require_read_only_request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=1,symbolId=2,volume=[100000]))
        require_read_only_request(m.ProtoOAAssetListReq(ctidTraderAccountId=1))
        require_read_only_request(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=1,leverageId=1))
        with self.assertRaises(CaptureContractError):
            require_read_only_request(m.ProtoOACancelOrderReq(ctidTraderAccountId=1,orderId=1))

    def test_native_money_cost_identity_and_stress_order(self):
        from pathlib import Path
        import json
        from .intraday_net import native
        if not Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists():
            self.skipTest('native build required')
        start=1767578400000  # 2026-01-05 02 UTC
        rows=[{'t':start+i*900000,'o':110000,'h':110500 if i==15 else 110100,
               'l':109900,'c':110500 if i==15 else 110000} for i in range(25)]
        entry=start+16*900000
        root={'schema':'mxm-intraday-net-v1','readOnly':True,'start':start,'end':start+370*86400000,
              'bars':rows,'currentMarginEur':34,'conservativeLeverage':30,
              'contract':{'minVolume':100000,'stepVolume':100000,'maxVolume':100000000,
              'lotSize':10000000,'commissionType':1,'minCommissionType':1,'minCommissionAsset':'USD',
              'preciseTradingCommissionRate':3500000000,'preciseMinCommission':0,'pnlConversionFeeRate':10,
              'swapLong':-7,'swapShort':-2,'swapCalculationType':0},
              'quotes':{str(entry):{'time':entry+100,'bid':110000,'ask':110002},
                        str(entry+3600000):{'time':entry+3600100,'bid':110100,'ask':110102}}}
        r=native(root,'--intraday-net');a,b,c=r['scenarios']
        self.assertEqual(r['proposals'],1)
        self.assertEqual(a['completeModeledRoundTrips'],1)
        self.assertAlmostEqual(a['grossEur']-a['totalCostEur'],a['netEur'],places=8)
        for k in ('spreadCostEur','commissionEur','slippageEur','conversionFeeEur','financingEur'):
            self.assertGreater(a[k],0)
        self.assertGreater(a['netEur'],b['netEur']);self.assertGreater(b['netEur'],c['netEur'])
        self.assertFalse(r['fullyFundedExecutionProven'])
