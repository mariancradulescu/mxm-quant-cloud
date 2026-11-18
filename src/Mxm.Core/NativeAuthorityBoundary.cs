using System;
using System.Linq;

namespace Mxm.Core;

// Prospective admission boundary only. This does not forecast, select,
// simulate fills, reprice a trade or grant permission to send an order.
// The existing native scorecard and common funded ledger own all money.
public sealed record NativeAuthorityKernels(
    Type Features, Type Model, Type Decision, Type SimulatedExecution,
    Type Costs, Type CommonCapital, Type Risk);

public sealed record NativeAuthorityFinding(
    bool SharedCoreTypes,
    bool ClosedBookArithmeticAligned,
    bool ReadyForNativeEconomicAudit,
    bool EconomicQualificationDemonstrated,
    bool TradingAuthorized,
    string[] BlockingReasons);

public static class NativeAuthorityBoundary
{
    private static bool IsCore(Type? type) =>
        type is not null &&
        type.Assembly == typeof(NativeFundedLedger).Assembly &&
        type.Namespace == typeof(NativeFundedLedger).Namespace;

    // Every new research study must supply a real same-input parity receipt
    // independently checked by CI/auditor. Booleans here are declarations,
    // NOT verification of the supporting traces or of source custody.
    public static NativeAuthorityFinding Examine(
        NativeAuthorityKernels kernels,
        NativeEconomicScorecard score,
        LedgerSummary book,
        bool SameInputFeatureModelDecisionFillAndMoneyParityAttested = false,
        bool EntireEligibleWeekCalendarAttested = false,
        bool IndependentTwelveMonthConfirmationAttested = false)
    {
        if (kernels is null || score is null || book is null)
            throw new ArgumentNullException("NATIVE_AUTHORITY_REQUIRED_EVIDENCE");

        bool sharedCore = new[] { kernels.Features, kernels.Model, kernels.Decision,
            kernels.SimulatedExecution, kernels.Costs, kernels.CommonCapital,
            kernels.Risk }.All(IsCore);
        bool closedBook = score.FullFinancialOutcomeKnown &&
            score.NetEur is decimal net &&
            book.OpenPositions == 0 && book.PendingIntents == 0 &&
            book.CompleteRoundTrips == score.CompletedRoundTrips &&
            Math.Abs(book.ClosedNetEur - net) <= .0000001m &&
            Math.Abs(book.CashEur - OwnerRiskAuthority.InitialCapitalEur - net) <= .0000001m;

        var blockers = new System.Collections.Generic.List<string>();
        if (!sharedCore) blockers.Add("POLICY_OR_FINANCE_CODE_OUTSIDE_SHARED_MXM_CORE");
        if (!SameInputFeatureModelDecisionFillAndMoneyParityAttested)
            blockers.Add("SAME_INPUT_FULL_STAGE_PARITY_NOT_ATTESTED");
        if (!closedBook || book.HistoryEvidenceIncomplete)
            blockers.Add("ONE_EUR300_NATIVE_BOOK_NOT_FULLY_RECONCILED");
        if (score.NetEur is not decimal positiveNet || positiveNet <= 0 ||
            score.IncrementalVersusBenchmarkEur is not decimal incremental || incremental <= 0)
            blockers.Add("POSITIVE_ADVERSE_INCREMENTAL_NET_NOT_DEMONSTRATED");
        if (!EntireEligibleWeekCalendarAttested ||
            score.FundedCompletionsByIsoWeek is null ||
            score.FundedCompletionsByIsoWeek.Count == 0 ||
            !score.Hard21AllEligibleWeeks ||
            score.FundedCompletionsByIsoWeek.Values.Any(v => v <
                OwnerRiskAuthority.MinimumSystemRoundTripsPerEligibleWeek))
            blockers.Add("SYSTEM_HARD21_ALL_ELIGIBLE_WEEKS_NOT_PROVEN");
        if (!score.ContinuousDrawdownCertified || !book.GlobalDrawdownCertified ||
            score.MaximumSampledFloatingDrawdown is not decimal drawdown ||
            drawdown > OwnerRiskAuthority.MaximumSystemDrawdown)
            blockers.Add("CONTINUOUS_FLOATING_DRAWDOWN_30_PERCENT_NOT_CERTIFIED");
        if (!book.BrokerStateReconciled)
            blockers.Add("BROKER_CASH_EXECUTION_AND_RESTART_NOT_CERTIFIED");
        if (!IndependentTwelveMonthConfirmationAttested)
            blockers.Add("TWELVE_MONTH_INDEPENDENT_CONFIRMATION_NOT_ATTESTED");

        // The path to further native economic review is intentionally distinct
        // from positive economics or product authorization. The current Cloud
        // adapter remains observation-only, regardless of these inputs.
        bool nativeAuditReady = sharedCore &&
            SameInputFeatureModelDecisionFillAndMoneyParityAttested &&
            closedBook && !book.HistoryEvidenceIncomplete;
        // Declarations and arithmetic can only open an independent audit;
        // they cannot themselves certify broker fills, trace provenance or
        // twelve months of unexposed confirmation. Owner activation is separate.
        if (!blockers.Contains("INDEPENDENT_ARTIFACT_AND_TRACE_AUDIT_REQUIRED"))
            blockers.Add("INDEPENDENT_ARTIFACT_AND_TRACE_AUDIT_REQUIRED");
        return new NativeAuthorityFinding(sharedCore, closedBook, nativeAuditReady,
            false, false, blockers.ToArray());
    }
}
