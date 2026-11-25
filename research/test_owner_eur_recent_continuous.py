import unittest
from unittest.mock import patch

from . import owner_eur_recent_continuous as recent
from .ctrader_proto import OpenApiModelMessages_pb2 as e


class RecentContinuousTests(unittest.TestCase):
    def test_partition_plan_keeps_prior_and_extends_new_and_conversion(self):
        p=dict(Base=["OLD"],New=["NEW"],WarmFrom="2026-10-05",Windows=[
            dict(Id="FIRST",From="2026-10-26",To="2026-11-02"),
            dict(Id="LAST",From="2026-11-23",To="2026-11-25")])
        meta=dict(roster={n:dict(id=i,enabled=True) for i,n in enumerate(("OLD","NEW","ROUTE"),1)},
                  routes={"USD":[dict(Symbol="ROUTE")]},terms={},margin={})
        result=recent.metadata_summary(p,"hash",meta,"run")
        targets=result["partitions"]
        self.assertEqual([(t["symbol"],t["window"]) for t in targets],
                         [("OLD","LAST"),("NEW","FIRST"),("NEW","LAST"),("ROUTE","FIRST"),("ROUTE","LAST")])
        self.assertEqual(targets[1]["barFrom"],recent.utc(p["WarmFrom"]))
        self.assertFalse(targets[-1]["bars"])
        self.assertFalse(result["historicalTermsCertified"])

    def test_mark_coverage_and_missing_data_are_distinguished(self):
        p=dict(PageHours=4,PerSidePageBudget=450)
        day=recent.utc("2026-11-23")
        target=dict(symbol="S",symbolId=1,window="TEST",bars=False,fromInclusive=day,throughExclusive=day+recent.DAY)
        def ticks(request,account,sid,side,lo,hi,budget):
            if lo==day and side==e.ASK:
                return [],[[lo,hi,"PENDING_BUDGET",None,0]]
            return [(lo+14_000,100_000 if side==e.BID else 100_001)],[[lo,hi,"VERIFIED_COMPLETE_PAGE",1,1]]
        class Journal:
            query=None
        with patch.object(recent.rollover,"tick_window",side_effect=ticks),patch("builtins.print"):
            result,_,quotes,_=recent.collect(Journal(),1,p,target,[],keep=True)
        self.assertFalse(result["days"][0]["sides"]["ASK"]["coverage"])
        self.assertFalse(result["historicalTariffContinuityCertified"])
        self.assertEqual(result["monetaryMarks"],len(quotes))
        self.assertTrue(all(q["At"]>=day+4*recent.HOUR for q in quotes))
        self.assertEqual(result["orders"],0)


if __name__=="__main__":
    unittest.main()
