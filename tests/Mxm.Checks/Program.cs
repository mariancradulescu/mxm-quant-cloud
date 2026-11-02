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


var accountRisk = new BrokerRiskSnapshot(220m, 130m, 240m,true,true,true,true);
var existingRisk = new[]{
    new OpenRiskExposure("position-1",5m,20m),
    new OpenRiskExposure("position-2",7m,30m)
};
var proposalRisk = new ProposedRiskExposure("position-3",8m,2m,35m);
var riskOk = PortfolioRiskBudget.Assess(accountRisk,existingRisk,proposalRisk);
Check(riskOk.Admissible && riskOk.PortfolioPositionCountAfter==3 &&
    riskOk.DrawdownHeadroomEur==52m && riskOk.TotalStressLossAfterEur==22m,
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

Console.WriteLine($"PASS {passed} recovery/accounting/portfolio/causal-H1/dynamic-risk/source-calendar checks; synthetic, no economic qualification.");
