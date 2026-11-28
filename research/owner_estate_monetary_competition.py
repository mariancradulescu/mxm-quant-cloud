"""Reconciled authentic estate -> native common-book recovery, with immutable originals."""
import argparse,gc,hashlib,json,os,shutil,subprocess,time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from . import owner_breadth57_ridge_recovery as ridge
from . import owner_estate_recovery as estate
from . import owner_lifecycle_estimation as base
from . import owner_eer1_source as eer
from . import owner_eer1_readback as readback
from . import owner_eur_recent_continuous as recent
from . import owner_eur_authentic_expansion as expansion
from . import owner_eur_recent_funded as funded
from . import owner_persistent_risk_recovery as risk
from . import source_history_universe as src
from .owner_official_breadth_spans import normalize_with_quarantine
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need
STUDY='MONETARY_FULL_ESTATE_COMPETITION_1'
REGISTRATION=Path('research/full_estate_monetary_competition_1.json')
REPORT=Path('estate-monetary-report')
PARTS=Path('estate-monetary-parts')
def write(path,obj):Path(path).write_text(exact_json(obj)+'\n')

def variants(n):
    profile=dict(risk.variants(n)[1]['Profile'],ReservePreventiveDrawdownHeadroom=True,
        PersistWitnessedPortfolioCloseUntilExecutable=True)
    return [dict(Id=name,UniverseCount=n,Profile=dict(profile,IncludeRecoveredEconomicFamilies=recovered,
        LifecycleEstimator=estimator,DistributionTargetRanges=Decimal(target)))
        for name,recovered,estimator,target in [('ORIGINAL_FAMILIES',False,'CENTERED_COST_CONTEXT','2.5'),
        ('RECOVERED_FAMILIES',True,'CENTERED_COST_CONTEXT','2.5'),
        ('RECOVERED_TARGET_15',True,'CENTERED_COST_CONTEXT','1.5'),
        ('RECOVERED_DISTRIBUTION',True,'DISTRIBUTION_CONTEXT','2.5')]]

def check():
    p=read(REGISTRATION)
    need(p['Study']==STUDY and p['Models']==[x['Id'] for x in variants(1)] and
        p['Start']<p['SelectionFrom']<p['EvaluationFrom']<p['End'] and
        p['Orders']==p['SourceBrokerRequests']==0 and not p['CloudActivated'] and
        not p['IndependentConfirmationCertified'],'ESTATE_MONETARY_REGISTRATION')
    return p

def artifact_specs(run):
    repo=os.environ['GITHUB_REPOSITORY']
    state=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}']))
    need(state['status']=='completed' and state['conclusion']=='success','ESTATE_COMPLETED_ARCHIVE')
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100']))
    return [dict(Id=a['id'],Name=a['name'],Sha256=a['digest'].removeprefix('sha256:'))
        for page in pages for a in page['artifacts'] if not a['expired']]

