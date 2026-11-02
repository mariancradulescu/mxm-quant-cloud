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
        var quotes=new Dictionary<string,object>();
        foreach(var symbol in root.GetProperty("historicalBidAsk").EnumerateObject())
        {
            var sides=symbol.Value;
            var bid=sides.GetProperty("bid");
            var ask=sides.GetProperty("ask");
            if(!bid.GetProperty("complete").GetBoolean() ||
               !ask.GetProperty("complete").GetBoolean())
            {
                quotes[symbol.Name]=new {sampleCount=0,medianPips=(decimal?)null,
                    status="BROKER_TICK_PAGE_INCOMPLETE"};
                continue;
            }
            var bids=bid.GetProperty("rows").EnumerateArray()
                .Select(x=>(time:x[0].GetInt64(),price:x[1].GetInt64()))
                .OrderBy(x=>x.time).ToArray();
            var asks=ask.GetProperty("rows").EnumerateArray()
                .Select(x=>(time:x[0].GetInt64(),price:x[1].GetInt64()))
                .OrderBy(x=>x.time).ToArray();
            var all=new List<(long time,bool bid,long price)>();
            all.AddRange(bids.Select(x=>(x.time,true,x.price)));
            all.AddRange(asks.Select(x=>(x.time,false,x.price)));
            (long time,long price)? lastBid=null;
            (long time,long price)? lastAsk=null;
            var samples=new List<decimal>();
            int pipPosition=contracts.GetProperty(symbol.Name).GetProperty("pipPosition").ValueKind
                == JsonValueKind.Number ?
                contracts.GetProperty(symbol.Name).GetProperty("pipPosition").GetInt32() : -1;
            if(pipPosition<0 || pipPosition>5)
            {
                quotes[symbol.Name]=new {sampleCount=0,medianPips=(decimal?)null,
                    status="PIP_POSITION_NOT_CERTIFIED"};
                continue;
            }
            decimal rawUnitsPerPip=1m;
            for(int p=pipPosition;p<5;p++)rawUnitsPerPip*=10m;
            foreach(var evt in all.OrderBy(x=>x.time))
            {
                if(evt.bid)lastBid=(evt.time,evt.price);
                else lastAsk=(evt.time,evt.price);
                if(lastBid is not { } b || lastAsk is not { } a ||
                    Math.Abs(b.time-a.time)>1000 ||
                    a.price<b.price || b.price<=0)
                    continue;
                // Historical, as-of paired quotes; NOT historical fills.
                samples.Add((a.price-b.price)/rawUnitsPerPip);
            }
            samples.Sort();
            decimal? median=samples.Count==0?null:
                samples.Count%2==1?samples[samples.Count/2]:
                (samples[samples.Count/2-1]+samples[samples.Count/2])/2m;
            quotes[symbol.Name]=new {sampleCount=samples.Count,medianPips=median,
                status=samples.Count>0?
                    "ONE_MINUTE_ASOF_BROKER_QUOTES_NOT_EXECUTABLE_FILLS":
                    "NO_TIME_ALIGNED_BID_ASK_QUOTES"};
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
            genuineHistoricalBidAskQuotes=quotes,
            sourceStatus="AUTHENTIC_READ_ONLY_MARKET_DEVELOPMENT_NOT_NET",
            actualBidAskAndMarginMissing=true,
            brokerExecutionCostsFullyPriced=false,
            independentConfirmation=false,
            fullyFundedNet200EurProven=false,
            ordersSubmitted=0
        };
    }
}
