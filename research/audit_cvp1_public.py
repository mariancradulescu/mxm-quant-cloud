"""Arithmetic-only audit of frozen CVP1 public ZIP. Does not replay a policy.
Usage: python research/audit_cvp1_public.py ZIP OUTPUT_JSON
Small-sample empirical metrics are descriptive, not scorecard qualification.
"""
import json,sys,math,statistics,hashlib,zipfile
from datetime import datetime,timezone
from pathlib import Path
blob=Path(sys.argv[1]).read_bytes()
assert hashlib.sha256(blob).hexdigest()=='a5125582a1cf4690871ad4d7640090c376ea8e85196228bf235d4a25ee7bc569'
with zipfile.ZipFile(sys.argv[1]) as z:
 r=json.loads(z.read('economic.json'));source=json.loads(z.read('source.json'))
assert source['Completed'] and source['NativeTapeSha256']==r['SourceSha256']
assert source['OriginalRun']=='44162043538' and source['OrdersSubmitted']==0 and not source['CloudActivated']
assert len(r['Books'])==16 and len(r['Models'])==3 and not r['Qualified'] and not r['IndependentConfirmation']
def close(a,b):
 assert abs(a-b)<1e-7,(a,b)
def quant(x):
 x=sorted(x);return [x[int(q*(len(x)-1))] for q in [0,.05,.25,.5,.75,.95,1]] if x else None
def stats(tr,entries,weeks):
 ns=[t['NetEur'] for t in tr];n=len(ns);rs=[t['NetEur']/entries[t['PositionId']]['InitialRiskEur'] for t in tr]
 wins=[x for x in ns if x>0];losses=[x for x in ns if x<0];wn={w:0. for w in weeks};wc={w:0 for w in weeks}
 for t in tr:
  iso=datetime.fromtimestamp(t['ClosedAt']/1000,timezone.utc).isocalendar();w=f'{iso.year}-W{iso.week:02d}';wn[w]+=t['NetEur'];wc[w]+=1
 reasons={}
 for t in tr:reasons[t['Reason']]=reasons.get(t['Reason'],0)+1
 se=statistics.stdev(wn.values())/math.sqrt(len(wn))
 return dict(Trades=n,NetEur=sum(ns),CostTotals={f:sum(t[f] or 0 for t in tr) for f in ['GrossEur','SpreadEur','SlippageEur','ConversionEur','CommissionsEur','FinancingEur']},ExpectancyEur=statistics.mean(ns) if n else None,WinRate=len(wins)/n if n else None,ProfitFactor=-sum(wins)/sum(losses) if losses else None,Payoff=-statistics.mean(wins)/statistics.mean(losses) if wins and losses else None,MeanR=statistics.mean(rs) if n else None,NetQuantiles=quant(ns),RQuantiles=quant(rs),Worst=min(ns) if ns else None,ES5=statistics.mean(sorted(ns)[:math.ceil(n*.05)]) if n else None,WeeksNet=wn,WeeksTrades=wc,WeeklyMeanMinus2SE=statistics.mean(wn.values())-2*se,Under60Seconds=sum(t['ClosedAt']-t['OpenedAt']<60000 for t in tr),DurationSecondsQuantiles=quant([(t['ClosedAt']-t['OpenedAt'])/1000 for t in tr]),Reasons=reasons,ReasonProbabilities={k:v/n for k,v in reasons.items()},MfeQuoteMean=statistics.mean(entries[t['PositionId']]['MfeQuote'] for t in tr) if n else None,MaeQuoteMean=statistics.mean(entries[t['PositionId']]['MaeQuote'] for t in tr) if n else None,InitialTargetRRQuantiles=quant([entries[t['PositionId']]['InitialRewardRisk'] for t in tr if entries[t['PositionId']]['InitialRewardRisk'] is not None]),StatisticallySufficient=n>=20)
books={}
for k,b in r['Books'].items():
 ts=b['Trades'];es={e['Id']:e for e in b['Entries']};weeks=b['Scorecard']['FundedCompletionsByIsoWeek']
 assert len(es)==len(ts) and all(t['CompletesRoundTrip'] and t['ClosedAt']>t['OpenedAt'] for t in ts)
 for t in ts:close(t['NetEur'],t['GrossEur']-(t['SpreadEur'] or 0)-(t['SlippageEur'] or 0)-(t['ConversionEur'] or 0)-t['CommissionsEur']-t['FinancingEur'])
 close(b['Ledger']['CashEur']-300,sum(t['NetEur'] for t in ts))
 assert b['FullSettlementKnown'] and b['Ledger']['OpenPositions']==b['Ledger']['PendingIntents']==0
 s=stats(ts,es,weeks);assert s['WeeksTrades']==weeks;close(s['NetEur'],b['Scorecard']['NetEur']);close(s['NetEur'],sum(b['NetDistribution']['Values']))
 close(sum(t['NetEur']/es[t['PositionId']]['InitialRiskEur'] for t in ts),sum(b['RDistribution']['Values']))
 if len(ts)>=20:
  for f,g in [('ExpectancyEur','NetExpectancyPerTradeEur'),('WinRate','WinRate'),('ProfitFactor','ProfitFactor'),('Payoff','PayoffRatio'),('MeanR','MeanRiskMultiple'),('ES5','ExpectedShortfall5PctEur')]:close(s[f],b['Scorecard'][g])
 books[k]=dict(**s,Families={f:stats([t for t in ts if es[t['PositionId']]['Family']==f],es,weeks) for f in ['FLOW','RETURN']},Symbols={a:stats([t for t in ts if t['Symbol']==a],es,weeks) for a in r['Symbols']},KnownMarkFloatingDD=b['SampledCurrentExitCostFloatingDrawdown'],KnownMarkMargin=b['PeakCurrentMarginEur'],KnownMarkMinFreeMargin=b['MinimumCurrentFreeMarginEur'],Concurrency=b['MaximumConcurrentPositions'],Hard21=b['Scorecard']['Hard21AllEligibleWeeks'],UnknownMarks=b['UnknownHoldingMarks'],UncertainTrades=b['UncertainTrades'])
for scenario in ['central','adverse']:
 full=books['FULL_'+scenario];full['IncrementalVsAlternatives']={name:full['NetEur']-books[name+'_'+scenario]['NetEur'] for name in ['CASH','SIMPLE','NO_PEER','NO_ACTIVITY','PROTECT_ONLY','FLOW_ONLY','RETURN_ONLY']}
result=dict(Study='CVP1_PUBLIC_ARITHMETIC_AUDIT',OriginalZipSha256=hashlib.sha256(blob).hexdigest(),Passed=True,NoPolicyReplay=True,IndependentMarketConfirmation=False,MetricsClass='DESCRIPTIVE_EMPIRICAL_SMALL_SAMPLES_NOT_QUALIFICATION',Books=books)
Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
print('PASS: original hash, source binding, 16 book cash/cost/NET/R identities, weekly counts and native scorecard arithmetic')
