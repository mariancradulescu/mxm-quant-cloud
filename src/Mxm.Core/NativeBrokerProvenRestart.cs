namespace Mxm.Core;

// This bridge reconstructs original broker-order intent identities when BOTH
// full authenticated chronology and complete monetary per-deal evidence exist.
// A missing local checkpoint never supplies evidence by itself.
public sealed record BrokerProvenRestartReport(
    bool Adopted,string Status,NativeFundedSession? Recovered,
    MoneyRecoveryReport? Monetary,bool OrdersEnabled=false);

public sealed partial class NativeFundedSession
{
    public static BrokerProvenRestartReport RebuildFromProvenBrokerHistory(
        MoneyRecoveryBatch input,BrokerNativeCashflow[] nativeCashflows)
    {
        BrokerProvenRestartReport Reject(string reason)=>
            new(false,reason,null,null);
        if(input.Domain!="BROKER_EXECUTION_FACT" ||
            string.IsNullOrWhiteSpace(input.AccountBinding) ||
            input.Snapshot.AccountBinding!=input.AccountBinding ||
            input.Snapshot.At<=0 || input.Snapshot.HistoryFrom<0 ||
            input.Snapshot.HistoryThrough<input.Snapshot.At-2000 ||
            !input.Snapshot.InventoryStable || !input.Snapshot.OrdersComplete ||
            !input.Snapshot.DealsComplete || !input.InitialCapitalProven ||
            !input.CashflowHistoryComplete || !input.FinancingHistoryComplete ||
            input.AdditionalExternalCashflowDetected || input.FundingRecords is null)
            return Reject("BROKER_RESTART_COMPLETE_HISTORY_NOT_ATTESTED");
        if(nativeCashflows is null || nativeCashflows.Length!=1)
            return Reject("BROKER_RESTART_ORIGINAL_FUNDING_NOT_EXCLUSIVE");
        var founding=nativeCashflows[0];
        if(founding.Kind!="DEPOSIT" || founding.AmountEur!=OwnerRiskAuthority.InitialCapitalEur ||
            Math.Abs(founding.BalanceAfterEur-OwnerRiskAuthority.InitialCapitalEur)>.01m ||
            string.IsNullOrWhiteSpace(founding.Id) || founding.At<=0 ||
            founding.At>input.Snapshot.At || input.Snapshot.HistoryFrom>founding.At)
            return Reject("BROKER_RESTART_PROSPECTIVE_FOUNDING_CAPITAL_UNPROVEN");
        var orders=input.Snapshot.Orders;
        if(orders.Length==0 || input.Facts.Length==0 ||
           orders.Select(x=>x.OrderId).Distinct(StringComparer.Ordinal).Count()!=orders.Length ||
           orders.Any(o=>o.SubmittedAt is not long sent ||
               sent<founding.At || sent>o.UpdatedAt ||
               o.PositionId.Length==0 || o.Closing is null ||
               o.Status is not ("FILLED" or "CANCELLED" or "EXPIRED" or "REJECTED") ||
               o.RequestedUnits<=0 || o.ExecutedUnits<0 ||
               o.ExecutedUnits>o.RequestedUnits ||
               o.Status=="FILLED" && o.ExecutedUnits!=o.RequestedUnits ||
               o.Status=="REJECTED" && o.ExecutedUnits!=0))
            return Reject("BROKER_RESTART_SUBMITTED_ORDER_OR_TERMINAL_IDENTITY_UNKNOWN");
        // All historical deal facts, including expenses and funding, must be
        // positively supplied, not made up from current balance or position PnL.
        var dealGroups=input.Snapshot.Deals.GroupBy(d=>d.OrderId)
            .ToDictionary(g=>g.Key,g=>g.ToArray(),StringComparer.Ordinal);
        if(orders.Any(o=>{
            bool hasDeals=dealGroups.TryGetValue(o.OrderId,out var ds);
            if(o.ExecutedUnits==0)return hasDeals; // positive unfilled terminal
            return !hasDeals || ds!.Sum(d=>d.Units)!=o.ExecutedUnits ||
                ds!.Any(d=>d.At<o.SubmittedAt || d.At>o.UpdatedAt ||
                    d.PositionId!=o.PositionId || d.Symbol!=o.Symbol ||
                    d.Side!=o.Side || d.Closing!=o.Closing);
        }))
            return Reject("BROKER_RESTART_DEALS_NOT_POSITIVELY_LINKED");
        var facts=input.Facts.Where(f=>f.Kind is "OPEN" or "CLOSE").ToArray();
        if(facts.Length!=input.Snapshot.Deals.Length ||
           facts.Select(f=>f.DealId).Distinct(StringComparer.Ordinal).Count()!=facts.Length ||
           input.Snapshot.Deals.Any(d=>!facts.Any(f=>f.DealId==d.DealId)))
            return Reject("BROKER_RESTART_PER_DEAL_MONEY_MISSING");
        var mappings=facts.GroupBy(f=>f.PositionId).ToDictionary(g=>g.Key,
            g=>g.Select(f=>f.LedgerPositionId).Distinct(StringComparer.Ordinal).ToArray(),
            StringComparer.Ordinal);
        if(mappings.Any(x=>x.Value.Length!=1 || string.IsNullOrWhiteSpace(x.Value[0])))
            return Reject("BROKER_RESTART_LEDGER_POSITION_BINDING_AMBIGUOUS");
        var intents=orders.Select(o=>new LocalIntentIdentity(
            "BROKER_CONFIRMED_ORDER/"+o.OrderId,o.OrderId,o.PositionId,o.Symbol,
            o.Side,o.RequestedUnits,o.Closing!.Value,o.SubmittedAt!.Value,
            mappings.TryGetValue(o.PositionId,out var ledger)?ledger[0]:"")).ToArray();
        if(intents.Any(i=>orders.Any(o=>o.OrderId==i.OrderId &&
            o.ExecutedUnits>0 && string.IsNullOrWhiteSpace(i.LedgerPositionId))))
            return Reject("BROKER_RESTART_OPEN_POSITION_LEDGER_ID_UNKNOWN");
        var candidate=new NativeFundedSession(input.AccountBinding,
            intents:intents,journalContinuityProven:true);
        var result=candidate.ReconcileMoney(input);
        if(!result.Adopted)return new(false,
            "BROKER_RESTART_MONETARY_RECONCILIATION_REJECTED",null,result);
        // Broker recovery only. Missing full lifetime peak, future costs and
        // stopout/position-management evidence remain separate hard gates.
        return new(true,"BROKER_RESTART_MONETARY_LEDGER_RECONSTRUCTED_PEAK_UNPROVEN",
            candidate,result);
    }
}
