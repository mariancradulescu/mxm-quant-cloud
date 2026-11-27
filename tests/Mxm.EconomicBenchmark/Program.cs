using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

// Deterministic synthetic technical benchmark, not broker data or economic evidence.
const long day=86400000L;
const long start=1700006400000L;
var results=new List<object>();
foreach(int size in (args.Contains("--small")?new[]{256}:new[]{256,1024,4096}))
{
    var rng=new Random(479+size);
    var rows=Enumerable.Range(0,size).Select(i=>
    {
        long clock=start+(i/64)*day+(i%64)*300000L;
        var features=Enumerable.Range(0,18).SelectMany(j=>new[]{
            (decimal)rng.Next(-100,101)/100m,(decimal)(rng.Next(5)==0?0:1)}).ToArray();
        return new NativeCompleteSample("S"+i%16,clock,clock+300000L,features,
            (decimal)rng.Next(-150,151)/100m){AssetClass="C"+i%4};
    }).ToArray();
    var gross=new NativeCompleteDistribution(rows,false){MaskedEconomicContext=true};
    var net=new NativeCompleteDistribution(rows.Select((x,i)=>x with {OutcomeR=x.OutcomeR-(i%7+1)/100m}).ToArray(),false){MaskedEconomicContext=true};
    // Warm JIT on a small independent model.
    _=new NativeCompleteDistribution(rows.Take(64).ToArray(),false){MaskedEconomicContext=true}
        .Predict(rows[0].Features,start+day,2m);
    long allocated=GC.GetAllocatedBytesForCurrentThread();
    var watch=Stopwatch.StartNew();
    var paired=Environment.GetEnvironmentVariable("MXM_ECONOMIC_PAIRED_DISTRIBUTION")=="1"
        ?new NativeCompleteDistributionPair(gross,net).Calibrate():null;
    var calibratedGross=paired?.Gross??gross.Calibrate(rows);
    var calibratedNet=paired?.Net??net.Calibrate(net.Samples);
    double calibrationMs=watch.Elapsed.TotalMilliseconds;
    watch.Restart();
    var predictions=Enumerable.Range(0,128).Select(i=>
    {
        var row=rows[(i*31)%size];
        long clock=i%3==0?row.SettledAt:rows[^1].SettledAt+1;
        var value=paired is null
            ?(Gross:calibratedGross.Predict(row.Features,clock,3.17m),Net:calibratedNet.Predict(row.Features,clock,3.17m))
            :paired.Predict(row.Features,clock,3.17m);
        return new {value.Gross,value.Net};
    }).ToArray();
    double predictionMs=watch.Elapsed.TotalMilliseconds;
    var digest=Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(new
    {
        calibratedGross.BiasR,calibratedGross.UncertaintyR,
        NetBias=calibratedNet.BiasR,NetUncertainty=calibratedNet.UncertaintyR,Predictions=predictions
    })));
    results.Add(new {Size=size,CalibrationMs=calibrationMs,PredictionMs=predictionMs,
        AllocatedBytes=GC.GetAllocatedBytesForCurrentThread()-allocated,Digest=digest});
}
// Independent deterministic registry lookup microbenchmark: original
// collect-all algorithm versus the allocation-free production lookup.
var prefixes=Enumerable.Range(0,8192).Select(i=>
{
    long at=1000L+i*100;
    return new NativeValuationPrefix("S","BID",new NativeHistoricalFundingPrefix(
        "AUTHENTIC_LATEST_PREFIX",at-50,at+75,at,1m+i/10000m,true,true),new string('a',64));
}).ToArray();
var registry=new NativeReusableValuationRegistry(prefixes);
var maximum=new long[prefixes.Length];
for(int i=0;i<prefixes.Length;i++)
    maximum[i]=Math.Max(i==0?-1:maximum[i-1],prefixes[i].Witness.SearchThrough);
NativeHistoricalFundingPrefix? Legacy(long at)
{
    int lo=0,hi=prefixes.Length;
    while(lo<hi){int mid=lo+(hi-lo)/2;if(prefixes[mid].Witness.At<=at)lo=mid+1;else hi=mid;}
    var found=new List<NativeValuationPrefix>();
    for(int i=lo-1;i>=0&&maximum[i]>=at;i--)
        if(prefixes[i].Witness.SearchFrom<=at&&at<=prefixes[i].Witness.SearchThrough)found.Add(prefixes[i]);
    var usable=found.ToArray();
    if(usable.Length==0)return null;
    var latest=usable[0].Witness;
    if(usable.Any(r=>r.Witness.At!=latest.At||r.Witness.Price!=latest.Price))return null;
    return latest with {SearchThrough=at};
}
var queries=Enumerable.Range(0,100000).Select(i=>950L+((i*7919L)%820000L)).ToArray();
foreach(var at in queries.Take(1024)){_=Legacy(at);_=registry.At("S",true,at);}
var expected=queries.Select(Legacy).ToArray();
if(!queries.Select(at=>registry.At("S",true,at)).SequenceEqual(expected))
    throw new InvalidOperationException("VALUATION_REGISTRY_BENCHMARK_PARITY");
object MeasureRegistry(Func<long,NativeHistoricalFundingPrefix?> lookup)
{
    long allocated=GC.GetAllocatedBytesForCurrentThread();
    var timer=Stopwatch.StartNew();
    decimal sum=0m;int count=0;
    foreach(long at in queries)if(lookup(at) is { } mark){sum+=mark.Price;count++;}
    timer.Stop();
    return new {Milliseconds=timer.Elapsed.TotalMilliseconds,
        AllocatedBytes=GC.GetAllocatedBytesForCurrentThread()-allocated,Matches=count,PriceSum=sum};
}
var legacy=MeasureRegistry(Legacy);
var optimized=MeasureRegistry(at=>registry.At("S",true,at));
using var process=Process.GetCurrentProcess();
process.Refresh();
Console.WriteLine(JsonSerializer.Serialize(new {Results=results,Timings=NativeEconomicProfiler.Snapshot(),
    Registry=new {Rows=prefixes.Length,Queries=queries.Length,ExactParity=true,Legacy=legacy,Optimized=optimized},
    PeakWorkingSetBytes=process.PeakWorkingSet64,ManagedBytes=GC.GetTotalMemory(false)}));
