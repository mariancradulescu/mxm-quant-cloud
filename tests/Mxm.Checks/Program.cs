using Mxm.Core;
var passed = 0;
MonetaryRecoveryChecks.Run(Check);
void Check(bool condition, string name) { if (!condition) throw new Exception(name); passed++; }
// Material identity/recovery contracts: no synthetic profitability claim.
var localIdentity=new LocalIntentIdentity("intent-A","order-A","position-A","SYNTH",1,2,false,1000);
var brokerOrder=new BrokerOrderIdentity("order-A","intent-A","position-A","SYNTH",1,2,2,false,"FILLED",2000);
var brokerDeals=new[]{new BrokerDealIdentity("deal-A","order-A","position-A","SYNTH",1,1,false,1500),new BrokerDealIdentity("deal-B","order-A","position-A","SYNTH",1,1,false,2000)};
var brokerIdentity=new BrokerIdentitySnapshot("TEST_ACCOUNT",3000,0,3000,true,true,true,new[]{brokerOrder},brokerDeals,new[]{new BrokerPositionIdentity("position-A","SYNTH",1,2)});
var matchedIdentity=BrokerIdentityReconciliation.Assess(brokerIdentity,new[]{localIdentity});
Check(matchedIdentity.SnapshotConsistent && matchedIdentity.Intents[0].PositiveTerminalEvidence && matchedIdentity.Intents[0].LedgerImportRequired,
    "split entry deals match order/position identities but do not manufacture monetary import");
var repeatedIdentity=BrokerIdentityReconciliation.Assess(brokerIdentity with {Deals=brokerDeals.Append(brokerDeals[0]).ToArray()},new[]{localIdentity});
Check(repeatedIdentity.SnapshotConsistent && repeatedIdentity.BrokerDeals==2,"duplicate broker executions count once");
Check(!BrokerIdentityReconciliation.Assess(brokerIdentity with {Positions=new[]{new BrokerPositionIdentity("position-A","SYNTH",1,1)}},new[]{localIdentity}).SnapshotConsistent,
    "partial position volume must equal positively linked open/close deals");
Check(!BrokerIdentityReconciliation.Assess(brokerIdentity with {Deals=brokerDeals.Append(brokerDeals[0] with {Units=2}).ToArray()},new[]{localIdentity}).SnapshotConsistent,
    "conflicting repeated deal cannot be reconciled");
var absentIdentity=BrokerIdentityReconciliation.Assess(brokerIdentity with {Orders=Array.Empty<BrokerOrderIdentity>(),Deals=Array.Empty<BrokerDealIdentity>(),Positions=Array.Empty<BrokerPositionIdentity>()},new[]{localIdentity});
Check(absentIdentity.UnresolvedIntents==1 && absentIdentity.Intents[0].State=="UNKNOWN_NO_RESUBMIT","empty complete query cannot cancel an unknown submission");
var identitySession=new NativeFundedSession("TEST_ACCOUNT",intents:new[]{localIdentity});
var restoredIdentitySession=NativeFundedSession.Restore(identitySession.Checkpoint(),"TEST_ACCOUNT");
Check(!restoredIdentitySession.Observe(brokerIdentity,200).CanConsiderNewExposure && !restoredIdentitySession.JournalContinuityProven,
    "checkpoint cannot promote unknown historical continuity or authorize orders");
bool wrongAccountBlocked=false;try{NativeFundedSession.Restore(identitySession.Checkpoint(),"OTHER_ACCOUNT");}catch(ArgumentException){wrongAccountBlocked=true;}
Check(wrongAccountBlocked,"checkpoint is account scoped");
// AIP1 real nonempty forecasts for causality and missing-label behavior.
const long auctionTestStart=1762128000000L;var auctionBars=new List<ProgramBar>();
for(int day=0;day<364;day++){
    var date=DateTimeOffset.FromUnixTimeMilliseconds(auctionTestStart+day*86400000L);if(date.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)continue;
    foreach(string symbol in new[]{"SYNTH1","SYNTH2"})for(int k=0;k<72;k++){
        double price=10000+day*50+k*2;long at=auctionTestStart+day*86400000L+6*3600000L+k*300000L;
        auctionBars.Add(new(symbol,at,at+300000,price,price+3,price-1,price+2,100+k));
    }
}
var auctionTest=new AuctionInput(auctionBars.ToArray(),new[]{new ProgramCost("SYNTH1",.01,10,1,true,1320,5),new ProgramCost("SYNTH2",.01,10,1,true,1320,5)},
    new[]{new AuctionSpec("SYNTH1","UTC",6,0,12,0),new AuctionSpec("SYNTH2","UTC",6,0,12,0)},auctionTestStart,auctionTestStart+26*604800000L,auctionTestStart+39*604800000L,auctionTestStart+52*604800000L);
