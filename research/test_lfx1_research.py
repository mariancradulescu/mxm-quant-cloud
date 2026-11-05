import unittest,json
from datetime import datetime,timezone
from .lfx1_research import candidate_clocks,time_rows,screen,M5,H
class Lfx1Checks(unittest.TestCase):
    def p(self):
        p=json.loads(open("research/lfx1_protocol.json").read())
        return p
    def test_dst_clock_and_no_fitted_or_hindsight_direction(self):
        p=self.p();c=list(candidate_clocks(p["calendar"]))
        dates=[datetime.fromtimestamp(t/1000,timezone.utc) for t in c]
        self.assertIn(16,{v.hour for v in dates})
        self.assertIn(15,{v.hour for v in dates})
        self.assertTrue(all(d.weekday()<5 for d in dates))
        self.assertEqual(len(c),260)
        self.assertTrue(p["locked"] and p["noHRC1OrOtherClosedStudyRerun"])
    def test_future_missing_label_rejects_without_lookahead_fill(self):
        p=self.p()
        origin=list(candidate_clocks(p["calendar"]))[1]
        # All pre-fix M5 sources exist but no future close at all.
        rows=[[origin-j*M5-M5,origin-j*M5,10,11,9,10,15] for j in range(49)]
        bars={s:rows for s in p["source"]["universe"]}
        r,s,v=time_rows(bars,p)
        self.assertEqual(len(r["development"]),0)
        self.assertEqual(sum(x["noFutureLabel"] for x in s.values()),5)
    def test_development_and_selection_not_scored_without_exante_power(self):
        p=self.p();r,s,v=time_rows({x:[] for x in p["source"]["universe"]},p)
        z=screen(p,r,s,v,{})
        self.assertFalse(z["passPreScoring"])
        self.assertIn("DEVELOPMENT_WEEKS_BELOW_PROTOCOL",z["reasons"])
        self.assertIn("SELECTION_WEEKS_BELOW_PROTOCOL",z["reasons"])
        self.assertFalse(p["calendar"]["independentConfirmation"])
if __name__=="__main__":unittest.main()
