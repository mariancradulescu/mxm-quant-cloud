using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// A source adapter supplies verified broker evidence. The engine checks its
// causal availability and binds it to an exact position and exposure window.
public sealed record NativeAccruedFundingEvidence(string PositionId,string Symbol,
    int Side,decimal Units,long FromExclusive,long ThroughInclusive,long AvailableAt,
    decimal? ExactSignedEur,decimal? MaximumTotalDebitEur,string SourceSha256);

public sealed record NativeFundingOfferEvidence(string Symbol,int Side,decimal Units,long AvailableAt,
    long EffectiveFrom,long NextScheduledManagementAt,long CoveredThrough,decimal MaximumDebitEur,
    string SourceSha256);

public sealed record NativeFundingExposure(string PositionId,string Symbol,int Side,
    decimal Units,long FromExclusive,decimal BookedSignedEur,bool ExactInLedger,
    decimal? AdditionalDebitCeilingEur,long? ClosedAt,string? EvidenceSha256);

public sealed record NativeFundingCheckpoint(NativeFundingExposure[] Exposures,
    decimal PostedFinancingEur,decimal MaximumSampledFundingAdjustedDrawdown);

public sealed record NativeFundingCapital(decimal PostedFinancingEur,
    int OutstandingHeldWindows,int OutstandingClosedWindows,decimal? OutstandingDebitCeilingEur,
    decimal? DemonstrableEquityEur,decimal? HeldMarginEur,decimal PendingOpenMarginEur,
    decimal? DemonstrableFreeMarginEur,decimal? ReconciledClosedModelNetEur,
    decimal MaximumSampledFundingAdjustedDrawdown);

// Carries funding evidence and reserves. All actual cash changes are applied
// through FINANCING for active exposure and CLOSED_FUNDING_SETTLEMENT for
// an ended exposure, in the portfolio's one funded ledger.
internal sealed class NativePortfolioFunding
{
    readonly Dictionary<(string PositionId,long From),NativeFundingExposure> windows=new();
    decimal postedFinancingEur;
    decimal maximumSampledFundingAdjustedDrawdown;

    public NativePortfolioFunding(NativeFundingCheckpoint? saved=null)
    {
        if(saved is null)return;
        foreach(var window in saved.Exposures)
            windows.Add((window.PositionId,window.FromExclusive),window);
        postedFinancingEur=saved.PostedFinancingEur;
        maximumSampledFundingAdjustedDrawdown=saved.MaximumSampledFundingAdjustedDrawdown;
    }

    public NativeFundingCheckpoint Checkpoint()=>new(InExposureOrder().ToArray(),
        postedFinancingEur,maximumSampledFundingAdjustedDrawdown);

