"""Original Pepperstone LIVE SCOPE_VIEW -> the EXISTING C# product replay.

Single read-only research execution. No original ciphertext, new custody,
OAuth refresh, client ID output, broker-account identifier output, or orders.
BID/ASK as-of M5 clocks come from genuine separate historical tick responses.
The input tape lives only in the GitHub runner's temporary directory.
"""
from __future__ import annotations

import bisect
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

from .collect import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars, decode_side

SYMBOLS = ("EURUSD", "GBPUSD")
M5 = 300000
SOURCE_START = int(datetime(2026, 11, 5, 17, tzinfo=timezone.utc).timestamp() * 1000)
DECISION_START = int(datetime(2026, 11, 6, 9, tzinfo=timezone.utc).timestamp() * 1000)
DECISION_END = int(datetime(2026, 11, 6, 13, tzinfo=timezone.utc).timestamp() * 1000)
SOURCE_END = DECISION_END + M5
QUOTING_WINDOW = 15 * 60000
MAX_REQUESTS = 850
MAX_TICK_PAGES = 16

class MarketReplayError(Exception):
    pass

def need(ok, code):
    if not ok:
        raise MarketReplayError("ORIGINAL_OPENAPI_PRODUCT_" + code)

def price(v):
    return str(D(int(v)) / D(100000))

def ms(val):
    return int(val)

def contract(symbol, c, quote_asset, at):
    fields = lambda x: getattr(c, x) if c.HasField(x) else None
    return {
        "Symbol": symbol, "QuoteAsset": quote_asset, "ObservedAtUtcMs": at,
        "MinimumUnits": str(D(c.minVolume)/100),
        "VolumeStepUnits": str(D(c.stepVolume)/100),
        "MaximumUnits": str(D(c.maxVolume)/100),
        "LotUnits": str(D(c.lotSize)/100),
        "CommissionType": int(c.commissionType),
        "PreciseRateWire": int(c.preciseTradingCommissionRate),
        "MinimumCommissionType": int(c.minCommissionType),
        "PreciseMinimumWire": int(c.preciseMinCommission),
        "MinimumCommissionAsset": c.minCommissionAsset,
        "PnlConversionFeeBps": int(c.pnlConversionFeeRate),
        "SwapCalculationType": int(c.swapCalculationType) if fields("swapCalculationType") is not None else None,
        "LongSwap": str(c.swapLong) if fields("swapLong") is not None else None,
        "ShortSwap": str(c.swapShort) if fields("swapShort") is not None else None,
        "PipPosition": int(c.pipPosition),
        "SwapPeriodHours": fields("swapPeriod"),
        "SwapTimeUtcMinute": fields("swapTime"),
        "TripleSwapWeekday": int(c.swapRollover3Days) if fields("swapRollover3Days") is not None else None,
        "ChargeSwapAtWeekends": fields("chargeSwapAtWeekends"),
        "SkipSwapPeriods": fields("skipSWAPPeriods"),
        "OriginalBrokerAuthenticated": True,
        "HistoricalTariffContinuityCertified": False
    }

