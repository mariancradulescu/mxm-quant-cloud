using System;
using System.Linq;
using Mxm.Core;

public static class NativeProductResearchLoopChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long m5=300000L,m15=900000L;
        long anchor=DateTimeOffset.Parse("2026-11-04T21:45:00Z").ToUnixTimeMilliseconds();
        NativeClosedMarketBar[] Window(string symbol,long step,long at)
        {
            long end=(at/step)*step;
            return Enumerable.Range(0,33).Select(i=>{
                decimal close=symbol=="SYNTH_A"
                    ?10.16m+i*.12m:22m-i*.12m;
                long open=end-(33-i)*step;
                return new NativeClosedMarketBar(open,open+step,close,
                    close+.02m,close-.02m,close,100+i);
            }).ToArray();
        }
        NativeObservedContractTerms Contract(string symbol,long at)=>
            new(symbol,"USD",at,1,1,1,1,2,5000000,
                1,0,"USD",10,0,-.05m,-.08m,2,24,1320,3,
                false,0,true,false);
        NativeProductMarket Market(string symbol,long at,int tick,
            bool support=false)
        {
            decimal bid=symbol=="SYNTH_A"
                ?14m+Math.Max(0,tick-1)*.12m
                :18m-Math.Max(0,tick-1)*.10m;
            var c=Contract(symbol,at);
            var cost=new NativeMarketCostContext(at,bid,bid+.02m,
                .99m,1.01m,1m,null,20m,1m,.005m);
            var charge=NativeBrokerContractCosts.Quote(c,cost);
            check(!charge.HistoricalExecutionCertified&&charge.OneSideCommissionEur>0,
                "current-term native cost source prices commission without claiming actual fills");
            return new(symbol,Window(symbol,m5,at-2000),
                Window(symbol,m15,at-2000),charge.Quote,c,.005m,30,support);
        }
        var cashOnly=new NativeProductResearchLoop();
        var at=anchor+2000;
        var refused=cashOnly.Advance(at,new[]{Market("SYNTH_A",at,0)},
            EnableUnqualifiedShadowSimulation:false);
        check(refused.Forecasts==1&&refused.AcceptedModelIntents==0&&
            refused.RejectedIntents>=1&&refused.ModelCashEur==300m&&
            refused.ModelClosedRoundTrips==0,
            "no independent predictive benchmark refuses prospective entry without mutating EUR300 cash");
        var loop=new NativeProductResearchLoop();
        var a=loop.Advance(at,new[]{Market("SYNTH_A",at,0),
            Market("SYNTH_B",at,0)},EnableUnqualifiedShadowSimulation:true);
        check(a.Forecasts==2&&a.AcceptedModelIntents==2&&
            a.ModelPendingIntents==2&&a.ModelCashEur==300m&&
            !a.Qualified&&!a.OrdersEnabled&&!a.BrokerNetCertified,
            "causal M5 plus M15 creates TWO common-capital conditional research intents only");
        NativeProductResearchReport r=a;
        for(int tick=1;tick<=9;tick++)
        {
            long clock=at+tick*m5;
            r=loop.Advance(clock,new[]{Market("SYNTH_A",clock,tick),
                Market("SYNTH_B",clock,tick)},
                EnableUnqualifiedShadowSimulation:tick<9);
            if(tick==1)
                check(r.ModelOpenPositions==2&&r.ModelCashEur<300m&&
                    r.ModelEquityEur<r.ModelCashEur,
                    "next market clock fills both model requests using real-side bid ask commission");
        }
        var settlement=loop.ResearchSession.Ledger;
        var summary=settlement.Summary();
        var fragments=settlement.ClosedFragments();
        check(r.ModelClosedRoundTrips==2&&summary.OpenPositions==0&&
            summary.PendingIntents==0&&r.ModelRoundTripsPerIsoWeek.Values.Sum()==2,
            "two closed model round trips are counted per UTC ISO week after 30m holding");
        check(summary.CashEur==300m+fragments.Sum(x=>x.NetEur)&&
            r.ModelCentralNetEur==summary.ClosedNetEur&&
            r.ModelGrossEur==fragments.Sum(x=>x.GrossEur),
            "one EUR300 funded MODEL domain reconciles gross, fees and cash without extra deposits");
        check(fragments.Any(x=>x.ConversionEur>0)&&
            fragments.All(x=>x.CommissionsEur>0)&&
            fragments.Any(x=>x.FinancingEur>0)&&
            fragments.All(x=>x.SpreadEur>0)&&
            fragments.All(x=>x.SlippageEur>0),
            "full modeled settlement itemizes conversion, commission, actual modeled rollover charge, spread and slippage");
        check(r.ModelAdverseNetProxyEur<r.ModelCentralNetEur&&
              r.ModelMaximumSampledDrawdown>0m&&!r.Qualified&&
              !r.BrokerNetCertified,
            "adverse extra-spread scenario and floating marked equity remain model-only");
        bool backwardRejected=false;
        try{loop.Advance(at+1,Array.Empty<NativeProductMarket>(),false);}
        catch(ArgumentException){backwardRejected=true;}
        check(backwardRejected,
            "out-of-order replay observations cannot overwrite a newer financial state");
        var checkpoint=loop.ResearchSession.Checkpoint();
        var restored=NativeFundedSession.Restore(checkpoint,loop.ResearchSession.AccountBinding);
        check(restored.Ledger.Summary()==loop.ResearchSession.Ledger.Summary(),
            "model-replay session checkpoint restarts with unchanged cash and closed round trips");
    }
}
