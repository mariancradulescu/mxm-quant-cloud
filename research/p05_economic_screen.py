"""P0.5: offline reproducible, source-only breadth and cost diagnostic.

This reads published, previously authenticated development receipts.
It never connects to a broker, handles credentials, trades or treats
price amplitude as attainable profit.
"""
import json
import hashlib
from pathlib import Path
from decimal import Decimal, InvalidOperation
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "roster": "docs/FULL_CTRADER_ACCOUNT_INVENTORY_AUTHENTIC_20261105.json",
    "multi": "docs/OWNER_EXECUTED_MULTI_ASSET_COST_CAPITAL_SCREEN_20261108.json",
    "h1": "docs/EUR_ECONOMIC_PREFLIGHT_RESULT.json",
    "m5": "docs/AUTHENTIC_TEMPORAL_COVERAGE_20261105.json",
}
HORIZONS = ("M15", "M30", "H1", "H4", "D1")
CAPITAL = Decimal("300")

def load(root=ROOT):
    sources, fingerprints = {}, {}
    for name, path in FILES.items():
        raw = (Path(root) / path).read_bytes()
        sources[name] = json.loads(raw)
        fingerprints[path] = hashlib.sha256(raw).hexdigest()
    return sources, fingerprints

def ratio(cost, typical):
    try:
        cost, typical = Decimal(str(cost)), Decimal(str(typical))
    except (InvalidOperation, ValueError) as ex:
        raise ValueError("INVALID_COST_MOVE") from ex
    if not cost.is_finite() or not typical.is_finite() or cost < 0 or typical <= 0:
        raise ValueError("INVALID_COST_MOVE")
    return cost / typical

