using System;
using System.Linq;
using System.Text.Json;
using Mxm.Core;
using Mxm.Cloud;

// UCP1 tests the ACTUAL one-Core product handler vs Replay under identical
// observations. These checks are synthetic software contract checks, NOT
// original economic performance; that is separately generated once on OEI1.
internal static class Ucp1UnifiedProductChecks
{
    public static void Run(Action<bool,string> check)
    {
        long baseAt=new DateTimeOffset(2026,11,19,14,0,0,
            TimeSpan.Zero).ToUnixTimeMilliseconds();
        NativeObservedContractTerms Term(string name)=>new(name,"USD",baseAt-1000,
            1m,1m,2m,100m,2,0,2,0,null,0,0,0m,0m,4,
            24,1320,3,false,0,true,false);
        LedgerQuote Q(string name,long at,decimal mid)=>new(name,at,
            mid,mid+.01m,1m,1m,.001m,.0001m,1m);
        NativeClosedMarketBar[] Bars5()
        {
            decimal[] v={100m,100.1m,100.2m,100.3m,100.9m};
            return v.Select((x,i)=>new NativeClosedMarketBar(
                baseAt-(5-i)*300000L,baseAt-(4-i)*300000L,
                x,x+.02m,x-.02m,x,5)).ToArray();
        }
        NativeClosedMarketBar[] Bars15()
        {
            decimal[] v={99.5m,100m,100.6m};
            return v.Select((x,i)=>new NativeClosedMarketBar(
                baseAt-(3-i)*900000L,baseAt-(2-i)*900000L,
                x,x+.03m,x-.03m,x,15)).ToArray();
        }
        Ucp1MarketFrame M(long at,string name="SYNTH")=>new(name,
            Q(name,at,100.95m),Term(name),Bars5(),Bars15(),
            .01m,"SYNTHETIC_PARITY_TEST_ONLY");
        check(Ucp1CausalSignals.Describe(M(baseAt+60000L),baseAt+60000L)
                .Any(s=>s.Family=="RANGE_TRANSITION" && s.Side==1),
            "UCP1 causal completed M5 breakout and aligned M15 regime signal");
        check(Ucp1CausalSignals.Describe(M(baseAt+60000L) with {
            M5=Bars5().Select((v,i)=>i==3?v with {CloseAt=v.CloseAt+1000}:v)
                .ToArray()},baseAt+60000L).Length==0,
            "UCP1 rejects inconsistent completed M5 history, never fills future gaps");

        var replay=new NativeUnifiedPortfolioEngine("JOINT","SYNTH_BROKER_ID");
        var cloud=new NativeUnifiedCloudParityAdapter("JOINT","SYNTH_BROKER_ID");
        var snap=new BrokerIdentitySnapshot("SYNTH_BROKER_ID",
            baseAt+60000L,baseAt-60000L,baseAt+60000L,true,false,false,
            Array.Empty<BrokerOrderIdentity>(),Array.Empty<BrokerDealIdentity>(),
            Array.Empty<BrokerPositionIdentity>());
        var snapshots=new long[]{baseAt+60000L,baseAt+120000L,
            baseAt+180000L,baseAt+420000L,baseAt+86400000L};
        foreach(var at in snapshots)
        {
            Ucp1MarketFrame[] observations=at==snapshots[3]?
                Array.Empty<Ucp1MarketFrame>():new[]{M(at)};
            var input=new Ucp1Frame(at,observations,new Ucp1BrokerFrame(
                snap with {At=at,HistoryThrough=at},300m,"Netted"));
            var a=replay.Advance(input);
            var b=cloud.Observe(input);
            check(JsonSerializer.Serialize(a)==JsonSerializer.Serialize(b) &&
                  a.ModelBook==b.ModelBook &&
                  a.ModelEventChain==b.ModelEventChain &&
                  !a.OrdersSubmitted && !b.OrdersSubmitted,
                "UCP1 same-input complete model decisions/ledger/rejections identical Replay→Cloud");
            check(replay.OriginalModelEvents.Length==cloud.ModelFacts.Length &&
                  JsonSerializer.Serialize(replay.OriginalModelEvents)==
                  JsonSerializer.Serialize(cloud.ModelFacts),
                "UCP1 all exact native model event receipts identical in Cloud and Replay");
        }
        var restored=NativeUnifiedPortfolioEngine.Restore(replay.Checkpoint());
        var cloudCopy=new NativeUnifiedCloudParityAdapter("JOINT","SYNTH_BROKER_ID");
        cloudCopy.Restore(cloud.Checkpoint());
        long fresh=snapshots[^1]+60000L;
        var next=new Ucp1Frame(fresh,new[]{M(fresh)},new Ucp1BrokerFrame(
            snap with {At=fresh,HistoryThrough=fresh},300m,"Hedged"));
        var afterReplay=restored.Advance(next);
        var afterCloud=cloudCopy.Observe(next);
        check(JsonSerializer.Serialize(afterReplay)==JsonSerializer.Serialize(afterCloud) &&
              JsonSerializer.Serialize(restored.OriginalModelEvents)==
              JsonSerializer.Serialize(cloudCopy.ModelFacts),
            "UCP1 full Core ledger/intents/trading state restore and same event replay parity");
        check(afterReplay.BrokerStatus.Contains("BROKER_Hedged") &&
              !afterReplay.OrdersSubmitted &&
              afterReplay.ModelBook.CashEur<=300m,
            "UCP1 official cTrader account type observed, broker status never becomes synthetic fill");
        var oneHeldOneClosing=new LedgerSummary(299m,299m,1m,298m,
            300m,0m,1,1,0,0m,false,new string('0',64));
        var closingIntent=new LedgerEvent("UCP1_SYNTH_CLOSE",fresh,
            "REQUEST_CLOSE","held-A","SYNTH",1,1m,0m,0m,
            0m,0m,fresh-1,fresh-2,100,
            "MODEL_UNTRANSMITTED_SYNTHETIC","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            Array.Empty<LedgerQuote>());
        check(NativeUnifiedPortfolioEngine.ModelSlotsPermitAdmission(
                oneHeldOneClosing,new[]{closingIntent}) &&
              !NativeUnifiedPortfolioEngine.ModelSlotsPermitAdmission(
                oneHeldOneClosing,new[]{closingIntent with {Kind="REQUEST_OPEN"}}),
            "UCP1 a modeled pending CLOSE does not double count already reserved held capacity, while new OPEN does");
        bool wrongBrokerProtected=false;
        var mismatch=new Ucp1Frame(fresh+60000L,new[]{M(fresh+60000L)},
            new Ucp1BrokerFrame(snap with {At=fresh+60000L,
                AccountBinding="WRONG_BROKER"},300m,"Netted"));
        var mismatchResult=restored.Advance(mismatch);
        wrongBrokerProtected=mismatchResult.BrokerStatus==
            "BROKER_ACCOUNT_BINDING_MISMATCH_PROTECTIVE";
        check(wrongBrokerProtected && !mismatchResult.OrdersSubmitted,
            "UCP1 broker account identity cannot be aliased to model EUR300");
    }
}
