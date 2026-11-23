using System;
using Mxm.Core;

public static class NativePostFillCapitalGuardChecks
{
    public static void Run(Action<bool,string> check)
    {
        var none=Array.Empty<NativePendingCapitalGate.Commitment>();
        var p=new NativePendingCapitalGate.Commitment(
            "future-intent-1","SYNTH",165m,1m,3m,"GROUP",true);
        var q=new LedgerQuote("SYNTH",1762128000000L,1m,1.001m,
            1m,1m,.001m,0m,1m){LiquidationSlippagePerSide=.0002m};
        var pre=NativePendingCapitalGate.RevalidatePendingFill(235.8m,true,
            none,new[]{p},p.PositionId);
        var post=NativePostFillCapitalGuard.Assess(235.8m,none,new[]{p},
            p.PositionId,1,q,.0002m);
        check(pre && !post.Allowed &&
            post.Reason=="POST_FILL_MARGIN_EXCEEDS_70PCT" &&
            post.TotalReservedMarginEur==165m &&
            post.MarginLimitEur<165m,
            "after fill costs, prefill 70pct PASS must become postfill FAIL");
        var safe=NativePostFillCapitalGuard.Assess(300m,none,new[]{p},
            p.PositionId,1,q,.0002m);
        check(safe.Allowed &&
            safe.TotalReservedMarginEur<=safe.MarginLimitEur,
            "postfill margin remains legal when fully paid liquidation costs are reserved");
        var unknown=NativePostFillCapitalGuard.Assess(null,none,new[]{p},
            p.PositionId,1,q,.0002m);
        check(!unknown.Allowed &&
            unknown.Reason=="MARKED_EQUITY_UNKNOWN",
            "future post-cost gate never funds unknown equity");
        var stress=NativePostFillCapitalGuard.Assess(300m,none,new[]{p},
            p.PositionId,-1,q,.0002m,extraPossibleDebitEur:90m);
        check(!stress.Allowed &&
            stress.Reason=="POST_FILL_MARGIN_EXCEEDS_70PCT",
            "conservative extra debit reduces projected free margin");
        var qHigherMargin=q with {MarginPerUnit=1.5m};
        var changed=NativePostFillCapitalGuard.Assess(300m,none,new[]{p},
            p.PositionId,1,qHigherMargin,.0002m);
        check(!changed.Allowed &&
            changed.PendingMarginEur==247.5m &&
            changed.Reason=="POST_FILL_MARGIN_EXCEEDS_70PCT",
            "source-valid higher margin-per-unit cannot be undercounted");
        var lowerEquity=NativePostFillCapitalGuard.Assess(300m,
            new[]{new NativePendingCapitalGate.Commitment(
                "held","OTHER",5m,1m,12m,"GROUP",false)},
            new[]{p},p.PositionId,1,q,.0002m);
        check(!lowerEquity.Allowed &&
            lowerEquity.Reason=="POST_FILL_AGGREGATE_RISK_EXCEEDS_5PCT",
            "prospective cost-paid equity also bounds aggregate stop risk");
    }
}