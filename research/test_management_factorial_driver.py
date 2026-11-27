"""Native registration smoke test on explicitly empty synthetic evidence.
Zero bars/quotes cannot produce fills, returns or economic qualification.
"""
import datetime,json,subprocess,tempfile,unittest
from pathlib import Path
from .owner_management_factorial import variants,check
from .merge_eur_scenarios import exact_json
class ManagementFactorialDriver(unittest.TestCase):
 def test_both_registered_universes_reach_native_cash_without_fabricated_prices(self):
  check();day=86400000;start=int(datetime.datetime(2026,1,1,tzinfo=datetime.timezone.utc).timestamp())*1000
  for count in (7,29):
   with self.subTest(markets=count),tempfile.TemporaryDirectory() as root:
    root=Path(root);(root/'tapes').mkdir();names=['SYNTHETIC_'+str(i) for i in range(count)]
    source=dict(Start=start,FitEnd=start+day,End=start+3*day,ProtocolSha256='a'*64,EngineRevision='0'*40,
     EvidenceManifestSha256='b'*64,SourceAcquiredAt=start-1,Routes={'EUR':[]},
     Markets=[dict(Market=dict(Name=n,Class='SYNTHETIC',Contract=None,TickSize=0,ShortAllowed=False,TradingMode=0,CostTermsComplete=False,
      Margin=[],M5=[],M15=[],H1=[],Quotes=[],ActiveHours=0,RequestedTickHours=0,Schedule=[],ScheduleTimeZone='UTC'),
      TermsAcquiredAt=start-1,ScheduledClocks=[],AmbiguousCalendarClocks=[],CalendarStatus='SYNTHETIC_COMPLETE_CALENDAR') for n in names],
     Tapes=[dict(Name=n,Quotes=[],FundingQuotes=[]) for n in names])
    plan=dict(Study='MONETARY_MANAGEMENT_FACTORIAL_1',Exposure='PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT',
     SourceProtocolSha256='a'*64,EvidenceManifestSha256='b'*64,Start=start,SelectionFrom=start+day,EvaluationFrom=start+2*day,
     End=start+3*day,Stresses=[0,.5,1],OriginalInstruments=names,Variants=variants(count))
    (root/'source.json').write_text(exact_json(source));(root/'plan.json').write_text(exact_json(plan))
    (root/'empty-registry.json').write_text('{"Rows":[]}')
    process=subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll','--owner-path-distribution',
     str(root/'plan.json'),str(root/'source.json'),str(root/'report'),str(root/'tapes'),'0',str(root/'empty-registry.json')],capture_output=True,text=True)
    self.assertEqual(process.returncode,0,process.stderr[-2500:])
    report=json.loads((root/'report/result.json').read_bytes());self.assertEqual(report['SharedPortfolioEvaluations'],9)
    self.assertEqual(report['Orders'],0);self.assertFalse(report['IndependentConfirmationCertified'])
    self.assertTrue(all(b['Result']['CashEur']==300 and b['Result']['Closed']==0 for b in report['CommonBooks']))
    (root/'demand.json').write_text(exact_json([dict(Symbol=names[0],At=start+3600000,Studies=['NET_HORIZON'])]))
    residual=root/'residual.json'
    result=subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll','--owner-held-residual-plan',
     str(root/'source.json'),str(root/'tapes'),str(root/'demand.json'),str(root/'empty-registry.json'),str(residual)],capture_output=True,text=True)
    self.assertEqual(result.returncode,0,result.stderr[-2500:])
    assessment=json.loads(residual.read_bytes());self.assertEqual(assessment['ResolvedBefore'],0)
    self.assertEqual(assessment['Assessments'][0]['Status'],'MISSING_DATED_TERMS')
    self.assertEqual(assessment['Groups'],[]);self.assertEqual(assessment['Orders'],0)
 def test_fresh_registry_coverage_prevents_redundant_requests_without_inventing_fx(self):
  from .test_owner_eur_checkpoint import fixture,START
  with tempfile.TemporaryDirectory() as root:
   root=Path(root);fixture(root)
   source=json.loads((root/'source.json').read_bytes())
   market=source['Markets'][0]['Market']
   market['Contract']['QuoteAsset']='USD'
   market['DatedDevelopment']['Contract']['QuoteAsset']='USD'
   (root/'source.json').write_text(exact_json(source))
   at=START+12*3600000+15000
   clocks=[at,at+300000,at+600000]
   rows=[]
   for clock,observed,through in ((clocks[0],clocks[0]-1000,clocks[0]),
      (clocks[1],clocks[1]-31000,clocks[1]),(clocks[2],clocks[2]+1000,clocks[2]+1000)):
    for side,price in (('BID','100'),('ASK','100.02')):
     rows.append(dict(Symbol='SYNTH_A',Side=side,EvidenceSha256='c'*64,
      Witness=dict(Status='AUTHENTIC_LATEST_PREFIX',SearchFrom=observed-1000,SearchThrough=through,
       At=observed,Price=price,PrefixNewestFirst=True,LeadingTimestampComplete=True)))
   (root/'registry.json').write_text(exact_json(dict(Rows=rows)))
   (root/'demand.json').write_text(exact_json([dict(Symbol='SYNTH_A',At=t,Studies=['TEST']) for t in clocks]))
   output=root/'assessment.json'
   process=subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',
     '--owner-held-residual-plan',str(root/'source.json'),str(root/'verified-protection'),
     str(root/'demand.json'),str(root/'registry.json'),str(output)],capture_output=True,text=True)
   self.assertEqual(process.returncode,0,process.stderr[-2500:])
   report=json.loads(output.read_bytes())
   self.assertEqual(report['Assessments'][0]['Status'],'MISSING_QUOTE_CONVERSION')
   self.assertEqual(report['ResolvedBefore'],0)
   self.assertEqual({t for g in report['Groups'] for t in g['Clocks']},set(clocks[1:]))
   self.assertEqual(report['Orders'],0)
 def test_factorial_replay_resume_matches_continuous_native_report(self):
  import copy,hashlib,os
  from .test_owner_eur_checkpoint import fixture,START,FIT,END,DAY
  with tempfile.TemporaryDirectory() as root:
   root=Path(root);fixture(root)
   source=json.loads((root/'source.json').read_bytes())
   for i in range(5):
    name=f'SYNTH_EXTRA_{i}'
    market=copy.deepcopy(source['Markets'][0]);market['Market']['Name']=name
    market['Market']['Contract']['Symbol']=name
    market['Market']['DatedDevelopment']['Contract']['Symbol']=name
    source['Markets'].append(market)
    tape=copy.deepcopy(source['Tapes'][0]);tape['Name']=name;source['Tapes'].append(tape)
    origin=hashlib.sha256(b'SYNTH_A').hexdigest();dest=hashlib.sha256(name.encode()).hexdigest()
    for suffix in ('bid-eer1.ticks','bid-eer1.coverage','ask-eer1.ticks','ask-eer1.coverage'):
     (root/'verified-protection'/f'{dest}-{suffix}').write_bytes((root/'verified-protection'/f'{origin}-{suffix}').read_bytes())
   (root/'source.json').write_text(exact_json(source))
   plan=dict(Study='MONETARY_MANAGEMENT_FACTORIAL_1',Exposure='PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT',
    SourceProtocolSha256=source['ProtocolSha256'],EvidenceManifestSha256=source['EvidenceManifestSha256'],
    Start=START,SelectionFrom=FIT,EvaluationFrom=FIT+DAY,End=END,Stresses=[0,.5,1],
    OriginalInstruments=[m['Market']['Name'] for m in source['Markets']],Variants=variants(7))
   (root/'factorial.json').write_text(exact_json(plan));(root/'registry.json').write_text('{"Rows":[]}')
   base=dict(os.environ,MXM_ECONOMIC_BOUNDED_NEIGHBORS='1',MXM_ECONOMIC_PAIRED_DISTRIBUTION='1')
   base.pop('MXM_FACTORIAL_STOP_AFTER_PHASE',None);base.pop('MXM_FACTORIAL_RESUME_FROM',None)
   def run(out,**settings):
    cmd=['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll','--owner-path-distribution',
     str(root/'factorial.json'),str(root/'source.json'),str(out),str(root/'verified-protection'),'0',str(root/'registry.json')]
    result=subprocess.run(cmd,env=dict(base,**settings),capture_output=True,text=True)
    self.assertEqual(result.returncode,0,result.stderr[-3500:])
    return result.stdout
   continuous=root/'continuous';resumed=root/'resumed'
   run(continuous)
   run(resumed,MXM_FACTORIAL_STOP_AFTER_PHASE='1')
   checkpoint=resumed/'checkpoints'/str(FIT+DAY)/'resume.json'
   saved=json.loads(checkpoint.read_bytes())
   self.assertEqual(saved['CalibrationFits'],16)
   self.assertGreater(saved['BookAdvances'],0);self.assertGreater(saved['ObserverAdvances'],0)
   self.assertFalse((resumed/'result.json').exists())
   output=run(resumed,MXM_FACTORIAL_RESUME_FROM=str(checkpoint))
   restored=next(json.loads(line.split(' ',1)[1]) for line in output.splitlines()
    if line.startswith('MXM_ECONOMIC_PROGRESS ') and '"FACTORIAL_CHECKPOINT_RESTORED"' in line)
   self.assertEqual(restored['clocksProcessed'],saved['Clocks'])
   self.assertEqual(restored['bookAdvances'],saved['BookAdvances'])
   self.assertEqual(restored['calibrationFits'],saved['CalibrationFits'])
   for name in ('result.json','holding-valuation-gaps.json'):
    self.assertEqual(hashlib.sha256((continuous/name).read_bytes()).hexdigest(),
                     hashlib.sha256((resumed/name).read_bytes()).hexdigest(),name)
   print('FACTORIAL_NATIVE_RESUME_PARITY',saved['Clocks'],saved['BookAdvances'],saved['CalibrationFits'],flush=True)
if __name__=='__main__':unittest.main()