def screen(src, hashes):
    roster, multi, h1, m5 = (src[k] for k in ("roster", "multi", "h1", "m5"))
    n = roster["completeNonArchivedAccountSymbolRoster"]
    probed = roster["contractProbeCount"]
    if n < probed or roster["unprobedContractEntries"] != n - probed:
        raise ValueError("ROSTER_RECONCILIATION")
    if not roster["authenticated"] or not roster["fullRawReadbackMatched"]:
        raise ValueError("ROSTER_UNAUTHENTICATED")
    markets = multi["sourceMarkets"]
    if len(markets) != multi["sourceMarketCount"]:
        raise ValueError("MULTICLASS_COUNT")
    if h1["eur_economic_preflight"]["horizon_minutes"] != 60:
        raise ValueError("H1_ORIGIN")
    h1markets = h1["eur_economic_preflight"]["markets"]
    coverage = {r["symbol"]: r for r in m5["assets"]}
    if len(coverage) != m5["sourceSymbols"] or sum(x["m5"] for x in coverage.values()) != m5["sourceBars"]:
        raise ValueError("M5_SOURCE_RECONCILIATION")
    classes = dict(sorted(Counter(x["category"] for x in markets.values()).items()))
    multi_rows = [
        {
            "symbol": name,
            "assetClass": row["category"],
            "asOfMinimumMarginEur": row["minMarginEUR"],
            "asOfMarginBelow300": row["minMarginEUR"] < float(CAPITAL),
            "freshBidAskPairs": row.get("quotePairs"),
            "sampledSpreadBps": row.get("spreadBps"),
            "historicallyCompleteRoundTripCost": None,
            "actualFinanceableCompletedTrades": None,
            "netEUR": None,
        }
        for name, row in sorted(markets.items())
    ]
    h1rows = []
    for symbol, row in sorted(h1markets.items()):
        typical = row["median_absolute_move_eur_at_reference_notional"]
        proxy = row["twice_original_base_cost_stress_eur"]
        h1rows.append({
            "symbol": symbol,
            "sourceMedianAbsoluteMoveEUR": typical,
            "sourceTwiceBaseCostProxyEUR": proxy,
            "ratio2xBaseProxyToMedianMovePercent": round(float(100 * ratio(proxy, typical)), 3),
            "sourceMinMarginEUR": row["source_minimum_margin_eur"],
            "distinctQuoteDates": row["source_distinct_quote_dates"],
            "allInCostConfirmed": False,
            "netPositiveOpportunities": None,
            "qualifiedForHard21": None,
        })
    if sorted(coverage) != sorted(h1markets):
        raise ValueError("SOURCE_INTERSECTION_CHECK")
    horizon_status = {
        "M15": "M5 source exists for 12, authentic correctly aggregated candle/cost evaluation NOT_DONE",
        "M30": "M5 source exists for 12, authentic correctly aggregated candle/cost evaluation NOT_DONE",
        "H1": "12 source median moves plus INCOMPLETE 2x base-cost proxy, NOT all-in NET",
        "H4": "M5 source exists for 12, full session-aware aggregation/cost evaluation NOT_DONE",
        "D1": "M5 source exists for 12, broker-session/DST D1 reaggregation and cost evaluation NOT_DONE",
    }
    return {
        "schema": "MXM_P05_OFFLINE_SOURCE_BREADTH_V1",
        "evidence": "REUSED_ORIGINAL_DEVELOPMENT_RECEIPTS_NO_NEW_MARKET_REQUESTS",
        "asOf": "2026-11-23",
        "capitalEUR": 300,
        "sourceSha256": hashes,
        "fullRoster": {
            "nonArchived": n,
            "visible": roster["visibleAccountSymbols"],
            "contractProbed": probed,
            "asOfMinMarginObserved": roster["contractCurrentMinMarginObserved"],
            "asOfMinMarginBelow200": roster["currentStaticMinimumMarginBelow200EurCount"],
            "notIndividuallyProbed": roster["unprobedContractEntries"],
            "wholeRosterCostsAndMarginsKnown": False,
        },
        "priorMulticlassSample": {
            "instrumentCount": len(markets),
            "assetClasses": classes,
            "allSourceSnapshotSingleLegMarginsBelow300": all(r["asOfMarginBelow300"] for r in multi_rows),
            "individualContractEvidenceNotPortfolioFinancing": True,
            "rows": multi_rows,
        },
        "historicalM5": {
            "sourceBars": m5["sourceBars"],
            "weeksReported": m5["sourceWeeks"],
            "symbols": sorted(coverage),
            "unknownSessionVsGap": True,
        },
        "horizonDiagnostics": horizon_status,
        "H1IncompleteProxy": {
            "symbols": len(h1rows),
            "rows": h1rows,
            "incomplete2xProxyAtLeastMedianMoveCount": sum(r["ratio2xBaseProxyToMedianMovePercent"] >= 100 for r in h1rows),
            "excludedFrictionFromSource": h1["eur_economic_preflight"]["friction_excludes"],
            "NOTAllInCost": True,
            "NOTMathematicalExclusion": True,
        },
        "policyEvidence": {
            "allInNetEUR": None,
            "allInNetPercent": None,
            "fundedWeeklyCompleteTrades": None,
            "markedEquityMaxDDPercent": None,
            "hard21": "UNKNOWN",
            "independentConfirmation": False,
            "sourceDatesAreDevelopmentOnly": True,
            "P0": "NOT_PASSED",
            "P0_5": "NOT_PASSED",
            "verdict": "INCONCLUSIVE",
        },
        "nextCollection": "READ_ONLY_AUTHENTIC_BROKER_SCOPE_CHECK_THEN_5339_NON_ARCHIVED_ROSTER_CONTRACT_PAGINATION; COST_FIRST_BY_FINANCEABLE_MIN_VOLUME_AND_CLASS; M15_M30_H1_H4_D1_CLOSED_BARS_WITH_HISTORICAL_DEPTH_AND_UTC_SESSION_QA",
    }

