using System;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using Mxm.Core;
using Mxm.Cloud;

// Synthetic **contract checks only**. Original authenticated economic
// forecast/ranking results are generated separately on owner-once custody.
internal static class Scp1EconomicScoringChecks
{
    public static void Run(Action<bool,string> check)
    {
        long at=new DateTimeOffset(2026,11,19,12,1,0,
            TimeSpan.Zero).ToUnixTimeMilliseconds();
        var m5=Enumerable.Range(0,5).Select(i=>{
            long start=at-60000L-(5-i)*300000L;
            decimal o=100m+i*.1m;
            return new NativeClosedMarketBar(start,start+300000L,
                o,o+.20m,o-.20m,o+.10m,12+i);
        }).ToArray();
        var m15=Enumerable.Range(0,3).Select(i=>{
            long start=at-60000L-(3-i)*900000L;
            decimal o=99m+i*.3m;
            return new NativeClosedMarketBar(start,start+900000L,
                o,o+.40m,o-.40m,o+.2m,38+i);
        }).ToArray();
        var features=NativeScp1EconomicScorer.Features(
            "SYNTH",at,1,"RANGE_TRANSITION",m5,m15,.25m);
        check(features.Length==11&&features.All(double.IsFinite) &&
            features[5]==1 &&features[6]==1,
            "SCP1 CSharp genuine-bar-compatible 11 predecision multi-timeframe context features");
        bool futureRefused=false;
        try
        {
            var unsafeBars=m5.ToArray();
            unsafeBars[^1]=unsafeBars[^1] with {CloseAt=at+1L};
            _=NativeScp1EconomicScorer.Features("SYNTH",at,1,
                "RANGE_TRANSITION",unsafeBars,m15,.25m);
        }
        catch(ArgumentException){futureRefused=true;}
        check(futureRefused,"SCP1 no still-forming/future bar allowed in native forecast");
        var cells=new Dictionary<string,Scp1Bucket>(StringComparer.Ordinal){
            ["RANGE_TRANSITION/1/FOLLOW/LOW"]=new Scp1Bucket(
                60,40,25m,-14m,42m)
        };
        var ridge=new double[12];
        ridge[0]=.48d;ridge[1]=.01d;
        var model=new Scp1ScoreModel(NativeScp1EconomicScorer.Version,
            "BAYES_CONTEXT",at-86400000L,at-43200000L,
            new string('a',64),200,4,.55d,1.1d,-.8d,.9d,
            cells,ridge,80,.245d,.236d,.240d,true);
        var prior=NativeScp1EconomicScorer.Predict(model,
            "RANGE_TRANSITION",1,features,"NO_SCORE");
        var bayes=NativeScp1EconomicScorer.Predict(model,
            "RANGE_TRANSITION",1,features,"BAYES_CONTEXT");
        var nonlinear=NativeScp1EconomicScorer.Predict(model,
            "RANGE_TRANSITION",1,features,"RIDGE_NONLINEAR");
        check(prior.PWin>=.01&&prior.PWin<=.99 &&
            bayes.LowerPWin<bayes.PWin &&bayes.UncertaintyR>0 &&
            nonlinear.LowerConfidenceR<nonlinear.MeanR,
            "SCP1 causal probability, conservative bound and loss-tail direction distinct estimators");
        var core=new NativeUnifiedPortfolioEngine("SCP1_ABSTAIN",
            "SCP1_SYNTH_BROKER",model);
        var cloud=new NativeUnifiedCloudParityAdapter("SCP1_ABSTAIN",
            "SCP1_SYNTH_BROKER",model);
        var names=new[]{"SYNTH","PEER"};
        var contract=new NativeObservedContractTerms("SYNTH","USD",at-1000,
            1m,1m,2m,100m,2,0,2,0,null,0,0,0m,0m,4,
            24,1320,3,false,0,true,false);
        var market=new Ucp1MarketFrame("SYNTH",
            new LedgerQuote("SYNTH",at,100.4m,100.41m,1m,1m,.001m,
                .0001m,1m),contract,m5,m15,.01m,
            "SYNTHETIC_SOURCE_CONTRACT_TEST_NOT_MARKET");
        var input=new Ucp1Frame(at,new[]{market},
            IntermarketBreadth:.25m);
        var a=core.Advance(input),b=cloud.Observe(input);
        check(JsonSerializer.Serialize(a)==JsonSerializer.Serialize(b) &&
            JsonSerializer.Serialize(core.Scp1ChoiceReceipts)==
              JsonSerializer.Serialize(cloud.ModelFacts.Where(x=>x.Kind=="SCP1_RESERVED_NONEXISTENT").ToArray())==false &&
            a.OrdersSubmitted==false && b.OrdersSubmitted==false,
            "SCP1 full same Core scorer entry/exit/ledger as Cloud adapter, no broker order side effect");
        var recovered=NativeUnifiedPortfolioEngine.Restore(core.Checkpoint());
        check(recovered.Checkpoint()==core.Checkpoint(),
            "SCP1 fitted method, features and complete portfolio restore deterministic");
    }
}
