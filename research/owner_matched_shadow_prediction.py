"""Matched matured-shadow comparisons. Conditional retrospective sample, not a trading policy."""
import argparse,collections,hashlib,json,statistics,zipfile
from pathlib import Path
D=86400000
INPUTS={'earlier':(15178354067,'641978ac7512089a850a4d3de86caeeefa8bbc7ed9d988d51628883022fd278f'),
        'recent':(15179335228,'d5a00b37256e12bf363138d84394a6a06e83a9f9a0fbcd4d3550bacc216c46e0')}
METHODS=('GLOBAL','LOCAL','SESSION','PAIRED_RELATIVE')

def assess(labels,start,end):
    labels=[x for x in labels if x['RiskEur']>0 and x['DecisionAt']<x['AvailableAt'] and x['ClosedAt']<=x['AvailableAt']]
    by=collections.defaultdict(list)
    for x in labels:by[x['Symbol'],x['DecisionAt']].append(x)
    ordered=sorted(labels,key=lambda x:x['AvailableAt']);j=0
    hist=collections.defaultdict(lambda:[0,0.,0.]);pairs=collections.defaultdict(lambda:[0,0.]);queue=[]
    for (symbol,t),g in by.items():
        if len(g)<2:continue
        values=[x['NetEur']/x['RiskEur'] for x in g];mu=statistics.mean(values)
        for x,n in zip(g,values):
            queue.append((max(y['AvailableAt'] for y in g),symbol,x['Family'],x['Side'],n-mu))
    queue.sort();k=0
    daily=collections.defaultdict(lambda:collections.defaultdict(list));counts=collections.Counter();shadow=[]
    def update(key,g,n):
        h=hist[key];h[0]+=1;h[1]+=g;h[2]+=n
    def score(x,method):
        f,s,sym=x['Family'],x['Side'],x['Symbol']
        glob=hist['F',f,s];local=hist['L',sym,f,s];session=hist['T',sym,f,s,(x['DecisionAt']%D)//(6*3600000)]
        if glob[0]<20:return None
        mean=glob[2]/glob[0]
        if method=='GLOBAL':return mean
        loc=(local[2]+20*mean)/(local[0]+20)
        if method=='LOCAL':return loc
        if method=='SESSION':return (session[2]+20*loc)/(session[0]+20)
        a=pairs['F',f,s];b=pairs['L',sym,f,s];prior=a[1]/a[0] if a[0]>=20 else 0
        return (b[1]+20*prior)/(b[0]+20)
    for (sym,t),g in sorted(by.items(),key=lambda x:(x[0][1],x[0][0])):
        while j<len(ordered) and ordered[j]['AvailableAt']<t:
            x=ordered[j];j+=1;f,s,sy=x['Family'],x['Side'],x['Symbol']
            a=x['GrossEur']/x['RiskEur'];n=x['NetEur']/x['RiskEur']
            update(('F',f,s),a,n);update(('L',sy,f,s),a,n)
            update(('T',sy,f,s,(x['DecisionAt']%D)//(6*3600000)),a,n)
        while k<len(queue) and queue[k][0]<t:
            _,sy,f,s,n=queue[k];k+=1
            for key in [('F',f,s),('L',sy,f,s)]:
                h=pairs[key];h[0]+=1;h[1]+=n
        if not start<=t<end:continue
        shadow.extend(g)
        if len(g)<2:continue
        scores={m:[score(x,m) for x in g] for m in METHODS}
        if any(s is None for v in scores.values() for s in v):continue
        net=[x['NetEur']/x['RiskEur'] for x in g]
        gross=[x['GrossEur']/x['RiskEur'] for x in g];base=statistics.mean(net)
        counts['MatchedGroups']+=1;counts['Candidates']+=len(g)
        counts['BothDirections']+=len({x['Side'] for x in g})==2
        for m,v in scores.items():
            best=max(range(len(g)),key=lambda i:(v[i],g[i]['Family'],g[i]['Side']))
            daily[m][t//D,sym].append((net[best]-base,net[best],gross[best],statistics.mean(gross)))
    rows={}
    for m,values in daily.items():
        days=collections.defaultdict(list)
        for (day,sym),v in values.items():days[day].append(tuple(statistics.mean(y) for y in zip(*v)))
        a=[tuple(statistics.mean(y) for y in zip(*v)) for v in days.values()];delta=[x[0] for x in a]
        rows[m]=dict(Days=len(a),MeanDailyNetRImprovement=statistics.mean(delta),
            MeanDailyChosenNetR=statistics.mean(x[1] for x in a),
            MeanDailyChosenGrossR=statistics.mean(x[2] for x in a),
            MeanDailyBaselineGrossR=statistics.mean(x[3] for x in a),
            PositiveImprovementDays=sum(x>0 for x in delta))
    return dict(**counts,ShadowEpisodes=len(shadow),ShadowGrossEur=sum(x['GrossEur'] for x in shadow),
        ShadowNetEur=sum(x['NetEur'] for x in shadow),Methods=rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--earlier',type=Path,required=True)
    p.add_argument('--recent',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=[]
    for scope,(aid,sha) in INPUTS.items():
        path=getattr(a,scope)
        with path.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=sha:raise ValueError('PREDICTIVE_ARCHIVE_SHA')
        with zipfile.ZipFile(path) as z:
            plan=json.loads(z.read('registered-plan.json'));summary=json.loads(z.read('summary.json'))
            if summary['Scope']!=scope or summary['Study']!='MONETARY_CAUSAL_RECENCY_COMPETITION_1':
                raise ValueError('PREDICTIVE_SCOPE')
            for stress in range(3):
                r=json.loads(z.read(f'S{stress}-result.json'))
                if r['SourceSha256']!=summary['SourceSha256'] or r['ProtocolSha256']!=summary['ProtocolSha256']:
                    raise ValueError('PREDICTIVE_SOURCE')
                for o in r['ObserverReceipts']:
                    result=assess(o['Report']['Labels'],plan['EvaluationFrom'],plan['End'])
                    out.append(dict(Scope=scope,Stress=stress,Id=o['Id'],**result))
    aggregates={m:dict(PositiveImprovement=sum(x['Methods'][m]['MeanDailyNetRImprovement']>0 for x in out),
        PositiveNet=sum(x['Methods'][m]['MeanDailyChosenNetR']>0 for x in out),
        MeanChosenNetR=statistics.mean(x['Methods'][m]['MeanDailyChosenNetR'] for x in out)) for m in METHODS}
    if len(out)!=24 or sum(x['MatchedGroups'] for x in out)!=26948 or sum(x['ShadowEpisodes'] for x in out)!=89476 or any(x['PositiveNet'] for x in aggregates.values()):
        raise ValueError('PREDICTIVE_AUDIT_REPRODUCTION')
    a.out.write_text(json.dumps(dict(Study='OWNER_MATCHED_SHADOW_PREDICTION_AUDIT_1',Contexts=out,Aggregates=aggregates,
        RetrospectiveMaturedSampleOnly=True,UnobservedCandidatesExcluded=True,IndependentSamples=False,
        PortfolioEvaluated=False,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False),indent=2)+'\n')
    print(aggregates,flush=True)
if __name__=='__main__':main()
