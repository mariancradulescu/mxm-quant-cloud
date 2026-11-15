"""MVE1 fixed multioutput ridge: joint continuous price/volatility/peer interactions.

Research-only numpy batch linear algebra, C#-replicable fixed parameters and
matrix coefficients; NO online Python service or production trading authority.
Closed WIDE_REGIME/IPF1/SPDE1 scorers are never called.
"""
from __future__ import annotations
from collections import Counter
from math import sqrt, erf
import numpy as np
from .mve1_event_interaction import (
    COLUMNS, INTERACTION_IDX, PEER_IDX, SIMPLE_IDX, M5
)

LAMBDA=32.0
MODEL_VARIANTS={
    "FULL_INTERACTIONS":tuple(range(len(COLUMNS))),
    "NO_PEER_COMPONENT":tuple(i for i in range(len(COLUMNS)) if i not in PEER_IDX),
    "NO_INTERACTION_TERMS":tuple(i for i in range(len(COLUMNS)) if i not in INTERACTION_IDX),
    "SIMPLE_OWN_PRICE":SIMPLE_IDX,
}
SCORERS=("FULL_INTERACTIONS","NO_PEER_COMPONENT",
         "NO_INTERACTION_TERMS","SIMPLE_OWN_PRICE")
MODELLING_TARGETS=("return","upExcursion","downExcursion","volExpansion01")
FIXED_Z=1.959963984540054


def normal_cdf(x):
    return .5*(1+erf(x/sqrt(2)))


def normalize_features(raw,avg,std):
    # Freeze train-only standardization + symmetric numerical winsorization.
    x=np.asarray(raw,dtype=float)
    z=(x-avg)/std
    z[0]=1.
    return np.clip(z,-5.,5.)


def training_scaler(events):
    a=np.asarray([x["features"] for x in events],dtype=np.float64)
    if a.shape[0]<100 or a.shape[1]!=len(COLUMNS):
        raise ValueError("MVE1_INSUFFICIENT_TRAIN_CAUSAL_EVENTS")
    avg=a.mean(axis=0)
    std=np.maximum(a.std(axis=0),.1)
    avg[0]=0.;std[0]=1.
    return avg,std


def fit_all_multitarget(rows, training_events, horizon):
    """Only already matured train period labels, one batch no grid search.

    Global per-instrument weights balance unequal market session densities.
    Four correlated targets use one common fixed 32-dimensional design.
    """
    eligible=[r for r in rows if r["phase"]=="training" and r["known"]]
    if len(eligible)<200:
        raise ValueError("MVE1_INSUFFICIENT_MATURE_TRAINING")
    counts=Counter(r["s"] for r in eligible)
    total=len(eligible);k=len(counts)
    avg,std=training_scaler(training_events)
    X=np.asarray([normalize_features(r["features"],avg,std) for r in eligible],
                 dtype=np.float64)
    y=np.asarray([r["target"] for r in eligible],dtype=np.float64)
    w=np.asarray([min(4.,total/(k*counts[r["s"]])) for r in eligible],dtype=float)
    w*=total/w.sum()
    # Same score against every candidate, not time-wise future-variable
    # selection. Weights depend only on train-instrument counts.
    designs={}
    for model_name,indices in MODEL_VARIANTS.items():
        x=X[:,indices]
        a=x.T@(w[:,None]*x)
        regularizer=np.eye(len(indices))*LAMBDA
        regularizer[0,0]=1e-8
        matrix=a+regularizer
        rhs=x.T@(w[:,None]*y)
        coeff=np.linalg.solve(matrix,rhs)
        residual=y-x@coeff
        resid_var=np.maximum(1e-4,np.average(residual*residual,axis=0,weights=w))
        # Conditional-mean inference variance. Predictive dispersion
        # (realized path noise) remains a distinct sigma in the receipt.
        inverse=np.linalg.inv(matrix)
        designs[model_name]={
            "indices":indices,"beta":coeff,"inverse":inverse,
            "residualVariance":resid_var,
            "trainingMeanSquaredError":(residual*residual).mean(axis=0),
        }
    return {"h":horizon,"avg":avg,"std":std,"variants":designs,
            "trainCount":len(eligible),
            "trainSymbolCount":dict(counts),
            "unconditionalDirectionUp":(np.count_nonzero(y[:,0]>0)+1)/(len(y)+2),
            "unconditionalVolExpansion":(np.count_nonzero(y[:,3]>0.5)+1)/(len(y)+2),
            "unconditionalTargets":y.mean(axis=0),
            "featureColumns":list(COLUMNS)}


