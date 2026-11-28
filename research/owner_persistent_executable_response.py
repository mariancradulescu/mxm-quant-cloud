"""Recover actual quote information for a frozen persistent close; no original policy replay."""
import argparse,gc,json,os,shutil,subprocess,time
from pathlib import Path
from . import owner_controlled_recency as parent
from . import owner_eur_recent_continuous as recent
from . import owner_eer1_source as eer
from . import owner_eer1_readback as readback
from . import source_history_universe as src
from .owner_held_equity_recovery import restore_final_books
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_eur_archive_funding_2 import plan_ids
from .owner_monetary_reduce_common_book import REPLAY
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport
from .custody_new import checked_public
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
STUDY='OWNER_PERSISTENT_EXECUTABLE_RESPONSE_1'
REG=Path('research/persistent_executable_response_1.json')
REPORT=Path('persistent-response-report')
CAPTURE=Path('persistent-response-protected')
def write(path,value):Path(path).write_text(exact_json(value)+'\n')
def registered():
    p=read(REG)
    need(p['Study']==STUDY and p['Targets']==['GBPUSD','EURUSD'] and p['From']==1795564800000 and p['ThroughExclusive']==1795651200000 and
        p['OriginalPreventiveAt']==1795578015000 and p['OriginalHardAt']==1795599015000 and
        p['OriginalResultsModified']==p['Orders']==0 and not p['CloudActivated'],'PERSISTENT_RESPONSE_REGISTRATION')
    return p

def targets(p):
    ids=plan_ids(dict(Targets=[dict(Symbol=n) for n in p['Targets']]))
    return [dict(symbol=n,symbolId=ids[n],bars=False,window='ACTUAL_NOV25_PENDING_PROTECTION',fromInclusive=p['From'],
        throughExclusive=p['ThroughExclusive']) for n in p['Targets']]

def original(work):
    p=registered();work.mkdir(parents=True,mode=0o700);a=p['OriginalReport'];b=p['OriginalBooks']
    verified_download(a['Artifact'],a['Run'],a['Sha256'],work/'original')
    receipt=read(work/'original/source-receipt.json');plan=read(work/'original/registered-plan.json')
    need(receipt['SourceSha256']==p['OriginalSourceSha256'],'PERSISTENT_RESPONSE_SOURCE_RECEIPT')
    revision=os.environ['GITHUB_SHA'];os.environ['GITHUB_SHA']=p['OriginalHead']
    try:parent.prepare(work/'source','recent')
    finally:os.environ['GITHUB_SHA']=revision
    source=read(work/'source/net-source.json')
    source.update(ProtocolSha256=plan['SourceProtocolSha256'],EvidenceManifestSha256=plan['EvidenceManifestSha256'],EngineRevision=p['OriginalHead'])
    path=work/'source/exact-original-source.json';write(path,source);del source;gc.collect()
    need(sha(path)==p['OriginalSourceSha256'],'PERSISTENT_RESPONSE_EXACT_SOURCE_BYTES')
    paths=list(restore_final_books((b['Artifact'],b['Run'],b['Sha256']),work/'books-cipher',work/'books',
        os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),receipt['SourceSha256'],wanted={('S1','CENTERED_GUARD')},protocol_sha=receipt['ProtocolSha256']))
    need(len(paths)==1,'PERSISTENT_RESPONSE_ONE_ORIGINAL_BOOK')
    return p,path,paths[0],work/'original/S1-result.json',work/'source/verified-protection'

def native(source,book,report,old_tape,new_tape,out):
    subprocess.run(['dotnet',REPLAY,'--owner-persistent-response',str(source),str(book),str(report),str(old_tape),str(new_tape),str(out)],check=True)
    r=read(out);need(r['Study']==STUDY and r['OriginalPrefixReconstructedWithoutPolicyReplay'] and
        r['InheritedOriginalStateResponseOnly'] and r['Orders']==0 and not r['CloudActivated'],'PERSISTENT_RESPONSE_NATIVE')
    return r

