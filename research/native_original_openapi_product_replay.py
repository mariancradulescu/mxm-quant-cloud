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
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

from .owner_readonly_auth import authenticate
from .guard import CaptureContractError
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars, decode_side

# Predeclared original-account USD-quoted FX markets, selected BEFORE scoring.
# This reuses the prior Open API product collector, not any closed MCS1 study.
# W45 original run is immutable when invoked in its original mode.
# W36/W37 historical profile is fixed in fx_historical_w36_w37_protocol.json
# committed before collecting a single W36 or W37 quote.
HISTORIC_W36_W37 = "--historical-w36w37" in sys.argv
CROSS_ENERGY_EQUITY = "--cross-energy-equity" in sys.argv
CRYPTO_CRUDE_HISTORIC = "--crypto-crude-w24w25" in sys.argv
US_INDEX_W20W21 = "--us-index-w20w21" in sys.argv
NAS100_FROZEN_W32W33 = "--nas100-frozen-w32w33" in sys.argv
NG_AUD_W38W39 = "--natgas-audusd-w38w39" in sys.argv
HK_BRENT_W40W41 = "--hk50-spotbrent-w40w41" in sys.argv
BRENT_AMD_W42W43 = "--brent-amd-w42w43" in sys.argv
US_INDEX_ANY = US_INDEX_W20W21 or NAS100_FROZEN_W32W33
if sum((HISTORIC_W36_W37, CROSS_ENERGY_EQUITY, CRYPTO_CRUDE_HISTORIC,
        US_INDEX_W20W21, NAS100_FROZEN_W32W33, NG_AUD_W38W39,
        HK_BRENT_W40W41, BRENT_AMD_W42W43))>1:
    raise RuntimeError("MULTIPLE_RESEARCH_PROFILES_NOT_ALLOWED")
SYMBOLS = (("EURUSD","SpotBrent","AMD.US") if BRENT_AMD_W42W43 else
           ("EURUSD","HK50","SpotBrent") if HK_BRENT_W40W41 else
           ("EURUSD","AUDUSD","NatGas") if NG_AUD_W38W39 else
           ("EURUSD","US500","NAS100") if US_INDEX_ANY else
           ("EURUSD","ETHUSD","SpotCrude") if CRYPTO_CRUDE_HISTORIC else
           ("EURUSD","SpotBrent","SpotCrude","AMD.US")
           if CROSS_ENERGY_EQUITY else
           ("EURUSD","GBPUSD","AUDUSD","NZDUSD") if HISTORIC_W36_W37
           else ("EURUSD","GBPUSD","AUDUSD"))
M5 = 300000
if BRENT_AMD_W42W43:
    SOURCE_START = int(datetime(2026,10,9,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,10,12,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,10,26,tzinfo=timezone.utc).timestamp()*1000)
elif HK_BRENT_W40W41:
    # Original predeclared index/energy cross-session weeks, no W46 use.
    SOURCE_START = int(datetime(2026,9,25,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,9,28,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,10,12,tzinfo=timezone.utc).timestamp()*1000)
elif NG_AUD_W38W39:
    # ORIGINAL newly frozen multi-class NatGas (energy) + AUDUSD (FX)
    # All 2026 W38/W39 source is globally exposed, never a holdout.
    SOURCE_START = int(datetime(2026,9,11,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,9,14,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,9,28,tzinfo=timezone.utc).timestamp()*1000)
elif NAS100_FROZEN_W32W33:
    # Same W20/W21 NAS100 and US500 fixed trading rules. NEVER a holdout.
    # Freeze dates and original source before Pepperstone source access.
    SOURCE_START = int(datetime(2026,7,31,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,8,3,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,8,17,tzinfo=timezone.utc).timestamp()*1000)
elif US_INDEX_W20W21:
    SOURCE_START = int(datetime(2026,5,8,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,5,11,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,5,25,tzinfo=timezone.utc).timestamp()*1000)
elif CRYPTO_CRUDE_HISTORIC:
    # Protocol was committed BEFORE opening any original W24/W25 source.
    # Distinct historic weeks, no previously closed FX/OIL/CRYPTO strategy rerun.
    SOURCE_START = int(datetime(2026,6,5,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,6,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,6,22,tzinfo=timezone.utc).timestamp()*1000)
