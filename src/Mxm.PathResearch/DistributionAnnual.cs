using System.Text.Json;
using System.Security.Cryptography;
using Mxm.Core;
internal static class DistributionAnnual
{
    record Market(string Symbol,string? AssetClass,Dictionary<string,long[][]> Bars);
    record Observation(string Symbol,string? AssetClass,long At,long AvailableAt,int Horizon,
        NativeClosedPathPrediction.Context Context,decimal RelativeVolatility,decimal Move,decimal Up,decimal Down,decimal FirstLower,decimal FirstUpper);
    sealed class Stat
    {
        public int Count,Active,ProbCount;public decimal Move,MatchedRaw,Brier,Pinball,UpperBrier;
        public void Add(int side,Observation x,int raw,NativePathDistributionForecast? f)
        {
            Count++;if(side!=0)Active++;Move+=side*x.Move;MatchedRaw+=raw*x.Move;
            if(f is null)return;ProbCount++;
            decimal e=f.PositiveProbability-(x.Move>0m?1m:0m);Brier+=e*e;
            for(int i=0;i<9;i++){decimal error=x.Move-f.Quantiles[i];Pinball+=(error>=0m?(i+1)/10m:(i+1)/10m-1m)*error/9m;}
            if(x.FirstLower==x.FirstUpper){e=(f.UpperFirstLower+f.UpperFirstUpper)/2m-x.FirstLower;UpperBrier+=e*e;}
        }
    }
    public static int Run(string source,string output)
    {
        var bytes=File.ReadAllBytes(source);var markets=JsonSerializer.Deserialize<Market[]>(bytes)!;
        if(markets.Length<5||markets.Select(m=>m.Symbol).Distinct().Count()!=markets.Length)throw new InvalidDataException("DISTRIBUTION_UNIVERSE");
        long U(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
        long start=U(2025,11,1),selection=U(2026,5,1),evaluation=U(2026,8,1),end=U(2026,11,26);
        string Stage(long at)=>at<selection?"DEVELOPMENT":at<evaluation?"SELECTION":"EVALUATION_EXPOSED";
        var observations=new List<Observation>();var coverage=new Dictionary<string,int>();
        void Count(string s)=>coverage[s]=coverage.GetValueOrDefault(s)+1;
        foreach(var m in markets)
        {
            NativeClosedMarketBar[] Bars(string tf,long width)=>m.Bars[tf].Where(x=>x.Length==7&&x[1]-x[0]==width&&x[0]>=start&&x[1]<=end&&
                x[4]>0&&x[4]<=Math.Min(x[2],x[5])&&x[3]>=Math.Max(x[2],x[5])&&x[6]>=0)
                .Select(x=>new NativeClosedMarketBar(x[0],x[1],x[2]/100000m,x[3]/100000m,x[4]/100000m,x[5]/100000m,x[6])).OrderBy(x=>x.OpenAt).ToArray();
            var f=Bars("M5",300000);var med=Bars("M15",900000);var slow=Bars("H1",3600000);int mi=0,si=0;
            for(int i=5;i<f.Length;i++)
            {
                long at=f[i].CloseAt+1;if(f[i].CloseAt%3600000!=0)continue;
                while(mi<med.Length&&med[mi].CloseAt<at)mi++;while(si<slow.Length&&slow[si].CloseAt<at)si++;
                if(mi<4||si<4||med[mi-1].CloseAt!=f[i].CloseAt||slow[si-1].CloseAt!=f[i].CloseAt){Count(m.Symbol+"/CONTEXT_GAP");continue;}
                NativeBarWindow W(NativeBarTimeframe tf,NativeClosedMarketBar[] a,int stop,int n)=>new(tf,n,a[stop-1].CloseAt,at,"AUTHENTIC_ARCHIVED_CLOSED_BARS",NativeBarStatus.Ready,a[(stop-n)..stop]);
                var context=NativeClosedPathPrediction.ObserveClosedWindows(new(at,new[]{W(NativeBarTimeframe.M5,f,i+1,6),W(NativeBarTimeframe.M15,med,mi,4),W(NativeBarTimeframe.H1,slow,si,4)}),at);
                if(context is null){Count(m.Symbol+"/UNSUPPORTED_CONTEXT");continue;}
                foreach(int h in new[]{15,30,60})
                {
                    int n=h/5;if(i+n>=f.Length||Enumerable.Range(i+1,n).Any(j=>f[j].OpenAt!=f[j-1].CloseAt))
                    {Count(m.Symbol+"/CENSORED");continue;}
                    long maturity=f[i+n].CloseAt+1;if(Stage(at)!=Stage(maturity)){Count(m.Symbol+"/CROSS_STAGE");continue;}
                    var future=f[(i+1)..(i+n+1)];decimal entry=f[i].Close,lower=0m,upper=0m;
                    foreach(var b in future)
                    {
                        bool up=b.High>=entry+context.Atr,down=b.Low<=entry-context.Atr;
                        if(!up&&!down)continue;lower=up&&!down?1m:0m;upper=up?1m:0m;break;
                    }
                    observations.Add(new(m.Symbol,m.AssetClass,at,maturity,h,context,1000m*context.Atr/entry,(future[^1].Close-entry)/context.Atr,
                        Math.Max(0m,(future.Max(b=>b.High)-entry)/context.Atr),Math.Max(0m,(entry-future.Min(b=>b.Low))/context.Atr),lower,upper));
                }
            }
        }
        var features=new Dictionary<(string,long),double?[]>();
        foreach(var g in observations.GroupBy(x=>x.At))
        {
            var current=g.GroupBy(x=>x.Symbol).Select(x=>x.First()).ToArray();
            foreach(var x in current)
            {
                var c=x.Context;var peers=current.Where(p=>p.Symbol!=x.Symbol&&x.AssetClass is not null&&p.AssetClass==x.AssetClass).ToArray();
                double phase=2*Math.PI*(x.At%86400000)/86400000d;
                features[(x.Symbol,x.At)]=new double?[]{(double)c.FastEfficiency,(double)c.MediumEfficiency,(double)c.SlowEfficiency,
                    (double)c.FastDisplacement,(double)c.SlowDisplacement,Math.Sin(phase),Math.Cos(phase),(double)x.RelativeVolatility,
                    peers.Length>=2?(double?)peers.Average(p=>p.Context.Alignment):null,
                    peers.Length>=2?(double?)(c.SlowDisplacement-peers.Average(p=>p.Context.SlowDisplacement)):null};
            }
        }
        var history=new Dictionary<(int H,string Scope),Queue<NativePathSample>>();
        var daily=new Dictionary<(string Stage,string Symbol,int H,string Method,long Day),Stat>();
        var matured=observations.OrderBy(x=>x.AvailableAt).ToArray();int k=0;
        var modes=new[]{("POOLED",0),("LOCAL",28),("CONTEXT",14),("CONTEXT",28),("CONTEXT",56)};
        foreach(var x in observations.OrderBy(x=>x.At).ThenBy(x=>x.Symbol,StringComparer.Ordinal))
        {
            while(k<matured.Length&&matured[k].AvailableAt<x.At)
            {
                var y=matured[k++];var row=new NativePathSample(y.Symbol,y.AssetClass,y.At,y.AvailableAt,features[(y.Symbol,y.At)],y.Move,y.Up,y.Down,y.FirstLower,y.FirstUpper,y.Horizon);
                foreach(string scope in new[]{"S/"+y.Symbol,"C/"+(y.AssetClass??y.Symbol)})
                {var key=(y.Horizon,scope);if(!history.TryGetValue(key,out var q))history.Add(key,q=new());q.Enqueue(row);while(q.Count>256)q.Dequeue();}
            }
            int raw=Math.Sign(x.Context.FastEfficiency);
            void Record(string name,int side,NativePathDistributionForecast? f)
            {
                var key=(Stage(x.At),x.Symbol,x.Horizon,name,x.At/86400000);
                if(!daily.TryGetValue(key,out var stat))daily.Add(key,stat=new());stat.Add(side,x,raw,f);
            }
            Record("RAW_REFERENCE",raw,null);
            foreach(var (mode,half) in modes)
            {
                var scope=mode=="LOCAL"?"S/"+x.Symbol:"C/"+(x.AssetClass??x.Symbol);
                history.TryGetValue((x.Horizon,scope),out var rows);
                var forecast=NativeCausalPathDistribution.Estimate(rows??new Queue<NativePathSample>(),x.Symbol,x.AssetClass,features[(x.Symbol,x.At)],x.At,mode,half);
                decimal? uncertainty=forecast?.Mean-forecast?.LowerMean;
                int side=forecast is null?0:forecast.Mean>uncertainty?1:forecast.Mean< -uncertainty?-1:0;
                Record(mode+"_"+half,side,forecast);
            }
        }
        var results=daily.GroupBy(x=>new{x.Key.Stage,x.Key.Symbol,x.Key.H,x.Key.Method}).Select(g=>new{
            g.Key.Stage,g.Key.Symbol,HorizonMinutes=g.Key.H,g.Key.Method,Days=g.Count(),Observations=g.Sum(x=>x.Value.Count),
            Active=g.Sum(x=>x.Value.Active),MeanDailyMoveAtr=g.Average(x=>x.Value.Move/x.Value.Count),
            MeanDailyIncrementVsRawAtr=g.Average(x=>(x.Value.Move-x.Value.MatchedRaw)/x.Value.Count),
            ProbabilityObservations=g.Sum(x=>x.Value.ProbCount),Brier=g.Sum(x=>x.Value.ProbCount)>0?
                (decimal?)g.Sum(x=>x.Value.Brier)/g.Sum(x=>x.Value.ProbCount):null,
            QuantilePinball=g.Sum(x=>x.Value.ProbCount)>0?(decimal?)g.Sum(x=>x.Value.Pinball)/g.Sum(x=>x.Value.ProbCount):null}).ToArray();
        // Select globally on equal-symbol/day later-development increments;
        // the final exposed interval never chooses its own winning method.
        var selectionScores=daily.Where(x=>x.Key.Stage=="SELECTION"&&x.Key.Method!="RAW_REFERENCE")
            .GroupBy(x=>new{x.Key.H,x.Key.Method}).Select(g=>{
                var days=g.GroupBy(x=>x.Key.Day).Select(d=>d.Average(x=>(x.Value.Move-x.Value.MatchedRaw)/x.Value.Count)).ToArray();
                decimal mean=days.Average();decimal se=days.Length>1?(decimal)Math.Sqrt((double)(days.Sum(d=>(d-mean)*(d-mean))/(days.Length*(days.Length-1m)))):decimal.MaxValue/10m;
                return new{g.Key.H,g.Key.Method,Increment=mean,Lower=mean-(decimal)Math.Sqrt(2*Math.Log(modes.Length))*se};}).ToArray();
        var choices=selectionScores.GroupBy(x=>x.H).Select(g=>g.OrderByDescending(x=>x.Lower).First()).Select(x=>new{x.H,Method=x.Lower>0m?x.Method:"CASH",x.Increment,x.Lower}).ToArray();
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{Study="OWNER_DISTRIBUTION_PATH_1",SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            Markets=markets.Select(m=>m.Symbol).ToArray(),Labels=observations.Count,Coverage=coverage,Results=results,Selection=selectionScores,Choices=choices,
            ChronologicalMaturityStrict=true,SelectionMultiplicity=modes.Length,SamplingMinutes=60,PathBarrierIntrabarAmbiguityRetained=true,
            PriceInformationOnly=true,PortfolioEvaluated=false,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false}));
        return 0;
    }
}
