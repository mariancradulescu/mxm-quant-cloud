"""Authenticated existing ciphertext -> common native system research probe.
No broker access, closed-signal imports, parameter searches or holdout scoring.
"""
import hashlib, json, os, subprocess, tempfile
from pathlib import Path
from .custody import unseal_new
SOURCE_RUN = '41476636915'


def run():
    raw = Path('sealed-output/source.envelope.json').read_bytes()
    receipt = json.loads(Path('sealed-output/receipt.public.json').read_text())
    if (receipt.get('status') != 'NEW_ECONOMIC_SOURCE_V2_SEALED' or
            receipt.get('ciphertextSha256') != '50e40f62156f598d715d6052e466ae7ef77b9bc39117cad37472c7f0f505e61d' or
            hashlib.sha256(raw).hexdigest() != receipt.get('ciphertextSha256')):
        raise ValueError('JOINT_SOURCE_CUSTODY_HASH')
    source = json.loads(unseal_new(raw, os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(), SOURCE_RUN))
    original = source.pop('csharpReceipt')
    with tempfile.TemporaryDirectory(prefix='mxm-joint-private-') as tmp:
        inp, out = Path(tmp)/'source.json', Path(tmp)/'result.json'
        inp.write_text(json.dumps(source, sort_keys=True)); inp.chmod(0o600)
        env = {k:v for k,v in os.environ.items() if not k.startswith(('R3_', 'CTRADER_', 'MXM_V4_'))}
        def native(mode):
            subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(inp),str(out),mode],
                           check=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return json.loads(out.read_text())
        if native('--economic-source') != original:
            raise ValueError('JOINT_ORIGINAL_NATIVE_RECEIPT_PARITY')
        result = native('--joint-opportunity-research')
        if result != native('--joint-opportunity-research'):
            raise ValueError('JOINT_NONDETERMINISTIC_RESULT')
    if (result['ordersSubmitted'] or result['economicQualification'] or result['nativeSelectorAdmitted'] or
            result['netOpportunityEstimateEur'] is not None):
        raise ValueError('JOINT_MISSING_EXECUTION_EVIDENCE_NOT_ENFORCED')
    result['sourceCiphertextSha256'] = receipt['ciphertextSha256']
    result['originalNativeReceiptParity'] = True
    result['deterministicRepeatMatched'] = True
    result['sourceCalendar'] = [dict(symbol=s, timeframe=tf,
        startMs=min(x['openTime'] for x in source['bars'] if x['symbol']==s and x['resolution']==tf),
        endMs=max(x['availableTime'] for x in source['bars'] if x['symbol']==s and x['resolution']==tf),
        exposure='PRIOR_PROJECT_DEVELOPMENT_EXPOSED', independent=False)
        for s,tf in sorted({(x['symbol'],x['resolution']) for x in source['bars']})]
    Path('joint-opportunity.public.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('AUTHENTIC_JOINT_OPPORTUNITY_RESEARCH '+json.dumps(result,sort_keys=True),flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception:
        print('JOINT_RESEARCH_FAILED_CLOSED_DETAILS_WITHHELD',flush=True)
        raise SystemExit(1)
