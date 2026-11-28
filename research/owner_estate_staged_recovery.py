"""Checkpointed technical restoration of the unchanged full-estate experiment.
Each authenticated source fragment commits before reconciliation or monetary work.
"""
import argparse,gc,hashlib,json,os,shutil,subprocess,time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from . import owner_estate_monetary_competition as original
from . import owner_breadth57_ridge_recovery as ridge
from . import owner_estate_recovery as estate
from . import owner_lifecycle_estimation as base
from . import owner_eer1_source as eer
from . import owner_eer1_readback as readback
from . import owner_eur_recent_continuous as recent
from . import owner_eur_authentic_expansion as expansion
from . import owner_eur_recent_funded as funded
from . import source_history_universe as src
from .owner_official_breadth_spans import normalize_with_quarantine
from .owner_earlier_lifecycle_digest_recovery import verified_download,normalized_run_id
from .owner_pav1_market_time import restore_checkpoint
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .bounded_exact_json import write,write_arrays
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need
REG=Path('research/estate_staged_technical_recovery_1.json')
REPORT=Path('estate-monetary-report')
RESUME=Path('research/estate_staged_resume_2.json')
FRAGMENTS=['base','T4','T5','T6','T7','T8','T9','T10','T11','legacy']

def check():
    p=read(REG);original.check();ridge.check()
    need(p['Study']=='FULL_ESTATE_TECHNICAL_RECOVERY_1' and p['FailedRun']==46141614947 and
        p['Fragments']==FRAGMENTS and p['EconomicPolicyChanged'] is False and
        p['Orders']==p['SourceBrokerRequests']==0 and not p['CloudActivated'],'STAGED_REGISTRATION')
    return p

def artifacts(run=None):
    repo=os.environ['GITHUB_REPOSITORY'];run=normalized_run_id(run if run is not None else os.environ['GITHUB_RUN_ID'])
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100']))
    return [dict(Id=a['id'],Name=a['name'],RunId=normalized_run_id(a['workflow_run']['id']),Sha256=a['digest'].removeprefix('sha256:'))
        for page in pages for a in page['artifacts'] if not a['expired'] and normalized_run_id(a['workflow_run']['id'])==run]

def latest(prefix,run=None):
    rows=[a for a in artifacts(run) if a['Name'].startswith(prefix)]
    need(bool(rows),'STAGED_ARTIFACT_'+prefix);return max(rows,key=lambda a:a['Id'])

def resume_fragments():
    p=read(RESUME)
    need(p['Study']=='FULL_ESTATE_STAGED_RESUME_2' and p['OriginRun']==46150207165 and
        p['FailedJob']==140995875020 and set(p['Fragments'])==set(FRAGMENTS) and
        p['Orders']==p['SourceBrokerRequests']==0 and not p['CloudActivated'],'STAGED_RESUME_REGISTRATION')
    ids=set()
    for part,items in p['Fragments'].items():
        need(set(items)=={'sealed','public'},'STAGED_RESUME_KINDS')
        for kind,spec in items.items():
            need(spec['RunId']==p['OriginRun'] and spec['Name']==f'estate-fragment-{part}-{kind}-attempt1'
                and spec['Id'] not in ids and len(spec['Sha256'])==64,'STAGED_RESUME_IDENTITY')
            ids.add(spec['Id'])
    return p

def pinned_fragments():
    p=resume_fragments();inventory=artifacts(p['OriginRun'])
    for items in p['Fragments'].values():
        for spec in items.values():
            need(sum(a==spec for a in inventory)==1,'STAGED_RESUME_PIN_MISMATCH')
    return p['Fragments']

def restore_artifact(spec,folder):
    cipher=folder.with_name(folder.name+'-cipher')
    run=str(normalized_run_id(spec['RunId']))
    verified_download(spec['Id'],run,spec['Sha256'],cipher)
    receipt=read(cipher/'checkpoint-receipt.json')
    need(receipt['RunId']==run,'STAGED_CHECKPOINT_ORIGIN')
    restore_checkpoint(cipher,folder,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),
        run,receipt['SourceSha256'])
    return receipt

def tranche(spec,root,work,tape,source,markets,tapes,proof,p):
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    sink=readback.protection_tick_sink(tape,'eer1')
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

