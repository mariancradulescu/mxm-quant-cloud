namespace Mxm.Core;
internal static class NativeDistributionLifecycle
{
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
        decimal penalty,Action<string>? diagnostic)
    {
        var valid=history.Where(x=>x.Family==family&&x.Side==side&&x.RiskEur>0m&&x.Context is not null&&
            x.PathEvidence is not null&&x.AvailableAt<at).ToArray();
        NativePathSample Row(NativeEurCalibrationOutcome x,bool net)
        {
            var p=x.PathEvidence!;
            return new(x.Context!.Symbol,x.Context.AssetClass,x.DecisionAt??(x.ClosedAt-1),x.AvailableAt,Features(x.Context),
                (net?x.NetEur:x.GrossEur)/x.RiskEur,p.FavorableR,p.AdverseR,p.TargetFirstLower,p.TargetFirstUpper,p.DurationMinutes);
        }
        var features=Features(target);
        var gross=NativeCausalPathDistribution.Estimate(valid.Select(x=>Row(x,false)),target.Symbol,target.AssetClass,
            features,at,mode,mode=="POOLED"?0:28,minimumSamples,minimumDays,penalty);
        var net=NativeCausalPathDistribution.Estimate(valid.Select(x=>Row(x,true)),target.Symbol,target.AssetClass,
            features,at,mode,mode=="POOLED"?0:28,minimumSamples,minimumDays,penalty);
        diagnostic?.Invoke(gross is null||net is null?"PATH_DISTRIBUTION_SUPPORT_MISSING":"PATH_DISTRIBUTION_"+mode);
        if(gross is null||net is null)return null;
        return new(gross.Samples,gross.Days,gross.Mean,gross.LowerMean,net.Mean,net.LowerMean,
            net.PositiveProbability,net.ExpectedShortfall,net.Quantiles[^1])
            {Cohort="PATH_DISTRIBUTION_"+mode,EffectiveObservationDays=gross.EffectiveDays,
                LatestEligibleObservationAt=gross.LatestAvailableAt,PathDistribution=net};
    }
}
public sealed record NativeEconomicPathEvidence(decimal FavorableR,decimal AdverseR,decimal TargetFirstLower,
    decimal TargetFirstUpper,decimal DurationMinutes);
