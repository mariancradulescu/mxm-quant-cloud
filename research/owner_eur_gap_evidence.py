"""Complete missing M1/M5 cells and preserve a separate, account-bound contract timeline."""
from collections import Counter, defaultdict, deque
from decimal import Decimal
import json
import os
import sys
from itertools import groupby
from pathlib import Path

from . import owner_official_eur_source as wire
from . import owner_source_history_expand as previous
from . import owner_eur_historical_development as dated
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import TransportError
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import CaptureContractError, need
from .owner_readonly_auth import authenticate

src = wire.source
OUT = Path("eur-gap-evidence")
START = src.END - 7*src.DAY
SAMPLE_INTERVAL = 6*60_000
SAMPLE_INTERVALS = 5
MAX_PAGES = 710
ORIGINAL_GAP_RUN = "45541671931"


def verified_plan():
    raw = dated.MATRIX.read_bytes()
    need(src.digest(raw) == dated.MATRIX_SHA256, "EUR_GAP_ORIGINAL_MATRIX")
    prior = Path("p05-public/receipt.json").read_bytes()
    need(src.digest(prior) == previous.P05_RECEIPT_SHA, "EUR_GAP_P05_RECEIPT")
    finance = json.loads(prior)["marketCoverage"]
    original = wire.public_original()
    names = {row["name"]:row for row in original["contractRoster"]}
    selected = []
    for row in json.loads(raw)["matrix"]:
        symbol = row["symbol"]
        old = finance.get(symbol)
        if old is None or row["tradingMode"] != 0 or symbol not in names:
            continue
        margin = Decimal(old["currentMinMarginEur"])
        if not 0 < margin < 210:
            continue
        m15 = row["timeframes"]["M15"]
        if not m15:
            continue
        end = min(src.END, m15["throughClose"])
        if end <= START:
            continue
        gaps = [p for p in ("M1","M5") if row["timeframes"][p] is None]
        if gaps:
            selected.append(dict(symbol=symbol, id=names[symbol]["symbolId"],
                assetClass=row["assetClass"], periods=gaps, fromUtc=START, throughExclusive=end))
    need(0 < len(selected) <= len(finance), "EUR_GAP_PLAN_SCOPE")
    return sorted(selected, key=lambda row:row["id"])


def collect_cells(plan, account, request, observed_spans=None):
    receipts = {}
    attempted = 0
    halted = False
    for item in plan:
        by_period = {}
        receipts[item["symbol"]] = by_period
        for period in item["periods"]:
            width = src.PERIODS[period]*60_000
            end = item["throughExclusive"]//width*width
            span = 900*width
            enum = e.ProtoOATrendbarPeriod.Value(period)
            pending = deque((lo,min(lo+span,end)-1) for lo in range(item["fromUtc"],end,span))
            diagnostics = Counter()
            accepted = set()
            for_bounds = []
            while pending:
                lo, hi = pending.popleft()
                if halted or attempted >= MAX_PAGES:
                    for_bounds.append([lo,hi+1,"PENDING_RESUME"])
                    diagnostics["PENDING_RESUME"] += 1
                    continue
                q = m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=item["id"],
                                             fromTimestamp=lo,toTimestamp=hi,period=enum)
                answer, at, status = request(q)
                if status != src.UNCOLLECTED:
                    attempted += 1
                if answer is None:
                    halted = True
                    for_bounds.append([lo,hi+1,status])
                    diagnostics[status] += 1
                    continue
                if previous.page_pair(q,answer) and answer.HasField("hasMore") and answer.hasMore and hi-lo>=2*width:
                    pending.extendleft(reversed(src.split_window(lo,hi)))
                    for_bounds.append([lo,hi+1,"PAGINATION_SPLIT"])
                    diagnostics["PAGINATION_SPLIT"] += 1
                    continue
                description, bars = wire.history.inspect_bars(q,answer,at,closed_through=end)
                code = description["status"]
                if isinstance(answer,m.ProtoOAErrorRes) and answer.errorCode == "NO_QUOTES":
                    code="PROVIDER_NO_QUOTES"
                for_bounds.append([lo,hi+1,code])
                diagnostics[code] += 1
                for b in bars:
                    need(b[0] not in accepted,"EUR_GAP_DUPLICATE_CLOSED_BAR")
                    accepted.add(b[0])
            by_period[period] = dict(closedBars=len(accepted), requests=for_bounds, diagnostics=dict(diagnostics))
            if observed_spans is not None and accepted:
                observed_spans.setdefault(item["symbol"], {})[period] = wire.observed_bar_span(period, accepted)
    return receipts, attempted


