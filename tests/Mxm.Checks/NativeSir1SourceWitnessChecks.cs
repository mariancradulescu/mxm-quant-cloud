using System;
using System.Linq;
using System.Text.Json;
using Mxm.Core;

// Pure SYNTHETIC native test of the separately frozen original source witness
// evaluator. Real OEI1 price source is only opened in protected one-time job.
internal static class NativeSir1SourceWitnessChecks
{
    public static void Run(Action<bool,string> check)
    {
        long[] clocks={
            new DateTimeOffset(2026,8,21,15,27,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
            new DateTimeOffset(2026,8,21,15,28,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
            new DateTimeOffset(2026,8,21,15,29,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
            new DateTimeOffset(2026,8,24,13,30,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
            new DateTimeOffset(2026,8,24,13,31,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
            new DateTimeOffset(2026,8,24,13,32,0,TimeSpan.Zero).ToUnixTimeMilliseconds()
        };
        Sir1SourceMarket Market(string name,decimal start,decimal tick)
        {
            var contract=new NativeObservedContractTerms(name,"USD",clocks[0]-1000,
                1m,1m,1m,100m,2,0,2,0,null,0,0,0m,0m,
                4,24,1320,3,false,0,true,false);
            var quotes=clocks.Select((at,i)=>{
                decimal price=start+(i>=3 ? -10m*tick : 0m);
                return new Sir1SourceQuote(at,price,price+tick,at,at);
            }).ToArray();
            return new Sir1SourceMarket(name,contract,1m,tick,quotes);
        }
        var tape=new Sir1OriginalSourceWitnessTape(new string('a',64),new[]{
            Market("EURUSD",1.1m,.0001m),Market("ETHUSD",100m,.01m),
            Market("US500",4500m,.01m),Market("SpotBrent",80m,.01m)
        });
        using var report=JsonDocument.Parse(JsonSerializer.Serialize(
            NativeSir1OriginalSourceWitness.Evaluate(tape)));
        var root=report.RootElement;
        var longBook=root.GetProperty("Long");
        var shortBook=root.GetProperty("Short");
        check(longBook.GetProperty("ModeledOpened").GetInt32()>0 &&
            shortBook.GetProperty("ModeledOpened").GetInt32()>0 &&
            longBook.GetProperty("ModelExpiredCloseIntents").GetInt32()>0 &&
            shortBook.GetProperty("ModelExpiredCloseIntents").GetInt32()>0,
            "source-shaped original witness accounts for both financed model LONG/SHORT and explicit local expiry");
        check(longBook.GetProperty("OriginalSourceBoundModelFacts").EnumerateArray()
                .Any(e=>e.GetProperty("Kind").GetString()=="MODEL_CLOSE_INTENT_EXPIRED") &&
            !longBook.GetProperty("OriginalSourceBoundModelFacts").EnumerateArray()
                .Any(e=>e.GetProperty("Kind").GetString()=="CONFIRMED_CANCEL"),
            "original-source witness trace has independently replayable model expiry without broker confirmation");
        check(root.GetProperty("CashControlInitialAndFinalEur").GetDecimal()==300m &&
            root.GetProperty("RealBrokerNetEur").ValueKind==JsonValueKind.Null &&
            !root.GetProperty("FundedSystemHard21Certified").GetBoolean(),
            "CASH comparator and original-source witness explicitly fail closed on broker NET and HARD21");
    }
}
