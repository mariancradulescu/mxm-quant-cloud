"""DCP1: preserve and audit a bounded, outcome-blind live information channel."""
import base64
from decimal import Decimal
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from .collect import authenticate, HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport, encode_envelope, extract_payload, ProtoHeartbeatEvent
from .ctrader_proto import OpenApiMessages_pb2 as m
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .decode import need
from .guard import require_read_only_request

P = Path('research/depth_channel_protocol.json')
SCHEMA = 'mxm-prospective-depth-channel-v1'
EVENTS = (m.ProtoOADepthEvent, m.ProtoOASpotEvent)
SUBSCRIPTIONS = {m.ProtoOASubscribeSpotsReq: m.ProtoOASubscribeSpotsRes,
                 m.ProtoOASubscribeDepthQuotesReq: m.ProtoOASubscribeDepthQuotesRes}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(q):
    return base64.b64encode(q.SerializeToString()).decode()


def decode(name, raw):
    q = getattr(m, name)()
    q.ParseFromString(base64.b64decode(raw, validate=True))
    need(q.IsInitialized(), 'DCP1_INCOMPLETE_PROTOBUF')
    return q


class ChannelCapture:
    # This isolated, exact subscription allowlist does not widen the existing
    # historical transport guard or expose any order/cancel/refresh operation.
    def __init__(self, transport, bundle, account, symbols):
        self.t, self.b, self.account, self.symbols = transport, bundle, account, set(symbols)

    def record_event(self, envelope):
        q = extract_payload(envelope)
        if type(q) not in EVENTS:
            need(False, 'DCP1_UNEXPECTED_UNSOLICITED_MESSAGE')
        need(q.IsInitialized() and q.ctidTraderAccountId == self.account and q.symbolId in self.symbols,
             'DCP1_EVENT_ACCOUNT_OR_SYMBOL')
        # The call site is immediately after complete frame reception. These are
        # availability observations; broker event creation clocks are not invented.
        self.b['events'].append(dict(sequence=len(self.b['events']), type=type(q).__name__,
                                     protobuf=encode(q), receivedMonoNs=time.monotonic_ns(),
                                     receivedUtcNs=time.time_ns()))

    def receive(self, deadline, wanted=None):
        envelope = self.t.receive_envelope(deadline=deadline)
        if envelope.payloadType == ProtoHeartbeatEvent().payloadType:
            self.t.send_heartbeat()
            return None
        if wanted is not None and envelope.clientMsgId == wanted:
            return extract_payload(envelope)
        self.record_event(envelope)
        return None

    def subscribe(self, request):
        need(type(request) in SUBSCRIPTIONS and request.IsInitialized() and
             request.payloadType == type(request)().payloadType and request.ctidTraderAccountId == self.account and
             set(request.symbolId) == self.symbols and len(request.symbolId) == len(self.symbols),
             'DCP1_SUBSCRIPTION_NOT_ALLOWLISTED')
        if type(request) is m.ProtoOASubscribeSpotsReq:
            need(request.HasField('subscribeToSpotTimestamp') and request.subscribeToSpotTimestamp,
                 'DCP1_SPOT_TIMESTAMP_REQUEST_REQUIRED')
        message_id = 'dcp1-' + str(len(self.b['subscriptions']))
        self.t._send_bytes(encode_envelope(request, message_id))
        deadline = time.monotonic() + 30
        while True:
            response = self.receive(deadline, message_id)
            if response is None:
                continue
            need(type(response) is SUBSCRIPTIONS[type(request)] and response.IsInitialized() and
                 response.ctidTraderAccountId == self.account, 'DCP1_SUBSCRIPTION_RESPONSE')
            self.b['subscriptions'].append(dict(requestType=type(request).__name__, requestProtobuf=encode(request),
                                                 type=type(response).__name__, protobuf=encode(response)))
            return


