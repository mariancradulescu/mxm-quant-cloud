"""Recover exact funding marks for two immutable economic studies.

Custody, broker read-only capture, packet readback and native settlement run
in separate jobs. No trading, policy execution or retrospective promotion.
"""
import argparse,json,os,subprocess
from pathlib import Path
from . import owner_financing_preflight_calendar_2 as pre
from . import owner_cost_context_geometry as geometry
from . import owner_lifecycle_estimation as parent
from . import owner_funding_prefix_settlement as prefix
from . import owner_eer1_source as eer
from . import source_history_universe as src
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_pav1_market_time import restore_checkpoint,REPLAY
from .verified_research_cache import sha
from .merge_eur_scenarios import read,exact_json
from .custody_new import checked_public
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport

STUDY='OWNER_NATIVE_FUNDING_RECOVERY_2'
GEOMETRY_REVISION='145190587b8c253d2efae4a1b20346e343ed9b6b'
PLAN=Path('funding-recovery-plan')
CAPTURE=Path('funding-recovery-protected')
REPORT=Path('funding-recovery-settlement')

def write(path,value):Path(path).write_text(exact_json(value)+'\n')

def sources(work):
    earlier=Path('earlier-closed-original');geo=Path('geometry-closed-original')
    for spec,destination in ((pre.EARLIER,earlier),(pre.GEOMETRY,geo),(pre.CACHE,Path('earlier-source-cipher'))):
        verified_download(*spec,destination)
    e=read(earlier/'summary.json');g=read(geo/'summary.json')
    restore_checkpoint(Path('earlier-source-cipher'),work/'earlier',os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),
        str(pre.CACHE[1]),e['SourceSha256'],source_only=True)
    parent.restore(work/'geometry')
    w=work/'geometry'
    proof=read(geo/'source-receipt.json')['Proof'];p=proof['Registry']
    verified_download(p['FundingArtifact'],p['FundingRun'],p['FundingArchiveSha256'],Path('geometry-original-registry'))
    witness=Path('geometry-original-registry/verified-prefix-registry.json')
    need(sha(witness)==p['FundingRegistrySha256'],'RECOVERY2_GEOMETRY_REGISTRY')
    source=read(w/'source.json')
    overlay=geometry.apply_registry(source,read(witness))
    need(overlay==proof['Overlay'],'RECOVERY2_GEOMETRY_OVERLAY')
    registered=read(geo/'registered-plan.json')
    source.update(ProtocolSha256=registered['SourceProtocolSha256'],
        EvidenceManifestSha256=registered['EvidenceManifestSha256'],EngineRevision=GEOMETRY_REVISION)
    write(w/'geometry-original.json',source)
    need(sha(w/'geometry-original.json')==g['SourceSha256'],'RECOVERY2_GEOMETRY_EXACT_SOURCE')
    return [(work/'earlier'/'source.json',work/'earlier'/'verified-protection',earlier),
            (w/'geometry-original.json',w/'verified-protection',geo)]

def native(source,tape,reports,witness,out):
    subprocess.run(['dotnet',REPLAY,'--owner-funding-recovery-2',str(source),str(tape),str(reports),str(witness),str(out)],check=True)
    return read(out)

def target_keys(rows):
    return {(r['Symbol'],r['At'],r['Side']) for r in rows}

def safe_mark(q,at,both):
    from .owner_economic_mechanisms import valid_mark
    try:return valid_mark(q,at,both)
    except (TypeError,ValueError):return False