def collect_and_evaluate():
    transport = StdlibCTraderTransport()
    counter = 0
    try:
        # Existing historical original-account binding and EXPLICIT VIEW scope.
        account = authenticate(transport)
        def req(q, klass):
            nonlocal counter
            need(counter < MAX_REQUESTS, "READONLY_REQUEST_BUDGET")
            require_read_only_request(q)
            result = transport.request(q)
            counter += 1
            need(type(result) is klass and result.IsInitialized()
                 and result.ctidTraderAccountId == q.ctidTraderAccountId == account,
                 "ORIGINAL_LIVE_ACCOUNT_REQUEST_RESPONSE")
            return result

        trader = req(m.ProtoOATraderReq(ctidTraderAccountId=account),
                     m.ProtoOATraderRes)
        asset_result = req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                           m.ProtoOAAssetListRes)
        roster_reply = req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        assets = {x.assetId:x.name for x in asset_result.asset}
        need(trader.trader.HasField("brokerName")
             and "pepperstone" in trader.trader.brokerName.casefold()
             and assets.get(trader.trader.depositAssetId) == "EUR",
             "BROKER_OR_EUR_ACCOUNT_MISMATCH")
        roster = {x.symbolName:x for x in roster_reply.symbol if x.enabled}
        need(all(x in roster for x in SYMBOLS), "PREREGISTERED_FX_SYMBOL_UNAVAILABLE")
        terms = {}
        ids = {}
        for name in SYMBOLS:
            light = roster[name]
            ids[name] = int(light.symbolId)
            need(assets.get(light.quoteAssetId) == "USD",
                 "RESEARCH_FX_QUOTE_ASSET_NOT_USD")
            detail = req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account, symbolId=[ids[name]]),
                m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1
                 and detail.symbol[0].symbolId == ids[name],
                 "CONTRACT_SYMBOL_MISMATCH")
            c = detail.symbol[0]
            need(c.digits == 5 and int(c.tradingMode) == 0 and
                 c.minVolume>0 and c.stepVolume>0 and
                 c.maxVolume>=c.minVolume and c.lotSize>0 and
                 c.HasField("preciseTradingCommissionRate") and
                 c.HasField("preciseMinCommission"),
                 "CONTRACT_COST_OR_PRICE_PRECISION_UNAVAILABLE")
            need(int(c.commissionType) in (1,2,3,4)
                 and int(c.minCommissionType) in (1,2)
                 and c.minCommissionAsset in ("USD",""),
                 "CONTRACT_COMMISSION_CONVERSION_UNAVAILABLE")
            margin = req(m.ProtoOAExpectedMarginReq(
                ctidTraderAccountId=account, symbolId=ids[name],
                volume=[c.minVolume]), m.ProtoOAExpectedMarginRes)
            need(len(margin.margin)==1 and
                 margin.margin[0].volume==c.minVolume
                 and margin.HasField("moneyDigits"),
                 "BROKER_MINIMUM_MARGIN_UNAVAILABLE")
            minimum_margin = D(max(margin.margin[0].buyMargin,
                                margin.margin[0].sellMargin)) / (
                                D(10)**margin.moneyDigits)
            terms[name] = (contract(name,c,"USD",DECISION_START),
                           minimum_margin)
        bars = []
        for name in SYMBOLS:
            history = {}
            lo = SOURCE_START
            while lo < SOURCE_END:
                hi = min(lo + 5*3600000, SOURCE_END)
                res = req(m.ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account,symbolId=ids[name],
                    period=e.M5,fromTimestamp=lo,toTimestamp=hi),
                    m.ProtoOAGetTrendbarsRes)
                need(res.period==e.M5 and
                     (not res.HasField("symbolId") or res.symbolId==ids[name]) and
                     not res.hasMore, "M5_TRENDBAR_BATCH_TRUNCATED")
                for t,closed,o,h,l,c,v in decode_bars(
                    res.trendbar,lo-M5,hi+M5,5):
                    need(t not in history or history[t]==(closed,o,h,l,c,v),
                         "M5_DUPLICATE_CONFLICT")
                    history[t]=(closed,o,h,l,c,v)
                lo = hi
            rows = [{"OpenAt":t,"CloseAt":v[0],
                     "Open":price(v[1]),"High":price(v[2]),
                     "Low":price(v[3]),"Close":price(v[4]),
                     "TickVolume":v[5]}
                    for t,v in sorted(history.items())
                    if v[0] <= SOURCE_END]
            need(len(rows)>=110, "INSUFFICIENT_COMPLETE_M5")
            bars.append({"Symbol":name,"M5":rows})

        def ticks(name, side, start, end):
            all_rows = []
            window_to = end
            pages = 0
            while window_to >= start:
                pages += 1
                need(pages<=MAX_TICK_PAGES, "TICK_BATCH_PAGINATION_UNFINISHED")
                res = req(m.ProtoOAGetTickDataReq(
                    ctidTraderAccountId=account,
                    symbolId=ids[name],type=side,
                    fromTimestamp=start,toTimestamp=window_to),
                    m.ProtoOAGetTickDataRes)
                data = decode_side(res.tickData,start,window_to)
                all_rows.extend(data)
                if not res.hasMore:
                    break
                need(len(data)>0, "TICK_PAGINATION_EMPTY")
                earliest = data[0][0]
                need(earliest>start, "TICK_PAGINATION_TIME_BOUNDARY")
                window_to = earliest-1
            return sorted(set((int(t),int(v)) for t,v in all_rows))

        streams = {name:{e.BID:[],e.ASK:[]} for name in SYMBOLS}
        for lo in range(DECISION_START-120000, DECISION_END+1500,
                        QUOTING_WINDOW):
            hi = min(lo+QUOTING_WINDOW-1,DECISION_END+1500)
            for name in SYMBOLS:
                for side in (e.BID,e.ASK):
                    streams[name][side].extend(ticks(name,side,lo,hi))
        # As-of quotations: never pick a future tick for an earlier M5 close.
        snapshots = {}
        for name in SYMBOLS:
            raw = {}
            for side in (e.BID,e.ASK):
                seq = sorted(set(streams[name][side]))
                raw[side] = ([t for t,_ in seq],[v for _,v in seq])
            snapshots[name] = raw
        def asof(name,side,at):
            ts,vs = snapshots[name][side]
            i=bisect.bisect_right(ts,at)-1
            if i<0 or at-ts[i]>60000:
                return None
            return D(vs[i])/D(100000)

        marks = []
        for clock in range(DECISION_START+1500,DECISION_END+1500,M5):
            eur_bid=asof("EURUSD",e.BID,clock)
            eur_ask=asof("EURUSD",e.ASK,clock)
            if eur_bid is None or eur_ask is None or eur_bid<=0 or eur_ask<eur_bid:
                continue
            fx_credit=D(1)/eur_ask
            fx_debit=D(1)/eur_bid
            usd_to_eur=(fx_credit+fx_debit)/2
            for name in SYMBOLS:
                bid=asof(name,e.BID,clock)
                ask=asof(name,e.ASK,clock)
                if bid is None or ask is None or bid<=0 or ask<bid:
                    continue
                c,margin=terms[name]
                spread=ask-bid
                # A disclosed slippage SCENARIO, not a certified fill price.
                slip=max(D("0.00001"),spread/4)
                marks.append({
                    "At":clock,"Symbol":name,"Bid":str(bid),"Ask":str(ask),
                    "QuoteCreditToEur":str(fx_credit),
                    "QuoteDebitToEur":str(fx_debit),
                    "UsdToEur":str(usd_to_eur),
                    "MarginRequirementEur":str(margin),
                    "SlippagePerSideQuote":str(slip),
                    "Contract":c
                })
        need(len(marks)>=20, "INSUFFICIENT_ASOF_BIDASK_CLOCKS")
        # The only file sent to the C# replay contains time-labeled market
        # readings, never OAuth values, original account ID, or broker orders.
        tape={"SourceLabel":"ORIGINAL_PEPPERSTONE_OPENAPI_ScopeView_2026_11_06_FX_M5",
              "Bars":bars,"Marks":marks}
        with tempfile.TemporaryDirectory(prefix="mxm-openapi-native-") as folder:
            input_file=Path(folder)/"source.json"
            output_file=Path(folder)/"receipt.json"
            input_file.write_text(json.dumps(tape,separators=(",",":")))
            input_file.chmod(0o600)
            env={k:v for k,v in os.environ.items() if not k.startswith(
                ("R3_CTRADER_","CTRADER_","MXM_V4_"))}
            process=subprocess.run(["dotnet",
                "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                str(input_file),str(output_file),
                "--native-original-openapi-research"],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,env=env,timeout=150)
            need(process.returncode==0 and output_file.is_file(),
                 "NATIVE_CSHARP_REPLAY_EXECUTION_FAILED")
            evaluated=json.loads(output_file.read_text())
        receipt=evaluated["Receipt"]
        result={
            "Schema":"MXM_OPENAPI_ACTUAL_NATIVE_REPLAY_20261109_V1",
            "ReadOnlyOriginalPepperstoneAuthenticated":True,
            "ExplicitViewScopeVerified":True,
            "InstrumentsRequested":list(SYMBOLS),
            "M5BarsBySymbol":{b["Symbol"]:len(b["M5"]) for b in bars},
            "AuthenticBidAskAsOfObservations":len(marks),
            "OpenApiReadOnlyRequests":counter,
            "InitialModelCapitalEur":300,
            "CurrentContractTermsNotHistoricalGuarantee":True,
            "HistoricalSlippageModeledNotBrokerFill":True,
            "UnqualifiedExploratoryResearch":True,
            "IndependentConfirmation":False,
            "OrdersSubmitted":0,
            "CloudActivated":False,
            "NativeProductReceipt":receipt
        }
        Path("native-original-openapi-public-receipt.json").write_text(
            json.dumps(result,indent=2,sort_keys=True)+"\n")
        print("MXM_ORIGINAL_OPENAPI_NATIVE_PRODUCT_ECONOMICS_EXECUTED",
              "symbols",len(SYMBOLS),"bars",
              sum(len(b["M5"]) for b in bars),"quote_marks",len(marks),
              "native_roundtrips",receipt["CompletedModelRoundTrips"],
              flush=True)
        return 0
    finally:
        transport.close()

def main():
    try:
        return collect_and_evaluate()
    except Exception as exc:
        code=str(exc) if isinstance(exc,MarketReplayError) else (
            "ORIGINAL_OPENAPI_PRODUCT_FAILED_"+type(exc).__name__)
        print(code,flush=True)
        return 1

if __name__=="__main__":
    sys.exit(main())
