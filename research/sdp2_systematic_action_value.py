"""SDP2 original systematic action-value development; no closed evaluators."""
from __future__ import annotations
from collections import Counter, defaultdict
from bisect import bisect_right
from pathlib import Path
from hashlib import sha256
from statistics import NormalDist
import json, math, os, subprocess, tempfile
import numpy as np
from sklearn.tree import DecisionTreeRegressor

M5=300000; H=3600000; DAY=24*H; WEEK=7*DAY
START=1762128000000; END=START+52*WEEK; FIRST=START+26*WEEK
PROTOCOL=Path('research/SDP2_SYSTEMATIC_ACTION_VALUE_PROTOCOL_20261117.md')
VARIANTS={'FULL':list(range(42)), 'NO_PEERS':list(range(39)),
 'NO_ACTIVITY':[i for i in range(42) if i%12 not in (8,9,10) or i>=36],
 'OWN_PRICE':[12+i for i in (0,3,4,5,6,7)]+[36,37,38]}
TARGETS=['CENTRAL_LONG','CENTRAL_SHORT','ADVERSE_LONG','ADVERSE_SHORT']
FEATURES=[f'{tf}_{f}' for tf in ('M15','H1','H4') for f in
 ('BODY','UPPER_WICK','LOWER_WICK','POSITION','RETURN1','RETURN4','RETURN8',
  'EFFICIENCY','LOG_RMS','RANGE_RATIO','LOG_ACTIVITY','GAP_FRACTION')]+[
 'HOUR_SIN','HOUR_COS','HORIZON','PEER_H1_MEAN','PEER_H1_SD','PEER_COVERAGE']

def need(x,why):
    if not x: raise ValueError('SDP2_'+why)
