import unittest
from .owner_eur_recent_funded import merge_bars,merge_quotes


class RecentFundedTests(unittest.TestCase):
    def test_exact_bar_dedup_and_conflict(self):
        bar=dict(OpenAt=1,CloseAt=2,Open="1.00",High="2",Low="1",Close="2",TickVolume=5)
        same=dict(bar,Open="1")
        bad=dict(bar,Close="1.5")
        merged,count=merge_bars([bar],[same])
        self.assertEqual(len(merged),1)
        self.assertEqual(count,0)
        self.assertEqual(merge_bars([bar],[bad,same]),([],1))

    def test_recovered_funding_not_invented(self):
        absent=dict(At=1,RequestedCoverage=False)
        exact=dict(At=1,RequestedCoverage=True,Bid="1",Ask="2",BidAt=1,AskAt=1)
        self.assertEqual(merge_quotes([absent],[exact],True),([exact],0))
        self.assertEqual(merge_quotes([exact],[absent],True),([exact],0))
        self.assertEqual(merge_quotes([exact],[dict(exact,Bid="0.9")],True),([],1))


if __name__=="__main__":
    unittest.main()
