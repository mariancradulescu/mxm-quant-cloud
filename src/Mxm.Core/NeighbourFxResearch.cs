using System.Text.Json;
namespace Mxm.Core;

// Frozen nonparametric conditional-return model, not an inversion/retuning of closed rules.
public static class NeighbourFxResearch
{
    public record Bar(long T,decimal O,decimal H,decimal L,decimal C);
    public record Sample(double[] X,decimal Y,long Entry,decimal LowReturn,decimal HighReturn);
    public record Plan(string Symbol,long Entry,long Horizon,long Exit,int Direction,decimal Reference,
        decimal Stop,decimal Target,decimal Forecast,bool MinuteComplete,decimal Adverse,decimal Favorable);
    public record Planning(Plan[] Plans,int FeatureWindows,int NoForecast,int CostRejected,int DataMissing);
    static decimal D(JsonElement e,string k)=>e.GetProperty(k).GetDecimal();
    static long T(JsonElement e,string k)=>e.GetProperty(k).GetInt64();
    static Bar[] Decode(JsonElement e)=>e.EnumerateArray().Select(b=>new Bar(T(b,"t"),D(b,"o")/100000m,D(b,"h")/100000m,D(b,"l")/100000m,D(b,"c")/100000m)).OrderBy(b=>b.T).ToArray();
    static Dictionary<string,Bar[]> Bars(JsonElement r)
    {
        var bs=r.GetProperty("bars").EnumerateObject().ToDictionary(x=>x.Name,x=>Decode(x.Value));
        foreach(var b in bs.Values)if(b.Length<3000 || b.Select(x=>x.T).Distinct().Count()!=b.Length ||
            b.Any(x=>x.L<=0 || x.O<x.L || x.O>x.H || x.C<x.L || x.C>x.H || x.T<T(r,"start") || x.T+3600000>T(r,"end")) ||
            b.Last().T+3600000-b.First().T<365L*86400000)throw new ArgumentException("YEAR_SOURCE_GEOMETRY");
        return bs;
    }
    static bool Slot(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t);return d.DayOfWeek is not DayOfWeek.Saturday and not DayOfWeek.Sunday && d.Minute==0 && new[]{6,8,10,12,14,16}.Contains(d.Hour);}
    static double[]? Features(Bar[] b,int i)
    {
        if(i<48 || b[i-1].T+3600000!=b[i].T)return null;
        decimal last=b[i-1].C,atr=b.Skip(i-48).Take(48).Average(x=>x.H-x.L);
        if(last<=0 || atr<=0)return null;
        double ret(int n)=>(double)((last-b[i-n].O)/atr)/Math.Sqrt(n);
        double vol=(double)(b.Skip(i-6).Take(6).Average(x=>x.H-x.L)/atr);
        int hour=DateTimeOffset.FromUnixTimeMilliseconds(b[i].T).Hour;
        return new[]{ret(1),ret(6),ret(24),Math.Log(Math.Max(.0001,vol)),.5*Math.Sin(hour*Math.PI/12),.5*Math.Cos(hour*Math.PI/12),Math.Log((double)(b[i].T-b[i-24].T)/(24*3600000d))};
    }
    static List<Sample> Train(Bar[] b,long cut)
    {
        var samples=new List<Sample>();
        for(int i=48;i+2<b.Length;i++)if(Slot(b[i].T) && b[i+1].T==b[i].T+3600000 && b[i+1].T+3600000<cut)
        {var x=Features(b,i);if(x!=null)samples.Add(new(x,b[i+1].C/b[i].O-1m,b[i].T,Math.Min(b[i].L,b[i+1].L)/b[i].O-1m,Math.Max(b[i].H,b[i+1].H)/b[i].O-1m));}
        if(samples.Count<128)throw new ArgumentException("NEIGHBOUR_TRAINING_SUPPORT");return samples;
    }
    static decimal Predict(List<Sample> fit,double[] x)
    {
        var near=fit.Select((s,i)=>new{S=s,I=i,D=s.X.Select((v,j)=>(v-x[j])*(v-x[j])).Sum()}).OrderBy(p=>p.D).ThenBy(p=>p.I).Take(64);
        decimal sum=0,weights=0;foreach(var p in near){decimal w=(decimal)(1/(1+p.D));sum+=w*p.S.Y;weights+=w;}
        return weights>0?sum/weights:0;
    }
    static decimal MinDistance(JsonElement c,decimal price,string field)=>(int)D(c,"distanceSetIn")==1?D(c,field)/(decimal)Math.Pow(10,(int)D(c,"digits")):price*D(c,field)/10000m;
    static decimal Commission(JsonElement c,decimal units,decimal price,decimal eurAsk)
    {
        decimal rate=D(c,"preciseTradingCommissionRate"),lot=D(c,"lotSize")/100m;
        decimal usd=(int)D(c,"commissionType") switch {1=>rate/100000000m*units/1000000m,2=>rate/100000000m*units/lot,
            3=>rate/100000m/100m*units,4=>rate/100000000m*units/lot/price,_=>throw new ArgumentException("COMMISSION_TYPE")};
        decimal floor=D(c,"preciseMinCommission")/100000000m;
        if((int)D(c,"minCommissionType")==2)floor/=price;
        else {string currency=c.GetProperty("minCommissionAsset").GetString()!;if(currency=="EUR")floor*=eurAsk;else if(currency!="USD")throw new ArgumentException("MIN_COMMISSION_CCY");}
        return Math.Max(usd,floor);
    }
    static decimal CarryUsd(JsonElement c,decimal units,decimal price)
    {
        if(c.TryGetProperty("swapPeriod",out var p)&&p.ValueKind==JsonValueKind.Number&&p.GetInt32()==24&&c.TryGetProperty("swapTime",out var t)&&t.ValueKind==JsonValueKind.Number&&t.GetInt32()>=0&&t.GetInt32()<1440&&(t.GetInt32()<360||t.GetInt32()>1080))return 0;
        decimal worst=3*Math.Max(Math.Abs(D(c,"swapLong")),Math.Abs(D(c,"swapShort")));
        return (int)D(c,"swapCalculationType")==0?worst*(decimal)Math.Pow(10,-(int)D(c,"pipPosition"))*units/price:worst/100m/360m*units;
    }
    public static Planning MakePlan(JsonElement r,bool confirmation=false)
    {
        var bs=Bars(r);long start=T(r,"start"),end=T(r,"end"),cut=start+(end-start)*6/10,lo=confirmation?start+(end-start)*8/10:cut,hi=confirmation?end:start+(end-start)*8/10;
        var result=new List<Plan>();int windows=0,neutral=0,costReject=0,missing=0;
        foreach(string symbol in new[]{"USDJPY","USDCAD"})
        {
            var b=bs[symbol];var fit=Train(b,cut);var c=r.GetProperty("contracts").GetProperty(symbol);var cal=r.GetProperty("calibration").GetProperty(symbol);
            decimal min=D(c,"minVolume")/100m;
            for(int i=48;i+2<b.Length;i++)
            {
                long entry=b[i].T,horizon=entry+7200000;
                if(entry<lo || horizon>=hi || !Slot(entry))continue;windows++;
                var x=Features(b,i);if(x==null){missing++;continue;}
                decimal reference=b[i-1].C,forecast=Predict(fit,x)*reference;
                if(forecast==0){neutral++;continue;}
                decimal costPrice=(2*Commission(c,min,reference,D(r,"screenEurAsk"))+CarryUsd(c,min,reference))/min*reference+D(cal,"spread")+2*D(cal,"move");
                if(Math.Abs(forecast)<=costPrice){costReject++;continue;}
                decimal stop=Math.Max(.6m*b.Skip(i-48).Take(48).Average(v=>v.H-v.L),MinDistance(c,reference,"slDistance"));
                decimal target=Math.Max(2*stop,MinDistance(c,reference,"tpDistance"));int sign=forecast>0?1:-1;
                long exit=horizon;bool complete=false;decimal adverse=reference,favorable=reference;
                if(r.GetProperty("minutes").TryGetProperty(symbol+":"+entry,out var minute))
                {
                    var path=Decode(minute).Where(z=>z.T>=entry&&z.T<horizon).ToArray();
                    complete=path.Length==120 && path.Select((z,j)=>z.T==entry+j*60000L).All(v=>v);
                    if(complete)foreach(var z in path)
                    {
                        adverse=sign>0?Math.Min(adverse,z.L):Math.Max(adverse,z.H);favorable=sign>0?Math.Max(favorable,z.H):Math.Min(favorable,z.L);
                        bool sl=sign>0?z.L<=reference-stop:z.H>=reference+stop,tp=sign>0?z.H>=reference+target:z.L<=reference-target;
                        if(sl||tp){exit=z.T+60000;break;}
                    }
                }
                result.Add(new(symbol,entry,horizon,exit,sign,reference,stop,target,forecast,complete,adverse,favorable));
            }
        }
        return new(result.OrderBy(p=>p.Entry).ThenBy(p=>p.Symbol,StringComparer.Ordinal).ToArray(),windows,neutral,costReject,missing);
    }
    static (decimal b,decimal a)? Quote(JsonElement r,string s,long t)
    {
        if(!r.GetProperty("quotes").TryGetProperty(s+":"+t,out var q)||q.ValueKind==JsonValueKind.Null)return null;
        decimal b=D(q,"bid")/100000m,a=D(q,"ask")/100000m;long tm=T(q,"time");return b>0&&a>=b&&tm>=t&&tm<=t+10000?(b,a):null;
    }
    static decimal EurQuote(decimal pnl,decimal pairBid,decimal pairAsk,decimal eurBid,decimal eurAsk)=>pnl>=0?pnl/pairAsk/eurAsk:pnl/pairBid/eurBid;
    public static object Evaluate(JsonElement r,bool confirmation=false)
    {
        if(r.GetProperty("schema").GetString()!="mxm-neighbour-net-v1"||!r.GetProperty("readOnly").GetBoolean())throw new ArgumentException("SOURCE");
        var planning=MakePlan(r,confirmation);var results=new List<object>();var survivors=new List<string>();
        var allowed=confirmation?r.GetProperty("selectionSurvivors").EnumerateArray().Select(x=>x.GetString()).ToHashSet():new HashSet<string?>{"USDJPY","USDCAD"};
        long start=T(r,"start"),end=T(r,"end"),lo=start+(end-start)*(confirmation?8:6)/10,hi=confirmation?end:start+(end-start)*8/10;
        var weeks=new List<string>();for(var d=DateTimeOffset.FromUnixTimeMilliseconds(lo).UtcDateTime.Date;d.AddDays(5)<=DateTimeOffset.FromUnixTimeMilliseconds(hi).UtcDateTime.Date;d=d.AddDays(1))if(d.DayOfWeek==DayOfWeek.Monday)weeks.Add($"{System.Globalization.ISOWeek.GetYear(d)}-{System.Globalization.ISOWeek.GetWeekOfYear(d):00}");
        foreach(string symbol in new[]{"USDJPY","USDCAD"}.Where(s=>allowed.Contains(s)))
        {
            var c=r.GetProperty("contracts").GetProperty(symbol);var cal=r.GetProperty("calibration").GetProperty(symbol);var scenarios=new List<object>();bool all=true;
            var sourceBars=Bars(r)[symbol];var fit=Train(sourceBars,start+(end-start)*6/10);
            var sourceIndex=sourceBars.Select((b,i)=>(b.T,i)).ToDictionary(x=>x.T,x=>x.i);
            foreach(decimal scale in new[]{.5m,1m,2m})
            {
                decimal equity=200,peak=200,dd=0,gross=0,spread=0,comm=0,slippage=0,carry=0,fx=0,maxRiskRatio=0,maxMarginRatio=0,minReserveRatio=1;
                int n=0,noData=0,riskBlocked=0,utilityRejected=0,technical=0,stressExceeded=0;long lastExit=0;var rows=new List<(string w,decimal net)>();
                foreach(var p in planning.Plans.Where(p=>p.Symbol==symbol))
                {
                    if(p.Entry<lastExit){technical++;continue;}
                    var en=Quote(r,symbol,p.Entry);var ex=Quote(r,symbol,p.Exit);var ef=Quote(r,"EURUSD",p.Entry);var xf=Quote(r,"EURUSD",p.Exit);
                    if(!p.MinuteComplete||en==null||ex==null||ef==null||xf==null){noData++;continue;}
                    var (eb,ea)=en.Value;var (xb,xa)=ex.Value;var (fb,fa)=ef.Value;var (zb,za)=xf.Value;
                    decimal sl=p.Reference-p.Direction*p.Stop,tp=p.Reference+p.Direction*p.Target;
                    if((p.Direction>0?eb-sl:sl-ea)<MinDistance(c,p.Reference,"slDistance") || (p.Direction>0?tp-ea:eb-tp)<MinDistance(c,p.Reference,"tpDistance")){technical++;continue;}
                    decimal stop=p.Stop+Math.Abs((p.Direction>0?ea:eb)-p.Reference),pairFloor=eb*(1-D(cal,"shock")),eurFloor=fb*(1-D(r,"eurShock"));
                    if(pairFloor<=0||eurFloor<=0){noData++;continue;}
                    decimal conversion=1m/pairFloor/eurFloor,gap=D(cal,"gap"),slipStress=4*D(cal,"move"),spreadStress=D(cal,"spreadStress");
                    decimal unitCosts=(2*Commission(c,D(c,"minVolume")/100m,eb,fa)+CarryUsd(c,D(c,"minVolume")/100m,eb))/(D(c,"minVolume")/100m)/eurFloor+(stop+gap)*conversion*D(c,"pnlConversionFeeRate")/10000m;
                    decimal minUnits=D(c,"minVolume")/100m,marginRate=Math.Max(D(r.GetProperty("margins"),symbol)/minUnits,1m/fb/D(r.GetProperty("leverage"),symbol));
                    var features=Features(sourceBars,sourceIndex[p.Entry])!;
                    var nearest=fit.Select((sample,index)=>new {sample,index,d=sample.X.Select((v,j)=>(v-features[j])*(v-features[j])).Sum()})
                        .OrderBy(x=>x.d).ThenBy(x=>x.index).Take(64).Select(x=>x.sample).ToArray();
                    int blocks=nearest.Select(x=>DateTimeOffset.FromUnixTimeMilliseconds(x.Entry).UtcDateTime.Date).Distinct().Count();
                    var states=nearest.Select(x=> {
                        decimal netPerUnit=p.Direction*x.Y/(1+x.Y)/eurFloor-unitCosts-(2*scale*D(cal,"move")+D(cal,"spread"))*conversion;
                        decimal low=p.Direction>0?Math.Max(0,-x.LowReturn/(1+x.LowReturn)):Math.Max(0,x.HighReturn/(1+x.HighReturn));
                        decimal favorable=p.Direction>0?Math.Max(0,x.HighReturn/(1+x.HighReturn)):Math.Max(0,-x.LowReturn/(1+x.LowReturn));
                        return new JointRiskScenario(0,netPerUnit,0,0,low/eurFloor+unitCosts,0,0,true,favorable/eurFloor);
                    }).ToList();
                    decimal stressPerUnit=(stop+gap+slipStress+spreadStress)*conversion+unitCosts;
                    states.Add(new JointRiskScenario(0,-stressPerUnit,0,0,stressPerUnit,0,0,false,(p.Target+gap)*conversion));
                    // The 100%-margin stopout envelope is an explicit conditional scenario,
                    // NOT an observed broker stopout term or certified funded execution.
                    var size=AdaptivePortfolioRisk.Choose(new(equity,peak,equity,minUnits,D(c,"stepVolume")/100m,D(c,"maxVolume")/100m,marginRate,
                        1m,true,true,blocks,2m),states);
                    if(size.Units<=0){if(size.FeasibleVolumes>0)utilityRejected++;else riskBlocked++;continue;}decimal u=size.Units;
                    decimal reserved=Math.Max(0,equity-size.WorstEquityEur),reserve=equity-size.MarginEur;
                    maxRiskRatio=Math.Max(maxRiskRatio,reserved/equity);maxMarginRatio=Math.Max(maxMarginRatio,size.MarginEur/equity);minReserveRatio=Math.Min(minReserveRatio,reserve/equity);
                    decimal pricePnl=p.Direction*u*((p.Direction>0?xb:xa)-(p.Direction>0?ea:eb));
                    decimal g=EurQuote(p.Direction*u*((xb+xa-eb-ea)/2),xb,xa,zb,za),quoted=EurQuote(pricePnl,xb,xa,zb,za);
                    decimal fees=Commission(c,u,p.Direction>0?ea:eb,fa)/fb+Commission(c,u,p.Direction>0?xb:xa,za)/zb;
                    decimal slip=2*scale*D(cal,"move")*u/Math.Min(eb,xb)/Math.Min(fb,zb),fin=CarryUsd(c,u,Math.Min(eb,xb))/Math.Min(fb,zb),conversionFee=Math.Abs(quoted)*D(c,"pnlConversionFeeRate")/10000m;
                    decimal cost=g-quoted+fees+slip+fin+conversionFee,net=g-cost;
                    decimal adverse=u*Math.Max(0,p.Direction>0?ea-p.Adverse:p.Adverse+Math.Max(ea-eb,xa-xb)-eb)/Math.Min(eb,xb)/Math.Min(fb,zb);
                    decimal favorable=u*Math.Max(0,p.Direction*(p.Favorable-(p.Direction>0?ea:eb)))/Math.Min(eb,xb)/Math.Min(fb,zb);
                    peak=Math.Max(peak,equity+favorable);dd=Math.Max(dd,1-(equity-adverse-fees-slip-fin-conversionFee)/peak);
                    if(adverse+fees+slip+fin+conversionFee>reserved||1m-(equity-adverse-fees-slip-fin-conversionFee)/peak>size.WorstScenarioDrawdown||xb<pairFloor||zb<eurFloor||xa-xb>spreadStress)stressExceeded++;
                    equity+=net;peak=Math.Max(peak,equity);dd=Math.Max(dd,1-equity/peak);gross+=g;spread+=g-quoted;comm+=fees;slippage+=slip;carry+=fin;fx+=conversionFee;n++;lastExit=p.Exit;
                    var d=DateTimeOffset.FromUnixTimeMilliseconds(p.Exit).UtcDateTime;rows.Add(($"{System.Globalization.ISOWeek.GetYear(d)}-{System.Globalization.ISOWeek.GetWeekOfYear(d):00}",net));
                }
                var wnet=weeks.Select(w=>rows.Where(x=>x.w==w).Sum(x=>x.net)).ToArray();decimal mean=wnet.Length>0?wnet.Average():0;
                double se=wnet.Length>1?Math.Sqrt(wnet.Sum(v=>(double)((v-mean)*(v-mean)))/(wnet.Length-1)/wnet.Length):0;decimal lower=mean-(decimal)(2.6*se);
                bool pass=n>=30&&noData==0&&equity>200&&lower>0&&dd<=.3m&&stressExceeded==0;all&=pass;
                scenarios.Add(new{slippageCalibrationScale=scale,completeModeledRoundTrips=n,dataMissing=noData,riskBlocked,utilityRejected,technicalBlocked=technical,declaredStressExceeded=stressExceeded,
                    grossEur=gross,spreadEur=spread,commissionEur=comm,slippageEur=slippage,financingEur=carry,conversionEur=fx,totalCostEur=spread+comm+slippage+carry+fx,netEur=equity-200,maxModeledDrawdown=dd,
                    maxAggregateReservedRiskRatio=maxRiskRatio,maxAggregateMarginRatio=maxMarginRatio,minFreeReserveRatio=minReserveRatio,eligibleWeeks=weeks.Count,
                    weeksWith21ModeledRoundTrips=weeks.Count(w=>rows.Count(x=>x.w==w)>=21),weeklyMeanLowerConservativeEur=lower,passesSelection=pass,
                    verdict=n==0?"NO_COMPLETE_ADMITTED_EPISODES":equity<=200?"REJECTED_NET_NONPOSITIVE_NO_RETUNING":!pass?"REJECTED_SUPPORT_OR_ROBUSTNESS":"REQUIRES_UNTOUCHED_CONFIRMATION"});
            }
            if(all)survivors.Add(symbol);results.Add(new{symbol,model="H1_CONDITIONAL_NEIGHBOUR_RETURN_K64_V1",proposals=planning.Plans.Count(p=>p.Symbol==symbol),eligibleForConfirmation=all,scenarios});
        }
        return new{schema="mxm-neighbour-net-public-v1",phase=confirmation?"CONFIRMATION":"SELECTION",results,selectionSurvivors=survivors,
            diagnosticCounters=new{planning.FeatureWindows,planning.NoForecast,planning.CostRejected,planning.DataMissing},
            sourceBars=Bars(r).ToDictionary(x=>x.Key,x=>x.Value.Length),observedSpanDays=Bars(r).ToDictionary(x=>x.Key,x=>(x.Value.Last().T+3600000-x.Value.First().T)/86400000m),phaseStart=lo,phaseEnd=hi,calibration=r.GetProperty("calibration"),authority=OwnerRiskAuthority.Authority,initialCapitalEur=200,ownerMaxSystemDrawdown=.30m,brokerStopoutObserved=false,assumedStopoutEquityToMargin=1m,riskPolicy="TRAIN_NEIGHBOUR_JOINT_SCENARIOS_AND_ADAPTIVE_LOWER_LOG_UTILITY; NO_UNIVERSAL_FIXED_PERCENTAGES",
            riskStressParameters="AUTHENTIC_TRAINING_M1_AND_QUOTE_SAMPLES; MODEL_SPECIFIC_NOT_OWNER_LIMITS",confirmationEvaluated=confirmation,ordersSubmitted=0,
            independentFinalQualification=false,absoluteDrawdownGuarantee=false,realFills=false,historicContractScheduleProven=false};
    }
}
