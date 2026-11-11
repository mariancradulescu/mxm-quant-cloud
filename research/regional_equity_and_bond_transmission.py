"""Frozen, read-only regional equity and bond transmission study."""
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contract_eur_cost import IncompleteCostEvidence, fee_at_current_contract
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, need
from .guard import require_read_only_request
from .mef1 import latest
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate

START = date(2026, 5, 4)
WEEKS = 26
BAR = 300_000
DAY = 86_400_000
ROUTES = {
    "AAXJ.US": ("ACWI.US", ZoneInfo("America/New_York"), time(9, 30)),
    "EUBund-F": ("EUBobl-F", ZoneInfo("Europe/Berlin"), time(9)),
}


def clock(day, local_time, zone):
    return int(datetime.combine(day, local_time, zone).timestamp() * 1000)


def collect_bars(request, account, sid, zone, source_open):
    bars = {}
    for week in range(WEEKS):
        monday = START + timedelta(weeks=week)
        for first, last in ((0, 2), (3, 4)):
            start = clock(monday + timedelta(days=first), source_open, zone)
            end = clock(monday + timedelta(days=last), time(11, 5), zone)
            response = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                               symbolId=sid, period=e.M5, fromTimestamp=start, toTimestamp=end),
                               m.ProtoOAGetTrendbarsRes)
            need(response.period == e.M5 and not response.hasMore and
                 (not response.HasField("symbolId") or response.symbolId == sid),
                 "REGIONAL_BOND_BAR_RESPONSE")
            for row in decode_bars(response.trendbar, start, end, 5):
                bars[row[0]] = row
    return bars


def move(bars, start, end):
    if any(at not in bars for at in range(start, end, BAR)):
        return None
    return D(bars[end - BAR][5]) / bars[start][2] - 1


def sign(value):
    return (value > 0) - (value < 0)


def sides(target, own, context):
    direction = sign(own - context) if target == "AAXJ.US" else (
        sign(context) if sign(own) * sign(context) == -1 else 0)
    if not direction:
        return {}
    signals = dict(model=direction, own=sign(own), long=1, short=-1, cash=0)
    if target == "AAXJ.US":
        signals["context"] = sign(context)
    return signals


def session_ok(terms, start, end):
    if not terms.scheduleTimeZone:
        return False
    try:
        zone = ZoneInfo(terms.scheduleTimeZone)
    except ZoneInfoNotFoundError:
        return False

    def week_second(at):
        local = datetime.fromtimestamp(at / 1000, zone)
        return ((local.weekday() + 1) % 7) * 86400 + local.hour * 3600 + local.minute * 60 + local.second

    return any(window.startSecond <= week_second(start) <= week_second(end) < window.endSecond
               for window in terms.schedule)


def no_financing(terms, start, end):
    return (terms.HasField("swapTime") and terms.swapPeriod == 24
            and 0 <= terms.swapTime < 1440 and start // DAY == end // DAY
            and not start % DAY <= terms.swapTime * 60_000 <= end % DAY)


def priced_sides(terms, quote, opening, closing, fx_in, fx_out):
    units = D(terms.minVolume) / 100
    if quote not in ("EUR", "USD"):
        raise IncompleteCostEvidence("QUOTE_ASSET_UNSUPPORTED")
    if quote != "EUR" and not terms.HasField("pnlConversionFeeRate"):
        raise IncompleteCostEvidence("PNL_CONVERSION_RATE_UNKNOWN")
    rates_in = {"EUR": D(1)}
    rates_out = {"EUR": D(1)}
    if fx_in and fx_out:
        rates_in["USD"] = 1 / fx_in[0]
        rates_out["USD"] = 1 / fx_out[0]
    if quote not in rates_in:
        raise IncompleteCostEvidence("MISSING_FX")
    base = units * mean(opening) * rates_in[quote]
    outcomes = {0: 0.0}
    components = {}
    for side in (1, -1):
        entry, exit_price = (opening[1], closing[0]) if side == 1 else (opening[0], closing[1])
        commission = sum(D(fee_at_current_contract(terms, quote, units, price, rates)
                         ["oneSideContractCommissionEur"])
                         for price, rates in ((entry, rates_in), (exit_price, rates_out)))
        raw_pnl = units * side * (exit_price - entry)
        exit_rate = 1 / fx_out[1] if quote == "USD" and raw_pnl >= 0 else rates_out[quote]
        pnl = raw_pnl * exit_rate
        conversion = abs(pnl) * D(terms.pnlConversionFeeRate) / 10_000 if quote != "EUR" else D(0)
        outcomes[side] = float(10_000 * (pnl - commission - conversion) / base)
        components[side] = (float(10_000 * commission / base), float(10_000 * conversion / base))
    return outcomes, components


