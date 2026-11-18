using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

// SHD1: NEW frozen historical price-information study. No order, fills or money engine.
// Reuse the genuine OHLC integer record type; AHR1's implementation is untouched.
public sealed record Shd1Stream(string Symbol,string Period,Ahr1H1Bar[] Bars);
public sealed record Shd1Input(string SourceRunId,string ProtocolSha256,
    string CiphertextSha256,Shd1Stream[] Streams);

public static class Shd1NativeDiscovery
{
    public const string Version="SHD1_SESSION_AWARE_H1_M15_CSHARP_V1";
    static long Utc(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero)
        .ToUnixTimeMilliseconds();
    const long Hour=3600000L, Minute=60000L;
    static readonly string[] Symbols={"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD",
        "XAUUSD","US500","NAS100","GER40","UK100","AUS200","JPN225"};
    static readonly string[] Models={"PRIOR","BAYES_SESSION_CONTEXT",
        "OBSERVED_STATE_TRANSITION","QUANTILE_DEPTH2_TREE"};

    sealed record Rule(long Start,long TrainEnd,long CalEnd,long End,long Period,
        int MinTrain,int MinCal,int MinEval);
    static Rule Settings(string p)=>p switch
    {
        "H1"=>new Rule(Utc(2025,11,16),Utc(2026,5,16),Utc(2026,7,16),
            Utc(2026,11,16),Hour,300,120,160),
        "M15"=>new Rule(Utc(2026,8,17),Utc(2026,9,28),Utc(2026,10,19),
            Utc(2026,11,16),15*Minute,500,160,160),
        _=>throw new ArgumentException("SHD1_UNKNOWN_PERIOD")
    };

    sealed record Row(long At,int Label,double[] X,int Context,int State);
    sealed class Counts
    {
        public readonly int[] Y=new int[3];
        public void Add(int k){Y[k]++;}
        public int Total=>Y[0]+Y[1]+Y[2];
        public double[] Prob(double[] parent,double strength)
        {
            return Enumerable.Range(0,3)
                .Select(k=>(Y[k]+strength*parent[k])/(Total+strength)).ToArray();
        }
    }
    sealed class Tree
    {
        public int Feature=-1;
        public double Threshold;
        public Tree? Left,Right;
        public double[] Prob=Array.Empty<double>();
        public int Leaves=>Feature<0||Left is null||Right is null?1:Left.Leaves+Right.Leaves;
        public int Internal=>Feature<0||Left is null||Right is null?0:1+Left.Internal+Right.Internal;
        public double[] Predict(Row r)=>Feature<0||Left is null||Right is null?Prob:
            r.X[Feature]<=Threshold?Left.Predict(r):Right.Predict(r);
    }
    static double Gini(List<Row> list)
    {
        if(list.Count==0)return 0;
        var counts=new int[3];
        foreach(var r in list)counts[r.Label]++;
        return list.Count*(1.0-counts.Sum(n=>Math.Pow((double)n/list.Count,2)));
    }
    static double Quantile(double[] v,double q)
    {
        var a=(double[])v.Clone();
        Array.Sort(a);
        if(a.Length==0)return 0;
        var at=(a.Length-1)*q;
        int k=(int)Math.Floor(at);
        return a[k]+(a[Math.Min(a.Length-1,k+1)]-a[k])*(at-k);
    }
    static Tree Grow(List<Row> data,int depth,double[] parent,
        (int Feature,double Threshold)[] candidates)
    {
        var counts=new Counts();
        foreach(var row in data)counts.Add(row.Label);
        var node=new Tree{Prob=counts.Prob(parent,24)};
        if(depth==2||data.Count<128)return node;
        double baseLoss=Gini(data),bestGain=0;
        int bestFeature=-1;double bestThreshold=0;
        List<Row>? bestLeft=null,bestRight=null;
        foreach(var (feature,threshold) in candidates)
        {
            var left=data.Where(r=>r.X[feature]<=threshold).ToList();
            var right=data.Where(r=>r.X[feature]>threshold).ToList();
            if(left.Count<64||right.Count<64)continue;
            double gain=baseLoss-Gini(left)-Gini(right);
            if(gain>bestGain)
            {
                bestGain=gain;bestFeature=feature;bestThreshold=threshold;
                bestLeft=left;bestRight=right;
            }
        }
        if(bestFeature<0||bestGain<Math.Max(.005*baseLoss,.002*data.Count)||
           bestLeft is null||bestRight is null)return node;
        node.Feature=bestFeature;node.Threshold=bestThreshold;
        node.Left=Grow(bestLeft,depth+1,parent,candidates);
        node.Right=Grow(bestRight,depth+1,parent,candidates);
        return node;
    }

