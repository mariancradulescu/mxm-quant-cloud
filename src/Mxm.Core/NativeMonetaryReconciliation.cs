using System.Text.Json;
using System.Text.Json.Serialization;
namespace Mxm.Core;

// Source monetary amounts, never inferred from a changed account balance.
// Conversion quotes must have existed at the monetary event, not at restart.
public sealed record MonetaryLeg(decimal? Amount,string Currency,decimal? EurPerUnit,long? RateAt,string EvidenceHash);
public sealed record AttributedMoneyFact(string AccountBinding,string Domain,string Kind,string EventId,
    string DealId,string OrderId,string PositionId,string LedgerPositionId,string Symbol,int Side,decimal Units,
    long At,long AvailableAt,long Sequence,decimal? ExecutionPrice,MonetaryLeg? Gross,MonetaryLeg? Commission,
    MonetaryLeg? ConversionFee,MonetaryLeg? Financing,string EvidenceHash);
public sealed record ConfirmedFundingEvent(string RecordId,string PositionId,string Symbol,long At,decimal? Amount,string Currency,long AvailableAt,string EvidenceHash);
public sealed record MoneyRecoveryBatch(string AccountBinding,string Domain,BrokerIdentitySnapshot Snapshot,
    AttributedMoneyFact[] Facts,decimal? BrokerCashEur,bool InitialCapitalProven,bool CashflowHistoryComplete,
    bool FinancingHistoryComplete,bool AdditionalExternalCashflowDetected,ConfirmedFundingEvent[]? FundingRecords,long? BrokerCashObservedAt)
{
    // Accept the original frozen EUR200 verification JSON *only* in its
    // non-broker historical domain. Never treat it as EUR300 funding proof.
    [JsonPropertyName("InitialCapital200Proven")]
    public bool FrozenHistoricalInitialCapital200Proven {get;init;}
}
public sealed record MoneyRecoveryReport(bool Adopted,string[] Reasons,LedgerSummary RetainedLedger,
    decimal? ReconstructedCashEur,int ConfirmedExecutionFacts,int AppliedFundingFacts,bool PositionInventoryMatched,
    bool BrokerExecutionRecoveryCertified=false,bool GlobalDrawdownCertified=false,bool OrdersEnabled=false);

