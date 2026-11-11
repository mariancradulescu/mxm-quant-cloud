"""CMR1: fixed US2000 cash-close anchored reversion; read-only Pepperstone evidence."""
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from .contract_eur_cost import IncompleteCostEvidence
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, need
from .guard import require_read_only_request
from .mef1 import latest
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate
from .regional_equity_and_bond_transmission import no_financing, priced_sides, session_ok

NY = ZoneInfo("America/New_York")
START = date(2026, 5, 4)
BAR = 300_000
MAX_REQUESTS = 1800


def at(day, hour, minute=0):
    return int(datetime.combine(day, time(hour, minute), NY).timestamp() * 1000)


def get_bars(request, account, symbol_id):
    """Two bounded original-account M5 requests a week; no missing bar interpolation."""
    bars = {}
    for week in range(26):
        monday = START + timedelta(weeks=week)
        for first, last in ((0, 2), (3, 4)):
            lo = at(monday + timedelta(days=first), 9, 30)
            hi = at(monday + timedelta(days=last), 16)
            response = request(
                m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=symbol_id,
                                         period=e.M5, fromTimestamp=lo, toTimestamp=hi),
                m.ProtoOAGetTrendbarsRes)
            need(response.period == e.M5 and not response.hasMore
                 and (not response.HasField("symbolId") or response.symbolId == symbol_id),
                 "CMR1_M5_SOURCE_RESPONSE")
            for row in decode_bars(response.trendbar, lo, hi, 5):
                bars[row[0]] = row
    return bars


def complete_session(bars, day):
    clock = at(day, 9, 30)
    rows = [bars.get(clock + BAR * i) for i in range(72)]
    if any(row is None for row in rows):
        return None
    volume = sum(row[6] for row in rows)
    if volume <= 0:
        return None
    # Completed candles only; this is NOT underlying-exchange VWAP.
    anchor = sum(D(row[6]) * (D(row[3]) + D(row[4]) + D(row[5])) / 3
                 for row in rows) / D(volume)
    if anchor <= 0:
        return None
    deviation = D(10_000) * (D(rows[-1][5]) / anchor - 1)
    earlier = D(10_000) * (D(rows[-4][5]) / anchor - 1)
    if abs(deviation) < 20 or abs(earlier) - abs(deviation) < 3:
        return None
    model = -1 if deviation > 0 else 1
    lookback = D(rows[-1][5]) / D(rows[-13][2]) - 1
    momentum = (lookback > 0) - (lookback < 0)
    return dict(model=model, momentum=int(momentum), deviationBps=float(deviation),
                reversionBps=float(abs(earlier) - abs(deviation)))


def score(request, account, sid, quote, terms, margin, bars, eurusd):
    if not terms or not margin or min(margin) <= 0 or max(margin) > 300:
        return dict(verdict="CURRENT_CONTRACT_OR_EUR300_MARGIN_UNATTESTED")
    if not terms.HasField("enableShortSelling") or not terms.enableShortSelling:
        return dict(verdict="SHORT_EXECUTION_UNATTESTED")
    if quote != "USD" or eurusd is None:
        return dict(verdict="USD_QUOTE_OR_EUR_CONVERSION_MISSING")
    halves = []
    for first_week in (0, 13):
        counts = Counter()
        net = defaultdict(list)
        spreads, deviations = [], []
        for week in range(first_week, first_week + 13):
            monday = START + timedelta(weeks=week)
            for weekday in range(5):
                day = monday + timedelta(days=weekday)
                counts["scheduledDays"] += 1
                signal = complete_session(bars, day)
                if signal is None:
                    counts["notSignaledOrIncompleteBars"] += 1
                    continue
                counts["completedBarSignals"] += 1
                entry, exit_at = at(day, 15, 35), at(day, 15, 55)
                if not session_ok(terms, entry, exit_at) or not no_financing(terms, entry, exit_at):
                    counts["sessionOrFinancingUnknown"] += 1
                    continue
                opening = latest(request, account, sid, entry)
                closing = latest(request, account, sid, exit_at)
                fx_in = latest(request, account, eurusd, entry)
                fx_out = latest(request, account, eurusd, exit_at)
                if not opening or not closing or not fx_in or not fx_out:
                    counts["missingFreshTargetOrFxSides"] += 1
                    continue
                try:
                    signed, components = priced_sides(
                        terms, quote, opening, closing, fx_in, fx_out)
                except (IncompleteCostEvidence, ZeroDivisionError):
                    counts["missingCommissionOrConversion"] += 1
                    continue
                counts["priced"] += 1
                deviations.append(signal["deviationBps"])
                spreads.append(float(D(10_000) * D(opening[1] - opening[0])
                                     / (D(opening[0] + opening[1]) / 2)))
                sides = dict(model=signal["model"], long=1, short=-1,
                             momentum=signal["momentum"], cash=0)
                net[week].append({
                    "central": {name: signed[side] - (0.5 if side else 0)
                                for name, side in sides.items()},
                    "adverse": {name: signed[side] - (2.0 if side else 0)
                                for name, side in sides.items()},
                })
        def aggregate(kind):
            if not net:
                return {}
            return {name: mean(mean(ob[kind][name] for ob in week) for week in net.values())
                    for name in ("model", "long", "short", "momentum", "cash")}
        adverse = aggregate("adverse")
        covered = (counts["priced"] >= 10 and len(net) >= 6
                   and counts["priced"] * 4 >= 3 * counts["completedBarSignals"])
        passed_gate = covered and all(
            adverse["model"] > adverse[name] for name in
            ("long", "short", "momentum", "cash"))
        halves.append(dict(firstWeek=first_week, counts=dict(counts), activeWeeks=len(net),
                           centralBps=aggregate("central"), adverseBps=adverse,
                           meanSignalDeviationBps=mean(deviations) if deviations else None,
                           meanObservedEntrySpreadBps=mean(spreads) if spreads else None,
                           coverageGate=covered, passed=bool(passed_gate)))
    verdict = ("ADMIT_PROSPECTIVE_NATIVE_FINANCED_REPLAY"
               if all(h["passed"] for h in halves)
               else "REJECT_EXACT_RULE"
               if any(h["coverageGate"] and not h["passed"] for h in halves)
               else "INSUFFICIENT_COMPARABLE_SIGNALS")
    return dict(verdict=verdict, halves=halves)


