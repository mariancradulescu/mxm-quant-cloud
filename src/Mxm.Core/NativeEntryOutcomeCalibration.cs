namespace Mxm.Core;

// Gross returns are dimensionless signed post-entry midpoint returns.
// Costs are kept separate in EUR at the authenticated minimum physical volume.
public sealed record NativeEntryForecast(
    long FeaturesKnownAt,long OutcomesKnownThrough,int Direction,int TrainingDays,
    decimal PositiveGrossProbability,decimal UnconditionalPositiveGrossProbability,decimal MeanGrossReturn,decimal MeanBenchmarkGrossReturn,
    decimal MeanUncertaintyReturn,decimal DownsideReturn)
{
    public decimal? StandaloneAdverseNetReturn {get;init;}
    public decimal? IncrementalAdverseNetReturn {get;init;}
    public decimal? MeanAdverseFrictionReturn {get;init;}
}

public sealed record NativeEntryCalibrationReport(
    int TrainingPairs,int EvaluationPairs,int MissingPairs,int ScoredForecasts,
    decimal? MeanRealizedGrossBps,decimal? MeanRealizedNetBps,decimal? DirectionBrier,
    decimal? NeutralBrier,decimal? UnconditionalBrier,int PredictedPositiveGross,int RealizedPositiveGross,
    string FrozenTrainingSha256)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=
        System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeInventoryDiagnostics? Inventory {get;init;}
    [System.Text.Json.Serialization.JsonIgnore(Condition=
        System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public Dictionary<string,NativeIntegratedWeek>? OpportunityFunnel {get;init;}
    [System.Text.Json.Serialization.JsonIgnore(Condition=
        System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? FrozenModel {get;init;}
    [System.Text.Json.Serialization.JsonIgnore(Condition=
        System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public Dictionary<string,NativeConditionalDistribution>? ConditionalDistributions {get;init;}
    [System.Text.Json.Serialization.JsonIgnore(Condition=
        System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public Dictionary<string,NativeIntegratedFamilyDiagnostics>? IntegratedFamilies {get;init;}
}

public sealed record NativeInventoryDiagnostics(int Pairs,decimal? FadeGrossBps,
    decimal? FadeCentralNetBps,decimal? FadeAdverseNetBps,decimal? ContinuationAdverseNetBps);

// One kernel for native market observations and chronological replay.
// Outcomes are paired even when the capital book abstains. Evaluation labels
// update diagnostics only. One pair per symbol/half-hour, not per tick.
public sealed class NativeEntryOutcomeCalibration
{
    public const int HoldingMinutes=45;
    public const string ExitPolicy=NativeCausalExitResearch.PredictionInvalidation;
    public static readonly long DevelopmentBoundary=new DateTimeOffset(
        2026,3,2,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    public const int InventoryHoldingMinutes=90;
    public const string InventoryExitPolicy=NativeCausalExitResearch.Chandelier;
    private readonly long boundary;
    private readonly bool inventory;
    private readonly bool integrated;
    private readonly bool conditional;
    private readonly NativeIntegratedSnapshot? restored;
    private NativeIntegratedSnapshot? frozen;
    internal string? FrozenEnvelope=>(frozen??restored)?.Seal();
    private readonly Dictionary<string,NativeIntegratedWeek> opportunitiesByWeek=new();
    private bool priced=>inventory || integrated;
    private readonly Dictionary<string,List<(decimal Gross,decimal Central,decimal Adverse,decimal Reverse,decimal? Error)>> familyOutcomes=new();
    private readonly Dictionary<string,List<(decimal Gross,decimal Central,decimal Adverse,decimal Reverse,decimal? Error,decimal? Baseline)>> conditionalOutcomes=new();

    private Dictionary<string,NativeConditionalDistribution> Distributions()=>conditionalOutcomes.ToDictionary(
        row=>row.Key,row=>{
            var x=row.Value;
            var ordered=x.Select(v=>v.Adverse).OrderBy(v=>v).ToArray();
            decimal P(decimal p)=>10000m*ordered[(int)Math.Floor((ordered.Length-1)*p)];
            var wins=x.Where(v=>v.Adverse>0).ToArray();
            var losses=x.Where(v=>v.Adverse<0).ToArray();
            return new NativeConditionalDistribution(x.Count,wins.Length,losses.Length,x.Count-wins.Length-losses.Length,
                10000m*x.Average(v=>v.Gross),10000m*x.Average(v=>v.Central),
                10000m*x.Average(v=>v.Adverse),10000m*x.Average(v=>v.Reverse),
                P(.10m),P(.50m),P(.90m),wins.Length==0?null:10000m*wins.Average(v=>v.Adverse),
                losses.Length==0?null:10000m*losses.Average(v=>v.Adverse),
                10000m*x.Average(v=>v.Gross-v.Adverse),x.Average(v=>v.Error),x.Average(v=>v.Baseline));
        });
    private Dictionary<string,NativeIntegratedFamilyDiagnostics> FamilyDiagnostics()=>familyOutcomes.ToDictionary(
        row=>row.Key,row=>new NativeIntegratedFamilyDiagnostics(row.Value.Count,
            10000m*row.Value.Average(x=>x.Gross),10000m*row.Value.Average(x=>x.Central),
            10000m*row.Value.Average(x=>x.Adverse),10000m*row.Value.Average(x=>x.Reverse),
            row.Value.Count(x=>x.Adverse>0m),row.Value.Average(x=>x.Error)));
    private readonly Dictionary<string,List<InventoryLabel>> inventoryTraining=new(StringComparer.Ordinal);
    private int Holding=>inventory?InventoryHoldingMinutes:HoldingMinutes;
    private string Policy=>inventory?InventoryExitPolicy:ExitPolicy;
    private sealed record InventoryLabel(long Week,long KnownAt,decimal FadeGross,decimal FadeAdverse,
        decimal OppositeAdverse,decimal FadeDownside);
    private readonly Dictionary<(string Symbol,long Start),Pending> pending=new();
    private readonly Dictionary<string,long> lastSlot=new(StringComparer.Ordinal);
    private readonly Dictionary<string,List<Label>> training=new(StringComparer.Ordinal);
    private int trainingPairs,evaluationPairs,missingPairs,scored,forecastPositive,actualPositive;
    private decimal grossSum,netSum,brier,neutralBrier,unconditionalBrier;
    private decimal fadeGross,fadeCentral,fadeAdverse,continuationAdverse;

    private sealed record Leg(decimal EntryPrice,decimal Extreme,long ExitRequested=0,
        decimal? GrossReturn=null,decimal? NetReturn=null,decimal WorstReturn=0,decimal AdverseReturn=0);
    private sealed record Pending(string Cohort,long Start,NativeEntryForecast? Forecast,
        NativeObservedContractTerms Contract,decimal Slippage,long EntryAt=0,
        decimal EntryMid=0,decimal EntryFee=0,decimal EntryFx=0,NativeExitSeed? Seed=null,
        Leg? Long=null,Leg? Short=null,int FadeSide=0,LedgerQuote? EntryQuote=null);
    private sealed record Label(long Day,long KnownAt,decimal LongGross,decimal ShortGross,
        decimal LongDownside,decimal ShortDownside);

    public NativeEntryOutcomeCalibration(long boundary,bool inventory=false,bool integrated=false,NativeIntegratedSnapshot? restored=null,bool conditional=false)
    {
        if(boundary<=0)throw new ArgumentOutOfRangeException(nameof(boundary));
        this.boundary=boundary;
        this.inventory=inventory;
        this.integrated=integrated;
        this.conditional=conditional;
        this.restored=restored;
    }

    public static string? Family(string symbol)=>symbol switch {
        "AUDUSD" or "GBPUSD" or "NZDUSD"=>"FX",
        "SpotBrent" or "XAUUSD"=>"COMMODITY", _=>null
    };

    public static string? InventoryFamily(string symbol)=>symbol switch {
        "AUDUSD" or "GBPUSD" or "NZDUSD"=>"FX",
        "XAUUSD" or "Copper"=>"METAL", _=>null
    };

    public NativeEntryCalibrationReport Report()=>new(trainingPairs,evaluationPairs,missingPairs+pending.Count,
        scored,scored>0?10000m*grossSum/scored:null,scored>0?10000m*netSum/scored:null,
        scored>0?brier/scored:null,scored>0?neutralBrier/scored:null,
        scored>0?unconditionalBrier/scored:null,forecastPositive,actualPositive,
        Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
            (priced?System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(inventoryTraining.OrderBy(x=>x.Key,StringComparer.Ordinal)):
                System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(training.OrderBy(x=>x.Key,StringComparer.Ordinal)))))
            .ToLowerInvariant())
        {
            Inventory=priced?new(evaluationPairs,Average(fadeGross),Average(fadeCentral),
                Average(fadeAdverse),Average(continuationAdverse)):null,
            OpportunityFunnel=integrated?opportunitiesByWeek:null,
            FrozenModel=integrated?frozen?.Seal():null,
            IntegratedFamilies=integrated?FamilyDiagnostics():null,
            ConditionalDistributions=conditional?Distributions():null
        };

    private void Count(long at,int stage)
    {
        var day=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        string key=System.Globalization.ISOWeek.GetYear(day)+"-W"+
            System.Globalization.ISOWeek.GetWeekOfYear(day).ToString("00");
        var row=opportunitiesByWeek.GetValueOrDefault(key)??new(0,0,0,0);
        opportunitiesByWeek[key]=stage switch {
            0=>row with {QuoteComplete=row.QuoteComplete+1},
            1=>row with {FeatureEligible=row.FeatureEligible+1},
            2=>row with {PredictionReady=row.PredictionReady+1},
            _=>row with {NetSupported=row.NetSupported+1}
        };
    }

    internal void CountNetSupported(long at)=>Count(at,3);

    private decimal? Average(decimal x)=>evaluationPairs>0?10000m*x/evaluationPairs:null;

    // Shared eligibility for features and directional controls. The last
    // 60-minute return conditions the expected direction; short-term alignment
    // separates continuation from a possible reversal of the same prior move.
    public IReadOnlyDictionary<string,(long KnownAt,NativeEntryForecast? Forecast)> Observe(
        long at,NativeProductMarket[] markets)
    {
        foreach(var item in pending.Where(p=>at-p.Value.Start>(priced?120:90)*60000L ||
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
        if(integrated)
        {
            if(!NativeIntegratedResearch.IsSlot(at))return opportunities;
            if(at>=boundary)
                frozen??=restored??(conditional?new NativeIntegratedSnapshot(boundary,null,null) {
                    Conditional=new[]{"FX/HIGH","FX/LOW","METAL/HIGH","METAL/LOW"}
                        .ToDictionary(x=>x,x=>PredictInventory(x,0,0))
                }:new(boundary,PredictInventory("FX",0,0),PredictInventory("METAL",0,0)));
        }
        else if(inventory)
        {
            if(minute!=16*60 || DateTimeOffset.FromUnixTimeMilliseconds(at).DayOfWeek!=DayOfWeek.Friday)
                return opportunities;
        }
        else if(minute<15*60 || minute>17*60+30 || minute%30!=0)return opportunities;
        foreach(var market in markets)
        {
            var family=conditional?NativeConditionalResearch.Family(market.Symbol):integrated?NativeIntegratedResearch.Family(market.Symbol):
                inventory?InventoryFamily(market.Symbol):Family(market.Symbol);
            if(conditional && family=="METAL" && minute%60!=30)continue;
            if(integrated && at>=boundary && family is not null && market.Contract is {MinimumUnits:>0})
                Count(at,0);
            if(family is null || market.Contract is not {MinimumUnits:>0} contract ||
               lastSlot.GetValueOrDefault(market.Symbol)==at/1800000L ||
               market.M5.Length<3 || market.M15.Length<4 ||
               !NativeCausalExitResearch.TrySeed(market.M5,market.M15,at,out _))
                continue;
            var m5=market.M5[^1];
            var m15=market.M15[^1];
            if(m5.CloseAt!=m15.CloseAt || at-m5.CloseAt>=60000L)continue;
            lastSlot[market.Symbol]=at/1800000L;
            var priorMove=m15.Close-market.M15[inventory?market.M15.Length-8:market.M15.Length-4].Open;
            var shortMove=m5.Close-market.M5[^3].Open;
            if(!integrated && priorMove==0m)continue;
            // Setups are a common opportunity tape for all policies. Paired
            // hypothetical labels may overlap, unlike funded positions.
            string cohort=priced?family:family+"/"+Math.Sign(priorMove)+"/"+(priorMove*shortMove>0m);
            var conditionalFeature=conditional?NativeConditionalResearch.Observe(market):(0,null);
            if(conditionalFeature.Item2 is { } selectedCohort)cohort=selectedCohort;
            int fade=conditional?conditionalFeature.Item1:integrated?NativeIntegratedResearch.Direction(market,markets):
                inventory?-Math.Sign(priorMove):0;
            if(integrated && fade==0)continue;
            if(integrated && at>=boundary)Count(at,1);
            var archived=conditional?frozen?.Conditional?.GetValueOrDefault(cohort):cohort=="FX"?frozen?.Fx:frozen?.Metal;
            var forecast=at<boundary?null:integrated?(archived is null?null:
                archived with {FeaturesKnownAt=m5.CloseAt,Direction=fade}):
                inventory?PredictInventory(cohort,m5.CloseAt,fade):Predict(cohort,m5.CloseAt);
            if(integrated && forecast is not null)Count(at,2);
            opportunities.Add(market.Symbol,(m5.CloseAt,forecast));
            pending.Add((market.Symbol,at),new(cohort,at,forecast,contract,market.SlippagePerSideQuote,FadeSide:fade));
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

    private NativeEntryForecast? PredictInventory(string cohort,long knownAt,int fade)
    {
        if(!inventoryTraining.TryGetValue(cohort,out var labels))return null;
        var weeks=labels.GroupBy(x=>x.Week).ToArray();
        if(weeks.Length<(integrated?4:3))return null;
        var standalone=weeks.Select(w=>w.Average(x=>x.FadeAdverse)).ToArray();
        var excess=weeks.Select(w=>w.Average(x=>x.FadeAdverse-x.OppositeAdverse)).ToArray();
        // Small-sample weekly dispersion, descriptive rather than independent coverage.
        static decimal Allowance(decimal[] x)
        {
            decimal mean=x.Average();
            return 3m*(decimal)Math.Sqrt((double)(x.Sum(y=>(y-mean)*(y-mean))/(x.Length*(x.Length-1))));
        }
        var probability=weeks.Average(w=>w.Average(x=>x.FadeAdverse>0m?1m:0m));
        decimal baseline=conditional?inventoryTraining.Where(x=>x.Key.StartsWith(cohort.Split('/')[0]+"/",StringComparison.Ordinal))
            .SelectMany(x=>x.Value).GroupBy(x=>x.Week).Average(w=>w.Average(x=>x.FadeAdverse>0m?1m:0m)):.5m;
        return new NativeEntryForecast(knownAt,labels.Max(x=>x.KnownAt),fade,weeks.Length,
            probability,baseline,weeks.Average(w=>w.Average(x=>x.FadeGross)),0m,
            Math.Max(Allowance(standalone),Allowance(excess)),
            weeks.Average(w=>w.Average(x=>x.FadeDownside)))
        {
            StandaloneAdverseNetReturn=standalone.Average(),
            IncrementalAdverseNetReturn=excess.Average(),
            MeanAdverseFrictionReturn=weeks.Average(w=>w.Average(x=>x.FadeGross-x.FadeAdverse))
        };
    }

    private void Update(long at,NativeProductMarket market,Pending p)
    {
        if((p.EntryAt==0 && at-p.Start>=600000L) || at-p.Start>(priced?120:90)*60000L || (p.Start<boundary && at>=boundary))
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
                EntryFx=(q.EurCredit+q.EurDebit)/2m,Seed=seed,Long=new(ask,ask),Short=new(bid,bid),EntryQuote=priced?q:null};
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
                decimal stress=0m;
                if(priced)
                {
                    var entry=p.EntryQuote!;
                    decimal stressedDebit=debit-
                        (entry.Ask-entry.Bid+q.Ask-q.Bid)/2m-2m*p.Slippage;
                    stress=stressedDebit*units*(stressedDebit>=0?q.EurCredit*.999m:q.EurDebit*1.001m)
                        -2m*(p.EntryFee+Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units))
                        +2m*Math.Min(0m,financing.Value);
                }
                return leg with {GrossReturn=side*((q.Ask+q.Bid)/2m-p.EntryMid)/p.EntryMid,
                    NetReturn=net/(p.EntryMid*units*p.EntryFx),AdverseReturn=stress/(p.EntryMid*units*p.EntryFx)};
            }
            var verdict=NativeCausalExitResearch.Assess(conditional?NativeConditionalResearch.Exit(market.Symbol):integrated?NativeIntegratedResearch.Exit(market.Symbol):Policy,at,p.EntryAt,side,leg.EntryPrice,
                p.Seed!,leg.Extreme,q,market.M5,market.M15,integrated?NativeIntegratedResearch.Holding(market.Symbol):Holding);
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
            if(priced)
            {
                if(!inventoryTraining.TryGetValue(p.Cohort,out var inventoryLabels))
                    inventoryTraining[p.Cohort]=inventoryLabels=new();
                var fade=p.FadeSide==1?lo:sh;
                var other=p.FadeSide==1?sh:lo;
                inventoryLabels.Add(new((p.Start+(integrated?259200000L:0L))/604800000L,at,fade.GrossReturn!.Value,
                    fade.AdverseReturn,other.AdverseReturn,fade.WorstReturn));
            }
            else
            {
                if(!training.TryGetValue(p.Cohort,out var labels))training[p.Cohort]=labels=new();
                labels.Add(new(p.Start/86400000L,at,lg,sg,lo.WorstReturn,sh.WorstReturn));
            }
            trainingPairs++;
        }
        else
        {
            evaluationPairs++;
            if(priced)
            {
                var fade=p.FadeSide==1?lo:sh;
                var other=p.FadeSide==1?sh:lo;
                fadeGross+=fade.GrossReturn!.Value;
                fadeCentral+=fade.NetReturn!.Value;
                fadeAdverse+=fade.AdverseReturn;
                continuationAdverse+=other.AdverseReturn;
                if(integrated)
                {
                    if(!familyOutcomes.TryGetValue(p.Cohort,out var rows))
                        familyOutcomes[p.Cohort]=rows=new();
                    decimal? delta=p.Forecast?.PositiveGrossProbability-(fade.AdverseReturn>0m?1m:0m);
                    rows.Add((fade.GrossReturn.Value,fade.NetReturn.Value,fade.AdverseReturn,
                        other.AdverseReturn,delta*delta));
                    if(conditional)
                    {
                        if(!conditionalOutcomes.TryGetValue(p.Cohort,out var samples))
                            conditionalOutcomes[p.Cohort]=samples=new();
                        decimal? baseline=p.Forecast?.UnconditionalPositiveGrossProbability-
                            (fade.AdverseReturn>0m?1m:0m);
                        samples.Add((fade.GrossReturn.Value,fade.NetReturn.Value,fade.AdverseReturn,
                            other.AdverseReturn,delta*delta,baseline*baseline));
                    }
                }
            }
            if(p.Forecast is not { } f)return;
            var leg=f.Direction==1?lo:sh;
            decimal actual=(priced?leg.AdverseReturn:leg.GrossReturn!.Value)>0?1m:0m;
            scored++;
            if(actual>0)actualPositive++;
            if(f.PositiveGrossProbability>.5m)forecastPositive++;
            grossSum+=leg.GrossReturn!.Value;
            netSum+=leg.NetReturn!.Value;
            brier+=(f.PositiveGrossProbability-actual)*(f.PositiveGrossProbability-actual);
            neutralBrier+=.25m;
            unconditionalBrier+=(f.UnconditionalPositiveGrossProbability-actual)*
                (f.UnconditionalPositiveGrossProbability-actual);
        }
    }
}
