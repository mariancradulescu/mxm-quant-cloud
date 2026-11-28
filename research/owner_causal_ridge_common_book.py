"""Actual native Ridge forecasts compete in the restored common EUR300 book."""
import argparse,gc,hashlib,json,os,subprocess,time
from pathlib import Path
from . import owner_estate_monetary_competition as estate
from .owner_earlier_lifecycle_digest_recovery import verified_download,normalized_run_id
from .owner_pav1_market_time import restore_checkpoint
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need
from .bounded_exact_json import write
STUDY='MONETARY_CAUSAL_RIDGE_COMMON_BOOK_1'
REG=Path('research/causal_ridge_common_book_1.json');REPORT=Path('ridge-monetary-report');PARTS=Path('ridge-monetary-parts')
def variants(n):
    profile=estate.variants(n)[1]['Profile']
    return [dict(Id=name,UniverseCount=n,Profile=dict(profile,RecoveredRidgeHorizons=mask)) for name,mask in
        [('RECOVERED_CONTROL',0),('RIDGE_30_COMPETITION',1),('RIDGE_60_COMPETITION',2),('RIDGE_30_60_COMPETITION',3)]]
def check():
    p=read(REG);need(p['Study']==STUDY and p['Models']==[v['Id'] for v in variants(1)] and
        p['BaseRun']==46141614947 and p['CommonBookEvaluations']==20 and p['PrimaryEvaluations']==15 and p['SelectionMultiplicity']==16 and
        p['Orders']==p['SourceBrokerRequests']==0 and not p['CloudActivated'],'RIDGE_MONETARY_REGISTRATION');return p

def await_source(run,staged=False):
    repo=os.environ['GITHUB_REPOSITORY'];started=time.monotonic()
    while True:
        jobs=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}/jobs?per_page=100']))['jobs']
        matching=[j for j in jobs if j['name']=='economic'];need(len(matching)==1,'RIDGE_ESTATE_ECONOMIC_JOB')
        if matching[0]['status']=='completed':
            need(matching[0]['conclusion']=='success','RIDGE_ESTATE_ECONOMIC_NOT_SUCCESS');break
        need(time.monotonic()-started<18000,'RIDGE_ESTATE_SOURCE_TIMEOUT')
        print('RIDGE_WAITING_FOR_REUSABLE_COMPLETE_ESTATE',run,flush=True);time.sleep(30)
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100']))
    items={a['name']:dict(Id=a['id'],Name=a['name'],RunId=normalized_run_id(a['workflow_run']['id']),Sha256=a['digest'].removeprefix('sha256:'))
        for page in pages for a in page['artifacts'] if not a['expired'] and normalized_run_id(a['workflow_run']['id'])==run}
    if not staged:return items
    chosen={}
    for name in ('full-estate-monetary-public','full-estate-monetary-reusable-source'):
        matches=[a for key,a in items.items() if key.startswith(name+'-attempt')]
        need(bool(matches),'RIDGE_STAGED_SOURCE_ARTIFACT');chosen[name]=max(matches,key=lambda a:a['Id'])
    return chosen

