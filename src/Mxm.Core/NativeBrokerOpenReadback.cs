namespace Mxm.Core;

// Non-flat broker recovery is deliberately a read-only observation of EXISTING
// positions. No journal, execution cost, closing deal or peak is inferred.
public sealed record BrokerOpenPositionFact(
    string PositionId,string Symbol,int Side,decimal Units,long EntryAt,
    decimal EntryPrice,decimal MarginEur,decimal NetPnlEur,
    decimal? StopLoss,decimal? TakeProfit);

public sealed record BrokerOpenReadback(
    string AccountBinding,long At,bool InventoryStable,
    decimal BalanceEur,decimal EquityEur,decimal MarginEur,decimal FreeMarginEur,
    decimal CreditEur,int PendingOrders,BrokerOpenPositionFact[] Positions);

public sealed record BrokerOpenReadbackReport(
    bool OpenExposureMonitoringReady,bool BrokerEquityIdentityMatched,
    bool ExecutionHistoryReconstructed,bool LifetimePeakCertified,bool OrdersEnabled,
    int PositionsObserved,string Status);

public sealed partial class NativeFundedSession
{
    // A lost Cloud LocalStorage checkpoint cannot erase an actual open exposure.
    // Inventory must be unchanged over two broker reads; the present monetary
    // mark must reconcile independently at a single read. No model-ledger entry
    // is invented and no broker intent is marked completed from mere absence.
    public BrokerOpenReadbackReport ReconcileBrokerOpen(BrokerOpenReadback b)
    {
        BrokerOpenReadbackReport Reject(string status)=>new(
            false,false,false,false,false,b.Positions?.Length??0,status);
        if(b.AccountBinding!=AccountBinding || b.At<=0)
            return Reject("OPEN_READBACK_ACCOUNT_OR_CLOCK_UNKNOWN");
        if(b.Positions is null || b.Positions.Length==0)
            return Reject("OPEN_READBACK_NO_OPEN_POSITIONS_USE_FLAT_PATH");
        if(!b.InventoryStable)
            return Reject("OPEN_READBACK_INVENTORY_PENDING_STABLE_REPOLL");
        if(b.PendingOrders<0 || b.BalanceEur<=0m || b.EquityEur<=0m ||
            b.MarginEur<0m || b.FreeMarginEur<0m || b.CreditEur<0m)
            return Reject("OPEN_READBACK_INVALID_ACCOUNT_MARK");
        if(b.Positions.Any(p=>string.IsNullOrWhiteSpace(p.PositionId) ||
            string.IsNullOrWhiteSpace(p.Symbol) || p.Side is not (-1 or 1) ||
            p.Units<=0m || p.EntryAt<=0 || p.EntryAt>b.At ||
            p.EntryPrice<=0m || p.MarginEur<0m ||
            p.StopLoss is <=0m || p.TakeProfit is <=0m) ||
            b.Positions.Select(p=>p.PositionId).Distinct(StringComparer.Ordinal).Count()!=b.Positions.Length)
            return Reject("OPEN_READBACK_DUPLICATE_OR_INVALID_POSITION");
        // The account margin is authoritative: individual margin requirements
        // need not add up under hedged exposure. This does NOT certify that
        // positions could be opened again with the same margin.
        if(Math.Abs(b.EquityEur-b.MarginEur-b.FreeMarginEur)>.01m)
            return Reject("OPEN_READBACK_FREE_MARGIN_MISMATCH");
        if(Math.Abs(b.BalanceEur+b.CreditEur+
                    b.Positions.Sum(p=>p.NetPnlEur)-b.EquityEur)>.01m)
            return Reject("OPEN_READBACK_BROKER_FLOATING_EQUITY_MISMATCH");
        // Foreign or prior-instance positions remain monitored, not silently
        // attributed to this bot. Pending orders stay unresolved.
        return new(true,true,false,false,false,b.Positions.Length,
            b.PendingOrders>0
                ?"OPEN_BROKER_EXPOSURES_MONITORED_PENDING_ORDERS_UNRESOLVED"
                :"OPEN_BROKER_EXPOSURES_MONITORED_EXECUTION_HISTORY_UNPROVEN");
    }
}
