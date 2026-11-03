using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace Mxm.Core;

public sealed record BrokerOrderIdentity(string OrderId,string ClientIntentId,string PositionId,string Symbol,int Side,
    decimal RequestedUnits,decimal ExecutedUnits,bool? Closing,string Status,long UpdatedAt);
public sealed record BrokerDealIdentity(string DealId,string OrderId,string PositionId,string Symbol,int Side,
    decimal Units,bool Closing,long At);
public sealed record BrokerPositionIdentity(string PositionId,string Symbol,int Side,decimal Units);
public sealed record LocalIntentIdentity(string IntentId,string OrderId,string PositionId,string Symbol,int Side,
    decimal RequestedUnits,bool Closing,long SubmittedAt,string LedgerPositionId="");
public sealed record BrokerIdentitySnapshot(string AccountBinding,long At,long HistoryFrom,long HistoryThrough,
    bool InventoryStable,bool OrdersComplete,bool DealsComplete,BrokerOrderIdentity[] Orders,BrokerDealIdentity[] Deals,
    BrokerPositionIdentity[] Positions);
public sealed record IdentityIntentResult(string IntentId,string OrderId,string PositionId,string State,decimal ConfirmedUnits,
    bool PositiveTerminalEvidence,bool LedgerImportRequired);
public sealed record IdentityReconciliationResult(bool SnapshotConsistent,bool HistoryRangeComplete,int OpenPositions,
    int BrokerOrders,int BrokerDeals,int UnattributedPositions,int UnresolvedIntents,string[] Reasons,IdentityIntentResult[] Intents,
    bool BrokerCashReconciled=false,bool LifetimeHistoryProven=false,bool OrdersEnabled=false);