using var auctionReceipt=System.Text.Json.JsonDocument.Parse(System.Text.Json.JsonSerializer.Serialize(AuctionInventoryResearch.Evaluate(auctionTest)));
Check(auctionReceipt.RootElement.GetProperty("TrainingSupportPassed").GetBoolean() && auctionReceipt.RootElement.GetProperty("Selection").GetProperty("PrimaryEpisodes").GetInt32()>0,
    "auction causality check exercises mature nonempty primary forecasts");
var futureAuction=auctionTest with {Bars=auctionTest.Bars.Select(b=>b.Start<auctionTest.SelectionEnd?b:b with {Open=1e10/b.Open,High=1e10/b.Low,Low=1e10/b.High,Close=1e10/b.Close}).ToArray()};
using var futureAuctionReceipt=System.Text.Json.JsonDocument.Parse(System.Text.Json.JsonSerializer.Serialize(AuctionInventoryResearch.Evaluate(futureAuction)));
Check(auctionReceipt.RootElement.GetProperty("Selection").GetRawText()==futureAuctionReceipt.RootElement.GetProperty("Selection").GetRawText(),"future audit prices cannot change earlier auction policy selection");
long firstAuction=auctionReceipt.RootElement.GetProperty("Forecasts").EnumerateArray().First(x=>x.GetProperty("Primary").GetBoolean()).GetProperty("At").GetInt64();
using var missingAuction=System.Text.Json.JsonDocument.Parse(System.Text.Json.JsonSerializer.Serialize(AuctionInventoryResearch.Evaluate(auctionTest with {Bars=auctionTest.Bars.Where(b=>b.Start!=firstAuction+300000L).ToArray()})));
Check(missingAuction.RootElement.GetProperty("Forecasts").EnumerateArray().Any(x=>x.GetProperty("At").GetInt64()==firstAuction&&x.GetProperty("Primary").GetBoolean()&&x.GetProperty("OutcomeBps").ValueKind==System.Text.Json.JsonValueKind.Null),
    "missing auction exit information preserves earlier forecast and unknown monetary outcome");
var clockWindow=new ObservationWindow(10000,1000,10000,2000,new[]{"X"},new[]{
    new QuoteSideEvent(11000,"X",0,100),new QuoteSideEvent(11000,"X",1,102),
    new QuoteSideEvent(12000,"X",0,1)},true);
var firstClock=CausalObservationClock.First(clockWindow);
Check(firstClock.At==11000 && firstClock.Quotes[0].Bid==100,"first causal event ignores later favorable price");
Check(CausalObservationClock.First(clockWindow with {Events=clockWindow.Events.Take(2).ToArray()}).At==firstClock.At,
    "observation prefix invariant");
Check(CausalObservationClock.First(clockWindow with {Complete=false}).At==null,"incomplete tick page never usable");
Check(CausalObservationClock.First(clockWindow with {Route=new[]{"X","FX"}}).At==null,"missing conversion route blocks observation");
Check(CausalObservationClock.First(clockWindow with {Events=clockWindow.Events.Append(new QuoteSideEvent(11000,"X",0,99)).ToArray()}).Status=="AMBIGUOUS_SAME_TIME_SIDE",
    "conflicting simultaneous quote makes window unavailable without inventing event order");
