using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

/// <summary>
/// Forward-only safety contract for a future native C# portfolio engine.
/// Original PAV1 #45192586825 remains frozen and MUST NOT be rerun with it.
/// Uses executable BID/ASK and friction at proposed model OPEN_FILL, not
/// founding or pre-fill equity, for the 70% Held+Pending margin envelope.
/// No orders, external API, synthetic broker fill or research selection.
/// </summary>
public static class NativePostFillCapitalGuard
{
    public sealed record PostFillCheck(
        bool Allowed,string Reason,
        decimal PreFillLiquidationEquityEur,
        decimal ProjectedPostFillLiquidationEquityEur,
        decimal EntryCommissionEur,decimal ProjectedExitCommissionEur,
        decimal ProjectedSpreadAndSlippageLossEur,
        decimal HeldMarginEur,decimal PendingMarginEur,
        decimal TotalReservedMarginEur,decimal MarginLimitEur,
        decimal AggregateReservedRiskEur,decimal RiskLimitEur,
        decimal ThisPositionReservedStopRiskEur,decimal SingleRiskLimitEur);

    public static PostFillCheck Assess(
        decimal? currentMarkedEquityEur,
        IReadOnlyCollection<NativePendingCapitalGate.Commitment> held,
        IReadOnlyCollection<NativePendingCapitalGate.Commitment> pendingOpen,
        string proposedPendingPositionId,int side,
        LedgerQuote currentQuote,decimal entrySlippage,
        decimal extraPossibleDebitEur=0m,decimal? exitSlippage=null)
    {
        ArgumentNullException.ThrowIfNull(held);
        ArgumentNullException.ThrowIfNull(pendingOpen);
        ArgumentNullException.ThrowIfNull(currentQuote);
        if(side is not (1 or -1)||entrySlippage<0m||exitSlippage is <0m||extraPossibleDebitEur<0m||
            currentQuote.Bid<=0m||currentQuote.Ask<currentQuote.Bid||
            currentQuote.EurCredit<=0m||currentQuote.EurDebit<currentQuote.EurCredit)
            throw new ArgumentException("POST_FILL_PRICE_OR_SIDE_INVALID");
        var proposal=pendingOpen.Where(x=>x.PositionId==proposedPendingPositionId)
            .ToArray();
        if(proposal.Length!=1 || proposal[0].Symbol!=currentQuote.Symbol)
            throw new ArgumentException("POST_FILL_PENDING_ID_OR_SYMBOL_UNKNOWN");
        var combined=held.Concat(pendingOpen).ToArray();
        if(combined.Select(x=>x.PositionId).Distinct(StringComparer.Ordinal).Count()!=
           combined.Length||combined.Any(x=>x.Units<=0m||x.MarginPerUnit<=0m||
               x.ReservedStopRiskEur<0m))
            throw new ArgumentException("POST_FILL_DUPLICATE_OR_UNVERIFIED_RESERVE");
        decimal equity=currentMarkedEquityEur??0m;
        decimal entryFee=NativeFundedLedger.Fee(currentQuote,proposal[0].Units,side);
        decimal exitFee=NativeFundedLedger.Fee(currentQuote,proposal[0].Units,-side);
        decimal entry=NativeExecutableEconomics.EntryPrice(currentQuote,side,entrySlippage);
        decimal exit=NativeExecutableEconomics.ExitPrice(
            side>0?currentQuote.Bid:currentQuote.Ask,side,exitSlippage??entrySlippage);
        decimal quoteProfit=side*(exit-entry)*proposal[0].Units;
        decimal converted=quoteProfit*(quoteProfit>=0m?
            currentQuote.EurCredit:currentQuote.EurDebit);
        decimal priceLoss=Math.Max(0m,-converted);
        decimal projected=equity-entryFee-exitFee-priceLoss-extraPossibleDebitEur;
        decimal heldMargin=held.Sum(x=>x.MarginEur);
        decimal pendingMargin=pendingOpen.Sum(x=>x.MarginEur);
        // Original historical margin unit may be lower than a current
        // source-valid quote. Revalue candidate conservatively at the larger.
        pendingMargin+=proposal[0].Units*
            Math.Max(0m,currentQuote.MarginPerUnit-proposal[0].MarginPerUnit);
        decimal totalMargin=heldMargin+pendingMargin;
        decimal risk=combined.Sum(x=>x.ReservedStopRiskEur);
        decimal cap=Math.Max(0m,projected*.70m);
        decimal riskCap=Math.Max(0m,projected*.05m);
        decimal tradeCap=Math.Max(0m,projected*.015m);
        string result=currentMarkedEquityEur is null?
            "MARKED_EQUITY_UNKNOWN":
            projected<=0m?"PROJECTED_EQUITY_NONPOSITIVE":
            totalMargin>cap?"POST_FILL_MARGIN_EXCEEDS_70PCT":
            risk>riskCap?"POST_FILL_AGGREGATE_RISK_EXCEEDS_5PCT":
            proposal[0].ReservedStopRiskEur>tradeCap?
                "POST_FILL_SINGLE_POSITION_RISK_EXCEEDS_1_5PCT":"ADMIT";
        return new(result=="ADMIT",result,equity,projected,entryFee,
            exitFee,priceLoss,heldMargin,pendingMargin,totalMargin,cap,
            risk,riskCap,proposal[0].ReservedStopRiskEur,tradeCap);
    }
}