def capture():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_REF")=="refs/heads/main"
         and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","EUR_GAP_CAPTURE_CONTEXT")
    run = os.environ["GITHUB_RUN_ID"]
    public = checked_public(Path("eur-gap-recipient"),run)
    plan = verified_plan()
    ids = [row["id"] for row in plan]
    t = wire.OfficialEvidenceTransport()
    journal = None
    samples = []
    cells, requests, interrupted = {}, 0, None
    try:
        account = authenticate(t)
        t.bind(account)
        t.read(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes, "trader")
        t.read(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes, "assets")
        schedule_start = wire.now_ms()
        for slot in range(SAMPLE_INTERVALS+1):
            if slot:
                t.observe_until(schedule_start+slot*SAMPLE_INTERVAL)
            reply = t.read(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=ids),
                           m.ProtoOASymbolByIdRes,f"boundary-contracts-{slot}")
            need(reply is not None and {x.symbolId for x in reply.symbol}==set(ids),"EUR_GAP_TERMS_RESPONSE")
            samples.append(t.journal[-1]["at"])
            print("EUR_GAP_TERM_SAMPLE",slot+1,flush=True)
            if slot==0:
                journal = src.Journal(t,account)
                cells, requests = collect_cells(plan,account,journal.query)
                print("EUR_GAP_HISTORICAL_PAGES",requests,flush=True)
                if journal.halted:
                    interrupted="EUR_GAP_HISTORICAL_TRANSPORT_STOPPED"
                    break
    except (TransportError,CaptureContractError,TimeoutError) as error:
        if t.bound is None:
            raise
        interrupted=wire.safe_reason(error)
    finally:
        t.close()
    OUT.mkdir(exist_ok=False)
    raw = src.canonical(dict(runId=run, plan=plan, historical=journal.packets if journal else [],
        contracts=t.journal, notices=t.changes, samples=samples, acquisitionInterrupted=interrupted,
        cells=cells, historyRequests=requests))
    sealed = seal_new(raw,public,run)
    (OUT/"original.sealed").write_bytes(sealed)
    (OUT/"receipt.json").write_bytes(src.canonical(dict(runId=run,plaintextSha256=src.digest(raw),
        ciphertextSha256=src.digest(sealed),historicalRequests=requests,termSamples=len(samples),
        acquisitionInterrupted=interrupted)))


def intersect(first, second):
    """Intersect observed half-open spans. Calendar breaks stay visible."""
    i = j = 0
    result = []
    while i < len(first) and j < len(second):
        a, b = first[i]
        c, d = second[j]
        left, right = max(a,c), min(b,d)
        if left < right:
            result.append((left,right))
        if b <= d:
            i += 1
        if d <= b:
            j += 1
    return result


def coalesced(intervals):
    result = []
    for start, stop in intervals:
        if result and start <= result[-1][1]:
            left, right = result[-1]
            result[-1] = (left,max(right,stop))
        else:
            result.append((start,stop))
    return result


