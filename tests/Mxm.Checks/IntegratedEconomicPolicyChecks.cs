using System;
using System.Linq;
using Mxm.Cloud;
using Mxm.Core;

internal static class IntegratedEconomicPolicyChecks
{
    public static void Run(Action<bool,string> check)
    {
        long start=new DateTimeOffset(2026,10,26,14,0,15,TimeSpan.Zero).ToUnixTimeMilliseconds();
        var contract=new NativeObservedContractTerms("AAA","USD",start-10_000,
            .25m,.25m,100m,100m,2,0,2,0,null,0,0,0m,0m,
            2,24,1320,3,false,0,true,false);
        var volumes=new[]{.25m,.50m,1m}.Select(v=>new NativeObservedVolume(v,v*10m,v*10m)).ToArray();
        NativeClosedMarketBar[] Bars(int n,int duration,decimal low,decimal high,decimal close)
            =>Enumerable.Range(0,n).Select(i=>{
                long open=start-15_000-(n-i)*duration;
                return new NativeClosedMarketBar(open,open+duration,close,high,low,close,100);
            }).ToArray();
        var m5=Bars(5,300_000,100.2m,103m,101.5m);
        m5[^1]=m5[^1] with {Low=99m};
        var m15=Bars(3,900_000,100m,110m,102m);
        var h1=Bars(2,3_600_000,100m,110m,102m);
        Ucp1MarketFrame Market(string name,long at,decimal bid,decimal ask)
            =>new(name,new LedgerQuote(name,at,bid,ask,1m,1m,.001m,0m,10m),
                contract with {Symbol=name},m5,m15,.025m,"SYNTHETIC_ONLY",
                new NativeIntegratedMarket(h1,volumes,true,.01m,new(bid,bid,ask,ask,true)));
        Ucp1Frame At(int minute,decimal bid,decimal ask)=>new(start+minute*60_000L,
            new[]{Market("AAA",start+minute*60_000L,bid,ask),Market("BBB",start+minute*60_000L,bid,ask)});
        var min=new NativeUnifiedPortfolioEngine("INTEGRATED_FIRST_MIN");
        var replay=new NativeUnifiedPortfolioEngine("INTEGRATED_STRUCTURE_BUDGET");
        var observer=new NativeUnifiedCloudParityAdapter("INTEGRATED_STRUCTURE_BUDGET");
        var frames=new[]{At(0,101.45m,101.55m),At(1,101.45m,101.55m),At(2,103.9m,104m),
            At(3,103.9m,104m),new Ucp1Frame(start+4*60_000L,Array.Empty<Ucp1MarketFrame>()),
            At(5,105.2m,105.3m),At(6,105.2m,105.3m)};
        bool parity=true;
        foreach(var frame in frames)
        {
            min.Advance(frame);
            parity&=replay.Advance(frame)==observer.Observe(frame);
        }
        check(parity && replay.Checkpoint()==observer.Checkpoint(),
            "Integrated Replay and observational cBot share identical causal frame decisions and funded facts");
        check(min.OriginalModelEvents.Single(e=>e.Kind=="REQUEST_OPEN").Units==.25m &&
            replay.OriginalModelEvents.Single(e=>e.Kind=="REQUEST_OPEN").Units==1m,
            "Integrated sizing keeps legal fractional volume and a bounded alternative to maximum volume");
        var fills=replay.OriginalModelEvents.Where(e=>e.Kind=="CLOSE_FILL").ToArray();
        check(fills.Length==2 && fills[0].Units==.25m && fills[1].Units==.75m &&
            replay.ModelSummary.CompleteRoundTrips==1 && replay.CompleteModelTrips.Single().NetEur==replay.ModelSummary.ClosedNetEur,
            "Integrated reduction settles only its legal amount and both fragments reconcile as one round trip");
        check(replay.CommonBookEquityPath[4].Held==1 && replay.CommonBookEquityPath[4].EquityEur is null &&
            replay.CompleteModelTrips.Single().CrossedUnknownHistory,
            "Integrated unknown path preserves exposure and prevents invented broker settlement");
    }
}
