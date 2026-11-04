using Mxm.Core;

internal static class BrokerOpenReadbackChecks
{
    public static void Run(Action<bool,string> check)
    {
        const string account="SYNTH_RESTART_ACCOUNT";
        var two=new[]{
            new BrokerOpenPositionFact("pos1","EURUSD",1,1000m,1000,1.08m,30m,1m,1.05m,1.12m),
            new BrokerOpenPositionFact("pos2","USDJPY",-1,1000m,1100,148m,40m,-3m,null,null)
        };
        var observed=new BrokerOpenReadback(account,6000,true,200m,198m,70m,128m,0m,0,two);
        var session=new NativeFundedSession(account);
        var first=session.ReconcileBrokerOpen(observed with {InventoryStable=false});
        check(!first.OpenExposureMonitoringReady&&!first.OrdersEnabled,
            "first read after Cloud restart cannot certify a stable native inventory");
        var stable=session.ReconcileBrokerOpen(observed);
        check(stable.OpenExposureMonitoringReady&&stable.BrokerEquityIdentityMatched&&
              stable.PositionsObserved==2&&!stable.ExecutionHistoryReconstructed&&
              !stable.LifetimePeakCertified&&!stable.OrdersEnabled,
            "two actual broker open positions can be monitored without reconstructing their missing execution journal");
        check(session.Ledger.Summary().CashEur==200m&&session.Ledger.Summary().OpenPositions==0,
            "unproven open fills never mutate the existing native EUR200 ledger or invent recovered capital");
        check(session.ReconcileBrokerOpen(observed with {Positions=two.Reverse().ToArray()}).OpenExposureMonitoringReady,
            "native open positions are stable independent of collection order");
        check(!session.ReconcileBrokerOpen(observed with {AccountBinding="OTHER_ACCOUNT"}).OpenExposureMonitoringReady,
            "open exposure readback rejects incorrect broker account binding");
        check(!session.ReconcileBrokerOpen(observed with {EquityEur=199m}).OpenExposureMonitoringReady,
            "floating account equity cannot be substituted without current position net reconciliation");
        check(!session.ReconcileBrokerOpen(observed with {FreeMarginEur=127m}).OpenExposureMonitoringReady,
            "used margin and free margin must reconcile to current broker equity");
        check(!session.ReconcileBrokerOpen(observed with {Positions=two.Append(two[0]).ToArray()}).OpenExposureMonitoringReady,
            "duplicated position identifiers are never silently dropped");
        check(!session.ReconcileBrokerOpen(observed with {Positions=new[]{two[0] with {Units=-1m},two[1]}}).OpenExposureMonitoringReady,
            "invalid open volumes cannot be adopted");
        check(!session.ReconcileBrokerOpen(observed with {Positions=new[]{two[0] with {EntryAt=7000},two[1]}}).OpenExposureMonitoringReady,
            "open entry clock cannot follow the broker snapshot");
        check(!session.ReconcileBrokerOpen(observed with {Positions=Array.Empty<BrokerOpenPositionFact>()}).OpenExposureMonitoringReady,
            "flat account recovery must take the separately validated flat path");
        check(session.ReconcileBrokerOpen(observed with {PendingOrders=1}).Status.Contains("PENDING_ORDERS_UNRESOLVED"),
            "pending broker orders remain unresolved despite positively observed open positions");
        // A stressed existing position must remain observable after restart.
        // Refusing to look at it because equity/free margin is negative would
        // blind risk monitoring at exactly the wrong time.
        var distressed=observed with {
            EquityEur=-5m,FreeMarginEur=-75m,
            Positions=new[]{two[0] with {NetPnlEur=-203m},two[1]}
        };
        var stressedReport=session.ReconcileBrokerOpen(distressed);
        check(stressedReport.OpenExposureMonitoringReady&&stressedReport.RequiresRiskReductionReview&&
              stressedReport.Status.Contains("DISTRESSED")&&!stressedReport.OrdersEnabled,
            "underwater broker exposure is monitored and flagged for reduction review, never new orders");
        check(session.Ledger.Summary().CashEur==200m,
            "negative observed floating equity cannot patch or reset the native monetary ledger");
        check(!session.ReconcileBrokerOpen(distressed with {FreeMarginEur=-74m}).OpenExposureMonitoringReady,
            "distressed account still needs an exact broker equity-margin-free margin identity");
        var afterCrash=new NativeFundedSession(account);
        check(afterCrash.ReconcileBrokerOpen(observed).OpenExposureMonitoringReady&&
            afterCrash.Ledger.Summary().OpenPositions==0,
            "read-only open-exposure monitoring can rehydrate from native broker facts without LocalStorage");
        check(!afterCrash.ReconcileBrokerOpen(observed with {CreditEur=3m}).OpenExposureMonitoringReady,
            "additional broker credit cannot be ignored when establishing floating equity");
    }
}
