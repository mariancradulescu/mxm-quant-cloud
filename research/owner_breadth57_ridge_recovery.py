"""Reuse the entire 57-name selected universe; no original economic replay."""
import argparse,gc,os,subprocess
from pathlib import Path
from decimal import Decimal
from . import owner_eur_recent_continuous as recent
from . import owner_eer1_source as eer
from . import source_history_universe as src
from . import owner_lifecycle_estimation as base
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_official_breadth_spans import normalize_with_quarantine
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/breadth57_causal_ridge_recovery_2.json')
REPORT=Path('breadth57-ridge-recovery-report')
STUDY='OWNER_BREADTH57_CAUSAL_RIDGE_AMPLITUDE_1'

def check():
    p=read(REGISTRY)
    prior=read(Path('research/official_breadth_extension_10.json'))
    need(p['Study']==STUDY and p['Universe']==sorted(prior['ExistingUniverse']+prior['New']) and
        len(set(p['Universe']))==57 and [s['tranche'] for s in p['Sources']]==list(range(4,11)) and
        p['BaseSourceSha256']==base.SOURCE and p['Horizons']==[30,60] and p['SelectionMultiplicity']==6 and
        p['Orders']==p['SourceBrokerRequests']==p['OriginalPoliciesReplayed']==0 and not p['CloudActivated'] and
        not p['IndependentConfirmationCertified'],'BREADTH57_REGISTRATION')
    for spec in p['Sources']:
        names=[x['Name'] for x in spec['artifacts']]
        need(len(names)==len(set(names)) and all(len(x['Sha256'])==64 for x in spec['artifacts']),'BREADTH57_ARCHIVES')
    return p

def normalized_quotes(rows):
    by={};conflict=set()
    for x in rows:
        q={k:int(x[k]) for k in ('At','BidAt','AskAt')}
        q.update({k:Decimal(str(x[k])) for k in ('Bid','Ask')})
        if not (q['Bid']>0 and q['Ask']>=q['Bid'] and all(0<=q['At']-q[k]<=30000 for k in ('BidAt','AskAt'))):continue
        if q['At'] in by and by[q['At']]!=q:conflict.add(q['At'])
        by[q['At']]=q
    return [by[k] for k in sorted(by) if k not in conflict],len(conflict)

