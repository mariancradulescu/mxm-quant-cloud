"""Causal diagnostic on existing mature contextual labels, not policy replay.
Candidate context is observed at original admission. All outcome values are
used only for evaluation or strictly earlier training; no book/volume
optimization or annual/promotion claim.
"""
import argparse,collections,gzip,hashlib,json,math,os
from pathlib import Path
from statistics import mean
from . import owner_causal_source_shards as shards
from .custody import unseal_new
from .decode import need
from .owner_eur_recent_archive import download_archive
from .merge_eur_scenarios import exact_json

META=15156138456
RUN=45902596346
META_SHA='28e273a13c516835acb0879d6ce9833b177552d6e773f0a999df41d0bcd6a7fc'
SOURCE='4336a525ad897bee1a280e2baff07dcd399606e25f9536d4a202bc2676d73b15'
PROTOCOL='3660724036972b2c1017f131585499d997eee7c43a10543b003f12a05cc65c05'
DAY=86400000
START=1793577600000
EVALUATION=1794787200000
END=1795651200000
PATHS=[f'S{i}/checkpoints/{END}/CENTER_LOCAL-observer.json' for i in range(3)]
MODES=('CENTERED_TRANSFER','COST_CONTEXT','COST_RESIDUAL','MATCHED_COST_RESIDUAL')

def restore():
    root=Path('residual-cipher');shards.download_artifact(META,RUN,META_SHA,root)
    rep=json.loads((root/'repack-receipt.json').read_bytes())
    need(rep['FullCipherReconstructionVerified'] and rep['OriginalSourceArtifact']==15150477614 and
         rep['SourceSha256']==SOURCE and rep['ProtocolSha256']==PROTOCOL and
         rep['SourceRunId']=='45885931266' and rep['VerifiedParts']==227,'RESIDUAL_SHARD_BINDING')
    key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    sealed=(root/'manifest.sealed').read_bytes()
    need(hashlib.sha256(sealed).hexdigest()==rep['ManifestCipherSha256'],'RESIDUAL_MANIFEST_CIPHER')
    manifest=json.loads(gzip.decompress(unseal_new(sealed,key,rep['SourceRunId'])))
    public=json.loads((root/'checkpoint-receipt.json').read_bytes())
    need(public.pop('ManifestCipherSha256')==rep['ManifestCipherSha256'] and manifest==public and
         manifest['Complete'] and manifest['SourceSha256']==SOURCE and manifest['ProtocolSha256']==PROTOCOL and
         manifest['RunId']==rep['SourceRunId'],'RESIDUAL_MANIFEST_PARITY')
    files={f['Path']:f for f in manifest['Files']};need(set(PATHS)<=set(files),'RESIDUAL_OBSERVERS')
    wanted={part['File'] for path in PATHS for part in files[path]['Parts']}
    for group in rep['Shards']:
        selected=wanted&{part['File'] for part in group['Files']}
        if not selected:continue
        folder=root/f"data-{group['Index']}"
        shards.download_artifact(group['ArtifactId'],RUN,group['ArchiveSha256'],folder)
        need({p.name for p in folder.iterdir()}=={part['File'] for part in group['Files']},'RESIDUAL_SHARD_MEMBERS')
        for part in group['Files']:
            if part['File'] not in selected:continue
            path=folder/part['File'];need(shards.sha(path)==part['CipherSha256'],'RESIDUAL_PART_CIPHER')
            path.rename(root/path.name)
    need(all((root/name).is_file() for name in wanted),'RESIDUAL_SELECTED_CIPHERS')
    rows=[]
    for name in PATHS:
        f=files[name];target=root/(name.split('/')[0]+'.json');digest=hashlib.sha256();offset=0
        with target.open('xb') as out:
            for part in f['Parts']:
                cipher=(root/part['File']).read_bytes()
                need(hashlib.sha256(cipher).hexdigest()==part['CipherSha256'] and part['Offset']==offset,'RESIDUAL_PART_IDENTITY')
                raw=gzip.decompress(unseal_new(cipher,key,rep['SourceRunId']))
                need(len(raw)==part['Bytes'] and hashlib.sha256(raw).hexdigest()==part['PlainSha256'],'RESIDUAL_PART_PLAIN')
                out.write(raw);digest.update(raw);offset+=len(raw)
        need(offset==f['Bytes'] and digest.hexdigest()==f['Sha256'],'RESIDUAL_FILE_IDENTITY')
        data=json.loads(target.read_bytes())
        need(data['ObservedThrough']==END-285000 and all(x['AvailableAt']<=data['ObservedThrough'] for x in data['Labels']),
            'RESIDUAL_OBSERVER_CLOCK')
        rows.append(data['Labels']);target.unlink()
    return rows,len(wanted)

def regime(context,tf):
    # Native enum numbers in historical JSON; accept the matching string
    # representation only if explicit. No future labels or current outcomes.
    matches=[x['Direction'] for x in context['ClosedStates'] if str(x['Timeframe'])==str(tf)]
    need(len(matches)<=1,'RESIDUAL_REGIME_DUPLICATE')
    return matches[0] if matches else None

