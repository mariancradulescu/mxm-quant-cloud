using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record PathOpening(long At,int Horizon,Ucp1MarketFrame Entry,NativeClosedPathPrediction.Context Context,
        Dictionary<string,int> Directions);
    sealed class PathDaily
    {
        public long Count,Correct,Wait;
        public decimal GrossR,NetBeforeFundingR,NetBeforeFundingEur,LongR,ShortR;
    }

    public static int RunClosedPathInformation(string protocolPath,string sourcePath,string protectionPath,string output)
    {
        var pb=File.ReadAllBytes(protocolPath);var sb=File.ReadAllBytes(sourcePath);
        var plan=JsonSerializer.Deserialize<PavMarketPlan>(pb,Json)!;
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        if(plan.Start!=input.Start||plan.End!=input.End||plan.SourceProtocolSha256!=input.ProtocolSha256||
            plan.EvidenceManifestSha256!=input.EvidenceManifestSha256||
            !(plan.Start<plan.SelectionFrom&&plan.SelectionFrom<plan.EvaluationFrom&&plan.EvaluationFrom<plan.End))
            throw new InvalidDataException("PATH_INFORMATION_SOURCE_BINDING");
        var tape=new EerProtectionTape(protectionPath);
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=tape};
        var streams=input.Markets.ToDictionary(m=>m.Market.Name,m=>new EerStream(m),StringComparer.Ordinal);
        var pending=new Dictionary<(string,int),PathOpening>();
        var daily=new Dictionary<(string Stage,int Horizon,string Method,long Day,string Symbol),PathDaily>();
        var censored=new Dictionary<string,int>();
        var horizons=new[]{15,30,60};
        void Count(string key)=>censored[key]=censored.GetValueOrDefault(key)+1;
        foreach(long at in Enumerable.Range(0,checked((int)((input.End-input.Start)/EurStep)))
            .Select(i=>input.Start+EurOffset+i*EurStep))
        {
            source.BeginHistoricalClock();
            var frames=streams.Values.Select(m=>source.Frame(m,at,"PATH_INFORMATION",0m,general:true))
                .OfType<Ucp1MarketFrame>().ToDictionary(m=>m.Symbol,StringComparer.Ordinal);
            foreach(var (key,entry) in pending.ToArray())
            {
                if(!frames.TryGetValue(key.Item1,out var exit))
                {pending.Remove(key);Count("MISSING_INTERMEDIATE_MARK_OR_SESSION");continue;}
                if(at<entry.At+entry.Horizon*60_000L)continue;
                pending.Remove(key);
                if(at!=entry.At+entry.Horizon*60_000L){Count("NONEXACT_HORIZON");continue;}
                var q=entry.Entry.Quote;var e=exit.Quote;
                decimal mid0=(q.Bid+q.Ask)/2m,mid1=(e.Bid+e.Ask)/2m;
                decimal units=entry.Entry.Contract.MinimumUnits;
                decimal scale=entry.Context.Atr*units*q.EurDebit;
                if(scale<=0m){Count("INVALID_NORMALIZATION");continue;}
                string stage=entry.At<plan.SelectionFrom?"DEVELOPMENT":entry.At<plan.EvaluationFrom?"SELECTION":"EVALUATION";
                if((entry.At<plan.SelectionFrom&&at>=plan.SelectionFrom)||(entry.At<plan.EvaluationFrom&&at>=plan.EvaluationFrom))
                {Count("CROSS_STAGE_LABEL");continue;}
                decimal gross=(mid1-mid0)/entry.Context.Atr;
                decimal longNet=NativeExecutableEconomics.EstimateNet(q,e,1,units,q.Ask,e.Bid,0m);
                decimal shortNet=NativeExecutableEconomics.EstimateNet(q,e,-1,units,q.Bid,e.Ask,0m);
                foreach(var (method,side) in entry.Directions)
                {
                    var id=(stage,entry.Horizon,method,entry.At/86_400_000L,entry.Entry.Symbol);
                    if(!daily.TryGetValue(id,out var stat))daily.Add(id,stat=new());
                    decimal net=side==0?0m:side>0?longNet:shortNet;
                    stat.Count++;stat.Wait+=side==0?1:0;stat.Correct+=side*gross>0m?1:0;
                    stat.GrossR+=side*gross;stat.NetBeforeFundingR+=net/scale;stat.NetBeforeFundingEur+=net;
                    stat.LongR+=longNet/scale;stat.ShortR+=shortNet/scale;
                }
            }
            var contexts=frames.Values.Select(f=>(Frame:f,Context:NativeClosedPathPrediction.Observe(f,at)))
                .Where(x=>x.Context is not null).ToArray();
            foreach(var row in contexts)
            {
                var f=row.Frame;var c=row.Context!;
                if(streams[f.Symbol].Source.Market.DatedDevelopment?.ShortAllowed!=true)
                {Count("NO_PAIRED_CONTRACT_DIRECTION");continue;}
                var peers=contexts.Where(x=>x.Frame.Symbol!=f.Symbol&&f.OfficialAssetClass is not null&&
                    x.Frame.OfficialAssetClass==f.OfficialAssetClass).Select(x=>x.Context!);
                decimal? relative=NativeClosedPathPrediction.RelativeDisplacement(c,peers);
                foreach(int h in horizons)
                {
                    if((at-input.Start-EurOffset)%(h*60_000L)!=0)continue;
                    var methods=new Dictionary<string,int>{
                        ["FAST_REFERENCE"]=Math.Sign(c.FastEfficiency),["MULTISCALE_ALIGNMENT"]=Math.Sign(c.Alignment),
                        ["PULLBACK_REPAIR"]=Math.Sign(c.PullbackRepair),["EXHAUSTION"]=Math.Sign(c.Exhaustion)};
                    if(relative is decimal value){methods["PEER_RELATIVE_CONTINUATION"]=Math.Sign(value);
                        methods["PEER_RELATIVE_REVERSION"]=-Math.Sign(value);}
                    pending.Add((f.Symbol,h),new(at,h,f,c,methods));
                }
            }
        }
        Count("RIGHT_CENSORED_PRESENT");censored["RIGHT_CENSORED_PRESENT"]=pending.Count;
        var summaries=daily.GroupBy(x=>new{x.Key.Stage,x.Key.Horizon,x.Key.Method}).Select(group=>
        {
            var days=group.GroupBy(x=>x.Key.Day).Select(day=>new{
                Gross=day.Average(x=>x.Value.GrossR/x.Value.Count),
                Net=day.Average(x=>x.Value.NetBeforeFundingR/x.Value.Count),
                Long=day.Average(x=>x.Value.LongR/x.Value.Count),
                Short=day.Average(x=>x.Value.ShortR/x.Value.Count)}).ToArray();
            return new {group.Key.Stage,group.Key.Horizon,group.Key.Method,
                Days=days.Length,Observations=group.Sum(x=>x.Value.Count),Wait=group.Sum(x=>x.Value.Wait),
                Correct=group.Sum(x=>x.Value.Correct),MeanDailyGrossAtr=days.Average(x=>x.Gross),
                MeanDailyNetBeforeFundingAtr=days.Average(x=>x.Net),MeanDailyMatchedLongAtr=days.Average(x=>x.Long),
                MeanDailyMatchedShortAtr=days.Average(x=>x.Short),PositiveNetDays=days.Count(x=>x.Net>0m)};
        }).OrderBy(x=>x.Stage).ThenBy(x=>x.Horizon).ThenBy(x=>x.Method).ToArray();
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{
            Study="MONETARY_CLOSED_PATH_INFORMATION_1",SourceSha256=GeneralSha(sb),ProtocolSha256=GeneralSha(pb),
            HorizonMinutes=horizons,Results=summaries,Censored=censored,MarketCount=streams.Count,
            PairedPriceMarksOnly=true,NoSyntheticExecution=true,FundingIncluded=false,
            PortfolioEvaluated=false,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false},Json));
        return 0;
    }
}
