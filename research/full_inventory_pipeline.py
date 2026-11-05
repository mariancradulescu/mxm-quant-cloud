"""Bounded full-symbol cTrader Open API inventory, existing custody v2 only.

The entire returned non-archived symbol list is preserved. A fixed maximum of
96 category-stratified visible symbols receives *current* contract/min-margin
queries. Unqueried != unavailable; static margin != funded NET or permission.
No trades, token refresh, or direct broker API.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from .full_inventory_core import (
    normalize_account_inventory, classify_contract_and_min_margin,
    public_receipt, InventoryIntegrityError)

SCHEMA = "mxm-full-account-inventory-raw-v1"
MAX_CONTRACT_PROBES = 96
MAX_REQUESTS = 3 + 2 * MAX_CONTRACT_PROBES

def need(value, code):
    if not value:
        raise InventoryIntegrityError(code)

def select_probe_ids(rows, limit=MAX_CONTRACT_PROBES):
    """Outcome-blind round robin by account-reported symbol category."""
    need(0 <= limit <= MAX_CONTRACT_PROBES, "INVENTORY_PROBE_LIMIT_INVALID")
    groups = {}
    for row in rows:
        if row["visible"] is True and row["symbolName"]:
            groups.setdefault(row["symbolCategoryId"], []).append(row["symbolId"])
    for group in groups.values():
        group.sort()
    cats = sorted(groups, key=lambda c: -1 if c is None else c)
    chosen = []
    while len(chosen) < limit and any(groups.values()):
        for cat in cats:
            if groups[cat] and len(chosen) < limit:
                chosen.append(groups[cat].pop(0))
    return chosen

def _raw_record(q,r):
    enc=lambda item:base64.b64encode(item.SerializeToString()).decode("ascii")
    return {"requestType":type(q).__name__,"requestProtobuf":enc(q),
            "type":type(r).__name__,"protobuf":enc(r)}

def _read_raw(raw, module, readonly):
    allow={"ProtoOATraderReq","ProtoOAAssetListReq","ProtoOASymbolsListReq",
           "ProtoOASymbolByIdReq","ProtoOAExpectedMarginReq"}
    pairs=[]
    for item in raw:
        need(set(item)=={"requestType","requestProtobuf","type","protobuf"},"INVENTORY_RAW_SHAPE")
        need(item["requestType"] in allow,"INVENTORY_RAW_REQUEST_TYPE")
        q=getattr(module,item["requestType"])()
        r=getattr(module,item["type"])()
        q.ParseFromString(base64.b64decode(item["requestProtobuf"],validate=True))
        r.ParseFromString(base64.b64decode(item["protobuf"],validate=True))
        readonly(q)
        need(q.IsInitialized() and r.IsInitialized(),"INVENTORY_RAW_PROTO_INVALID")
        pairs.append((q,r))
    return pairs

def from_pairs(pairs, m, historic_commitment, limit=MAX_CONTRACT_PROBES):
    """Reconstruct and bind ALL responses to original approved cTrader account."""
    need(3 <= len(pairs) <= MAX_REQUESTS,"INVENTORY_REQUEST_COUNT")
    tq,tr=pairs[0];aq,ar=pairs[1];lq,lr=pairs[2]
    need(type(tq) is m.ProtoOATraderReq and type(tr) is m.ProtoOATraderRes,
         "INVENTORY_TRADER_PAIR_TYPE")
    need(type(aq) is m.ProtoOAAssetListReq and type(ar) is m.ProtoOAAssetListRes,
         "INVENTORY_ASSET_PAIR_TYPE")
    need(type(lq) is m.ProtoOASymbolsListReq and type(lr) is m.ProtoOASymbolsListRes,
         "INVENTORY_LIST_PAIR_TYPE")
    aid=int(tr.ctidTraderAccountId)
    need(aid>0 and all(int(x.ctidTraderAccountId)==aid for x in (tq,aq,ar,lq,lr)),
         "INVENTORY_ORIGINAL_ACCOUNT_MISMATCH")
    fingerprint=hashlib.sha256(f"ctrader-account:{aid}".encode("ascii")).hexdigest()
    need(hashlib.sha256(fingerprint.encode("ascii")).hexdigest()==historic_commitment,
         "INVENTORY_HISTORIC_BINDING_MISMATCH")
    need(lq.HasField("includeArchivedSymbols") and lq.includeArchivedSymbols is False,
         "INVENTORY_ARCHIVE_SCOPE")
    need(tr.trader.HasField("brokerName") and
         "pepperstone" in tr.trader.brokerName.lower(),"INVENTORY_BROKER_MISMATCH")
    assets={int(x.assetId):x.name for x in ar.asset}
    need(assets.get(int(tr.trader.depositAssetId))=="EUR","INVENTORY_CURRENCY_MISMATCH")
    rows=normalize_account_inventory(lr,ar,aid)
    ids=select_probe_ids(rows,limit)
    by_id={x["symbolId"]:x for x in rows}
    pointer=3
    for sid in ids:
        need(pointer<len(pairs),"INVENTORY_DETAIL_MISSING")
        dq,dr=pairs[pointer];pointer+=1
        need(type(dq) is m.ProtoOASymbolByIdReq and
             type(dr) is m.ProtoOASymbolByIdRes and
             int(dq.ctidTraderAccountId)==aid and int(dr.ctidTraderAccountId)==aid and
             list(dq.symbolId)==[sid] and len(dr.symbol)==1 and
             int(dr.symbol[0].symbolId)==sid,"INVENTORY_DETAIL_BINDING")
        c=dr.symbol[0];row=by_id[sid]
        row["tradingModeExplicit"]=bool(c.HasField("tradingMode"))
        row["tradingModeValue"]=int(c.tradingMode)
        if int(c.tradingMode)!=0:
            row["contractStatus"]="CLOSE_ONLY_OR_DISABLED"
            continue
        if any(not c.HasField(k) for k in ("minVolume","stepVolume","maxVolume")) or (
            c.minVolume<=0 or c.stepVolume<=0 or c.maxVolume<c.minVolume):
            row["contractStatus"]="VOLUME_GRID_UNKNOWN"
            continue
        row["contractMinVolumeCents"]=str(c.minVolume)
        row["contractStepVolumeCents"]=str(c.stepVolume)
        row["contractMaxVolumeCents"]=str(c.maxVolume)
        row["minVolumeUnits"]=str(Decimal(c.minVolume)/100)
        row["contractStatus"]="CONTRACT_ONLY_MARGIN_NOT_QUERIED"
        need(pointer<len(pairs),"INVENTORY_MARGIN_MISSING")
        mq,mr=pairs[pointer];pointer+=1
        need(type(mq) is m.ProtoOAExpectedMarginReq and
             type(mr) is m.ProtoOAExpectedMarginRes and
             int(mq.ctidTraderAccountId)==aid and
             int(mr.ctidTraderAccountId)==aid and int(mq.symbolId)==sid and
             list(mq.volume)==[c.minVolume],"INVENTORY_MARGIN_PAIR_BINDING")
        if not c.HasField("tradingMode"):
            # Classification uses effective official proto default; preserve
            # provenance separately without pretending the wire field was explicit.
            copied=m.ProtoOASymbolByIdRes()
            copied.CopyFrom(dr)
            copied.symbol[0].tradingMode=0
            checked=classify_contract_and_min_margin(row,copied,mr,aid)
        else:
            checked=classify_contract_and_min_margin(row,dr,mr,aid)
        checked.update({
            "tradingModeExplicit":row["tradingModeExplicit"],
            "tradingModeValue":row["tradingModeValue"],
            "contractMinVolumeCents":row["contractMinVolumeCents"],
            "contractStepVolumeCents":row["contractStepVolumeCents"],
            "contractMaxVolumeCents":row["contractMaxVolumeCents"]})
        by_id[sid]=checked
    need(pointer==len(pairs),"INVENTORY_UNEXPECTED_RAW_RESPONSES")
    return {"rows":sorted(by_id.values(),key=lambda x:x["symbolId"]),
            "probes":ids,"requestCount":len(pairs),
            "originalAccountBindingRechecked":True}

def collect():
    """Authentic read-only collector; all secrets stay in existing GH environment."""
    from .collect import authenticate,secret,HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
    from .ctrader_transport import StdlibCTraderTransport
    from .ctrader_proto import OpenApiMessages_pb2 as m
    from .guard import require_read_only_request
    from .custody import seal_new
    from .custody_new import checked_public
    run=os.environ.get("GITHUB_RUN_ID","")
    need(run.isdecimal() and int(run)>0,"INVENTORY_GITHUB_RUN_ID_MISSING")
    for key in ("R3_CTRADER_CLIENT_ID","R3_CTRADER_CLIENT_SECRET","R3_CTRADER_ACCESS_TOKEN"):
        secret(key)
    recipient=checked_public(Path("new-source-recipient"),run)
    raw=[];pairs=[];transport=StdlibCTraderTransport()
    try:
        account=authenticate(transport)
        def req(q,kind):
            require_read_only_request(q)
            need(len(raw)<MAX_REQUESTS,"INVENTORY_REQUEST_BUDGET")
            r=transport.request(q)
            need(type(r) is kind and r.IsInitialized() and
                 int(r.ctidTraderAccountId)==int(q.ctidTraderAccountId)==int(account),
                 "INVENTORY_RESPONSE_ACCOUNT_OR_TYPE")
            raw.append(_raw_record(q,r))
            pairs.append((q,r))
            return r
        req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        listing=req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        rows=normalize_account_inventory(listing,assets,account)
        for sid in select_probe_ids(rows):
            full=req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(full.symbol)==1 and full.symbol[0].symbolId==sid,
                 "INVENTORY_DETAIL_BINDING")
            c=full.symbol[0]
            if int(c.tradingMode)!=0 or any(
                not c.HasField(k) for k in ("minVolume","stepVolume","maxVolume")) or (
                c.minVolume<=0 or c.stepVolume<=0 or c.maxVolume<c.minVolume):
                continue
            req(m.ProtoOAExpectedMarginReq(
                ctidTraderAccountId=account,symbolId=sid,volume=[c.minVolume]),
                m.ProtoOAExpectedMarginRes)
        audit=from_pairs(pairs,m,HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT)
        bundle={"schema":SCHEMA,"readOnly":True,"runId":run,
                "captureUnixSeconds":int(time.time()),"raw":raw,
                "rows":audit["rows"],"probes":audit["probes"],
                "accountBindingVerified":True,"ordersSubmitted":0,
                "tradingActivated":False,"economicQualification":False}
        encrypted=seal_new(json.dumps(bundle,sort_keys=True).encode("utf-8"),
                           recipient,run)
        target=Path("sealed-output")
        target.mkdir(parents=True,exist_ok=True)
        (target/"source.envelope.json").write_bytes(encrypted)
        (target/"receipt.public.json").write_text(json.dumps({
            "schema":SCHEMA,"runId":run,"complete":True,
            "sha256":hashlib.sha256(encrypted).hexdigest(),"ordersSubmitted":0,
            "fullAccountInstrumentCount":len(rows),
            "historicalCostsCertified":False},sort_keys=True)+"\n")
        print("FULL_ACCOUNT_INVENTORY_SEALED_ONLY",flush=True)
    finally:
        transport.close()

def readback():
    """Rebuild sealed request/response pairs independently, publish redacted receipt."""
    from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
    from .ctrader_proto import OpenApiMessages_pb2 as m
    from .guard import require_read_only_request
    from .custody import unseal_new
    run=os.environ.get("GITHUB_RUN_ID","")
    cipher=Path("sealed-output/source.envelope.json").read_bytes()
    source=json.loads(Path("sealed-output/receipt.public.json").read_text())
    need(source["complete"] and source["runId"]==run and
         source["sha256"]==hashlib.sha256(cipher).hexdigest(),
         "INVENTORY_CUSTODY_BINDING")
    plaintext=unseal_new(cipher,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),run)
    bundle=json.loads(plaintext)
    need(bundle["schema"]==SCHEMA and bundle["readOnly"] is True and
         bundle["runId"]==run and bundle["ordersSubmitted"]==0 and
         bundle["tradingActivated"] is False,"INVENTORY_SCHEMA_OR_AUTHORITY")
    audit=from_pairs(_read_raw(bundle["raw"],m,require_read_only_request),m,
                     HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT)
    need(audit["rows"]==bundle["rows"] and audit["probes"]==bundle["probes"] and
         len(bundle["rows"])==source["fullAccountInstrumentCount"],
         "INVENTORY_RAW_RECONSTRUCTION_MISMATCH")
    result=public_receipt(audit["rows"])
    result.update(sourceRunId=int(run),
                  sourceCiphertextSha256=hashlib.sha256(cipher).hexdigest(),
                  originalAccountBindingRechecked=True,
                  fullRawReadbackMatched=True,authenticated=True,
                  contractProbes=len(audit["probes"]),
                  readOnlyRequestCount=audit["requestCount"],
                  costQualification=False,confidence="AUTHENTIC_ACCOUNT_INVENTORY_ONLY")
    Path("full-inventory.public.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("FULL_ACCOUNT_INVENTORY_PUBLIC_RECEIPT_VERIFIED",flush=True)

if __name__=="__main__":
    try:
        readback() if "--readback" in sys.argv else collect()
    except Exception:
        # Never print broker, account, or file-payload exception messages.
        print("FULL_ACCOUNT_INVENTORY_FAILED_CLOSED_DETAIL_WITHHELD",flush=True)
        raise SystemExit(1)
