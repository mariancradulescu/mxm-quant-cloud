using Mxm.Core;
using Mxm.Cloud;
using static Cpe1IntegratedEconomicChecks;

internal static class NativeEurPortfolioChecks
{
    const long Step=300_000L;
    static readonly long Origin=new DateTimeOffset(2026,11,24,14,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly string Proof=new string('a',64);

    static Ucp1Frame OfficialShape(int slot,int symbols,long? day=null,decimal bid=100.95m,bool offer=true)
    {
        long origin=day??Origin;
        long at=origin+slot*Step;
        var frame=Frame(origin,at,bid,unknownSwap:true);
        return frame with {Markets=Enumerable.Range(0,symbols).Select(i=>
        {
            var market=Named(frame.Markets[0],"MARKET"+i);
            return market with
            {
                EurMargins=new[]{new NativeEurMarginObservation(1,1m,1m,at,Proof)},
                FundingOffers=offer?new[]{new NativeFundingOfferEvidence(market.Symbol,1,1m,at,at,at+Step,
                    at+Step,0m,Proof)}:null
            };
        }).ToArray()};
    }

    internal static void Run(Action<bool,string> check)
    {
        check(NativeExecutableEconomics.TradeStopReached(1,99m,100m)&&
              NativeExecutableEconomics.TradeStopReached(-1,101m,100m)&&
              NativeExecutableEconomics.TradeStopReached(-1,100m,100m)&&
              !NativeExecutableEconomics.TradeStopReached(1,101m,100m)&&
              !NativeExecutableEconomics.TradeStopReached(-1,99m,100m),
            "The executable Trade stop comparison respects direction, gaps and equality");
        var first=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst);
        var rank=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank);
        var cash=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurCash);
        var parity=new NativeUnifiedCloudParityAdapter(NativeUnifiedPortfolioEngine.EurFirst);
        var input=OfficialShape(1,3);
        var initial=first.Advance(input);
        check(initial==parity.Observe(input) && initial is {Pending:3,Held:0,
            FundingCapital:{PendingOpenMarginEur:3m,DemonstrableFreeMarginEur:297m}},
            "EUR FIRST reserves three simultaneous positions in a single 300 EUR book");
        check(rank.Advance(input).Pending==0 && rank.EurOpportunityReceipts.Any(x=>
            x.Decision=="WAIT_RECONCILED_PAYOFF_EVIDENCE"),
            "EUR RANK waits with no causally reconciled payoffs");
        check(cash.Advance(input) is {Held:0,Pending:0,ModelBook.CashEur:300m},
            "EUR CASH receives the same input and preserves its own 300 EUR");
        var next=OfficialShape(2,3);
        var later=first.Advance(next);
        check(later==parity.Observe(next) && later is {Held:3,Pending:0,
            FundingCapital:{HeldMarginEur:3m,PendingOpenMarginEur:0m}},
            "Three witnessed fills are repriced and equity-admitted after Pending");
        var restored=NativeUnifiedPortfolioEngine.Restore(first.Checkpoint());
        check(restored.ModelSummary==first.ModelSummary,"EUR checkpoint retains common funded book");
        var known=later.FundingCapital!;
        const string missingMark="MISSING_CURRENT_LIQUIDATION_MARK";
        check(NativeUnifiedPortfolioEngine.EurRejectedCapital(missingMark,later.ModelBook,
                  known with { OutstandingDebitCeilingEur=null })=="WAIT_UNBOUNDED_PORTFOLIO_FUNDING"&&
              NativeUnifiedPortfolioEngine.EurRejectedCapital(missingMark,
                  later.ModelBook with {LiquidationEquityEur=null},known)=="WAIT_"+missingMark,
            "EUR distinguishes missing collateral marks from fully marked equity with unbounded carry");
        ExplicitScenarioContinuity(check);
        ExplicitScenarioMultiDay(check);
        const long charge=1794002400000L;
        var bid=new NativeConditionalRolloverSide(charge-70_000,new long[]{100_000,100_001},true,charge+100_000);
        var ask=new NativeConditionalRolloverSide(charge-65_000,new long[]{100_010,100_012},true,charge+100_000);
        var fx=NativeConditionalRollover.UsdToEur(bid,ask,charge);
        check(fx is not null && fx.DebitToEur==1m && fx.CreditToEur==1m/1.00012m &&
            NativeConditionalRollover.MarketBid(bid,charge,-1m)==1.00001m,
            "Conditional rollover uses observed adverse endpoints without extending execution quote age");
        check(NativeConditionalRollover.UsdToEur(bid with {At=charge+1},ask,charge) is null &&
            NativeConditionalRollover.MarketBid(bid with {Complete=false},charge,-1m) is null,
            "Conditional rollover rejects post-charge and incomplete witnesses");
        LateNetChangesRanking(check);
        ContractClocksAndDirectionalCosts(check);
        GeneralEurChoosesFundedCombination(check);
        var flexible=input.Markets[0] with {EurNativeClock=true};
        check(NativeUnifiedPortfolioEngine.EurFrameFollows(flexible,input.At+1_000,input.At+Step+2_000)&&
            !NativeUnifiedPortfolioEngine.EurFrameFollows(flexible,input.At+1_000,input.At+2*Step+2_000)&&
            !NativeUnifiedPortfolioEngine.EurFrameFollows(input.Markets[0],input.At+1_000,input.At+Step+2_000),
            "Native platform margin observation jitter permits adjacent slots but cannot bridge a missing slot");
        const long day=86_400_000L;
        var opens=new[]{Origin,Origin+day,Origin+4*day};
        NativeClosedMarketBar Read(int index)
        {
            if(index==2)throw new InvalidOperationException("The active daily OHLC must never be read");
            return new(opens[index],opens[index]+day,100m,102m,99m,101m,100);
        }
        var ready=NativeClosedMarketContext.WitnessedDailySessions(2,opens[2]+15_000,opens[2]+1,"TEST_D1",
            opens.Length,i=>opens[i],Read);
        var tooEarly=NativeClosedMarketContext.WitnessedDailySessions(2,opens[2],opens[2]-1,"TEST_D1",
            opens.Length,i=>opens[i],Read);
        check(ready is {Ready:true,DailyCalendarBreaks:1}&&ready.Bars[1].OpenAt==opens[1]&&!tooEarly.Ready,
            "Daily EUR context retains a calendar gap and requires a witnessed active successor");
    }

    static void GeneralEurChoosesFundedCombination(Action<bool,string> check)
    {
        const long day=86_400_000L;
        Ucp1Frame Shape(long at)
        {
            var shape=OfficialShape(1,1,at-Step);
            var windows=NativeClosedMarketContext.CoverageWindows.Select(r=>
            {
                long width=NativeClosedMarketContext.Duration(r.Timeframe);
                long close=at-1;
                var bars=Enumerable.Range(0,r.Count).Select(i=>new NativeClosedMarketBar(
                    close-(r.Count-i)*width,close-(r.Count-i-1)*width,100m,100.40m,99.80m,100.20m,100)).ToArray();
                return new NativeBarWindow(r.Timeframe,r.Count,close,close,"SYNTHETIC",NativeBarStatus.Ready,bars);
            }).ToArray();
            return shape with {Markets=new[]{("A",180m),("B",95m),("C",95m)}.Select(x=>
            {
                var m=Named(shape.Markets[0],x.Item1);
                return m with {Quote=m.Quote with {Bid=100.20m,Ask=100.22m,MarginPerUnit=x.Item2},
                    M5=windows[1].Bars,M15=windows[2].Bars,EurTickSize=.01m,OfficialAssetClass="SYNTHETIC",
                    ClosedBars=new(at,windows),
                    EurMargins=new[]{new NativeEurMarginObservation(1,1m,x.Item2,at,Proof)},
                    FundingOffers=new[]{new NativeFundingOfferEvidence(m.Symbol,1,1m,at,at,at+Step,at+Step,0m,Proof)}};
            }).ToArray()};
        }
        var probe=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe);
        var fit=Shape(Origin);
        var observed=probe.Advance(fit);
        check(observed.Pending>0&&probe.EurOpportunityReceipts.Any(x=>
            x.Family==NativeGeneralOpportunity.Distribution&&x.Context?.MarketState?.Length==16),
            "General EUR evaluates broad direction, witnessed frames and net geometry in Core");
        var calibration=probe.ExportEurCalibration();
        var uncalibrated=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralSelect);
        var frame=Shape(Origin+Step);
        check(uncalibrated.Advance(frame).Pending==0&&uncalibrated.EurOpportunityReceipts.Any(x=>
            x.Decision=="WAIT_RECONCILED_PAYOFF_EVIDENCE"),"General EUR waits without supported monetary outcomes");

        var observations=fit.Markets.SelectMany(m=>Enumerable.Range(1,20).Select(i=>
        {
            long past=Origin-i*day;
            decimal net=m.Symbol=="A"?4m:3m;
            var context=probe.EurOpportunityReceipts.First(x=>x.Symbol==m.Symbol&&x.Context is not null).Context;
            return new NativeEurCalibrationOutcome(m.Symbol+i,NativeGeneralOpportunity.Distribution,1,past,past,
                net+.50m,net,1m){Context=context};
        })).ToArray();
        calibration=calibration with {Outcomes=observations};
        var contextual=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralSelect);
        contextual.LoadEurCalibration(calibration);
        var adapter=new NativeUnifiedCloudParityAdapter(NativeUnifiedPortfolioEngine.EurGeneralSelect);
        adapter.LoadEurCalibration(calibration);
        var pending=contextual.Advance(frame);
        var selected=contextual.EurOpportunityReceipts.Where(x=>x.Decision=="LONG_PENDING").ToArray();
        check(pending==adapter.Observe(frame) && selected.Select(x=>x.Symbol).SequenceEqual(new[]{"B","C"}) &&
            pending.FundingCapital?.PendingOpenMarginEur==190m && selected.All(x=>x.DisplacedAlternativeEur.HasValue),
            "General EUR chooses two jointly financed alternatives over the largest standalone forecast");
        var restored=NativeUnifiedPortfolioEngine.Restore(contextual.Checkpoint());
        var later=Shape(Origin+2*Step);
        check(contextual.Advance(later)==restored.Advance(later)&&adapter.Observe(later).Held==2,
            "General EUR revalidates fills and resumes the same reserved portfolio from a checkpoint");
        var checkedFuture=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralSelect);
        checkedFuture.LoadEurCalibration(calibration);
        var malformed=frame.Markets[0];
        var altered=malformed.ClosedBars!.Windows.Select(w=>w.Timeframe==NativeBarTimeframe.H1
            ?w with {Bars=w.Bars.Select(b=>b with {CloseAt=frame.At+Step}).ToArray()}:w).ToArray();
        check(checkedFuture.Advance(frame with {Markets=new[]{malformed with {ClosedBars=new(frame.At,altered)}}}).Pending==0,
            "General EUR rejects a claimed ready context containing future bars");

        var sparse=frame.Markets[1];
        var required=sparse.ClosedBars!.Windows.Where(w=>w.Timeframe is NativeBarTimeframe.M5 or NativeBarTimeframe.M15)
            .ToArray();
        var sparseFrame=frame with {Markets=new[]{sparse with {ClosedBars=new(frame.At,required)}}};
        var strictProbe=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe);
        var available=new NativeEurDevelopmentProfile(UseAvailableContext:true,MinimumEpisodes:12);
        var recoveredProbe=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,eurDevelopmentProfile:available);
        check(strictProbe.Advance(sparseFrame).Pending==0&&recoveredProbe.Advance(sparseFrame).Pending==1&&
            recoveredProbe.EurOpportunityReceipts.All(x=>x.Family==NativeGeneralOpportunity.Distribution),
            "Registered EUR profile uses absent optional windows without creating an H1 equilibrium or changing the old policy");
        var recoveredModel=recoveredProbe.ExportEurCalibration() with {Outcomes=observations};
        var revisable=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralSelect,eurDevelopmentProfile:available);
        revisable.LoadEurCalibration(recoveredModel);
        revisable.Advance(later);
        var beforeRecalibration=revisable.ModelSummary;
        var matured=recoveredModel with {ObservationThrough=later.At};
        revisable.UpdateEurResearchCalibration(matured);
        check(revisable.ModelSummary==beforeRecalibration&&
            NativeUnifiedPortfolioEngine.Restore(revisable.Checkpoint()).ModelSummary==beforeRecalibration,
            "Recalibration preserves the common cash, margin, risk and intent chain across the walk-forward boundary");
        try
        {
            revisable.UpdateEurResearchCalibration(matured with {ObservationThrough=later.At+Step});
            check(false,"future calibration must be rejected");
        }
        catch(ArgumentException)
        {
            check(revisable.ModelSummary==beforeRecalibration,"future calibration is rejected without changing the EUR book");
        }

        check(NativeCompleteDistribution.ContextDistance(new[]{0m,1m},new[]{0m,0m})>
            NativeCompleteDistribution.ContextDistance(new[]{0m,1m},new[]{0m,1m}),
            "Extended local distance distinguishes observed zero from missing context");
        var contextSamples=Enumerable.Range(1,8).SelectMany(i=>Enumerable.Range(0,8).SelectMany(j=>new[]{
            new NativeCompleteSample("A",Origin-i*day+j*Step,Origin-i*day+(j+1)*Step,new[]{0m,1m},1m){AssetClass="CLASS_A"},
            new NativeCompleteSample("B",Origin-i*day+j*Step,Origin-i*day+(j+1)*Step,new[]{0m,1m},-1m){AssetClass="CLASS_B"}
        })).Append(new NativeCompleteSample("A",Origin-Step,Origin,new[]{0m,1m},1000m){AssetClass="CLASS_A"}).ToArray();
        var contextDistribution=new NativeCompleteDistribution(contextSamples,false){MaskedEconomicContext=true};
        var positive=contextDistribution.Predict(new[]{0m,1m},Origin,1m,out _,"A","CLASS_A");
        var negative=contextDistribution.Predict(new[]{0m,1m},Origin,1m,out _,"B","CLASS_B");
        check(positive?.Mean==1m&&negative?.Mean==-1m,
            "Extended local prediction ranks prior contextual samples and excludes settlement at decision clock");
        var extendedProfile=available with {UseRecoveredLocalPayoff=true,UseExtendedLocalPayoff=true};
        var extendedBook=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralSelect,eurDevelopmentProfile:extendedProfile);
        extendedBook.LoadEurCalibration(recoveredModel with {Outcomes=observations.Select(o=>o with {DecisionAt=o.ClosedAt-Step}).ToArray()});
        extendedBook.Advance(sparseFrame);
        check(extendedBook.EurOpportunityReceipts.Any(o=>o.Payoff?.Cohort=="EXTENDED_MASKED_CONTEXT_LOCAL_DISTRIBUTION"),
            "Extended local payoff can use a causal sparse frame in the common EUR book");

        var tickProfile=available with {ModeledStopLatencyMs=100L};
        var tickBook=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,eurDevelopmentProfile:tickProfile);
        tickBook.Advance(sparseFrame);
        var laterSingle=later with {Markets=new[]{later.Markets[1]}};
        var entered=tickBook.Advance(laterSingle);
        var watch=tickBook.ProtectionWatches().Single();
        long touched=later.At+1_791L;
        Ucp1Frame Tick(long at,decimal bid,Ucp1StopTouch[] touches,Ucp1StopQuote[] quotes)
        {
            var market=laterSingle.Markets[0];
            return new Ucp1Frame(at,new[]{market with {Quote=market.Quote with
                {At=at,Bid=bid,Ask=bid+.02m,LiquidationSlippagePerSide=.02m}}})
            {
                FundingEvidence=new[]{new NativeAccruedFundingEvidence(watch.PositionId,watch.Symbol,watch.Side,
                    1m,later.At,at,at,0m,null,Proof)},
                Protection=new(true,touches,quotes,Array.Empty<string>())
            };
        }
        var trigger=tickBook.Advance(Tick(touched,watch.Stop-.03m,
            new[]{new Ucp1StopTouch(watch.PositionId,watch.Stop-.03m,watch.Stop-.01m,true)},Array.Empty<Ucp1StopQuote>()));
        check(trigger is {Held:1,Pending:1,CloseFills:0}&&trigger.Proposed==entered.Proposed&&
            tickBook.OriginalModelEvents.Last().Kind=="MODEL_NATIVE_STOP_TRIGGER",
            "A Trade tick latches protection between decisions and leaves cash and the held position unsettled");
        var resumed=NativeUnifiedPortfolioEngine.Restore(tickBook.Checkpoint());
        var observedQuote=new[]{new Ucp1StopQuote(watch.PositionId,true)};
        var premature=Tick(touched+99L,watch.Stop-.06m,Array.Empty<Ucp1StopTouch>(),observedQuote);
        check(tickBook.Advance(premature)==resumed.Advance(premature)&&tickBook.ModelSummary.OpenPositions==1,
            "Protection survives checkpoint and cannot fill before the registered modeled latency");
        var exitFrame=Tick(touched+101L,watch.Stop-.10m,Array.Empty<Ucp1StopTouch>(),observedQuote);
        check(tickBook.Advance(exitFrame)==resumed.Advance(exitFrame)&&tickBook.ModelSummary is {OpenPositions:0,CompleteRoundTrips:1}&&
            tickBook.OriginalModelEvents.Last().ExecutionPrice==watch.Stop-.12m&&
            tickBook.CompleteModelTrips.Single().StopExecution is
                {Trigger.MinimumGap:.01m,Trigger.MaximumGap:.03m,MinimumMoveAfterTrigger:.07m,MaximumMoveAfterTrigger:.09m,
                 ModeledSlippage:.02m,TickFillQuote:true,CompleteSinceTrigger:true}&&
            tickBook.ExportEurCalibration().Outcomes.Single().AvailableAt==exitFrame.At,
            "Stop execution binds a later quote, distinguishes trigger gap, waiting move and slippage, and then matures a label");

        var intentBook=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            eurDevelopmentProfile:tickProfile with {ObserveIntentExecutionOnTicks=true});
        var intended=intentBook.Advance(sparseFrame);
        var order=intentBook.IntentWatches().Single();
        Ucp1Frame ExecutionQuote(long at)
        {
            var market=sparseFrame.Markets.Single();
            return new Ucp1Frame(at,new[]{market with {Quote=market.Quote with {At=at},
                FundingOffers=market.FundingOffers!.Select(o=>o with {NextScheduledManagementAt=at+Step,
                    CoveredThrough=at+Step}).ToArray()}})
            {
                Protection=new(true,Array.Empty<Ucp1StopTouch>(),Array.Empty<Ucp1StopQuote>(),Array.Empty<string>())
                    {ExecutableIntentIds=new[]{order.PositionId}}
            };
        }
        check(order.Opening&&order.Buy&&intentBook.Advance(ExecutionQuote(order.FillNotBefore-1)).Pending==1,
            "An opening intent retains its closed-bar decision and rejects a premature ASK fill");
        var intrabar=intentBook.Advance(ExecutionQuote(order.FillNotBefore+1));
        check(intrabar is {Pending:0,Held:1,OpenFills:1}&&intrabar.Proposed==intended.Proposed&&
              intentBook.OriginalModelEvents.Last(e=>e.Kind=="OPEN_FILL").At==order.FillNotBefore+1,
            "An executable quote fills the existing intent between bars without generating another decision");
    }

    static void ExplicitScenarioContinuity(Action<bool,string> check)
    {
        string scenario=new string('b',64);
        var book=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst,fundingScenarioId:scenario);
        Ucp1Frame Conditional(Ucp1Frame x)=>x with {Markets=x.Markets.Select(m=>m with
            {FundingOffers=m.FundingOffers?.Select(o=>o with {ScenarioId=scenario}).ToArray()}).ToArray()};
        var first=book.Advance(Conditional(OfficialShape(1,1)));
        check(first.Pending==1&&first.FundingCapital is {DemonstrableEquityEur:null,ConditionalEquityEur:300m},
            "Scenario uses common capital without representing it as demonstrated equity");
        book.Advance(Conditional(OfficialShape(2,1)));
        var fill=book.OriginalModelEvents.Last(e=>e.Kind=="OPEN_FILL");
        var frame=OfficialShape(3,1,bid:102.20m,offer:false);
        var proof=new NativeAccruedFundingEvidence(fill.PositionId,fill.Symbol,fill.Side,fill.Units,
            fill.At,frame.At,frame.At,-.05m,null,Proof);
        var before=book.Checkpoint();
        try {book.Advance(frame with {FundingEvidence=new[]{proof}});check(false,"Scenario must reject unlabeled amount");}
        catch(ArgumentException){check(before==book.Checkpoint(),"Unlabeled funding rejection is atomic");}
        var observed=book.Advance(frame with {FundingEvidence=new[]{proof with {ScenarioId=scenario,ExactSignedEur=null,ConditionalSignedEur=-.05m,SourceAcquiredAt=frame.At+Step}}});
        check(observed.FundingCapital is {DemonstrableEquityEur:null,ConditionalEquityEur:>0m,PostedFinancingEur:-.05m},
            "Conditional debit affects the same cash ledger and admission equity");
        var restored=NativeUnifiedPortfolioEngine.Restore(book.Checkpoint());
        check(restored.FundingScenarioId==scenario&&restored.ModelSummary==book.ModelSummary,
            "Scenario identity and monetary state survive checkpoint");
        var next=OfficialShape(4,1,bid:102.20m,offer:false);
        var missing=restored.Advance(next);
        check(missing.FundingCapital is {ConditionalEquityEur:null,DemonstrableEquityEur:null},
            "Missing scenario evidence remains unbounded, not zero");
        try {new NativeUnifiedCloudParityAdapter(NativeUnifiedPortfolioEngine.EurFirst).Restore(book.Checkpoint());
            check(false,"Cloud cannot restore scenario");}
        catch(ArgumentException){check(true,"Cloud rejects scenario checkpoint");}
        var calibration=book.ExportEurCalibration();
        try {new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank).LoadEurCalibration(calibration);
            check(false,"Ordinary rank cannot load scenario calibration");}
        catch(ArgumentException){check(true,"Scenario calibration cannot cross into ordinary rank");}
        new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank,fundingScenarioId:scenario).LoadEurCalibration(calibration);
    }

    static void ExplicitScenarioMultiDay(Action<bool,string> check)
    {
        const long day=86_400_000L;
        string scenario=new string('c',64);
        var first=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst,fundingScenarioId:scenario);
        Ucp1Frame FrameWithScenario(int slot,long at,decimal bid=100.95m,bool offer=true)
        {
            var frame=OfficialShape(slot,1,at,bid,offer);
            return frame with {Markets=frame.Markets.Select(m=>m with
                {FundingOffers=m.FundingOffers?.Select(o=>o with {ScenarioId=scenario}).ToArray()}).ToArray()};
        }
        for(int i=0;i<20;i++)
        {
            long start=Origin+i*day;
            var admitted=first.Advance(FrameWithScenario(1,start));
            if(admitted.Pending!=1)throw new InvalidOperationException("Scenario did not resume on next day");
            first.Advance(FrameWithScenario(2,start));
            var fill=first.OriginalModelEvents.Last(e=>e.Kind=="OPEN_FILL");
            first.Advance(FrameWithScenario(3,start,102.20m,false));
            first.Advance(FrameWithScenario(4,start,102.20m,false));
            first.Advance(FrameWithScenario(5,start,102.20m,false));
            var frame=FrameWithScenario(6,start,102.20m,false);
            var proof=new NativeAccruedFundingEvidence(fill.PositionId,fill.Symbol,fill.Side,fill.Units,
                fill.At,start+5*Step,frame.At,null,null,Proof)
                {ScenarioId=scenario,ConditionalSignedEur=-.01m,SourceAcquiredAt=frame.At+day};
            var result=first.Advance(frame with {FundingEvidence=new[]{proof}});
            if(result.FundingCapital is not {ConditionalEquityEur:>0m,DemonstrableEquityEur:null,OutstandingClosedWindows:0})
                throw new InvalidOperationException("Scenario cash continuity failed");
        }
        var calibration=first.ExportEurCalibration();
        var rank=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank,fundingScenarioId:scenario);
        rank.LoadEurCalibration(calibration);
        var comparison=rank.Advance(FrameWithScenario(1,Origin+20*day));
        check(calibration.Outcomes.Length==20&&calibration.Outcomes.Select(x=>x.ClosedAt/day).Distinct().Count()==20&&
            comparison.Pending==1&&comparison.FundingCapital is {DemonstrableEquityEur:null,ConditionalEquityEur:300m},
            "Conditional financing restores multi-day capital and causally transfers sufficient EUR outcomes into RANK");
    }

    static void ContractClocksAndDirectionalCosts(Action<bool,string> check)
    {
        var c=OfficialShape(1,1).Markets[0].Contract with
            {CommissionType=3,PreciseRateWire=10_000,SwapPeriodHours=6,SwapTimeUtcMinute=240};
        var quote=NativeBrokerContractCosts.QuoteBothDirections(c,
            new(Origin,100m,101m,1m,1m,1m,null,1m,1m,0m)).Quote;
        check(quote is {ExitFeePerUnit:.101m,SellFeePerUnit:.100m} &&
            NativeExecutableEconomics.EstimateNet(quote,quote,1,1m,101m,100m,0m)==-1.201m &&
            NativeExecutableEconomics.EstimateNet(quote,quote,-1,1m,100m,101m,0m)==-1.201m,
            "Official proportional commission uses the witnessed bid on sells and ask on buys");
        long midnight=Origin/86_400_000L*86_400_000L;
        check(NativeBrokerContractCosts.NextScheduledSwapCharge(c,midnight+23*3_600_000L)==
            midnight+28*3_600_000L&&NativeBrokerContractCosts.NextScheduledSwapCharge(
                c with {SwapTimeUtcMinute=null},Origin) is null,
            "Rollover respects the first charge hour and preserves an absent official clock");
    }

    static void LateNetChangesRanking(Action<bool,string> check)
    {
        var profitable=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst);
        var financed=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst);
        const long day=86_400_000L;
        Ucp1Frame Evidence(Ucp1Frame frame,LedgerEvent fill,long through,decimal amount)
            =>frame with {FundingEvidence=new[]{new NativeAccruedFundingEvidence(fill.PositionId,fill.Symbol,
                fill.Side,fill.Units,fill.At,through,frame.At,amount,null,Proof)}};
        void Cycle(NativeUnifiedPortfolioEngine book,long origin,decimal late)
        {
            book.Advance(OfficialShape(1,1,origin));
            book.Advance(OfficialShape(2,1,origin));
            var fill=book.OriginalModelEvents.Last(e=>e.Kind=="OPEN_FILL");
            book.Advance(OfficialShape(3,1,origin,102.20m,offer:false));
            book.Advance(OfficialShape(4,1,origin,102.20m,offer:false));
            var closed=book.Advance(OfficialShape(5,1,origin,102.20m,offer:false));
            if(closed is not {Held:0,ModelBook.CompleteRoundTrips:>0})
                throw new InvalidOperationException("EUR test failed to close an observed favorable episode");
            book.Advance(Evidence(OfficialShape(6,1,origin,102.20m,offer:false),fill,origin+5*Step,late));
        }
        for(int i=0;i<20;i++)
        {
            Cycle(profitable,Origin+i*day,0m);
            Cycle(financed,Origin+i*day,-2m);
        }

        var positiveRank=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank);
        var negativeRank=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank);
        positiveRank.CalibrateEurRankFrom(profitable);
        negativeRank.CalibrateEurRankFrom(financed);
        var input=OfficialShape(1,1,Origin+20*day);
        var invalidClock=OfficialShape(1,1,Origin+19*day);
        var before=negativeRank.Checkpoint();
        try
        {
            negativeRank.Advance(invalidClock);
            check(false,"RANK cannot read a calibration completed after its decision");
        }
        catch(ArgumentException)
        {
            check(negativeRank.Checkpoint()==before,"Future calibration rejection is atomic");
        }
        negativeRank=NativeUnifiedPortfolioEngine.Restore(before);
        check(positiveRank.ModelSummary.CashEur==300m&&negativeRank.ModelSummary.CashEur==300m,
            "RANK calibration carries no cash from the FIRST ledger");
        check(positiveRank.Advance(input).Pending==1&&negativeRank.Advance(input).Pending==0,
            "Same recurrent gross with a late financing debit changes the actual RANK decision");
        var positive=positiveRank.EurOpportunityReceipts.Single().Payoff;
        var negative=negativeRank.EurOpportunityReceipts.Single().Payoff;
        check(positive is {GrossLowerEur:>0m,NetLowerEur:>0m} &&
            negative is {GrossLowerEur:>0m,NetLowerEur:<0m} &&
            positive.GrossLowerEur==negative.GrossLowerEur,
            "RANK keeps gross and reconciled net separate through settlement, scoring and admission");
    }
}