def prepare(work):
    p=check();work.mkdir(mode=0o700,parents=True);REPORT.mkdir()
    staged=os.environ.get('MXM_RIDGE_STAGED_RUN_ID')
    run=normalized_run_id(staged if staged is not None else p['BaseRun'])
    # The staged workflow binds its own successful economic job and the
    # actual source receipt; the original failed run remains in registration.
    items=await_source(run,staged is not None);public=items['full-estate-monetary-public'];cache=items['full-estate-monetary-reusable-source']
    verified_download(public['Id'],run,public['Sha256'],work/'original')
    receipt=read(work/'original/source-receipt.json');verified_download(cache['Id'],run,cache['Sha256'],work/'cipher')
    if staged is not None:
        summary=read(work/'original/summary.json')
        need(summary['Study']==estate.STUDY and summary['CommonBookEvaluations']==15 and
            summary['SourceSha256']==receipt['SourceSha256'] and summary['Orders']==0 and not summary['CloudActivated'],
            'RIDGE_STAGED_ECONOMIC_BINDING')
        need({x['Role'] for x in receipt['Evidence']['Fragments']}=={'base','T4','T5','T6','T7','T8','T9','T10','T11','legacy'},
            'RIDGE_STAGED_FRAGMENT_COVERAGE')
    root=work/'estate';restore_checkpoint(work/'cipher',root,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),str(run),receipt['SourceSha256'])
    original=read(root/'plan.json');need(sha(root/'plan.json')==receipt['ProtocolSha256'] and original['Study']==estate.STUDY,'RIDGE_ORIGINAL_ESTATE_PLAN')
    names=original['OriginalInstruments'];manifest=read(work/'original/recovered-estate-manifest.json')
    lookup={(x['Symbol'],x['Timeframe']):x for x in manifest};classes={}
    # Read only the original source once; retain original monetary contracts and
    # clocks, but build the full price-information input from reconciled series.
    source=read(root/'source.json');classes={m['Market']['Name']:m['Market'].get('OfficialAssetClass') for m in source['Markets']}
    hourly={m['Market']['Name']:m['Market'].get('RecoveryH1',m['Market']['H1']) for m in source['Markets']}
    price_input=work/'ridge-price-input.json'
    with price_input.open('w') as out:
        out.write('[')
        for i,name in enumerate(names):
            bars={}
            for tf in ('M5','M15','H1'):
                row=lookup.get((name,tf));values=[]
                if row:
                    path=root/'reconciled-estate'/row['File'];need(sha(path)==row['Sha256'],'RIDGE_RECONCILED_SERIES_SHA');values=read(path)['Bars']
                bars[tf]=hourly[name] if tf=='H1' else values
            if i:out.write(',')
            out.write(exact_json(dict(Symbol=name,AssetClass=classes[name],Bars=bars,Quotes=[])))
        out.write(']\n')
    del source,hourly;gc.collect()
    subprocess.run(['dotnet','src/Mxm.PathResearch/bin/Release/net8.0/Mxm.PathResearch.dll','--breadth-ridge-monetary-signals',
        str(price_input),str(REPORT/'price-information.json'),str(work/'forecasts.json')],check=True)
    price=read(REPORT/'price-information.json');need(price['Study']=='OWNER_CAUSAL_RIDGE_MONETARY_OFFERS_1' and set(price['Markets'])==set(names),'RIDGE_NATIVE_FORECAST_UNIVERSE')
    forecasts=read(work/'forecasts.json');source=read(root/'source.json');by={n:[] for n in names}
    for row in forecasts:
        f=row['Forecast'];need(f['LatestTrainingAt']<f['FitBefore']<=f['DecisionAt'] and f['TrainingDays']>=20,'RIDGE_STRICT_PREDICTION_CAUSALITY')
        if source['Start']<=f['DecisionAt']<source['End'] and f['Side']!=0:by[row['Symbol']].append(f)
    count=len(forecasts);del forecasts;gc.collect()
    for market in source['Markets']:market['Market']['RecoveryRidge']=by[market['Market']['Name']]
    offer_counts={n:len(v) for n,v in by.items()};del by;gc.collect()
    plan=dict(original,Study=STUDY,Variants=variants(len(names)))
    evidence=dict(OriginalRun=run,RegisteredFailedBaseRun=p['BaseRun'],OriginalPublic=public,ReusableSource=cache,OriginalSourceSha256=receipt['SourceSha256'],
        OriginalProtocolSha256=receipt['ProtocolSha256'],RegistrationSha256=sha(REG),PriceInputSha256=sha(price_input),
        ForecastSha256=sha(work/'forecasts.json'),ForecastRows=count,ActiveOfferRows=offer_counts,
        TrainingStrictlyMatureBeforeDay=True,PeerMembershipIndependentOfFutureLabels=True,SourceBrokerRequests=0)
    plan.pop('SourceProtocolSha256',None);plan.pop('EvidenceManifestSha256',None)
    protocol=hashlib.sha256(exact_json(plan).encode()).hexdigest();digest=hashlib.sha256(exact_json(evidence).encode()).hexdigest()
    source.update(ProtocolSha256=protocol,EvidenceManifestSha256=digest,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=digest)
    write(work/'source.json',source);write(work/'plan.json',plan);del source;gc.collect()
    write(REPORT/'source-receipt.json',dict(Study=STUDY,SourceSha256=sha(work/'source.json'),ProtocolSha256=sha(work/'plan.json'),
        Evidence=evidence,Orders=0,CloudActivated=False));write(REPORT/'registered-plan.json',plan)
    public_key,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(work/'source.json','source.json'),(work/'plan.json','plan.json'),(work/'forecasts.json','forecasts.json')],
        'ridge-monetary-source-sealed',public_key,os.environ['GITHUB_RUN_ID'],STUDY,sha(work/'source.json'),protocol_sha=sha(work/'plan.json'))
    registry=estate.risk.restore_registry(work,p)
    write(work/'prepared-paths.json',dict(Registry=str(registry),RegistrySha256=sha(registry),SourceSha256=sha(work/'source.json'),ProtocolSha256=sha(work/'plan.json')))
    return registry,root/'verified-protection',work/'original'

