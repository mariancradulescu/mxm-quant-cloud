"""Invariant tests; synthetic fixtures are NEVER economic evidence."""
import math,unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from .tick_volume_net import signals, eligible_weeks, DAY, HOUR
from .funded_replay import FundedReplay,Quote,Contract,Decision

END=int(datetime(2026,11,3,tzinfo=timezone.utc).timestamp()*1000)

def fixture():
    first=END-370*DAY
    out=[]
    price=110000
    for i in range(370*24):
        variation=int(15*math.sin(i*.12)+10*math.cos(i*.05))
        nxt=max(50000,price+variation)
        out.append({"t":first+i*HOUR,"o":price,"h":max(price,nxt)+6,
                    "l":min(price,nxt)-6,"c":nxt,"v":130+(i%11)*7+(i%23)*2})
        price=nxt
    return {"start":first,"end":END,"bars":out}

class TickVolumeInvariants(unittest.TestCase):
    def test_frozen_selection_excludes_future_final20(self):
        b=fixture()
        before=signals(b)
        cutoff=b["start"]+296*DAY
        for row in b["bars"]:
            if row["t"]>cutoff:
                row["c"]=row["o"]*2
        after=signals(b)
        self.assertEqual(before,after)
        self.assertGreater(before["trainingExamples"],100)
        self.assertGreater(before["selectionWindows"],80)
        self.assertGreaterEqual(len(before["eligibleMondayUtcMs"]),8)

    def test_future_bar_not_signal_clock(self):
        b=fixture();r=signals(b)
        self.assertTrue(all(p["exit"]>p["signal"] and p["signal"]<r["selectionEndMs"] for p in r["plan"]))
        self.assertEqual(len(eligible_weeks(b["start"]+222*DAY,b["start"]+296*DAY)),10)

    def test_exit_fee_not_future_in_entry_risk(self):
        r=FundedReplay(starting_eur=D("200"),max_staleness_ms=20000,financing_schedule_proven=True)
        def q(t,bid,ask):
            return Quote(t,"EURUSD",D(bid),D(ask),D("0.9"),D("0.91"),"authenticated-source-fixture")
        con=Contract(1000,1000,3000,D("0.02"),D("0.03"),D("0.03"),D("0.00001"),"broker-terms-fixture")
        r.decide(Decision(100000,100000,90000,"x","EURUSD","OPEN",1000,1,1000,con))
        r.quote(q(102000,"1.1","1.1001"))
        self.assertEqual(len(r.open),1)
        r.decide(Decision(200000,200000,190000,"x","EURUSD","CLOSE",1000))
        r.quote(q(202000,"1.1020","1.1021"),observed_exit_commission_eur=D("0.09"))
        result=r.report([])
        self.assertEqual(result["complete_round_trips"],1)
        self.assertEqual(r.trades[0]["commissions_eur"],D("0.12"))
        self.assertEqual(result["balance_eur"],D("200")+r.trades[0]["net_eur"])

if __name__=="__main__":unittest.main()
