"""CSI1 original source research causality and missingness regression tests."""
import unittest
from datetime import date,timedelta
from .csi1_company_gap_original_eur import (
    M5,stamp,causal_event,exit_decision,weekday_previous,summarize)


def row(day,hh,mm,op,cl):
    at=stamp(day,hh,mm)
    return [at,at+M5,op,max(op,cl),min(op,cl),cl]


def make_records(day):
    """Four older same weekday references with deliberately smaller innovations."""
    records={}
    for k in range(5):
        current=day-timedelta(weeks=k)
        prior=weekday_previous(current)
        move=9 if k==0 else 0.2
        records[prior.isoformat()]={"bars":{
            "AMD.US":[row(prior,15,50,100,100)],
            "INTC.US":[row(prior,15,50,100,100)],
            "NAS100":[row(prior,15,50,100,100)]}}
        records[current.isoformat()]={"bars":{
            "AMD.US":[row(current,9,30,100+move,101+move)]
                     +[row(current,9,35+i*5,101+move,102+move)
                       if 35+i*5<60 else row(current,10,(35+i*5)-60,101+move,102+move)
                       for i in range(8)],
            "INTC.US":[row(current,9,30,100,100.1)]
                      +[row(current,9,35+i*5,100.1,100.2)
                        if 35+i*5<60 else row(current,10,(35+i*5)-60,100.1,100.2)
                        for i in range(8)],
            "NAS100":[row(current,9,30,100,100.1)]
                     +[row(current,9,35+i*5,100.1,100.2)
                       if 35+i*5<60 else row(current,10,(35+i*5)-60,100.1,100.2)
                       for i in range(8)]}}
    return records


class Csi1Tests(unittest.TestCase):
    def test_monday_previous_is_friday(self):
        self.assertEqual(weekday_previous(date(2026,1,5)),date(2026,1,2))

    def test_unusual_company_gap_with_peer_and_index_agreement(self):
        day=date(2026,1,5)
        rows=make_records(day)
        x=causal_event(day,rows)
        self.assertEqual(x["state"],"CAUSAL_FIRM_SURPRISE")
        self.assertEqual(x["side"],1)
        self.assertEqual(exit_decision(day,rows,x["side"]),"11:00")

    def test_future_outcome_not_used_to_choose_entry(self):
        day=date(2026,1,5)
        rows=make_records(day)
        earlier=causal_event(day,rows)
        rows[day.isoformat()]["bars"]["AMD.US"].append(
            row(day,10,20,10,200))
        self.assertEqual(causal_event(day,rows),earlier)

    def test_invalidation_only_when_relative_repricing_opposes(self):
        day=date(2026,1,5);rows=make_records(day)
        rows[day.isoformat()]["bars"]["AMD.US"][8]=row(day,10,10,110,100)
        self.assertEqual(exit_decision(day,rows,1),"10:20")

    def test_missing_middle_monitor_candle_is_unknown(self):
        day=date(2026,1,5);rows=make_records(day)
        rows[day.isoformat()]["bars"]["INTC.US"].pop(4)
        self.assertIsNone(exit_decision(day,rows,1))

    def test_unknown_reference_not_disguised_as_zero(self):
        day=date(2026,1,5);rows=make_records(day)
        rows.pop((day-timedelta(weeks=3)).isoformat())
        self.assertEqual(causal_event(day,rows)["state"],
                         "UNKNOWN_FOUR_WEEK_REFERENCE")

    def test_only_priced_intents_contribute_conditional_eur(self):
        template={k:0.0 for k in
                  ("primary","sameSideFixed","ownMomentum","long",
                   "short","oppositeFalsifier","cash")}
        template["primary"]=-1.2
        rows=[{"state":"UNKNOWN_BID_ASK_AMD","week":0,"side":1},
              {"state":"MATCHED_ORIGINAL_QUOTES_CURRENT_CONTRACT_EUR",
               "week":1,"side":-1,
               "money":{"central":dict(template),"adverse":dict(template)}}]
        z=summarize(rows)
        self.assertEqual(z["calendarDays"],2)
        self.assertEqual(z["pricedEvents"],1)
        self.assertEqual(z["adverseCurrentContractConditionalNetEur"]["primary"],-1.2)


if __name__=="__main__":
    unittest.main()
