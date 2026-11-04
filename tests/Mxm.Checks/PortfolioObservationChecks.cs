using Mxm.Core;
internal static class PortfolioObservationChecks
{
    public static void Run(Action<bool,string> check)
    {
        string proof=new('c',64);var session=new NativeFundedSession("RISK_TEST");
        PortfolioRiskMark Mark(long t,decimal equity,decimal margin,decimal pnl)=>new("RISK_TEST","BROKER_PLATFORM_OBSERVATION","PLATFORM_MARK_EQUITY",t,t,
            200,equity,margin,equity-margin,0,true,true,new[]{new PositionRiskMark("P","X",1,1,pnl)},null,null,null,.01m,proof);
        var first=session.ObservePortfolio(Mark(1000,200,80,0),1000);
        check(first.MaximumSampledDrawdown is null&&first.ConservativeExitEquityEur is null,"one mark cannot manufacture drawdown or executable liquidation value");
        var fall=session.ObservePortfolio(Mark(2000,130,90,-70),2000);
        check(fall.MaximumSampledDrawdown==.35m&&fall.ReviewReductionIds.Length==1&&fall.SuspendNewExposure,
            "a measured35 percent drawdown lower bound requests reduction review under shared owner risk");
        session=NativeFundedSession.Restore(session.Checkpoint(),"RISK_TEST");
        var rebound=session.ObservePortfolio(Mark(3000,180,80,-20),3000);
        check(rebound.ObservedPeakEur==200&&rebound.MaximumSampledDrawdown==.35m&&!rebound.ContinuousDrawdownCertified,
            "restart and rebound cannot erase the observed peak or claim a continuous path");
        var gap=session.ObservePortfolio(Mark(4000,180,80,-20) with {EquityEur=null},4000);
        check(gap.ObservationGap&&gap.ObservedEquityEur is null&&gap.ReviewReductionIds.Length==1,"unknown held equity is not a zero-PNL mark");
        var bad=session.ObservePortfolio(Mark(5000,190,80,-20),5000);
        check(bad.ComponentsReconciled==false&&bad.ValidSamples==3,"a cash/PNL/equity contradiction cannot advance the healthy risk series");
        var fresh=new NativePortfolioObservation("EMPTY");
        var empty=Mark(1000,0,0,0) with {AccountBinding="EMPTY",CashEur=0,Positions=Array.Empty<PositionRiskMark>()};
        check(fresh.Observe(empty,1000).MaximumSampledDrawdown is null,"an unfunded empty account has no inferred200EUR drawdown path");
    }
}
