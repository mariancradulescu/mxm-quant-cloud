using Mxm.Core;

internal static class NativeEconomicMechanismChecks
{
    internal static void Run(Action<bool,string> check)
    {
        const long at=1_785_800_015_000L;
        var market=Cpe1IntegratedEconomicChecks.Frame(at-300_000L,at,101m,false).Markets[0];
        var windows=NativeClosedMarketContext.CoverageWindows.Select(r=>
        {
            long width=(long)r.Timeframe*60_000L,last=(at/width)*width;
            var bars=Enumerable.Range(0,r.Count).Select(i=>
            {
                decimal price=100m+i*.1m;
                return new NativeClosedMarketBar(last-(r.Count-i)*width,last-(r.Count-i-1)*width,
                    price-.05m,price+.15m,price-.15m,price,i==r.Count-1?200:100);
            }).ToArray();
            return new NativeBarWindow(r.Timeframe,r.Count,last,at,"SYNTHETIC",NativeBarStatus.Ready,bars);
        }).ToArray();
        market=market with {ClosedBars=new(at,windows),EurTickSize=.01m,
            M5=windows.Single(w=>w.Timeframe==NativeBarTimeframe.M5).Bars,
            M15=windows.Single(w=>w.Timeframe==NativeBarTimeframe.M15).Bars};
        // Conditional monetary comparison for partial-close alternatives.
        decimal? Reduction(decimal held=2m,decimal close=1m,decimal min=1m,decimal step=1m,
            decimal uncertainty=.05m,decimal? remainderDebit=.1m,decimal remainderFee=.1m,decimal closeFee=.1m)
            =>NativeEconomicMechanisms.PartialReductionAdvantage(held,close,min,10m,step,.5m,
                uncertainty,2m,remainderDebit,.2m,closeFee,remainderFee);
        check(Reduction()==.35m,"Synthetic nonlinear funding arithmetic, not broker evidence or a portfolio decision");
        check(Reduction(remainderDebit:1m) is null,"Proportional funding cannot make partial close strictly dominate both endpoints");
        decimal? Constrained(decimal equity=100m,decimal otherMargin=40m,decimal otherRisk=2m,
            decimal? funding=.1m,decimal fee=.1m,decimal uncertainty=.05m)
            =>NativeEconomicMechanisms.ConstrainedReductionValue(2m,1m,1m,10m,1m,.5m,
                uncertainty,funding,.2m,fee,.1m,equity,50m,otherMargin,otherRisk,20m,2m,1m);
        check(Constrained()==.35m,"Positive residual is financeable when full exposure violates actual common-book limits");
        check(Constrained(otherMargin:20m,equity:200m) is null,"No partial close when HOLD fits all constraints");
        check(Constrained(otherMargin:65m) is null,"Cannot release an insufficient amount of margin");
        check(Constrained(otherRisk:4.5m) is null,"Cannot leave the aggregate stop reservation above its cap");
        check(Constrained(funding:null) is null,"No constrained reduction on missing residual financing");
        check(Constrained(uncertainty:.5m) is null,"No residual with a nonpositive conservative continuation");
        check(Constrained(fee:.5m) is null,"Additional split costs can erase the residual benefit");
        check(Reduction(held:1m) is null,"Minimum-volume position cannot be partially closed");
        check(Reduction(held:2.5m,close:1m) is null,"Residual volume must remain on the contract grid");
        check(Reduction(step:0m) is null,"Invalid volume increments cannot authorize reductions");
        check(Reduction(remainderDebit:null) is null,"Unknown residual funding cannot authorize reductions");
        check(Reduction(remainderFee:.2m) is null,"Nonproportional remaining fees cannot release proportional risk");
        check(Reduction(closeFee:.5m) is null,"Split fees can remove the conditional economic advantage");
        check(Reduction(uncertainty:.5m) is null,"Uncertain continuation cannot establish partial-close dominance");
        var jointProfile=new NativeEurDevelopmentProfile(UseAvailableContext:true)
        {EconomicMechanism=NativeEconomicMechanisms.Scored,EconomicManagement="TRANSITION_VALUE",
            CompeteEconomicFamilies=true,ObserveIntentExecutionOnTicks=true,ModeledStopLatencyMs=100,
            EconomicGeometryTimeframe="H1",EconomicStopRanges=.75m,KeepAdmissionRiskAtFill=true,
            ResizeWithinAdmissionRiskAtFill=true,ReserveObservedBarGaps=true};
        var jointBook=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            eurDevelopmentProfile:jointProfile);
        var jointSignals=jointBook.DescribeEurGeneral(market,at,new(at,new[]{market}));
        check(jointSignals.Any(s=>s.Family==NativeEconomicMechanisms.Transition)&&
            jointSignals.Any(s=>s.Family==NativeEconomicMechanisms.Follow)&&
            jointSignals.Select(s=>s.Family).Distinct().Count()>1,
            "Opt-in shared family discovery retains PAV1 and competing distinct families");
        check(new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            eurDevelopmentProfile:jointProfile with {CompeteEconomicFamilies=false,ReserveObservedBarGaps=false})
            .DescribeEurGeneral(market,at,new(at,new[]{market})).All(s=>s.Family!=NativeEconomicMechanisms.Transition),
            "Frozen scored mechanism still excludes the new transition family");
        var pathContext=NativeClosedPathPrediction.Observe(market,at);
        check(pathContext is {Alignment:>0m}&&pathContext.PullbackRepair==0m,
            "Closed path information separates coherent trend from countertrend repair");
        var futurePath=market with {ClosedBars=new(at,windows.Select(w=>w with
            {Bars=w.Bars.Append(w.Bars[^1] with {CloseAt=at}).ToArray()}).ToArray())};
        check(NativeClosedPathPrediction.Observe(futurePath,at) is null,
            "Closed path predictor rejects unavailable and current-clock bars");
        check(pathContext is not null&&NativeClosedPathPrediction.RelativeDisplacement(pathContext,new[]{pathContext}) is null,
            "Relative information requires two independently observed classified peers");
        var follow=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,market,at,1.5m);
        var reverse=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Reverse,market,at,1.5m);
        check(follow.Single().Side==1&&reverse.Single().Side==-1,
            "Distinct follow and reverse mechanisms produce opposed executable causal geometries");
        var future=market with {ClosedBars=new(at,windows.Select(w=>w with
            {Bars=w.Bars.Append(w.Bars[^1] with {CloseAt=at+1}).ToArray()}).ToArray())};
        check(NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,future,at,1.5m).Length==0,
            "Distinct economic mechanisms reject forming/future bars");
        check(NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Intermarket,market,at,1.5m,new(at,new[]{market})).Length==0,
            "Intermarket mechanism abstains without an authenticated class and aligned peers");
        check(NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Activity,market,at,1.5m).Single().Side==1,
            "Recovered V3.3 impulse and activity drive a distinct multiscale mechanism");
        check(NativeEconomicMechanisms.Continuation(market,at) is {Mean:>0m},
            "Recovered PAV1 transition value uses completed adjacent movements");
        var context=new NativeEurDecisionContext("EURUSD",null,0,Array.Empty<NativeEurBarState>(),0m,.1m,true);
        var rows=Enumerable.Range(0,30).Select(i=>new NativeEurCalibrationOutcome("E"+i,"F",1,
            at-(i/10+1)*86_400_000L,at-(i/10+1)*86_400_000L+1, i%2==0?2m:-1m,i%2==0?1.9m:-1.1m,1m)
            {Context=context}).ToArray();
        // Exercise >1024 rows, stable timestamp ties, class transfer,
        // malformed/future path evidence and multiple context dimensions.
        var pathRows=Enumerable.Range(0,1400).Select(i=>rows[i%rows.Length] with
        {
            PositionId="PATH"+i,AvailableAt=at-((i%200)+1)*86_400_000L+(i%3),
            ClosedAt=at-((i%200)+1)*86_400_000L,
            Context=context with {Symbol=i%3==0?"OTHER":"EURUSD",AssetClass=i%5==0?"OTHER":"FX",
                MarketState=new decimal?[]{i%11/10m,null, i%2==0?1m:-1m}},
            PathEvidence=new NativeEconomicPathEvidence(i%9==0?-1m:2m,1m,0m,1m,60m)
        }).Append(rows[0] with {AvailableAt=at,PathEvidence=new(2m,1m,0m,1m,60m)}).ToArray();
        var pathTarget=context with {AssetClass="FX",MarketState=new decimal?[]{.3m,null,1m}};
        foreach(string mode in new[]{"LOCAL","POOLED","CONTEXT"})
        {
            var originalPath=NativeDistributionLifecycle.Estimate(pathRows,"F",1,pathTarget,at,mode,24,5,1.645m,null,false);
            var compactPath=NativeDistributionLifecycle.Estimate(pathRows,"F",1,pathTarget,at,mode,24,5,1.645m,null,true);
            check(originalPath is not null&&System.Text.Json.JsonSerializer.Serialize(originalPath)==
                System.Text.Json.JsonSerializer.Serialize(compactPath),"compact paired paths retain exact monetary and distribution digests "+mode);
        }
        var payoff=NativeEconomicMechanisms.LifecyclePayoff(rows,"F",1,context,at,1m,.1m,20,3,0m);
        var centered=NativeCenteredLifecycle.Estimate(rows,"F",1,context,at,1m,.3m,20,3,1.645m,false);
        check(centered is {NetMeanEur:.2m,NetLowerEur:.2m},
            "Centered lifecycle measures historical NET dispersion about its own mean before current cost cap");
        check(centered==NativeCenteredLifecycle.Estimate(rows.Append(rows[0] with {AvailableAt=at,GrossEur=1000m}),
            "F",1,context,at,1m,.3m,20,3,1.645m,false),"Centered lifecycle excludes future and current clock labels");
        var unitEstimate=NativeCenteredLifecycle.Estimate(rows,"F",1,context,at,1m,0m,20,3,1.645m,false);
        check(NativeCenteredLifecycle.Reprice(unitEstimate,2m,.6m)==NativeCenteredLifecycle.Estimate(
            rows,"F",1,context,at,2m,.6m,20,3,1.645m,false),
            "Cached normalized statistics retain candidate-specific costs and volume risk scale");
        check(NativeCenteredLifecycle.Corroborate(centered,null) is null,
            "Hybrid PAV1 cannot credit an absent direct forecast");
        check(NativeCenteredLifecycle.Corroborate(centered,centered! with {NetLowerEur=-.1m}) is {NetLowerEur:-.1m},
            "Hybrid corroboration preserves a negative conservative forecast");
        var shifted=Enumerable.Range(1,30).Select(i=>rows[0] with
            {PositionId="SHIFT"+i,ClosedAt=at-i*86_400_000L,AvailableAt=at-i*86_400_000L+1,
             GrossEur=i<=7?-1m:2m,NetEur=i<=7?-1.1m:1.9m}).ToArray();
        var equalDays=NativeCenteredLifecycle.Estimate(shifted,"F",1,context,at,1m,.1m,8,3,0m,true,costMatched:true);
        var recentDays=NativeCenteredLifecycle.Estimate(shifted,"F",1,context,at,1m,.1m,8,3,0m,true,costMatched:true,halfLifeDays:7);
        check(equalDays is not null&&recentDays is not null&&recentDays.NetMeanEur<equalDays.NetMeanEur&&
            recentDays==NativeCenteredLifecycle.Estimate(shifted.Append(shifted[0] with {AvailableAt=at,NetEur=1000m}),
                "F",1,context,at,1m,.1m,8,3,0m,true,costMatched:true,halfLifeDays:7),
            "Recency-weighted monetary lifecycle adapts to deterioration without unmatured outcomes");
        var audited=NativeCenteredLifecycle.Estimate(shifted,"F",1,context,at,1m,.1m,8,3,0m,true,
            costMatched:true,halfLifeDays:7,captureRecencyEvidence:true);
        check(audited is {EffectiveObservationDays:>0m and <30m}&&audited.LatestEligibleObservationAt==shifted[0].AvailableAt&&
            NativeCenteredLifecycle.Reprice(audited,2m,.2m)?.LatestEligibleObservationAt==audited.LatestEligibleObservationAt,
            "Recency evidence preserves latest eligible settlement clock and effective days through repricing");
        var recovering=shifted.Select(x=>x with {GrossEur=-x.GrossEur,NetEur=-x.GrossEur-.1m}).ToArray();
        check(NativeCenteredLifecycle.Estimate(recovering,"F",1,context,at,1m,.1m,8,3,0m,true,costMatched:true,halfLifeDays:7)!
            .NetMeanEur>NativeCenteredLifecycle.Estimate(recovering,"F",1,context,at,1m,.1m,8,3,0m,true,costMatched:true)!.NetMeanEur,
            "A recovering causal cohort can improve; no permanent family exclusion");
        var highCostRows=rows.Select(r=>r with {Context=context with {CostRiskFraction=.6m}}).ToArray();
        check(NativeCenteredLifecycle.Estimate(highCostRows,"F",1,context,at,1m,.1m,20,3,0m,true,costMatched:true) is null,
            "Cost-context estimate does not transfer a mismatched execution-cost regime");
        check(NativeCenteredLifecycle.Estimate(rows,"F",1,context,at,1m,.3m,20,3,1.645m,true,costMatched:true)
            is {NetLowerEur:.2m},"Cost-matched historical outcomes retain the executable cost cap");
        check(!NativePendingCapitalGate.StopAdjustedMarginFits(294.34m,204.52m,5m)&&
            NativePendingCapitalGate.StopAdjustedMarginFits(294.34m,190m,5m),
            "Reserve actual committed stop risk below original 70 percent margin ceiling");
        var transferPeers=rows.Select((row,i)=>row with {Context=context with {Symbol=i%2==0?"A":"B",AssetClass="FX"}}).ToArray();
        var targetContext=context with {AssetClass="FX"};
        check(NativeCenteredLifecycle.Estimate(transferPeers,"F",1,targetContext,at,1m,.1m,20,3,0m,true)
            is {Cohort:"CENTERED_CLASS_OTHER_SYMBOLS_REGIME"},"Transfer requires authenticated class and two other symbols");
        check(NativeCenteredLifecycle.Estimate(transferPeers,"F",1,targetContext,at,1m,.1m,20,3,0m,false) is null,
            "Local-only ablation cannot borrow peer outcomes");
        var localLoss=rows.Select(row=>row with {GrossEur=-1m,NetEur=-1.1m,Context=targetContext});
        check(NativeCenteredLifecycle.Estimate(localLoss.Concat(transferPeers),"F",1,targetContext,at,1m,.1m,20,3,0m,true)
            is {NetLowerEur:<0m,Cohort:"CENTERED_LOCAL_REGIME"},"Supported losing local cohort never falls back to transferPeers");
        var managementBase=rows.Select((r,i)=>r with {DecisionAt=r.ClosedAt-1000L-i,EconomicManagement="TRANSITION_VALUE"}).ToArray();
        var managementAlt=managementBase.Select(r=>r with {PositionId=r.PositionId+"/REDUCE",NetEur=r.NetEur+.5m,
            EconomicManagement=NativeEconomicMechanisms.MonetaryReduce}).ToArray();
        NativeCausalManagementSelection.Choice Choose(IEnumerable<NativeEurCalibrationOutcome> values)
            =>NativeCausalManagementSelection.Select(values,"F",1,context,at,20,3,1.645m);
        check(Choose(managementBase.Concat(managementAlt)) is {Management:NativeEconomicMechanisms.MonetaryReduce,Pairs:30,LowerDeltaR:.5m},
            "Management switches only on matured same-entry day-clustered positive incremental NET");
        check(Choose(managementBase.Concat(managementAlt.Select(r=>r with {NetEur=r.NetEur-1m}))).Management=="TRANSITION_VALUE",
            "Inferior monetary reduction is never forced on a family");
        check(Choose(managementBase.Concat(managementAlt.Select(r=>r with {AvailableAt=at}))) is {Management:"TRANSITION_VALUE",Pairs:0},
            "Management selection excludes the current clock and future outcomes");
        check(Choose(managementBase.Concat(managementAlt.Select(r=>r with {RiskEur=2m}))).Pairs==0,
            "Management comparisons reject unequal initial risks");
        check(Choose(managementBase.Concat(managementAlt.Select(r=>r with {Context=context with {Symbol="OTHER"}}))).Pairs==0,
            "Unrelated instruments never select management for this symbol");
        check(Choose(managementBase.Concat(managementAlt).Append(managementAlt[0] with {PositionId="DUPLICATE"})).Pairs==29,
            "Duplicate alternative outcomes invalidate their pair instead of adding weight");
        var contaminated=rows.Append(rows[0] with {PositionId="FUTURE",AvailableAt=at+1,GrossEur=100000m}).ToArray();
        check(payoff is {GrossMeanEur:.5m,NetMeanEur:.4m}&&payoff==NativeEconomicMechanisms.LifecyclePayoff(
            contaminated,"F",1,context,at,1m,.1m,20,3,0m),
            "SCP1 conditional win/loss magnitudes match funded realized EUR and exclude unmatured labels");
        check(NativeEconomicMechanisms.LifecyclePayoff(rows,"F",1,context with {Symbol="US500"},at,1m,.1m,20,3,0m) is null,
            "SCP1 lifecycle scores never transfer unsupported results across instruments");
        // Identical admission risk scale. The early-stop cash loss has no
        // excursion requirement; its modeled monetary value must change the estimate.
        var fastLoss=rows[0] with {PositionId="FAST_STOP",GrossEur=-30m,NetEur=-31m};
        var baseScore=NativeEconomicMechanisms.EntryQualityPayoff(rows,"F",1,context,at,1m,.1m,20,3,0m,false);
        var corrected=NativeEconomicMechanisms.EntryQualityPayoff(rows.Append(fastLoss),"F",1,context,at,1m,.1m,20,3,0m,false);
        check(baseScore is {NetLowerEur:>0m}&&corrected is {NetLowerEur:<0m},
            "Settled fast-stop cash losses must affect entry quality even without excursion marks");
        var band=NativeEconomicMechanisms.EntryQualityPayoff(rows,"F",1,context,at,1m,.1m,20,3,0m,true);
        check(band is not null&&band==NativeEconomicMechanisms.EntryQualityPayoff(contaminated,"F",1,context,at,1m,.1m,20,3,0m,true),
            "Causal cost/risk bands and estimates exclude future outcomes");
        check(NativeEconomicMechanisms.EntryQualityPayoff(rows,"F",1,context with {CostRiskFraction=.9m},at,1m,.1m,20,3,0m,true) is null,
            "Unsupported cost band abstains rather than borrowing an unrelated payoff");

        var close=market.M5[^1].Close;
        var near=market with {Quote=market.Quote with {Bid=close,Ask=close+.01m}};
        var moved=near with {Quote=near.Quote with {Bid=close+.02m,Ask=close+.03m}};
        var anchored=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,near,at,4m,
            geometryTimeframe:"M5",stopRanges:1m,closedStructure:true).Single();
        var later=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,moved,at,4m,
            geometryTimeframe:"M5",stopRanges:1m,closedStructure:true).Single();
        check(anchored.Stop==later.Stop&&anchored.Target==later.Target&&anchored.Stop<close,
            "Closed-structure stop and economic destination do not drift with executable entry");
        var profile=new NativeEurDevelopmentProfile(UseAvailableContext:true)
        {
            EconomicMechanism=NativeEconomicMechanisms.Follow,EconomicManagement="CAPTURE_VALUE",
            EconomicGeometryTimeframe="M5",EconomicStopRanges=1m,EconomicManagementTimeframe="M5",
            AnchorEconomicGeometryToClosedStructure=true,KeepAdmissionRiskAtFill=true,ResizeWithinAdmissionRiskAtFill=true
        };
        profile.Verify();
        check(profile.GeometryIdentity.Contains("CLOSED_STRUCTURE_ANCHOR")&&profile.GeometryIdentity.Contains("MECHANISM_KEEP_RISK"),
            "Distinct economic mechanisms may reuse admission-risk guard with independent geometry identity");
        var fx=context with {AssetClass="FX"};
        var peers=new[]{"GBPUSD","USDJPY"}.SelectMany(symbol=>rows.Select(row=>row with
            {PositionId=symbol+row.PositionId,Context=fx with {Symbol=symbol}})).ToArray();
        var peer=NativeEconomicMechanisms.LeaveSymbolOutPayoff(peers,"F",1,fx,at,1m,.1m,20,3,0m);
        var contamination=peers.Concat(rows.Select(row=>row with {Context=fx,GrossEur=10000m,NetEur=10000m}))
            .Append(peers[0] with {AvailableAt=at+1,GrossEur=100000m,NetEur=100000m});
        check(peer is {SupportedPeers:2,MeanNetEur:.4m}&&peer==NativeEconomicMechanisms.LeaveSymbolOutPayoff(
            contamination,"F",1,fx,at,1m,.1m,20,3,0m),
            "Leave-symbol-out forecast excludes target and future outcomes, normalizes only same-class supported peers");
        check(NativeEconomicMechanisms.LeaveSymbolOutPayoff(peers,"F",1,fx with {AssetClass="METAL"},at,1m,.1m,20,3,0m) is null,
            "Peer estimate cannot transfer across unrelated classes");
        var balanced=NativeEconomicMechanisms.LeaveSymbolOutPayoff(peers,"F",1,fx,at,1m,.1m,20,3,1.645m,true);
        check(balanced is {BalancedNetLowerEur:>0m}&&balanced==NativeEconomicMechanisms.LeaveSymbolOutPayoff(
            contamination,"F",1,fx,at,1m,.1m,20,3,1.645m,true),
            "Balanced peer diagnostic keeps local-day uncertainty and excludes target/future labels");
        var swing=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,near,at,4m,
            geometryTimeframe:"M5",stopRanges:1m,closedStructure:true,structureLookback:3).Single();
        var swingLater=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,moved,at,4m,
            geometryTimeframe:"M5",stopRanges:1m,closedStructure:true,structureLookback:3).Single();
        check(swing.Stop<anchored.Stop&&swing.Target==anchored.Target&&swing.Stop==swingLater.Stop&&swing.Target==swingLater.Target,
            "Swing invalidation uses three closed bars and observed M5 noise; destination and stop stay stationary");
        var opposite=near with {ClosedBars=new(at,windows.Select(w=>w.Timeframe!=NativeBarTimeframe.M15?w:w with
            {Bars=w.Bars.Select((bar,i)=>bar with {Close=102m-i*.1m,High=103m,Low=99m}).ToArray()}).ToArray())};
        opposite=opposite with {M15=opposite.ClosedBars!.For(NativeBarTimeframe.M15).Bars};
        check(NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,opposite,at,4m,
            geometryTimeframe:"M15",stopRanges:1m).Length==1&&
            NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,opposite,at,4m,
                geometryTimeframe:"M15",stopRanges:1m,confirmM5:true).Length==0,
            "Closed M5 timing confirmation detects a contrary entry direction without future bars");

        // H1 continuation is positive, M15 continuation negative. This exact
        // native pending/fill pair proves the former horizon mismatch and its
        // opt-in correction, rather than merely checking a serialized flag.
        var opposingWindows=windows.Select(w=>w.Timeframe!=NativeBarTimeframe.M15?w:w with
            {Bars=w.Bars.Select((bar,i)=>bar with {Close=102m-i*.1m,Open=102m-i*.1m,High=103m,Low=99m}).ToArray()}).ToArray();
        Ucp1Frame Clock(long time)
        {
            var m=market with {Quote=market.Quote with {At=time},EurDatedMarginScenario=true,
                ClosedBars=new(time,opposingWindows),M15=opposingWindows.Single(w=>w.Timeframe==NativeBarTimeframe.M15).Bars,
                EurMargins=new[]{new NativeEurMarginObservation(1,1m,1m,at-1,new string('a',64)),
                    new NativeEurMarginObservation(1,2m,2m,at-1,new string('a',64))},
                FundingOffers=new[]{1m,2m}.Select(units=>new NativeFundingOfferEvidence(market.Symbol,1,units,
                    time,time,time+300000L,time+300000L,0m,new string('a',64))).ToArray()};
            return new(time,new[]{m});
        }
        var transitionProfile=new NativeEurDevelopmentProfile(UseAvailableContext:true)
        {EconomicMechanism=NativeEconomicMechanisms.Transition,EconomicManagement="BRACKET",
            EconomicGeometryTimeframe="H1",EconomicStopRanges=.75m,MinimumContractVolumeOnly=true,
            KeepAdmissionRiskAtFill=true,ResizeWithinAdmissionRiskAtFill=true};
        var oldClock=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,eurDevelopmentProfile:transitionProfile);
        var sameClock=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            eurDevelopmentProfile:transitionProfile with {MatchEconomicTransitionHorizonAtFill=true});
        oldClock.Advance(Clock(at));sameClock.Advance(Clock(at));
        check(oldClock.ModelSummary.PendingIntents==1&&sameClock.ModelSummary.PendingIntents==1,
            "Both registered PAV1 variants admit the same positive H1 transition");
        oldClock.Advance(Clock(at+1000));sameClock.Advance(Clock(at+1000));
        check(oldClock.ModelSummary.OpenPositions==0&&sameClock.ModelSummary.OpenPositions==1,
            "Matched H1 fill revalidates H1 monetary evidence while legacy M15 rejects the same intent");
        var marginal=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            eurDevelopmentProfile:transitionProfile with {MatchEconomicTransitionHorizonAtFill=true,
                MinimumContractVolumeOnly=false,OptimizeTransitionNetVolume=true});
        marginal.Advance(Clock(at));
        check(marginal.OriginalModelEvents.Count(e=>e.Kind=="REQUEST_OPEN")==1&&
            marginal.OriginalModelEvents.Single(e=>e.Kind=="REQUEST_OPEN").Units==2m,
            "Marginal transition NET search chooses one evidenced legal amount with highest financed monetary value");
        var corroborated=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            eurDevelopmentProfile:transitionProfile with {MatchEconomicTransitionHorizonAtFill=true,
                MinimumContractVolumeOnly=false,OptimizeTransitionNetVolume=true,RequireMaturedCashForLargerVolume=true});
        corroborated.Advance(Clock(at));
        check(corroborated.OriginalModelEvents.Single(e=>e.Kind=="REQUEST_OPEN").Units==1m&&
            corroborated.ResearchDecisionCounts.ContainsKey("EUR_PAV1_LARGER_VOLUME_NO_MATURED_MONETARY_EDGE"),
            "Missing matured cash support rejects extra volume and preserves a minimum-volume entry");
        var consensus=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            eurDevelopmentProfile:transitionProfile with {MatchEconomicTransitionHorizonAtFill=true,RequirePav1FastAgreement=true});
        consensus.Advance(Clock(at));
        check(consensus.ModelSummary.PendingIntents==0&&consensus.ResearchDecisionCounts.ContainsKey("EUR_PAV1_M15_ADMISSION_DISAGREEMENT"),
            "Contrary M15 monetary evidence is detected at admission rather than creating known-unfillable H1 intents");
        var extended=market with {EconomicTransitionWindows=windows.Where(w=>w.Timeframe is NativeBarTimeframe.H1 or NativeBarTimeframe.M15 or NativeBarTimeframe.M5)
            .Select(w=>w with {RequiredBars=24,Bars=Enumerable.Range(0,24).Select(i=>w.Bars[^1] with
                {OpenAt=w.Bars[^1].CloseAt-(24-i)*(long)w.Timeframe*60000L,
                 CloseAt=w.Bars[^1].CloseAt-(23-i)*(long)w.Timeframe*60000L,Open=100m+i*.1m,
                 Close=100m+i*.1m,High=101m+i*.1m,Low=99m+i*.1m}).ToArray()}).ToArray()};
        check(NativeEconomicMechanisms.Continuation(extended,at,"H1",24) is {Count:>=2,Mean:>0m},
            "Longer PAV1 history uses only adjacent transitions in the registered causal closed-bar window");
        check(NativeEconomicMechanisms.BoundaryPathValueEur(1,100m,95m,105m,100m,106m,94m,104m,1m,1m)==-5m&&
            NativeEconomicMechanisms.BoundaryPathValueEur(-1,100m,105m,95m,100m,106m,94m,96m,1m,1m)==-5m,
            "Both-boundary ambiguity is adverse for LONG and SHORT, never a fabricated target fill");
        check(NativeEconomicMechanisms.BoundaryPathValueEur(1,100m,95m,105m,90m,102m,89m,101m,1m,1m)==-10m,
            "A stop gap retains the worse opening loss");
        check(NativeEconomicMechanisms.BoundaryPathValueEur(1,100m,95m,105m,100m,106m,99m,104m,1m,1m)==5m,
            "A target path is bounded by the target before any subsequent close");
        var boundaryForecast=NativeEconomicMechanisms.BoundaryDistributionEur(extended,at,1,102m,100m,104m,"H1");
        check(boundaryForecast is {Count:>=8,Days:>=1,Mean:>0m,HorizonMs:3_600_000L}&&boundaryForecast.Through<at,
            "Boundary projection discloses completed historical support, days and actual forecast horizon");
        var twoBarBoundary=NativeEconomicMechanisms.BoundaryDistributionEur(extended,at,1,102m,100m,104m,"H1",horizonBars:2);
        check(twoBarBoundary is {Count:>=8 and <=11,HorizonMs:7_200_000L}&&
            boundaryForecast is not null&&twoBarBoundary.Mean>boundaryForecast.Mean&&twoBarBoundary.Through<at,
            "Two-bar boundary paths accumulate causal movement without overlapping forward labels");
        check(NativeEconomicMechanisms.BoundaryDistributionEur(extended,at,1,102m,100m,104m,"H1",horizonBars:3) is null&&
            NativeEconomicMechanisms.BoundaryDistributionEur(extended,at,1,102m,100m,104m,"H1",horizonBars:7) is null,
            "Insufficient nonoverlapping multi-bar evidence or out-of-range horizon cannot establish a forecast");
        check(NativeEconomicMechanisms.BoundaryDistributionEur(extended,at,1,102m,100m,104m,"H1",40) is null&&
            NativeEconomicMechanisms.BoundaryDistributionEur(extended,at,1,102m,100m,104m,"H1",2) is null,
            "Neither insufficient support nor a two-observation profile establishes a boundary forecast");
        check(NativeEconomicMechanisms.BoundaryDistributionEur(extended with
            {ClosedBars=extended.ClosedBars! with {DecisionAt=at-1}},at,1,102m,100m,104m,"H1") is null,
            "Boundary forecasts reject context from a different decision clock");
        NativeBarWindow Scaled(NativeBarWindow w)=>w with {Bars=w.Bars.Select(b=>b with
            {Open=b.Open*10m,High=b.High*10m,Low=b.Low*10m,Close=b.Close*10m}).ToArray()};
        var scaledBoundary=extended with {Quote=extended.Quote with
            {EurCredit=extended.Quote.EurCredit/10m,EurDebit=extended.Quote.EurDebit/10m},
            ClosedBars=extended.ClosedBars! with {Windows=extended.ClosedBars.Windows.Select(Scaled).ToArray()},
            EconomicTransitionWindows=extended.EconomicTransitionWindows!.Select(Scaled).ToArray()};
        var scaledForecast=NativeEconomicMechanisms.BoundaryDistributionEur(scaledBoundary,at,1,1020m,1000m,1040m,"H1");
        check(scaledForecast is not null&&boundaryForecast is not null&&scaledForecast.Count==boundaryForecast.Count&&
            Math.Abs(scaledForecast.Mean-boundaryForecast.Mean)<.000000001m&&
            scaledForecast.StopProbability==boundaryForecast.StopProbability,
            "Price denomination and its EUR conversion do not change a normalized monetary boundary forecast");
        NativeBarWindow FutureBoundary(NativeBarWindow w)=>w with {Bars=w.Bars.Append(w.Bars[^1] with {CloseAt=at+1}).ToArray()};
        check(NativeEconomicMechanisms.BoundaryDistributionEur(extended with
            {ClosedBars=extended.ClosedBars! with {Windows=extended.ClosedBars.Windows.Select(FutureBoundary).ToArray()},
             EconomicTransitionWindows=extended.EconomicTransitionWindows!.Select(FutureBoundary).ToArray()},
            at,1,102m,100m,104m,"H1") is null,
            "A future label invalidates boundary evidence rather than increasing support or its payoff");
        var adverseProjection=extended with {EconomicTransitionWindows=extended.EconomicTransitionWindows!.Select(w=>w with
            {Bars=w.Bars.Select((b,i)=>i==2?b with {Low=.001m}:b).ToArray()}).ToArray()};
        check(NativeEconomicMechanisms.BoundaryDistributionEur(adverseProjection,at,1,100m,99m,101m,"H1") is null&&
            NativeEconomicMechanisms.BoundaryDistributionEur(adverseProjection,at,1,100m,99m,101m,"H1",horizonBars:2) is null,
            "An invalid adverse projection cannot be omitted to improve the empirical forecast");
        var forecastFunding=market with {FundingOffers=new[]{new NativeFundingOfferEvidence(market.Symbol,1,1m,
            at-1,at-1,at+300_000L,at+900_000L,.1m,new string('a',64))}};
        check(NativePortfolioFunding.OfferDebit(forecastFunding,1,1m,at,null,at+900_000L)==.1m&&
            NativePortfolioFunding.OfferDebit(forecastFunding,1,1m,at,null,at+3_600_000L) is null&&
            NativePortfolioFunding.OfferDebit(forecastFunding,1,1m,at,null,at+7_200_000L) is null,
            "A shorter management funding offer cannot finance a longer boundary forecast");
        check(NativeEconomicMechanisms.Continuation(extended with {ClosedBars=extended.ClosedBars! with {DecisionAt=at-1}},at,"H1",24) is null,
            "Extended transition evidence must bind to the same decision clock");
        check(NativeEconomicMechanisms.Continuation(extended with {EconomicTransitionWindows=extended.EconomicTransitionWindows!
            .Select(w=>w with {Bars=w.Bars.Append(w.Bars[^1] with {CloseAt=at+1}).ToArray()}).ToArray()},at,"H1",24) is null,
            "A future bar invalidates an extended transition window rather than improving its estimate");
        string scenario=new string('a',64);
        var conditional=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,fundingScenarioId:scenario,
            eurDevelopmentProfile:transitionProfile with {MatchEconomicTransitionHorizonAtFill=true,UseMarketTimeFxValuation=true});
        Ucp1Frame Bound(long time)=>Clock(time) with {Markets=Clock(time).Markets.Select(m=>m with
            {FundingOffers=m.FundingOffers!.Select(f=>f with {ScenarioId=scenario}).ToArray()}).ToArray()};
        conditional.Advance(Bound(at));conditional.Advance(Bound(at+1000));
        var held=conditional.ModelSummary;
        check(held.OpenPositions==1,"Conditional valuation fixture contains an actual native held position");
        var quote=Clock(at+2000).Markets[0].Quote;
        var mark=new Ucp1Frame(at+2000,Array.Empty<Ucp1MarketFrame>())
            {ConditionalHoldingValuations=new[]{quote with {Bid=1m,Ask=2m}}};
        conditional.Advance(mark);
        check(conditional.ModelSummary.OpenPositions==1&&conditional.ModelSummary.PendingIntents==0&&
            conditional.ModelSummary.CashEur==held.CashEur&&conditional.ModelSummary.LiquidationEquityEur<held.LiquidationEquityEur,
            "Carried holding marks change conditional valuation but cannot fill, stop or close a position");
        var recovered=NativeUnifiedPortfolioEngine.RestoreHistoricalEurCheckpoint(conditional.HistoricalEurCheckpoint());
        var next=mark with {At=at+3000,ConditionalHoldingValuations=new[]{quote with {At=at+3000,Bid=2m,Ask=3m}}};
        conditional.Advance(next);recovered.Advance(next);
        check(recovered.ModelSummary.EventChainHash==conditional.ModelSummary.EventChainHash,
            "Conditional valuation profile and common ledger resume exactly from a native checkpoint");
        bool rejected=false;
        try{recovered.Advance(next with {At=at+4000,ConditionalHoldingValuations=new[]{quote with {At=at+4000,Symbol="UNHELD"}}});}
        catch(ArgumentException e){rejected=e.Message=="CONDITIONAL_HOLDING_VALUATION_BINDING";}
        check(rejected,"Conditional holding valuation cannot be used for an unheld instrument");
    }
}
