"""Broad DEVELOPMENT on existing authentic encrypted source. No broker calls.
No closed strategy replay, no independent confirmation, no EUR200 NET claim.
"""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from .custody import unseal_new
SOURCE_RUN='41476636915'

def run():
    if os.environ.get('MXM_REGIME_SOURCE_RUN_ID')!=SOURCE_RUN:
        raise ValueError('REGIME_SOURCE_BINDING')
    data=Path('sealed-output/source.envelope.json').read_bytes()
    pub=json.loads(Path('sealed-output/receipt.public.json').read_text())
    if pub.get('status')!='NEW_ECONOMIC_SOURCE_V2_SEALED' or hashlib.sha256(data).hexdigest()!=pub.get('ciphertextSha256'):
        raise ValueError('REGIME_CUSTODY_HASH')
    source=json.loads(unseal_new(data,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),SOURCE_RUN))
    original=source.pop('csharpReceipt')
    with tempfile.TemporaryDirectory(prefix='mxm-regime-private-') as tmp:
        inp=Path(tmp)/'source.json';out=Path(tmp)/'result.json'
        inp.write_text(json.dumps(source,sort_keys=True));inp.chmod(0o600)
        env={k:v for k,v in os.environ.items() if not k.startswith(('R3_','CTRADER_','MXM_V4_'))}
        def native(mode):
            subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(inp),str(out),mode],
                check=True,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return json.loads(out.read_text())
        if native('--economic-source')!=original:raise ValueError('REGIME_ORIGINAL_CSHARP_PARITY')
        result=native('--regime-discovery')
    if result['ordersSubmitted']!=0 or result['brokerNetEur'] is not None or result['independentConfirmation']:
        raise ValueError('REGIME_UNAUTHORIZED_QUALIFICATION')
    result['originalSourceReceiptParity']=True
    result['sourceCiphertextSha256']=pub['ciphertextSha256']
    Path('regime-discovery.public.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    families={}
    candidates=[]
    for row in result['results']:
        key=row['family'];f=families.setdefault(key,{'trials':0,'positiveGross':0,'supportAt3Bps':0,'stableAt3Bps':0})
        f['trials']+=1
        zero=row['scenarios'][0];cost=row['scenarios'][2]
        f['positiveGross']+=int((zero['meanGrossBps'] or 0)>0)
        support=cost['approximateExploratorySupportOnly'];f['supportAt3Bps']+=int(support)
        stable=support and cost['positiveFolds']==3;f['stableAt3Bps']+=int(stable)
        if support:candidates.append(row)
    summary={'sourceRunId':int(SOURCE_RUN),'sourceCiphertextSha256':pub['ciphertextSha256'],
        'originalSourceReceiptParity':True,'trialCount':result['trialCount'],'families':families,
        'candidates':candidates,'brokerNetEur':None,'ordersSubmitted':0,
        'independentConfirmation':False,'costStatus':result['costStatus']}
    Path('regime-discovery-summary.public.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    print('AUTHENTIC_REGIME_DISCOVERY_SUMMARY '+json.dumps(summary,sort_keys=True),flush=True)

if __name__=='__main__':
    try:run()
    except Exception:
        print('REGIME_DISCOVERY_FAILED_DETAIL_WITHHELD');sys.exit(1)
