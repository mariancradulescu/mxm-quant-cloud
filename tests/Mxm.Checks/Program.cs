using Mxm.Core;
var passed = 0;
void Check(bool condition, string name) { if (!condition) throw new Exception(name); passed++; }
var good = new RecoveryEvidence(200, 200, 200, true, true, true, false, false);
Check(Recovery.Assess(good).Mode == RecoveryMode.ReconciledObservation, "complete evidence permits observation only");
Check(Recovery.Assess(good with { EquityPeakUpperBound = null }).Mode == RecoveryMode.Protective, "missing peak");
Check(Recovery.Assess(good with { Equity = 140 }).Mode == RecoveryMode.Protective, "exact 30 percent boundary");
Check(Recovery.Assess(good with { EquityPeakUpperBound = 300 }).Mode == RecoveryMode.Protective, "profit peak survives restart");
Check(Recovery.Assess(good with { AmbiguousOrder = true }).Mode == RecoveryMode.Protective, "ambiguous order never retried");
Check(Recovery.Assess(good with { CashflowsVerified = false }).Mode == RecoveryMode.Protective, "cashflow uncertainty");
Check(Recovery.Assess(good with { AdaptationRebuilt = false }).Mode == RecoveryMode.Protective, "rebuild uncertainty");
var t = new DateTime(2026, 10, 26, 0, 0, 0, DateTimeKind.Utc);
var a = new ClosedDeal(1, 10, t.AddDays(1), 40);
var b = new ClosedDeal(2, 10, t.AddDays(2), 60);
var volumes = new Dictionary<long, decimal> { [10] = 100 };
Check(RoundTrips.Count(t,t.AddDays(7),new[]{a,b,a},volumes,new HashSet<long>()) == 1,"partial exits and duplicate events count once");
Check(RoundTrips.Count(t,t.AddDays(7),new[]{a},volumes,new HashSet<long>()) == 0,"incomplete close excluded");
Check(RoundTrips.Count(t,t.AddDays(7),new[]{a,b},volumes,new HashSet<long>{10}) == 0,"still open excluded");
var ledger=new NetLedger();
var settlement=new NetSettlement("deal-1",5m,1m,-0.5m,0.2m,new string('a',64));
ledger.Apply(settlement);
Check(ledger.Balance==203.3m,"net settlement in EUR includes all supplied costs");
ledger.Apply(settlement);
Check(ledger.Balance==203.3m,"duplicate settlement idempotency");
var conflict=false;
try { ledger.Apply(settlement with { GrossEur=6m }); } catch (InvalidOperationException) { conflict=true; }
Check(conflict,"conflicting economic evidence rejected");

// Synthetic cost-floor arithmetic, never a claim about live broker pricing.
var missingCosts=FundedBrokerCostScreen.Assess(new FundedBrokerQuote(
    "EURUSD",1.10000m,1.10010m,1000m,null,null,null,null,null,null,null,true,true));
Check(!missingCosts.Complete && missingCosts.Status=="OBSERVED_BID_ASK_MARGIN_OR_COST_MISSING",
    "no assumed currency conversion commission slippage or margin at EUR200");
var costScenario=FundedBrokerCostScreen.Assess(new FundedBrokerQuote(
    "SYNTH",1.10000m,1.10010m,1000m,.90m,.10m,.10m,.05m,0m,45m,.02m,true,true));
Check(costScenario.Complete && costScenario.CanFundFromInitialCapital &&
    costScenario.MinimumAllInCostEur==.36m &&
    costScenario.MinimumNonnegativeProfitMoveInQuote==.0004m,
    "cost-adjusted break-even from executable bid ask for minimum volume");
var marginBlocked=FundedBrokerCostScreen.Assess(new FundedBrokerQuote(
    "SYNTH",1.1m,1.1001m,1000m,.90m,.10m,.10m,.05m,0m,205m,.02m,true,true));
Check(marginBlocked.Complete && !marginBlocked.CanFundFromInitialCapital &&
    marginBlocked.Status=="INITIAL_200_EUR_OR_MAX_DRAWDOWN_INCOMPATIBLE",
    "minimum broker margin above EUR200 is not fundable");

