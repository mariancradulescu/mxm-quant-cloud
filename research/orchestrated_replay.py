"""Thin adapter: shared native selection -> existing chronological funded ledger.

No independent Python allocator, no outcome labels in the decision request.
Risk estimates, complete contracts and a peak upper certificate are required
from the source-bound caller. A sampled replay peak is never such a certificate.
"""
import json, os, subprocess, tempfile
from pathlib import Path
from decimal import Decimal
from .funded_replay import Decision, IncompleteEvidence


def allocate(replay, request, execution, native_dll, *, peak_upper_certificate=None):
    clock = request['Clock']
    if clock < replay.clock or replay.pending:
        raise IncompleteEvidence('UNRECONCILED_OR_NONCHRONOLOGICAL_ALLOCATION')
    # New entries must reserve the same marked equity and broker margin that
    # the common funded ledger will consume. Never trust caller account capital.
    equity = replay.equity(clock)
    margin = sum((p.margin for p in replay.open.values()), Decimal('0'))
    if peak_upper_certificate is not None and peak_upper_certificate < replay.peak:
        raise IncompleteEvidence('PEAK_CERTIFICATE_CONTRADICTS_OBSERVED_EQUITY')
    if any(Decimal(str(s['MarginEur'])) < margin for s in request['Baseline']):
        raise IncompleteEvidence('OPEN_PORTFOLIO_OMITTED_FROM_JOINT_STATES')
    account = dict(request['Account'])
    account['EquityEur'] = str(equity)
    account['FreeMarginEur'] = str(max(Decimal('0'), equity-margin))
    account['CertifiedPeakEur'] = str(peak_upper_certificate or 0)
    account['Reconciled'] = bool(account['Reconciled'] and peak_upper_certificate is not None)
    payload = dict(request, Account=account)
    # Decimal JSON fields use strings with explicit C# AllowReadingFromString.
    with tempfile.TemporaryDirectory(prefix='mxm-joint-decision-') as tmp:
        inp, out = Path(tmp)/'decision.json', Path(tmp)/'allocation.json'
        inp.write_text(json.dumps(payload,default=str)); inp.chmod(0o600)
        env={k:v for k,v in os.environ.items() if not k.startswith(('R3_','CTRADER_','MXM_V4_'))}
        subprocess.run(['dotnet',str(native_dll),str(inp),str(out),'--orchestrate-opportunities'],
                       check=True,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        result=json.loads(out.read_text())
    by_id={o['Id']:o for o in request['Opportunities']}
    # Validate all selected execution metadata before mutating the ledger.
    decisions=[]
    for allocation in result['Allocations']:
        pid=allocation['Id']; o=by_id[pid]; terms=execution[pid]
        units=Decimal(str(allocation['Units']))
        if units != int(units):
            raise IncompleteEvidence('BROKER_VOLUME_ENCODING_NOT_INTEGER_UNITS')
        contract=terms['contract']; contract.check()
        if not isinstance(terms['latency_ms'], int) or terms['latency_ms'] <= 0:
            raise IncompleteEvidence('INVALID_EXECUTION_LATENCY')
        if (Decimal(str(o['VolumeGrid']['MarginPerUnitEur'])) != contract.margin_eur_per_unit or
                not contract.accepts(int(units)) or pid in replay.used_ids):
            raise IncompleteEvidence('NATIVE_ALLOCATION_BROKER_CONTRACT_MISMATCH')
        decisions.append(Decision(clock,o['AvailableAt'],o['CalibratedThrough'],pid,o['Symbol'],
            'OPEN',terms['latency_ms'],o['Direction'],int(units),contract,
            terms.get('stop'),terms.get('target')))
    for d in decisions:
        replay.decide(d)
    return result