def apply_recovered_registry(source,registry,source_sha):
    """Overlay verified witnesses on a compatible child; never change a saved original."""
    from decimal import Decimal
    need(registry['Study']==STUDY and registry['Orders']==0 and not registry['CloudActivated']
         and source_sha in registry['SourceSha256']+registry.get('CompatibleBaseSourceSha256',[]),
         'RECOVERY2_REGISTRY_SOURCE')
    tapes={t['Name']:t for t in source['Tapes']};seen=set();filled=retained=unresolved=0
    for row in registry['Rows']:
        t=row['Target'];w=row['Witness'];k=(t['Symbol'],t['At'],t['Side'])
        need(k not in seen and t['Side'] in ('BID','ASK'),'RECOVERY2_REGISTRY_DUPLICATE');seen.add(k)
        if t['Symbol'] not in tapes:continue
        if w['Status']!='AUTHENTIC_LATEST_PREFIX':unresolved+=1;continue
        at=t['At'];need(w['SearchThrough']==at and w['SearchFrom']==at-345600000
            and 0<w['At']<=at and at-w['At']<=345600000 and Decimal(w['Price'])>0
            and w['PrefixNewestFirst'] and w['LeadingTimestampComplete'],'RECOVERY2_REGISTRY_PREFIX')
        quotes=tapes[t['Symbol']]['FundingQuotes'];matches=[q for q in quotes if q['At']==at]
        need(len(matches)<=1,'RECOVERY2_OVERLAY_DUPLICATE_CLOCK')
        if matches:q=matches[0]
        else:q=dict(At=at,RequestedCoverage=False,BidAt=None,AskAt=None,Bid=None,Ask=None);quotes.append(q)
        side='Bid' if t['Side']=='BID' else 'Ask';field='Latest'+side+'Prefix'
        stamp=q.get(side+'At');price=q.get(side)
        if stamp==w['At'] and price is not None:
            need(Decimal(str(price))==Decimal(w['Price']),'RECOVERY2_SAME_TIMESTAMP_CONFLICT')
        if q.get(field) is not None:
            need(q[field]==w,'RECOVERY2_EXISTING_PREFIX_CONFLICT');retained+=1
        elif q.get('RequestedCoverage') and stamp is not None and price is not None and price>0 and 0<stamp<=at and at-stamp<=7200000:
            retained+=1
        else:q[field]=w;filled+=1
        quotes.sort(key=lambda q:q['At'])
    return dict(Filled=filled,Retained=retained,UnresolvedWitnesses=unresolved)

def collect(journal,account,p):
    """Reuse complete latest prefixes across compatible clocks before issuing a request."""
    from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
    from .owner_eur_archive_funding_2 import plan_ids
    ids=plan_ids(p);cache={};rows=[]
    for t in sorted(p['Targets'],key=lambda t:(t['Symbol'],t['Side'],-t['At'])):
        hi=t['At'];lo=hi-p['LookbackMs'];key=(t['Symbol'],t['Side']);w=cache.get(key)
        if w and w['Status']=='AUTHENTIC_LATEST_PREFIX' and lo<=w['At']<=hi:
            w=dict(w,SearchFrom=lo,SearchThrough=hi)
        else:
            response,_,_=journal.query(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                symbolId=ids[t['Symbol']],type=e.BID if t['Side']=='BID' else e.ASK,
                fromTimestamp=lo,toTimestamp=hi))
            w=prefix.latest(response,account,lo,hi);cache[key]=w
        rows.append(dict(Target=t,Witness=w))
    return rows

def parity(report,native_report,source):
    from decimal import Decimal
    terms={x['Market']['Name']:x['Market']['DatedDevelopment']['Contract'] for x in source['Markets']}
    windows={}
    for i in range(3):
        for b in read(report/f'S{i}.json')['CommonBooks']:
            for w in b['Details']['OutstandingFunding']:
                windows[(b['Id'],Decimal(i)/2,w['PositionId'],w['FromExclusive'],w['Through'])]=w
    count=0;differences=[]
    for row in native_report['Windows']:
        k=(row['Id'],row['Stress'],row['PositionId'],row['FromExclusive'],row['Through'])
        w=windows[k];contract=terms[w['Symbol']]
        classifications=pre.classify_window(w)
        expected=[q['At'] for q,s in classifications if s in ('MISSING_EVIDENCE_ON_ELIGIBLE_CLOCK','NO_REPORTED_REQUIRED_MARK_GAP')]
        rate=contract['LongSwap'] if w['Side']>0 else contract['ShortSwap']
        if rate==0:expected=[]
        if row['EligibleClocks']!=expected:
            differences.append(dict(Symbol=w['Symbol'],PositionId=w['PositionId'],
                Python=expected,Native=row['EligibleClocks']))
        count+=1
    return dict(Compared=count,Differences=differences)

