using System;
using System.Collections.Generic;
using System.Linq;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Core;

// SCP1: genuine completed native M5/M15 price features in C#.
// Prices in a training *label* are NOT executed broker/model-order fills.
// The full causal modeled exit thesis is evaluated at later completed bars.
public sealed record Scp1OriginalBarStream(string Symbol,
    NativeClosedMarketBar[] M5,NativeClosedMarketBar[] M15);
public sealed record Scp1OriginalQuoteSource(string Symbol,
    NativeObservedContractTerms Contract,decimal MinMarginEur,
    decimal TickSize,Npi1ObservedQuote[] Quotes);
public sealed record Scp1OriginalInput(string OriginalHxc1SourceSha256,
    string OriginalOei1SourceSha256,Scp1OriginalBarStream[] Streams,
    Scp1OriginalQuoteSource[] QuoteMarkets);
public sealed record Scp1LabeledEpisode(long At,long End,string Symbol,
    string Family,int Side,double[] Features,decimal GrossPriceOnlyR,
    string ExitReason,bool Complete,int MissingFutureSegments);
public sealed record Scp1Bucket(int N,int Wins,decimal PositiveSumR,
    decimal NegativeSumR,decimal SquaredSumR);
public sealed record Scp1Prediction(double PWin,double LowerPWin,
    double MeanPositiveR,double MeanNegativeR,double MeanR,
    double LowerConfidenceR,double UncertaintyR,string Method,
    int LocalTrainingN);
public sealed record Scp1ScoreModel(string Version,string Method,
    long TrainingEnd,long CalibrationEnd,string TrainingDataHash,
    int TrainingComplete,int TrainingCensored,double GlobalPrior,
    double GlobalMeanWinR,double GlobalMeanLossR,double GlobalStdR,
    Dictionary<string,Scp1Bucket> Cells,double[] RidgeWeights,
    int CalibrationComplete,double? PriorCalibrationBrier,
    double? BayesCalibrationBrier,double? RidgeCalibrationBrier,
    bool MethodSelectedWithoutEvaluation,
    int TrainingEffectiveCalendarWeeks=0);
public sealed record Scp1ScoreBand(int Band,int Count,double? AverageForecastP,
    double? ActualPositiveRate,decimal? MeanGrossPriceOnlyR,
    string Disclosure);
public sealed record Scp1ScoreDiagnostics(string Stage,string Method,
    int Eligible,int Complete,int Censored,double? Brier,
    double? PriorBrier,double? BrierSkill,double? PairRankAgreement,
    double? HighMinusLowMeanGrossR,
    Scp1ScoreBand[] Bands,Dictionary<string,int> ExitReasons,
    string EconomicEvidenceClass);

public static class NativeScp1EconomicScorer
{
    public const string Version="SCP1_FROZEN_CAUSAL_M5_M15_COMPLETE_POLICY_PROBABILITY_V1";
    static long Date(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,
        TimeSpan.Zero).ToUnixTimeMilliseconds();
    public static readonly long Start=Date(2026,8,17);
    public static readonly long EndTrain=Date(2026,9,28);
    public static readonly long EndCal=Date(2026,10,19);
    public static readonly long EndEval=Date(2026,11,9);
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static double C(double x)=>Math.Clamp(x,-4d,4d);

