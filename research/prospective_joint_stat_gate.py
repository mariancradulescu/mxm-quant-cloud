"""Prospective-only joint statistical gate for NEXT research programmes.

SFX1 results, historical HAC label and economic verdict are IMMUTABLE.
For a NEW family, test BOTH hypotheses separately:
 (a) adverse conditional NET > cash (0), and
 (b) adverse conditional NET - SAME-event benchmark NET > 0.
Missing costs are unknown, never zero. Exact predeclared number of families
defines the familywise one-sided Bonferroni confidence for 2 * N tests.
Calendar weeks with no opportunities count as zero SYSTEM activity, but do
not manufacture per-trade returns or a financed portfolio.
Research-only approximation; does not certify independent replication/fills.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from statistics import NormalDist
import math

@dataclass(frozen=True)
class ProspectiveJointGate:
    completeSignals: int
    activeWeeks: int
    eligibleWeeks: int
    projectedPotentialSignalsPerWeek: float
    grossMeanBps: float | None
    benchmarkGrossMeanBps: float | None
    centralNetMeanBps: float | None
    adverseNetMeanBps: float | None
    adverseBenchmarkNetMeanBps: float | None
    adverseIncrementalMeanBps: float | None
    cashAdverseWeeklyHacBonferroniLowerBps: float | None
    benchmarkIncrementalWeeklyHacBonferroniLowerBps: float | None
    familywiseOneSidedAlpha: float
    testsInFamily: int
    costAndConversionEvidenceComplete: bool
    passesBothProspectiveStatGates: bool
    evidenceClass: str = "CONDITIONAL_MODEL_NOT_BROKER_EUR_NET"

def _hac_lower(series:list[float],one_sided_alpha:float,lag:int=3):
    n=len(series)
    if n<12:return None
    mean=sum(series)/n
    centered=[x-mean for x in series]
    v=sum(x*x for x in centered)/n
    for k in range(1,min(lag,n-1)+1):
        v+=2*(1-k/(lag+1))*sum(centered[t]*centered[t-k]
                                 for t in range(k,n))/n
    if v < -1e-9:raise ValueError("NEGATIVE_HAC_VARIANCE")
    z=NormalDist().inv_cdf(1-one_sided_alpha)
    return mean-z*math.sqrt(max(v,0)/n)

def assess_prospective_weekly(events:list[dict],first_week:int,last_week:int,
                              declared_number_of_families:int,
                              minimum_complete_events:int=40,
                              minimum_active_weeks:int=8,
                              familywise_alpha:float=.05)->ProspectiveJointGate:
    if not 1<=declared_number_of_families<=20 or not 0<familywise_alpha<=.10 or \
       last_week-first_week<12 or first_week<0 or \
       minimum_complete_events<1 or minimum_active_weeks<1:
        raise ValueError("PROSPECTIVE_TEST_PROTOCOL_INVALID")
    require=("week","grossBps","benchmarkGrossBps",
             "centralNetBps","adverseNetBps","adverseBenchmarkNetBps")
    if any(not all(k in x for k in require) for x in events):
        raise ValueError("PROSPECTIVE_EVENT_SHAPE_INVALID")
    scoped=[x for x in events if first_week<=x["week"]<last_week]
    for x in scoped:
        if any(v is not None and
               (not isinstance(v,(int,float)) or not math.isfinite(v))
               for k,v in x.items() if k!="week"):
            raise ValueError("PROSPECTIVE_NONFINITE_ECONOMICS")
    buckets=[[x for x in scoped if x["week"]==w]
             for w in range(first_week,last_week)]
    count=len(scoped)
    active=sum(bool(w) for w in buckets)
    complete=all(x["adverseNetBps"] is not None and
                 x["adverseBenchmarkNetBps"] is not None and
                 x["centralNetBps"] is not None for x in scoped) and count>0
    def mean_or_null(key):
        if not scoped or any(x[key] is None for x in scoped):return None
        return sum(x[key] for x in scoped)/count
    incremental=(sum(x["adverseNetBps"]-x["adverseBenchmarkNetBps"]
                       for x in scoped)/count) if complete else None
    tests=2*declared_number_of_families
    alpha=familywise_alpha/tests
    cashLower=benchmarkLower=None
    if complete:
        cashWeek=[sum(x["adverseNetBps"] for x in group)/len(group)
                  if group else 0.0 for group in buckets]
        incrementalWeek=[sum(x["adverseNetBps"]-x["adverseBenchmarkNetBps"]
                             for x in group)/len(group)
                         if group else 0.0 for group in buckets]
        cashLower=_hac_lower(cashWeek,alpha)
        benchmarkLower=_hac_lower(incrementalWeek,alpha)
    passed=(count>=minimum_complete_events and active>=minimum_active_weeks and
            complete and cashLower is not None and cashLower>0 and
            benchmarkLower is not None and benchmarkLower>0)
    return ProspectiveJointGate(
      completeSignals=count,activeWeeks=active,eligibleWeeks=len(buckets),
      projectedPotentialSignalsPerWeek=count/len(buckets),
      grossMeanBps=mean_or_null("grossBps"),
      benchmarkGrossMeanBps=mean_or_null("benchmarkGrossBps"),
      centralNetMeanBps=mean_or_null("centralNetBps"),
      adverseNetMeanBps=mean_or_null("adverseNetBps"),
      adverseBenchmarkNetMeanBps=mean_or_null("adverseBenchmarkNetBps"),
      adverseIncrementalMeanBps=incremental,
      cashAdverseWeeklyHacBonferroniLowerBps=cashLower,
      benchmarkIncrementalWeeklyHacBonferroniLowerBps=benchmarkLower,
      familywiseOneSidedAlpha=alpha,testsInFamily=tests,
      costAndConversionEvidenceComplete=complete,
      passesBothProspectiveStatGates=passed)

def public_dict(receipt:ProspectiveJointGate):return asdict(receipt)