    static string Week(long time)
    {
        var dt=DateTimeOffset.FromUnixTimeMilliseconds(time).UtcDateTime;
        return ISOWeek.GetYear(dt)+"-W"+
            ISOWeek.GetWeekOfYear(dt).ToString("00",CultureInfo.InvariantCulture);
    }
    static int Split(long time,Rule r)=>time<r.TrainEnd?0:time<r.CalEnd?1:time<r.End?2:-1;
    static long SplitEnd(int split,Rule r)=>split switch{0=>r.TrainEnd,
        1=>r.CalEnd,2=>r.End,_=>r.End};
    static double Brier(double[] p,int y)=>Enumerable.Range(0,3)
        .Sum(i=>Math.Pow(p[i]-(i==y?1.0:0.0),2));
    static double LogLoss(double[] p,int y)=>-Math.Log(Math.Max(1e-12,p[y]));
    static double[] Marginal(List<Row> rows)
    {
        var counts=new Counts();
        foreach(var row in rows)counts.Add(row.Label);
        return Enumerable.Range(0,3)
            .Select(k=>(counts.Y[k]+4.0)/(rows.Count+12.0)).ToArray();
    }
    static Dictionary<string,int> Stat()=>new(StringComparer.Ordinal);
    static void Count(Dictionary<string,int> d,string k,int n=1)=>
        d[k]=d.GetValueOrDefault(k)+n;

    // Session-breaks are measured on real timestamps; no invented weekend bars.
    static (List<Row> Rows,Dictionary<string,int> Stats) Observe(Shd1Stream stream,Rule r)
    {
        var b=stream.Bars??throw new ArgumentException("SHD1_NULL_BARS");
        var stats=Stat();
        var rows=new List<Row>();
        int age=0;
        for(int i=0;i<b.Length;i++)
        {
            var z=b[i];
            if(z.End-z.Start!=r.Period||z.Start<r.Start||z.End>r.End||
               z.Open<=0||z.Close<=0||z.Low<=0||z.High<z.Low||
               z.Low>Math.Min(z.Open,z.Close)||z.High<Math.Max(z.Open,z.Close)||
               z.Volume<0||(i>0&&z.Start<b[i-1].End))
                throw new ArgumentException("SHD1_INVALID_OR_OVERLAPPING_BROKER_BARS");
            bool contiguous=i>0&&z.Start==b[i-1].End;
            if(!contiguous)
            {
                age=1;
                Count(stats,"real_session_starts");
                if(i>0)Count(stats,"observed_session_gaps");
            }
            else age=Math.Min(10000,age+1);
            if(i<12)continue;
            Count(stats,"complete_bar_with_12_observed_warmup");
            // 12 REAL observed bars, not 12 consecutive 24/7 clock periods.
            double range=0,volume=0;
            for(int j=i-11;j<=i;j++)
            {
                range+=(double)(b[j].High-b[j].Low)/12.0;
                volume+=(double)b[j].Volume/12.0;
            }
            if(range<=0){Count(stats,"zero_observed_range");continue;}
            double m=contiguous?((double)z.Close-b[i-1].Close)/range:0;
            double relativeRange=(z.High-z.Low)/range;
            double relativeVolume=volume>0?z.Volume/volume:1;
            double gapHours=contiguous?0:Math.Min(72.0,Math.Max(0.0,
                (double)(z.Start-b[i-1].End)/Hour));
            double utcHour=DateTimeOffset.FromUnixTimeMilliseconds(z.End).UtcDateTime.TimeOfDay.TotalHours;
            double[] features={Math.Max(-8,Math.Min(8,m)),relativeRange,
                relativeVolume,Math.Min(4,age),gapHours,utcHour/24.0};
            int momentumSign=m>0?2:m<0?0:1;
            int context=(momentumSign*2+(age>=3?1:0))*2+(relativeVolume>=1?1:0);
            // Previous volatility regime is valid only for completed adjacent observations.
            bool previousHigh=contiguous&&b[i-1].High-b[i-1].Low>=range;
            int state=((relativeRange>=1?1:0)*2+(previousHigh?1:0))*2+
                (contiguous?0:1);
            int split=Split(z.End,r);
            if(split<0){Count(stats,"out_of_split");continue;}
            bool fullPath=true;
            for(int k=i+1;k<=i+3;k++)
            {
                if(k>=b.Length||b[k].Start!=b[k-1].End)
                {fullPath=false;break;}
            }
            if(!fullPath){Count(stats,"path_unknown_session_or_source_gap");continue;}
            if(b[i+3].End>=SplitEnd(split,r))
            {Count(stats,"three_bar_chronological_embargo");continue;}
            double width=Math.Max(1.0,.75*range);
            bool ambiguous=false;
            int label=2;
            for(int k=i+1;k<=i+3;k++)
            {
                bool up=(double)b[k].High>=z.Close+width;
                bool down=(double)b[k].Low<=z.Close-width;
                if(up&&down){ambiguous=true;break;}
                if(up){label=0;break;}
                if(down){label=1;break;}
            }
            if(ambiguous){Count(stats,"ambiguous_first_touch");continue;}
            rows.Add(new Row(z.End,label,features,context,state));
            Count(stats,split==0?"train_eligible":split==1?"cal_eligible":"eval_eligible");
            Count(stats,label==0?"first_touch_up":label==1?"first_touch_down":"no_touch");
        }
        stats["original_bars"]=b.Length;
        stats["admissible_rows"]=rows.Count;
        return(rows,stats);
    }