def fragment(work,part):
    check();p=original.check();r=ridge.check();work.mkdir(mode=0o700,parents=True)
    root=work/'estate';root.mkdir();tape=work/'verified-protection';tape.mkdir()
    source=dict(Routes={},SourceAcquiredAt=0);markets={};tapes={};proof=[]
    if part=='base':
        base.restore(work/'base');source=read(work/'base/source.json')
        need(sha(work/'base/source.json')==r['BaseSourceSha256'],'STAGED_BASE_SHA')
        source.update(Start=p['Start'],FitEnd=p['SelectionFrom'],End=p['End'],ExtendedEconomicContext=True)
        tapes={x['Name']:x for x in source['Tapes']};markets={x['Market']['Name']:x for x in source['Markets']}
        source['Tapes']=[];source['Markets']=[]
        for name,entry in markets.items():
            m=entry['Market']
            for tf in ('M5','M15','H1'):
                estate.save_series(root,name,tf,m[tf],'BASE29');m[tf]=[]
            for tf,obj in (m.get('AdditionalTimeframes') or {}).items():
                estate.save_series(root,name,tf,obj.get('Bars',[]),'BASE29-ADDITIONAL');obj['Bars']=[]
        shutil.copytree(work/'base/verified-protection',tape,dirs_exist_ok=True)
        proof=[dict(OriginalSourceSha256=r['BaseSourceSha256'])]
    elif part=='legacy':
        estate.extend_estate(root,work/'older',r,include_expansion=False)
        from .owner_estate_complete_sources import extend
        extend(root,work/'complete-originals',p)
        proof=read(work/'older/estate-provenance.json')
    else:
        number=int(part[1:]);spec=next((s for s in r['Sources'] if s['tranche']==number),None)
        if number==11:spec=dict(tranche=11,run=r['ExpansionRun'],artifacts=original.artifact_specs(r['ExpansionRun']))
        need(spec is not None,'STAGED_TRANCHE_SPEC')
        tranche(spec,root,work,tape,source,markets,tapes,proof,p)
    rows=sorted(root.glob('*.json'))
    payload=dict(Role=part,OriginalRegistrationSha256=sha(original.REGISTRATION),Header=source,
        Markets=[markets[n] for n in sorted(markets)],Tapes=[tapes[n] for n in sorted(tapes)],Proof=proof)
    write(work/'source.json',payload);del payload,source,markets,tapes;gc.collect()
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    files=[(work/'source.json','source.json')]+[(f,'estate/'+f.name) for f in rows]+[(f,'verified-protection/'+f.name) for f in tape.iterdir()]
    seal_files(files,'estate-fragment-sealed',public,os.environ['GITHUB_RUN_ID'],check()['Study'],sha(work/'source.json'))
    out=Path('estate-fragment-public');out.mkdir()
    write(out/'receipt.json',dict(Role=part,SourceSha256=sha(work/'source.json'),Series=len(rows),
        OriginalRegistrationSha256=sha(original.REGISTRATION),Orders=0,SourceBrokerRequests=0,CloudActivated=False))
    print('STAGED_FRAGMENT_COMPLETE',part,len(rows),flush=True)

