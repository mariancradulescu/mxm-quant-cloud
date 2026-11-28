"""Verified original source recovery and per-instrument timeframe spool.
No source request, no strategy replay, no unverified bars silently substituted.
"""
import gc,hashlib,json,os,subprocess
from decimal import Decimal
from pathlib import Path
from collections import defaultdict
from .merge_eur_scenarios import read,exact_json
from .decode import need
from . import source_history_universe as src
from . import owner_source_history_use as old
from . import owner_eer1_source as eer
from . import owner_eur_recent_continuous as recent
from . import multiscale_conditional_research as historic
from . import integrated_market_readback as normalize
from .owner_official_breadth_spans import normalize_with_quarantine
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .custody import unseal_new
from .verified_research_cache import sha
from .bounded_exact_json import write as bounded_write
from .ctrader_proto import OpenApiMessages_pb2 as messages,OpenApiModelMessages_pb2 as models

def canonical_bar(x):
    return dict(OpenAt=int(x['OpenAt']),CloseAt=int(x['CloseAt']),Open=Decimal(str(x['Open'])),
        High=Decimal(str(x['High'])),Low=Decimal(str(x['Low'])),Close=Decimal(str(x['Close'])),TickVolume=int(x['TickVolume']))

def merge_series(*parts):
    return merge_series_parts(parts)

def merge_series_parts(parts):
    """Consume one authenticated shard at a time; keep quarantines across shards."""
    by={};bad=set()
    for part in parts:
        for x in part:
            x=canonical_bar(x);t=x['OpenAt']
            if t in by and by[t]!=x:bad.add(t)
            by[t]=x
    ordered=[by[t] for t in sorted(by) if t not in bad]
    overlap=set()
    for a,b in zip(ordered,ordered[1:]):
        if a['CloseAt']>b['OpenAt']:overlap.update((a['OpenAt'],b['OpenAt']))
    return [x for x in ordered if x['OpenAt'] not in overlap],dict(ConflictingOpens=len(bad),OverlappingOpens=len(overlap))

def save_series(root,symbol,tf,series,origin):
    if tf not in src.PERIODS or not series:return
    name=hashlib.sha256((symbol+'/'+tf+'/'+origin).encode()).hexdigest()
    p=root/(name+'.json')
    need(not p.exists(),'ESTATE_SOURCE_IDENTITY')
    bounded_write(p,dict(Symbol=symbol,Timeframe=tf,Origin=origin,Bars=series))

def fetch(a,dest):
    verified_download(a['Artifact'],a['Run'],a['Sha256'],dest)

def raw_packets(root,archive,packets,roster,proofs):
    rows=defaultdict(list);accepted=0;account=None
    for packet in packets:
        q=src.decode(packet['reqType'],packet['req'])
        if not isinstance(q,messages.ProtoOAGetTrendbarsReq):continue
        if account is None:account=q.ctidTraderAccountId
        need(src.original_account(account) and q.ctidTraderAccountId==account,'ESTATE_ACCOUNT')
        if packet['res'] is None:continue
        reply=src.decode(packet['resType'],packet['res'])
        if not isinstance(reply,messages.ProtoOAGetTrendbarsRes):continue
        tf=models.ProtoOATrendbarPeriod.Name(q.period);symbol=roster.get(q.symbolId)
        if not symbol or tf not in src.PERIODS:continue
        receipt,bars=old.inspect_bars(q,reply,packet['availableAt'])
        if receipt['status']!='CLOSED_ROWS_VERIFIED':continue
        rows[symbol,tf].extend(bars);accepted+=len(bars)
    for (symbol,tf),series in rows.items():
        by=defaultdict(list)
        for row in series:by[row[0]].append(row)
        unique=[x[0] for _,x in sorted(by.items()) if all(v==x[0] for v in x)]
        normalized,_=normalize_with_quarantine(unique)
        save_series(root,symbol,tf,normalized,str(archive['Artifact']))
    proofs.append(dict(Archive=archive,Packets=len(packets),AcceptedRawBars=accepted,Markets=len({x[0] for x in rows}),Series=len(rows)))