    sealed class Weekly
    {
        public double Sum;
        public int N;
    }
    static object Score(List<Row> sample,int variant,double[] baseline,
        Dictionary<int,Counts> context,Dictionary<int,Counts> states,Tree tree)
    {
        double sumB=0,sumL=0,sumBaseB=0;
        int proposed=0,material=0;
        var byWeek=new SortedDictionary<string,Weekly>(StringComparer.Ordinal);
        var proposals=new SortedDictionary<string,int>(StringComparer.Ordinal);
        foreach(var r in sample)
        {
            double[] p=variant switch
            {
                0=>baseline,
                1=>context.TryGetValue(r.Context,out var c)?c.Prob(baseline,24):baseline,
                2=>states.TryGetValue(r.State,out var t)?t.Prob(baseline,24):baseline,
                _=>tree.Predict(r)
            };
            double b=Brier(p,r.Label),baseB=Brier(baseline,r.Label);
            sumB+=b;sumL+=LogLoss(p,r.Label);sumBaseB+=baseB;
            if(Enumerable.Range(0,3).Max(k=>Math.Abs(p[k]-baseline[k]))>.02)material++;
            bool take=(p[0]>=.55&&p[0]-p[1]>=.10)||
                      (p[1]>=.55&&p[1]-p[0]>=.10);
            var week=Week(r.At);
            if(take){proposed++;proposals[week]=proposals.GetValueOrDefault(week)+1;}
            if(!byWeek.TryGetValue(week,out var w))
            {w=new Weekly();byWeek.Add(week,w);}
            w.Sum+=baseB-b;w.N++;
        }
        var weeklyMeans=byWeek.ToDictionary(x=>x.Key,x=>x.Value.Sum/x.Value.N);
        var vals=weeklyMeans.Values.ToArray();
        double? ciLow=null,ciHigh=null,weeklyMean=null;
        if(vals.Length>0)weeklyMean=vals.Average();
        if(vals.Length>=8)
        {
            double sq=vals.Sum(x=>Math.Pow(x-weeklyMean!.Value,2));
            double se=Math.Sqrt(sq/(vals.Length-1)/vals.Length);
            ciLow=weeklyMean-1.96*se;ciHigh=weeklyMean+1.96*se;
        }
        return new{
            Count=sample.Count,
            Brier=sample.Count>0?(double?)(sumB/sample.Count):null,
            PriorBrier=sample.Count>0?(double?)(sumBaseB/sample.Count):null,
            IncrementalBrier=sample.Count>0?(double?)((sumBaseB-sumB)/sample.Count):null,
            LogLoss=sample.Count>0?(double?)(sumL/sample.Count):null,
            MaterialDifferentFraction=sample.Count>0?(double?)material/sample.Count:null,
            DiagnosticProposals=proposed,DiagnosticProposalsByWeek=proposals,
            WeeklyPairedIncrementalBrier=weeklyMeans,
            PositiveWeeks=vals.Count(x=>x>0),
            EligibleWeeks=vals.Length,
            PositiveWeekFraction=vals.Length>0?(double?)vals.Count(x=>x>0)/vals.Length:null,
            MeanWeeklyPairedIncrementalBrier=weeklyMean,
            Descriptive95Low=ciLow,Descriptive95High=ciHigh,
            WeeklyInferenceIsDependenceRobust=false
        };
    }

