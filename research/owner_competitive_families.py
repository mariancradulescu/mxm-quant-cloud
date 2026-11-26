"""29-market conditional research with seven-family competitive common books.
The annual archive supplies authentic closed-bar context, NOT annual execution
coverage. New instruments only trade where original marks actually exist.
"""
import argparse,base64,gzip,hashlib,json,os,subprocess,time
from decimal import Decimal
from pathlib import Path
from .decode import need
from .merge_eur_scenarios import read,exact_json
from .owner_eur_recent_archive import download_archive
from .owner_pav1_market_time import restore_checkpoint,select
from .owner_eur_authentic_expansion import dated_market
from .owner_eur_recent_funded import merge_quotes
from .owner_monetary_reduce_common_book import (SOURCE_RUN,SOURCE_ARTIFACT,SOURCE_ARCHIVE_SHA,
    SOURCE_SHA,ORIGINAL_PLAN_SHA,REPLAY,STRESSES,file_digest)
from .custody import unseal_new,seal_new
from .custody_new import derive_recipient

STUDY='MONETARY_COMPETITIVE_FAMILIES_1'
ANNUAL_RUN=45835675987
PUBLIC_ID=15125780700
PUBLIC_SHA='013ec18ecc163d7f1a50b10fc601733184138344324eba592c728e651be15d59'
NORMAL_ID=15125391357
NORMAL_SHA='31bf99af7a8c22d3eaf72ca0efb5d0824b55c22b3b4341ef247877a2f53e871b'
NEW=('USDX','XPDUSD','Copper','DOTUSD')
DAY=86400000

def write(path,obj):path.write_text(exact_json(obj)+'\n')
def digest(raw):return hashlib.sha256(raw).hexdigest()

def variants():
    base=dict(UseAvailableContext=True,EconomicMechanism='SCP1_LOCAL_LIFECYCLE',
              CompeteEconomicFamilies=True,LearnFromOpportunityEpisodes=True,
              ObserveFamilyDirectionsOnClosedBars=True,UseMarketTimeFxValuation=True,
              CaptureClosedBarActivity=True,ModeledStopLatencyMs=100,
              ObserveIntentExecutionOnTicks=True,KeepAdmissionRiskAtFill=True,
              ResizeWithinAdmissionRiskAtFill=True,ReserveObservedBarGaps=True,
              DistributionTargetRanges=2,EconomicGeometryTimeframe='H1',
              EconomicStopRanges=Decimal('.75'),MinimumContractVolumeOnly=False)
    return [dict(Id='JOINT_'+management,UniverseCount=29,Profile=dict(base,EconomicManagement=management))
            for management in ('TRANSITION_VALUE','MONETARY_REDUCE')]

