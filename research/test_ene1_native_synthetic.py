"""ENE1 C# source-blind synthetic funded ETH min-volume/float/equity test."""
import json,math,os,subprocess,tempfile,unittest
from pathlib import Path
from . import ene1_eth_original_source_and_features as src
from . import ene1_direct_net_eth_original as model

class Ene1NativeSynthetic(unittest.TestCase):
    def native(self,args,obj):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"input.json";z=Path(td)/"out.json"
            a.write_text(json.dumps(obj))
            p=subprocess.run([os.environ["ENE1_DOTNET"],
                 "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                 str(a),str(z),args],capture_output=True,text=True,timeout=45)
            self.assertEqual(p.returncode,0,p.stderr[-1300:])
            return json.loads(z.read_text())

    def test_fixed_original_ridge_replicated_by_csharp(self):
        if not os.environ.get("ENE1_DOTNET"):self.skipTest("dotnet absent")
        import numpy as np
        rng=np.random.default_rng(55);X=rng.normal(size=(40,14))
        y=rng.normal(size=40)
        sample=[]
        for variant in ("FULL","BASE"):
            cols=list(src.FULL_COLS if variant=="FULL" else src.BASE_COLS)
            beta=model.ridge(X,y,cols)
            for j in range(3):
                sample.append(dict(variant=variant,side=1,features=X[j].tolist(),
                    columns=cols,coefficients=beta.tolist(),
                    expected=float(model.pred(X[j:j+1],cols,beta)[0])))
        v=self.native("--ene1-parity",sample)
        self.assertTrue(v["Passed"])
        self.assertLess(v["MaximumAbsoluteDifference"],1e-10)

    def test_eth_minimum_volume_risk_one_funded_trip_and_cash_na(self):
        if not os.environ.get("ENE1_DOTNET"):self.skipTest("dotnet absent")
        t=src.MONDAY+9*src.WEEK+8*3600000+30*60000+1500
        q0=dict(Symbol="ETHUSD",At=t,Bid="2500.0",Ask="2500.1",
            EurCredit=".9091",EurDebit=".9092",ExitFeePerUnit=".10",
            ExitFeeFloor="0",MarginPerUnit="1000")
        qz=dict(q0,At=t+30*60000,Bid="2550.0",Ask="2550.1")
        offer=dict(At=t+1,ExitAt=t+30*60000,Symbol="ETHUSD",
            Variant="FULL",CalibratedThrough=t-5*3600000,
            MinUnits="0.01",StepUnits="0.01",MinMarginEur="10.0",
            MeanAdverseEur=[.3,-.3],RiskEur=[.3,.3],
            ActionScore=[.2,-.2],
            ScenarioNetEur=[[.35+j*.0001 for j in range(16)],[-.5]*16])
        v=self.native("--native-ene1",dict(Start=src.MONDAY+9*src.WEEK,
            End=src.MONDAY+13*src.WEEK,Scenario="adverse",
            Quotes=[q0,qz],Offers=[offer]))
        self.assertEqual(set(v),{"FULL","BASE","CASH"})
        self.assertEqual(v["FULL"]["Scorecard"]["CompletedRoundTrips"],1)
        self.assertGreater(v["FULL"]["Scorecard"]["NetEur"],0)
        self.assertEqual(v["FULL"]["OrdersSubmitted"],0)
        self.assertFalse(v["FULL"]["Qualified"])
        self.assertEqual(v["BASE"]["Scorecard"]["CompletedRoundTrips"],0)
        self.assertEqual(v["CASH"]["Scorecard"]["NetEur"],0)
        self.assertIsNone(v["CASH"]["Scorecard"]["WinRate"])
        self.assertEqual(len(v["FULL"]["Scorecard"]["FundedCompletionsByIsoWeek"]),4)

if __name__=="__main__":unittest.main()
