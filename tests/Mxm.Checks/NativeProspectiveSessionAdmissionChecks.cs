using System;
using Mxm.Core;

public static class NativeProspectiveSessionAdmissionChecks
{
    public static void Run(Action<bool,string> check)
    {
        long at=DateTimeOffset.Parse("2026-09-02T15:35:01.500Z")
            .ToUnixTimeMilliseconds();
        // SYNTHETIC as-of session snapshots; the actual MSE1 schedule was
        // observed after its historical period and is not backdated here.
        var intervals=new[]{
            new NativeWeeklyTradingInterval(101700,134940),
            new NativeWeeklyTradingInterval(188100,221340),
            new NativeWeeklyTradingInterval(274500,307740),
            new NativeWeeklyTradingInterval(360900,394140),
            new NativeWeeklyTradingInterval(447300,480300)
        };
        var e=new NativeProspectiveSessionRiskEvidence(
            "America/New_York",intervals,at-60000,at,120,1000,
            true,true,300m,300m,300m,249.315m,40m);
        var rejected=NativeProspectiveSessionAdmission.Assess(e);
        check(!rejected.Admit && rejected.PlannedProtectionCrossesClosure &&
            rejected.Reason=="PROTECTIVE_EXIT_CROSSES_SESSION_CLOSE",
            "Coffee 120-minute protection extending after broker close is not admitted");
        var earlier=NativeProspectiveSessionAdmission.Assess(e with {
            DecisionAtMs=at-25*60000,
            ScheduleKnownAtMs=at-30*60000
        });
        check(earlier.Admit&&!earlier.PlannedProtectionCrossesClosure &&
            !earlier.StopFillCertified,
            "same 120-minute protective policy inside open session can be admitted without fill certification");
        check(!NativeProspectiveSessionAdmission.Assess(e with {
            ExplicitSessionGapAcceptance=true
        }).Admit,"gap carry without an independently priced bound is blocked");
        var carry=NativeProspectiveSessionAdmission.Assess(e with {
            ExplicitSessionGapAcceptance=true,AdditionalGapLossReserveEur=25m
        });
        check(carry.Admit&&carry.PlannedProtectionCrossesClosure &&
            !carry.StopFillCertified,"explicitly risk-underwritten overnight carry can pass without claiming stop execution");
        check(!NativeProspectiveSessionAdmission.Assess(e with {
            ExplicitSessionGapAcceptance=true,AdditionalGapLossReserveEur=25m,
            MarginalAdverseLossEur=70m
        }).Admit,"common 30 percent budget includes marginal loss plus gap reserve");
        check(!NativeProspectiveSessionAdmission.Assess(e with {
            CommonFreeMarginEur=220m
        }).Admit,"margin is checked against common free capital, not initial cash alone");
        check(!NativeProspectiveSessionAdmission.Assess(e with {
            PriorHoldingQuoteCoverageSufficient=false
        }).Admit,"missing held quote coverage is a prospective data no-go");
        check(!NativeProspectiveSessionAdmission.Assess(e with {
            ScheduleKnownAtMs=at+1
        }).Admit,"late-discovered session rules cannot authorize historical entry");
        check(!NativeProspectiveSessionAdmission.Assess(e with {
            HolidayCalendarCovered=false
        }).Admit,"uncertified holiday exceptions block protective planning");
        check(NativeProspectiveSessionAdmission.Assess(e with {
            ProtectiveMinutes=1500,ExplicitSessionGapAcceptance=true,
            AdditionalGapLossReserveEur=25m
        }).Admit,"no universal holding duration ceiling: longer position requires explicit gap underwriting");
        check(!NativeProspectiveSessionAdmission.Assess(e with {
            ExplicitSessionGapAcceptance=true,AdditionalGapLossReserveEur=25m,
            CommonLiquidationEquityEur=230m
        }).Admit,"already incurred floating drawdown consumes the common risk budget");
        check(NativeProspectiveSessionAdmission.Assess(e with {
            ExplicitSessionGapAcceptance=true,AdditionalGapLossReserveEur=25m,
            BrokerSideStopAcknowledged=true
        }).StopFillCertified==false,"server-side stop acknowledgement never certifies execution through gaps");
    }
}
