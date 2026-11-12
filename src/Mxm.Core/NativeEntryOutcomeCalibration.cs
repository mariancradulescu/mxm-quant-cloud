namespace Mxm.Core;

// Gross returns are dimensionless signed post-entry midpoint returns.
// Costs are kept separate in EUR at the authenticated minimum physical volume.
public sealed record NativeEntryForecast(
    long FeaturesKnownAt,long OutcomesKnownThrough,int Direction,int TrainingDays,
    decimal PositiveGrossProbability,decimal UnconditionalPositiveGrossProbability,decimal MeanGrossReturn,decimal MeanBenchmarkGrossReturn,
    decimal MeanUncertaintyReturn,decimal DownsideReturn);

public sealed record NativeEntryCalibrationReport(
    int TrainingPairs,int EvaluationPairs,int MissingPairs,int ScoredForecasts,
    decimal? MeanRealizedGrossBps,decimal? MeanRealizedNetBps,decimal? DirectionBrier,
    decimal? NeutralBrier,decimal? UnconditionalBrier,int PredictedPositiveGross,int RealizedPositiveGross,
    string FrozenTrainingSha256);

// One kernel for native market observations and chronological replay.
// Outcomes are paired even when the capital book abstains. Evaluation labels
// update diagnostics only. One pair per symbol/half-hour, not per tick.
public sealed class NativeEntryOutcomeCalibration
{
    public const int HoldingMinutes=45;
    public const string ExitPolicy=NativeCausalExitResearch.PredictionInvalidation;
    public static readonly long DevelopmentBoundary=new DateTimeOffset(
        2026,3,2,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    private readonly long boundary;
    private readonly Dictionary<(string Symbol,long Start),Pending> pending=new();
    private readonly Dictionary<string,long> lastSlot=new(StringComparer.Ordinal);
    private readonly Dictionary<string,List<Label>> training=new(StringComparer.Ordinal);
    private int trainingPairs,evaluationPairs,missingPairs,scored,forecastPositive,actualPositive;
    private decimal grossSum,netSum,brier,neutralBrier,unconditionalBrier;

    private sealed record Leg(decimal EntryPrice,decimal Extreme,long ExitRequested=0,
        decimal? GrossReturn=null,decimal? NetReturn=null,decimal WorstReturn=0);
    private sealed record Pending(string Cohort,long Start,NativeEntryForecast? Forecast,
        NativeObservedContractTerms Contract,decimal Slippage,long EntryAt=0,
        decimal EntryMid=0,decimal EntryFee=0,decimal EntryFx=0,NativeExitSeed? Seed=null,
        Leg? Long=null,Leg? Short=null);
    private sealed record Label(long Day,long KnownAt,decimal LongGross,decimal ShortGross,
        decimal LongDownside,decimal ShortDownside);

    public NativeEntryOutcomeCalibration(long boundary)
    {
        if(boundary<=0)throw new ArgumentOutOfRangeException(nameof(boundary));
        this.boundary=boundary;
    }

    public static string? Family(string symbol)=>symbol switch {
        "AUDUSD" or "GBPUSD" or "NZDUSD"=>"FX",
        "SpotBrent" or "XAUUSD"=>"COMMODITY", _=>null
    };

    public NativeEntryCalibrationReport Report()=>new(trainingPairs,evaluationPairs,missingPairs+pending.Count,
        scored,scored>0?10000m*grossSum/scored:null,scored>0?10000m*netSum/scored:null,
        scored>0?brier/scored:null,scored>0?neutralBrier/scored:null,
        scored>0?unconditionalBrier/scored:null,forecastPositive,actualPositive,
        Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
            System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(training.OrderBy(x=>x.Key,StringComparer.Ordinal))))
            .ToLowerInvariant());

    // Shared eligibility for features and directional controls. The last
    // 60-minute return conditions the expected direction; short-term alignment
    // separates continuation from a possible reversal of the same prior move.
    public IReadOnlyDictionary<string,(long KnownAt,NativeEntryForecast? Forecast)> Observe(
        long at,NativeProductMarket[] markets)
    {
        foreach(var item in pending.Where(p=>at-p.Value.Start>90*60000L ||
            (p.Value.Start<boundary && at>=boundary)).ToArray())
        {
            pending.Remove(item.Key);
            missingPairs++;
        }
        foreach(var market in markets)
            foreach(var observation in pending.Where(p=>p.Key.Symbol==market.Symbol).ToArray())
                Update(at,market,observation.Value);

        var opportunities=new Dictionary<string,(long,NativeEntryForecast?)>(StringComparer.Ordinal);
        long minute=at/60000L%1440;
        if(minute<15*60 || minute>17*60+30 || minute%30!=0)return opportunities;
        foreach(var market in markets)
        {
            var family=Family(market.Symbol);
            if(family is null || market.Contract is not {MinimumUnits:>0} contract ||
               lastSlot.GetValueOrDefault(market.Symbol)==at/1800000L ||
               market.M5.Length<3 || market.M15.Length<4 ||
               !NativeCausalExitResearch.TrySeed(market.M5,market.M15,at,out _))
                continue;
            var m5=market.M5[^1];
            var m15=market.M15[^1];
            if(m5.CloseAt!=m15.CloseAt || at-m5.CloseAt>=60000L)continue;
            lastSlot[market.Symbol]=at/1800000L;
            var priorMove=m15.Close-market.M15[^4].Open;
            var shortMove=m5.Close-market.M5[^3].Open;
            if(priorMove==0m)continue;
            // Setups are a common opportunity tape for all policies. Paired
            // hypothetical labels may overlap, unlike funded positions.
            string cohort=family+"/"+Math.Sign(priorMove)+"/"+(priorMove*shortMove>0m);
            var forecast=at>=boundary?Predict(cohort,m5.CloseAt):null;
            opportunities.Add(market.Symbol,(m5.CloseAt,forecast));
            pending.Add((market.Symbol,at),new(cohort,at,forecast,contract,market.SlippagePerSideQuote));
        }
        return opportunities;
    }

    private NativeEntryForecast? Predict(string cohort,long knownAt)
    {
        if(!training.TryGetValue(cohort,out var labels))return null;
        var days=labels.GroupBy(x=>x.Day).ToArray();
        if(days.Length<5)return null;
        var longMeans=days.Select(d=>d.Average(x=>x.LongGross)).ToArray();
        var shortMeans=days.Select(d=>d.Average(x=>x.ShortGross)).ToArray();
        int side=longMeans.Average()>=shortMeans.Average()?1:-1;
        var selected=side==1?longMeans:shortMeans;
        var control=side==1?shortMeans:longMeans;
        var edge=selected.Zip(control,(a,b)=>a-Math.Max(0,b)).ToArray();
        decimal Probability(IEnumerable<Label> observations)=>observations.Average(
            x=>(side==1?x.LongGross:x.ShortGross)>0m?1m:0m);
        string family=cohort[..cohort.IndexOf('/')];
        var unconditional=training.Where(x=>x.Key.StartsWith(family+"/",StringComparison.Ordinal))
            .SelectMany(x=>x.Value).GroupBy(x=>x.Day).Average(Probability);
        static decimal Se(decimal[] sample)
        {
            var mean=sample.Average();
            return (decimal)Math.Sqrt((double)(sample.Sum(x=>(x-mean)*(x-mean))/
                (sample.Length*(sample.Length-1))));
        }
        return new(knownAt,labels.Max(x=>x.KnownAt),side,days.Length,
            days.Average(Probability),unconditional,
            selected.Average(),selected.Average()-edge.Average(),
            Math.Max(Se(selected),Se(edge)),
            days.Average(d=>d.Average(x=>side==1?x.LongDownside:x.ShortDownside)));
    }

    private void Update(long at,NativeProductMarket market,Pending p)
    {
        if((p.EntryAt==0 && at-p.Start>=600000L) || at-p.Start>90*60000L || (p.Start<boundary && at>=boundary))
        {
            pending.Remove((market.Symbol,p.Start));
            missingPairs++;
            return;
        }
        var q=market.Quote;
        var units=p.Contract.MinimumUnits;
        if(p.EntryAt==0)
        {
            if(at<p.Start+1000)return;
            if(!NativeCausalExitResearch.TrySeed(market.M5,market.M15,at,out var seed))return;
            var ask=q.Ask+p.Slippage;
            var bid=q.Bid-p.Slippage;
            if(bid<=0)return;
            pending[(market.Symbol,p.Start)]=p with {EntryAt=at,EntryMid=(q.Ask+q.Bid)/2m,
                EntryFee=Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units),
                EntryFx=(q.EurCredit+q.EurDebit)/2m,Seed=seed,Long=new(ask,ask),Short=new(bid,bid)};
            return;
        }

        Leg UpdateLeg(int side,Leg leg)
        {
            if(leg.GrossReturn.HasValue)return leg;
            decimal exit=side==1?q.Bid-p.Slippage:q.Ask+p.Slippage;
            decimal debit=side*(exit-leg.EntryPrice);
            leg=leg with {WorstReturn=Math.Max(leg.WorstReturn,-debit/p.EntryMid)};
            if(leg.ExitRequested>0)
            {
                if(at<leg.ExitRequested+1000)return leg;
                var financing=p.Contract.OriginalBrokerAuthenticated
                    ?NativeBrokerContractCosts.SignedFinancing(p.Contract,p.EntryAt,at,side,units,q.EurCredit,q.EurDebit)
                    :NativeBrokerContractCosts.SignedFinancingCurrentAlgo(p.Contract,p.EntryAt,at,side,units,q.EurCredit,q.EurDebit);
                if(financing is null)return leg;
                decimal net=debit*units*(debit>=0?q.EurCredit:q.EurDebit)-p.EntryFee-
                    Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units)+financing.Value;
                return leg with {GrossReturn=side*((q.Ask+q.Bid)/2m-p.EntryMid)/p.EntryMid,
                    NetReturn=net/(p.EntryMid*units*p.EntryFx)};
            }
            var verdict=NativeCausalExitResearch.Assess(ExitPolicy,at,p.EntryAt,side,leg.EntryPrice,
                p.Seed!,leg.Extreme,q,market.M5,market.M15,HoldingMinutes);
            return leg with {Extreme=verdict.FavorableExtreme,ExitRequested=verdict.RequestClose?at:0};
        }

        var lo=UpdateLeg(1,p.Long!);
        var sh=UpdateLeg(-1,p.Short!);
        if(lo.GrossReturn is not decimal lg || sh.GrossReturn is not decimal sg)
        {
            pending[(market.Symbol,p.Start)]=p with {Long=lo,Short=sh};
            return;
        }
        pending.Remove((market.Symbol,p.Start));
        if(at<boundary)
        {
            if(!training.TryGetValue(p.Cohort,out var labels))training[p.Cohort]=labels=new();
            labels.Add(new(p.Start/86400000L,at,lg,sg,lo.WorstReturn,sh.WorstReturn));
            trainingPairs++;
        }
        else
        {
            evaluationPairs++;
            if(p.Forecast is not { } f)return;
            var leg=f.Direction==1?lo:sh;
            decimal actual=leg.GrossReturn!.Value>0?1m:0m;
            scored++;
            if(actual>0)actualPositive++;
            if(f.PositiveGrossProbability>.5m)forecastPositive++;
            grossSum+=leg.GrossReturn.Value;
            netSum+=leg.NetReturn!.Value;
            brier+=(f.PositiveGrossProbability-actual)*(f.PositiveGrossProbability-actual);
            neutralBrier+=.25m;
            unconditionalBrier+=(f.UnconditionalPositiveGrossProbability-actual)*
                (f.UnconditionalPositiveGrossProbability-actual);
        }
    }
}
