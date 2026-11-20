using System;
using System.Linq;
using Mxm.Cloud;
using Mxm.Core;

internal static class CompletePolicyChecks
{
    public static void Run(Action<bool,string> check)
    {
        long at = new DateTimeOffset(2026,7,7,8,15,15,TimeSpan.Zero).ToUnixTimeMilliseconds();
        var contract = new NativeObservedContractTerms("EURUSD","USD",at-1,.25m,.25m,100m,100m,
            2,0,2,0,null,0,0,0m,0m,2,24,1320,3,false,0,true,false);
        NativeClosedMarketBar[] Bars(long clock, long size, int count, decimal low, decimal high)
        {
            long end=clock/size*size;
            return Enumerable.Range(0,count).Select(i=>{
                long close=end-(count-1-i)*size;
                return new NativeClosedMarketBar(close-size,close,100m,high,low,100m,5);
            }).ToArray();
        }
        Ucp1Frame Frame(long clock, decimal price)
        {
            decimal bid=price-.05m, ask=price+.05m;
            return new(clock,new[]{new Ucp1MarketFrame("EURUSD",
                new("EURUSD",clock,bid,ask,.8m,.9m,.01m,0m,15m),contract,
                Bars(clock,300_000L,5,99.25m,100.75m),Bars(clock,900_000L,3,99m,101m),.025m,
                "SYNTHETIC",new(Bars(clock,3_600_000L,1,97m,103m),
                    new[]{new NativeObservedVolume(.25m,3.75m,3.75m)},true,.01m,new(bid,bid,ask,ask,true)))});
        }
        var positive = new NativeQuoteResidenceStream();
        var negative = new NativeQuoteResidenceStream();
        Ucp1Frame lastUp=Frame(at,100m), lastDown=lastUp;
        var replay=new NativeUnifiedPortfolioEngine(NativeCompletePolicy.Prefix+"FIRST");
        var observer=new NativeUnifiedCloudParityAdapter(NativeCompletePolicy.Prefix+"FIRST");
        bool parity=true;
        for(int i=0;i<30;i++)
        {
            long clock=at-(29-i)*30_000L;
            decimal up=i<10||i==29?100m:i==10?99m:101m;
            decimal down=i<10||i==29?100m:i==10?101m:99m;
            var raw=Frame(clock,up);
            lastUp=positive.Observe(raw);
            lastDown=negative.Observe(Frame(clock,down));
            parity &= replay.Advance(lastUp)==observer.Observe(raw);
        }
        check(lastUp.Markets[0].Integrated!.Residence!.Mean>0m &&
              lastDown.Markets[0].Integrated!.Residence!.Mean<0m &&
              lastUp.Markets[0].Integrated!.Residence!.MidDisplacement==lastDown.Markets[0].Integrated!.Residence!.MidDisplacement,
              "Executable quote occupation differs when path extrema and first/last prices agree");
        foreach(var (offset,price) in new[]{(30_000L,100m),(60_000L,98m),(90_000L,97.7m)})
        {
            var f=Frame(at+offset,price);
            parity &= replay.Advance(positive.Observe(f))==observer.Observe(f);
        }
        check(parity && replay.ModelSummary.CompleteRoundTrips==1 &&
              replay.OriginalModelEvents.Single(e=>e.Kind=="CLOSE_FILL").At==at+90_000L &&
              replay.CompleteModelTrips.Single().Integrated!.CompletePolicy is not null,
              "Complete-policy Replay and observational adapter share feature timing, priced protection and settlements");

        var probe=new NativeUnifiedPortfolioEngine(NativeCompletePolicy.Probe,
            probe:new NativeCompleteProbe("EURUSD",1,at));
        var intent=probe.Advance(lastUp);
        check(intent.Pending==1 && intent.Held==0 && intent.ModelBook==probe.ModelSummary,
            "The isolated training probe receives the committed pending intent from the authoritative ledger");
        var opened=probe.Advance(positive.Observe(Frame(at+30_000L,100m)));
        var trigger=probe.Advance(positive.Observe(Frame(at+60_000L,98m)));
        var settled=probe.Advance(positive.Observe(Frame(at+90_000L,97.7m)));
        check(opened.Held==1 && trigger.Held==1 && settled.ModelBook.CompleteRoundTrips==1 &&
            probe.CompleteModelTrips.Single().NetEur==probe.ModelSummary.ClosedNetEur &&
            probe.CompleteModelTrips.Single().Integrated!.CompletePolicy!.ScaleEur>0m,
            "The same isolated episode reaches a real complete-label event, not a pending-state prefill exit");

        var observations=Enumerable.Range(1,4).SelectMany(i=>Enumerable.Range(0,4).Select(j=>
            new NativeCompleteSample("EURUSD",at-i*NativeCompletePolicy.Day+j,
                at-i*NativeCompletePolicy.Day+j+1,new[]{0m,1m},2m))).Append(
                new NativeCompleteSample("EURUSD",at-1,at+30_000L,new[]{0m,1m},-500m)).ToArray();
        var distribution=new NativeCompleteDistribution(observations,false);
        var prediction=distribution.Predict(new[]{0m,1m},at,.5m);
        check(prediction is { Mean:1m, P10:1m, P90:1m, Observations:16, Days:4 },
            "Causal empirical distribution excludes settlements after the decision");
    }
}
