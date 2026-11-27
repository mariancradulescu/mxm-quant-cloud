namespace Mxm.Core;

public sealed partial class NativeUnifiedPortfolioEngine
{
    sealed class BoundaryTotals
    {
        public long Forecasts,Samples;
        public int MinimumSupport=int.MaxValue,MaximumSupport,MinimumDays=int.MaxValue,MaximumDays;
        public decimal Stops,Targets,Ambiguous;
        public long From=long.MaxValue,Through,Horizon;
    }
    readonly Dictionary<string,BoundaryTotals> boundaryTotals=new(StringComparer.Ordinal);

    NativeEconomicMechanisms.BoundaryEstimate? BoundaryForecast(Ucp1MarketFrame market,long at,
        int side,decimal now,decimal stop,decimal target,NativeEurDevelopmentProfile profile,string stage)
    {
        var forecast=NativeEconomicMechanisms.BoundaryDistributionEur(market,at,side,now,stop,target,
            profile.EconomicManagementTimeframe??profile.EconomicGeometryTimeframe,
            profile.BoundaryMinimumSamples==0?8:profile.BoundaryMinimumSamples,
            profile.BoundaryMinimumDays==0?1:profile.BoundaryMinimumDays,!profile.UseUnscaledBoundaryPaths);
        if(forecast is null){Count("BOUNDARY_"+stage+"_INSUFFICIENT_CAUSAL_SUPPORT");return null;}
        string key=stage+"/"+market.Symbol;
        if(!boundaryTotals.TryGetValue(key,out var t))boundaryTotals.Add(key,t=new());
        t.Forecasts++;t.Samples+=forecast.Count;
        t.MinimumSupport=Math.Min(t.MinimumSupport,forecast.Count);t.MaximumSupport=Math.Max(t.MaximumSupport,forecast.Count);
        t.MinimumDays=Math.Min(t.MinimumDays,forecast.Days);t.MaximumDays=Math.Max(t.MaximumDays,forecast.Days);
        t.Stops+=forecast.StopProbability*forecast.Count;t.Targets+=forecast.TargetProbability*forecast.Count;
        t.Ambiguous+=forecast.AmbiguousProbability*forecast.Count;
        t.From=Math.Min(t.From,forecast.From);t.Through=Math.Max(t.Through,forecast.Through);t.Horizon=forecast.HorizonMs;
        return forecast;
    }

    public object BoundaryForecastDiagnostics()=>boundaryTotals.OrderBy(x=>x.Key,StringComparer.Ordinal).Select(x=>new
    {
        Scope=x.Key,x.Value.Forecasts,x.Value.Samples,x.Value.MinimumSupport,x.Value.MaximumSupport,
        x.Value.MinimumDays,x.Value.MaximumDays,x.Value.From,x.Value.Through,HorizonMs=x.Value.Horizon,
        StopProbability=x.Value.Stops/x.Value.Samples,TargetProbability=x.Value.Targets/x.Value.Samples,
        BothBoundariesProbability=x.Value.Ambiguous/x.Value.Samples,
        RepeatedForecastSamplesAreIndependent=false,HistoricalFillCertified=false,EconomicQualification=false
    }).ToArray();
}
