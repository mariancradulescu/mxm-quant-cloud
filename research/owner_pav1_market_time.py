"""Conditional FX over verified closed sessions and common PAV1 development.

All broker facts are read from already verified custody archives. No source
collection or authentication is performed by this study. Original source bytes
are verified before a distinct source/protocol is bound.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import gzip
import hashlib

from . import owner_monetary_causal_lifecycle as prior
from . import owner_eur_recent_archive as archive
from . import owner_eur_recent_continuous as recent
from . import owner_eur_recent_funded as union
from . import owner_eur_authentic_expansion as expansion
from . import owner_eer1_source as eer
from . import owner_eer1_readback as readback
from . import integrated_market_readback as marks
from . import source_history_universe as src
from . import custody_new
from .custody import seal_new
from .decode import need
from .merge_eur_scenarios import read,exact_json

REGISTRY=Path('research/pav1_market_time_fx_1.json')
REPLAY='src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll'


def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw);old,_=prior.registered()
    need(p['Study']=='PAV1_MARKET_TIME_FX_1' and p['OriginalInstruments']==old['Instruments'] and
         p['Instruments']==sorted(old['Instruments']+['AAPL.US-24','ACWI.US','HK50-F','USDJPY']) and
         all(p[k]==old[k] for k in ('Exposure','Start','SelectionFrom','EvaluationFrom','End','Stresses')) and
         p['MaximumOpenFxAgeMs']==7200000 and p['MaximumWallFxAgeMs']==345600000 and p['SharedCapitalEur']==300 and
         p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,'PAV_MT_REGISTRY')
    rows=p['Variants'];need(len(rows)==len({r['Id'] for r in rows})==13,'PAV_MT_VARIANTS')
    base=next(v['Profile'] for v in old['Variants'] if v['Id']=='PAV1_LOCAL_TRANSITION__RISK_CONTROL')
    need(rows[0]==dict(Id='STRICT21_RISK_CONTROL',UniverseCount=21,Profile=base) and
         all(v['Profile']['KeepAdmissionRiskAtFill'] and v['Profile']['ResizeWithinAdmissionRiskAtFill'] and
             not v['Profile'].get('ModelFundingAtPriorClosedSessionQuote') and
             (v['Id']=='STRICT21_RISK_CONTROL') is (not v['Profile'].get('UseMarketTimeFxValuation',False)) for v in rows),
         'PAV_MT_PRESERVED_CONTROL')
    return p,src.digest(raw)


def download(p):
    old,_=prior.registered();prior.download(old)
    for prefix,folder in [('OriginalCausal','original-causal'),('Funding','original-funding'),('Conversion','original-conversion')]:
        archive.download_archive(p[prefix+'Artifact'],p[prefix+'Run'],p[prefix+'Sha256'],Path(folder))
    Path('extension-source').mkdir(mode=0o700)
    for a in p['ExtensionArtifacts']:
        archive.download_archive(a['Id'],a['Run'],a['Sha256'],Path('extension-source')/a['Name'])
    need(read(Path('original-causal/economic-lifecycle.json'))['Study']=='MONETARY_CAUSAL_LIFECYCLE_1',
         'PAV_MT_ORIGINAL_SCOPE')


def extension_readback(p,work,key):
    plan_raw=Path('research/official_breadth_extension_2.json').read_bytes();plan=json.loads(plan_raw)
    root=Path('extension-source');old_meta=recent.META
    recent.META=root/'breadth-extension-source-metadata'
    try:receipt,meta,account=recent.metadata_readback(plan,src.digest(plan_raw),key,str(p['ExtensionRun']))
    finally:recent.META=old_meta
    summary=receipt['summary'];public=read(root/'breadth-extension-source-verified-summary/breadth-extension-source-summary.json')
    need(read(root/'breadth-extension-source-plan/recent-plan.json')==summary and
         public['protocolSha256']==src.digest(plan_raw) and not public['pending'] and public['planned']==public['verified']==6,
         'PAV_MT_EXTENSION_COMPLETE')
    receipts={r['report']['index']:r for r in public['receipts']}
    values=defaultdict(lambda:defaultdict(list));quotes=defaultdict(list);funding=defaultdict(list)
    sink=readback.protection_tick_sink(work/'verified-protection','eer1');proofs=[]
    for i,t in enumerate(summary['partitions']):
        folder=root/f'breadth-extension-source-protected-{i}'
        row=read(folder/'receipt.json');verified=read(root/f'breadth-extension-source-verified-{i}/recent-verified.json')
        need(verified==receipts[i] and verified['sealed']==row['sealed'],'PAV_MT_EXTENSION_PUBLIC_PARITY')
        payload=eer.unpack(folder,row['sealed'],key,str(p['ExtensionRun']));packets=payload['packets']
        need(packets and all(src.decode(x['reqType'],x['req']).ctidTraderAccountId==account for x in packets),
             'PAV_MT_EXTENSION_ACCOUNT')
        journal=src.ReadbackJournal(packets)
        report,bars,q,f=recent.collect(journal,account,plan,t,summary['chargeMinutes'],tick_sink=sink,keep=True)
        report.update(runId=str(p['ExtensionRun']),protocolSha256=src.digest(plan_raw),index=i,requests=len(packets))
        need(journal.index==len(packets)==verified['packetsReconciled'] and report==row['report']==payload['report'],
             'PAV_MT_EXTENSION_PACKET_PARITY')
        for tf,series in bars.items():values[t['symbol']][tf].extend(marks.normalized_bars(series))
        quotes[t['symbol']].extend(q);funding[t['symbol']].extend(f)
        proofs.append(dict(Index=i,Target=t,Seal=row['sealed'],Packets=journal.index))
        print('PAV_MT_EXTENSION_READBACK',i+1,'/6',t['symbol'],flush=True)
    # Independently verified route leg, including its authenticated empty pages.
    conversion=read(Path('original-conversion/receipt.json'))
    payload=eer.unpack(Path('original-conversion'),conversion['sealed'],key,str(p['ConversionRun']))
    c=payload['plan'];need(c['Target']['symbol']=='USDHKD' and c['OriginalMetadataRun']==p['ExtensionRun'],
                             'PAV_MT_HKD_ROUTE_IDENTITY')
    journal=src.ReadbackJournal(payload['packets'])
    report,_,q,f=recent.collect(journal,account,json.loads(Path('research/disabled_conversion_history_1.json').read_bytes()),
        c['Target'],c['ChargeMinutes'],tick_sink=sink,keep=True)
    report.update(runId=str(p['ConversionRun']),protocolSha256=c['RegistrySha256'],requests=len(payload['packets']))
    need(journal.index==len(payload['packets']) and report==payload['report']==conversion['report'],
         'PAV_MT_HKD_FULL_PACKET_PARITY')
    quotes['USDHKD'].extend(q);funding['USDHKD'].extend(f)
    return meta,values,quotes,funding,dict(Metadata=receipt['sealed'],Partitions=proofs,Conversion=conversion['sealed'])


def add_funding_prefixes(source,original):
    tapes={t['Name']:t for t in source['Tapes']};count=0
    for row in original['Witnesses']:
        target=row['Target'];w=row['Witness']
        need(w['Status']=='AUTHENTIC_LATEST_PREFIX' and w['SearchThrough']==target['At'] and
             w['At']<=target['At'] and w['PrefixNewestFirst'] and w['LeadingTimestampComplete'],'PAV_MT_PREFIX_BINDING')
        tape=tapes[target['Symbol']];by_at={q['At']:q for q in tape['FundingQuotes']}
        q=by_at.setdefault(target['At'],dict(At=target['At'],RequestedCoverage=False,BidAt=None,AskAt=None,Bid=None,Ask=None))
        field='LatestBidPrefix' if target['Side']=='BID' else 'LatestAskPrefix'
        need(field not in q or q[field]==w,'PAV_MT_CONFLICTING_AUTHENTIC_PREFIX')
        q[field]=w;tape['FundingQuotes']=sorted(by_at.values(),key=lambda q:q['At']);count+=1
    need(count==18,'PAV_MT_EXACT_RECOVERED_PREFIX_SET');return count


def materialize(p,digest,work,receipt_path):
    old,old_digest=prior.registered();revision=os.environ['GITHUB_SHA']
    os.environ['GITHUB_SHA']=p['OriginalCausalRevision']
    try:prior.materialize(old,old_digest,work,receipt_path)
    finally:os.environ['GITHUB_SHA']=revision
    old_receipt=read(Path('original-causal/opportunity-source.json'));raw=(work/'source.json').read_bytes()
    need(read(receipt_path)==old_receipt and src.digest(raw)==old_receipt['SourceSha256'],'PAV_MT_EXACT_ORIGINAL_SOURCE_BYTES')
    source=json.loads(raw);key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    meta,bars,quotes,funding,extension=extension_readback(p,work,key)
    coverage={}
    for name in ['AAPL.US-24','ACWI.US','HK50-F','USDJPY']:
        info=meta['info'][name];terms=meta['terms'][name];margins=meta['margin'][name]
        market=dict(Name=name,Class=meta['roster'][name]['assetClass'] or 'UNMAPPED',OfficialAssetClass=meta['roster'][name]['assetClass'],
            Contract=terms,Margin=margins,TickSize=str(Decimal(1).scaleb(-info['priceDigits'])),Quotes=[],
            M5=bars[name]['M5'],M15=bars[name]['M15'],H1=bars[name]['H1'],ShortAllowed=info['shortAllowed'],
            TradingMode=info['tradingMode'],CostTermsComplete=True,EnabledAtCapture=meta['roster'][name]['enabled'],
            AdditionalTimeframes={tf:dict(Source='AUTHENTIC_BREADTH_EXTENSION_2',Bars=bars[name][tf]) for tf in ('M1','M30','H4','D1')})
        source['Markets'].append(expansion.dated_market(name,market,terms,info,meta,margins,p['Start'],p['End'],p['ExtensionRun']))
        coverage[name]={tf:len(rows) for tf,rows in bars[name].items()}
    by_name={t['Name']:t for t in source['Tapes']};quote_counts={}
    for name in sorted(set(quotes)|set(funding)):
        t=by_name.setdefault(name,dict(Name=name,Quotes=[],FundingQuotes=[]))
        t['Quotes'],conflicts=union.merge_quotes(t['Quotes'],quotes[name])
        t['FundingQuotes'],fund_conflicts=union.merge_quotes(t['FundingQuotes'],funding[name],True)
        quote_counts[name]=dict(NewMarks=len(quotes[name]),Conflicts=conflicts,FundingConflicts=fund_conflicts)
    source['Tapes']=list(by_name.values())
    for asset,route in meta['routes'].items():
        need(asset not in source['Routes'] or source['Routes'][asset]==route,'PAV_MT_ROUTE_CHANGED')
        source['Routes'].setdefault(asset,route)
    native=read(Path('original-funding/pav1-funding-native-input.json'))
    recovered=add_funding_prefixes(source,native)
    # New child source is scoped to this study. All original bytes were verified
    # above; all earlier bar history remains available causally to context.
    source['Start']=p['Start'];source['End']=p['End'];source['ExtendedEconomicContext']=True
    for m in source['Markets']:
        for field in ('ScheduledClocks','AmbiguousCalendarClocks'):
            if m.get(field) is not None:m[field]=[t for t in m[field] if p['Start']<=t<p['End']+7*recent.DAY]
    proof=dict(OriginalCausalRun=p['OriginalCausalRun'],OriginalCausalArtifact=p['OriginalCausalArtifact'],
        OriginalSourceSha256=src.digest(raw),OriginalSourceByteIdentity=True,OriginalProof=old_receipt['Proof'],
        Extension=extension,NewBarCoverage=coverage,QuoteUnion=quote_counts,ReusedAuthenticFundingPrefixes=recovered,
        SourceBrokerRequests=0,OriginalResultsModified=False,MarketCount=len(source['Markets']))
    source.update(ProtocolSha256=digest,EvidenceManifestSha256=src.digest(src.canonical(proof)),EngineRevision=revision,
        SourceAcquiredAt=max(source['SourceAcquiredAt'],max(meta['actual'].values())))
    plan={k:p[k] for k in ('Study','Exposure','Start','SelectionFrom','EvaluationFrom','End','Stresses','OriginalInstruments','Variants')}
    plan.update(SourceProtocolSha256=digest,EvidenceManifestSha256=source['EvidenceManifestSha256'])
    raw,plan_raw=src.canonical(source),src.canonical(plan)
    (work/'source.json').write_bytes(raw);(work/'pav-market-protocol.json').write_bytes(plan_raw)
    receipt_path.write_bytes(src.canonical(dict(Study=p['Study'],Proof=proof,SourceSha256=src.digest(raw),ProtocolSha256=src.digest(plan_raw),
        EvidenceManifestSha256=source['EvidenceManifestSha256'],SourceBrokerRequests=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False)))
    eur=next(m for m in source['Markets'] if m['Market']['Name']=='EURUSD')
    need(eur['CalendarStatus'] in ('CONDITIONAL_OFFICIAL_SNAPSHOT','PARTIALLY_SUPPORTED_SNAPSHOT') and
         eur['ScheduledClocks'] is not None and eur['AmbiguousCalendarClocks'] is not None,'PAV_MT_OFFICIAL_FX_CALENDAR_SCOPE')
    native['MarketTimeCalendar']=dict(From=p['Start'],Through=p['End']+7*recent.DAY,OpenClocks=eur['ScheduledClocks'],
        AmbiguousClocks=eur['AmbiguousCalendarClocks'],EvidenceSha256=src.digest(src.canonical(eur)))
    Path('pav-market-funding-input.json').write_text(exact_json(native)+'\n')
    print('PAV_MT_SOURCE_READY',len(source['Markets']),'markets',recovered,'reused prefixes',flush=True)


def seal_checkpoint(work,folder):
    """Bounded-memory encrypted file pieces; immutable source pieces are reused."""
    if not (work/'source.json').is_file():
        print('PAV_MT_NO_NORMALIZED_SOURCE_CHECKPOINT_BEFORE_SOURCE_PREPARATION',flush=True)
        return
    folder=Path(folder);folder.mkdir(exist_ok=True)
    rid=os.environ['GITHUB_RUN_ID'];public=custody_new.checked_public(Path('current-checkpoint-recipient'),rid)
    manifest_path=folder/'checkpoint-receipt.json'
    old=json.loads(manifest_path.read_bytes()) if manifest_path.exists() else {}
    need(not old or old.get('RunId')==rid,'PAV_MT_CHECKPOINT_RUN_BINDING')
    previous={f['Path']:f for f in old.get('Files',[])};files=[]
    part_number=max((int(f.stem.split('-')[1]) for f in folder.glob('part-*.sealed')),default=-1)+1
    paths=[]
    for name in ('source.json','pav-market-protocol.json','verified-protection'):
        root=work/name
        paths.extend((f,str(f.relative_to(work))) for f in ([root] if root.is_file() else sorted(root.rglob('*'))) if f.is_file())
    paths.extend((f,str(f)) for root in sorted(Path('market-partitions').glob('*/checkpoints')) for f in sorted(root.rglob('*')) if f.is_file())
    def file_sha(path):
        digest=hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(1048576),b''):digest.update(chunk)
        return digest.hexdigest()
    def record(complete):
        manifest=dict(Study='PAV1_MARKET_TIME_FX_1',RunId=rid,Schema='MXM_BOUNDED_FILE_CHECKPOINT_V1',Complete=complete,
            Files=files,ExpectedFiles=len(paths),SourceSha256=next((f['Sha256'] for f in files if f['Path']=='source.json'),None),
            MaximumPlainChunkBytes=33554432,Orders=0,CloudActivated=False)
        raw=src.canonical(manifest)
        sealed=seal_new(gzip.compress(raw,compresslevel=1,mtime=0),public,rid)
        (folder/'manifest.sealed').write_bytes(sealed)
        manifest['ManifestCipherSha256']=src.digest(sealed)
        tmp=manifest_path.with_suffix('.tmp');tmp.write_bytes(src.canonical(manifest));tmp.replace(manifest_path)
    for path,relative in paths:
        need(not path.is_symlink(),'PAV_MT_CHECKPOINT_NO_SYMLINK')
        digest=file_sha(path);prior=previous.get(relative)
        if prior and prior['Sha256']==digest and all((folder/p['File']).is_file() and
                file_sha(folder/p['File'])==p['CipherSha256'] for p in prior['Parts']):
            files.append(prior);record(False);print('PAV_MT_CHECKPOINT_REUSED',relative,flush=True);continue
        parts=[];offset=0
        with path.open('rb') as source:
            for chunk in iter(lambda:source.read(33554432),b''):
                clear=gzip.compress(chunk,compresslevel=1,mtime=0);cipher=seal_new(clear,public,rid)
                name=f'part-{part_number:06d}.sealed';part_number+=1
                (folder/name).write_bytes(cipher)
                parts.append(dict(File=name,Offset=offset,Bytes=len(chunk),PlainSha256=src.digest(chunk),CipherSha256=src.digest(cipher)))
                offset+=len(chunk)
                print('PAV_MT_CHECKPOINT_PROGRESS',relative,offset,path.stat().st_size,flush=True)
        files.append(dict(Path=relative,Bytes=offset,Sha256=digest,Parts=parts));record(False)
    record(True);print('PAV_MT_BOUNDED_CHECKPOINT_COMPLETE',len(files),'files',flush=True)


def restore_checkpoint(folder,destination,key,run,expected_source_sha256):
    """Verify the encrypted manifest and every part before exposing a source."""
    from .custody import unseal_new
    folder=Path(folder);destination=Path(destination)
    public=json.loads((folder/'checkpoint-receipt.json').read_bytes());sealed=(folder/'manifest.sealed').read_bytes()
    need(src.digest(sealed)==public['ManifestCipherSha256'],'PAV_MT_CHECKPOINT_MANIFEST_HASH')
    manifest=json.loads(gzip.decompress(unseal_new(sealed,key,run)))
    need(manifest['RunId']==run and manifest['Complete'] and manifest['SourceSha256']==expected_source_sha256 and
         len(manifest['Files'])==manifest['ExpectedFiles'],'PAV_MT_CHECKPOINT_SOURCE_BINDING')
    destination.mkdir(mode=0o700)
    for row in manifest['Files']:
        relative=Path(row['Path']);need(not relative.is_absolute() and '..' not in relative.parts,'PAV_MT_CHECKPOINT_SAFE_PATH')
        path=destination/relative;path.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256();offset=0
        with path.open('xb') as target:
            for part in row['Parts']:
                name=Path(part['File']);need(name.name==str(name),'PAV_MT_CHECKPOINT_PART_PATH')
                cipher=(folder/name).read_bytes();need(src.digest(cipher)==part['CipherSha256'],'PAV_MT_CHECKPOINT_CIPHER_HASH')
                clear=gzip.decompress(unseal_new(cipher,key,run))
                need(part['Offset']==offset and len(clear)==part['Bytes'] and src.digest(clear)==part['PlainSha256'],
                     'PAV_MT_CHECKPOINT_PART_INTEGRITY')
                target.write(clear);digest.update(clear);offset+=len(clear)
        need(offset==row['Bytes'] and digest.hexdigest()==row['Sha256'],'PAV_MT_CHECKPOINT_FILE_INTEGRITY')
    need(src.digest((destination/'source.json').read_bytes())==expected_source_sha256,'PAV_MT_RESTORED_SOURCE_IDENTITY')


def partition(p,work,stress):
    out=Path('market-partitions')/('S'+str(p['Stresses'].index(stress)));out.mkdir(parents=True,exist_ok=False)
    subprocess.run(['dotnet',REPLAY,'--owner-pav1-market-time',str(work/'pav-market-protocol.json'),str(work/'source.json'),
        str(out),str(work/'verified-protection'),str(stress)],check=True)
    r=read(out/'result.json');need(r['SharedPortfolioEvaluations']==15 and r['Orders']==0 and not r['CloudActivated'],
                                  'PAV_MT_PARTITION_RESULT')


def select(rows):
    candidates=[]
    for id in sorted(set(r['Id'] for r in rows)-{'CASH_STRICT','CASH_MARKET_TIME'}):
        selected=[r for r in rows if r['Id']==id];scores=[r['Monetary']['Score'] for r in selected]
        score=min(scores) if len(selected)==3 and all(s is not None for s in scores) else None
        support=len(selected)==3 and all(r['Result']['Hard21AllFullRegisteredWeeks'] and
            r['Result']['SampledDrawdown'] is not None and r['Result']['SampledDrawdown']<Decimal('.30') and
            (r['Result']['MaxSampledHeldPendingMarginFraction'] or 0)<=Decimal('.70') for r in selected)
        candidates.append(dict(Id=id,Score=score,OwnerSampledConstraintsMet=support,Eligible=support and score is not None and score>0 and
            all(r['Monetary']['GrossEur']>0 and r['Monetary']['NetEur']>0 for r in selected)))
    eligible=sorted((c for c in candidates if c['Eligible']),key=lambda c:(-c['Score'],c['Id']))
    return dict(Decision=eligible[0]['Id'] if eligible else 'WAIT',Candidates=candidates,
        Basis='ONLY_SELECTION_SNAPSHOTS_TAKEN_BEFORE_LATER_PERIOD; SAME_CONFIG_ALL_COST_STRESSES',PromotionCertified=False)


def combine(p):
    results=[read(path) for path in sorted(Path('market-partitions').glob('*/result.json'))]
    need(len(results)==3 and {r['Stress'] for r in results}=={Decimal(0),Decimal('.5'),Decimal(1)} and
         len({(r['SourceSha256'],r['ProtocolSha256'],r['EvidenceManifestSha256']) for r in results})==1,'PAV_MT_COMPLETE_IDENTITY')
    selection=select([row for r in results for row in r['Selection']])
    output=dict(Study=p['Study'],Results=results,Selection=selection,SharedPortfolioEvaluations=45,
        OriginalResultsModified=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False,Orders=0,CloudActivated=False)
    out=Path('market-report');out.mkdir(exist_ok=False)
    (out/'economic-market-time.json').write_text(exact_json(output)+'\n')
    for path in ('pav-market-source.json','pav-market-funding-input.json','pav-market-funding-result.json'):
        (out/path).write_bytes(Path(path).read_bytes())
    print('PAV_MT_ALL_COMPLETE',selection['Decision'],flush=True)


def main():
    cli=argparse.ArgumentParser();cli.add_argument('stage',choices=('download','materialize','partition','combine','checkpoint'))
    cli.add_argument('--work',type=Path);cli.add_argument('--stress',type=Decimal);a=cli.parse_args();p,digest=registered()
    if a.stage=='download':download(p)
    elif a.stage=='materialize':materialize(p,digest,a.work,Path('pav-market-source.json'))
    elif a.stage=='partition':partition(p,a.work,a.stress)
    elif a.stage=='checkpoint':seal_checkpoint(a.work,Path('market-checkpoint'))
    else:combine(p)


if __name__=='__main__':main()
