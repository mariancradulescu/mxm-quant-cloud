using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
namespace Mxm.Core;

public sealed record LedgerQuote(string Symbol,long At,decimal Bid,decimal Ask,decimal EurCredit,decimal EurDebit,
    decimal ExitFeePerUnit,decimal ExitFeeFloor,decimal MarginPerUnit)
{
    [JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)]
    public decimal? LiquidationSlippagePerSide { get; init; }
}
public sealed record LedgerEvent(string EventId,long At,string Kind,string PositionId,string Symbol,int Side,
    decimal Units,decimal ExecutionPrice,decimal FeeEur,decimal MarginPerUnit,decimal SlippagePerSide,
    long AvailableAt,long CalibratedThrough,long LatencyMs,string Reason,string EvidenceHash,LedgerQuote[] Quotes,
    decimal SignedFinancingEur=0)
{
    [JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)]
    public decimal? ObservedExitSlippagePerSide { get; init; }
    [JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)]
    public long? FundingFromExclusive { get; init; }
}
public sealed record LedgerPosition(string Id,string Symbol,int Side,decimal Units,decimal? EntryPrice,long EntryAt,
    decimal EntryFeeRemaining,decimal MarginPerUnit,decimal SlippagePerSide,LedgerQuote? EntryQuote,decimal FinancingRemaining,
    decimal EntryConversionRemaining=0,string MonetaryDomain="MODEL_REPLAY");
public sealed record LedgerClosedFragment(string PositionId,string Symbol,long OpenedAt,long ClosedAt,decimal Units,
    decimal GrossEur,decimal? SpreadEur,decimal? SlippageEur,decimal? ConversionEur,decimal CommissionsEur,
    decimal FinancingEur,decimal NetEur,bool CompletesRoundTrip,string Reason);
public sealed record LedgerClosedFundingSettlement(string EventId,string PositionId,string Symbol,int Side,
    decimal Units,long FromExclusive,long ThroughInclusive,long AvailableAt,long PostedAt,
    decimal SignedDeltaEur,string EvidenceHash);
public sealed record LedgerState(string Version,decimal InitialCashEur,decimal CashEur,long Clock,decimal ObservedPeakEur,
    decimal MaximumSampledDrawdown,bool HistoryEvidenceIncomplete,Dictionary<string,LedgerQuote> Quotes,
    Dictionary<string,LedgerPosition> Positions,Dictionary<string,LedgerEvent> Pending,
    Dictionary<string,string> AppliedEventHashes,HashSet<string> UsedPositionIds,List<LedgerClosedFragment> Closed,
    string EventChainHash,string MonetaryDomain="MODEL_REPLAY")
{
    [JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)]
    public List<LedgerClosedFundingSettlement>? ClosedFunding { get; init; }
}
public sealed record LedgerSummary(decimal CashEur,decimal? LiquidationEquityEur,decimal? UsedMarginEur,
    decimal? FreeMarginEur,decimal ObservedPeakEur,decimal MaximumSampledDrawdown,int OpenPositions,int PendingIntents,
    int CompleteRoundTrips,decimal ClosedNetEur,bool HistoryEvidenceIncomplete,string EventChainHash,
    bool GlobalDrawdownCertified=false,bool BrokerStateReconciled=false,bool OrdersEnabled=false);