// Synthetic-only portfolio evaluation: input truth flags are NOT evidence.
DateTime UTC(int year,int month,int day) => new(year,month,day,0,0,0,DateTimeKind.Utc);
var study = new StudyWindow(UTC(2025,10,20), UTC(2026,3,2), UTC(2026,7,6), UTC(2026,11,2));
var week = UTC(2026,7,6);
var syntheticTrades = Enumerable.Range(1,21).Select(i => new CompletedPortfolioTrade(
    i, week.AddHours(i), week.AddHours(i+1),
    1m, .1m, .1m, .1m, 0m, .1m, new string('a',64), true)).ToArray();
var observed = new [] {
    new LiquidationEquityMark(study.DevelopmentStartUtc,200m,true),
    new LiquidationEquityMark(study.ConfirmationStartUtc,200m,true),
    new LiquidationEquityMark(study.EndUtc,212.6m,true)
};
var unproven = new EconomicProof(false,false,false,false,false,false,false,false,null,null);
var observedOnly = PortfolioEconomics.Evaluate(study, syntheticTrades, observed,
    new[]{week}, unproven);
Check(observedOnly.StartCapitalEur==200m && observedOnly.ClosedNetEur==12.6m &&
    observedOnly.FinalRealizedBalanceEur==212.6m, "continuous funded EUR200 cost ledger");
Check(observedOnly.MinimumCompleteRoundTripsPerEligibleWeek==21 && !observedOnly.Pass &&
    observedOnly.Verdict=="AUTHENTIC_SOURCE_NOT_PROVEN", "synthetic profits cannot qualify");
var completeFlags = new EconomicProof(true,true,true,true,true,true,true,true,199m,220m);
// Even with assertions set to true, this is ONLY a test of the gate's logic.
// No synthetic assertions are attached to real source evidence.
var logicalPass = PortfolioEconomics.Evaluate(study,syntheticTrades,observed,
    new[]{week},completeFlags);
Check(!logicalPass.Pass && logicalPass.Verdict=="EVIDENCE_CHAIN_NOT_VERIFIED" &&
    logicalPass.CertifiedMaxDrawdownUpperBound is > 0m and < .30m,
    "manufactured true proof cannot qualify an economically attractive fixture");
var tooFew = PortfolioEconomics.Evaluate(study,syntheticTrades.Take(20),
    new [] {observed[0],observed[1],observed[2] with {EquityEur=212m}},
    new[]{week},completeFlags);
Check(!tooFew.Pass && tooFew.Verdict=="HARD21_NOT_DEMONSTRATED",
    "HARD21 counts complete positions at portfolio level");
var uncertified = PortfolioEconomics.Evaluate(study,syntheticTrades,observed,
    new[]{week}, completeFlags with {CertifiedGlobalEquityFloorEur=null});
Check(uncertified.Verdict=="GLOBAL_DRAWDOWN_BOUND_NOT_PROVEN" && !uncertified.Pass,
    "sampled equity is not certified max drawdown");
var breached = PortfolioEconomics.Evaluate(study,syntheticTrades,observed,
    new[]{week},completeFlags with {CertifiedGlobalEquityFloorEur=140m});
Check(!breached.Pass && breached.Verdict=="DRAWDOWN_LIMIT",
    "conservative liquidation-extrema bound enforces owner maximum");
var noNet = PortfolioEconomics.Evaluate(study,
    syntheticTrades.Select(x=>x with {GrossEur=.1m}),
    new[]{observed[0],observed[1],observed[2] with {EquityEur=193.7m}},
    new[]{week},completeFlags with {CertifiedGlobalEquityFloorEur=190m});
Check(!noNet.Pass && noNet.Verdict=="CONFIRMATION_NET_NOT_POSITIVE",
    "broker economic costs are never suppressed for favorable score");
var noFullYear = PortfolioEconomics.Evaluate(study with {DevelopmentStartUtc=UTC(2026,1,1)},
    syntheticTrades, new[]{observed[0] with {TimeUtc=UTC(2026,1,1)},observed[1],observed[2]},
    new[]{week},completeFlags);
Check(!noFullYear.Pass && noFullYear.Verdict=="LESS_THAN_TWELVE_CALENDAR_MONTHS",
    "twelve actual calendar months mandatory");
bool Rejects(Action check) {try{check();return false;}catch(ArgumentException){return true;}}
Check(Rejects(()=>PortfolioEconomics.Evaluate(study,
    syntheticTrades.Concat(new[]{syntheticTrades[0]}),observed,new[]{week},completeFlags)),
    "duplicate position rejected");
