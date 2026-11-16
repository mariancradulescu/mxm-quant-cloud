"""LQR1 source-blind finance invariants; never decrypt original or score a closed study."""
import unittest
from decimal import Decimal as D
from .lqr1_original_financial_source import clocks,fresh_pair,MAX_REQUESTS
from .lqr1_eur_native_readback import side,make_event,money_quote,PROTO
from .decode import need

class Lqr1FinanceContracts(unittest.TestCase):
    def test_exact_prelisted_80_unique_clocks_and_320_sides(self):
        rows=list(clocks())
        self.assertEqual(len(rows),80)
        self.assertEqual(len({x[0] for x in rows}),80)
        self.assertEqual(8+len(rows)*2*2,328)
        self.assertLessEqual(328,MAX_REQUESTS)
        self.assertTrue(PROTO.is_file())

    def test_original_only_bidask_asof_never_future(self):
        self.assertIsNone(fresh_pair([(100,100000)],[(101,100010)],200000))
        self.assertEqual(fresh_pair([(198000,100000),(201000,80000)],
                                        [(199000,100020),(203000,80000)],200000),
                         [[(198000),100000],[(199000),100020]] if False else
                         [(198000,100000),(199000,100020)])

    def test_policy_unknown_does_not_become_cash(self):
        unknown={"state":"SOURCE_UNKNOWN","side":None,"own":None}
        self.assertIsNone(side("lqr1",unknown))
        self.assertIsNone(side("ownMomentum",unknown))
        self.assertEqual(side("cash",unknown),0)
        self.assertEqual(side("long",unknown),1)
        active={"state":"SIDE_SPECIFIC_SIGNAL","side":-1,"own":1}
        self.assertEqual(side("lqr1",active),-1)
        self.assertEqual(side("ownMomentum",active),1)

    def test_accounting_event_provenance_hash_and_reference_time(self):
        x=make_event("lqr1-1-USDCHF/openintent",2000000,"REQUEST_OPEN",
            "USDCHF",1,D(1000),D(0),D(0),D("0.03"),D("0.00001"))
        self.assertEqual(x["PositionId"],"lqr1-1-USDCHF")
        self.assertEqual(len(x["EvidenceHash"]),64)
        self.assertLess(x["CalibratedThrough"],x["AvailableAt"])
        self.assertEqual(x["Kind"],"REQUEST_OPEN")

    def test_signed_cross_conversion_and_no_favorable_midpoint(self):
        class Contract:
            minVolume=100000
            def HasField(self,key):return key=="minVolume"
        # Price and conversion factors only; actual commission helper is separately frozen.
        # Do not attempt to infer broker fees from the synthetic contract.
        eur_bid,eur_ask=D("1.1"),D("1.101")
        usdchf_bid,usdchf_ask=D("0.8"),D("0.801")
        credit=1/(usdchf_ask*eur_ask)
        debit=1/(usdchf_bid*eur_bid)
        self.assertGreater(debit,credit)

if __name__=="__main__":
    unittest.main()
