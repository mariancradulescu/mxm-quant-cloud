using System;
using System.Linq;
using Mxm.Core;

public static class NativePendingCapitalGateChecks
{
    public static void Run(Action<bool,string> check)
    {
        var none=Array.Empty<NativePendingCapitalGate.Commitment>();
        NativePendingCapitalGate.Proposal Offer(string symbol,decimal margin=80m,
            decimal min=1m,decimal step=1m,decimal risk=1m)=>
            new(symbol,"GROUP_A",min,step,100m,margin,risk);
        NativePendingCapitalGate.Commitment Reserve(string id,string sym,bool pending)=>
            new(id,sym,1m,80m,1m,"GROUP_A",pending);
        var first=NativePendingCapitalGate.Assess(300m,true,none,none,
            Offer("A"));
        check(first.IsFinanceable && first.Units>=1m &&
            first.ReservedMarginAfterEur<=210m,"PAV1 initial legal volume");
        var pendingA=new[]{Reserve("a","A",true)};
        var second=NativePendingCapitalGate.Assess(300m,true,none,pendingA,
            Offer("B"));
        check(second.IsFinanceable&&second.HeldMarginEur==0m&&
            second.PendingOpenMarginEur==80m &&
            second.ReservedMarginAfterEur<=210m,
            "PAV1 pending OPEN reserved before any fills");
        var pendingAB=new[]{Reserve("a","A",true),Reserve("b","B",true)};
        var third=NativePendingCapitalGate.Assess(300m,true,none,pendingAB,
            Offer("C"));
        check(!third.IsFinanceable&&third.Status=="PENDING_PLUS_HELD_MARGIN_CAP",
            "PAV1 concurrent third request cannot exceed 70 percent");
        check(NativePendingCapitalGate.RevalidatePendingFill(300m,true,none,
            pendingAB,"a")&&
            !NativePendingCapitalGate.RevalidatePendingFill(200m,true,none,
            pendingAB,"a"),"PAV1 fill revalidates shrinking equity");
        var heldA=new[]{Reserve("a","A",false)};
        var pendingB=new[]{Reserve("b","B",true)};
        var afterFill=NativePendingCapitalGate.Assess(300m,true,heldA,
            pendingB,Offer("C"));
        check(!afterFill.IsFinanceable&&
            afterFill.HeldMarginEur==80m&&
            afterFill.PendingOpenMarginEur==80m,
            "PAV1 open fill transitions reservation exactly once");
        var afterExpire=NativePendingCapitalGate.Assess(300m,true,heldA,
            none,Offer("C"));
        check(afterExpire.IsFinanceable,
            "PAV1 explicit expiry releases pending but NOT held");
        // A requested CLOSE/REDUCE is not included in pendingOpen, but A
        // remains fully HELD until positive close-fill evidence.
        var pendingC=new[]{Reserve("c","C",true)};
        var closeRequested=NativePendingCapitalGate.Assess(300m,true,heldA,
            pendingC,Offer("D"));
        check(!closeRequested.IsFinanceable,
            "PAV1 REQUEST_CLOSE cannot release held margin pre-fill");
        var missing=NativePendingCapitalGate.Assess(null,false,none,none,
            Offer("A"));
        check(!missing.IsFinanceable &&
            missing.Status=="MISSING_CURRENT_LIQUIDATION_MARK",
            "PAV1 unknown mark fails closed");
        var unaffordable=NativePendingCapitalGate.Assess(300m,true,none,none,
            Offer("A",margin:220m));
        check(!unaffordable.IsFinanceable,
            "PAV1 broker minimum above 70 percent cannot be underfunded");
        var step=NativePendingCapitalGate.Assess(300m,true,none,none,
            Offer("A",margin:1m,min:3m,step:2m,risk:.02m));
        check(step.IsFinanceable && step.Units>=3m &&
            (step.Units-3m)%2m==0m && step.Units<=100m,
            "PAV1 legal volume rounds down minimum plus step grid");
        var riskCap=NativePendingCapitalGate.Assess(300m,true,none,none,
            Offer("A",margin:1m,risk:10m));
        check(!riskCap.IsFinanceable &&
            riskCap.Status=="PENDING_PLUS_HELD_STOP_CAP",
            "PAV1 stop-to-liquidation risk cannot exceed trade budget");
    }
}