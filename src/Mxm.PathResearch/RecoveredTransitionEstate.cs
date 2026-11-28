using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;
internal static class RecoveredTransitionEstate
{
    const long Day=86400000L;
    static readonly long Selection=new DateTimeOffset(2026,5,1,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly long Evaluation=new DateTimeOffset(2026,8,1,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static string Phase(long at)=>at<Selection?"DEVELOPMENT":at<Evaluation?"SELECTION":"EXPOSED";
    record Item(string Symbol,string Timeframe,string File,string Sha256,int Rows);
    record Series(string Symbol,string Timeframe,NativeClosedMarketBar[] Bars);
    record Label(long At,long Mature,int Horizon,int Direction,int Run,int[] FixedSignals,decimal Move,decimal Up,decimal Down);
    sealed class Stat
    {
        public long N,Active,Hits;public decimal Move,Favorable,Adverse;
        public void Add(Label l,int side){N++;if(side==0)return;Active++;if(side*l.Move>0)Hits++;
            Move+=side*l.Move;Favorable+=side>0?l.Up:l.Down;Adverse+=side>0?l.Down:l.Up;}
    }
    static int Hrc(NativeClosedMarketBar[] bars,int i,int n)
    {
        if(i<n+1)return 0;decimal[] r=new decimal[n+1];
        for(int j=0;j<=n;j++){int k=i-n+j;if(bars[k-1].CloseAt!=bars[k].OpenAt)return 0;r[j]=bars[k].Close-bars[k-1].Close;}
        decimal x=0,y=0;for(int j=0;j<n;j++){x+=r[j];y+=r[j+1];}x/=n;y/=n;
        decimal xy=0,xx=0,yy=0;for(int j=0;j<n;j++){decimal a=r[j]-x,b=r[j+1]-y;xy+=a*b;xx+=a*a;yy+=b*b;}
        if(xx==0||yy==0)return 0;
        double corr=(double)xy/(Math.Sqrt((double)xx)*Math.Sqrt((double)yy));
        return Math.Abs(corr)<.2?0:Math.Sign(corr)*Math.Sign(r[^1]);
    }
    public static int Run(string folder,string output)
    {
        var options=new JsonSerializerOptions{NumberHandling=JsonNumberHandling.AllowReadingFromString};
        var manifest=JsonSerializer.Deserialize<Item[]>(File.ReadAllBytes(Path.Combine(folder,"manifest.json")),options)!;
        var seen=new HashSet<(string,string)>();var results=new List<object>();long total=0;
        string[] methods={"MOMENTUM","HRC1_4","HRC1_8","HRC1_21","SQP1_STATE","RCP1_COMPRESSION"};
        var selection=new Dictionary<(string Tf,int H,string Method,long Day),List<decimal>>();
        foreach(var item in manifest)
        {
            if(!seen.Add((item.Symbol,item.Timeframe))||Path.GetFileName(item.File)!=item.File)throw new InvalidDataException("ESTATE_IDENTITY");
            var path=Path.Combine(folder,item.File);
            using(var stream=File.OpenRead(path))
                if(Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant()!=item.Sha256)throw new InvalidDataException("ESTATE_HASH");
            var data=JsonSerializer.Deserialize<Series>(File.ReadAllBytes(path),options)!;
            if(data.Symbol!=item.Symbol||data.Timeframe!=item.Timeframe||data.Bars.Length!=item.Rows)throw new InvalidDataException("ESTATE_SCOPE");
            var bars=data.Bars;long width=(long)Enum.Parse<NativeBarTimeframe>(item.Timeframe)*60000;
            if(bars.Any(b=>b.CloseAt-b.OpenAt!=width||b.Low<=0||b.Low>Math.Min(b.Open,b.Close)||b.High<Math.Max(b.Open,b.Close))||
                bars.Zip(bars.Skip(1)).Any(p=>p.First.CloseAt>p.Second.OpenAt))throw new InvalidDataException("ESTATE_INVALID_BAR");
            var labels=new List<Label>();int run=0,prev=0;
            for(int i=1;i<bars.Length;i++)
            {
                if(bars[i-1].CloseAt!=bars[i].OpenAt){run=0;prev=0;continue;}
                int side=Math.Sign(bars[i].Close-bars[i-1].Close);
                run=side==0?0:side==prev?run+1:1;prev=side;
                if(i<8||Enumerable.Range(i-7,8).Any(j=>bars[j-1].CloseAt!=bars[j].OpenAt))continue;
                decimal atr=0;for(int j=i-7;j<=i;j++)atr+=Math.Max(bars[j].High-bars[j].Low,Math.Max(Math.Abs(bars[j].High-bars[j-1].Close),Math.Abs(bars[j].Low-bars[j-1].Close)));
                atr/=8;if(atr<=0)continue;
                decimal upper=decimal.MinValue,lower=decimal.MaxValue,range=0;
                for(int j=i-8;j<i;j++){upper=Math.Max(upper,bars[j].High);lower=Math.Min(lower,bars[j].Low);range+=bars[j].High-bars[j].Low;}
                int compression=(upper-lower)<=range*.65m?(bars[i].Close>upper?1:bars[i].Close<lower?-1:0):0;
                var signals=new[]{side,Hrc(bars,i,4),Hrc(bars,i,8),Hrc(bars,i,21),0,compression};
                foreach(int h in new[]{1,3})
                {
                    if(i%h!=0||i+h>=bars.Length||Enumerable.Range(i+1,h).Any(j=>bars[j-1].CloseAt!=bars[j].OpenAt))continue;
                    long at=bars[i].CloseAt+1,mature=bars[i+h].CloseAt+1;if(Phase(at)!=Phase(mature))continue;
                    decimal up=0,down=0;for(int j=i+1;j<=i+h;j++){up=Math.Max(up,(bars[j].High-bars[i].Close)/atr);down=Math.Max(down,(bars[i].Close-bars[j].Low)/atr);}
                    labels.Add(new(at,mature,h,side,Math.Min(run,4),signals,(bars[i+h].Close-bars[i].Close)/atr,up,down));
                }
            }
            total+=labels.Count;var maturity=labels.OrderBy(l=>l.Mature).ToArray();int k=0;
            var fitted=new Dictionary<(int H,int Side,int Run),List<(long Day,decimal Sum,int N)>>();
            var daily=new Dictionary<(string Phase,int H,string Method,long Day),Stat>();
            foreach(var group in labels.GroupBy(l=>l.At/Day))
            {
                long cutoff=group.Key*Day;
                while(k<maturity.Length&&maturity[k].Mature<cutoff)
                {
                    var l=maturity[k++];if(l.Direction==0)continue;
                    var key=(l.Horizon,l.Direction,l.Run);
                    if(!fitted.TryGetValue(key,out var list))fitted.Add(key,list=new());
                    long d=l.Mature/Day;
                    if(list.Count>0&&list[^1].Day==d){var a=list[^1];list[^1]=(d,a.Sum+l.Move,a.N+1);}
                    else list.Add((d,l.Move,1));
                }
                var forecasts=fitted.ToDictionary(x=>x.Key,x=>{
                    if(x.Value.Count<20)return 0m;
                    return x.Value.Average(a=>a.Sum/a.N);
                });
                foreach(var l in group)
                    for(int i=0;i<methods.Length;i++)
                    {
                        int side=i==4?Math.Sign(forecasts.GetValueOrDefault((l.Horizon,l.Direction,l.Run))):l.FixedSignals[i];
                        var key=(Phase(l.At),l.Horizon,methods[i],group.Key);
                        if(!daily.TryGetValue(key,out var stat))daily.Add(key,stat=new());
                        stat.Add(l,side);
                    }
            }
            foreach(var g in daily.GroupBy(x=>new{x.Key.Phase,x.Key.H,x.Key.Method}))
            {
                results.Add(new{item.Symbol,item.Timeframe,g.Key.Phase,HorizonBars=g.Key.H,g.Key.Method,
                    Days=g.Count(),Labels=g.Sum(x=>x.Value.N),Active=g.Sum(x=>x.Value.Active),Hits=g.Sum(x=>x.Value.Hits),
                    MeanDailyMoveAtr=g.Average(x=>x.Value.Move/x.Value.N),
                    MeanDailyFavorableAtr=g.Average(x=>x.Value.Favorable/x.Value.N),
                    MeanDailyAdverseAtr=g.Average(x=>x.Value.Adverse/x.Value.N),
                    MeanDailyAfterIllustrativeHurdleAtr=g.Average(x=>(x.Value.Move-.15m*x.Value.Active)/x.Value.N)});
                if(g.Key.Phase=="SELECTION")foreach(var x in g)
                {
                    var key=(item.Timeframe,g.Key.H,g.Key.Method,x.Key.Day);
                    if(!selection.TryGetValue(key,out var values))selection.Add(key,values=new());
                    values.Add((x.Value.Move-.15m*x.Value.Active)/x.Value.N);
                }
            }
        }
        var scores=selection.GroupBy(x=>new{x.Key.Tf,x.Key.H,x.Key.Method}).Select(g=>{
            var days=g.Select(x=>x.Value.Average()).ToArray();decimal mean=days.Average();
            decimal? lower=days.Length<20?null:mean-3.3m*(decimal)Math.Sqrt((double)(days.Sum(x=>(x-mean)*(x-mean))/(days.Length*(days.Length-1m))));
            return new{g.Key.Tf,g.Key.H,g.Key.Method,Days=days.Length,Mean=mean,Lower=lower};
        }).ToArray();
        var choice=scores.Where(s=>s.Lower is >0m).OrderByDescending(s=>s.Lower).FirstOrDefault();
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{Study="OWNER_RECOVERED_HRC_SQP_RCP_ESTATE_1",
            Markets=seen.Select(x=>x.Item1).Distinct().Order().ToArray(),Series=seen.Count,Labels=total,Results=results,
            Selection=scores,Choice=choice?.Method??"CASH",SelectionMultiplicity=84,IllustrativeHurdleAtr=.15m,
            PriceInformationOnly=true,PortfolioEvaluated=false,HistoricalCostsCertified=false,
            IndependentConfirmationCertified=false,Orders=0,CloudActivated=false}));
        return 0;
    }
}
