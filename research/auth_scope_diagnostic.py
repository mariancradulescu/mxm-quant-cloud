"""One bounded, no-data, no-refresh cTrader VIEW-scope diagnostic.

Only three existing allowlisted authentication messages, account-bound by the
unchanged historic double-SHA256. All public outputs are fixed categorical
codes: never serialize an OAuth token, account ID or protobuf/error description.
No HTTP calls, no rotation and no retry in this module.
"""
import hashlib
import json
import os
import sys
from pathlib import Path
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .ctrader_proto import OpenApiCommonMessages_pb2 as common
from .ctrader_transport import StdlibCTraderTransport, TransportError
from .guard import require_read_only_request
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT

EXPIRED="AUTH_TOKEN_INVALID_OR_EXPIRED_EXPLICIT"
SCOPE="AUTH_SCOPE_INCOMPATIBLE_OR_MISSING"
ORIGINAL="AUTH_ORIGINAL_ACCOUNT_UNAUTHORIZED_OR_ABSENT"
TRANSPORT="AUTH_TRANSPORT_SERVER_INVALID_OR_TIMEOUT"
UNKNOWN="AUTH_CAUSE_UNDETERMINED"
PASS="AUTH_SCOPE_VIEW_ORIGINAL_LIVE_ACCOUNT_VERIFIED"
CATEGORIES=frozenset([EXPIRED,SCOPE,ORIGINAL,TRANSPORT,UNKNOWN,PASS])
DOCUMENTED_EXPLICIT={
    "OA_AUTH_TOKEN_EXPIRED": EXPIRED,
    "ACCOUNT_NOT_AUTHORIZED": ORIGINAL,
    "RET_NO_SUCH_LOGIN": ORIGINAL,
    "RET_ACCOUNT_DISABLED": ORIGINAL,
    "TIMEOUT_ERROR": TRANSPORT,
    "CANT_ROUTE_REQUEST": TRANSPORT,
    "BLOCKED_PAYLOAD_TYPE": TRANSPORT,
    "FRAME_TOO_LONG": TRANSPORT,
}
# The broker error description, unexpected codes and whole replies are NEVER
# printed, stored, compared to token strings or copied into public output.

def error_reply_category(reply):
    if isinstance(reply,(m.ProtoOAErrorRes,common.ProtoErrorRes)):
        # Only exact official code names, with no substring heuristic.
        return DOCUMENTED_EXPLICIT.get(reply.errorCode, UNKNOWN)
    return UNKNOWN

def token_list_category(reply):
    if isinstance(reply, m.ProtoOAGetAccountListByAccessTokenRes):
        if not reply.HasField("permissionScope") or reply.permissionScope != e.SCOPE_VIEW:
            return SCOPE
        return None
    return error_reply_category(reply)

def account_bound_to_original(account):
    fingerprint=hashlib.sha256(
        f"ctrader-account:{int(account.ctidTraderAccountId)}".encode("ascii")).hexdigest()
    return hashlib.sha256(fingerprint.encode("ascii")).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT

def original_account_matches(reply):
    if not isinstance(reply,m.ProtoOAGetAccountListByAccessTokenRes):
        return []
    return [a for a in reply.ctidTraderAccount
            if account_bound_to_original(a) and
            a.HasField("isLive") and a.isLive]

def safe_exception_category(exc):
    if isinstance(exc,(TransportError,TimeoutError,ConnectionError,OSError)):
        return TRANSPORT
    return UNKNOWN

def current_refresh_posture():
    # Do not attempt to access GitHub secret metadata; the installed workflow
    # has no refresh secret and no authorized durable pair update API.
    # This flag describes static configuration only, not any hidden secret.
    return dict(automaticRefreshAttempted=False,
        existingApprovedSecureAtomicTokenPairWriteback=False,
        currentReadOnlyWorkflowAcceptsRefreshToken=False,
        rotationPossibleSafelyInCurrentWorkflow=False)

def diagnose(request_fn, creds):
    """Pure injection-friendly state machine; request_fn sends at most 3 messages."""
    stage="local_configuration"
    count=0
    application=False
    view=False
    bound=False
    account_auth=False
    category=UNKNOWN
    def send(req):
        nonlocal count
        require_read_only_request(req)
        if count>=3:
            raise ValueError("AUTH_DIAGNOSTIC_REQUEST_BUDGET")
        count+=1
        return request_fn(req)
    try:
        app_id,app_secret,access=creds
        if not all(isinstance(x,str) and x.strip() for x in creds):
            raise ValueError("AUTH_LOCAL_SECRET_MISSING")
        stage="application"
        response=send(m.ProtoOAApplicationAuthReq(clientId=app_id,clientSecret=app_secret))
        if not isinstance(response,m.ProtoOAApplicationAuthRes):
            category=error_reply_category(response)
        else:
            application=True
            stage="access_token_scope"
            response=send(m.ProtoOAGetAccountListByAccessTokenReq(accessToken=access))
            category=token_list_category(response)
            if category is None:
                view=True
                matches=original_account_matches(response)
                if len(matches)!=1:
                    category=ORIGINAL
                    stage="original_live_account_binding"
                else:
                    bound=True
                    stage="original_account_authorization"
                    account=matches[0].ctidTraderAccountId
                    response=send(m.ProtoOAAccountAuthReq(
                        ctidTraderAccountId=account,accessToken=access))
                    if isinstance(response,m.ProtoOAAccountAuthRes) and response.ctidTraderAccountId==account:
                        account_auth=True
                        category=PASS
                    else:
                        category=error_reply_category(response)
                        if isinstance(response,m.ProtoOAAccountAuthRes):
                            category=ORIGINAL
    except Exception as exc:
        category=safe_exception_category(exc)
    assert category in CATEGORIES
    return dict(schema="MXM_READ_ONLY_AUTH_SCOPE_DIAGNOSTIC_V1",
        category=category,stage=stage,
        applicationAuthenticationVerified=application,
        explicitSCOPE_VIEWVerified=view,
        originalLiveAccountCryptographicallyBound=bound,
        originalAccountAuthenticationVerified=account_auth,
        authenticationRequestsSent=count,
        brokerAccountDataOrHistoryRequests=0,
        rawBrokerErrorCodesOrDescriptionsDisclosed=False,
        usedOnlyExistingReadOnlyTransport=True,
        secretValuesInOutput=False,
        originalAccountIdInOutput=False,
        refresh=current_refresh_posture(),
        tradingOrders=0,cloudActivated=False)

def main():
    # This process does not use the model or source research code paths.
    # GitHub environment secrets are accessible only inside the protected job.
    names=("R3_CTRADER_CLIENT_ID","R3_CTRADER_CLIENT_SECRET","R3_CTRADER_ACCESS_TOKEN")
    creds=tuple(os.environ.get(k,"") for k in names)
    t=StdlibCTraderTransport()
    try:
        result=diagnose(t.request,creds)
    finally:
        t.close()
    dest=Path("auth-scope-diagnostic.public.json")
    dest.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("MXM_AUTH_SCOPE_DIAGNOSTIC_CATEGORY "+result["category"],flush=True)
    print("MXM_AUTH_SCOPE_DIAGNOSTIC_STAGE "+result["stage"],flush=True)
    # Data-free auth denial is a result, not a workflow crash that hides the
    # category; follow-up research is NEVER triggered by this job.
    return 0

if __name__=="__main__":
    sys.exit(main())
