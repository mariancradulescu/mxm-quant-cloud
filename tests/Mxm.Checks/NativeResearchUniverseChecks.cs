using System;
using System.Linq;
using Mxm.Core;

public static class NativeResearchUniverseChecks
{
    public static void Run(Action<bool,string> check)
    {
        var plan=NativeResearchUniverse.Resolve("EURUSD;NAS100;MISSING;EURUSD",
            "US500",new[]{"AUDUSD","GBPUSD"},
            name=>name is "EURUSD" or "NAS100");
        check(plan.ResearchSymbols.SequenceEqual(new[]{"EURUSD","NAS100"})&&
              plan.Unavailable.SequenceEqual(new[]{"MISSING"})&&
              plan.Symbols.SequenceEqual(new[]{"AUDUSD","GBPUSD","US500","EURUSD","NAS100"}),
              "read-only multiasset universe includes never-held markets and preserves all broker exposure");
        var empty=NativeResearchUniverse.Resolve("","US500",new[]{"GBPUSD"},
            _=>true);
        check(empty.ResearchSymbols.Length==0&&
              empty.Symbols.SequenceEqual(new[]{"GBPUSD","US500"}),
              "empty research universe preserves existing account observation lanes");
        var tooLarge=NativeResearchUniverse.Resolve(string.Join(",",Enumerable.Range(1,13)
            .Select(x=>"SYM"+x)),"US500",new[]{"HELD"},_=>true);
        check(tooLarge.ResearchSymbols.Length==0&&
              tooLarge.Symbols.SequenceEqual(new[]{"HELD","US500"})&&
              tooLarge.Status=="NATIVE_UNIVERSE_INVALID_OR_TOO_LARGE",
              "oversized universe cannot silently truncate while hiding held exposure");
        var malformed=NativeResearchUniverse.Resolve("EURUSD,GBP/USD","US500",
            Array.Empty<string>(),_=>true);
        check(malformed.ResearchSymbols.Length==0&&malformed.Symbols.Length==1,
            "invalid research name fails closed without suppressing chart monitoring");
        var terms=new NativeResearchMarketTerms("EURUSD",true,
            1.1000,1.1001,1000,23,25);
        var screen=NativeResearchMarketCapacity.Screen(terms);
        check(screen.QuoteUsable&&screen.SpreadBps>0&&
              screen.EitherDirectionWithinInitial300&&
              screen.BothDirectionsWithinStressed210&&
              screen.Status=="BROKER_PRESENT_SNAPSHOT_ONLY_NOT_FINANCED_NET",
              "current bid ask and both sided minimum margin screen remain non-financed");
        var expensive=NativeResearchMarketCapacity.Screen(terms with {
            BuyMinimumMarginEur=190,SellMinimumMarginEur=220});
        check(expensive.EitherDirectionWithinInitial300&&
              !expensive.BothDirectionsWithinStressed210,
              "300 EUR static minimum-margin possibility does not claim 210 EUR downside capacity");
        var impossible=NativeResearchMarketCapacity.Screen(terms with {
            BuyMinimumMarginEur=310,SellMinimumMarginEur=320});
        check(!impossible.EitherDirectionWithinInitial300,
              "minimum volume beyond 300 EUR is excluded from initial static capacity");
        var invalid=NativeResearchMarketCapacity.Screen(terms with {
            Ask=double.NaN});
        check(!invalid.QuoteUsable&&!invalid.EitherDirectionWithinInitial300,
              "invalid broker quote never becomes candidate capital evidence");
    }
}
