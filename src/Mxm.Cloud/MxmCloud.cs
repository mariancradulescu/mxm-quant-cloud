using cAlgo.API;
using Mxm.Core;

namespace cAlgo.Robots;

[Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
public class MxmCloud : Robot
{
    protected override void OnStart()
    {
        // Native broker surfaces, never LocalStorage. Enumeration alone does not
        // establish completeness, historical equity peaks or in-flight outcomes.
        var positions = Positions.ToArray();
        var pending = PendingOrders.ToArray();
        var closed = History.ToArray();
        var historicalOrders = HistoricalOrders.ToArray();
        var transactions = Transactions.ToArray();
        var evidence = new RecoveryEvidence((decimal)Account.Equity, 200m, null,
            false, false, false, true, positions.Any(p => p.Label != "MXM"));
        var decision = Recovery.Assess(evidence);
        // No account IDs, balances, trade records or symbols printed.
        Print("MXM observation build: {0}; {1}. Native snapshots: {2}/{3}/{4}/{5}/{6}.",
            decision.Mode, decision.Reason, positions.Length, pending.Length,
            closed.Length, historicalOrders.Length, transactions.Length);
        Stop(); // This diagnostic build has no execution path or trade parameters.
    }
}
