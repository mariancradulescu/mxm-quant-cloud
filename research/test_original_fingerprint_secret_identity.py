"""Synthetic-only, no network / GitHub environment / real broker identity."""
import hashlib
import json
import unittest
from .original_fingerprint_secret_identity import (
    NAME, RESULT_MATCH, RESULT_UNKNOWN, RESULT_UNAVAILABLE,
    compare_secret_to_original, sanitized_receipt
)

class FingerprintSecretIdentityTests(unittest.TestCase):
    def test_exact_synthetic_original_fingerprint(self):
        synthetic="ab"*32
        own_commitment=hashlib.sha256(synthetic.encode("ascii")).hexdigest()
        self.assertEqual(compare_secret_to_original(synthetic,commitment=own_commitment),RESULT_MATCH)
        self.assertEqual(compare_secret_to_original("sha256:"+synthetic,commitment=own_commitment),RESULT_MATCH)
        self.assertEqual(compare_secret_to_original("ACCOUNT_FINGERPRINT_SHA256 = '"+synthetic+"'",commitment=own_commitment),RESULT_MATCH)
        
    def test_refresh_shaped_or_other_value_remains_unknown_not_validated(self):
        for candidate in ["fake-refresh-not-a-hex-fingerprint","invalid_token","ff"*32,"token=secret"]:
            self.assertEqual(compare_secret_to_original(candidate,commitment="aa"*32),RESULT_UNKNOWN)
            summary=sanitized_receipt({NAME:candidate})
            self.assertEqual(summary["identityComparison"],RESULT_UNKNOWN)
            self.assertTrue(summary["unknownValueMayBeRefreshTokenButNotProven"])
            self.assertFalse(summary["refreshTokenValidityTested"])
            self.assertNotIn(candidate,json.dumps(summary))

    def test_empty_value_distinct_from_mismatch(self):
        self.assertEqual(sanitized_receipt({})["identityComparison"],RESULT_UNAVAILABLE)
        self.assertEqual(sanitized_receipt({NAME:""})["identityComparison"],RESULT_UNAVAILABLE)
        self.assertEqual(sanitized_receipt({NAME:" "})["identityComparison"],RESULT_UNKNOWN)
        
    def test_no_side_effects_or_secret_derivatives_in_receipt(self):
        secret="SYNTHETIC_TOKEN_NEVER_REAL"
        response=sanitized_receipt({NAME:secret})
        raw=json.dumps(response)
        self.assertNotIn(secret,raw)
        self.assertFalse(response["secretValueOrLengthOrPrefixOrHashDisclosed"])
        self.assertFalse(response["refreshedOrRotatedAnyToken"])
        self.assertFalse(response["updatedAnyGitHubSecret"])
        self.assertFalse(response["researchDataCollected"])
        self.assertEqual(response["brokerRequests"],0)
        self.assertEqual(response["ordersSubmitted"],0)
        self.assertFalse(response["cloudActivated"])

if __name__=="__main__":
    unittest.main()
