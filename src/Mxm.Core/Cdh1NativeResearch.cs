using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

// CDH1: ALL clocks are selected causally. Censoring and ambiguous outcomes remain
// in the denominator. No order, entry fill, money or Cloud activation exists here.
// Closed AHR1 / SHD1 code and receipts are not modified or rerun.
public sealed record Cdh1Stream(string Symbol,string Period,Ahr1H1Bar[] Bars);
public sealed record Cdh1Input(string SourceRunId,string ProtocolSha256,
    string CiphertextSha256,Cdh1Stream[] Streams);

public static class Cdh1NativeResearch
{
    public const string Version="CDH1_EXANTE_COMPETING_RISKS_DIRECTIONAL_V1";
    const long H=3600000L, M=60000L;
    static long U(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero)
        .ToUnixTimeMilliseconds();
    static readonly string[] Symbols={"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD",
        "XAUUSD","US500","NAS100","GER40","UK100","AUS200","JPN225"};
    static readonly string[] Names={"PRIOR","CONTEXT_BAYES_HAZARD","L2_SOFTMAX_COMPETING_HAZARD"};
    sealed record Rule(long Start,long TrainEnd,long CalEnd,long End,long Step,
        int MinTrain,int MinCal,int MinEval);
    static Rule Spec(string p)=>p switch
    {
        "H1"=>new(U(2025,11,16),U(2026,5,16),U(2026,7,16),
            U(2026,11,16),H,300,120,160),
        "M15"=>new(U(2026,8,17),U(2026,9,14),U(2026,9,21),
            U(2026,11,16),15*M,500,160,500),
        _=>throw new ArgumentException("CDH1_INVALID_PERIOD")
    };
    // Evidence at a genuinely observed future step: 0 survived, 1 UP,
    // 2 DOWN, 3 dual-touch unknown order. CENSORED is zero subsequent steps,
    // not a price outcome.
    sealed record Decision(long At,int Outcome,int[] Steps,double[] X,
        int Context,int MomentumSide);
    sealed class Counts
    {
        public readonly double[] Y=new double[3];
        public int Ambiguous;
        public double Total=>Y.Sum();
        public void Add(int evidence,double ambiguityUp)
        {
            if(evidence==3)
            {
                Y[1]+=ambiguityUp;Y[2]+=1-ambiguityUp;Ambiguous++;
            }
            else Y[evidence]++;
        }
        public double[] Probability(double[] prior,double strength)=>
            Enumerable.Range(0,3).Select(k=>(Y[k]+strength*prior[k])/(Total+strength))
                .ToArray();
    }
    sealed record Scored(
        int ExAnteDecisions,int ObservedRiskSteps,int CensoredDecisions,
        int AmbiguousDecisions,int UpFirst,int DownFirst,int NoTouch,
        double? MeanObservedNegativeLogLikelihoodPerDecision,
        double? PriorMeanObservedNegativeLogLikelihoodPerDecision,
        double? IncrementalObservedLogLikelihoodPerDecision,
        double? MeanObservedNegativeLogLikelihoodPerRiskStep,
        int MaterialForecastDifferences,double? MaterialDifferenceFraction,
        int Proposals,int Wins,int OppositeFirst,int ProposalNoTouch,
        int ProposalAmbiguous,int ProposalCensored,
        double? ConservativeDirectionalSuccessLower,
        double? ConservativeDirectionalSuccessUpper,
        int MatchedMomentumWins,int MatchedContrarianWins,
        int AllClockMomentumProposals,int AllClockMomentumWins,
        int AllClockContrarianProposals,int AllClockContrarianWins,
        Dictionary<string,int> ProposalsByIsoWeek,
        Dictionary<string,double> PairedWeeklyObservedLogLikelihoodGain,
        int EvaluationWeeks,int PositiveGainWeeks,double? WeeklyMeanGain,
        double? WeeklyNormalReference95Low,double? WeeklyNormalReference95High,
        int ProposalWeeksWith21,bool StatisticalCertificate);

    static string Week(long t)
    {
        var dt=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return ISOWeek.GetYear(dt)+"-W"+
            ISOWeek.GetWeekOfYear(dt).ToString("00",CultureInfo.InvariantCulture);
    }
    static int Split(long t,Rule r)=>t<r.TrainEnd?0:t<r.CalEnd?1:t<r.End?2:-1;
    static long SplitEnd(int split,Rule r)=>split switch
    {
        0=>r.TrainEnd,1=>r.CalEnd,2=>r.End,_=>r.End
    };
    static void Inc(Dictionary<string,int> d,string key,int n=1)=>
        d[key]=d.GetValueOrDefault(key)+n;
    static double Clamp(double x,double lo,double hi)=>Math.Max(lo,Math.Min(hi,x));

