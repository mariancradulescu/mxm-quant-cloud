"""Offline synthetic authentication-only contract; never uses real credentials/network."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from .auth_scope_diagnostic import (
    diagnose,token_list_category,EXPIRED,SCOPE,ORIGINAL,TRANSPORT,UNKNOWN,PASS
)
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .ctrader_proto import OpenApiCommonMessages_pb2 as common

CREDS=("synthetic-client","synthetic-application-secret","synthetic-access-token")

def run(*responses):
    sent=[]
    it=iter(responses)
    def sender(request):
        sent.append(type(request).__name__)
        r=next(it)
        if isinstance(r,Exception): raise r
        return r
    return diagnose(sender,CREDS),sent

class DiagnosticTests(unittest.TestCase):
    def test_unknown_broker_code_never_called_expired(self):
        x,s=run(m.ProtoOAApplicationAuthRes(),m.ProtoOAErrorRes(errorCode="UNMAPPED_BROKER_ERROR",description="secret!"))
        self.assertEqual(x["category"],UNKNOWN)
        self.assertEqual(x["authenticationRequestsSent"],2)
        self.assertNotIn("secret!",json.dumps(x))
        self.assertNotIn(CREDS[-1],json.dumps(x))

    def test_expired_only_with_exact_explicit_broker_code(self):
        x,s=run(m.ProtoOAApplicationAuthRes(),m.ProtoOAErrorRes(errorCode="OA_AUTH_TOKEN_EXPIRED"))
        self.assertEqual(x["category"],EXPIRED)
        self.assertTrue(x["applicationAuthenticationVerified"])
        self.assertFalse(x["explicitSCOPE_VIEWVerified"])

    def test_missing_scope_and_trade_scope_both_fail_closed(self):
        for response in (m.ProtoOAGetAccountListByAccessTokenRes(accessToken="x"),
                         m.ProtoOAGetAccountListByAccessTokenRes(accessToken="x",permissionScope=e.SCOPE_TRADE)):
            x,_=run(m.ProtoOAApplicationAuthRes(),response)
            self.assertEqual(x["category"],SCOPE)
            self.assertEqual(x["authenticationRequestsSent"],2)
            self.assertFalse(x["originalAccountAuthenticationVerified"])
            self.assertFalse(x["explicitSCOPE_VIEWVerified"])

    def test_proxy_timed_out_is_transport_not_expired(self):
        x,_=run(m.ProtoOAApplicationAuthRes(),common.ProtoErrorRes(errorCode="TIMEOUT_ERROR"))
        self.assertEqual(x["category"],TRANSPORT)
        y,_=run(m.ProtoOAApplicationAuthRes(),TimeoutError("secret?"))
        self.assertEqual(y["category"],TRANSPORT)
        self.assertNotIn("secret?",json.dumps(y))

    def test_account_rejected_with_exact_documented_code(self):
        x,_=run(m.ProtoOAApplicationAuthRes(),m.ProtoOAErrorRes(errorCode="ACCOUNT_NOT_AUTHORIZED"))
        self.assertEqual(x["category"],ORIGINAL)

    def test_empty_account_list_cannot_infer_any_original_account(self):
        res=m.ProtoOAGetAccountListByAccessTokenRes(accessToken="x",permissionScope=e.SCOPE_VIEW)
        x,_=run(m.ProtoOAApplicationAuthRes(),res)
        self.assertEqual(x["category"],ORIGINAL)
        self.assertTrue(x["explicitSCOPE_VIEWVerified"])
        self.assertFalse(x["originalLiveAccountCryptographicallyBound"])

    def test_fully_validated_original_account_uses_only_three_allowed_auth_requests(self):
        res=m.ProtoOAGetAccountListByAccessTokenRes(accessToken="x",permissionScope=e.SCOPE_VIEW)
        with patch("research.auth_scope_diagnostic.original_account_matches",
                   return_value=[SimpleNamespace(ctidTraderAccountId=314159)]):
            x,s=run(m.ProtoOAApplicationAuthRes(),res,
                    m.ProtoOAAccountAuthRes(ctidTraderAccountId=314159))
        self.assertEqual(x["category"],PASS)
        self.assertEqual(s,["ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq","ProtoOAAccountAuthReq"])
        self.assertEqual(x["authenticationRequestsSent"],3)
        self.assertEqual(x["brokerAccountDataOrHistoryRequests"],0)
        self.assertTrue(x["originalAccountAuthenticationVerified"])
        self.assertNotIn("314159",json.dumps(x))

    def test_refreshed_tokens_never_requested_or_written(self):
        x,s=run(m.ProtoOAApplicationAuthRes(),m.ProtoOAErrorRes(errorCode="OA_AUTH_TOKEN_EXPIRED"))
        self.assertFalse(x["refresh"]["automaticRefreshAttempted"])
        self.assertFalse(x["refresh"]["rotationPossibleSafelyInCurrentWorkflow"])
        self.assertFalse(x["refresh"]["existingApprovedSecureAtomicTokenPairWriteback"])
        self.assertNotIn("ProtoOARefreshTokenReq",s)

    def test_missing_credentials_no_request(self):
        sent=[]
        x=diagnose(lambda q:sent.append(q),("","",""))
        self.assertEqual(x["authenticationRequestsSent"],0)
        self.assertEqual(x["category"],UNKNOWN)
        self.assertFalse(sent)

    def test_application_error_does_not_reach_token(self):
        x,s=run(m.ProtoOAErrorRes(errorCode="CH_CLIENT_AUTH_FAILURE"))
        self.assertEqual(x["category"],UNKNOWN)
        self.assertEqual(len(s),1)

if __name__=="__main__":
    unittest.main()