    IEnumerable<NativeFundingExposure> InExposureOrder()=>windows.Values
        .OrderBy(w=>w.PositionId,StringComparer.Ordinal).ThenBy(w=>w.FromExclusive);

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
            if(!seen.Add(key) || !windows.TryGetValue(key,out var window) ||
               window.Symbol!=proof.Symbol || window.Side!=proof.Side || window.Units!=proof.Units ||
               proof.ThroughInclusive!= (window.ClosedAt??at) ||
               proof.ThroughInclusive<=proof.FromExclusive || proof.AvailableAt<=0 ||
               proof.AvailableAt>at || !ValidHash(proof.SourceSha256) ||
               (proof.ExactSignedEur.HasValue==proof.MaximumTotalDebitEur.HasValue) ||
               proof.MaximumTotalDebitEur is <0m ||
               (proof.ExactSignedEur.HasValue && proof.AvailableAt<proof.ThroughInclusive) ||
               (window.ClosedAt is not null && window.ExactInLedger &&
                proof.ExactSignedEur!=window.BookedSignedEur))
                throw new ArgumentException("FUNDING_EVIDENCE_CLOCK_EXPOSURE_OR_AMOUNT");
        }
    }

    public void Observe(NativeAccruedFundingEvidence[] evidence,
        Action<NativeFundingExposure,decimal,NativeAccruedFundingEvidence> post)
    {
        var byWindow=evidence.ToDictionary(p=>(p.PositionId,p.FromExclusive));
        foreach(var window in InExposureOrder().ToArray())
        {
            var key=(window.PositionId,window.FromExclusive);
            if(!byWindow.TryGetValue(key,out var proof))
            {
                if(window.ClosedAt is null)
                    windows[key]=window with {ExactInLedger=false,AdditionalDebitCeilingEur=null,EvidenceSha256=null};
                continue;
            }
            // A settled closed exposure is a durable idempotence tombstone.
            // Validate has already rejected contradictory replacement evidence.
            if(window.ClosedAt is not null && window.ExactInLedger)continue;
            if(proof.ExactSignedEur is decimal exact)
            {
                var delta=exact-window.BookedSignedEur;
                if(delta!=0m)
                {
                    post(window,delta,proof);
                    postedFinancingEur+=delta;
                }
                windows[key]=window with {BookedSignedEur=exact,ExactInLedger=true,
                    AdditionalDebitCeilingEur=0m,EvidenceSha256=proof.SourceSha256};
                continue;
            }
            // The cap refers to total signed financing for this window. Any
            // amount already booked belongs to the same window and stays cash.
            decimal unused=Math.Max(0m,proof.MaximumTotalDebitEur!.Value+window.BookedSignedEur);
            windows[key]=window with {ExactInLedger=false,AdditionalDebitCeilingEur=unused,
                EvidenceSha256=proof.SourceSha256};
        }
    }

    public void Open(string id,string symbol,int side,decimal units,long at)
        =>windows.Add((id,at),new(id,symbol,side,units,at,0m,true,0m,null,null));

    public bool IsOutstanding(string id)=>windows.Values.Any(x=>x.PositionId==id&&!x.ExactInLedger);

    public void Close(string id,decimal closedUnits,long at)
    {
        var active=windows.Single(x=>x.Key.PositionId==id&&x.Value.ClosedAt is null);
        var w=active.Value;
        if(at<=w.FromExclusive && w.ExactInLedger)windows.Remove(active.Key);
        else windows[active.Key]=w with {ClosedAt=at};
        decimal remaining=w.Units-closedUnits;
        if(remaining>0m)Open(id,w.Symbol,w.Side,remaining,at);
    }

    public NativeFundingCapital Capital(LedgerSummary book,decimal pendingOpenMarginEur)
    {
        var unresolved=InExposureOrder().Where(x=>!x.ExactInLedger).ToArray();
        int settledExposure=unresolved.Count(x=>x.ClosedAt.HasValue);
        decimal? debitCeiling=unresolved.Any(x=>x.AdditionalDebitCeilingEur is null)?
            null:unresolved.Sum(x=>x.AdditionalDebitCeilingEur!.Value);
        decimal? equity=book.LiquidationEquityEur-debitCeiling;
        if(equity is decimal floor)
            maximumSampledFundingAdjustedDrawdown=Math.Max(maximumSampledFundingAdjustedDrawdown,
                1m-floor/book.ObservedPeakEur);
        return new(postedFinancingEur,unresolved.Length-settledExposure,settledExposure,debitCeiling,
            equity,book.UsedMarginEur,pendingOpenMarginEur,
            equity-book.UsedMarginEur-pendingOpenMarginEur,
            settledExposure==0?book.ClosedNetEur:null,
            Math.Max(book.MaximumSampledDrawdown,maximumSampledFundingAdjustedDrawdown));
    }

    public static decimal? OfferDebit(Ucp1MarketFrame market,int side,decimal units,long at)
    {
        // The source schedule supplies the next available management clock,
        // including any known market closure.
        var offers=market.FundingOffers?.Where(f=>f.Symbol==market.Symbol && f.Side==side && f.Units==units &&
            f.AvailableAt>0 && f.AvailableAt<=at && f.EffectiveFrom>0 && f.EffectiveFrom<=at &&
            f.NextScheduledManagementAt>=at+300000L && f.CoveredThrough>=f.NextScheduledManagementAt &&
            f.MaximumDebitEur>=0m && ValidHash(f.SourceSha256)).Take(2).ToArray();
        return offers is {Length:1}?offers[0].MaximumDebitEur:null;
    }
}
