using System.Text.Json;

namespace Mxm.Core;

/// <summary>Source-only admission for new multi-timeframe Pepperstone research.
/// It never constructs trades, calculates P/L, or certifies historical independence.</summary>
public static class EconomicSourceAdmission
{
    public static object ReadReceipt(JsonElement root)
    {
        if(root.GetProperty("schema").GetString()!="mxm-econ-source-v2" ||
           root.GetProperty("source").GetString()!="Pepperstone-cTrader-OpenAPI" ||
           !root.GetProperty("readOnly").GetBoolean() ||
           !root.GetProperty("developmentDataOnly").GetBoolean())
            throw new ArgumentException("ECONOMIC_SOURCE_CONTRACT_INVALID");
        var resolution=new Dictionary<string,int>(StringComparer.Ordinal) {
            ["H4"]=240,["M15"]=15
        };
        var seen=new HashSet<(string,string,long)>();
        var counts=new Dictionary<string,int>();
        var months=new Dictionary<string,HashSet<(int,int)>>();
        var ranges=new Dictionary<string,(DateTime min,DateTime max)>();
        var end=root.GetProperty("captureEnd").GetInt64();
        foreach(var bar in root.GetProperty("bars").EnumerateArray())
        {
            var symbol=bar.GetProperty("symbol").GetString() ??
                throw new ArgumentException("SYMBOL_MISSING");
            var tf=bar.GetProperty("resolution").GetString() ??
                throw new ArgumentException("TF_MISSING");
            if(!resolution.TryGetValue(tf,out int minutes) ||
               bar.GetProperty("periodMinutes").GetInt32()!=minutes)
                throw new ArgumentException("TF_INVALID");
            var open=bar.GetProperty("openTime").GetInt64();
            var available=bar.GetProperty("availableTime").GetInt64();
            var lo=bar.GetProperty("low").GetInt64();
            var hi=bar.GetProperty("high").GetInt64();
            var o=bar.GetProperty("open").GetInt64();
            var c=bar.GetProperty("close").GetInt64();
            if(!seen.Add((symbol,tf,open)) ||
                available != open+minutes*60000L ||
                open<0 || available>end || open%60000!=0 ||
                lo<=0 || o<lo || o>hi || c<lo || c>hi ||
                bar.GetProperty("tickVolume").GetInt64()<0)
                throw new ArgumentException("ECONOMIC_BAR_CAUSALITY_FAIL");
            var dt=DateTimeOffset.FromUnixTimeMilliseconds(open).UtcDateTime;
            var key=symbol+":"+tf;
            counts[key]=counts.GetValueOrDefault(key)+1;
            if(!months.TryGetValue(key,out var set))
                months[key]=set=new HashSet<(int,int)>();
            set.Add((dt.Year,dt.Month));
            if(!ranges.TryGetValue(key,out var bounds)) ranges[key]=(dt,dt);
            else ranges[key]=(dt<bounds.min?dt:bounds.min,dt>bounds.max?dt:bounds.max);
        }
        if(seen.Count==0)throw new ArgumentException("EMPTY_AUTHENTIC_SOURCE");
        var contracts=root.GetProperty("brokerContract");
        var contractStatuses=new Dictionary<string,string>();
        foreach(var prop in contracts.EnumerateObject())
        {
            var s=prop.Value;
            bool known=s.TryGetProperty("minVolume",out var mv) && mv.ValueKind==JsonValueKind.Number &&
                mv.GetInt64()>0 &&
                s.TryGetProperty("stepVolume",out var sv) && sv.ValueKind==JsonValueKind.Number && sv.GetInt64()>0 &&
                s.TryGetProperty("lotSize",out var lot) && lot.ValueKind==JsonValueKind.Number && lot.GetInt64()>0;
            // Do not invent margin/conversion/executable spread, financing or
            // guaranteed slippage from broker contract metadata alone.
            var q=new FundedBrokerQuote(prop.Name,null,null,
               known?(decimal?)mv.GetInt64()/100m:null,null,null,null,
               null,null,null,null,true,known);
            contractStatuses[prop.Name]=FundedBrokerCostScreen.Assess(q).Status;
        }
        bool observed12=months.Any(kv=>kv.Key.EndsWith(":H4",StringComparison.Ordinal) &&
            kv.Value.Count>=12 && ranges.TryGetValue(kv.Key,out var r) &&
            r.min.AddMonths(12) <= r.max.AddDays(1));
        return new {
            schema="mxm-econ-source-native-receipt-v2",
            sourceBarCount=seen.Count,
            perResolutionBars=counts,
            observedCalendarMonths=months.ToDictionary(x=>x.Key,x=>x.Value.Count),
            twelveMonthSpanObserved=observed12,
            brokerSourceContract=contractStatuses,
            sourceStatus="AUTHENTIC_READ_ONLY_MARKET_DEVELOPMENT_NOT_NET",
            actualBidAskAndMarginMissing=true,
            brokerExecutionCostsFullyPriced=false,
            independentConfirmation=false,
            fullyFundedNet200EurProven=false,
            ordersSubmitted=0
        };
    }
}
