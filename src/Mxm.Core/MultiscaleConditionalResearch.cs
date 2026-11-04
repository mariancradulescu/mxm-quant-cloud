namespace Mxm.Core;

public sealed record MultiscaleInput(ProgramBar[] Bars,EmpiricalCostObservation[] Costs,long Start,long DevelopmentEnd,long SelectionEnd,long End);
public sealed record StructuralForecast(long At,long Exit,double MeanBps,double ProbabilityUp,double VolatilityBps,double SourceVolBps,double? OutcomeBps,bool ForwardPathIncomplete=false);

// MSP1 structural hypotheses: persistent repricing, temporary concessions and
// a zero-drift skeptic. Fixed prequential likelihood updates, no old model calls.
public static class MultiscaleConditionalResearch
{
    public sealed class Filter
    {
        double drift,reference,variance=1,activity=1;int count;
        double previousPrice;long previousEnd;
        double[] previousMeans=new double[3];double previousVariance=1;
        readonly double[] logWeights=new double[3];
        public int Count=>count;
        public void Observe(ProgramBar b)
        {
            if(count==0){reference=Math.Log(b.Close);previousPrice=b.Close;previousEnd=b.End;activity=Math.Max(1,b.Volume);count++;return;}
            double r=Math.Log(b.Close/previousPrice)*10000;
            if(b.Start==previousEnd)
                for(int j=0;j<3;j++)logWeights[j]=.99*logWeights[j]-.5*Math.Min(100,Math.Pow(r-previousMeans[j],2)/previousVariance);
            double top=logWeights.Max();for(int j=0;j<3;j++)logWeights[j]-=top;
            drift=.96875*drift+.03125*r;variance=.96875*variance+.03125*r*r;
            reference=.9921875*reference+.0078125*Math.Log(b.Close);
            double sigma=Math.Sqrt(Math.Max(variance,1e-12));
            previousMeans=new[]{0,Math.Clamp(drift,-sigma,sigma),Math.Clamp(-.1*(Math.Log(b.Close)-reference)*10000,-sigma,sigma)};
            double ratio=Math.Clamp(b.Volume/Math.Max(1,activity),1,4);
            previousVariance=Math.Max(variance*ratio,1e-12);activity=.96875*activity+.03125*b.Volume;
            previousPrice=b.Close;previousEnd=b.End;count++;
        }
        public (double Mean,double Up,double Sigma) Forecast(int horizon,int variant)
        {
            if(horizon<=0||variant is <0 or >2)throw new ArgumentException("STRUCTURAL_FORECAST_REQUEST");
            double[] weights=logWeights.Select(x=>Math.Exp(Math.Max(-700,x))).ToArray();
            if(variant==1)weights[1]=0;if(variant==2)weights[2]=0;
            var allowed=Enumerable.Range(0,3).Where(j=>variant==0||j!=(variant==1?1:2)).ToArray();
            double total=weights.Sum();for(int j=0;j<3;j++)weights[j]=allowed.Contains(j)? .01/allowed.Length+.99*weights[j]/total:0;
            double[] means={0,horizon*previousMeans[1],previousMeans[2]*(1-Math.Pow(.9,horizon))/.1};
            double sigma=Math.Sqrt(horizon*previousVariance);
            double mean=Enumerable.Range(0,3).Sum(j=>weights[j]*means[j]);
            double up=Enumerable.Range(0,3).Sum(j=>weights[j]*Cdf(means[j]/sigma));
            return (mean,up,sigma);
        }
    }
    static double Cdf(double x)
    {
        double a=Math.Abs(x),t=1/(1+.2316419*a),pdf=Math.Exp(-a*a/2)/Math.Sqrt(2*Math.PI);
        double q=pdf*t*(.319381530+t*(-.356563782+t*(1.781477937+t*(-1.821255978+t*1.330274429))));
        return Math.Clamp(x>=0?1-q:q,0,1);
    }
    static ProgramBar[] Aggregate(ProgramBar[] a,int minutes)
    {
        if(minutes==5)return a;long duration=minutes*60000L;
        return a.GroupBy(b=>b.Start/duration).Select(g=>{
            var x=g.OrderBy(b=>b.Start).ToArray();long start=g.Key*duration;
            return x.Length==minutes/5&&x[0].Start==start&&x[^1].End==start+duration&&Enumerable.Range(1,x.Length-1).All(i=>x[i].Start==x[i-1].End)?
                new ProgramBar(x[0].Symbol,start,start+duration,x[0].Open,x.Max(b=>b.High),x.Min(b=>b.Low),x[^1].Close,x.Sum(b=>b.Volume)):null;
        }).Where(x=>x!=null).Select(x=>x!).OrderBy(b=>b.Start).ToArray();
    }
    static Dictionary<long,double> Volumes(ProgramBar[] a)
    {
        var result=new Dictionary<long,double>();var q=new Queue<double>();double sum=0;
        for(int i=1;i<a.Length;i++){
            double r=Math.Log(a[i].Close/a[i-1].Close)*10000;q.Enqueue(r*r);sum+=r*r;if(q.Count>32)sum-=q.Dequeue();
            if(q.Count==32)result[a[i].End]=Math.Sqrt(Math.Max(0,sum/32));
        }return result;
    }
    public static StructuralForecast[][] Forecasts(ProgramBar[] a,int minutes,int horizon,Dictionary<long,double> rawVol)
    {
        var byEnd=a.ToDictionary(b=>b.End);var filter=new Filter();var result=Enumerable.Range(0,3).Select(_=>new List<StructuralForecast>()).ToArray();
        for(int i=0;i<a.Length;i++)
        {
            filter.Observe(a[i]);if(filter.Count<128)continue;
            // Generate forecast from observed past BEFORE inspecting label coverage.
            var predictions=Enumerable.Range(0,3).Select(v=>filter.Forecast(horizon,v)).ToArray();
            long at=a[i].End,exit=at+horizon*minutes*60000L;
            bool known=byEnd.TryGetValue(exit,out var target);
            bool pathIncomplete=!Enumerable.Range(1,horizon).All(k=>byEnd.ContainsKey(at+k*minutes*60000L));
            double? y=known?(target!.Close/a[i].Close-1)*10000:null;
            if(!rawVol.TryGetValue(at,out double vol))throw new ArgumentException("PAST_M5_VOLATILITY_MISSING");
            for(int v=0;v<3;v++){var p=predictions[v];result[v].Add(new(at,exit,p.Mean,p.Up,p.Sigma,vol,y,pathIncomplete));}
        }return result.Select(x=>x.ToArray()).ToArray();
    }
    sealed record Plan(long At,long Exit,double? Gross,double? Net,double Cost,string Cell,int Samples,int Dates,bool PathIncomplete);
    public sealed record ProxyStats(int Forecasts,int Proposals,int KnownOutcomes,int MissingOutcomes,int ActiveWeeks,int FullWeeks,
        int UnpricedFundingForecasts,int IncompleteForwardPaths,double? ConditionalNetBpsSum,double KnownOnlyNetBpsSum,double? MeanPerProposalBps,double WeeklyHacSe,
        double? WeeklyDescriptive90LowerBps,double MeanModeledCostBps,object[] Weekly,Dictionary<string,int> CostCells);
    static ProxyStats Stats(StructuralForecast[] rows,string symbol,int minutes,int horizon,int scenario,long start,long end,ConditionalEmpiricalCosts costs)
    {
        var plans=new List<Plan>();long next=0;int unknownFunding=0;
        foreach(var r in rows.Where(x=>x.At>=start&&x.At<end))
        {
            int side=Math.Sign(r.MeanBps);if(side==0||r.At<next||r.Exit>=end)continue;
            var weekday=DateTimeOffset.FromUnixTimeMilliseconds(r.Exit).DayOfWeek;
            if(weekday is DayOfWeek.Saturday or DayOfWeek.Sunday)continue;
            double latencyVol=r.VolatilityBps/Math.Sqrt(horizon*minutes*60.0);
            var c=costs.Estimate(symbol,r.At,r.SourceVolBps,latencyVol,side,minutes*horizon,scenario);
            if(!c.FundingKnown){unknownFunding++;continue;}
            if(Math.Abs(r.MeanBps)-c.TotalBps<=(Math.Abs(r.MeanBps)+c.TotalBps)*c.ProfitConversionRate)continue;
            next=r.Exit;double? gross=r.OutcomeBps.HasValue?side*r.OutcomeBps:null;
            double? totalCost=gross.HasValue?c.TotalBps+(Math.Abs(gross.Value)+c.TotalBps)*c.ProfitConversionRate:null;
            plans.Add(new(r.At,r.Exit,gross,gross-totalCost,totalCost??c.TotalBps,c.Cell,c.Samples,c.DistinctDates,r.ForwardPathIncomplete));
        }
        int weeks=(int)((end-start)/604800000L);var totals=new double[weeks];var weekly=new List<object>();
        int active=0;
        for(int i=0;i<weeks;i++){
            long at=start+i*604800000L;var rowsAt=plans.Where(p=>p.At>=at&&p.At<at+604800000L).ToArray();
            totals[i]=rowsAt.Sum(p=>p.Net??0);if(rowsAt.Length>0)active++;
            weekly.Add(new {Week=at,Proposals=rowsAt.Length,Missing=rowsAt.Count(p=>!p.Net.HasValue),KnownOnlyConditionalNetBps=totals[i]});
        }
        double mean=weeks>0?totals.Average():0,variance=weeks>1?totals.Sum(x=>(x-mean)*(x-mean))/weeks:0,hac=variance;
        for(int lag=1;lag<=Math.Min(2,weeks-1);lag++)hac+=2*(1-lag/3.0)*Enumerable.Range(lag,weeks-lag).Sum(i=>(totals[i]-mean)*(totals[i-lag]-mean))/weeks;
        double se=weeks>1?Math.Sqrt(Math.Max(variance,hac)/weeks):0;
        int missing=plans.Count(p=>!p.Net.HasValue);double knownSum=plans.Sum(p=>p.Net??0);
        return new(rows.Count(r=>r.At>=start&&r.At<end),plans.Count,plans.Count-missing,missing,active,weeks,
            unknownFunding,plans.Count(p=>p.PathIncomplete),missing==0?knownSum:null,knownSum,missing==0&&plans.Count>0?knownSum/plans.Count:null,se,
            missing==0&&weeks>1?mean-1.645*se:null,plans.Count>0?plans.Average(p=>p.Cost):0,weekly.ToArray(),
            plans.GroupBy(p=>p.Cell).ToDictionary(g=>g.Key,g=>g.Count()));
    }
    static object Predictive(StructuralForecast[] a,long start,long end)
    {
        var rows=a.Where(x=>x.At>=start&&x.At<end&&x.Exit<end&&x.OutcomeBps.HasValue).ToArray();
        return new {KnownForecasts=rows.Length,MissingOrBoundary=a.Count(x=>x.At>=start&&x.At<end)-rows.Length,
            Brier=rows.Length>0?(double?)rows.Average(x=>Math.Pow(x.ProbabilityUp-(x.OutcomeBps>0?1:0),2)):null,
            NeutralBrier=.25,MeanAbsoluteForecastBps=rows.Length>0?(double?)rows.Average(x=>Math.Abs(x.MeanBps)):null,
            DirectionHitRate=rows.Length>0?(double?)rows.Average(x=>Math.Sign(x.MeanBps)==Math.Sign(x.OutcomeBps!.Value)?1d:0d):null};
    }
    public static object Evaluate(MultiscaleInput input)
    {
        if(input.Start>=input.DevelopmentEnd||input.DevelopmentEnd>=input.SelectionEnd||input.SelectionEnd>=input.End||
           input.Bars.Any(b=>b.Start<input.Start||b.End>input.End||b.End-b.Start!=300000||b.Low<=0||
             b.Low>Math.Min(b.Open,b.Close)||b.High<Math.Max(b.Open,b.Close)||b.Volume<0))throw new ArgumentException("MSP1_SOURCE_GEOMETRY");
        var costs=new ConditionalEmpiricalCosts(input.Costs,input.DevelopmentEnd);
        var groups=new List<object>();var support=new List<object>();var amplitudes=new List<object>();
        var admitted=new List<string>();string[] variants={"PRIMARY_ALL","REMOVE_PERSISTENT","REMOVE_TRANSITORY"};
        foreach(var source in input.Bars.GroupBy(b=>b.Symbol).OrderBy(g=>g.Key))
        {
            var raw=source.OrderBy(b=>b.Start).ToArray();if(raw.Select(b=>b.Start).Distinct().Count()!=raw.Length)throw new ArgumentException("MSP1_DUPLICATE_BAR");
            var vol=Volumes(raw);
            foreach(int minutes in new[]{5,15,60,240})
            {
                var a=Aggregate(raw,minutes);support.Add(new {Symbol=source.Key,Minutes=minutes,Bars=a.Length});
                foreach(int horizon in new[]{1,4})
                {
                    var predictions=Forecasts(a,minutes,horizon,vol);
                    var moves=predictions[0].Where(x=>x.At<input.DevelopmentEnd&&x.Exit<input.DevelopmentEnd&&x.OutcomeBps.HasValue).Select(x=>Math.Abs(x.OutcomeBps!.Value)).ToArray();
                    amplitudes.Add(new {Symbol=source.Key,Minutes=minutes,HorizonMinutes=minutes*horizon,KnownDevelopmentMoves=moves.Length,
                        MedianAbsMoveBps=moves.Length>0?(double?)ConditionalEmpiricalCosts.Quantile(moves,.5):null,
                        P90AbsMoveBps=moves.Length>0?(double?)ConditionalEmpiricalCosts.Quantile(moves,.9):null,IsPredictability=false});
                    for(int v=0;v<3;v++)
                    {
                        var selection=Enumerable.Range(0,3).Select(c=>Stats(predictions[v],source.Key,minutes,horizon,c,input.DevelopmentEnd,input.SelectionEnd,costs)).ToArray();
                        // Admissions fixed ONLY on selection, before audit statistics are computed.
                        string id=$"{source.Key}_{minutes}_{horizon}";var adverse=selection[1];
                        bool followup=v==0&&adverse.Proposals>=30&&adverse.ActiveWeeks>=8&&adverse.MissingOutcomes==0&&adverse.WeeklyDescriptive90LowerBps>0;
                        if(followup)admitted.Add(id);
                        var audit=Enumerable.Range(0,3).Select(c=>Stats(predictions[v],source.Key,minutes,horizon,c,input.SelectionEnd,input.End,costs)).ToArray();
                        groups.Add(new {Id=id,Symbol=source.Key,Minutes=minutes,HorizonMinutes=minutes*horizon,Variant=variants[v],
                            SelectionPredictive=Predictive(predictions[v],input.DevelopmentEnd,input.SelectionEnd),
                            ExposedAuditPredictive=Predictive(predictions[v],input.SelectionEnd,input.End),
                            Selection=selection,ExposedAudit=audit,ExecutionPricingFollowupSupported=followup,
                            ConditionalCostClass="CONDITIONAL_COST_MODEL",FundedNetEur=(decimal?)null});
                    }
                }
            }
        }
        return new {Schema="mxm-multiscale-conditional-research-v1",SourceSupport=support,Amplitude=amplitudes,
            CostModel=costs.Describe(),Groups=groups,PrimaryFollowupCandidateIds=admitted,CostScenarios=new[]{"CENTRAL","ADVERSE","STRESS"},
            PredictiveGroupCount=groups.Count,ConditionalCostClass="CONDITIONAL_COST_MODEL",FundedNetEur=(decimal?)null,
            CostsAreHistoricalFacts=false,ActualFills=false,IndependentConfirmation=false,MultipleTestingQualification=false,
            EconomicQualification=false,Hard21Proven=false,GlobalDrawdownCertified=false,OrdersSubmitted=0,CloudActivated=false};
    }
}