def summarize(bundle, protocol):
    states = {}
    for symbol, row in bundle['symbols'].items():
        states[row['symbolId']] = dict(symbol=symbol, book={}, spot={}, counts=Counter(),
                                      lastAssociated=None, imbalance=None)
    cutoff = bundle['observationStartMonoNs'] + protocol['warmupSeconds'] * 10**9
    deadline = bundle['observationStartMonoNs'] + protocol['captureSeconds'] * 10**9
    last_mono = -1
    for seq, row in enumerate(bundle['events']):
        need(row['sequence'] == seq and row['receivedMonoNs'] >= last_mono, 'DCP1_RECEIVE_ORDER')
        last_mono = row['receivedMonoNs']
        q = decode(row['type'], row['protobuf'])
        need(type(q) in EVENTS and q.ctidTraderAccountId == bundle['account'] and q.symbolId in states,
             'DCP1_RECONSTRUCTED_EVENT_BINDING')
        s = states[q.symbolId]
        at = row['receivedMonoNs']
        scored = cutoff <= at <= deadline
        c = s['counts']
        c['totalReceivedEvents'] += 1
        if type(q) is m.ProtoOASpotEvent:
            if scored:
                c['spotEventsAfterWarmup'] += 1
                c['spotEventsWithBrokerTimestamp'] += int(q.HasField('timestamp'))
            for side in ('bid', 'ask'):
                if q.HasField(side):
                    s['spot'][side] = (getattr(q, side), at)
            continue
        if scored:
            c['depthEventsAfterWarmup'] += 1
        for identity in q.deletedQuotes:
            if identity not in s['book'] and scored:
                c['unknownDeletedIdsAfterWarmup'] += 1
            s['book'].pop(identity, None)
        for quote in q.newQuotes:
            sides = [side for side in ('bid', 'ask') if quote.HasField(side)]
            if len(sides) != 1 or getattr(quote, sides[0]) <= 0:
                c['malformedDepthQuotes'] += 1
                s['book'].pop(quote.id, None)
            else:
                s['book'][quote.id] = (sides[0], getattr(quote, sides[0]), quote.size)
        if not scored:
            continue
        levels = {'bid': Counter(), 'ask': Counter()}
        for side, price, size in s['book'].values():
            if size > 0:
                levels[side][price] += size
        if not levels['bid'] or not levels['ask']:
            continue
        bid_prices, ask_prices = sorted(levels['bid'], reverse=True), sorted(levels['ask'])
        if bid_prices[0] >= ask_prices[0]:
            c['crossedObservedBooks'] += 1
            continue
        if not all(side in s['spot'] and 0 <= at-s['spot'][side][1] <= protocol['maximumSpotSideReceiveAgeMs']*10**6
                   for side in ('bid', 'ask')):
            continue
        spot = (s['spot']['bid'][0], s['spot']['ask'][0])
        if spot[0] <= 0 or spot[0] >= spot[1]:
            c['crossedSpotStates'] += 1
            continue
        c['twoSidedAssociatedStates'] += 1
        if (bid_prices[0], ask_prices[0]) != spot:
            c['observedTopDiffersFromSpot'] += 1
        bid_size = sum(levels['bid'][price] for price in bid_prices[:3])
        ask_size = sum(levels['ask'][price] for price in ask_prices[:3])
        imbalance = Fraction(bid_size-ask_size, bid_size+ask_size)
        if s['lastAssociated'] == spot and s['imbalance'] is not None and s['imbalance'] != imbalance:
            c['sizeImbalanceChangesAtUnchangedSpot'] += 1
        s['lastAssociated'], s['imbalance'] = spot, imbalance
    rows = []
    for symbol in protocol['universe']:
        state = next((s for s in states.values() if s['symbol'] == symbol), None)
        c = state['counts'] if state else Counter()
        counts = {key: c[key] for key in ('totalReceivedEvents', 'depthEventsAfterWarmup', 'spotEventsAfterWarmup',
                  'spotEventsWithBrokerTimestamp', 'unknownDeletedIdsAfterWarmup', 'malformedDepthQuotes',
                  'crossedObservedBooks', 'twoSidedAssociatedStates', 'crossedSpotStates',
                  'observedTopDiffersFromSpot', 'sizeImbalanceChangesAtUnchangedSpot')}
        supported = (c['depthEventsAfterWarmup'] >= protocol['minimumDepthEventsAfterWarmup'] and
                     c['twoSidedAssociatedStates'] >= protocol['minimumTwoSidedAssociatedStates'] and
                     c['sizeImbalanceChangesAtUnchangedSpot'] >= protocol['minimumSizeImbalanceChangesAtUnchangedSpot'] and
                     c['malformedDepthQuotes'] == 0)
        rows.append(dict(symbol=symbol, available=state is not None, counts=counts, informationChannelSupported=supported))
    passed = bundle['captureComplete'] and sum(r['informationChannelSupported'] for r in rows) >= protocol['minimumSupportedSymbols']
    return dict(schema='mxm-depth-channel-pilot-result-v1', rows=rows, sourcePilotPassed=passed,
                verdict='VARIABLE_DISPLAYED_DEPTH_CHANNEL_OBSERVED_ECONOMIC_VALUE_UNTESTED' if passed else
                        'PREDECLARED_DISPLAYED_DEPTH_CHANNEL_SOURCE_GATE_NOT_MET',
                captureComplete=bundle['captureComplete'], captureError=bundle.get('captureError'),
                fullStudyAdmitted=False, returnsInspected=False, fundedNetEur=None,
                historicalDepthPanelEstablished=False, fullBookCompletenessProven=False,
                exchangeTimingOrLatencyProven=False, executableSizeProven=False,
                independentEconomicConfirmation=False, economicModelEvaluated=False,
                hard21Proven=False, ordersSubmitted=0, cloudActivated=False)