    static (List<Decision>,Dictionary<string,int>) Build(Cdh1Stream s,Rule r)
    {
        var bars=s.Bars??throw new ArgumentException("CDH1_NULL_SOURCE");
        var counts=new Dictionary<string,int>(StringComparer.Ordinal);
        var decisions=new List<Decision>();
        int age=0;
        for(int i=0;i<bars.Length;i++)
        {
            var b=bars[i];
            if(b.Start<r.Start||b.End>r.End||b.End-b.Start!=r.Step||
               b.Open<=0||b.Close<=0||b.Low<=0||b.High<b.Low||
               b.Low>Math.Min(b.Open,b.Close)||b.High<Math.Max(b.Open,b.Close)||
               b.Volume<0||(i>0&&b.Start<bars[i-1].End))
                throw new ArgumentException("CDH1_BAD_BROKER_SOURCE_BAR");
            bool adjacent=i>0&&b.Start==bars[i-1].End;
            if(!adjacent)
            {
                age=1;Inc(counts,"real_session_starts");
                if(i>0)Inc(counts,"true_session_gaps");
            }
            else age=Math.Min(10000,age+1);
            // Ex-ante admission is ONLY about current & past observations.
            if(i<12)continue;
            Inc(counts,"causal_12_observed_warmup");
            double avgRange=0,avgVolume=0;
            for(int k=i-11;k<=i;k++)
            {
                avgRange+=(double)(bars[k].High-bars[k].Low)/12;
                avgVolume+=(double)bars[k].Volume/12;
            }
            // Zero historical range is an observable source gate at t.
            if(avgRange<=0){Inc(counts,"observable_zero_range");continue;}
            int split=Split(b.End,r);
            if(split<0){Inc(counts,"out_of_predeclared_split");continue;}
            // No next-bar existence or outcome is tested above this line.
            double momentum=adjacent?((double)b.Close-bars[i-1].Close)/avgRange:0;
            double gap=adjacent?0:Clamp((double)(b.Start-bars[i-1].End)/H,0,72);
            double vol=avgVolume>0?b.Volume/avgVolume:1;
            double utcHour=DateTimeOffset.FromUnixTimeMilliseconds(b.End)
                .UtcDateTime.TimeOfDay.TotalHours;
            int sign=momentum>0?1:momentum<0?-1:0;
            int context=((sign+1)*2+(age>=3?1:0))*2+(vol>=1?1:0);
            double[] f={1,Clamp(momentum,-6,6),
                Clamp((b.High-b.Low)/avgRange,0,6),
                Clamp(vol,0,6),Math.Min(4,age),gap,utcHour/24};
            double width=Math.Max(1,.75*avgRange);
            var observed=new List<int>(3);
            int outcome=4; // CENSORED until three full steps are really observed
            long previousEnd=b.End;
            for(int k=1;k<=3;k++)
            {
                if(i+k>=bars.Length||bars[i+k].Start!=previousEnd||
                   bars[i+k].End>=SplitEnd(split,r))
                    break;
                var next=bars[i+k];
                bool up=next.High>=b.Close+width;
                bool down=next.Low<=b.Close-width;
                int evidence=up&&down?3:up?1:down?2:0;
                observed.Add(evidence);
                previousEnd=next.End;
                if(evidence!=0)
                {
                    outcome=evidence==1?0:evidence==2?1:3;
                    break;
                }
                if(k==3)outcome=2; // full 3-step survival: true NO_TOUCH
            }
            decisions.Add(new Decision(b.End,outcome,observed.ToArray(),f,context,sign));
            Inc(counts,split==0?"TRAIN_EXANTE":split==1?"CAL_EXANTE":"EVAL_EXANTE");
            Inc(counts,outcome==0?"FIRST_UP":outcome==1?"FIRST_DOWN":
                outcome==2?"OBSERVED_NO_TOUCH":outcome==3?"AMBIGUOUS":"CENSORED");
        }
        counts["original_real_bars"]=bars.Length;
        counts["total_exante_decisions"]=decisions.Count;
        return(decisions,counts);
    }

    static double[] Prior(List<Decision> train)
    {
        var c=new Counts();
        foreach(var d in train)
            foreach(int e in d.Steps)
                if(e!=3)c.Add(e,.5);
        double denom=c.Total+12;
        double up=(c.Y[1]+4)/denom,down=(c.Y[2]+4)/denom;
        // For reporting and score order [none,up,down].
        return new[]{(c.Y[0]+4)/denom,up,down};
    }
    static Dictionary<int,Counts> Context(List<Decision> train,double[] prior,
        out int ambiguityCount)
    {
        ambiguityCount=0;
        var groups=new Dictionary<int,Counts>();
        double fractional=prior[1]/Math.Max(1e-12,prior[1]+prior[2]);
        foreach(var d in train)
        {
            if(!groups.TryGetValue(d.Context,out var c))
            {c=new Counts();groups[d.Context]=c;}
            foreach(var e in d.Steps)
            {
                c.Add(e,fractional);
                if(e==3)ambiguityCount++;
            }
        }
        return groups;
    }

    sealed class Softmax
    {
        public readonly double[,] Beta=new double[2,7];
        public readonly double[] Mean=new double[7],Scale=new double[7];
        public int TrainedRiskSteps;
        public double[] Normalized(double[] f)
        {
            var a=new double[7];a[0]=1;
            for(int k=1;k<7;k++)a[k]=Clamp((f[k]-Mean[k])/Scale[k],-6,6);
            return a;
        }
        public double[] Predict(double[] f)
        {
            var x=Normalized(f);
            double up=0,down=0;
            for(int k=0;k<7;k++){up+=Beta[0,k]*x[k];down+=Beta[1,k]*x[k];}
            // Softmax with stable subtract-max, none has reference logit 0.
            double shift=Math.Max(0,Math.Max(up,down));
            double a=Math.Exp(up-shift),b=Math.Exp(down-shift),c=Math.Exp(-shift);
            double z=a+b+c;
            return new[]{c/z,a/z,b/z};
        }
        public double CoefficientNorm()
        {
            double s=0;
            foreach(double v in Beta)s+=v*v;
            return Math.Sqrt(s);
        }
    }
    static Softmax FitSoftmax(List<Decision> train)
    {
        var model=new Softmax();
        for(int k=1;k<7;k++)
        {
            model.Mean[k]=train.Average(d=>d.X[k]);
            double variance=train.Average(d=>Math.Pow(d.X[k]-model.Mean[k],2));
            model.Scale[k]=Math.Max(1e-6,Math.Sqrt(variance));
        }
        var observations=train.SelectMany(d=>d.Steps.Select(e=>new{
            X=model.Normalized(d.X),Evidence=e})).ToArray();
        model.TrainedRiskSteps=observations.Length;
        if(observations.Length==0)return model;
        for(int iter=0;iter<160;iter++)
        {
            double[,] grad=new double[2,7];
            foreach(var o in observations)
            {
                double up=0,down=0;
                for(int k=0;k<7;k++)
                {up+=model.Beta[0,k]*o.X[k];down+=model.Beta[1,k]*o.X[k];}
                double shift=Math.Max(0,Math.Max(up,down));
                double a=Math.Exp(up-shift),b=Math.Exp(down-shift),c=Math.Exp(-shift);
                double z=a+b+c,pu=a/z,pd=b/z;
                double effectiveUp=o.Evidence==1?1:
                    o.Evidence==3?pu/(pu+pd):0;
                double effectiveDown=o.Evidence==2?1:
                    o.Evidence==3?pd/(pu+pd):0;
                for(int k=0;k<7;k++)
                {
                    grad[0,k]+=(pu-effectiveUp)*o.X[k];
                    grad[1,k]+=(pd-effectiveDown)*o.X[k];
                }
            }
            for(int side=0;side<2;side++)
                for(int k=0;k<7;k++)
                {
                    double g=grad[side,k]/observations.Length+
                        (k==0?0:.02*model.Beta[side,k]);
                    model.Beta[side,k]-=.15*g;
                }
        }
        return model;
    }

