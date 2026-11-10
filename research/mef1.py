"""MEF1: prespecified exploratory multi-asset minimum executable cost evidence."""
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from decimal import Decimal

from .contract_eur_cost import fee_at_current_contract, IncompleteCostEvidence
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_side, need
from .guard import require_read_only_request
from .native_original_openapi_product_replay import contract
from .owner_readonly_auth import authenticate

START = date(2026, 9, 1)
WEEKS = 8
TARGETS = {
    "AUDUSD": ("FX", 13, 5),
    "SpotCrude": ("energy", 14, 5),
    "XPTUSD": ("metal", 14, 5),
    "Coffee": ("agriculture", 14, 5),
    "US2000": ("equity_index", 14, 5),
}
SYMBOLS = (*TARGETS, "EURUSD")
UTC = ZoneInfo("UTC")


def latest(request, account, symbol_id, stamp):
    prices = []
    for side in (e.BID, e.ASK):
        r = request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                    symbolId=symbol_id, type=side, fromTimestamp=stamp - 20_000,
                    toTimestamp=stamp), m.ProtoOAGetTickDataRes)
        if r.hasMore:
            return None
        rows = decode_side(r.tickData, stamp - 20_000, stamp)
        if not rows:
            return None
        prices.append(Decimal(rows[-1][1]) / 100_000)
    return prices if 0 < prices[0] < prices[1] else None


def compare(request, account, tape, contracts, terms):
    output = {}
    fx_cache = {}
    for symbol, (asset_class, hour, minute) in TARGETS.items():
        if symbol not in tape:
            continue
        sid, quote_asset = tape[symbol]
        term = terms[symbol]
        observations = []
        for week in range(WEEKS):
            day = START + timedelta(weeks=week)
            stamp = int(datetime.combine(day, time(hour, minute), UTC).timestamp() * 1000)
            prices = latest(request, account, sid, stamp)
            obs = dict(date=day.isoformat(), spreadBps=None, commissionBps=None)
            observations.append(obs)
            if prices is None:
                continue
            bid, ask = prices
            mid = (bid + ask) / 2
            obs["spreadBps"] = float((ask - bid) / mid * 10_000)
            if "EURUSD" not in tape or quote_asset not in ("USD", "EUR"):
                continue
            if stamp not in fx_cache:
                fx_cache[stamp] = latest(request, account, tape["EURUSD"][0], stamp)
            fx = fx_cache[stamp]
            if fx is None:
                continue
            rates = {"EUR": Decimal(1), "USD": 1 / fx[0]}
            c = contracts[symbol]
            units = Decimal(c.minVolume) / 100
            try:
                fee = sum(Decimal(fee_at_current_contract(c, quote_asset, units, price, rates)
                          ["oneSideContractCommissionEur"]) for price in prices)
            except IncompleteCostEvidence:
                continue
            obs["commissionBps"] = float(fee / (mid * units * rates[quote_asset]) * 10_000)
        paired = [o for o in observations if o["spreadBps"] is not None]
        costed = [o for o in paired if o["commissionBps"] is not None]
        floor = [o["spreadBps"] + o["commissionBps"] for o in costed]
        output[symbol] = dict(assetClass=asset_class, terms=term, observations=observations,
                              validQuotePairs=len(paired), costedQuotePairs=len(costed),
                              medianSpreadBps=median(o["spreadBps"] for o in paired) if paired else None,
                              medianCurrentFeePlusSampledSpreadBps=median(floor) if floor else None,
                              maxCurrentFeePlusSampledSpreadBps=max(floor) if floor else None)
    return output


def main():
    t = StdlibCTraderTransport()
    requests = 0
    missing = []
    tape = {}
    terms = {}
    contracts = {}
    try:
        account = authenticate(t)

        def request(q, result_type):
            nonlocal requests
            need(requests < 175, "MEF1_READ_ONLY_BUDGET")
            require_read_only_request(q)
            r = t.request(q)
            requests += 1
            need(type(r) is result_type and r.IsInitialized()
                 and r.ctidTraderAccountId == account, "MEF1_RESPONSE_ACCOUNT_OR_TYPE")
            return r

        roster = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                         includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        currencies = {a.assetId: a.name for a in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and currencies.get(trader.trader.depositAssetId) == "EUR", "MEF1_BROKER_OR_EUR")
        available = {x.symbolName.casefold(): x for x in roster.symbol if x.enabled}
        for symbol in SYMBOLS:
            light = available.get(symbol.casefold())
            if light is None:
                missing.append(symbol)
                continue
            if symbol in TARGETS:
                details = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                                  symbolId=[light.symbolId]), m.ProtoOASymbolByIdRes)
                need(len(details.symbol) == 1 and details.symbol[0].symbolId == light.symbolId,
                     "MEF1_SYMBOL_CONTRACT")
                c = details.symbol[0]
                contracts[symbol] = c
                terms[symbol] = dict(
                    tradingMode=int(c.tradingMode),
                    currentContract=contract(symbol, c, currencies.get(light.quoteAssetId),
                                             int(datetime.now(ET).timestamp() * 1000)),
                    currentMinimumMarginEur=None,
                )
                if c.tradingMode == 0 and c.minVolume > 0:
                    r = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                                symbolId=light.symbolId, volume=[c.minVolume]),
                                m.ProtoOAExpectedMarginRes)
                    if r.HasField("moneyDigits") and len(r.margin) == 1 and r.margin[0].volume == c.minVolume:
                        margin = r.margin[0]
                        terms[symbol]["currentMinimumMarginEur"] = {
                            "buy": margin.buyMargin / 10**r.moneyDigits,
                            "sell": margin.sellMargin / 10**r.moneyDigits,
                        }
            tape[symbol] = (light.symbolId, currencies.get(light.quoteAssetId))
        receipts = compare(request, account, tape, contracts, terms)
    finally:
        t.close()
    payload = dict(protocolSha256=sha256(Path("research/MEF1.md").read_bytes()).hexdigest(),
                   missingEnabledSymbols=missing, readOnlyRequestsAfterAuth=requests,
                   candidates=receipts, fundedNetEur=None, orders=0, cloudActivated=False)
    Path("mef1-public.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    print("MEF1_RECEIPT " + json.dumps(payload, separators=(",", ":"), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
