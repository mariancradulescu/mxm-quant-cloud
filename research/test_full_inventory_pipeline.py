"""Synthetic no-network regression suite for the full cTrader account inventory."""
import copy
import hashlib
import unittest
from types import SimpleNamespace
from .full_inventory_pipeline import from_pairs,select_probe_ids
from .full_inventory_core import (
    normalize_account_inventory,classify_contract_and_min_margin,
    InventoryIntegrityError,public_receipt)

class Proto:
    def __init__(self, **fields):
        object.__setattr__(self,"_present",set(fields))
        for k,v in fields.items():object.__setattr__(self,k,v)
    def __getattr__(self,key):
        if key=="tradingMode":return 0
        raise AttributeError(key)
    def __setattr__(self,k,v):
        if not k.startswith("_"):self._present.add(k)
        object.__setattr__(self,k,v)
    def HasField(self,k):return k in self._present
    def IsInitialized(self):return True
    def CopyFrom(self,other):
        self.__dict__.clear()
        self.__dict__.update(copy.deepcopy(other.__dict__))

class TraderReq(Proto):pass
class TraderRes(Proto):pass
class AssetReq(Proto):pass
class AssetRes(Proto):pass
class ListReq(Proto):pass
class ListRes(Proto):pass
class DetailReq(Proto):pass
class DetailRes(Proto):pass
class MarginReq(Proto):pass
class MarginRes(Proto):pass

M=SimpleNamespace(ProtoOATraderReq=TraderReq,ProtoOATraderRes=TraderRes,
    ProtoOAAssetListReq=AssetReq,ProtoOAAssetListRes=AssetRes,
    ProtoOASymbolsListReq=ListReq,ProtoOASymbolsListRes=ListRes,
    ProtoOASymbolByIdReq=DetailReq,ProtoOASymbolByIdRes=DetailRes,
    ProtoOAExpectedMarginReq=MarginReq,ProtoOAExpectedMarginRes=MarginRes)

def pair_fixture():
    aid=41
    trader=Proto(brokerName="Pepperstone EU",depositAssetId=1)
    symbols=[
        Proto(symbolId=15,symbolName="SILVER",enabled=True,
              baseAssetId=2,quoteAssetId=1,symbolCategoryId=2),
        Proto(symbolId=10,symbolName="FX1",enabled=True,
              baseAssetId=1,quoteAssetId=2,symbolCategoryId=1),
        Proto(symbolId=11,symbolName="FX2",enabled=True,
              baseAssetId=1,quoteAssetId=2,symbolCategoryId=1),
        Proto(symbolId=17,symbolName="DISABLED",enabled=False,
              baseAssetId=1,quoteAssetId=2,symbolCategoryId=3)]
    pairs=[
        (TraderReq(ctidTraderAccountId=aid),
         TraderRes(ctidTraderAccountId=aid,trader=trader)),
        (AssetReq(ctidTraderAccountId=aid),
         AssetRes(ctidTraderAccountId=aid,
                  asset=[Proto(assetId=1,name="EUR"),Proto(assetId=2,name="USD")])),
        (ListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False),
         ListRes(ctidTraderAccountId=aid,symbol=symbols))]
    for sid in [10,15,11]:
        c=Proto(symbolId=sid,digits=5,pipPosition=4,
                minVolume=100,stepVolume=100,maxVolume=100000)
        pairs.append((DetailReq(ctidTraderAccountId=aid,symbolId=[sid]),
                      DetailRes(ctidTraderAccountId=aid,symbol=[c])))
        pairs.append((MarginReq(ctidTraderAccountId=aid,symbolId=sid,volume=[100]),
                      MarginRes(ctidTraderAccountId=aid,moneyDigits=2,
                                margin=[Proto(volume=100,buyMargin=3300+sid,
                                              sellMargin=3100+sid)])))
    fp=hashlib.sha256(f"ctrader-account:{aid}".encode()).hexdigest()
    commitment=hashlib.sha256(fp.encode()).hexdigest()
    return pairs,commitment

