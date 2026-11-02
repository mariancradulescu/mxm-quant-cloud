namespace Mxm.Core;

public enum RecoveryMode { Protective, ReconciledObservation }
public sealed record RecoveryEvidence(decimal Equity, decimal InitialCapital,
    decimal? EquityPeakUpperBound, bool CompleteInventory, bool CashflowsVerified,
    bool AdaptationRebuilt, bool AmbiguousOrder, bool ForeignExposure);
public sealed record RecoveryDecision(RecoveryMode Mode, string Reason, decimal? DrawdownUpperBound);

public static class Recovery
{
    public const decimal OwnerDrawdownLimit = 0.30m;
    // An upper bound on the historical peak gives an upper bound on drawdown.
    // max(initial capital, balance, current equity) is only a LOWER bound: unsafe.
    public static RecoveryDecision Assess(RecoveryEvidence e)
    {
        RecoveryDecision Halt(string reason, decimal? dd = null) => new(RecoveryMode.Protective, reason, dd);
        if (e.InitialCapital != 200m || e.Equity <= 0m) return Halt("capital-policy-or-insolvency");
        if (!e.CompleteInventory) return Halt("inventory-unverified");
        if (!e.CashflowsVerified) return Halt("cashflows-unverified");
        if (e.AmbiguousOrder) return Halt("unknown-order-outcome-no-retry");
        if (e.ForeignExposure) return Halt("unattributed-exposure");
        if (!e.AdaptationRebuilt) return Halt("adaptation-unverified");
        if (e.EquityPeakUpperBound is not decimal peak || peak < e.Equity || peak < e.InitialCapital)
            return Halt("equity-peak-not-bounded");
        var dd = 1m - e.Equity / peak;
        if (dd >= OwnerDrawdownLimit) return Halt("drawdown-limit", dd);
        return new(RecoveryMode.ReconciledObservation, "observation-only-no-trading-authority", dd);
    }
}