    // Predicted one-step hazards: [NONE,UP,DOWN].
    static double[] Predict(int variant,Decision d,double[] baseline,
        Dictionary<int,Counts> context,Softmax nonlinear)
    {
        if(variant==0)return baseline;
        if(variant==1)return context.TryGetValue(d.Context,out var c)?
            c.Probability(baseline,24):baseline;
        return nonlinear.Predict(d.X);
    }
    static double StepLoss(double[] p,int e)=>
        -Math.Log(Math.Max(1e-12,e==3?p[1]+p[2]:p[e]));
    static int Proposal(double[] p)
    {
        double s=1+p[0]+p[0]*p[0],up=p[1]*s,down=p[2]*s;
        if(up>=.30&&up-down>=.10)return 1;
        if(down>=.30&&down-up>=.10)return -1;
        return 0;
    }
    static bool Win(int side,int outcome)=>
        (side>0&&outcome==0)||(side<0&&outcome==1);

    sealed class WeekAgg
    {
        public double Sum;
        public int N;
    }
    static Scored Score(List<Decision> sample,int variant,double[] baseline,
        Dictionary<int,Counts> context,Softmax softmax)
    {
        int riskSteps=0,censored=0,ambiguous=0,up=0,down=0,noTouch=0,
            material=0,proposals=0,wins=0,opposite=0,propNone=0,
            propAmbiguous=0,propCensored=0,matchedMom=0,matchedContra=0,
            allMom=0,allMomWins=0,allContra=0,allContraWins=0;
        double sumLoss=0,sumBaseLoss=0;
        var weekly=new SortedDictionary<string,WeekAgg>(StringComparer.Ordinal);
        var signals=new SortedDictionary<string,int>(StringComparer.Ordinal);
        foreach(var d in sample)
        {
            var week=Week(d.At);
            if(!weekly.TryGetValue(week,out var w))
            {w=new WeekAgg();weekly.Add(week,w);signals[week]=0;}
            var p=Predict(variant,d,baseline,context,softmax);
            double loss=0,baseLoss=0;
            foreach(int e in d.Steps)
            {
                loss+=StepLoss(p,e);
                baseLoss+=StepLoss(baseline,e);
                riskSteps++;
            }
            sumLoss+=loss;sumBaseLoss+=baseLoss;
            w.Sum+=baseLoss-loss;w.N++;
            if(Enumerable.Range(0,3).Max(k=>Math.Abs(p[k]-baseline[k]))>.02)
                material++;
            if(d.Outcome==4)censored++;
            if(d.Outcome==3)ambiguous++;
            if(d.Outcome==0)up++;
            if(d.Outcome==1)down++;
            if(d.Outcome==2)noTouch++;
            if(d.MomentumSide!=0)
            {
                allMom++;allContra++;
                if(Win(d.MomentumSide,d.Outcome))allMomWins++;
                if(Win(-d.MomentumSide,d.Outcome))allContraWins++;
            }
            int side=Proposal(p);
            if(side==0)continue;
            proposals++;signals[week]++;
            if(Win(side,d.Outcome))wins++;
            if((side>0&&d.Outcome==1)||(side<0&&d.Outcome==0))opposite++;
            if(d.Outcome==2)propNone++;
            if(d.Outcome==3)propAmbiguous++;
            if(d.Outcome==4)propCensored++;
            if(Win(d.MomentumSide,d.Outcome))matchedMom++;
            if(Win(-d.MomentumSide,d.Outcome))matchedContra++;
        }
        var weeks=weekly.ToDictionary(x=>x.Key,x=>x.Value.Sum/x.Value.N);
        var values=weeks.Values.ToArray();
        double? mean=values.Length>0?values.Average():null,low=null,high=null;
        if(values.Length>=8)
        {
            double sd=Math.Sqrt(values.Sum(x=>Math.Pow(x-mean!.Value,2))/
                (values.Length-1)/values.Length);
            low=mean-1.96*sd;high=mean+1.96*sd;
        }
        return new Scored(sample.Count,riskSteps,censored,ambiguous,up,down,noTouch,
            sample.Count>0?sumLoss/sample.Count:null,
            sample.Count>0?sumBaseLoss/sample.Count:null,
            sample.Count>0?(sumBaseLoss-sumLoss)/sample.Count:null,
            riskSteps>0?sumLoss/riskSteps:null,
            material,sample.Count>0?(double)material/sample.Count:null,
            proposals,wins,opposite,propNone,propAmbiguous,propCensored,
            proposals>0?(double?)wins/proposals:null,
            proposals>0?(double?)(wins+propAmbiguous+propCensored)/proposals:null,
            matchedMom,matchedContra,allMom,allMomWins,allContra,allContraWins,
            signals.ToDictionary(x=>x.Key,x=>x.Value),weeks,values.Length,
            values.Count(x=>x>0),mean,low,high,
            signals.Count(x=>x.Value>=21),false);
    }

