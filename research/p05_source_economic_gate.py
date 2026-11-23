"""OWNER V3.2 P0.5: original encrypted-source cost/opportunity *diagnostic*, no broker calls.

Only inside existing custody environment. This is not a strategy, broker fill,
account ledger, policy simulator or NET calculation. All raw original account
protobuf stays in memory; only count aggregates leave the protected job.
"""
import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
from statistics import median

from .custody import unseal_new
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import decode_bars

RUN = "45134137836"
SOURCE_FIRST_MS = 1787529600000  # UTC 2026-08-24T00:00:00
SOURCE_END_MS = 1795392000000    # UTC 2026-11-23T00:00:00
PERIODS = {"M15": (int(e.M15), 15), "M30": (int(e.M30), 30),
           "H1": (int(e.H1), 60), "H4": (int(e.H4), 240),
           "D1": (int(e.D1), 1440)}
PERIOD_BY_ID = {v[0]: (name, v[1]) for name, v in PERIODS.items()}
MULTIPLIERS = (1, 1.5, 2)
KNOWN_SCHEMA = "P05_NEW_PEPPERSTONE_AUTHENTIC_READ_ONLY_SOURCE"
ORIGINAL_ARTIFACT_HASH = "8536052ab5782e107c63caa67a63ddfdec9923efb54a72f44e7925707e9fec3c"


def need(condition, label):
    if not condition:
        raise ValueError("P05_READBACK_" + label)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def _decoded_packet(record, typ):
    need(record.get("resType") == typ.__name__, "RESPONSE_TYPE")
    raw = base64.b64decode(record["res"], validate=True)
    res = typ()
    res.ParseFromString(raw)
    need(res.IsInitialized(), "RESPONSE_PROTO_INVALID")
    return res


def _roster(rows):
    names = {}
    for p in rows:
        if p.get("resType") != "ProtoOASymbolsListRes":
            continue
        res = _decoded_packet(p, m.ProtoOASymbolsListRes)
        for s in res.symbol:
            need(s.symbolId not in names, "DUPLICATE_ROSTER_SYMBOL_ID")
            names[s.symbolId] = s.symbolName
    need(bool(names), "ROSTER_MISSING")
    return names


def _load_sealed(meta, sealed_dir, private_pem):
    path = sealed_dir / meta["name"]
    need(path.is_file() and path.suffix == ".sealed", "SEALED_SHARD_MISSING")
    cipher = path.read_bytes()
    need(sha(cipher) == meta["ciphertextSha256"], "SEALED_HASH_MISMATCH")
    plain = unseal_new(cipher, private_pem, RUN)
    need(sha(plain) == meta["originalGzipSha256"], "RAW_GZIP_HASH_MISMATCH")
    return json.loads(gzip.decompress(plain))


def _bars_from_original(rows):
    """Reconstruct leaf-page bars (no new requests), preserving original as-of closes."""
    by_period = defaultdict(dict)
    symbol_ids = set()
    for packet in rows:
        if packet.get("reqType") != "ProtoOAGetTrendbarsReq":
            continue
        request = m.ProtoOAGetTrendbarsReq()
        request.ParseFromString(base64.b64decode(packet["req"], validate=True))
        symbol_ids.add(int(request.symbolId))
        if packet.get("resType") == "ProtoOAErrorRes":
            continue
        res = _decoded_packet(packet, m.ProtoOAGetTrendbarsRes)
        need(res.HasField("hasMore"), "HISTORY_PAGINATION_UNVERIFIED")
        if res.hasMore:
            continue  # Recursive children were captured as separate leaf replies.
        need(int(request.period) in PERIOD_BY_ID, "UNKNOWN_TIMEFRAME")
        name, minutes = PERIOD_BY_ID[int(request.period)]
        a, b = int(request.fromTimestamp), int(request.toTimestamp)
        need(a < b and SOURCE_FIRST_MS <= a < SOURCE_END_MS, "OUTSIDE_ORIGINAL_RANGE")
        need((not res.HasField("symbolId") or res.symbolId == request.symbolId)
             and int(res.period) == int(request.period), "HISTORY_RESPONSE_MISMATCH")
        # Original collector admitted a +/- one-period broker boundary candle.
        lo = max(0, a - minutes * 60000)
        hi = b + minutes * 60000
        decoded = decode_bars(res.trendbar, lo, hi, 0)
        for row in decoded:
            t, _, op, high, low, close, tickvol = row
            if not (a <= t <= b and t + minutes * 60000 <= SOURCE_END_MS):
                continue
            need(low > 0 and low <= op <= high and low <= close <= high
                 and tickvol >= 0, "BAD_BAR_GEOMETRY")
            # Preserve the collector's de-duplication across page boundaries.
            by_period[name].setdefault(t, row)
    need(len(symbol_ids) == 1, "SOURCE_MARKET_ID_BINDING")
    return next(iter(symbol_ids)), by_period