def prepare(work):
    work.mkdir(mode=0o700);data=sources(work);PLAN.mkdir()
    targets=set();results=[];retrospective=set();preventive_keys=set()
    for i,(source,tape,reports) in enumerate(data):
        n=native(source,tape,reports,'-',PLAN/f'native-{i}.json')
        s=read(source);comparison=parity(reports,n,s)
        # Preventive planning is reusable on either compatible normalized source.
        preventive=pre.preflight(s,safe_mark)
        write(PLAN/f'preventive-{i}.json',dict(SourceSha256=sha(source),Plan=preventive,CalendarParity=comparison))
        retrospective.update(target_keys(n['Targets']));preventive_keys.update(target_keys(preventive['Targets']))
        targets.update(target_keys(n['Targets']));targets.update(target_keys(preventive['Targets']))
        results.append(dict(SourceSha256=sha(source),ReportSha256=sha(PLAN/f'native-{i}.json'),
            PreventiveSha256=sha(PLAN/f'preventive-{i}.json'),
            OriginalWindows=n['OriginalWindows'],ReconciledBeforeCapture=n['ReconciledWindows'],
            ExcludedDiagnosticClocks=n['ExcludedDiagnosticClocks'],Parity=comparison))
    plan=dict(Study=STUDY,RunId=os.environ['GITHUB_RUN_ID'],LookbackMs=345600000,
        Targets=[dict(Symbol=s,At=a,Side=d) for s,a,d in sorted(targets)],
        RetrospectiveTargets=len(retrospective),PreventiveTargets=len(preventive_keys),
        SharedTargets=len(retrospective&preventive_keys),
        Sources=results,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False)
    write(PLAN/'plan.json',plan)
    print('RECOVERY2_AUTHORIZED_TARGETS',len(targets),flush=True)

def checked_plan():
    p=json.loads((PLAN/'plan.json').read_bytes())
    need(p['Study']==STUDY and p['RunId']==os.environ['GITHUB_RUN_ID']
         and p['LookbackMs']==345600000 and len(p['Targets'])==len(target_keys(p['Targets']))
         and p['Orders']==0 and not p['CloudActivated'],'RECOVERY2_PLAN_BINDING')
    for i,s in enumerate(p['Sources']):
        need(sha(PLAN/f'native-{i}.json')==s['ReportSha256'],'RECOVERY2_PLAN_REPORT')
        need(sha(PLAN/f'preventive-{i}.json')==s['PreventiveSha256'],'RECOVERY2_PREVENTIVE_REPORT')
    union=set().union(*(target_keys(read(PLAN/f'native-{i}.json')['Targets']) for i in range(len(p['Sources']))))
    union.update(set().union(*(target_keys(read(PLAN/f'preventive-{i}.json')['Plan']['Targets']) for i in range(len(p['Sources'])))))
    need(target_keys(p['Targets'])==union,'RECOVERY2_PLAN_SCOPE')
    return p,sha(PLAN/'plan.json')

def capture():
    p,digest=checked_plan();rid=os.environ['GITHUB_RUN_ID']
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main'
        and os.environ['GITHUB_RUN_ATTEMPT']=='1','RECOVERY2_READONLY_CONTEXT')
    rows=[];packets=[]
    if p['Targets']:
        t=P05ReadOnlyTransport(response_timeout=20)
        try:
            account=authenticate(t);need(src.original_account(account),'RECOVERY2_ACCOUNT')
            journal=src.Journal(t,account);rows=collect(journal,account,p);packets=journal.packets
        finally:t.close()
    CAPTURE.mkdir()
    sealed=eer.seal(CAPTURE/'packets.sealed',dict(runId=rid,protocolSha256=digest,rows=rows,packets=packets),
        checked_public(Path('new-recipient-output'),rid),rid)
    write(CAPTURE/'receipt.json',dict(sealed=sealed,requests=len(packets),targets=len(p['Targets']),Orders=0,CloudActivated=False))
    print('RECOVERY2_CAPTURE',len(packets),'REQUESTS',flush=True)

