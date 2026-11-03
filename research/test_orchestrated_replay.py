import json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
from decimal import Decimal as D
from .funded_replay import FundedReplay, Quote, Contract, Decision, IncompleteEvidence
from .orchestrated_replay import allocate

DLL=Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll')

@unittest.skipUnless(shutil.which('dotnet') and DLL.exists(), 'native replay build required')
class NativeOrchestratedReplay(unittest.TestCase):
    def request(self):
        grid=dict(EquityEur=200,CertifiedPeakEur=200,FreeMarginEur=200,MinimumUnits=1,
                  StepUnits=1,MaximumUnits=1,MarginPerUnitEur=10,BrokerStopoutEquityToMargin=.5,
                  Reconciled=True,CompleteJointRiskEvidence=True,EffectiveIndependentBlocks=4,UncertaintyMultiplier=3)
        states=[dict(StateId=str(i),KnownAt=1,Estimation=True,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0) for i in range(4)]
        opportunities=[dict(Id=s,Candidate=s,Symbol=s,RedundancyKey=s,Direction=1,AvailableAt=100,
             CalibratedThrough=90,Level=1,ExecutionEvidenceComplete=True,VolumeGrid=grid,
             Scenarios=[dict(StateId=str(i),KnownAt=50,Estimation=True,NetPerUnitEur=1,
                             FixedCostEur=0,LossPerUnitEur=2,PeakPerUnitEur=0) for i in range(4)])
             for s in ['AAA','BBB']]
        return dict(Clock=100,Account=grid,Baseline=states,Opportunities=opportunities)

    def test_native_selection_and_common_funded_ledger(self):
        r=self.request(); replay=FundedReplay(max_staleness_ms=1000,financing_schedule_proven=True)
        contract=Contract(1,1,1,D(10),D(0),D(0),D(0),'SYNTHETIC_TEST_ONLY')
        result=allocate(replay,r,{s:dict(contract=contract,latency_ms=1) for s in ['AAA','BBB']},DLL,
                        peak_upper_certificate=D(200))
        # Independently invoke the native CLI on identical capital inputs. This
        # checks adapter decision parity, not an independent research engine.
        with tempfile.TemporaryDirectory() as tmp:
            inp,out=Path(tmp)/'i.json',Path(tmp)/'o.json';inp.write_text(json.dumps(r))
            subprocess.run(['dotnet',str(DLL),str(inp),str(out),'--orchestrate-opportunities'],check=True)
            self.assertEqual(result,json.loads(out.read_text()))
        self.assertEqual({x.position_id for x in replay.pending},{'AAA','BBB'})
        self.assertEqual(result['ReservedMarginEur'],20)
        for s in ['AAA','BBB']:
            replay.quote(Quote(110,s,D(1),D(1),D(1),D(1),'synthetic'))
        self.assertEqual(len(replay.open),2)
        for s in ['AAA','BBB']:
            replay.decide(Decision(200,200,90,s,s,'CLOSE',1))
        for s in ['AAA','BBB']:
            replay.quote(Quote(210,s,D(2),D(2),D(1),D(1),'synthetic'))
        report=replay.report()
        self.assertEqual(report['balance_eur'],D(202))
        self.assertEqual(report['complete_round_trips'],2)
        self.assertFalse(report['economic_qualification'])

    def test_no_peak_certificate_no_allocations(self):
        replay=FundedReplay(max_staleness_ms=1,financing_schedule_proven=True)
        result=allocate(replay,self.request(),{},DLL)
        self.assertEqual(result['Allocations'],[])
        self.assertEqual(replay.pending,[])

    def test_observed_peak_cannot_be_forgotten(self):
        replay=FundedReplay(max_staleness_ms=1,financing_schedule_proven=True);replay.peak=D(220)
        with self.assertRaises(IncompleteEvidence):
            allocate(replay,self.request(),{},DLL,peak_upper_certificate=D(200))

if __name__=='__main__': unittest.main()
