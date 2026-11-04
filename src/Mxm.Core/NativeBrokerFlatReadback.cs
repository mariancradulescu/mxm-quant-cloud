using System.Text.Json;
namespace Mxm.Core;

// Read-only reconstruction from native account surfaces after a lost Cloud
// checkpoint. This is one additional admission path into the SAME funded ledger,
// limited to a fully flat broker snapshot. Never invent open fills or a peak bound.
public sealed record BrokerNativeCashflow(string Id,long At,string Kind,decimal AmountEur,
    decimal BalanceAfterEur,decimal? ReportedMaximumEquityEur);
public sealed record BrokerNativeClosedTrade(string ClosingDealId,string PositionId,string Symbol,
    long EntryAt,long ClosedAt,decimal GrossEur,decimal CommissionEur,decimal SwapEur,
    decimal NetEur,decimal BalanceAfterEur);
public sealed record BrokerFlatReadback(string AccountBinding,long At,bool SnapshotStable,
    decimal BalanceEur,decimal EquityEur,decimal MarginEur,decimal CreditEur,
    int OpenPositions,int PendingOrders,BrokerNativeCashflow[] Cashflows,
    BrokerNativeClosedTrade[] Closed);
public sealed record BrokerFlatReadbackReport(bool Adopted,bool BrokerCashIdentityMatched,
    bool HistoricalEquityPeakCertified,bool CompleteBrokerHistoryCertified,
    bool DecisionResearchMayResume,bool OrdersEnabled,decimal? ReconstructedCashEur,
    decimal? ObservedPeakLowerBoundEur,string Status);

