"""Synthetic no-source tests for NEW DVI1-A1; no closed original evaluation."""
import unittest
from decimal import Decimal as D
from research.dvi1_action_value import economic_label,score_side,predict,historical_pool,EMBARGO

class Dvi1A1Checks(unittest.TestCase):
    def test_zero_price_move_is_negative_after_crossing(self):
        q=dict(Bid="100",Ask="102",EurCredit="1",EurDebit="1",
               ExitFeePerUnit="0.1")
        for side in (-1,1):
            z=economic_label(q,q,D(".01"),side,D(".5"))
            self.assertLess(z["net"],0)
            self.assertEqual(z["gross"],D(0))
            self.assertAlmostEqual(float(z["friction"]),-float(z["net"]),places=8)

    def sample(self,week,b,side=1,net=D(".20"),exit_at=100):
        return dict(sourceValid=True,week=week,E=1,B=b,exitAt=exit_at,
            labels={"adverse":{1:dict(net=net),-1:dict(net=-net)}})

    def test_exact_embargo_and_state_ablation(self):
        data=[self.sample(w,1,exit_at=1000+w*100) for w in range(5) for _ in range(5)]
        data.append(self.sample(6,1,net=D("999"),exit_at=10000000))
        t=10000000+EMBARGO
        selected=historical_pool(data,t,"FULL",1,1)
        self.assertEqual(len(selected),25)
        self.assertTrue(all(x["exitAt"]<t-EMBARGO for x in selected))
        self.assertEqual(len(historical_pool(data,t,"FULL",1,-1)),0)
        self.assertEqual(len(historical_pool(data,t,"OWN",1,-1)),25)

    def test_positive_conditional_expected_action_with_week_support(self):
        data=[self.sample(w,1,exit_at=100+w*100) for w in range(5) for _ in range(5)]
        p=predict(data,10000000,"FULL",1,1)
        self.assertEqual(p["action"],1)
        self.assertEqual(p["sideForecasts"][1]["n"],25)
        self.assertEqual(p["sideForecasts"][1]["blocks"],5)
        self.assertEqual(predict(data,10000000,"FULL",1,-1)["action"],0)
        self.assertEqual(predict(data,10000000,"CASH",1,1)["action"],0)

    def test_only_three_actions_and_exact_support(self):
        rows=[self.sample(w,1,net=D("0.1"),exit_at=100+w*100) for w in range(3) for _ in range(5)]
        result=predict(rows,10000000,"OWN",1,1)
        self.assertEqual(result["action"],0)
        self.assertEqual(result["reason"],"MATURED_BLOCK_SUPPORT_LOW")
        self.assertIn(predict(rows,10000000,"FULL",0,1)["action"],(-1,0,1))

if __name__=="__main__":unittest.main()