Check(Rejects(()=>PortfolioEconomics.Evaluate(study,
    new[]{syntheticTrades[0] with {ExitCommissionEur=null}},observed,new[]{week},completeFlags)),
    "unknown cost cannot default to zero");
Check(Rejects(()=>PortfolioEconomics.Evaluate(study,
    new[]{syntheticTrades[0] with {OpenUtc=study.SelectionStartUtc.AddHours(-1),
        CloseUtc=study.SelectionStartUtc.AddHours(1)}},observed,new[]{week},completeFlags)),
    "chronological splits forbid cross-boundary PnL relabeling");
Check(Rejects(()=>PortfolioEconomics.Evaluate(study,
    syntheticTrades,observed,new[]{week,week},completeFlags)),
    "eligible weeks must be unique and predeclared");
Check(Rejects(()=>PortfolioEconomics.Evaluate(study,
    syntheticTrades,observed,new[]{week},completeFlags
        with {CertifiedGlobalEquityPeakUpperEur=200m})),
    "claimed peak certificate cannot contradict observed equity");


// The H1 predictor learns only after a preceding target bar is completed.
var research = new CausalRangePressureResearch();
var independent = new CausalRangePressureResearch();
DateTime h1Base=UTC(2026,9,7);
CompletedH1Candle Bar(int i,decimal close) =>
    new("EURUSD",h1Base.AddHours(i),h1Base.AddHours(i+1),
        close-.0002m,close+.0004m,close-.0005m,close,
        100+i,new string('c',64));
var predictiveBars=Enumerable.Range(0,14).Select(i=>
    Bar(i,1.1000m+i*.0001m)).ToArray();
ResearchForecast? twelve=null;
for(int i=0;i<12;i++)
{
    var forecast=research.Observe(predictiveBars[i]);
    if(i<11) Check(forecast is null,"H1 causal warmup no early score");
    if(i==11)twelve=forecast;
}
Check(twelve is { Status: CausalRangePressureResearch.ResearchOnly } &&
    twelve.AsOfUtc==predictiveBars[11].EvidenceAvailableUtc &&
    twelve.TargetBarEndsUtc==predictiveBars[11].EvidenceAvailableUtc.AddHours(1),
    "predict next bar only after complete candle");
for(int i=0;i<12;i++)independent.Observe(predictiveBars[i]);
var changedFuture=predictiveBars[12] with {Close=1.10105m};
var nextOriginal=research.Observe(predictiveBars[12]);
var nextChanged=independent.Observe(changedFuture);
Check(nextOriginal is not null && nextChanged is not null &&
    twelve is not null && twelve.ProbabilityUp >= .05m && twelve.ProbabilityUp <= .95m,
    "bounded, observation-only probability");
var gap=research.Observe(Bar(15,1.1020m));
Check(gap is null,"H1 gap resets adaptation and warmup");
Check(Rejects(()=>research.Observe(Bar(15,1.1020m))),"duplicate H1 bar rejected");
Check(Rejects(()=>new CausalRangePressureResearch().Observe(
    Bar(1,1.1m) with {EvidenceAvailableUtc=h1Base.AddHours(1)})),
    "no use of unclosed candle");
Check(Rejects(()=>new CausalRangePressureResearch().Observe(
    Bar(1,1.1m) with {SourceEvidenceSha256="invalid"})),
    "unverified H1 input blocked");
var fixedSource = new CausalRangePressureResearch();
fixedSource.Observe(Bar(0,1.10m));
Check(Rejects(()=>fixedSource.Observe(
    Bar(1,1.10m) with {Symbol="GBPUSD"})),"different symbol never shares adaptive weights");


var accountRisk = new BrokerRiskSnapshot(220m, 170m, 240m,true,true,true,true);
var existingRisk = new[]{
    new OpenRiskExposure("position-1",.5m,20m),
    new OpenRiskExposure("position-2",.7m,30m)
};
var proposalRisk = new ProposedRiskExposure("position-3",.8m,.2m,35m);
var riskOk = PortfolioRiskBudget.Assess(accountRisk,existingRisk,proposalRisk);
Check(riskOk.Admissible && riskOk.PortfolioPositionCountAfter==3 &&
    riskOk.DrawdownHeadroomEur==52m && riskOk.TotalStressLossAfterEur==2.2m,
    "dynamic multi-position risk without obsolete per-trade caps");