def extend_estate(root,work,p,include_expansion=True):
    work.mkdir(mode=0o700);spec=p['ExtendedEstateSources'];proofs=[]
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    a,b=spec[:2];fetch(a,work/'original');fetch(b,work/'receipt')
    receipt_path=work/'original/receipt.json'
    if receipt_path.exists():need(receipt_path.read_bytes()==(work/'receipt/receipt.json').read_bytes(),'ESTATE_RECEIPT_PARITY')
    else:receipt_path.write_bytes((work/'receipt/receipt.json').read_bytes())
    packets,receipt=old.verified_original(work/'original',key)
    roster={x['symbolId']:x['name'] for x in receipt['contractRoster']}
    raw_packets(root,a,packets,roster,proofs);del packets,receipt;gc.collect()
    for a in spec[2:5]:
        dest=work/str(a['Artifact']);fetch(a,dest)
        receipt=read(dest/'receipt.json');cipher=(dest/a['File']).read_bytes()
        need(src.digest(cipher)==receipt['ciphertextSha256'] and str(receipt['runId'])==str(a['Run']),'ESTATE_CIPHER')
        raw=unseal_new(cipher,key,str(a['Run']))
        need(src.digest(raw)==receipt['plaintextSha256'],'ESTATE_PLAINTEXT')
        obj=json.loads(raw);need(receipt==dict(obj[a['Payload']],ciphertextSha256=src.digest(cipher),plaintextSha256=src.digest(raw)),'ESTATE_RECEIPT')
        raw_packets(root,a,obj['packets'],roster,proofs);del obj,raw,cipher;gc.collect()
    older=read(Path('research/hrc1_protocol.json'))['source']
    for a,recipe in zip(spec[5:],older):
        dest=work/str(a['Artifact']);fetch(a,dest)
        b,decoded,proof=historic.recover(dest,recipe['run'],recipe['hash'],recipe['schema'],recipe['protocol'])
        for symbol,rows in b['bars'].items():
            normalized,_=normalize_with_quarantine(rows)
            save_series(root,symbol,'M5',normalized,str(a['Artifact']))
        proofs.append(dict(Archive=a,Readback=proof));del b,decoded;gc.collect()
    # Include tranche 11 if its original collection has completed. No new
    # source calls and no incomplete artifact masquerades as complete coverage.
    run=p['ExpansionRun'];repo=os.environ['GITHUB_REPOSITORY']
    if not include_expansion:
        bounded_write(work/'estate-provenance.json',dict(Archives=proofs,Expansion=dict(Run=run,Included=False,
            SeparateVerifiedFragment=True),SourceBrokerRequests=0,Orders=0,CloudActivated=False))
        return
    state=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}']))
    expansion=dict(Run=run,Status=state['status'],Conclusion=state['conclusion'],Included=False)
    if state['status']=='completed' and state['conclusion']=='success':
        pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100']))
        arts={a['name']:dict(Run=run,Artifact=a['id'],Sha256=a['digest'].removeprefix('sha256:')) for page in pages for a in page['artifacts'] if not a['expired']}
        prefix='breadth-extension-11-source-';dest=work/'tranche11';dest.mkdir()
        for name in ('plan','metadata','verified-summary'):fetch(arts[prefix+name],dest/name)
        plan=read(dest/'plan/recent-plan.json');summary=read(dest/'verified-summary/breadth-extension-11-source-summary.json')
        receipt=read(dest/'metadata/receipt.json');payload=eer.unpack(dest/'metadata',receipt['sealed'],key,str(run))
        account=src.decode(payload['packets'][0]['reqType'],payload['packets'][0]['req']).ctidTraderAccountId
        need(src.original_account(account) and plan['runId']==str(run) and plan['protocolSha256']==summary['protocolSha256']==payload['protocolSha256']
            and summary['planned']==summary['verified']==len(plan['partitions']) and not summary['pending'],'ESTATE_TRANCHE11_BINDING')
        recipe=read(Path('research/official_breadth_extension_11.json'))
        for i,t in enumerate(plan['partitions']):
            if not t['bars']:continue
            a=arts[prefix+'protected-'+str(i)];folder=dest/str(i);fetch(a,folder)
            rec=read(folder/'receipt.json');data=eer.unpack(folder,rec['sealed'],key,str(run));j=src.ReadbackJournal(data['packets'])
            report,bars,_,_=recent.collect(j,account,recipe,t,plan['chargeMinutes'],keep=True)
            report.update(runId=str(run),protocolSha256=plan['protocolSha256'],index=i,requests=len(data['packets']))
            original=next(x for x in summary['receipts'] if x['report']['index']==i)
            need(report==data['report']==rec['report']==original['report'] and j.index==original['packetsReconciled']==len(data['packets'])
                and rec['sealed']==original['sealed'],'ESTATE_TRANCHE11_PARITY')
            for tf,rows in bars.items():
                norm,_=normalize_with_quarantine(rows);save_series(root,t['symbol'],tf,norm,f'T11-{i}')
            del data,bars;gc.collect()
        expansion.update(Included=True,Selected=plan['chosen'],VerifiedPartitions=summary['verified'])
    (work/'estate-provenance.json').write_text(exact_json(dict(Archives=proofs,Expansion=expansion,SourceBrokerRequests=0,Orders=0,CloudActivated=False))+'\n')

def reconcile_series(root,report):
    groups=defaultdict(list)
    for path in sorted(root.glob('*.json')):
        # Read just the identity once; no raw prices go to the public report.
        x=read(path);groups[x['Symbol'],x['Timeframe']].append(path);del x
    merged=root.parent/'merged-estate';merged.mkdir()
    manifest=[]
    for (symbol,tf),paths in sorted(groups.items()):
        rows,quality=merge_series_parts(read(f)['Bars'] for f in paths)
        path=merged/(hashlib.sha256((symbol+'/'+tf).encode()).hexdigest()+'.json')
        bounded_write(path,dict(Symbol=symbol,Timeframe=tf,Bars=rows))
        manifest.append(dict(Symbol=symbol,Timeframe=tf,File=path.name,Sha256=sha(path),Rows=len(rows),Quarantine=quality,SourceFiles=len(paths)))
        del rows;gc.collect()
    (merged/'manifest.json').write_text(exact_json(manifest)+'\n')
    (report/'recovered-estate-manifest.json').write_text(exact_json(manifest)+'\n')
    (report/'estate-provenance.json').write_bytes((root.parent/'older/estate-provenance.json').read_bytes())
    return merged,manifest

def run_recovered(root,report,p):
    merged,_=reconcile_series(root,report)
    subprocess.run(['dotnet','run','--project','src/Mxm.PathResearch','-c','Release','--no-build','--','--estate-recovery',str(merged),str(report/'recovered-mechanisms.json')],check=True)
