from .ctrader_proto import OpenApiMessages_pb2 as m

class CaptureContractError(Exception):
    pass

ALLOWED = frozenset({"ProtoOAApplicationAuthReq", "ProtoOAGetAccountListByAccessTokenReq",
    "ProtoOAAccountAuthReq", "ProtoOASymbolsListReq", "ProtoOASymbolByIdReq",
    "ProtoOATraderReq", "ProtoOAAssetListReq", "ProtoOAExpectedMarginReq",
    "ProtoOAReconcileReq", "ProtoOAOrderListReq", "ProtoOADealListReq",
    "ProtoOAGetDynamicLeverageByIDReq", "ProtoOAGetTrendbarsReq", "ProtoOAGetTickDataReq"})

def require_read_only_request(request):
    name = type(request).__name__
    cls = getattr(m, name, None)
    if name not in ALLOWED or type(request) is not cls or request.payloadType != cls().payloadType:
        raise CaptureContractError("REQUEST_NOT_ALLOWLISTED")
    if not request.IsInitialized():
        raise CaptureContractError("REQUEST_INCOMPLETE")

def redact_text(_text):
    # Broker/OS exception strings are never copied into public logs.
    return "DETAIL_WITHHELD"
