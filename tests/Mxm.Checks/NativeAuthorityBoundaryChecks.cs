using System;
using System.Linq;
using Mxm.Core;

internal static class NativeAuthorityBoundaryChecks
{
    public static void Run(Action<bool, string> check)
    {
        var path = new NativeAuthorityKernels(
            typeof(NativeProductResearchLoop),
            typeof(NativeEntryOutcomeCalibration),
            typeof(NativeFundedSession),
            typeof(NativeFundedLedger),
            typeof(NativeBrokerContractCosts),
            typeof(NativeFundedLedger),
            typeof(NativePerformanceScorecard));
        var book = new NativeFundedLedger().Summary();
        var score = NativePerformanceScorecard.Calculate(
            new NativeEconomicScorecardInput("FUTURE_SYNTHETIC_ONLY",
                Array.Empty<LedgerClosedFragment>(),
                Array.Empty<NativeEconomicMark>(),
                Array.Empty<NativeEntryRisk>(),
                new[] { "2026-W47" }));
        var review = NativeAuthorityBoundary.Examine(path, score, book);
        check(review.SharedCoreTypes, "native authority requires shared Mxm.Core classes");
        check(!review.ClosedBookArithmeticAligned && !review.ReadyForNativeEconomicAudit,
            "zero-trade synthetics cannot masquerade as a reconciled book or audit-ready economics");
        check(!review.EconomicQualificationDemonstrated && !review.TradingAuthorized,
            "compilation and zero-trade scorecard never authorize economics or orders");
        check(review.BlockingReasons.Contains("SYSTEM_HARD21_ALL_ELIGIBLE_WEEKS_NOT_PROVEN") &&
              review.BlockingReasons.Contains("CONTINUOUS_FLOATING_DRAWDOWN_30_PERCENT_NOT_CERTIFIED"),
            "systemic HARD21 and floating-DD remain separate protective gates");
        var replayOnly = path with { Model = typeof(string) };
        var mismatch = NativeAuthorityBoundary.Examine(replayOnly, score, book,
            SameInputFeatureModelDecisionFillAndMoneyParityAttested: true,
            EntireEligibleWeekCalendarAttested: true,
            IndependentTwelveMonthConfirmationAttested: true);
        check(!mismatch.SharedCoreTypes && !mismatch.ReadyForNativeEconomicAudit &&
              mismatch.BlockingReasons.Contains("POLICY_OR_FINANCE_CODE_OUTSIDE_SHARED_MXM_CORE"),
            "non-Core model is ineligible even if a caller asserts all parity attestations");
        check(!mismatch.EconomicQualificationDemonstrated && !mismatch.TradingAuthorized,
            "unverified attestations never bypass missing economic and broker evidence");
        check(OwnerRiskAuthority.InitialCapitalEur == 300m &&
              OwnerRiskAuthority.MinimumSystemRoundTripsPerEligibleWeek == 21 &&
              OwnerRiskAuthority.MaximumSystemDrawdown == .30m,
            "OWNER EUR300, systemic HARD21 and DD30 remain unchanged");
    }
}
