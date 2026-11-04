"""Material receive-order, delta reconstruction and no-order boundary contracts."""
import json
import unittest
from pathlib import Path
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as model
from .ctrader_transport import encode_envelope, decode_envelope
from .depth_channel_pilot import ChannelCapture, encode, summarize


class DepthChannelChecks(unittest.TestCase):
    def setUp(self):
        self.p = json.loads(Path('research/depth_channel_protocol.json').read_text())
        self.p.update(minimumDepthEventsAfterWarmup=2, minimumTwoSidedAssociatedStates=2,
                      minimumSizeImbalanceChangesAtUnchangedSpot=1, minimumSupportedSymbols=1)
        self.b = dict(account=5, symbols={'EURUSD':dict(symbolId=1)}, events=[],
                      observationStartMonoNs=0, captureComplete=True)

    def event(self, q, seconds):
        self.b['events'].append(dict(sequence=len(self.b['events']), type=type(q).__name__, protobuf=encode(q),
                                     receivedMonoNs=seconds*10**9, receivedUtcNs=seconds*10**9))

    def depth(self, size=100, deleted=()):
        return m.ProtoOADepthEvent(ctidTraderAccountId=5, symbolId=1, deletedQuotes=deleted, newQuotes=[
            model.ProtoOADepthQuote(id=1, size=size, bid=100000),
            model.ProtoOADepthQuote(id=2, size=100, ask=100010)])

    def spot(self):
        return m.ProtoOASpotEvent(ctidTraderAccountId=5, symbolId=1, bid=100000, ask=100010, timestamp=31000)

    def test_distinct_depth_size_changes_with_fixed_spot_are_retained(self):
        self.event(self.spot(), 31); self.event(self.depth(), 32); self.event(self.depth(300), 33)
        result = summarize(self.b, self.p)
        self.assertTrue(result['sourcePilotPassed'])
        self.assertFalse(result['economicModelEvaluated'])
        self.assertIsNone(result['fundedNetEur'])
        self.assertEqual(result['rows'][0]['counts']['sizeImbalanceChangesAtUnchangedSpot'], 1)
        self.assertEqual(len(result['rows']), 6)  # Absent instruments are not hidden.

    def test_stale_spot_and_missing_depth_side_do_not_pass(self):
        self.event(self.spot(), 1); self.event(self.depth(), 32); self.event(self.depth(300), 33)
        self.assertFalse(summarize(self.b, self.p)['sourcePilotPassed'])
        self.b['events']=[]
        self.event(self.spot(), 31); self.event(self.depth(), 32)
        self.event(m.ProtoOADepthEvent(ctidTraderAccountId=5, symbolId=1, deletedQuotes=[2]), 33)
        self.event(m.ProtoOADepthEvent(ctidTraderAccountId=5, symbolId=1, newQuotes=[model.ProtoOADepthQuote(id=1, size=300, bid=100000)]), 34)
        self.assertFalse(summarize(self.b, self.p)['sourcePilotPassed'])

    def test_delta_replaces_ids_and_unknown_deletions_do_not_manufacture_completeness(self):
        self.event(self.spot(), 31); self.event(self.depth(), 32); self.event(self.depth(300, [999]), 33)
        result=summarize(self.b, self.p)
        self.assertEqual(result['rows'][0]['counts']['unknownDeletedIdsAfterWarmup'], 1)
        self.assertTrue(result['sourcePilotPassed'])
        self.assertFalse(result['fullBookCompletenessProven'])
        self.b['captureComplete']=False
        self.assertFalse(summarize(self.b, self.p)['sourcePilotPassed'])

    def test_receiver_does_not_discard_events_interleaved_with_subscription_ack(self):
        event=decode_envelope(encode_envelope(self.depth())[4:])
        ack=decode_envelope(encode_envelope(m.ProtoOASubscribeDepthQuotesRes(ctidTraderAccountId=5), 'dcp1-0')[4:])
        class FakeTransport:
            def __init__(self):self.frames=[event,ack];self.sent=[]
            def _send_bytes(self, raw):self.sent.append(raw)
            def receive_envelope(self, **kwargs):return self.frames.pop(0)
        t=FakeTransport(); b=dict(events=[], subscriptions=[])
        stream=ChannelCapture(t,b,5,[1])
        stream.subscribe(m.ProtoOASubscribeDepthQuotesReq(ctidTraderAccountId=5,symbolId=[1]))
        self.assertEqual(len(b['events']),1)
        self.assertEqual(len(b['subscriptions']),1)
        self.assertEqual(len(t.sent),1)
        with self.assertRaises(Exception):
            stream.subscribe(m.ProtoOANewOrderReq())
        with self.assertRaises(Exception):
            stream.subscribe(m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=5,symbolId=[1]))
        self.assertEqual(len(t.sent),1)

    def test_reversed_receive_clock_and_wrong_account_rejected(self):
        self.event(self.spot(), 33); self.event(self.depth(), 32)
        with self.assertRaises(Exception):summarize(self.b,self.p)
        self.b['events']=[]
        q=self.depth();q.ctidTraderAccountId=6;self.event(q,32)
        with self.assertRaises(Exception):summarize(self.b,self.p)


if __name__ == '__main__':unittest.main()