def prepare(work):
    p,source,book,report,tape=original(work);REPORT.mkdir()
    result=native(source,book,report,tape,tape,REPORT/'preflight.json')
    write(REPORT/'registered-targets.json',dict(Study=STUDY,RegistrationSha256=sha(REG),Targets=targets(p),
        NeedCapture=result['NeedAdditionalQuoteCapture'],OriginalSourceSha256=p['OriginalSourceSha256'],Orders=0,CloudActivated=False))
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('need_capture='+str(result['NeedAdditionalQuoteCapture']).lower()+'\n')
    print('PERSISTENT_RESPONSE_PREFLIGHT_NEED_CAPTURE',result['NeedAdditionalQuoteCapture'],flush=True)

def collect(journal,account,p,sink=None):
    results=[]
    for t in targets(p):
        report,_,_,_=recent.collect(journal,account,p,t,[],tick_sink=sink,keep=False)
        results.append(report)
    return results

def capture():
    p=registered();rid=os.environ['GITHUB_RUN_ID']
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main' and os.environ['GITHUB_RUN_ATTEMPT']=='1','PERSISTENT_RESPONSE_CAPTURE_CONTEXT')
    plan=read(REPORT/'registered-targets.json');need(plan['RegistrationSha256']==sha(REG) and plan['NeedCapture'],'PERSISTENT_RESPONSE_CAPTURE_NEEDED')
    transport=P05ReadOnlyTransport(response_timeout=20)
    try:
        account=authenticate(transport);need(src.original_account(account),'PERSISTENT_RESPONSE_ORIGINAL_ACCOUNT')
        src.MAX_REQUESTS=5000;journal=src.Journal(transport,account);journal.deadline=time.monotonic()+3000
        rows=collect(journal,account,p)
    finally:transport.close()
    CAPTURE.mkdir();sealed=eer.seal(CAPTURE/'packets.sealed',dict(Study=STUDY,RunId=rid,RegistrationSha256=sha(REG),
        Reports=rows,Packets=journal.packets),checked_public(Path('new-recipient-output'),rid),rid)
    write(CAPTURE/'receipt.json',dict(Study=STUDY,RunId=rid,RegistrationSha256=sha(REG),sealed=sealed,Requests=len(journal.packets),Orders=0,CloudActivated=False))
    print('PERSISTENT_RESPONSE_CAPTURE_REQUESTS',len(journal.packets),flush=True)

def evaluate(work,captured):
    p,source,book,report,tape=original(work);REPORT.mkdir(exist_ok=True)
    old=native(source,book,report,tape,tape,REPORT/'original-witness-audit.json')
    extended=work/'extended-tape';shutil.copytree(tape,extended);count=0;proof=None
    if captured:
        receipt=read(CAPTURE/'receipt.json');rid=os.environ['GITHUB_RUN_ID']
        payload=eer.unpack(CAPTURE,receipt['sealed'],os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),rid)
        need(payload['Study']==STUDY and payload['RunId']==rid and payload['RegistrationSha256']==sha(REG)==receipt['RegistrationSha256'],'PERSISTENT_RESPONSE_CAPTURE_BINDING')
        packets=payload['Packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
        need(src.original_account(account),'PERSISTENT_RESPONSE_READBACK_ACCOUNT')
        j=src.ReadbackJournal(packets);rows=collect(j,account,p,readback.protection_tick_sink(extended,'eer1'))
        need(j.index==len(packets)==receipt['Requests'] and rows==payload['Reports'],'PERSISTENT_RESPONSE_EXACT_PACKET_PARITY')
        count=j.index;proof=dict(Capture=receipt,ReadbackReports=rows,PacketsReconciled=count)
        del payload,packets,j;gc.collect()
    result=native(source,book,report,tape,extended,REPORT/'response.json')
    write(REPORT/'summary.json',dict(Study=STUDY,Original=p['OriginalReport'],OriginalBooks=p['OriginalBooks'],
        RegistrationSha256=sha(REG),OriginalWitness=old,Response=result,CaptureProof=proof,SourceBrokerRequests=count,
        OriginalPoliciesReplayed=0,OriginalResultsModified=False,Orders=0,CloudActivated=False,
        WholePolicyEconomicQualification=False,ContinuousProtectionCertified=False,IndependentConfirmationCertified=False))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','prepare','capture','evaluate']);parser.add_argument('--work',type=Path);parser.add_argument('--captured',choices=['true','false'],default='false');a=parser.parse_args()
    if a.stage=='check':registered()
    elif a.stage=='prepare':prepare(a.work)
    elif a.stage=='capture':capture()
    else:evaluate(a.work,a.captured=='true')
if __name__=='__main__':main()
