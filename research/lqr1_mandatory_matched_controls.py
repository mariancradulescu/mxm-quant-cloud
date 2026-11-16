"""LQR1 MANDATORY EXACT MATCHED FINANCIAL CONTROL READBACK; NOT new study.

The original LQR1 source and exact negative native EUR result remain IMMUTABLE.
This completes prespecified comparisons on precisely LQR1's 42 PREDECISION
signal clocks; no LQR1 return rescoring, refit, retrospective subset,
future-available admission, or additional broker requests. Reuse the SAME
native C# EUR300 funded replay with source- and outcome-independent fixed
control directions, and preserve any missing financial evidence as UNKNOWN.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
import json,os

from .bti1_temporal_burstiness import authenticated_tape
from .lqr1_eur_native_readback import (
    new_original,source_rows,build_native,run_native,
    SLIP,PROTO,TARGETS)
from .decode import need

ORIGINAL=Path("lqr1-immutable-money/lqr1-original-authentic-eur300-native-financial.public.json")
ORIGINAL_SHA="a6f539d37fa7d541ec60434efc66bd8d0adec936f31e144b90cf154072df5033"
OUTPUT=Path("lqr1-mandatory-exact-matched-42-controls.public.json")
POLICIES=("ownMomentum","long","short","cash")


def matched_source_only(rows,control):
    """Derive 42 masks using ONLY the existing predecision LQR1 feature.

    The original C#-fact adapter is called with its unchanged LQR1 dispatch,
    but receives an observationally fixed control side per original LQR1
    intention. There is NO reexecution of the actual LQR1 policy/score.
    """
    need(control in POLICIES,"LQR1_PAIRED_CONTROL_UNKNOWN")
    selected=0
    divergent=0
    transformed=[]
    for row in rows:
        new=dict(row)
        new["symbols"]={}
        for sym in TARGETS:
            source=row["symbols"][sym]
            orig=source["feature"]
            f=dict(orig)
            if f["state"]=="SIDE_SPECIFIC_SIGNAL":
                selected+=1
                need(f["side"] in (-1,1) and f["own"] in (-1,0,1),
                     "LQR1_ORIGINAL_FIXED_PREDECISION_SIDE_INVALID")
                divergent+=int(f["side"]!=f["own"])
                if control=="ownMomentum":
                    chosen=f["own"]
                elif control=="long":
                    chosen=1
                elif control=="short":
                    chosen=-1
                else:
                    chosen=0
                f["side"]=chosen
            else:
                need(f["state"]=="ABSTAIN_SIMULTANEOUS"
                     and f["side"]==0,"LQR1_ORIGINAL_PREDECISION_UNKNOWN")
                f["state"]="ABSTAIN_SIMULTANEOUS"
                f["side"]=0
            new["symbols"][sym]=dict(source,feature=f)
        transformed.append(new)
    need(selected==42 and divergent==21,"LQR1_PAIRED_ORIGINAL_MASK_CHANGED")
    return transformed,dict(originalLqr1Intents=selected,
                            originalSideDiffersFromMomentum=divergent,
                            control=control,maskOnlyPredecision=True)


def control_book(rows,control,slip):
    transformed,mask=matched_source_only(rows,control)
    # Original readback's event converter is unchanged and sends model facts
    # to original shared C# NativeFundedLedger, not a second Python ledger.
    events,counts,missing=build_native(transformed,"lqr1",slip)
    if events is None:
        return dict(mask=mask,netEur=None,
                    reason="MISSING_ASOF_OR_COST_MUST_NOT_DROP_PRIMARY_INTENT",
                    missingOriginalFinancial=len(missing),
                    predecision=counts)
    if not events:
        return dict(mask=mask,netEur=0.0,fundedRoundTrips=0,
                    finalCashEur=300.0,predecision=counts)
    original_native=run_native(events)
    summary=original_native["Summary"]
    need(original_native["RestartEveryEventMatched"]
         and original_native["DuplicatesIdempotent"]
         and original_native["OrdersSubmitted"]==0
         and original_native["CloudActivated"] is False,
         "LQR1_PAIRED_NATIVE_RECEIPT")
    return dict(mask=mask,
        netEur=float(D(str(summary["ClosedNetEur"]))),
        fundedRoundTrips=int(summary["CompleteRoundTrips"]),
        finalCashEur=float(D(str(summary["CashEur"]))),
        sampledDrawdownFraction=float(summary["MaximumSampledDrawdown"]),
        floating30PctContinuousCertified=False,
        modeledBrokerFillsOnly=True,
        nativeRestartEveryEventMatched=True,
        predecision=counts)


def main():
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"LQR1_ORIGINAL_CUSTODY_NOT_AUTHORIZED")
    raw=ORIGINAL.read_bytes()
    need(sha256(raw).hexdigest()==ORIGINAL_SHA,"LQR1_ORIGINAL_FINANCE_REPORT_NOT_IMMUTABLE")
    old=json.loads(raw)
    need(old["schema"]=="MXM_LQR1_ORIGINAL_PAIRED_EUR300_NATIVE_DEVELOPMENT_V1"
         and old["singleInitialCapitalEur"]==300
         and old["sourceOriginalProtobufVerified"]
         and old["newOriginalPepperstoneFinancialRunId"]==43900286858
         and old["frozenProtocolSha256"]==sha256(PROTO.read_bytes()).hexdigest(),
         "LQR1_ORIGINAL_MONEY_IDENTITY")
    for name in ("central","adverse","stress"):
        primary=old["originalNativeFundedPolicies"]["lqr1"][name]
        need(primary["fundedCompletedRoundTrips"]==42
             and primary["fullConditionalNativeNetEur"]<0,
             "LQR1_ORIGINAL_LQR1_NEGATIVE_RECEIPT_PRESERVED")
    tape,_=authenticated_tape() # strict raw protobuf/source-only readback; not old score
    financial,contracts,margins,checks,receipt,swapfree=new_original(private)
    need(receipt["runId"]==43900286858 and checks["valid"]==160
         and financial["originalReadOnlyRequestCount"]==328,
         "LQR1_ORIGINAL_FINANCIAL_SOURCE_DIFFERENT")
    rows=source_rows(tape,financial,contracts,margins,swapfree)
    comparators={}
    for control in POLICIES:
        comparators[control]={}
        for scenario,slip in SLIP.items():
            comparators[control][scenario]=control_book(rows,control,slip)
    deltas={}
    for scenario in SLIP:
        net=old["originalNativeFundedPolicies"]["lqr1"][scenario]["fullConditionalNativeNetEur"]
        deltas[scenario]={control:(
            round(net-comparators[control][scenario]["netEur"],9)
            if comparators[control][scenario]["netEur"] is not None else None)
            for control in POLICIES}
    out=dict(schema="MXM_LQR1_MANDATORY_PAIRED_42_DEVELOPMENT_CONTROLS_ONLY_V1",
        originalPrimaryEconomicRunId=43900286858,
        originalPrimaryEconomicArtifactId=14240978134,
        originalPrimaryInnerJsonSha256=ORIGINAL_SHA,
        originalPrimarySourceCipherSha256=receipt["cipherSha256"],
        frozenProtocolSha256=old["frozenProtocolSha256"],
        originalSourceAuthenticatedFullProtobuf=True,
        exactPredecisionMatchedLqr1Intents=42,
        baselinePolicyCapitalEur=300,
        primaryLqr1OriginalNativeEur={s:{
            "netEur":old["originalNativeFundedPolicies"]["lqr1"][s]["fullConditionalNativeNetEur"],
            "fundedRoundTrips":old["originalNativeFundedPolicies"]["lqr1"][s]["fundedCompletedRoundTrips"]}
            for s in SLIP},
        sameExact42IntentsNativeFinancedControls=comparators,
        originalLqr1MinusMatchedControlEur=deltas,
        globalOutcomesAlreadyExposed=True,
        noPrimaryLqr1RerunOrRetuning=True,
        noClosedQpiOrBtiRerun=True,
        originalStudyResultUnchanged=True,
        brokerNewReadOnlyRequests=0,
        historicalTariffContinuityCertified=False,
        actualBrokerExecutionNetEur=None,
        systemHard21Certified=False,
        continuousFloatingDrawdown30Certified=False,
        independentLongChronologyCertified=False,
        ordersSubmitted=0,cloudActivation=False)
    OUTPUT.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("LQR1_EXACT_42_ORIGINAL_INTENTS_MATCHED_CONTROLS_FINANCED_IN_NATIVE_NO_PRIMARY_REPLAY",flush=True)


if __name__=="__main__":
    main()
