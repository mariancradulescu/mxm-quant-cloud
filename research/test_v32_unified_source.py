"""Minimal input-shape parity for the SAME integrated source adapter, no broker."""
import unittest
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .v32_unified_source_adapter import term

class V32BrokerSourceContractShape(unittest.TestCase):
    def test_original_p05_protobuf_contract(self):
        original=e.ProtoOASymbol(symbolId=1,digits=5,pipPosition=4)
        original.minVolume=100
        original.stepVolume=100
        original.maxVolume=10000
        original.lotSize=10000
        original.commissionType=1
        original.preciseTradingCommissionRate=70000000
        original.preciseMinCommission=0
        original.minCommissionType=1
        original.minCommissionAsset="USD"
        original.swapLong=-1
        original.swapShort=-2
        result=term("SYNTHETIC",original,"USD","12.34",2.5,1795392000000)
        self.assertEqual(result["MinimumUnits"],"1.0")
        self.assertEqual(result["MarginMinimumEur"],"12.34")
        self.assertEqual(result["MinimumCommissionAsset"],"USD")
        self.assertEqual(result["SwapLong"] if "SwapLong" in result else result["LongSwap"],-1)
        self.assertFalse(result["HistoricallyCertified"])
    def test_historical_source_dictionary_shape(self):
        data={"contract":{"minVolume":100,"stepVolume":100,"maxVolume":10000,
                          "lotSize":10000,"commissionType":1,
                          "preciseTradingCommissionRate":70000000,
                          "preciseMinCommission":0,"minCommissionType":1,
                          "minCommissionAsset":"USD"}}
        result=term("SYNTHETIC",data,"USD","15.00",1.2,1795392000000)
        self.assertEqual(result["MinimumCommissionAsset"],"USD")
        self.assertEqual(result["CommissionType"],1)
        self.assertIsNone(result["LongSwap"])

if __name__=="__main__":
    unittest.main()
