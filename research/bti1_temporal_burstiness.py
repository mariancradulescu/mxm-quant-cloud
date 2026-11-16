"""BTI1: one prespecified event-TIMING hypothesis on original QPI1 ciphertext.

This NEVER imports or executes QPI1's closed decide/score routines. No broker
connection, new research engine, execution fills, EUR net or trading orders.
"""
from __future__ import annotations

import base64
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from statistics import mean, median, stdev

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .custody import unseal_new
from .decode import decode_side, need
from .guard import require_read_only_request

PROTOCOL = Path("research/BTI1_TEMPORAL_QUOTE_BURSTINESS_PRESOURCE.md")
SOURCE = Path("bti1-source/qpi1-original-quote-events.v2.enc")
OUTPUT = Path("bti1-original-timing-incremental-public.json")
QPI_RUN = "43458050084"
QPI_CIPHER = "853ddd0951f23f6c59efd45f775a8092a4f8a00e2d3766fef944efbd121b9236"
QPI_PLAIN = "d554e47205e53473fbe49f80fb5b1fd0d0a2c094efa17d37825e62d8de5c2c3b"
TARGETS = ("USDCHF", "EURGBP")
START = date(2026, 9, 14)
MAX_AGE = 20000
WINDOW = 600000
MIN_REVISIONS = 12
BURST_CUTOFF = 0.20


def ts(day, hour):
    return int(datetime(day.year, day.month, day.day, hour,
                        tzinfo=timezone.utc).timestamp() * 1000)


def decode_wire(entry, req_name, res_name):
    need(entry["requestType"] == req_name and
         entry["responseType"] == res_name, "BTI1_WIRE_TYPES")
    req = getattr(m, req_name)()
    res = getattr(m, res_name)()
    req.ParseFromString(base64.b64decode(entry["request"], validate=True))
    res.ParseFromString(base64.b64decode(entry["response"], validate=True))
    require_read_only_request(req)
    need(req.IsInitialized() and res.IsInitialized(), "BTI1_WIRE_INVALID")
    return req, res


