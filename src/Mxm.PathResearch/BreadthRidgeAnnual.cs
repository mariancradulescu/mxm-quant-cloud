using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;
using Moments=Mxm.Core.NativeCausalRidgeMoments;

internal static class BreadthRidgeAnnual
{
    const long Day=86_400_000, Hour=3_600_000, Step=300_000, Offset=15_000;
    const int D=12;
    record Quote(long At,long BidAt,long AskAt,decimal Bid,decimal Ask);
    record Market(string Symbol,string? AssetClass,Dictionary<string,NativeClosedMarketBar[]> Bars,Quote[] Quotes);
    record Context(string Symbol,string? AssetClass,long At,NativeClosedPathPrediction.Context Path,decimal Price);
    record Label(Context Context,long AvailableAt,int Horizon,double[] X,decimal Move,decimal Up,decimal Down,Quote? Entry,Quote? Exit);
    sealed class Stat
    {
        public int N,Active,QuoteEligible,QuoteObserved,QuoteActive;
        public decimal Move,Raw,QuoteMove,Favorable,Adverse,ForecastError;
        public decimal[] Hurdles=new decimal[4];
        public void Add(Label l,int side,decimal predicted)
        {
            N++;if(side!=0)Active++;
            decimal move=side*l.Move;Move+=move;Raw+=Math.Sign(l.Context.Path.FastEfficiency)*l.Move;
            Favorable+=side>0?l.Up:side<0?l.Down:0;Adverse+=side>0?l.Down:side<0?l.Up:0;
            ForecastError+=Math.Abs(predicted-l.Move);
            decimal[] hurdle={0,.05m,.15m,.3m};
            for(int i=0;i<hurdle.Length;i++)if(side!=0)Hurdles[i]+=move-hurdle[i];
            if(l.Entry is { } q)
            {
                QuoteEligible++;
                if(l.Exit is { } exit)
                {
                    QuoteObserved++;
                    if(side!=0&&Math.Abs(predicted)>(q.Ask-q.Bid)/l.Context.Path.Atr)
                    {
                        QuoteActive++;
                        QuoteMove+=(side>0?exit.Bid-q.Ask:q.Bid-exit.Ask)/l.Context.Path.Atr;
                    }
                }
            }
        }
    }
    static long U(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly long Start=U(2025,11,1),Selection=U(2026,5,1),Evaluation=U(2026,8,1),End=U(2026,11,27);
    static string Stage(long t)=>t<Selection?"DEVELOPMENT":t<Evaluation?"SELECTION":"EVALUATION_EXPOSED";
    static string[] Scopes(Context c)=>new[]{"S/"+c.Symbol,"C/"+(c.AssetClass??c.Symbol),"GLOBAL"};
    static bool Fresh(Quote q)=>q.Bid>0&&q.Ask>=q.Bid&&q.BidAt<=q.At&&q.AskAt<=q.At&&q.At-q.BidAt<=30000&&q.At-q.AskAt<=30000;
    static NativeClosedMarketBar[] Valid(Market m,string tf,long width)
    {
        var b=m.Bars[tf].Where(x=>x.CloseAt-x.OpenAt==width&&x.OpenAt>=Start&&x.CloseAt<End&&x.Low>0&&
            x.Low<=Math.Min(x.Open,x.Close)&&x.High>=Math.Max(x.Open,x.Close)&&x.TickVolume>=0).OrderBy(x=>x.OpenAt).ToArray();
        if(b.Zip(b.Skip(1)).Any(x=>x.First.CloseAt>x.Second.OpenAt))throw new InvalidDataException("RIDGE_OVERLAPPING_SOURCE_BARS");
        return b;
    }
    public static int Run(string source,string output,string? forecastsOutput=null)
    {
        using var stream=File.OpenRead(source);
        var options=new JsonSerializerOptions {NumberHandling=JsonNumberHandling.AllowReadingFromString};
        var markets=JsonSerializer.Deserialize<Market[]>(stream,options)??throw new InvalidDataException("RIDGE_INPUT");
        if(markets.Length==0||markets.Select(x=>x.Symbol).Distinct(StringComparer.Ordinal).Count()!=markets.Length||forecastsOutput is null&&markets.Length!=57)
            throw new InvalidDataException("RIDGE_UNIVERSE");
        var contexts=new List<Context>();var labels=new List<(Context C,long Maturity,int H,decimal Move,decimal Up,decimal Down,Quote? Entry,Quote? Exit)>();
        var coverage=new Dictionary<string,int>();
        void Count(string name)=>coverage[name]=coverage.GetValueOrDefault(name)+1;
        foreach(var market in markets)
        {
            var fast=Valid(market,"M5",Step);var medium=Valid(market,"M15",3*Step);var slow=Valid(market,"H1",Hour);
            var quotes=market.Quotes.Where(Fresh).ToDictionary(x=>x.At);int mi=0,si=0;
            for(int i=5;i<fast.Length;i++)
            {
                long at=fast[i].CloseAt+Offset;if(fast[i].CloseAt%Hour!=0)continue;
                while(mi<medium.Length&&medium[mi].CloseAt<at)mi++;while(si<slow.Length&&slow[si].CloseAt<at)si++;
                if(mi<4||si<4||medium[mi-1].CloseAt!=fast[i].CloseAt||slow[si-1].CloseAt!=fast[i].CloseAt){Count(market.Symbol+"/CONTEXT_GAP");continue;}
                NativeBarWindow W(NativeBarTimeframe tf,NativeClosedMarketBar[] b,int n,int take)=>
                    new(tf,take,b[n-1].CloseAt,at,"AUTHENTIC_CLOSED_SOURCE",NativeBarStatus.Ready,b[(n-take)..n]);
                var path=NativeClosedPathPrediction.ObserveClosedWindows(new(at,new[]{W(NativeBarTimeframe.M5,fast,i+1,6),
                    W(NativeBarTimeframe.M15,medium,mi,4),W(NativeBarTimeframe.H1,slow,si,4)}),at);
                if(path is null){Count(market.Symbol+"/UNSUPPORTED_CONTEXT");continue;}
                var c=new Context(market.Symbol,market.AssetClass,at,path,fast[i].Close);
                contexts.Add(c);Count(market.Symbol+"/CONTEXT");
                foreach(int horizon in new[]{30,60})
                {
                    int n=horizon/5;
                    if(i+n>=fast.Length||Enumerable.Range(i+1,n).Any(j=>fast[j].OpenAt!=fast[j-1].CloseAt))
                    {Count(market.Symbol+"/CENSORED_"+horizon);continue;}
                    long maturity=fast[i+n].CloseAt+Offset;
                    if(Stage(at)!=Stage(maturity)){Count(market.Symbol+"/PURGED_"+horizon);continue;}
                    decimal move=(fast[i+n].Close-c.Price)/path.Atr,up=0,down=0;
                    for(int j=i+1;j<=i+n;j++){up=Math.Max(up,(fast[j].High-c.Price)/path.Atr);down=Math.Max(down,(c.Price-fast[j].Low)/path.Atr);}
                    labels.Add((c,maturity,horizon,move,up,down,quotes.GetValueOrDefault(at),quotes.GetValueOrDefault(maturity)));
                }
            }
        }
        // Peer membership is determined before considering maturity or label existence.
        var features=new Dictionary<(string,long),double[]>();
        foreach(var g in contexts.GroupBy(x=>x.At))
        {
            var rows=g.ToArray();
            foreach(var c in rows)
            {
                var p=c.Path;var peers=rows.Where(x=>x.Symbol!=c.Symbol&&c.AssetClass is not null&&x.AssetClass==c.AssetClass).ToArray();
                double phase=2*Math.PI*(c.At%Day)/Day;
                features[(c.Symbol,c.At)]=new[]{1d,(double)p.FastEfficiency,(double)p.MediumEfficiency,(double)p.SlowEfficiency,
                    Math.Atan((double)p.FastDisplacement),Math.Atan((double)p.SlowDisplacement),Math.Atan((double)p.PullbackRepair),
                    Math.Atan((double)p.Exhaustion),Math.Sin(phase),Math.Cos(phase),
                    peers.Length>=2?(double)peers.Average(x=>x.Path.Alignment):0d,peers.Length>=2?1d:0d};
            }
        }
        var rowsByTime=labels.Select(x=>new Label(x.C,x.Maturity,x.H,features[(x.C.Symbol,x.C.At)],x.Move,x.Up,x.Down,x.Entry,x.Exit))
            .OrderBy(x=>x.Context.At).ThenBy(x=>x.Context.Symbol,StringComparer.Ordinal).ThenBy(x=>x.Horizon).ToArray();
        var matured=rowsByTime.OrderBy(x=>x.AvailableAt).ToArray();int k=0;
        var history=new Dictionary<(int,string),Moments>();
        var fits=new Dictionary<(int,string),double[,]?>();
        var forecasts=forecastsOutput is null?null:new List<object>();
        var daily=new Dictionary<(string Stage,string Symbol,int H,string Method,long Day),Stat>();
        string[] methods={"LOCAL_RIDGE","CLASS_RIDGE","GLOBAL_RIDGE"};
        // Prediction availability never depends on existence of a later label.
        // The immutable original scoring route still uses only observed labels.
        var observed=forecastsOutput is null?null:rowsByTime.ToDictionary(l=>(l.Context.Symbol,l.Context.At,l.Horizon));
        var decisions=forecastsOutput is null?rowsByTime:contexts.SelectMany(c=>new[]{30,60}
            .Select(h=>new Label(c,0,h,features[(c.Symbol,c.At)],0m,0m,0m,null,null)))
            .OrderBy(l=>l.Context.At).ThenBy(l=>l.Context.Symbol,StringComparer.Ordinal).ThenBy(l=>l.Horizon).ToArray();
        foreach(var group in decisions.GroupBy(x=>x.Context.At/Day))
        {
            long cutoff=group.Key*Day;
            // At each new day, combine ONLY labels mature before the day.
            // Equal-symbol within each mature day; equal weight per day.
            var batch=new Dictionary<(long Day,int H,string Scope,string Symbol),Moments>();
            while(k<matured.Length&&matured[k].AvailableAt<cutoff)
            {
                var l=matured[k++];
                foreach(string scope in Scopes(l.Context))
                {
                    var key=(l.AvailableAt/Day,l.Horizon,scope,l.Context.Symbol);
                    if(!batch.TryGetValue(key,out var m))batch.Add(key,m=new());
                    m.Add(l.X,l.Move,l.Up,l.Down,1,l.AvailableAt);
                }
            }
            foreach(var b in batch.GroupBy(x=>(x.Key.Day,x.Key.H,x.Key.Scope)))
            {
                var key=(b.Key.H,b.Key.Scope);if(!history.TryGetValue(key,out var m))history.Add(key,m=new());
                var values=b.ToArray();foreach(var x in values)m.AddDay(x.Value,1d/values.Length);
                m.Days++;
            }
            fits.Clear();
            foreach(var l in group)
            {
                var scopes=Scopes(l.Context);
                for(int i=0;i<methods.Length;i++)
                {
                    var key=(l.Horizon,scopes[i]);
                    if(!fits.TryGetValue(key,out var coef))
                    {coef=history.GetValueOrDefault(key)?.Fit();fits.Add(key,coef);}
                    decimal pred=0;int side=0;decimal favorable=0,adverse=0;
                    if(coef is not null)
                    {
                        double[] pred3=new double[3];
                        for(int a=0;a<D;a++)for(int b=0;b<3;b++)pred3[b]+=coef[a,b]*l.X[a];
                        if(pred3.All(double.IsFinite))
                        {
                            pred=(decimal)pred3[0];favorable=(decimal)pred3[1];adverse=(decimal)pred3[2];
                            // Predicted favorable amplitude must exceed the
                            // predicted adverse amplitude, not merely a direction sign.
                            if(pred>0&&pred3[1]>Math.Max(0,pred3[2]))side=1;
                            if(pred<0&&pred3[2]>Math.Max(0,pred3[1]))side=-1;
                        }
                    }
                    if(forecasts is not null&&coef is not null)
                    {var model=history[key];forecasts.Add(new{l.Context.Symbol,Forecast=new NativeRidgeEconomicForecast(l.Context.At,cutoff,model.LatestTrainingAt,model.Days,l.Horizon,methods[i],side,pred,
                        favorable,adverse,l.Context.Price,l.Context.Path.Atr)});}
                    var scored=observed is null?l:observed.GetValueOrDefault((l.Context.Symbol,l.Context.At,l.Horizon));
                    if(scored is null)continue;
                    var dk=(Stage(l.Context.At),l.Context.Symbol,l.Horizon,methods[i],group.Key);
                    if(!daily.TryGetValue(dk,out var stat))daily.Add(dk,stat=new());
                    stat.Add(scored,side,pred);
                }
            }
        }
        var results=daily.GroupBy(x=>new{x.Key.Stage,x.Key.Symbol,x.Key.H,x.Key.Method}).Select(g=>new{
            g.Key.Stage,g.Key.Symbol,HorizonMinutes=g.Key.H,g.Key.Method,Days=g.Count(),Observations=g.Sum(x=>x.Value.N),
            Active=g.Sum(x=>x.Value.Active),MeanDailyMoveAtr=g.Average(x=>x.Value.Move/x.Value.N),
            MeanDailyRawAtr=g.Average(x=>x.Value.Raw/x.Value.N),
            MeanDailyFavorableAtr=g.Average(x=>x.Value.Favorable/x.Value.N),MeanDailyAdverseAtr=g.Average(x=>x.Value.Adverse/x.Value.N),
            MeanAbsoluteForecastErrorAtr=g.Sum(x=>x.Value.ForecastError)/g.Sum(x=>x.Value.N),
            HurdleSensitivity=Enumerable.Range(0,4).Select(i=>g.Average(x=>x.Value.Hurdles[i]/x.Value.N)).ToArray(),
            QuoteEligible=g.Sum(x=>x.Value.QuoteEligible),QuoteObserved=g.Sum(x=>x.Value.QuoteObserved),
            QuoteActive=g.Sum(x=>x.Value.QuoteActive),QuoteGrossSpreadInclusiveAtr=g.Sum(x=>x.Value.QuoteMove)}).ToArray();
        var scores=daily.Where(x=>x.Key.Stage=="SELECTION").GroupBy(x=>new{x.Key.H,x.Key.Method}).Select(g=>{
            // Selection sees no later exposed outcomes; cost hurdle is only
            // normalized sensitivity, never asserted to be historical NET.
            var days=g.GroupBy(x=>x.Key.Day).Select(d=>d.Average(x=>x.Value.Hurdles[2]/x.Value.N)).ToArray();
            decimal mean=days.Average();
            decimal? lower=days.Length<20?null:mean-2.64m*(decimal)Math.Sqrt((double)(days.Sum(x=>(x-mean)*(x-mean))/(days.Length*(days.Length-1m))));
            return new{g.Key.H,g.Key.Method,Days=days.Length,Mean=mean,Lower=lower};
        }).ToArray();
        var choices=new[]{30,60}.Select(h=>{
            var best=scores.Where(x=>x.H==h&&x.Lower.HasValue).OrderByDescending(x=>x.Lower).FirstOrDefault();
            return new{HorizonMinutes=h,Method=best is not null&&best.Lower is >0m?best.Method:"CASH",Lower=best?.Lower};
        }).ToArray();
        stream.Position=0;string sha=Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{Study=forecastsOutput is null?"OWNER_BREADTH57_CAUSAL_RIDGE_AMPLITUDE_1":"OWNER_CAUSAL_RIDGE_MONETARY_OFFERS_1",
            SourceSha256=sha,Markets=markets.Select(x=>x.Symbol).ToArray(),Labels=rowsByTime.Length,Coverage=coverage,
            Results=results,Selection=scores,Choices=choices,SelectionMultiplicity=6,TrainingStrictlyMatureBeforeDay=true,
            PeerMembershipUsesClosedContextsOnly=true,PriceHurdlesAtr=new[]{0m,.05m,.15m,.3m},QuoteScreenSpreadOnly=true,
            PortfolioEvaluated=false,HistoricalExecutionCertified=false,HistoricalTariffContinuityCertified=false,
            IndependentConfirmationCertified=false,Orders=0,CloudActivated=false}));
        if(forecastsOutput is not null)File.WriteAllBytes(forecastsOutput,JsonSerializer.SerializeToUtf8Bytes(forecasts));
        return 0;
    }
}
