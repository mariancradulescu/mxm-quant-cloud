"""QSR1: spread-shock recovery with original two-sided historical quotes."""
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
from itertools import groupby
from math import comb
import json
import os
from pathlib import Path
from statistics import mean

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_side, need
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .portfolio_economic_replay import fee, native, net_quote
from .portfolio_economic_source import contract_snapshot

SYMBOLS = ("EURUSD", "GBPUSD")
START = int(datetime(2026, 6, 22, tzinfo=timezone.utc).timestamp()) * 1000
DAY = 86400000
WEEKS = 20
HOURS = (8, 14)
SCHEMA = "mxm-frozen-observed-facts-v1"


def asof(tape, at):
    quote = {}
    for side, (times, prices) in tape.items():
        i = bisect_right(times, at) - 1
        if i < 0 or at - times[i] > 2000:
            return None
        quote[side] = prices[i]
        quote[side + "At"] = times[i]
    return quote if 0 < quote["bid"] < quote["ask"] else None


def feature(tape, at):
    base, shock, now = (asof(tape, at - lag) for lag in (20000, 5000, 0))
    if not all((base, shock, now)):
        return None
    midpoint2 = lambda q: q["bid"] + q["ask"]
    width = lambda q: q["ask"] - q["bid"]
    displacement = midpoint2(shock) - midpoint2(base)
    if displacement == 0 or width(now) > width(base):
        return (0, False)
    side = -1 if displacement > 0 else 1
    one_sided = (shock["bid"] == base["bid"]) != (shock["ask"] == base["ask"])
    return side, one_sided and width(shock) >= 2 * width(base)


def scenario(entry, exit_, side, units):
    px_in, px_out = (entry["Ask"], exit_["Bid"]) if side > 0 else (entry["Bid"], exit_["Ask"])
    amount = side * (px_out - px_in) * units
    spread = ((entry["Ask"] - entry["Bid"]) + (exit_["Ask"] - exit_["Bid"])) * units / 2
    costs = fee(entry, units) + fee(exit_, units)
    gross = side * (exit_["Bid"] + exit_["Ask"] - entry["Bid"] - entry["Ask"]) * units / 2
    return dict(gross=net_quote(exit_, gross), central=net_quote(exit_, amount) - costs,
                adverse=net_quote(exit_, amount - spread) - costs)


