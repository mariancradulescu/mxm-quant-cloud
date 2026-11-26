using Mxm.Core;

internal static class NativeEconomicMechanismChecks
{
    internal static void Run(Action<bool,string> check)
    {
        const long at=1_785_800_015_000L;
        var market=Cpe1IntegratedEconomicChecks.Frame(at-300_000L,at,101m,false).Markets[0];
        var windows=NativeClosedMarketContext.CoverageWindows.Select(r=>
        {
            long width=(long)r.Timeframe*60_000L,last=(at/width)*width;
            var bars=Enumerable.Range(0,r.Count).Select(i=>
            {
                decimal price=100m+i*.1m;
                return new NativeClosedMarketBar(last-(r.Count-i)*width,last-(r.Count-i-1)*width,
                    price-.05m,price+.15m,price-.15m,price,i==r.Count-1?200:100);
            }).ToArray();
            return new NativeBarWindow(r.Timeframe,r.Count,last,at,"SYNTHETIC",NativeBarStatus.Ready,bars);
        }).ToArray();
        market=market with {ClosedBars=new(at,windows),EurTickSize=.01m,
            M5=windows.Single(w=>w.Timeframe==NativeBarTimeframe.M5).Bars,
            M15=windows.Single(w=>w.Timeframe==NativeBarTimeframe.M15).Bars};
        var follow=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,market,at,1.5m);
        var reverse=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Reverse,market,at,1.5m);
        check(follow.Single().Side==1&&reverse.Single().Side==-1,
            "Distinct follow and reverse mechanisms produce opposed executable causal geometries");
        var future=market with {ClosedBars=new(at,windows.Select(w=>w with
            {Bars=w.Bars.Append(w.Bars[^1] with {CloseAt=at+1}).ToArray()}).ToArray())};
        check(NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,future,at,1.5m).Length==0,
            "Distinct economic mechanisms reject forming/future bars");
        check(NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Intermarket,market,at,1.5m,new(at,new[]{market})).Length==0,
            "Intermarket mechanism abstains without an authenticated class and aligned peers");
        check(NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Activity,market,at,1.5m).Single().Side==1,
            "Recovered V3.3 impulse and activity drive a distinct multiscale mechanism");
        check(NativeEconomicMechanisms.Continuation(market,at) is {Mean:>0m},
            "Recovered PAV1 transition value uses completed adjacent movements");
        var context=new NativeEurDecisionContext("EURUSD",null,0,Array.Empty<NativeEurBarState>(),0m,.1m,true);
        var rows=Enumerable.Range(0,30).Select(i=>new NativeEurCalibrationOutcome("E"+i,"F",1,
            at-(i/10+1)*86_400_000L,at-(i/10+1)*86_400_000L+1, i%2==0?2m:-1m,i%2==0?1.9m:-1.1m,1m)
            {Context=context}).ToArray();
        var payoff=NativeEconomicMechanisms.LifecyclePayoff(rows,"F",1,context,at,1m,.1m,20,3,0m);
        var contaminated=rows.Append(rows[0] with {PositionId="FUTURE",AvailableAt=at+1,GrossEur=100000m}).ToArray();
        check(payoff is {GrossMeanEur:.5m,NetMeanEur:.4m}&&payoff==NativeEconomicMechanisms.LifecyclePayoff(
            contaminated,"F",1,context,at,1m,.1m,20,3,0m),
            "SCP1 conditional win/loss magnitudes match funded realized EUR and exclude unmatured labels");
        check(NativeEconomicMechanisms.LifecyclePayoff(rows,"F",1,context with {Symbol="US500"},at,1m,.1m,20,3,0m) is null,
            "SCP1 lifecycle scores never transfer unsupported results across instruments");
        // Identical admission risk scale. The early-stop cash loss has no
        // excursion requirement; its modeled monetary value must change the estimate.
        var fastLoss=rows[0] with {PositionId="FAST_STOP",GrossEur=-30m,NetEur=-31m};
        var baseScore=NativeEconomicMechanisms.EntryQualityPayoff(rows,"F",1,context,at,1m,.1m,20,3,0m,false);
        var corrected=NativeEconomicMechanisms.EntryQualityPayoff(rows.Append(fastLoss),"F",1,context,at,1m,.1m,20,3,0m,false);
        check(baseScore is {NetLowerEur:>0m}&&corrected is {NetLowerEur:<0m},
            "Settled fast-stop cash losses must affect entry quality even without excursion marks");
        var band=NativeEconomicMechanisms.EntryQualityPayoff(rows,"F",1,context,at,1m,.1m,20,3,0m,true);
        check(band is not null&&band==NativeEconomicMechanisms.EntryQualityPayoff(contaminated,"F",1,context,at,1m,.1m,20,3,0m,true),
            "Causal cost/risk bands and estimates exclude future outcomes");
        check(NativeEconomicMechanisms.EntryQualityPayoff(rows,"F",1,context with {CostRiskFraction=.9m},at,1m,.1m,20,3,0m,true) is null,
            "Unsupported cost band abstains rather than borrowing an unrelated payoff");

        var close=market.M5[^1].Close;
        var near=market with {Quote=market.Quote with {Bid=close,Ask=close+.01m}};
        var moved=near with {Quote=near.Quote with {Bid=close+.02m,Ask=close+.03m}};
        var anchored=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,near,at,4m,
            geometryTimeframe:"M5",stopRanges:1m,closedStructure:true).Single();
        var later=NativeEconomicMechanisms.Describe(NativeEconomicMechanisms.Follow,moved,at,4m,
            geometryTimeframe:"M5",stopRanges:1m,closedStructure:true).Single();
        check(anchored.Stop==later.Stop&&anchored.Target==later.Target&&anchored.Stop<close,
            "Closed-structure stop and economic destination do not drift with executable entry");
        var profile=new NativeEurDevelopmentProfile(UseAvailableContext:true)
        {
            EconomicMechanism=NativeEconomicMechanisms.Follow,EconomicManagement="CAPTURE_VALUE",
            EconomicGeometryTimeframe="M5",EconomicStopRanges=1m,EconomicManagementTimeframe="M5",
            AnchorEconomicGeometryToClosedStructure=true,KeepAdmissionRiskAtFill=true,ResizeWithinAdmissionRiskAtFill=true
        };
        profile.Verify();
        check(profile.GeometryIdentity.Contains("CLOSED_STRUCTURE_ANCHOR")&&profile.GeometryIdentity.Contains("MECHANISM_KEEP_RISK"),
            "Distinct economic mechanisms may reuse admission-risk guard with independent geometry identity");
        var fx=context with {AssetClass="FX"};
        var peers=new[]{"GBPUSD","USDJPY"}.SelectMany(symbol=>rows.Select(row=>row with
            {PositionId=symbol+row.PositionId,Context=fx with {Symbol=symbol}})).ToArray();
        var peer=NativeEconomicMechanisms.LeaveSymbolOutPayoff(peers,"F",1,fx,at,1m,.1m,20,3,0m);
        var contamination=peers.Concat(rows.Select(row=>row with {Context=fx,GrossEur=10000m,NetEur=10000m}))
            .Append(peers[0] with {AvailableAt=at+1,GrossEur=100000m,NetEur=100000m});
        check(peer is {SupportedPeers:2,MeanNetEur:.4m}&&peer==NativeEconomicMechanisms.LeaveSymbolOutPayoff(
            contamination,"F",1,fx,at,1m,.1m,20,3,0m),
            "Leave-symbol-out forecast excludes target and future outcomes, normalizes only same-class supported peers");
        check(NativeEconomicMechanisms.LeaveSymbolOutPayoff(peers,"F",1,fx with {AssetClass="METAL"},at,1m,.1m,20,3,0m) is null,
            "Peer estimate cannot transfer across unrelated classes");
    }
}