Check(!PortfolioRiskBudget.Assess(accountRisk with {CertifiedEquityPeakUpperEur=null},
    existingRisk,proposalRisk).Admissible,"uncertified peak cannot open risk capacity");
Check(!PortfolioRiskBudget.Assess(accountRisk with {OrderOutcomesKnown=false},
    existingRisk,proposalRisk).Admissible,"ambiguous execution blocks new exposure");
Check(!PortfolioRiskBudget.Assess(accountRisk with {EquityEur=168m},
    existingRisk,proposalRisk).Admissible,"drawdown boundary has zero headroom");
Check(!PortfolioRiskBudget.Assess(accountRisk,existingRisk,
    proposalRisk with {RequiredMarginEur=131m}).Admissible,
    "margin cannot exceed actual free broker margin");
Check(!PortfolioRiskBudget.Assess(accountRisk,
    new[]{existingRisk[0],existingRisk[0]},proposalRisk).Admissible,
    "duplicated native positions cannot fake exposure");
Check(!PortfolioRiskBudget.Assess(accountRisk with {ProposedMarginAndLossBoundsVerified=false},
    existingRisk,proposalRisk).Admissible,
    "estimated scenario risk does not replace verified broker bounds");


var sourceClocks = new [] {
    new SourceBarClock("EURUSD",UTC(2026,1,5),UTC(2026,1,5).AddMinutes(5),TimeSpan.FromMinutes(5),new string('a',64)),
    new SourceBarClock("EURUSD",UTC(2026,1,5).AddMinutes(5),UTC(2026,1,5).AddMinutes(10),TimeSpan.FromMinutes(5),new string('a',64)),
    new SourceBarClock("GBPUSD",UTC(2026,1,5),UTC(2026,1,5).AddHours(1),TimeSpan.FromHours(1),new string('b',64)),
    new SourceBarClock("EURUSD",UTC(2026,1,12),UTC(2026,1,12).AddMinutes(5),TimeSpan.FromMinutes(5),new string('a',64))
};
var clockAudit = CausalSourceCalendar.Assess(sourceClocks);
Check(clockAudit.ObservedBars==4 && clockAudit.DistinctSymbols==2 &&
    clockAudit.DistinctObservedIsoWeeks==2 && !clockAudit.TwelveCalendarMonthsObservedForAnySymbol,
    "multitimeframe weeks counted once, not multiplied by instruments");
Check(clockAudit.DiscontinuitiesBetweenSuccessiveSameSymbolBars==1,
    "unobserved session gaps explicitly retained");
Check(Rejects(()=>CausalSourceCalendar.Assess(
    sourceClocks.Concat(new[]{sourceClocks[0]}))),
    "duplicate source candles fail independently");
Check(!CausalSourceCalendar.Assess(new[]{
    sourceClocks[0],sourceClocks[0] with {
        OpenUtc=UTC(2027,1,5),
        AvailableUtc=UTC(2027,1,5).AddMinutes(5)
    }}).TwelveCalendarMonthsObservedForAnySymbol,
    "two isolated annual endpoints do not constitute annual source coverage");
Check(Rejects(()=>CausalSourceCalendar.Assess(
    new[]{sourceClocks[0] with {AvailableUtc=sourceClocks[0].OpenUtc}})),
    "unclosed candle cannot be a causal source input");


var brierLedger=new CausalForecastScoreLedger();
for (int i=0;i<99;i++)brierLedger.Score(.6m,1m);
var insufficientBrier=brierLedger.Summarize();
Check(insufficientBrier.Count==99 && insufficientBrier.MeanBrier==0m &&
    insufficientBrier.Qualification=="INSUFFICIENT_OBSERVATIONS_NO_PUBLIC_NUMERIC_SKILL",
    "no public numeric skill for small authentic research sample");
brierLedger.Score(.6m,1m);
var brierScore=brierLedger.Summarize();
Check(brierScore.Count==100 && brierScore.MeanBrier==.16m &&
    brierScore.BaselineMeanBrier==.25m &&
    brierScore.BrierSkillVersusNeutral==.36m,
    "proper prequential Brier score against fixed neutral baseline");
Check(Rejects(()=>brierLedger.Score(1.01m,0m)),
    "causal probabilities cannot be outside [0,1]");
