"""Protected coverage diagnosis and preregistered US2000 economic screen."""
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo

from .contract_eur_cost import IncompleteCostEvidence, fee_at_current_contract
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, decode_side, need
from .guard import require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate
from .regional_equity_and_bond_transmission import (
    BAR, START, clock, move, no_financing, priced_sides, session_ok, sign, summary,
)

NY = ZoneInfo("America/New_York")
ZONES = {"AAXJ.US": NY, "EUBund-F": ZoneInfo("Europe/Berlin"), "US2000": NY}
CLOCKS = (time(10, 5), time(11, 5))
DIAGNOSTIC_DAYS = [date(2026, 11, day) for day in (2, 3, 4, 5, 6, 9, 10)]


def paired(request, account, symbol_id, at, counts):
    counts["clocks"] += 1
    points = []
    for side, name in ((e.BID, "Bid"), (e.ASK, "Ask")):
        result = request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                         symbolId=symbol_id, type=side, fromTimestamp=at-60_000,
                         toTimestamp=at), m.ProtoOAGetTickDataRes)
        ticks = decode_side(result.tickData, at-60_000, at) if not result.hasMore else []
        if result.hasMore:
            counts[f"truncated{name}"] += 1
        elif not ticks:
            counts[f"missing{name}Within60s"] += 1
        points.append(ticks[-1] if ticks else None)
    if None in points:
        return None
    bid, ask = (D(point[1]) / 100_000 for point in points)
    if bid > ask:
        counts["crossed"] += 1
        return None
    counts["pairedWithin60s"] += 1
    if at - min(point[0] for point in points) > 20_000:
        counts["olderThan20s"] += 1
        return None
    counts["pairedWithin20s"] += 1
    if bid == ask:
        counts["lockedWithin20s"] += 1
    return bid, ask


def priced(terms, quote, opening, closing, fx, counts):
    if not opening or not closing:
        counts["missingTargetPair"] += 1
        return None
    if quote != "EUR" and not all(fx):
        counts["missingPrincipalFx"] += 1
        return None
    try:
        return priced_sides(terms, quote, opening, closing, *fx)
    except IncompleteCostEvidence as exc:
        counts[str(exc)] += 1
        return None


def diagnose(request, account, ids, contracts, margin):
    quotes = defaultdict(Counter)
    fx_cache = {}

    def fx(at):
        if at not in fx_cache:
            fx_cache[at] = (paired(request, account, ids["EURUSD"][0], at, quotes["EURUSD"])
                            if "EURUSD" in ids else None)
        return fx_cache[at]

    results = {}
    for target, zone in ZONES.items():
        if target not in contracts:
            continue
        sid, quote = ids[target]
        terms = contracts[target]
        counts = Counter()
        coverage = 0
        spreads, fees = [], []
        for day in DIAGNOSTIC_DAYS:
            entry, exit_at = (clock(day, t, zone) for t in CLOCKS)
            opening, closing = (paired(request, account, sid, at, quotes[target])
                                for at in (entry, exit_at))
            fx_pair = [fx(at) for at in (entry, exit_at)]
            units = D(terms.minVolume)/100
            for target_pair, fx_at in zip((opening, closing), fx_pair):
                if not target_pair:
                    continue
                mid = mean(target_pair)
                spreads.append(float((target_pair[1]-target_pair[0])*10_000/mid))
                for label, rates in (("withoutUsd", {"EUR": D(1)}),
                                     ("observedRates", {"EUR": D(1), **({"USD": 1/fx_at[0]} if fx_at else {})})):
                    try:
                        fee = fee_at_current_contract(terms, quote, units, target_pair[1], rates)
                    except IncompleteCostEvidence as exc:
                        counts[f"{label}:{exc}"] += 1
                    else:
                        counts[f"{label}:feePriced"] += 1
                        if label == "observedRates":
                            fees.append(float(fee["oneSideContractCommissionEur"]))
            if not session_ok(terms, entry, exit_at) or not no_financing(terms, entry, exit_at):
                counts["sessionOrFundingUnavailable"] += 1
                continue
            if priced(terms, quote, opening, closing, fx_pair, counts) is not None:
                coverage += 1
        observed = margin.get(target)
        viable = (coverage >= 5 and observed is not None and 0 < min(observed)
                  and max(observed) <= 300 and terms.HasField("enableShortSelling")
                  and terms.enableShortSelling)
        results[target] = dict(completeDays=coverage, counts=dict(counts), canScreen=viable,
                               medianObservedSpreadBps=median(spreads) if spreads else None,
                               medianOneSideMinimumVolumeCommissionEur=median(fees) if fees else None)
    return dict(results=results, quotes={symbol: dict(counts) for symbol, counts in quotes.items()})