    static object Evaluate(Cdh1Stream stream)
    {
        Rule rule=Spec(stream.Period);
        var (decisions,stats)=Build(stream,rule);
        var train=decisions.Where(d=>d.At<rule.TrainEnd).ToList();
        var cal=decisions.Where(d=>d.At>=rule.TrainEnd&&d.At<rule.CalEnd).ToList();
        var eval=decisions.Where(d=>d.At>=rule.CalEnd).ToList();
        int evalWeeks=eval.Select(d=>Week(d.At)).Distinct().Count();
        bool admit=train.Count>=rule.MinTrain&&cal.Count>=rule.MinCal&&
            eval.Count>=rule.MinEval&&evalWeeks>=8;
        if(!admit)
            return new {stream.Symbol,stream.Period,Source=stats,
                Train=train.Count,Cal=cal.Count,Eval=eval.Count,
                EvalWeeks=evalWeeks,Status="PRESCORE_EXANTE_POPULATION_GATE_FAIL",
                Learned=(object?)null,SplitScores=(object?)null,
                DirectionalCandidate=(object?)null};
        var prior=Prior(train);
        var context=Context(train,prior,out int ambiguousTrain);
        var model=FitSoftmax(train);
        var splits=new Dictionary<string,object>();
        var all=new Dictionary<string,Scored[]>();
        foreach(var (name,rows) in new[]{("TRAIN",train),("CAL",cal),("EVAL",eval)})
        {
            var scores=Enumerable.Range(0,3).Select(k=>
                Score(rows,k,prior,context,model)).ToArray();
            splits[name]=new Dictionary<string,Scored>{
                [Names[0]]=scores[0],[Names[1]]=scores[1],[Names[2]]=scores[2]};
            all[name]=scores;
        }
        var calBayes=all["CAL"][1];var calLinear=all["CAL"][2];
        var evalBayes=all["EVAL"][1];var evalLinear=all["EVAL"][2];
        static object Candidate(Scored cal,Scored eval)
        {
            bool enoughWeeks=eval.EvaluationWeeks>=8;
            bool interval=eval.WeeklyNormalReference95Low is double lo&&lo>0;
            bool calibration=cal.IncrementalObservedLogLikelihoodPerDecision is double c&&c>=0;
            bool material=eval.MaterialDifferenceFraction is double q&&q>.02;
            bool directional=eval.Proposals>0&&eval.Wins>
                Math.Max(eval.MatchedMomentumWins,eval.MatchedContrarianWins);
            bool frequency=eval.ProposalWeeksWith21>=
                (int)Math.Ceiling(.75*eval.EvaluationWeeks);
            return new {
                DescriptiveDirectionalCandidate=enoughWeeks&&interval&&calibration&&
                    material&&directional&&frequency,
                EnoughWeeks=enoughWeeks,PositiveNormalReferenceInterval=interval,
                NonNegativeCalibrationIncrement=calibration,
                MateriallyDistinctForecasts=material,
                DirectionalLowerBoundBeatsMatchedSimpleControls=directional,
                Meets21DiagnosticProposalsIn75PercentWeeks=frequency,
                EconomicQualification=false
            };
        }
        return new{stream.Symbol,stream.Period,Source=stats,Train=train.Count,
            Cal=cal.Count,Eval=eval.Count,EvalWeeks=evalWeeks,
            Status="ORIGINAL_EXANTE_POPULATION_WITH_COMPETING_CENSORS",
            Learned=(object)new{
                TrainObservedRiskSteps=train.Sum(x=>x.Steps.Length),
                TrainAmbiguousEvidence=ambiguousTrain,
                TrainMarginalHazardNoneUpDown=prior,
                NonEmptyContextCells=context.Count,
                ContextSupport=context.ToDictionary(
                    x=>x.Key.ToString(CultureInfo.InvariantCulture),x=>x.Value.Total),
                SoftmaxRiskSteps=model.TrainedRiskSteps,
                SoftmaxCoefficientNorm=model.CoefficientNorm(),
                SoftmaxActuallyLearned=model.CoefficientNorm()>1e-6,
                SoftmaxBetaUp=Enumerable.Range(0,7).Select(k=>model.Beta[0,k]).ToArray(),
                SoftmaxBetaDown=Enumerable.Range(0,7).Select(k=>model.Beta[1,k]).ToArray(),
                FeatureTrainOnlyMeans=model.Mean,FeatureTrainOnlyScales=model.Scale
            },
            SplitScores=(object)splits,
            DirectionalCandidate=(object)new{
                Bayes=Candidate(calBayes,evalBayes),
                Softmax=Candidate(calLinear,evalLinear)
            }};
    }

    public static object Run(Cdh1Input input)
    {
        if(input is null||input.Streams is null||
           input.SourceRunId!="43817213663"||
           input.ProtocolSha256?.Length!=64||input.CiphertextSha256?.Length!=64||
           input.Streams.Length!=24||
           input.Streams.Select(x=>x.Symbol+"/"+x.Period)
                .Distinct(StringComparer.Ordinal).Count()!=24||
           !input.Streams.Select(x=>x.Symbol).Distinct(StringComparer.Ordinal)
                .OrderBy(x=>x,StringComparer.Ordinal)
                .SequenceEqual(Symbols.OrderBy(x=>x,StringComparer.Ordinal),
                    StringComparer.Ordinal)||
           input.Streams.Any(x=>x.Period is not ("H1" or "M15")))
            throw new ArgumentException("CDH1_ORIGINAL_HXC1_SOURCE_UNBOUND");
        var reports=input.Streams.OrderBy(x=>x.Symbol,StringComparer.Ordinal)
            .ThenBy(x=>x.Period,StringComparer.Ordinal).Select(Evaluate).ToArray();
        return new {
            Protocol=Version,
            SourceClass="AUTHENTIC_PEPPERSTONE_HXC1_CAUSAL_EXANTE_COMPETING_HAZARDS",
            input.SourceRunId,input.ProtocolSha256,input.CiphertextSha256,
            Models=Names,
            Population="CAUSAL_CLOSED_BAR_DECISIONS_INCLUDING_ALL_FUTURE_CENSORS_AND_AMBIGUITIES",
            Endpoint="THREE_TIME_STEPS_COMPETING_UP_DOWN_CENSORED_AMBIGUOUS",
            EvidenceLimitations=new[]{
                "EXPOSED_HISTORICAL_SOURCE_IS_NOT_GENUINELY_BLIND_CONFIRMATION",
                "AMBIGUOUS_BOTH_BARRIERS_SAME_BAR_NO_ORDER_INFERRED",
                "CENSORING_MAY_BE_INFORMATIVE_AND_DID_NOT_DISAPPEAR_FROM_DENOMINATOR",
                "OBSERVED_PARTIAL_LIKELIHOOD_IS_NOT_FULL_UNCENSORED_BRIER",
                "TRAINING_RISK_STEPS_OVERLAP_AND_EVAL_WEEKS_ARE_NOT_INDEPENDENT",
                "REFERENCE_NORMAL_INTERVAL_NOT_MULTIPLICITY_OR_DEPENDENCE_ROBUST",
                "ONE_WEEK_M15_CALIBRATION_LIMITS_REGIME_STABILITY_INFERENCE",
                "HISTORICAL_TICK_VOLUME_NOT_EXCHANGE_TRANSACTED_VOLUME",
                "NO_HISTORIC_EXECUTION_BIDASK_FEES_SWAPS_MARGIN_FX_OR_BROKER_FILLS",
                "NO_EUR300_COMMON_BOOK_NET_HARD21_FLOATING_DD_OR_INDEPENDENT_TWELVE_MONTHS"
            },
            Streams=reports,OneInitialCapitalEur=300,
            RealFundedTrades=(int?)null,NetEur=(decimal?)null,
            CapitalAndHard21Certified=false,ContinuousFloatingDd30Certified=false,
            Independent12MonthsCertified=false,
            OrdersSubmitted=0,CloudActivated=false,EconomicQualification=false
        };
    }

