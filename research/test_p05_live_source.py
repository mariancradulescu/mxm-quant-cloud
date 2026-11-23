"""Offline source-specific checks. No credentials, socket, or broker queries."""
import ast
import unittest
from pathlib import Path
from decimal import Decimal

from .p05_live_source import (
    START,END,PERIODS,MAX_MARKETS,
    choose_visible,choose_market_sample,spread_bps,gate
)
from .p05_safe_transport import P05ReadOnlyTransport
from .guard import ALLOWED

class LiveP05Preflight(unittest.TestCase):
    def test_closed_horizon_before_future_confirmation(self):
        self.assertLess(START,END)
        self.assertEqual(set(PERIODS),{"M15","M30","H1","H4","D1"})
        self.assertGreater(MAX_MARKETS,12)

    def test_complete_visible_roster_and_no_old_favorites(self):
        data=[{"symbolId":i,"visible":True,"symbolName":str(i)} for i in range(1,1500)]
        self.assertEqual(len(choose_visible(data)),1499)

    def test_cost_first_sampling_and_no_unfundable_margin(self):
        rows=[dict(symbolId=i,symbolName=str(i),visible=True,
                   symbolCategoryId=i%5,currentMinMarginEur=str(i%100+1),
                   contractStatus="MARGIN_OBSERVED") for i in range(1,301)]
        rows.append(dict(symbolId=9999,symbolName="NO",symbolCategoryId=7,
                         currentMinMarginEur="300",contractStatus="MARGIN_OBSERVED"))
        choice=choose_market_sample(rows)
        self.assertEqual(len(choice),MAX_MARKETS)
        self.assertTrue(all(Decimal(x["currentMinMarginEur"])<300 for x in choice))
        self.assertEqual({x["symbolCategoryId"] for x in choice},{0,1,2,3,4})

    def test_bidask_requires_asof_both_sides(self):
        expected=20000*(1000)/(20001000)
        self.assertEqual(spread_bps([(1000,10000000)],[(1002,10001000)]),[expected])
        self.assertEqual(spread_bps([(1000,10000000)],[(9000,10001000)]),[])
        self.assertEqual(spread_bps([(3000,10000000)],[(1000,10001000)]),[])
        self.assertEqual(spread_bps([(1000,10002000)],[(1000,10001000)]),[])

    def test_whitelist_every_raw_openapi_request_in_collector(self):
        code=Path(__file__).with_name("p05_live_source.py").read_text()
        tree=ast.parse(code)
        calls={n.func.attr for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and isinstance(n.func.value,ast.Name) and n.func.value.id=="m"
               and n.func.attr.endswith("Req")}
        self.assertTrue(calls)
        self.assertFalse(calls-ALLOWED)
        self.assertIn("P05ReadOnlyTransport(response_timeout=30)",code)
        self.assertNotIn("StdlibCTraderTransport(",code)
        self.assertNotIn("ProtoOANewOrderReq(",code)
        self.assertNotIn("ProtoOARefreshTokenReq(",code)

if __name__=="__main__":
    unittest.main()
