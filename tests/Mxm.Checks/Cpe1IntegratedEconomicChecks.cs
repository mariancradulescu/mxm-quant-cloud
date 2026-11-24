using System;
using System.Linq;
using Mxm.Core;

// CPE1 synthetic-only INTEGRATION checks, not another economic backtest.
// Directly invokes the same NativeUnifiedPortfolioEngine.Advance as the
// cTrader observation-only Cloud adapter and the genuine source-only Replay.
internal static class Cpe1IntegratedEconomicChecks
{
    const long M5=300000L,M15=900000L;
    static NativeClosedMarketBar B(long at,long w,decimal close)
        =>new(at,at+w,close,close+.02m,close-.02m,close,5);
    internal static Ucp1Frame Frame(long origin,long t,decimal bid,bool unknownSwap)
    {
        var c=new NativeObservedContractTerms("EURUSD","USD",origin-1000,
            1m,1m,2m,100m,2,0,2,0,null,0,0,0m,0m,4,
            24,1320,3,unknownSwap?(bool?)null:false,
            unknownSwap?(int?)null:0,true,false);
        decimal[] samples={100m,100.1m,100.2m,100.3m,100.9m};
        // Advance each synthetic source bar as its clock closes, never
        // reuse frozen historical context at an unrelated future mark.
        long next5=Math.Max(0L,(t-(origin+M5))/M5)*M5;
        long next15=Math.Max(0L,(t-(origin+M5))/M15)*M15;
        var bars=samples.Select((v,i)=>new NativeClosedMarketBar(
            origin-(5-i)*M5+next5,origin-(4-i)*M5+next5,
            v,v+.02m,v-.02m,v,100)).ToArray();
        var f15=new decimal[]{99.5m,100m,100.6m}.Select((v,i)=>
            new NativeClosedMarketBar(origin-(3-i)*M15+next15,
                origin-(2-i)*M15+next15,v,v+.03m,v-.03m,v,100)).ToArray();
        var q=new LedgerQuote("EURUSD",t,bid,bid+.01m,
            1m,1m,.001m,.0001m,1m);
        return new Ucp1Frame(t,new[]{new Ucp1MarketFrame("EURUSD",q,c,
            bars,f15,.01m,"SYNTHETIC_PRE-CLOSE_SOURCE_ONLY")});
    }
    static NativeUnifiedPortfolioEngine Cycle(long origin,
        bool unknownSwap,Action<bool,string> check)
    {
        var e=new NativeUnifiedPortfolioEngine("CPE1_ECONOMIC");
        long openSignal=origin+M5;
        e.Advance(Frame(origin,openSignal,100.95m,unknownSwap));
        check(e.ModelSummary.PendingIntents==1&&e.ModelSummary.OpenPositions==0,
            "CPE1 common capital causal EUR risk/reward requests a real pending OPEN");
        e.Advance(Frame(origin,openSignal+M5,100.95m,unknownSwap));
        check(e.ModelSummary.PendingIntents==0&&e.ModelSummary.OpenPositions==1,
            "CPE1 next observed M5 fill passed native projected post-fill Held+Pending guard");
        e.Advance(Frame(origin,openSignal+2*M5,100.11m,unknownSwap));
        check(e.ModelSummary.PendingIntents==1&&e.ModelSummary.OpenPositions==1,
            "CPE1 protective REQUEST_CLOSE does not prematurely release Held exposure");
        e.Advance(Frame(origin,openSignal+3*M5,100.10m,unknownSwap));
        check(e.ModelSummary.PendingIntents==0&&e.ModelSummary.OpenPositions==0&&
            e.CompleteModelTrips.Length==1,
            "CPE1 protective close filled only at LATER authentic source clock");
        var trip=e.CompleteModelTrips.Single();
        check(trip.EconomicEvidence is {
            CompletePair:true,ExpectedLegs:1,ClosedLegs:1} &&
            trip.EconomicEvidence.ReservedRiskEur>0m &&
            trip.EconomicEvidence.ProjectedRewardEur>0m,
            "CPE1 one real funded episode contains projected EUR reward and loss before fill");
        return e;
    }
    internal static Ucp1MarketFrame Named(Ucp1MarketFrame market,string symbol,decimal? margin=null)
        =>market with {Symbol=symbol,Contract=market.Contract with {Symbol=symbol},
            Quote=market.Quote with {Symbol=symbol,MarginPerUnit=margin??market.Quote.MarginPerUnit}};