    // Feature EXACTNESS: last 5 fully observed authentic M5, 3 M15 bars
    // preceding decision time. Cloud and Replay call this SAME pure method.
    public static double[] Features(string symbol,long clock,int side,string family,
        NativeClosedMarketBar[] m5,NativeClosedMarketBar[] m15,
        decimal breadth=0m)
    {
        if(side is not (-1 or 1) ||
           family is not ("RANGE_TRANSITION" or "EQUILIBRIUM_REPAIR" or
                          "FUNDED_LONG_CONTROL" or "FUNDED_SHORT_CONTROL") ||
           m5 is null||m15 is null||m5.Length<5||m15.Length<3)
            throw new ArgumentException("SCP1_FEATURE_EVIDENCE_MISSING");
        var x=m5.Where(p=>p.CloseAt<clock).TakeLast(5).ToArray();
        var z=m15.Where(p=>p.CloseAt<clock).TakeLast(3).ToArray();
        if(x.Length!=5||z.Length!=3||
           x.Zip(x.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt)||
           z.Zip(z.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt)||
           x[^1].CloseAt>=clock||clock-x[^1].CloseAt>300000L||
           z[^1].CloseAt>=clock||clock-z[^1].CloseAt>900000L)
            throw new ArgumentException("SCP1_FEATURE_CLOCK_NOT_COMPLETE");
        decimal tr=0m;
        for(int i=1;i<5;i++)
            tr+=Math.Max(x[i].High-x[i].Low,
                Math.Max(Math.Abs(x[i].High-x[i-1].Close),
                    Math.Abs(x[i].Low-x[i-1].Close)));
        decimal atr=tr/4m;
        if(atr<=0m)throw new ArgumentException("SCP1_ZERO_CAUSAL_ATR");
        double trend5=C((double)(side*(x[^1].Close-x[^2].Close)/atr));
        double trend15=C((double)(side*(z[^1].Close-z[^2].Close)/atr));
        double dist=C((double)(side*(z[^1].Close-z.Average(v=>v.Close))/atr));
        double vol=C((double)((x[^1].High-x[^1].Low)/atr));
        double activity=C(x.Sum(v=>v.TickVolume)>0?
            5d*x[^1].TickVolume/x.Sum(v=>v.TickVolume)-1d:0d);
        double h=(DateTimeOffset.FromUnixTimeMilliseconds(clock).UtcDateTime.Hour+
            DateTimeOffset.FromUnixTimeMilliseconds(clock).UtcDateTime.Minute/60d);
        double sin=Math.Sin(2d*Math.PI*h/24d),cos=Math.Cos(2d*Math.PI*h/24d);
        double fellow=C((double)breadth*side);
        return new[]{trend5,trend15,dist,vol,activity,
            family=="RANGE_TRANSITION"?1d:-1d, (double)side,
            sin,cos,fellow,C(trend5*trend15)};
    }
    static string Key(string family,int side,double[] features)
    {
        string regime=features[1]>=0?"FOLLOW":"AGAINST";
        string volatility=features[3]>=1.1?"HIGH":"LOW";
        return family+"/"+side+"/"+regime+"/"+volatility;
    }
    static double ClipP(double p)=>Math.Clamp(p,.01,.99);
    static double Sigma(double p,int n)=>Math.Sqrt(Math.Max(.00001,
        p*(1-p)/(n+13d)));
    public static Scp1Prediction Predict(Scp1ScoreModel model,
        string family,int side,double[] features,string method)
    {
        if(model.Version!=Version||features.Length!=11||
           method is not ("BAYES_CONTEXT" or "RIDGE_NONLINEAR" or "NO_SCORE"))
            throw new ArgumentException("SCP1_MODEL_METHOD_OR_FEATURE");
        string key=Key(family,side,features);
        model.Cells.TryGetValue(key,out var cell);
        int n=cell?.N??0,w=cell?.Wins??0;
        double pBayes=(w+12d*model.GlobalPrior)/(n+12d);
        double p=method=="RIDGE_NONLINEAR"?
            ClipP(NativeContextValueResearch.Predict(model.RidgeWeights,features)):
            method=="NO_SCORE"?model.GlobalPrior:pBayes;
        // Overlapping trade episodes and twelve correlated symbols do NOT
        // provide n independent trials. The bound is floored by the actual
        // number of distinct TRAIN calendar weeks, irrespective of signal
        // count, and is explicitly a diagnostic not 12-month confirmation.
        int effective=Math.Min(n,Math.Max(1,model.TrainingEffectiveCalendarWeeks));
        double uncertainty=Math.Max(Sigma(p,effective),
            Sigma(p,Math.Max(1,model.TrainingEffectiveCalendarWeeks)));
        double lower=ClipP(p-1.645*uncertainty);
        // Train conditional upside/downside on observed COMPLETE price-path
        // proxy labels. Empirical sizes shrink to train-wide prior, not a
        // guessed static EUR win/loss or ex-post UCP1 winner amplitude.
        double win=(double)(((cell?.PositiveSumR??0m)+
            12m*(decimal)model.GlobalMeanWinR)/(w+12m));
        double loss=(double)(((cell?.NegativeSumR??0m)+
            12m*(decimal)model.GlobalMeanLossR)/(Math.Max(0,n-w)+12m));
        double mean=p*win+(1-p)*loss;
        double magnitude=Math.Abs(win-loss);
        double width=1.645*uncertainty*magnitude+
            1.645*model.GlobalStdR/Math.Sqrt(Math.Max(12,n));
        return new(p,lower,win,loss,mean,mean-width,width,
            method,n);
    }
    public static Scp1ScoreModel Train(Scp1LabeledEpisode[] rows,
        string originalSourceHash)
    {
        if(originalSourceHash.Length!=64||
           rows.Any(x=>x.Features.Length!=11||
               x.Features.Any(z=>!double.IsFinite(z))))
            throw new ArgumentException("SCP1_TRAIN_CAUSAL_EVIDENCE");
        var train=rows.Where(x=>x.At>=Start&&x.At<EndTrain&&x.Complete&&
                    x.End<EndTrain).ToArray();
        int censored=rows.Count(x=>x.At>=Start&&x.At<EndTrain&&
                    (!x.Complete||x.End>=EndTrain));
        if(train.Length<100)throw new InvalidOperationException("SCP1_LEARNING_SUPPORT_LT100");
        double prior=(train.Count(x=>x.GrossPriceOnlyR>0)+2d)/(train.Length+4d);
        var winners=train.Where(x=>x.GrossPriceOnlyR>0).ToArray();
        var losers=train.Where(x=>x.GrossPriceOnlyR<=0).ToArray();
        double wmean=winners.Length>0?(double)winners.Average(x=>x.GrossPriceOnlyR):1d;
        double lmean=losers.Length>0?(double)losers.Average(x=>x.GrossPriceOnlyR):-1d;
        double mean=(double)train.Average(x=>x.GrossPriceOnlyR);
        double std=Math.Sqrt(Math.Max(.00001,
            train.Average(x=>Math.Pow((double)x.GrossPriceOnlyR-mean,2))));
        int calendarWeeks=train.Select(x=>{
            var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
            return System.Globalization.ISOWeek.GetYear(d)+"-"+
                System.Globalization.ISOWeek.GetWeekOfYear(d);
        }).Distinct(StringComparer.Ordinal).Count();
        var cells=train.GroupBy(x=>Key(x.Family,x.Side,x.Features),
                StringComparer.Ordinal).ToDictionary(g=>g.Key,g=>
            new Scp1Bucket(g.Count(),g.Count(x=>x.GrossPriceOnlyR>0),
                g.Where(x=>x.GrossPriceOnlyR>0).Sum(x=>x.GrossPriceOnlyR),
                g.Where(x=>x.GrossPriceOnlyR<=0).Sum(x=>x.GrossPriceOnlyR),
                g.Sum(x=>x.GrossPriceOnlyR*x.GrossPriceOnlyR)),
                StringComparer.Ordinal);
        // Deterministic ridge with penalty fixed by existing C# implementation.
        double[] beta=NativeContextValueResearch.Ridge(
            train.Select(x=>x.Features).ToArray(),
            train.Select(x=>x.GrossPriceOnlyR>0?1d:0d).ToArray());
        var draft=new Scp1ScoreModel(Version,"NO_SCORE",EndTrain,EndCal,
            Hash(originalSourceHash+":"+train.Length+":"+
                string.Join("|",train.Select(x=>x.At+":"+x.Symbol+":"+x.Family+
                    ":"+x.Side+":"+x.GrossPriceOnlyR.ToString(CultureInfo.InvariantCulture)))),
            train.Length,censored,prior,wmean,lmean,std,cells,beta,
            0,null,null,null,false,calendarWeeks);
        var cal=rows.Where(x=>x.At>=EndTrain&&x.At<EndCal&&
                   x.Complete&&x.End<EndCal).ToArray();
        double? Brier(string method)=>cal.Length>0?cal.Average(x=>{
            double p=method=="PRIOR"?prior:
                Predict(draft,x.Family,x.Side,x.Features,method).PWin;
            double y=x.GrossPriceOnlyR>0?1d:0d;
            return (p-y)*(p-y);
        }):null;
        double? priorError=Brier("PRIOR"),
            bayes=Brier("BAYES_CONTEXT"),ridge=Brier("RIDGE_NONLINEAR");
        string chosen="NO_SCORE";
        if(cal.Length>=60 && priorError.HasValue&&
           bayes.HasValue&&ridge.HasValue)
        {
            string best=bayes<=ridge?"BAYES_CONTEXT":"RIDGE_NONLINEAR";
            double score=Math.Min(bayes.Value,ridge.Value);
            if(score+.0000001<priorError.Value)
            {
                var ranked=cal.OrderBy(x=>Predict(draft,x.Family,x.Side,
                    x.Features,best).PWin).ToArray();
                int q=Math.Max(1,ranked.Length/4);
                decimal low=ranked.Take(q).Average(x=>x.GrossPriceOnlyR);
                decimal high=ranked.TakeLast(q).Average(x=>x.GrossPriceOnlyR);
                if(high>low)chosen=best;
            }
        }
        return draft with {Method=chosen,CalibrationComplete=cal.Length,
            PriorCalibrationBrier=priorError,BayesCalibrationBrier=bayes,
            RidgeCalibrationBrier=ridge,MethodSelectedWithoutEvaluation=true};
    }
    public static Scp1ScoreDiagnostics Diagnose(Scp1ScoreModel m,
        Scp1LabeledEpisode[] rows,string stage,string method,
        long begin,long end)
    {
        var eligible=rows.Where(x=>x.At>=begin&&x.At<end).ToArray();
        var sample=eligible.Where(x=>x.Complete&&x.End<end).ToArray();
        var pairs=sample.Select(x=>(Row:x,P:Predict(m,x.Family,x.Side,
            x.Features,method).PWin)).OrderBy(x=>x.P).ToArray();
        double? brier=sample.Length>0?pairs.Average(x=>
            Math.Pow(x.P-(x.Row.GrossPriceOnlyR>0?1d:0d),2)):null;
        double? prior=sample.Length>0?pairs.Average(x=>
            Math.Pow(m.GlobalPrior-(x.Row.GrossPriceOnlyR>0?1d:0d),2)):null;
        var bands=new List<Scp1ScoreBand>();
        for(int i=0;i<5;i++)
        {
            var chunk=pairs.Skip(i*pairs.Length/5)
                .Take((i+1)*pairs.Length/5-i*pairs.Length/5).ToArray();
            bands.Add(new(i+1,chunk.Length,
                chunk.Length>0?(double?)chunk.Average(x=>x.P):null,
                chunk.Length>0?(double?)(chunk.Count(x=>x.Row.GrossPriceOnlyR>0)/
                    (double)chunk.Length):null,
                chunk.Length>0?(decimal?)chunk.Average(x=>x.Row.GrossPriceOnlyR):null,
                "PRICE_ONLY_COMPLETED_BAR_PATH_PROXY_NOT_NET_EUR"));
        }
        double? uplift=pairs.Length>=10 &&
            bands[^1].MeanGrossPriceOnlyR is decimal high &&
            bands[0].MeanGrossPriceOnlyR is decimal low?
            (double)(high-low):null;
        // Pairwise random baseline .5; fixed deterministic stratified comparison
        // to avoid quadratic comparisons or hindsight-selected winners.
        int concord=0,disagree=0;
        foreach(var a in pairs.Where((x,i)=>i%11==0))
        foreach(var b in pairs.Where((x,i)=>i%13==0))
        {
            if(a.P==b.P||a.Row.GrossPriceOnlyR==b.Row.GrossPriceOnlyR)continue;
            if((a.P-b.P)*((double)a.Row.GrossPriceOnlyR-(double)b.Row.GrossPriceOnlyR)>0)
                concord++;else disagree++;
        }
        return new(stage,method,eligible.Length,sample.Length,
            eligible.Length-sample.Length,brier,prior,
            prior>0&&brier.HasValue?1-brier.Value/prior:null,
            concord+disagree>0?(double?)concord/(concord+disagree):null,
            uplift,bands.ToArray(),sample.GroupBy(x=>x.ExitReason)
                .ToDictionary(g=>g.Key,g=>g.Count(),StringComparer.Ordinal),
            "GLOBALLY_EXPOSED_COMPLETED_M5_M15_PRICE_ONLY_LABEL_NOT_EXECUTION");
    }

