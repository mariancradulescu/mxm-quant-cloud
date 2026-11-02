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
Console.WriteLine($"PASS {passed} recovery/accounting checks; synthetic, no economic qualification.");