def append_file(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    with source.open('rb') as incoming,destination.open('ab') as target:shutil.copyfileobj(incoming,target,1024*1024)

def market_rows(markets,by,merged,p,history):
    for name in sorted(markets):
        entry=markets[name];m=entry['Market'];m5=None
        for tf in src.PERIODS:
            item=by.get(name,{}).get(tf);rows=read(merged/item['File'])['Bars'] if item else []
            if tf=='M5':m5=rows
            if tf=='H1':
                existing={b['OpenAt'] for b in rows}
                derived=[b for b in original.derive_hourly(m5 or []) if b['OpenAt'] not in existing]
                rows,_=estate.merge_series(rows,derived);m['RecoveryH1']=rows
                history[name]=dict(Hourly=len(rows),DerivedHourly=len(derived),OriginalHourly=len(existing))
            width=src.PERIODS[tf]*60000;keep=60*recent.DAY if tf in ('H1','H4','D1') else 20*recent.DAY
            rows=[b for b in rows if p['Start']-keep<=b['OpenAt'] and b['CloseAt']<p['End'] and b['CloseAt']-b['OpenAt']==width]
            if tf in ('M5','M15','H1'):m[tf]=rows
            else:m['AdditionalTimeframes'][tf]=dict(Source='AUTHENTIC_RECONCILED_ESTATE',Bars=rows)
        yield entry
        markets[name]=None;del entry,m,m5,rows;gc.collect()
        print('STAGED_MARKET_WRITTEN',name,flush=True)

def assemble(work,reuse=False):
    check();p=original.check();work.mkdir(mode=0o700,parents=True);REPORT.mkdir()
    root=work/'estate';root.mkdir();tape=work/'verified-protection';tape.mkdir()
    markets={};tapes={};proof=[];fragment_bindings=[];source=None
    pinned=pinned_fragments() if reuse else None
    for part in FRAGMENTS:
        spec=pinned[part]['sealed'] if pinned is not None else latest('estate-fragment-'+part+'-sealed-attempt');folder=work/part
        restore_artifact(spec,folder);data=read(folder/'source.json')
        need(data['Role']==part and data['OriginalRegistrationSha256']==sha(original.REGISTRATION),'STAGED_FRAGMENT_BINDING')
        binding=dict(Role=part,Artifact=spec,SourceSha256=sha(folder/'source.json'))
        if pinned is not None:
            public=pinned[part]['public'];dest=work/(part+'-public')
            verified_download(public['Id'],public['RunId'],public['Sha256'],dest)
            receipt=read(dest/'receipt.json')
            need(receipt['Role']==part and receipt['SourceSha256']==binding['SourceSha256'] and
                receipt['OriginalRegistrationSha256']==sha(original.REGISTRATION) and
                receipt['Series']==len(list((folder/'estate').glob('*.json'))) and
                receipt['Orders']==receipt['SourceBrokerRequests']==0 and not receipt['CloudActivated'],'STAGED_RESUME_PUBLIC_BINDING')
            binding['PublicArtifact']=public
        fragment_bindings.append(binding)
        if part=='base':source=data['Header']
        else:
            for asset,route in data['Header']['Routes'].items():source['Routes'].setdefault(asset,route)
            source['SourceAcquiredAt']=max(source['SourceAcquiredAt'],data['Header']['SourceAcquiredAt'])
        for entry in data['Markets']:markets[entry['Market']['Name']]=entry
        for row in data['Tapes']:
            t=tapes.setdefault(row['Name'],dict(Name=row['Name'],Quotes=[],FundingQuotes=[]))
            t['Quotes'].extend(row['Quotes']);t['FundingQuotes'].extend(row['FundingQuotes'])
        if part=='legacy':
            older=work/'older';older.mkdir();write(older/'estate-provenance.json',data['Proof'])
        elif part!='base':proof.extend(data['Proof'])
        for f in (folder/'estate').glob('*.json'):
            dest=root/f.name;need(not dest.exists(),'STAGED_SERIES_IDENTITY');os.link(f,dest)
        for f in (folder/'verified-protection').iterdir():append_file(f,tape/f.name)
        del data;gc.collect();print('STAGED_FRAGMENT_RESTORED',part,flush=True)
    merged,manifest=estate.reconcile_series(root,REPORT)
    by=defaultdict(dict)
    for row in manifest:by[row['Symbol']][row['Timeframe']]=row
    need(set(p['HistoricalUniverse106']).issubset(by) and sorted(markets)==p['Universe'],'STAGED_COMPLETE_UNIVERSE')
    quality={}
    for name,t in tapes.items():
        t['Quotes'],q=funded.merge_quotes([],t['Quotes']);t['FundingQuotes'],f=funded.merge_quotes([],t['FundingQuotes'],funding=True)
        quality[name]=dict(Quotes=len(t['Quotes']),QuoteConflicts=q,FundingQuotes=len(t['FundingQuotes']),FundingConflicts=f)
    plan=dict(Study=original.STUDY,Exposure='PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT',Start=p['Start'],SelectionFrom=p['SelectionFrom'],
        EvaluationFrom=p['EvaluationFrom'],End=p['End'],Stresses=[0,Decimal('.5'),1],OriginalInstruments=sorted(markets),Variants=original.variants(len(markets)))
    # History counts are determined before hashing evidence, without holding any
    # financial bar arrays. The subsequent generator verifies the same counts.
    history={}
    for name in sorted(markets):
        h=by.get(name,{}).get('H1');f=by.get(name,{}).get('M5')
        hourly=read(merged/h['File'])['Bars'] if h else [];m5=read(merged/f['File'])['Bars'] if f else []
        existing={b['OpenAt'] for b in hourly};derived=[b for b in original.derive_hourly(m5) if b['OpenAt'] not in existing]
        hourly,_=estate.merge_series(hourly,derived)
        history[name]=dict(Hourly=len(hourly),DerivedHourly=len(derived),OriginalHourly=len(existing));del hourly,m5,derived;gc.collect()
    evidence=dict(RegistrationSha256=sha(original.REGISTRATION),TechnicalRecoverySha256=sha(REG),Tranches=proof,Fragments=fragment_bindings,
        QuoteQuality=quality,RecoveryHistory=history,ManifestSha256=sha(REPORT/'recovered-estate-manifest.json'),
        RegistryBundleSha256=sha(Path(p['RegistryBundle'])),RegistryRows=p['RegistryRows'],
        InformationalMarkets=sorted(by),EconomicMarkets=sorted(markets),HistoricalTariffsCertified=False)
    protocol=hashlib.sha256(exact_json(plan).encode()).hexdigest();digest=hashlib.sha256(exact_json(evidence).encode()).hexdigest()
    source.update(ProtocolSha256=protocol,EvidenceManifestSha256=digest,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=digest)
    verify_history={};write_arrays(work/'source.json',source,dict(Markets=market_rows(markets,by,merged,p,verify_history),Tapes=(tapes[n] for n in sorted(tapes))))
    need(verify_history==history,'STAGED_HISTORY_NUMERICAL_PARITY');write(work/'plan.json',plan)
    del source,markets,tapes;gc.collect()
    write(REPORT/'registered-plan.json',plan)
    write(REPORT/'source-receipt.json',dict(Study=original.STUDY,SourceSha256=sha(work/'source.json'),ProtocolSha256=sha(work/'plan.json'),
        Evidence=evidence,Orders=0,CloudActivated=False,SourceBrokerRequests=0,IndependentConfirmationCertified=False))
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    files=[(work/'source.json','source.json'),(work/'plan.json','plan.json')]+[(f,'verified-protection/'+f.name) for f in tape.iterdir()]
    files += [(f,'reconciled-estate/'+f.name) for f in merged.iterdir() if f.is_file()]
    seal_files(files,'estate-monetary-source-sealed',public,os.environ['GITHUB_RUN_ID'],original.STUDY,sha(work/'source.json'),protocol_sha=sha(work/'plan.json'))
    print('STAGED_REUSABLE_SOURCE_COMPLETE',len(by),len(p['Universe']),flush=True)

def restore_source(work):
    work.mkdir(mode=0o700,parents=True)
    spec=latest('full-estate-monetary-reusable-source-attempt');root=work/'prepared';restore_artifact(spec,root)
    public=latest('full-estate-prepared-public-attempt');verified_download(public['Id'],public['RunId'],public['Sha256'],work/'original')
    receipt=read(work/'original/source-receipt.json');need(sha(root/'source.json')==receipt['SourceSha256'] and sha(root/'plan.json')==receipt['ProtocolSha256'],'STAGED_PREPARED_SHA')
    return root,receipt

def information(work):
    root,receipt=restore_source(work);REPORT.mkdir()
    subprocess.run(['dotnet','src/Mxm.PathResearch/bin/Release/net8.0/Mxm.PathResearch.dll','--estate-recovery',str(root/'reconciled-estate'),str(REPORT/'recovered-mechanisms.json')],check=True)
    write(REPORT/'information-binding.json',dict(SourceSha256=receipt['SourceSha256'],Orders=0,CloudActivated=False))

def evaluate(work,cost):
    root,receipt=restore_source(work);REPORT.mkdir();write(REPORT/'source-receipt.json',receipt)
    registry=original.risk.restore_registry(work,original.check());out=Path('estate-monetary-parts')/f'S{cost}';out.mkdir(parents=True)
    env=dict(os.environ,MXM_ECONOMIC_BOUNDED_NEIGHBORS='1',MXM_ECONOMIC_PAIRED_DISTRIBUTION='1',MXM_ECONOMIC_PROFILE='1',
        MXM_ECONOMIC_COMPACT_REGISTRY='1',MXM_ECONOMIC_COMPACT_PATH='1',MXM_ECONOMIC_STREAM_REGISTRY='1',DOTNET_GCHeapHardLimit='0x280000000')
    with (REPORT/f'S{cost}-progress.log').open('w') as log:
        process=subprocess.Popen(['dotnet',REPLAY,'--owner-path-distribution',str(root/'plan.json'),str(root/'source.json'),str(out),
            str(root/'verified-protection'),STRESSES[cost],str(registry)],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in process.stdout:log.write(line);log.flush();print(line.rstrip(),flush=True)
        need(process.wait()==0,'STAGED_MONETARY_NATIVE_EXECUTION')
    result=read(out/'result.json');need(result['Study']==original.STUDY and result['SharedPortfolioEvaluations']==5 and
        result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256'] and result['Orders']==0,'STAGED_MONETARY_RESULT')
    for name in ('result.json','holding-valuation-gaps.json','persistent-risk-audit.json'):(REPORT/f'S{cost}-{name}').write_bytes((out/name).read_bytes())
    write(REPORT/'scenario-complete.json',dict(Cost=cost,RegistrySha256=sha(registry),SourceSha256=receipt['SourceSha256'],Orders=0,CloudActivated=False))

def finalize(work):
    check();work.mkdir(mode=0o700,parents=True);REPORT.mkdir();rows=[];registry_hashes=set()
    prefix='full-estate-prepared-public-attempt';spec=latest(prefix)
    verified_download(spec['Id'],spec['RunId'],spec['Sha256'],work/'prepared')
    for f in (work/'prepared').iterdir():shutil.copyfile(f,REPORT/f.name)
    receipt=read(REPORT/'source-receipt.json')
    for cost in range(3):
        spec=latest(f'full-estate-cost-S{cost}-public-attempt');dest=work/f'S{cost}'
        verified_download(spec['Id'],spec['RunId'],spec['Sha256'],dest)
        result=read(dest/f'S{cost}-result.json');need(result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256'],'STAGED_FINAL_SOURCE_PARITY')
        completed=read(dest/'scenario-complete.json');need(completed['Cost']==cost and completed['SourceSha256']==receipt['SourceSha256'],'STAGED_COST_COMPLETION')
        registry_hashes.add(completed['RegistrySha256']);write(REPORT/f'S{cost}-registry-binding.json',completed)
        rows.append(result)
        for f in dest.iterdir():
            if f.name.startswith(f'S{cost}-'):shutil.copyfile(f,REPORT/f.name)
    need(len(registry_hashes)==1,'STAGED_ALL_COST_REGISTRY_PARITY')
    spec=latest('full-estate-information-public-attempt');dest=work/'information'
    verified_download(spec['Id'],spec['RunId'],spec['Sha256'],dest)
    need(read(dest/'information-binding.json')['SourceSha256']==receipt['SourceSha256'],'STAGED_INFORMATION_SOURCE')
    shutil.copyfile(dest/'recovered-mechanisms.json',REPORT/'recovered-mechanisms.json')
    write(REPORT/'summary.json',dict(Study=original.STUDY,CommonBookEvaluations=15,SourceSha256=receipt['SourceSha256'],
        Selection=base.corrected_selection([x for r in rows for x in r['Selection']],Decimal('3.0')),SelectionMultiplicity=12,
        TechnicalRecovery=read(REG),Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','fragment','assemble','information','evaluate','finalize','conserve'])
    parser.add_argument('--reuse-fragments',action='store_true');parser.add_argument('--work',type=Path);parser.add_argument('--part',choices=FRAGMENTS);parser.add_argument('--cost',type=int,choices=range(3));a=parser.parse_args()
    if a.stage=='check':check();resume_fragments()
    elif a.stage=='fragment':fragment(a.work,a.part)
    elif a.stage=='assemble':assemble(a.work,a.reuse_fragments)
    elif a.stage=='information':information(a.work)
    elif a.stage=='evaluate':evaluate(a.work,a.cost)
    elif a.stage=='finalize':finalize(a.work)
    else:original.conserve()
