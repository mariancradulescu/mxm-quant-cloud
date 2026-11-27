"""Offline gap attribution on immutable reports, not a broker-request plan."""
import argparse,hashlib,json,zipfile
from collections import Counter,defaultdict
from pathlib import Path
SOURCES={
 'earlier':(15176413393,'12553a26e1b2ae9b587baa7443fac7c2e5cf71082965a73092fed50a2848348c'),
 'recent':(15175739827,'1a68b4f0de7a2accb20cecfd7b776b3d8fa6d2e1c8be18939de85fec691a7839')}
STEP=300000

def intervals(clocks):
    out=[]
    for t in sorted(set(clocks)):
        if out and t==out[-1][1]+STEP:out[-1][1]=t
        else:out.append([t,t])
    return out

def analyze(path,scope):
    with open(path,'rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=SOURCES[scope][1]:raise ValueError('ARCHIVE_SHA')
    union=defaultdict(set);raw=0;unknown=unattributed=parity=0;reason_hits=Counter();sole=Counter()
    with zipfile.ZipFile(path) as z:
        def read(n):return json.loads(z.read(n))
        receipt=read('summary.json')
        if receipt['Scope']!=scope or receipt['Orders']!=0 or receipt['CloudActivated']:raise ValueError('SCOPE')
        for i in range(3):
            result=read(f'S{i}-result.json');gaps=defaultdict(set)
            if result['SourceSha256']!=receipt['SourceSha256'] or result['ProtocolSha256']!=receipt['ProtocolSha256']:
                raise ValueError('SOURCE_BINDING')
            for g in read(f'S{i}-holding-valuation-gaps.json'):
                raw+=len(g['Clocks']);union[g['Symbol'],g['Reason']].update(g['Clocks'])
                for t in g['Clocks']:gaps[g['Symbol'],t].add(g['Reason'])
            for b in result['CommonBooks']:
                d=b['Details'];closed={e['PositionId']:e['CloseAt'] for e in d['Episodes']};events=[]
                for a in d['Admissions']:
                    if a['FillAt'] is None:continue
                    k,s=a['PositionId'],a['Symbol'];events.append((a['FillAt'],1,k,s))
                    if k in closed:events.append((closed[k],-1,k,s))
                events.sort();j=0;active={};count=0
                for q in d['EquityPath']:
                    t=q['At']
                    while j<len(events) and events[j][0]<=t:
                        _,act,k,s=events[j];j+=1
                        if act>0:active[k]=s
                        else:active.pop(k,None)
                    if q['EquityEur'] is not None:continue
                    count+=1;unknown+=1
                    if len(active)!=q['Held']:parity+=1;continue
                    found={(s,r) for s in set(active.values()) for r in gaps[s,t]}
                    if not found:unattributed+=1
                    for s,r in found:
                        reason_hits[r]+=1
                        if len(active)==1:sole[s,r]+=1
                if count!=b['Result']['UnknownEquityClocks']:raise ValueError('UNKNOWN_CLOCK_PARITY')
    groups=[dict(Symbol=s,Reason=r,UniqueClocks=len(v),Intervals=intervals(v)) for (s,r),v in sorted(union.items())]
    return dict(Scope=scope,ArchiveSha256=digest,RawDiagnostics=raw,UniqueDiagnostics=sum(len(v) for v in union.values()),
        DiagnosticIntervals=sum(len(g['Intervals']) for g in groups),UnknownBookClocks=unknown,
        UnattributedBookClocks=unattributed,HeldCountMismatch=parity,ReasonHits=dict(reason_hits),
        SoleHoldingHits=[dict(Symbol=s,Reason=r,Count=n) for (s,r),n in sorted(sole.items())],
        Groups=groups,DiagnosticOnly=True,RequestPlanAuthorized=False,SourceBrokerRequests=0,
        OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('scope',choices=tuple(SOURCES));p.add_argument('archive',type=Path)
    p.add_argument('output',type=Path);a=p.parse_args()
    result=analyze(a.archive,a.scope)
    with a.output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
if __name__=='__main__':main()
