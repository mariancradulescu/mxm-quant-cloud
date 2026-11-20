using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Mxm.Core;
using Mxm.Cloud;

// Synthetic finance/clock/Cloud contracts; NEVER actual price history,
// broker orders or evidence of positive economic performance.
internal static class Fcp1FundedComparatorChecks
{
    public static void Run(Action<bool,string> check)
    {
        long t=new DateTimeOffset(2026,11,19,12,1,0,
            TimeSpan.Zero).ToUnixTimeMilliseconds();
        var m5=Enumerable.Range(0,5).Select(i=>{
            long open=t-60000L-(5-i)*300000L;
            decimal price=100m+i*.1m;
            decimal close=i==4?101m:price+.05m;
            return new NativeClosedMarketBar(open,open+300000L,
                price,close+.08m,price-.08m,close,12+i);
        }).ToArray();
        var m15=Enumerable.Range(0,3).Select(i=>{
            long open=t-60000L-(3-i)*900000L;
            decimal price=99m+i*.25m;
            return new NativeClosedMarketBar(open,open+900000L,
                price,price+.45m,price-.2m,price+.2m,30+i);
        }).ToArray();
        var cells=new Dictionary<string,Scp1Bucket>(StringComparer.Ordinal);
        foreach(var regime in new[]{"FOLLOW","AGAINST"})
        foreach(var vol in new[]{"HIGH","LOW"})
        {
            cells["RANGE_TRANSITION/1/"+regime+"/"+vol]=
                new Scp1Bucket(40,35,25m,-3m,35m);
            cells["EQUILIBRIUM_REPAIR/1/"+regime+"/"+vol]=
                new Scp1Bucket(40,5,3m,-25m,35m);
        }
        var model=new Scp1ScoreModel(NativeScp1EconomicScorer.Version,
            "NO_SCORE",t-86400000L,t-43200000L,
            new string('a',64),240,0,.55d,.75d,-.70d,.90d,
            cells,new double[12],80,.24d,.25d,.26d,true,6);
        var contract=new NativeObservedContractTerms("BBB","USD",t-1000,
            1m,1m,100m,100m,2,0,2,0,null,0,0,0m,0m,
            4,24,1320,3,false,0,true,false);
        Ucp1MarketFrame Market(string symbol,decimal margin)=>
            new(symbol,new LedgerQuote(symbol,t,100.95m,101.05m,
                1m,1m,.00001m,0m,margin),
                contract with {Symbol=symbol},m5,m15,.01m,"SYNTH_ONLY");
        var aaa=Market("AAA",500m);var bbb=Market("BBB",2m);
        var sa=new Ucp1DecisionSignal("AAA","RANGE_TRANSITION",1,
            .30m,100m,.45m,t-60000L);
        var sb=sa with {Symbol="BBB"};
        var book=new NativeFundedLedger().Summary(t);
        var offers=new[]{new Fcp1Offer(sa,aaa),new Fcp1Offer(sb,bbb)};
        var first=NativeFcp1FinancedSelection.Choose("FCP1_FIRST",t,
            model,offers,book,Array.Empty<LedgerPosition>(),
            Array.Empty<LedgerEvent>(),0m,0m,new[]{aaa,bbb});
        check(first.Selected?.Signal.Symbol=="BBB" &&
            first.Examined.Length==2 &&
            first.Examined[0].Reason=="FCP1_MINIMUM_NOT_FINANCEABLE_COMMON_EUR300" &&
            first.Selected.Units>=contract.MinimumUnits,
            "FCP1 FIRST checks every candidate for real finance BEFORE picking first, without utility veto");
        var negativeModel=model with {Method="NO_SCORE",GlobalPrior=.01d,
            GlobalMeanWinR=.01d,GlobalMeanLossR=-3d};
        var noAlpha=NativeFcp1FinancedSelection.Choose("FCP1_FIRST",t,
            negativeModel,offers,book,Array.Empty<LedgerPosition>(),
            Array.Empty<LedgerEvent>(),0m,0m,new[]{aaa,bbb});
        check(noAlpha.Selected?.Signal.Symbol=="BBB",
            "FCP1 simple benchmark never requires trained positive marginal utility");

        var repair=sa with {Symbol="BBB",Family="EQUILIBRIUM_REPAIR"};
        var scoredOffers=new[]{new Fcp1Offer(repair,bbb),
            new Fcp1Offer(sa with {Symbol="CCC"},Market("CCC",2m))};
        var scored=NativeFcp1FinancedSelection.Choose("FCP1_SCORE",t,model,
            scoredOffers,book,Array.Empty<LedgerPosition>(),
            Array.Empty<LedgerEvent>(),0m,0m,
            scoredOffers.Select(x=>x.Market).ToArray());
        check(scored.Examined.Length==2 &&
            scored.Selected?.Signal.Symbol=="CCC" &&
            scored.Selected.FavorableProbability>
                scored.Examined.Single(x=>x.Signal.Symbol=="BBB").FavorableProbability,
            "FCP1 Bayesian score ranking is predecision and differs from FIRST order without selecting hindsight winners");
        var guarded=NativeFcp1FinancedSelection.Choose("FCP1_FIRST",t,
            model,offers,book with {MaximumSampledDrawdown=.30m},
            Array.Empty<LedgerPosition>(),Array.Empty<LedgerEvent>(),
            0m,0m,new[]{aaa,bbb});
        check(guarded.Selected is null,
            "FCP1 common drawdown gate rejects finance even for the simple comparator");
        var threeHeld=new[]{"P1","P2","P3"}.Select((id,i)=>
            new LedgerPosition(id,"HELD"+i,1,1m,100m,t-100000L,
                0m,10m,.01m,null,0m)).ToArray();
        var multiple=NativeFcp1FinancedSelection.Choose("FCP1_FIRST",t,
            model,new[]{new Fcp1Offer(sb,bbb)},
            book with {LiquidationEquityEur=260m,FreeMarginEur=190m,
                UsedMarginEur=70m,OpenPositions=3},
            threeHeld,Array.Empty<LedgerEvent>(),10m,0m,new[]{bbb});
        check(multiple.Selected is not null,
            "FCP1 permits a fourth financed symbol when aggregate capital and risk support it, no two-slot ceiling");

        // End-to-end shared Core selection, later quote modeled fill and
        // observation-only Cloud parity. NO broker orders.
        var native=new NativeUnifiedPortfolioEngine("FCP1_FIRST","SYNTH_BROKER",model);
        var cloud=new NativeUnifiedCloudParityAdapter("FCP1_FIRST","SYNTH_BROKER",model);
        var frame=new Ucp1Frame(t,new[]{aaa,bbb});
        var n1=native.Advance(frame);var c1=cloud.Observe(frame);
        check(n1.Admitted==1&&n1.ModelBook.PendingIntents==1 &&
            n1.ModelBook.OpenPositions==0 &&
            JsonSerializer.Serialize(n1)==JsonSerializer.Serialize(c1),
            "FCP1 FIRST routes later-funded model open intent through identical Replay / Cloud native Core");
        var later=new Ucp1Frame(t+60000L,new[]{
            aaa with {Quote=aaa.Quote with {At=t+60000L}},
            bbb with {Quote=bbb.Quote with {At=t+60000L}}});
        var n2=native.Advance(later);var c2=cloud.Observe(later);
        check(n2.OpenFills==1&&n2.ModelBook.OpenPositions==1 &&
            JsonSerializer.Serialize(n2)==JsonSerializer.Serialize(c2) &&
            JsonSerializer.Serialize(native.OriginalModelEvents)==
                JsonSerializer.Serialize(cloud.ModelFacts) &&
            native.CompleteModelTrips.Length==0 &&
            !n2.OrdersSubmitted&&!n2.CloudActivated,
            "FCP1 only a later quote permits conditional model fill; same event chain, no orders or Cloud activation");
        var restored=NativeUnifiedPortfolioEngine.Restore(native.Checkpoint());
        check(restored.Checkpoint()==native.Checkpoint(),
            "FCP1 model position and scoring snapshot survive deterministic checkpoint restore");
    }
}
