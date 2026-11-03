"""Prospective identity-only read extension; original transport/guard stay frozen."""
import time
from . import ctrader_transport as wire
from .guard import require_read_only_request as original_guard,CaptureContractError
from .ctrader_proto import OpenApiMessages_pb2 as m

EXTRA=frozenset({'ProtoOAReconcileReq','ProtoOAOrderListReq','ProtoOADealListReq'})
def require_read_only_request(q):
    name=type(q).__name__
    if name not in EXTRA:return original_guard(q)
    cls=getattr(m,name,None)
    if type(q) is not cls or q.payloadType!=cls().payloadType or not q.IsInitialized():
        raise CaptureContractError('IDENTITY_READ_REQUEST_INVALID')

class IdentityReadTransport(wire.StdlibCTraderTransport):
    def request(self,request,*,timeout=None):
        require_read_only_request(request)
        if type(request).__name__ not in EXTRA:return super().request(request,timeout=timeout)
        if not self.connected:self.connect()
        wait=.21-(self._clock()-self._last_rate_limited_request_send)
        if wait>0:time.sleep(wait)
        self._last_rate_limited_request_send=self._clock();self._sequence+=1
        client_msg_id=f'mxm-identity-{self._sequence:012d}'
        self._send_bytes(wire.encode_envelope(request,client_msg_id))
        deadline=self._clock()+float(timeout or self.response_timeout)
        while True:
            envelope=self.receive_envelope(deadline=deadline)
            if int(envelope.payloadType)==int(wire.ProtoHeartbeatEvent().payloadType):self.send_heartbeat();continue
            if str(getattr(envelope,'clientMsgId',''))!=client_msg_id:continue
            return wire.extract_payload(envelope)