var sequenceBars=Enumerable.Range(0,129).Select(i=>new long[]{i*3600000L,(i+1)*3600000L,100000,100002,99998,100000+(i%2==0?1:-1),100}).ToArray();
var sequenceBlock=new SequenceFeatureBlock("SYNTHETIC","X","H1",129*3600000L,sequenceBars);
var sequencePlan=SequenceOpportunityResearch.Describe(new[]{sequenceBlock});
Check(sequencePlan.Length==2 && sequencePlan.All(x=>x.Side==-1 && x.MatureTransitions==127),"ordinal and duration forecasts use mature alternating transitions");
var futureSequenceBar=new long[]{129*3600000L,130*3600000L,100000,999999,99998,999998,100};
Check(sequencePlan.SequenceEqual(SequenceOpportunityResearch.Describe(new[]{sequenceBlock with {Bars=sequenceBars.Append(futureSequenceBar).ToArray()}})),"future bar cannot change prior native sequence forecasts");
Check(SequenceOpportunityResearch.Describe(new[]{sequenceBlock with {Bars=sequenceBars.Take(128).ToArray()}}).Length==0,"incomplete sequence warmup cannot forecast");
var ledgerQuote=new LedgerQuote("SYNTH",2000,10,10.01m,1,1,0,.1m,1);
LedgerEvent Journal(string id,long at,string kind,decimal units=2,decimal price=0,LedgerQuote[]? quotes=null)=>
    new(id,at,kind,"native-position","SYNTH",1,units,price,.1m,1,0,0,0,1000,"SYNTHETIC_TEST_ONLY",new string('a',64),quotes??Array.Empty<LedgerQuote>());
var nativeBook=new NativeFundedLedger();
nativeBook.Apply(Journal("intent",1000,"REQUEST_OPEN"));
nativeBook=NativeFundedLedger.Restore(nativeBook.Checkpoint());
nativeBook.Apply(Journal("fill",2000,"OPEN_FILL",price:10.01m,quotes:new[]{ledgerQuote}));
Check(nativeBook.Summary().OpenPositions==1 && nativeBook.Summary().CashEur==199.9m,"native funded entry charges fee and restores pending intent");
var positionBridge=new NativeFundedSession("TEST_ACCOUNT",nativeBook,new[]{localIdentity with {LedgerPositionId="native-position"}},true);
Check(positionBridge.Observe(brokerIdentity with {Positions=new[]{new BrokerPositionIdentity("position-A","SYNTH",1,2)}},199.9m).PositionInventoryMatchesModel,
    "broker position identities join the actual funded model position, symbol side and remaining units");
Check(!positionBridge.Observe(brokerIdentity with {Positions=new[]{new BrokerPositionIdentity("position-A","SYNTH",1,1)}},199.9m).PositionInventoryMatchesModel,
    "a broker partial close cannot silently retain the model's previous volume");
Check(positionBridge.Observe(brokerIdentity with {At=5000},199.9m).ModelLedger.LiquidationEquityEur is null,
    "a previously fresh model mark cannot become current broker-clock floating equity after an interruption");
var missingMarkBook=NativeFundedLedger.Restore(nativeBook.Checkpoint());missingMarkBook.Apply(Journal("missing-held",4000,"MARK"));
bool missingEntryRejected=false;
try{missingMarkBook.Apply(Journal("unsafe-new",4001,"REQUEST_OPEN") with {PositionId="different-position"});}catch(ArgumentException){missingEntryRejected=true;}
Check(missingMarkBook.Summary().HistoryEvidenceIncomplete && missingEntryRejected,"missing held quote remains unknown and blocks further model entry");

nativeBook.Apply(Journal("close-intent",3000,"REQUEST_CLOSE"));
var closeQuote=ledgerQuote with {At=4000,Bid=11,Ask=11.01m};
nativeBook.Apply(Journal("partial",4000,"CLOSE_FILL",units:1,price:11,quotes:new[]{closeQuote}));
Check(nativeBook.Summary().OpenPositions==1 && nativeBook.Summary().CompleteRoundTrips==0,"native partial exit is not a round trip");
nativeBook=NativeFundedLedger.Restore(nativeBook.Checkpoint());
var finalQuote=closeQuote with {At=5000};var finalFill=Journal("final",5000,"CLOSE_FILL",units:1,price:11,quotes:new[]{finalQuote});
nativeBook.Apply(finalFill);var nativeBefore=nativeBook.Summary();nativeBook.Apply(finalFill);
Check(nativeBook.Summary()==nativeBefore && nativeBefore.CompleteRoundTrips==1 && nativeBefore.CashEur==201.68m,
    "native partial commissions reconcile and duplicate fills are idempotent");