    public static object SelfTest()
    {
        long t=U(2026,9,22);
        var bars=new List<Ahr1H1Bar>();
        for(int i=0;i<78;i++)
        {
            long s=t+(i<35?i:i+24)*H;
            long low=i==25?955:990,high=i==25?1050:1010;
            bars.Add(new Ahr1H1Bar(s,s+H,1000,high,low,1001,20+i));
        }
        var (decisions,stats)=Build(new Cdh1Stream("EURUSD","H1",bars.ToArray()),
            Spec("H1"));
        if(decisions.Count!=bars.Count-12||
           decisions.Count(d=>d.Outcome==4)==0||
           decisions.Count(d=>d.Outcome==3)==0||
           !decisions.Any(d=>d.Steps.Length<3&&d.Outcome==4)||
           !decisions.Any(d=>d.X[5]>0))
            throw new InvalidOperationException("CDH1_EXANTE_CENSORED_AND_DUAL_TOUCH_CONTROL_FAIL");
        var synthetic=new List<Decision>();
        for(int i=0;i<320;i++)
        {
            int e=i%2==0?1:2;
            synthetic.Add(new Decision(t+i*H,e==1?0:1,new[]{e},
                new[]{1.0,i%2==0?-1.0:1.0,1.0,1.0,3.0,0.0,.5},0,
                i%2==0?-1:1));
        }
        var fit=FitSoftmax(synthetic);
        double[] x0={1,-1,1,1,3,0,.5},x1={1,1,1,1,3,0,.5};
        if(fit.CoefficientNorm()<.05||
           Math.Abs(fit.Predict(x0)[1]-fit.Predict(x1)[1])<.10)
            throw new InvalidOperationException("CDH1_ORIGINAL_SOFTMAX_TRAIN_ONLY_LEARNING_CONTROL_FAIL");
        return new {
            Source="SYNTHETIC_CONTROLS_ONLY",OriginalBrokerMarketScores=0,
            ExAnteClocks=decisions.Count,SessionGaps=stats.GetValueOrDefault("true_session_gaps"),
            FutureCensorStillInPopulation=true,AmbiguousDualTouchRemainsUnknown=true,
            SoftmaxTrulyLearned=true,Orders=0,CloudActivated=false,NetEur=(decimal?)null
        };
    }