elif CROSS_ENERGY_EQUITY:
    # Locked in cross_asset_energy_equity_w30_w31_protocol.json BEFORE request.
    # July W30/W31 are globally historically exposed, NOT independent.
    SOURCE_START = int(datetime(2026,7,17,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,7,20,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,8,3,tzinfo=timezone.utc).timestamp()*1000)
elif HISTORIC_W36_W37:
    SOURCE_START = int(datetime(2026,8,28,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,8,31,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,9,14,tzinfo=timezone.utc).timestamp()*1000)
else:
    # Immutable W45 mode for reproducibility; never run it again in this PR.
    SOURCE_START = int(datetime(2026,10,30,8,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_START = int(datetime(2026,11,2,tzinfo=timezone.utc).timestamp()*1000)
    DECISION_END = int(datetime(2026,11,9,tzinfo=timezone.utc).timestamp()*1000)
SOURCE_END = DECISION_END + M5
QUOTING_WINDOW = 30 * 60000
MAX_REQUESTS = 7000
MAX_TICK_PAGES = 24

class MarketReplayError(Exception):
    pass

def need(ok, code):
    if not ok:
        raise MarketReplayError("ORIGINAL_OPENAPI_PRODUCT_" + code)

def price(v):
    return str(D(int(v)) / D(100000))

def ms(val):
    return int(val)

def contract(symbol, c, quote_asset, observed_at):
    fields = lambda x: getattr(c, x) if c.HasField(x) else None
    return {
        "Symbol": symbol, "QuoteAsset": quote_asset, "ObservedAtUtcMs": observed_at,
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

def emit_native_failure(process):
    match = re.search(r"^(?:LDP1|JRC1|OTC1|MCT2)_NATIVE_REPLAY_REJECTED:[A-Za-z0-9_-]+:[A-Za-z0-9_]+$",
                      process.stderr or "", re.MULTILINE)
    if process.returncode and match:
        print(match.group(0), flush=True)


def collect_and_evaluate(profile=None):
    symbols = SYMBOLS if profile is None else profile["symbols"]
    source_start = SOURCE_START if profile is None else profile["source_start"]
    decision_start = DECISION_START if profile is None else profile["start"]
    decision_end = DECISION_END if profile is None else profile["end"]
    source_end = decision_end + M5

    def eligible(clock):
        day = datetime.fromtimestamp(clock / 1000, timezone.utc)
        return day.weekday() < 5 and (profile is None or profile.get("quote_hour_start", 14) <= day.hour < profile.get("quote_hour_end", 21))

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
        need(all(x in roster for x in symbols), "PREREGISTERED_FX_SYMBOL_UNAVAILABLE")
        terms = {}
        ids = {}

        for name in symbols:
            light = roster[name]
            ids[name] = int(light.symbolId)
            quote_asset=assets.get(light.quoteAssetId)
            allowed=("USD","JPY") if profile and profile.get("jpy_route") else ("USD",)
            need(quote_asset in allowed,
                 "RESEARCH_FX_QUOTE_ASSET_NOT_USD")
            detail = req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account, symbolId=[ids[name]]),
                m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1
                 and detail.symbol[0].symbolId == ids[name],
                 "CONTRACT_SYMBOL_MISMATCH")
            c = detail.symbol[0]
            need((0<=int(c.digits)<=8 if (profile is not None or CROSS_ENERGY_EQUITY or CRYPTO_CRUDE_HISTORIC or US_INDEX_ANY or NG_AUD_W38W39 or HK_BRENT_W40W41 or BRENT_AMD_W42W43) else c.digits==5)
                 and int(c.tradingMode)==0 and
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
            need(minimum_margin>0 and minimum_margin<=D(300),
                 "MINIMUM_BROKER_MARGIN_EXCEEDS_SINGLE_300_EUR_BUDGET")
            terms[name] = (contract(name,c,quote_asset,
                            int(datetime.now(timezone.utc).timestamp()*1000)),
                           minimum_margin)
        if profile is not None and profile.get("contract_preflight"):
            with tempfile.TemporaryDirectory(prefix="mxm-contract-preflight-") as folder:
                inp, out = Path(folder)/"terms.json", Path(folder)/"result.json"
                inp.write_text(json.dumps([terms[name][0] for name in symbols]))
                inp.chmod(0o600)
                env = {k: v for k, v in os.environ.items()
                       if not k.startswith(("R3_CTRADER_", "CTRADER_", "MXM_V4_"))}
                preflight = subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                    str(inp), str(out), profile["contract_preflight"]], capture_output=True,
                    text=True, env=env, timeout=30)
                emit_native_failure(preflight)
                need(preflight.returncode == 0 and out.is_file(), "NATIVE_CONTRACT_PREFLIGHT_FAILED")
        bars = []
        for name in symbols:
            history = {}
            lo = source_start
            while lo < source_end:
                hi = min(lo + 6*3600000, source_end)
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
                    if v[0] <= source_end]
            need(len(rows)>=(400 if (CROSS_ENERGY_EQUITY or CRYPTO_CRUDE_HISTORIC or US_INDEX_ANY or NG_AUD_W38W39 or HK_BRENT_W40W41 or BRENT_AMD_W42W43)
                                 and name not in ("EURUSD","AUDUSD")
                            else 2100 if HISTORIC_W36_W37 else 1100),
                 "INSUFFICIENT_PREDECLARED_COMPLETE_M5")
            # Mandatory development window integrity check before further
            # tick data is requested; weekend bars are not manufactured.
            first_week=decision_start+7*86400000
            minimum_week=(200 if (CROSS_ENERGY_EQUITY or CRYPTO_CRUDE_HISTORIC or US_INDEX_ANY or NG_AUD_W38W39 or HK_BRENT_W40W41 or BRENT_AMD_W42W43)
                            and name not in ("EURUSD","AUDUSD") else 1000)
            need(sum(decision_start<=x["OpenAt"]<first_week for x in rows)>=minimum_week,
                 "FIRST_COMPLETE_WEEK_M5_COVERAGE_UNSATISFACTORY")
            if NAS100_FROZEN_W32W33 or NG_AUD_W38W39 or HK_BRENT_W40W41 or BRENT_AMD_W42W43:
                # No empty/gappy second scoring week counted as genuine.
                need(sum(first_week<=x["OpenAt"]<decision_end for x in rows)>=minimum_week,
                     "SECOND_COMPLETE_WEEK_M5_COVERAGE_UNSATISFACTORY")
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

        # Query complete genuine BID and ASK events in 30-minute windows,
        # then discard raw ticks after deriving the six as-of M5 snapshots.
        # No price is reconstructed from OHLCV, no future tick is used, no
        # weekend gaps are forward-filled, and raw ticks never leave runner.
        sampled={name:{e.BID:{},e.ASK:{}} for name in symbols}
        quote_stamps={name:{e.BID:{},e.ASK:{}} for name in symbols}
        quote_windows=0
        for lo in range(decision_start-120000,decision_end+1500,
                        QUOTING_WINDOW):
            hi=min(lo+QUOTING_WINDOW-1,decision_end+1500)
            first=decision_start+1500+max(
                0,(lo-(decision_start+1500)+M5-1)//M5)*M5
            clocks=[clock for clock in range(first,hi+1,M5)
                    if clock<decision_end and
                    eligible(clock)]
            if not clocks:continue
            quote_windows+=1
            for name in symbols:
                for side in (e.BID,e.ASK):
                    points=ticks(name,side,lo,hi)
                    ts=[t for t,_ in points]
                    for clock in clocks:
                        i=bisect.bisect_right(ts,clock)-1
                        if i>=0 and clock-ts[i]<=60000:
                            sampled[name][side][clock]=D(points[i][1])/D(100000)
                            quote_stamps[name][side][clock]=points[i][0]
        marks=[]
        total_clocks=0
        missing_pair_clock=0
        for clock in range(decision_start+1500,decision_end,M5):
            if not eligible(clock):
                continue
            total_clocks+=1
            eur_bid=sampled["EURUSD"][e.BID].get(clock)
            eur_ask=sampled["EURUSD"][e.ASK].get(clock)
            if eur_bid is None or eur_ask is None or eur_bid<=0 or eur_ask<eur_bid:
                missing_pair_clock+=len(symbols)
                continue
            fx_credit=D(1)/eur_ask
            fx_debit=D(1)/eur_bid
            usd_to_eur=(fx_credit+fx_debit)/2
            for name in symbols:
                bid=sampled[name][e.BID].get(clock)
                ask=sampled[name][e.ASK].get(clock)
                if bid is None or ask is None or bid<=0 or ask<bid:
                    missing_pair_clock+=1
                    continue
                c,margin=terms[name]
                route = None
                if profile and profile.get("jpy_route"):
                    names = ("USDJPY","EURUSD") if c["QuoteAsset"]=="JPY" else ("EURUSD",)
                    route=[]
                    for pair in names:
                        pair_bid=sampled[pair][e.BID].get(clock)
                        pair_ask=sampled[pair][e.ASK].get(clock)
                        light=roster[pair]
                        if pair_bid is None or pair_ask is None or pair_bid<=0 or pair_ask<pair_bid:
                            break
                        route.append(dict(Symbol=pair,BaseAsset=assets[light.baseAssetId],
                            QuoteAsset=assets[light.quoteAssetId],AtUtcMs=min(quote_stamps[pair][e.BID][clock],quote_stamps[pair][e.ASK][clock]),
                            Bid=str(pair_bid),Ask=str(pair_ask),OriginalBrokerAuthenticated=True))
                    if len(route)!=len(names):
                        missing_pair_clock+=1
                        continue
                spread=ask-bid
                # Conditional slippage model, not authentic broker fill.
                slip=max(D("0.00001"),spread/4)
                marks.append({
                    "At":clock,"Symbol":name,"Bid":str(bid),"Ask":str(ask),
                    "QuoteCreditToEur":str(fx_credit),
                    "QuoteDebitToEur":str(fx_debit),
                    "UsdToEur":str(usd_to_eur),
                    "MarginRequirementEur":str(margin),
                    "SlippagePerSideQuote":str(slip),
                    "Contract":c,
                    **({"OriginalFxRoute":route} if route is not None else {})
                })
        need(len(marks)>=300, "INSUFFICIENT_MULTI_WEEK_ASOF_BIDASK_CLOCKS")
        # The only file sent to the C# replay contains time-labeled market
        # readings, never OAuth values, original account ID, or broker orders.
        tape={"SourceLabel":(profile["label"] if profile is not None else (
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W42_W43_BRENT_AMD_PREDECLARED"
              if BRENT_AMD_W42W43 else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W40_W41_HK_BRENT_PREDECLARED"
              if HK_BRENT_W40W41 else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W38_W39_NG_AUD_PREDECLARED"
              if NG_AUD_W38W39 else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W32_W33_NAS_REPLICATION_EXPOSED"
              if NAS100_FROZEN_W32W33 else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W20_W21_US_INDEX_PREDECLARED"
              if US_INDEX_W20W21 else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W24_W25_CRYPTO_CRUDE_PREDECLARED"
              if CRYPTO_CRUDE_HISTORIC else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W30_W31_ENERGY_EQUITY_PREDECLARED"
              if CROSS_ENERGY_EQUITY else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W36_W37_FX_M5_SHOCK_TICKFLOW_PREDECLARED"
              if HISTORIC_W36_W37 else
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W45_FX_M5_BREADTH_AND_SHOCK_PREDECLARED")),
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
                (profile["mode"] if profile is not None else
                 "--native-original-openapi-brent-amd-w42w43"
                  if BRENT_AMD_W42W43 else
                  "--native-original-openapi-hk50-spotbrent-w40w41"
                 if HK_BRENT_W40W41 else
                 "--native-original-openapi-natgas-audusd-w38w39"
                 if NG_AUD_W38W39 else
                 "--native-original-openapi-nas100-w32w33"
                 if NAS100_FROZEN_W32W33 else
                 "--native-original-openapi-us-index-w20w21"
                 if US_INDEX_W20W21 else
                 "--native-original-openapi-crypto-crude-w24w25"
                 if CRYPTO_CRUDE_HISTORIC else
                 "--native-original-openapi-energy-equity-w30w31"
                 if CROSS_ENERGY_EQUITY else
                 "--native-original-openapi-historic-w36w37"
                 if HISTORIC_W36_W37 else "--native-original-openapi-w45")],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE if profile and profile.get("contract_preflight") else subprocess.DEVNULL,
                text=True,env=env,timeout=150)
            if profile and profile.get("contract_preflight"):
                emit_native_failure(process)
            need(process.returncode==0 and output_file.is_file(),
                 "NATIVE_CSHARP_REPLAY_EXECUTION_FAILED")
            evaluated=json.loads(output_file.read_text())
        receipt=evaluated["Receipt"]
        if profile is not None:
            return dict(evaluated, OriginalPepperstoneAccountAuthenticated=True,
                        PostAuthenticationReadOnlyRequests=counter,
                        OriginalBarsBySymbol={b["Symbol"]:len(b["M5"]) for b in bars},
                        OriginalBidAskAsOfMarks=len(marks), QuoteWindows=quote_windows,
                        MissingQuoteInstrumentClocks=missing_pair_clock,
                        ExpectedClocksPerSymbol=total_clocks,
                        InitialModelCapitalEur=300, OrdersSubmitted=0,
                        CloudActivated=False, IndependentConfirmation=False)
        result={
            "Schema":("MXM_OPENAPI_ORIGINAL_BRENT_AMD_W42_W43_V1"
                       if BRENT_AMD_W42W43 else"MXM_OPENAPI_ORIGINAL_HK50_SPOTBRENT_W40_W41_V1"
                      if HK_BRENT_W40W41 else
                      "MXM_OPENAPI_ORIGINAL_NATGAS_AUDUSD_W38_W39_V1"
                      if NG_AUD_W38W39 else
                      "MXM_OPENAPI_ORIGINAL_NAS100_FROZEN_W32_W33_V1"
                      if NAS100_FROZEN_W32W33 else
                      "MXM_OPENAPI_ORIGINAL_US_INDEX_W20W21_V1"
                      if US_INDEX_W20W21 else
                      "MXM_OPENAPI_ORIGINAL_CRYPTO_CRUDE_W24W25_V1"
                      if CRYPTO_CRUDE_HISTORIC else
                      "MXM_OPENAPI_ORIGINAL_CROSS_ASSET_W30W31_V1"
                      if CROSS_ENERGY_EQUITY else
                      "MXM_OPENAPI_AUTHENTIC_NATIVE_HISTORICAL_W36_W37_V1"
                      if HISTORIC_W36_W37 else "MXM_OPENAPI_AUTHENTIC_NATIVE_W45_FX_V1"),
            "ProtocolPath":("research/brent_amd_w42_w43_protocol.json"
                             if BRENT_AMD_W42W43 else"research/hk50_spotbrent_w40_w41_protocol.json"
                            if HK_BRENT_W40W41 else
                            "research/natgas_audusd_w38_w39_protocol.json"
                            if NG_AUD_W38W39 else
                            "research/nas100_frozen_w32_w33_replication_protocol.json"
                            if NAS100_FROZEN_W32W33 else
                            "research/us_index_w20_w21_protocol.json"
                            if US_INDEX_W20W21 else
                            "research/crypto_crude_w24_w25_protocol.json"
                            if CRYPTO_CRUDE_HISTORIC else
                            "research/cross_asset_energy_equity_w30_w31_protocol.json"
                            if CROSS_ENERGY_EQUITY else
                            "research/fx_historical_w36_w37_protocol.json"
                            if HISTORIC_W36_W37 else
                            "research/fx_w45_new_mechanisms_protocol.json"),
            "WindowRole":("EXPOSED_2026_W42_W43_NEW_BRENT_AMD_MULTI_CLASS_NOT_INDEPENDENT"
                           if BRENT_AMD_W42W43 else"EXPOSED_2026_W40_W41_NEW_HK_BRENT_CROSS_SESSION_NOT_INDEPENDENT"
                          if HK_BRENT_W40W41 else
                          "EXPOSED_2026_W38_W39_NEW_MULTICLASS_CAUSAL_DEVELOPMENT_NOT_INDEPENDENT"
                          if NG_AUD_W38W39 else
                          "EXPOSED_2026_W32_W33_FIXED_UNCHANGED_NAS_REPLICATION_NOT_INDEPENDENT"
                          if NAS100_FROZEN_W32W33 else
                          "EXPOSED_2026_W20_DEV_W21_CHRONO_SELECTION_NOT_INDEPENDENT"
                          if US_INDEX_W20W21 else
                          "EXPOSED_2026_W24_DEV_W25_CHRONO_SELECTION_NOT_INDEPENDENT"
                          if CRYPTO_CRUDE_HISTORIC else
                          "EXPOSED_2026_W30_DEV_W31_TEMPORAL_SELECTION_NOT_INDEPENDENT"
                          if CROSS_ENERGY_EQUITY else
                          "RETROSPECTIVE_GLOBALLY_EXPOSED_DEV_W36_SELECTION_W37_NOT_CONFIRMATION"
                          if HISTORIC_W36_W37 else
                          "EXPLORATORY_DEVELOPMENT_NOT_INDEPENDENT_CONFIRMATION"),
            "Week":("2026-W42_W43" if BRENT_AMD_W42W43 else"2026-W40_W41" if HK_BRENT_W40W41 else
                     "2026-W38_W39" if NG_AUD_W38W39 else
                     "2026-W32_W33" if NAS100_FROZEN_W32W33 else
                     "2026-W20_W21" if US_INDEX_W20W21 else
                     "2026-W24_W25" if CRYPTO_CRUDE_HISTORIC else
                     "2026-W30_W31" if CROSS_ENERGY_EQUITY else
                     "2026-W36_W37" if HISTORIC_W36_W37 else "2026-W45"),
            "HistoricalDevelopmentStartUtcMs":(DECISION_START if
                 (CRYPTO_CRUDE_HISTORIC or CROSS_ENERGY_EQUITY or
                  HISTORIC_W36_W37 or US_INDEX_ANY or NG_AUD_W38W39) else None),
            "HistoricalSelectionStartUtcMs":(
                 int(datetime(2026,10,19,tzinfo=timezone.utc).timestamp()*1000)
                 if BRENT_AMD_W42W43 else
                 int(datetime(2026,10,5,tzinfo=timezone.utc).timestamp()*1000)
                 if HK_BRENT_W40W41 else
                 int(datetime(2026,9,21,tzinfo=timezone.utc).timestamp()*1000)
                 if NG_AUD_W38W39 else
                 int(datetime(2026,8,10,tzinfo=timezone.utc).timestamp()*1000)
                 if NAS100_FROZEN_W32W33 else
                 int(datetime(2026,5,18,tzinfo=timezone.utc).timestamp()*1000)
                 if US_INDEX_W20W21 else
                 int(datetime(2026,6,15,tzinfo=timezone.utc).timestamp()*1000)
                 if CRYPTO_CRUDE_HISTORIC else
                 int(datetime(2026,7,27,tzinfo=timezone.utc).timestamp()*1000)
                 if CROSS_ENERGY_EQUITY else
                 int(datetime(2026,9,7,tzinfo=timezone.utc).timestamp()*1000)
                 if HISTORIC_W36_W37 else None),
            "FutureW46HoldoutNotScored":True,
            "FrozenNas100SessionUtcPreserved":(
                "14:30-19:00 fixed UTC post-open, NOT full cash session"
                if NAS100_FROZEN_W32W33 else None),
            "FrozenW20W21MechanismsAndExitsUnchanged":US_INDEX_ANY,
            "NewRegimeSessionsUtc":(
                ["SpotBrent 10:00-15:00 UTC after 07:00-09:00 2h drive",
                 "AMD.US 17:00-19:30 UTC late US cash"]
                if BRENT_AMD_W42W43 else
                ["HK50 02:15-03:30 UTC; HKEX HKT UTC+8",
                 "SpotBrent 07:00-12:00 UTC"]
                if HK_BRENT_W40W41 else
                ["NatGas 13:00-19:00 UTC","AUDUSD 07:00-09:30 UTC"]
                if NG_AUD_W38W39 else None),
            "TwoFundedConstantSideAndInvertedBenchmarks":(
                NG_AUD_W38W39 or HK_BRENT_W40W41 or BRENT_AMD_W42W43),
            "ReadOnlyOriginalPepperstoneAuthenticated":True,
            "ExplicitViewScopeVerified":False,
            "ViewPermissionRequestPath":"EXISTING_OWNER_READONLY_AUTH_SCOPE_DECLARED_IN_RUN_LOG",
            "InstrumentsRequested":list(SYMBOLS),
            "DevelopmentStartUtcMs":DECISION_START,
            "DevelopmentEndUtcMsExclusive":DECISION_END,
            "M5MarketClocksExpectedPerSymbol":total_clocks,
            "M5HistoricalQuoteClocksMissingOrInvalid":missing_pair_clock,
            "QuoteWindowQueries":quote_windows,
            "ContractsActuallyObservedAtUtcMs":{
                name:terms[name][0]["ObservedAtUtcMs"] for name in SYMBOLS},
            "HistoricContractTariffsAreRetrospectiveScenarios":True,
            "ResearchMechanismsPreregistered":(
                ["SPOTBRENT_EU_MORNING_DRIVE_PULLBACK_CONTINUATION",
                 "AMD_US_LATE_CASH_COMPRESSION_BREAK_TICK_ACCELERATION"]
                if BRENT_AMD_W42W43 else
                ["HK50_HK_CASH_OPEN_RANGE_FALSE_BREAK_REVERSION",
                 "SPOTBRENT_EU_OPEN_RANGE_EXPANSION_CONTINUATION"]
                if HK_BRENT_W40W41 else
                ["NATGAS_US_LIQUIDITY_VOL_COMPRESSION_REVERSION",
                 "AUDUSD_LATE_ASIA_LONDON_SWEEP_FAILURE"]
                if NG_AUD_W38W39 else
                ["NAS100_US_CASH_INDEX_RELATIVE_DISPERSION_FADE",
                 "US500_US_CASH_H1_VOLATILITY_PERSISTENCE"]
                if US_INDEX_ANY else
                ["CRYPTO_M5_LIQUIDITY_WICK_ABSORPTION",
                 "CRUDE_US_SESSION_TICK_ACTIVITY_DRIFT"]
                if CRYPTO_CRUDE_HISTORIC else
                ["ENERGY_BRENT_TO_CRUDE_LAG","AMD_US_OPENING_HOUR_TICKFLOW"]
                if CROSS_ENERGY_EQUITY else
                ["FX_M5_SHOCK_EXHAUSTION_REVERSION",
                 "FX_HIGH_TICK_ACTIVITY_ABSORPTION"] if HISTORIC_W36_W37 else
                ["FX_USD_BREADTH_DELAYED_CATCHUP",
                 "FX_M5_SHOCK_EXHAUSTION_REVERSION"]),
            "EURUSDOnlyUsdToEurConversionContext":(
                 CROSS_ENERGY_EQUITY or CRYPTO_CRUDE_HISTORIC or US_INDEX_ANY or NG_AUD_W38W39 or HK_BRENT_W40W41 or BRENT_AMD_W42W43),
            "SourceAssetClasses":(["energy","equity"]
                    if BRENT_AMD_W42W43 else["index","energy"]
                   if HK_BRENT_W40W41 else
                   ["fx","energy"]
                   if NG_AUD_W38W39 else
                   ["index","index"]
                   if US_INDEX_ANY else
                   ["crypto","energy"]
                   if CRYPTO_CRUDE_HISTORIC else
                   ["energy","energy","equity"]
                   if CROSS_ENERGY_EQUITY else ["FX"]*len(SYMBOLS)),
            "FrozenLegacyM5M15NotRetunedOrPromoted":True,
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
            "NativeProductReceipt":receipt,
            "CounterfactualFamilyAblations":(
                evaluated["FundedAblations"] if
                 (CROSS_ENERGY_EQUITY or CRYPTO_CRUDE_HISTORIC or US_INDEX_ANY or NG_AUD_W38W39 or HK_BRENT_W40W41 or BRENT_AMD_W42W43)
                else evaluated["CounterfactualAblation"])
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
        safe=str(exc)
        code=safe if (isinstance(exc,(MarketReplayError,CaptureContractError))
            and safe.isupper() and safe.replace("_","").isalnum()
            and len(safe)<160) else (
            "ORIGINAL_OPENAPI_PRODUCT_FAILED_"+type(exc).__name__)
        print(code,flush=True)
        return 1

if __name__=="__main__":
    sys.exit(main())
