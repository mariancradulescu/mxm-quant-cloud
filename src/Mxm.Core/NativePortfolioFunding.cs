using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// A source adapter supplies verified broker evidence. The engine checks its
// causal availability and binds it to an exact position and exposure window.
public sealed record NativeAccruedFundingEvidence(string PositionId,string Symbol,
    int Side,decimal Units,long FromExclusive,long ThroughInclusive,long AvailableAt,
    decimal? ExactSignedEur,decimal? MaximumTotalDebitEur,string SourceSha256)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? ScenarioId { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? ConditionalSignedEur { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public long? SourceAcquiredAt { get; init; }
    [System.Text.Json.Serialization.JsonIgnore]
    public decimal? LedgerAmount => ExactSignedEur??ConditionalSignedEur;
}

public sealed record NativeFundingOfferEvidence(string Symbol,int Side,decimal Units,long AvailableAt,
    long EffectiveFrom,long NextScheduledManagementAt,long CoveredThrough,decimal MaximumDebitEur,
    string SourceSha256)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? ScenarioId { get; init; }
}

public sealed record NativeFundingExposure(string PositionId,string Symbol,int Side,
    decimal Units,long FromExclusive,decimal BookedSignedEur,bool ExactInLedger,
    decimal? AdditionalDebitCeilingEur,long? ClosedAt,string? EvidenceSha256)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public long? ExactObservedAt { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? ScenarioId { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public long? SourceAcquiredAt { get; init; }
    [System.Text.Json.Serialization.JsonIgnore]
    public string EvidenceClass => ScenarioId is not null && ExactInLedger ? "CONDITIONAL_SCENARIO" :
        ExactInLedger ? "SUPPORTED_LEDGER_AMOUNT" :
        AdditionalDebitCeilingEur.HasValue ? "SUPPORTED_DEBIT_CEILING" : "UNKNOWN_UNBOUNDED";
}

public sealed record NativeFundingCheckpoint(NativeFundingExposure[] Exposures,
    decimal PostedFinancingEur,decimal MaximumSampledFundingAdjustedDrawdown)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? ScenarioId { get; init; }
}