    // MCE1 NEW: additive adapter to reuse the EXACT existing CDH1 private causal
    // Build/Prior/Context/FitSoftmax/Score methods with new prespecified chronology.
    // Every existing CDH1 original method and byte of its body remains unchanged.
    // This new method does NOT relaunch or amend the closed CDH1 Run() experiment.
    public static object RunCumulativeMce1(Cdh1Input input)
    {
        const string frozenNewRun = "44352570167";
        if(input is null||input.Streams is null||
           input.SourceRunId!=frozenNewRun||
           input.ProtocolSha256?.Length!=64||input.CiphertextSha256?.Length!=64||
           input.Streams.Length!=12||input.Streams.Any(s=>s.Period!="M15")||
           input.Streams.Select(s=>s.Symbol).Distinct(StringComparer.Ordinal).Count()!=12||
           !input.Streams.Select(s=>s.Symbol).OrderBy(s=>s,StringComparer.Ordinal)
                .SequenceEqual(Symbols.OrderBy(s=>s,StringComparer.Ordinal),
                    StringComparer.Ordinal))
            throw new ArgumentException("MCE1_NEW_274DAY_ORIGINAL_SOURCE_REQUIRED");
        var rule=new Rule(U(2025,11,16),U(2026,4,20),U(2026,6,15),
            U(2026,8,17),15*M,500,400,500);
        (string Id,string Symbol,int ModelIndex)[] frozen={
            ("H1_AUDUSD_SOFTMAX","AUDUSD",2),
            ("H2_EURUSD_BAYES","EURUSD",1),
            ("H3_GBPUSD_SOFTMAX","GBPUSD",2),
            ("H4_JPN225_SOFTMAX","JPN225",2)};
        var reports=new List<object>();
        foreach(var hypothesis in frozen)
        {
            var stream=input.Streams.Single(s=>s.Symbol==hypothesis.Symbol);
            var (decisions,sourceStats)=Build(stream,rule);
            var train=decisions.Where(d=>d.At<rule.TrainEnd).ToList();
            var cal=decisions.Where(d=>d.At>=rule.TrainEnd&&d.At<rule.CalEnd).ToList();
            var eval=decisions.Where(d=>d.At>=rule.CalEnd).ToList();
            int evalWeeks=eval.Select(d=>Week(d.At)).Distinct().Count();
            bool admitted=train.Count>=rule.MinTrain&&cal.Count>=rule.MinCal&&
                eval.Count>=rule.MinEval&&evalWeeks>=8;
            if(!admitted)
            {
                reports.Add(new{
                    hypothesis.Id,hypothesis.Symbol,
                    FrozenSelectedModel=Names[hypothesis.ModelIndex],
                    Source=sourceStats,
                    Train=train.Count,Calibration=cal.Count,
                    HistoricalTransportEval=eval.Count,EvalWeeks=evalWeeks,
                    Status="MCE1_EXANTE_PRESCORE_SOURCE_SUPPORT_FAIL_NO_ECONOMIC_INFERENCE",
                    TrainedModel=(object?)null,Score=(object?)null,
                    DirectionalGate=(object?)null});
                continue;
            }
            // EXACT reused CDH1 estimators: unchanged strength, feature
            // standardisation and softmax training iterations from the old
            // shared Core. Only TRAIN contributes to fit.
            var prior=Prior(train);
            var context=Context(train,prior,out int trainingAmbiguous);
            var softmax=FitSoftmax(train);
            int selected=hypothesis.ModelIndex;
            var trainPrior=Score(train,0,prior,context,softmax);
            var trainSelected=Score(train,selected,prior,context,softmax);
            var calPrior=Score(cal,0,prior,context,softmax);
            var calSelected=Score(cal,selected,prior,context,softmax);
            var evalPrior=Score(eval,0,prior,context,softmax);
            var evalSelected=Score(eval,selected,prior,context,softmax);
            int signed=evalSelected.Wins-evalSelected.OppositeFirst;
            int worstSigned=signed-evalSelected.ProposalAmbiguous-
                evalSelected.ProposalCensored;
            int matchedMomSigned=evalSelected.MatchedMomentumWins-
                evalSelected.MatchedContrarianWins;
            int matchedContraSigned=-matchedMomSigned;
            bool calStable=calSelected.IncrementalObservedLogLikelihoodPerDecision
                is double calInc&&calInc>=0;
            bool evalIncrement=evalSelected.WeeklyNormalReference95Low
                is double low&&low>0;
            bool sufficientlyDifferent=evalSelected.MaterialDifferenceFraction
                is double f&&f>.02;
            bool signedBetter=evalSelected.Proposals>0&&
                worstSigned>Math.Max(0,Math.Max(matchedMomSigned,matchedContraSigned));
            bool repeatFrequency=evalSelected.ProposalWeeksWith21>=
                (int)Math.Ceiling(.75*evalWeeks);
            bool historicalDiagnostic=calStable&&evalIncrement&&
                sufficientlyDifferent&&signedBetter&&repeatFrequency;
            reports.Add(new{
                hypothesis.Id,hypothesis.Symbol,
                FrozenSelectedModel=Names[selected],
                Source=sourceStats,Train=train.Count,Calibration=cal.Count,
                HistoricalTransportEval=eval.Count,EvalWeeks=evalWeeks,
                Status="MCE1_EXPOSED_HISTORICAL_TRANSPORT_DIAGNOSTIC_NOT_INDEPENDENT",
                TrainedModel=(object)new{
                    TrainOnlyPriorNoneUpDown=prior,
                    BayesianSupportedCells=context.Count,
                    TrainAmbiguousEvidence=trainingAmbiguous,
                    SoftmaxTrainObservedSteps=softmax.TrainedRiskSteps,
                    SoftmaxActuallyLearned=softmax.CoefficientNorm()>1e-6,
                    SoftmaxTrainCoefficientNorm=softmax.CoefficientNorm(),
                    NewFitNotOriginalCDH1Coefficients=true,
                    OriginalCDH1ExistingMethodBodiesUnmodified=true},
                Score=(object)new{
                    TrainPrior=trainPrior,TrainFrozenMechanismNewFit=trainSelected,
                    CalibrationPrior=calPrior,CalibrationFrozenMechanismNewFit=calSelected,
                    HistoricalTransportEvalPrior=evalPrior,
                    HistoricalTransportEvalFrozenMechanismNewFit=evalSelected},
                DirectionalGate=(object)new{
                    SignedFirstTouchWinMinusOpposite=signed,
                    WorstCaseSignedIncludingAmbiguousAndCensor=worstSigned,
                    SignedFirstTouchPerProposal=evalSelected.Proposals>0?
                        (double?)signed/evalSelected.Proposals:null,
                    ConservativeSignedLowerBoundPerProposal=evalSelected.Proposals>0?
                        (double?)worstSigned/evalSelected.Proposals:null,
                    MatchedMomentumSignedTouch=matchedMomSigned,
                    MatchedContrarianSignedTouch=matchedContraSigned,
                    CashNoTradeComparatorIsZeroExposure=true,
                    CalibrationNotWorseThanPrior=calStable,
                    DescriptiveHistoricalEvalReferenceIntervalAboveZero=evalIncrement,
                    MateriallyDifferentPrediction=sufficientlyDifferent,
                    SignedIncrementBeatsSimpleControlsConservatively=signedBetter,
                    AtLeast21NonfundedProposalsIn75PctWeeks=repeatFrequency,
                    HistoricallyRecurringDiagnosticOnly=historicalDiagnostic,
                    FundedQualification=false}
            });
        }
        return new{
            Protocol="MCE1_CUMULATIVE_CDH1_EXACT_MECHANISMS_NEW_HISTORICAL_M15_V1",
            SourceClass="NEW_AUTHENTIC_XMH2_ORIGINAL_PEPPERSTONE_M15_274D",
            input.SourceRunId,input.ProtocolSha256,input.CiphertextSha256,
            EarlierSourceStartUtc="2025-11-16",TrainEndUtc="2026-04-20",
            CalibrationEndUtc="2026-06-15",HistoricalTransportEvalEndUtc="2026-08-17",
            FrozenFourPostselectedHistoricalHypothesesOnly=true,
            PreviouslyExposedCDH1OriginalUnmodified=true,
            ExistingCausalCSharpBuildBayesSoftmaxScoreReusedExactly=true,
            DateDirection="HISTORICALLY_EARLIER_THAN_EXPOSED_CDH1_SEP_NOV",
            TrueIndependentFutureConfirmation=false,
            AllSourceCounts=input.Streams.ToDictionary(s=>s.Symbol,s=>s.Bars.Length),
            Hypotheses=reports,
            AllReportedWinsAreNONFUNDEDPriceFirstTouches=true,
            HistoricalBrokerFillsAvailable=false,
            OneSharedCapitalEur=300,
            NetEur=(decimal?)null,AdverseNetEur=(decimal?)null,
            FundedHard21Certified=false,FloatingDd30Certified=false,
            OrdersSubmitted=0,CloudActivated=false,EconomicQualification=false
        };
    }

