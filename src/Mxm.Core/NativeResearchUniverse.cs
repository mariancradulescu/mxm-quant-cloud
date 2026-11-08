using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Read-only product input surface: proactively observe configured symbols before
// there is a position in them. Never creates an opportunity or order permission.
public sealed record NativeResearchUniversePlan(
    string[] Symbols,string[] ResearchSymbols,string[] Unavailable,string Status);

public static class NativeResearchUniverse
{
    public const int MaxResearchSymbols = 32;
    public const int MaxConfiguredResearchSymbols = 256;

    public static NativeResearchUniversePlan Resolve(string? requested,string chartSymbol,
        IEnumerable<string>? exposureSymbols,Func<string,bool> isAvailable,int sweep=0)
    {
        if(isAvailable is null)throw new ArgumentNullException(nameof(isAvailable));
        var forced=(exposureSymbols??Array.Empty<string>())
            .Where(x=>!string.IsNullOrWhiteSpace(x))
            .Concat(string.IsNullOrWhiteSpace(chartSymbol)
                ? Array.Empty<string>() : new[]{chartSymbol})
            .Distinct(StringComparer.Ordinal).ToArray();
        NativeResearchUniversePlan Reject(string reason)=>
            new(forced,Array.Empty<string>(),Array.Empty<string>(),reason);

        if(requested is null || requested.Length>16384 || sweep<0)
            return Reject("NATIVE_UNIVERSE_INVALID_CONFIGURATION");
        var names=requested.Split(new[]{',',';'},StringSplitOptions.TrimEntries|
            StringSplitOptions.RemoveEmptyEntries)
            .Distinct(StringComparer.Ordinal).ToArray();
        if(names.Length>MaxConfiguredResearchSymbols ||
           names.Any(x=>x.Length>64 || x.Any(c=>!(char.IsLetterOrDigit(c)||
                    c is '.' or '-' or '_' or '#'))))
            return Reject("NATIVE_UNIVERSE_INVALID_OR_TOO_LARGE");
        var available=new List<string>();
        var unavailable=new List<string>();
        // Deterministic bounded rotation: more research symbols can be
        // explored over successive completed observation cycles, without
        // suppressing ANY model or broker position outside the current slice.
        var window=names.Length<=MaxResearchSymbols?names:
            Enumerable.Range(0,MaxResearchSymbols).Select(i=>
                names[(int)(((long)sweep*MaxResearchSymbols+i)%names.Length)]).ToArray();
        foreach(var name in window)
        {
            if(isAvailable(name))available.Add(name);
            else unavailable.Add(name);
        }
        return new(forced.Concat(available).Distinct(StringComparer.Ordinal).ToArray(),
            available.ToArray(),unavailable.ToArray(),
            unavailable.Count>0?"NATIVE_UNIVERSE_PARTIAL_BROKER_AVAILABILITY":
                names.Length>MaxResearchSymbols?
                    "NATIVE_UNIVERSE_ROTATING_OBSERVATION_ONLY":
                    "NATIVE_UNIVERSE_CONFIGURED_OBSERVATION_ONLY");
    }
}

// Current cTrader account/broker snapshot only: margin can depend on existing
// exposure and does NOT certify portfolio feasibility, past costs, or fills.
public sealed record NativeResearchMarketTerms(string Symbol,bool TradingEnabled,
    double Bid,double Ask,double MinimumVolumeUnits,double BuyMinimumMarginEur,
    double SellMinimumMarginEur);
public sealed record NativeResearchMarketScreen(string Symbol,decimal? SpreadBps,
    bool QuoteUsable,bool EitherDirectionWithinInitial300,
    bool BothDirectionsWithinStressed210,string Status);

public static class NativeResearchMarketCapacity
{
    public static NativeResearchMarketScreen Screen(NativeResearchMarketTerms t)
    {
        NativeResearchMarketScreen Unknown(string reason)=>
            new(t.Symbol,null,false,false,false,reason);
        if(string.IsNullOrWhiteSpace(t.Symbol)||!t.TradingEnabled)
            return Unknown("BROKER_SYMBOL_UNAVAILABLE");
        var values=new[]{t.Bid,t.Ask,t.MinimumVolumeUnits,
            t.BuyMinimumMarginEur,t.SellMinimumMarginEur};
        if(values.Any(x=>!double.IsFinite(x)||x<0||x>1e12)||
           t.Bid<=0||t.Ask<t.Bid||t.MinimumVolumeUnits<=0||
           t.BuyMinimumMarginEur<=0||t.SellMinimumMarginEur<=0)
            return Unknown("BROKER_MARK_OR_MINIMUM_MARGIN_UNKNOWN");
        decimal bid=(decimal)t.Bid,ask=(decimal)t.Ask;
        decimal buy=(decimal)t.BuyMinimumMarginEur;
        decimal sell=(decimal)t.SellMinimumMarginEur;
        decimal initial=OwnerRiskAuthority.InitialCapitalEur;
        decimal stressed=initial*(1-OwnerRiskAuthority.MaximumSystemDrawdown);
        return new(t.Symbol,10000m*(ask-bid)/((ask+bid)/2m),true,
            Math.Min(buy,sell)<=initial,Math.Max(buy,sell)<=stressed,
            "BROKER_PRESENT_SNAPSHOT_ONLY_NOT_FINANCED_NET");
    }
}
