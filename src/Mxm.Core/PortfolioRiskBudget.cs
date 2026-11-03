namespace Mxm.Core;

// Analysis-only risk admission; never submits, modifies or closes an order.
// Numbers must be obtained from the broker and a reconciled account history,
// not a guessed risk-per-trade, reserved cash or single-position cap.
public sealed record OpenRiskExposure(
    string PositionKey, decimal WorstAdditionalLossEur, decimal MarginEur);

public sealed record ProposedRiskExposure(
    string ProposalKey, decimal StopAndGapLossEur, decimal EntryExitCostBoundEur,
    decimal RequiredMarginEur);

public sealed record BrokerRiskSnapshot(
    decimal EquityEur, decimal FreeMarginEur, decimal? CertifiedEquityPeakUpperEur,
    bool AccountAndPositionsReconciled, bool OrderOutcomesKnown,
    bool ExistingRiskBoundsComplete, bool ProposedMarginAndLossBoundsVerified);

public sealed record PortfolioRiskObservation(bool Admissible, string Reason,
    decimal DrawdownHeadroomEur, decimal TotalStressLossAfterEur,
    decimal FreeMarginAfterEur, int PortfolioPositionCountAfter);

// Mandatory current-equity aggregate OWNER 1% risk /40% margin /60% reserve.
// Unknown broker data refuses new exposure; no fixed position-count restriction.
public static class PortfolioRiskBudget
{
    public static PortfolioRiskObservation Assess(
        BrokerRiskSnapshot account,
        IEnumerable<OpenRiskExposure> openExposures,
        ProposedRiskExposure proposed)
    {
        ArgumentNullException.ThrowIfNull(account);
        ArgumentNullException.ThrowIfNull(openExposures);
        ArgumentNullException.ThrowIfNull(proposed);
        var rows = openExposures.ToArray();
        PortfolioRiskObservation Deny(string reason) =>
            new(false, reason, 0m, 0m, 0m, rows.Length);

        if (account.EquityEur <= 0m || account.FreeMarginEur < 0m)
            return Deny("EQUITY_OR_MARGIN_INVALID");
        if (!account.AccountAndPositionsReconciled || !account.OrderOutcomesKnown)
            return Deny("UNKNOWN_ACCOUNT_OR_ORDER_OUTCOME");
        if (!account.ExistingRiskBoundsComplete ||
            !account.ProposedMarginAndLossBoundsVerified)
            return Deny("UNVERIFIED_RISK_OR_EXECUTION_BOUNDS");
        if (account.CertifiedEquityPeakUpperEur is not decimal peak ||
            peak < 200m || peak < account.EquityEur)
            return Deny("UNCERTIFIED_EQUITY_PEAK");
        if (string.IsNullOrWhiteSpace(proposed.ProposalKey) ||
            rows.Any(x => string.IsNullOrWhiteSpace(x.PositionKey)) ||
            rows.Select(x => x.PositionKey).Distinct(StringComparer.Ordinal).Count() != rows.Length ||
            rows.Any(x => x.PositionKey == proposed.ProposalKey))
            return Deny("AMBIGUOUS_EXPOSURE_IDENTITY");
        if (rows.Any(x => x.WorstAdditionalLossEur < 0m || x.MarginEur < 0m) ||
            proposed.StopAndGapLossEur < 0m ||
            proposed.EntryExitCostBoundEur < 0m ||
            proposed.RequiredMarginEur < 0m)
            return Deny("NEGATIVE_RISK_OR_COST_INPUT");

        decimal headroom = .70m * peak <= account.EquityEur ?
            account.EquityEur - .70m * peak : 0m;
        decimal combinedStress = rows.Sum(x => x.WorstAdditionalLossEur) +
            proposed.StopAndGapLossEur + proposed.EntryExitCostBoundEur;
        decimal freeAfter = account.FreeMarginEur - proposed.RequiredMarginEur;
        var owner=OwnerRiskLimits.Check(account.EquityEur,account.FreeMarginEur,rows.Sum(x=>x.WorstAdditionalLossEur),rows.Sum(x=>x.MarginEur),proposed.StopAndGapLossEur+proposed.EntryExitCostBoundEur,proposed.RequiredMarginEur);
        bool withinRisk = headroom > 0m && combinedStress < headroom && owner.Allowed;
        bool withinMargin = proposed.RequiredMarginEur > 0m && freeAfter >= 0m;
        string reason = !owner.Allowed ? owner.Reason : !withinRisk ? "CORRELATED_STRESS_EXCEEDS_DRAWDOWN_BUFFER" :
            !withinMargin ? "BROKER_MARGIN_NOT_AVAILABLE" :
            "OBSERVATION_ONLY_RISK_CAPACITY_WITHIN_BOUNDS";
        return new PortfolioRiskObservation(withinRisk && withinMargin, reason,
            headroom, combinedStress, freeAfter, rows.Length + 1);
    }
}
