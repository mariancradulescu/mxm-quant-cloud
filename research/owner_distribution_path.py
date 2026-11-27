"""Causal path distributions on conservatively reused authentic annual sources."""
import argparse,json,os,subprocess
from pathlib import Path
from . import owner_eur_recent_continuous as recent
from . import owner_eer1_source as eer
from . import source_history_universe as src
from .decode import need
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .owner_official_breadth_spans import normalize_with_quarantine
REGISTRY=Path('research/distribution_path_1.json');REPORT=Path('distribution-path-report')

def check():
 p=read(REGISTRY)
 need(p['Study']=='OWNER_DISTRIBUTION_PATH_1' and len(p['Sources'])==5 and [x['tranche'] for x in p['Sources']]==list(range(5,10))
  and p['SourceBrokerRequests']==p['Orders']==0 and not p['CloudActivated'] and not p['IndependentConfirmationCertified'],'PATH_DISTRIBUTION_REGISTRATION')
 return p

def normalized_arrays(rows):
 """Keep exact original integer trendbar rows after interval quarantine."""
 normalized,quality=normalize_with_quarantine(rows)
 clocks={(int(x['OpenAt']),int(x['CloseAt'])) for x in normalized}
 return [r for r in rows if (r[0],r[1]) in clocks],quality

def annual(work):
 p=check();work.mkdir(mode=0o700);key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode();records=[];proofs=[];money=[]
 for original in p['Sources']:
  tranche,run=original['tranche'],original['run'];root=work/str(tranche);root.mkdir()
  artifacts={x['Name']:x for x in original['artifacts']};prefix=f'breadth-extension-{tranche}-source-'
  def fetch(name,destination):
   a=artifacts[prefix+name];verified_download(a['Id'],run,a['Sha256'],destination);return a
  fetch('plan',root/'plan');fetch('verified-summary',root/'summary');fetch('metadata',root/'metadata')
  plan=read(root/'plan/recent-plan.json');summary=read(root/f'summary/breadth-extension-{tranche}-source-summary.json')
  receipt=read(root/'metadata/receipt.json');metadata=eer.unpack(root/'metadata',receipt['sealed'],key,str(run))
  need(plan['runId']==str(run) and plan['protocolSha256']==summary['protocolSha256']==metadata['protocolSha256']
   and not summary['pending'] and summary['planned']==summary['verified'] and summary['orders']==0
   and not summary['cloudActivated'],'PATH_ANNUAL_SOURCE_BINDING')
  packets=metadata['packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
  meta=eer.metadata_read(packets,plan['chosen'],account)
  recipe=read(Path(f'research/official_breadth_extension_{tranche}.json'))
  selected=[(i,t) for i,t in enumerate(plan['partitions']) if t['bars'] and t['barFrom']==recent.utc('2025-11-01')]
  need(len(selected)==4,'PATH_ANNUAL_FOUR_PREREGISTERED_NEW_MARKETS')
  for i,target in selected:
   spec=fetch('protected-'+str(i),root/str(i));r=read(root/str(i)/'receipt.json');d=eer.unpack(root/str(i),r['sealed'],key,str(run))
   journal=src.ReadbackJournal(d['packets']);report,bars,_,_=recent.collect(journal,account,recipe,target,plan['chargeMinutes'],keep=True)
   report.update(runId=str(run),protocolSha256=plan['protocolSha256'],index=i,requests=len(d['packets']))
   prior=next(x for x in summary['receipts'] if x['report']['index']==i)
   need(journal.index==len(d['packets'])==prior['packetsReconciled'] and report==d['report']==r['report']==prior['report']
    and r['sealed']==prior['sealed'],'PATH_ANNUAL_FULL_PACKET_PARITY')
   name=target['symbol'];normalized={};quarantine={}
   for tf in ('M5','M15','H1'):normalized[tf],quarantine[tf]=normalized_arrays(bars[tf])
   records.append(dict(Symbol=name,AssetClass=meta['roster'][name]['assetClass'],Bars=normalized))
   proofs.append(dict(Symbol=name,Run=run,Artifact=spec['Id'],ArchiveSha256=spec['Sha256'],Packets=journal.index,
    Bars={tf:len(v) for tf,v in normalized.items()},Quarantine=quarantine))
   money.append(dict(Symbol=name,AssetClass=meta['roster'][name]['assetClass'],ContractFieldsPresent=sorted(meta['info'][name]['fields']),
    MarginObservations=len(meta['margin'].get(name,[])),QuoteAsset=meta['terms'][name]['QuoteAsset'],
    HistoricalTariffCertified=False,AnnualExecutableMonetaryCoverageCertified=False))
   print('ANNUAL_DISTRIBUTION_SOURCE_REUSED',name,journal.index,flush=True)
 need(len(records)==len({x['Symbol'] for x in records})==20,'PATH_ANNUAL_DISTINCT_UNIVERSE')
 source=work/'annual-input.json';source.write_text(json.dumps(records,separators=(',',':')));REPORT.mkdir()
 subprocess.run(['dotnet','run','--project','src/Mxm.PathResearch','-c','Release','--no-build','--','--distribution',str(source),str(REPORT/'annual-distribution.json')],check=True)
 r=read(REPORT/'annual-distribution.json');need(r['SourceSha256']==sha(source) and len(r['Markets'])==20 and not r['PortfolioEvaluated']
  and not r['IndependentConfirmationCertified'] and r['Orders']==0 and not r['CloudActivated'],'PATH_ANNUAL_RESULT_BINDING')
 (REPORT/'source-receipt.json').write_text(exact_json(dict(Study=p['Study'],SourceSha256=sha(source),Proofs=proofs,MonetaryInventory=money,
  SourceBrokerRequests=0,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))+'\n')
 print('ANNUAL_DISTRIBUTION_COMPLETE',r['Labels'],r['Choices'],flush=True)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','annual']);parser.add_argument('--work',type=Path);a=parser.parse_args()
 if a.stage=='check':check()
 else:annual(a.work)
if __name__=='__main__':main()