public sealed partial class NativeFundedLedger
{
    internal string MonetaryDomain=>state.MonetaryDomain;
    internal void PreserveObservedRisk(NativeFundedLedger old)=>state=state with {ObservedPeakEur=Math.Max(state.ObservedPeakEur,old.state.ObservedPeakEur),MaximumSampledDrawdown=Math.Max(state.MaximumSampledDrawdown,old.state.MaximumSampledDrawdown),HistoryEvidenceIncomplete=state.HistoryEvidenceIncomplete||old.state.HistoryEvidenceIncomplete};
    internal int AppliedCount=>state.AppliedEventHashes.Count;
    internal IReadOnlyDictionary<string,string> FactHashes=>state.AppliedEventHashes;
    static decimal Eur(MonetaryLeg? leg,long at)
    {
        if(leg is null || leg.Amount is not decimal value || leg.EurPerUnit is not decimal rate || leg.RateAt is not long rateAt ||
            string.IsNullOrWhiteSpace(leg.Currency) || rate<=0 || rateAt>at || at-rateAt>2000 || string.IsNullOrEmpty(leg.EvidenceHash) ||
            leg.EvidenceHash.Length!=64 || !leg.EvidenceHash.All(Uri.IsHexDigit) || leg.Currency=="EUR"&&rate!=1)
            throw new ArgumentException("MONETARY_AMOUNT_OR_CAUSAL_CONVERSION_UNKNOWN");
        return value*rate;
    }
    static object? LegIdentity(MonetaryLeg? l)=>l is null?null:new {l.Amount,l.Currency,l.EurPerUnit,l.RateAt};
    internal static string EconomicFactHash(AttributedMoneyFact f)=>Hash(JsonSerializer.Serialize(new {
        f.AccountBinding,f.Domain,f.Kind,f.EventId,f.DealId,f.OrderId,f.PositionId,f.LedgerPositionId,f.Symbol,f.Side,f.Units,
        f.At,f.Sequence,f.ExecutionPrice,Gross=LegIdentity(f.Gross),Commission=LegIdentity(f.Commission),
        Conversion=LegIdentity(f.ConversionFee),Financing=LegIdentity(f.Financing)}));
    internal void ApplyAttributedMoney(AttributedMoneyFact f)
    {
        if(f.Domain is not ("BROKER_EXECUTION_FACT" or "FROZEN_MODELED_SETTLEMENT") || string.IsNullOrWhiteSpace(f.AccountBinding) ||
            f.At<0 || f.AvailableAt<f.At || f.Sequence<0 || f.EvidenceHash.Length!=64 || !f.EvidenceHash.All(Uri.IsHexDigit))
            throw new ArgumentException("MONETARY_FACT_BINDING");
        string key="MONEY/"+f.EventId,hash=EconomicFactHash(f);
        if(state.AppliedEventHashes.TryGetValue(key,out var prior)){
            if(prior!=hash)throw new InvalidOperationException("CONFLICTING_MONETARY_FACT");return;
        }
        if(f.At<state.Clock || state.AppliedEventHashes.Count>0 && state.MonetaryDomain!=f.Domain)
            throw new InvalidOperationException("MONEY_HISTORY_ORDER_OR_DOMAIN_MISMATCH");
        if(string.IsNullOrWhiteSpace(f.LedgerPositionId)||string.IsNullOrWhiteSpace(f.PositionId)||string.IsNullOrWhiteSpace(f.Symbol)||f.Side is not (-1 or 1))
            throw new ArgumentException("MONEY_POSITION_BINDING");
        if(f.Kind=="FUNDING")
        {
            if(f.EventId!="funding/"+f.DealId || f.Units!=0 || !state.Positions.TryGetValue(f.LedgerPositionId,out var funded) || funded.Symbol!=f.Symbol)
                throw new ArgumentException("FUNDING_EVENT_IDENTITY");
            decimal financing=Eur(f.Financing,f.At);
            state.Positions[f.LedgerPositionId]=funded with {FinancingRemaining=funded.FinancingRemaining+financing};
            state=state with {CashEur=state.CashEur+financing};
        }
        else
        {
            if(f.Kind is not ("OPEN" or "CLOSE") || f.EventId!="deal/"+f.DealId || string.IsNullOrWhiteSpace(f.DealId)||
                string.IsNullOrWhiteSpace(f.OrderId)||f.Units<=0 || f.ExecutionPrice is <=0)
                throw new ArgumentException("EXECUTION_FACT_IDENTITY");
            decimal gross=Eur(f.Gross,f.At),commission=Eur(f.Commission,f.At),conversion=Eur(f.ConversionFee,f.At);
            if(commission<0 || conversion<0)throw new ArgumentException("MONETARY_COST_SIGN");
            if(f.Kind=="OPEN")
            {
                if(gross!=0)throw new ArgumentException("OPEN_FILL_CANNOT_CREATE_REALIZED_PNL");
                if(state.Positions.TryGetValue(f.LedgerPositionId,out var open))
                {
                    if(open.MonetaryDomain!=f.Domain||open.Symbol!=f.Symbol||open.Side!=f.Side)throw new ArgumentException("PARTIAL_ENTRY_IDENTITY_CONFLICT");
                    decimal units=open.Units+f.Units;
                    decimal? price=open.EntryPrice.HasValue&&f.ExecutionPrice.HasValue?(open.EntryPrice.Value*open.Units+f.ExecutionPrice.Value*f.Units)/units:null;
                    state.Positions[f.LedgerPositionId]=open with {Units=units,EntryPrice=price,EntryFeeRemaining=open.EntryFeeRemaining+commission,EntryConversionRemaining=open.EntryConversionRemaining+conversion};
                }
                else
                {
                    if(state.UsedPositionIds.Contains(f.LedgerPositionId))throw new ArgumentException("UNPROVEN_POSITION_ID_REUSE_AFTER_FLAT");
                    state.Positions.Add(f.LedgerPositionId,new(f.LedgerPositionId,f.Symbol,f.Side,f.Units,f.ExecutionPrice,f.At,commission,0,0,null,0,conversion,f.Domain));
                    state.UsedPositionIds.Add(f.LedgerPositionId);
                }
                state=state with {CashEur=state.CashEur-commission-conversion};
            }
            else
            {
                if(!state.Positions.TryGetValue(f.LedgerPositionId,out var p)||p.MonetaryDomain!=f.Domain||p.Symbol!=f.Symbol||p.Side!=-f.Side||f.Units>p.Units)
                    throw new ArgumentException("PARTIAL_CLOSE_VOLUME_OR_IDENTITY");
                decimal fraction=f.Units/p.Units,entryFee=p.EntryFeeRemaining*fraction,entryConversion=p.EntryConversionRemaining*fraction,funding=p.FinancingRemaining*fraction;
                bool complete=f.Units==p.Units;decimal net=gross-commission-entryFee-conversion-entryConversion+funding;
                // Actual spread/slippage decomposition is unknown, never zero.
                state.Closed.Add(new(p.Id,p.Symbol,p.EntryAt,f.At,f.Units,gross,null,null,conversion+entryConversion,commission+entryFee,-funding,net,complete,"ATTRIBUTED_"+f.Domain));
                if(complete)state.Positions.Remove(p.Id);
                else state.Positions[p.Id]=p with {Units=p.Units-f.Units,EntryFeeRemaining=p.EntryFeeRemaining-entryFee,EntryConversionRemaining=p.EntryConversionRemaining-entryConversion,FinancingRemaining=p.FinancingRemaining-funding};
                state=state with {CashEur=state.CashEur+gross-commission-conversion};
            }
        }
        state=state with {Clock=f.At,MonetaryDomain=f.Domain,HistoryEvidenceIncomplete=true,
            EventChainHash=Hash(state.EventChainHash+hash),ObservedPeakEur=Math.Max(state.ObservedPeakEur,state.CashEur)};
        state.AppliedEventHashes.Add(key,hash);Reconcile();
    }
}