public sealed record NativeFundingCapital(decimal PostedFinancingEur,
    int OutstandingHeldWindows,int OutstandingClosedWindows,decimal? OutstandingDebitCeilingEur,
    decimal? DemonstrableEquityEur,decimal? HeldMarginEur,decimal PendingOpenMarginEur,
    decimal? DemonstrableFreeMarginEur,decimal? ReconciledClosedModelNetEur,
    decimal MaximumSampledFundingAdjustedDrawdown)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? ScenarioId { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? ConditionalEquityEur { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? ConditionalFreeMarginEur { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? ConditionalClosedModelNetEur { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? ConditionalUnmodeledDebitCeilingEur { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public int? ScenarioSettledWindows { get; init; }
    [System.Text.Json.Serialization.JsonIgnore]
    public decimal? ResearchAdmissionEquityEur => ScenarioId is null ? DemonstrableEquityEur : ConditionalEquityEur;
}

internal sealed record NativeObservedFundingRate(string Unit,decimal Long,decimal Short);

// Carries funding evidence and reserves. All actual cash changes are applied
// through FINANCING for active exposure and CLOSED_FUNDING_SETTLEMENT for
// an ended exposure, in the portfolio's one funded ledger.
internal sealed class NativePortfolioFunding
{
    static readonly IComparer<(string PositionId,long From)> ExposureOrder=
        Comparer<(string PositionId,long From)>.Create((a,b)=>
        {
            int c=StringComparer.Ordinal.Compare(a.PositionId,b.PositionId);
            return c==0?a.From.CompareTo(b.From):c;
        });
    readonly Dictionary<(string PositionId,long From),NativeFundingExposure> windows=new();
    readonly Dictionary<string,List<long>> positionWindows=new(StringComparer.Ordinal);
    readonly SortedSet<(string PositionId,long From)> needingEvidence=new(ExposureOrder);
    int exactWindows;
    decimal postedFinancingEur;
    decimal maximumSampledFundingAdjustedDrawdown;

    public string? ScenarioId {get;}
    public NativePortfolioFunding(NativeFundingCheckpoint? saved=null,string? scenarioId=null)
    {
        ScenarioId=saved?.ScenarioId??scenarioId;
        if(ScenarioId is not null && !ValidHash(ScenarioId))
            throw new ArgumentException("FUNDING_SCENARIO_ID_MUST_BE_PROTOCOL_SHA256");
        if(saved is null)return;
        if(saved.Exposures.Any(w=>w.ScenarioId!=ScenarioId))
            throw new ArgumentException("FUNDING_SCENARIO_CHECKPOINT_MISMATCH");
        foreach(var window in saved.Exposures)
            AddWindow(window);
        postedFinancingEur=saved.PostedFinancingEur;
        maximumSampledFundingAdjustedDrawdown=saved.MaximumSampledFundingAdjustedDrawdown;
    }

    public NativeFundingCheckpoint Checkpoint()=>new(InExposureOrder().ToArray(),
        postedFinancingEur,maximumSampledFundingAdjustedDrawdown) {ScenarioId=ScenarioId};

    IEnumerable<NativeFundingExposure> InExposureOrder()=>windows.Values
        .OrderBy(w=>w.PositionId,StringComparer.Ordinal).ThenBy(w=>w.FromExclusive);

    void AddWindow(NativeFundingExposure window)
    {
        var key=(window.PositionId,window.FromExclusive);
        windows.Add(key,window);
        if(!positionWindows.TryGetValue(window.PositionId,out var clocks))
            positionWindows.Add(window.PositionId,clocks=new());
        clocks.Add(window.FromExclusive);
        if(window.ExactInLedger)exactWindows++;
        if(window.ClosedAt is null||!window.ExactInLedger)needingEvidence.Add(key);
    }

    void UpdateWindow(NativeFundingExposure previous,NativeFundingExposure replacement)
    {
        var key=(previous.PositionId,previous.FromExclusive);
        windows[key]=replacement;
        if(previous.ExactInLedger!=replacement.ExactInLedger)exactWindows+=replacement.ExactInLedger?1:-1;
        if(replacement.ClosedAt is not null && replacement.ExactInLedger)needingEvidence.Remove(key);
    }

    IEnumerable<NativeFundingExposure> PositionWindows(string id)
        =>positionWindows.TryGetValue(id,out var clocks)?clocks.Select(at=>windows[(id,at)]):
            Array.Empty<NativeFundingExposure>();

    public NativeFundingExposure[] EvidenceWindows()=>needingEvidence.Select(key=>windows[key]).ToArray();

    public void ValidateHeldBinding(LedgerPosition[] held)
    {
        var active=windows.Values.Where(x=>x.ClosedAt is null).ToArray();
        if(active.Length!=held.Length || held.Any(p=>active.Count(w=>w.PositionId==p.Id &&
            w.Symbol==p.Symbol && w.Side==p.Side && w.Units==p.Units && w.FromExclusive>=p.EntryAt)!=1))
            throw new ArgumentException("FUNDING_CHECKPOINT_HELD_EXPOSURE_MISMATCH");
    }

    static bool ValidHash(string value)=>value is {Length:64} && value.All(Uri.IsHexDigit);

    public void Validate(long at,NativeAccruedFundingEvidence[] evidence)
    {
        var seen=new HashSet<(string,long)>();
        foreach(var proof in evidence)
        {
            var key=(proof.PositionId,proof.FromExclusive);
            if(proof.ScenarioId!=ScenarioId || !seen.Add(key) || !windows.TryGetValue(key,out var window) ||
               window.Symbol!=proof.Symbol || window.Side!=proof.Side || window.Units!=proof.Units ||
               proof.ThroughInclusive!= (window.ClosedAt??at) ||
               proof.ThroughInclusive<=proof.FromExclusive || proof.AvailableAt<=0 ||
               proof.AvailableAt>at || !ValidHash(proof.SourceSha256) ||
               ((proof.ExactSignedEur.HasValue?1:0)+(proof.ConditionalSignedEur.HasValue?1:0)+
                    (proof.MaximumTotalDebitEur.HasValue?1:0)!=1) ||
               (ScenarioId is null ? proof.ConditionalSignedEur.HasValue || proof.SourceAcquiredAt.HasValue :
                    proof.ExactSignedEur.HasValue || proof.SourceAcquiredAt is not >0L) ||
               proof.MaximumTotalDebitEur is <0m ||
               (proof.LedgerAmount.HasValue && proof.AvailableAt<proof.ThroughInclusive) ||
               (window.ClosedAt is not null && window.ExactInLedger &&
                proof.LedgerAmount!=window.BookedSignedEur))
                throw new ArgumentException("FUNDING_EVIDENCE_CLOCK_EXPOSURE_OR_AMOUNT");
        }
    }

    public void Observe(long at,NativeAccruedFundingEvidence[] evidence,
        Action<NativeFundingExposure,decimal,NativeAccruedFundingEvidence> post)
    {
        var byWindow=evidence.ToDictionary(p=>(p.PositionId,p.FromExclusive));
        foreach(var window in EvidenceWindows())
        {
            var key=(window.PositionId,window.FromExclusive);
            if(!byWindow.TryGetValue(key,out var proof))
            {
                if(window.ClosedAt is null)
                    UpdateWindow(window,window with {ExactInLedger=false,AdditionalDebitCeilingEur=null,EvidenceSha256=null});
                continue;
            }
            if(proof.LedgerAmount is decimal exact)
            {
                var delta=exact-window.BookedSignedEur;
                if(delta!=0m)
                {
                    decimal postedTotal=postedFinancingEur+delta;
                    post(window,delta,proof);
                    postedFinancingEur=postedTotal;
                }
                UpdateWindow(window,window with {BookedSignedEur=exact,ExactInLedger=true,
                    AdditionalDebitCeilingEur=0m,EvidenceSha256=proof.SourceSha256,ExactObservedAt=at,
                    SourceAcquiredAt=proof.SourceAcquiredAt});
                continue;
            }
            // The cap refers to total signed financing for this window. Any
            // amount already booked belongs to the same window and stays cash.
            decimal unused=Math.Max(0m,proof.MaximumTotalDebitEur!.Value+window.BookedSignedEur);
            UpdateWindow(window,window with {ExactInLedger=false,AdditionalDebitCeilingEur=unused,
                EvidenceSha256=proof.SourceSha256,SourceAcquiredAt=proof.SourceAcquiredAt});
        }
    }

    public void Open(string id,string symbol,int side,decimal units,long at)
        =>AddWindow(new(id,symbol,side,units,at,0m,true,0m,null,null) {ScenarioId=ScenarioId});

    public bool IsOutstanding(string id)=>PositionWindows(id).Any(x=>!x.ExactInLedger);

    public long? ClosedReconciliationAt(string id,long closedAt,long legacyKnowledgeAt)
    {
        var exposures=PositionWindows(id).ToArray();
        if(exposures.Any(w=>w.ClosedAt is null || !w.ExactInLedger))return null;
        long lastEvidence=exposures.Select(w=>w.ExactObservedAt??legacyKnowledgeAt).DefaultIfEmpty(closedAt).Max();
        return Math.Max(closedAt,lastEvidence);
    }

    public void Close(string id,decimal closedUnits,long at)
    {
        var w=PositionWindows(id).Single(x=>x.ClosedAt is null);
        if(at<=w.FromExclusive && w.ExactInLedger)
        {
            var key=(id,w.FromExclusive);
            windows.Remove(key);
            needingEvidence.Remove(key);
            positionWindows[id].Remove(w.FromExclusive);
            exactWindows--;
        }
        else UpdateWindow(w,w with {ClosedAt=at});
        decimal remaining=w.Units-closedUnits;
        if(remaining>0m)Open(id,w.Symbol,w.Side,remaining,at);
    }

    public NativeFundingCapital Capital(LedgerSummary book,decimal pendingOpenMarginEur) =>
        Capital(book,pendingOpenMarginEur,updateObservedDrawdown:true);

    internal NativeFundingCapital Capital(LedgerSummary book,decimal pendingOpenMarginEur,bool updateObservedDrawdown)
    {
        var unresolved=needingEvidence.Select(key=>windows[key]).Where(x=>!x.ExactInLedger).ToArray();
        int settledExposure=unresolved.Count(x=>x.ClosedAt.HasValue);
        decimal? debitCeiling=unresolved.Any(x=>x.AdditionalDebitCeilingEur is null)?
            null:unresolved.Sum(x=>x.AdditionalDebitCeilingEur!.Value);
        decimal? equity=book.LiquidationEquityEur-debitCeiling;
        if(updateObservedDrawdown && equity is decimal floor)
            maximumSampledFundingAdjustedDrawdown=Math.Max(maximumSampledFundingAdjustedDrawdown,
                1m-floor/book.ObservedPeakEur);
        return new(postedFinancingEur,unresolved.Length-settledExposure,settledExposure,ScenarioId is null?debitCeiling:null,
            ScenarioId is null?equity:null,book.UsedMarginEur,pendingOpenMarginEur,
            ScenarioId is null?equity-book.UsedMarginEur-pendingOpenMarginEur:null,
            ScenarioId is null&&settledExposure==0?book.ClosedNetEur:null,
            Math.Max(book.MaximumSampledDrawdown,maximumSampledFundingAdjustedDrawdown))
            {
                ScenarioId=ScenarioId,
                ConditionalEquityEur=ScenarioId is null?null:equity,
                ConditionalFreeMarginEur=ScenarioId is null?null:equity-book.UsedMarginEur-pendingOpenMarginEur,
                ConditionalClosedModelNetEur=ScenarioId is not null&&settledExposure==0?book.ClosedNetEur:null,
                ConditionalUnmodeledDebitCeilingEur=ScenarioId is null?null:debitCeiling,
                ScenarioSettledWindows=ScenarioId is null?null:exactWindows
            };
    }

    public static decimal? OfferDebit(Ucp1MarketFrame market,int side,decimal units,long at,string? scenarioId=null)
    {
        // The source schedule supplies the next available management clock,
        // including any known market closure.
        var offers=market.FundingOffers?.Where(f=>f.ScenarioId==scenarioId && f.Symbol==market.Symbol && f.Side==side && f.Units==units &&
            f.AvailableAt>0 && f.AvailableAt<=at && f.EffectiveFrom>0 && f.EffectiveFrom<=at &&
            f.NextScheduledManagementAt>=at+300000L && f.CoveredThrough>=f.NextScheduledManagementAt &&
            f.MaximumDebitEur>=0m && ValidHash(f.SourceSha256)).Take(2).ToArray();
        return offers is {Length:1}?offers[0].MaximumDebitEur:null;
    }

    // Normalize the observed quote of a rate, without assigning a period of
    // effectiveness or creating an offer. Percent rates still need the
    // original rollover bid, charge calendar, conversion and deposit rounding.
    internal static NativeObservedFundingRate? InterpretObservedPoint(int? kind,decimal? longRate,
        decimal? shortRate,int? pipPosition,int? digits)
    {
        if(longRate is not decimal buy || shortRate is not decimal sell)return null;
        if(kind==1)return new("ANNUAL_PERCENT_OF_NOTIONAL",buy,sell);
        int? position=kind switch {0=>pipPosition,2=>digits,_=>null};
        if(position is not (>=0 and <=18))return null;
        decimal one=NativeBrokerContractCosts.Pip(position.Value);
        return new("QUOTE_CURRENCY_PER_UNIT_PER_ROLLOVER",buy*one,sell*one);
    }
}