def derive_hourly(rows):
    groups=defaultdict(list)
    for b in rows:groups[b['OpenAt']//3600000*3600000].append(b)
    result=[]
    for at,values in sorted(groups.items()):
        v=sorted(values,key=lambda x:x['OpenAt'])
        if len(v)!=12 or v[0]['OpenAt']!=at or v[-1]['CloseAt']!=at+3600000 or any(a['CloseAt']!=b['OpenAt'] for a,b in zip(v,v[1:])):continue
        result.append(dict(OpenAt=at,CloseAt=at+3600000,Open=v[0]['Open'],High=max(b['High'] for b in v),
            Low=min(b['Low'] for b in v),Close=v[-1]['Close'],TickVolume=sum(b['TickVolume'] for b in v)))
    return result

def prepare(work):
    p=check();r=ridge.check();work.mkdir(mode=0o700,parents=True)
    registry=risk.restore_registry(work,p)
    root=work/'estate';root.mkdir();base.restore(work/'base')
    source=read(work/'base/source.json');need(sha(work/'base/source.json')==r['BaseSourceSha256'],'ESTATE_BASE_SHA')
    source.update(Start=p['Start'],FitEnd=p['SelectionFrom'],End=p['End'],ExtendedEconomicContext=True)
    tapes={x['Name']:x for x in source['Tapes']};markets={x['Market']['Name']:x for x in source['Markets']}
    for name,entry in markets.items():
        m=entry['Market']
        for tf in ('M5','M15','H1'):estate.save_series(root,name,tf,m[tf],'BASE29')
        for tf,obj in (m.get('AdditionalTimeframes') or {}).items():estate.save_series(root,name,tf,obj.get('Bars',[]),'BASE29-ADDITIONAL')
    tape=work/'verified-protection';shutil.copytree(work/'base/verified-protection',tape)
    sink=readback.protection_tick_sink(tape,'eer1')
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode();proof=[]
    specs=r['Sources']+[dict(tranche=11,run=r['ExpansionRun'],artifacts=artifact_specs(r['ExpansionRun']))]
    for spec in specs:
        tranche,run=spec['tranche'],spec['run'];folder=work/f'T{tranche}';folder.mkdir()
        prefix=f'breadth-extension-{tranche}-source-';items={a['Name']:a for a in spec['artifacts']}
        def fetch(name,dest):
            a=items[prefix+name];verified_download(a['Id'],run,a['Sha256'],dest);return a
        fetch('metadata',folder/'metadata');fetch('verified-summary',folder/'summary')
        receipt=read(folder/'metadata/receipt.json');summary=read(folder/f'summary/{prefix}summary.json')
        recipe=read(Path(f'research/official_breadth_extension_{tranche}.json'))
        if tranche==4:plan=receipt['summary']
        else:fetch('plan',folder/'plan');plan=read(folder/'plan/recent-plan.json')
        payload=eer.unpack(folder/'metadata',receipt['sealed'],key,str(run));account=src.decode(payload['packets'][0]['reqType'],payload['packets'][0]['req']).ctidTraderAccountId
        need(src.original_account(account) and plan['runId']==str(run) and plan['protocolSha256']==summary['protocolSha256']==payload['protocolSha256']
            and summary['planned']==summary['verified']==len(plan['partitions']) and not summary['pending'] and summary['orders']==0,'ESTATE_TRANCHE_BINDING')
        meta=eer.metadata_read(payload['packets'],plan['chosen'],account);del payload
        for name in plan['chosen']:
            info=meta['info'].get(name);terms=meta['terms'].get(name)
            need(info is not None and terms is not None,'ESTATE_CHOSEN_CONTRACT')
            row=meta['roster'][name];margin=meta['margin'].get(name,[])
            m=dict(Name=name,Class=row['assetClass'] or 'UNMAPPED',OfficialAssetClass=row['assetClass'],Contract=terms,Margin=margin,
                TickSize=str(Decimal(1).scaleb(-info['priceDigits'])),Quotes=[],M5=[],M15=[],H1=[],ShortAllowed=info['shortAllowed'],
                TradingMode=info['tradingMode'],CostTermsComplete=True,EnabledAtCapture=row['enabled'],AdditionalTimeframes={})
            # A new conditional scenario may use a captured current contract, but
            # retains its actual acquisition time and never certifies old tariffs.
            markets[name]=expansion.dated_market(name,m,terms,info,meta,margin,p['Start'],p['End'],run)
        for asset,route in meta['routes'].items():source['Routes'].setdefault(asset,route)
        source['SourceAcquiredAt']=max(source['SourceAcquiredAt'],*meta['actual'].values())
        for i,target in enumerate(plan['partitions']):
            a=fetch('protected-'+str(i),folder/str(i));rec=read(folder/str(i)/'receipt.json')
            data=eer.unpack(folder/str(i),rec['sealed'],key,str(run));j=src.ReadbackJournal(data['packets'])
            report,bars,quotes,funding=recent.collect(j,account,recipe,target,plan['chargeMinutes'],tick_sink=sink,keep=True)
            report.update(runId=str(run),protocolSha256=plan['protocolSha256'],index=i,requests=len(data['packets']))
            original=next(x for x in summary['receipts'] if x['report']['index']==i)
            need(j.index==len(data['packets'])==original['packetsReconciled'] and report==data['report']==rec['report']==original['report']
                and rec['sealed']==original['sealed'],'ESTATE_EXACT_PACKET_PARITY')
            name=target['symbol']
            for tf,rows in bars.items():
                normalized,quality=normalize_with_quarantine(rows);estate.save_series(root,name,tf,normalized,f'FULL-T{tranche}-{i}')
            t=tapes.setdefault(name,dict(Name=name,Quotes=[],FundingQuotes=[]))
            # Keep all raw quote records until one final reconciliation. A
            # conflicted clock cannot reappear in a later incremental merge.
            t['Quotes'].extend(quotes);t['FundingQuotes'].extend(funding)
            proof.append(dict(Tranche=tranche,Index=i,Symbol=name,Archive=a,Packets=j.index,Report=report))
            del data,j,bars,quotes,funding;gc.collect()
        print('ESTATE_MONETARY_TRANCHE_VERIFIED',tranche,len(markets),flush=True)
    # Original 106-market history, BDP/AIP, original source, continuation, and
    # 2023/24 source all join the same series reconciliation as newer tranches.
    estate.extend_estate(root,work/'older',r)
    from .owner_estate_complete_sources import extend
    extend(root,work/'complete-originals',p)
    estate.run_recovered(root,REPORT,r)
    manifest=read(REPORT/'recovered-estate-manifest.json');merged=work/'merged-estate'
    by=defaultdict(dict)
    for item in manifest:by[item['Symbol']][item['Timeframe']]=item
    need(set(p['HistoricalUniverse106']).issubset(by),'ESTATE_ALL_ORIGINAL_106_RECONCILED')
    history_counts={}
    for name,entry in markets.items():
        m=entry['Market'];m5=None
        for tf in src.PERIODS:
            item=by.get(name,{}).get(tf)
            rows=read(merged/item['File'])['Bars'] if item else []
            if tf=='M5':m5=rows
            if tf=='H1':
                # Derive a missing hourly clock only from 12 adjacent complete
                # authenticated M5 bars; never fabricate an unobserved interval.
                existing={b['OpenAt'] for b in rows}
                derived=[b for b in derive_hourly(m5 or []) if b['OpenAt'] not in existing]
                rows,_=estate.merge_series(rows,derived)
                m['RecoveryH1']=rows;history_counts[name]=dict(Hourly=len(rows),DerivedHourly=len(derived),OriginalHourly=len(existing))
            width=src.PERIODS[tf]*60000
            keep=60*recent.DAY if tf in ('H1','H4','D1') else 20*recent.DAY
            rows=[b for b in rows if p['Start']-keep<=b['OpenAt'] and b['CloseAt']<p['End'] and b['CloseAt']-b['OpenAt']==width]
            if tf in ('M5','M15','H1'):m[tf]=rows
            else:m['AdditionalTimeframes'][tf]=dict(Source='AUTHENTIC_RECONCILED_ESTATE',Bars=rows)
        del m5;gc.collect()
    need(sorted(markets)==p['Universe'],'ESTATE_MONETARY_RECONCILED_UNIVERSE')
    quote_quality={}
    for name,t in tapes.items():
        t['Quotes'],q=funded.merge_quotes([],t['Quotes'])
        t['FundingQuotes'],f=funded.merge_quotes([],t['FundingQuotes'],funding=True)
        quote_quality[name]=dict(Quotes=len(t['Quotes']),QuoteConflicts=q,FundingQuotes=len(t['FundingQuotes']),FundingConflicts=f)
    source['Markets']=[markets[n] for n in sorted(markets)];source['Tapes']=[tapes[n] for n in sorted(tapes)]
    plan=dict(Study=STUDY,Exposure='PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT',Start=p['Start'],SelectionFrom=p['SelectionFrom'],
        EvaluationFrom=p['EvaluationFrom'],End=p['End'],Stresses=[0,Decimal('.5'),1],OriginalInstruments=sorted(markets),Variants=variants(len(markets)))
    evidence=dict(RegistrationSha256=sha(REGISTRATION),Tranches=proof,QuoteQuality=quote_quality,RecoveryHistory=history_counts,
        ManifestSha256=sha(REPORT/'recovered-estate-manifest.json'),RegistrySha256=sha(registry),
        InformationalMarkets=sorted(by),EconomicMarkets=sorted(markets),HistoricalTariffsCertified=False)
    protocol=hashlib.sha256(exact_json(plan).encode()).hexdigest();digest=hashlib.sha256(exact_json(evidence).encode()).hexdigest()
    source.update(ProtocolSha256=protocol,EvidenceManifestSha256=digest,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=digest)
    write(work/'source.json',source);write(work/'plan.json',plan);del source,tapes,markets;gc.collect()
    write(REPORT/'registered-plan.json',plan)
    write(REPORT/'source-receipt.json',dict(Study=STUDY,SourceSha256=sha(work/'source.json'),ProtocolSha256=sha(work/'plan.json'),
        Evidence=evidence,Orders=0,CloudActivated=False,SourceBrokerRequests=0,IndependentConfirmationCertified=False))
    public,_=derive_recipient(key)
    files=[(work/'source.json','source.json'),(work/'plan.json','plan.json')]+[(f,'verified-protection/'+f.name) for f in tape.iterdir()]
    files += [(f,'reconciled-estate/'+f.name) for f in merged.iterdir() if f.is_file()]
    seal_files(files,'estate-monetary-source-sealed',public,os.environ['GITHUB_RUN_ID'],STUDY,sha(work/'source.json'),protocol_sha=sha(work/'plan.json'))
    return registry

def evaluate(work):
    REPORT.mkdir();registry=prepare(work);receipt=read(REPORT/'source-receipt.json');results=[]
    for i,stress in enumerate(STRESSES):
        out=PARTS/f'S{i}';out.mkdir(parents=True)
        env=dict(os.environ,MXM_ECONOMIC_BOUNDED_NEIGHBORS='1',MXM_ECONOMIC_PAIRED_DISTRIBUTION='1',MXM_ECONOMIC_PROFILE='1',
            MXM_ECONOMIC_COMPACT_REGISTRY='1',MXM_ECONOMIC_COMPACT_PATH='1',MXM_ECONOMIC_STREAM_REGISTRY='1')
        subprocess.run(['dotnet',REPLAY,'--owner-path-distribution',str(work/'plan.json'),str(work/'source.json'),str(out),str(work/'verified-protection'),stress,str(registry)],env=env,check=True)
        result=read(out/'result.json');need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==5 and result['Orders']==0 and not result['CloudActivated'],'ESTATE_MONETARY_RESULT')
        results.append(result)
        for name in ('result.json','holding-valuation-gaps.json','persistent-risk-audit.json'):(REPORT/f'S{i}-{name}').write_bytes((out/name).read_bytes())
    write(REPORT/'summary.json',dict(Study=STUDY,CommonBookEvaluations=15,SourceSha256=receipt['SourceSha256'],
        Selection=base.corrected_selection([x for r in results for x in r['Selection']],Decimal('3.0')),SelectionMultiplicity=12,
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    files=sorted(PARTS.glob('*/checkpoints/**/*.json'))
    if not files:return
    receipt=read(REPORT/'source-receipt.json');public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(f,str(f.relative_to(PARTS))) for f in files],'estate-monetary-books-sealed',public,os.environ['GITHUB_RUN_ID'],STUDY,
        receipt['SourceSha256'],complete=(REPORT/'summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','evaluate','conserve']);parser.add_argument('--work',type=Path);a=parser.parse_args()
    if a.stage=='check':check()
    elif a.stage=='conserve':conserve()
    else:evaluate(a.work)
if __name__=='__main__':main()
