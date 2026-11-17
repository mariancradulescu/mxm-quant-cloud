"""New synthetic EUR300 C# native selector/ledger interoperability check.
NO broker, no original source, no claim about profitability.
"""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from . import mrf1_authentic_m1_multiresolution as m

class MRF1NativeSynthetic(unittest.TestCase):
    def test_native_pure_m1_closes_and_volume_parity(self):
        if not os.environ.get("MRF1_DOTNET"):
            self.skipTest("C# pre-built binary not provided")
        import math
        import numpy as np
        closes=[1.1+.00001*i+.000004*math.sin(i/4) for i in range(61)]
        tick=[90+3*i for i in range(61)]
        rets=[math.log(closes[i]/closes[i-1]) for i in range(1,61)]
        last=rets[-5:];prior=rets[:-5]
        rms=lambda x:math.sqrt(sum(z*z for z in x)/len(x))
        sg=lambda x:1 if x>0 else -1 if x<0 else 0
        eff=sum(last)/max(1e-12,sum(abs(v) for v in last))
        accel=rms(last)/max(.0001,rms(prior))-1
        flip=sum(sg(last[i])!=sg(last[i-1]) for i in range(1,5))/4
        old=rets[-55:-5]
        oldflip=sum(sg(old[i])!=sg(old[i-1]) for i in range(1,len(old)))/(len(old)-1)
        activity=sum(tick[-5:])/(sum(tick[:-5])/56*5)-1
        expected=[m.clamp(eff),m.clamp(accel),m.clamp(flip-oldflip),m.clamp(activity)]
        payload=[dict(closes=closes,tickVolumes=tick,expected=expected)]*4
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"feature.json";b=Path(td)/"out.json"
            a.write_text(json.dumps(payload))
            proc=subprocess.run([os.environ["MRF1_DOTNET"],
                "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                str(a),str(b),"--mrf1-feature-parity"],
                capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr[-1000:])
            self.assertTrue(json.loads(b.read_text())["Passed"])
    def test_one_positive_minimum_volume_roundtrip_and_cash_nulls(self):
        if not os.environ.get("MRF1_DOTNET"):
            self.skipTest("C# pre-built binary not provided")
        t=m.START+2*m.W+8*m.H+30*m.M+1500
        # Original-style marks are synthetic here and must never appear in the
        # original authenticated financial result.
        q0=dict(Symbol="EURUSD",At=t,Bid="1.1000",Ask="1.1001",
                EurCredit="0.9089",EurDebit="0.9091",
                ExitFeePerUnit="0.000028",ExitFeeFloor="0",
                MarginPerUnit="0.03333")
        qz=dict(q0,At=t+30*m.M,Bid="1.1010",Ask="1.1011",
                 EurCredit="0.9083",EurDebit="0.9085")
        positive=dict(At=t+1,ExitAt=t+30*m.M,Symbol="EURUSD",
            Variant="FULL",CalibratedThrough=t-5*m.H,
            MinUnits="1000",MinMarginEur="33.33",
            MeanAdverseEur=[1.2,-1.2],RiskEur=[1,1],
            ActionScore=[1,-1],
            ScenarioNetEur=[[1.2+i*.01 for i in range(16)],
                            [-1.2 for _ in range(16)]])
        inp=dict(Start=m.START+2*m.W,End=m.END,Scenario="adverse",
                 Quotes=[q0,qz],Offers=[positive])
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"input.json";b=Path(td)/"out.json"
            a.write_text(json.dumps(inp))
            proc=subprocess.run([os.environ["MRF1_DOTNET"],
                "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                str(a),str(b),"--native-mrf1"],
                capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr[-1500:])
            report=json.loads(b.read_text())
            self.assertEqual(report["CASH"]["Scorecard"]["NetEur"],0)
            self.assertIsNone(report["CASH"]["Scorecard"]["WinRate"])
            self.assertEqual(report["BASE"]["Scorecard"]["CompletedRoundTrips"],0)
            self.assertEqual(report["FULL"]["Scorecard"]["CompletedRoundTrips"],1)
            self.assertGreater(report["FULL"]["Scorecard"]["NetEur"],0)
            self.assertFalse(report["FULL"]["Qualified"])
            self.assertEqual(report["FULL"]["OrdersSubmitted"],0)
            self.assertFalse(report["FULL"]["CloudActivated"])
            self.assertEqual(sum(report["FULL"]["Scorecard"]["FundedCompletionsByIsoWeek"].values()),1)
if __name__=="__main__":unittest.main()