// Positive broker facts are required. An absent order/deal is never cancellation.
// Identity validation does NOT import money, fabricate fills or certify a peak.
public static class BrokerIdentityReconciliation
{
    public static IdentityReconciliationResult Assess(BrokerIdentitySnapshot s,LocalIntentIdentity[] intents)
    {
        var errors=new List<string>();
        if(string.IsNullOrWhiteSpace(s.AccountBinding) || s.At<0 || s.HistoryFrom<0 || s.HistoryThrough<s.HistoryFrom || s.HistoryThrough>s.At)
            errors.Add("INVALID_ACCOUNT_OR_HISTORY_RANGE");
        T[] Unique<T>(T[] rows,Func<T,string> id)
        {
            foreach(var g in rows.GroupBy(id))if(string.IsNullOrWhiteSpace(g.Key) || g.Select(x=>JsonSerializer.Serialize(x)).Distinct().Count()!=1)
                errors.Add("CONFLICTING_OR_EMPTY_BROKER_ID");
            return rows.GroupBy(id).Select(g=>g.First()).ToArray();
        }
        var orders=Unique(s.Orders,x=>x.OrderId);var deals=Unique(s.Deals,x=>x.DealId);var positions=Unique(s.Positions,x=>x.PositionId);
        if(intents.Select(x=>x.IntentId).Distinct().Count()!=intents.Length || intents.Any(x=>string.IsNullOrWhiteSpace(x.IntentId) || x.RequestedUnits<=0 || x.Side is not (-1 or 1) || x.SubmittedAt>s.At))
            errors.Add("INVALID_LOCAL_INTENT_IDENTITY");
        if(orders.Any(x=>x.RequestedUnits<=0 || x.ExecutedUnits<0 || x.ExecutedUnits>x.RequestedUnits || x.Side is not (-1 or 1) || x.UpdatedAt>s.At) ||
            deals.Any(x=>x.Units<=0 || x.At>s.At || x.Side is not (-1 or 1)) || positions.Any(x=>x.Units<=0 || x.Side is not (-1 or 1)))
            errors.Add("INVALID_BROKER_VOLUME_OR_CLOCK");
        foreach(var d in deals)
        {
            var o=orders.FirstOrDefault(x=>x.OrderId==d.OrderId);
            if(o==null || o.PositionId!=d.PositionId || o.Symbol!=d.Symbol || o.Side!=d.Side || o.Closing!=d.Closing)
                errors.Add("DEAL_ORDER_POSITION_LINK_MISMATCH_OR_HISTORY_GAP");
        }
        var results=new List<IdentityIntentResult>();
        foreach(var intent in intents)
        {
            var matching=orders.Where(o=>!string.IsNullOrEmpty(intent.OrderId)?o.OrderId==intent.OrderId:o.ClientIntentId==intent.IntentId).ToArray();
            if(matching.Length!=1){results.Add(new(intent.IntentId,"",intent.PositionId,"UNKNOWN_NO_RESUBMIT",0,false,false));continue;}
            var o=matching[0];var executions=deals.Where(d=>d.OrderId==o.OrderId).ToArray();decimal units=executions.Sum(d=>d.Units);
            bool binding=o.Symbol==intent.Symbol && o.Side==intent.Side && o.RequestedUnits==intent.RequestedUnits && o.Closing==intent.Closing &&
                (string.IsNullOrEmpty(intent.PositionId)||intent.PositionId==o.PositionId) && o.UpdatedAt>=intent.SubmittedAt &&
                executions.All(d=>d.At>=intent.SubmittedAt) && (!string.IsNullOrEmpty(intent.OrderId)||o.ClientIntentId==intent.IntentId);
            bool full=s.OrdersComplete && s.DealsComplete && s.InventoryStable && s.HistoryFrom<=intent.SubmittedAt && s.HistoryThrough>=o.UpdatedAt;
            bool terminal=o.Status is "FILLED" or "CANCELLED" or "REJECTED" or "EXPIRED";
            bool matches=units==o.ExecutedUnits && (o.Status!="FILLED" || units==o.RequestedUnits) && (o.Status!="REJECTED" || units==0);
            bool affirmative=binding && full && terminal && matches && errors.Count==0;
            string status=!binding?"IDENTITY_CONFLICT":!full || !matches?"INCOMPLETE_EXECUTION_EVIDENCE":!terminal?"ACTIVE_OR_UNKNOWN_NO_RESUBMIT":
                units>0?"TERMINAL_EXECUTIONS_REQUIRE_LEDGER_IMPORT":"AFFIRMATIVE_UNFILLED_TERMINAL";
            results.Add(new(intent.IntentId,o.OrderId,o.PositionId,status,units,affirmative,affirmative && units>0));
        }
        var attributed=intents.Where(i=>!string.IsNullOrEmpty(i.PositionId)).Select(i=>i.PositionId)
            .Concat(results.Where(r=>r.PositiveTerminalEvidence || r.State=="ACTIVE_OR_UNKNOWN_NO_RESUBMIT"&&r.ConfirmedUnits>0).Select(r=>r.PositionId)).ToHashSet(StringComparer.Ordinal);
        foreach(string id in attributed.Where(x=>!string.IsNullOrEmpty(x)))
        {
            var localOpening=intents.Where(x=>!x.Closing && x.PositionId==id).ToArray();
            if(localOpening.Length==0 || localOpening.Min(x=>x.SubmittedAt)<s.HistoryFrom || !s.DealsComplete)continue;
            var related=deals.Where(x=>x.PositionId==id).ToArray();decimal remaining=related.Sum(x=>x.Closing?-x.Units:x.Units);
            var present=positions.FirstOrDefault(x=>x.PositionId==id);
            if(remaining<0 || remaining!=(present?.Units??0) || present!=null && related.Any(x=>x.Symbol!=present.Symbol || x.Side!=(x.Closing?-present.Side:present.Side)))
                errors.Add("POSITION_PARTIAL_VOLUME_OR_SIDE_NOT_RECONCILED");
        }
        int foreign=positions.Count(p=>!attributed.Contains(p.PositionId));
        if(!s.InventoryStable)errors.Add("CURRENT_INVENTORY_UNSTABLE_OR_UNPROVEN");
        if(!s.OrdersComplete || !s.DealsComplete)errors.Add("BOUNDED_HISTORY_INCOMPLETE");
        if(foreign>0)errors.Add("UNATTRIBUTED_OPEN_POSITIONS");
        return new(errors.Count==0,s.OrdersComplete&&s.DealsComplete,positions.Length,orders.Length,deals.Length,foreign,
            results.Count(x=>!x.PositiveTerminalEvidence || x.LedgerImportRequired),errors.Distinct().ToArray(),results.ToArray());
    }
}

public sealed record NativeSessionReport(IdentityReconciliationResult Identity,LedgerSummary ModelLedger,
    bool JournalContinuityProven,bool ModelCashMatchesBroker,bool PositionInventoryMatchesModel,bool CanConsiderNewExposure,string Status,
    bool GlobalDrawdownCertified=false,bool OrdersEnabled=false,string MonetaryDomain="MODEL_REPLAY");
