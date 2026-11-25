import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from research.merge_eur_scenarios import combine, exact_json


class MergeEurScenarios(unittest.TestCase):
    def test_exact_order_scope_and_reject_bad_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            protocol={"Study":"EUR_CONTEXTUAL_NET_1","Stresses":[0,0.5,1],
                      "Trials":[{"Id":str(i)} for i in range(4)],
                      "TestBoundaries":[100,200,300,400],"InitialFitFrom":0,
                      "EvidenceManifestSha256":"a"*64}
            p=root/"protocol.json"
            p.write_text(json.dumps(protocol))
            paths=[]
            exact=Decimal("0.1234567890123456789012345678")
            for i,stress in enumerate([0,Decimal("0.5"),1]):
                row={"SpreadMultiplier":stress,"CommissionAndDebitMultiplier":1+stress,
                     "Fits":[{"AvailableBefore":x} for x in [100,200,300]],
                     "Trials":[{"Id":str(j),"Result":{"InitialCapitalEur":300,"ClosedNetEur":exact}} for j in range(4)],
                     "OpportunityObservations":[{},{}],"TrialDetails":[{}]*4}
                doc={"Summary":{"Study":protocol["Study"],"ProtocolSha256":hashlib.sha256(p.read_bytes()).hexdigest(),
                                "EvidenceManifestSha256":"a"*64,"SourceSha256":"b"*64,
                                "TestBoundaries":protocol["TestBoundaries"],"InitialFitFrom":0,
                                "DeclaredScenarioTrialCount":12,"SourceBrokerRequests":0,"Orders":0,
                                "CloudActivated":False,"IndependentConfirmationCertified":False,
                                "DistilledWinnerForPromotion":False,"Results":[row]},
                     "BrokerFillEvidence":False,"StopWitness":{"At":12}}
                path=root/str(i)
                path.write_text(exact_json(doc))
                paths.append(path)
            merged=combine(p,paths[::-1])
            self.assertEqual([x["SpreadMultiplier"] for x in merged["Summary"]["Results"]],[0,Decimal("0.5"),1])
            self.assertEqual(json.loads(exact_json(merged),parse_float=Decimal)["Summary"]["Results"][0]["Trials"][0]["Result"]["ClosedNetEur"],exact)
            with self.assertRaises(ValueError): combine(p,[paths[0],paths[0],paths[2]])
            with self.assertRaises(ValueError): combine(p,paths[:2])
            bad=json.loads(paths[2].read_text(),parse_float=Decimal)
            bad["Summary"]["SourceSha256"]="c"*64
            paths[2].write_text(exact_json(bad))
            with self.assertRaises(ValueError): combine(p,paths)


if __name__=="__main__":
    unittest.main()
