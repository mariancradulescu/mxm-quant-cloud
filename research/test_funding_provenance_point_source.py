"""Offline only. Synthetic data tests structure, never broker authenticity."""
import ast
import unittest
from pathlib import Path

from .ctrader_proto import OpenApiModelMessages_pb2 as model
from .funding_provenance_point_source import observation, SYMBOLS
from .guard import ALLOWED, CaptureContractError

class FundingPointSourceChecks(unittest.TestCase):
    def test_point_is_never_a_tariff_interval_or_funding_offer(self):
        c = model.ProtoOASymbol(symbolId=126, swapLong=-6.42, swapShort=1.42)
        o = observation(c,126,100,120)
        self.assertEqual(o["availableAt"],120)
        self.assertEqual(o["observedFields"]["swapLong"],-6.42)
        self.assertIsNone(o["observedFields"]["swapPeriod"])
        self.assertIsNone(o["effectiveFrom"])
        self.assertIsNone(o["effectiveThrough"])
        self.assertIsNone(o["maximumDebitEur"])
        self.assertIsNone(o["exactSignedEur"])
        self.assertFalse(o["historicalContinuityCertified"])

    def test_wrong_instrument_or_reverse_time_fails(self):
        c = model.ProtoOASymbol(symbolId=126)
        for sid, start, end in ((127,100,120),(126,120,100),(126,0,100)):
            with self.assertRaises(CaptureContractError):
                observation(c,sid,start,end)

    def test_targets_and_request_types(self):
        self.assertEqual(SYMBOLS,{"NAS100":126,"US500":127})
        code = Path(__file__).with_name("funding_provenance_point_source.py").read_text()
        calls = {n.func.attr for n in ast.walk(ast.parse(code))
                 if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                 and isinstance(n.func.value,ast.Name) and n.func.value.id=="m"
                 and n.func.attr.endswith("Req")}
        self.assertEqual(calls,{"ProtoOATraderReq","ProtoOAAssetListReq",
                               "ProtoOASymbolsListReq","ProtoOASymbolByIdReq"})
        self.assertFalse(calls-ALLOWED)
        self.assertIn("P05ReadOnlyTransport(response_timeout=30)",code)

if __name__=="__main__":
    unittest.main()
