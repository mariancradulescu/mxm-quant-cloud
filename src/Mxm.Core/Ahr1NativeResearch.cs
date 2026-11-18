using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

// AHR1: authentic completed H1 price event research. NO fills, orders or EUR accounting.
// All fitted models, labels, causal features, actions and scores live here (not Python).
public sealed record Ahr1H1Bar(long Start,long End,long Open,long High,long Low,long Close,long Volume);
public sealed record Ahr1H1Symbol(string Symbol,Ahr1H1Bar[] Bars);
public sealed record Ahr1H1Input(string SourceRunId,string ProtocolSha256,
    string CiphertextSha256,Ahr1H1Symbol[] Symbols);

public static class Ahr1NativeResearch
{
    public const string Version="AHR1_AUTHENTIC_H1_EVENT_CORE_V1";
    const long H=3600000L;
    static readonly long T0=Utc(2025,11,16),T1=Utc(2026,5,16),
        T2=Utc(2026,7,16),T3=Utc(2026,11,16);
    static long Utc(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero)
        .ToUnixTimeMilliseconds();
    static readonly string[] Universe={"EURUSD","GBPUSD","USDJPY","AUDUSD",
        "USDCAD","XAUUSD","US500","NAS100","GER40","UK100","AUS200","JPN225"};
    static readonly string[] Names={"PRIOR","BAYES_CONTEXT","VOLATILITY_STATE","DEPTH2_TREE"};

    sealed record Example(string Symbol,long At,int Label,double Momentum,
        double VolRatio,double VolumeRatio,int PreviousState,int CurrentState,
        double BarrierWidth);
    sealed class Counts
    {
        public readonly int[] Y=new int[3];
        public void Add(int c){Y[c]++;}
        public int Total=>Y.Sum();
        public double[] Prob(double[] parent,double strength=12)
        {
            if(parent.Length!=3)throw new ArgumentException("AHR1_PROB_LENGTH");
            double denom=Total+strength;
            return Enumerable.Range(0,3).Select(k=>(Y[k]+strength*parent[k])/denom).ToArray();
        }
    }
    sealed class Node
    {
        public int Feature=-1;
        public double Threshold;
        public Node? Left,Right;
        public double[] Prob=new double[3];
        public double[] Predict(Example e)
        {
            if(Feature<0||Left is null||Right is null)return Prob;
            return Get(e,Feature)<=Threshold?Left.Predict(e):Right.Predict(e);
        }
    }
    static double Get(Example r,int f)=>f==0?r.Momentum:f==1?r.VolRatio:r.VolumeRatio;
    static readonly (int,double)[] Splits={
        (0,-0.3),(0,0.0),(0,0.3),(1,0.8),(1,1.2),(2,0.8),(2,1.2)};
    static double Impurity(List<Example> data)
    {
        if(data.Count==0)return 0;
        var n=new double[3];
        foreach(var r in data)n[r.Label]++;
        return data.Count*(1-n.Sum(k=>Math.Pow(k/data.Count,2)));
    }
    static Node Grow(List<Example> data,int depth,double[] prior)
    {
        var count=new Counts();
        foreach(var r in data)count.Add(r.Label);
        var node=new Node{Prob=count.Prob(prior)};
        if(depth>=2||data.Count<80)return node;
        double baseLoss=Impurity(data),bestGain=0;
        List<Example>? bestL=null,bestR=null;
        int bestF=-1;double bestT=0;
        foreach(var (f,t) in Splits)
        {
            var left=data.Where(x=>Get(x,f)<=t).ToList();
            var right=data.Where(x=>Get(x,f)>t).ToList();
            if(left.Count<40||right.Count<40)continue;
            double gain=baseLoss-Impurity(left)-Impurity(right);
            if(gain>bestGain)
            {
                bestGain=gain;bestL=left;bestR=right;bestF=f;bestT=t;
            }
        }
        if(bestF<0||bestGain<0.10*baseLoss||bestL is null||bestR is null)
            return node;
        node.Feature=bestF;node.Threshold=bestT;
        node.Left=Grow(bestL,depth+1,prior);
        node.Right=Grow(bestR,depth+1,prior);
        return node;
    }
    static int Group(Example x)=>
        (x.Momentum>0?2:x.Momentum<0?0:1)*2+(x.VolumeRatio>=1?1:0);
    static int State(Example x)=>x.PreviousState*2+x.CurrentState;
    static double[] Marginal(List<Example> train)
    {
        var count=new Counts();
        foreach(var x in train)count.Add(x.Label);
        return Enumerable.Range(0,3).Select(k=>(count.Y[k]+4.0)/(train.Count+12.0)).ToArray();
    }
    static double Brier(double[] p,int y)=>
        Enumerable.Range(0,3).Sum(k=>Math.Pow(p[k]-(k==y?1.0:0.0),2));
    static double LogLoss(double[] p,int y)=>-Math.Log(Math.Max(1e-12,p[y]));
    static string Week(long time)
    {
        var date=DateTimeOffset.FromUnixTimeMilliseconds(time).UtcDateTime;
        return ISOWeek.GetYear(date)+"-W"+ISOWeek.GetWeekOfYear(date).ToString("00",CultureInfo.InvariantCulture);
    }
    static string Split(long at)=>at<T1?"TRAIN":at<T2?"CAL":at<T3?"EVAL":"OUT";
    static long EndOfSplit(long at)=>at<T1?T1:at<T2?T2:T3;

