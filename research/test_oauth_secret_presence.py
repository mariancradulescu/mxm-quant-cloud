"""No real secret, no integration calls; fixed synthetic fixtures only."""
import json
import unittest
from .oauth_secret_presence import presence_only,SECRET_NAMES

class OriginalOauthPresenceTests(unittest.TestCase):
    def test_all_four_available_does_not_claim_token_validity(self):
        fake=dict.fromkeys(SECRET_NAMES,"SYNTHETIC_VALUE_NEVER_REAL")
        result=presence_only(fake)
        self.assertTrue(result["allFourAvailable"])
        self.assertEqual(set(result["valuesBySecretName"]),set(SECRET_NAMES))
        self.assertTrue(all(v=="AVAILABLE_IN_PROTECTED_JOB" for v in result["valuesBySecretName"].values()))
        self.assertFalse(result["validityOfAnyCredentialTested"])
        self.assertFalse(result["originalAccountReauthenticated"])
        self.assertFalse(result["refreshTokenConsumed"])
        self.assertFalse(result["durablePairWritten"])
        encoded=json.dumps(result)
        self.assertNotIn("SYNTHETIC_VALUE_NEVER_REAL",encoded)
        self.assertNotIn("LEN_",encoded)
    
    def test_refresh_missing_not_claimed_absent_from_github(self):
        fake={s:"fake" for s in SECRET_NAMES[:-1]}
        result=presence_only(fake)
        self.assertFalse(result["allFourAvailable"])
        self.assertEqual(result["valuesBySecretName"]["R3_CTRADER_REFRESH_TOKEN"],"NOT_AVAILABLE_OR_EMPTY_IN_PROTECTED_JOB")
        self.assertFalse(result["missingMeansProvenAbsentFromGitHub"])
        self.assertFalse(result["readGitHubSecretMetadata"])
    
    def test_empty_refresh_is_injected_unavailable_not_broker_invalid(self):
        fake={s:"fake" for s in SECRET_NAMES}
        fake["R3_CTRADER_REFRESH_TOKEN"]=""
        result=presence_only(fake)
        self.assertEqual(result["valuesBySecretName"]["R3_CTRADER_REFRESH_TOKEN"],"NOT_AVAILABLE_OR_EMPTY_IN_PROTECTED_JOB")
        self.assertFalse(result["validityOfAnyCredentialTested"])
    
    def test_no_secrets_or_permanent_side_effects_in_report(self):
        fake={s:"SYNTHETIC_SECRET_"+str(i) for i,s in enumerate(SECRET_NAMES)}
        result=presence_only(fake)
        raw=json.dumps(result)
        for v in fake.values(): self.assertNotIn(v,raw)
        self.assertEqual(result["brokerCalls"],0)
        self.assertEqual(result["liveOrDemoOrders"],0)
        self.assertFalse(result["cloudActivated"])

if __name__=="__main__":
    unittest.main()