    // MDE1 additive C# diagnostic. ALL original closed CDH1 and MCE1
    // method bodies remain byte-for-byte unchanged above this point.
    // Evaluate exactly the same causal risk sets and original estimator math
    // on all twelve original markets, without selecting a historical winner.
    static object Mde1SignedConditional(List<Decision> decisions,int variant,
        double[] prior,Dictionary<int,Counts> context,Softmax softmax)
    {
        int resolved=0,up=0,down=0,censored=0,ambiguous=0,untouched=0;
        double modelBrier=0,priorBrier=0,halfBrier=0;
        var weeks=new SortedDictionary<string,(double delta,int n)>(StringComparer.Ordinal);
        foreach(var d in decisions)
        {
            if(d.Outcome==4){censored++;continue;}
            if(d.Outcome==3){ambiguous++;continue;}
            if(d.Outcome==2){untouched++;continue;}
            bool isUp=d.Outcome==0;
            resolved++;if(isUp)up++;else down++;
            var p=Predict(variant,d,prior,context,softmax);
            double den=p[1]+p[2], baseDen=prior[1]+prior[2];
            double q=den>0?p[1]/den:.5;
            double qb=baseDen>0?prior[1]/baseDen:.5;
            double y=isUp?1:0;
            double bm=(q-y)*(q-y);
            double bb=(qb-y)*(qb-y);
            modelBrier+=bm;priorBrier+=bb;halfBrier+=.25;
            string week=Week(d.At);
            var previous=weeks.GetValueOrDefault(week,(0.0,0));
            weeks[week]=(previous.delta+bb-bm,previous.n+1);
        }
        int total=decisions.Count;
        return new {
            ExAnteClocksAllOutcomes=total,
            ResolvedFirstTouchDirectionalOutcomeCount=resolved,
            Up=up,Down=down,NoTouch=untouched,Ambiguous=ambiguous,Censored=censored,
            MeanConditionalDirectionalBrierModel=resolved>0?(double?)modelBrier/resolved:null,
            MeanConditionalDirectionalBrierPrior=resolved>0?(double?)priorBrier/resolved:null,
            MeanConditionalDirectionalBrierFairCoin=resolved>0?(double?)halfBrier/resolved:null,
            IncrementalConditionalDirectionalBrierGainVsPrior=
                resolved>0?(double?)(priorBrier-modelBrier)/resolved:null,
            ConditionalOnResolvedFirstTouchOnly=true,
            InformativeAmbiguityAndCensoringStillPossible=true,
            BrierImprovementByObservedUtcWeek=weeks.ToDictionary(
                x=>x.Key,x=>x.Value.delta/x.Value.n),
            GenuineFinancedProfit=false
        };
    }