    // Source-only NONEXECUTABLE complete-policy label, under SCP1-A0
    // pre-original causal alignment. The next *completed M5 close* is a
    // directional price-only proxy entry, never a Pepperstone fill.
    // We invoke the SAME native signal/structure/risk exit decision on
    // later genuinely completed M5 closes, with M15 trends as-of each.
    static Scp1LabeledEpisode Label(string symbol,long at,
        Ucp1DecisionSignal signal,double[] features,
        NativeClosedMarketBar[] m5,NativeClosedMarketBar[] m15,
        int nextM5Index,int lastSignalM15Index)
    {
        Scp1LabeledEpisode Unknown(string reason,int gaps=1)
            =>new(at,0,symbol,signal.Family,signal.Side,features,
                0m,reason,false,gaps);
        if(nextM5Index<=0 ||nextM5Index+2>=m5.Length ||
           m5[nextM5Index-1].CloseAt>=at ||
           m5[nextM5Index].CloseAt<=at ||
           m5[nextM5Index].OpenAt!=m5[nextM5Index-1].CloseAt)
            return Unknown("NEXT_REAL_COMPLETED_M5_ENTRY_PRICE_UNKNOWN");
        decimal entry=m5[nextM5Index].Close;
        decimal stop=entry-signal.Side*1.5m*signal.Atr;
        decimal extreme=entry;
        var seed=new NativeExitSeed(signal.Atr,signal.Equilibrium);
        int lastM15=Math.Max(1,lastSignalM15Index);
        int max=Math.Min(m5.Length-2,nextM5Index+128);
        for(int k=nextM5Index+1;k<=max;k++)
        {
            if(m5[k].OpenAt!=m5[k-1].CloseAt ||
               m5[k+1].OpenAt!=m5[k].CloseAt)
                return Unknown("UNOBSERVED_COMPLETE_POLICY_M5_PATH_GAP");
            // No M15 regime information becomes visible before its
            // genuine completed timestamp. Never read the forming candle.
            while(lastM15+1<m15.Length &&
                  m15[lastM15+1].CloseAt<=m5[k].CloseAt)
                lastM15++;
            decimal direction=0m;
            if(lastM15>0 && m15[lastM15-1].CloseAt==m15[lastM15].OpenAt)
                direction=m15[lastM15].Close-m15[lastM15-1].Close;
            var q=new LedgerQuote(symbol,m5[k].CloseAt,
                m5[k].Close,m5[k].Close,1m,1m,0m,0m,1m);
            NativeExitVerdict exit;
            try {
                exit=NativeCausalExitResearch.AssessLifecycle(
                    signal.Family=="RANGE_TRANSITION"?"ADAPT":"STRUCT",
                    signal.Side,entry,seed,stop,extreme,q,direction,false);
            }
            catch(ArgumentException)
            {return Unknown("M5_COMPLETE_POLICY_EXIT_INPUT_INVALID");}
            extreme=exit.FavorableExtreme;
            if(!exit.RequestClose)continue;
            // Modeled CLOSE request is known here; realized proxy
            // exit requires a later *authentic* contiguous M5 close.
            decimal grossR=signal.Side*(m5[k+1].Close-entry)/
                (1.5m*signal.Atr);
            return new(at,m5[k+1].CloseAt,symbol,signal.Family,
                signal.Side,features,grossR,exit.Reason,true,0);
        }
        return Unknown("EMERGENCY_M5_MAX_OBSERVATIONS_CENSORED_NOT_EXIT");
    }

