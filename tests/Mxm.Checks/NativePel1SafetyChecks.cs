using System;
using Mxm.Core;

public static class NativePel1SafetyChecks
{
    static LedgerEvent E(string id,long at,string kind,string pos,int side,decimal units,
        decimal price,decimal fee,decimal perMargin,decimal slip,LedgerQuote[] quotes,
        string reason="NATIVE_CONDITIONAL_SELECTION",long available=1000L,long latency=100L)
        =>new(id,at,kind,pos,"SYNTH",side,units,price,fee,perMargin,slip,
            available,available,latency,reason,new string('a',64),quotes);
    public static void Run(Action<bool,string> check)
    {
        const long t=1000;
        var initial=new LedgerQuote("SYNTH",t,1.000m,1.002m,1m,1m,
            .00001m,0m,1m);
        var after=new LedgerQuote("SYNTH",1300,0.998m,0.999m,1m,1m,
            .00001m,0m,1m);
        var none=Array.Empty<NativePendingCapitalGate.Commitment>();
        var p=new NativePendingCapitalGate.Commitment(
            "PE1","SYNTH",100m,1m,1m,"FX",true);
        var pre=NativePendingCapitalGate.Assess(300m,true,none,none,
            new NativePendingCapitalGate.Proposal("SYNTH","FX",
                100m,1m,100m,1m,.01m));
        check(pre.IsFinanceable && pre.Units==100m,
            "PEL1 legal EUR300 pending margin reservation");
        var projected=NativePostFillCapitalGuard.Assess(300m,none,new[]{p},
            p.PositionId,1,after,.001m);
        check(projected.Allowed && projected.TotalReservedMarginEur==100m &&
            projected.ProjectedPostFillLiquidationEquityEur<300m,
            "PEL1 actual full post-fee Held+Pending prefill guard");
        var ledger=new NativeFundedLedger(1000);
        ledger.Apply(E("M",t,"MARK","",0,0,0,0,0,0,new[]{initial}));
        ledger.Apply(E("Q",t+10,"REQUEST_OPEN","PE1",1,100m,1m,0,1m,0,
            new[]{initial}));
        check(ledger.Summary().PendingIntents==1 && ledger.Summary().OpenPositions==0,
            "PEL1 reserve remains pending before modeled fill");
        var bad=new LedgerQuote("SYNTH",1300,1.000m,1.001m,1m,1m,
            .00001m,0m,1m);
        bool crossRejected=false;
        try{
            ledger.Apply(E("NO_CROSS",1320,"MODEL_LIMIT_OPEN_FILL","PE1",
                1,100m,1m,.001m,1m,0,new[]{bad}));
        }catch(ArgumentException){crossRejected=true;}
        check(crossRejected && ledger.Summary().PendingIntents==1,
            "PEL1 limit fill rejects noncrossed genuine quote, keeps Pending");
        ledger.Apply(E("F",1320,"MODEL_LIMIT_OPEN_FILL","PE1",1,100m,
            1m,.001m,1m,.001m,new[]{after}));
        check(ledger.Summary().PendingIntents==0 && ledger.Summary().OpenPositions==1,
            "PEL1 modeled filled limit transfers Pending to Held once");
        var favorable=new LedgerQuote("SYNTH",1500,1.005m,1.006m,1m,1m,
            .00001m,0m,1m){LiquidationSlippagePerSide=.0002m};
        ledger.Apply(E("C",1510,"REQUEST_CLOSE","PE1",1,100m,0,0,0,0,
            new[]{favorable},reason:"MODEL_UNTRANSMITTED_PEL1_TARGET",available:1500));
        check(ledger.Summary().OpenPositions==1 && ledger.Summary().PendingIntents==1,
            "PEL1 CLOSE request does not release Held prematurely");
        ledger.Apply(E("X",1700,"CLOSE_FILL","PE1",1,100m,1.0048m,.001m,
            1m,0,new[]{favorable},reason:"PEL1_TARGET",available:1500)
            with {ObservedExitSlippagePerSide=.0002m});
        var z=ledger.Summary();
        check(z.OpenPositions==0 && z.PendingIntents==0 &&
            z.CompleteRoundTrips==1 && z.ClosedNetEur>0m &&
            z.CashEur==300m+z.ClosedNetEur &&
            !string.IsNullOrWhiteSpace(z.EventChainHash),
            "PEL1 genuine full Core requested funded limit -> close NET and event chain");
    }
}