"""Read-only, prospectively frozen London closing-fix development screen."""
from base64 import b64encode
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo

from .contract_eur_cost import IncompleteCostEvidence
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_transport import StdlibCTraderTransport
from .custody import seal_new
from .custody_new import checked_public
from .decode import need
from .guard import require_read_only_request
from .mef1 import latest
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate
from .regional_equity_and_bond_transmission import no_financing, priced_sides, session_ok

SYMBOLS = ("AUDUSD", "GBPUSD", "NZDUSD")
FX = "EURUSD"
WINDOWS = {"fix": time(16), "control": time(15, 15)}
ZONE = ZoneInfo("Europe/London")
START = date(2026, 5, 4)
MAX_REQUESTS = 5220
PROTOCOL = Path("research/london_fix_residual.md")


def bps_spread(quote):
    return 10_000 * (quote[1] - quote[0]) / mean(quote)


def signal(before, after):
    returns = {name: 10_000 * (mean(after[name]) / mean(before[name]) - 1)
               for name in SYMBOLS}
    common = median(returns.values())
    residuals = sorted((abs(value - common), name, value - common)
                       for name, value in returns.items())
    size, name, residual = residuals[-1]
    if size == residuals[-2][0]:
        return None
    if size <= 2 * max(bps_spread(before[name]), bps_spread(after[name])):
        return None
    return name, -1 if residual > 0 else 1


def price_window(quote, terms, center, counts):
    start = center - 151_000
    decision = center + 150_000
    entry, exit_at = center + 180_000, center + 1_080_000
    counts["scheduled"] += 1
    if not all(session_ok(terms[name], start - 20_000, decision)
               for name in SYMBOLS):
        counts["sessionUnknown"] += 1
        return None
    before = {name: quote(name, start) for name in SYMBOLS}
    after = {name: quote(name, decision) for name in SYMBOLS}
    if None in before.values() or None in after.values():
        counts["missingFeatureQuotes"] += 1
        return None
    pick = signal(before, after)
    if pick is None:
        counts["abstained"] += 1
        return (0.0, None)
    name, direction = pick
    counts["signals"] += 1
    counts[f"signals_{name}"] += 1
    if not session_ok(terms[name], entry - 20_000, exit_at) or not no_financing(
            terms[name], entry, exit_at):
        counts["executionSessionOrFinancingUnknown"] += 1
        return None
    opening, closing = quote(name, entry), quote(name, exit_at)
    fx_in, fx_out = quote(FX, entry), quote(FX, exit_at)
    if None in (opening, closing, fx_in, fx_out):
        counts["missingExecutionOrFxQuotes"] += 1
        return None
    try:
        net, components = priced_sides(terms[name], "USD", opening, closing, fx_in, fx_out)
    except IncompleteCostEvidence:
        counts["missingContractCost"] += 1
        return None
    counts["priced"] += 1
    counts[f"priced_{name}"] += 1
    comparators = {"model": direction, "long": 1, "short": -1, "cash": 0}
    cases = {case: {key: net[side] - cost * abs(side) for key, side in comparators.items()}
             for case, cost in (("central", 0.5), ("adverse", 2.0))}
    fees, conversion = components[direction]
    cases["costs"] = {"entrySpreadBps": float(bps_spread(opening)),
                      "exitSpreadBps": float(bps_spread(closing)),
                      "roundTripCommissionBps": fees, "conversionFeeBps": conversion}
    return cases["adverse"]["model"], cases


def weekly_rows(weeks, key):
    return {name: mean(mean(row[key][name] for row in group) for group in weeks.values())
            for name in next(iter(weeks.values()))[0][key]} if weeks else {}


def evaluate(quote, terms):
    halves = []
    for first in (0, 13):
        counts = {name: Counter() for name in WINDOWS}
        trades = {name: defaultdict(list) for name in WINDOWS}
        paired = defaultdict(list)
        for week in range(first, first + 13):
            for weekday in range(5):
                day = START + timedelta(weeks=week, days=weekday)
                values = {}
                for label, hour in WINDOWS.items():
                    center = int(datetime.combine(day, hour, ZONE).timestamp() * 1000)
                    outcome = price_window(quote, terms, center, counts[label])
                    if outcome is None:
                        continue
                    policy_net, trade = outcome
                    values[label] = policy_net
                    if trade is not None:
                        trades[label][week].append(trade)
                if len(values) == len(WINDOWS):
                    paired[week].append(values["fix"] - values["control"])
        matched_days = sum(map(len, paired.values()))
        difference = mean(map(mean, paired.values())) if paired else None
        summaries = {label: dict(counts=dict(counts[label]), pricedWeeks=len(trades[label]),
                                 **{key: weekly_rows(trades[label], key)
                                    for key in ("central", "adverse", "costs")})
                     for label in WINDOWS}
        covered = matched_days >= 50 and len(paired) >= 10 and all(
            counts[label]["priced"] >= 20 and len(trades[label]) >= 8
            and 4 * counts[label]["priced"] >= 3 * counts[label]["signals"]
            for label in WINDOWS)
        adverse = summaries["fix"]["adverse"]
        passed = covered and difference > 0 and all(
            adverse["model"] > adverse[key] for key in ("long", "short", "cash"))
        halves.append(dict(firstWeekIndex=first, windows=summaries,
                           matchedDays=matched_days, matchedWeeks=len(paired),
                           matchedAdversePolicyDifferenceBps=difference,
                           coverageGate=covered, passed=passed))
    if all(half["passed"] for half in halves):
        verdict = "SUPPORTS_PROSPECTIVE_NATIVE_FUNDED_REPLAY_ONLY"
    elif any(half["coverageGate"] and not half["passed"] for half in halves):
        verdict = "REJECT_EXACT_RULE"
    else:
        verdict = "INSUFFICIENT_COMPARABLE_EVIDENCE"
    return dict(verdict=verdict, halves=halves)


