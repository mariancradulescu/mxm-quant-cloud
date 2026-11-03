import copy,unittest
from .causal_observation import first_observation


class CausalClockTests(unittest.TestCase):
    def window(self):
        return dict(Nominal=10000,LatencyMs=1000,SearchMs=10000,MaximumAgeMs=2000,
            Route=['X'],Complete=True,Events=[
                dict(At=11000,Symbol='X',Side=0,Price=100),
                dict(At=11000,Symbol='X',Side=1,Price=102),
                dict(At=12000,Symbol='X',Side=0,Price=150)])
    def test_first_not_favorable_future(self):
        w=self.window();r=first_observation(w)
        self.assertEqual(r['At'],11000);self.assertEqual(r['Quotes'][0]['Bid'],100)
        for price in (1,100000):
            w['Events'][-1]['Price']=price
            self.assertEqual(first_observation(w),r)
    def test_prefix_invariance_and_order(self):
        w=self.window();r=first_observation(w)
        w['Events'].reverse();self.assertEqual(first_observation(w),r)
        w['Events']=[e for e in w['Events'] if e['At']<=r['At']]
        self.assertEqual(first_observation(w),r)
    def test_stale_route_and_crossed_quotes(self):
        w=self.window();w['Route'].append('FX')
        self.assertIsNone(first_observation(w)['At'])
        w['Events'] += [dict(At=8000,Symbol='FX',Side=k,Price=10+k) for k in (0,1)]
        self.assertIsNone(first_observation(w)['At'])
        w=self.window();w['Events'][1]['Price']=99;w['Events']=w['Events'][:2]
        self.assertIsNone(first_observation(w)['At'])
    def test_atomic_duplicate_and_incomplete_page(self):
        w=self.window();w['Events'].append(copy.deepcopy(w['Events'][0]))
        self.assertEqual(first_observation(w)['At'],11000)
        w['Events'][-1]['Price']=99
        with self.assertRaises(ValueError):first_observation(w)
        w=self.window();w['Complete']=False
        self.assertEqual(first_observation(w)['Status'],'INCOMPLETE_SOURCE')


if __name__=='__main__':unittest.main()