    public static Scp1LabeledEpisode[] BuildTrainingEpisodes(
        Scp1OriginalBarStream[] source)
    {
        var rows=new List<Scp1LabeledEpisode>();
        var universe=source.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        // One macro breadth per authentic M15 close using all available
        // original symbols. All calculations consume only same-clock closes.
        var breadth=new Dictionary<long,decimal>();
        var breadthScratch=new Dictionary<long,(int N,int Positive)>();
        foreach(var s in source)
        for(int j=1;j<s.M15.Length;j++)
        {
            var a=s.M15[j-1];var z=s.M15[j];
            if(a.CloseAt!=z.OpenAt)continue;
            if(!breadthScratch.TryGetValue(z.CloseAt,out var old))old=(0,0);
            breadthScratch[z.CloseAt]=(old.N+1,old.Positive+(z.Close>a.Close?1:0));
        }
        foreach(var kv in breadthScratch)
            breadth[kv.Key]=kv.Value.N>=4?
                (2m*kv.Value.Positive/kv.Value.N-1m):0m;
        foreach(var s in source)
        {
            var m5=s.M5;var m15=s.M15;int k5=0;
            for(int j=2;j<m15.Length;j++)
            {
                var bar=m15[j];long t=bar.CloseAt+1000L;
                if(t<Start||t>=EndEval)continue;
                while(k5<m5.Length&&m5[k5].CloseAt<t)k5++;
                var x=m5.Skip(Math.Max(0,k5-5)).Take(5).ToArray();
                var z=m15.Skip(j-2).Take(3).ToArray();
                if(x.Length!=5)continue;
                var symbol=s.Symbol;
                var market=new Ucp1MarketFrame(symbol,
                    new LedgerQuote(symbol,t,bar.Close,bar.Close,1m,1m,
                        0m,0m,1m),
                    // PLACEHOLDER contract NEVER passed to financial engine
                    // or treated as authentic broker market terms.
                    new NativeObservedContractTerms(symbol,"PROXY_ONLY",
                        t,1m,1m,1m,1m,2,0,2,0,null,0,0,0m,0m,
                        4,24,1320,3,false,0,false,false),
                    x,z,0m,"PRICE_ONLY_TRAINING_NOT_EXECUTION");
                var candidates=Ucp1CausalSignals.Describe(market,t);
                foreach(var signal in candidates)
                {
                    double[] f;
                    try {f=Features(symbol,t,signal.Side,signal.Family,
                        x,z,breadth.GetValueOrDefault(bar.CloseAt));}
                    catch(ArgumentException){continue;}
                    rows.Add(Label(symbol,t,signal,f,m5,m15,k5,j));
                }
            }
        }
        return rows.ToArray();
    }
}