def integrate_coverage(spans, horizon_start, horizon_end, original_run):
    base = json.loads(dated.MATRIX.read_bytes())
    counts = Counter()
    matches = Counter()
    edges = []
    for row in base["matrix"]:
        symbol = row["symbol"]
        for period, span in spans.get(symbol, {}).items():
            need(row["timeframes"][period] is None, "EUR_GAP_MATRIX_DUPLICATE_CELL")
            row["timeframes"][period] = dict(span, evidenceRun=original_run)
            row["warmup"][period] = span["closedBars"]
            counts[period] += span["closedBars"]
        frames = row["timeframes"]
        if not any(frames.values()):
            continue
        matches["marketsWithBars"] += 1
        simultaneous = [(horizon_start,horizon_end)]
        prior = {}
        for period, frame in frames.items():
            width = src.PERIODS[period]*60_000
            intervals = frame["observedIntervals"] if frame else []
            prior[period] = sum(max(0, (min(horizon_start, stop)-start)//width) for start,stop in intervals)
            simultaneous = intersect(simultaneous,coalesced(intervals))
        if all(frames.values()):
            matches["marketsWithSevenTimeframes"] += 1
        if simultaneous:
            matches["marketsWithSevenTimeframesInWindow"] += 1
            for first, last in simultaneous:
                edges.extend(((first,1),(last,-1)))
        row["registeredWindow"] = dict(previousClosedBars=prior,missingTimeframes=[
            p for p,frame in frames.items() if frame is None or not intersect(
                [(horizon_start,horizon_end)],frame["observedIntervals"])],
            simultaneousObservedBarIntervals=simultaneous)
    minutes = 0
    active = 0
    last = horizon_start
    for time, grouped in groupby(sorted(edges),key=lambda e:e[0]):
        if active >= 2:
            minutes += time-last
        active += sum(delta for _, delta in grouped)
        last = time
    return dict(base, integratedGapRun=original_run, priorMatrixSha256=dated.MATRIX_SHA256,
        window=[horizon_start,horizon_end], addedClosedBarsByTimeframe=dict(counts),
        coverageWithClocks=matches["marketsWithBars"], overlapSummary=dict(matches),
        simultaneousSevenTimeframePriceMinutesAtLeastTwoMarkets=minutes//60_000,
        pricedPortfolioEligibilityCertified=False, economicEvaluations=0, orders=0, cloudActivated=False)


def readback(integrate=False):
    run = ORIGINAL_GAP_RUN if integrate else os.environ["GITHUB_RUN_ID"]
    private = os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    receipt = json.loads((OUT/"receipt.json").read_bytes())
    sealed = (OUT/"original.sealed").read_bytes()
    need(receipt["runId"]==run and receipt["ciphertextSha256"]==src.digest(sealed),"EUR_GAP_CUSTODY")
    raw = unseal_new(sealed,private,run)
    need(receipt["plaintextSha256"]==src.digest(raw),"EUR_GAP_CUSTODY_PLAINTEXT")
    data = json.loads(raw)
    plan = verified_plan()
    need(data["plan"]==plan and data["runId"]==run,"EUR_GAP_VERIFIED_PLAN_MISMATCH")
    account = src.decode(data["contracts"][0]["reqType"],data["contracts"][0]["req"]).ctidTraderAccountId
    need(src.original_account(account),"EUR_GAP_ACCOUNT_BINDING")
    journal = src.ReadbackJournal(data["historical"])
    spans = {} if integrate else None
    if journal.packets:
        cells, tries = collect_cells(plan,account,journal.query,spans)
        need(journal.index==len(journal.packets) and data["cells"]==cells and data["historyRequests"]==tries,
             "EUR_GAP_EXACT_REQUEST_RECONCILIATION")
    else:
        cells, tries = data["cells"], 0
    snapshots = defaultdict(list)
    notices = defaultdict(list)
    trader = None
    assets = {}
    for at, packet in data["notices"]:
        notice = src.decode("ProtoOASymbolChangedEvent",packet)
        need(notice.ctidTraderAccountId==account,"EUR_GAP_NOTICE_ACCOUNT")
        for sid in notice.symbolId:
            notices[sid].append(at)
    for row,q,r in wire.decoded_packets(dict(requests=data["contracts"])):
        if type(r) is m.ProtoOATraderRes:
            trader = r.trader
        if type(r) is m.ProtoOAAssetListRes:
            assets = {asset.assetId:asset.name for asset in r.asset}
        if type(r) is not m.ProtoOASymbolByIdRes:
            continue
        seen = set()
        for terms in r.symbol:
            need(terms.symbolId in q.symbolId and terms.symbolId not in seen,"EUR_GAP_TERM_WIRE_BINDING")
            seen.add(terms.symbolId)
            snapshots[terms.symbolId].append([row["at"],src.digest(terms.SerializeToString())])
    need(trader is not None and "pepperstone" in trader.brokerName.lower() and
         assets.get(trader.depositAssetId)=="EUR","EUR_GAP_ORIGINAL_PEPPERSTONE_EUR")
    timing = {}
    for item in plan:
        sid = item["id"]
        points = sorted(snapshots[sid])
        intervals = []
        for (start,old),(end,new) in zip(points,points[1:]):
            changes = sum(start<t<=end for t in notices[sid])
            intervals.append(dict(fromUtc=start,throughUtc=end,noticeCount=changes,sameEndpointHash=old==new))
        timing[item["symbol"]]=dict(observations=points,intervals=intervals)
    report=dict(sourceRun=run,plan=plan,historicalPages=tries,barsAndMissingPages=cells,
        contracts=timing,acquisitionInterrupted=data["acquisitionInterrupted"],sessionSamples=data["samples"],
        brokerNotices=len(data["notices"]),historicalTariffsCertified=False,
        observationIntervalsEstablishHistoricalContinuity=False, orders=0,cloudActivated=False)
    (OUT/"gap-and-contract-timeline.json").write_bytes(src.canonical(report)+b"\n")
    if integrate:
        matrix = integrate_coverage(spans,START,src.END,run)
        (OUT/"integrated-coverage-matrix.json").write_bytes(src.canonical(matrix)+b"\n")
    print("EUR_GAP_PROTECTED_READBACK_VERIFIED",flush=True)


if __name__=="__main__":
    try:
        if sys.argv[1:]==["--readback"]:
            readback()
        elif sys.argv[1:]==["--integrate-verified-cells"]:
            readback(integrate=True)
        elif not sys.argv[1:]:
            capture()
        else:
            raise ValueError("EUR_GAP_MODE")
    except (CaptureContractError, TransportError, ValueError, TimeoutError) as error:
        print("EUR_GAP_FAILED",wire.safe_reason(error),flush=True)
        raise SystemExit(1) from None
