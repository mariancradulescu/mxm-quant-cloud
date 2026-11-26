import unittest
from .owner_disabled_conversion_history import registered,target


class DisabledConversion(unittest.TestCase):
    def test_disabled_conversion_leg_is_still_eligible_for_history_read(self):
        p,_=registered()
        meta=dict(roster={'USDHKD':dict(id=42,enabled=False)},routes={'HKD':[dict(Symbol='USDHKD')]})
        t=target(meta,p)
        self.assertEqual((t['symbolId'],t['roles'],t['bars']),(42,['CONVERSION'],False))
        self.assertGreater(t['throughExclusive'],t['fromInclusive'])
        with self.assertRaises(Exception):target(dict(meta,routes={}),p)


if __name__=='__main__':unittest.main()