    static object RunStream(Shd1Stream stream)
    {
        var rule=Settings(stream.Period);
        var (rows,source)=Observe(stream,rule);
        var train=rows.Where(r=>r.At<rule.TrainEnd).ToList();
        var cal=rows.Where(r=>r.At>=rule.TrainEnd&&r.At<rule.CalEnd).ToList();
        var eval=rows.Where(r=>r.At>=rule.CalEnd).ToList();
        bool admitted=train.Count>=rule.MinTrain&&cal.Count>=rule.MinCal&&
            eval.Count>=rule.MinEval;
        if(!admitted)return new{stream.Symbol,stream.Period,Source=source,
            Train=train.Count,Cal=cal.Count,Eval=eval.Count,
            Status="INSUFFICIENT_CHRONOLOGICAL_SUPPORT_NO_MODEL_SCORE",
            Learn=(object?)null,Scores=(object?)null,
            Funding=(object?)null};
        var prior=Marginal(train);
        var context=new Dictionary<int,Counts>();
        var states=new Dictionary<int,Counts>();
        foreach(var r in train)
        {
            if(!context.TryGetValue(r.Context,out var a)){a=new Counts();context[r.Context]=a;}
            a.Add(r.Label);
            if(!states.TryGetValue(r.State,out var b)){b=new Counts();states[r.State]=b;}
            b.Add(r.Label);
        }
        var thresholds=new List<(int Feature,double Threshold)>();
        for(int f=0;f<6;f++)
        {
            int at=f;
            var values=train.Select(x=>x.X[at]).ToArray();
            foreach(var q in new[]{.20,.40,.60,.80})
            {
                var threshold=Quantile(values,q);
                if(!thresholds.Any(x=>x.Feature==at&&x.Threshold==threshold))
                    thresholds.Add((at,threshold));
            }
        }
        var tree=Grow(train,0,prior,thresholds.ToArray());
        var scores=new Dictionary<string,object>();
        foreach(var (name,sample) in new[]{("TRAIN",train),("CAL",cal),("EVAL",eval)})
        {
            var perModel=new Dictionary<string,object>();
            for(int i=0;i<Models.Length;i++)
                perModel[Models[i]]=Score(sample,i,prior,context,states,tree);
            scores.Add(name,perModel);
        }
        return new{stream.Symbol,stream.Period,Source=source,Train=train.Count,
            Cal=cal.Count,Eval=eval.Count,Status="GATED_AUTHENTIC_PRICE_PREDICTION",
            Learn=(object)new{
                TrainMarginal=prior,
                ContextCellsWithTrainSupport=context.Count,
                ContextTrainSupport=context.ToDictionary(x=>x.Key.ToString(CultureInfo.InvariantCulture),x=>x.Value.Total),
                ObservedStateCellsWithTrainSupport=states.Count,
                ObservedStateTrainSupport=states.ToDictionary(x=>x.Key.ToString(CultureInfo.InvariantCulture),x=>x.Value.Total),
                TreeRootSplit=tree.Feature,TreeRootThreshold=tree.Feature>=0?(double?)tree.Threshold:null,
                TreeInternalNodes=tree.Internal,TreeLeaves=tree.Leaves,
                TreeActuallyLearned=tree.Feature>=0,
                TreeLearningVerdict=tree.Feature>=0?"NONLINEAR_TRAIN_SPLITS_LEARNED":"TREE_NOT_LEARNED",
                ModelDiscoveryIsCertified=false
            },
            Scores=(object)scores,Funding=(object?)null};
    }

