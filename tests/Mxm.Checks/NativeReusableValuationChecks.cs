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
        // Compare the allocation-free lookup to the original descending,
        // collect-all semantics, including ties, gaps, and conflicting overlaps.
        var random=new Random(271126);
        var rows=Enumerable.Range(0,256).Select(i=>
        {
            long observed=100+random.Next(0,100);
            var witness=w with {At=observed,SearchFrom=observed-random.Next(0,20),
                SearchThrough=observed+random.Next(0,100),Price=1m+random.Next(0,3)/10m};
            return r with {Symbol=i%3==0?"GBPUSD":"EURUSD",Side=i%2==0?"ASK":"BID",Witness=witness};
        }).Concat(new[]{r,r}).ToArray();
        var indexed=new NativeReusableValuationRegistry(rows);
        bool parity=true;
        foreach(string symbol in new[]{"EURUSD","GBPUSD","ABSENT"})
        foreach(bool bid in new[]{false,true})
        for(long at=75;at<=320;at++)
        {
            var usable=rows.Where(x=>x.Symbol==symbol&&x.Side==(bid?"BID":"ASK"))
                .OrderBy(x=>x.Witness.At).Reverse()
                .Where(x=>x.Witness.At<=at&&x.Witness.SearchFrom<=at&&at<=x.Witness.SearchThrough)
                .Select(x=>x.Witness).ToArray();
            var expected=usable.Length==0||usable.Any(x=>x.At!=usable[0].At||x.Price!=usable[0].Price)
                ?null:usable[0] with {SearchThrough=at};
            parity&=indexed.At(symbol,bid,at)==expected;
        }
        check(parity,"allocation-free registry equals original overlap semantics at every deterministic clock");
        var ledger=new NativeFundedLedger();var before=ledger.Checkpoint();
        var summary=ledger.InspectConditionalValuation(1000,Array.Empty<LedgerQuote>());
        check(summary.CashEur==300m&&summary.LiquidationEquityEur==300m&&ledger.Checkpoint()==before,
            "conditional valuation preserves original cash events and checkpoint");
        var book=new NativeFundedLedger(0L);
        LedgerQuote Q(long clock,decimal bid=100m)=>new("A",clock,bid,bid+1m,1m,1m,0m,0m,1m);
        LedgerEvent E(string kind,long clock,decimal execution=0m)=>new(kind,clock,kind,"P","A",1,1m,
            execution,0m,1m,0m,clock-1,clock-2,1L,"SYNTHETIC_FROZEN_TEST",new string('b',64),new[]{Q(clock)});
        book.Apply(E("REQUEST_OPEN",1000));book.Apply(E("OPEN_FILL",1001,101m));
        var heldCheckpoint=book.Checkpoint();
        check(book.Summary(5000).LiquidationEquityEur is null,"frozen held book retains its missing original mark");
        var measured=book.InspectConditionalValuation(5000,new[]{Q(5000,102m)});
        check(measured.LiquidationEquityEur==301m&&measured.UsedMarginEur==1m,
            "new authentic-shaped held marks recover liquidation equity and margin without a new fill");
        check(book.Checkpoint()==heldCheckpoint&&book.Summary().CashEur==300m,
            "held restatement leaves the original event chain position and cash byte-identical");
    }
}
