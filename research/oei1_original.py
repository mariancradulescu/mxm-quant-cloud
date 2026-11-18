"""OEI1 new read-only original 4-class source. Never invokes any closed study."""
import base64, hashlib, json, os, time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars, decode_side
from .custody import seal_new
from .custody_new import checked_public

START = int(datetime(2026, 8, 17, tzinfo=timezone.utc).timestamp() * 1000)
END = START + 84 * 86400000
DAY, MINUTE = 86400000, 60000
SYMBOLS = ("EURUSD", "ETHUSD", "SpotBrent", "US500")
PROTOCOL = Path("research/OEI1_FROZEN_INTEGRATED_3PHASE_20261118.md")

def need(ok, reason):
    if not ok:
        raise ValueError("OEI1_" + reason)

def main():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    protected = Path("oei1-encrypted")
    public = Path("oei1-public")
    protected.mkdir(exist_ok=True)
    public.mkdir(exist_ok=True)
    summary = dict(Study="OEI1", OriginalRun=run, ProtocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
                   Requests=0, Counts={}, Exclusions={}, SourceChunks=[], OrdersSubmitted=0,
                   CloudActivated=False, IndependentConfirmation=False, Qualified=False,
                   SourceStartUtc=START, SourceEndUtc=END)
    raw = []
    tape = dict(Start=START, End=END, Symbols=[])
    transport = StdlibCTraderTransport()
    count = 0
    def write():
        summary["Requests"] = count
        (public/"source.json").write_text(json.dumps(summary, indent=2)+"\n")
    def seal(tag):
        if not raw:
            return
        clear = json.dumps(raw, separators=(",", ":")).encode()
        cipher = seal_new(clear, recipient, run)
        (protected/(tag+".enc")).write_bytes(cipher)
        summary["SourceChunks"].append(dict(Name=tag, PlainSha256=hashlib.sha256(clear).hexdigest(),
                                             CipherSha256=hashlib.sha256(cipher).hexdigest(), Responses=len(raw)))
        raw.clear()
        write()
    try:
        account = authenticate(transport)
        def request(q, klass, historical=False):
            nonlocal count
            need(count < 9000, "ORIGINAL_READONLY_REQUEST_BUDGET")
            require_read_only_request(q)
            if historical:
                time.sleep(.23)
            res = transport.request(q)
            count += 1
            raw.append(dict(Type=type(q).__name__, ResponseType=type(res).__name__,
                            Req=base64.b64encode(q.SerializeToString()).decode(),
                            Res=base64.b64encode(res.SerializeToString()).decode()))
            if (klass is m.ProtoOAGetTickDataRes and
                type(res) is m.ProtoOAErrorRes and
                res.errorCode == "NO_QUOTES" and res.ctidTraderAccountId == account):
                return klass(ctidTraderAccountId=account, hasMore=False)
            need(type(res) is klass and res.IsInitialized()
                 and res.ctidTraderAccountId == account, "AUTHENTIC_BROKER_RESPONSE_BINDING")
            return res
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes)
        assets_reply = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)
        assets = {x.assetId: x.name for x in assets_reply.asset}
        need("pepperstone" in trader.trader.brokerName.lower()
             and assets.get(trader.trader.depositAssetId) == "EUR", "BROKER_IDENTITY_EUR")
        roster_reply = request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
        roster = {x.symbolName:x for x in roster_reply.symbol if x.enabled}
        detail_cache = {}
        for name in SYMBOLS:
            if name not in roster:
                summary["Exclusions"][name] = "UNAVAILABLE_ENABLED_SYMBOL"
                continue
            light = roster[name]
            if assets.get(light.quoteAssetId) != "USD":
                summary["Exclusions"][name] = "QUOTE_NOT_USD"
                continue
            details = request(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account, symbolId=[light.symbolId]), m.ProtoOASymbolByIdRes)
            need(len(details.symbol) == 1 and details.symbol[0].symbolId == light.symbolId,
                 "CONTRACT_ID_BINDING")
            c = details.symbol[0]
            if (c.tradingMode != 0 or not c.enableShortSelling or
                not c.HasField("preciseTradingCommissionRate") or
                not c.HasField("preciseMinCommission") or
                not c.HasField("swapTime") or not c.HasField("swapPeriod") or
                not c.HasField("pnlConversionFeeRate") or
                c.minVolume <= 0 or c.stepVolume <= 0 or c.lotSize <= 0):
                summary["Exclusions"][name] = "CURRENT_LEGAL_COST_FUNDING_CONTRACT_MISSING"
                continue
            # No assumption of zero financing; only a session strictly before authentic charge.
            charge = int(c.swapTime)
            if (c.swapPeriod < 24 or 810 <= charge <= 930 or
                c.minVolume > c.maxVolume):
                summary["Exclusions"][name] = "FINANCING_OR_VOLUME_SCHEDULE_UNSAFE"
                continue
            margin = request(m.ProtoOAExpectedMarginReq(
                ctidTraderAccountId=account, symbolId=light.symbolId,
                volume=[c.minVolume]), m.ProtoOAExpectedMarginRes)
            need(len(margin.margin) == 1 and margin.margin[0].volume == c.minVolume
                 and margin.HasField("moneyDigits"), "DIRECTIONAL_MARGIN_UNKNOWN")
            margin_eur = Decimal(max(margin.margin[0].buyMargin,
                                     margin.margin[0].sellMargin)) / (Decimal(10) ** margin.moneyDigits)
            if not 0 < margin_eur < 300:
                summary["Exclusions"][name] = "MINIMUM_MARGIN_NOT_FUNDED_300EUR"
                continue
            detail_cache[name] = (light, c, margin_eur)
        seal("verified-contract-terms")
        need("EURUSD" in detail_cache, "EURUSD_CONVERSION_SOURCE_UNAVAILABLE")
        if len(detail_cache) < 3:
            summary["Status"] = "PRESOURCE_STOP_BELOW_THREE_CLASSES"
            write()
            return
        def side_ticks(symbol_id, side, lo, hi):
            res = request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                symbolId=symbol_id, type=side, fromTimestamp=lo, toTimestamp=hi),
                m.ProtoOAGetTickDataRes, True)
            if res.hasMore:
                need(hi > lo, "UNRESOLVED_SINGLE_MS_TICK_TRUNCATION")
                midpoint = (lo+hi)//2
                return side_ticks(symbol_id, side, lo, midpoint) + side_ticks(symbol_id, side, midpoint+1, hi)
            return decode_side(res.tickData, lo, hi)
        for name in SYMBOLS:
            if name not in detail_cache:
                continue
            light,c, margin_eur = detail_cache[name]
            market = dict(Name=name, Class={"EURUSD":"fx","ETHUSD":"crypto","SpotBrent":"energy","US500":"index"}[name],
                          MinMarginEur=str(margin_eur), MinimumUnits=str(Decimal(c.minVolume)/100),
                          TickSize=str(Decimal(10)**-c.digits),
                          ContractProto=base64.b64encode(c.SerializeToString()).decode(),
                          Days=[], M1Count=0, ContractObservedAt=int(time.time()*1000))
            summary["Counts"][name] = dict(M1=0, BID=0, ASK=0, Days=0)
            for d in range(START, END, DAY):
                if datetime.fromtimestamp(d/1000,timezone.utc).weekday() >= 5:
                    continue
                lo, hi = d+810*MINUTE, d+930*MINUTE-1
                # One two-hour segment can exceed 500 bars. Split into bounded M1 requests.
                bars = []
                for barlo in range(lo-30*MINUTE, hi, 450*MINUTE):
                    barhi = min(barlo+450*MINUTE-1,hi)
                    response = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                        symbolId=light.symbolId, period=e.M1,
                        fromTimestamp=barlo, toTimestamp=barhi), m.ProtoOAGetTrendbarsRes,True)
                    need(response.period == e.M1 and not response.hasMore,
                         "M1_SOURCE_TRUNCATED_"+name)
                    bars.extend(decode_bars(response.trendbar, barlo-60000,barhi,1))
                bids,asks = [],[]
                for a in range(lo,hi+1,20*MINUTE):
                    b=min(a+20*MINUTE-1,hi)
                    bids.extend(side_ticks(light.symbolId,e.BID,a,b))
                    asks.extend(side_ticks(light.symbolId,e.ASK,a,b))
                market["Days"].append(dict(Start=d, Bid=bids,Ask=asks))
                market["M1Count"] += len(bars)
                for key,n in (("M1",len(bars)),("BID",len(bids)),("ASK",len(asks))):
                    summary["Counts"][name][key] += n
                summary["Counts"][name]["Days"] += 1
                # Original protobuf custody segmented by market/day, including source gaps.
                seal(name+"-"+str(d))
                if summary["Counts"][name]["Days"] % 10 == 0:
                    print("OEI1_SOURCE",name,summary["Counts"][name],flush=True)
            tape["Symbols"].append(market)
        # Strict source scope: no guessed or substituted instruments.
        if len(tape["Symbols"]) < 3:
            summary["Status"]="PRESOURCE_STOP_BELOW_THREE_COLLECTED_CLASSES"
            write()
            return
        encoded = json.dumps(tape,separators=(",", ":")).encode()
        cipher = seal_new(encoded,recipient,run)
        (protected/"oei1-native-tape.enc").write_bytes(cipher)
        summary["SourceSha256"]=hashlib.sha256(encoded).hexdigest()
        summary["SourceCipherSha256"]=hashlib.sha256(cipher).hexdigest()
        summary["SourceSymbols"]=[x["Name"] for x in tape["Symbols"]]
        write()
        # New integrated 3-phase evaluation; no old source/economics runner invoked.
        from .oei1_integrated import run
        result = run(tape)
        result["SourceSha256"] = summary["SourceSha256"]
        result["OriginalRun"] = run_id = int(run_number) if False else int(os.environ["GITHUB_RUN_ID"])
        result["OriginalProtocolSha256"] = summary["ProtocolSha256"]
        result["SourceCounts"] = summary["Counts"]
        result["SourceExclusions"] = summary["Exclusions"]
        result["OrdersSubmitted"] = 0
        result["CloudActivated"] = False
        result["IndependentConfirmation"] = False
        result["Qualified"] = False
        (public/"economic.json").write_text(json.dumps(result,indent=2)+"\n")
        summary["Status"]="COMPLETED_INTEGRATED_3PHASE_RESEARCH"
        summary["Completed"]=True
        write()
    except Exception as exc:
        summary["FailureType"] = type(exc).__name__
        if raw:
            seal("failed-readonly-checkpoint")
        write()
        raise
    finally:
        transport.close()

if __name__ == "__main__":
    main()
