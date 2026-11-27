using System.Text.Json;
using System.Security.Cryptography;
using Mxm.Core;

// Annual information diagnostic. Authentic trendbars are not executable
// prices. No fees, fill, financing, equity or portfolio is inferred.
if(args is ["--distribution",var distributionSource,var distributionOutput]){Environment.Exit(DistributionAnnual.Run(distributionSource,distributionOutput));return;}
if(args.Length!=2)throw new ArgumentException("ANNUAL_PATH_ARGUMENTS");
var bytes=File.ReadAllBytes(args[0]);
var input=JsonSerializer.Deserialize<Market[]>(bytes)??throw new InvalidDataException("ANNUAL_PATH_INPUT");
var names=new[]{"AUS200","III.GB","USDCAD","USTN2YR-F"};
if(!input.Select(x=>x.Symbol).Order(StringComparer.Ordinal).SequenceEqual(names))
    throw new InvalidDataException("ANNUAL_PATH_UNIVERSE");
const long step=300_000L,day=86_400_000L;
static long U(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
var start=U(2025,11,1);var selection=U(2026,5,1);var evaluation=U(2026,8,1);var end=U(2026,11,26);
string Stage(long at)=>at<selection?"DEVELOPMENT":at<evaluation?"SELECTION":"EVALUATION_EXPOSED";
var observations=new List<Label>();
var coverage=new Dictionary<string,long>();
void Count(string key)=>coverage[key]=coverage.GetValueOrDefault(key)+1;
foreach(var market in input)
{
    NativeClosedMarketBar[] Bars(string period,long width)
    {
        var raw=market.Bars[period];
        if(raw.Length==0||raw.Any(x=>x.Length!=7||x[1]-x[0]!=width||x[0]<start||x[1]>end||
            x[4]<=0||x[4]>Math.Min(x[2],x[5])||x[3]<Math.Max(x[2],x[5])||x[6]<0)||
            raw.Zip(raw.Skip(1)).Any(x=>x.First[1]>x.Second[0]))
            throw new InvalidDataException("ANNUAL_PATH_BAR_GEOMETRY");
        return raw.Select(x=>new NativeClosedMarketBar(x[0],x[1],x[2]/100000m,x[3]/100000m,x[4]/100000m,x[5]/100000m,x[6])).ToArray();
    }
    var fast=Bars("M5",step);var medium=Bars("M15",3*step);var slow=Bars("H1",12*step);
    int mi=0,si=0;
    for(int i=0;i<fast.Length;i++)
    {
        long at=fast[i].CloseAt+1;
        while(mi<medium.Length&&medium[mi].CloseAt<at)mi++;
        while(si<slow.Length&&slow[si].CloseAt<at)si++;
        if(i<5||mi<4||si<4){Count(market.Symbol+"/WARMUP");continue;}
        NativeBarWindow Window(NativeBarTimeframe tf,NativeClosedMarketBar[] a,int stop,int n)=>
            new(tf,n,a[stop-1].CloseAt,at,"AUTHENTIC_ARCHIVED_CLOSED_TRENDBARS",NativeBarStatus.Ready,a[(stop-n)..stop]);
        if(medium[mi-1].CloseAt!=fast[i].CloseAt/900_000L*900_000L||
            slow[si-1].CloseAt!=fast[i].CloseAt/3_600_000L*3_600_000L)
        {Count(market.Symbol+"/MISSING_SLOW_CONTEXT");continue;}
        var windows=new NativeBarContext(at,new[]{Window(NativeBarTimeframe.M5,fast,i+1,6),
            Window(NativeBarTimeframe.M15,medium,mi,4),Window(NativeBarTimeframe.H1,slow,si,4)});
        var c=NativeClosedPathPrediction.ObserveClosedWindows(windows,at);
        if(c is null){Count(market.Symbol+"/UNSUPPORTED_CONTEXT");continue;}
        string regime=Math.Abs(c.SlowEfficiency)>=.6m?"PERSISTENT":Math.Abs(c.SlowEfficiency)<=.2m?"CHOPPY":"TRANSITION";
        foreach(int h in new[]{15,30,60})
        {
            if(fast[i].CloseAt%(h*60_000L)!=0)continue;
            Count(market.Symbol+"/"+h+"/ELIGIBLE_CONTEXT");
            int n=h/5;
            if(i+n>=fast.Length||Enumerable.Range(i+1,n).Any(j=>fast[j].OpenAt!=fast[j-1].CloseAt))
            {Count(market.Symbol+"/"+h+"/CENSORED_GAP");continue;}
            long maturity=fast[i+n].CloseAt;
            if(Stage(at)!=Stage(maturity)){Count(market.Symbol+"/"+h+"/CROSS_STAGE");continue;}
            decimal entry=fast[i].Close;
            var future=fast[(i+1)..(i+n+1)];
            decimal move=(future[^1].Close-entry)/c.Atr;
            decimal up=(future.Max(x=>x.High)-entry)/c.Atr,down=(entry-future.Min(x=>x.Low))/c.Atr;
            observations.Add(new(market.Symbol,at,maturity,h,regime,move,Math.Max(up,0m),Math.Max(down,0m),
                new Dictionary<string,int>{
                    ["FAST"]=Math.Sign(c.FastEfficiency),["ALIGNMENT"]=Math.Sign(c.Alignment),
                    ["PULLBACK"]=Math.Sign(c.PullbackRepair),["EXHAUSTION"]=Math.Sign(c.Exhaustion)}));
        }
    }
}
// Calibration is pooled by instrument and regime only after label maturity.
// Equal-weight daily symbol outcomes are reported, not independent tick counts.
var history=new Dictionary<(string Symbol,int H,string Regime,string Method,int Signal),Stats>();
var daily=new Dictionary<(string Stage,string Symbol,int H,string Method,long Day),Stats>();
var matured=observations.OrderBy(x=>x.AvailableAt).ThenBy(x=>x.Symbol,StringComparer.Ordinal).ToArray();
int k=0;
foreach(var label in observations.OrderBy(x=>x.At).ThenBy(x=>x.Symbol,StringComparer.Ordinal))
{
    while(k<matured.Length&&matured[k].AvailableAt<label.At)
    {
        var x=matured[k++];
        foreach(var (method,side) in x.Signals)
        {
            if(side==0)continue;
            var key=(x.Symbol,x.Horizon,x.Regime,method,side);
            if(!history.TryGetValue(key,out var stat))history.Add(key,stat=new());
            stat.Add(side*x.Move,side*x.Move>0m,side>0?x.Up:x.Down,side>0?x.Down:x.Up,x.At/day);
        }
    }
    foreach(var (method,signal) in label.Signals)
    {
        void Record(string policy,int side,decimal? prob)
        {
            var key=(Stage(label.At),label.Symbol,label.Horizon,policy,label.At/day);
            if(!daily.TryGetValue(key,out var stat))daily.Add(key,stat=new());
            stat.Add(side*label.Move,side*label.Move>0m,side==0?0m:side>0?label.Up:label.Down,
                side==0?0m:side>0?label.Down:label.Up,label.At/day,side==0,prob);
        }
        Record(method+"/RAW",signal,null);
        history.TryGetValue((label.Symbol,label.Horizon,label.Regime,method,signal),out var local);
        var peers=history.Where(x=>x.Key.Symbol!=label.Symbol&&x.Key.H==label.Horizon&&
            x.Key.Regime==label.Regime&&x.Key.Method==method&&x.Key.Signal==signal&&x.Value.Days.Count>=8).Select(x=>x.Value).ToArray();
        decimal? peerMean=peers.Length>=2?peers.Average(x=>x.Sum/x.Count):null;
        decimal? peerProbability=peers.Length>=2?peers.Average(x=>(x.Positive+1m)/(x.Count+2m)):null;
        bool localReady=local is {Count:>=30}&&local.Days.Count>=8;
        decimal? mean=localReady?local!.Sum/local.Count:null;
        decimal? probability=localReady?(local!.Positive+1m)/(local.Count+2m):null;
        Record(method+"/LOCAL_CALIBRATED",signal!=0&&mean>0m&&probability>.5m?signal:0,probability);
        Record(method+"/TRANSFER_ONLY",signal!=0&&peerMean>0m&&peerProbability>.5m?signal:0,peerProbability);
    }
}
var results=daily.GroupBy(x=>new{x.Key.Stage,x.Key.Symbol,x.Key.H,x.Key.Method}).Select(g=>{
    var ds=g.Select(x=>x.Value).ToArray();
    var mean=ds.Average(x=>x.Sum/x.Count);
    decimal variance=ds.Length>1?ds.Sum(x=>(x.Sum/x.Count-mean)*(x.Sum/x.Count-mean))/(ds.Length-1):0m;
    return new{g.Key.Stage,g.Key.Symbol,HorizonMinutes=g.Key.H,g.Key.Method,Days=ds.Length,
        Observations=ds.Sum(x=>x.Count),Wait=ds.Sum(x=>x.Wait),MeanDailyMoveAtr=mean,
        DailyMeanStandardError=ds.Length>1?(double?)Math.Sqrt((double)variance/ds.Length):null,
        DirectionHits=ds.Sum(x=>x.Positive),MeanDailyFavorableAtr=ds.Average(x=>x.Favorable/x.Count),
        MeanDailyAdverseAtr=ds.Average(x=>x.Adverse/x.Count),ProbabilityObservations=ds.Sum(x=>x.ProbCount),
        Brier=ds.Sum(x=>x.ProbCount)>0?(decimal?)ds.Sum(x=>x.Brier)/ds.Sum(x=>x.ProbCount):null};
}).OrderBy(x=>x.Stage).ThenBy(x=>x.Symbol).ThenBy(x=>x.HorizonMinutes).ThenBy(x=>x.Method).ToArray();
File.WriteAllText(args[1],JsonSerializer.Serialize(new{
    Study="OWNER_BREADTH_8_ANNUAL_PATH_INFORMATION_1",SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
    Markets=names,Labels=observations.Count,Coverage=coverage,Results=results,PriceInformationOnly=true,
    HistoricalExecutionCertified=false,FundingIncluded=false,PortfolioEvaluated=false,IndependentConfirmationCertified=false,
    DailyStandardErrorNotIndependentConfidenceInterval=true,Orders=0,CloudActivated=false}));
record Market(string Symbol,Dictionary<string,long[][]> Bars);
record Label(string Symbol,long At,long AvailableAt,int Horizon,string Regime,decimal Move,decimal Up,decimal Down,Dictionary<string,int> Signals);
sealed class Stats
{
    public long Count,Positive,Wait,ProbCount;
    public decimal Sum,Favorable,Adverse,Brier;
    public HashSet<long> Days=new();
    public void Add(decimal v,bool positive,decimal favorable,decimal adverse,long day,bool wait=false,decimal? p=null)
    {
        Count++;Positive+=positive?1:0;Wait+=wait?1:0;Sum+=v;Favorable+=favorable;Adverse+=adverse;Days.Add(day);
        if(p is decimal prob&&!wait){ProbCount++;decimal error=prob-(positive?1m:0m);Brier+=error*error;}
    }
}
