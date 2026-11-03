namespace Mxm.Core;

public enum RecoveryLaneMode
{
    ReconcileAccount, AutoRecoverTransient, QuarantinedAmbiguous,
    QuarantinedLocal, ReadyForObservation
}

public sealed record RecoveryLaneEvidence(
    string Symbol, bool NativeMarketDataFresh, bool InstrumentInventoryReconciled,
    bool TransientFault, bool UncertainOrderSubmission,
    bool PositiveBrokerFinalOutcomeReconciled,
    decimal? WorstCaseUnknownOrderLossEur,
    decimal? WorstCaseUnknownOrderMarginEur);

public sealed record RecoveryPortfolioEvidence(
    decimal EquityEur, decimal FreeMarginEur, decimal? CertifiedPeakUpperEur,
    bool CompleteNativeAccountInventory, bool CashFlowsReconciled,
    bool HistoricalInFlightIntentsCertified,
    decimal ExistingStressLossEur, decimal ExistingMarginEur,
    int VerifiedCurrentInFlightRequests);

public sealed record RecoveryLaneDecision(
    string Symbol, RecoveryLaneMode Mode, bool MonitorAndRetryAutomatically,
    bool EligibleForFurtherRiskReview, string Reason);

public sealed record RecoveryPortfolioDecision(
    bool MonitoringActive, bool CanReviewAnyNewExposure,
    decimal AvailableWorstCaseDrawdownHeadroomEur,
    decimal ReservableFreeMarginEur,
    IReadOnlyList<RecoveryLaneDecision> Lanes, string Status);

/// <summary>
/// Pure deterministic scheduler *admission*, not an order transmitter.
/// Ambiguous intents need affirmative terminal broker evidence: absence from
/// positions/history is NEVER accepted as a negative submission receipt.
/// Allows otherwise healthy lanes only when adverse unresolved exposure is
/// fully bounded under certified account equity and margin.
///
/// Stateless snapshots permit autonomous retries. Across restarts, callers
/// must prove complete historical in-flight intent knowledge separately:
/// in-memory maps and Cloud LocalStorage cannot certify this.
/// </summary>
public static class SelectiveRecovery
{
    public const int MaxConcurrentRequests=1;
    public static RecoveryPortfolioDecision Assess(
        RecoveryPortfolioEvidence account,
        IEnumerable<RecoveryLaneEvidence> lanes)
    {
        ArgumentNullException.ThrowIfNull(account);
        ArgumentNullException.ThrowIfNull(lanes);
        var list=lanes.ToArray();
        if(list.Any(x=>string.IsNullOrWhiteSpace(x.Symbol)) ||
            list.Select(x=>x.Symbol).Distinct(StringComparer.Ordinal).Count()!=list.Length)
            throw new ArgumentException("DUPLICATE_RECOVERY_LANE");
        if(account.ExistingStressLossEur<0m || account.ExistingMarginEur<0m ||
            account.VerifiedCurrentInFlightRequests<0 ||
            list.Any(x=>x.WorstCaseUnknownOrderLossEur<0m ||
                        x.WorstCaseUnknownOrderMarginEur<0m))
            throw new ArgumentException("INVALID_ADVERSE_RISK_RESERVATION");

        bool global=account.EquityEur>0m && account.FreeMarginEur>=0m &&
            account.CertifiedPeakUpperEur is decimal peak &&
            peak>=200m && peak>=account.EquityEur &&
            account.CompleteNativeAccountInventory &&
            account.CashFlowsReconciled &&
            account.HistoricalInFlightIntentsCertified;

        var unresolved=list.Where(x=>x.UncertainOrderSubmission &&
                    !x.PositiveBrokerFinalOutcomeReconciled).ToArray();
        bool allBounded=unresolved.All(x=>
            x.WorstCaseUnknownOrderLossEur.HasValue &&
            x.WorstCaseUnknownOrderMarginEur.HasValue);
        decimal adverseLoss=account.ExistingStressLossEur+
            unresolved.Sum(x=>x.WorstCaseUnknownOrderLossEur ?? 0m);
        decimal adverseMargin=account.ExistingMarginEur+
            unresolved.Sum(x=>x.WorstCaseUnknownOrderMarginEur ?? 0m);
        decimal headroom=global && allBounded ?
            Math.Max(0m,account.EquityEur-
                 .70m*account.CertifiedPeakUpperEur!.Value-adverseLoss):0m;
        decimal margin=global && allBounded ?
            Math.Max(0m,account.FreeMarginEur-unresolved.Sum(x=>x.WorstCaseUnknownOrderMarginEur ?? 0m)):0m;
        bool admissibleBase=global && allBounded &&
            headroom>0m && margin>0m &&
            account.VerifiedCurrentInFlightRequests<MaxConcurrentRequests;
        var result=new List<RecoveryLaneDecision>(list.Length);
        foreach(var x in list)
        {
            RecoveryLaneMode mode;
            string reason;
            if(!global || !allBounded)
            {
                mode=RecoveryLaneMode.ReconcileAccount;
                reason="ACCOUNT_OR_UNBOUNDED_AMBIGUITY_NOT_CERTIFIED";
            }
            else if(x.UncertainOrderSubmission &&
                    !x.PositiveBrokerFinalOutcomeReconciled)
            {
                mode=RecoveryLaneMode.QuarantinedAmbiguous;
                reason="POSITIVE_TERMINAL_OUTCOME_NOT_PROVEN_NO_RESUBMIT";
            }
            else if(x.TransientFault || !x.NativeMarketDataFresh)
            {
                mode=RecoveryLaneMode.AutoRecoverTransient;
                reason="RETRY_NATIVE_MARKET_SNAPSHOT_NO_NEW_ORDER";
            }
            else if(!x.InstrumentInventoryReconciled)
            {
                mode=RecoveryLaneMode.QuarantinedLocal;
                reason="INSTRUMENT_INVENTORY_PENDING";
            }
            else
            {
                mode=RecoveryLaneMode.ReadyForObservation;
                reason=admissibleBase ?
                    "INDEPENDENT_LANE_ADVERSE_RISK_REVIEW_ONLY" :
                    "ACCOUNT_STRESS_OR_INFLIGHT_BUDGET_EXHAUSTED";
            }
            result.Add(new(x.Symbol,mode,true,
                mode==RecoveryLaneMode.ReadyForObservation && admissibleBase,
                reason));
        }
        return new(true,result.Any(x=>x.EligibleForFurtherRiskReview),
            headroom,margin,result,
            !global || !allBounded?"MONITORING_ONLY_GLOBAL_EVIDENCE_MISSING" :
            "ISOLATED_AUTOMATIC_RECOVERY_OBSERVATION_ONLY");
    }
}
