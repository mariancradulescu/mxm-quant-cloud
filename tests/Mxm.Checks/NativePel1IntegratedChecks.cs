using System;
using System.Linq;
using System.Text.Json;
using Mxm.Core;

// Integrated event-clock, source-as-of and EUR300 financial smoke proof.
// Every market and price here is SYNTHETIC, never an economic outcome.
public static class NativePel1IntegratedChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long start=1777852800000L;
        long open=start+8*60*60*1000L;
        const long five=300000L;
        var bars=Enumerable.Range(0,20).Select(k=>
        {
            long t=start+(6*60+20+5*k)*60000L;
            return new long[]{t,t+five,100000,100040,99980,99990,15};
        }).ToArray();
        long[][] bid={
            new long[]{open+4000,100000},
            new long[]{open+5200,99980},
            new long[]{open+5500,99970},
            new long[]{open+17000,100220},
            new long[]{open+22000,100220}};
        long[][] ask={
            new long[]{open+4000,100020},
            new long[]{open+5200,99990},
            new long[]{open+5500,99988},
            new long[]{open+17000,100240},
            new long[]{open+22000,100240}};
        Pel1Market Build(string symbol)
        {
            var contract=new NativeObservedContractTerms(
                symbol,"USD",start,1000m,1000m,1000m,100000m,
                2,200000000L,2,0L,null,0,
                0,0m,0m,4,24,0,3,false,0);
            return new Pel1Market(symbol,contract,33m,.00001m,
                new System.Collections.Generic.Dictionary<string,long[][]>{
                    ["M5"]=bars
                },new[]{new Pel1Day(start,bid,ask)});
        }
        var tape=new Pel1Tape(start,1785110400000L,
            new[]{Build("EURUSD"),Build("GBPUSD"),Build("AUDUSD")});
        using var proof=JsonDocument.Parse(JsonSerializer.Serialize(
            NativePel1Economic.Evaluate(tape,new string('b',64))));
        var books=proof.RootElement.GetProperty("Books").EnumerateArray().ToArray();
        check(books.Length==12 &&
            books.Count(x=>x.GetProperty("Policy").GetString()=="CASH")==3,
            "PEL1 synthetic complete native shared EUR300 counterfactual universe");
        var passive=books.Single(x=>
            x.GetProperty("Policy").GetString()=="PASSIVE" &&
            x.GetProperty("CostMultiplier").GetDecimal()==1m);
        check(passive.GetProperty("Financed").GetInt32()>0 &&
            passive.GetProperty("Completed").GetInt32()>0 &&
            passive.GetProperty("FinalFullySettled").GetBoolean() &&
            passive.GetProperty("Summary").GetProperty("CompleteRoundTrips").GetInt32()==
                passive.GetProperty("Completed").GetInt32(),
            "PEL1 integrated synthetic causal M5 -> limits -> full eventual financed closes");
        check(passive.GetProperty("MaxHeldPlusPendingEur").GetDecimal()>0m &&
            passive.GetProperty("MaxHeldPlusPendingMarginToEquity").GetDecimal()<=.70m &&
            passive.GetProperty("SampledDrawdownPercent").GetDecimal()<30m,
            "PEL1 integrated held+pending margin reservation and DD checks");
        check(proof.RootElement.GetProperty("Orders").GetInt32()==0 &&
            !proof.RootElement.GetProperty("Cloud").GetBoolean() &&
            !proof.RootElement.GetProperty("Independent").GetBoolean(),
            "PEL1 synthetics never falsely certify broker fills/cloud/independent alpha");
    }
}
