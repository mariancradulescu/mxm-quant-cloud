import unittest
from .owner_estate_recovery import merge_series
class EstateRecovery(unittest.TestCase):
    def test_identical_overlap_and_conflict(self):
        a=dict(OpenAt=0,CloseAt=60,Open='1',High='2',Low='1',Close='2',TickVolume=5)
        self.assertEqual(len(merge_series([a],[dict(a,Open='1.0')])[0]),1)
        self.assertEqual(merge_series([a],[dict(a,Close='1')])[1]['ConflictingOpens'],1)
        self.assertEqual(merge_series([a],[dict(a,OpenAt=30,CloseAt=90)])[1]['OverlappingOpens'],2)