class CompleteInventoryChecks(unittest.TestCase):
    def test_full_symbol_list_not_fixed_historical_universe(self):
        p,h=pair_fixture();d=from_pairs(p,M,h)
        self.assertEqual(len(d["rows"]),4)
        self.assertEqual(d["probes"],[10,15,11])
        self.assertEqual(d["rows"][-1]["contractStatus"],"NOT_QUERIED")
        self.assertEqual(d["requestCount"],9)
        self.assertEqual(sum(x["contractStatus"]=="CURRENT_MIN_MARGIN_OBSERVED_COSTS_UNVERIFIED"
                             for x in d["rows"]),3)
        self.assertEqual(public_receipt(d["rows"])["visibleSymbols"],3)
    def test_large_roster_is_preserved_with_finite_probes(self):
        p,h=pair_fixture()
        p[2][1].symbol.extend([
            Proto(symbolId=1000+i,symbolName=f"S{i}",enabled=True,
                  baseAssetId=1,quoteAssetId=2,symbolCategoryId=i%5)
            for i in range(150)])
        rows=normalize_account_inventory(p[2][1],p[1][1],41)
        self.assertEqual(len(rows),154)
        self.assertEqual(len(select_probe_ids(rows)),96)
        self.assertEqual(len(set(select_probe_ids(rows))),96)
        self.assertEqual(public_receipt(rows)["totalReturnedSymbols"],154)
    def test_original_account_binding(self):
        p,h=pair_fixture()
        with self.assertRaisesRegex(InventoryIntegrityError,"HISTORIC_BINDING"):
            from_pairs(p,M,"e"*64)
    def test_margin_request_volume_is_original_contract_minimum(self):
        p,h=pair_fixture();p[-1][0].volume[:]=[200]
        with self.assertRaisesRegex(InventoryIntegrityError,"MARGIN_PAIR_BINDING"):
            from_pairs(p,M,h)
    def test_margin_response_volume_must_match_request(self):
        p,h=pair_fixture();p[-1][1].margin[0].volume=200
        with self.assertRaisesRegex(InventoryIntegrityError,"INVENTORY_MARGIN_VOLUME"):
            from_pairs(p,M,h)
    def test_lost_detail_fails_closed(self):
        p,h=pair_fixture();p.pop(5)
        with self.assertRaises(InventoryIntegrityError):from_pairs(p,M,h)
    def test_wrong_contract_id_fails_closed(self):
        p,h=pair_fixture();p[3][1].symbol[0].symbolId=700
        with self.assertRaisesRegex(InventoryIntegrityError,"DETAIL_BINDING"):
            from_pairs(p,M,h)
    def test_wrong_margin_account_fails_closed(self):
        p,h=pair_fixture();p[-1][1].ctidTraderAccountId=42
        with self.assertRaisesRegex(InventoryIntegrityError,"MARGIN_PAIR_BINDING"):
            from_pairs(p,M,h)
    def test_disabled_symbol_stays_unprobed(self):
        p,h=pair_fixture()
        rows=normalize_account_inventory(p[2][1],p[1][1],41)
        self.assertEqual(select_probe_ids(rows),[10,15,11])
        self.assertEqual(select_probe_ids(rows,1),[10])
    def test_non_pepperstone_broker_rejected(self):
        p,h=pair_fixture();p[0][1].trader.brokerName="Other Broker"
        with self.assertRaisesRegex(InventoryIntegrityError,"BROKER_MISMATCH"):
            from_pairs(p,M,h)
    def test_missing_min_volume_kept_as_unknown(self):
        p,h=pair_fixture()
        p[3][1].symbol[0]._present.remove("minVolume")
        p.pop(4)
        out=from_pairs(p,M,h)
        self.assertEqual(out["rows"][0]["contractStatus"],"VOLUME_GRID_UNKNOWN")
        self.assertIsNone(out["rows"][0]["currentMinMarginEur"])
    def test_not_openable_trading_mode(self):
        p,h=pair_fixture();p[3][1].symbol[0].tradingMode=3
        p.pop(4)
        self.assertEqual(from_pairs(p,M,h)["rows"][0]["contractStatus"],
                         "CLOSE_ONLY_OR_DISABLED")
    def test_default_trading_mode_provenance(self):
        p,h=pair_fixture();rows=from_pairs(p,M,h)["rows"]
        self.assertFalse(rows[0]["tradingModeExplicit"])
        self.assertEqual(rows[0]["tradingModeValue"],0)
    def test_incomplete_prefix_does_not_claim_complete(self):
        p,h=pair_fixture()
        with self.assertRaises(InventoryIntegrityError):from_pairs(p[:3],M,h)
    def test_synthetic_success_does_not_certify_economics(self):
        p,h=pair_fixture()
        receipt=public_receipt(from_pairs(p,M,h)["rows"])
        self.assertFalse(receipt["historicalMarginCertified"])
        self.assertFalse(receipt["historicalExecutionCostsCertified"])
        self.assertFalse(receipt["independentNetEdgeEstablished"])
        self.assertFalse(receipt["hard21Established"])
        self.assertEqual(receipt["ordersSubmitted"],0)

if __name__=="__main__":
    unittest.main()