def verify(work):
    p,digest=checked_plan();rid=os.environ['GITHUB_RUN_ID']
    receipt=read(CAPTURE/'receipt.json')
    d=eer.unpack(CAPTURE,receipt['sealed'],os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),rid)
    need(d['runId']==rid and d['protocolSha256']==digest,'RECOVERY2_CAPTURE_BINDING')
    packets=d['packets']
    if packets:
        account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
        need(src.original_account(account),'RECOVERY2_READBACK_ACCOUNT')
        journal=src.ReadbackJournal(packets);rows=collect(journal,account,p)
        need(journal.index==len(packets)==receipt['requests'],'RECOVERY2_PACKET_PARITY')
    else:
        need(not p['Targets'] and receipt['requests']==0,'RECOVERY2_EMPTY_CAPTURE');rows=[]
    need(rows==d['rows'],'RECOVERY2_EXACT_READBACK')
    work.mkdir(mode=0o700);data=sources(work);REPORT.mkdir()
    witness=work/'witness.json';write(witness,rows)
    results=[];coverage=[]
    registry=dict(Study=STUDY,RunId=rid,PlanSha256=digest,
        SourceSha256=[s['SourceSha256'] for s in p['Sources']],CompatibleBaseSourceSha256=[parent.SOURCE],
        PacketReceipt=receipt,Rows=rows,PacketsReconciled=len(packets),
        OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False)
    for i,(source,tape,reports) in enumerate(data):
        need(sha(source)==p['Sources'][i]['SourceSha256'],'RECOVERY2_SOURCE_RESTORATION')
        n=native(source,tape,reports,witness,REPORT/f'native-{i}.json')
        need(target_keys(n['Targets'])==target_keys(read(PLAN/f'native-{i}.json')['Targets']),'RECOVERY2_REPRODUCED_TARGETS')
        results.append(n)
        child=read(source);overlay=apply_recovered_registry(child,registry,sha(source))
        remaining=pre.preflight(child,safe_mark)
        coverage.append(dict(SourceSha256=sha(source),Overlay=overlay,Remaining=remaining))
    write(REPORT/'verified-prefix-registry.json',registry)
    write(REPORT/'preventive-coverage.json',dict(Sources=coverage,Targets=len(p['Targets']),
        RetrospectiveTargets=p['RetrospectiveTargets'],PreventiveTargets=p['PreventiveTargets'],
        SharedTargets=p['SharedTargets'],SourceBrokerRequests=len(packets),
        ReusedWitnesses=len(rows)-len(packets),
        UnresolvedWitnesses=[r for r in rows if r['Witness']['Status']!='AUTHENTIC_LATEST_PREFIX'],
        Orders=0,CloudActivated=False))
    write(REPORT/'summary.json',dict(Study=STUDY,OriginalWindows=sum(n['OriginalWindows'] for n in results),
        ReconciledWindows=sum(n['ReconciledWindows'] for n in results),SourceBrokerRequests=len(packets),
        AuthenticPrefixes=sum(r['Witness']['Status']=='AUTHENTIC_LATEST_PREFIX' for r in rows),
        PreventiveTargets=p['PreventiveTargets'],DistinctCollectionTargets=len(p['Targets']),
        RemainingPreventiveTargets=len(set().union(*(target_keys(c['Remaining']['Targets']) for c in coverage))),
        LocalUnresolved=sum(len(c['Remaining']['LocalUnresolved']) for c in coverage),
        OriginalPoliciesReplayed=0,OriginalEquityHistoryRestored=False,HistoricalTariffCertified=False,
        IndependentConfirmationCertified=False,Orders=0,CloudActivated=False))
    print('RECOVERY2_SETTLEMENT',read(REPORT/'summary.json'),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','capture','verify'))
    p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='prepare':prepare(a.work)
    elif a.stage=='capture':capture()
    else:verify(a.work)

if __name__=='__main__':main()
