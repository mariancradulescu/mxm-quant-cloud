using System.Text.Json;
namespace Mxm.Core;

// Frozen before authentic outcomes. Shared net6 native code; no trading API.
public static class IntradayReversalNet
{
    public const string Id="EURUSD_M15_HOURLY_SHOCK_REVERSAL_V1_20261103";
    public record Bar(long T,decimal O,decimal H,decimal L,decimal C);
    public record Proposal(long Entry,long Exit,int Direction,decimal AdverseBid);
    public static Bar[] Bars(JsonElement root) => root.GetProperty("bars").EnumerateArray()
        .Select(b=>new Bar(b.GetProperty("t").GetInt64(),b.GetProperty("o").GetDecimal()/100000m,
            b.GetProperty("h").GetDecimal()/100000m,b.GetProperty("l").GetDecimal()/100000m,
            b.GetProperty("c").GetDecimal()/100000m)).OrderBy(b=>b.T).ToArray();
    public static Proposal[] Propose(Bar[] bars)
    {
        if(bars.Select(b=>b.T).Distinct().Count()!=bars.Length || bars.Any(b=>b.L<=0 || b.H<b.L || b.O<b.L || b.O>b.H || b.C<b.L || b.C>b.H))
            throw new ArgumentException("INVALID_BARS");
        var result=new List<Proposal>();
        for(int i=16;i+4<bars.Length;i++)
        {
            long t=bars[i].T;
            var clock=DateTimeOffset.FromUnixTimeMilliseconds(t);
            if(clock.Minute!=0 || !new[]{6,8,10,12,14,16}.Contains(clock.Hour) || clock.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday) continue;
            if(Enumerable.Range(i-16,21).Any(j=>bars[j].T!=t+(j-i)*900000L))continue;
            decimal range=bars.Skip(i-16).Take(16).Average(b=>b.H-b.L);
            decimal shock=bars[i-1].C-bars[i-4].O;
            if(range<=0 || Math.Abs(shock)<range || shock==0)continue;
            int direction=shock>0?-1:1;
            var hold=bars.Skip(i).Take(4);
            result.Add(new(t,t+3600000,direction,direction>0?hold.Min(b=>b.L):hold.Max(b=>b.H)));
        }
        return result.ToArray();
    }
    static decimal D(JsonElement e,string k)=>e.GetProperty(k).GetDecimal();
    static decimal ConvertUsd(decimal value,decimal bid,decimal ask)=>value>=0?value/ask:value/bid;
    // Quote: first reconstructed, noncrossed, both-sides-observed state after intended time.
    static (decimal bid,decimal ask)? Quote(JsonElement root,long time)
    {
        if(!root.GetProperty("quotes").TryGetProperty(time.ToString(),out var q) || q.ValueKind==JsonValueKind.Null)return null;
        if(q.GetProperty("time").GetInt64()<time || q.GetProperty("time").GetInt64()>time+10000)return null;
        decimal bid=D(q,"bid")/100000m,ask=D(q,"ask")/100000m;
        return bid>0 && ask>=bid?(bid,ask):null;
    }
    public static object Assess(JsonElement root)
    {
        if(root.GetProperty("schema").GetString()!="mxm-intraday-net-v1" || !root.GetProperty("readOnly").GetBoolean())throw new ArgumentException();
        var bars=Bars(root); var proposals=Propose(bars); var c=root.GetProperty("contract");
        decimal units=D(c,"minVolume")/100m, step=D(c,"stepVolume")/100m;
        if(units<=0 || step<=0 || units>D(c,"maxVolume")/100m)throw new ArgumentException("VOLUME");
        var ct=c.GetProperty("commissionType").GetInt32();
        var minType=c.GetProperty("minCommissionType").GetInt32();
        string minAsset=c.GetProperty("minCommissionAsset").GetString()!;
        decimal rate=D(c,"preciseTradingCommissionRate"),min=D(c,"preciseMinCommission")/100000000m;
        decimal conversionRate=D(c,"pnlConversionFeeRate")/10000m;
        decimal worstSwap=Math.Max(Math.Abs(D(c,"swapLong")),Math.Abs(D(c,"swapShort")));
        int swapType=c.GetProperty("swapCalculationType").GetInt32();
        if(swapType is not 0 and not 1)throw new ArgumentException("SWAP_METHOD");
        decimal lot=D(c,"lotSize")/100m;
        if(rate<0 || min<0 || conversionRate<0 || lot<=0 || ct<1 || ct>4 || minType<1 || minType>2 || (minAsset!="USD" && minAsset!="EUR"))throw new ArgumentException("COST_CONTRACT");
        decimal leverage=D(root,"conservativeLeverage");
        if(leverage<=0)throw new ArgumentException("LEVERAGE");
        decimal margin=Math.Max(units/leverage,D(root,"currentMarginEur"));
        decimal Commission(decimal price,decimal bid,decimal ask)
        {
            decimal usd=ct switch {1=>rate/100000000m*units*price/1000000m,
                2 or 4=>rate/100000000m*units/lot,
                3=>rate/100000m/100m*units*price,_=>throw new ArgumentException()};
            decimal floorUsd=minAsset=="EUR" && minType==1?min*ask:min;
            return Math.Max(usd,floorUsd)/bid; // conservative USD debit conversion
        }
        var scenarios=new List<object>();
        foreach(decimal slipPips in new[]{0.25m,1m,2m})
        {
            decimal equity=200m,peak=200m,maxDd=0,grossSum=0,spreadSum=0,commissionSum=0,slippageSum=0,fxSum=0,financingSum=0;
            int missing=0,blocked=0,completed=0; var netRows=new List<(long t,decimal net)>();
            var weeks=new Dictionary<string,int>(); var slices=new decimal[3];
            long start=root.GetProperty("start").GetInt64(),end=root.GetProperty("end").GetInt64();
            foreach(var p in proposals)
            {
                var en=Quote(root,p.Entry); var ex=Quote(root,p.Exit);
                if(en==null || ex==null){missing++;continue;}
                var (eb,ea)=en.Value;var (xb,xa)=ex.Value;
                // Stop adding exposure on breached drawdown or unavailable funded stress reserve.
                decimal reserve=units*0.002m/Math.Min(eb,xb)+4m; // disclosed 20-pip gap scenario, not guarantee
                if(maxDd>=0.30m || margin+reserve>=equity){blocked++;continue;}
                decimal midEntry=(eb+ea)/2m,midExit=(xb+xa)/2m;
                decimal gross=ConvertUsd(p.Direction*units*(midExit-midEntry),xb,xa);
                decimal actual=ConvertUsd(p.Direction*units*((p.Direction>0?xb:xa)-(p.Direction>0?ea:eb)),xb,xa);
                decimal spread=gross-actual;
                decimal commission=Commission(p.Direction>0?ea:eb,eb,ea)+Commission(p.Direction>0?xb:xa,xb,xa);
                decimal slip=2m*slipPips*0.0001m*units/Math.Min(eb,xb);
                decimal fx=Math.Abs(actual)*conversionRate;
                // Conservative one-day carry reserve EACH episode; avoids inventing a
                // historical zero financing schedule from today's contract.
                decimal finance=swapType==0 ? worstSwap*0.0001m*units/Math.Min(eb,xb)
                    : worstSwap/100m/360m*units*Math.Max(ea,xa)/Math.Min(eb,xb);
                decimal net=actual-commission-slip-fx-finance;
                decimal excursion=p.Direction>0?units*Math.Max(0,ea-p.AdverseBid)/Math.Min(eb,xb):units*Math.Max(0,p.AdverseBid+(xa-xb)-eb)/Math.Min(eb,xb);
                maxDd=Math.Max(maxDd,(peak-(equity-excursion-commission-slip-fx-finance))/peak);
                grossSum+=gross;spreadSum+=spread;commissionSum+=commission;slippageSum+=slip;fxSum+=fx;financingSum+=finance;
                equity+=net;peak=Math.Max(peak,equity);maxDd=Math.Max(maxDd,(peak-equity)/peak);
                completed++;netRows.Add((p.Exit,net));
                int slice=(p.Entry-start)*10/(end-start)<6?0:(p.Entry-start)*10/(end-start)<8?1:2;
                slices[slice]+=net;
                var day=DateTimeOffset.FromUnixTimeMilliseconds(p.Exit).UtcDateTime;
                string week=$"{System.Globalization.ISOWeek.GetYear(day)}-{System.Globalization.ISOWeek.GetWeekOfYear(day):00}";
                weeks[week]=weeks.GetValueOrDefault(week)+1;
            }
            // Eligible weeks are every complete Mon-Fri calendar week in predeclared source span,
            // including weeks with zero signals or blocked/missing episodes.
            var eligible=new List<string>();
            var first=DateTimeOffset.FromUnixTimeMilliseconds(start).UtcDateTime.Date;
            var last=DateTimeOffset.FromUnixTimeMilliseconds(end).UtcDateTime.Date;
            for(var d=first;d.AddDays(5)<=last;d=d.AddDays(1))if(d.DayOfWeek==DayOfWeek.Monday)
                eligible.Add($"{System.Globalization.ISOWeek.GetYear(d)}-{System.Globalization.ISOWeek.GetWeekOfYear(d):00}");
            var weekly=eligible.Select(w=>netRows.Where(x=> {
                var d=DateTimeOffset.FromUnixTimeMilliseconds(x.t).UtcDateTime;
                return $"{System.Globalization.ISOWeek.GetYear(d)}-{System.Globalization.ISOWeek.GetWeekOfYear(d):00}"==w;
            }).Sum(x=>x.net)).ToArray();
            decimal mean=weekly.Length>0?weekly.Average():0;
            double se=weekly.Length>1?Math.Sqrt(weekly.Sum(x=>(double)((x-mean)*(x-mean)))/(weekly.Length-1)/weekly.Length):double.NaN;
            scenarios.Add(new {slippagePipsPerSide=slipPips,completeModeledRoundTrips=completed,missingEventQuotes=missing,
                fundedOrDrawdownBlocked=blocked,grossEur=grossSum,spreadCostEur=spreadSum,commissionEur=commissionSum,
                slippageEur=slippageSum,conversionFeeEur=fxSum,financingEur=financingSum,
                totalCostEur=spreadSum+commissionSum+slippageSum+fxSum+financingSum,netEur=equity-200m,netBeforeConservativeDailyCarryReserveEur=equity-200m+financingSum,endingEquityEur=equity,
                modeledPeakToTroughWithBarExcursion=maxDd,eligibleWeeks=eligible.Count,
                weeksWith21ModeledRoundTrips=eligible.Count(w=>weeks.GetValueOrDefault(w)>=21),
                minimumModeledRoundTripsEligibleWeek=eligible.Count>0?eligible.Min(w=>weeks.GetValueOrDefault(w)):0,
                chronological60_20_20NetEur=slices,weeklyMeanNetEur=mean,
                weeklyMeanApprox95LowerEur=double.IsNaN(se)?null:(decimal?)(mean-(decimal)(1.96*se)),
                verdict=completed==0?"INSUFFICIENT_PRICED_EPISODES":equity<=200m?"REJECTED_NET_NONPOSITIVE_NO_RETUNING":"POSITIVE_CONDITIONAL_DEVELOPMENT_ONLY"});
        }
        return new {schema="mxm-intraday-net-public-v1",model=Id,sourceBars=bars.Length,
            sourceSpanDays=(bars.Last().T-bars.First().T)/86400000m,proposals=proposals.Length,
            minUnits=units,stepUnits=step,marginScenarioEur=margin,conservativeLeverage=leverage,
            scenarios,ordersSubmitted=0,independentConfirmation=false,cloudCertified=false,
            historicMarginScheduleProven=false,historicCommissionScheduleProven=false,
            continuousTickDrawdownProven=false,fullyFundedExecutionProven=false,
            financingBasis="One worst-direction broker daily swap reserved per hourly episode despite planned intraday closure; historical schedule not proven",
            qualification="CONDITIONAL_QUOTE_SIMULATION_NOT_REAL_FILLS; ALL_NONPOSITIVE_CONFIGURATIONS_CLOSED"};
    }
}