var nativeConflict=false;try{nativeBook.Apply(finalFill with {FeeEur=.2m});}catch(InvalidOperationException){nativeConflict=true;}
Check(nativeConflict,"native conflicting duplicate rejected");
var pendingBook=new NativeFundedLedger();pendingBook.Apply(Journal("request",1000,"REQUEST_OPEN"));
pendingBook.Apply(Journal("cancel",1500,"CONFIRMED_CANCEL"));
Check(pendingBook.Summary().PendingIntents==0 && pendingBook.Summary().CashEur==200,"confirmed cancellation retains cash and leaves no invented fill");
var highMarginBook=new NativeFundedLedger();highMarginBook.Apply(Journal("margin-intent",1000,"REQUEST_OPEN"));
var rejectsHigherCurrentMargin=false;
try{highMarginBook.Apply(Journal("margin-fill",2000,"OPEN_FILL",price:10.01m,quotes:new[]{ledgerQuote with {MarginPerUnit=101}}));}
catch(InvalidOperationException){rejectsHigherCurrentMargin=true;}
Check(rejectsHigherCurrentMargin && highMarginBook.Summary().OpenPositions==0 && highMarginBook.Summary().CashEur==200,
    "new native fill cannot use lower recorded margin when current causal margin is higher");
const long bdpSyntheticStart=1762128000000L;
var bdpSyntheticBars=new List<ProgramBar>();
void AddProgramWindow(long start,int count)
{
    for(int k=0;k<count;k++)
    {
        double price=100000*Math.Pow(1.001,k);
        bdpSyntheticBars.Add(new("SYNTH",start+k*300000L,start+(k+1)*300000L,price/1.001,price*1.0001,price/1.001*.9999,price,100));
    }
}
AddProgramWindow(bdpSyntheticStart,1000);
for(int w=26;w<52;w++)AddProgramWindow(bdpSyntheticStart+w*604800000L,128);
var bdpSyntheticInput=new DiscoveryInput(bdpSyntheticBars.ToArray(),new[]{new ProgramCost("SYNTH",.01,1000,10,true,1320,18)},
    bdpSyntheticStart,bdpSyntheticStart+26*604800000L,bdpSyntheticStart+39*604800000L,bdpSyntheticStart+52*604800000L);
using var bdpFirst=System.Text.Json.JsonDocument.Parse(System.Text.Json.JsonSerializer.Serialize(PortfolioDiscoveryProgram.Evaluate(bdpSyntheticInput)));
foreach(var phase in new[]{("Selection",bdpSyntheticInput.DevelopmentEnd),("Audit",bdpSyntheticInput.SelectionEnd)})
    foreach(var group in bdpFirst.RootElement.GetProperty("Groups").EnumerateArray())
    {
        var stats=group.GetProperty(phase.Item1);var counts=stats.GetProperty("WeeklyOpportunityCounts").EnumerateArray().ToArray();
        Check(counts.Length==13 && counts.Select((week,index)=>week.GetProperty("Week").GetInt64()==phase.Item2+index*604800000L).All(x=>x),
            "every calendar week uses nonoverflowing 64 bit milliseconds");
        Check(counts.Sum(x=>x.GetProperty("Count").GetInt32())==stats.GetProperty("Windows").GetInt32(),
            "all decisions belong to exactly one of the thirteen complete weeks");
    }
var bdpChanged=bdpSyntheticInput with {Bars=bdpSyntheticBars.Select(b=>b.Start<bdpSyntheticInput.SelectionEnd?b:
    b with {Open=1e10/b.Open,High=1e10/b.Low,Low=1e10/b.High,Close=1e10/b.Close}).ToArray()};
using var bdpSecond=System.Text.Json.JsonDocument.Parse(System.Text.Json.JsonSerializer.Serialize(PortfolioDiscoveryProgram.Evaluate(bdpChanged)));
string[] SelectionFacts(System.Text.Json.JsonElement root)=>root.GetProperty("Groups").EnumerateArray().Select(g=>
    g.GetProperty("Id").GetString()+"/"+g.GetProperty("TrainingLabels").GetInt32()+"/"+g.GetProperty("SelectedBeforeAudit").GetBoolean()+"/"+g.GetProperty("Selection").GetRawText()).ToArray();