def cost_band(c):return 0 if c<=.1 else 1 if c<=.25 else 2 if c<=.5 else 3
def supported(rows):return len(rows)>=8 and len({r['ClosedAt']//DAY for r in rows})>=3
def lower(values):
    m=mean(values)
    return m-.75*math.sqrt(sum((x-m)**2 for x in values)/(len(values)*(len(values)-1)))

def estimate(history,target,mode,h1,m15):
    c=target['Context'];symbol=c['Symbol'];side=target['Side'];family=target['Family'];asset=c.get('AssetClass')
    r=regime(c,h1);fast=regime(c,m15);cost=c['CostRiskFraction']
    match=mode in ('COST_CONTEXT','MATCHED_COST_RESIDUAL')
    pool=[x for x in history if x['Family']==family and x['Side']==side]
    if match:pool=[x for x in pool if cost_band(x['Context']['CostRiskFraction'])==cost_band(cost)]
    local=[x for x in pool if x['Context']['Symbol']==symbol]
    selected=[x for x in local if regime(x['Context'],h1)==r]
    if match:
        near=[x for x in selected if regime(x['Context'],m15)==fast]
        if supported(near):selected=near
    if not supported(selected):
        selected=local
        if not supported(selected):
            selected=[x for x in pool if x['Context']['Symbol']!=symbol and asset and x['Context'].get('AssetClass')==asset
                and regime(x['Context'],h1)==r]
            if len({x['Context']['Symbol'] for x in selected})<2:return None
    if not supported(selected):return None
    days=collections.defaultdict(lambda:collections.defaultdict(list))
    residual=mode in ('COST_RESIDUAL','MATCHED_COST_RESIDUAL')
    for x in selected:
        net=x['NetEur']/x['RiskEur']
        if residual:net+=x['Context']['CostRiskFraction']
        days[x['ClosedAt']//DAY][x['Context']['Symbol']].append((x['GrossEur']/x['RiskEur'],net))
    def daily(j):return [mean(mean(v[j] for v in rows) for rows in groups.values()) for groups in days.values()]
    gross=lower(daily(0));net=lower(daily(1))
    # Current observed round-trip floor is always charged. Additional funding
    # ceilings are not present in public context; this diagnostic cannot admit trades.
    if residual:net-=cost
    return gross,min(net,gross-cost)

def diagnostic(rows,h1,m15):
    result=[]
    for mode in MODES:
        report=[dict(Count=0,GrossEur=0.,NetEur=0.) for _ in range(2)]
        clocks=[START,START+7*DAY,EVALUATION,EVALUATION+7*DAY,END]
        for lo,hi in zip(clocks,clocks[1:]):
            fit=[x for x in rows if x['AvailableAt']<lo and x['ClosedAt']<=x['AvailableAt']]
            cache={}
            for x in rows:
                if not lo<=x['DecisionAt']<hi:continue
                c=x['Context']
                # Cache only the normalized cohort statistics, but cost itself
                # affects repricing; keep it in the exact key for this diagnostic.
                k=(x['Family'],x['Side'],c['Symbol'],c.get('AssetClass'),regime(c,h1),regime(c,m15),c['CostRiskFraction'])
                if k not in cache:cache[k]=estimate(fit,x,mode,h1,m15)
                score=cache[k]
                if score is None or min(score)<=0:continue
                item=report[int(lo>=EVALUATION)];item['Count']+=1;item['GrossEur']+=x['GrossEur'];item['NetEur']+=x['NetEur']
        result.append(dict(Mode=mode,Selection=report[0],Later=report[1]))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','evaluate'));a=p.parse_args()
    if a.stage=='check':
        need(len(PATHS)==3 and cost_band(.25)==1 and cost_band(.5)==2,'RESIDUAL_SCOPE')
        return
    rows,parts=restore()
    original=Path('residual-public-original')
    download_archive(15149404567,45885931266,'b3490ed9f10e77dd80969d69f3e6492237cbacf9fcc47c4a112ae49a2cca0b02',original)
    result=[]
    for i,labels in enumerate(rows):
        old=json.loads((original/f'S{i}.json').read_bytes())
        public=next(x['Report']['Labels'] for x in old['ObserverReceipts'] if x['Id']=='CENTER_LOCAL')
        lookup={x['PositionId']:x for x in public}
        need(len(lookup)==len(labels) and len({x['PositionId'] for x in labels})==len(labels),'RESIDUAL_LABEL_COUNT')
        for x in labels:
            q=lookup[x['PositionId']]
            need(all(x[k]==q[k] for k in ('Family','Side','DecisionAt','ClosedAt','AvailableAt','GrossEur','NetEur','RiskEur')) and
                 x['Context']['Symbol']==q['Symbol'] and x['RiskEur']>0 and x['DecisionAt']<x['ClosedAt']<=x['AvailableAt'] and
                 x['Context']['CostRiskFraction']>=0,'RESIDUAL_LABEL_PARITY')
        # Enum names/values are pinned to the native timeframe declaration.
        result.append(dict(Stress=i*.5,Labels=len(labels),Results=diagnostic(labels,60,15)))
        print('RESIDUAL_DIAGNOSTIC_SCENARIO',i,flush=True)
    out=Path('residual-context-report');out.mkdir()
    (out/'diagnostic.json').write_text(exact_json(dict(Study='COST_RESIDUAL_CONTEXT_DIAGNOSTIC_1',SourceSha256=SOURCE,
        OriginalArtifact=15149404567,CheckpointMetadataArtifact=META,SelectedCipherParts=parts,
        Results=result,OriginalPoliciesReplayed=0,CommonBookEvaluations=0,Orders=0,CloudActivated=False,
        IndependentConfirmationCertified=False,Limitation='ISOLATED OVERLAPPING MATURED EPISODES; OBSERVED ADMISSION COST FLOOR ONLY; NO PORTFOLIO OR FUTURE CLAIM'))+'\n')
if __name__=='__main__':main()