def bars_for_week(request, account, sid, monday):
    bars = {}
    for first, last in ((0, 2), (3, 4)):
        start = clock(monday + timedelta(days=first), time(9, 30), NY)
        end = clock(monday + timedelta(days=last), time(16), NY)
        response = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                           symbolId=sid, period=e.M5, fromTimestamp=start, toTimestamp=end),
                           m.ProtoOAGetTrendbarsRes)
        need(response.period == e.M5 and not response.hasMore and
             (not response.HasField("symbolId") or response.symbolId == sid), "SMALL_CAP_BAR_RESPONSE")
        bars.update((row[0], row) for row in decode_bars(response.trendbar, start, end, 5))
    return bars


def screen(request, account, ids, terms):
    sid, quote = ids["US2000"]
    fx_sid = ids["EURUSD"][0]
    halves = []
    for start_week in (0, 13):
        counts, quote_counts = Counter(), defaultdict(Counter)
        gross, central, adverse = defaultdict(list), defaultdict(list), defaultdict(list)
        for week in range(start_week, start_week + 13):
            monday = START + timedelta(weeks=week)
            bars = bars_for_week(request, account, sid, monday)
            counts["bars"] += len(bars)
            counts["tickVolume"] += sum(row[6] for row in bars.values())
            for weekday in range(1, 5):
                counts["scheduled"] += 1
                prior, day = (monday + timedelta(days=d) for d in (weekday-1, weekday))
                close_at = clock(prior, time(16), NY)
                final_hour = move(bars, close_at-12*BAR, close_at)
                first = bars.get(clock(day, time(9, 30), NY))
                entry, exit_at = (clock(day, t, NY) for t in CLOCKS)
                realized = move(bars, entry, exit_at)
                if first is None or final_hour is None or realized is None:
                    counts["missingBars"] += 1
                    continue
                gap = sign(first[2]-bars[close_at-BAR][5])
                if gap * sign(final_hour) != -1:
                    continue
                counts["signals"] += 1
                directions = dict(model=-gap, gapContinuation=gap, long=1, short=-1, cash=0)
                gross[week].append({name: float(10_000*realized*side) for name, side in directions.items()})
                if not session_ok(terms, entry, exit_at) or not no_financing(terms, entry, exit_at):
                    counts["sessionOrFundingUnavailable"] += 1
                    continue
                opening, closing = (paired(request, account, sid, at, quote_counts["US2000"])
                                    for at in (entry, exit_at))
                if not opening or not closing:
                    counts["missingTargetPair"] += 1
                    continue
                fx = [paired(request, account, fx_sid, at, quote_counts["EURUSD"])
                      for at in (entry, exit_at)]
                result = priced(terms, quote, opening, closing, fx, counts)
                if result is None:
                    continue
                counts["priced"] += 1
                outcomes, _ = result
                central[week].append({name: outcomes[side]-.5*abs(side) for name, side in directions.items()})
                adverse[week].append({name: outcomes[side]-2*abs(side) for name, side in directions.items()})
        adv = summary(list(adverse.values()))
        covered = counts["priced"] >= 12 and len(adverse) >= 6 and 4*counts["priced"] >= 3*counts["signals"]
        passed = covered and all(adv["model"] > value for name, value in adv.items() if name != "model")
        halves.append(dict(counts=dict(counts), quoteCounts={s: dict(c) for s, c in quote_counts.items()},
                           pricedWeeks=len(adverse), coverageGate=covered, passed=passed,
                           grossBps=summary(list(gross.values())), centralBps=summary(list(central.values())),
                           adverseBps=adv))
    verdict = "ADMIT_COMMON_REPLAY" if all(half["passed"] for half in halves) else (
        "REJECT_EXACT_RULE" if any(half["coverageGate"] and not half["passed"] for half in halves)
        else "INSUFFICIENT_COVERAGE")
    return dict(verdict=verdict, halves=halves)


