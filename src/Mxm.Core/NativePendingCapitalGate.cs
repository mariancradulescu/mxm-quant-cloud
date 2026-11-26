using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

/// <summary>
/// Forward-only capital admission guard. Distinct from an actual broker fill:
/// it reserves all funded positions AND all requested but unfilled OPENs.
/// REQUEST_CLOSE/REDUCE never releases risk before their CLOSE_FILL witness.
/// This pure deterministic Core component submits no orders.
/// </summary>
public static class NativePendingCapitalGate
{
    public const decimal MaximumMarginFraction = .70m;
    public const decimal MaximumAggregateStopFraction = .05m;
    public const decimal MaximumTradeStopFraction = .015m;

    // Extra headroom is a function of committed monetary stop risk; the
    // original 70% gate remains unchanged and still applies independently.
    public static bool StopAdjustedMarginFits(decimal equity,decimal margin,decimal reservedRisk)
        =>equity>reservedRisk&&margin>=0m&&reservedRisk>=0m&&margin<=(equity-reservedRisk)*MaximumMarginFraction;

    public sealed record Commitment(string PositionId,string Symbol,decimal Units,
        decimal MarginPerUnit,decimal ReservedStopRiskEur,
        string RiskClass,bool IsPendingOpen)
    {
        public decimal MarginEur=>Units*MarginPerUnit;
    }
    public sealed record Proposal(string Symbol,string RiskClass,
        decimal MinimumUnits,decimal StepUnits,decimal MaximumUnits,
        decimal MarginPerUnit,decimal RiskEurPerUnit,
        decimal ExtraCorrelatedRiskEur=0m);
    public sealed record Admission(string Status,decimal EquityEur,
        decimal HeldMarginEur,decimal PendingOpenMarginEur,
        decimal HeldRiskEur,decimal PendingOpenRiskEur,
        decimal MarginLimitEur,decimal RiskLimitEur,
        decimal Units,decimal NewMarginEur,decimal NewRiskEur,
        decimal ReservedMarginAfterEur,decimal ReservedRiskAfterEur,
        bool IsFinanceable)
    {
        public decimal RemainingMarginEur=>MarginLimitEur-ReservedMarginAfterEur;
        public decimal RemainingRiskEur=>RiskLimitEur-ReservedRiskAfterEur;
    }
    public static Admission Assess(
        decimal? witnessedLiquidationEquityEur,bool currentMarksVerified,
        IReadOnlyCollection<Commitment> held,
        IReadOnlyCollection<Commitment> pendingOpen,
        Proposal proposal)
    {
        ArgumentNullException.ThrowIfNull(held);
        ArgumentNullException.ThrowIfNull(pendingOpen);
        ArgumentNullException.ThrowIfNull(proposal);
        // Caller must maintain separate consistent identities and must NOT
        // pass unconfirmed pending CLOSE as an offsetting negative reservation.
        var combined=held.Concat(pendingOpen).ToArray();
        if(combined.Any(x=>string.IsNullOrWhiteSpace(x.PositionId)||
            string.IsNullOrWhiteSpace(x.Symbol)||x.Units<=0m||
            x.MarginPerUnit<=0m||x.ReservedStopRiskEur<0m)||
            combined.Select(x=>x.PositionId).Distinct(StringComparer.Ordinal).Count()!=combined.Length||
            held.Any(x=>x.IsPendingOpen)||pendingOpen.Any(x=>!x.IsPendingOpen))
            throw new ArgumentException("PAV1_RESERVATION_IDENTITY_OR_COST_INVALID");
        decimal equity=witnessedLiquidationEquityEur??0m;
        decimal heldMargin=held.Sum(x=>x.MarginEur),pendingMargin=pendingOpen.Sum(x=>x.MarginEur);
        decimal heldRisk=held.Sum(x=>x.ReservedStopRiskEur),pendingRisk=pendingOpen.Sum(x=>x.ReservedStopRiskEur);
        decimal marginCap=Math.Max(0m,equity*MaximumMarginFraction);
        decimal riskCap=Math.Max(0m,equity*MaximumAggregateStopFraction);
        Admission Reject(string code)=>new(code,equity,heldMargin,pendingMargin,
            heldRisk,pendingRisk,marginCap,riskCap,0m,0m,0m,
            heldMargin+pendingMargin,heldRisk+pendingRisk,false);
        if(!currentMarksVerified||witnessedLiquidationEquityEur is null)
            return Reject("MISSING_CURRENT_LIQUIDATION_MARK");
        if(equity<=0m)return Reject("NO_EQUITY");
        if(proposal.MinimumUnits<=0m||proposal.StepUnits<=0m||
           proposal.MaximumUnits<proposal.MinimumUnits||proposal.MarginPerUnit<=0m||
           proposal.RiskEurPerUnit<=0m||proposal.ExtraCorrelatedRiskEur<0m||
           string.IsNullOrWhiteSpace(proposal.Symbol))
            return Reject("UNVERIFIED_LEGAL_VOLUME_OR_COST");
        if(combined.Any(x=>x.Symbol==proposal.Symbol))
            return Reject("SYMBOL_HELD_OR_PENDING");
        decimal reservedMargin=heldMargin+pendingMargin;
        decimal reservedRisk=heldRisk+pendingRisk+proposal.ExtraCorrelatedRiskEur;
        if(reservedMargin>=marginCap)
            return Reject("PENDING_PLUS_HELD_MARGIN_CAP");
        if(reservedRisk>=riskCap)
            return Reject("PENDING_PLUS_HELD_STOP_CAP");
        decimal allowedRisk=Math.Min(
            MaximumTradeStopFraction*equity,
            riskCap-reservedRisk);
        decimal allowedMargin=marginCap-reservedMargin;
        if(allowedMargin<proposal.MinimumUnits*proposal.MarginPerUnit)
            return Reject("PENDING_PLUS_HELD_MARGIN_CAP");
        if(allowedRisk<proposal.MinimumUnits*proposal.RiskEurPerUnit)
            return Reject("PENDING_PLUS_HELD_STOP_CAP");
        decimal candidate=Math.Min(proposal.MaximumUnits,Math.Min(
            allowedMargin/proposal.MarginPerUnit,
            allowedRisk/proposal.RiskEurPerUnit));
        if(candidate<proposal.MinimumUnits)
            return Reject("VOLUME_BELOW_ORIGINAL_MINIMUM");
        // Legal cTrader lot grid: MinimumUnits + exact StepUnits multiples.
        decimal steps=Math.Floor((candidate-proposal.MinimumUnits)/proposal.StepUnits);
        decimal units=proposal.MinimumUnits+steps*proposal.StepUnits;
        decimal newMargin=units*proposal.MarginPerUnit;
        decimal newRisk=units*proposal.RiskEurPerUnit;
        decimal afterMargin=reservedMargin+newMargin;
        decimal afterRisk=heldRisk+pendingRisk+newRisk+proposal.ExtraCorrelatedRiskEur;
        if(afterMargin>marginCap||afterRisk>riskCap||
           newRisk>MaximumTradeStopFraction*equity)
            throw new InvalidOperationException("PAV1_INTERNAL_RISK_ROUNDING_OR_ADMISSION_BREACH");
        return new("ADMIT",equity,heldMargin,pendingMargin,
            heldRisk,pendingRisk,marginCap,riskCap,units,newMargin,newRisk,
            afterMargin,afterRisk,true);
    }

    /// <summary>
    /// Called before an OPEN_FILL: the pending reservation is still in the
    /// book, so do NOT add it a second time. A reduced equity can force
    /// cancellation/expiry instead of financing the old requested volume.
    /// </summary>
    public static bool RevalidatePendingFill(
        decimal? currentEquityEur,bool marksVerified,
        IReadOnlyCollection<Commitment> held,
        IReadOnlyCollection<Commitment> pendingOpen,
        string pendingPositionId)
    {
        if(!marksVerified||currentEquityEur is not >0m)return false;
        var all=held.Concat(pendingOpen).ToArray();
        if(pendingOpen.Count(x=>x.PositionId==pendingPositionId)!=1)return false;
        decimal margin=all.Sum(x=>x.MarginEur),risk=all.Sum(x=>x.ReservedStopRiskEur);
        return margin<=currentEquityEur.Value*MaximumMarginFraction&&
            risk<=currentEquityEur.Value*MaximumAggregateStopFraction;
    }
}