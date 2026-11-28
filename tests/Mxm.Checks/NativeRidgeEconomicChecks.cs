using Mxm.Core;
internal static class NativeRidgeEconomicChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long at=1793577615000L;
        var contract=new NativeObservedContractTerms("SYNTHETIC","USD",at-1000000,1m,1m,2m,100m,2,0,2,0,null,0,0,0m,0m,4,24,1320,3,false,0,true,false);
        var quote=new LedgerQuote("SYNTHETIC",at,100m,100.01m,1m,1m,.001m,0m,1m);
        NativeBarWindow Window(NativeBarTimeframe tf,int n)
        {long width=(long)tf*60000,last=at/width*width;return new(tf,n,last,at,"SYNTHETIC",NativeBarStatus.Ready,
            Enumerable.Range(0,n).Select(i=>new NativeClosedMarketBar(last-(n-i)*width,last-(n-i-1)*width,
                100m,100.1m,99.9m,100m,100)).ToArray());}
        var windows=NativeClosedMarketContext.CoverageWindows.Select(r=>Window(r.Timeframe,r.Count)).ToArray();
        var prediction=new NativeRidgeEconomicForecast(at,at/86400000*86400000,at/86400000*86400000-1,30,
            30,"LOCAL_RIDGE",1,.2m,.3m,.1m,100m,1m);
        var market=new Ucp1MarketFrame("SYNTHETIC",quote,contract,windows.Single(w=>w.Timeframe==NativeBarTimeframe.M5).Bars,
            windows.Single(w=>w.Timeframe==NativeBarTimeframe.M15).Bars,0m,"SYNTHETIC")
        {ClosedBars=new(at,windows),EconomicTransitionWindows=new[]{Window(NativeBarTimeframe.M5,72),Window(NativeBarTimeframe.M15,72),Window(NativeBarTimeframe.H1,72)},
            EurTickSize=.01m,RecoveryRidge=new[]{prediction},EurDatedMarginScenario=true,
            EurMargins=new[]{new NativeEurMarginObservation(1,1m,1m,at,new string('a',64))},
            FundingOffers=new[]{new NativeFundingOfferEvidence("SYNTHETIC",1,1m,at,at,at+3600000,at+3600000,0m,new string('a',64))
                {ScenarioId=new string('b',64)}}};
        var profile=new NativeEurDevelopmentProfile(UseAvailableContext:true,DistributionTargetRanges:2.5m)
        {EconomicMechanism=NativeEconomicMechanisms.Scored,EconomicManagement="MONETARY_REDUCE",EconomicManagementTimeframe="M15",
            CompeteEconomicFamilies=true,IncludeRecoveredEconomicFamilies=true,RecoveredRidgeHorizons=1,
            ObserveIntentExecutionOnTicks=true,ModeledStopLatencyMs=100,EconomicGeometryTimeframe="M15",EconomicStopRanges=.75m,
            KeepAdmissionRiskAtFill=true,ResizeWithinAdmissionRiskAtFill=true,ReserveObservedBarGaps=true,
            AnchorEconomicGeometryToClosedStructure=true,EconomicStructureLookbackBars=6};
        NativeUnifiedPortfolioEngine Book(NativeEurDevelopmentProfile p)=>new(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            fundingScenarioId:new string('b',64),eurDevelopmentProfile:p);
        Ucp1DecisionSignal[] Offers(Ucp1MarketFrame m,NativeEurDevelopmentProfile p)=>
            Book(p).DescribeEurGeneral(m,at,new(at,new[]{m}));
        var offers=Offers(market,profile);
        check(offers.Length==1&&offers[0].Family=="RECOVERED_RIDGE_30_LOCAL_RIDGE"&&offers[0].GeneralGeometry?.Target==100.3m,
            "Ridge creates its own legal native target geometry on closed context, not a horizon time exit");
        check(Offers(market,profile with {RecoveredRidgeHorizons=0}).Length==0&&
            Offers(market,profile with {RecoveredRidgeHorizons=2}).Length==0,
            "Disabled Ridge and an unmatched horizon preserve the original candidate set");
        check(Offers(market with {RecoveryRidge=new[]{prediction with {LatestTrainingAt=prediction.FitBefore}}},profile).Length==0&&
            Offers(market with {RecoveryRidge=new[]{prediction with {DecisionAt=at-1}}},profile).Length==0,
            "Future training labels and forecasts for a different decision cannot authorize Ridge entries");
        var book=Book(profile);var frame=new Ucp1Frame(at,new[]{market});book.Advance(frame);
        check(book.ModelSummary.PendingIntents==1,"Ridge enters the common EUR300 funded admission and pending reservation");
        var ids=book.IntentWatches().Select(x=>x.PositionId).ToArray();long next=at+200;
        book.Advance(frame with {At=next,Markets=new[]{market with {Quote=quote with {At=next}}},
            Protection=new(true,Array.Empty<Ucp1StopTouch>(),Array.Empty<Ucp1StopQuote>(),Array.Empty<string>()){ExecutableIntentIds=ids}});
        check(book.ModelSummary.OpenPositions==1&&book.ModelSummary.PendingIntents==0,
            "Ridge admission becomes a same-ledger modeled fill only on the later executable witness");
    }
}