def audit(bundle, protocol):
    need(bundle['schema'] == SCHEMA and bundle['protocolSha256'] == sha(P.read_bytes()) and bundle['readOnly'], 'DCP1_PROTOCOL')
    account = bundle['account']
    fp = sha(f'ctrader-account:{account}'.encode())
    need(sha(fp.encode()) == HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT, 'DCP1_ORIGINAL_ACCOUNT')
    reconstructed = []
    for row in bundle['metadata']:
        q = decode(row['requestType'], row['requestProtobuf']); require_read_only_request(q)
        r = decode(row['type'], row['protobuf'])
        need(q.ctidTraderAccountId == account and r.ctidTraderAccountId == account, 'DCP1_METADATA_ACCOUNT')
        reconstructed.append((q, r))
    need(len(reconstructed) >= 3, 'DCP1_METADATA_MISSING')
    trader, assets, listing = reconstructed[:3]
    need(type(trader[1]) is m.ProtoOATraderRes and type(assets[1]) is m.ProtoOAAssetListRes and
         type(listing[1]) is m.ProtoOASymbolsListRes, 'DCP1_METADATA_TYPES')
    asset_names = {x.assetId: x.name for x in assets[1].asset}
    need('pepperstone' in trader[1].trader.brokerName.lower() and asset_names[trader[1].trader.depositAssetId] == 'EUR', 'DCP1_BROKER_EUR')
    available = {x.symbolName: x for x in listing[1].symbol if x.enabled and x.symbolName in protocol['universe']}
    need(set(bundle['symbols']) == set(available), 'DCP1_FIXED_UNIVERSE')
    for symbol, row in bundle['symbols'].items():
        cq, cr = reconstructed[row['contractIndex']]; mq, mr = reconstructed[row['marginIndex']]
        need(type(cq) is m.ProtoOASymbolByIdReq and type(cr) is m.ProtoOASymbolByIdRes and
             list(cq.symbolId) == [available[symbol].symbolId] and len(cr.symbol) == 1 and cr.symbol[0].symbolId == row['symbolId'], 'DCP1_CONTRACT')
        need(type(mq) is m.ProtoOAExpectedMarginReq and type(mr) is m.ProtoOAExpectedMarginRes and
             mq.symbolId == row['symbolId'] and list(mq.volume) == [cr.symbol[0].minVolume] and
             mr.HasField('moneyDigits') and len(mr.margin) == 1 and mr.margin[0].volume == cr.symbol[0].minVolume, 'DCP1_MIN_MARGIN')
    ids = {x['symbolId'] for x in bundle['symbols'].values()}
    need(len(bundle['subscriptions']) == 2, 'DCP1_SUBSCRIPTIONS_MISSING')
    for row, kind in zip(bundle['subscriptions'], SUBSCRIPTIONS):
        q = decode(row['requestType'], row['requestProtobuf']); r = decode(row['type'], row['protobuf'])
        need(type(q) is kind and type(r) is SUBSCRIPTIONS[kind] and q.ctidTraderAccountId == account and
             r.ctidTraderAccountId == account and set(q.symbolId) == ids and len(q.symbolId) == len(ids), 'DCP1_SUBSCRIPTION_BINDING')
        if kind is m.ProtoOASubscribeSpotsReq:
            need(q.HasField('subscribeToSpotTimestamp') and q.subscribeToSpotTimestamp, 'DCP1_TIMESTAMP_REQUEST')
    need(len(reconstructed)+2 <= protocol['maximumEvidenceRequestsExcludingOAuth'] and
         len(bundle['events']) <= protocol['maximumEvents'] and
         sum(len(x['protobuf']) for x in bundle['events']) <= protocol['maximumEncodedEvidenceBytes'], 'DCP1_BUDGET')
    if bundle['captureComplete']:
        need(bundle['observationEndMonoNs'] >= bundle['observationStartMonoNs'] + protocol['captureSeconds']*10**9, 'DCP1_DURATION')
    return dict(evidenceRequestsExcludingOAuth=len(reconstructed)+2, retainedEvents=len(bundle['events']),
                originalAccountBindingRechecked=True, oauthScope='EXPLICIT_VIEW_AT_AUTHENTICATION',
                rawReadbackMatched=True)