def summary(weeks):
    return {name: mean(mean(row[name] for row in week) for week in weeks)
            for name in weeks[0][0]} if weeks else {}


def score(request, account, target, terms, margin, tape, bars):
    context, zone, source_open = ROUTES[target]
    if not terms or not margin or min(margin) <= 0 or max(margin) > 300:
        return dict(verdict="TARGET_CONTRACT_OR_MARGIN_UNAVAILABLE")
    if not terms.HasField("enableShortSelling") or not terms.enableShortSelling:
        return dict(verdict="SHORT_EXECUTION_NOT_ATTESTED")
    if target not in bars or context not in bars:
        return dict(verdict="PRICE_SOURCE_UNAVAILABLE")
    sid, quote = tape[target]
    fx_sid = tape.get("EURUSD", (None, None))[0]
    halves = []
    for first in (0, 13):
        gross, central, adverse = defaultdict(list), defaultdict(list), defaultdict(list)
        counts = Counter()
        spreads, commissions, conversions = [], [], []
        for week in range(first, first + 13):
            for weekday in range(5):
                day = START + timedelta(weeks=week, days=weekday)
                start = clock(day, source_open, zone)
                decision = clock(day, time(10), zone)
                entry, exit_at = decision + BAR, decision + 13 * BAR
                counts["scheduled"] += 1
                own = move(bars[target], start, decision)
                peer = move(bars[context], start, decision)
                realized = move(bars[target], entry, exit_at)
                if own is None or peer is None or realized is None:
                    counts["missingBars"] += 1
                    continue
                signals = sides(target, own, peer)
                if not signals:
                    continue
                counts["barCompleteSignals"] += 1
                if not session_ok(terms, entry, exit_at) or not no_financing(terms, entry, exit_at):
                    counts["missingSessionOrFinancingEvidence"] += 1
                    continue
                gross[week].append({name: float(realized * 10_000 * side)
                                    for name, side in signals.items()})
                opening = latest(request, account, sid, entry)
                closing = latest(request, account, sid, exit_at)
                if not opening or not closing:
                    counts["missingTargetQuotes"] += 1
                    continue
                fx_in = latest(request, account, fx_sid, entry) if fx_sid else None
                fx_out = latest(request, account, fx_sid, exit_at) if fx_sid else None
                try:
                    outcome, costs = priced_sides(terms, quote, opening, closing, fx_in, fx_out)
                except IncompleteCostEvidence:
                    counts["missingCostOrFx"] += 1
                    continue
                counts["priced"] += 1
                spreads.extend(float(10_000 * (ask - bid) / mean((ask, bid)))
                               for bid, ask in (opening, closing))
                commission, conversion = costs[signals["model"]]
                commissions.append(commission)
                conversions.append(conversion)
                central[week].append({name: outcome[side] - .5 * abs(side)
                                      for name, side in signals.items()})
                adverse[week].append({name: outcome[side] - 2 * abs(side)
                                      for name, side in signals.items()})
        adv = summary(list(adverse.values()))
        covered = (counts["priced"] >= 12 and len(adverse) >= 6
                   and 4 * counts["priced"] >= 3 * counts["barCompleteSignals"])
        passed = covered and all(adv["model"] > value for name, value in adv.items() if name != "model")
        halves.append(dict(counts=dict(counts), pricedWeeks=len(adverse), coverageGate=covered,
                           grossBps=summary(list(gross.values())), centralBps=summary(list(central.values())),
                           adverseBps=adv, passed=passed,
                           medianSampledSpreadBps=median(spreads) if spreads else None,
                           medianModelCommissionBps=median(commissions) if commissions else None,
                           medianModelConversionFeeBps=median(conversions) if conversions else None))
    verdict = "ADMIT_COMMON_REPLAY" if all(h["passed"] for h in halves) else (
        "REJECT_EXACT_RULE" if any(h["coverageGate"] and not h["passed"] for h in halves)
        else "INSUFFICIENT_COVERAGE")
    return dict(halves=halves, verdict=verdict)