def collect():
    transport = StdlibCTraderTransport()
    count = 0
    try:
        account = authenticate(transport)

        def request(q, response):
            nonlocal count
            need(count < 5000, "QSR1_REQUEST_BUDGET")
            require_read_only_request(q)
            r = transport.request(q)
            count += 1
            need(type(r) is response and r.IsInitialized() and r.ctidTraderAccountId == account,
                 "QSR1_ORIGINAL_RESPONSE_BINDING")
            return r

        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes).trader
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        currencies = {a.assetId: a.name for a in assets.asset}
        need("pepperstone" in trader.brokerName.casefold()
             and currencies.get(trader.depositAssetId) == "EUR", "QSR1_BROKER_EUR")
        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account, includeArchivedSymbols=False),
                         m.ProtoOASymbolsListRes)
        ids = {s.symbolName: s.symbolId for s in roster.symbol
               if s.enabled and currencies.get(s.quoteAssetId) == "USD"}
        need(all(s in ids for s in SYMBOLS), "QSR1_ORIGINAL_SYMBOLS")
        terms, margins = {}, {}
        for symbol in SYMBOLS:
            sid = ids[symbol]
            d = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account, symbolId=[sid]),
                        m.ProtoOASymbolByIdRes)
            need(len(d.symbol) == 1 and d.symbol[0].symbolId == sid, "QSR1_CONTRACT_ID")
            c = d.symbol[0]
            need(c.minVolume > 0 and c.stepVolume > 0 and c.maxVolume >= c.minVolume
                 and c.tradingMode == 0, "QSR1_CONTRACT_COVERAGE")
            r = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account, symbolId=sid,
                                                  volume=[c.minVolume]), m.ProtoOAExpectedMarginRes)
            need(r.HasField("moneyDigits") and len(r.margin) == 1 and r.margin[0].volume == c.minVolume,
                 "QSR1_MARGIN_COVERAGE")
            margins[symbol] = D(max(r.margin[0].buyMargin, r.margin[0].sellMargin)) / 10 ** r.moneyDigits
            terms[symbol] = dict(contract=contract_snapshot(c), quoteAsset="USD")

        def ticks(symbol, side, start, stop):
            points = []
            for _ in range(24):
                q = m.ProtoOAGetTickDataReq(ctidTraderAccountId=account, symbolId=ids[symbol], type=side,
                                           fromTimestamp=start, toTimestamp=stop)
                r = request(q, m.ProtoOAGetTickDataRes)
                if not r.HasField("hasMore"):
                    return None
                page = decode_side(r.tickData, start, stop)
                if not r.hasMore:
                    points.extend(page)
                    break
                if not page or page[0][0] >= stop:
                    return None
                # Re-request the oldest millisecond so a split millisecond
                # cannot be silently treated as a complete page.
                stop = page[0][0]
                points.extend(row for row in page if row[0] > stop)
            else:
                return None
            collapsed = [(t, list(rows)[-1][1])
                         for t, rows in groupby(sorted(points, key=lambda x: x[0]), key=lambda x: x[0])]
            return (tuple(t for t, _ in collapsed), tuple(p for _, p in collapsed)), len(points)

        snapshots, decisions = {}, []
        counts = {s: [Counter(), Counter()] for s in SYMBOLS}
        for day in range(WEEKS * 7):
            if day % 7 >= 5:
                continue
            week = day // 7
            phase = int(week >= 10)
            for hour in HOURS:
                start = START + day * DAY + hour * 3600000
                tapes = {}
                for symbol in SYMBOLS:
                    c = counts[symbol][phase]
                    c["windows"] += 1
                    sides = {name: ticks(symbol, kind, start - 22000, start + 602000)
                             for name, kind in (("bid", e.BID), ("ask", e.ASK))}
                    if any(x is None for x in sides.values()):
                        c["incompleteWindows"] += 1
                        continue
                    c["tickEvents"] += sum(x[1] for x in sides.values())
                    tapes[symbol] = {name: x[0] for name, x in sides.items()}
                for offset in range(0, 600000, 30000):
                    at = start + offset
                    for symbol in SYMBOLS:
                        c = counts[symbol][phase]
                        c["scheduled"] += 1
                        if symbol not in tapes:
                            c["missingFeature"] += 1
                            continue
                        result = feature(tapes[symbol], at)
                        if result is None:
                            c["missingFeature"] += 1
                            continue
                        side, selected = result
                        if not side:
                            continue
                        c["eligibleDirection"] += 1
                        c["signals"] += int(selected)
                        a, b = at + 1000, at + 31000
                        contract = terms[symbol]["contract"]
                        swap = contract["swapTime"]
                        if swap is None or not 0 <= swap < 1440 or contract["swapPeriod"] != 24:
                            c["missingRolloverTerms"] += 1
                            continue
                        if a % DAY <= swap * 60000 <= b % DAY:
                            c["rolloverExcluded"] += 1
                            continue
                        route = {symbol, "EURUSD"}
                        if not route <= tapes.keys():
                            c["missingQuoteRoute"] += 1
                            continue
                        pair = [{s: asof(tapes[s], t) for s in sorted(route)} for t in (a, b)]
                        if any(q is None for point in pair for q in point.values()):
                            c["missingQuoteRoute"] += 1
                            continue
                        for t, point in zip((a, b), pair):
                            snapshots.setdefault(str(t), dict(at=t, quotes={}))["quotes"].update(point)
                        decisions.append((symbol, week, hour, side, selected, a, b))
        return terms, margins, snapshots, decisions, counts, count
    finally:
        transport.close()