def collect():
    need(not Path('docs/DCP1_AUTHENTIC_CHANNEL_RESULT.json').exists(), 'DCP1_FROZEN_NO_RERUN')
    protocol = json.loads(P.read_text()); run = os.environ['GITHUB_RUN_ID']
    recipient = checked_public(Path('new-source-recipient'), run)
    t = StdlibCTraderTransport(); b = None
    def seal():
        if b is None:
            return
        raw = seal_new(json.dumps(b, sort_keys=True).encode(), recipient, run)
        out = Path('sealed-output'); out.mkdir(exist_ok=True)
        (out/'source.envelope.json').write_bytes(raw)
        (out/'receipt.public.json').write_text(json.dumps(dict(runId=run, sha256=sha(raw)))+'\n')
    try:
        account = authenticate(t)
        b = dict(schema=SCHEMA, protocolSha256=sha(P.read_bytes()), readOnly=True, account=account,
                 metadata=[], subscriptions=[], symbols={}, events=[], captureComplete=False)
        def request(q, kind):
            need(len(b['metadata'])+2 < protocol['maximumEvidenceRequestsExcludingOAuth'], 'DCP1_REQUEST_BUDGET')
            r = t.request(q)
            need(type(r) is kind and r.IsInitialized() and r.ctidTraderAccountId == account, 'DCP1_METADATA_RESPONSE')
            ix = len(b['metadata'])
            b['metadata'].append(dict(requestType=type(q).__name__, requestProtobuf=encode(q), type=type(r).__name__, protobuf=encode(r)))
            return r, ix
        trader = request(m.ProtoOATraderReq(ctidTraderAccountId=account), m.ProtoOATraderRes)[0].trader
        assets = {x.assetId: x.name for x in request(m.ProtoOAAssetListReq(ctidTraderAccountId=account), m.ProtoOAAssetListRes)[0].asset}
        need('pepperstone' in trader.brokerName.lower() and assets[trader.depositAssetId] == 'EUR', 'DCP1_BROKER_EUR')
        listing = {x.symbolName:x for x in request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account, includeArchivedSymbols=False), m.ProtoOASymbolsListRes)[0].symbol if x.enabled}
        for symbol in protocol['universe']:
            if symbol not in listing:
                continue
            identity = listing[symbol].symbolId
            detail, ci = request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account, symbolId=[identity]), m.ProtoOASymbolByIdRes)
            need(len(detail.symbol) == 1 and detail.symbol[0].HasField('minVolume') and detail.symbol[0].minVolume > 0, 'DCP1_MIN_UNITS')
            _, mi = request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account, symbolId=identity, volume=[detail.symbol[0].minVolume]), m.ProtoOAExpectedMarginRes)
            b['symbols'][symbol] = dict(symbolId=identity, contractIndex=ci, marginIndex=mi)
        need(bool(b['symbols']), 'DCP1_NO_SYMBOLS')
        ids = [x['symbolId'] for x in b['symbols'].values()]
        b['observationStartMonoNs'] = time.monotonic_ns(); b['observationStartUtcNs'] = time.time_ns()
        stream = ChannelCapture(t, b, account, ids)
        stream.subscribe(m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=account, symbolId=ids, subscribeToSpotTimestamp=True))
        stream.subscribe(m.ProtoOASubscribeDepthQuotesReq(ctidTraderAccountId=account, symbolId=ids))
        deadline = b['observationStartMonoNs']/10**9 + protocol['captureSeconds']
        last_seal = time.monotonic(); seal()
        encoded_bytes = 0; previous_count = 0
        while time.monotonic() < deadline:
            if time.monotonic()-t._last_send >= 10:
                t.send_heartbeat()
            try:
                stream.receive(deadline)
            except TimeoutError:
                break
            for row in b['events'][previous_count:]:
                encoded_bytes += len(row['protobuf'])
            previous_count = len(b['events'])
            need(len(b['events']) < protocol['maximumEvents'] and encoded_bytes < protocol['maximumEncodedEvidenceBytes'], 'DCP1_EVENT_BUDGET')
            if time.monotonic()-last_seal >= 30:
                seal(); last_seal = time.monotonic()
        b['observationEndMonoNs'] = time.monotonic_ns()
        b['captureComplete'] = b['observationEndMonoNs'] >= b['observationStartMonoNs']+protocol['captureSeconds']*10**9
        b['auditReceipt'] = audit(b, protocol)
        b['summary'] = summarize(b, protocol)
        seal()
        print('DCP1_BOUNDED_CHANNEL_SEALED '+json.dumps(b['auditReceipt'], sort_keys=True), flush=True)
    except Exception:
        if b is not None:
            b['captureError'] = 'BOUNDED_CAPTURE_INCOMPLETE'; seal()
        raise
    finally:
        t.close()  # End the bounded subscriptions; no reconnect or resubscription.