    static (List<Example>,Dictionary<string,int>) Observe(Ahr1H1Symbol sym)
    {
        var data=sym.Bars;
        var stats=new Dictionary<string,int>(StringComparer.Ordinal);
        void Count(string k)=>stats[k]=stats.GetValueOrDefault(k)+1;
        if(data is null)throw new ArgumentException("AHR1_NULL_BARS");
        if(data.Length==0)return(new List<Example>(),stats);
        for(int i=0;i<data.Length;i++)
        {
            var b=data[i];
            if(b.End!=b.Start+H||b.Start<T0||b.End>T3||
               b.Low<=0||b.Low>Math.Min(b.Open,b.Close)||
               b.High<Math.Max(b.Open,b.Close)||b.Volume<0)
                throw new ArgumentException("AHR1_INVALID_BROKER_BAR");
            if(i>0&&data[i-1].Start>=b.Start)
                throw new ArgumentException("AHR1_UNSORTED_OR_DUPLICATE");
        }
        var rows=new List<Example>();
        for(int i=24;i<data.Length;i++)
        {
            Count("all_warmup_candidates");
            bool contiguous=true;
            for(int j=i-24;j<i;j++)
                if(data[j+1].Start!=data[j].End){contiguous=false;break;}
            if(!contiguous){Count("incomplete_24h_warmup");continue;}
            var b=data[i];
            if(b.End>=T3){Count("outside_eval_clock");continue;}
            double range24=0,range4=0,oldRange4=0,vol24=0,vol4=0;
            for(int j=i-23;j<=i;j++)
            {
                var z=data[j];
                range24+=(double)(z.High-z.Low)/24.0;
                vol24+=(double)z.Volume/24.0;
                if(j>=i-3){range4+=(double)(z.High-z.Low)/4.0;vol4+=(double)z.Volume/4.0;}
                if(j>=i-7&&j<=i-4)oldRange4+=(double)(z.High-z.Low)/4.0;
            }
            if(range24<=0){Count("zero_price_range");continue;}
            double momentum=((double)b.Close-data[i-4].Close)/range24;
            double volRatio=range4/range24,volumeRatio=vol24>0?vol4/vol24:1;
            int currentState=range4>=range24?1:0,prevState=oldRange4>=range24?1:0;
            double barrier=Math.Max(1.0,0.75*range24);
            // A resolved early barrier MUST NOT hide a later missing hour:
            // protocol requires the complete predeclared six-hour source window.
            bool missing=false;
            for(int j=i+1;j<=i+6;j++)
                if(j>=data.Length||data[j].Start!=data[j-1].End)
                {missing=true;break;}
            if(missing){Count("future_path_gap");continue;}
            if(data[i+6].End>EndOfSplit(b.End))
            {Count("six_hour_embargo_or_source_end");continue;}
            bool ambiguous=false;int label=2;
            for(int j=i+1;j<=i+6;j++)
            {
                var q=data[j];
                bool up=q.High>=b.Close+barrier,down=q.Low<=b.Close-barrier;
                if(up&&down){ambiguous=true;break;}
                if(up){label=0;break;}
                if(down){label=1;break;}
            }
            if(ambiguous){Count("same_hour_barrier_order_unknown");continue;}
            if(b.End<T0||b.End>=T3)continue;
            rows.Add(new Example(sym.Symbol,b.End,label,momentum,volRatio,
                volumeRatio,prevState,currentState,barrier));
            Count("label_"+(label==0?"UP":label==1?"DOWN":"NO_TOUCH"));
        }
        stats["original_h1_bars"]=data.Length;
        stats["admissible_labels"]=rows.Count;
        return(rows,stats);
    }