def prepare(work):
    started=time.monotonic()
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    download_archive(SOURCE_ARTIFACT,SOURCE_RUN,SOURCE_ARCHIVE_SHA,work.parent/'competitive-source-archive')
    downloaded=time.monotonic()
    restore_checkpoint(work.parent/'competitive-source-archive',work,key,str(SOURCE_RUN),SOURCE_SHA,source_only=True)
    need(file_digest(work/'pav-market-protocol.json')==ORIGINAL_PLAN_SHA,'COMPETITIVE_ORIGINAL_PLAN')
    restored=time.monotonic()
    download_archive(PUBLIC_ID,ANNUAL_RUN,PUBLIC_SHA,work.parent/'annual-public')
    download_archive(NORMAL_ID,ANNUAL_RUN,NORMAL_SHA,work.parent/'annual-normalized')
    receipt=read(work.parent/'annual-public/official-annual-bar-spans.json')
    seal=receipt['NormalizedSourceSeal']
    cipher=(work.parent/'annual-normalized'/seal['file']).read_bytes()
    need(digest(cipher)==seal['cipherSha256'],'COMPETITIVE_ANNUAL_CIPHER')
    compressed=unseal_new(cipher,key,str(ANNUAL_RUN))
    need(digest(compressed)==seal['plainSha256'],'COMPETITIVE_ANNUAL_PLAINTEXT')
    del cipher
    annual=json.loads(gzip.decompress(compressed),parse_float=Decimal)
    del compressed
    need(annual['Study']==receipt['Study']=='OFFICIAL_BREADTH_EXTENSION_3_SPANS'
         and annual['SourceRegistrySha256']==receipt['SourceRegistrySha256']
         and annual['Proof']==receipt['Reports'] and annual['Orders']==0
         and not annual['CloudActivated'],'COMPETITIVE_ANNUAL_RECEIPT')
    # Raw nominal rows are preserved in the sealed parent. Only quarantined,
    # reusable normalized rows enter this new source.
    annual.pop('OriginalNominalClosedRows')
    source=read(work/'source.json');original=read(work/'pav-market-protocol.json')
    plan={k:original[k] for k in ('Exposure','Start','SelectionFrom','EvaluationFrom','Stresses','OriginalInstruments')}
    plan.update(Study=STUDY,End=original['End']+DAY,Variants=variants())
    need(len(source['Markets'])==25 and {m['Market']['Name'] for m in source['Markets']}.isdisjoint(NEW),
         'COMPETITIVE_ORIGINAL_UNIVERSE')
    meta=annual['Metadata'];bars=annual['Bars'];coverage={}
    for name in NEW:
        info=meta['info'][name];terms=meta['terms'][name];margins=meta['margin'][name]
        market=dict(Name=name,Class=meta['roster'][name]['assetClass'] or 'UNMAPPED',
            OfficialAssetClass=meta['roster'][name]['assetClass'],Contract=terms,Margin=margins,
            TickSize=str(Decimal(1).scaleb(-info['priceDigits'])),Quotes=[],
            M5=bars[name]['M5'],M15=bars[name]['M15'],H1=bars[name]['H1'],
            ShortAllowed=info['shortAllowed'],TradingMode=info['tradingMode'],
            CostTermsComplete=True,EnabledAtCapture=meta['roster'][name]['enabled'],
            AdditionalTimeframes={tf:dict(Source='AUTHENTIC_BREADTH_EXTENSION_3_SPANS',Bars=bars[name][tf])
                                  for tf in ('M1','M30','H4','D1')})
        source['Markets'].append(dated_market(name,market,terms,info,meta,margins,plan['Start'],plan['End'],annual['SourceRun']))
        observed=next(row for row in receipt['Reports'] if row['Symbol']==name)
        need(all(len(bars[name][tf])==row['ReusableRows'] for tf,row in observed['BarCoverage'].items()),
             'COMPETITIVE_ANNUAL_QUARANTINE_PARITY')
        coverage[name]=dict(ReusableBars={tf:len(rows) for tf,rows in bars[name].items()},
                            MonetaryMarks=observed['MonetaryMarks'],TickFrom=observed['TickFrom'],
                            TickThrough=observed['TickThrough'])
    by_name={t['Name']:t for t in source['Tapes']}
    for name in sorted(set(annual['Quotes'])|set(annual['Funding'])):
        t=by_name.setdefault(name,dict(Name=name,Quotes=[],FundingQuotes=[]))
        t['Quotes'],q_conflicts=merge_quotes(t['Quotes'],annual['Quotes'].get(name,[]))
        t['FundingQuotes'],f_conflicts=merge_quotes(t['FundingQuotes'],annual['Funding'].get(name,[]),True)
        need(q_conflicts==f_conflicts==0,'COMPETITIVE_EXTENSION_CONFLICT')
    source['Tapes']=list(by_name.values())
    for asset,route in meta['routes'].items():
        need(asset not in source['Routes'] or source['Routes'][asset]==route,'COMPETITIVE_FX_ROUTE_CHANGED')
        source['Routes'].setdefault(asset,route)
    for name,encoded in annual['ProtectionFiles'].items():
        need(Path(name).name==name and name.endswith(('.ticks','.coverage')),'COMPETITIVE_SAFE_TAPE')
        raw=base64.b64decode(encoded,validate=True)
        need(len(raw)%16==0,'COMPETITIVE_TAPE_RECORD_SIZE')
        with (work/'verified-protection'/name).open('ab') as tape:tape.write(raw)
    proof=dict(OriginalSourceSha256=SOURCE_SHA,OriginalCheckpointArtifact=SOURCE_ARTIFACT,
               AnnualSourceArtifact=NORMAL_ID,AnnualArchiveSha256=NORMAL_SHA,AnnualReceiptArtifact=PUBLIC_ID,
               AnnualReceiptArchiveSha256=PUBLIC_SHA,AnnualSeal=seal,NewMarketCoverage=coverage,
               OriginalSourceReconstructionExecutions=0,SourceBrokerRequests=0,
               AnnualBarHistoryIsNotAnnualEconomicConfirmation=True,Orders=0,CloudActivated=False)
    registration=digest(exact_json(plan).encode())
    evidence=digest(exact_json(proof).encode())
    source.update(End=plan['End'],FitEnd=plan['SelectionFrom'],ProtocolSha256=registration,
                  EvidenceManifestSha256=evidence,EngineRevision=os.environ['GITHUB_SHA'],
                  SourceAcquiredAt=max(source['SourceAcquiredAt'],max(meta['actual'].values())))
    plan.update(SourceProtocolSha256=registration,EvidenceManifestSha256=evidence)
    del annual
    write(work/'competitive-source.json',source)
    write(work/'competitive-plan.json',plan)
    report=Path('competitive-report');report.mkdir()
    write(report/'source-receipt.json',dict(Study=STUDY,Proof=proof,SourceSha256=file_digest(work/'competitive-source.json'),
        ProtocolSha256=file_digest(work/'competitive-plan.json'),DownloadSeconds=round(downloaded-started,3),
        SourceOnlyRestoreSeconds=round(restored-downloaded,3),TotalPreparationSeconds=round(time.monotonic()-started,3)))
    print('COMPETITIVE_SOURCE_READY',len(source['Markets']),flush=True)