def source_correction(work,tapes,registry):
    """Keep the primary comparison frozen; evaluate all new executable evidence separately."""
    from . import owner_persistent_executable_response as response
    from . import owner_eer1_source as eer
    from . import owner_eer1_readback as readback
    from . import source_history_universe as src
    from . import owner_eur_recent_continuous as recent
    from . import owner_eur_recent_funded as funded
    import shutil
    p=check();c=p['SourceCorrection'];run=c['Run'];folder=work/'corrected-capture';public=work/'corrected-public'
    verified_download(c['ProtectedArtifact'],run,c['ProtectedSha256'],folder)
    verified_download(c['AuditArtifact'],run,c['AuditSha256'],public)
    proof=read(public/'summary.json');receipt=read(folder/'receipt.json');key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    payload=eer.unpack(folder,receipt['sealed'],key,str(run));registration=response.registered()
    need(payload['Study']==response.STUDY and payload['RunId']==str(run) and
        payload['RegistrationSha256']==sha(response.REG)==receipt['RegistrationSha256'] and
        proof['CaptureProof']['Capture']==receipt,'RIDGE_CORRECTED_CAPTURE_BINDING')
    target_tape=work/'all-observed-protection';shutil.copytree(tapes,target_tape)
    from .owner_held_raw_execution_recovery import restore as restore_raw_held
    raw_held=restore_raw_held(work/'all-original-held-raw',target_tape)
    packets=payload['Packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
    need(src.original_account(account),'RIDGE_CORRECTED_ORIGINAL_ACCOUNT')
    j=src.ReadbackJournal(packets);sink=readback.protection_tick_sink(target_tape,'eer1');reports=[];new_quotes={}
    for target in response.targets(registration):
        report,_,quotes,_=recent.collect(j,account,registration,target,[],tick_sink=sink,keep=True)
        reports.append(report);new_quotes[target['symbol']]=quotes
    need(j.index==len(packets)==receipt['Requests']==proof['SourceBrokerRequests'] and
        reports==payload['Reports']==proof['CaptureProof']['ReadbackReports'],'RIDGE_CORRECTED_EXACT_PACKET_PARITY')
    acquired=max(x['availableAt'] for x in packets);del payload,packets,j;gc.collect()
    projected=work/'actual-raw-grid-quotes.json'
    subprocess.run(['dotnet',REPLAY,'--owner-protection-grid-quotes',str(work/'source.json'),str(target_tape),str(projected)],check=True)
    grid=read(projected);need(grid['SourceSha256']==sha(work/'source.json') and grid['ObservedActualQuoteSidesOnly'] and
        not grid['ValuationPrefixesUsedForExecution'] and grid['Orders']==0,'RIDGE_RAW_TICK_GRID_BINDING')
    new_quotes={row['Symbol']:row['Quotes'] for row in grid['Rows']}
    source=read(work/'source.json');quote_reconciliation={}
    for tape in source['Tapes']:
        if tape['Name'] in new_quotes:
            tape['Quotes'],conflicts=funded.merge_quotes(tape['Quotes'],new_quotes[tape['Name']])
            quote_reconciliation[tape['Name']]=dict(Captured=len(new_quotes[tape['Name']]),ConflictingClocks=conflicts)
    del grid,new_quotes;gc.collect()
    source['SourceAcquiredAt']=max(source['SourceAcquiredAt'],acquired)
    plan=read(work/'plan.json');plan.pop('SourceProtocolSha256');plan.pop('EvidenceManifestSha256')
    plan['SourceCorrection']=dict(OriginalRun=run,NewEntryRules=False,FullPolicyReevaluated=True)
    evidence=dict(PrimaryReceipt=read(REPORT/'source-receipt.json'),Capture=c,PacketCount=receipt['Requests'],
        QuoteReconciliation=quote_reconciliation,RawProjectionSha256=sha(projected),RestoredHeldRaw=raw_held,AllNewInformationAppliedToEntryAndProtection=True,Orders=0,CloudActivated=False)
    protocol=hashlib.sha256(exact_json(plan).encode()).hexdigest();digest=hashlib.sha256(exact_json(evidence).encode()).hexdigest()
    source.update(ProtocolSha256=protocol,EvidenceManifestSha256=digest);plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=digest)
    write(work/'corrected-source.json',source);write(work/'corrected-plan.json',plan);del source;gc.collect()
    corrected_receipt=dict(Study=STUDY,SourceSha256=sha(work/'corrected-source.json'),ProtocolSha256=sha(work/'corrected-plan.json'),
        Evidence=evidence,WholePolicyReevaluated=True,ContinuousDrawdownCertified=False,Orders=0,CloudActivated=False)
    write(REPORT/'source-corrected-receipt.json',corrected_receipt)
    public_key,_=derive_recipient(key)
    seal_files([(work/'corrected-source.json','source.json'),(work/'corrected-plan.json','plan.json')]+
        [(f,'verified-protection/'+f.name) for f in target_tape.iterdir() if f.is_file()],
        'ridge-monetary-corrected-source-sealed',public_key,os.environ['GITHUB_RUN_ID'],STUDY,
        corrected_receipt['SourceSha256'],protocol_sha=corrected_receipt['ProtocolSha256'])
    out=Path('ridge-corrected-parts/S1');out.mkdir(parents=True)
    env=dict(os.environ,MXM_ECONOMIC_BOUNDED_NEIGHBORS='1',MXM_ECONOMIC_PAIRED_DISTRIBUTION='1',MXM_ECONOMIC_PROFILE='1',
        MXM_ECONOMIC_COMPACT_REGISTRY='1',MXM_ECONOMIC_COMPACT_PATH='1',MXM_ECONOMIC_STREAM_REGISTRY='1')
    subprocess.run(['dotnet',REPLAY,'--owner-path-distribution',str(work/'corrected-plan.json'),str(work/'corrected-source.json'),
        str(out),str(target_tape),'0.5',str(registry)],env=env,check=True)
    result=read(out/'result.json');need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==5 and
        result['SourceSha256']==corrected_receipt['SourceSha256'] and result['Orders']==0,'RIDGE_CORRECTED_WHOLE_POLICY_RESULT')
    original={b['Id']:b['Result'] for b in read(REPORT/'S1-result.json')['CommonBooks']}
    comparisons=[]
    fields=['Closed','ClosedNetEur','AllTerminalNetEur','OpenPositions','PendingIntents','SampledDrawdown','Hard21AllFullRegisteredWeeks']
    for b in result['CommonBooks']:
        comparisons.append(dict(Id=b['Id'],Before={k:original[b['Id']][k] for k in fields},After={k:b['Result'][k] for k in fields}))
    write(REPORT/'source-correction-comparison.json',dict(Study=STUDY,CostStress='0.5',Books=5,Comparisons=comparisons,
        WholePolicyReevaluated=True,SelectionFrozenFromPrimaryStudy=True,NoNewQualificationFromSingleStress=True,
        SourceBrokerRequests=0,ReusedAuthenticRequests=receipt['Requests']+raw_held['PacketsReconciled'],ContinuousDrawdownCertified=False,Orders=0,CloudActivated=False))
    for name in ('result.json','holding-valuation-gaps.json','persistent-risk-audit.json'):(REPORT/('source-corrected-S1-'+name)).write_bytes((out/name).read_bytes())
    return dict(Books=5,WholePolicyReevaluated=True,SourceSha256=corrected_receipt['SourceSha256'],ReusedAuthenticRequests=receipt['Requests']+raw_held['PacketsReconciled'],
        SourceBrokerRequests=0,ContinuousDrawdownCertified=False,IndependentConfirmationCertified=False)

