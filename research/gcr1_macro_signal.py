"""GCR1 pre-source pure causal classifier; NO broker collection, finance, or orders.

Each input is a completed M5 close with the *end* timestamp. The adapter
must independently attest the completed bar was available at decision+1.5s.
Neither outcome quotes nor future labels are supplied to this classifier.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite, log
from typing import Sequence

START, END = date(2025, 11, 3), date(2026, 10, 30)
HOURS_UTC = (8, 12, 16)
STEP_MS = 300_000
NUM_CLOSES = 49
DECISION_LATENCY_MS = 1500
ENTRY_AFTER_MS = 300_000
EXIT_AFTER_MS = 14_400_000 + ENTRY_AFTER_MS


@dataclass(frozen=True)
class BarClose:
    end_utc_ms: int
    close: float


@dataclass(frozen=True)
class Decision:
    clock_utc_ms: int
    state: str
    side: int | None
    reason: str
    copper_four_hour_log_return: float | None = None
    gold_four_hour_log_return: float | None = None

    @property
    def entry_clock_utc_ms(self) -> int | None:
        return self.clock_utc_ms + ENTRY_AFTER_MS if self.side is not None else None

    @property
    def exit_clock_utc_ms(self) -> int | None:
        return self.clock_utc_ms + EXIT_AFTER_MS if self.side is not None else None


def scheduled_clocks() -> list[int]:
    """Exactly 780 original proposed slots, regardless of later coverage."""
    slots = []
    day = START
    while day <= END:
        if day.weekday() < 5:
            for h in HOURS_UTC:
                slots.append(int(datetime.combine(day, time(h), tzinfo=timezone.utc).timestamp()*1000))
        day += timedelta(days=1)
    return slots


def _check_clock(clock_ms: int) -> None:
    t = datetime.fromtimestamp(clock_ms/1000, tz=timezone.utc)
    if (not START <= t.date() <= END or t.weekday() >= 5 or t.hour not in HOURS_UTC
            or t.minute or t.second or t.microsecond):
        raise ValueError("not a fixed GCR1 UTC decision boundary")


def _log_return(data: Sequence[BarClose], clock_ms: int) -> tuple[float | None, str]:
    if len(data) != NUM_CLOSES:
        return None, "EXPECTED_49_COMPLETE_M5_CLOSES"
    for i, bar in enumerate(data):
        expected = clock_ms - (NUM_CLOSES - 1 - i)*STEP_MS
        if type(bar.end_utc_ms) is not int or bar.end_utc_ms != expected:
            return None, "MISSING_ASYNCHRONOUS_OR_FUTURE_M5"
        if not isfinite(bar.close) or bar.close <= 0:
            return None, "INVALID_PRICE"
    return log(data[-1].close/data[0].close), "OK"


def decide(copper: Sequence[BarClose], gold: Sequence[BarClose], clock_utc_ms: int) -> Decision:
    """Immutable intent only from aligned causal metal prices, never labels."""
    _check_clock(clock_utc_ms)
    c, cr = _log_return(copper, clock_utc_ms)
    g, gr = _log_return(gold, clock_utc_ms)
    if c is None or g is None:
        return Decision(clock_utc_ms, "DECISION_UNKNOWN", None,
                        "COPPER_" + cr if c is None else "GOLD_" + gr, c, g)
    if c > 0 and g < 0:
        return Decision(clock_utc_ms, "BUY_AUDUSD_GROWTH", 1, "OPPOSITE_METAL_SIGNS", c, g)
    if c < 0 and g > 0:
        return Decision(clock_utc_ms, "SELL_AUDUSD_SAFETY", -1, "OPPOSITE_METAL_SIGNS", c, g)
    return Decision(clock_utc_ms, "ABSTAIN_MACRO_AMBIGUOUS", None,
                    "NONOPPOSITE_METAL_SIGNS", c, g)
