"""OWNER 2026-11-07 bounded read-only OAuth adapter for ACTIVE BCF1 source.

The historical research.collect module and account commitment stay byte-identical.
This adapter changes ONLY optional permissionScope handling; all three messages
are explicitly allowlisted, no refresh, trading, order, Cloud or account fallback.
"""
import hashlib
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT, secret
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need
from .guard import require_read_only_request


def read_only_scope_attestation(accounts):
    """Return an honest category; absence NEVER means asserted VIEW/TRADE."""
    need(isinstance(accounts, m.ProtoOAGetAccountListByAccessTokenRes),
         "TOKEN_INVALID_OR_EXPIRED")
    if not accounts.HasField("permissionScope"):
        return "NOT_ATTESTED"
    need(accounts.permissionScope in (e.SCOPE_VIEW, e.SCOPE_TRADE),
         "UNKNOWN_EXPLICIT_PERMISSION_SCOPE")
    return "VIEW" if accounts.permissionScope == e.SCOPE_VIEW else "TRADE_CAPABLE"


def authenticate(t):
    """Authenticate the ONE frozen original LIVE account; read-only traffic."""
    client=secret("R3_CTRADER_CLIENT_ID")
    client_secret=secret("R3_CTRADER_CLIENT_SECRET")
    token=secret("R3_CTRADER_ACCESS_TOKEN")

    def request(q):
        require_read_only_request(q)
        return t.request(q)

    app=request(m.ProtoOAApplicationAuthReq(clientId=client, clientSecret=client_secret))
    need(isinstance(app, m.ProtoOAApplicationAuthRes), "APPLICATION_AUTH_FAILED")
    print("APPLICATION_AUTH_VERIFIED",flush=True)

    accounts=request(m.ProtoOAGetAccountListByAccessTokenReq(accessToken=token))
    scope=read_only_scope_attestation(accounts)
    print("ACCESS_TOKEN_SCOPE_"+scope+"_OWNER_READ_ONLY",flush=True)

    def is_original(a):
        fingerprint=hashlib.sha256(
            f"ctrader-account:{int(a.ctidTraderAccountId)}".encode("ascii")
        ).hexdigest()
        return (hashlib.sha256(fingerprint.encode("ascii")).hexdigest()
                == HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT)

    matched=[a for a in accounts.ctidTraderAccount if is_original(a)]
    need(len(matched)==1 and matched[0].HasField("isLive") and matched[0].isLive,
         "ACCOUNT_BINDING_FAILED")
    account=matched[0].ctidTraderAccountId
    response=request(m.ProtoOAAccountAuthReq(ctidTraderAccountId=account,accessToken=token))
    need(isinstance(response, m.ProtoOAAccountAuthRes)
         and response.ctidTraderAccountId==account,"ACCOUNT_AUTH_FAILED")
    print("BOUND_LIVE_ACCOUNT_AUTH_VERIFIED_OWNER_READ_ONLY",flush=True)
    return account