Check(Rejects(()=>brierLedger.Score(.6m,.8m)),
    "resolved labels must be strict binary or tie");
Check(Rejects(()=>brierLedger.Summarize(1)),
    "public privacy minimum cannot be bypassed");

// Strictly synthetic directional OHLC proxy; no brokerage fills or NET.
var breakoutBars=new List<PriceOnlyBar>();
DateTime breakoutStart=UTC(2026,9,1);
for(int k=0;k<20;k++)
{
    long o=1000,h=1020,l=980,cl=1000;
    if(k==12){o=1005;h=1050;l=1000;cl=1040;}
    if(k>=13){o=1040;h=1080;l=1030;cl=1070;}
    breakoutBars.Add(new PriceOnlyBar("TEST","H4",
        breakoutStart.AddHours(4*k),breakoutStart.AddHours(4*(k+1)),
        240,o,h,l,cl));
}
var breakoutResult=EconomicBreakoutProbe.Assess(breakoutBars,4);
Check(breakoutResult.Episodes>0 && breakoutResult.MeanGrossPips is > 0m &&
    breakoutResult.Verdict==EconomicBreakoutProbe.PriceOnly,
    "new distinct H4 range breakout reports only gross pip proxies");
var gapBars=breakoutBars.Select((x,k)=>k==13?
    x with {OpenUtc=x.OpenUtc.AddHours(4),AvailableUtc=x.AvailableUtc.AddHours(4)}:x);
Check(Rejects(()=>EconomicBreakoutProbe.Assess(gapBars,4)),
    "duplicate or out-of-order market timeline blocks research");


// Funded quote-level EUR lower bound (SYNTHETIC inputs; no broker fill proof).
DateTime e0=new(2026,11,2,12,0,0,DateTimeKind.Utc);
var quoted=new ExecutableQuoteEvidence("SYNTH",PositionDirection.Buy,
    e0,e0.AddMinutes(15),1.1000m,1.1002m,1.1010m,1.1012m,
    1000m,1000m,1000m,.9m,.1m,.1m,.1m,.2m,.1m,
    20m,200m,new string('f',64),true,true,true,true);
var priced=ExecutableNet.Evaluate(quoted);
Check(priced.FullyPriced && priced.FundableAt200Eur &&
    priced.QuoteGrossEur==.72m &&
    priced.TotalCostUpperEur==.6m &&
    priced.AdverseNetLowerEur==.12m && !priced.EconomicQualified,
    "quote bid ask and all bound EUR costs computed but not mistaken for broker fills");
Check(ExecutableNet.Evaluate(quoted with {SlippageUpperEur=null}).Verdict==
    "EXECUTABLE_QUOTE_MARGIN_OR_NET_COST_MISSING",
    "no slippage value never treated as free");
Check(!ExecutableNet.Evaluate(quoted with {BothQuoteEventsVerified=false}).FullyPriced,
    "bar-open or one-minute disconnected quotes do not price roundtrip");
Check(!ExecutableNet.Evaluate(quoted with {Units=1200m}).FullyPriced,
    "minimum broker volume step enforced exactly");
Check(!ExecutableNet.Evaluate(quoted with {RequiredMarginEur=250m}).FundableAt200Eur,
    "EUR200 cannot fund broker-required margin");
Check(!ExecutableNet.Evaluate(quoted with {Original200EurNoDepositsReconciled=false}).FullyPriced,
    "no synthetic 200 EUR funded account identity");
Check(Rejects(()=>ExecutableNet.Evaluate(quoted with {EntryAsk=1.099m})),
    "crossed impossible original bid ask is rejected");
var shortScenario=ExecutableNet.Evaluate(quoted with {Direction=PositionDirection.Sell});
Check(shortScenario.QuoteGrossEur==-1.08m &&
    shortScenario.AdverseNetLowerEur==-1.68m,
    "shorts sell at bid and cover at ask without favorable fills");

// Multi-lane automatic recovery from independent snapshots; no order calls.
var safeAccount=new RecoveryPortfolioEvidence(200m,170m,200m,true,true,true,
    .5m,30m,0);
var uncertain=new RecoveryLaneEvidence("EURUSD",true,true,false,true,false,
    1m,10m);