public sealed partial class NativeFundedLedger
{
    internal static NativeFundedLedger RebuildFlatBrokerHistory(BrokerFlatReadback b,
        decimal retainedObservedPeak)
    {
        var closed=b.Closed.OrderBy(x=>x.ClosedAt).ThenBy(x=>x.ClosingDealId,StringComparer.Ordinal).ToArray();
        var ledger=new NativeFundedLedger();
        var fragments=closed.Select(x=>new LedgerClosedFragment(
            x.PositionId,x.Symbol,x.EntryAt,x.ClosedAt,0,x.GrossEur,
            null,null,null,Math.Abs(x.CommissionEur),-x.SwapEur,x.NetEur,
            false,"BROKER_NATIVE_HISTORICAL_NET_NOT_FULL_EXECUTION_CHAIN")).ToList();
        // Closed fragments have zero reconstructed execution units deliberately:
        // HistoricalTrade represents completed closing slices, not all opening
        // deal fills. Never invent closed round trips or an executable book.
        var hashes=new Dictionary<string,string>(StringComparer.Ordinal);
        foreach(var trade in closed)
            hashes.Add("BROKER_FLAT/"+trade.ClosingDealId,
                Hash(JsonSerializer.Serialize(new {b.AccountBinding,Trade=trade})));
        var chain=new string('0',64);
        foreach(var pair in hashes.OrderBy(x=>x.Key,StringComparer.Ordinal))
            chain=Hash(chain+pair.Key+pair.Value);
        decimal maximum=retainedObservedPeak;
        foreach(var f in b.Cashflows)
        {
            maximum=Math.Max(maximum,f.BalanceAfterEur);
            if(f.ReportedMaximumEquityEur.HasValue)
                maximum=Math.Max(maximum,f.ReportedMaximumEquityEur.Value);
        }
        foreach(var f in closed)maximum=Math.Max(maximum,f.BalanceAfterEur);
        maximum=Math.Max(maximum,Math.Max(200m,b.EquityEur));
        ledger.state=ledger.state with {
            CashEur=b.BalanceEur,Clock=b.At,ObservedPeakEur=maximum,
            MaximumSampledDrawdown=0,HistoryEvidenceIncomplete=true,
            Positions=new(),Pending=new(),Closed=fragments,
            UsedPositionIds=closed.Select(x=>x.PositionId).ToHashSet(StringComparer.Ordinal),
            AppliedEventHashes=hashes,EventChainHash=chain,MonetaryDomain="BROKER_EXECUTION_FACT"
        };
        ledger.Reconcile();
        return ledger;
    }
}
public sealed partial class NativeFundedSession
{
    // Cash recovery and hypothesis scoring are allowed to resume without
    // LocalStorage. A historical equity *upper* bound, a complete deal chain,
    // and trading authority remain separate, unproven acceptance conditions.
    public BrokerFlatReadbackReport ReconcileBrokerFlat(BrokerFlatReadback b)
    {
        BrokerFlatReadbackReport Reject(string reason)=>new(false,false,false,false,
            false,false,null,null,reason);
        if(b.AccountBinding!=AccountBinding || b.At<=0)
            return Reject("NATIVE_FLAT_ACCOUNT_OR_CLOCK");
        if(!b.SnapshotStable) return Reject("NATIVE_FLAT_SNAPSHOT_NOT_STABLE_RETRY");
        if(b.OpenPositions!=0||b.PendingOrders!=0)
            return Reject("NATIVE_NONFLAT_REQUIRES_OPEN_EXECUTION_RECONCILIATION");
        if(Intents.Length!=0 || Ledger.Summary().PendingIntents!=0 ||
           Ledger.Summary().OpenPositions!=0)
            return Reject("NATIVE_UNRECONCILED_LOCAL_INTENT_OR_HELD_POSITION");
        if(b.BalanceEur<=0||b.MarginEur!=0||b.CreditEur!=0||
            Math.Abs(b.EquityEur-b.BalanceEur)>.01m)
            return Reject("NATIVE_FLAT_CASH_EQUITY_MARGIN_MISMATCH");
        // Positive initial funding only. API collection length does not certify
        // lifetime transaction completeness; the report does not claim that.
        if(b.Cashflows.Length!=1 || b.Cashflows[0].Kind!="DEPOSIT" ||
            b.Cashflows[0].AmountEur!=200m ||
            Math.Abs(b.Cashflows[0].BalanceAfterEur-200m)>.01m ||
            b.Cashflows[0].At<=0||b.Cashflows[0].At>b.At ||
            string.IsNullOrWhiteSpace(b.Cashflows[0].Id))
            return Reject("NATIVE_FOUNDING_DEPOSIT_OR_EXTRA_CASHFLOW_UNPROVEN");
        if(b.Closed.Select(x=>x.ClosingDealId).Distinct(StringComparer.Ordinal).Count()!=b.Closed.Length ||
           b.Closed.Any(x=>string.IsNullOrWhiteSpace(x.ClosingDealId)||
               string.IsNullOrWhiteSpace(x.PositionId)||string.IsNullOrWhiteSpace(x.Symbol)||
               x.EntryAt<b.Cashflows[0].At||x.EntryAt>x.ClosedAt||x.ClosedAt>b.At||
               x.CommissionEur<0||
               Math.Abs((x.GrossEur+x.SwapEur-x.CommissionEur)-x.NetEur)>.01m))
            return Reject("NATIVE_CLOSED_TRADE_IDENTITY_OR_NET_COMPONENTS_UNKNOWN");
        decimal reconstructed=200m+b.Closed.Sum(x=>x.NetEur);
        if(Math.Abs(reconstructed-b.BalanceEur)>.01m)
            return Reject("NATIVE_CLOSED_TRADES_DO_NOT_RECONCILE_ACCOUNT_CASH");
        if(Ledger.AppliedCount>0 &&
           Ledger.FactHashes.Any(old=>!old.Key.StartsWith("BROKER_FLAT/",StringComparison.Ordinal)))
            return Reject("NATIVE_NONFLAT_LEDGER_HISTORY_CANNOT_BE_REPLACED");
        NativeFundedLedger candidate;
        try {
            decimal previousPeak=Math.Max(Ledger.Summary().ObservedPeakEur,
                PortfolioObservation.State.ObservedPeakEur??200m);
            candidate=NativeFundedLedger.RebuildFlatBrokerHistory(b,previousPeak);
            foreach(var old in Ledger.FactHashes)
                if(!candidate.FactHashes.TryGetValue(old.Key,out var h)||h!=old.Value)
                    return Reject("NATIVE_OLD_FINANCIAL_EVIDENCE_CANNOT_BE_DROPPED");
        }catch(ArgumentException){return Reject("NATIVE_FLAT_RECONSTRUCTION_INVALID");}
         catch(InvalidOperationException){return Reject("NATIVE_FLAT_FINANCIAL_IDENTITY_INVALID");}
        Ledger=candidate;
        // History completeness, historical max-equity and broker order intent
        // attribution remain unknown, even though current flat cash matches.
        return new(true,true,false,false,true,false,reconstructed,
            candidate.Summary().ObservedPeakEur,"NATIVE_FLAT_CASH_REBUILT_RESEARCH_ONLY_PEAK_UNKNOWN");
    }
}