def load_contracts(request, account, receipt):
    roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                     includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
    trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes).trader
    assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
    currencies = {a.assetId: a.name for a in assets.asset}
    need("pepperstone" in trader.brokerName.casefold()
         and currencies.get(trader.depositAssetId) == "EUR", "LFR1_ORIGINAL_BROKER_OR_CURRENCY")
    enabled = {item.symbolName.upper(): item for item in roster.symbol if item.enabled}
    tape = {name: enabled[name].symbolId for name in (*SYMBOLS, FX)
            if name in enabled and currencies.get(enabled[name].quoteAssetId) == "USD"}
    if len(tape) != len(SYMBOLS) + 1:
        return tape, {}
    details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                      symbolId=[tape[name] for name in SYMBOLS]), m.ProtoOASymbolByIdRes)
    by_id = {item.symbolId: item for item in details.symbol}
    terms = {}
    observed = int(datetime.now(UTC).timestamp() * 1000)
    for name in SYMBOLS:
        item = by_id.get(tape[name])
        if item is None:
            continue
        current = contract(name, item, "USD", observed)
        receipt[name] = dict(terms=current, minimumMarginEur=None)
        if (not item.HasField("tradingMode") or item.tradingMode != 0
                or not item.HasField("enableShortSelling") or not item.enableShortSelling
                or not 0 < item.minVolume <= item.maxVolume or item.stepVolume <= 0):
            continue
        expected = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                           symbolId=item.symbolId, volume=[item.minVolume]),
                           m.ProtoOAExpectedMarginRes)
        if not expected.HasField("moneyDigits") or len(expected.margin) != 1:
            continue
        row = expected.margin[0]
        if row.volume != item.minVolume:
            continue
        margins = [value / 10 ** expected.moneyDigits for value in (row.buyMargin, row.sellMargin)]
        receipt[name]["minimumMarginEur"] = margins
        if 0 < min(margins) and max(margins) <= 300:
            terms[name] = item
    return tape, terms


def main():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    protocol_hash = sha256(PROTOCOL.read_bytes()).hexdigest()
    wire = []
    receipt = dict(study="LFR1", runId=run, protocolSha256=protocol_hash,
                   calendar="2026-05-04/2026-10-30_EXPOSED_DEVELOPMENT",
                   originalTerms={}, fundedNetEur=None, independentConfirmation=False,
                   brokerFillsCertified=False, orders=0, cloudActivated=False)
    transport = StdlibCTraderTransport()
    try:
        account = authenticate(transport)

        def request(query, reply_type):
            need(len(wire) < MAX_REQUESTS, "LFR1_READ_ONLY_BUDGET")
            require_read_only_request(query)
            reply = transport.request(query)
            wire.append([type(query).__name__, b64encode(query.SerializeToString()).decode(),
                         type(reply).__name__, b64encode(reply.SerializePartialToString()).decode()])
            if (reply_type is m.ProtoOAGetTickDataRes and type(reply) is m.ProtoOAErrorRes
                    and reply.errorCode == "NO_QUOTES" and reply.ctidTraderAccountId == account):
                return reply_type(ctidTraderAccountId=account, hasMore=False)
            need(type(reply) is reply_type and reply.IsInitialized()
                 and reply.ctidTraderAccountId == account, "LFR1_INVALID_SOURCE_RESPONSE")
            return reply

        tape, terms = load_contracts(request, account, receipt["originalTerms"])
        if len(terms) == len(SYMBOLS):
            receipt["result"] = evaluate(
                lambda name, clock: latest(request, account, tape[name], clock), terms)
        else:
            receipt["result"] = dict(verdict="CURRENT_BASKET_INELIGIBLE_OR_UNATTESTED")
    finally:
        transport.close()
        if wire:
            source = json.dumps(dict(study="LFR1", runId=run, protocolSha256=protocol_hash,
                                     wire=wire), separators=(",", ":")).encode()
            encrypted = seal_new(source, recipient, run)
            Path("lfr1-source.v2.enc").write_bytes(encrypted)
            receipt["ciphertextSha256"] = sha256(encrypted).hexdigest()
    receipt["readOnlyRequestsAfterAuth"] = len(wire)
    Path("lfr1-public.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print("LFR1", receipt["result"]["verdict"], len(wire), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("LFR1_FAILED_DETAIL_WITHHELD") from None