def aggregate(rows, key):
    result = []
    for strata in rows.values():
        chosen, matched = [], []
        for records in strata.values():
            pool = [float(record[key]) for _, record in records]
            selected = [float(record[key]) for flag, record in records if flag]
            chosen.extend(selected)
            matched.extend([mean(pool)] * len(selected))
        if chosen:
            result.append((mean(chosen), mean(matched)))
    if not result:
        return None
    a, b = zip(*result)
    delta = [x - y for x, y in result]

    def sign_test(data):
        signs = [x for x in data if x != 0]
        n, positive = len(signs), sum(x > 0 for x in signs)
        return min(1, 8 * sum(comb(n, j) for j in range(positive, n + 1)) / 2 ** n)

    return dict(eurPerMinimumVolumeRoundTrip=mean(a), matchedEur=mean(b), incrementalEur=mean(delta),
                activeWeeks=len(result), adjustedPositiveWeekP=sign_test(a),
                adjustedIncrementalWeekP=sign_test(delta))


def main():
    terms, margins, snapshots, decisions, counts, requests = collect()
    valued = native(dict(schema=SCHEMA, readOnly=True, depositCurrency="EUR",
                         symbols=terms, snapshots=snapshots), "--value-portfolio-source")["Snapshots"]
    data = {s: [defaultdict(lambda: defaultdict(list)) for _ in range(2)] for s in SYMBOLS}
    for symbol, week, hour, side, selected, a, b in decisions:
        phase = int(week >= 10)
        c = counts[symbol][phase]
        entry, exit_ = (valued[str(t)]["Quotes"].get(symbol) for t in (a, b))
        if entry is None or exit_ is None:
            c["missingNativeValuation"] += 1
            continue
        c["valuedLabels"] += 1
        c["valuedSignals"] += int(selected)
        units = D(terms[symbol]["contract"]["minVolume"]) / 100
        data[symbol][phase][week][hour, side].append((selected, scenario(entry, exit_, side, units)))
    results = {}
    for symbol in SYMBOLS:
        phases = {}
        for i, name in enumerate(("selection", "exposedAudit")):
            phases[name] = dict(counts=dict(counts[symbol][i]),
                                metrics={key: aggregate(data[symbol][i], key)
                                         for key in ("gross", "central", "adverse")})
        candidate = 0 < margins[symbol] < 300
        for phase in phases.values():
            adverse = phase["metrics"]["adverse"]
            candidate &= bool(phase["counts"].get("valuedSignals", 0) >= 30
                              and adverse and adverse["activeWeeks"] >= 8
                              and adverse["adjustedPositiveWeekP"] <= .05
                              and adverse["adjustedIncrementalWeekP"] <= .05
                              and adverse["eurPerMinimumVolumeRoundTrip"] > 0
                              and adverse["incrementalEur"] > 0)
        results[symbol] = dict(minimumMarginEur=float(margins[symbol]),
                               minimumUnits=terms[symbol]["contract"]["minVolume"] / 100,
                               phases=phases, candidate=candidate)
    report = dict(study="QSR1", runId=int(os.environ.get("GITHUB_RUN_ID", "0")),
                  protocolSha256=sha256(Path("research/QSR1.md").read_bytes()).hexdigest(),
                  originalPepperstoneLiveAccountAuthenticated=True, postAuthenticationReadOnlyRequests=requests,
                  usedM5Bars=0, usedDom=False, initialCapitalEur=300, fundedClosures=0,
                  portfolioNetCentralEur=None, portfolioNetAdverseEur=None, hard21=None,
                  floatingDrawdown=None, independentConfirmation=False, ordersSubmitted=0,
                  cloudActivated=False, results=results)
    output = json.dumps(report, indent=2, allow_nan=False) + "\n"
    Path("qsr1-public.json").write_text(output)
    print(output)


if __name__ == "__main__":
    main()
