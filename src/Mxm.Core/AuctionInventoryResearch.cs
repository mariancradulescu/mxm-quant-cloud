namespace Mxm.Core;

public sealed record AuctionSpec(string Symbol,string TimeZone,int OpenHour,int OpenMinute,int CloseHour,int CloseMinute);
public sealed record AuctionInput(ProgramBar[] Bars,ProgramCost[] Costs,AuctionSpec[] Sessions,long Start,long DevelopmentEnd,long SelectionEnd,long End);
public sealed record AuctionEpisode(string Symbol,long At,long Exit,double ScaleBps,double[] X,double? Outcome,int Week);

// AIP1: pooled inventory-acceptance hypothesis, not a calendar mean, a closed
// price-breakout rule or BDP1 cells. One session episode per asset/business date.
public static class AuctionInventoryResearch
{
    static long Utc(DateTime d,int hour,int minute,TimeZoneInfo zone)=>new DateTimeOffset(TimeZoneInfo.ConvertTimeToUtc(
        DateTime.SpecifyKind(d.Date.AddHours(hour).AddMinutes(minute),DateTimeKind.Unspecified),zone)).ToUnixTimeMilliseconds();
    public static AuctionEpisode[] Episodes(AuctionInput input)
    {
        var result=new List<AuctionEpisode>();
        foreach(var spec in input.Sessions)
        {
            var rows=input.Bars.Where(b=>b.Symbol==spec.Symbol).OrderBy(b=>b.Start).ToArray();var map=rows.ToDictionary(b=>b.Start);
            var zone=TimeZoneInfo.FindSystemTimeZoneById(spec.TimeZone);var prior=new Queue<(double Close,double RangeBps,double FirstVolume)>();
            for(var day=DateTimeOffset.FromUnixTimeMilliseconds(input.Start).UtcDateTime.Date;day<DateTimeOffset.FromUnixTimeMilliseconds(input.End).UtcDateTime.Date;day=day.AddDays(1))
            {
                if(day.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)continue;
                long open=Utc(day,spec.OpenHour,spec.OpenMinute,zone),close=Utc(day,spec.CloseHour,spec.CloseMinute,zone),at=open+1800000,exit=at+7200000;
                ProgramBar[] Window(long lo,long hi)=>Enumerable.Range(0,(int)((hi-lo)/300000)).Select(i=>map.TryGetValue(lo+i*300000L,out var b)?b:null).Where(b=>b!=null).Select(b=>b!).ToArray();
                bool Complete(ProgramBar[] b,long lo,long hi)=>b.Length==(hi-lo)/300000 && b.All(x=>x.End==x.Start+300000) && b.FirstOrDefault()?.Start==lo && b.LastOrDefault()?.End==hi;
                var first=Window(open,at);var future=Window(at,exit);var session=Window(open,close);
                if(Complete(first,open,at) && prior.Count==10 && at>=input.Start && exit<input.End)
                {
                    double scale=prior.Average(x=>x.RangeBps),last=prior.Last().Close;
                    if(scale>0 && last>0)
                    {
                        double gap=(first[0].Open/last-1)*10000/scale;
                        double acceptance=(first[^1].Close/first[0].Open-1)*10000/scale;
                        double activity=first.Sum(b=>b.Volume)/Math.Max(1,prior.Average(x=>x.FirstVolume));
                        double Clamp(double x)=>Math.Clamp(x,-4,4);
                        var x=new[]{1.0,Clamp(gap),Clamp(acceptance),Clamp(gap)*Clamp(acceptance),Clamp(Math.Log(Math.Max(.01,activity)))};
                        result.Add(new(spec.Symbol,at,exit,scale,x,Complete(future,at,exit)?(future[^1].Close/first[^1].Close-1)*10000/scale:null,(int)((at-input.Start)/604800000L)));
                    }
                }
                // A missing cash session is not replaced by a forward-filled close.
                if(Complete(session,open,close) && Complete(first,open,at))
                {
                    prior.Enqueue((session[^1].Close,(session.Max(b=>b.High)-session.Min(b=>b.Low))/session[0].Open*10000,first.Sum(b=>b.Volume)));
                    if(prior.Count>10)prior.Dequeue();
                }
                else prior.Clear();
            }
        }
        return result.OrderBy(x=>x.At).ThenBy(x=>x.Symbol,StringComparer.Ordinal).ToArray();
    }
    static double[] Fit(AuctionEpisode[] rows)
    {
        const int n=5;var a=new double[n,n+1];
        foreach(var r in rows)for(int i=0;i<n;i++){
            for(int j=0;j<n;j++)a[i,j]+=r.X[i]*r.X[j];a[i,n]+=r.X[i]*r.Outcome!.Value;
        }
        for(int i=1;i<n;i++)a[i,i]+=20; // fixed zero-centred ridge, never tuned
        a[0,0]+=1e-9;
        for(int k=0;k<n;k++)
        {
            int pivot=Enumerable.Range(k,n-k).OrderByDescending(i=>Math.Abs(a[i,k])).First();
            if(Math.Abs(a[pivot,k])<1e-12)throw new ArgumentException("AIP1_SINGULAR_FIT");
            for(int j=k;j<=n;j++)(a[k,j],a[pivot,j])=(a[pivot,j],a[k,j]);
            double v=a[k,k];for(int j=k;j<=n;j++)a[k,j]/=v;
            for(int i=0;i<n;i++)if(i!=k){v=a[i,k];for(int j=k;j<=n;j++)a[i,j]-=v*a[k,j];}
        }
        return Enumerable.Range(0,n).Select(i=>a[i,n]).ToArray();
    }
    public static object Evaluate(AuctionInput input)
    {
        var episodes=Episodes(input);var train=episodes.Where(x=>x.Exit<input.DevelopmentEnd && x.Outcome.HasValue).ToArray();
        var weeks=train.Select(x=>x.Week).Distinct().OrderBy(x=>x).ToArray();var cost=input.Costs.ToDictionary(x=>x.Symbol);
        bool support=train.Length>=200 && weeks.Length>=20 && input.Sessions.Count(s=>train.Count(x=>x.Symbol==s.Symbol)>=40)>=2;
        double[] fit=support?Fit(train):Array.Empty<double>();var deleteWeek=support?weeks.Select(w=>Fit(train.Where(x=>x.Week!=w).ToArray())).ToArray():Array.Empty<double[]>();
        double Dot(double[] b,double[] x)=>b.Zip(x).Sum(p=>p.First*p.Second);
        var forecasts=episodes.Where(x=>x.At>=input.DevelopmentEnd && x.Exit<input.End).Select(x=>{
            double mean=support?Dot(fit,x.X)*x.ScaleBps:0;
            var jack=deleteWeek.Select(b=>Dot(b,x.X)*x.ScaleBps).ToArray();double average=jack.Length>0?jack.Average():0;
            double se=jack.Length>1?Math.Sqrt((jack.Length-1.0)/jack.Length*jack.Sum(y=>(y-average)*(y-average))):0;
            bool funded=cost.TryGetValue(x.Symbol,out var c)&&c.Samples>=3&&c.CurrentMinimumMarginEur<200&&c.CurrentFundingScheduleKnown;
            long nextSwap=x.At/86400000*86400000+(c?.SwapMinute??0)*60000L;if(nextSwap<x.At)nextSwap+=86400000;
            bool swap=funded && c!.SwapMinute.HasValue && nextSwap>x.Exit;
            bool symbolSupport=support && train.Count(t=>t.Symbol==x.Symbol)>=40;
            bool primary=symbolSupport && swap && Math.Abs(mean)-2*se-2*c!.RoundTripBps>0;
            bool baseline=symbolSupport && swap && Math.Abs(mean)-2*se-c!.RoundTripBps>0;
            // Future label availability cannot suppress an earlier forecast/admission.
            return new {x.Symbol,x.At,x.Exit,x.Week,x.ScaleBps,MeanBps=mean,StandardErrorBps=se,
                TwoSeBeforeCostBps=Math.Abs(mean)-2*se,Side=mean>=0?1:-1,Primary=primary,BaseCostSensitivity=baseline,
                CostBps=c?.RoundTripBps,FinancingScenarioCovered=swap,OutcomeBps=x.Outcome*x.ScaleBps};
        }).ToArray();
        object Phase(long start,long end,string? remove=null)
        {
            var all=forecasts.Where(x=>start<=x.At&&x.Exit<end&&(remove==null||x.Symbol!=remove)).ToArray();var active=all.Where(x=>x.Primary).ToArray();
            // Equal-notional diagnostic, no fictitious EUR200 pooling or fills.
            var clocks=active.GroupBy(x=>x.At).Select(g=>new {At=g.Key,Net=g.All(x=>x.OutcomeBps.HasValue)?g.Average(x=>x.Side*x.OutcomeBps!.Value-2*x.CostBps!.Value):(double?)null}).ToArray();
            var weekRows=Enumerable.Range(0,13).Select(i=>{
                long w=start+i*604800000L;var included=clocks.Where(c=>w<=c.At&&c.At<w+604800000L).ToArray();
                return new {Week=w,ActiveEpisodes=active.Count(x=>w<=x.At&&x.At<w+604800000L),ProxyBps=included.All(c=>c.Net.HasValue)?included.Sum(c=>c.Net!.Value):(double?)null};
            }).ToArray();
            return new {ScheduledFeatureEpisodes=all.Length,PrimaryEpisodes=active.Length,BaseCostSensitivityEpisodes=all.Count(x=>x.BaseCostSensitivity),
                MissingActiveLabels=active.Count(x=>!x.OutcomeBps.HasValue),Weekly=weekRows,
                EqualNotionalConditionalCostProxyBps=clocks.All(x=>x.Net.HasValue)?clocks.Sum(x=>x.Net!.Value):(double?)null,
                GrossDirectionalBpsSum=active.All(x=>x.OutcomeBps.HasValue)?active.Sum(x=>x.Side*x.OutcomeBps!.Value):(double?)null,
                FundedNetEur=(decimal?)null,FinancedRoundTrips=0};
        }
        return new {Schema="mxm-auction-inventory-v1",TrainingSupportPassed=support,TrainingEpisodes=train.Length,TrainingWeeks=weeks.Length,
            TrainingLabelsBySymbol=input.Sessions.Select(s=>new {s.Symbol,Count=train.Count(x=>x.Symbol==s.Symbol)}).ToArray(),
            FittedCoefficients=fit,LeaveWeekOutFits=deleteWeek.Length,SourceFeatureEpisodes=episodes.Length,
            Selection=Phase(input.DevelopmentEnd,input.SelectionEnd),ExposedAudit=Phase(input.SelectionEnd,input.End),
            MarginalProxyComparisons=input.Sessions.Select(s=>new {RemovedSymbol=s.Symbol,SelectionWithout=Phase(input.DevelopmentEnd,input.SelectionEnd,s.Symbol),AuditWithout=Phase(input.SelectionEnd,input.End,s.Symbol),RefitOrFundedMarginalNet=false}).ToArray(),
            Forecasts=forecasts,EffectiveIndependentObservationsClaimed=false,CostsAreHistoricalBound=false,FundedNetEur=(decimal?)null,
            IndependentConfirmation=false,GlobalDrawdownCertified=false,EconomicQualification=false,OrdersSubmitted=0,CloudActivated=false};
    }
}
