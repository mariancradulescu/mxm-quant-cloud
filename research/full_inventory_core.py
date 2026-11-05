"""MXM full account symbol inventory -- pure data integrity/capacity screening.

No network, credentials, orders or economic model. Responses must come from
one authenticated cTrader account and are stored in existing encrypted custody.
"""
from __future__ import annotations
from decimal import Decimal

class InventoryIntegrityError(ValueError):
    pass

def _need(condition, code):
    if not condition:
        raise InventoryIntegrityError(code)

def _optional(message, name):
    return getattr(message, name) if message.HasField(name) else None

def normalize_account_inventory(listing, assets_response, bound_account_id):
    """Retain every non-archived light symbol, including invisible/unknown."""
    _need(listing.IsInitialized() and assets_response.IsInitialized(), "INVENTORY_LIST_INCOMPLETE")
    _need(listing.ctidTraderAccountId == bound_account_id and
          assets_response.ctidTraderAccountId == bound_account_id, "INVENTORY_LIST_ACCOUNT")
    assets = {}
    for a in assets_response.asset:
        _need(a.assetId not in assets and bool(a.name), "INVENTORY_ASSET_DUPLICATE")
        assets[a.assetId] = a.name
    seen_ids, seen_names, rows = set(), set(), []
    for symbol in listing.symbol:
        sid = int(symbol.symbolId)
        _need(sid > 0 and sid not in seen_ids, "INVENTORY_DUPLICATE_SYMBOL_ID")
        seen_ids.add(sid)
        name = _optional(symbol, "symbolName")
        if name is not None:
            _need(bool(name.strip()) and name not in seen_names, "INVENTORY_DUPLICATE_NAME")
            seen_names.add(name)
        base = _optional(symbol, "baseAssetId")
        quote = _optional(symbol, "quoteAssetId")
        enabled = _optional(symbol, "enabled")
        rows.append({
            "symbolId": sid, "symbolName": name,
            "visible": bool(enabled) if enabled is not None else None,
            "baseAsset": assets.get(base) if base is not None else None,
            "quoteAsset": assets.get(quote) if quote is not None else None,
            "symbolCategoryId": _optional(symbol, "symbolCategoryId"),
            "contractStatus": "NOT_QUERIED", "currentMinMarginEur": None,
            "historicalMarginCertified": False,
            "historicalExecutionCostsCertified": False,
        })
    _need(len(rows) == len(listing.symbol), "INVENTORY_COVERAGE_MISMATCH")
    return sorted(rows, key=lambda x:x["symbolId"])

def classify_contract_and_min_margin(row, details, margin_reply, account_id):
    """Screen minimum lot and *current* margin only; never imply trade fitness."""
    out = dict(row)
    _need(row["visible"] is True and bool(row["symbolName"]), "INVENTORY_VISIBILITY_UNKNOWN")
    _need(details.IsInitialized() and margin_reply.IsInitialized(), "INVENTORY_DETAIL_INCOMPLETE")
    _need(details.ctidTraderAccountId == account_id and
          margin_reply.ctidTraderAccountId == account_id, "INVENTORY_DETAIL_ACCOUNT")
    _need(len(details.symbol) == 1 and details.symbol[0].symbolId == row["symbolId"],
          "INVENTORY_DETAIL_SYMBOL_ID")
    c = details.symbol[0]
    mode = _optional(c, "tradingMode")
    if mode is None:
        out["contractStatus"] = "TRADING_MODE_NOT_EXPLICIT"
        return out
    if mode != 0:
        out["contractStatus"] = "NOT_OPENABLE_TRADING_MODE"
        return out
    mn, st, mx = (_optional(c,k) for k in ("minVolume","stepVolume","maxVolume"))
    if any(x is None for x in (mn,st,mx)) or not 0 < mn <= mx or st <= 0:
        out["contractStatus"] = "VOLUME_GRID_INCOMPLETE"
        return out
    out["minVolumeUnits"] = str(Decimal(mn)/100)
    out["stepVolumeUnits"] = str(Decimal(st)/100)
    _need(margin_reply.HasField("moneyDigits") and
          len(margin_reply.margin) == 1 and
          margin_reply.margin[0].volume == mn, "INVENTORY_MARGIN_VOLUME")
    r = margin_reply.margin[0]
    _need(r.buyMargin >= 0 and r.sellMargin >= 0 and 0 <= margin_reply.moneyDigits <= 12,
          "INVENTORY_MARGIN_NUMERIC_INVALID")
    buy = Decimal(r.buyMargin)/(Decimal(10)**margin_reply.moneyDigits)
    sell = Decimal(r.sellMargin)/(Decimal(10)**margin_reply.moneyDigits)
    out.update(buyMinMarginEur=str(buy),sellMinMarginEur=str(sell),
        currentMinMarginEur=str(max(buy,sell)),
        contractStatus="CURRENT_MIN_MARGIN_OBSERVED_COSTS_UNVERIFIED",
        marginBelowInitial200Eur=max(buy,sell)<Decimal(200),
        marginBelowEquity140Eur=max(buy,sell)<Decimal(140))
    return out

def public_receipt(rows):
    """Aggregate source metadata only; no account id, quote, P&L, or raw wire data."""
    statuses = {}
    for x in rows:
        statuses[x["contractStatus"]] = statuses.get(x["contractStatus"],0)+1
    return {
        "schema":"mxm-full-symbol-inventory-observation-v1",
        "researchOnly":True, "ordersSubmitted":0,
        "sourceAuthenticatedExternally":None,
        "totalReturnedSymbols":len(rows),
        "visibleSymbols":sum(x["visible"] is True for x in rows),
        "visibilityUnconfirmed":sum(x["visible"] is None for x in rows),
        "contractStatuses":statuses,
        "instrumentNames":[x["symbolName"] for x in rows if x["symbolName"]],
        "contractProbes":sum(x["contractStatus"] != "NOT_QUERIED" for x in rows),
        "currentMinMarginObserved":sum(x["currentMinMarginEur"] is not None for x in rows),
        "staticBelow200EurCount":sum(x.get("marginBelowInitial200Eur") is True for x in rows),
        "screenedInstruments":[{
            "name":x["symbolName"],"status":x["contractStatus"],
            "minVolumeUnits":x.get("minVolumeUnits"),
            "currentMinMarginEur":x.get("currentMinMarginEur"),
            "staticMarginBelow200Eur":x.get("marginBelowInitial200Eur")
        } for x in rows if x["contractStatus"] != "NOT_QUERIED"],
        "historicalMarginCertified":False,
        "historicalExecutionCostsCertified":False,
        "independentNetEdgeEstablished":False,
        "hard21Established":False,
    }