// Native funded position/cash lifecycle. Research/model execution facts are
// explicit inputs; this class submits no orders and manufactures no execution,
// historical-cost, source-authenticity or lifetime-peak certificate.
public sealed partial class NativeFundedLedger
{
    const string Version="mxm-native-funded-ledger-v3";
    static readonly JsonSerializerOptions Options=new(){NumberHandling=JsonNumberHandling.AllowReadingFromString};
    LedgerState state=new(Version,OwnerRiskAuthority.InitialCapitalEur,OwnerRiskAuthority.InitialCapitalEur,-1,OwnerRiskAuthority.InitialCapitalEur,0,false,new(),new(),new(),new(),new(),new(),new string('0',64));
    readonly long maximumStalenessMs;
    decimal closedNetEur;
    int completeRoundTrips;
    public NativeFundedLedger(long maximumStalenessMs=1000)
    {
        if(maximumStalenessMs<0)throw new ArgumentException("NATIVE_LEDGER_STALENESS");
        this.maximumStalenessMs=maximumStalenessMs;
    }
    // Historical immutable receipt verifier only: never used by broker recovery,
    // prospectively funded decisions, or the observation-only cBot. Its EUR200
    // modeled facts remain in a non-execution domain, never credited to EUR300.
    internal static NativeFundedLedger ForFrozenHistorical200Receipt()
    {
        var x=new NativeFundedLedger();
        x.state=x.state with {InitialCashEur=200m,CashEur=200m,
            ObservedPeakEur=200m,MonetaryDomain="FROZEN_MODELED_SETTLEMENT"};
        return x;
    }
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    internal static decimal Fee(LedgerQuote q,decimal units)=>Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);
    internal static decimal ConvertQuote(LedgerQuote q,decimal amount)=>amount*(amount>=0?q.EurCredit:q.EurDebit);
    LedgerQuote Quote(Dictionary<string,LedgerQuote> quotes,string symbol,long at)
    {
        if(!quotes.TryGetValue(symbol,out var q) || q.At>at || at-q.At>maximumStalenessMs)
            throw new InvalidOperationException("NATIVE_LEDGER_HELD_MARK_UNKNOWN");
        return q;
    }
    decimal Floating(LedgerPosition p,LedgerQuote q)
    {
        if(p.MonetaryDomain!="MODEL_REPLAY")throw new InvalidOperationException("BROKER_FLOATING_AND_EXIT_COST_EVIDENCE_NOT_SUPPLIED");
        decimal liquidation=NativeExecutableEconomics.ExitPrice(p.Side>0?q.Bid:q.Ask,p.Side,
            q.LiquidationSlippagePerSide??p.SlippagePerSide);
        return ConvertQuote(q,p.Side*p.Units*(liquidation-(p.EntryPrice??throw new InvalidOperationException("ENTRY_BASIS_UNKNOWN"))))-Fee(q,p.Units);
    }
    decimal Equity(Dictionary<string,LedgerQuote> quotes,long at)=>state.CashEur+
        state.Positions.Values.Sum(p=>Floating(p,Quote(quotes,p.Symbol,at)));
    void Reconcile(decimal? settlementNetEur=null)
    {
        decimal expected=state.InitialCashEur+(settlementNetEur??closedNetEur)-state.Positions.Values.Sum(p=>p.EntryFeeRemaining+p.EntryConversionRemaining)+
            state.Positions.Values.Sum(p=>p.FinancingRemaining);
        if(Math.Abs(expected-state.CashEur)>.000000001m)throw new InvalidOperationException("NATIVE_LEDGER_CASH_IDENTITY");
    }

    void AppendSettlement(LedgerClosedFragment settlement,decimal settledNet)
    {
        state.Closed.Add(settlement);
        closedNetEur=settledNet;
        if(settlement.CompletesRoundTrip)completeRoundTrips++;
    }

    void RebuildSettlementTotals()
    {
        closedNetEur=0m;
        completeRoundTrips=0;
        foreach(var settlement in state.Closed)
        {
            closedNetEur+=settlement.NetEur;
            if(settlement.CompletesRoundTrip)completeRoundTrips++;
        }
        closedNetEur+=state.ClosedFunding?.Sum(x=>x.SignedDeltaEur)??0m;
    }
    public void Apply(LedgerEvent e)=>Apply(e,validateSummary:false);

    // The engine owns this model book. Stage only mutable live exposure;
    // the event identities and settlements are appended after validation.
    internal void ApplyOwnedResearchFact(LedgerEvent fact)
    {
        var previous=state;
        if(fact.Kind!="MARK")
            state=state with {
                Positions=new(state.Positions,StringComparer.Ordinal),
                Pending=new(state.Pending,StringComparer.Ordinal)
            };
        try {Apply(fact,validateSummary:true);}
        catch
        {
            state=previous;
            throw;
        }
    }

    void Apply(LedgerEvent e,bool validateSummary)
    {
        if(state.MonetaryDomain!="MODEL_REPLAY")throw new InvalidOperationException("EXECUTION_DOMAIN_MISMATCH_NO_MODEL_FILL_ON_RECOVERED_BOOK");
        string hash=Hash(JsonSerializer.Serialize(e));
        if(state.AppliedEventHashes.TryGetValue(e.EventId,out var seen))
        {
            if(seen!=hash)throw new InvalidOperationException("NATIVE_LEDGER_CONFLICTING_EVENT");
            if(validateSummary)_=Summary();
            return;
        }
        if(string.IsNullOrWhiteSpace(e.EventId) || e.At<0 || e.At<state.Clock || e.EvidenceHash.Length!=64 ||
            !e.EvidenceHash.All(Uri.IsHexDigit) || e.Quotes.Select(q=>q.Symbol).Distinct().Count()!=e.Quotes.Length)
            throw new ArgumentException("NATIVE_LEDGER_EVENT_CONTRACT");
        var quotes=new Dictionary<string,LedgerQuote>(state.Quotes,StringComparer.Ordinal);
        foreach(var q in e.Quotes)
        {
            if(string.IsNullOrWhiteSpace(q.Symbol) || q.At>e.At || e.At-q.At>maximumStalenessMs || q.Bid<=0 || q.Ask<q.Bid ||
                q.EurCredit<=0 || q.EurDebit<q.EurCredit || q.ExitFeePerUnit<0 || q.ExitFeeFloor<0 || q.MarginPerUnit<=0 || q.LiquidationSlippagePerSide is <0m ||
                (quotes.TryGetValue(q.Symbol,out var old) && (q.At<old.At || q.At==old.At && q!=old)))
                throw new ArgumentException("NATIVE_LEDGER_QUOTE_CONTRACT");
            quotes[q.Symbol]=q;
        }
        // Validate and calculate before mutating monetary/position state.
        LedgerClosedFragment? settlement=null;
        LedgerClosedFundingSettlement? closedFunding=null;
        if(e.Kind!="CLOSED_FUNDING_SETTLEMENT" && e.FundingFromExclusive.HasValue)
            throw new ArgumentException("NATIVE_LEDGER_UNEXPECTED_FUNDING_WINDOW");
        switch(e.Kind)
        {
            case "REQUEST_OPEN":
                if(string.IsNullOrWhiteSpace(e.PositionId) || string.IsNullOrWhiteSpace(e.Symbol) || e.Side is not (-1 or 1) ||
                    e.Units<=0 || e.AvailableAt>e.At || e.CalibratedThrough>e.AvailableAt || e.CalibratedThrough<0 ||
                    e.LatencyMs<=0 || state.UsedPositionIds.Contains(e.PositionId) || state.Pending.ContainsKey(e.PositionId))
                    throw new ArgumentException("NATIVE_LEDGER_OPEN_INTENT");
                // A past missing mark remains disclosed, but must not permanently
                // prevent conditional model decisions once current marks recover.
                // No broker/trading certificate follows from this research path.
                try { _=Equity(quotes,e.At); }
                catch(InvalidOperationException) { throw new ArgumentException("NATIVE_LEDGER_CURRENT_HOLDING_MARK_UNKNOWN"); }
                state.Pending.Add(e.PositionId,e);break;
            case "REQUEST_CLOSE":
                if(!state.Positions.TryGetValue(e.PositionId,out var closePosition) || closePosition.Symbol!=e.Symbol ||
                    e.LatencyMs<=0 || state.Pending.ContainsKey(e.PositionId))
                    throw new ArgumentException("NATIVE_LEDGER_CLOSE_INTENT");
                state.Pending.Add(e.PositionId,e);break;
            case "OPEN_FILL":
                if(!state.Pending.TryGetValue(e.PositionId,out var request) || request.Kind!="REQUEST_OPEN" ||
                    request.Symbol!=e.Symbol || request.Side!=e.Side || request.Units!=e.Units || e.At<request.At+request.LatencyMs ||
                    e.ExecutionPrice<=0 || e.FeeEur<0 || e.MarginPerUnit<=0 || e.SlippagePerSide<0 || e.SlippagePerSide!=request.SlippagePerSide)
                    throw new ArgumentException("NATIVE_LEDGER_OPEN_FILL");
                var entryQuote=Quote(quotes,e.Symbol,e.At);
                decimal expectedPrice=NativeExecutableEconomics.EntryPrice(entryQuote,e.Side,e.SlippagePerSide);
                if(e.ExecutionPrice!=expectedPrice || Math.Abs(e.FeeEur-Fee(entryQuote,e.Units))>.000000001m)
                    throw new ArgumentException("NATIVE_LEDGER_MODELED_FILL_COST_BINDING");
                var position=new LedgerPosition(e.PositionId,e.Symbol,e.Side,e.Units,e.ExecutionPrice,e.At,e.FeeEur,
                    e.MarginPerUnit,e.SlippagePerSide,entryQuote,0);
                decimal projected=Equity(quotes,e.At)-e.FeeEur+Floating(position,entryQuote);
                decimal margin=state.Positions.Values.Sum(p=>Math.Max(p.MarginPerUnit,Quote(quotes,p.Symbol,e.At).MarginPerUnit)*p.Units)+Math.Max(e.MarginPerUnit,entryQuote.MarginPerUnit)*e.Units;
                if(projected<=margin || projected<=0)throw new InvalidOperationException("NATIVE_LEDGER_UNFINANCED_MODEL_FILL");
                state=state with {CashEur=state.CashEur-e.FeeEur};state.Positions.Add(e.PositionId,position);state.Pending.Remove(e.PositionId);break;
            case "CLOSE_FILL":
                if(!state.Positions.TryGetValue(e.PositionId,out var closedPosition) || !state.Pending.TryGetValue(e.PositionId,out var close) ||
                    close.Kind!="REQUEST_CLOSE" || close.Symbol!=e.Symbol || e.At<close.At+close.LatencyMs || e.Units<=0 || e.Units>closedPosition.Units || e.FeeEur<0)
                    throw new ArgumentException("NATIVE_LEDGER_CLOSE_FILL");
                var entry=closedPosition.EntryQuote??throw new InvalidOperationException("MODEL_ENTRY_QUOTE_UNKNOWN");
                var q=Quote(quotes,closedPosition.Symbol,e.At);
                decimal exitSlippage=e.ObservedExitSlippagePerSide??closedPosition.SlippagePerSide;
                if(exitSlippage<0)throw new ArgumentException("NATIVE_LEDGER_MODELED_EXIT_SLIPPAGE");
                decimal outPrice=NativeExecutableEconomics.ExitPrice(closedPosition.Side>0?q.Bid:q.Ask,
                    closedPosition.Side,exitSlippage);
                if(e.ExecutionPrice!=outPrice || Math.Abs(e.FeeEur-Fee(q,e.Units))>.000000001m)
                    throw new ArgumentException("NATIVE_LEDGER_MODELED_EXIT_COST_BINDING");
                decimal fraction=e.Units/closedPosition.Units,entryFee=closedPosition.EntryFeeRemaining*fraction,finance=closedPosition.FinancingRemaining*fraction;
                decimal converted=ConvertQuote(q,closedPosition.Side*e.Units*(outPrice-(closedPosition.EntryPrice??throw new InvalidOperationException("ENTRY_BASIS_UNKNOWN"))));
                decimal reference=(q.EurCredit+q.EurDebit)/2;
                decimal gross=closedPosition.Side*e.Units*((q.Bid+q.Ask)/2-(entry.Bid+entry.Ask)/2)*reference;
                decimal spread=e.Units*((entry.Ask-entry.Bid)+(q.Ask-q.Bid))/2*reference;
                decimal slip=e.Units*(closedPosition.SlippagePerSide+exitSlippage)*reference;
                decimal conversion=gross-spread-slip-converted;
                if(conversion<-.000000001m)throw new InvalidOperationException("NATIVE_LEDGER_CONVERSION_COST");
                conversion=Math.Max(0,conversion);decimal net=converted-entryFee-e.FeeEur+finance;
                bool complete=e.Units==closedPosition.Units;
                settlement=new(closedPosition.Id,closedPosition.Symbol,closedPosition.EntryAt,e.At,e.Units,gross,spread,slip,conversion,entryFee+e.FeeEur,-finance,net,complete,e.Reason);
                state=state with {CashEur=state.CashEur+converted-e.FeeEur};
                if(complete){state.Positions.Remove(closedPosition.Id);state.Pending.Remove(closedPosition.Id);}
                else
                {
                    state.Positions[closedPosition.Id]=closedPosition with {Units=closedPosition.Units-e.Units,EntryFeeRemaining=closedPosition.EntryFeeRemaining-entryFee,FinancingRemaining=closedPosition.FinancingRemaining-finance};
                    if(close.Reason=="MODEL_UNTRANSMITTED_INTEGRATED_FAVORABLE_REDUCTION" &&
                       close.Units==e.Units)
                        state.Pending.Remove(closedPosition.Id);
                }
                break;
            // SIR1: entirely local, NEVER TRANSMITTED model close intent.
            // Unlike CONFIRMED_CANCEL, this never claims a broker acknowledgement,
            // cannot cancel a real broker order, and NEVER removes the held position.
            // New UCP1 MODEL-ONLY open intent: no real broker transmission.
            // Explicit cancellation cannot release an opened position: there
            // must not be one, and no broker-confirmed CANCEL is manufactured.
            case "MODEL_OPEN_INTENT_EXPIRED":
                if(!state.Pending.TryGetValue(e.PositionId,out var modelOpen) ||
                   modelOpen.Kind!="REQUEST_OPEN" ||
                   modelOpen.Reason!="NATIVE_CONDITIONAL_SELECTION" ||
                   state.Positions.ContainsKey(e.PositionId) ||
                   e.At<=modelOpen.At ||
                   e.Symbol!=modelOpen.Symbol ||e.Side!=modelOpen.Side ||
                   e.Units!=modelOpen.Units ||
                   e.Reason is not ("MODEL_UNTRANSMITTED_OPEN_RESPONSE_WINDOW_EXPIRED" or
                                    "MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED") ||
                   e.Quotes.Length!=0 ||e.ExecutionPrice!=0m ||
                   e.FeeEur!=0m ||e.MarginPerUnit!=0m ||
                   e.SlippagePerSide!=0m)
                    throw new ArgumentException("MODEL_OPEN_EXPIRY_MUST_BE_UNTRANSMITTED");
                state.Pending.Remove(e.PositionId);break;
            case "MODEL_CLOSE_INTENT_EXPIRED":
                if(!state.Pending.TryGetValue(e.PositionId,out var staleClose) ||
                   staleClose.Kind!="REQUEST_CLOSE" ||
                   !staleClose.Reason.StartsWith("MODEL_UNTRANSMITTED_",StringComparison.Ordinal) ||
                   !state.Positions.TryGetValue(e.PositionId,out var retained) ||
                   e.At<=staleClose.At ||
                   retained.Symbol!=e.Symbol || retained.Side!=e.Side ||
                   retained.Units!=e.Units ||
                   e.Reason!="MODEL_UNTRANSMITTED_CLOSE_RESPONSE_WINDOW_EXPIRED" ||
                   e.Quotes.Length!=0 || e.ExecutionPrice!=0m ||
                   e.FeeEur!=0m || e.MarginPerUnit!=0m ||
                   e.SlippagePerSide!=0m)
                    throw new ArgumentException("MODEL_CLOSE_INTENT_EXPIRY_NOT_PROVEN");
                state.Pending.Remove(e.PositionId);break;
            case "CONFIRMED_CANCEL":
                if(!state.Pending.ContainsKey(e.PositionId) || string.IsNullOrWhiteSpace(e.Reason))
                    throw new ArgumentException("NATIVE_LEDGER_CANCELLATION_EVIDENCE");
                state.Pending.Remove(e.PositionId);break;
            case "FINANCING":
                if(!state.Positions.TryGetValue(e.PositionId,out var financed))throw new ArgumentException("NATIVE_LEDGER_FINANCING_POSITION");
                state.Positions[e.PositionId]=financed with {FinancingRemaining=financed.FinancingRemaining+e.SignedFinancingEur};
                state=state with {CashEur=state.CashEur+e.SignedFinancingEur};break;
            case "CLOSED_FUNDING_SETTLEMENT":
                if(e.FundingFromExclusive is not long from || from<0 || e.CalibratedThrough<=from ||
                    e.AvailableAt<e.CalibratedThrough || e.AvailableAt>e.At || e.Units<=0m ||
                    e.Side is not (-1 or 1) || e.SignedFinancingEur==0m ||
                    e.ExecutionPrice!=0m || e.FeeEur!=0m || e.MarginPerUnit!=0m ||
                    e.SlippagePerSide!=0m || e.LatencyMs!=0 ||
                    e.Reason!="SUPPORTED_CLOSED_EXPOSURE_FUNDING_SETTLEMENT" ||
                    !state.Closed.Any(x=>x.PositionId==e.PositionId && x.Symbol==e.Symbol &&
                        x.OpenedAt<=from && x.ClosedAt==e.CalibratedThrough) ||
                    (state.ClosedFunding?.Any(x=>x.PositionId==e.PositionId &&
                        (x.FromExclusive==from || x.ThroughInclusive==e.CalibratedThrough))??false))
                    throw new ArgumentException("NATIVE_LEDGER_CLOSED_FUNDING_WINDOW");
                // An ended exposure starts at the original entry or the
                // immediately preceding reduction. A caller cannot rename or
                // shorten a settled window to create a second cash debit.
                var closing=state.Closed.Single(x=>x.PositionId==e.PositionId &&
                    x.Symbol==e.Symbol && x.ClosedAt==e.CalibratedThrough);
                long canonicalFrom=state.Closed.Where(x=>x.PositionId==e.PositionId &&
                    x.ClosedAt<e.CalibratedThrough).Select(x=>x.ClosedAt)
                    .DefaultIfEmpty(closing.OpenedAt).Max();
                if(from!=canonicalFrom)
                    throw new ArgumentException("NATIVE_LEDGER_CLOSED_FUNDING_START");
                // The window covers the pre-reduction exposure, not just the
                // units closed by the first fill. Later fills and remaining
                // units reconstruct that exposure without altering any fill.
                decimal exposureUnits=state.Closed.Where(x=>x.PositionId==e.PositionId &&
                    x.Symbol==e.Symbol && x.ClosedAt>=e.CalibratedThrough).Sum(x=>x.Units);
                if(state.Positions.TryGetValue(e.PositionId,out var remainder))
                {
                    if(remainder.Symbol!=e.Symbol || remainder.Side!=e.Side)
                        throw new ArgumentException("NATIVE_LEDGER_CLOSED_FUNDING_BINDING");
                    exposureUnits+=remainder.Units;
                }
                if(exposureUnits!=e.Units)
                    throw new ArgumentException("NATIVE_LEDGER_CLOSED_FUNDING_UNITS");
                closedFunding=new(e.EventId,e.PositionId,e.Symbol,e.Side,e.Units,from,
                    e.CalibratedThrough,e.AvailableAt,e.At,e.SignedFinancingEur,e.EvidenceHash);
                state=state with {CashEur=state.CashEur+e.SignedFinancingEur};break;
            case "MARK":break;
            default:throw new ArgumentException("NATIVE_LEDGER_UNKNOWN_EVENT");
        }
        state=state with {Quotes=quotes,Clock=e.At,EventChainHash=Hash(state.EventChainHash+hash)};
        if(e.Kind is "MARK" or "OPEN_FILL" or "CLOSE_FILL" or "FINANCING" or "CLOSED_FUNDING_SETTLEMENT")
        {
            try
            {
                decimal eq=Equity(quotes,e.At),peak=Math.Max(state.ObservedPeakEur,eq);
                state=state with {ObservedPeakEur=peak,MaximumSampledDrawdown=Math.Max(state.MaximumSampledDrawdown,1-eq/peak)};
            }
            catch(InvalidOperationException){state=state with {HistoryEvidenceIncomplete=true};}
        }
        decimal settledNet=closedNetEur+(settlement?.NetEur??0m)+(closedFunding?.SignedDeltaEur??0m);
        Reconcile(settledNet);
        if(validateSummary)_=Summary();
        state.AppliedEventHashes.Add(e.EventId,hash);
        if(e.Kind=="REQUEST_OPEN")state.UsedPositionIds.Add(e.PositionId);
        if(settlement is not null)AppendSettlement(settlement,settledNet);
        if(closedFunding is not null)
        {
            var adjustments=state.ClosedFunding is null?new List<LedgerClosedFundingSettlement>():
                new List<LedgerClosedFundingSettlement>(state.ClosedFunding);
            adjustments.Add(closedFunding);
            state=state with {ClosedFunding=adjustments};
            closedNetEur=settledNet;
        }
    }
    public LedgerSummary Summary(long? observedAt=null)
    {
        long valuationClock=observedAt??state.Clock;
        if(valuationClock<state.Clock)throw new ArgumentException("NATIVE_LEDGER_VALUATION_CLOCK_BEFORE_STATE");
        decimal? equity=null,margin=null;
        try {equity=Equity(state.Quotes,valuationClock);margin=state.Positions.Values.Sum(p=>p.Units*Math.Max(p.MarginPerUnit,Quote(state.Quotes,p.Symbol,valuationClock).MarginPerUnit));}
        catch(InvalidOperationException){}
        return new(state.CashEur,equity,margin,equity-margin,state.ObservedPeakEur,state.MaximumSampledDrawdown,
            state.Positions.Count,state.Pending.Count,completeRoundTrips,closedNetEur,
            state.HistoryEvidenceIncomplete,state.EventChainHash);
    }
    internal LedgerPosition[] PositionSnapshot()=>state.Positions.Values.ToArray();
    public LedgerClosedFragment[] ClosedFragments()=>state.Closed.ToArray();
    public LedgerClosedFundingSettlement[] ClosedFundingSettlements()=>
        state.ClosedFunding?.ToArray()??Array.Empty<LedgerClosedFundingSettlement>();
    internal LedgerClosedFragment LastClosedRoundTrip(string positionId)
        =>state.Closed.Last(x=>x.PositionId==positionId&&x.CompletesRoundTrip);
    internal LedgerClosedFragment[] ClosedFragments(string positionId)
        =>state.Closed.Where(x=>x.PositionId==positionId).ToArray();
    public string Checkpoint()
    {
        string payload=JsonSerializer.Serialize(state);return JsonSerializer.Serialize(new {Payload=payload,Sha256=Hash(payload),MaximumStalenessMs=maximumStalenessMs});
    }
    public static NativeFundedLedger Restore(string checkpoint)
    {
        using var d=JsonDocument.Parse(checkpoint);var root=d.RootElement;string payload=root.GetProperty("Payload").GetString()!;
        if(Hash(payload)!=root.GetProperty("Sha256").GetString())throw new ArgumentException("NATIVE_LEDGER_CHECKPOINT_HASH");
        var restored=JsonSerializer.Deserialize<LedgerState>(payload,Options) ?? throw new ArgumentException("NATIVE_LEDGER_CHECKPOINT_STATE");
        if(restored.Version is not ("mxm-native-funded-ledger-v1" or "mxm-native-funded-ledger-v2" or Version) || !(restored.InitialCashEur==OwnerRiskAuthority.InitialCapitalEur ||
             (restored.InitialCashEur==200m && restored.MonetaryDomain=="FROZEN_MODELED_SETTLEMENT")) ||
           restored.ObservedPeakEur<restored.InitialCashEur || restored.MaximumSampledDrawdown<0)
            throw new ArgumentException("NATIVE_LEDGER_CHECKPOINT_VERSION_OR_CAPITAL");
        restored=restored with {Version=Version,MonetaryDomain=restored.MonetaryDomain??"MODEL_REPLAY"};
        if(restored.MonetaryDomain is not ("MODEL_REPLAY" or "BROKER_EXECUTION_FACT" or "FROZEN_MODELED_SETTLEMENT"))
            throw new ArgumentException("NATIVE_LEDGER_CHECKPOINT_MONETARY_DOMAIN");
        foreach(var key in restored.Positions.Keys.ToArray())restored.Positions[key]=restored.Positions[key] with {MonetaryDomain=restored.Positions[key].MonetaryDomain??"MODEL_REPLAY"};
        var ledger=new NativeFundedLedger(root.GetProperty("MaximumStalenessMs").GetInt64()){state=restored};
        ledger.RebuildSettlementTotals();
        ledger.Reconcile();
        return ledger;
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