def authenticated_tape():
    need(PROTOCOL.exists() and "PRE-ORIGINAL-READBACK-FROZEN" in
         PROTOCOL.read_text(), "BTI1_PROTOCOL_NOT_FROZEN")
    sealed = SOURCE.read_bytes()
    need(sha256(sealed).hexdigest() == QPI_CIPHER, "BTI1_ORIGINAL_CIPHERTEXT_CHANGED")
    private = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(private.strip()), "BTI1_PROTECTED_KEY_UNAVAILABLE")
    raw = unseal_new(sealed, private, QPI_RUN)
    need(sha256(raw).hexdigest() == QPI_PLAIN, "BTI1_ORIGINAL_PLAINTEXT_CHANGED")
    tape = json.loads(raw)
    need(tape.get("classification") == "ORIGINAL_PEPPERSTONE_QPI1_PROTECTED_TICK_EVENTS"
         and str(tape.get("run")) == QPI_RUN
         and tape.get("requestCount") == 645
         and len(tape.get("rawAuthenticatedReadOnlyMessages", [])) == 645,
         "BTI1_ORIGINAL_SOURCE_IDENTITY")
    proof = tape["rawAuthenticatedReadOnlyMessages"]
    req, trader = decode_wire(proof[0], "ProtoOATraderReq", "ProtoOATraderRes")
    account = req.ctidTraderAccountId
    fp = sha256(("ctrader-account:" + str(account)).encode("ascii")).hexdigest()
    need(sha256(fp.encode("ascii")).hexdigest() == HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and trader.ctidTraderAccountId == account
         and "pepperstone" in trader.trader.brokerName.casefold(), "BTI1_ACCOUNT_BINDING")
    _, assets = decode_wire(proof[1], "ProtoOAAssetListReq", "ProtoOAAssetListRes")
    need(assets.ctidTraderAccountId == account
         and {a.assetId: a.name for a in assets.asset}.get(
             trader.trader.depositAssetId) == "EUR", "BTI1_EUR_ACCOUNT")
    _, roster = decode_wire(proof[2], "ProtoOASymbolsListReq", "ProtoOASymbolsListRes")
    need(roster.ctidTraderAccountId == account, "BTI1_ROSTER_ACCOUNT")
    symbols = {s.symbolName: s.symbolId for s in roster.symbol if s.enabled}
    need(all(s in symbols for s in TARGETS), "BTI1_TARGET_BINDING")
    idx = 3
    for s in TARGETS:
        req, result = decode_wire(proof[idx], "ProtoOASymbolByIdReq",
                                  "ProtoOASymbolByIdRes")
        idx += 1
        need(req.ctidTraderAccountId == result.ctidTraderAccountId == account
             and list(req.symbolId) == [symbols[s]]
             and len(result.symbol) == 1
             and result.symbol[0].symbolId == symbols[s],
             "BTI1_CONTRACT_BINDING")
        need(tape["symbolStatus"][s] ==
             "ORIGINAL_ENABLED_CURRENT_NOT_HISTORICALLY_CERTIFIED"
             and len(tape["targets"][s]) == 80, "BTI1_ORIGINAL_POPULATION")
        for w in range(8):
            for d in range(5):
                day = START + timedelta(weeks=w, days=d)
                for h in (9, 14):
                    t = ts(day, h)
                    obs = tape["targets"][s][w * 10 + d * 2 + ((h == 14) * 1)]
                    need(obs["week"] == w and obs["decision"] == t,
                         "BTI1_SCHEDULE_INVARIANT")
                    truncated = False
                    rebuilt = []
                    for left, right in ((t - 620000, t), (t, t + 1860000)):
                        sides = []
                        for kind in (e.BID, e.ASK):
                            entry = proof[idx]
                            idx += 1
                            need(entry["requestType"] == "ProtoOAGetTickDataReq" and
                                 entry["responseType"] in
                                 ("ProtoOAGetTickDataRes", "ProtoOAErrorRes"),
                                 "BTI1_TICK_WIRE_TYPE")
                            request = m.ProtoOAGetTickDataReq()
                            request.ParseFromString(
                                base64.b64decode(entry["request"], validate=True))
                            require_read_only_request(request)
                            need(request.IsInitialized() and
                                 request.ctidTraderAccountId == account and
                                 request.symbolId == symbols[s] and
                                 request.type == kind and
                                 request.fromTimestamp == left and
                                 request.toTimestamp == right,
                                 "BTI1_TICK_REQUEST_PROVENANCE")
                            if entry["responseType"] == "ProtoOAErrorRes":
                                res = m.ProtoOAErrorRes()
                                res.ParseFromString(base64.b64decode(
                                    entry["response"], validate=True))
                                need(res.IsInitialized() and
                                     res.ctidTraderAccountId == account and
                                     res.errorCode == "NO_QUOTES",
                                     "BTI1_TICK_ERROR_UNAPPROVED")
                                ticks = []
                            else:
                                res = m.ProtoOAGetTickDataRes()
                                res.ParseFromString(base64.b64decode(
                                    entry["response"], validate=True))
                                need(res.IsInitialized() and
                                     res.ctidTraderAccountId == account,
                                     "BTI1_TICK_RESPONSE_ACCOUNT")
                                if res.hasMore:
                                    truncated = True
                                    ticks = []
                                else:
                                    ticks = decode_side(res.tickData, left, right)
                            sides.append(ticks)
                        rebuilt.append(sides)
                    need(truncated == obs["truncated"] and
                         rebuilt == obs["before"], "BTI1_ORIGINAL_BEFORE_TICKS")
                    # The after window is verified separately; no post-t
                    # information ever reaches the presignal feature function.
                    need(rebuilt[1] == obs["after"], "BTI1_ORIGINAL_AFTER_TICKS")
    need(idx == len(proof), "BTI1_ORIGINAL_UNRECONCILED_REQUESTS")
    return tape, sha256(PROTOCOL.read_bytes()).hexdigest()


