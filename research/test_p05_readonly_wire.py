"""Demonstrate that trading-capable OAuth cannot send order-changing traffic.

All fixtures are offline. The fake socket records bytes but is NEVER networked.
The assertions cover request, batch, serializer and final socket send path.
"""
import struct
import unittest

from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_transport import (
    StdlibCTraderTransport, ProtoMessage, encode_envelope, TransportError
)
from .p05_safe_transport import P05ReadOnlyTransport, check_outbound_frame
from .guard import CaptureContractError, require_read_only_request, ALLOWED

DENIED = (
    "ProtoOANewOrderReq",
    "ProtoOAAmendOrderReq",
    "ProtoOACancelOrderReq",
    "ProtoOAClosePositionReq",
    "ProtoOAAmendPositionSLTPReq",
    "ProtoOAReconcileReq",  # not in approved read-only list
    "ProtoOADealListReq",   # not in approved read-only list
)

class SpySocket:
    def __init__(self):
        self.sent = []
    def sendall(self, value):
        self.sent.append(value)
    def close(self):
        pass

class ReadOnlyWireChecks(unittest.TestCase):
    def test_explicit_allowlist_has_no_order_operations(self):
        self.assertIn("ProtoOAGetTrendbarsReq", ALLOWED)
        self.assertIn("ProtoOAGetTickDataReq", ALLOWED)
        self.assertIn("ProtoOAExpectedMarginReq", ALLOWED)
        self.assertTrue(all("Order" not in n and "Position" not in n for n in ALLOWED))
        self.assertTrue(all(n.endswith("Req") for n in ALLOWED))

    def test_all_known_trading_mutations_fail_before_connect(self):
        seen = 0
        for name in DENIED:
            cls = getattr(m, name, None)
            if cls is None:
                continue
            seen += 1
            order = cls()
            with self.subTest(name=name):
                with self.assertRaises(CaptureContractError):
                    require_read_only_request(order)
                t = P05ReadOnlyTransport()
                def must_not_connect():
                    self.fail("BLOCKED REQUEST MUST NEVER CONNECT")
                t.connect = must_not_connect
                with self.assertRaises(CaptureContractError):
                    t.request(order)
                with self.assertRaises(CaptureContractError):
                    t.request_batch([order])
                # Original serializer remains immutable for legacy parity.
                # The NEW transport verifies even a prebuilt partial raw frame.
                raw = ProtoMessage(payloadType=order.payloadType,
                                   payload=order.SerializePartialToString())
                with self.assertRaises(CaptureContractError):
                    check_outbound_frame(encode_envelope(raw))
        self.assertGreaterEqual(seen, 4, "expected native trading request message definitions")

    def test_raw_envelope_cannot_bypass_encoding(self):
        order = m.ProtoOANewOrderReq()
        raw = ProtoMessage(payloadType=order.payloadType, payload=order.SerializePartialToString())
        # The original formatter is frozen; the NEW collector rejects the
        # frame at the final socket boundary instead.
        wire = encode_envelope(raw)
        with self.assertRaises(CaptureContractError):
            check_outbound_frame(wire)

    def test_direct_raw_frame_cannot_reach_socket(self):
        order = m.ProtoOANewOrderReq()
        raw = ProtoMessage(payloadType=order.payloadType, payload=order.SerializePartialToString()).SerializeToString()
        frame = struct.pack("!I", len(raw)) + raw
        t = P05ReadOnlyTransport()
        spy = SpySocket()
        t._sock = spy
        with self.assertRaises(CaptureContractError):
            t._send_bytes(frame)
        self.assertEqual(spy.sent, [])

    def test_approved_auth_read_request_and_heartbeat_can_serialize(self):
        req = m.ProtoOAApplicationAuthReq(clientId="FAKE_OFFLINE", clientSecret="FAKE_OFFLINE")
        require_read_only_request(req)
        data = encode_envelope(req)
        self.assertGreater(len(data), 4)
        self.assertEqual(len(data)-4, struct.unpack("!I", data[:4])[0])
        t = P05ReadOnlyTransport()
        spy = SpySocket()
        t._sock = spy
        t._send_bytes(data)
        self.assertEqual(len(spy.sent), 1)

    def test_unknown_and_invalid_raw_frame_fail_closed(self):
        t = P05ReadOnlyTransport()
        spy = SpySocket()
        t._sock = spy
        for raw in (b"", b"xxxx", b"\x00\x00\x00\x02xx"):
            with self.assertRaises(TransportError):
                t._send_bytes(raw)
        self.assertEqual(spy.sent, [])

if __name__ == "__main__":
    unittest.main()