var other=new RecoveryLaneEvidence("AUDUSD",true,true,false,false,false,null,null);
var isolation=SelectiveRecovery.Assess(safeAccount,new[]{uncertain,other});
Check(isolation.MonitoringActive && isolation.CanReviewAnyNewExposure &&
    isolation.AvailableWorstCaseDrawdownHeadroomEur==58.5m &&
    isolation.ReservableFreeMarginEur==40m &&
    isolation.Lanes[0].Mode==RecoveryLaneMode.QuarantinedAmbiguous &&
    !isolation.Lanes[0].EligibleForFurtherRiskReview &&
    isolation.Lanes[1].EligibleForFurtherRiskReview,
    "bounded unknown order isolates EURUSD while AUDUSD survives adverse risk certificate");
var noHistoryProof=SelectiveRecovery.Assess(
    safeAccount with {HistoricalInFlightIntentsCertified=false},new[]{other});
Check(!noHistoryProof.CanReviewAnyNewExposure && noHistoryProof.MonitoringActive,
    "restart never treats empty in-memory requests as proof of absent ambiguous orders");
var missingBudget=SelectiveRecovery.Assess(safeAccount,
    new[]{uncertain with {WorstCaseUnknownOrderLossEur=null},other});
Check(!missingBudget.CanReviewAnyNewExposure && missingBudget.MonitoringActive,
    "unbounded unknown order blocks new risk globally while monitor continues");
var networkDown=SelectiveRecovery.Assess(safeAccount,new[]{
    uncertain with {UncertainOrderSubmission=false,TransientFault=true},other});
Check(networkDown.Lanes[0].Mode==RecoveryLaneMode.AutoRecoverTransient &&
    networkDown.Lanes[1].EligibleForFurtherRiskReview,
    "transient local disconnect recovers without freezing unaffected symbol");
var autoReturned=SelectiveRecovery.Assess(safeAccount,new[]{
    uncertain with {UncertainOrderSubmission=false},other});
Check(autoReturned.Lanes.All(x=>x.EligibleForFurtherRiskReview),
    "fresh native snapshots automatically restore eligible lanes");
var vanishedButUnknown=SelectiveRecovery.Assess(safeAccount,new[]{uncertain});
Check(vanishedButUnknown.Lanes[0].Mode==RecoveryLaneMode.QuarantinedAmbiguous,
    "mere absence in inventory never clears unknown submission");
var finalReconciliation=SelectiveRecovery.Assess(safeAccount,new[]{
    uncertain with {PositiveBrokerFinalOutcomeReconciled=true},other});
Check(finalReconciliation.Lanes.All(x=>x.EligibleForFurtherRiskReview) &&
    finalReconciliation.AvailableWorstCaseDrawdownHeadroomEur==59.5m,
    "affirmative terminal broker proof releases adverse reservation automatically");
var inFlightFull=SelectiveRecovery.Assess(
    safeAccount with {VerifiedCurrentInFlightRequests=1},new[]{other});
Check(!inFlightFull.CanReviewAnyNewExposure &&
    inFlightFull.Lanes[0].Mode==RecoveryLaneMode.ReadyForObservation,
    "one global in-flight slot prevents overlapping ambiguous requests");
Check(!SelectiveRecovery.Assess(
    safeAccount with {EquityEur=140m},new[]{other}).CanReviewAnyNewExposure,
    "30 percent drawdown boundary remains protective but timer can continue");


