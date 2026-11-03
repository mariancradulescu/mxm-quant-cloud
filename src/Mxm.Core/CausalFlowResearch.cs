using System.Text.Json;
namespace Mxm.Core;

public static class CausalFlowResearch
{
    public const string Session="GBPUSD_TRAINED_CALENDAR_FLOW_V1";
    public const string Relative="AUDUSD_CROSS_CURRENCY_RESPONSE_V1";
    public record Candle(long T,decimal O,decimal H,decimal L,decimal C);
    public record Plan(string Model,string Symbol,long Entry,long Exit,int Direction,decimal StopDistance,
        decimal TargetDistance,decimal ForecastPrice,decimal ReferencePrice,decimal AssumedStopPrice,int Trigger,
        decimal AdverseBid,decimal FavorableBid);
    public record Fit(Dictionary<int,decimal> Hours,decimal Intercept,decimal Slope,int SessionExamples,int RelativeExamples);
    static decimal D(JsonElement e,string k)=>e.GetProperty(k).GetDecimal();
    public static Dictionary<string,Candle[]> Bars(JsonElement r)
    {
        var result=r.GetProperty("bars").EnumerateObject().ToDictionary(p=>p.Name,p=>p.Value.EnumerateArray()
            .Select(b=>new Candle(b.GetProperty("t").GetInt64(),D(b,"o")/100000m,D(b,"h")/100000m,D(b,"l")/100000m,D(b,"c")/100000m)).OrderBy(b=>b.T).ToArray());
        long start=r.GetProperty("start").GetInt64(),end=r.GetProperty("end").GetInt64();
        foreach(var rows in result.Values)
            if(rows.Length<2 || rows.Select(b=>b.T).Distinct().Count()!=rows.Length || rows.Any(b=>b.T<start || b.T+900000>end || b.L<=0 || b.H<b.L || b.O<b.L || b.O>b.H || b.C<b.L || b.C>b.H) || rows.Last().T+900000-rows.First().T<365L*86400000)
                throw new ArgumentException("AUTHENTIC_YEAR_GEOMETRY");
        return result;
    }
    static bool Supported(Candle[] b,int i,int prior,int future)=>i>=prior && i+future<b.Length && Enumerable.Range(i-prior,prior+future+1).All(j=>b[j].T==b[i].T+(j-i)*900000L);
    static bool Slot(long t,int kind){var d=DateTimeOffset.FromUnixTimeMilliseconds(t);return d.DayOfWeek is not DayOfWeek.Saturday and not DayOfWeek.Sunday && d.Minute==0 && (kind==0?d.Hour>=6&&d.Hour<=17:new[]{6,9,12,15}.Contains(d.Hour));}
    public static Fit Train(JsonElement r)
    {
        var bs=Bars(r);var g=bs["GBPUSD"];var a=bs["AUDUSD"];var gd=g.ToDictionary(b=>b.T);long start=r.GetProperty("start").GetInt64(),end=r.GetProperty("end").GetInt64(),cut=start+(end-start)*6/10;
        var hours=new Dictionary<int,List<decimal>>();var xy=new List<(decimal x,decimal y)>();int n=0;
        for(int i=96;i+8<g.Length;i++)if(Supported(g,i,96,3)&&Slot(g[i].T,0)&&g[i+2].T+900000<cut)
        {
            int h=DateTimeOffset.FromUnixTimeMilliseconds(g[i].T).Hour;
            if(!hours.ContainsKey(h))hours[h]=new();hours[h].Add(g[i+2].C-g[i].O);n++;
        }
        for(int i=96;i+8<a.Length;i++)if(Supported(a,i,96,8)&&Slot(a[i].T,1)&&a[i+7].T+900000<cut && gd.ContainsKey(a[i].T-900000)&&gd.ContainsKey(a[i].T-96*900000L))
        {
            decimal x=(gd[a[i].T-900000].C/gd[a[i].T-96*900000L].O-1m)-(a[i-1].C/a[i-96].O-1m);
            xy.Add((x,a[i+7].C/a[i].O-1m));
        }
        if(n<100 || xy.Count<100)throw new ArgumentException("TRAINING_SUPPORT");
        decimal mx=xy.Average(p=>p.x),my=xy.Average(p=>p.y),v=xy.Sum(p=>(p.x-mx)*(p.x-mx));
        decimal slope=v>0?xy.Sum(p=>(p.x-mx)*(p.y-my))/v:0m;
        // Fixed shrinkage, not selected after economic outcomes.
        slope*=xy.Count/(xy.Count+100m);
        return new(hours.ToDictionary(p=>p.Key,p=>p.Value.Count>=20?p.Value.Average()*p.Value.Count/(p.Value.Count+20m):0m),my-slope*mx,slope,n,xy.Count);
    }
    public static Plan[] Propose(JsonElement r,bool confirmation=false)
    {
        var bs=Bars(r);var fit=Train(r);var gd=bs["GBPUSD"].ToDictionary(b=>b.T);
        long start=r.GetProperty("start").GetInt64(),end=r.GetProperty("end").GetInt64();
        long lo=start+(end-start)*(confirmation?8:6)/10,hi=confirmation?end:start+(end-start)*8/10;
        var result=new List<Plan>();
        foreach(var pair in new[]{(Session,"GBPUSD",0,3),(Relative,"AUDUSD",1,8)})
        {
            var (id,symbol,kind,hold)=pair;var bars=bs[symbol];var terms=new BrokerQuoteNet(r.GetProperty("contracts").GetProperty(symbol));
            for(int i=96;i+hold<bars.Length;i++)
            {
                var b=bars[i];if(b.T<lo || b.T+hold*900000>=hi || !Slot(b.T,kind) || !Supported(bars,i,96,hold))continue;
                decimal known=bars[i-1].C;
                decimal forecast;
                if(kind==0)forecast=fit.Hours.GetValueOrDefault(DateTimeOffset.FromUnixTimeMilliseconds(b.T).Hour);
                else
                {
                    if(!gd.ContainsKey(b.T-900000)||!gd.ContainsKey(b.T-96*900000L))continue;
                    decimal x=gd[b.T-900000].C/gd[b.T-96*900000L].O-1m-(bars[i-1].C/bars[i-96].O-1m);
                    forecast=(fit.Intercept+fit.Slope*x)*known;
                }
                // Broker minimum monetary cost converted back to quote-price per unit;
                // include 0.25 pip per-side slippage and 0.5 pip spread/uncertainty buffer.
                decimal cost=2m*terms.CommissionUsd(terms.Min,known,D(r,"screenEurAsk"))/terms.Min+terms.CarryReserveUsd(terms.Min,known)/terms.Min+0.0001m;
                if(Math.Abs(forecast)<=cost)continue;
                int sign=forecast>0?1:-1;
                decimal range=bars.Skip(i-16).Take(16).Average(x=>x.H-x.L);
                decimal stop=Math.Max(2m*range,terms.MinimumStop(known)),target=Math.Max(2m*stop,terms.MinimumTarget(known));
                if(stop<=0)continue;
                // OHLC-triggered defensive exit at completed trigger bar, using actual
                // subsequent quote. It is a delayed software stop, never an invented fill.
                long exit=b.T+hold*900000L;int trigger=0;decimal assumed=0;
                int last=i+hold-1;
                for(int j=i;j<i+hold;j++)
                {
                    bool sl=sign>0?bars[j].L<=known-stop:bars[j].H>=known+stop;
                    bool tp=sign>0?bars[j].H>=known+target:bars[j].L<=known-target;
                    if(sl||tp){exit=bars[j].T+900000;trigger=sl?-1:1;assumed=known+sign*(sl?-stop:target);last=j;break;}
                }
                var held=bars.Skip(i).Take(last-i+1);
                result.Add(new(id,symbol,b.T,exit,sign,stop,target,forecast,known,assumed,trigger,
                    sign>0?held.Min(x=>x.L):held.Max(x=>x.H),sign>0?held.Max(x=>x.H):held.Min(x=>x.L)));
            }
        }
        return result.OrderBy(p=>p.Entry).ThenBy(p=>p.Model,StringComparer.Ordinal).ToArray();
    }
    static (decimal bid,decimal ask)? Quote(JsonElement r,string symbol,long t)
    {
        if(!r.GetProperty("quotes").TryGetProperty(symbol+":"+t,out var q)||q.ValueKind==JsonValueKind.Null)return null;
        long stamp=q.GetProperty("time").GetInt64();decimal bid=D(q,"bid")/100000m,ask=D(q,"ask")/100000m;
        return stamp>=t && stamp<=t+10000 && bid>0 && ask>=bid?(bid,ask):null;
    }
    public static object Evaluate(JsonElement r,bool confirmation=false)
    {
        if(r.GetProperty("schema").GetString()!="mxm-flow-net-v1"||!r.GetProperty("readOnly").GetBoolean()||r.GetProperty("source").GetString()!="Pepperstone-cTrader-OpenAPI")throw new ArgumentException("SOURCE_BINDING");
        var plans=Propose(r,confirmation);long start=r.GetProperty("start").GetInt64(),end=r.GetProperty("end").GetInt64();
        long lo=start+(end-start)*(confirmation?8:6)/10,hi=confirmation?end:start+(end-start)*8/10;
        var results=new List<object>();var survivors=new List<string>();
        var eligible=new List<string>();
        for(var d=DateTimeOffset.FromUnixTimeMilliseconds(lo).UtcDateTime.Date;d.AddDays(5)<=DateTimeOffset.FromUnixTimeMilliseconds(hi).UtcDateTime.Date;d=d.AddDays(1))
            if(d.DayOfWeek==DayOfWeek.Monday)eligible.Add($"{System.Globalization.ISOWeek.GetYear(d)}-{System.Globalization.ISOWeek.GetWeekOfYear(d):00}");
        var allowed=confirmation?r.GetProperty("selectionSurvivors").EnumerateArray().Select(x=>x.GetString()).ToHashSet():new HashSet<string?>{Session,Relative};
        foreach(var id in new[]{Session,Relative}.Where(x=>allowed.Contains(x)))
        {
            var source=plans.Where(p=>p.Model==id).ToArray();var scenarios=new List<object>();bool allPass=true;
            string symbol=id==Session?"GBPUSD":"AUDUSD";var terms=new BrokerQuoteNet(r.GetProperty("contracts").GetProperty(symbol));
            foreach(decimal slipPips in new[]{.25m,1m,2m})
            {
                decimal equity=200,peak=200,dd=0,gross=0,spread=0,commission=0,slippage=0,carry=0,fx=0;
                int completed=0,missing=0,blocked=0,overlap=0,stressExceeded=0;long lastExit=0;
                decimal maxUnits=0,maxMargin=0,maxAdmittedStressDd=0;var rows=new List<(string week,decimal net)>();
                foreach(var p in source)
                {
                    if(p.Entry<lastExit){overlap++;continue;}
                    var eq=Quote(r,p.Symbol,p.Entry);var xq=Quote(r,p.Symbol,p.Exit);var ef=Quote(r,"EURUSD",p.Entry);var xf=Quote(r,"EURUSD",p.Exit);
                    if(eq==null||xq==null||ef==null||xf==null){missing++;continue;}
                    var (eb,ea)=eq.Value;var (xb,xa)=xq.Value;var (fb,fa)=ef.Value;var (zbid,zask)=xf.Value;
                    decimal stop=p.StopDistance+Math.Abs((p.Direction>0?ea:eb)-p.ReferencePrice);
                    decimal gap=.002m,spreadStress=Math.Max(.0002m,3*(ea-eb)),currencyFloor=fb*.98m;
                    decimal unitCost=(2*terms.CommissionUsd(terms.Min,Math.Max(ea,eb)+p.TargetDistance+gap,fa)/terms.Min+
                        terms.CarryReserveUsd(terms.Min,Math.Max(ea,eb)+p.TargetDistance+gap)/terms.Min+(stop+gap)*terms.FxFeeRate)/currencyFloor;
                    decimal marginPerUnit=Math.Max(D(r.GetProperty("margins"),symbol)/terms.Min,Math.Max(ea,eb)/fb/D(r.GetProperty("leverage"),symbol));
                    var sizing=PreventiveExecutionRisk.Size(equity,peak,equity,Array.Empty<ReservedPositionRisk>(),
                        new(terms.Min,terms.Step,terms.Max,stop,p.TargetDistance,terms.MinimumStop(p.ReferencePrice),gap,.0004m,spreadStress,
                            1m/currencyFloor,unitCost,0,marginPerUnit,true,true));
                    if(sizing.Units<=0){blocked++;continue;}
                    decimal units=sizing.Units;
                    decimal actualUsd=p.Direction*units*((p.Direction>0?xb:xa)-(p.Direction>0?ea:eb));
                    decimal midUsd=p.Direction*units*((xb+xa-eb-ea)/2m);
                    decimal g=BrokerQuoteNet.Eur(midUsd,zbid,zask),quoted=BrokerQuoteNet.Eur(actualUsd,zbid,zask);
                    decimal comm=terms.CommissionUsd(units,p.Direction>0?ea:eb,fa)/fb+terms.CommissionUsd(units,p.Direction>0?xb:xa,zask)/zbid;
                    decimal slip=2*slipPips*.0001m*units/Math.Min(fb,zbid),finance=terms.CarryReserveUsd(units,Math.Max(ea,xa))/Math.Min(fb,zbid);
                    decimal convert=Math.Abs(quoted)*terms.FxFeeRate,cost=g-quoted+comm+slip+finance+convert,net=g-cost;
                    decimal adverse=units*Math.Max(0,p.Direction>0?ea-p.AdverseBid:p.AdverseBid+Math.Max(xa-xb,ea-eb)-eb)/Math.Min(fb,zbid);
                    decimal favorable=units*Math.Max(0,p.Direction*(p.FavorableBid-(p.Direction>0?ea:eb)))/Math.Min(fb,zbid);
                    peak=Math.Max(peak,equity+favorable);
                    dd=Math.Max(dd,1m-(equity-adverse-comm-slip-finance-convert)/peak);
                    if(zbid<currencyFloor || xa-xb>spreadStress || adverse+comm+slip+finance+convert>sizing.StressLossEur || peak>sizing.StressPeakEur)stressExceeded++;
                    equity+=net;peak=Math.Max(peak,equity);dd=Math.Max(dd,1m-equity/peak);
                    gross+=g;spread+=g-quoted;commission+=comm;slippage+=slip;carry+=finance;fx+=convert;
                    maxUnits=Math.Max(maxUnits,units);maxMargin=Math.Max(maxMargin,sizing.MarginEur);maxAdmittedStressDd=Math.Max(maxAdmittedStressDd,sizing.StressDrawdown);
                    completed++;lastExit=p.Exit;
                    var d=DateTimeOffset.FromUnixTimeMilliseconds(p.Exit).UtcDateTime;
                    rows.Add(($"{System.Globalization.ISOWeek.GetYear(d)}-{System.Globalization.ISOWeek.GetWeekOfYear(d):00}",net));
                }
                var weekly=eligible.Select(w=>rows.Where(x=>x.week==w).Sum(x=>x.net)).ToArray();
                decimal mean=weekly.Length>0?weekly.Average():0;
                double se=weekly.Length>1?Math.Sqrt(weekly.Sum(x=>(double)((x-mean)*(x-mean)))/(weekly.Length-1)/weekly.Length):0;
                decimal lower=mean-(decimal)(1.96*se);
                bool pass=completed>=30 && missing==0 && equity>200 && lower>0 && dd<=.30m && stressExceeded==0;
                allPass&=pass;
                scenarios.Add(new{slippagePipsPerSide=slipPips,completeModeledRoundTrips=completed,missingQuotes=missing,
                    preventiveRiskBlocked=blocked,overlapBlocked=overlap,declaredStressExceeded=stressExceeded,
                    grossEur=gross,spreadEur=spread,commissionEur=commission,slippageEur=slippage,financingReserveEur=carry,conversionEur=fx,
                    totalCostEur=spread+commission+slippage+carry+fx,netEur=equity-200,endingEquityEur=equity,maxModeledDrawdown=dd,
                    maxAdmittedScenarioDrawdown=maxAdmittedStressDd,maxUnits,maxMarginEur=maxMargin,
                    eligibleWeeks=eligible.Count,weeksWith21ModeledRoundTrips=eligible.Count(w=>rows.Count(x=>x.week==w)>=21),
                    minimumEligibleWeekRoundTrips=eligible.Count==0?0:eligible.Min(w=>rows.Count(x=>x.week==w)),weeklyMeanNetEur=mean,weeklyMeanApprox95LowerEur=lower,
                    passesPredeclaredSelection=pass,verdict=completed==0?"NO_FUNDED_COST_ADMISSIBLE_EPISODES":equity<=200?"REJECTED_NET_NONPOSITIVE_NO_RETUNING":!pass?"REJECTED_ROBUSTNESS_OR_SUPPORT_NO_RETUNING":"POSITIVE_SCENARIO_REQUIRES_UNTOUCHED_HOLDOUT"});
            }
            if(allPass)survivors.Add(id);
            results.Add(new{model=id,symbol,proposals=source.Length,eligibleForUntouchedHoldout=allPass,scenarios});
        }
        var fit=Train(r);var allBars=Bars(r);
        return new{schema="mxm-causal-flow-net-public-v1",phase=confirmation?"CONFIRMATION":"SELECTION",
            trainingExamples=new{session=fit.SessionExamples,crossCurrency=fit.RelativeExamples},
            sourceBars=allBars.ToDictionary(p=>p.Key,p=>p.Value.Length),requestedSpanDays=(end-start)/86400000m,sourceObservedSpanDays=allBars.ToDictionary(p=>p.Key,p=>(p.Value.Last().T+900000-p.Value.First().T)/86400000m),
            phaseStart=lo,phaseEnd=hi,results,selectionSurvivors=survivors,
            confirmationEvaluated=confirmation,ordersSubmitted=0,absoluteDrawdownGuarantee=false,
            historicCostSchedulesProven=false,realFillsProven=false,independentlyQualifiedProduct=false,
            riskPolicy="PREENTRY_STOP_GAP_SLIPPAGE_SPREAD_FX_COST_MARGIN_VOLUME_STEP_AND_FAVORABLE_PEAK_STRESS",
            stopExecutionModel="COMPLETED_M15_TRIGGER_BAR_THEN_AUTHENTIC_QUOTE; SOFTWARE_DELAY_EXPLICIT; NOT_BROKER_STOP_FILL",
            financingPolicy="OBSERVED_DAILY_ROLLOVER_OUTSIDE_06_18_UTC_IMPLIES_CURRENT_SCHEDULE_NO_CARRY; OTHERWISE_THREE_WORST_DAILY_SWAPS_RESERVED; HISTORIC_SCHEDULE_UNKNOWN",
            economicQualification="CONDITIONAL_QUOTE_MODEL_ONLY"};
    }
}
