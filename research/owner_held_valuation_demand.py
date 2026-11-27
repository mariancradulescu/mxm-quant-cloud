"""Frozen-report demand registry, not broker requests or reconstructed equity."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import zipfile

STUDY = 'OWNER_HELD_VALUATION_DEMAND_1'
PARENT = 'MONETARY_NET_HORIZON_CROSS_CONTEXT_1'
INPUTS = {
    'earlier': (15176413393, '12553a26e1b2ae9b587baa7443fac7c2e5cf71082965a73092fed50a2848348c'),
    'recent': (15175739827, '1a68b4f0de7a2accb20cecfd7b776b3d8fa6d2e1c8be18939de85fec691a7839'),
}
STEP = 300000
OFFSET = 15000


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def kind(reason):
    if reason.startswith('MISSING_CLOSED_') and reason.endswith('_WITNESS'):
        return 'VERIFY_CALENDAR_AND_LATEST_SIDE_PREFIX'
    if reason.startswith('MISSING_QUOTE_CONVERSION:'):
        return 'RESOLVE_AUTHENTIC_CURRENCY_ROUTE'
    if reason == 'NO_EXECUTABLE_FRAME_AND_NOT_VERIFIED_CLOSED':
        return 'VERIFY_FRESH_TAPE_OR_CONTRACT_CALENDAR'
    if reason == 'BETWEEN_DECISIONS_UNATTRIBUTED':
        return 'TRACE_EVENT_AND_HELD_MARKS'
    return 'VERIFY_TERMS_OR_OTHER_LOCAL_EVIDENCE'


def intervals(clocks):
    """Only consecutive observed grid clocks; never infer coverage between events."""
    rows = []
    for at in sorted(set(clocks)):
        if rows and at % STEP == OFFSET and rows[-1]['Last'] % STEP == OFFSET and at == rows[-1]['Last'] + STEP:
            rows[-1]['Last'] = at
            rows[-1]['Count'] += 1
        else:
            rows.append(dict(First=at, Last=at, Count=1))
    return rows


def build(scope, archive):
    artifact, expected = INPUTS[scope]
    with Path(archive).open('rb') as f:
        require(hashlib.file_digest(f, 'sha256').hexdigest() == expected, 'ARCHIVE_SHA256')
    demand = collections.defaultdict(collections.Counter)
    sole = collections.defaultdict(collections.Counter)
    books = collections.defaultdict(set)
    unknown = missing = offgrid = missing_margin = 0
    with zipfile.ZipFile(archive) as z:
        def read(name):
            return json.loads(z.read(name))
        summary = read('summary.json')
        source = read('source-receipt.json')
        require(summary['Study'] == source['Study'] == PARENT and summary['Scope'] == source['Scope'] == scope and
                summary['SourceSha256'] == source['SourceSha256'] and summary['ProtocolSha256'] == source['ProtocolSha256'] and
                summary['Orders'] == source['Orders'] == 0 and not summary['CloudActivated'] and not source['CloudActivated'], 'PARENT_BINDING')
        for stress in range(3):
            report = read(f'S{stress}-result.json')
            require(report['Study'] == PARENT and report['SourceSha256'] == source['SourceSha256'] and
                    report['ProtocolSha256'] == source['ProtocolSha256'] and report['Stress'] == stress / 2 and
                    report['Orders'] == 0 and not report['CloudActivated'], 'SCENARIO_BINDING')
            gaps = collections.defaultdict(set)
            for g in read(f'S{stress}-holding-valuation-gaps.json'):
                for at in g['Clocks']:
                    gaps[g['Symbol'], at].add(g['Reason'])
            for book in report['CommonBooks']:
                d = book['Details']
                events = []
                ep = {e['PositionId']: e for e in d['Episodes']}
                for a in d['Admissions']:
                    if a['FillAt'] is None:
                        continue
                    key = a['PositionId']
                    events.append((a['FillAt'], 1, key, a['Symbol']))
                    if key in ep:
                        events.append((ep[key]['CloseAt'], -1, key, a['Symbol']))
                events.sort()
                active = {}
                j = 0
                prev = -1
                for q in d['EquityPath']:
                    at = q['At']
                    require(at >= prev, 'EQUITY_ORDER')
                    prev = at
                    while j < len(events) and events[j][0] <= at:
                        _, op, key, symbol = events[j]
                        j += 1
                        if op == 1:
                            active[key] = symbol
                        else:
                            active.pop(key, None)
                    if q['EquityEur'] is not None:
                        continue
                    unknown += 1
                    require(len(active) == q['Held'], 'HELD_COUNT_PARITY')
                    symbols = set(active.values())
                    found = {(s, r) for s in symbols for r in gaps[s, at]}
                    if not found:
                        missing += 1
                        offgrid += int(at % STEP != OFFSET)
                        missing_margin += int(q['UsedMarginEur'] is None)
                        found = {(s, 'BETWEEN_DECISIONS_UNATTRIBUTED' if at % STEP != OFFSET else 'GRID_UNATTRIBUTED') for s in symbols}
                    for key in found:
                        demand[key][at] += 1
                        sole[key][at] += int(len(symbols) == 1)
                        books[key].add((stress, book['Id']))
    rows = []
    for (symbol, reason), counts in demand.items():
        key = symbol, reason
        rows.append(dict(Symbol=symbol, Reason=reason, NextEvidence=kind(reason),
                         DistinctClocks=len(counts), AffectedBookClockOccurrences=sum(counts.values()),
                         SoleHeldSymbolOccurrences=sum(sole[key].values()), AffectedScenarioBooks=len(books[key]),
                         ObservedIntervals=intervals(counts), PriorityBasis='SHARED_BOOK_DECISION_CONTINUITY_NOT_MONETARY_LOSS'))
    rows.sort(key=lambda r: (-r['AffectedBookClockOccurrences'], -r['SoleHeldSymbolOccurrences'], r['Symbol'], r['Reason']))
    return dict(Scope=scope, Artifact=artifact, ArchiveSha256=expected, SourceSha256=source['SourceSha256'],
                ProtocolSha256=source['ProtocolSha256'], UnknownBookClockOccurrences=unknown,
                UnattributedBookClockOccurrences=missing, UnattributedOffGrid=offgrid,
                UnattributedUsedMarginUnknown=missing_margin,
                AttributedDistinctSymbolReasonClocks=sum(r['DistinctClocks'] for r in rows if not r['Reason'].endswith('_UNATTRIBUTED')),
                UnattributedDistinctHeldSymbolClocks=sum(r['DistinctClocks'] for r in rows if r['Reason'].endswith('_UNATTRIBUTED')),
                Rows=rows, Orders=0, CloudActivated=False, SourceBrokerRequests=0,
                EquityRecovered=False, RequestAuthorization=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--earlier', required=True, type=Path)
    p.add_argument('--recent', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    result = dict(Study=STUDY, ScopeReports=[build(s, getattr(a, s)) for s in INPUTS],
                  OriginalPoliciesReplayed=0, Orders=0, CloudActivated=False, SourceBrokerRequests=0,
                  RequiredBeforeCapture=['Verify compatible source and contract calendar', 'Reuse authenticated tape and latest prefixes',
                                         'Resolve official currency routes', 'Deduplicate actual missing source intervals'],
                  EquityRecovered=False, RequestAuthorization=False)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    for r in result['ScopeReports']:
        print(r['Scope'], {k: v for k, v in r.items() if k not in ('Rows',)})


if __name__ == '__main__':
    main()
