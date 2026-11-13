using System;
using System.Linq;
using Mxm.Core;

public static class NativeNxe1MandatoryAdmissionChecks
{
    public static void Run(Action<bool,string> check)
    {
        long at=DateTimeOffset.Parse("2026-11-13T15:00:01.500Z")
            .ToUnixTimeMilliseconds();
        long anchor=at-1500L;
        NativeClosedMarketBar[] Bars(string symbol)
        {
            decimal basePrice=symbol=="US30"?30000m:
                symbol=="US500"?5000m:1.1m;
            decimal delta=symbol=="US30"?-1m:
                symbol=="US500"?1m:.00001m;
            return Enumerable.Range(0,99).Select(i=>{
                long start=anchor-(99-i)*300000L;
                decimal price=basePrice+delta*i;
                decimal span=Math.Abs(delta)*2m;
                return new NativeClosedMarketBar(start,start+300000L,
                    price,price+span,price-span,price,
                    symbol=="US30"&&i>=96?20:150);
            }).ToArray();
        }
        NativeObservedContractTerms Contract(string symbol)=>
            new(symbol,"USD",at-60000L,1,1,1,1,2,5000000,
                1,0,"USD",10,0,-.05m,-.08m,2,24,1320,3,
                false,0,true,false);
        (LedgerQuote Quote,NativeObservedContractTerms Contract) Quote(string symbol)
        {
            decimal bid=symbol=="US30"?29902m:symbol=="US500"?5098m:1.10099m;
            decimal spread=symbol=="EURUSD"?.0001m:1m;
            var c=Contract(symbol);
            var context=new NativeMarketCostContext(at,bid,bid+spread,
                .95m,1.01m,.98m,null,40m,1m,
                symbol=="EURUSD"?.00001m:.2m);
            return (NativeBrokerContractCosts.Quote(c,context).Quote,c);
        }
        NativeProductMarket Frame(string symbol,NativeProspectiveSessionRiskEvidence? proof=null)
        {
            var x=Quote(symbol);var m5=Bars(symbol);
            return new NativeProductMarket(symbol,m5,
                NativeHistoricalProductReplay.AggregateCompletedM15(m5),
                x.Quote,x.Contract,.00001m,180,
                ExitPolicy:NativeCausalExitResearch.Chandelier,
                SessionAdmissionEvidence:proof);
        }
        var loop=new NativeProductResearchLoop("NXE1_JOINT",
            requireProspectiveExitFeasibility:false);
        var markets=new[]{Frame("US500"),Frame("EURUSD"),Frame("US30")};
        var first=loop.Advance(at,markets,true);
        check(first.AcceptedModelIntents==0 && first.ModelPendingIntents==0 &&
            first.LatestSignals.Any(x=>x.Symbol=="US30"&&
               x.DecisionReason=="SESSION_EVIDENCE_MISSING"),
            "NXE1 loop cannot bypass prospective session gate with false flag");
        var tape=new NativeHistoricalMarketTape("SYNTHETIC_NXE1_NON_BROKER",
            new[]{"US500","EURUSD","US30"}.Select(s=>new NativeHistoricalBars(s,Bars(s))).ToArray(),
            markets.Select(m=>new NativeHistoricalQuoteObservation(at,m.Quote,m.Contract,
                m.SlippagePerSideQuote,180,NativeCausalExitResearch.Chandelier)).ToArray());
        var result=NativeHistoricalProductReplay.Evaluate(tape,true,"NXE1_JOINT");
        check(result.ModelIntentCount==0 && result.CompletedModelRoundTrips==0 &&
            result.RejectionReasons?.ContainsKey("SESSION_EVIDENCE_MISSING")==true,
            "NativeHistoricalProductReplay.Evaluate activates full gate without optional caller flag");
        var intervals=new[]{new NativeWeeklyTradingInterval(0,604800)};
        var oldTerms=new NativeProspectiveSessionRiskEvidence("UTC",intervals,
            at+1000,at,180,1000,true,true,300m,300m,300m,40m,50m) {
            QuoteConversionRouteCovered=true,
            MonitoringCalendarCoveredThroughMs=at+181L*60000L
        };
        var second=new NativeProductResearchLoop("NXE1_NEW");
        var refusal=second.Advance(at,new[]{Frame("US500"),
            Frame("EURUSD"),Frame("US30",oldTerms)},true);
        check(refusal.AcceptedModelIntents==0 &&
            refusal.LatestSignals.Any(x=>x.Symbol=="US30"&&
               x.DecisionReason=="SESSION_EVIDENCE_NOT_CAUSALLY_BOUND"),
            "future-known broker schedule cannot backdate original-account historical admission");
        var third=new NativeProductResearchLoop("NXE1_NEW");
        var safe=third.Advance(at,new[]{Frame("US500"),
            Frame("EURUSD"),Frame("US30",oldTerms with {
                ScheduleKnownAtMs=at-1000
            })},false);
        check(safe.LatestSignals.Any(x=>x.Symbol=="US30") &&
            safe.LatestSignals.All(x=>x.DecisionReason!="SESSION_EVIDENCE_MISSING"),
            "future-profile C# admission uses full evidence when causally supplied");
    }
}