    static object RunSymbol(Ahr1H1Symbol sym,out Dictionary<string,object> total)
    {
        var (rows,sourceStats)=Observe(sym);
        var train=rows.Where(x=>x.At<T1).ToList();
        var marginal=Marginal(train);
        var contextual=train.GroupBy(Group).ToDictionary(x=>x.Key,x=>{
            var c=new Counts();foreach(var r in x)c.Add(r.Label);return c;});
        var regimes=train.GroupBy(State).ToDictionary(x=>x.Key,x=>{
            var c=new Counts();foreach(var r in x)c.Add(r.Label);return c;});
        var tree=Grow(train,0,marginal);
        var eval=new Dictionary<string,object>();
        total=new Dictionary<string,object>();
        foreach(var split in new[]{"TRAIN","CAL","EVAL"})
        {
            var sample=rows.Where(x=>Split(x.At)==split).ToList();
            var modelScore=new Dictionary<string,object>();
            for(int k=0;k<4;k++)
            {
                double sumB=0,sumL=0;
                var signals=new Dictionary<string,int>(StringComparer.Ordinal);
                var reliability=new int[5];
                var positives=new int[5];
                foreach(var row in sample)
                {
                    double[] probs=k switch {
                        0=>marginal,
                        1=>contextual.TryGetValue(Group(row),out var a)?a.Prob(marginal):marginal,
                        2=>regimes.TryGetValue(State(row),out var b)?b.Prob(marginal):marginal,
                        _=>tree.Predict(row)};
                    sumB+=Brier(probs,row.Label);
                    sumL+=LogLoss(probs,row.Label);
                    var max=Math.Max(probs[0],probs[1]);
                    int bin=Math.Min(4,(int)Math.Floor(Math.Max(0,Math.Min(0.999999,max))*5));
                    reliability[bin]++;if(row.Label==(probs[0]>=probs[1]?0:1))positives[bin]++;
                    bool signal=(probs[0]>=0.60&&probs[0]-probs[1]>=0.20)||
                                (probs[1]>=0.60&&probs[1]-probs[0]>=0.20);
                    if(signal){string week=Week(row.At);signals[week]=signals.GetValueOrDefault(week)+1;}
                }
                modelScore[Names[k]]=new{Count=sample.Count,
                    Brier=sample.Count>0?(double?)(sumB/sample.Count):null,
                    LogLoss=sample.Count>0?(double?)(sumL/sample.Count):null,
                    ProposalCount=signals.Values.Sum(),
                    ProposalCountsByWeek=signals,
                    ReliabilityBinCounts=reliability,
                    ReliabilityDirectionalHits=positives};
            }
            eval[split]=modelScore;
        }
        total["all"]=eval;
        total["trainN"]=train.Count;
        return new{Symbol=sym.Symbol,Source=sourceStats,TrainDistribution=marginal,
            Eval=eval,TreeRootSplit=tree.Feature,
            ValidPriceObservationsOnly=true,FundedTrades=(int?)null,
            BrokerCostEur=(decimal?)null,NetEur=(decimal?)null,
            Hard21Certified=false,FloatingDdCertified=false,IndependentConfirmation=false};
    }
    public static object Run(Ahr1H1Input input)
    {
        if(input is null||input.Symbols is null||
           input.SourceRunId!="43817213663"||
           input.ProtocolSha256?.Length!=64||input.CiphertextSha256?.Length!=64||
           input.Symbols.Length!=Universe.Length||
           !input.Symbols.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
           .SequenceEqual(Universe.OrderBy(x=>x,StringComparer.Ordinal),StringComparer.Ordinal))
            throw new ArgumentException("AHR1_UNBOUND_AUTHENTIC_ORIGINAL_SOURCE");
        var reports=new List<object>();
        var perSymbol=new List<(string Symbol,Dictionary<string,object> scores)>();
        foreach(var item in input.Symbols.OrderBy(x=>x.Symbol,StringComparer.Ordinal))
        {
            var report=RunSymbol(item,out var result);
            reports.Add(report);
            perSymbol.Add((item.Symbol,result));
        }
        return new {Protocol=Version,SourceClass="AUTHENTIC_PEPPERSTONE_ORIGINAL_HXC1_H1",
            input.SourceRunId,input.ProtocolSha256,input.CiphertextSha256,
            SourceTimeStartUtc="2025-11-16",SourceTimeEndUtc="2026-11-16",
            SplitTrainEndUtc="2026-05-16",SplitCalibrationEndUtc="2026-07-16",
            SplitEvaluationEndUtc="2026-11-16",Models=Names,
            Results=reports,Limitations=new[]{
                "EXPOSED_HISTORICAL_EVALUATION_NOT_INDEPENDENT_12_MONTHS",
                "H1_BAR_BARRIERS_NO_INTRABAR_FILL_TIMING",
                "NO_AUTHENTIC_HISTORICAL_BIDASK_OR_ORDER_FILLS_IN_THIS_STUDY",
                "NO_VERIFIED_EUR300_LEGAL_MINIMUM_COSTS_CONVERSIONS_OR_CONTINUOUS_DD",
                "NO_SYSTEMIC_FUNDED_HARD21_OR_NET_EUR_CLAIM",
                "OVERLAPPING_LABELS_PRECLUDE_NAIVE_INDEPENDENCE_SIGNIFICANCE"},
            OwnerOneBookInitialCapitalEur=300,
            GenuineFundedTrades=(int?)null,NetEur=(decimal?)null,
            SystemicHard21Certified=false,MaximumFloatingDrawdownCertified=false,
            IndependentTwelveMonthsConfirmed=false,
            OrdersSubmitted=0,CloudActivated=false,EconomicQualification=false};
    }
}
