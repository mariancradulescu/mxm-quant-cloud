using Mxm.Core;
internal static class NativeReusableValuationChecks
{
    public static void Run(Action<bool,string> check)
    {
        var w=new NativeHistoricalFundingPrefix("AUTHENTIC_LATEST_PREFIX",100,300,200,1.2m,true,true);
        var r=new NativeValuationPrefix("EURUSD","BID",w,new string('a',64));
        var registry=new NativeReusableValuationRegistry(new[]{r});
        check(registry.At("EURUSD",true,199) is null,"registry never borrows a future observation");
        check(registry.At("EURUSD",true,301) is null,"registry never extends proven coverage");
        check(registry.At("EURUSD",true,250)?.PriceAtCharge(250,1000)==1.2m,"registry rebinds only inside proven prefix");
        check(registry.At("EURUSD",false,250) is null,"registry quote sides stay independent");
        var conflict=new NativeReusableValuationRegistry(new[]{r,r with {Witness=w with {Price=1.3m}}});
        check(conflict.At("EURUSD",true,250) is null,"conflicting authentic prefixes remain missing");
        var ledger=new NativeFundedLedger();var before=ledger.Checkpoint();
        var summary=ledger.InspectConditionalValuation(1000,Array.Empty<LedgerQuote>());
        check(summary.CashEur==300m&&summary.LiquidationEquityEur==300m&&ledger.Checkpoint()==before,
            "conditional valuation preserves original cash events and checkpoint");
    }
}
