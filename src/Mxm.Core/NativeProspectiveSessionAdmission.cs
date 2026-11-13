using System;
using System.Linq;

namespace Mxm.Core;

// Prospective-only, NO-ORDER entry underwriting. The weekly schedule MUST be
// broker-observed and known before the decision. A broker acknowledgement of
// a stop is not a guarantee of a fill through a closure/gap.
public sealed record NativeWeeklyTradingInterval(int StartSecond,int EndSecond);
public sealed record NativeProspectiveSessionRiskEvidence(
    string ScheduleTimeZone,NativeWeeklyTradingInterval[] TradingIntervals,
    long ScheduleKnownAtMs,long DecisionAtMs,int ProtectiveMinutes,
    long ExitRequestLatencyMs,bool HolidayCalendarCovered,
    bool PriorHoldingQuoteCoverageSufficient,
    decimal? CommonLiquidationEquityEur,decimal? CommonPeakEquityEur,
    decimal? CommonFreeMarginEur,decimal NewMarginEur,
    decimal? MarginalAdverseLossEur,
    bool ExplicitSessionGapAcceptance=false,
    decimal? AdditionalGapLossReserveEur=null,
    bool BrokerSideStopAcknowledged=false);
public sealed record NativeSessionAdmissionResult(
    bool Admit,string Reason,long? SessionCloseAtMs,
    bool PlannedProtectionCrossesClosure,bool StopFillCertified=false);

public static class NativeProspectiveSessionAdmission
{
    public static NativeSessionAdmissionResult Assess(
        NativeProspectiveSessionRiskEvidence? e)
    {
        NativeSessionAdmissionResult Deny(string reason,long? close=null,
            bool crossing=false)=>new(false,reason,close,crossing,false);
        if(e is null)return Deny("SESSION_EVIDENCE_MISSING");
        if(e.DecisionAtMs<=0||e.ScheduleKnownAtMs<=0||
           e.ScheduleKnownAtMs>e.DecisionAtMs||
           e.ProtectiveMinutes<=0||e.ExitRequestLatencyMs<=0)
            return Deny("SESSION_EVIDENCE_NOT_CAUSALLY_BOUND");
        if(!e.HolidayCalendarCovered)return Deny("HOLIDAY_EXCEPTION_COVERAGE_UNKNOWN");
        if(!e.PriorHoldingQuoteCoverageSufficient)
            return Deny("HISTORICAL_HOLDING_QUOTE_COVERAGE_INSUFFICIENT");
        if(e.CommonLiquidationEquityEur is not decimal equity ||
           e.CommonPeakEquityEur is not decimal peak ||
           e.CommonFreeMarginEur is not decimal free ||
           e.MarginalAdverseLossEur is not decimal marginal ||
           equity<=0m||peak<=0m||free<0m||e.NewMarginEur<=0m||
           marginal<0m)
            return Deny("COMMON_PORTFOLIO_RISK_UNPRICED");
        if(e.NewMarginEur>free)return Deny("COMMON_FREE_MARGIN_INSUFFICIENT");
        if(e.TradingIntervals is null || e.TradingIntervals.Length==0 ||
           e.TradingIntervals.Any(x=>x.StartSecond<0 ||
               x.EndSecond>604800 || x.StartSecond>=x.EndSecond))
            return Deny("BROKER_WEEKLY_SESSION_INVALID");
        TimeZoneInfo zone;
        try{zone=TimeZoneInfo.FindSystemTimeZoneById(e.ScheduleTimeZone);}
        catch(Exception ex) when(ex is TimeZoneNotFoundException ||
                                 ex is InvalidTimeZoneException ||
                                 ex is ArgumentException)
        {
            return Deny("BROKER_SESSION_TIMEZONE_UNVERIFIED");
        }
        long closing;
        try
        {
            DateTime nowUtc=DateTimeOffset.FromUnixTimeMilliseconds(
                e.DecisionAtMs).UtcDateTime;
            DateTime local=TimeZoneInfo.ConvertTimeFromUtc(nowUtc,zone);
            int second=(int)local.DayOfWeek*86400+
                local.Hour*3600+local.Minute*60+local.Second;
            var session=e.TradingIntervals.FirstOrDefault(x=>
                x.StartSecond<=second&&second<x.EndSecond);
            if(session is null)return Deny("SYMBOL_NOT_OPEN_AT_DECISION");
            DateTime sunday=local.Date.AddDays(-(int)local.DayOfWeek);
            DateTime localClose=DateTime.SpecifyKind(
                sunday.AddSeconds(session.EndSecond),DateTimeKind.Unspecified);
            if(zone.IsInvalidTime(localClose)||zone.IsAmbiguousTime(localClose))
                return Deny("SESSION_CLOSE_DST_AMBIGUOUS");
            closing=new DateTimeOffset(TimeZoneInfo.ConvertTimeToUtc(
                localClose,zone)).ToUnixTimeMilliseconds();
        }
        catch(Exception ex) when(ex is ArgumentOutOfRangeException ||
                                 ex is OverflowException)
        {
            return Deny("BROKER_SESSION_TIME_CALCULATION_UNCERTAIN");
        }
        if(closing<=e.DecisionAtMs)return Deny("BROKER_SESSION_CLOSE_UNCERTAIN");
        long deadline;
        try
        {
            deadline=checked(e.DecisionAtMs+
                checked((long)e.ProtectiveMinutes*60000L)+
                e.ExitRequestLatencyMs);
        }
        catch(OverflowException){return Deny("PROTECTIVE_EXIT_CLOCK_OVERFLOW");}
        bool crosses=deadline>=closing; // endSecond is exclusive, no fill at the boundary
        if(crosses&&!e.ExplicitSessionGapAcceptance)
            return Deny("PROTECTIVE_EXIT_CROSSES_SESSION_CLOSE",closing,true);
        if(crosses && (e.AdditionalGapLossReserveEur is not decimal reserve ||
                       reserve<=0m))
            return Deny("SESSION_GAP_LOSS_UNDERWRITING_MISSING",closing,true);
        decimal risk;
        try{risk=checked(marginal+(crosses?
            e.AdditionalGapLossReserveEur!.Value:0m));}
        catch(OverflowException){return Deny("PORTFOLIO_LOSS_BOUND_OVERFLOW",closing,crosses);}
        decimal floatingDrawdown=Math.Max(0m,peak-equity);
        // Risk includes the already incurred floating loss and the marginal
        // predeclared scenario, without claiming a guaranteed broker stop.
        if(floatingDrawdown+risk>peak*.30m)
            return Deny("COMMON_FLOATING_DRAWDOWN_BUDGET_EXCEEDED",closing,crosses);
        return new(true,crosses?"OVERNIGHT_GAP_EXPLICITLY_UNDERWRITTEN":
            "PROTECTIVE_DEADLINE_WITHIN_OPEN_SESSION",
            closing,crosses,false);
    }
}