Check(bdpFirst.RootElement.GetProperty("Groups").EnumerateArray().Any(g=>g.GetProperty("Selection").GetProperty("Windows").GetInt32()>0),
    "context programme causality check exercises actual nonempty forecasts");
Check(SelectionFacts(bdpFirst.RootElement).SequenceEqual(SelectionFacts(bdpSecond.RootElement)),
    "changing later audit prices cannot alter training or prior selection facts");
Check(bdpFirst.RootElement.GetProperty("Groups").EnumerateArray().Any(g=>g.GetProperty("Selection").GetProperty("MissingOutcomeWindows").GetInt32()>0 &&
    g.GetProperty("Selection").GetProperty("ConditionalCostScenarioBpsSum").ValueKind==System.Text.Json.JsonValueKind.Null),
    "missing future label retains its causal signal and never becomes zero net");
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
var safeAccount=new RecoveryPortfolioEvidence(200m,120m,200m,true,true,true,
    5m,30m,0);
var uncertain=new RecoveryLaneEvidence("EURUSD",true,true,false,true,false,
    10m,10m);
var other=new RecoveryLaneEvidence("AUDUSD",true,true,false,false,false,null,null);
var isolation=SelectiveRecovery.Assess(safeAccount,new[]{uncertain,other});
Check(isolation.MonitoringActive && isolation.CanReviewAnyNewExposure &&
    isolation.AvailableWorstCaseDrawdownHeadroomEur==45m &&
    isolation.ReservableFreeMarginEur==110m &&
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
    finalReconciliation.AvailableWorstCaseDrawdownHeadroomEur==55m,
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
var executionTerms=new StopExecutionTerms(1000m,1000m,100000m,.001m,.002m,.0001m,.001m,.0004m,.0002m,
    1m/1.08m,.0001m,0m,.04m,true,true);
var preventive=HistoricalPr16Risk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms);
Check(preventive.Units>=1000m && preventive.StressDrawdown<.30m && !preventive.AbsoluteGuarantee,
    "pre-entry native stop gap slip FX cost and favorable-peak scenario capacity; residual gaps not guaranteed");
Check(HistoricalPr16Risk.Size(141m,200m,141m,Array.Empty<ReservedPositionRisk>(),executionTerms).Units==0,
    "minimum lot blocked BEFORE entry when remaining DD cannot absorb stop plus gap");
var portfolioReserved=new[]{new ReservedPositionRisk("GBP",2m,4m,40m),new ReservedPositionRisk("AUD",2m,4m,20m)};
Check(HistoricalPr16Risk.Size(200m,200m,140m,portfolioReserved,executionTerms).Units>=1000m,
    "correlated risk reserves support multiple positions without historic single-position restriction");
Check(HistoricalPr16Risk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms with {MinimumUnits=100000m,StepUnits=100000m}).Units==0,
    "broker minimum larger than funded risk budget rejected without rounding up");
Check(HistoricalPr16Risk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms with {MinimumBrokerStopDistance=.002m}).Units==0,
    "invalid broker stop rejected before exposure");
Check(HistoricalPr16Risk.Size(200m,200m,200m,Array.Empty<ReservedPositionRisk>(),executionTerms with {ReconciledAccount=false}).Units==0,
    "unknown account inhibits new exposure without changing selective monitor recovery");
Check(HistoricalPr16Risk.Size(200m,200m,20m,new[]{new ReservedPositionRisk("other",1m,0,180m)},executionTerms).Units==0,
    "open portfolio margin and potential loss reserved before minimum lot");

