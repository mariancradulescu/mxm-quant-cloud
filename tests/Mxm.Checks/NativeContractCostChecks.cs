using Mxm.Core;
using System;

static class NativeContractCostChecks
{
    public static void Run(Action<bool,string> check)
    {
        var terms=new NativeObservedContractTerms(
            "EURJPY","JPY",1793765701009L,
            1000m,1000m,100000m,100000m,
            2,300000000L,1,0L,"USD",0,
            0,-0.37m,-1.08m,2,24,1320,3,false,0);
        // Fixed rates and prices are ILLUSTRATIVE. The broker tariff
        // 3 USD/lot per side is authenticated CMA1, not the hypothetical FX.
        var context=new NativeMarketCostContext(2000,161m,161.02m,
            .006m,.006m,.9m,null,33.33m,1000m,.0005m);
        var priced=NativeBrokerContractCosts.Quote(terms,context);
        check(priced.OneSideCommissionEur==.027m &&
            priced.Quote.ExitFeePerUnit==.000027m &&
            priced.Quote.ExitFeeFloor==0m,
            "original CMA1 USD-per-lot exact fee at fixed modeled USD/EUR route");
        check(priced.SpreadRoundTripEur==.12m &&
            priced.SlippageRoundTripEur==.006m &&
            priced.Quote.EurCredit==.006m &&
            !priced.HistoricalExecutionCertified,
            "bid-ask and slippage separated; no historical tariff certificate");
        var source=new NativeFundedLedger(1000);
        const string hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        LedgerEvent E(string id,long at,string kind,decimal price=0,LedgerQuote[]? quotes=null,decimal fee=.027m)=>
            new(id,at,kind,"contract-test","EURJPY",1,1000m,price,fee,.03333m,
                .0005m,0,0,1000,"SYNTHETIC_NATIVE_LEDGER",hash,
                quotes??Array.Empty<LedgerQuote>());
        source.Apply(E("open-request",1000,"REQUEST_OPEN"));
        source.Apply(E("open-fill",2000,"OPEN_FILL",161.0205m,new[]{priced.Quote}));
        var afterOpen=source.Summary();
        check(afterOpen.OpenPositions==1 &&
            afterOpen.CashEur==299.973m && afterOpen.UsedMarginEur==33.33m,
            "one native EUR300 ledger applies authentic rate as conditional fee");
        var exitQuote=NativeBrokerContractCosts.Quote(terms,context with {
            AtUtcMs=4000,Bid=161.10m,Ask=161.12m});
        source.Apply(E("close-request",3000,"REQUEST_CLOSE"));
        source.Apply(E("close-fill",4000,"CLOSE_FILL",161.0995m,
            new[]{exitQuote.Quote}));
        var closed=source.ClosedFragments();
        check(source.Summary().CompleteRoundTrips==1 &&
            closed.Length==1 && closed[0].CommissionsEur==.054m &&
            closed[0].SpreadEur==.12m && closed[0].SlippageEur==.006m &&
            closed[0].NetEur==.420m &&
            source.Summary().CashEur==300.420m,
            "existing ledger posts commission spread and slippage exactly once");
        var restored=NativeFundedLedger.Restore(source.Checkpoint());
        check(restored.Summary()==source.Summary() &&
            restored.ClosedFragments()[0]==closed[0],
            "native restart accounting agrees without parallel cost ledger");

        long wed= new DateTimeOffset(2026,11,4,21,50,0,TimeSpan.Zero)
            .ToUnixTimeMilliseconds();
        decimal? swap=NativeBrokerContractCosts.SignedFinancing(
            terms,wed,wed+20*60000L,1,1000m,.006m,.006m);
        check(swap==-.0666m,
            "real CMA1 Wednesday 22UTC triple pips charged, not UTC midnight");
        check(NativeBrokerContractCosts.SignedFinancing(
            terms,wed,wed+5*60000L,1,1000m,.006m,.006m)==0m,
            "known intraday exposure before rollover has zero financing");
        check(NativeBrokerContractCosts.SignedFinancing(
            terms with {SkipSwapPeriods=null},wed,wed+20*60000L,1,
            1000m,.006m,.006m)==null,
            "unknown rollover skip cannot be assumed zero");
        var feeFloor=terms with {PreciseRateWire=0,PreciseMinimumWire=2000000L};
        var min=NativeBrokerContractCosts.Quote(feeFloor,context);
        check(min.OneSideCommissionEur==.018m,
            "USD minimum commission overrides zero variable rate");
        bool invalid=false;
        try{_ = NativeBrokerContractCosts.Quote(terms,context with {Units=1001m});}
        catch(ArgumentException){invalid=true;}
        check(invalid,"volume step and minimum enforced prospectively");
        var conversion=NativeBrokerContractCosts.Quote(
            terms with {PnlConversionFeeBps=4},context);
        check(conversion.Quote.EurCredit==.0059976m &&
            conversion.Quote.EurDebit==.0060024m,
            "conversion fee follows signed native debit/credit rates");
        // Percentage-of-value tariffs are based on the actual submitted
        // side, not a universal ASK; an implicit ASK for short exits or
        // short entries would silently overcharge / distort NET.
        var equities=terms with {CommissionType=3,PreciseRateWire=5000L};
        var buyPrice=NativeBrokerContractCosts.Quote(equities,context);
        var sellPrice=NativeBrokerContractCosts.Quote(equities,context,
            executionIsBuy:false);
        check(buyPrice.OneSideCommissionEur>sellPrice.OneSideCommissionEur &&
            buyPrice.OneSideCommissionEur-sellPrice.OneSideCommissionEur==.006m,
            "percentage commission follows the execution side bid/ask, not extra spread");
        check(!priced.HistoricalExecutionCertified,
            "synthetic parity never asserts actual broker-funded profit");
    }
}
