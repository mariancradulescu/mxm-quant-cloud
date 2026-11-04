using cAlgo.API;
using Mxm.Core;

namespace cAlgo.Robots;

[Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
public class MxmCloud : Robot
{
    private string _lastMode = "";
    private bool _transientFault;
    private NativeFundedSession? _fundedSession;
    private string _accountBinding="";
    private bool _journalFault;
    private string _lastInventory="";
    private const string JournalKey="MXM_NATIVE_FUNDED_SESSION_V1";
    private static long Stamp(System.DateTime t)=>new System.DateTimeOffset(System.DateTime.SpecifyKind(t,System.DateTimeKind.Utc)).ToUnixTimeMilliseconds();


    protected override void OnStart()
    {
        // The actual delivered .algo is OBSERVATION ONLY: no order code,
        // no live/demo permission and no external runtime dependencies.
        // Timer resumes native reconciliation after a recoverable exception.
        _accountBinding=System.Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes("ctrader-native-account:"+Account.Number))).ToLowerInvariant();
        try {
            var saved=LocalStorage.GetString(JournalKey,LocalStorageScope.Instance);
            _fundedSession=string.IsNullOrEmpty(saved)?new NativeFundedSession(_accountBinding):NativeFundedSession.Restore(saved,_accountBinding);
        } catch { _journalFault=true; } // never overwrite a corrupt/wrong-account journal
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
            // Native balances are in the deposit asset, not automatically EUR.
            if(Account.Asset.Name!="EUR")
            {
                if(_lastMode!="PROTECTIVE_DEPOSIT_CURRENCY_UNVERIFIED")
                    Print("MXM protective observation: EUR deposit currency not established; no monetary import.");
                _lastMode="PROTECTIVE_DEPOSIT_CURRENCY_UNVERIFIED";
                return;
            }
            var positions=Positions.ToArray();
            var pending=PendingOrders.ToArray();
            var closed=History.ToArray();
            var historicalOrders=HistoricalOrders.ToArray();
            var transactions=Transactions.ToArray();
            var dealRows=positions.SelectMany(p=>p.Deals)
                .Concat(closed.Select(t=>t.ClosingDeal)).SelectMany(d=>d.Closing.Append(d)).ToArray();
            var mappedDeals=dealRows.Where(d=>d.VolumeInUnits>0).Select(d=>new BrokerDealIdentity(
                d.Id.ToString(),d.OrderId.ToString(),d.PositionId.ToString(),d.SymbolName,d.TradeType==TradeType.Buy?1:-1,
                (decimal)d.VolumeInUnits,d.PositionImpact==DealPositionImpact.Closing,Stamp(d.ExecutionTime))).ToArray();
            var mappedOrders=historicalOrders.Select(o=>{
                var related=mappedDeals.Where(d=>d.OrderId==o.Id.ToString()).ToArray();
                bool? closing=related.Length>0&&related.All(d=>d.Closing==related[0].Closing)?related[0].Closing:null;
                return new BrokerOrderIdentity(o.Id.ToString(),"",o.PositionId?.ToString()??"",o.SymbolName,o.TradeType==TradeType.Buy?1:-1,
                    (decimal)o.VolumeInUnits,(decimal)(o.FilledVolumeInUnits??0),closing,o.Status.ToString().ToUpperInvariant(),Stamp(o.FilledTime??o.SubmittedTime));
            }).Concat(pending.Select(o=>new BrokerOrderIdentity(o.Id.ToString(),"","",o.SymbolName,o.TradeType==TradeType.Buy?1:-1,
                (decimal)o.VolumeInUnits,0,null,"ACTIVE",Stamp(Server.TimeInUtc)))).ToArray();
            var mappedPositions=positions.Select(p=>new BrokerPositionIdentity(p.Id.ToString(),p.SymbolName,p.TradeType==TradeType.Buy?1:-1,(decimal)p.VolumeInUnits)).ToArray();
            string inventory=System.Text.Json.JsonSerializer.Serialize(new {mappedPositions,Pending=pending.Select(p=>p.Id).OrderBy(x=>x).ToArray()});
            var broker=new BrokerIdentitySnapshot(_accountBinding,Stamp(Server.TimeInUtc),0,Stamp(Server.TimeInUtc),
                inventory==_lastInventory,false,false,mappedOrders,mappedDeals,mappedPositions);
            _lastInventory=inventory;
            // Current surfaces do not prove initial funding, complete cashflows,
            // per-deal monetary legs or funding history. Keep those facts UNKNOWN.
            // This attempts the same atomic recovery gate; it cannot invent money.
            var money=_fundedSession?.ReconcileMoney(new MoneyRecoveryBatch(_accountBinding,"BROKER_EXECUTION_FACT",broker,
                System.Array.Empty<AttributedMoneyFact>(),(decimal)Account.Balance,false,false,false,false,null,null));
            var funded=_fundedSession?.Observe(broker,(decimal)Account.Balance);
            if(!_journalFault && _fundedSession!=null) {
                LocalStorage.SetString(JournalKey,_fundedSession.Checkpoint(),LocalStorageScope.Instance);
                LocalStorage.Flush(LocalStorageScope.Instance);
            }
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
            var mode=_journalFault?"PROTECTIVE_JOURNAL_UNAVAILABLE":funded?.Status??result.Status;
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
