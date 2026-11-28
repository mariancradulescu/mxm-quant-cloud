namespace Mxm.Core;
internal static class NativeDistributionLifecycle
{
    static readonly bool CompactPath=Environment.GetEnvironmentVariable("MXM_ECONOMIC_COMPACT_PATH")=="1";
    internal static double?[] Features(NativeEurDecisionContext c)
    {
        var values=(c.MarketState??Array.Empty<decimal?>()).Select(x=>(double?)x).ToList();
        values.Add((double)c.CostRiskFraction);
        values.Add(Math.Sin(2*Math.PI*c.UtcMinute/1440d));values.Add(Math.Cos(2*Math.PI*c.UtcMinute/1440d));
        values.AddRange((c.RelativeVolatility??new decimal?[7]).Select(x=>x is >0m?(double?)Math.Log((double)x.Value):null));
        return values.ToArray();
    }
    internal static (decimal Mean,decimal Sem,int Count)? Continuation(Ucp1MarketFrame market,long at,int side)
    {
        var w=market.EconomicTransitionWindows?.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1&&x.Ready);
        if(w is null||w.Bars.Length<32||w.Bars.Any(b=>b.CloseAt>=at))return null;
        var bars=w.Bars;var rows=new List<NativePathSample>();
        (double?[] Values,decimal Atr)? Context(int i)
        {
            var b=bars[(i-5)..(i+1)];
            if(b.Zip(b.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt))return null;
            decimal atr=b.Average(x=>x.High-x.Low);if(atr<=0m)return null;
            return (new double?[]{(double)(side*(b[^1].Close-b[^2].Close)/atr),
                (double)(side*(b[^1].Close-b[0].Close)/(5m*atr)),
                Math.Sign(side*(b[^1].Close-b[0].Close)),(double)((b[^1].High-b[^1].Low)/atr)},atr);
        }
        for(int i=5;i<bars.Length-1;i++)
        {
            if(Context(i) is not { } c||bars[i].CloseAt!=bars[i+1].OpenAt)continue;
            var next=bars[i+1];decimal entry=bars[i].Close;
            decimal favorable=(side>0?next.High-entry:entry-next.Low)/c.Atr;
            decimal adverse=(side>0?entry-next.Low:next.High-entry)/c.Atr;
            bool upper=favorable>=1m,lower=adverse>=1m;
            rows.Add(new(market.Symbol,market.OfficialAssetClass,bars[i].CloseAt+1,next.CloseAt+1,c.Values,
                side*(next.Close-entry)/c.Atr,Math.Max(0m,favorable),Math.Max(0m,adverse),upper&&!lower?1m:0m,upper?1m:0m,60m));
        }
        if(Context(bars.Length-1) is not { } current)return null;
        var f=NativeCausalPathDistribution.Estimate(rows,market.Symbol,market.OfficialAssetClass,current.Values,at,
            "CONTEXT",0,24,2);
        return f is null?null:(side*f.Mean*current.Atr,(f.Mean-f.LowerMean)*current.Atr,f.Samples);
    }

    internal static NativeEurPayoff? Estimate(IEnumerable<NativeEurCalibrationOutcome> history,
        string family,int side,NativeEurDecisionContext target,long at,string mode,int minimumSamples,int minimumDays,
        decimal penalty,Action<string>? diagnostic,bool? compactOverride=null)
    {
        using var profile=NativeEconomicProfiler.Measure("eur.path_distribution");
        var valid=history.Where(x=>x.Family==family&&x.Side==side&&x.RiskEur>0m&&x.Context is not null&&
            x.PathEvidence is not null&&x.AvailableAt<at);
        NativePathSample Row(NativeEurCalibrationOutcome x,bool net)
        {
            var p=x.PathEvidence!;
            return new(x.Context!.Symbol,x.Context.AssetClass,x.DecisionAt??(x.ClosedAt-1),x.AvailableAt,Features(x.Context),
                (net?x.NetEur:x.GrossEur)/x.RiskEur,p.FavorableR,p.AdverseR,p.TargetFirstLower,p.TargetFirstUpper,p.DurationMinutes);
        }
        var features=Features(target);
        NativePathDistributionForecast? gross,net;
        NativePathDistributionForecast? Estimate(IEnumerable<NativePathSample> rows)=>
            NativeCausalPathDistribution.Estimate(rows,target.Symbol,target.AssetClass,features,at,mode,
                mode=="POOLED"?0:28,minimumSamples,minimumDays,penalty);
        if(compactOverride??CompactPath)
        {
            // The original estimator applies these predicates and stable
            // newest-first Take(1024) before weighting. Filter and cap
            // before materializing expensive feature vectors, once for
            // both monetary outcomes. The estimator still revalidates.
            int Length(NativeEurDecisionContext c)=>(c.MarketState?.Length??0)+3+(c.RelativeVolatility?.Length??7);
            var pairs=valid.Where(x=>
            {
                var c=x.Context!;var p=x.PathEvidence!;
                return (x.DecisionAt??(x.ClosedAt-1))<x.AvailableAt&&Length(c)==features.Length&&
                    p.FavorableR>=0m&&p.AdverseR>=0m&&p.TargetFirstLower>=0m&&
                    p.TargetFirstLower<=p.TargetFirstUpper&&p.TargetFirstUpper<=1m&&p.DurationMinutes>0m&&
                    (c.Symbol==target.Symbol||mode!="LOCAL"&&target.AssetClass is not null&&c.AssetClass==target.AssetClass);
            }).OrderByDescending(x=>x.AvailableAt).Take(1024).Select(x=>
            {
                var g=Row(x,false);
                return (Gross:g,Net:g with {Outcome=x.NetEur/x.RiskEur});
            }).ToArray();
            gross=Estimate(pairs.Select(x=>x.Gross));net=Estimate(pairs.Select(x=>x.Net));
        }
        else
        {
            var rows=valid.ToArray();
            gross=Estimate(rows.Select(x=>Row(x,false)));net=Estimate(rows.Select(x=>Row(x,true)));
        }
        diagnostic?.Invoke(gross is null||net is null?"PATH_DISTRIBUTION_SUPPORT_MISSING":"PATH_DISTRIBUTION_"+mode);
        if(gross is null||net is null)return null;
        return new(gross.Samples,gross.Days,gross.Mean,gross.LowerMean,net.Mean,net.LowerMean,
            net.PositiveProbability,net.MinimumOutcome,net.MaximumOutcome)
            {Cohort="PATH_DISTRIBUTION_"+mode,EffectiveObservationDays=gross.EffectiveDays,
                LatestEligibleObservationAt=gross.LatestAvailableAt,PathDistribution=net,
                ExpectedShortfallEur=net.ExpectedShortfall,GrossExpectedShortfallEur=gross.ExpectedShortfall};
    }
}
public sealed record NativeEconomicPathEvidence(decimal FavorableR,decimal AdverseR,decimal TargetFirstLower,
    decimal TargetFirstUpper,decimal DurationMinutes);
