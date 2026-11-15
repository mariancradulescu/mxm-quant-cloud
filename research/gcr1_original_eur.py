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
from .gcr1_macro_signal import scheduled_clocks, STEP_MS

SYMBOLS = ("Copper", "XAUUSD", "AUDUSD", "EURUSD")
BAR_SYMBOLS = ("Copper",)
FX_SYMBOLS = ("AUDUSD", "EURUSD")
M5 = STEP_MS
MAX_CALLS = 4600
MAX_QUOTE_AGE_MS = 20000
ORIGINAL = Path("gcr1-original-protected.v2.enc")
PUBLIC = Path("gcr1-original-source-public.json")


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
        metadata["targetCurrentContractBase64"] = (base64.b64encode(target.SerializeToString()).decode("ascii") if target else None)
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
                en = ms(day, 16, 10)
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
            # Only original Copper source is newly acquired: BDP1 owns
            # original XAUUSD/AUDUSD M5. No GCR1 outcome or direction is
            # computed in this job. In the protected custody readback the
            # verified BDP1 closes are joined with this immutable Copper
            # tape before ANY financial label can be scored.
            # Every future quote clock is requested independent of signals.
            quotes = {name: {} for name in FX_SYMBOLS}
            for name in FX_SYMBOLS:
                for clock in quote_clocks(day):
                    quotes[name][str(clock)] = observed_quote(name, clock, ids)
            source[key] = {"bars": day_bars, "quotes": quotes}
            if d_index % 30 == 29:
                print("GCR1_ORIGINAL_SOURCE_ONLY_DAYS", d_index+1, "OF", len(days),
                      "READONLY_REQUESTS", calls, flush=True)
    finally:
        t.close()

    packed = {
        "schema": "MXM_GCR1_A2_ORIGINAL_COPPER_AND_QUOTES_SOURCE_ONLY",
        "originalRunId": run,
        "originalPepperstoneEurAccountVerified": True,
        "fixed780CalendarSlots": True,
        "originalNewSourceCollectedIndependentOfFutureIntentOrReturn": True,
        "reusedBDP1BarInputIsSeparateProtectedCustodyJob": True,
        "originalRawProtobuf": raw_protobuf,
        "originalDecodedDayPanels": source,
        "originalAsObservedCurrentContract": metadata,
        "authenticatedRequestsAfterAccountAuth": calls,
    }
    plaintext = json.dumps(packed, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    cipher = seal_new(plaintext, recipient, run)
    ORIGINAL.write_bytes(cipher)
    # CURRENT sealed source is now frozen. No EUR return, result,
    # selected signal or complete-priced event is computed in this job.
    published = {
        "schema": "MXM_GCR1_A2_SOURCE_ONLY_NO_FINANCIAL_SCORING",
        "originalRunId": int(run),
        "originalProtocolSha256": sha256(
            Path("research/GCR1_COPPER_GOLD_AUD_MACRO_DIFFUSION.md").read_bytes()).hexdigest(),
        "a1ProtocolSha256": sha256(
            Path("research/GCR1_OWNER_PRESOURCE_ADDENDUM_A1.md").read_bytes()).hexdigest(),
        "a2SourceReuseProtocolSha256": sha256(
            Path("research/GCR1_OWNER_PRESOURCE_SOURCE_REUSE_A2.md").read_bytes()).hexdigest(),
        "originalCiphertextSha256": sha256(cipher).hexdigest(),
        "originalPlaintextSha256": sha256(plaintext).hexdigest(),
        "readOnlyRequestsAfterAuth": calls,
        "fixed260Weekdays": True,
        "fixed780ClockGrid": True,
        "sourceEncryptedBeforeAllGCR1OutcomeScoring": True,
        "reusedSourceRequired": "BDP1_41724643418_SEALED_GOLD_AUD_M5",
        "newBarTargets": ["Copper"],
        "newQuoteTargets": ["AUDUSD", "EURUSD"],
        "brokerActualFills": None,
        "conditionalNetEur": None,
        "ordersSubmitted": 0,
        "cloudActivated": False,
    }
    PUBLIC.write_text(json.dumps(published, indent=2, allow_nan=False) + "\\n")
    print("GCR1_A2_ORIGINAL_SOURCE_ONLY", json.dumps({
        "requests": calls, "days": 260, "fixedClocks": 780,
        "encryptedFirst": True, "originalAccount": True,
        "sourceStates": metadata["sourceStates"],
        "financialScoring": False
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
