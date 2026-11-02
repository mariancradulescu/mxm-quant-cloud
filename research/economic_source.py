"""Predeclared broad authentic economic research tape. No orders or token refresh.

Source differs completely from the closed H1 predictor. This is DATA DEVELOPMENT,
not independent validation; historical model results never guide selection.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .collect import authenticate, secret
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need, decode_bars
from .custody import seal_new
from .custody_new import checked_public

# Fixed before any new source pull; no cherry-picking after seeing outcomes.
UNIVERSE=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD")
RESOLUTIONS=(("H4",e.H4,240,370,28),("M15",e.M15,15,14,4))
MAX_BROKER_REQUESTS=220

def snapshot_contract(symbol):
    """Broker's own raw fields, with missing values remaining None, not zero."""
    fields=("minVolume","stepVolume","maxVolume","lotSize","digits",
       "pipPosition","preciseTradingCommissionRate","preciseMinCommission",
       "commissionType","minCommissionType","pnlConversionFeeRate",
       "swapLong","swapShort","swapCalculationType","leverageId",
       "tradingMode","swapPeriod","swapTime","skipSWAPPeriods",
       "maxExposure","scheduleTimeZone")
    return {f:(getattr(symbol,f) if symbol.HasField(f) else None)
            for f in fields}

def _windows(start,stop,days):
    lo=start
    while lo<stop:
        hi=min(lo+days*86400000,stop)
        yield lo,hi-1
        lo=hi

def _request(t,q,cls,account,raw):
    need(len(raw)<MAX_BROKER_REQUESTS,"ECONOMIC_SOURCE_REQUEST_BUDGET")
    r=t.request(q)
    need(isinstance(r,cls) and r.IsInitialized() and
         r.ctidTraderAccountId==account,"ECONOMIC_BROKER_RESPONSE_BINDING")
    raw.append({"type":type(r).__name__,
                "protobuf":base64.b64encode(r.SerializeToString()).decode()})
    return r