// Material causality and currency-cost invariants for new quote NET engine.
var shockBars=Enumerable.Range(0,25).Select(i=>new IntradayReversalNet.Bar(
    new DateTimeOffset(2026,1,5,2,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds()+i*900000L,
    1.10m,1.101m,1.099m,i>=12?1.104m:1.10m)).ToArray();
// Build valid high/low geometry and a preceding one-hour upward shock at 06 UTC.
shockBars=shockBars.Select((b,i)=>b with {H=1.109m,L=1.099m,C=i>=12?1.108m:1.10m}).ToArray();
Check(IntradayReversalNet.Propose(shockBars).Length==0,"subthreshold hour never forced to satisfy HARD21");
shockBars=shockBars.Select((b,i)=>b with {H=1.12m,C=i==15?1.12m:1.10m}).ToArray();
Check(IntradayReversalNet.Propose(shockBars).Length==0,"range threshold is causal and honored");
var reversalBars=Enumerable.Range(0,25).Select(i=>new IntradayReversalNet.Bar(shockBars[i].T,
    1.10m,i==15?1.105m:1.101m,1.099m,i==15?1.105m:1.10m)).ToArray();
var frozenPlans=IntradayReversalNet.Propose(reversalBars);
Check(frozenPlans.Length==1 && frozenPlans[0].Direction==-1,"predeclared large upward shock is faded at six UTC");
var alteredFuture=reversalBars.Select((b,i)=>i>=16?b with {C=1.2m,H=1.3m,L=1.0m}:b).ToArray();
Check(IntradayReversalNet.Propose(alteredFuture).Select(p=>(p.Entry,p.Exit,p.Direction)).SequenceEqual(
    frozenPlans.Select(p=>(p.Entry,p.Exit,p.Direction))),"future holding returns cannot change frozen signal");
Check(Rejects(()=>IntradayReversalNet.Propose(reversalBars.Concat(new[]{reversalBars[0]}).ToArray())),
    "duplicate source cannot create additional modeled trades");

// OWNER material correction: preventive stop/gap/cost risk BEFORE entry.
var executionTerms=new StopExecutionTerms(1000m,1000m,100000m,.001m,.002m,.0001m,.0003m,.0002m,.0001m,
    1m/1.08m,.0001m,0m,.04m,true,true);
var preventive=PreventiveExecutionRisk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms);
Check(preventive.Units>=1000m && preventive.StressDrawdown<.30m && !preventive.AbsoluteGuarantee,
    "pre-entry native stop gap slip FX cost and favorable-peak scenario capacity; residual gaps not guaranteed");
Check(PreventiveExecutionRisk.Size(141m,200m,141m,Array.Empty<ReservedPositionRisk>(),executionTerms).Units==0,
    "minimum lot blocked BEFORE entry when remaining DD cannot absorb stop plus gap");
var portfolioReserved=new[]{new ReservedPositionRisk("GBP",2m,4m,40m),new ReservedPositionRisk("AUD",2m,4m,20m)};
Check(PreventiveExecutionRisk.Size(200m,200m,140m,portfolioReserved,executionTerms).Units==0,
    "existing aggregate risk above 1 percent cannot admit another position");
Check(PreventiveExecutionRisk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms with {MinimumUnits=100000m,StepUnits=100000m}).Units==0,
    "broker minimum larger than funded risk budget rejected without rounding up");
Check(PreventiveExecutionRisk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms with {MinimumBrokerStopDistance=.002m}).Units==0,
    "invalid broker stop rejected before exposure");
Check(PreventiveExecutionRisk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms with {ReconciledAccount=false}).Units==0,
    "unknown account inhibits new exposure without changing selective monitor recovery");
Check(PreventiveExecutionRisk.Size(200m,200m,20m,new[]{new ReservedPositionRisk("other",1m,0,180m)},executionTerms).Units==0,
    "open portfolio margin and potential loss reserved before minimum lot");
Check(OwnerRiskLimits.Check(200m,160m,1m,40m,1m,40m).Allowed,"aggregate two-position exact 1/40/60 boundary admitted");
Check(!OwnerRiskLimits.Check(200m,160m,1.01m,40m,1m,40m).Allowed,"aggregate risk counts open plus proposed without correlation discount");
Check(!OwnerRiskLimits.Check(200m,160m,0,40m,1m,40.01m).Allowed,"margin 40 percent boundary enforced");
Check(!OwnerRiskLimits.Check(200m,120m,0,20m,1m,1m).Allowed,"actual free reserve below60 blocks even with low reported aggregate margin");
Check(OwnerRiskLimits.Check(300m,240m,1.5m,60m,1.5m,60m).Allowed,"limits scale on reconciled current equity after reinvestment");
Check(!OwnerRiskLimits.Check(150m,120m,1m,30m,.51m,10m).Allowed,"risk budget contracts with current equity loss");
Check(!SelectiveRecovery.Assess(safeAccount with {ExistingStressLossEur=2.1m},new[]{other}).CanReviewAnyNewExposure &&
    SelectiveRecovery.Assess(safeAccount with {ExistingStressLossEur=2.1m},new[]{other}).MonitoringActive,
    "owner risk exhaustion blocks new risk but monitoring and recovery continue");
Console.WriteLine($"PASS {passed} recovery/accounting/portfolio/causal-H1/dynamic-risk/source-calendar/causal-score checks; synthetic, no economic qualification.");