// Material new economic/risk logic: causal forecasts and joint portfolio shocks.
var adaptiveAccount=new AdaptiveRiskInputs(200m,200m,200m,1000m,1000m,10000m,.01m,.5m,true,true,8,2m);
var optimistic=Enumerable.Range(0,8).Select(i=>new JointRiskScenario(0,.001m,0,0,.002m,0,0,true)).ToArray();
var adaptive=AdaptivePortfolioRisk.Choose(adaptiveAccount,optimistic);
Check(adaptive.Units>0 && adaptive.WorstScenarioDrawdown<.30m,"adaptive funded positive utility chooses broker steps");
Check(adaptive.Units%1000m==0,"adaptive volume respects broker step");
Check(AdaptivePortfolioRisk.Choose(adaptiveAccount,optimistic.Select(x=>x with {ProposedNetPerUnitEur=-.001m})).Units==0,"negative net scenarios suspend exposure");
Check(AdaptivePortfolioRisk.Choose(adaptiveAccount,optimistic.Append(new JointRiskScenario(-10,-.1m,0,10,.1m,0,0,false))).Units==0,"unweighted tail stress blocks despite positive estimation sample");
Check(AdaptivePortfolioRisk.Choose(adaptiveAccount,optimistic.Select(x=>x with {IntrahorizonOpenLossEur=59m})).Units==0,"existing correlated portfolio risk consumes capacity");
Check(AdaptivePortfolioRisk.Choose(adaptiveAccount with {FreeMarginEur=5m},optimistic).Units==0,"broker minimum cannot be fractionally invented");
Check(AdaptivePortfolioRisk.Choose(adaptiveAccount with {CompleteJointRiskEvidence=false},optimistic).Units==0,"unknown joint risk stops only new exposure");
Check(AdaptivePortfolioRisk.Choose(adaptiveAccount,optimistic.Select((x,i)=>x with {ProposedNetPerUnitEur=i%2==0?.003m:-.002m})).Units==0,"uncertain mean not enough for new exposure");
Check(AdaptivePortfolioRisk.Choose(adaptiveAccount,optimistic.Select(x=>x with {ProposedFavorablePeakPerUnitEur=.2m})).Units==0,
    "favorable portfolio peak scales with candidate volume and consumes subsequent drawdown capacity");
Check(PortfolioRiskBudget.Assess(new BrokerRiskSnapshot(200m,200m,200m,true,true,true,true),Array.Empty<OpenRiskExposure>(),new ProposedRiskExposure("adaptive",5m,1m,30m)).Admissible,
    "withdrawn aggregate1 percent does not survive in portfolio observation capacity");
var anchor=DateTimeOffset.Parse("2025-01-01T00:00:00Z").ToUnixTimeMilliseconds();
var researchBars=Enumerable.Range(0,1000).Select(i=>{
    double o=100000+10*i+20*Math.Sin(i*.4),c=o+10;
    return new RegimeDiscovery.Bar("TEST","H4",anchor+i*14400000L,anchor+(i+1)*14400000L,o,c+5,o-5,c,100+i%10);
}).ToArray();
var featurePoints=RegimeDiscovery.Features(researchBars,new Dictionary<string,RegimeDiscovery.Bar[]>{{"TEST",researchBars}},4);
Check(featurePoints.All(p=>p.Exit>p.Entry),"research labels follow prediction clock");
var originalWalk=RegimeDiscovery.Walk(featurePoints);
var modifiedPoints=featurePoints.Select((p,i)=>i>=featurePoints.Length*8/10?p with {Y=p.Y+10000,X=p.X.Select(v=>v+50).ToArray()}:p).ToArray();
Check(System.Text.Json.JsonSerializer.Serialize(originalWalk)==System.Text.Json.JsonSerializer.Serialize(RegimeDiscovery.Walk(modifiedPoints)),"withheld late outcomes and features cannot affect walk results");
var noLookahead=RegimeDiscovery.Features(researchBars.Take(500).ToArray(),new Dictionary<string,RegimeDiscovery.Bar[]>{{"TEST",researchBars}},4);
Check(noLookahead.Zip(featurePoints.Take(noLookahead.Length)).All(p=>p.First.X.SequenceEqual(p.Second.X)),"future source cannot alter historical features");
var incomplete=RegimeDiscovery.Aggregate(researchBars.Where((b,i)=>i!=2),"D1",86400000);
Check(incomplete.All(b=>b.T!=anchor),"incomplete higher timeframe never fabricated");
// Joint allocation economic invariants, not economic performance evidence.
var jointClock=100L;
var jointBase=Enumerable.Range(0,8).Select(i=>new PortfolioScenario($"s{i}",1,true,0,0,0,0)).ToArray();
EconomicOpportunity Opp(string id,string symbol,string key,decimal gain) => new(id,id,symbol,key,1,100,90,
    EvidenceLevel.Exploratory,true,adaptiveAccount with {MaximumUnits=1000},
    Enumerable.Range(0,8).Select(i=>new OpportunityScenario($"s{i}",50,true,gain,0,.002m,0)).ToArray());
