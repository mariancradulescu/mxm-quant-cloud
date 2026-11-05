"""F1 model-only independent Decimal oracle against existing C# native funded ledger."""
import json,subprocess,unittest
from decimal import Decimal as D
from datetime import datetime,timezone
from pathlib import Path
from .portfolio_economic_replay import native

class NativeParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=json.loads(Path("research/fixtures/f1_native_events.json").read_text())
        cls.events=cls.f["events"]

    def test_exact_model_events_and_cash(self):
        self.assertEqual(self.f["initialCapitalEur"],300)
        self.assertEqual(self.f["eurTolerance"],"0.000000001")
        self.assertFalse(self.f["independentConfirmation"])
        r=native(self.events,"--native-funded-facts")
        self.assertTrue(r["RestartEveryEventMatched"])
        self.assertTrue(r["DuplicatesIdempotent"])
        self.assertFalse(r["ModelOrAllocationRerun"])
        self.assertEqual(r["OrdersSubmitted"],0)
        self.assertFalse(r["CloudActivated"])
        self.assertEqual(len(r["Receipts"]),len(self.events))
        x=r["Trades"]; s=r["Summary"]; eps=D(self.f["eurTolerance"])
        self.assertEqual([(z["PositionId"],z["CompletesRoundTrip"]) for z in x],
            [("A",False),("A",True),("B",True)])
        self.assertEqual([z["Symbol"] for z in x],["SYNTH_A","SYNTH_A","SYNTH_B"])
        self.assertEqual([D(str(z["Units"])) for z in x],[D(1)]*3)
        # Separate Python decimal math from the literal event prices and costs:
        # A long: ASK+slip entry; BID-slip exit; half of one entry
        # fee per partial fill; each exit fee, negative funding prorated.
        anet=(D("11")-D(".005"))-(D("10.02")+D(".005"))-D(".1")/2-D(".1")-D(".05")/2
        # B short: positive quote P/L credit converted to EUR (0.9),
        # two commissions and the exact positive financing fact.
        bnet=((D("20")-D(".01"))-(D("19.04")+D(".01")))*D(".9")-D(".2")+D(".02")
        self.assertEqual([anet,anet,bnet],[D(".795"),D(".795"),D(".666")])
        for fragment,expected in zip(x,[anet,anet,bnet]):
            self.assertLessEqual(abs(D(str(fragment["NetEur"]))-expected),eps)
        expected_cash=D("300")+anet*2+bnet
        for key,value in (("CashEur",expected_cash),("LiquidationEquityEur",expected_cash),
                          ("FreeMarginEur",expected_cash),("UsedMarginEur",D(0)),
                          ("ClosedNetEur",anet*2+bnet)):
            self.assertLessEqual(abs(D(str(s[key]))-value),eps,key)
        self.assertEqual(expected_cash,D("302.256"))
        self.assertEqual((s["OpenPositions"],s["PendingIntents"],s["CompleteRoundTrips"]),(0,0,2))
        self.assertFalse(s["HistoryEvidenceIncomplete"])
        self.assertFalse(s["GlobalDrawdownCertified"])
        self.assertFalse(s["BrokerStateReconciled"])
        self.assertFalse(s["OrdersEnabled"])
        week=datetime(2026,11,2,tzinfo=timezone.utc).isocalendar()
        self.assertEqual(sum(datetime.fromtimestamp(z["ClosedAt"]/1000,tz=timezone.utc).isocalendar()==week
             for z in x if z["CompletesRoundTrip"]),2)
        self.assertLess(s["CompleteRoundTrips"],21)

    def test_idempotence_conflict_old_clock_and_fx_binding(self):
        first=native(self.events,"--native-funded-facts")
        again=native(self.events+[self.events[-1]],"--native-funded-facts")
        self.assertEqual(first["Summary"],again["Summary"])
        self.assertEqual(first["Trades"],again["Trades"])
        old=dict(self.events[-1],EventId="OLD_MARK",Kind="MARK",
                 At=self.events[0]["At"]+1000,PositionId="",Symbol="",Side=0,
                 Units=0,ExecutionPrice=0,FeeEur=0,Quotes=[])
        bad_duplicate=dict(self.events[-1],FeeEur=.2)
        q=dict(self.events[-1]["Quotes"][0],EurDebit=.5)
        bad_fx=dict(self.events[-1],EventId="BAD_CONVERSION",Kind="MARK",
            At=self.events[-1]["At"]+1000,Quotes=[dict(q,At=self.events[-1]["At"]+1000)])
        for fact in (old,bad_duplicate,bad_fx):
            with self.assertRaises(subprocess.CalledProcessError):
                native(self.events+[fact],"--native-funded-facts")

if __name__=="__main__":unittest.main()
