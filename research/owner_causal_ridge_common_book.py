"""Actual native Ridge forecasts compete in the restored common EUR300 book."""
import argparse,gc,hashlib,json,os,subprocess,time
from pathlib import Path
from . import owner_estate_monetary_competition as estate
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_pav1_market_time import restore_checkpoint
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need
STUDY='MONETARY_CAUSAL_RIDGE_COMMON_BOOK_1'
REG=Path('research/causal_ridge_common_book_1.json');REPORT=Path('ridge-monetary-report');PARTS=Path('ridge-monetary-parts')
def write(p,v):Path(p).write_text(exact_json(v)+'\n')
def variants(n):
    profile=estate.variants(n)[1]['Profile']
    return [dict(Id=name,UniverseCount=n,Profile=dict(profile,RecoveredRidgeHorizons=mask)) for name,mask in
        [('RECOVERED_CONTROL',0),('RIDGE_30_COMPETITION',1),('RIDGE_60_COMPETITION',2),('RIDGE_30_60_COMPETITION',3)]]
def check():
    p=read(REG);need(p['Study']==STUDY and p['Models']==[v['Id'] for v in variants(1)] and
        p['BaseRun']==46141614947 and p['CommonBookEvaluations']==15 and p['SelectionMultiplicity']==12 and
        p['Orders']==p['SourceBrokerRequests']==0 and not p['CloudActivated'],'RIDGE_MONETARY_REGISTRATION');return p

def await_source(run):
    repo=os.environ['GITHUB_REPOSITORY'];started=time.monotonic()
    while True:
        jobs=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}/jobs?per_page=100']))['jobs']
        matching=[j for j in jobs if j['name']=='economic'];need(len(matching)==1,'RIDGE_ESTATE_ECONOMIC_JOB')
        if matching[0]['status']=='completed':
            need(matching[0]['conclusion']=='success','RIDGE_ESTATE_ECONOMIC_NOT_SUCCESS');break
        need(time.monotonic()-started<18000,'RIDGE_ESTATE_SOURCE_TIMEOUT')
        print('RIDGE_WAITING_FOR_REUSABLE_COMPLETE_ESTATE',run,flush=True);time.sleep(30)
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100']))
    return {a['name']:dict(Id=a['id'],Name=a['name'],Sha256=a['digest'].removeprefix('sha256:'))
        for page in pages for a in page['artifacts'] if not a['expired']}

def prepare(work):
    p=check();work.mkdir(mode=0o700,parents=True);REPORT.mkdir()
    items=await_source(p['BaseRun']);public=items['full-estate-monetary-public'];cache=items['full-estate-monetary-reusable-source']
    verified_download(public['Id'],p['BaseRun'],public['Sha256'],work/'original')
    receipt=read(work/'original/source-receipt.json');verified_download(cache['Id'],p['BaseRun'],cache['Sha256'],work/'cipher')
    root=work/'estate';restore_checkpoint(work/'cipher',root,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),str(p['BaseRun']),receipt['SourceSha256'])
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
    evidence=dict(OriginalRun=p['BaseRun'],OriginalPublic=public,ReusableSource=cache,OriginalSourceSha256=receipt['SourceSha256'],
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
    return registry,root/'verified-protection',work/'original'

def evaluate(work):
    registry,tapes,original=prepare(work);rows=[]
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
    receipt=read(REPORT/'source-receipt.json')
    write(REPORT/'summary.json',dict(Study=STUDY,CommonBookEvaluations=15,SourceSha256=receipt['SourceSha256'],
        Selection=estate.base.corrected_selection([x for r in rows for x in r['Selection']],3),SelectionMultiplicity=12,
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    files=sorted(PARTS.glob('*/checkpoints/**/*.json'))
    if not files:return
    receipt=read(REPORT/'source-receipt.json');public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(f,str(f.relative_to(PARTS))) for f in files],'ridge-monetary-books-sealed',public,os.environ['GITHUB_RUN_ID'],STUDY,
        receipt['SourceSha256'],complete=(REPORT/'summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','evaluate','conserve']);parser.add_argument('--work',type=Path);a=parser.parse_args()
    if a.stage=='check':check()
    elif a.stage=='evaluate':evaluate(a.work)
    else:conserve()