def run(output):
    for name in ("R3_CTRADER_CLIENT_ID","R3_CTRADER_CLIENT_SECRET",
                 "R3_CTRADER_ACCESS_TOKEN"):
        secret(name)
    run_id=os.environ.get("GITHUB_RUN_ID","")
    recipient=checked_public(Path("new-source-recipient"),run_id)
    transport=StdlibCTraderTransport()
    raw=[]
    try:
        account=authenticate(transport)
        trader=_request(transport,m.ProtoOATraderReq(ctidTraderAccountId=account),
                       m.ProtoOATraderRes,account,raw)
        need(trader.trader.HasField("brokerName") and
             "pepperstone" in trader.trader.brokerName.casefold(),
             "ECONOMIC_BROKER_NOT_PEPPERSTONE")
        universe=_request(transport,m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes,account,raw)
        symbol_lookup={s.symbolName:s for s in universe.symbol if s.enabled}
        choices=[symbol_lookup[name] for name in UNIVERSE if name in symbol_lookup]
        need(len(choices)>=2,"ECONOMIC_UNIVERSE_TOO_SMALL")

        # Fixed UTC daily boundary; includes 370 days H4 to tolerate initial
        # weekend boundary, and an independent 14-day M15 execution window.
        stop_dt=datetime.now(timezone.utc).replace(
            hour=0,minute=0,second=0,microsecond=0)
        stop=int(stop_dt.timestamp()*1000)
        bars=[]; contracts={}
        for s in choices:
            detail=_request(transport,m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[s.symbolId]),
                m.ProtoOASymbolByIdRes,account,raw)
            need(len(detail.symbol)==1 and
                 detail.symbol[0].symbolId==s.symbolId,
                 "ECONOMIC_SYMBOL_DETAIL_MISMATCH")
            contracts[s.symbolName]=snapshot_contract(detail.symbol[0])
            for period_name,period,minutes,lookback,chunk_days in RESOLUTIONS:
                seen=set(); rows=[]
                first=stop-lookback*86400000
                def window(lo,hi,depth=0):
                    need(depth<20,"ECONOMIC_HISTORY_DEPTH_LIMIT")
                    response=_request(transport,m.ProtoOAGetTrendbarsReq(
                        ctidTraderAccountId=account,symbolId=s.symbolId,
                        period=period,fromTimestamp=lo,toTimestamp=hi),
                        m.ProtoOAGetTrendbarsRes,account,raw)
                    need(response.period==period and
                        (not response.HasField("symbolId") or
                         response.symbolId==s.symbolId) and
                        response.HasField("hasMore"),
                        "ECONOMIC_BAR_RESPONSE_INVALID")
                    if response.hasMore:
                        need(hi>lo,"ECONOMIC_HISTORY_UNRESOLVABLE_TRUNCATION")
                        middle=(lo+hi)//2
                        return window(lo,middle,depth+1)+window(middle+1,hi,depth+1)
                    return decode_bars(response.trendbar,lo,hi,0)
                for lo,hi in _windows(first,stop,chunk_days):
                    for row in window(lo,hi):
                        stamp=row[0]
                        # Last unfinished bar is inadmissible.
                        if stamp+minutes*60000>stop:continue
                        need(stamp not in seen,"ECONOMIC_BAR_DUPLICATE")
                        seen.add(stamp)
                        rows.append({"symbol":s.symbolName,"resolution":period_name,
                            "periodMinutes":minutes,"openTime":stamp,
                            "availableTime":stamp+minutes*60000,
                            "open":row[2],"high":row[3],"low":row[4],
                            "close":row[5],"tickVolume":row[6]})
                bars.extend(sorted(rows,key=lambda x:x["openTime"]))
        need(bool(bars),"ECONOMIC_NO_AUTHENTIC_BARS")
        tape={"schema":"mxm-econ-source-v2","source":"Pepperstone-cTrader-OpenAPI",
              "readOnly":True,"captureEnd":stop,
              "predeclaredUniverse":list(UNIVERSE),
              "predeclaredResolutions":[x[0] for x in RESOLUTIONS],
              "developmentDataOnly":True,
              "brokerContract":contracts,
              "traderRaw":base64.b64encode(trader.SerializeToString()).decode(),
              "bars":bars,"raw":raw}
        with tempfile.TemporaryDirectory(prefix="mxm-economic-private-") as tmp:
            inp=Path(tmp)/"source.json"
            receipt=Path(tmp)/"receipt.json"
            inp.write_text(json.dumps(tape,sort_keys=True))
            inp.chmod(0o600)
            env={k:v for k,v in os.environ.items() if not k.startswith(
                ("R3_","CTRADER_","MXM_V4_"))}
            result=subprocess.run(["dotnet",
                "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                str(inp),str(receipt),"--economic-source"],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
            need(result.returncode==0 and receipt.exists(),
                 "ECONOMIC_NATIVE_CSHARP_RECONCILIATION_FAILED")
            tape["csharpReceipt"]=json.loads(receipt.read_text())
        cipher=seal_new(json.dumps(tape,sort_keys=True).encode(),
                        recipient,run_id)
        output.mkdir(parents=True,exist_ok=True)
        (output/"source.envelope.json").write_bytes(cipher)
        (output/"receipt.public.json").write_text(json.dumps({
            "schema":2,"status":"NEW_ECONOMIC_SOURCE_V2_SEALED",
            "ciphertextSha256":hashlib.sha256(cipher).hexdigest(),
            "sourceFamily":"MULTI_RESOLUTION_COST_METADATA_DEVELOPMENT",
            "ordersSubmitted":0,"economicQualification":False},sort_keys=True))
        print("ECONOMIC_MULTIRESOLUTION_SOURCE_AND_CSHARP_RECEIPT_SEALED")
    finally:
        transport.close()

if __name__=="__main__":
    try:
        run(Path("sealed-output"))
    except Exception as exc:
        from .guard import CaptureContractError
        print(str(exc) if isinstance(exc,CaptureContractError) and
              str(exc).isupper() and str(exc).replace("_","").isalnum()
              else "ECONOMIC_COLLECT_FAILED_DETAIL_WITHHELD")
        sys.exit(1)
