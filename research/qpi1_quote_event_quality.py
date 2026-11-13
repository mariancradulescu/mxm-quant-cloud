"""QPI1: original BID/ASK revision-event pressure and forecast quality.

Frozen protocol precedes implementation. Price-only, read-only, unfunded;
all raw source/request protobuf is sealed before result scoring.
"""
from __future__ import annotations
import base64
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import mean, median
from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import decode_side
from .guard import require_read_only_request
from .custody import seal_new
from .custody_new import checked_public

START = date(2026, 9, 14)
WEEKS = 8
TARGETS = ("USDCHF", "EURGBP")
DECISION_HOURS = (9, 14)
MAX_REQUESTS = 1500
MAX_AGE = 20000


def direction(value):
    return (value > 0) - (value < 0)


def midpoint(q):
    return (q[0] + q[1]) / 2


def asof(rows, at, max_age=MAX_AGE):
    if not rows:
        return None
    times = [x[0] for x in rows]
    i = bisect_right(times, at) - 1
    return rows[i][1] if i >= 0 and 0 <= at - times[i] <= max_age else None


def pair(bids, asks, at):
    b, a = asof(bids, at), asof(asks, at)
    return (b, a) if b is not None and a is not None and 0 < b <= a else None


def pressure(bids, asks, low, high):
    """Count strictly changing, same-side original broker quotes, no OHLC proxy."""
    counts = Counter()
    for name, rows in (("bid", bids), ("ask", asks)):
        previous = None
        for at, value in rows:
            if at < low:
                previous = value
                continue
            if at > high:
                break
            if previous is not None:
                diff = direction(value - previous)
                if diff:
                    counts[name + ("Up" if diff > 0 else "Down")] += 1
            previous = value
    up = counts["bidUp"] + counts["askUp"]
    down = counts["bidDown"] + counts["askDown"]
    total = up + down
    return ((up - down) / total if total else 0.0), total, dict(counts)


def price_bps(entry, exit_, side):
    initial = midpoint(entry)
    gross = side * (midpoint(exit_) - initial) / initial * 10000
    start = entry[1] if side > 0 else entry[0]
    finish = exit_[0] if side > 0 else exit_[1]
    crossing = side * (finish - start) / initial * 10000
    return [gross, crossing]


def decide(prior_bids, prior_asks, after_bids, after_asks, t):
    before = pair(prior_bids, prior_asks, t - 600000)
    now = pair(prior_bids, prior_asks, t)
    if before is None or now is None:
        return {"state": "MISSING_DECISION"}
    p, updates, counts = pressure(prior_bids, prior_asks, t - 600000, t)
    side = direction(p)
    if not updates:
        return {"state": "ZERO_REVISIONS"}
    if not side:
        return {"state": "BALANCED_REVISIONS"}
    entry = pair(after_bids, after_asks, t + 60000)
    if entry is None:
        return {"state": "MISSING_ENTRY", "side": side, "strength": abs(p)}
    # The original signal is immutable. Recompute subsequent quote pressure
    # ONLY for causal invalidation at 10/20 minutes.
    path = [entry]
    reason = None
    for step in (10, 20, 30):
        at = t + step * 60000
        q = pair(after_bids, after_asks, at)
        if q is None:
            return {"state": "MISSING_MONITOR", "side": side,
                    "strength": abs(p), "failedMinute": step}
        path.append(q)
        if step < 30:
            emerging, _, _ = pressure(after_bids, after_asks,
                                       t + (step - 10) * 60000, at)
            if emerging * side < 0:
                reason = "QUOTE_PRESSURE_REVERSAL"
                break
        else:
            reason = "PROTECTIVE_CEILING"
    result = {
        "state": "CANDIDATE_PRICED", "side": side, "strength": abs(p),
        "entry": entry, "exit": path[-1], "reason": reason,
        "minutes": (len(path) - 1) * 10 if reason == "PROTECTIVE_CEILING"
                   else (10 if len(path) == 2 else 20),
        "candidate": price_bps(entry, path[-1], side),
        "own": direction(midpoint(now) - midpoint(before)),
    }
    fixed = pair(after_bids, after_asks, t + 1800000)
    if fixed is not None:
        sides = {"qpi1": side, "fixed": side,
                 "momentum": result["own"], "long": 1, "short": -1,
                 "cash": 0}
        result["fixed_complete"] = True
        result["paired"] = {
            k: ([0.0, 0.0] if v == 0 else
                price_bps(entry, path[-1] if k == "qpi1" else fixed, v))
            for k, v in sides.items()
        }
    else:
        result["fixed_complete"] = False
    return result