def evaluate(work):
    report=Path('competitive-report');receipt=read(report/'source-receipt.json')
    need(receipt['SourceSha256']==file_digest(work/'competitive-source.json') and
         receipt['ProtocolSha256']==file_digest(work/'competitive-plan.json'),'COMPETITIVE_SOURCE_BINDING')
    results=[]
    for i,stress in enumerate(STRESSES):
        out=Path('competitive-partitions')/('S'+str(i));out.mkdir(parents=True,exist_ok=False)
        subprocess.run(['dotnet',REPLAY,'--owner-competitive-families',str(work/'competitive-plan.json'),
                        str(work/'competitive-source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==3 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256']
             and result['Orders']==0 and not result['CloudActivated'],'COMPETITIVE_RESULT_BINDING')
        results.append(result)
        (report/('S'+str(i)+'.json')).write_bytes((out/'result.json').read_bytes())
        print('COMPETITIVE_SCENARIO_COMPLETE',i,flush=True)
    write(report/'summary.json',dict(Study=STUDY,SharedPortfolioEvaluations=9,
        Selection=select([row for r in results for row in r['Selection']]),SourceSha256=receipt['SourceSha256'],
        ProtocolSha256=receipt['ProtocolSha256'],Orders=0,CloudActivated=False,
        IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve(work):
    root=Path('competitive-partitions')
    if not root.exists():return
    files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:return
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    rid=os.environ['GITHUB_RUN_ID'];dest=Path('competitive-sealed-books');dest.mkdir()
    rows=[];counter=0
    for path in files:
        parts=[];offset=0
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(33554432),b''):
                cipher=seal_new(gzip.compress(chunk,compresslevel=1,mtime=0),public,rid)
                name=f'part-{counter:06d}.sealed';counter+=1;(dest/name).write_bytes(cipher)
                parts.append(dict(File=name,Offset=offset,Bytes=len(chunk),PlainSha256=digest(chunk),CipherSha256=digest(cipher)))
                offset+=len(chunk)
        rows.append(dict(Path=str(path.relative_to(root)),Bytes=offset,Sha256=file_digest(path),Parts=parts))
    receipt=read(Path('competitive-report/source-receipt.json'))
    manifest=dict(Study=STUDY,RunId=rid,SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
                  OriginalCheckpointArtifact=SOURCE_ARTIFACT,AnnualSourceArtifact=NORMAL_ID,Files=rows,
                  Complete=(Path('competitive-report/summary.json').exists()),Orders=0,CloudActivated=False)
    (dest/'manifest.sealed').write_bytes(seal_new(gzip.compress(exact_json(manifest).encode(),compresslevel=1,mtime=0),public,rid))
    write(dest/'receipt.json',dict(Study=STUDY,RunId=rid,Files=len(rows),Complete=manifest['Complete'],
        SourceSha256=receipt['SourceSha256'],ManifestCipherSha256=file_digest(dest/'manifest.sealed'),Orders=0,CloudActivated=False))

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','prepare','evaluate','conserve'))
    p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':
        need(len(variants())==2 and len(NEW)==4,'COMPETITIVE_REGISTRATION')
        print('COMPETITIVE_VARIANTS_READY')
    elif a.stage=='prepare':prepare(a.work)
    elif a.stage=='evaluate':evaluate(a.work)
    else:conserve(a.work)
if __name__=='__main__':main()