    public static object Run(Shd1Input input)
    {
        if(input is null||input.Streams is null||
           input.SourceRunId!="43817213663"||
           input.ProtocolSha256?.Length!=64||input.CiphertextSha256?.Length!=64||
           input.Streams.Length!=24||
           input.Streams.Select(x=>x.Symbol+"/"+x.Period)
               .OrderBy(x=>x,StringComparer.Ordinal)
               .Distinct(StringComparer.Ordinal).Count()!=24||
           !input.Streams.Select(x=>x.Symbol).Distinct(StringComparer.Ordinal)
               .OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(Symbols.OrderBy(x=>x,StringComparer.Ordinal),StringComparer.Ordinal)||
           input.Streams.Any(x=>x.Period is not ("H1" or "M15")))
            throw new ArgumentException("SHD1_UNBOUND_HXC1_ORIGINAL_SOURCE");
        var reports=input.Streams.OrderBy(x=>x.Symbol,StringComparer.Ordinal)
            .ThenBy(x=>x.Period,StringComparer.Ordinal).Select(RunStream).ToArray();
        return new{
            Protocol=Version,SourceClass="AUTHENTIC_PEPPERSTONE_HXC1_H1_M15_BAR_HISTORY",
            input.SourceRunId,input.ProtocolSha256,input.CiphertextSha256,
            Streams=reports,Models,
            Label="NEXT_THREE_CONTIGUOUS_COMPLETED_BARS_FIRST_OBSERVED_SYMMETRIC_TOUCH",
            Exposure="PREVIOUSLY_HISTORICALLY_EXPOSED_NOT_INDEPENDENT_CONFIRMATION",
            Limitations=new[]{
                "H1_M15_BAR_EXTREMA_ARE_NOT_EXECUTABLE_BROKER_FILLS",
                "SESSION_BREAKS_NO_FORWARD_FILL_NO_GAP_RETURNS",
                "ROLLING_LABEL_OVERLAP_AND_MULTI_MARKET_DEPENDENCE",
                "DESCRIPTIVE_WEEK_NORMAL_INTERVAL_NOT_ROBUST_SIGNIFICANCE",
                "MULTIPLE_MODELS_SYMBOLS_RESOLUTIONS_NO_EX_POST_WINNER_PROMOTION",
                "HISTORICAL_BIDASK_FEES_MARGIN_FINANCING_FX_AND_CONTINUOUS_DD_UNPROVEN"
            },
            InitialSharedCapitalEur=300,
            AuthenticFundedTrades=(int?)null,
            NetEur=(decimal?)null,
            FundedHard21Certified=false,ContinuousFloatingDd30Certified=false,
            IndependentTwelveMonthsConfirmed=false,
            OrdersSubmitted=0,CloudActivated=false,EconomicQualification=false
        };
    }

    public static object SelfTest()
    {
        long t=Utc(2026,9,7);
        var bars=new List<Ahr1H1Bar>();
        for(int i=0;i<55;i++)
        {
            long start=t+(i<25?i:i+48)*Hour;
            long open=1000+i*3;
            bars.Add(new Ahr1H1Bar(start,start+Hour,open,open+7,open-5,open+2,25+i));
        }
        var (rows,stats)=Observe(new Shd1Stream("EURUSD","H1",bars.ToArray()),
            Settings("H1"));
        if(stats.GetValueOrDefault("observed_session_gaps")!=1||
           !rows.Any(x=>x.X[4]>0&&x.X[0]==0))
            throw new InvalidOperationException("SHD1_CAUSAL_SESSION_GAP_SELFTEST_FAILED");
        var prior=new[]{.33,.33,.34};
        var synthetic=new List<Row>();
        for(int i=0;i<400;i++)
        {
            double f=i%2==0?-.8:.8;
            synthetic.Add(new Row(t+i*Hour,f<0?0:1,
                new[]{f,1.0,1.0,4.0,0.0,.5},0,0));
        }
        var split=Grow(synthetic,0,prior,new[]{(0,0.0)});
        if(split.Feature!=0||split.Internal<1||
           Math.Abs(split.Predict(synthetic[0])[0]-
                    split.Predict(synthetic[1])[0])<.10)
            throw new InvalidOperationException("SHD1_SYNTHETIC_TREE_LEARNING_SELFTEST_FAILED");
        return new{FixtureOnly=true,OriginalBrokerObservations=0,
            SessionGapDetected=true,SyntheticTreeLearned=true,
            OriginalEconomicResult=false,CloudOrderActions=0};
    }
}