public sealed partial class NativeFundedSession
{
    public string AccountBinding {get;}
    public NativeFundedLedger Ledger {get;private set;}
    public LocalIntentIdentity[] Intents {get;private set;}
    public bool JournalContinuityProven {get;}
    // New/missing journals never silently acquire historical continuity.
    public NativeFundedSession(string accountBinding,NativeFundedLedger? ledger=null,LocalIntentIdentity[]? intents=null,bool journalContinuityProven=false)
    {
        if(string.IsNullOrWhiteSpace(accountBinding))throw new ArgumentException("SESSION_ACCOUNT_BINDING");
        AccountBinding=accountBinding;Ledger=ledger??new();Intents=intents??Array.Empty<LocalIntentIdentity>();JournalContinuityProven=journalContinuityProven;
    }
    public NativeSessionReport Observe(BrokerIdentitySnapshot snapshot,decimal? brokerCash)
    {
        if(snapshot.AccountBinding!=AccountBinding)throw new InvalidOperationException("SESSION_ACCOUNT_MISMATCH");
        var identity=BrokerIdentityReconciliation.Assess(snapshot,Intents);var book=Ledger.Summary(snapshot.At);
        var settled=identity.Intents.Select(r=>{
            var executions=snapshot.Deals.Where(d=>d.OrderId==r.OrderId).ToArray();
            bool imported=executions.Length>0&&executions.All(d=>Ledger.FactHashes.ContainsKey("MONEY/deal/"+d.DealId));
            return imported?r with {LedgerImportRequired=false,State=r.PositiveTerminalEvidence?"TERMINAL_EXECUTIONS_MONETARILY_RECONCILED":"ACTIVE_PARTIAL_BOOKED_NO_RESUBMIT"}:r;
        }).ToArray();
        identity=identity with {Intents=settled,UnresolvedIntents=settled.Count(r=>!r.PositiveTerminalEvidence||r.LedgerImportRequired)};
        bool cash=brokerCash.HasValue && Math.Abs(book.CashEur-brokerCash.Value)<.00000001m;
        var modelPositions=Ledger.PositionSnapshot();
        var bindings=Intents.Where(i=>!string.IsNullOrEmpty(i.LedgerPositionId)).Select(i=>{
            string position=!string.IsNullOrEmpty(i.PositionId)?i.PositionId:identity.Intents.FirstOrDefault(r=>r.IntentId==i.IntentId&&r.PositiveTerminalEvidence)?.PositionId??"";
            return (Model:i.LedgerPositionId,Broker:position);
        }).Where(x=>!string.IsNullOrEmpty(x.Broker)).Distinct().ToArray();
        bool positions=bindings.GroupBy(x=>x.Model).All(g=>g.Count()==1)&&bindings.GroupBy(x=>x.Broker).All(g=>g.Count()==1)&&
            modelPositions.Length==snapshot.Positions.Length && modelPositions.All(p=>{
                var bind=bindings.FirstOrDefault(x=>x.Model==p.Id);var actual=snapshot.Positions.FirstOrDefault(x=>x.PositionId==bind.Broker);
                return actual!=null && actual.Symbol==p.Symbol && actual.Side==p.Side && actual.Units==p.Units;
            });
        // Reconciliation has no authority to invent missing cash flows, import
        // unpriced fills or promote the observed peak to a lifetime certificate.
        return new(identity,book,JournalContinuityProven,cash,positions,false,
            !JournalContinuityProven?"PROTECTIVE_JOURNAL_CONTINUITY_UNKNOWN":!identity.SnapshotConsistent || identity.UnresolvedIntents>0?"PROTECTIVE_BROKER_IDENTITIES_UNRESOLVED":
            !positions?"PROTECTIVE_MODEL_BROKER_POSITION_MISMATCH":book.LiquidationEquityEur is null?"PROTECTIVE_FLOATING_VALUATION_MISSING":!cash?"PROTECTIVE_CASH_MISMATCH":"PROTECTIVE_PEAK_AND_EXECUTION_AUTHORITY_UNPROVEN",MonetaryDomain:Ledger.MonetaryDomain);
    }
    static string Hash(string x)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(x))).ToLowerInvariant();
    public string Checkpoint()
    {
        string payload=JsonSerializer.Serialize(new {Version=1,AccountBinding,Ledger=Ledger.Checkpoint(),Intents,JournalContinuityProven});
        return JsonSerializer.Serialize(new {Payload=payload,Sha256=Hash(payload)});
    }
    public static NativeFundedSession Restore(string checkpoint,string expectedAccountBinding)
    {
        using var d=JsonDocument.Parse(checkpoint);string payload=d.RootElement.GetProperty("Payload").GetString()!;
        if(Hash(payload)!=d.RootElement.GetProperty("Sha256").GetString())throw new ArgumentException("SESSION_CHECKPOINT_HASH");
        using var p=JsonDocument.Parse(payload);var root=p.RootElement;
        if(root.GetProperty("Version").GetInt32()!=1 || root.GetProperty("AccountBinding").GetString()!=expectedAccountBinding)
            throw new ArgumentException("SESSION_CHECKPOINT_ACCOUNT_OR_VERSION");
        return new(expectedAccountBinding,NativeFundedLedger.Restore(root.GetProperty("Ledger").GetString()!),
            JsonSerializer.Deserialize<LocalIntentIdentity[]>(root.GetProperty("Intents").GetRawText()),root.GetProperty("JournalContinuityProven").GetBoolean());
    }
}