def summary(data):
    r = data["fullRoster"]
    s = data["priorMulticlassSample"]
    h = data["H1IncompleteProxy"]
    lo = min(x["ratio2xBaseProxyToMedianMovePercent"] for x in h["rows"])
    hi = max(x["ratio2xBaseProxyToMedianMovePercent"] for x in h["rows"])
    out = [
        "# P0.5 — Comprehensive prior-source inventory (preliminary, 2026-11-23)",
        "",
        "Not a new collection, not a net backtest, not P0/P0.5 certification.",
        "",
        f"- Historical account inventory: **{r['nonArchived']}** nonarchived symbols; **{r['visible']}** visible; **{r['contractProbed']}** sampled contracts; **{r['notIndividuallyProbed']}** unprobed.",
        f"- Historical sampled margins: **{r['asOfMinMarginBelow200']}** below EUR200 (out of {r['asOfMinMarginObserved']} with margin observation). This is NOT current financing proof.",
        f"- Other original multi-class snapshot: **{s['instrumentCount']}** sampled instruments across **{len(s['assetClasses'])}** classes ({', '.join(f'{k}: {v}' for k,v in s['assetClasses'].items())}). Every one had historical minimum single-leg margin below EUR300, but complete costs and portfolio funding are UNKNOWN.",
        f"- M5 historical observations: **{data['historicalM5']['sourceBars']}** bars / {data['historicalM5']['weeksReported']} weeks / 12 instruments. Missing-session vs real gaps unresolved.",
        f"- H1 median-move vs twice original base cost proxy: **{lo:.2f}%–{hi:.2f}%** across {h['symbols']} instruments; **{h['incomplete2xProxyAtLeastMedianMoveCount']}** ratio >=100%. NOT all-in; NOT a permanent instrument/horizon exclusion.",
        "",
        "| H1 symbol | Min margin EUR (old snapshot) | Typical move EUR | 2x old base-cost proxy EUR | Cost/move |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in h["rows"]:
        out.append(f"| {row['symbol']} | {row['sourceMinMarginEUR']:.2f} | {row['sourceMedianAbsoluteMoveEUR']:.3f} | {row['sourceTwiceBaseCostProxyEUR']:.3f} | {row['ratio2xBaseProxyToMedianMovePercent']:.1f}% |")
    out += [
        "",
        "## M15–D1 status (none excluded)",
        "",
    ]
    for p, state in data["horizonDiagnostics"].items():
        out.append(f"- **{p}:** {state}")
    out += [
        "",
        "## Hard gates: NOT MEASURED",
        "",
        "NET EUR/%: UNKNOWN. Funded completed trades/eligible week: UNKNOWN. Mark-to-market max drawdown: UNKNOWN. Independent B/C confirmation: unavailable. No reported opportunity count is a profitable strategy.",
        "",
        "No new Open API calls; no OAuth/secrets touched; no LIVE/DEMO orders; no cTrader Cloud activation; no old study rerun.",
        "",
        "## Blocking evidence / next economic step",
        "",
        "Read-only authenticated broker roster + current executable minimum volumes, spreads, commissions, swap, FX, slippage model, effective leverage and actual historical depth; fill cost/move M15 M30 H1 H4 D1 using closed bars and explicit uncertainty. First rank by funding and cost, not by old strategy results. Prove eligible-week financed positive NET opportunity frontier and HARD21/DD coexistence. If no secure authorized read-only collector path is available, report blockage rather than invent data.",
    ]
    return "\n".join(out) + "\n"

def run():
    src, hashes = load()
    report = screen(src, hashes)
    out = ROOT / "p05-public"
    out.mkdir(exist_ok=True)
    (out / "economic-inventory.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "economic-inventory.md").write_text(summary(report))
    print("P05_SOURCE_ONLY_INVENTORY", report["fullRoster"]["nonArchived"], len(report["priorMulticlassSample"]["rows"]), report["policyEvidence"]["verdict"])

if __name__ == "__main__":
    run()