var jo=Opp("A","EURUSD","same",.001m);var jb=Opp("B","GBPUSD","other",.001m);
var multi=OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{jo,jb});
Check(multi.Allocations.Length==2 && multi.ReservedMarginEur==20 && !multi.Qualified,
    "native joint selector admits financed simultaneous research allocations without component HARD21");
Check(OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{jo,jo with {Id="duplicate"}}).Allocations.Length==1,
    "redundant opportunity is not independently funded");
Check(OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{jo,jb with {Symbol="EURUSD",Direction=-1}}).Allocations.Length==1,
    "contradictory same symbol exposure withheld");
Check(OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{jo with {ExecutionEvidenceComplete=false}}).Allocations.Length==0,
    "gross source descriptor cannot acquire invented execution evidence");
Check(OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{jo with {CalibratedThrough=101}}).Allocations.Length==0,
    "future calibration cannot rank current opportunities");
Check(Rejects(()=>OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{jo with {
    Scenarios=jo.Scenarios.Select(x=>x with {KnownAt=101}).ToArray()}})),"future outcome cannot enter joint estimate");
var tight=OpportunityOrchestrator.Select(jointClock,adaptiveAccount with {FreeMarginEur=15},jointBase,new[]{jo,jb});
Check(tight.Allocations.Length==1 && tight.ReservedMarginEur==10,"shared capital reserved before ranking remaining opportunities");
Check(OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{jo with {
    Scenarios=jo.Scenarios.Select(x=>x with {LossPerUnitEur=.04m}).ToArray()},jb with {
    Scenarios=jb.Scenarios.Select(x=>x with {LossPerUnitEur=.04m}).ToArray()}}).Allocations.Length==1,
    "joint correlated stress prevents independently feasible allocations exceeding common drawdown capacity");
var descriptors=JointOpportunityResearch.Describe(researchBars);
var futureMutated=researchBars.Select((x,i)=>i>=900?x with {C=x.C*2}:x).ToArray();
Check(System.Text.Json.JsonSerializer.Serialize(descriptors)==System.Text.Json.JsonSerializer.Serialize(JointOpportunityResearch.Describe(futureMutated)),
    "unscored late source cannot influence joint research descriptors");
// Conditional research cannot manufacture evidence for the verified pathway.
var unverifiedJo=jo with {ExecutionEvidenceComplete=false,VolumeGrid=jo.VolumeGrid with {
    CertifiedPeakEur=0,Reconciled=false,CompleteJointRiskEvidence=false}};
var estimatedRequest=new ResearchOrchestrationRequest("EPA1_CONDITIONAL_RESEARCH_NOT_CERTIFIED",240,jointClock,
    AdaptivePortfolioRisk.ToScenario(adaptiveAccount),jointBase,new[]{unverifiedJo},true,new[]{unverifiedJo.Id});
Check(OpportunityOrchestrator.Estimate(estimatedRequest).Allocations.Length==1,
    "explicit conditional estimate uses numeric scenario grid without a fabricated peak certificate");
Check(OpportunityOrchestrator.Select(jointClock,adaptiveAccount,jointBase,new[]{unverifiedJo}).Allocations.Length==0,
    "same unverified opportunity remains blocked on verified endpoint");
Check(!OpportunityOrchestrator.Estimate(estimatedRequest).Qualified,
    "conditional positive estimates never qualify portfolio trading");
Check(Rejects(()=>OpportunityOrchestrator.Estimate(estimatedRequest with {Scope="TRADING"})),
    "conditional endpoint requires explicit research scope");
Check(Rejects(()=>OpportunityOrchestrator.Estimate(estimatedRequest with {CommonHorizonMinutes=15})),
    "EPA1 cannot compare different economic holding horizons");
Check(OpportunityOrchestrator.Estimate(estimatedRequest with {LedgerReconciled=false}).Allocations.Length==0,
    "conditional research still refuses unreconciled capital");
Console.WriteLine($"PASS {passed} recovery/accounting/portfolio/causal-H1/dynamic-risk/source-calendar/causal-score checks; synthetic, no economic qualification.");