    static void SharedCapital(long origin,Action<bool,string> check,bool rejectSecondFill)
    {
        var e=new NativeUnifiedPortfolioEngine("CPE1_ECONOMIC");
        var at=origin+M5;
        e.Advance(Frame(origin,at,100.95m,false));
        var second=Frame(origin,at+M5,100.95m,false);
        e.Advance(second with {Markets=new[]{second.Markets[0],Named(second.Markets[0],"GBPUSD")}});
        check(e.ModelSummary.OpenPositions==1&&e.ModelSummary.PendingIntents==1,
            "CPE1 shared EUR300 holds EURUSD and reserves concurrent GBPUSD OPEN");
        var third=Frame(origin,at+2*M5,100.95m,false);
        e.Advance(third with {Markets=new[]{third.Markets[0],
            Named(third.Markets[0],"GBPUSD",rejectSecondFill?250m:null)}});
        check(e.ModelSummary.OpenPositions==(rejectSecondFill?1:2)&&e.ModelSummary.PendingIntents==0,
            rejectSecondFill?"CPE1 repriced GBPUSD fill rejected against shared Held+Pending equity":
            "CPE1 EURUSD and GBPUSD concurrently funded by one ledger");
    }

    public static void Run(Action<bool,string> check)
    {
        long baseAt=new DateTimeOffset(2026,11,23,14,0,0,
            TimeSpan.Zero).ToUnixTimeMilliseconds();
        var normal=Cycle(baseAt,false,check);
        var settled=normal.CompleteModelTrips.Single();
        check(!settled.CrossedUnknownHistory &&
            settled.EconomicEvidence is {MarkCoverageComplete:true},
            "CPE1 continuous M5 evidence is not falsely censored by absent legacy path");
        check(settled.EconomicEntry is {AdmissionReservedRiskEur:>0m,AdmissionProjectedRewardEur:>0m} &&
            settled.EconomicEntry.ReservedRiskEur==settled.EntryRiskEur &&
            settled.EconomicEvidence!.ReservedRiskEur==settled.EntryRiskEur,
            "CPE1 admission geometry preserved and R uses revalidated fill risk");
        SharedCapital(baseAt,check,false);
        SharedCapital(baseAt,check,true);
        var replay=new NativeUnifiedPortfolioEngine("CPE1_ECONOMIC");
        var adapter=new Mxm.Cloud.NativeUnifiedCloudParityAdapter("CPE1_ECONOMIC");
        var clock=baseAt+M5;
        foreach(var sample in new[]{100.95m,100.95m,100.11m,100.10m})
        {
            var frame=Frame(baseAt,clock,sample,false);
            check(replay.Advance(frame)==adapter.Observe(frame) &&
                replay.ModelSummary==adapter.ModelBook,
                "CPE1 exact identical frame Core/Cloud observation parity (no Cloud runtime)");
            clock+=M5;
        }
        check(normal.CompleteModelTrips.Single().EconomicEvidence!.ConditionalNetKnown,
            "CPE1 same-day known original swap schedule and finance produce conditional net");
        var cash=new NativeUnifiedPortfolioEngine("CPE1_CASH");
        cash.Advance(Frame(baseAt,baseAt+M5,100.95m,false));
        check(cash.ModelSummary.OpenPositions==0&&cash.ModelSummary.PendingIntents==0,
            "CPE1 CASH WAIT uses same source clock and never invents funded opportunities");
        long beforeSwap=new DateTimeOffset(2026,11,23,21,45,0,
            TimeSpan.Zero).ToUnixTimeMilliseconds();
        var unknown=Cycle(beforeSwap,true,check);
        check(unknown.CompleteModelTrips.Single().EconomicEvidence is {
            CompletePair:true,ConditionalNetKnown:false,RealizedNetR:null} &&
            unknown.ModelSummary.OpenPositions==0,
            "CPE1 protective exit permitted through genuine new price despite unverified swap; no invented NET/R");
        var restored=NativeUnifiedPortfolioEngine.Restore(normal.Checkpoint());
        check(restored.ModelSummary==normal.ModelSummary &&
            restored.CompleteModelTrips.Single().EconomicEvidence==
            normal.CompleteModelTrips.Single().EconomicEvidence,
            "CPE1 existing session/checkpoint restores EUR episode evidence and capital");
    }
}