def digest(x):return sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def aggregate(rows,minutes):
    span=minutes*60000; groups=defaultdict(list); out=[]
    for r in rows:groups[((r[1]-1)//span+1)*span].append(r)
    for t,v in sorted(groups.items()):
        v=sorted(v)
        if len(v)!=span//M5 or v[0][0]!=t-span or v[-1][1]!=t or any(a[1]!=b[0] for a,b in zip(v,v[1:])):continue
        out.append([t-span,t,v[0][2],max(x[3] for x in v),min(x[4] for x in v),v[-1][5],sum(x[6] for x in v)])
    return out

def scale_features(w,span):
    if len(w)!=8:return None
    p=np.asarray(w,float);ranges=p[:,3]-p[:,4]
    if np.any(ranges<=0) or np.any(p[:,2:6]<=0) or np.any(p[:,6]<=0):return None
    r=np.log(p[:,5]/p[:,2]);sig=max(.0001,float(np.sqrt(np.mean(r*r))))
    last=p[-1];body=(last[5]-last[2])/ranges[-1]
    features=[body,(last[3]-max(last[2],last[5]))/ranges[-1],
      (min(last[2],last[5])-last[4])/ranges[-1],(last[5]-last[4])/ranges[-1],
      math.log(last[5]/last[2])/sig,math.log(last[5]/p[-4,2])/(sig*2),
      math.log(last[5]/p[0,2])/(sig*math.sqrt(8)),
      abs(last[5]-p[0,2])/max(1e-12,float(np.sum(np.abs(p[:,5]-p[:,2])))),
      math.log(sig),ranges[-1]/float(np.mean(ranges[:-1])),
      math.log(last[6]/float(np.mean(p[:-1,6]))),
      float(np.mean(p[1:,0]!=p[:-1,1]))]
    return features,sig

def panel(bars):
    names=sorted(bars); views={}; prices={}; rows=[]; census=Counter()
    for s,rr in bars.items():
        prices[s]={r[1]:r[5] for r in rr}
        views[s]=[(v,[x[1] for x in v],tf*60000) for tf in (15,60,240) for v in [aggregate(rr,tf)]]
    for t in range(START,END,H):
        if (t//DAY+3)%7>=5:continue
        own={}
        for s in names:
            census[(int((t-START)//WEEK),s,'scheduled')]+=2
            feats=[];sigma=None
            for v,ends,span in views[s]:
                i=bisect_right(ends,t);w=v[max(0,i-8):i]
                if len(w)!=8 or t-w[-1][1]>span or w[0][0]<t-7*DAY:break
                f=scale_features(w,span)
                if f is None:break
                feats.extend(f[0])
                if span==H:sigma=f[1]
            if len(feats)==36 and t in prices[s]:own[s]=(feats,sigma)
        for s,(f,sigma) in sorted(own.items()):
            peer=[v[0][16] for k,v in own.items() if k!=s]
            context=[float(np.mean(peer)) if peer else 0.,float(np.std(peer)) if peer else 0.,len(peer)/max(1,len(names)-1)]
            for h in (1,4):
                hour=(t%DAY)/H
                x=f+[math.sin(2*math.pi*hour/24),math.cos(2*math.pi*hour/24),h/4]+context
                rows.append(dict(t=t,s=s,h=h,x=x,sigma=sigma,scaleReturn=max(.0001,sigma*math.sqrt(h)),due=t+M5+h*H))
                census[((t-START)//WEEK,s,'featureKnown')]+=1
    return rows,prices,[dict(week=k[0]+1,symbol=k[1],state=k[2],count=v) for k,v in sorted(census.items())]

def conversion(s,t,prices,terms):
    ccy=terms[s]['quoteAsset']
    def p(n):return prices.get(n,{}).get(t)
    eu=p('EURUSD')
    if ccy=='EUR':return 1.
    if not eu:return None
    if ccy=='USD':return 1/eu
    if ccy in ('JPY','CAD'):
        v=p('USD'+ccy);return 1/(eu*v) if v else None
    if ccy in ('GBP','AUD'):
        v=p(ccy+'USD');return v/eu if v else None
    return None

def crossings(start,end,minute):
    return max(0,(end-int(minute)*60000)//DAY-(start-int(minute)*60000)//DAY)

def payoff(row,prices,costs,terms):
    s=row['s'];t=row['t'];a=t+M5;z=row['due'];c=costs.get(s)
    if c is None:return None
    ps=prices[s]
    # Check outcomes only after features have been generated; no forward filtering.
    if any(k not in ps for k in range(a,z+1,M5)):return None
    ea=conversion(s,a,prices,terms);ez=conversion(s,z,prices,terms)
    et=conversion(s,t,prices,terms)
    if ea is None or ez is None or et is None:return None
    n=terms[s]['units'];notional=ps[t]*n*et
    scale=notional*row['scaleReturn'];y=[]
    k=crossings(a,z,c['swapMinute'])
    if k and not c['fundingKnown']:return None
    for scenario in ('central','adverse'):
        # All friction charged as explicit modeled per-side fees, zero model spread.
        # Native quote builder below uses the same decomposition: observed-spread
        # component in model ask; remaining roundtrip friction as fees.
        spread=c['observedSpreadP90Bps'] if scenario=='adverse' else c['spreadMeanBps']
        friction=c[scenario+'Bps'];feeRate=max(0,friction-spread)/20000
        for side in (1,-1):
            ep=ps[a]*(1+spread/10000) if side>0 else ps[a]
            xp=ps[z] if side>0 else ps[z]*(1+spread/10000)
            gross=side*n*(xp-ep)*ez
            charge=n*(ps[a]*ea+ps[z]*ez)*feeRate
            swap=c['longDailyDebitBps'] if side>0 else c['shortDailyDebitBps']
            funding=0.
            for stamp in range(a+M5,z+1,M5):
                if crossings(stamp-M5,stamp,c['swapMinute']):
                    fx=conversion(s,stamp,prices,terms)
                    if fx is None:return None
                    funding+=3*swap*n*ps[stamp]*fx/10000
            y.append((gross-charge-funding)/scale)
    return np.asarray(y),scale

class Boost:
    def fit(self,X,Y,weights):
        self.cuts=np.quantile(X,[.25,.5,.75],axis=0).T
        Z=self.encode(X);self.initial=np.average(Y,axis=0,weights=weights)
        pred=np.tile(self.initial,(len(X),1));self.trees=[]
        for _ in range(16):
            residual=Y-pred
            tree=DecisionTreeRegressor(max_depth=2,min_samples_leaf=128,random_state=0)
            tree.fit(Z,residual,sample_weight=weights)
            leaf=tree.apply(Z)
            for node in np.unique(leaf):
                mask=leaf==node;w=weights[mask]
                tree.tree_.value[node,:,0]=np.sum(residual[mask]*w[:,None],axis=0)/(w.sum()+32)
            pred+=.1*tree.predict(Z);self.trees.append(tree)
        return self
    def encode(self,X):return np.sum(np.asarray(X)[:,:,None]>self.cuts[None,:,:],axis=2).astype(np.float32)
    def predict(self,X):
        Z=self.encode(X);p=np.tile(self.initial,(len(X),1))
        for tree in self.trees:p+=.1*tree.predict(Z)
        return p
    def export(self):
        return dict(cuts=self.cuts.tolist(),initial=self.initial.tolist(),trees=[dict(
            left=t.tree_.children_left.tolist(),right=t.tree_.children_right.tolist(),
            feature=t.tree_.feature.tolist(),threshold=t.tree_.threshold.tolist(),
            value=t.tree_.value[:,:,0].tolist()) for t in self.trees])

def fit_masks(rows,at):
    maturity=np.asarray([r['due'] for r in rows]);ts=np.asarray([r['t'] for r in rows])
    eligible=maturity<at-4*H
    return (maturity<at-4*WEEK-4*H),eligible&(ts>=at-4*WEEK)

def evaluate(rows,prices,costs,terms):
    X=np.asarray([r['x'] for r in rows]);labels=[payoff(r,prices,costs,terms) for r in rows]
    known=np.asarray([v is not None for v in labels]);Y=np.asarray([v[0] if v is not None else [0]*4 for v in labels])
    scales=np.asarray([v[1] if v is not None else 0 for v in labels]);ts=np.asarray([r['t'] for r in rows])
    syms=np.asarray([r['s'] for r in rows]);hs=np.asarray([r['h'] for r in rows]);weeks=(ts-START)//WEEK
    metrics=[];models=[];offers=[];forecast_hash=sha256();examples=[];parity=[]
    for week in range(26,52):
        at=START+week*WEEK;train,cal=fit_masks(rows,at);train&=known;cal&=known
        test=(weeks==week);ids=np.flatnonzero(test)
        need(train.sum()>=512 and cal.sum()>=128 and len(ids)>0,'TRAINING_OR_CALIBRATION_SUPPORT')
        counts=Counter(syms[train]);weights=np.asarray([train.sum()/len(counts)/counts[s] for s in syms[train]])
        prior=np.average(Y[train],axis=0,weights=weights)
        for name,columns in list(VARIANTS.items())+[('PRIOR',[])]:
            if columns:
                fit=Boost().fit(X[train][:,columns],Y[train],weights)
                predictions=fit.predict(X[test][:,columns]);calpred=fit.predict(X[cal][:,columns])
                exported=fit.export();exported.update(week=week+1,variant=name,columns=columns)
                models.append(exported)
                parity.append(dict(model=exported,x=X[ids[0]].tolist(),expected=predictions[0].tolist()))
            else:
                predictions=np.tile(prior,(test.sum(),1));calpred=np.tile(prior,(cal.sum(),1))
            residuals=Y[cal]-calpred
            for h in (1,4):
                cm=hs[cal]==h;res=residuals[cm];cy=Y[cal][cm]
                need(len(res)>=64,'CALIBRATION_HORIZON_SUPPORT')
                quant=np.quantile(res,(np.arange(16)+.5)/16,axis=0)
                calweeks=weeks[cal][cm];weekly=[res[calweeks==w].mean(axis=0).tolist() for w in sorted(set(calweeks))]
                maxLoss=np.maximum(0,-cy.min(axis=0))*3
                local=np.flatnonzero(hs[test]==h);idx=ids[local];pred=predictions[local]
                valid=known[idx];iy=Y[idx][valid];ip=pred[valid];sc=scales[idx][valid]
                probability=np.mean(quant[None,:,:]+ip[:,None,:]>0,axis=1)
                record=dict(week=week+1,variant=name,horizonHours=h,featureKnown=len(idx),labelKnown=int(valid.sum()),
                    futureUnknown=int((~valid).sum()),training=int(train.sum()),calibration=len(res),
                    residualWeeklyMeans=weekly,calibratedThrough=int(max(r['due'] for r,m in zip(rows,cal) if m)),
                    normalizedMse=np.mean((ip-iy)**2,axis=0).tolist(),
                    eurMae=np.mean(np.abs(ip-iy)*sc[:,None],axis=0).tolist(),
                    brier=np.mean((probability-(iy>0))**2,axis=0).tolist(),
                    positivePayoffRate=np.mean(iy>0,axis=0).tolist(),
                    unconditionalActionEur=np.sum(iy*sc[:,None],axis=0).tolist())
                # Chosen action is determined before checking its label availability.
                choice=np.argmax(np.column_stack((np.zeros(len(pred)),pred[:,2:])),axis=1)
                chosen=choice[valid];pay=np.where(chosen==0,0,iy[np.arange(len(iy)),np.maximum(0,chosen-1)+2]*sc)
                record.update(chosenCounterfactualNetEur=float(pay.sum()),chosenNonCash=int((choice>0).sum()),chosenFutureUnknown=int(((choice>0)&~valid).sum()))
                zero=[]
                for i in idx[valid]:
                    r=rows[i];c=costs[r['s']]
                    cycles=crossings(r['t']+M5,r['due'],c['swapMinute'])
                    zero.append([-(c[scenario+'Bps']+3*cycles*c[side+'DailyDebitBps'])/10000/r['scaleReturn']
                        for scenario in ('central','adverse') for side in ('long','short')])
                record['knownCostZeroMoveNormalizedMse']=np.mean((np.asarray(zero)-iy)**2,axis=0).tolist()
                record['knownCostZeroMoveEurMae']=np.mean(np.abs(np.asarray(zero)-iy)*sc[:,None],axis=0).tolist()
                record['meanForecastPositiveProbability']=np.mean(probability,axis=0).tolist()
                record['probabilityCalibrationBins']=[[
                    dict(lower=k/5,upper=(k+1)/5,count=int(((probability[:,a]>=k/5)&((probability[:,a]<(k+1)/5) if k<4 else (probability[:,a]<=1))).sum()),
                      observedPositiveRate=float(np.mean((iy[:,a]>0)[(probability[:,a]>=k/5)&((probability[:,a]<(k+1)/5) if k<4 else (probability[:,a]<=1))])) if np.any((probability[:,a]>=k/5)&((probability[:,a]<(k+1)/5) if k<4 else (probability[:,a]<=1))) else None)
                    for k in range(5)] for a in range(4)]
                metrics.append(record)
                for j,i in enumerate(idx):
                    r=rows[i];c=costs.get(r['s']);fx=conversion(r['s'],r['t'],prices,terms)
                    fh=dict(t=r['t'],s=r['s'],h=h,variant=name,pred=pred[j].tolist())
                    forecast_hash.update(json.dumps(fh,sort_keys=True).encode())
                    if len(examples)<20:examples.append(fh)
                    if c is None or fx is None:continue
                    scale=prices[r['s']][r['t']]*terms[r['s']]['units']*fx*r['scaleReturn']
                    offers.append(dict(At=r['t']+1,Symbol=r['s'],HorizonHours=h,Variant=name,
                        CalibratedThrough=record['calibratedThrough'],Means=(pred[j]*scale).tolist(),
                        Scenarios=((quant+pred[j])*scale).T.tolist(),
                        Risk=(maxLoss*scale+2*c['adverseBps']*prices[r['s']][r['t']]*terms[r['s']]['units']*fx/10000).tolist()))
        print('SDP2_WEEK_COMPLETED',week+1,flush=True)
    paired=[];z=NormalDist().inv_cdf(1-.05/(2*8))
    for h in (1,4):
        for comparator in ('NO_PEERS','NO_ACTIVITY','OWN_PRICE','PRIOR'):
            a=[m for m in metrics if m['variant']=='FULL' and m['horizonHours']==h]
            b=[m for m in metrics if m['variant']==comparator and m['horizonHours']==h]
            benefit=[float(np.mean(np.asarray(y['normalizedMse'])[2:]-np.asarray(x['normalizedMse'])[2:])) for x,y in zip(a,b)]
            paired.append(dict(horizonHours=h,comparator=comparator,weeklyMseBenefit=benefit,
              first13Mean=float(np.mean(benefit[:13])),last13Mean=float(np.mean(benefit[13:])),
              mean=float(np.mean(benefit)),bonferroniLower=float(np.mean(benefit)-z*np.std(benefit,ddof=1)/math.sqrt(26)),
              limitation='DESCRIPTIVE_WEEK_BLOCK_NORMAL_INTERVAL_SERIAL_DEPENDENCE_NOT_INDEPENDENT_CONFIRMATION'))
    census=[]
    for week in range(52):
        for s in sorted(terms):
            for h in (1,4):
                mask=(weeks==week)&(syms==s)&(hs==h)
                census.append(dict(week=week+1,symbol=s,horizonHours=h,featureKnown=int(mask.sum()),labelKnown=int((mask&known).sum())))
    return dict(metrics=metrics,paired=paired,models=models,forecastsSha256=forecast_hash.hexdigest(),examples=examples,labelCensus=census),offers,parity

def native_input(bars,prices,costs,terms,offers,scenario):
    quotes=[]
    for s,ps in sorted(prices.items()):
        c=costs.get(s)
        if c is None:continue
        u=terms[s]['units'];spread=c['observedSpreadP90Bps'] if scenario=='adverse' else c['spreadMeanBps']
        for t,bid in sorted(ps.items()):
            if t<FIRST or t>END:continue
            fx=conversion(s,t,prices,terms)
            if fx is None:continue
            quotes.append(dict(Symbol=s,At=t,Bid=bid,Ask=bid*(1+spread/10000),EurCredit=fx,EurDebit=fx,
              ExitFeePerUnit=bid*fx*max(0,c[scenario+'Bps']-spread)/20000,ExitFeeFloor=0,
              MarginPerUnit=c['minimumMarginEur']/u))
    contracts=[dict(Symbol=s,MinimumUnits=v['units'],StepUnits=v['step'],
      SwapMinute=costs[s]['swapMinute'],FundingKnown=costs[s]['fundingKnown'],
      LongDailyDebitBps=costs[s]['longDailyDebitBps'],ShortDailyDebitBps=costs[s]['shortDailyDebitBps'])
      for s,v in sorted(terms.items()) if s in costs]
    return dict(Start=FIRST,End=END,Scenario=scenario,Quotes=quotes,Contracts=contracts,Offers=offers)

def main():
    from .multiscale_conditional_research import recover,extract_costs
    from .integrated_predictive_funded import cost_context
    p=json.loads(Path('research/spde1_protocol.json').read_text()) # source descriptors only
    bars={};terms={};costsamples=[];audits=[]
    for spec,folder in zip(p['source'],('bdp-source','aip-source')):
        b,decoded,audit=recover(Path(folder),spec['run'],spec['sha256'],spec['schema'],spec['protocol'])
        need(set(b['bars']).isdisjoint(bars),'SOURCE_SYMBOL_COLLISION');bars.update(b['bars']);audits.append(audit)
        for s,v in b['symbols'].items():
            if s in b['bars']:terms[s]=dict(quoteAsset=v['quoteAsset'],units=float(v['contract']['minVolume'])/100,step=float(v['contract']['stepVolume'])/100)
        samples,_=extract_costs(b,decoded);costsamples.extend(x for x in samples if int(x['At'])<FIRST)
    costs=cost_context(costsamples)
    for s,c in costs.items():c['spreadMeanBps']=float(np.mean([float(x['SpreadBps']) for x in costsamples if x['Symbol']==s]))
    rows,prices,census=panel(bars)
    report,offers,parity=evaluate(rows,prices,costs,terms)
    report.update(study='SDP2',sourceAudit=audits,protocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),sourceBars=sum(map(len,bars.values())),sourceCensus=census,universe=sorted(bars),independentConfirmation=False,qualified=False,orders=0,executionRunId=os.environ.get('GITHUB_RUN_ID'))
    Path('sdp2-original-predictive.json').write_text(json.dumps(report,sort_keys=True,allow_nan=False)+'\n')
    executable=os.environ.get('SDP2_DOTNET','dotnet');dll='src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll'
    with tempfile.TemporaryDirectory(prefix='sdp2-private-') as folder:
        a=Path(folder)/'in.json';z=Path(folder)/'out.json'
        a.write_text(json.dumps(parity,allow_nan=False));a.chmod(0o600)
        subprocess.run([executable,dll,str(a),str(z),'--sdp2-parity'],check=True)
        report['nativeModelParity']=json.loads(z.read_text())
        for scenario in ('central','adverse'):
            a.write_text(json.dumps(native_input(bars,prices,costs,terms,offers,scenario),allow_nan=False))
            from .custody import seal_new
            sealed=seal_new(a.read_bytes(),Path('research/custody_public.pem').read_bytes(),os.environ['GITHUB_RUN_ID'])
            Path('sdp2-native-input-'+scenario+'.enc').write_bytes(sealed)
            report['nativeInput'+scenario+'Sha256']=sha256(a.read_bytes()).hexdigest()
            report['nativeInput'+scenario+'CipherSha256']=sha256(sealed).hexdigest()
            subprocess.run([executable,dll,str(a),str(z),'--sdp2-native'],check=True,timeout=1800)
            report['native_'+scenario]=json.loads(z.read_text())
            Path('sdp2-original-native-'+scenario+'.json').write_text(z.read_text())
    report.update(study='SDP2',protocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),sourceAudit=audits,
      sourceBars=sum(map(len,bars.values())),universe=sorted(bars),featureColumns=FEATURES,sourceCensus=census,
      originalCostSamples=len(costsamples),costModel=costs,executionRunId=os.environ.get('GITHUB_RUN_ID'),
      independentConfirmation=False,qualified=False,orders=0,cloudActivated=False,
      economicDomain='CONDITIONAL_BAR_PRICE_CURRENT_TERM_COST_FX_PROXY_NOT_BROKER_EXECUTION',
      continuousFloatingDrawdownCertified=False,otherArchiveCoverageNotYetIntegrated=True,
      codeSha256=sha256(Path(__file__).read_bytes()).hexdigest(),nativeCodeSha256=sha256(Path('src/Mxm.Replay/Sdp2ActionValueResearch.cs').read_bytes()).hexdigest(),
      preregisteredA1Sha256=sha256(Path('research/SDP2_A1_PRESOURCE_KNOWN_COST_BENCHMARK_20261117.md').read_bytes()).hexdigest())
    Path('sdp2-original-public.json').write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print('SDP2_COMPLETE',json.dumps(dict(sourceBars=report['sourceBars'],forecastsSha256=report['forecastsSha256'],paired=report['paired'])),flush=True)

if __name__=='__main__':main()