def main():
    transport = StdlibCTraderTransport()
    calls = 0
    ids, contracts, terms, margins = {}, {}, {}, {}
    try:
        account = authenticate(transport)

        def request(query, expected):
            nonlocal calls
            need(calls < 1200, "ECONOMIC_COVERAGE_REQUEST_BUDGET")
            require_read_only_request(query)
            response = transport.request(query)
            calls += 1
            if (expected is m.ProtoOAGetTickDataRes and type(response) is m.ProtoOAErrorRes
                    and response.errorCode == "NO_QUOTES" and response.ctidTraderAccountId == account):
                return expected(ctidTraderAccountId=account, hasMore=False)
            need(type(response) is expected and response.IsInitialized()
                 and response.ctidTraderAccountId == account, "ECONOMIC_COVERAGE_RESPONSE_BINDING")
            return response

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account), m.ProtoOASymbolsListRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes).trader
        currencies = {asset.assetId: asset.name for asset in assets.asset}
        need("pepperstone" in trader.brokerName.casefold() and currencies.get(trader.depositAssetId) == "EUR",
             "ECONOMIC_COVERAGE_PEPPERSTONE_EUR")
        available = {symbol.symbolName.casefold(): symbol for symbol in roster.symbol if symbol.enabled}
        for name in ("EURUSD", *ZONES):
            light = available.get(name.casefold())
            if light is None:
                continue
            ids[name] = (light.symbolId, currencies.get(light.quoteAssetId))
            if name == "EURUSD":
                continue
            details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account, symbolId=[light.symbolId]),
                              m.ProtoOASymbolByIdRes)
            need(len(details.symbol) == 1 and details.symbol[0].symbolId == light.symbolId,
                 "ECONOMIC_COVERAGE_CONTRACT_SYMBOL")
            c = details.symbol[0]
            contracts[name] = c
            terms[name] = contract(name, c, ids[name][1], int(datetime.now(UTC).timestamp()*1000))
            terms[name]["ExplicitFields"] = [field for field in (
                "tradingMode", "enableShortSelling", "preciseTradingCommissionRate", "preciseMinCommission",
                "commissionType", "minCommissionType", "minCommissionAsset", "pnlConversionFeeRate",
                "swapTime", "swapPeriod") if c.HasField(field)]
            if c.HasField("tradingMode") and c.tradingMode == 0 and c.minVolume > 0:
                result = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                                 symbolId=light.symbolId, volume=[c.minVolume]), m.ProtoOAExpectedMarginRes)
                if result.HasField("moneyDigits") and len(result.margin) == 1 and result.margin[0].volume == c.minVolume:
                    row = result.margin[0]
                    margins[name] = [value/10**result.moneyDigits for value in (row.buyMargin, row.sellMargin)]
        diagnosis = diagnose(request, account, ids, contracts, margins)
        us2000 = diagnosis["results"].get("US2000", {})
        print(f"US2000 diagnostic complete days: {us2000.get('completeDays', 0)}", flush=True)
        predictive = (screen(request, account, ids, contracts["US2000"]) if us2000.get("canScreen")
                      else dict(verdict="SOURCE_GATE_NOT_MET", halves=[]))
    finally:
        transport.close()
    protocol = Path("research/economic_coverage_and_small_cap_open.md")
    receipt = dict(protocolSha256=sha256(protocol.read_bytes()).hexdigest(), readOnlyRequestsAfterAuth=calls,
                   currentTerms=terms, currentMinimumMarginsEurBuySell=margins, diagnosis=diagnosis,
                   predictive=predictive, fundedNetEur=None, independentConfirmation=False, orders=0,
                   cloudActivated=False)
    Path("economic-coverage-small-cap-public.json").write_text(json.dumps(receipt, indent=2, allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