def _iso_week(t):
    d = datetime.fromtimestamp(t / 1000, tz=timezone.utc).isocalendar()
    return "%04d-W%02d" % (d.year, d.week)


def upper_bound_diagnostic(rows, spread_bps, margin_eur, period_minutes):
    """Hindsight bar amplitude necessary-condition diagnostic only.

    Never calculate trade NET/entry/fill/DD/eligible weeks from these rows.
    """
    need(spread_bps is None or spread_bps >= 0, "NEGATIVE_SPREAD")
    need(margin_eur is not None and margin_eur >= 0, "MARGIN_MISSING")
    totals = Counter()
    passes = {str(k): Counter() for k in MULTIPLIERS}
    absolute_close = {str(k): Counter() for k in MULTIPLIERS}
    for t, _, op, high, low, close, tickvol in rows:
        # Clock of the observation is its bar-close, not the start.
        at = t + period_minutes * 60000
        need(SOURCE_FIRST_MS <= t and at <= SOURCE_END_MS, "FUTURE_OR_UNCLOSED_BAR")
        week = _iso_week(at)
        totals[week] += 1
        if spread_bps is None or close <= 0:
            continue
        range_bps = 10000 * (high - low) / close
        close_move_bps = 10000 * abs(close - op) / close
        for multiplier in MULTIPLIERS:
            k = str(multiplier)
            if range_bps > spread_bps * multiplier:
                passes[k][week] += 1
            if close_move_bps > spread_bps * multiplier:
                absolute_close[k][week] += 1
    return {
        "barCount": sum(totals.values()),
        "weeksWithBars": len(totals),
        "observedWeekKeys": sorted(totals),
        "fundableMinimumMarginAt300": margin_eur < 300,
        "fundableMinimumMarginAt210StaticStress": margin_eur < 210,
        "hindsightRangeOnly": {k: dict(v) for k, v in passes.items()},
        "hindsightAbsoluteOpenCloseOnly": {k: dict(v) for k, v in absolute_close.items()},
    }