def asof(side, at):
    """Last source-side tick <= query with no more than 20s staleness."""
    lo, hi = 0, len(side)
    while lo < hi:
        md = (lo + hi) // 2
        if side[md][0] <= at:
            lo = md + 1
        else:
            hi = md
    idx = lo - 1
    return (side[idx][1] if idx >= 0 and
            0 <= at - side[idx][0] <= MAX_AGE else None)


def pair(bid, ask, at):
    b, a = asof(bid, at), asof(ask, at)
    return (b, a) if b is not None and a is not None and 0 < b <= a else None


def mid(q):
    return (q[0] + q[1]) / 2.0


def revisions(side, low, high):
    old = None
    out = []
    up = down = 0
    for at, price in side:
        if at < low:
            old = price
            continue
        if at > high:
            break
        if old is not None and price != old:
            out.append(at)
            if price > old:
                up += 1
            else:
                down += 1
        old = price
    return out, up, down


def timing_feature(before, t):
    """Only <= t quote events. QPI count alone cannot recover this feature."""
    bid, ask = before
    first = pair(bid, ask, t-WINDOW)
    last = pair(bid, ask, t)
    if first is None or last is None:
        return {"state": "PREDECISION_QUOTE_MISSING"}
    b, bu, bd = revisions(bid, t-WINDOW, t)
    a, au, ad = revisions(ask, t-WINDOW, t)
    n = len(b) + len(a)
    if n < MIN_REVISIONS:
        return {"state": "INSUFFICIENT_ACTIVITY", "N": n}
    bins = [0]*10
    for at in b + a:
        k = min(9, max(0, (at - (t-WINDOW)) // 60000))
        bins[k] += 1
    concentration = sum(x*(x-1) for x in bins)/(n*(n-1))
    side = int(mid(last) > mid(first)) - int(mid(last) < mid(first))
    return {"state": "BURST" if concentration >= BURST_CUTOFF else "QUIET",
            "N": n, "collision": concentration, "side": side,
            "signedCount": bu + au - bd - ad,
            "spreadAtT": (last[1] - last[0]) / mid(last) * 10000,
            "ownMomentumBps": (mid(last) - mid(first))/mid(first)*10000}


def side_bps(entry, exit_, side):
    if side == 0:
        return (0.0, 0.0)
    den = mid(entry)
    gross = side*(mid(exit_) - den)/den*10000
    crossing = side*((exit_[0] if side > 0 else exit_[1]) -
                     (entry[1] if side > 0 else entry[0]))/den*10000
    return gross, crossing


def sampled_mae(after, start, finish, entry, side):
    if side == 0:
        return 0.0
    times = sorted({r[0] for half in after for r in half
                    if start <= r[0] <= finish} | {finish})
    prices = [pair(after[0], after[1], k) for k in times]
    eligible = [x for x in prices if x is not None]
    if not eligible:
        return None
    return max(0.0, max(-side*(mid(x)-mid(entry))/mid(entry)*10000
                        for x in eligible))


def paired_weekly_lower(values):
    """Paired four-week interval; no false independent event-level confidence."""
    need(len(values) == 4, "BTI1_WEEKLY_GATE")
    return mean(values) - 3.182*stdev(values)/math.sqrt(4)


def summarize_policy(rows, name, slippage):
    vals = [r[name][1] - (slippage if r[name][2] else 0) for r in rows]
    return {"meanPerMatchedClockBps": round(mean(vals), 6) if vals else None,
            "totalMatchedClocks": len(vals),
            "trades": sum(r[name][2] for r in rows),
            "meanPerEnteredTradeBps": (
                round(mean(v for v,r in zip(vals,rows) if r[name][2]),6)
                if any(r[name][2] for r in rows) else None)}


def evaluate(tape, protocol_sha):
    schedules = {}
    summaries = {}
    accepted = True
    for symbol in TARGETS:
        records = []
        for obs in tape["targets"][symbol]:
            f = ({"state": "TRUNCATED_SOURCE"} if obs["truncated"]
                 else timing_feature(obs["before"], obs["decision"]))
            records.append({"week": obs["week"], "t": obs["decision"],
                            "features": f, "source": obs})
        counts_first = [r["features"]["N"] for r in records if
                        r["week"] < 4 and r["features"]["state"] in
                        ("BURST", "QUIET")]
        count_median = median(counts_first) if counts_first else None
        counts = Counter()
        weekly = []
        matched_all = []
        within_count = defaultdict(list)
        for w in range(8):
            matched = []
            for r in (x for x in records if x["week"] == w):
                obs = r["source"]
                f = r["features"]
                counts[f["state"]] += 1
                if f["state"] not in ("BURST", "QUIET"):
                    continue
                if f["side"] == 0:
                    counts["MOMENTUM_ZERO_ABSTAIN"] += 1
                entry = pair(*obs["after"], r["t"] + 60000)
                exit_ = pair(*obs["after"], r["t"] + 1800000)
                if entry is None or exit_ is None:
                    counts["POSTDECISION_ENTRY_EXIT_UNKNOWN"] += 1
                    continue
                counts["PAIRED_ECONOMIC_PRICE_CONTEXT"] += 1
                side = f["side"]
                strategies = {
                    "bti1": side if f["state"] == "QUIET" else 0,
                    "momentum": side,
                    "countOnly": (side if count_median is not None
                                  and f["N"] < count_median else 0),
                    "long": 1, "short": -1, "cash": 0}
                row = {"week": w, "features": f}
                for name, order in strategies.items():
                    gross, cross = side_bps(entry, exit_, order)
                    row[name] = (gross, cross, int(order != 0))
                row["momentumSampledAdverseBps"] = sampled_mae(
                    obs["after"], r["t"]+60000, r["t"]+1800000,
                    entry, side)
                matched.append(row)
                matched_all.append(row)
                if w >= 4:
                    band = ("low" if count_median is not None
                            and f["N"] < count_median else "high")
                    within_count[band].append(row)
            weekly.append({
                "week": w + 1,
                "pairedClocks": len(matched),
                "bti1AdverseMeanPerPricedClock": summarize_policy(
                    matched, "bti1", 4.0)["meanPerMatchedClockBps"],
                "momentumAdverseMeanPerPricedClock": summarize_policy(
                    matched, "momentum", 4.0)["meanPerMatchedClockBps"],
                "countOnlyAdverseMeanPerPricedClock": summarize_policy(
                    matched, "countOnly", 4.0)["meanPerMatchedClockBps"]})
        development = [x for x in matched_all if x["week"] >= 4]
        by_week = [[x for x in development if x["week"] == w]
                   for w in range(4,8)]
        complete = all(bool(x) for x in by_week) and len(development) >= 30
        contrasts = {}
        for comparator in ("momentum", "countOnly", "cash"):
            differences = []
            for group in by_week:
                if group:
                    differences.append(mean(
                        (x["bti1"][1] - 4*x["bti1"][2]) -
                        (x[comparator][1] - 4*x[comparator][2])
                        for x in group))
            contrasts[comparator] = {
                "meanWeeklyPairedImprovementBps": (
                    round(mean(differences), 6) if len(differences)==4 else None),
                "lowerPairedWeekly95Bps": (
                    round(paired_weekly_lower(differences), 6)
                    if len(differences)==4 else None)}
        scored = {
            "scheduledAllWeeks": 80,
            "developmentScheduledWeeks5to8": 40,
            "predecisionPopulation": dict(counts),
            "countOnlyBaselineMedianFromWeeks1to4": count_median,
            "weekly": weekly,
            "developmentFourWeeks": {
                name: {"central1Bps": summarize_policy(development,name,1.0),
                       "adverse4Bps": summarize_policy(development,name,4.0)}
                for name in ("bti1","momentum","countOnly","long","short","cash")},
            "fourWeekPairedContrastsAdverse": contrasts,
            "activityMatchedDescriptive": {
                band: {"n":len(group),
                       "highBurst":sum(r["features"]["state"] == "BURST"
                                       for r in group),
                       "quiet":sum(r["features"]["state"] == "QUIET"
                                   for r in group),
                       "burstMomentumMeanAdverseBps": (
                           round(mean(r["momentumSampledAdverseBps"] for r in group
                                      if r["features"]["state"] == "BURST"
                                      and r["momentumSampledAdverseBps"] is not None),6)
                           if any(r["features"]["state"] == "BURST" and
                                  r["momentumSampledAdverseBps"] is not None
                                  for r in group) else None),
                       "quietMomentumMeanAdverseBps": (
                           round(mean(r["momentumSampledAdverseBps"] for r in group
                                      if r["features"]["state"] == "QUIET"
                                      and r["momentumSampledAdverseBps"] is not None),6)
                           if any(r["features"]["state"] == "QUIET" and
                                  r["momentumSampledAdverseBps"] is not None
                                  for r in group) else None)}
                for band,group in within_count.items()},
            "developmentSourceCoveragePassed": complete,
        }
        primary = scored["developmentFourWeeks"]["bti1"]["adverse4Bps"][
            "meanPerMatchedClockBps"]
        pass_gate = bool(complete and primary is not None and primary > 0
                         and all(contrasts[k]["lowerPairedWeekly95Bps"] is not None
                                 and contrasts[k]["lowerPairedWeekly95Bps"] > 0
                                 for k in ("momentum", "countOnly", "cash")))
        scored["exactIncrementalGatePassed"] = pass_gate
        accepted &= pass_gate
        summaries[symbol] = scored
    return {
        "schema": "MXM_BTI1_FROZEN_ORIGINAL_QUOTE_TIMING_INCREMENTAL_V1",
        "status": ("EXPLORATORY_PROXY_GATE_ONLY_NO_PROMOTION" if accepted else
                   "CLOSED_EXACT_NO_INCREMENTAL_ECONOMIC_GATE"),
        "protocolSha256": protocol_sha,
        "originalQpi1SourceRunId": int(QPI_RUN),
        "originalQpi1SealedSourceSha256": QPI_CIPHER,
        "originalQpi1RawPlaintextSha256": QPI_PLAIN,
        "originalQpi1ReadOnlyRequestsIndependentlyRebuilt": 645,
        "zeroNewBrokerRequests": True,
        "zeroOrders": True,
        "originalQpi1ModelNeverRescored": True,
        "sourceGloballyResearchExposed": True,
        "targets": summaries,
        "pooledBpsNotNetEur": True,
        "netFundedEur": None,
        "historicalCompleteCostFxMargin": False,
        "nativeCloudTickRestartParityDemonstrated": False,
        "independentConfirmation": False,
        "hard21Certified": False,
        "floatingDrawdown30Certified": False,
        "disclosure": "Quote-crossing bps minus ASSUMED 1/4bps slippage, without historical commission, swap, CHF/GBP EUR conversion, financing or real fills. Cash/abstention retained. Same exposed source, never independent validation."
    }


def main():
    tape, protocol_hash = authenticated_tape()
    report = evaluate(tape, protocol_hash)
    OUTPUT.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False) + "\n")
    print("BTI1_AUTHENTIC_QPI1_SOURCE_TIMING_REBUILT_NEW_HYPOTHESIS_ONLY",
          report["status"], flush=True)


if __name__ == "__main__":
    main()
