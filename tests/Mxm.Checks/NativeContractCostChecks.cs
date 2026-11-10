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
        var route=new[] {
            new NativeOriginalFxHop("USDJPY","USD","JPY",2000,150m,150.02m,true),
            new NativeOriginalFxHop("EURUSD","EUR","USD",2000,1.10m,1.1002m,true)
        };
        var originalMark=new NativeOriginalOpenApiMarketMark(2000,"EURJPY",161m,161.02m,
            1m,1m,.9m,33.33m,.0005m,terms,null,route);
        var routed=NativeOriginalOpenApiProductAdapter.Convert(
            new NativeOriginalOpenApiTape("SYNTHETIC_ROUTE_ADAPTER_ONLY",
                Array.Empty<NativeHistoricalBars>(),new[]{originalMark}));
        var expected=NativeBrokerContractCosts.ComposeCausalQuoteToEur("JPY",2000,route);
        check(routed.Quotes[0].Quote.EurCredit==expected.CreditToEur &&
              routed.Quotes[0].Quote.EurDebit==expected.DebitToEur,
            "native original adapter prices JPY from explicit causal route instead of supplied placeholder rates");
        var stressed=new NativeProductAdverseBook();
        const string stressHash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        var stressQuote=new LedgerQuote("EURJPY",1000,161m,161.02m,.006m,.006m,0,0,.301m);
        var intent=new LedgerEvent("stress-request",1000,"REQUEST_OPEN","stress-open","EURJPY",1,
            1000,0,0,.301m,0,0,0,1000,"SYNTHETIC_MARGIN_RECHECK",stressHash,new[]{stressQuote});
        stressed.Apply(intent);
        stressed.Apply(intent with {EventId="stress-fill",At=2000,Kind="OPEN_FILL",
            ExecutionPrice=161.02m,Quotes=new[]{stressQuote with {At=2000}}});
        check(!stressed.Complete && stressed.Summary is null &&
              stressed.FailureKind=="UNFINANCEABLE_OPEN_AT_STRESSED_MARK" &&
              stressed.FailureAt==2000 && stressed.FailureEventKind=="OPEN_FILL",
            "adverse funding failure has its own classification and no invented completed NET");
        var restoredStress=NativeProductAdverseBook.Restore(stressed.Export());
        check(restoredStress.FailureKind==stressed.FailureKind && restoredStress.FailureAt==2000,
            "adverse failure classification survives the existing checkpoint");
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
            buyPrice.OneSideCommissionEur-sellPrice.OneSideCommissionEur==.00006m,
            "percentage commission follows the execution side bid/ask, not extra spread");
        // Synthetic prices test arithmetic only, NEVER claim these
        // specific HKD source quotes came from the original broker.
        long fxAt=1793765701009L;
        var usdToEur=NativeBrokerContractCosts.ComposeCausalQuoteToEur(
            "USD",fxAt,new[]{
                new NativeOriginalFxHop("EURUSD","EUR","USD",fxAt-1000,
                    1.08m,1.09m,true)
            });
        check(usdToEur.CreditToEur==1m/1.09m &&
            usdToEur.DebitToEur==1m/1.08m &&
            usdToEur.RouteSymbols.Length==1,
            "real BID/ASK reverse pair produces distinct signed USD to EUR rates");
        var chain=new[]{
            new NativeOriginalFxHop("USDHKD","USD","HKD",fxAt-1000,
                7.79m,7.81m,true),
            new NativeOriginalFxHop("EURUSD","EUR","USD",fxAt-1000,
                1.08m,1.09m,true)
        };
        var hkd=NativeBrokerContractCosts.ComposeCausalQuoteToEur(
            "HKD",fxAt,chain);
        check(hkd.CreditToEur==(1m/7.81m)/1.09m &&
            hkd.DebitToEur==(1m/7.79m)/1.08m &&
            hkd.DebitToEur>hkd.CreditToEur &&
            hkd.RouteSymbols.Length==2,
            "multi-hop currency route composes the causal two-sided spread");
        bool RejectFx(NativeOriginalFxHop[] hops)
        {
            try{
                _=NativeBrokerContractCosts.ComposeCausalQuoteToEur(
                    "HKD",fxAt,hops);
                return false;
            }
            catch(ArgumentException){return true;}
        }
        check(!RejectFx(chain),
            "valid synthetic route passes only when fully connected");
        check(RejectFx(new[]{chain[0]}) &&
            RejectFx(new[]{chain[0],chain[1] with {AtUtcMs=fxAt+1}}) &&
            RejectFx(new[]{chain[0] with {Bid=0m},chain[1]}) &&
            RejectFx(new[]{chain[0] with {OriginalBrokerAuthenticated=false},chain[1]}),
            "missing EUR leg, future quote, invalid bid and unauthenticated hop all rejected");
        bool wrongFeeRejected=false;
        try{
            _=NativeBrokerContractCosts.Quote(
                terms with {MinimumCommissionAsset="HKD",
                    PreciseMinimumWire=2000000L},context);
        }catch(ArgumentException){wrongFeeRejected=true;}
        check(wrongFeeRejected,"missing nonUSD minimum fee currency must never be priced as USD");
        var fundedFee=NativeBrokerContractCosts.Quote(
            terms with {MinimumCommissionAsset="HKD",
                PreciseMinimumWire=2000000L},
            context with {MinimumFeeAssetToEur=hkd.DebitToEur});
        check(fundedFee.OneSideCommissionEur>0m &&
            fundedFee.Quote.ExitFeeFloor>0m,
            "existing native cost model accepts only explicit nonUSD fee route");
        check(!priced.HistoricalExecutionCertified,
            "synthetic parity never asserts actual broker-funded profit");
    }
}