def readback():
    need(not Path('docs/DCP1_AUTHENTIC_CHANNEL_RESULT.json').exists(), 'DCP1_FROZEN_NO_RERUN')
    protocol = json.loads(P.read_text()); run = os.environ['GITHUB_RUN_ID']
    raw = Path('sealed-output/source.envelope.json').read_bytes()
    receipt = json.loads(Path('sealed-output/receipt.public.json').read_text())
    need(receipt['runId'] == run and receipt['sha256'] == sha(raw), 'DCP1_ENVELOPE_BINDING')
    b = json.loads(unseal_new(raw, os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(), run))
    source_audit = audit(b, protocol); result = summarize(b, protocol)
    if 'summary' in b:
        need(result == b['summary'] and source_audit == b['auditReceipt'], 'DCP1_INDEPENDENT_RAW_RECONSTRUCTION')
    financial = []
    for symbol, row in b['symbols'].items():
        cr = b['metadata'][row['contractIndex']]; mr = b['metadata'][row['marginIndex']]
        contract = decode(cr['type'], cr['protobuf']).symbol[0]
        margin = decode(mr['type'], mr['protobuf'])
        scale = Decimal(10)**margin.moneyDigits
        financial.append(dict(symbol=symbol, minimumUnits=str(Decimal(contract.minVolume)/100),
                              currentBuyMarginEur=str(Decimal(margin.margin[0].buyMargin)/scale),
                              currentSellMarginEur=str(Decimal(margin.margin[0].sellMargin)/scale),
                              historicalOrRiskAdmission=False))
    result['currentMinimumFinancialContext'] = financial
    result.update(protocol=protocol, protocolSha256=sha(P.read_bytes()), sourceAudit=source_audit,
                  sourceRunId=int(run), sourceCiphertextSha256=sha(raw), rawReadbackMatched=True)
    Path('depth-channel.public.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print('DCP1_CHANNEL_RESULT '+json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        readback() if '--readback' in sys.argv else collect()
    except Exception as error:
        import traceback
        print('DCP1_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)), flush=True)
        raise SystemExit(1)