def aggregate_original(receipt, sealed_dir, private_pem):
    need(str(receipt.get("runId")) == RUN and receipt.get("schema") == KNOWN_SCHEMA,
         "ORIGINAL_RUN_OR_SCHEMA")
    need(receipt["historicalStart"] == "2026-08-24T00:00:00Z"
         and receipt["endExclusive"] == "2026-11-23T00:00:00Z",
         "ORIGINAL_WINDOW_CHANGED")
    need(receipt.get("ordersSubmitted") == 0
         and receipt.get("cloudActivated") is False
         and receipt.get("resultsDevelopmentOnly") is True, "SAFETY_SOURCE_FLAGS")
    source = receipt["sources"]
    need(len(source) == 76 and len({x["name"] for x in source}) == len(source),
         "ORIGINAL_SHARD_SET_CHANGED")
    roster_rows = next(x for x in source if x["kind"] == "ROSTER")
    ids = _roster(_load_sealed(roster_rows, sealed_dir, private_pem))
    inspected = 0
    for metadata in source:
        if metadata["kind"] == "CONTRACTS":
            # Never expose identities: verify every authenticated contract shard.
            data = _load_sealed(metadata, sealed_dir, private_pem)
            need(len(data) > 0, "EMPTY_CONTRACT_SOURCE")
            inspected += 1
    completed = []
    by_horizon = {tf: {
        "symbolCountWithRawBarsAndCostProxy": 0,
        "rawClosedBarCount": 0,
        "hindsightRangeBarCounts": {str(k): 0 for k in MULTIPLIERS},
        "hindsightOpenCloseBarCounts": {str(k): 0 for k in MULTIPLIERS},
        "weeksWithData": set(),
        "weeksWith21RangeExcursions": {str(k): set() for k in MULTIPLIERS},
    } for tf in PERIODS}
    by_week_range = {tf: {str(k): Counter() for k in MULTIPLIERS} for tf in PERIODS}
    by_week_oc = {tf: {str(k): Counter() for k in MULTIPLIERS} for tf in PERIODS}
    commission_available = swap_pair_present = quote_pair_available = 0
    seen_symbols = set()
    for metadata in source:
        if metadata["kind"] != "MARKET":
            continue
        rows = _load_sealed(metadata, sealed_dir, private_pem)
        need(rows and isinstance(rows[0], dict) and "contract" in rows[0],
             "CONTRACT_MARKET_BINDING")
        symbol_id, bars = _bars_from_original(rows[1:])
        need(symbol_id in ids, "MARKET_UNLISTED_SYMBOL_ID")
        symbol = ids[symbol_id]
        need(symbol not in seen_symbols and symbol in receipt["marketCoverage"],
             "MARKET_NOT_IN_PUBLIC_AGGREGATE")
        seen_symbols.add(symbol)
        public = receipt["marketCoverage"][symbol]
        contract = rows[0]["contract"]
        need(isinstance(contract, dict), "MARKET_CONTRACT_UNKNOWN")
        c_fields = ("minVolume", "stepVolume", "maxVolume", "lotSize",
                    "preciseTradingCommissionRate", "preciseMinCommission",
                    "commissionType", "minCommissionType")
        commission = all(contract.get(k) is not None for k in c_fields)
        commission_available += int(commission)
        swap_pair_present += int(contract.get("swapLong") is not None and contract.get("swapShort") is not None)
        sampled_spread = public["observedFixedClockMedianSpreadBps"]
        # A zero/negative sampled spread is not evidence of free execution.
        spread = sampled_spread if sampled_spread is not None and sampled_spread > 0 else None
        quote_pair_available += int(spread is not None)
        margin_str = public["currentMinMarginEur"]
        need(margin_str is not None, "MARKET_MARGIN_MISSING")
        margin = float(margin_str)
        for tf, (_, minutes) in PERIODS.items():
            originals = list(bars.get(tf, {}).values())
            need(len(originals) == public["timeframes"][tf]["bars"], "RAW_BAR_COUNT_MISMATCH")
            # Legitimate duplicates/gaps are never filled.
            d = upper_bound_diagnostic(originals, spread, margin, minutes)
            agg = by_horizon[tf]
            agg["rawClosedBarCount"] += d["barCount"]
            agg["weeksWithData"].update(d["observedWeekKeys"])
            if spread is not None and d["barCount"]:
                agg["symbolCountWithRawBarsAndCostProxy"] += 1
            for k in [str(m) for m in MULTIPLIERS]:
                count = sum(d["hindsightRangeOnly"][k].values())
                agg["hindsightRangeBarCounts"][k] += count
                agg["hindsightOpenCloseBarCounts"][k] += sum(d["hindsightAbsoluteOpenCloseOnly"][k].values())
                by_week_range[tf][k].update(d["hindsightRangeOnly"][k])
                by_week_oc[tf][k].update(d["hindsightAbsoluteOpenCloseOnly"][k])
        completed.append(symbol)
    need(len(completed) == receipt["marketProbesCompleted"] == 48, "SOURCE_COMPLETENESS")
    horizons = {}
    for tf, data in by_horizon.items():
        keys = sorted(data["weeksWithData"])
        horizons[tf] = {
            "authenticClosedBars": data["rawClosedBarCount"],
            "symbolsWithBarsAndPartialVariableCost": data["symbolCountWithRawBarsAndCostProxy"],
            "weeksWithAnyBarsNotEligibleCertified": len(keys),
            "hindsightRangeBarsExceedSpreadProxy": data["hindsightRangeBarCounts"],
            "hindsightCloseOpenBarsExceedSpreadProxy": data["hindsightOpenCloseBarCounts"],
            "weeksWithAtLeast21HindsightRangeEventsNotFinanceableTrades": {
                k: sum(v >= 21 for v in by_week_range[tf][k].values())
                for k in [str(m) for m in MULTIPLIERS]
            },
            "weeksWithAtLeast21HindsightOpenCloseEventsNotFinanceableTrades": {
                k: sum(v >= 21 for v in by_week_oc[tf][k].values())
                for k in [str(m) for m in MULTIPLIERS]
            },
            "verifiedEligibleWeeks": None,
            "causallyDetectableFinancedTrades": None,
            "allInNetEUR": None,
        }
        need(data["rawClosedBarCount"] ==
             sum(s["timeframes"][tf]["bars"] for s in receipt["marketCoverage"].values()),
             "TOTAL_BAR_COUNTS_MISMATCH")
    return {
        "schema": "MXM_P05_ORIGINAL_AUTHENTIC_DECRYPTED_COST_FRONTIER_V32",
        "sourceRunId": RUN,
        "originalSealedShardsVerified": len(source),
        "originalContractShardsVerified": inspected,
        "sampledSymbols": len(completed),
        "currentMinimumMarginUnder210Sample": sum(
            float(row["currentMinMarginEur"]) < 210 for row in receipt["marketCoverage"].values()),
        "symbolsWithPositiveFixedClockSpreadProxy": quote_pair_available,
        "zeroOrInvalidFixedClockSpreadNotPromoted": sum(
            x["observedFixedClockMedianSpreadBps"] is not None and
            x["observedFixedClockMedianSpreadBps"] <= 0
            for x in receipt["marketCoverage"].values()),
        "symbolsWithExplicitCommissionWireTerms": commission_available,
        "symbolsWithSwapPairWireValues": swap_pair_present,
        "symbolsWithAllInHistoricalCostEurCertified": 0,
        "conditionalVariableSpreadOnlyMultipliers": [1, 1.5, 2],
        "horizons": horizons,
        "initialCommonCapitalEur": 300,
        "maximumFloatingDrawdownPercent": 30,
        "NET_EUR": None,
        "CASH_EUR": 0,
        "HARD21": "UNKNOWN",
        "eligibleISOWeeks": None,
        "floatingDDPercent": None,
        "costCertification": "INCOMPLETE_FIXED_FEES_FX_SWAP_SLIPPAGE_FILL_ASOF",
        "hindsightBarsAreNotCausalOpportunities": True,
        "hindsightBarsAreNotIndependentAcrossTimeframes": True,
        "allSourceDatesInPreviouslyExposedA": True,
        "brokerRequests": 0,
        "ordersSubmitted": 0,
        "cloudActivated": False,
        "verdict": "P05_PARTIAL_MATHEMATICAL_BOUND_NO_EXECUTABLE_NET",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--sealed-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    key = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key.strip()), "CUSTODY_UNAVAILABLE")
    receipt = json.loads(args.receipt.read_text())
    result = aggregate_original(receipt, args.sealed_dir, key)
    # This report is aggregate-only; no symbol names, account IDs or original prices.
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("P05_ORIGINAL_ECONOMIC_BOUNDS " + json.dumps({
        "originalSealedShardsVerified": result["originalSealedShardsVerified"],
        "costProxyMarkets": result["symbolsWithPositiveFixedClockSpreadProxy"],
        "eligibleWeeks": None, "NET": None, "HARD21": "UNKNOWN",
        "DD": None, "orders": 0, "brokerRequests": 0}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # No decrypted protobuf, account or secret in exception trace / logs.
        print("P05_SOURCE_READBACK_FAILED_DETAIL_WITHHELD")
        raise SystemExit(1)