def main():
    transport = StdlibCTraderTransport()
    calls = 0
    tape, bars, terms, contracts, margins, results = {}, {}, {}, {}, {}, {}
    protocol = Path("research/regional_equity_and_bond_transmission.md")
    protocol_sha = sha256(protocol.read_bytes()).hexdigest()
    try:
        account = authenticate(transport)

        def request(query, response_type):
            nonlocal calls
            need(calls < 2400, "REGIONAL_BOND_READ_ONLY_BUDGET")
            require_read_only_request(query)
            response = transport.request(query)
            calls += 1
            if (response_type is m.ProtoOAGetTickDataRes and type(response) is m.ProtoOAErrorRes
                    and response.errorCode == "NO_QUOTES"
                    and response.ctidTraderAccountId == account):
                return response_type(ctidTraderAccountId=account, hasMore=False)
            need(type(response) is response_type and response.IsInitialized()
                 and response.ctidTraderAccountId == account, "REGIONAL_BOND_RESPONSE_ACCOUNT_OR_TYPE")
            return response

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                         includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes).trader
        currencies = {asset.assetId: asset.name for asset in assets.asset}
        need("pepperstone" in trader.brokerName.casefold() and currencies.get(trader.depositAssetId) == "EUR",
             "REGIONAL_BOND_PEPPERSTONE_EUR")
        available = {symbol.symbolName.casefold(): symbol for symbol in roster.symbol if symbol.enabled}
        names = ("EURUSD", *ROUTES, *(context for context, _, _ in ROUTES.values()))
        for name in names:
            light = available.get(name.casefold())
            if light is not None:
                tape[name] = (light.symbolId, currencies.get(light.quoteAssetId))

        for target, (context, zone, source_open) in ROUTES.items():
            if target in tape:
                sid, quote = tape[target]
                details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account, symbolId=[sid]),
                                  m.ProtoOASymbolByIdRes)
                need(len(details.symbol) == 1 and details.symbol[0].symbolId == sid,
                     "REGIONAL_BOND_CONTRACT_SYMBOL")
                c = details.symbol[0]
                contracts[target] = c
                terms[target] = contract(target, c, quote, int(datetime.now(UTC).timestamp() * 1000))
                terms[target]["TradingMode"] = c.tradingMode if c.HasField("tradingMode") else None
                terms[target]["ScheduleTimeZone"] = c.scheduleTimeZone
                terms[target]["ScheduleIntervals"] = len(c.schedule)
                if c.HasField("tradingMode") and c.tradingMode == 0 and c.minVolume > 0:
                    response = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                                       symbolId=sid, volume=[c.minVolume]), m.ProtoOAExpectedMarginRes)
                    if response.HasField("moneyDigits") and len(response.margin) == 1:
                        margin = response.margin[0]
                        if margin.volume == c.minVolume:
                            margins[target] = [value / 10**response.moneyDigits
                                               for value in (margin.buyMargin, margin.sellMargin)]
            for name in (target, context):
                if name in tape:
                    bars[name] = collect_bars(request, account, tape[name][0], zone, source_open)
            results[target] = score(request, account, target, contracts.get(target),
                                    margins.get(target), tape, bars)
            print(f"{target}: {results[target]['verdict']}", flush=True)
    finally:
        transport.close()
    receipt = dict(protocolSha256=protocol_sha, readOnlyRequestsAfterAuth=calls,
                   missingEnabledSymbols=sorted(set(names) - tape.keys()),
                   bars={name: dict(count=len(rows), tickVolume=sum(row[6] for row in rows.values()))
                         for name, rows in bars.items()},
                   currentTerms=terms, currentMinimumMarginsEurBuySell=margins, results=results,
                   fundedNetEur=None, independentConfirmation=False, orders=0, cloudActivated=False)
    Path("regional-equity-bond-public.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
