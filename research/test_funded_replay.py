"""Synthetic invariants only. No genuine NET or credential access is implied."""
import unittest
from decimal import Decimal as D
from .funded_replay import Quote, Contract, Decision, FundedReplay, IncompleteEvidence

T = 1793577600000  # Monday 2026-11-02 00:00 UTC


def q(t, bid, ask=None, sym='EURUSD', credit='1', debit='1'):
    return Quote(T+t,sym,D(str(bid)),D(str(ask if ask is not None else bid)),
                 D(credit),D(debit),'SYNTHETIC_TEST_ONLY')


def contract(*, margin='1',fee='0.1',slip='0.5',mini=1,step=1):
    return Contract(mini,step,100,D(margin),D(fee),D(fee),D(slip),'SYNTHETIC_BROKER_ONLY')


def d(t,pid='a',action='OPEN',sym='EURUSD',side=1,units=1,c=None,latency=1,stop=None,target=None):
    return Decision(T+t,T+t-1,T+t-2,pid,sym,action,latency,side,units,c or contract(),
                    D(str(stop)) if stop is not None else None,
                    D(str(target)) if target is not None else None)


class CausalFundedReplayChecks(unittest.TestCase):
    def setUp(self):
        self.r = FundedReplay(max_staleness_ms=200,financing_schedule_proven=True)

    def test_no_same_quote_fill_and_exact_spread_slippage_commission(self):
        self.r.quote(q(10,100,102))
        self.r.decide(d(10))
        self.assertEqual(len(self.r.open),0)
        self.r.quote(q(11,100,102))
        self.assertEqual(len(self.r.open),1)
        self.r.decide(d(11,action='CLOSE'))
        self.r.quote(q(12,105,107))
        x=self.r.report([T])
        self.assertEqual(x['complete_round_trips'],1)
        trade=self.r.trades[0]
        self.assertEqual(trade['gross_eur'],D('5'))
        self.assertEqual(trade['spread_eur'],D('2'))
        self.assertEqual(trade['slippage_eur'],D('1'))
        self.assertEqual(trade['commissions_eur'],D('0.2'))
        self.assertEqual(trade['net_eur'],D('1.8'))
        self.assertEqual(x['balance_eur'],D('201.8'))
        self.assertEqual(x['weeks_with_21'],0)
        self.assertFalse(x['economic_qualification'])

    def test_stop_trigger_fills_at_next_quote_with_gap_not_stop_level(self):
        self.r.quote(q(10,100,101))
        self.r.decide(d(10,stop=95,target=110,latency=2,c=contract(slip='0')))
        self.r.quote(q(12,100,101))
        self.r.quote(q(13,94,95))  # trigger; cannot close yet
        self.assertEqual(len(self.r.open),1)
        self.r.quote(q(16,80,81))  # gap through stop; observed bid=80
        self.assertEqual(self.r.trades[0]['exit_reason'],'DELAYED_EXIT_AT_OBSERVED_QUOTE')
        self.assertEqual(self.r.trades[0]['net_eur'],D('-21.2'))
        self.assertGreater(self.r.max_sampled_drawdown,D('0.10'))

    def test_portfolio_margin_is_aggregate_and_same_capital(self):
        c=contract(margin='100',fee='0',slip='0')
        self.r.quote(q(10,100,100))
        self.r.decide(d(10,pid='a',c=c))
        self.r.decide(d(10,pid='b',c=c))
        self.r.quote(q(11,100,100))
        self.assertEqual(len(self.r.open),1)
        self.assertEqual(self.r.rejected,[('b','BROKER_MARGIN_OR_FUNDING')])
        self.assertEqual(self.r.report()['initial_eur'],D('200'))

    def test_multisymbol_floating_drawdown_is_marked_not_realized_only(self):
        c=contract(margin='5',fee='0',slip='0')
        self.r.quote(q(10,100,102))
        self.r.quote(q(10,100,102,sym='GBPUSD'))
        self.r.decide(d(10,pid='a',units=5,c=c))
        self.r.decide(d(10,pid='b',sym='GBPUSD',units=5,c=c))
        self.r.quote(q(11,100,102))
        self.r.quote(q(11,100,102,sym='GBPUSD'))
        self.r.quote(q(12,90,92))
        self.r.quote(q(12,90,92,sym='GBPUSD'))
        self.assertEqual(len(self.r.trades),0)
        self.assertGreater(self.r.max_sampled_drawdown,D('0.30'))
        self.assertEqual(self.r.report()['open_positions'],2)
        self.assertEqual(self.r.report()['status'],'INCOMPLETE_EXPOSURE_OR_EVIDENCE')

    def test_stale_concurrent_mark_is_not_silently_assumed_flat(self):
        c=contract(margin='1',fee='0',slip='0')
        self.r.quote(q(10,100,100))
        self.r.decide(d(10,c=c))
        self.r.quote(q(11,100,100))
        with self.assertRaisesRegex(IncompleteEvidence,'MISSING_OR_STALE_POSITION_MARK'):
            self.r.quote(q(250,100,100,sym='GBPUSD'))
        self.assertTrue(self.r.incomplete_marks)

    def test_lookahead_and_backdated_events_rejected(self):
        with self.assertRaisesRegex(IncompleteEvidence,'LOOKAHEAD'):
            self.r.decide(Decision(T+10,T+11,T+5,'a','EURUSD','OPEN',1,1,1,contract()))
        self.r.quote(q(10,100,101))
        with self.assertRaisesRegex(IncompleteEvidence,'NON_CHRONOLOGICAL'):
            self.r.quote(q(9,100,101))
        with self.assertRaisesRegex(IncompleteEvidence,'LOOKAHEAD'):
            self.r.decide(Decision(T+11,T+11,T+12,'a','EURUSD','OPEN',1,1,1,contract()))

    def test_broker_step_and_conversion_evidence(self):
        self.r.quote(q(10,100,101))
        self.r.decide(d(10,units=2,c=contract(mini=1,step=2)))
        self.assertEqual(self.r.rejected,[('a','BROKER_MIN_STEP_MAX')])
        with self.assertRaisesRegex(IncompleteEvidence,'MISSING_OR_INVALID_EVENT'):
            self.r.quote(q(11,100,101,credit='2',debit='1'))

    def test_currency_conversion_cost_is_conserved(self):
        c=contract(margin='1',fee='0',slip='0')
        self.r.quote(q(10,100,100,credit='0.9',debit='1.1'))
        self.r.decide(d(10,c=c))
        self.r.quote(q(11,100,100,credit='0.9',debit='1.1'))
        self.r.decide(d(11,action='CLOSE'))
        self.r.quote(q(12,110,110,credit='0.9',debit='1.1'))
        trade=self.r.trades[0]
        self.assertEqual(trade['gross_eur'],D('10.0'))
        self.assertEqual(trade['conversion_eur'],D('1.0'))
        self.assertEqual(trade['net_eur'],D('9.0'))
        self.assertEqual(self.r.report()['balance_eur'],D('209.0'))

    def test_explicit_carry_and_missing_financing_proof(self):
        c=contract(margin='1',fee='0',slip='0')
        self.r.quote(q(10,100,100))
        self.r.decide(d(10,c=c))
        self.r.quote(q(11,100,100))
        self.r.finance(t=T+11,position_id='a',signed_eur=D('-2'),evidence='SYNTHETIC_SWAP')
        self.r.decide(d(11,action='CLOSE'))
        self.r.quote(q(12,100,100))
        self.assertEqual(self.r.trades[0]['financing_eur'],D('2'))
        self.assertEqual(self.r.trades[0]['net_eur'],D('-2'))
        other=FundedReplay(max_staleness_ms=30,financing_schedule_proven=False)
        self.assertEqual(other.report()['status'],'INCOMPLETE_EXPOSURE_OR_EVIDENCE')

    def test_unclosed_positions_and_zero_weeks_cannot_be_validated(self):
        self.r.quote(q(10,100,100))
        self.r.decide(d(10,c=contract(fee='0',slip='0')))
        self.r.quote(q(11,100,100))
        result=self.r.report([T,T+7*86400000])
        self.assertEqual(result['weekly_closed_count'][T],0)
        self.assertEqual(result['weekly_closed_count'][T+7*86400000],0)
        self.assertEqual(result['status'],'INCOMPLETE_EXPOSURE_OR_EVIDENCE')
        with self.assertRaisesRegex(IncompleteEvidence,'ELIGIBLE_WEEK'):
            self.r.report([T+86400000])


if __name__ == '__main__':
    unittest.main()
