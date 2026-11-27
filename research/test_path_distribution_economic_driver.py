"""Native registration smoke test on explicitly empty synthetic evidence.
Zero bars/quotes cannot produce fills, returns or economic qualification.
"""
import datetime,json,subprocess,tempfile,unittest
from pathlib import Path
from .owner_path_distribution_economic import variants
from .merge_eur_scenarios import exact_json
class RegisteredNativeDriver(unittest.TestCase):
 def test_both_registered_universes_reach_native_cash_without_fabricated_prices(self):
  day=86400000;start=int(datetime.datetime(2026,1,1,tzinfo=datetime.timezone.utc).timestamp())*1000
  for count in (7,29):
   with self.subTest(markets=count),tempfile.TemporaryDirectory() as root:
    root=Path(root);(root/'tapes').mkdir();names=['SYNTHETIC_'+str(i) for i in range(count)]
    source=dict(Start=start,FitEnd=start+day,End=start+3*day,ProtocolSha256='a'*64,EngineRevision='0'*40,
     EvidenceManifestSha256='b'*64,SourceAcquiredAt=start-1,Routes={'EUR':[]},
     Markets=[dict(Market=dict(Name=n,Class='SYNTHETIC',Contract=None,TickSize=0,ShortAllowed=False,TradingMode=0,CostTermsComplete=False,
      Margin=[],M5=[],M15=[],H1=[],Quotes=[],ActiveHours=0,RequestedTickHours=0,Schedule=[],ScheduleTimeZone='UTC'),
      TermsAcquiredAt=start-1,ScheduledClocks=[],AmbiguousCalendarClocks=[],CalendarStatus='SYNTHETIC_COMPLETE_CALENDAR') for n in names],
     Tapes=[dict(Name=n,Quotes=[],FundingQuotes=[]) for n in names])
    plan=dict(Study='MONETARY_PATH_DISTRIBUTION_1',Exposure='PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT',
     SourceProtocolSha256='a'*64,EvidenceManifestSha256='b'*64,Start=start,SelectionFrom=start+day,EvaluationFrom=start+2*day,
     End=start+3*day,Stresses=[0,.5,1],OriginalInstruments=names,Variants=variants(count))
    (root/'source.json').write_text(exact_json(source));(root/'plan.json').write_text(exact_json(plan))
    process=subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll','--owner-path-distribution',
     str(root/'plan.json'),str(root/'source.json'),str(root/'report'),str(root/'tapes'),'0','-'],capture_output=True,text=True)
    self.assertEqual(process.returncode,0,process.stderr[-2500:])
    report=json.loads((root/'report/result.json').read_bytes());self.assertEqual(report['SharedPortfolioEvaluations'],5)
    self.assertEqual(report['Orders'],0);self.assertFalse(report['IndependentConfirmationCertified'])
    self.assertTrue(all(b['Result']['CashEur']==300 and b['Result']['Closed']==0 for b in report['CommonBooks']))
if __name__=='__main__':unittest.main()
