using System.Text.Json;
namespace Mxm.Core;

public sealed record ProgramBar(string Symbol,long Start,long End,double Open,double High,double Low,double Close,double Volume);
public sealed record ProgramCost(string Symbol,double RoundTripBps,double MinimumNotionalEur,decimal CurrentMinimumMarginEur,
    bool CurrentFundingScheduleKnown,int? SwapMinute,int Samples);
public sealed record DiscoveryInput(ProgramBar[] Bars,ProgramCost[] Costs,long Start,long DevelopmentEnd,long SelectionEnd,long End);

// BDP1: one predeclared contextual distribution learner with four economically
// different feature views. No closed model, grid search or hindsight inversion.
// Outputs are BID-bar return/cost SCENARIOS, never executable/funded NET.
public static class PortfolioDiscoveryProgram
{
    static readonly string[] Families={"PATH_CONTEXT","LIQUIDITY_CONTEXT","SCALE_CONTEXT","RELATIVE_CONTEXT"};
    sealed class Moments
    {
        public int N;public double Sum,Square;
        public void Add(double x){N++;Sum+=x;Square+=x*x;}
        public double Mean=>N>0?Sum/N:0;
        public double Variance=>N>1?Math.Max(0,(Square-Sum*Sum/N)/(N-1)):0;
    }
    sealed record Example(long At,long KnownAt,int Cell,double? Outcome);
    sealed record Prediction(long At,long Exit,int Side,double? Gross,double? ProxyNet,double LowerAtDecision);
    static int Bin(double x,double low,double high)=>x<low?0:x>high?2:1;
    static int Cell(int a,int b,int c)=>a*9+b*3+c;
    static int UsdSign(string s)=>s is "USDJPY" or "USDCAD"?-1:1;
    static ProgramBar[] Aggregate(ProgramBar[] source,long duration)
        =>source.GroupBy(b=>(b.Symbol,Bucket:b.Start/duration)).Select(g=>{
            var a=g.OrderBy(b=>b.Start).ToArray();long start=g.Key.Bucket*duration;
            return a.Length==duration/300000 && a[0].Start==start && a[^1].End==start+duration &&
                Enumerable.Range(1,a.Length-1).All(i=>a[i].Start==a[i-1].End)?
                new ProgramBar(g.Key.Symbol,start,start+duration,a[0].Open,a.Max(b=>b.High),a.Min(b=>b.Low),a[^1].Close,a.Sum(b=>b.Volume)):null;
        }).Where(x=>x!=null).Select(x=>x!).OrderBy(b=>b.Start).ToArray();
    static Example[] Examples(ProgramBar[] a,Dictionary<long,List<double>> peers,int horizon,int family)
    {
        var result=new List<Example>();
        for(int i=64;i<a.Length;i++)
        {
            if(!Enumerable.Range(i-31,32).All(j=>a[j].Start==a[j-1].End))continue;
            double R(int n)=>(a[i].Close/a[i-n].Close-1)*10000;
            var r=Enumerable.Range(i-31,32).Select(j=>(a[j].Close/a[j-1].Close-1)*10000).ToArray();
            double vol=Math.Sqrt(r.Select(x=>x*x).Average());if(vol<=0)continue;
            double range=a[i].High-a[i].Low;if(range<=0)continue;
            double priorRange=Enumerable.Range(i-32,32).Average(j=>a[j].High-a[j].Low);
            double priorVolume=Enumerable.Range(i-32,32).Average(j=>a[j].Volume);
            double location=(2*a[i].Close-a[i].High-a[i].Low)/range;
            double path=Enumerable.Range(i-15,16).Sum(j=>Math.Abs(a[j].Close-a[j-1].Close));
            double efficiency=path>0?Math.Abs(a[i].Close-a[i-16].Close)/path:0;
            double ratio=Math.Sqrt(r.TakeLast(8).Select(x=>x*x).Average())/vol;
            int cell;
            switch(family)
            {
                case 0:cell=Cell(Bin(R(4)/(2*vol),-.5,.5),Bin(efficiency,.2,.5),Bin((a[i].Close-a[i].Open)/range,-.33,.33));break;
                case 1:
                    if(priorRange<=0 || priorVolume<=0)continue;
                    cell=Cell(Bin(a[i].Volume/priorVolume,.75,1.5),Bin(range/priorRange,.75,1.5),Bin(location,-.33,.33));break;
                case 2:cell=Cell(Bin(ratio,.75,1.25),Bin(Math.Sign(R(4))*Math.Sign((a[i-4].Close/a[i-8].Close-1)),-.5,.5),Bin(location,-.33,.33));break;
                default:
                    if(!peers.TryGetValue(a[i].End,out var cross) || cross.Count<3)continue;
                    var ordered=cross.OrderBy(x=>x).ToArray();double median=ordered[ordered.Length/2];
                    cell=Cell(Bin((UsdSign(a[i].Symbol)*R(1)-median)/vol,-.5,.5),Bin(Math.Sqrt(cross.Average(x=>x*x))/vol,.75,1.5),Bin(location,-.33,.33));break;
            }
            bool labelKnown=i+horizon<a.Length && Enumerable.Range(i+1,horizon).All(j=>a[j].Start==a[j-1].End);
            result.Add(new(a[i].End,a[i].End+horizon*(a[i].End-a[i].Start),cell,labelKnown?(a[i+horizon].Close/a[i].Close-1)*10000:null));
        }
        return result.ToArray();
    }
    static object Statistics(Prediction[] predictions,long start,long end,double multiplier)
    {
        var weeks=Enumerable.Range(0,(int)((end-start)/604800000)).Select(i=>start+i*604800000).ToArray();
        var totals=weeks.Select(w=>predictions.Where(x=>w<=x.At && x.At<w+604800000).Sum(x=>x.ProxyNet??0)).ToArray();
        double mean=totals.Length>0?totals.Average():0;
        double se=totals.Length>1?Math.Sqrt(totals.Sum(x=>(x-mean)*(x-mean))/(totals.Length-1)/totals.Length):double.PositiveInfinity;
        return new {Windows=predictions.Length,FullPredeclaredWeeks=weeks.Length,ActiveWeeks=totals.Count(x=>x!=0),
            KnownLabelWindows=predictions.Count(x=>x.ProxyNet.HasValue),MissingOutcomeWindows=predictions.Count(x=>!x.ProxyNet.HasValue),
            GrossBpsSum=predictions.All(x=>x.Gross.HasValue)?predictions.Sum(x=>x.Gross):(double?)null,
            ConditionalCostScenarioBpsSum=predictions.All(x=>x.ProxyNet.HasValue)?predictions.Sum(x=>x.ProxyNet):(double?)null,
            ObservedLabelsOnlyCostScenarioBpsSum=predictions.Sum(x=>x.ProxyNet??0),
            WeeklyMeanBps=predictions.All(x=>x.ProxyNet.HasValue)?mean:(double?)null,
            WeeklyStandardErrorBps=predictions.All(x=>x.ProxyNet.HasValue)&&double.IsFinite(se)?se:(double?)null,
            DescriptiveFiveSeLowerBps=predictions.All(x=>x.ProxyNet.HasValue)&&double.IsFinite(se)?mean-5*se:(double?)null,
            MultipleTestingQualification=false,NotionalOrCapitalProfitEur=(decimal?)null,
            CostMultiplier=multiplier,WeeklyOpportunityCounts=weeks.Select(w=>new {Week=w,Count=predictions.Count(x=>w<=x.At && x.At<w+604800000)}).ToArray()};
    }
    public static object Evaluate(DiscoveryInput input)
    {
        if(input.Start>=input.DevelopmentEnd || input.DevelopmentEnd>=input.SelectionEnd || input.SelectionEnd>=input.End ||
           input.Bars.Any(b=>b.Start<input.Start || b.End>input.End || b.End-b.Start!=300000 || b.Low<=0 ||
               b.Low>Math.Min(b.Open,b.Close) || b.High<Math.Max(b.Open,b.Close) || b.Volume<0))throw new ArgumentException("BDP1_SOURCE_GEOMETRY");
        var costMap=input.Costs.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        var sources=input.Bars.GroupBy(b=>b.Symbol).ToDictionary(g=>g.Key,g=>g.OrderBy(b=>b.Start).ToArray());
        if(sources.Any(g=>g.Value.Select(b=>b.Start).Distinct().Count()!=g.Value.Length))throw new ArgumentException("BDP1_DUPLICATE_BAR");
        var groups=new List<object>();var admittedSelection=new List<(string Symbol,Prediction P)>();var admittedAudit=new List<(string Symbol,Prediction P)>();
        var sourceCoverage=new List<object>();int trials=0;
        foreach(int minutes in new[]{5,15,60,240})
        {
            var lanes=sources.ToDictionary(g=>g.Key,g=>minutes==5?g.Value:Aggregate(g.Value,minutes*60000L));
            var peers=new Dictionary<long,List<double>>();
            foreach(var lane in lanes.Values)
                for(int i=1;i<lane.Length;i++)if(lane[i].Start==lane[i-1].End)
                {
                    if(!peers.TryGetValue(lane[i].End,out var list))peers[lane[i].End]=list=new();
                    list.Add(UsdSign(lane[i].Symbol)*(lane[i].Close/lane[i-1].Close-1)*10000);
                }
            foreach(var (symbol,bars) in lanes)
            {
                sourceCoverage.Add(new {Symbol=symbol,Minutes=minutes,Bars=bars.Length,First=bars.FirstOrDefault()?.Start,Last=bars.LastOrDefault()?.End});
                foreach(int horizon in new[]{1,4})foreach(int family in Enumerable.Range(0,4))
                {
                    trials++;var examples=Examples(bars,peers,horizon,family);var train=examples.Where(x=>x.KnownAt<input.DevelopmentEnd && x.Outcome.HasValue).ToArray();
                    var global=new Moments();var cells=Enumerable.Range(0,27).Select(_=>new Moments()).ToArray();
                    foreach(var x in train){global.Add(x.Outcome!.Value);cells[x.Cell].Add(x.Outcome.Value);}
                    costMap.TryGetValue(symbol,out var costs);bool financeable=costs!=null && costs.Samples>=12 && costs.CurrentMinimumMarginEur<200;
                    bool fundingCovered=costs!=null && costs.CurrentFundingScheduleKnown && minutes*horizon<=240;
                    Prediction[] Predict(long start,long end,double costMultiplier)
                    {
                        var predicted=new List<Prediction>();
                        if(costs==null || !financeable || !fundingCovered || global.N<256*horizon)return predicted.ToArray();
                        foreach(var x in examples.Where(x=>start<=x.At && x.At<end && x.KnownAt<end))
                        {
                            // Current daily swap schedule is only a declared historical
                            // scenario. Never assign zero funding across a rollover.
                            int minute=(int)((x.At/60000)%1440);
                            if(costs.SwapMinute is null || minute<=costs.SwapMinute && costs.SwapMinute<=minute+minutes*horizon || minute+minutes*horizon>=1440)continue;
                            var leaf=cells[x.Cell];if(leaf.N<32*horizon)continue;
                            double mean=(leaf.Sum+32*global.Mean)/(leaf.N+32);
                            double variance=Math.Max(global.Variance,leaf.Variance);
                            double se=Math.Sqrt(variance/(leaf.N/(double)horizon));
                            double lower=Math.Abs(mean)-2*se-costMultiplier*costs.RoundTripBps;
                            if(lower<=0)continue;
                            int side=mean>0?1:-1;double? gross=side*x.Outcome;
                            predicted.Add(new(x.At,x.KnownAt,side,gross,gross-costMultiplier*costs.RoundTripBps,lower));
                        }
                        return predicted.ToArray();
                    }
                    var select=Predict(input.DevelopmentEnd,input.SelectionEnd,2);var audit=Predict(input.SelectionEnd,input.End,2);
                    var selectBase=Predict(input.DevelopmentEnd,input.SelectionEnd,1);var auditBase=Predict(input.SelectionEnd,input.End,1);
                    var weekly=Enumerable.Range(0,13).Select(i=>select.Where(x=>input.DevelopmentEnd+i*604800000<=x.At && x.At<input.DevelopmentEnd+(i+1)*604800000).Sum(x=>x.ProxyNet??0)).ToArray();
                    double m=weekly.Average(),sew=Math.Sqrt(weekly.Sum(x=>(x-m)*(x-m))/12/13);
                    bool selected=select.Length>=26 && select.All(x=>x.ProxyNet.HasValue) && weekly.Count(x=>x!=0)>=8 && m-5*sew>0;
                    if(selected){admittedSelection.AddRange(select.Select(x=>(symbol,x)));admittedAudit.AddRange(audit.Select(x=>(symbol,x)));}
                    groups.Add(new {Id=Families[family]+"/M"+minutes+"/H"+(minutes*horizon)+"/"+symbol,Symbol=symbol,
                        FeatureView=Families[family],Minutes=minutes,HorizonMinutes=minutes*horizon,TrainingLabels=train.Length,
                        MatureNonemptyCells=cells.Count(x=>x.N>=32*horizon),MinimumVolumeCapacityCurrentScenario=financeable,
                        FundingScenarioCovered=fundingCovered,CostProxyBps=costs?.RoundTripBps,CostSamples=costs?.Samples,
                        SelectedBeforeAudit=selected,Selection=Statistics(select,input.DevelopmentEnd,input.SelectionEnd,2),
                        Audit=Statistics(audit,input.SelectionEnd,input.End,2),BaseCostSelection=Statistics(selectBase,input.DevelopmentEnd,input.SelectionEnd,1),
                        BaseCostAudit=Statistics(auditBase,input.SelectionEnd,input.End,1),ActualOrders=0,IndependentEdge=false});
                }
            }
        }
        object Ceiling(List<(string Symbol,Prediction P)> all,long start,long end)
        {
            var unique=all.GroupBy(x=>(x.Symbol,x.P.At,x.P.Exit,x.P.Side)).Select(g=>g.First()).ToArray();
            return new {UniqueUnfinancedOpportunities=unique.Length,Weeks=Enumerable.Range(0,(int)((end-start)/604800000)).Select(i=>{
                long w=start+i*604800000;int n=unique.Count(x=>w<=x.P.At && x.P.At<w+604800000);
                return new {Week=w,UnfinancedOpportunityCeiling=n,EvenUnfinancedCeilingBelow21=n<21};}).ToArray(),
                IsFinancedRoundTripCount=false,MarginConcurrencyApplied=false,Hard21Proven=false};
        }
        return new {Schema="mxm-integrated-discovery-program-v1",Trials=trials,SourceCoverage=sourceCoverage,Groups=groups,
            SelectionSystemOpportunityCeiling=Ceiling(admittedSelection,input.DevelopmentEnd,input.SelectionEnd),
            AuditSystemOpportunityCeiling=Ceiling(admittedAudit,input.SelectionEnd,input.End),
            StatisticalPolicy="FROZEN26W_TRAIN_13W_SELECTION_13W_EXPOSED_CHRONOLOGICAL_AUDIT;192_TRIALS;5SE_DESCRIPTIVE_NOT_CERTIFICATION",
            PriceBasis="BID_BAR_CLOSE_TO_FUTURE_BID_CLOSE_NOT_EXECUTION_FILLS",Costs="MINIMUM_VOLUME_CURRENT_TARIFF_AND_WORST_DEVELOPMENT_OBSERVED_SPREAD_SCENARIOS_NOT_HISTORICAL_BOUND",
            FundedNetEur=(decimal?)null,ActualFillProbability=(double?)null,HistoricalMarginConfirmed=false,
            IndependentConfirmation=false,GlobalDrawdownCertified=false,EconomicQualification=false,OrdersSubmitted=0,CloudActivated=false};
    }
}