    public static object RunCumulativeMde1(Cdh1Input input)
    {
        const string sourceId="MDE1_XMH2_44352570167_HXC1_43817213663";
        if(input is null||input.Streams is null||
           input.SourceRunId!=sourceId||
           input.ProtocolSha256?.Length!=64||input.CiphertextSha256?.Length!=64||
           input.Streams.Length!=12||input.Streams.Any(s=>s.Period!="M15")||
           input.Streams.Select(s=>s.Symbol).Distinct(StringComparer.Ordinal).Count()!=12||
           !input.Streams.Select(s=>s.Symbol).OrderBy(s=>s,StringComparer.Ordinal)
             .SequenceEqual(Symbols.OrderBy(s=>s,StringComparer.Ordinal),
                 StringComparer.Ordinal)||
           input.Streams.Sum(s=>s.Bars.Length)!=279491)
            throw new ArgumentException("MDE1_IMMUTABLE_ORIGINAL_DUAL_SOURCE_UNBOUND");
        var spec=new Rule(U(2025,11,16),U(2026,7,13),U(2026,9,14),
            U(2026,11,16),15*M,500,400,500);
        var reports=new List<object>();
        int allAdmitted=0,allPassGates=0;
        foreach(string symbol in Symbols.OrderBy(x=>x,StringComparer.Ordinal))
        {
            var original=input.Streams.Single(s=>s.Symbol==symbol);
            var (all,sourceStats)=Build(original,spec);
            var train=all.Where(d=>d.At<spec.TrainEnd).ToList();
            var cal=all.Where(d=>d.At>=spec.TrainEnd&&d.At<spec.CalEnd).ToList();
            var eval=all.Where(d=>d.At>=spec.CalEnd).ToList();
            int weeks=eval.Select(d=>Week(d.At)).Distinct().Count();
            bool sufficient=train.Count>=spec.MinTrain&&cal.Count>=spec.MinCal&&
                eval.Count>=spec.MinEval&&weeks>=8;
            if(!sufficient)
            {
                reports.Add(new {
                    Symbol=symbol,Source=sourceStats,Train=train.Count,
                    Calibration=cal.Count,ExposedEval=eval.Count,
                    EvalWeeks=weeks,Status="MDE1_EXANTE_PRESCORE_SUPPORT_STOP",
                    Models=(object?)null});
                continue;
            }
            allAdmitted++;
            var prior=Prior(train);
            var context=Context(train,prior,out int ambiguousInTraining);
            var softmax=FitSoftmax(train);
            var priorEval=Score(eval,0,prior,context,softmax);
            var alternatives=new List<object>();
            foreach(int k in new[]{1,2})
            {
                var trainScore=Score(train,k,prior,context,softmax);
                var calScore=Score(cal,k,prior,context,softmax);
                var evalScore=Score(eval,k,prior,context,softmax);
                var calDirection=Mde1SignedConditional(cal,k,prior,context,softmax);
                var evalDirection=Mde1SignedConditional(eval,k,prior,context,softmax);
                // Reuse CDH1's exact diagnostics, not a new fitted algorithm.
                int signed=evalScore.Wins-evalScore.OppositeFirst;
                int worst=signed-evalScore.ProposalAmbiguous-evalScore.ProposalCensored;
                int momentum=evalScore.MatchedMomentumWins-
                    evalScore.MatchedContrarianWins;
                int contrarian=-momentum;
                bool calGain=calDirection.IncrementalConditionalDirectionalBrierGainVsPrior
                    is double calG&&calG>0;
                bool evalGain=evalDirection.IncrementalConditionalDirectionalBrierGainVsPrior
                    is double evalG&&evalG>0;
                bool causalUtility=worst>Math.Max(0,Math.Max(momentum,contrarian));
                bool frequent=evalScore.ProposalWeeksWith21>=
                    (int)Math.Ceiling(.75*weeks);
                bool allDescriptive=calGain&&evalGain&&causalUtility&&frequent;
                if(allDescriptive)allPassGates++;
                alternatives.Add(new{
                    Model=Names[k],
                    TrainObservedHazardScore=trainScore,
                    CalObservedHazardScore=calScore,
                    EvalObservedHazardScore=evalScore,
                    CalConditionalSignedBrier=calDirection,
                    EvalConditionalSignedBrier=evalDirection,
                    SignedPriceFirstTouchWinMinusLoss=signed,
                    ConservativeSignedMinusAmbiguousCensor=worst,
                    MatchedMomentumSigned=momentum,
                    MatchedContrarianSigned=contrarian,
                    CashSigned=0,
                    AtLeast21UnfundedProposalsIn75PctExposedWeeks=frequent,
                    ConditionalDirectionImprovesVsPriorBothCalEval=calGain&&evalGain,
                    ConservativeSignedProxyBeatsSimpleSameClocks=causalUtility,
                    ExploratoryDirectionalUtilityGateOnly=allDescriptive,
                    FinancialOrIndependentQualification=false
                });
            }
            reports.Add(new{
                Symbol=symbol,Source=sourceStats,Train=train.Count,
                Calibration=cal.Count,ExposedEval=eval.Count,EvalWeeks=weeks,
                Status="MDE1_AUTHENTIC_EXPOSED_HISTORICAL_DIAGNOSTIC_ONLY",
                TrainPriorHazardNoneUpDown=prior,
                BayesianContextCells=context.Count,
                TrainingAmbiguousEvidence=ambiguousInTraining,
                SoftmaxTrainOnlyRiskSteps=softmax.TrainedRiskSteps,
                SoftmaxTrueCoefficientNorm=softmax.CoefficientNorm(),
                SoftmaxLearned=softmax.CoefficientNorm()>1e-6,
                EvalPriorObservedHazard=priorEval,
                Models=(object)alternatives
            });
        }
        return new{
            Protocol="MDE1_CUMULATIVE_ALL12_EXPOSED_M15_SIGN_VS_TOUCH_V1",
            SourceClass="EXISTING_XMH2_HXC1_ORIGINAL_AUTHENTIC_PEPPERSTONE_M15_UNION",
            input.SourceRunId,input.ProtocolSha256,input.CiphertextSha256,
            FullSourceBarCount=279491,
            OriginalPepperstoneSourceRuns=new[]{"44352570167","43817213663"},
            AllTwelveMarketsPrespecified=true,
            OriginalCdh1AndMce1MethodBodiesUnchanged=true,
            ExistingBuildPriorContextFitSoftmaxScoreReusedExactly=true,
            Timeline=new{
                Start="2025-11-16",TrainEnd="2026-07-13",
                CalibrationEnd="2026-09-14",ExposedEvalEnd="2026-11-16"},
            HistoricalEvalAlreadyExposedByCdh1Mce1=true,
            NotGenuineNewChronologicalIndependentConfirmation=true,
            CausalSourceSupportedSymbols=allAdmitted,
            AllModelsTestedIfSupported=24,
            ExploratoryDirectionalUtilityDescriptiveGatePasses=allPassGates,
            AllOriginalPriceFirstTouchesAreNotFinancedTrades=true,
            SourceBarCounts=input.Streams.ToDictionary(s=>s.Symbol,s=>s.Bars.Length),
            Reports=reports,
            Limitations=new[]{
                "SAME_HISTORICAL_DATES_ALREADY_EXPOSED_NO_MODEL_PROMOTION",
                "CONDITIONAL_BINARY_BRIER_CONDITIONS_ON_OBSERVABLE_RESOLVED_TOUCH",
                "NONE_AMBIGUOUS_CENSORED_RETAINED_IN_EXANTE_DENOMINATOR",
                "OVERLAPPING_OUTCOME_HORIZONS_WEAKEN_WEEKLY_UNCERTAINTY",
                "TWENTY_FOUR_COMPARISONS_NOT_MULTIPLICITY_CONTROLLED",
                "NO_BROKER_REAL_BIDASK_ORDER_FILL_FEES_MARGIN_FX_OR_ROLLOVER",
                "NO_COMMON_EUR300_LEDGER_ADVERSARIAL_NET_HARD21_FLOATING_DD",
                "NO_INDEPENDENT_FUTURE_TWELVE_MONTH_CONFIRMATION"
            },
            FundedNetEur=(decimal?)null,AdversarialNetEur=(decimal?)null,
            FundedHard21Certified=false,FloatingDd30Certified=false,
            IndependentTwelveMonthsCertified=false,
            OrdersSubmitted=0,CloudActivated=false,EconomicQualification=false
        };
    }

    public static object SelfTestMde1()
    {
        // Synthetic ONLY. No historical market source or closed study execution.
        long clock=U(2026,10,1);
        double[] basis={1.0,0.0,1.0,1.0,3.0,0.0,.5};
        var rows=new List<Decision>{
            new(clock,0,new[]{1},basis,0,1),
            new(clock+15*M,1,new[]{2},basis,0,-1),
            new(clock+30*M,2,new[]{0,0,0},basis,0,0),
            new(clock+45*M,3,new[]{3},basis,0,1),
            new(clock+60*M,4,Array.Empty<int>(),basis,0,1)
        };
        double[] baseline={.5,.25,.25};
        var context=new Dictionary<int,Counts>();
        var fit=FitSoftmax(rows);
        var sign=Mde1SignedConditional(rows,0,baseline,context,fit);
        // Type inference is anonymous and strong-typed inside this method.
        if(sign.ExAnteClocksAllOutcomes!=5||
           sign.ResolvedFirstTouchDirectionalOutcomeCount!=2||
           sign.Censored!=1||sign.Ambiguous!=1||sign.NoTouch!=1||
           Math.Abs(sign.MeanConditionalDirectionalBrierModel!.Value-.25)>1e-9||
           Math.Abs(sign.IncrementalConditionalDirectionalBrierGainVsPrior!.Value)>1e-9)
            throw new InvalidOperationException(
                "MDE1_SYNTHETIC_EVENT_VS_CONDITIONAL_SIGN_DENOMINATOR_FAIL");
        return new {
            Source="SYNTHETIC_ONLY",
            CausalClocks=sign.ExAnteClocksAllOutcomes,
            ResolvedConditionalBrierClocks=sign.ResolvedFirstTouchDirectionalOutcomeCount,
            AmbiguousAndCensoredStillCounted=true,
            EventLikelihoodNotClaimedSignedEdge=true,
            NativeCoreOnly=true,OriginalBrokerTrades=0,
            FundedNetEur=(decimal?)null,CloudActivated=false
        };
    }
}