def predict_all(row,fit):
    f=normalize_features(row["features"],fit["avg"],fit["std"])
    ans={}
    for name,m in fit["variants"].items():
        x=f[list(m["indices"])]
        estimate=x@m["beta"]
        se2=float(x@m["inverse"]@x)
        sigma=np.sqrt(m["residualVariance"])
        se=sigma*sqrt(max(0.,se2))
        p=normal_cdf(float(estimate[0]/max(1e-6,sigma[0])))
        ans[name]={
            "target":estimate,
            "meanSE":se,
            "pathResidualSD":sigma,
            "probUp":p,
            "volExpansionProb":float(np.clip(estimate[3],0.,1.)),
        }
    return ans


def current_term_friction_bps(row,side,current_cost,scenario):
    """Original-date current-term BID/ASK fees + conservative swap model.

    No historical event fill, historical swap or broker P&L is asserted.
    """
    if side==0:
        return 0.
    if (current_cost is None or not current_cost.get("fundingKnown",False)
            or not isinstance(current_cost.get("swapMinute"),int)):
        return None
    minute=current_cost["swapMinute"]
    if not 0<=minute<1440:
        return None
    opening=row["entryClock"]
    ending=opening+row["h"]*M5
    boundary=(opening//86400000)*86400000+minute*60000
    if boundary<=opening:
        boundary+=86400000
    crossings=0
    while boundary<=ending:
        crossings+=1
        boundary+=86400000
    daily_key="longDailyDebitBps" if side>0 else "shortDailyDebitBps"
    funding=current_cost.get(daily_key)
    if funding is None:
        return None
    return float(current_cost[scenario+"Bps"])+3.*crossings*max(0.,float(funding))


def admitted_research_opportunity(row,forecast,current_cost):
    """Evaluate predictive confidence first, cost admissibility second.

    Classification and all outcomes are separated from the eventual
    capital/risk C# layer; no automatic broker or portfolio order.
    """
    x=forecast["target"];sig=forecast["meanSE"]
    direction=int(np.sign(x[0]))
    if direction==0 or abs(x[0])<=FIXED_Z*sig[0]:
        return {"state":"PREDICTIVE_ABSTAIN","side":0,
                "direction":direction,"predictedNormalizedMove":float(x[0]),
                "probUp":forecast["probUp"]}
    if current_cost is None or (
        current_cost.get("minimumNotionalEur",0)<=0 or
        current_cost.get("minimumMarginEur",1e8)>=300
    ):
        return {"state":"FINANCIAL_UNKNOWN_OR_UNFUNDED","side":None,
                "direction":direction,"probUp":forecast["probUp"]}
    scale=row["vol5"]*sqrt(row["h"])*10000
    expected=abs(float(x[0]))*scale
    se_bps=float(sig[0])*scale
    friction=current_term_friction_bps(row,direction,current_cost,"adverse")
    if friction is None:
        return {"state":"FINANCIAL_UNKNOWN_OR_UNFUNDED","side":None,
                "direction":direction,"probUp":forecast["probUp"]}
    conservative=expected-FIXED_Z*se_bps-friction
    if conservative<=0:
        return {"state":"COST_ABSTAIN","side":0,
                "direction":direction,"probUp":forecast["probUp"],
                "conservativeNetEur":conservative*current_cost["minimumNotionalEur"]/10000}
    high=float(x[1]);low=float(x[2])
    favorable=max(0.,(high if direction>0 else -low)*scale)
    adverse=max(0.,(-low if direction>0 else high)*scale)
    return {"state":"RESEARCH_OPPORTUNITY_UNFUNDED","side":direction,
            "direction":direction,"probUp":forecast["probUp"],
            "predictedFavorableExcursionBps":favorable,
            "predictedAdverseExcursionBps":adverse,
            "predictedVolExpansionProb":forecast["volExpansionProb"],
            "conservativeNetEur":conservative*current_cost["minimumNotionalEur"]/10000,
            "currentMinimumMarginEur":current_cost["minimumMarginEur"]}


def diagnostic_eur(row,direction,cost,scenario):
    """Single-candidate conditional current-term EUR; NOT a common book."""
    if direction is None or not row["known"] or cost is None:
        return None
    if direction==0:
        return 0.
    friction=current_term_friction_bps(row,direction,cost,scenario)
    if friction is None:
        return None
    return cost["minimumNotionalEur"]*(
        direction*row["returnBps"]-friction)/10000.