public sealed partial class NativeFundedSession
{
    public MoneyRecoveryReport ReconcileMoney(MoneyRecoveryBatch b)
    {
        var reasons=new List<string>();
        if(b.AccountBinding!=AccountBinding||b.Snapshot.AccountBinding!=AccountBinding)reasons.Add("ACCOUNT_BINDING_MISMATCH");
        if(b.Domain is not ("BROKER_EXECUTION_FACT" or "FROZEN_MODELED_SETTLEMENT")||b.Facts.Any(f=>f.Domain!=b.Domain||f.AccountBinding!=AccountBinding))reasons.Add("MONETARY_SOURCE_DOMAIN_MISMATCH");
        if(!JournalContinuityProven||
           !(b.InitialCapitalProven ||
             (b.Domain=="FROZEN_MODELED_SETTLEMENT" && b.FrozenHistoricalInitialCapital200Proven))||
           !b.CashflowHistoryComplete||!b.FinancingHistoryComplete||b.FundingRecords is null)
            reasons.Add("JOURNAL_INITIAL_FUNDING_OR_CASHFLOW_HISTORY_UNPROVEN");
        if(b.AdditionalExternalCashflowDetected)reasons.Add("EXTERNAL_CASHFLOW_OUTSIDE_OWNER_BOOK");
        if(!b.Snapshot.InventoryStable||!b.Snapshot.OrdersComplete||!b.Snapshot.DealsComplete||b.BrokerCashEur is null)
            reasons.Add("CURRENT_INVENTORY_OR_ACCOUNT_CASH_UNPROVEN");
        if(b.BrokerCashObservedAt is not long cashAt || cashAt>b.Snapshot.At || b.Snapshot.At-cashAt>2000 || b.Snapshot.HistoryThrough<cashAt)
            reasons.Add("ACCOUNT_CASH_CLOCK_OR_HISTORY_COVERAGE_UNPROVEN");
        if(Ledger.AppliedCount>0&&Ledger.MonetaryDomain!=b.Domain)reasons.Add("EXISTING_LEDGER_DOMAIN_CANNOT_BE_RESET_OR_REPLACED");
        var identity=BrokerIdentityReconciliation.Assess(b.Snapshot,Intents);
        if(!identity.SnapshotConsistent)reasons.AddRange(identity.Reasons);
        if(identity.Intents.Any(r=>r.State is "IDENTITY_CONFLICT" or "INCOMPLETE_EXECUTION_EVIDENCE"))reasons.Add("ORDER_EXECUTION_HISTORY_INCOMPLETE_OR_CONFLICTING");
        var orders=b.Snapshot.Orders.GroupBy(o=>o.OrderId).ToDictionary(g=>g.Key,g=>g.First());
        var deals=b.Snapshot.Deals.GroupBy(d=>d.DealId).ToDictionary(g=>g.Key,g=>g.First());
        var facts=b.Facts.GroupBy(f=>f.EventId).Select(g=>{
            if(g.Select(NativeFundedLedger.EconomicFactHash).Distinct().Count()!=1)reasons.Add("CONFLICTING_MONETARY_FACT");return g.First();
        }).ToArray();
        foreach(var f in facts)
        {
            if(f.AvailableAt>b.Snapshot.At||f.At<b.Snapshot.HistoryFrom||f.At>b.Snapshot.HistoryThrough)reasons.Add("MONETARY_EVENT_OUTSIDE_PROVEN_HISTORY");
            if(f.Kind=="FUNDING"){
                var funding=(b.FundingRecords??Array.Empty<ConfirmedFundingEvent>()).Where(r=>r.RecordId==f.DealId).ToArray();
                if(funding.Length!=1||funding[0].PositionId!=f.PositionId||funding[0].Symbol!=f.Symbol||funding[0].At!=f.At||funding[0].AvailableAt>b.Snapshot.At||funding[0].EvidenceHash.Length!=64||!funding[0].EvidenceHash.All(Uri.IsHexDigit)||
                    f.Financing is null||funding[0].Amount!=f.Financing.Amount||funding[0].Currency!=f.Financing.Currency)reasons.Add("FUNDING_NOT_MATCHED_TO_POSITIVE_FINANCIAL_RECORD");
                if(!Intents.Any(i=>i.PositionId==f.PositionId&&i.LedgerPositionId==f.LedgerPositionId&&i.Symbol==f.Symbol))reasons.Add("FUNDING_POSITION_NOT_ATTRIBUTED");continue;
            }
            if(!deals.TryGetValue(f.DealId,out var d)||d.OrderId!=f.OrderId||d.PositionId!=f.PositionId||d.Symbol!=f.Symbol||d.Side!=f.Side||d.Units!=f.Units||d.At!=f.At||d.Closing!=(f.Kind=="CLOSE"))
                reasons.Add("MONETARY_EXECUTION_DOES_NOT_MATCH_CONFIRMED_DEAL");
            if(!orders.TryGetValue(f.OrderId,out var o)){reasons.Add("CONFIRMED_ORDER_MISSING");continue;}
            var matched=Intents.Where(i=>(!string.IsNullOrEmpty(i.OrderId)?i.OrderId==o.OrderId:i.IntentId==o.ClientIntentId)&&i.LedgerPositionId==f.LedgerPositionId&&(string.IsNullOrEmpty(i.PositionId)||i.PositionId==f.PositionId)&&i.Symbol==f.Symbol&&i.Side==f.Side&&i.Closing==(f.Kind=="CLOSE")&&i.RequestedUnits==o.RequestedUnits&&i.SubmittedAt<=f.At).ToArray();
            if(matched.Length!=1 || b.Snapshot.HistoryFrom>matched[0].SubmittedAt)reasons.Add("LOCAL_INTENT_MONEY_LINK_UNPROVEN");
        }
        if((b.FundingRecords??Array.Empty<ConfirmedFundingEvent>()).GroupBy(r=>r.RecordId).Any(g=>g.Count()!=1)||
            (b.FundingRecords??Array.Empty<ConfirmedFundingEvent>()).Any(r=>!facts.Any(f=>f.Kind=="FUNDING"&&f.DealId==r.RecordId)))reasons.Add("FUNDING_HISTORY_MISSING_OR_DUPLICATED");
        if(deals.Keys.Any(id=>!facts.Any(f=>(f.Kind is "OPEN" or "CLOSE")&&f.DealId==id)))reasons.Add("MISSING_MONETARY_FACT_FOR_CONFIRMED_EXECUTION");
        if(reasons.Count>0)return Reject();
        var candidate=new NativeFundedLedger();
        try {
            // Explicit sequence resolves equal timestamps; no favorable price/order search.
            var ordered=facts.OrderBy(f=>f.At).ThenBy(f=>f.Sequence).ToArray();
            if(ordered.GroupBy(f=>(f.At,f.Sequence)).Any(g=>g.Count()>1))throw new ArgumentException("AMBIGUOUS_SAME_TIME_FINANCIAL_SEQUENCE");
            foreach(var f in ordered)candidate.ApplyAttributedMoney(f);
            foreach(var old in Ledger.FactHashes)
                if(!candidate.FactHashes.TryGetValue(old.Key,out var hash)||hash!=old.Value)throw new ArgumentException("RECOVERY_DROPS_OR_CHANGES_EXISTING_MONETARY_HISTORY");
        } catch(ArgumentException e){reasons.Add(e.Message);return Reject();}
          catch(InvalidOperationException e){reasons.Add(e.Message);return Reject();}
        var positions=candidate.PositionSnapshot();
        bool positionMatch=positions.Length==b.Snapshot.Positions.Length&&positions.All(p=>{
            var bound=facts.Where(f=>f.LedgerPositionId==p.Id).Select(f=>f.PositionId).Distinct().ToArray();
            var actual=bound.Length==1?b.Snapshot.Positions.FirstOrDefault(x=>x.PositionId==bound[0]):null;
            return actual!=null&&actual.Symbol==p.Symbol&&actual.Side==p.Side&&actual.Units==p.Units;
        });
        candidate.PreserveObservedRisk(Ledger);
        var summary=candidate.Summary(b.Snapshot.At);
        if(!positionMatch)reasons.Add("RECONSTRUCTED_POSITION_INVENTORY_MISMATCH");
        if(Math.Abs(summary.CashEur-b.BrokerCashEur!.Value)>.00000001m)reasons.Add("RECONSTRUCTED_ACCOUNT_CASH_MISMATCH_NO_BALANCE_PATCH");
        if(reasons.Count>0)return new(false,reasons.Distinct().ToArray(),Ledger.Summary(),summary.CashEur,0,0,positionMatch);
        var boundIntents=Intents.Select(i=>{
            var matches=b.Snapshot.Orders.Where(o=>(!string.IsNullOrEmpty(i.OrderId)?i.OrderId==o.OrderId:i.IntentId==o.ClientIntentId)&&o.Symbol==i.Symbol&&o.Side==i.Side&&o.RequestedUnits==i.RequestedUnits&&o.Closing==i.Closing).ToArray();
            return matches.Length==1?i with {OrderId=matches[0].OrderId,PositionId=string.IsNullOrEmpty(i.PositionId)?matches[0].PositionId:i.PositionId}:i;
        }).ToArray();
        Ledger=candidate;Intents=boundIntents; // Single atomic replacement of the same continuously proven journal.
        return new(true,Array.Empty<string>(),summary,summary.CashEur,facts.Count(f=>f.Kind!="FUNDING"),facts.Count(f=>f.Kind=="FUNDING"),true);
        MoneyRecoveryReport Reject()=>new(false,reasons.Distinct().ToArray(),Ledger.Summary(),null,0,0,false);
    }
}
