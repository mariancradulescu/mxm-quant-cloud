"""OWNER 2026-11-23 LIVE read-only protection around frozen original transport.

Never alter research/ctrader_transport.py: existing study hashes depend on it.
Only this adapter is authorized for newly collected P0/P0.5 market evidence.
The invariant is verified at the last socket-bound byte frame even when callers
possess a trading-scope token. Heartbeats are the sole non-request exception.
"""
import struct

from .ctrader_transport import (
    StdlibCTraderTransport, ProtoHeartbeatEvent, ProtoMessage,
    MAX_FRAME_BYTES, TransportError, decode_envelope, extract_payload
)
from .guard import require_read_only_request

def check_outbound_frame(frame):
    if not isinstance(frame, bytes) or len(frame) < 5:
        raise TransportError("P05_OUTBOUND_FRAME_INVALID")
    n = struct.unpack("!I", frame[:4])[0]
    if n <= 0 or n > MAX_FRAME_BYTES or n != len(frame) - 4:
        raise TransportError("P05_OUTBOUND_FRAME_INVALID")
    try:
        env = decode_envelope(frame[4:])
        decoded = extract_payload(env)
    except Exception:
        raise TransportError("P05_OUTBOUND_PROTO_INVALID") from None
    if type(decoded) is not ProtoHeartbeatEvent:
        require_read_only_request(decoded)
    return True

class P05ReadOnlyTransport(StdlibCTraderTransport):
    """Do not bypass: instantiated only in OWNER-authorized new collector."""
    def _send_bytes(self, payload: bytes) -> None:
        check_outbound_frame(payload)
        return super()._send_bytes(payload)
