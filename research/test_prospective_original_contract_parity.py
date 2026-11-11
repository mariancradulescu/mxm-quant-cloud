"""Independent Python Decimal vs existing native C# broker-cost + funded ledger.

Rate/minimum/margin/swap *contract* values are real CMA1/CMA2 original-account
receipts; BID/ASK levels and FX routes are deliberately illustrative (AMD,
NatGas and USDX source-observed spread bps calibrate symmetric example sides).
No historical broker fills, no LIVE order, no re-evaluation of SFX1.
"""
from __future__ import annotations
import json,unittest
from decimal import Decimal as D
from datetime import datetime,timezone
from pathlib import Path
from .portfolio_economic_replay import native
from .contract_eur_cost import IncompleteCostEvidence,fee_at_current_contract
from .test_contract_eur_cost import contract as protobuf_contract

P=Path("research/fixtures/prospective_original_contract_cost_parity_20261108.json")
M=Path("docs/CMA1_AUTHENTIC_CONTRACT_TERMS_20261108.json")
N=Path("docs/CMA2_AUTHENTIC_COST_SURFACE_20261108.json")
def dec(v):return D(str(v))

def python_oracle(x):
    c=x["Contract"];entry=x["Entry"];exit=x["Exit"]
    side=x["Side"];units=dec(entry["Units"])
    assert units==dec(exit["Units"])
    assert c["CommissionType"]==2 and c["MinimumCommissionType"]==1
    def fee(p):
        rate=dec(c["PreciseRateWire"])/D("100000000")
        floor=dec(c["PreciseMinimumWire"])/D("100000000")
        return max(rate*units/dec(c["LotUnits"]),floor)*dec(p["UsdToEur"])
    bid1=dec(entry["Bid"]);ask1=dec(entry["Ask"])
    bid2=dec(exit["Bid"]);ask2=dec(exit["Ask"])
    slippage=dec(entry["SlippagePerSideQuote"])
    entry_price=ask1+slippage if side==1 else bid1-slippage
    exit_price=bid2-slippage if side==1 else ask2+slippage
    quote_pnl=side*units*(exit_price-entry_price)
    ex_credit=dec(exit["QuoteCreditToEur"])*(1-dec(c["PnlConversionFeeBps"])/10000)
    ex_debit=dec(exit["QuoteDebitToEur"])*(1+dec(c["PnlConversionFeeBps"])/10000)
    converted=quote_pnl*(ex_credit if quote_pnl>=0 else ex_debit)
    reference=(ex_credit+ex_debit)/2
    spread=units*((ask1-bid1)+(ask2-bid2))/2*reference
    slip=units*2*slippage*reference
    gross=side*units*((bid2+ask2)/2-(bid1+ask1)/2)*reference
    conversion=gross-spread-slip-converted
    # 24h source-asof contract rollover; the only crossed case is original
    # CMA1 EURJPY Wednesday triple. Future percentage/carry is NOT extrapolated.
    financing=D("0")
    if x["Id"].startswith("CMA1_EURJPY_WEDNESDAY"):
        dt=datetime.fromtimestamp(entry["AtUtcMs"]/1000,tz=timezone.utc)
        end=datetime.fromtimestamp(exit["AtUtcMs"]/1000,tz=timezone.utc)
        assert dt.weekday()==2 and dt.hour==21 and end.hour==22
        assert c["SwapCalculationType"]==0
        pip=D(1)/(D(10)**int(c["PipPosition"]))
        funding_quote=dec(c["LongSwap"])*pip*units*3
        financing=funding_quote*(dec(exit["QuoteCreditToEur"]) if funding_quote>=0
                                 else dec(exit["QuoteDebitToEur"]))
    total=converted-fee(entry)-fee(exit)+financing
    return {"feeEntry":fee(entry),"feeExit":fee(exit),
            "gross":gross,"spread":spread,"slip":slip,
            "conversion":conversion,"financing":financing,"net":total,
            "cash":D(300)+total,"margin":dec(entry["MarginRequirementEur"])}

class AuthenticatedContractNativeMoneyParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads(P.read_text())
        cls.cma=json.loads(M.read_text())
        cls.cmb=json.loads(N.read_text())

    def test_original_broker_receipt_matches_every_fee_and_margin_case(self):
        fx=self.cma["sharedCurrentContract"]
        for x in self.rows:
            c=x["Contract"];symbol=c["Symbol"]
            if symbol in self.cma["instruments"]:
                r=self.cma["instruments"][symbol]
                self.assertEqual(c["PreciseRateWire"],fx["preciseTradingCommissionRateWire"])
                self.assertEqual(c["PreciseMinimumWire"],fx["preciseMinCommissionWire"])
                self.assertEqual(dec(x["Entry"]["MarginRequirementEur"]),dec(r["currentMinMarginEur"]))
                self.assertEqual(dec(c["LongSwap"]),dec(r["swapLongPips"]))
                self.assertEqual(dec(c["ShortSwap"]),dec(r["swapShortPips"]))
            else:
                r=self.cmb["candidates"][symbol]
                self.assertEqual(c["PreciseRateWire"],r["commissionRateWire"])
                self.assertEqual(c["PreciseMinimumWire"],r["minCommissionWire"])
                self.assertEqual(dec(x["Entry"]["MarginRequirementEur"]),dec(r["minMarginEur"]))
                self.assertEqual(dec(c["LongSwap"]),dec(r["swapLong"]))
                self.assertEqual(dec(c["ShortSwap"]),dec(r["swapShort"]))
                spread=abs(dec(x["Entry"]["Ask"])-dec(x["Entry"]["Bid"]))
                mid=(dec(x["Entry"]["Ask"])+dec(x["Entry"]["Bid"]))/2
                spreadbps=spread/mid*10000
                self.assertLess(abs(spreadbps-dec(r["observedSpreadBps"])),D(".000001"))
            self.assertFalse(c["HistoricalTariffContinuityCertified"])
            self.assertIn("ILLUSTRATIVE",x["Provenance"].upper()+
                          ("ILLUSTRATIVE" if "synthetic" in x["Provenance"].lower() else ""))

    def test_all_5_cases_python_decimal_equal_exact_native_funded_ledger(self):
        out=native(self.rows,"--prospective-native-contract-ledger-parity")
        self.assertEqual(out["OrdersSubmitted"],0)
        self.assertFalse(out["CloudActivated"])
        self.assertFalse(out["IndependentConfirmation"])
        receipts=out["NativeContractAndLedgerReceipts"]
        self.assertEqual(len(receipts),len(self.rows))
        for x,c in zip(self.rows,receipts):
            with self.subTest(case=x["Id"]):
                expected=python_oracle(x)
                self.assertEqual(c["ContractSymbol"],x["Contract"]["Symbol"])
                self.assertTrue(c["NativeLedgerRestartExact"])
                self.assertFalse(c["HistoricalContractContinuityCertified"])
                self.assertIsNone(c["ActualBrokerNetEur"])
                self.assertFalse(c["SourcePricesAuthenticBrokerTicks"])
                self.assertEqual(c["OrdersSubmitted"],0)
                self.assertEqual(dec(c["Entry"]["OneSideCommissionEur"]),expected["feeEntry"])
                self.assertEqual(dec(c["Exit"]["OneSideCommissionEur"]),expected["feeExit"])
                self.assertEqual(dec(c["FinancingSignedEur"]),expected["financing"])
                j=c["ClosedFragment"];summary=c["Ledger"]
                for key,src in [
                    ("GrossEur","gross"),("SpreadEur","spread"),
                    ("SlippageEur","slip"),("ConversionEur","conversion"),
                    ("NetEur","net")
                ]:
                    self.assertLessEqual(abs(dec(j[key])-expected[src]),D(".000000001"),key)
                self.assertEqual(dec(j["CommissionsEur"]),
                                 expected["feeEntry"]+expected["feeExit"])
                self.assertEqual(dec(summary["ClosedNetEur"]),expected["net"])
                self.assertEqual(dec(summary["CashEur"]),expected["cash"])
                self.assertEqual(dec(summary["UsedMarginEur"]),0)
                self.assertEqual(summary["CompleteRoundTrips"],1)
                self.assertFalse(summary["BrokerStateReconciled"])
                self.assertFalse(summary["GlobalDrawdownCertified"])
                self.assertFalse(summary["OrdersEnabled"])

    def test_prospective_fee_route_eligibility_matches_python(self):
        from subprocess import CalledProcessError

        template=self.rows[0]
        for kind,rate,floor,usd,eligible in (
            (1,0,0,0,True),
            (2,0,0,0,True),
            (3,0,0,0,True),
            (4,0,0,0,True),
            (1,5000000000,0,0,True),
            (2,300000000,0,0,False),
            (2,0,2000000,0,False),
            (2,0,2000000,D(".9"),True),
        ):
            with self.subTest(kind=kind,rate=rate,floor=floor,usd=usd):
                row=dict(template)
                row["Contract"]=dict(template["Contract"],QuoteAsset="EUR",
                                     CommissionType=kind,PreciseRateWire=rate,
                                     PreciseMinimumWire=floor)
                for clock in ("Entry","Exit"):
                    row[clock]=dict(template[clock],UsdToEur=usd,QuoteCreditToEur=1,
                                    QuoteDebitToEur=1)
                broker=protobuf_contract(kind,rate,floor)
                terms=row["Contract"]
                for field,key in (("minVolume","MinimumUnits"),("stepVolume","VolumeStepUnits"),
                                  ("maxVolume","MaximumUnits"),("lotSize","LotUnits")):
                    setattr(broker,field,int(dec(terms[key])*100))
                rates={"EUR":1}
                if usd:
                    rates["USD"]=usd
                def expected(clock,price_side):
                    mark=row[clock]
                    return dec(fee_at_current_contract(broker,"EUR",mark["Units"],
                                                       mark[price_side],rates)
                               ["oneSideContractCommissionEur"])
                entry_side,exit_side=("Ask","Bid") if row["Side"]>0 else ("Bid","Ask")
                if not eligible:
                    with self.assertRaises(IncompleteCostEvidence):
                        expected("Entry",entry_side)
                    with self.assertRaises(CalledProcessError):
                        native([row],"--prospective-native-contract-ledger-parity")
                    continue
                receipt=native([row],"--prospective-native-contract-ledger-parity")[
                    "NativeContractAndLedgerReceipts"][0]
                self.assertEqual(dec(receipt["Entry"]["OneSideCommissionEur"]),
                                 expected("Entry",entry_side))
                self.assertEqual(dec(receipt["Exit"]["OneSideCommissionEur"]),
                                 expected("Exit",exit_side))

    def test_missing_contract_and_route_never_zero(self):
        bad=dict(self.rows[0])
        bad["Entry"]=dict(bad["Entry"],UsdToEur="0")
        import subprocess
        with self.assertRaises(subprocess.CalledProcessError):
            native([bad],"--prospective-native-contract-ledger-parity")
        bad2=dict(self.rows[0])
        bad2["Contract"]=dict(bad2["Contract"],SwapTimeUtcMinute=None)
        with self.assertRaises(subprocess.CalledProcessError):
            native([bad2],"--prospective-native-contract-ledger-parity")

if __name__=="__main__":unittest.main()
