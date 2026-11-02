"""Bounded read-only source admission. No token refresh or trading requests."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import need, decode_bars
from .custody import seal

def secret(name):
    value = os.environ.get(name, "").strip()
    need(bool(value), "CONFIGURATION_MISSING")
    return value

def normalize_binding(value):
    """Accept exact SHA-256 or tightly delimited copies of the same 64-hex value.

    Never discover/select an account from available accounts or accept a partial hash.
    A different or malformed fingerprint must stop account authentication.
    """
    import re
    value = value.strip()
    if "=" in value:
        label, value = value.split("=", 1)
        need(label.strip() in {"ACCOUNT_FINGERPRINT_SHA256", "R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256"}, "ACCOUNT_BINDING_INVALID")
        value = value.strip()
    if value[:1] in ("'", '"', "`") or value[-1:] in ("'", '"', "`"):
        need(len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"', "`"), "ACCOUNT_BINDING_INVALID")
        value = value[1:-1].strip()
    if value.lower().startswith("sha256:"):
        value = value[7:]
    elif value.lower().startswith("0x"):
        value = value[2:]
    need(re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None, "ACCOUNT_BINDING_INVALID")
    return value.lower()

def authenticate(t):
    client = secret("R3_CTRADER_CLIENT_ID")
    client_secret = secret("R3_CTRADER_CLIENT_SECRET")
    token = secret("R3_CTRADER_ACCESS_TOKEN")
    expected = secret("R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256")
    reply = t.request(m.ProtoOAApplicationAuthReq(clientId=client, clientSecret=client_secret))
    need(isinstance(reply, m.ProtoOAApplicationAuthRes), "APPLICATION_AUTH_FAILED")
    print("APPLICATION_AUTH_VERIFIED", flush=True)
    accounts = t.request(m.ProtoOAGetAccountListByAccessTokenReq(accessToken=token))
    need(isinstance(accounts, m.ProtoOAGetAccountListByAccessTokenRes), "TOKEN_INVALID_OR_EXPIRED")
    need(accounts.HasField("permissionScope") and accounts.permissionScope == e.SCOPE_VIEW, "SCOPE_NOT_EXPLICIT_VIEW")
    print("ACCESS_TOKEN_EXPLICIT_VIEW_VERIFIED", flush=True)
    # Authenticate the application/token independently, but never select or
    # authenticate an account until the existing binding is well formed.
    expected = normalize_binding(expected)
    matches = [a for a in accounts.ctidTraderAccount if hashlib.sha256(f"ctrader-account:{int(a.ctidTraderAccountId)}".encode("ascii")).hexdigest() == expected]
    need(len(matches) == 1 and matches[0].HasField("isLive") and matches[0].isLive, "ACCOUNT_BINDING_FAILED")
    account = matches[0].ctidTraderAccountId
    reply = t.request(m.ProtoOAAccountAuthReq(ctidTraderAccountId=account, accessToken=token))
    need(isinstance(reply, m.ProtoOAAccountAuthRes) and reply.ctidTraderAccountId == account, "ACCOUNT_AUTH_FAILED")
    print("BOUND_LIVE_ACCOUNT_AUTH_VERIFIED", flush=True)
    return account

def run(output):
    # All credential presence checks happen before the first connection.
    for name in ("R3_CTRADER_CLIENT_ID", "R3_CTRADER_CLIENT_SECRET", "R3_CTRADER_ACCESS_TOKEN", "R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256"):
        secret(name)
    t = StdlibCTraderTransport()
    raw = []
    def request(q, cls, account):
        need(len(raw) < 256, "SOURCE_REQUEST_BUDGET")
        r = t.request(q)
        need(isinstance(r, cls) and r.IsInitialized(), "BROKER_RESPONSE_INVALID")
        need(r.ctidTraderAccountId == account, "BROKER_ACCOUNT_MISMATCH")
        raw.append({"type":type(r).__name__, "protobuf":base64.b64encode(r.SerializeToString()).decode()})
        return r
    try:
        account = authenticate(t)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes, account)
        need(trader.trader.HasField("brokerName") and "pepperstone" in trader.trader.brokerName.casefold(), "BROKER_NOT_VERIFIED")
        universe = request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account, includeArchivedSymbols=False), m.ProtoOASymbolsListRes, account)
        # Integration sample only, not the final eligible universe or a strategy.
        targets = [s for s in universe.symbol if s.enabled and s.symbolName in {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD"}]
        need(bool(targets), "NO_SAMPLE_SYMBOLS")
        end_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end = int(end_dt.timestamp()*1000)-1
        start = int((end_dt-timedelta(days=7)).timestamp()*1000)
        normalized = []
        for s in targets:
            detail = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account, symbolId=[s.symbolId]), m.ProtoOASymbolByIdRes, account)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==s.symbolId, "SYMBOL_DETAIL_MISMATCH")
            def window(lo, hi, depth=0):
                need(depth <= 24, "PAGINATION_LIMIT")
                r = request(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account, symbolId=s.symbolId, period=e.H1, fromTimestamp=lo, toTimestamp=hi), m.ProtoOAGetTrendbarsRes, account)
                need(r.period==e.H1 and (not r.HasField("symbolId") or r.symbolId==s.symbolId), "BAR_RESPONSE_BINDING")
                need(r.HasField("hasMore"), "BAR_COMPLETENESS_UNKNOWN")
                if r.hasMore:
                    need(hi > lo, "UNRESOLVABLE_TRUNCATION")
                    mid=(lo+hi)//2
                    return window(lo,mid,depth+1)+window(mid+1,hi,depth+1)
                # Decode window membership separately; completion uses global horizon.
                return decode_bars(r.trendbar,lo,hi,0)
            rows=window(start,end)
            need(len({r[0] for r in rows})==len(rows), "DUPLICATE_BAR")
            for row in rows:
                row[1]=row[0]+3600000
                if row[1] <= end:
                    normalized.append(dict(symbol=s.symbolName,openTime=row[0],availableTime=row[1],open=row[2],high=row[3],low=row[4],close=row[5],tickVolume=row[6]))
        need(bool(normalized), "NO_COMPLETE_BARS")
        bundle={"schema":1,"source":"Pepperstone-cTrader-OpenAPI", "readOnly":True, "start":start,"end":end,"bars":sorted(normalized,key=lambda x:(x["symbol"],x["openTime"])),"raw":raw}
        # Private ephemeral files only; C# receipt is sealed with the originals.
        with tempfile.TemporaryDirectory(prefix="mxm-private-") as folder:
            p=Path(folder)/"source.json"; p.write_text(json.dumps(bundle,sort_keys=True)); p.chmod(0o600)
            receipt=Path(folder)/"receipt.json"
            clean_env={k:v for k,v in os.environ.items() if not k.startswith(("R3_", "CTRADER_", "MXM_V4_"))}
            result=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",str(p),str(receipt)],env=clean_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            need(result.returncode==0 and receipt.exists(),"CSHARP_SOURCE_RECEIPT_FAILED")
            bundle["csharpReceipt"]=json.loads(receipt.read_text())
        cipher=seal(json.dumps(bundle,sort_keys=True).encode(),Path(__file__).with_name("custody_public.pem").read_bytes())
        output.mkdir(parents=True,exist_ok=True)
        (output/"source.envelope.json").write_bytes(cipher)
        (output/"receipt.public.json").write_text(json.dumps({"schema":1,"status":"SOURCE_RECEIPT_ONLY","ciphertextSha256":hashlib.sha256(cipher).hexdigest(),"ordersSubmitted":0,"economicQualification":False}))
    finally:
        t.close()

if __name__ == "__main__":
    try:
        run(Path("sealed-output"))
        print("READ_ONLY_SOURCE_CSHARP_RECEIPT_SEALED; NOT_ECONOMIC_QUALIFICATION")
    except Exception as exc:
        # Only our allowlisted constant codes; never broker payloads/tracebacks.
        from .guard import CaptureContractError
        print(str(exc) if isinstance(exc,CaptureContractError) and str(exc).isupper() and str(exc).replace('_','').isalnum() else "COLLECTION_FAILED_DETAIL_WITHHELD")
        sys.exit(1)
