import unittest
from .authentic_temporal_coverage import measure,M5,H,W
class CoverageChecks(unittest.TestCase):
    def cal(self,o):return dict(start=o,developmentEnd=o+W,selectionEnd=o+2*W,end=o+3*W,developmentWeeks=1)
    def rows(self,o,n):return [[o+i*M5-M5,o+i*M5,10,11,9,10,15] for i in range(1,n+1)]
    def test_session_like_gap_never_imputed_and_multiple_windows(self):
        t=1762128000000
        rows=self.rows(t,302)+self.rows(t+3*24*H,302)
        z=measure(dict(X=rows,Y=rows),self.cal(t))
        self.assertEqual(z["sourceBars"],1208)
        self.assertGreater(z["assets"]["X"]["gaps"]["missingM5Slots"],200)
        self.assertGreater(z["assets"]["X"]["label21h"],0)
        self.assertGreater(z["assets"]["X"]["label8h"],z["assets"]["X"]["label21h"])
        self.assertEqual(z["hrc1DevelopmentWeeksWith8Assets"],0)
        self.assertLessEqual(max(w["concurrent"]["21"] for w in z["weekly"]),2)
    def test_too_short_for_21h_but_valid_4h(self):
        t=1762128000000;z=measure(dict(X=self.rows(t,12*14)),self.cal(t))["assets"]["X"]
        self.assertEqual(z["label21h"],0)
        self.assertGreater(z["label4h"],0)
    def test_duplicate_rejected_without_scoring(self):
        t=1762128000000;r=self.rows(t,1)
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            measure(dict(X=r+r),self.cal(t))
if __name__=="__main__":unittest.main()