def materialize(work):
    from .owner_estate_recovery import save_series,merge_series,extend_estate,run_recovered
    estate=work/'estate';estate.mkdir(parents=True,mode=0o700)
    work=work/'ridge'
    p=check();work.mkdir(mode=0o700)
    base.restore(work/'base')
    need(sha(work/'base/source.json')==p['BaseSourceSha256'],'BREADTH57_BASE_SHA')
    source=read(work/'base/source.json');records=[];proofs=[]
    tapes={x['Name']:x['Quotes'] for x in source['Tapes']}
    for row in source['Markets']:
        m=row['Market'];quotes,conflict=normalized_quotes(tapes.get(m['Name'],[]))
        bars={tf:m[tf] for tf in ('M5','M15','H1')}
        for tf,series in bars.items():save_series(estate,m['Name'],tf,series,'BASE29')
        for tf,obj in (m.get('AdditionalTimeframes') or {}).items():
            if isinstance(obj,dict) and 'Bars' in obj:save_series(estate,m['Name'],tf,obj['Bars'],'BASE29-ADDITIONAL')
        records.append(dict(Symbol=m['Name'],AssetClass=m.get('OfficialAssetClass'),Bars=bars,Quotes=quotes))
        proofs.append(dict(Symbol=m['Name'],SourceSha256=p['BaseSourceSha256'],
            Bars={k:len(v) for k,v in bars.items()},QuoteMarks=len(quotes),ConflictingQuoteClocks=conflict))
    need(len(records)==len({r['Symbol'] for r in records})==29,'BREADTH57_BASE_SCOPE')
    del source,tapes;gc.collect()
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    for spec in p['Sources']:
        tranche,run=spec['tranche'],spec['run'];root=work/f'tranche-{tranche}';root.mkdir()
        prefix=f'breadth-extension-{tranche}-source-';items={a['Name']:a for a in spec['artifacts']}
        def fetch(name,dest):
            a=items[prefix+name];verified_download(a['Id'],run,a['Sha256'],dest);return a
        fetch('metadata',root/'metadata');fetch('verified-summary',root/'summary')
        recipe=read(Path(f'research/official_breadth_extension_{tranche}.json'))
        summary=read(root/f'summary/{prefix}summary.json')
        receipt=read(root/'metadata/receipt.json')
        if tranche==4:
            plan=receipt['summary'];need(plan['protocolSha256']==sha(Path('research/official_breadth_extension_4.json')),'BREADTH57_FOUR_PROTOCOL')
        else:
            fetch('plan',root/'plan');plan=read(root/'plan/recent-plan.json')
        metadata=eer.unpack(root/'metadata',receipt['sealed'],key,str(run))
        need(plan['runId']==str(run) and plan['protocolSha256']==summary['protocolSha256']==metadata['protocolSha256'] and
             not summary['pending'] and summary['planned']==summary['verified']==len(plan['partitions']) and summary['orders']==0 and
             not summary['cloudActivated'],'BREADTH57_SOURCE_BINDING')
        packets=metadata['packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
        need(src.original_account(account),'BREADTH57_ACCOUNT')
        meta=eer.metadata_read(packets,plan['chosen'],account)
        selected={name:dict(Bars={},Quotes=[],Packets=0,Archives=[],Quarantine={}) for name in plan['chosen']}
        existing={r['Symbol'] for r in records};completion=set(recipe['Base'])
        need(set(selected)&existing==completion and len(set(selected)-existing)==4,'BREADTH57_TRANCHE_COMPLETION_BINDING')
        for i,target in enumerate(plan['partitions']):
            name=target['symbol']
            if name not in selected:continue # conversion-only symbols are not extra universe members
            item=fetch('protected-'+str(i),root/str(i));r=read(root/str(i)/'receipt.json')
            payload=eer.unpack(root/str(i),r['sealed'],key,str(run));journal=src.ReadbackJournal(payload['packets'])
            report,bars,q,_=recent.collect(journal,account,recipe,target,plan['chargeMinutes'],keep=True)
            report.update(runId=str(run),protocolSha256=plan['protocolSha256'],index=i,requests=len(payload['packets']))
            prior=next(x for x in summary['receipts'] if x['report']['index']==i)
            need(journal.index==len(payload['packets'])==prior['packetsReconciled'] and report==payload['report']==r['report']==prior['report']
                and r['sealed']==prior['sealed'],'BREADTH57_EXACT_PACKET_PARITY')
            s=selected[name];s['Quotes'].extend(q);s['Packets']+=journal.index;s['Archives'].append(item)
            if target['bars']:
                for tf,series in bars.items():
                    values,quality=normalize_with_quarantine(series)
                    save_series(estate,name,tf,values,f'T{tranche}-{i}')
                    if tf in ('M5','M15','H1'):
                        s['Bars'][tf],conflicts=merge_series(s['Bars'].get(tf,[]),values)
                        s['Quarantine'][f'{i}/{tf}']=dict(Nominal=quality,Conflicts=conflicts)
            del payload,journal,bars,q;gc.collect()
        for name,s in selected.items():
            need(set(s['Bars'])=={'M5','M15','H1'},'BREADTH57_ANNUAL_SCOPE')
            q,conflict=normalized_quotes(s['Quotes'])
            if name in existing:
                m=next(x for x in records if x['Symbol']==name)
                need(m['AssetClass']==meta['roster'][name]['assetClass'],'BREADTH57_COMPLETION_CLASS')
                for tf,values in s['Bars'].items():
                    m['Bars'][tf],conflicts=merge_series(m['Bars'][tf],values)
                    s['Quarantine']['CROSS_TRANCHE/'+tf]=conflicts
                m['Quotes'],extra=normalized_quotes(m['Quotes']+q);conflict+=extra
            else:
                records.append(dict(Symbol=name,AssetClass=meta['roster'][name]['assetClass'],Bars=s['Bars'],Quotes=q))
            proofs.append(dict(Symbol=name,Run=run,Packets=s['Packets'],Archives=s['Archives'],
                Bars={k:len(v) for k,v in s['Bars'].items()},Quarantine=s['Quarantine'],QuoteMarks=len(q),
                ConflictingQuoteClocks=conflict,HistoricalTariffsCertified=False))
            print('BREADTH57_REUSED_MARKET',name,s['Packets'],len(q),flush=True)
    need(sorted(x['Symbol'] for x in records)==p['Universe'],'BREADTH57_ALL_SELECTED')
    path=work/'predictive-input.json';path.write_text(exact_json(records)+'\n')
    REPORT.mkdir();(REPORT/'source-receipt.json').write_text(exact_json(dict(Study=STUDY,SourceSha256=sha(path),
        RegistrationSha256=sha(REGISTRY),Markets=proofs,SourceBrokerRequests=0,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))+'\n')
    subprocess.run(['dotnet','run','--project','src/Mxm.PathResearch','-c','Release','--no-build','--','--breadth57-ridge',str(path),str(REPORT/'result.json')],check=True)
    result=read(REPORT/'result.json')
    need(result['SourceSha256']==sha(path) and sorted(result['Markets'])==p['Universe'] and result['Study']==STUDY and
        not result['PortfolioEvaluated'] and not result['IndependentConfirmationCertified'] and result['Orders']==0 and not result['CloudActivated'],'BREADTH57_RESULT')
    print('BREADTH57_RIDGE_COMPLETE',result['Labels'],result['Choices'],flush=True)
    del records,result;gc.collect()
    extend_estate(estate,work.parent/'older',p)
    run_recovered(estate,REPORT,p)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','evaluate']);parser.add_argument('--work',type=Path);args=parser.parse_args()
    if args.stage=='check':check()
    else:materialize(args.work)
if __name__=='__main__':main()
