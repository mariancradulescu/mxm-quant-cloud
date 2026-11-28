"""Restore actual conserved tick packets into a protective tape, never valuation proxies."""
import gc,os
from pathlib import Path
from . import owner_held_equity_recovery as original
from . import owner_eer1_source as eer
from . import owner_eer1_readback as readback
from . import source_history_universe as src
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_eur_archive_funding_2 import plan_ids
from .merge_eur_scenarios import read,exact_json
from .decode import need

def specs():
    receipt=read(Path('research/held_source_recovery_receipt_20261127.json'))
    rows=[dict(Run=receipt['OriginalCaptureRun'],Artifact=receipt['OriginalCaptureArtifact'],Sha256=receipt['OriginalCaptureArchiveSha256'],
        Requests=receipt['OriginalReconciledPackets'],Original=True)]
    rows += [dict(Run=int(x['RunId']),Artifact=x['Artifact'],Sha256=x['ArchiveSha256'],Requests=x['Requests'],Original=False)
        for x in receipt['SupplementalProtectedArchives']]
    residual=read(Path('research/held_residual_source_receipt_20261127.json'))
    rows += [dict(Run=x['Run'],Artifact=x['ProtectedArtifact'],Sha256=x['ProtectedArchiveSha256'],Requests=x['PacketVerification']['PacketsReconciled'],Original=False)
        for x in residual['Scopes']]
    return rows

def restore(work,tape):
    work.mkdir(mode=0o700);key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    sink=readback.protection_tick_sink(tape,'eer1');proof=[]
    for i,spec in enumerate(specs()):
        folder=work/str(i);verified_download(spec['Artifact'],spec['Run'],spec['Sha256'],folder)
        receipt=read(folder/'receipt.json');payload=eer.unpack(folder,receipt['sealed'],key,str(spec['Run']))
        targets=payload['Groups'] if spec['Original'] else payload['Targets'];packets=payload['Packets']
        need(payload['RunId']==str(spec['Run']) and len(packets)==receipt['Requests']==spec['Requests'] and
            receipt['Orders']==0 and not receipt['CloudActivated'],'HELD_RAW_CAPTURE_BINDING')
        if spec['Original']:need(payload['PlanSha256']==receipt['PlanSha256'],'HELD_RAW_ORIGINAL_GROUP_BINDING')
        ids=plan_ids(dict(Targets=[dict(Symbol=g['Symbol']) for g in targets]));names={sid:n for n,sid in ids.items()}
        account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
        need(src.original_account(account),'HELD_RAW_ORIGINAL_ACCOUNT')
        j=src.ReadbackJournal(packets);actual_window=original.roll.tick_window;counts=dict(RawTicks=0,CompleteIntervals=0)
        def witnessed(query,account_id,sid,side,lo,hi,budget):
            ticks,leaves=actual_window(query,account_id,sid,side,lo,hi,budget)
            complete=[(a,b) for a,b,status,_,_ in leaves if status in ('VERIFIED_COMPLETE_PAGE','PROVIDER_NO_QUOTES')]
            sink(names[sid],side,ticks,complete);counts['RawTicks']+=len(ticks);counts['CompleteIntervals']+=len(complete)
            return ticks,leaves
        original.roll.tick_window=witnessed;coverage=[]
        try:rows=original.collect(j,account,targets,coverage,page_budget=6000 if spec['Original'] else 4000)
        finally:original.roll.tick_window=actual_window
        need(j.index==len(packets) and rows==payload['Rows'] and
            (spec['Original'] or coverage==payload['Coverage']),'HELD_RAW_EXACT_REQUEST_ROW_AND_COVERAGE_PARITY')
        proof.append(dict(Archive=spec,PacketsReconciled=j.index,PrefixRowsVerified=len(rows),**counts,
            RawOfficialTickResponsesRestored=True,ValuationRegistryPromotedToExecution=False,Orders=0,CloudActivated=False))
        del payload,packets,rows,j;gc.collect()
        print('HELD_RAW_EXECUTION_SOURCE_RESTORED',i+1,len(proof),spec['Requests'],counts['RawTicks'],flush=True)
    return dict(Archives=proof,PacketsReconciled=sum(x['PacketsReconciled'] for x in proof),
        RawOfficialTickResponsesRestored=True,ValuationRegistryPromotedToExecution=False,SourceBrokerRequests=0,Orders=0,CloudActivated=False)
