import unittest
from .owner_eur_conditional_source import boundary, matrix_update

class ConditionalSourceChecks(unittest.TestCase):
    def test_timestamp_conflicts_are_explicit(self):
        rows=[[99,100],[100,101],[100,102],[101,103]]
        self.assertEqual(boundary(rows,100,True),dict(at=100,rawPrices=[101,102],conflict=True))
        self.assertEqual(boundary(rows,100,False),dict(at=101,rawPrices=[103],conflict=False))
        self.assertIsNone(boundary(rows,98,True))

    def test_merge_is_clock_deduplicated(self):
        frames={p:None for p in ("M1","M5","M15","M30","H1","H4","D1")}
        frames["M5"]={"closedBars":2,"observedIntervals":[[0,600000]]}
        base=dict(matrix=[dict(symbol="USDJPY",timeframes=frames,warmup={})],
            integratedGapRun="old",window=[600000,1200000])
        report=matrix_update(base,{300000,600000,900000})
        self.assertEqual(report["USDJPY_M5"]["duplicates"],1)
        self.assertEqual(report["USDJPY_M5"]["added"],2)
        self.assertEqual(report["matrix"][0]["timeframes"]["M5"]["closedBars"],4)

if __name__=="__main__":unittest.main()
