using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
namespace Mxm.Core;

public sealed record LedgerQuote(string Symbol,long At,decimal Bid,decimal Ask,decimal EurCredit,decimal EurDebit,
    decimal ExitFeePerUnit,decimal ExitFeeFloor,decimal MarginPerUnit);
public sealed record LedgerEvent(string EventId,long At,string Kind,string PositionId,string Symbol,int Side,
    decimal Units,decimal ExecutionPrice,decimal FeeEur,decimal MarginPerUnit,decimal SlippagePerSide,
    long AvailableAt,long CalibratedThrough,long LatencyMs,string Reason,string EvidenceHash,LedgerQuote[] Quotes,
    decimal SignedFinancingEur=0);
public sealed record LedgerPosition(string Id,string Symbol,int Side,decimal Units,decimal EntryPrice,long EntryAt,
    decimal EntryFeeRemaining,decimal MarginPerUnit,decimal SlippagePerSide,LedgerQuote EntryQuote,decimal FinancingRemaining);
public sealed record LedgerClosedFragment(string PositionId,string Symbol,long OpenedAt,long ClosedAt,decimal Units,
    decimal GrossEur,decimal SpreadEur,decimal SlippageEur,decimal ConversionEur,decimal CommissionsEur,
    decimal FinancingEur,decimal NetEur,bool CompletesRoundTrip,string Reason);
public sealed record LedgerState(string Version,decimal InitialCashEur,decimal CashEur,long Clock,decimal ObservedPeakEur,
    decimal MaximumSampledDrawdown,bool HistoryEvidenceIncomplete,Dictionary<string,LedgerQuote> Quotes,
    Dictionary<string,LedgerPosition> Positions,Dictionary<string,LedgerEvent> Pending,
    Dictionary<string,string> AppliedEventHashes,HashSet<string> UsedPositionIds,List<LedgerClosedFragment> Closed,
    string EventChainHash);
public sealed record LedgerSummary(decimal CashEur,decimal? LiquidationEquityEur,decimal? UsedMarginEur,
    decimal? FreeMarginEur,decimal ObservedPeakEur,decimal MaximumSampledDrawdown,int OpenPositions,int PendingIntents,
    int CompleteRoundTrips,decimal ClosedNetEur,bool HistoryEvidenceIncomplete,string EventChainHash,
    bool GlobalDrawdownCertified=false,bool BrokerStateReconciled=false,bool OrdersEnabled=false);

