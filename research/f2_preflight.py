
"""Short fail-closed scientific and financial feasibility SCREEN, not a scored study.

Uses frozen authentic-public aggregates only; never downloads/decrypts bars,
reconstructs closed forecasts, or manufactures effective week variances.
"""
import json, math
from pathlib import Path
from statistics import NormalDist

ROOT=Path("research/f2_screening_candidate.json")
def causal_sign(returns):
    """Synthetic functional discriminant, not a fit or market forecast."""
    if len(returns)<21 or returns[-1]==0:return 0
    tail=returns[-21:]
    x=tail[:-1];y=tail[1:]
    xm=sum(x)/20;ym=sum(y)/20
    top=sum((a-xm)*(b-ym) for a,b in zip(x,y))
    den=math.sqrt(sum((a-xm)**2 for a in x)*sum((b-ym)**2 for b in y))
    if not den:return 0
    rho=top/den
    return (1 if returns[-1]>0 else -1)*(1 if rho>.2 else -1 if rho<-.2 else 0)

def assess(candidate=None, pilot=None):
    p=candidate or json.loads(ROOT.read_text())
    orig=json.loads(Path(p["source"]["receiptFile"]).read_text())
    inventory=json.loads(Path("docs/FULL_CTRADER_ACCOUNT_INVENTORY_AUTHENTIC_20261105.json").read_text())
    margins=json.loads(Path("docs/IES1_AUTHENTIC_EXPOSED_RECEIPT.json").read_text())
    contract=Path("src/Mxm.Core/ResearchScopeContract.cs").read_text()
    ledger=Path("src/Mxm.Core/OwnerRiskLimits.cs").read_text()
    reasons=[]
    def fail(code):reasons.append(code)
    if p["status"]!="PREFLIGHT_SCREEN_NOT_SCORED" or p["statusClaims"]["netQualified"]:
        fail("SCIENTIFIC_STATUS_OR_NET_PROMOTION_FORBIDDEN")
    if p["capital"]["prospectiveInitialEur"]!=300 or "InitialCapitalEur=300m" not in ledger:
        fail("ACTIVE_EUR300_CAPITAL_MISMATCH")
    if not p["capital"]["physicalUnitRequirement"] or p["capital"]["nativeFundedAuthority"]!="NativeFundedLedger" or "NATIVE_FUNDED_CYCLE_DEVELOPMENT_NOT_CERTIFIED" not in contract:
        fail("NATIVE_PHYSICAL_FINANCIAL_AUTHORITY_MISSING")
    cal=p["calendar"]
    if (cal["developmentWeeks"],cal["selectionWeeks"],cal["globallyExposedAuditWeeks"])!=(26,13,13):
        fail("CAUSAL_CALENDAR_NOT_RECONCILED")
    if cal["independentConfirmationWeeks"]!=0 or not p["source"]["brokerSourcePreviouslyExposed"]:
        fail("GLOBALLY_EXPOSED_MUST_NOT_BE_CALLED_INDEPENDENT")
    if orig["originalAuthenticM5Bars"]!=p["source"]["requiredAuthenticatedM5Bars"] or orig["sourceInstruments"]!=p["source"]["expectedInstruments"]:
        fail("AUTHENTIC_SOURCE_AGGREGATE_MISMATCH")
    if not orig["evidenceLimits"]["allSourceWeeksGloballyExposed"] or orig["evidenceLimits"]["independentConfirmation"]:
        fail("HISTORIC_INDEPENDENCE_CLAIM_CONFLICT")
    if inventory["completeNonArchivedAccountSymbolRoster"]!=5339 or inventory["contractProbeCount"]!=96:
        fail("SOURCE_SYMBOL_ROSTER_OR_TERMS_INTEGRITY")
    if margins["sourceWeeks"]!=52 or margins["sourceInstruments"]!=6:
        fail("COST_RECEIPT_CALENDAR_OR_UNIVERSE_MISMATCH")
    if not p["mechanism"] or not p["benchmark"] or not p["predictor"]:
        fail("FALSIFIABLE_DISTINCT_PREDICTOR_OR_BENCHMARK_MISSING")
    # Construction check: an alternating historical sequence must produce
    # a signed forecast opposite the unconditional H1 momentum benchmark.
    pattern=[1 if i%2==0 else -1 for i in range(21)]
    if causal_sign(pattern)!=-pattern[-1] or causal_sign([1]*21)!=0:
        fail("PREDICTOR_BENCHMARK_CONSTRUCTION_NOT_DISTINCT")
    if p["uncertainty"]["oneSidedComparisons"]<1 or p["uncertainty"]["alphaFamily"]<=0 or p["uncertainty"]["alphaFamily"]>=1:
        fail("MULTIPLICITY_PROTOCOL_INVALID")
    u=p["uncertainty"]
    if pilot is not None:
        u=dict(u,**pilot)
    n=u["effectiveSelectionWeeks"];sd=u["selectionWeeklyStandardDeviationBps"]
    threshold=u["requiredEconomicallyDetectableEffectBps"]
    mde=None
    if n is None or sd is None or threshold is None or n<8 or n>cal["selectionWeeks"] or sd<=0 or threshold<=0:
        fail("INFORMATIVE_WEEKS_OR_PILOT_VARIANCE_UNKNOWN")
    else:
        z=NormalDist().inv_cdf(1-u["alphaFamily"]/u["oneSidedComparisons"])+NormalDist().inv_cdf(u["targetPower"])
        mde=z*sd/math.sqrt(n)
        if mde>threshold:fail("POWER_INSUFFICIENT_FOR_ECONOMIC_MINIMUM_EFFECT")
    # Authenticated *old* margin observations are only a necessary feasibility
    # signal.  They are not a current financing or historical BID/ASK certificate.
    rows={x["symbol"]:x["currentMinimumMarginEur"] for x in margins["instruments"]}
    fx=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD"]
    fx5=round(sum(rows[x] for x in fx),2)
    fxgold=round(fx5+rows["XAUUSD"],2)
    if fx5>300 or fxgold<=300:fail("AUTHENTIC_OLD_MARGIN_EXPECTATION_CHANGED")
    if not p["funding"]["currentMinVolumeCommissionAndSpreadComplete"]:
        fail("MIN_VOLUME_CURRENT_COST_AND_FX_NOT_COMPLETE")
    if not p["funding"]["oneCapitalPortfolioFinanceCertified"]:
        fail("ONE_CAPITAL_EXECUTABILITY_NOT_CERTIFIED")
    # Operational preflight must not prevent exploratory feature construction.
    scoring_allowed=not reasons
    return dict(study=p["id"],status=p["status"],authenticOldM5Bars=orig["originalAuthenticM5Bars"],
        sourceInstruments=orig["sourceInstruments"],accountRoster=inventory["completeNonArchivedAccountSymbolRoster"],
        oldObservedFx5MinMarginEur=fx5,oldObservedFx5PlusGoldMarginEur=fxgold,
        powerMdeBps=mde,exploratoryFeaturesAllowed=True,
        protectedEconomicScoringAllowed=scoring_allowed,fundedNetPromotionAllowed=False,
        independentConfirmation=False,ordersSubmitted=0,cloudActivated=False,blockReasons=reasons)