def metrics(rows):
    if not rows:
        return {"count": 0, "hitRate": None, "grossSignedBpsMean": None,
                "quoteCrossingBpsMean": None, "incrementVsOwnMomentumGrossBps": None}
    return {"count": len(rows),
            "hitRate": mean(x["paired"]["qpi1"][0] > 0 for x in rows),
            "grossSignedBpsMean": mean(x["paired"]["qpi1"][0] for x in rows),
            "quoteCrossingBpsMean": mean(x["paired"]["qpi1"][1] for x in rows),
            "incrementVsOwnMomentumGrossBps":
                mean(x["paired"]["qpi1"][0] - x["paired"]["momentum"][0]
                     for x in rows)}


def summarize_target(rows):
    events, weekly, past_strengths = Counter(), [], []
    all_paired = []
    all_quality_high, all_quality_low = [], []
    for w in range(WEEKS):
        week = [x for x in rows if x["week"] == w]
        counts = Counter(x["state"] for x in week)
        priced = [x for x in week if x["state"] == "CANDIDATE_PRICED"]
        paired = [x for x in priced if x.get("fixed_complete")]
        events.update(counts)
        all_paired.extend(paired)
        threshold = median(past_strengths) if w >= 4 and past_strengths else None
        high = [x for x in paired if threshold is not None and x["strength"] > threshold]
        low = [x for x in paired if threshold is not None and x["strength"] <= threshold]
        all_quality_high.extend(high)
        all_quality_low.extend(low)
        weekly.append({
            "start": (START + timedelta(weeks=w)).isoformat(),
            "counts": dict(counts),
            "pricedAdaptive": len(priced),
            "pricedPaired": len(paired),
            "pairedUnavailableAfterEarlyExit": len(priced) - len(paired),
            "exitReasons": dict(Counter(x["reason"] for x in priced)),
            "grossAdaptiveBps": mean(x["candidate"][0] for x in priced) if priced else None,
            "quoteCrossingAdaptiveBps": mean(x["candidate"][1] for x in priced) if priced else None,
            "qualityThresholdFromOnlyPastWeeks": threshold,
            "qualityHigh": metrics(high), "qualityLow": metrics(low),
        })
        past_strengths.extend(x["strength"] for x in priced)
    comparator = {p: {
        "grossMeanBps": mean(x["paired"][p][0] for x in all_paired) if all_paired else None,
        "quoteCrossingMeanBps": mean(x["paired"][p][1] for x in all_paired) if all_paired else None
    } for p in ("qpi1", "fixed", "momentum", "long", "short", "cash")}
    return {
        "counts": dict(events),
        "pairedAll": metrics(all_paired),
        "comparators": comparator,
        "segments": [metrics([x for x in all_paired if x["week"] < 4]),
                     metrics([x for x in all_paired if x["week"] >= 4])],
        "qualityCohortsPastOnlyWeeks5to8": {
            "high": metrics(all_quality_high),
            "low": metrics(all_quality_low),
            "weekly": [{"start": w["start"], "pastMedianStrength": w["qualityThresholdFromOnlyPastWeeks"],
                        "high": w["qualityHigh"], "low": w["qualityLow"]} for w in weekly[4:]],
        },
        "weekly": weekly,
    }