// Native funded position/cash lifecycle. Research/model execution facts are
// explicit inputs; this class submits no orders and manufactures no execution,
// historical-cost, source-authenticity or lifetime-peak certificate.
public sealed class NativeFundedLedger
{
    const string Version="mxm-native-funded-ledger-v1";
    static readonly JsonSerializerOptions Options=new(){NumberHandling=JsonNumberHandling.AllowReadingFromString};
    LedgerState state=new(Version,200,200,-1,200,0,false,new(),new(),new(),new(),new(),new(),new string('0',64));
    readonly long maximumStalenessMs;
    public NativeFundedLedger(long maximumStalenessMs=1000)
    {
        if(maximumStalenessMs<0)throw new ArgumentException("NATIVE_LEDGER_STALENESS");
        this.maximumStalenessMs=maximumStalenessMs;
    }
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static decimal Fee(LedgerQuote q,decimal units)=>Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);
    static decimal ConvertQuote(LedgerQuote q,decimal amount)=>amount*(amount>=0?q.EurCredit:q.EurDebit);
    LedgerQuote Quote(Dictionary<string,LedgerQuote> quotes,string symbol,long at)
    {
        if(!quotes.TryGetValue(symbol,out var q) || q.At>at || at-q.At>maximumStalenessMs)
            throw new InvalidOperationException("NATIVE_LEDGER_HELD_MARK_UNKNOWN");
        return q;
    }
    decimal Floating(LedgerPosition p,LedgerQuote q)
    {
        decimal liquidation=p.Side>0?q.Bid-p.SlippagePerSide:q.Ask+p.SlippagePerSide;
        return ConvertQuote(q,p.Side*p.Units*(liquidation-p.EntryPrice))-Fee(q,p.Units);
    }
    decimal Equity(Dictionary<string,LedgerQuote> quotes,long at)=>state.CashEur+
        state.Positions.Values.Sum(p=>Floating(p,Quote(quotes,p.Symbol,at)));
    void Reconcile()
    {
        decimal expected=200+state.Closed.Sum(t=>t.NetEur)-state.Positions.Values.Sum(p=>p.EntryFeeRemaining)+
            state.Positions.Values.Sum(p=>p.FinancingRemaining);
        if(Math.Abs(expected-state.CashEur)>.000000001m)throw new InvalidOperationException("NATIVE_LEDGER_CASH_IDENTITY");
    }
    public void Apply(LedgerEvent e)
    {
        string hash=Hash(JsonSerializer.Serialize(e));
        if(state.AppliedEventHashes.TryGetValue(e.EventId,out var seen))
        {
            if(seen!=hash)throw new InvalidOperationException("NATIVE_LEDGER_CONFLICTING_EVENT");
            return;
        }
        if(string.IsNullOrWhiteSpace(e.EventId) || e.At<0 || e.At<state.Clock || e.EvidenceHash.Length!=64 ||
            !e.EvidenceHash.All(Uri.IsHexDigit) || e.Quotes.Select(q=>q.Symbol).Distinct().Count()!=e.Quotes.Length)
            throw new ArgumentException("NATIVE_LEDGER_EVENT_CONTRACT");
        var quotes=new Dictionary<string,LedgerQuote>(state.Quotes,StringComparer.Ordinal);
        foreach(var q in e.Quotes)
        {
            if(string.IsNullOrWhiteSpace(q.Symbol) || q.At>e.At || e.At-q.At>maximumStalenessMs || q.Bid<=0 || q.Ask<q.Bid ||
                q.EurCredit<=0 || q.EurDebit<q.EurCredit || q.ExitFeePerUnit<0 || q.ExitFeeFloor<0 || q.MarginPerUnit<=0 ||
                (quotes.TryGetValue(q.Symbol,out var old) && (q.At<old.At || q.At==old.At && q!=old)))
                throw new ArgumentException("NATIVE_LEDGER_QUOTE_CONTRACT");
            quotes[q.Symbol]=q;
        }
        // Validate and calculate before mutating monetary/position state.
        switch(e.Kind)
        {
            case "REQUEST_OPEN":
                if(string.IsNullOrWhiteSpace(e.PositionId) || string.IsNullOrWhiteSpace(e.Symbol) || e.Side is not (-1 or 1) ||
                    e.Units<=0 || e.AvailableAt>e.At || e.CalibratedThrough>e.AvailableAt || e.CalibratedThrough<0 ||
                    e.LatencyMs<=0 || state.UsedPositionIds.Contains(e.PositionId) || state.Pending.ContainsKey(e.PositionId))
                    throw new ArgumentException("NATIVE_LEDGER_OPEN_INTENT");
                state.Pending.Add(e.PositionId,e);state.UsedPositionIds.Add(e.PositionId);break;
            case "REQUEST_CLOSE":
                if(!state.Positions.TryGetValue(e.PositionId,out var closePosition) || closePosition.Symbol!=e.Symbol ||
                    e.LatencyMs<=0 || state.Pending.ContainsKey(e.PositionId))
                    throw new ArgumentException("NATIVE_LEDGER_CLOSE_INTENT");
                state.Pending.Add(e.PositionId,e);break;
            case "OPEN_FILL":
                if(!state.Pending.TryGetValue(e.PositionId,out var request) || request.Kind!="REQUEST_OPEN" ||
                    request.Symbol!=e.Symbol || request.Side!=e.Side || request.Units!=e.Units || e.At<request.At+request.LatencyMs ||
                    e.ExecutionPrice<=0 || e.FeeEur<0 || e.MarginPerUnit<=0 || e.SlippagePerSide<0)
                    throw new ArgumentException("NATIVE_LEDGER_OPEN_FILL");
                var entryQuote=Quote(quotes,e.Symbol,e.At);
                decimal expectedPrice=e.Side>0?entryQuote.Ask+e.SlippagePerSide:entryQuote.Bid-e.SlippagePerSide;
                if(e.ExecutionPrice!=expectedPrice || Math.Abs(e.FeeEur-Fee(entryQuote,e.Units))>.000000001m)
                    throw new ArgumentException("NATIVE_LEDGER_MODELED_FILL_COST_BINDING");
                var position=new LedgerPosition(e.PositionId,e.Symbol,e.Side,e.Units,e.ExecutionPrice,e.At,e.FeeEur,
                    e.MarginPerUnit,e.SlippagePerSide,entryQuote,0);
                decimal projected=Equity(quotes,e.At)-e.FeeEur+Floating(position,entryQuote);
                decimal margin=state.Positions.Values.Sum(p=>Math.Max(p.MarginPerUnit,Quote(quotes,p.Symbol,e.At).MarginPerUnit)*p.Units)+e.MarginPerUnit*e.Units;
                if(projected<=margin || projected<=0)throw new InvalidOperationException("NATIVE_LEDGER_UNFINANCED_MODEL_FILL");
                state=state with {CashEur=state.CashEur-e.FeeEur};state.Positions.Add(e.PositionId,position);state.Pending.Remove(e.PositionId);break;
            case "CLOSE_FILL":
                if(!state.Positions.TryGetValue(e.PositionId,out var closedPosition) || !state.Pending.TryGetValue(e.PositionId,out var close) ||
                    close.Kind!="REQUEST_CLOSE" || close.Symbol!=e.Symbol || e.At<close.At+close.LatencyMs || e.Units<=0 || e.Units>closedPosition.Units || e.FeeEur<0)
                    throw new ArgumentException("NATIVE_LEDGER_CLOSE_FILL");
                var q=Quote(quotes,closedPosition.Symbol,e.At);decimal outPrice=closedPosition.Side>0?q.Bid-closedPosition.SlippagePerSide:q.Ask+closedPosition.SlippagePerSide;
                if(e.ExecutionPrice!=outPrice || Math.Abs(e.FeeEur-Fee(q,e.Units))>.000000001m)
                    throw new ArgumentException("NATIVE_LEDGER_MODELED_EXIT_COST_BINDING");
                decimal fraction=e.Units/closedPosition.Units,entryFee=closedPosition.EntryFeeRemaining*fraction,finance=closedPosition.FinancingRemaining*fraction;
                decimal converted=ConvertQuote(q,closedPosition.Side*e.Units*(outPrice-closedPosition.EntryPrice));
                decimal reference=(q.EurCredit+q.EurDebit)/2;
                decimal gross=closedPosition.Side*e.Units*((q.Bid+q.Ask)/2-(closedPosition.EntryQuote.Bid+closedPosition.EntryQuote.Ask)/2)*reference;
                decimal spread=e.Units*((closedPosition.EntryQuote.Ask-closedPosition.EntryQuote.Bid)+(q.Ask-q.Bid))/2*reference;
                decimal slip=e.Units*2*closedPosition.SlippagePerSide*reference;
                decimal conversion=gross-spread-slip-converted;
                if(conversion<-.000000001m)throw new InvalidOperationException("NATIVE_LEDGER_CONVERSION_COST");
                conversion=Math.Max(0,conversion);decimal net=converted-entryFee-e.FeeEur+finance;
                bool complete=e.Units==closedPosition.Units;
                state.Closed.Add(new(closedPosition.Id,closedPosition.Symbol,closedPosition.EntryAt,e.At,e.Units,gross,spread,slip,conversion,entryFee+e.FeeEur,-finance,net,complete,e.Reason));
                state=state with {CashEur=state.CashEur+converted-e.FeeEur};
                if(complete){state.Positions.Remove(closedPosition.Id);state.Pending.Remove(closedPosition.Id);}
                else state.Positions[closedPosition.Id]=closedPosition with {Units=closedPosition.Units-e.Units,EntryFeeRemaining=closedPosition.EntryFeeRemaining-entryFee,FinancingRemaining=closedPosition.FinancingRemaining-finance};
                break;
            case "CONFIRMED_CANCEL":
                if(!state.Pending.ContainsKey(e.PositionId) || string.IsNullOrWhiteSpace(e.Reason))
                    throw new ArgumentException("NATIVE_LEDGER_CANCELLATION_EVIDENCE");
                state.Pending.Remove(e.PositionId);break;
            case "FINANCING":
                if(!state.Positions.TryGetValue(e.PositionId,out var financed))throw new ArgumentException("NATIVE_LEDGER_FINANCING_POSITION");
                state.Positions[e.PositionId]=financed with {FinancingRemaining=financed.FinancingRemaining+e.SignedFinancingEur};
                state=state with {CashEur=state.CashEur+e.SignedFinancingEur};break;
            case "MARK":break;
            default:throw new ArgumentException("NATIVE_LEDGER_UNKNOWN_EVENT");
        }
        state=state with {Quotes=quotes,Clock=e.At,EventChainHash=Hash(state.EventChainHash+hash)};
        state.AppliedEventHashes.Add(e.EventId,hash);
        if(e.Kind is "MARK" or "OPEN_FILL" or "CLOSE_FILL" or "FINANCING")
        {
            try
            {
                decimal eq=Equity(quotes,e.At),peak=Math.Max(state.ObservedPeakEur,eq);
                state=state with {ObservedPeakEur=peak,MaximumSampledDrawdown=Math.Max(state.MaximumSampledDrawdown,1-eq/peak)};
            }
            catch(InvalidOperationException){state=state with {HistoryEvidenceIncomplete=true};}
        }
        Reconcile();
    }
    public LedgerSummary Summary()
    {
        decimal? equity=null,margin=null;
        try {equity=Equity(state.Quotes,state.Clock);margin=state.Positions.Values.Sum(p=>p.Units*Math.Max(p.MarginPerUnit,Quote(state.Quotes,p.Symbol,state.Clock).MarginPerUnit));}
        catch(InvalidOperationException){}
        return new(state.CashEur,equity,margin,equity-margin,state.ObservedPeakEur,state.MaximumSampledDrawdown,
            state.Positions.Count,state.Pending.Count,state.Closed.Count(t=>t.CompletesRoundTrip),state.Closed.Sum(t=>t.NetEur),
            state.HistoryEvidenceIncomplete,state.EventChainHash);
    }
    public LedgerClosedFragment[] ClosedFragments()=>state.Closed.ToArray();
    public string Checkpoint()
    {
        string payload=JsonSerializer.Serialize(state);return JsonSerializer.Serialize(new {Payload=payload,Sha256=Hash(payload),MaximumStalenessMs=maximumStalenessMs});
    }
    public static NativeFundedLedger Restore(string checkpoint)
    {
        using var d=JsonDocument.Parse(checkpoint);var root=d.RootElement;string payload=root.GetProperty("Payload").GetString()!;
        if(Hash(payload)!=root.GetProperty("Sha256").GetString())throw new ArgumentException("NATIVE_LEDGER_CHECKPOINT_HASH");
        var restored=JsonSerializer.Deserialize<LedgerState>(payload,Options) ?? throw new ArgumentException("NATIVE_LEDGER_CHECKPOINT_STATE");
        if(restored.Version!=Version || restored.InitialCashEur!=200 || restored.ObservedPeakEur<200 || restored.MaximumSampledDrawdown<0)
            throw new ArgumentException("NATIVE_LEDGER_CHECKPOINT_VERSION_OR_CAPITAL");
        var ledger=new NativeFundedLedger(root.GetProperty("MaximumStalenessMs").GetInt64()){state=restored};ledger.Reconcile();return ledger;
    }
    public static object ReceiveFacts(LedgerEvent[] events)
    {
        var uninterrupted=new NativeFundedLedger();var resumed=new NativeFundedLedger();var receipts=new List<LedgerSummary>();
        foreach(var e in events)
        {
            uninterrupted.Apply(e);resumed.Apply(e);resumed=Restore(resumed.Checkpoint());
            if(uninterrupted.Summary()!=resumed.Summary())throw new InvalidOperationException("NATIVE_LEDGER_RESTART_PARITY");
            var before=resumed.Summary();resumed.Apply(e);
            if(before!=resumed.Summary())throw new InvalidOperationException("NATIVE_LEDGER_IDEMPOTENCE");
            receipts.Add(uninterrupted.Summary());
        }
        return new {Summary=uninterrupted.Summary(),Trades=uninterrupted.ClosedFragments(),Receipts=receipts,
            RestartEveryEventMatched=true,DuplicatesIdempotent=true,ModelOrAllocationRerun=false,OrdersSubmitted=0,CloudActivated=false};
    }
}