def evaluate(work,prepared=False):
    if prepared:
        state=read(work/'prepared-paths.json');registry=Path(state['Registry'])
        need(sha(registry)==state['RegistrySha256'] and sha(work/'source.json')==state['SourceSha256'] and
            sha(work/'plan.json')==state['ProtocolSha256'],'RIDGE_PREPARED_SOURCE_BINDING')
        tapes,original=work/'estate/verified-protection',work/'original'
    else:registry,tapes,original=prepare(work)
    rows=[]
    for i,stress in enumerate(STRESSES):
        out=PARTS/f'S{i}';out.mkdir(parents=True)
        env=dict(os.environ,MXM_ECONOMIC_BOUNDED_NEIGHBORS='1',MXM_ECONOMIC_PAIRED_DISTRIBUTION='1',MXM_ECONOMIC_PROFILE='1',
            MXM_ECONOMIC_COMPACT_REGISTRY='1',MXM_ECONOMIC_COMPACT_PATH='1',MXM_ECONOMIC_STREAM_REGISTRY='1')
        subprocess.run(['dotnet',REPLAY,'--owner-path-distribution',str(work/'plan.json'),str(work/'source.json'),str(out),str(tapes),stress,str(registry)],env=env,check=True)
        result=read(out/'result.json');need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==5 and result['Orders']==0,'RIDGE_MONETARY_RESULT')
        baseline=next(b['Result'] for b in read(original/f'S{i}-result.json')['CommonBooks'] if b['Id']=='RECOVERED_FAMILIES')
        control=next(b['Result'] for b in result['CommonBooks'] if b['Id']=='RECOVERED_CONTROL')
        fields=['CashEur','OpenPositions','PendingIntents','Closed','ClosedGrossEur','ClosedNetEur','AllTerminalNetEur','SampledDrawdown',
            'CommissionEur','SpreadEur','SlippageEur','ConversionEur','FundingSettlementsEur','Hard21AllFullRegisteredWeeks']
        equality={k:control[k]==baseline[k] for k in fields};write(REPORT/f'S{i}-control-equivalence.json',equality)
        need(all(equality.values()),'RIDGE_DISABLED_CONTROL_NUMERICAL_EQUIVALENCE')
        rows.append(result)
        for name in ('result.json','holding-valuation-gaps.json','persistent-risk-audit.json'):(REPORT/f'S{i}-{name}').write_bytes((out/name).read_bytes())
    write(REPORT/'primary-summary.json',dict(Study=STUDY,CommonBookEvaluations=15,Selection=estate.base.corrected_selection(
        [x for r in rows for x in r['Selection']],3),SelectionMultiplicity=16,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False))
    correction=source_correction(work,tapes,registry)
    receipt=read(REPORT/'source-receipt.json')
    write(REPORT/'summary.json',dict(Study=STUDY,CommonBookEvaluations=20,PrimaryEvaluations=15,SourceCorrection=correction,SourceSha256=receipt['SourceSha256'],
        Selection=estate.base.corrected_selection([x for r in rows for x in r['Selection']],3),SelectionMultiplicity=16,
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    files=sorted(PARTS.glob('*/checkpoints/**/*.json'))
    if not files:return
    receipt=read(REPORT/'source-receipt.json');public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(f,str(f.relative_to(PARTS))) for f in files],'ridge-monetary-books-sealed',public,os.environ['GITHUB_RUN_ID'],STUDY,
        receipt['SourceSha256'],complete=(REPORT/'primary-summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])
    corrected=sorted(Path('ridge-corrected-parts').glob('*/checkpoints/**/*.json'))
    if corrected:
        other=read(REPORT/'source-corrected-receipt.json')
        seal_files([(f,str(f.relative_to(Path('ridge-corrected-parts')))) for f in corrected],
            'ridge-monetary-corrected-books-sealed',public,os.environ['GITHUB_RUN_ID'],STUDY,other['SourceSha256'],
            complete=(REPORT/'source-correction-comparison.json').exists(),protocol_sha=other['ProtocolSha256'])
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','prepare','evaluate','conserve']);parser.add_argument('--prepared',action='store_true');parser.add_argument('--work',type=Path);a=parser.parse_args()
    if a.stage=='check':check()
    elif a.stage=='prepare':prepare(a.work)
    elif a.stage=='evaluate':evaluate(a.work,a.prepared)
    else:conserve()
