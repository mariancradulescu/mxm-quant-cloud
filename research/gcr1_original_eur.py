"""GCR1 original Pepperstone EUR protected read-only source + ex-ante A1 finance.

RUN ONLY via OWNER-gated protected workflow on main; no trading methods,
OAuth refresh, new account, new external service, Cloud, or order submission.
Original request/response bytes and decoded tape are sealed before any EUR
score. Missing future quote cannot remove predecision intent.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, decode_side
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody import seal_new
from .custody_new import checked_public
from .gcr1_macro_signal import scheduled_clocks, STEP_MS, ENTRY_AFTER_MS
from .gcr1_eur_model import intents, evaluate

SYMBOLS = ("Copper", "XAUUSD", "AUDUSD", "EURUSD")
BAR_SYMBOLS = ("Copper", "XAUUSD", "AUDUSD")
FX_SYMBOLS = ("AUDUSD", "EURUSD")
M5 = STEP_MS
MAX_CALLS = 5200
MAX_QUOTE_AGE_MS = 20000
ORIGINAL = Path("gcr1-original-protected.v2.enc")
PUBLIC = Path("gcr1-original-public-eur.json")


def ms(day, hour, minute=0):
    return int(datetime(day.year, day.month, day.day, hour, minute,
                        tzinfo=timezone.utc).timestamp() * 1000)


def quote_clocks(day):
    return [ms(day, h, 5) for h in (8, 12, 16, 20)]


def choose_asof(rows, clock):
    eligible = [(int(at), int(raw)) for at, raw in rows
                if at <= clock and 0 <= clock-at <= MAX_QUOTE_AGE_MS and raw > 0]
    if not eligible:
        return None
    at, raw = max(eligible, key=lambda item: item[0])
    return {"at": at, "raw": raw}


def main():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    raw_protobuf = []
    source = {}
    metadata = {"contracts": {}, "sourceStates": []}
    calls = 0
    t = StdlibCTraderTransport()

    def req(q, klass, allow_no_quotes=False):
        nonlocal calls
        if calls >= MAX_CALLS:
            raise RuntimeError("GCR1_PRESOURCE_REQUEST_CEILING_REACHED")
        require_read_only_request(q)
        reply = t.request(q)
        calls += 1
        if (not reply.IsInitialized() or
                int(reply.ctidTraderAccountId) != int(q.ctidTraderAccountId)
                or int(q.ctidTraderAccountId) != int(account)):
            raise RuntimeError("GCR1_WRONG_ORIGINAL_ACCOUNT_RESPONSE")
        raw_protobuf.append({
            "requestType": type(q).__name__,
            "responseType": type(reply).__name__,
            "request": base64.b64encode(q.SerializeToString()).decode("ascii"),
            "response": base64.b64encode(reply.SerializeToString()).decode("ascii"),
        })
        if (allow_no_quotes and type(reply) is m.ProtoOAErrorRes and
                reply.errorCode == "NO_QUOTES"):
            return None
        if type(reply) is not klass:
            raise RuntimeError("GCR1_UNEXPECTED_SOURCE_RESPONSE_TYPE")
        return reply

    def observed_quote(symbol, clock, ids):
        if symbol not in ids:
            return None
        result = {"hasMore": False}
        for name, side in (("bid", e.BID), ("ask", e.ASK)):
            z = req(m.ProtoOAGetTickDataReq(
                ctidTraderAccountId=account, symbolId=ids[symbol],
                type=side, fromTimestamp=clock-60000, toTimestamp=clock
            ), m.ProtoOAGetTickDataRes, True)
            if z is None:
                result[name] = None
            elif z.hasMore:
                result["hasMore"] = True
                result[name] = None
            else:
                rows = decode_side(z.tickData, clock-60000, clock)
                result[name] = choose_asof(rows, clock)
        return result

    try:
        account = authenticate(t)
        trader = req(m.ProtoOATraderReq(
            ctidTraderAccountId=account), m.ProtoOATraderRes)
        assets_reply = req(m.ProtoOAAssetListReq(
            ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        assets = {a.assetId: a.name for a in assets_reply.asset}
        if (not trader.trader.HasField("brokerName") or
                "pepperstone" not in trader.trader.brokerName.lower() or
                assets.get(trader.trader.depositAssetId) != "EUR"):
            raise RuntimeError("GCR1_NOT_ORIGINAL_PEPPERSTONE_EUR_ACCOUNT")
        roster = req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        listing = {name: [x for x in roster.symbol
                          if x.symbolName == name and x.enabled]
                   for name in SYMBOLS}
        for name, matches in listing.items():
            if len(matches) > 1:
                raise RuntimeError("GCR1_DUPLICATE_ACCOUNT_SYMBOL_NAME")
        ids = {name: listing[name][0].symbolId for name in SYMBOLS
               if len(listing[name]) == 1}
        metadata["enabledSymbols"] = sorted(ids)
        contracts = {}
        for name in SYMBOLS:
            if name not in ids:
                metadata["sourceStates"].append(name + "_NOT_ENABLED")
                continue
            z = req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account, symbolId=[ids[name]]),
                m.ProtoOASymbolByIdRes)
            if len(z.symbol) != 1 or z.symbol[0].symbolId != ids[name]:
                raise RuntimeError("GCR1_WRONG_ORIGINAL_CONTRACT")
            c = z.symbol[0]
            if not c.HasField("tradingMode") or c.tradingMode != e.ENABLED:
                metadata["sourceStates"].append(name + "_NOT_CURRENTLY_TRADE_ENABLED")
            if assets.get(listing[name][0].quoteAssetId) != "USD":
                metadata["sourceStates"].append(name + "_QUOTE_CURRENCY_NOT_USD")
            contracts[name] = c

        # The original predictor may be economically invalid if one of the
        # context markets is not currently USD-quoted; do not invent ratios.
        market_currencies_ok = all(
            name in ids and assets.get(listing[name][0].quoteAssetId) == "USD"
            for name in SYMBOLS
        ) and (
            "EURUSD" in ids and
            assets.get(listing["EURUSD"][0].baseAssetId) == "EUR"
        )
        if not market_currencies_ok:
            metadata["sourceStates"].append("CURRENCY_ROUTE_OR_MARKET_INELIGIBLE")

        margin = None
        target = contracts.get("AUDUSD")
        if target is not None and target.HasField("minVolume") and target.minVolume > 0:
            z = req(m.ProtoOAExpectedMarginReq(
                ctidTraderAccountId=account, symbolId=ids["AUDUSD"],
                volume=[target.minVolume]), m.ProtoOAExpectedMarginRes)
            if z.HasField("moneyDigits") and len(z.margin) == 1 and (
                    z.margin[0].volume == target.minVolume):
                div = D(10) ** z.moneyDigits
                margin = {
                    "buy": str(D(z.margin[0].buyMargin) / div),
                    "sell": str(D(z.margin[0].sellMargin) / div),
                }
        metadata["targetMinimumMarginEur"] = margin
        clock_list = scheduled_clocks()
        assert len(clock_list) == 780
        days = [date(2025, 11, 3) + timedelta(days=i)
                for i in range(362) if
                (date(2025, 11, 3) + timedelta(days=i)).weekday() < 5]
        if len(days) != 260 or days[-1] != date(2026, 10, 30):
            raise RuntimeError("GCR1_FIXED_260_DAY_CALENDAR_CHANGED")
        for d_index, day in enumerate(days):
            key = day.isoformat()
            day_bars = {}
            for name in BAR_SYMBOLS:
                if name not in ids:
                    day_bars[name] = {}
                    continue
                st = ms(day, 3, 50)
                en = ms(day, 20, 10) if name == "AUDUSD" else ms(day, 16, 10)
                z = req(m.ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account, symbolId=ids[name],
                    period=e.M5, fromTimestamp=st, toTimestamp=en
                ), m.ProtoOAGetTrendbarsRes, True)
                if z is None or z.hasMore:
                    day_bars[name] = {}
                elif z.period != e.M5 or (
                        z.HasField("symbolId") and z.symbolId != ids[name]):
                    raise RuntimeError("GCR1_M5_SYMBOL_OR_PERIOD_MISMATCH")
                else:
                    decoded = decode_bars(z.trendbar, st-2*M5, en+2*M5, 5)
                    day_bars[name] = {str(row[1]): int(row[5]) for row in decoded
                                      if row[1] <= en}
            events = {}
            for hr in (8, 12, 16):
                at = ms(day, hr)
                events[str(at)] = intents(day_bars, at)
            # source and *prequote* immutable intents now exist on all dates.
            # Quote reads below target every fixed timestamp irrespective of
            # event state, morning signal, future completeness or return.
            quotes = {name: {} for name in FX_SYMBOLS}
            for name in FX_SYMBOLS:
                for clock in quote_clocks(day):
                    quotes[name][str(clock)] = observed_quote(name, clock, ids)
            source[key] = {"bars": day_bars, "intents": events, "quotes": quotes}
            if d_index % 30 == 29:
                print("GCR1_ORIGINAL_SOURCE_ONLY_DAYS", d_index+1, "OF", len(days),
                      "READONLY_REQUESTS", calls, flush=True)
    finally:
        t.close()

    packed = {
        "schema": "MXM_GCR1_A1_ORIGINAL_EXPOSED_DEVELOPMENT_SOURCE",
        "originalRunId": run,
        "originalPepperstoneEurAccountVerified": True,
        "fixed780CalendarSlots": True,
        "futureAvailabilityExcludedFromIntentSelection": True,
        "originalRawProtobuf": raw_protobuf,
        "originalDecodedDayPanels": source,
        "originalAsObservedCurrentContract": metadata,
        "authenticatedRequestsAfterAccountAuth": calls,
    }
    plaintext = json.dumps(packed, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    cipher = seal_new(plaintext, recipient, run)
    ORIGINAL.write_bytes(cipher)
    # ENCRYPTED RAW SOURCE CUSTODY FIRST; only now compute EUR path returns.
    min_margin = (max(D(v) for v in margin.values()) if margin else None)
    if not market_currencies_ok:
        min_margin = None
    scored = evaluate(source, target, min_margin)
    first = scored["first26Weeks"]
    last = scored["last26Weeks"]
    def half_pass(x):
        if not x["commonPricedClocks"]:
            return False
        d = x["adverseMatchedNetEur"]
        return (d["combined"] > 0 and
                all(d["combined"] > d[p] for p in
                    ("copperOnly", "inverseGoldOnly", "audOwnMomentum",
                     "long", "short", "cash")))
    all_complete = scored["overall"]["commonPricedClocks"] == 780
    if all_complete and half_pass(first) and half_pass(last):
        verdict = "POSSIBLE_DEVELOPMENT_EDGE_ONLY_REQUIRES_NATIVE_INDEPENDENT"
    elif not all_complete:
        verdict = "INCONCLUSIVE_FULL_CALENDAR_SOURCE_INCOMPLETE_REPORT_CONDITIONAL_NET"
    else:
        verdict = "REJECT_EXACT_GCR1_NO_ROBUST_ADVERSE_INCREMENTAL_NET"
    published = {
        "schema": "MXM_GCR1_A1_ORIGINAL_FOUR_MARKET_EXPOSED_EUR",
        "originalRunId": int(run),
        "initialProtocolSha256": sha256(
            Path("research/GCR1_COPPER_GOLD_AUD_MACRO_DIFFUSION.md").read_bytes()).hexdigest(),
        "a1ProtocolSha256": sha256(
            Path("research/GCR1_OWNER_PRESOURCE_ADDENDUM_A1.md").read_bytes()).hexdigest(),
        "originalCiphertextSha256": sha256(cipher).hexdigest(),
        "originalPlaintextSha256": sha256(plaintext).hexdigest(),
        "readOnlyRequestsAfterAuth": calls,
        "originalSourceEncryptedBeforeOutcomeScoring": True,
        "fixed780ScheduledClocks": True,
        "fixed260Weekdays": True,
        "all52WeeksGloballyExposedDevelopmentOnly": True,
        "marketSources": {
            "enabledSymbolNames": metadata["enabledSymbols"],
            "nonSecretSourceStates": metadata["sourceStates"],
            "targetMinimumMarginEur": margin,
        },
        "results": scored,
        "verdict": verdict,
        "brokerActualFills": None,
        "historicalTrueTariffCertified": False,
        "independentConfirmation": False,
        "nativeFundedPortfolioNetEur": None,
        "continuousFloatingDrawdownCertified": False,
        "hard21Proven": False,
        "ordersSubmitted": 0,
        "cloudActivated": False,
        "oauthRefreshed": False,
    }
    PUBLIC.write_text(json.dumps(published, indent=2, allow_nan=False) + "\n")
    print("GCR1_ORIGINAL_CONDITIONAL_EUR", json.dumps({
        "requests": calls,
        "scheduled": 780,
        "commonPriced": scored["overall"]["commonPricedClocks"],
        "firstAdverse": first["adverseMatchedNetEur"],
        "lastAdverse": last["adverseMatchedNetEur"],
        "verdict": verdict,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