def prospective_economic_futility(weekly_adverse_net_bps, weekly_incremental_bps, *,
                                  model_cost_context_complete,
                                  predeclared_comparisons, active_development_weeks,
                                  required_incremental_surplus_bps=0.0,
                                  alpha_family=0.05, hac_lags=3,
                                  minimum_development_weeks=20):
    """Prospective DEVELOPMENT-only bound; does not score or promote a candidate.

    Both series contain one paired observation per chronological eligible calendar
    week INCLUDING genuine zero-trade weeks. Do not use past globally exposed
    selection or audit returns; never call this on a closed study.
    Upper bounds account for serial weekly dependence using the larger of a
    fixed-lag Newey-West and unadjusted variance. The Bonferroni comparison
    count belongs to the preregistered whole programme.
    A positive upper bound merely means "futility NOT demonstrated".
    """
    from statistics import mean, stdev
    a=list(weekly_adverse_net_bps)
    b=list(weekly_incremental_bps)
    n=len(a)
    if (not model_cost_context_complete or n!=len(b) or
        n<minimum_development_weeks or active_development_weeks<8 or
        active_development_weeks>n or
        predeclared_comparisons<2 or hac_lags!=3 or
        not 0<alpha_family<1 or required_incremental_surplus_bps<0 or
        not all(math.isfinite(x) for x in a+b)):
        return dict(status="NOT_INFORMATIVE_NO_ECONOMIC_PROMOTION",
                    economicallyFutile=None,
                    scoreSelectionAllowed=False,
                    developmentWeeks=n,returnOutcomesIndependent=False,
                    reasons=["MISSING_COST_OR_WEEKLY_DEPENDENCE_EVIDENCE"])
    def upper(xs):
        mu=mean(xs)
        if stdev(xs)<=0:
            return None,None
        centered=[x-mu for x in xs]
        gamma0=sum(z*z for z in centered)/n
        lrv=gamma0
        for lag in range(1,hac_lags+1):
            gamma=sum(centered[t]*centered[t-lag]
                      for t in range(lag,n))/n
            lrv+=2*(1-lag/(hac_lags+1))*gamma
        se=max(stdev(xs)/math.sqrt(n),math.sqrt(max(0,lrv)/n))
        z=NormalDist().inv_cdf(1-alpha_family/predeclared_comparisons)
        return mu+z*se, se
    net_ub,net_se=upper(a)
    inc_ub,inc_se=upper(b)
    if net_ub is None or inc_ub is None:
        return dict(status="NOT_INFORMATIVE_NO_ECONOMIC_PROMOTION",
                    economicallyFutile=None,scoreSelectionAllowed=False,
                    developmentWeeks=n,returnOutcomesIndependent=False,
                    reasons=["ZERO_WEEKLY_VARIANCE_CANNOT_CERTIFY_FUTILITY"])
    # Reject only if the plausible upper bound cannot cover adverse all-in
    # cost or beat the fixed same-clock benchmark.
    futile=net_ub<=0 or inc_ub<=required_incremental_surplus_bps
    return dict(status="FUTILE_STOP_BEFORE_SELECTION" if futile else
                "UPPER_BOUND_ALLOWS_PLAUSIBILITY_NOT_EVIDENCE",
                economicallyFutile=futile,
                scoreSelectionAllowed=not futile,developmentWeeks=n,
                activeDevelopmentWeeks=active_development_weeks,
                conditionalAdverseNetMeanBps=mean(a),
                incrementalMatchedBenchmarkMeanBps=mean(b),
                upperAdverseNetBps=net_ub,
                upperIncrementalBps=inc_ub,
                standardErrorAdverseHacConservativeBps=net_se,
                standardErrorIncrementalHacConservativeBps=inc_se,
                familyComparisons=predeclared_comparisons,
                hacLagsFixedExAnte=hac_lags,
                independenceCertified=False,financeCertified=False,
                hard21Certified=False,
                statusIsNotProofOfPositiveEdge=True)

if __name__=="__main__":
    print(json.dumps(assess(),sort_keys=True))
