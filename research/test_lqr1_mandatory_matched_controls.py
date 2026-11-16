"""Synthetic tests for exactly prespecified same-intent control, not old return scoring."""
import unittest
from .lqr1_mandatory_matched_controls import matched_source_only

def frames():
    rows=[]
    for i in range(80):
        book={}
        for sym in ("USDCHF","EURGBP"):
            if sym=="USDCHF" and i<21:
                feature={"state":"SIDE_SPECIFIC_SIGNAL","side":1,"own":-1}
            elif sym=="EURGBP" and 21<=i<42:
                feature={"state":"SIDE_SPECIFIC_SIGNAL","side":-1,"own":-1}
            else:
                feature={"state":"ABSTAIN_SIMULTANEOUS","side":0,"own":1}
            book[sym]={"feature":feature,
                        "entry":None,"exit":None,
                        "unusedSourceOutcomeFutureMustNotBeRead":i}
        rows.append({"t":i,"symbols":book})
    return rows

class MatchedControl(unittest.TestCase):
    def test_42_original_intents_21_diverge_and_no_outcome_use(self):
        rows=frames()
        new,meta=matched_source_only(rows,"ownMomentum")
        self.assertEqual(meta["originalLqr1Intents"],42)
        self.assertEqual(meta["originalSideDiffersFromMomentum"],21)
        self.assertEqual(new[0]["symbols"]["USDCHF"]["feature"]["side"],-1)
        self.assertEqual(new[25]["symbols"]["EURGBP"]["feature"]["side"],-1)
        self.assertEqual(new[43]["symbols"]["USDCHF"]["feature"]["side"],0)
        self.assertEqual(rows[0]["symbols"]["USDCHF"]["feature"]["side"],1)
        for x in rows:x["symbols"]["USDCHF"]["unusedSourceOutcomeFutureMustNotBeRead"]=99999999
        later=matched_source_only(rows,"ownMomentum")[0]
        self.assertEqual([z["symbols"]["USDCHF"]["feature"] for z in new],
                         [z["symbols"]["USDCHF"]["feature"] for z in later])

    def test_fixed_controls_only_exact_primary_observation_mask(self):
        rows=frames()
        for policy,sign in (("long",1),("short",-1),("cash",0)):
            new,meta=matched_source_only(rows,policy)
            self.assertEqual(meta["originalLqr1Intents"],42)
            self.assertEqual(new[0]["symbols"]["USDCHF"]["feature"]["side"],sign)
            self.assertEqual(new[25]["symbols"]["EURGBP"]["feature"]["side"],sign)
            self.assertEqual(new[63]["symbols"]["EURGBP"]["feature"]["side"],0)
        with self.assertRaises(Exception):
            matched_source_only(rows,"unknownControl")

if __name__=="__main__":
    unittest.main()
