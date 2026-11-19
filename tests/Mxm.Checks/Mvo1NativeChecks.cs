using System;
using System.Linq;
using System.Text.Json;
using Mxm.Core;

internal static class Mvo1NativeChecks
{
    public static void Run(Action<bool,string> check)
    {
        var first=new LedgerQuote("SYNTH",90000000,99m,100m,1m,1m,0m,0m,1m);
        var hold=NativeCausalExitResearch.AssessMarginalPriceOnlyThesis(
            "RANGE_RELEASE",1,100m,1m,100m,100.5m,0m,0m,0m,0m,
            false,true,2);
        check(!hold.RequestClose && hold.Reason=="HOLD_UNKNOWN_REGIME_WAIT_REAL_OBSERVATIONS",
            "MVO1 a missing session price does not close or release the position");
        var observed=NativeCausalExitResearch.AssessMarginalPriceOnlyThesis(
            "RANGE_RELEASE",1,100m,1m,100m,98.3m,0m,0m,0m,0m,
            false,true,3);
        check(observed.RequestClose && observed.Reason=="POST_GAP_OBSERVED_PROTECTIVE_CLOSE",
            "MVO1 after a gap only a genuinely observed protective close-price breach can request a modeled exit");
        var recovery=NativeCausalExitResearch.AssessMarginalPriceOnlyThesis(
            "EXHAUSTION_REPAIR",-1,100m,1m,100m,101m,100m,100m,102m,99m,
            true,false,4);
        check(!recovery.RequestClose,
            "MVO1 intact post-gap short thesis continues to reserve its slot");

        long start=new DateTimeOffset(2025,11,24,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
        string[] names={"AUDUSD","AUS200","EURUSD","GBPUSD","GER40","JPN225",
            "NAS100","UK100","US500","USDCAD","USDJPY","XAUUSD"};
        var streams=names.Select(name=>
        {
            int impulse=name=="AUDUSD"?34:name=="AUS200"?42:-1;
            var bars=Enumerable.Range(0,66).Where(i=>!(name=="AUDUSD"&&i>=40&&i<50))
                .Select(i=>
                {
                    long p=10000000L;
                    bool wide=impulse>0&&i>=impulse-32&&i<impulse-16;
                    long h=p+(wide?100000:2000),l=p-(wide?100000:2000);
                    long open=p,close=p;
                    if(impulse>0 && i==impulse)
                    {open=p;close=p+30000;h=close+10000;l=p-10000;}
                    else if(impulse>0 && i>impulse)
                    {open=close=p+40000;h=close+2000;l=close-2000;}
                    return new Ahr1H1Bar(start+i*900000L,
                        start+(i+1)*900000L,open,h,l,close,150);
                }).ToArray();
            return new Cdh1Stream(name,"M15",bars);
        }).ToArray();
        using var result=JsonDocument.Parse(JsonSerializer.Serialize(
            NativeMarginalValueResearch.Evaluate(new Cdh1Input(
                "SYNTHETIC_MVO1_CAUSAL_GAP_TEST",new string('a',64),
                new string('b',64),streams))));
        var root=result.RootElement;
        check(root.GetProperty("SourceGapsNeverReleaseCapacity").GetBoolean() &&
            !root.GetProperty("NativeEur300FundedLedgerEvaluated").GetBoolean() &&
            root.GetProperty("RealizedBrokerNetEur").ValueKind==JsonValueKind.Null,
            "MVO1 original native Core economic scope cannot claim funded EUR300 NET from OHLCV");
        var firstBook=root.GetProperty("Results").EnumerateArray().First(x=>
            x.GetProperty("Policy").GetString()=="FIRST_ADMISSIBLE");
        var stage=firstBook.GetProperty("Stages").EnumerateArray().First();
        check(firstBook.GetProperty("OpenPositionGapOccurrences").GetInt32()>0 &&
            firstBook.GetProperty("TerminalUnresolvedModelPositions").GetInt32()>=1 &&
            stage.GetProperty("BlockedByStalePositionMark").GetInt32()>0,
            "MVO1 actual original-style source interruption keeps exposure reserved and blocks competing offer");
    }
}
