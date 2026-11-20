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

        var warmup=new Ucp1Frame(start-NativeIntegratedLifecycle.CalibrationMs,Array.Empty<Ucp1MarketFrame>());
        Ucp1Frame CoherentAt(long offset,decimal bid=101.45m,decimal ask=101.55m,bool newM15=false)
        {
            long at=start+offset;
            NativeClosedMarketBar[] Context(long duration,int count,decimal low,decimal high,decimal close)
            {
                long last=at/duration*duration;
                return Enumerable.Range(0,count).Select(j=>{
                    long open=last-(count-j)*duration;
                    return new NativeClosedMarketBar(open,open+duration,close,high,low,close,100);
                }).ToArray();
            }
            var shortBars=Context(300_000,5,100.2m,103m,101.5m);
            shortBars[^1]=shortBars[^1] with {Low=99m};
            var medium=Context(900_000,3,100m,110m,102m);
            medium[^2]=medium[^2] with {Close=103m};
            if(newM15)medium[^1]=medium[^1] with {Close=98m,Low=98m};
            return new(at,new[]{Market("AAA",at,bid,ask) with {
                M5=shortBars,M15=medium,Integrated=new NativeIntegratedMarket(
                    Context(3_600_000,2,100m,110m,102m),volumes,true,.01m,new(bid,bid,ask,ask,true))
                    { Protection=new NativeProtectionDistances(.01m,.01m,false) }
            }});
        }

        var coherent=new NativeUnifiedPortfolioEngine(NativeIntegratedLifecycle.First);
        var cloud=new NativeUnifiedCloudParityAdapter(NativeIntegratedLifecycle.First);
        bool coherentParity=coherent.Advance(warmup)==cloud.Observe(warmup);
        for(long offset=0L;offset<=120_000L;offset+=NativeIntegratedLifecycle.IntervalMs)
        {
            var frame=CoherentAt(offset);
            coherentParity&=coherent.Advance(frame)==cloud.Observe(frame);
        }
        check(coherent.ModelSummary.OpenPositions==1 &&
              !coherent.OriginalModelEvents.Any(e=>e.Kind=="REQUEST_CLOSE"),
            "An already adverse M15 reading at failed-auction admission cannot trigger the old immediate exit");
        var restored=NativeUnifiedPortfolioEngine.Restore(coherent.Checkpoint());
        check(restored.Checkpoint()==coherent.Checkpoint(),"Coherent protection evidence survives a Core checkpoint");
        for(long offset=150_000L;offset<=930_000L;offset+=NativeIntegratedLifecycle.IntervalMs)
        {
            var frame=CoherentAt(offset,newM15:offset>=900_000L);
            var replayStep=coherent.Advance(frame);
            coherentParity&=replayStep==cloud.Observe(frame) && replayStep==restored.Advance(frame);
        }
        var thesisTrip=coherent.CompleteModelTrips.Single();
        var thesis=thesisTrip.Integrated!.Thesis!;
        check(coherentParity && thesis.InvalidatingM15CloseAt==start+885_000L &&
            thesis.InvalidatingM15CloseAt>thesisTrip.OpenAt &&
            thesisTrip.ExitReason=="MODEL_UNTRANSMITTED_INTEGRATED_NEW_M15_THESIS_INVALIDATION",
            "A genuinely new adverse M15 close invalidates the frozen thesis in Replay, restore and cBot Core");
        var stopped=new NativeUnifiedPortfolioEngine(NativeIntegratedLifecycle.First);
        stopped.Advance(warmup);
        stopped.Advance(CoherentAt(0));
        stopped.Advance(CoherentAt(30_000L));
        stopped.Advance(CoherentAt(60_000L,98.4m,98.5m));
        check(stopped.ModelSummary.OpenPositions==1 &&
              stopped.OriginalModelEvents.Last(e=>e.Kind!="MARK").Reason=="MODEL_UNTRANSMITTED_INTEGRATED_OBSERVED_INVALIDATION",
            "The structural stop requests protection immediately without a minimum holding period");
        stopped.Advance(CoherentAt(90_000L,97.9m,98m));
        var stopFact=stopped.OriginalModelEvents.Single(e=>e.Kind=="CLOSE_FILL");
        check(stopFact.At==start+90_000L && stopFact.ExecutionPrice==97.875m &&
              stopped.CompleteModelTrips.Single().R< -1m,
            "A stop settles only at a later observed price and reports overruns instead of inventing protection fills");

        var economic=new NativeUnifiedPortfolioEngine(NativeIntegratedLifecycle.Economic);
        economic.Advance(warmup);
        economic.Advance(CoherentAt(0));
        check(economic.ModelSummary.PendingIntents==0 && economic.IntegratedCalibration()!.Cells.Length==0,
            "Economic selection abstains where a financeable offer has insufficient causal observations to prefer it to cash");
        var calibrated=new NativeUnifiedPortfolioEngine(NativeIntegratedLifecycle.Economic);
        calibrated.Advance(warmup);
        for(int day=1;day<=4;day++)
            for(int slot=0;slot<4;slot++)
            {
                long offset=-NativeIntegratedLifecycle.CalibrationMs+day*86_400_000L+slot*300_000L;
                calibrated.Advance(CoherentAt(offset));
                calibrated.Advance(CoherentAt(offset+30_000L));
                calibrated.Advance(CoherentAt(offset+60_000L,105.2m,105.3m));
            }
        calibrated=NativeUnifiedPortfolioEngine.Restore(calibrated.Checkpoint());
        calibrated.Advance(CoherentAt(0));
        calibrated.Advance(CoherentAt(30_000L));
        check(calibrated.IntegratedCalibration()!.Cells.Any(c=>c.TargetFirst==16 && c.LowerProbability>0m) &&
            calibrated.ModelSummary.OpenPositions==1,
            "Completed historical target-first evidence can justify admission, and the positive EUR value is rechecked at fill");
    }
}