def main():
    source = Path("research/cmr1.md")
    transport = StdlibCTraderTransport()
    calls = 0
    bars = {}
    receipt = dict(hypothesis="CMR1_US2000_CASH_CLOSE_SESSION_TICK_ANCHOR",
                   protocolSha256=sha256(source.read_bytes()).hexdigest(),
                   sourceCalendar="2026-05-04/2026-10-30; globally exposed development",
                   scenario="CURRENT_TERMS_MODELLED_NOT_HISTORICAL_FILLS",
                   fundedNetEur=None, independentConfirmation=False,
                   orders=0, cloudActivated=False)
    try:
        account = authenticate(transport)
        def request(query, response_type):
            nonlocal calls
            need(calls < MAX_REQUESTS, "CMR1_READONLY_BUDGET")
            require_read_only_request(query)
            response = transport.request(query)
            calls += 1
            if (response_type is m.ProtoOAGetTickDataRes
                    and type(response) is m.ProtoOAErrorRes
                    and response.errorCode == "NO_QUOTES"
                    and response.ctidTraderAccountId == account):
                return response_type(ctidTraderAccountId=account, hasMore=False)
            need(type(response) is response_type and response.IsInitialized()
                 and response.ctidTraderAccountId == account,
                 "CMR1_ACCOUNT_RESPONSE_MISMATCH")
            return response

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                         includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes).trader
        currencies = {a.assetId: a.name for a in assets.asset}
        need("pepperstone" in trader.brokerName.lower()
             and currencies.get(trader.depositAssetId) == "EUR",
             "CMR1_ORIGINAL_PEPPERSTONE_EUR_ACCOUNT")
        enabled = {s.symbolName.casefold(): s for s in roster.symbol if s.enabled}
        target, fx = enabled.get("us2000"), enabled.get("eurusd")
        if target is None or fx is None:
            receipt["result"] = dict(verdict="REQUIRED_SYMBOL_NOT_ENABLED")
        else:
            details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                              symbolId=[target.symbolId]), m.ProtoOASymbolByIdRes)
            need(len(details.symbol) == 1
                 and details.symbol[0].symbolId == target.symbolId,
                 "CMR1_ORIGINAL_SYMBOL_CONTRACT")
            symbol = details.symbol[0]
            terms = contract("US2000", symbol, currencies.get(target.quoteAssetId),
                             int(datetime.now(UTC).timestamp() * 1000))
            margin = None
            if (symbol.minVolume > 0 and symbol.HasField("tradingMode")
                    and symbol.tradingMode == 0):
                reply = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                                symbolId=target.symbolId, volume=[symbol.minVolume]),
                                m.ProtoOAExpectedMarginRes)
                if reply.HasField("moneyDigits") and len(reply.margin) == 1:
                    record = reply.margin[0]
                    if record.volume == symbol.minVolume:
                        margin = [v / 10 ** reply.moneyDigits
                                  for v in (record.buyMargin, record.sellMargin)]
            if margin and 0 < min(margin) and max(margin) <= 300:
                bars = get_bars(request, account, target.symbolId)
            result = score(request, account, target.symbolId,
                           currencies.get(target.quoteAssetId), symbol,
                           margin, bars, fx.symbolId)
            receipt.update(currentContract=terms, minimumMarginEurBuySell=margin,
                           completedM5SourceBars=len(bars), result=result)
    finally:
        transport.close()
    receipt["readOnlyRequestsAfterAuth"] = calls
    Path("cmr1-public-receipt.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print("CMR1:", receipt["result"]["verdict"], "read-only requests:", calls, flush=True)


if __name__ == "__main__":
    main()
