using cAlgo.API;
using Mxm.Core;

namespace cAlgo.Robots;

[Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
public class MxmCloud : Robot
{
    private string _lastMode = "";
    private bool _transientFault;

    protected override void OnStart()
    {
        // The actual delivered .algo is OBSERVATION ONLY: no order code,
        // no live/demo permission and no external runtime dependencies.
        // Timer resumes native reconciliation after a recoverable exception.
        Timer.Start(15);
        ObserveNative();
    }

    protected override void OnTimer()
    {
        ObserveNative();
    }

    protected override void OnException(System.Exception exception)
    {
        // Do not log account data, arbitrary exception contents or secrets.
        // A subsequent successful native observation clears transient state.
        _transientFault = true;
        Print("MXM native observation exception; scheduled auto-reconciliation continues.");
    }

    private void ObserveNative()
    {
        try
        {
            var positions=Positions.ToArray();
            var pending=PendingOrders.ToArray();
            var closed=History.ToArray();
            var historicalOrders=HistoricalOrders.ToArray();
            var transactions=Transactions.ToArray();
            var symbols=positions.Select(x=>x.SymbolName)
                .Concat(pending.Select(x=>x.SymbolName))
                .Append(SymbolName)
                .Distinct(System.StringComparer.Ordinal)
                .ToArray();
            var lanes=symbols.Select(symbol=>new RecoveryLaneEvidence(
                symbol,
                // A price snapshot on another symbol must be checked separately.
                symbol==SymbolName && Symbol.Bid>0 && Symbol.Ask>=Symbol.Bid,
                false, _transientFault, false, false, null, null)).ToArray();
            var snapshot=new RecoveryPortfolioEvidence(
                (decimal)Account.Equity,(decimal)Account.FreeMargin,null,
                // Enumerating native surfaces on a single poll is NOT
                // proof of complete historical in-flight outcome recovery,
                // cashflow reconciliation or certified lifetime equity peak.
                false,false,false,0m,0m,0);
            var result=SelectiveRecovery.Assess(snapshot,lanes);
            var mode=result.Status;
            if(mode!=_lastMode)
            {
                Print("MXM observation-only recovery: {0}; lanes {1}; native evidence {2}/{3}/{4}/{5}/{6}; orders disabled.",
                    mode,lanes.Length,positions.Length,pending.Length,
                    closed.Length,historicalOrders.Length,transactions.Length);
                _lastMode=mode;
            }
            _transientFault=false; // only the transient observation fault clears
        }
        catch(System.Exception)
        {
            _transientFault=true;
            if(_lastMode!="OBSERVATION_RETRY")
            {
                Print("MXM native observation read unavailable; retry on timer, no orders.");
                _lastMode="OBSERVATION_RETRY";
            }
        }
    }
}
