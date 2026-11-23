using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Mxm.Core;

// RVC1 synthetic-only SOURCE->H1/M15->PAIR->Pending->two OPEN_FILL->
// shared risk/equity -> two CLOSE_FILL->one COMPLETE pair, not profit evidence.
public static class NativeRvc1JointResidualChecks
{
    const long H1=3600000L,M15=900000L,M5=300000L;
    const long Start=1777852800000L;
    static V32Bar Bar(long at,decimal price,decimal spread,long volume=100)
        => new(at,price,price+spread,price-spread,price,volume);
    static V32Terms Terms(string symbol)=>new(symbol,"USD",
        1000m,1000m,1000m,100000m,2,0L,2,0L,
        null,0,0,0m,0m,4,24,0,3,20m,.1m,1793577600000L,false);
    static V32Tape Synthetic(bool removeSecondMarketClose=false)
    {
        long signal=Start+50*H1;
        var aH=new List<V32Bar>();var bH=new List<V32Bar>();
        for(int i=0;i<54;i++)
        {
            decimal close=i%2==0?1.10025m:1.09975m;
            aH.Add(Bar(Start+i*H1,close,.0005m));
            bH.Add(Bar(Start+i*H1,1.3000m,.0005m));
        }
        var a15=new[]{
            Bar(signal-2*M15,1.10000m,.0008m),
            Bar(signal-M15,1.10047m,.0008m),
            Bar(signal,1.09980m,.0008m)
        };
        var b15=new[]{
            Bar(signal-2*M15,1.3000m,.0008m),
            Bar(signal-M15,1.3000m,.0008m),
            Bar(signal,1.3000m,.0008m)
        };
        long[] times={signal,signal+M5,signal+2*M5,
            signal+3*M5,signal+4*M5};
        decimal[] prices={1.10050m,1.10050m,1.10038m,1.09995m,1.09980m};
        var a5=times.Select((x,i)=>Bar(x,prices[i],.0002m)).ToArray();
        var b5=times.Select(x=>Bar(x,1.3000m,.0002m)).ToArray();
        if(removeSecondMarketClose)b5=b5.Where(x=>x.OpenAt!=signal+4*M5).ToArray();
        return new V32Tape(new[]{"SYNTHETIC_ONLY"},"TEST_NOT_BROKER_SOURCE",
            "SYNTHETIC_TEST",true,new[]{
                new V32Market("EURUSD",Terms("EURUSD"),new Dictionary<string,V32Bar[]>{
                    ["H1"]=aH.ToArray(),["M15"]=a15,["M5"]=a5}),
                new V32Market("GBPUSD",Terms("GBPUSD"),new Dictionary<string,V32Bar[]>{
                    ["H1"]=bH.ToArray(),["M15"]=b15,["M5"]=b5})
            });
    }
    static JsonElement Policy(JsonElement root,string name,decimal factor)=>
        root.GetProperty("Books").EnumerateArray().Single(x=>
            x.GetProperty("Policy").GetString()==name&&
            x.GetProperty("Factor").GetDecimal()==factor);
    public static void Run(Action<bool,string> check)
    {
        using var d=JsonDocument.Parse(JsonSerializer.Serialize(
            NativeRvc1JointResidualEconomic.Evaluate(
                Synthetic(),new string('b',64))));
        var root=d.RootElement;
        check(root.GetProperty("Books").GetArrayLength()==12 &&
            root.GetProperty("BrokerOrders").GetInt32()==0 &&
            root.GetProperty("IndependentConfirmation").GetBoolean()==false,
            "RVC1 4 separate EUR300 policies x3 frictions, no broker/independence certificate");
        var full=Policy(root,"JOINT_RESIDUAL",1m);
        check(full.GetProperty("FinancedPairs").GetInt32()==1 &&
            full.GetProperty("CompletePairs").GetInt32()==1 &&
            full.GetProperty("CompleteLegs").GetInt32()==2 &&
            full.GetProperty("FinalOpenPositions").GetInt32()==0 &&
            full.GetProperty("FinalPendingIntents").GetInt32()==0,
            "RVC1 simulated pair submits both, commits both, exits both and counts ONE pair");
        check(full.GetProperty("ClosingCashEur").GetDecimal() ==
            300m+full.GetProperty("ClosedNetEUR").GetDecimal() &&
            full.GetProperty("PeakHeldPendingMarginEur").GetDecimal()>0m &&
            full.GetProperty("PeakHeldPendingMarginEur").GetDecimal()<210m &&
            full.GetProperty("PeakHeldPendingStopRiskEur").GetDecimal()>0m &&
            full.GetProperty("EventChainSha256").GetString()!.Length==64,
            "RVC1 complete native cash/Held+Pending/margin/risk/event-chain witness");
        var control=Policy(root,"PAIRED_NO_CONVERGENCE",1m);
        check(control.GetProperty("CompletePairs").GetInt32()==0 &&
            control.GetProperty("FinalOpenPositions").GetInt32()==2,
            "RVC1 paired no-convergence benchmark retains funded exposures and cannot invent exit");
        var cash=Policy(root,"CASH",1.5m);
        check(cash.GetProperty("ClosedNetEUR").GetDecimal()==0m&&
            cash.GetProperty("ClosingCashEur").GetDecimal()==300m,
            "RVC1 CASH never earns synthetic returns");
        using var dMissing=JsonDocument.Parse(JsonSerializer.Serialize(
            NativeRvc1JointResidualEconomic.Evaluate(
                Synthetic(removeSecondMarketClose:true),new string('b',64))));
        var missing=Policy(dMissing.RootElement,"JOINT_RESIDUAL",1m);
        check(missing.GetProperty("CompletePairs").GetInt32()==0 &&
            missing.GetProperty("FinalOpenPositions").GetInt32()==2 &&
            missing.GetProperty("Incomplete").GetBoolean(),
            "RVC1 unilateral missing genuine market forbids filled close and claims unknown");
    }
}
