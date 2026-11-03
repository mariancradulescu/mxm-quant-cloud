"""Read-only event-quote replay for research, never a broker execution adapter.

Every price is an observed bid/ask snapshot; every conversion and tariff is
supplied explicitly by a source-bound caller. Marks are sampled, not global-DD
certificates. No OHLC proxy may be silently promoted to a broker fill.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

D = Decimal


class IncompleteEvidence(ValueError):
    pass


@dataclass(frozen=True)
class Quote:
    t: int  # UTC epoch milliseconds; observed at this time
    symbol: str
    bid: Decimal
    ask: Decimal
    eur_credit_per_quote: Decimal  # EUR received per quote-asset unit
    eur_debit_per_quote: Decimal   # EUR paid per quote-asset unit
    source_hash: str               # source identity, validated upstream

    def check(self):
        if (self.t <= 0 or not self.symbol or not self.source_hash or
            self.bid <= 0 or self.ask < self.bid or
            self.eur_credit_per_quote <= 0 or
            self.eur_debit_per_quote < self.eur_credit_per_quote):
            raise IncompleteEvidence('MISSING_OR_INVALID_EVENT_BID_ASK_FX')

    @property
    def mid(self):
        return (self.bid + self.ask) / 2

    @property
    def eur_reference(self):
        return (self.eur_credit_per_quote + self.eur_debit_per_quote) / 2

    def convert(self, amount_quote):
        return amount_quote * (self.eur_credit_per_quote if amount_quote >= 0 else self.eur_debit_per_quote)


@dataclass(frozen=True)
class Contract:
    min_units: int
    step_units: int
    max_units: int
    margin_eur_per_unit: Decimal
    entry_commission_eur: Decimal
    exit_commission_eur: Decimal
    slippage_price_each_side: Decimal
    broker_terms_source: str

    def check(self):
        if (self.min_units <= 0 or self.step_units <= 0 or
            self.max_units < self.min_units or self.margin_eur_per_unit <= 0 or
            min(self.entry_commission_eur, self.exit_commission_eur,
                self.slippage_price_each_side) < 0 or not self.broker_terms_source):
            raise IncompleteEvidence('BROKER_CONTRACT_COST_OR_MARGIN_MISSING')

    def accepts(self, units):
        return (self.min_units <= units <= self.max_units and
                (units - self.min_units) % self.step_units == 0)


@dataclass(frozen=True)
class Decision:
    t: int
    signal_available_at: int
    calibrated_through: int
    position_id: str
    symbol: str
    action: str             # OPEN or CLOSE only, no broker calls
    latency_ms: int         # positive: never fill on signal quote
    side: int = 0           # +1 long, -1 short for OPEN
    units: int = 0
    contract: Contract | None = None
    stop: Decimal | None = None
    target: Decimal | None = None


@dataclass
class _Position:
    request: Decision
    entry_quote: Quote
    entry_exec: Decimal
    entry_at: int
    financing_paid_eur: Decimal = D('0')  # signed: credits positive

    @property
    def margin(self):
        return self.request.units * self.request.contract.margin_eur_per_unit


class FundedReplay:
    def __init__(self, *, starting_eur=D('200'), max_staleness_ms: int,
                 financing_schedule_proven: bool):
        if starting_eur != D('200') or max_staleness_ms < 0:
            raise IncompleteEvidence('UNAUTHORIZED_CAPITAL_OR_STALENESS')
        self.balance = D('200')
        self.starting_eur = D('200')
        self.max_staleness_ms = max_staleness_ms
        self.financing_schedule_proven = financing_schedule_proven
        self.clock = -1
        self.quotes = {}
        self.pending = []
        self.open = {}
        self.used_ids = set()
        self.trades = []
        self.rejected = []
        self.marks = []
        self.peak = D('200')
        self.max_sampled_drawdown = D('0')
        self.source_ids = set()
        self.incomplete_marks = False

    def _clock(self, t):
        if t < self.clock:
            raise IncompleteEvidence('NON_CHRONOLOGICAL_INPUT')
        self.clock = t

    def _quote_for(self, symbol, t):
        q = self.quotes.get(symbol)
        if q is None or q.t > t or t - q.t > self.max_staleness_ms:
            raise IncompleteEvidence('MISSING_OR_STALE_POSITION_MARK')
        return q

    def _floating(self, p, q):
        c = p.request.contract
        liquidation = q.bid - c.slippage_price_each_side if p.request.side == 1 else q.ask + c.slippage_price_each_side
        amount_quote = p.request.side * p.request.units * (liquidation - p.entry_exec)
        return q.convert(amount_quote) - c.exit_commission_eur

    def equity(self, t):
        return self.balance + sum((self._floating(p, self._quote_for(p.request.symbol, t))
                                   for p in self.open.values()), D('0'))

    def _mark(self, t):
        try:
            equity = self.equity(t)
        except IncompleteEvidence:
            self.incomplete_marks = True
            raise
        self.peak = max(self.peak, equity)
        if self.peak > 0:
            self.max_sampled_drawdown = max(self.max_sampled_drawdown, D('1') - equity / self.peak)
        self.marks.append((t, equity, sum((p.margin for p in self.open.values()), D('0'))))

    def decide(self, d: Decision):
        self._clock(d.t)
        if (not d.position_id or not d.symbol or d.action not in ('OPEN', 'CLOSE') or
            d.latency_ms <= 0 or d.signal_available_at > d.t or
            d.calibrated_through > d.signal_available_at or
            d.signal_available_at < 0 or d.calibrated_through < 0):
            raise IncompleteEvidence('LOOKAHEAD_OR_INVALID_SIGNAL_CLOCK')
        if d.action == 'OPEN':
            if (d.position_id in self.used_ids or d.side not in (-1, 1) or
                d.contract is None or not isinstance(d.units, int)):
                raise IncompleteEvidence('DUPLICATE_OR_INVALID_ENTRY')
            d.contract.check()
            if not d.contract.accepts(d.units):
                self.rejected.append((d.position_id, 'BROKER_MIN_STEP_MAX'))
                return
            self.used_ids.add(d.position_id)
        else:
            if d.position_id not in self.open or self.open[d.position_id].request.symbol != d.symbol:
                self.rejected.append((d.position_id, 'CLOSE_WITHOUT_OPEN_POSITION'))
                return
            if any(x.position_id == d.position_id and x.action == 'CLOSE' for x in self.pending):
                self.rejected.append((d.position_id, 'DUPLICATE_CLOSE_REQUEST'))
                return
        self.pending.append(d)

    def _entry(self, d, q):
        c = d.contract
        fill = q.ask + c.slippage_price_each_side if d.side == 1 else q.bid - c.slippage_price_each_side
        if fill <= 0 or (d.stop is not None and
                         ((d.side == 1 and d.stop >= fill) or (d.side == -1 and d.stop <= fill))) or \
                        (d.target is not None and
                         ((d.side == 1 and d.target <= fill) or (d.side == -1 and d.target >= fill))):
            self.rejected.append((d.position_id, 'INVALID_ENTRY_OR_STOP_GEOMETRY'))
            return
        old_margin = sum((p.margin for p in self.open.values()), D('0'))
        temp = _Position(d, q, fill, q.t)
        try:
            projected = self.equity(q.t) - c.entry_commission_eur + self._floating(temp, q)
        except IncompleteEvidence:
            self.rejected.append((d.position_id, 'STALE_CONCURRENT_PORTFOLIO'))
            self.incomplete_marks = True
            return
        if projected <= 0 or projected <= old_margin + temp.margin:
            self.rejected.append((d.position_id, 'BROKER_MARGIN_OR_FUNDING'))
            return
        self.balance -= c.entry_commission_eur
        self.open[d.position_id] = temp

    def _exit(self, position_id, q, reason, observed_exit_commission_eur=None):
        p = self.open.pop(position_id)
        d = p.request
        c = d.contract
        # Only an entry-time fee estimate is available before opening.
        # True quote-dependent exit fee is supplied after the exit quote appears.
        exit_fee = c.exit_commission_eur if observed_exit_commission_eur is None else observed_exit_commission_eur
        if exit_fee < 0:
            raise IncompleteEvidence('INVALID_OBSERVED_EXIT_COMMISSION')
        out = q.bid - c.slippage_price_each_side if d.side == 1 else q.ask + c.slippage_price_each_side
        actual_quote = d.side * d.units * (out - p.entry_exec)
        raw_mid_quote = d.side * d.units * (q.mid - p.entry_quote.mid)
        gross = raw_mid_quote * q.eur_reference
        spread = d.units * ((p.entry_quote.ask - p.entry_quote.bid) + (q.ask - q.bid)) / 2 * q.eur_reference
        slip = d.units * 2 * c.slippage_price_each_side * q.eur_reference
        converted = q.convert(actual_quote)
        conversion = gross - spread - slip - converted
        if conversion < -D('0.000000001'):
            raise IncompleteEvidence('INCONSISTENT_FX_CONVERSION_COST')
        conversion = max(D('0'), conversion)
        net = converted - c.entry_commission_eur - exit_fee + p.financing_paid_eur
        self.balance += converted - exit_fee
        trade = {'id':position_id, 'symbol':d.symbol, 'opened_at':p.entry_at, 'closed_at':q.t,
                 'side':d.side, 'units':d.units, 'exit_reason':reason,
                 'gross_eur':gross, 'spread_eur':spread, 'slippage_eur':slip,
                 'conversion_eur':conversion, 'commissions_eur':c.entry_commission_eur+exit_fee,
                 'financing_eur':-p.financing_paid_eur, 'net_eur':net}
        expected = gross - spread - slip - conversion - trade['commissions_eur'] - trade['financing_eur']
        if abs(expected-net) > D('0.000000001'):
            raise IncompleteEvidence('ACCOUNTING_NOT_CONSERVED')
        self.trades.append(trade)

    def quote(self, q: Quote, *, observed_exit_commission_eur=None):
        q.check()
        self._clock(q.t)
        previous = self.quotes.get(q.symbol)
        if previous is not None and previous.t >= q.t:
            raise IncompleteEvidence('REPEATED_OR_REVERSED_QUOTE')
        self.quotes[q.symbol] = q
        self.source_ids.add(q.source_hash)
        # Trigger from executable side; close only on a later observed quote.
        for pid,p in list(self.open.items()):
            if p.request.symbol != q.symbol or any(x.position_id == pid and x.action == 'CLOSE' for x in self.pending):
                continue
            hit_stop = p.request.stop is not None and (q.bid <= p.request.stop if p.request.side == 1 else q.ask >= p.request.stop)
            hit_target = p.request.target is not None and (q.bid >= p.request.target if p.request.side == 1 else q.ask <= p.request.target)
            if hit_stop or hit_target:
                self.pending.append(Decision(q.t,q.t,q.t,pid,q.symbol,'CLOSE',p.request.latency_ms))
        rest = []
        for d in self.pending:
            if d.symbol != q.symbol or q.t < d.t + d.latency_ms:
                rest.append(d)
                continue
            if d.action == 'CLOSE':
                if d.position_id in self.open:
                    self._exit(d.position_id,q,'DELAYED_EXIT_AT_OBSERVED_QUOTE',observed_exit_commission_eur)
            else:
                self._entry(d,q)
        self.pending = rest
        self._mark(q.t)

    def finance(self, *, t: int, position_id: str, signed_eur: Decimal, evidence: str):
        self._clock(t)
        if not self.financing_schedule_proven or not evidence or position_id not in self.open:
            raise IncompleteEvidence('FINANCING_SCHEDULE_OR_POSITION_UNPROVEN')
        self._quote_for(self.open[position_id].request.symbol,t)
        self.balance += signed_eur
        self.open[position_id].financing_paid_eur += signed_eur
        self._mark(t)

    def report(self, eligible_monday_utc_ms=()):
        weeks = list(eligible_monday_utc_ms)
        if len(weeks) != len(set(weeks)) or weeks != sorted(weeks):
            raise IncompleteEvidence('DUPLICATE_OR_UNSORTED_ELIGIBLE_WEEK')
        counts = {}
        for w in weeks:
            d = datetime.fromtimestamp(w/1000, timezone.utc)
            if d.weekday() != 0 or d.hour or d.minute or d.second or d.microsecond:
                raise IncompleteEvidence('ELIGIBLE_WEEK_NOT_FULL_UTC_MONDAY')
            counts[w] = sum(w <= t['closed_at'] < w + 7*86400000 for t in self.trades)
        if not self.open and not self.pending and abs(self.starting_eur + sum((t['net_eur'] for t in self.trades),D('0')) - self.balance) > D('0.000000001'):
            raise IncompleteEvidence('FUNDED_ACCOUNTING_NOT_RECONCILED')
        return {'initial_eur':self.starting_eur,'balance_eur':self.balance,
                'closed_net_eur':sum((t['net_eur'] for t in self.trades),D('0')),
                'complete_round_trips':len(self.trades),'rejected':list(self.rejected),
                'eligible_weeks':len(weeks),'weeks_with_21':sum(v>=21 for v in counts.values()),
                'weekly_closed_count':counts,'sampled_max_drawdown':self.max_sampled_drawdown,
                'quoted_equity_marks':len(self.marks),'incomplete_marks':self.incomplete_marks,
                'open_positions':len(self.open),'pending_actions':len(self.pending),
                'financing_schedule_declared':self.financing_schedule_proven,
                'real_fills':False,'global_drawdown_certified':False,
                'independent_confirmation':False,'economic_qualification':False,
                'status':'INCOMPLETE_EXPOSURE_OR_EVIDENCE' if self.open or self.pending or self.incomplete_marks or not self.financing_schedule_proven
                else 'HISTORICAL_EVENT_QUOTE_MODEL_ONLY'}