def main():
    run = os.environ["GITHUB_RUN_ID"]
    public = checked_public(Path("new-recipient-output"), run)
    tr = StdlibCTraderTransport()
    requests = 0
    raw = []
    tape = {s: [] for s in TARGETS}
    status = {}
    def request(q, kind, allow_empty=False):
        nonlocal requests
        if requests >= MAX_REQUESTS:
            raise RuntimeError("QPI1_BOUNDED_READONLY_BUDGET_EXHAUSTED")
        require_read_only_request(q)
        reply = tr.request(q)
        requests += 1
        if (allow_empty and type(reply) is m.ProtoOAErrorRes and
            reply.errorCode == "NO_QUOTES" and reply.ctidTraderAccountId == account):
            result = None
        elif (type(reply) is kind and reply.IsInitialized() and
              reply.ctidTraderAccountId == account):
            result = reply
        else:
            raise RuntimeError("QPI1_ORIGINAL_ACCOUNT_RESPONSE_MISMATCH")
        raw.append({
            "request": base64.b64encode(q.SerializeToString()).decode(),
            "requestType": type(q).__name__,
            "response": base64.b64encode(reply.SerializeToString()).decode(),
            "responseType": type(reply).__name__,
        })
        return result

    try:
        account = authenticate(tr)
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account),
                         m.ProtoOATraderRes)
        assets = request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                         m.ProtoOAAssetListRes)
        currency = {a.assetId: a.name for a in assets.asset}
        if ("pepperstone" not in trader.trader.brokerName.casefold() or
            currency.get(trader.trader.depositAssetId) != "EUR"):
            raise RuntimeError("QPI1_NOT_ORIGINAL_PEPPESTONE_EUR")
        roster = request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        available = {x.symbolName: x for x in roster.symbol if x.enabled}
        for name in TARGETS:
            item = available.get(name)
            if item is None:
                status[name] = "SYMBOL_UNAVAILABLE_NO_SUBSTITUTION"
                continue
            details = request(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account, symbolId=[item.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(details.symbol) != 1 or details.symbol[0].symbolId != item.symbolId:
                raise RuntimeError("QPI1_CONTRACT_IDENTITY_UNVERIFIED")
            c = details.symbol[0]
            status[name] = "ORIGINAL_ENABLED_CURRENT_NOT_HISTORICALLY_CERTIFIED"
            for w in range(WEEKS):
                monday = START + timedelta(weeks=w)
                for d in range(5):
                    day = monday + timedelta(days=d)
                    for hour in DECISION_HOURS:
                        t = int(datetime(day.year, day.month, day.day, hour,
                                         tzinfo=timezone.utc).timestamp() * 1000)
                        windows = [(t - 620000, t), (t, t + 1860000)]
                        events = []
                        truncated = False
                        for low, high in windows:
                            by_side = []
                            for kind in (e.BID, e.ASK):
                                reply = request(m.ProtoOAGetTickDataReq(
                                    ctidTraderAccountId=account, symbolId=item.symbolId,
                                    type=kind, fromTimestamp=low,
                                    toTimestamp=high), m.ProtoOAGetTickDataRes, True)
                                if reply is None:
                                    by_side.append([])
                                elif reply.hasMore:
                                    truncated = True
                                    by_side.append([])
                                else:
                                    by_side.append(decode_side(reply.tickData, low, high))
                            events.append(by_side)
                        tape[name].append({
                            "week": w, "decision": t,
                            "truncated": truncated,
                            "before": events[0], "after": events[1],
                        })
    finally:
        tr.close()
    # Original collection is encrypted and hash-bound BEFORE any outcome score.
    plaintext = json.dumps({
        "classification": "ORIGINAL_PEPPERSTONE_QPI1_PROTECTED_TICK_EVENTS",
        "run": run, "rawAuthenticatedReadOnlyMessages": raw,
        "targets": tape, "symbolStatus": status,
        "requestCount": requests,
    }, separators=(",", ":")).encode()
    sealed = seal_new(plaintext, public, run)
    Path("qpi1-original-quote-events.v2.enc").write_bytes(sealed)

    result = {}
    for name in TARGETS:
        scored = []
        for obs in tape[name]:
            if obs["truncated"]:
                row = {"state": "TRUNCATED_SOURCE"}
            else:
                row = decide(*obs["before"], *obs["after"], obs["decision"])
            row["week"] = obs["week"]
            scored.append(row)
        result[name] = {
            "sourceStatus": status.get(name),
            "scheduled": WEEKS * 5 * len(DECISION_HOURS),
            "sampled": len(scored),
            "summary": summarize_target(scored) if scored else None,
        }
    document = {
        "schema": "MXM_QPI1_EXPOSED_DEVELOPMENT_GROSS_NO_NET",
        "protocolSha256": sha256(Path("research/QPI1_QUOTE_EVENT_QUALITY.md").read_bytes()).hexdigest(),
        "sourceRun": int(run), "cipherSha256": sha256(sealed).hexdigest(),
        "plainSha256": sha256(plaintext).hexdigest(),
        "readOnlyRequests": requests, "originalPepperstoneEurAuthenticated": True,
        "targets": result, "brokerOrders": 0, "cloudActivated": False,
        "oauthReauthorized": False, "independentConfirmation": False,
        "fundedRoundTrips": 0, "eurNet": None, "historicalTariffsCertified": False,
        "disclosure": "BID/ASK quote revisions are not trades or DOM; sampled ten-minute monitors are not continuous stops; gross bps and quote crossing are not NET and can omit commission, slippage and currency conversion."
    }
    Path("qpi1-original-public.json").write_text(json.dumps(document, indent=2, allow_nan=False)+"\n")
    print("QPI1_PROTECTED_ORIGINAL_SOURCE_AND_GROSS_COMPLETE",
          {"requests": requests, "symbolStatuses": status,
           "counts": {s: (result[s]["summary"] or {}).get("counts")
                      for s in TARGETS}}, flush=True)


if __name__ == "__main__":
    main()
