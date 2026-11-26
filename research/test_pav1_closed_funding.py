import json,subprocess,tempfile,unittest
from pathlib import Path
from .owner_pav1_closed_funding import charge_clocks,registered


class Pav1Funding(unittest.TestCase):
    def test_clock_plan_preserves_weekend_and_entry_boundaries(self):
        p,_=registered();self.assertEqual(p['EconomicPolicyReruns'],0)
        day=86_400_000;start=1795198215125;end=1795392000231
        c=dict(SwapPeriodHours=24,ChargeSwapAtWeekends=True,SkipSwapPeriods=0,SwapTimeUtcMinute=1320)
        clocks=charge_clocks(c,dict(FromExclusive=start,ClosedAt=end))
        self.assertEqual(len(clocks),3)
        self.assertEqual(charge_clocks(dict(c,ChargeSwapAtWeekends=False),dict(FromExclusive=start,ClosedAt=end)),clocks[:1])

    def test_native_missing_or_stale_fx_does_not_become_zero_funding(self):
        from .test_funding_latest_prefix import NativeSettlement
        x=NativeSettlement().fixture();x.update(Study='PAV1_CLOSED_FUNDING_RECOVERY_1',OriginalArtifact=1,
            ScenarioObservedAtUtcMs=x['Contract']['ObservedAtUtcMs'])
        x['Contract']['Symbol']='ETHUSD';x['Window']['Symbol']='ETHUSD'
        x['Books']=[dict(Id='SYNTHETIC',Stress=0,Window=x['Window'],OriginalCashEur=299.9,KnownOtherNetEur=-.5,
            OriginalSampledDrawdown=.01,OriginalUnknownEquityClocks=10)]
        x['Witnesses']=[]
        for charge in x['Charges']:
            for symbol,side,key in [('ETHUSD','BID','Bid'),('EURUSD','BID','FxBid'),('EURUSD','ASK','FxAsk')]:
                x['Witnesses'].append(dict(Target=dict(Symbol=symbol,Side=side,At=charge['At']),Witness=charge[key]))
        dll='research/NativePav1FundingRecovery/bin/Release/net8.0/NativePav1FundingRecovery.dll'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for stale in (False,True):
                if stale:
                    for row in x['Witnesses']:
                        if row['Target']['Symbol']=='EURUSD':row['Witness']['At']=row['Target']['At']-7200001
                source=root/('stale.json' if stale else 'fresh.json');out=root/(source.stem+'-out.json')
                source.write_text(json.dumps(x));subprocess.run(['dotnet',dll,str(source),str(out)],check=True,capture_output=True)
                r=json.loads(out.read_bytes())['Results'][0]
                self.assertEqual(r['Resolved'],not stale)
                if stale:self.assertIsNone(r['FinanciallyReconciledClosedNetEur'])


if __name__=='__main__':unittest.main()
