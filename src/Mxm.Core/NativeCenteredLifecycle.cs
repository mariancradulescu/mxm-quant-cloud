namespace Mxm.Core;

// New selection-only estimator. Preserve legacy SCP1 and every frozen result.
// Do not measure dispersion around a cost-capped mean of a different series.
internal static class NativeCenteredLifecycle
{
    // Both estimates already use the same current units and monetary costs.
    // Do not sum overlapping forecasts or assume their errors independent.
    internal static NativeEurPayoff? Corroborate(NativeEurPayoff? empirical,NativeEurPayoff? direct)
        =>empirical is null||direct is null?null:empirical with
        {GrossMeanEur=Math.Min(empirical.GrossMeanEur,direct.GrossMeanEur),
         GrossLowerEur=Math.Min(empirical.GrossLowerEur,direct.GrossLowerEur),
         NetMeanEur=Math.Min(empirical.NetMeanEur,direct.NetMeanEur),
         NetLowerEur=Math.Min(empirical.NetLowerEur,direct.NetLowerEur),
         Cohort=empirical.Cohort+"/CORROBORATED_PAV1_DIRECT_PRICE_PROXY"};

    internal static NativeEurPayoff? Reprice(NativeEurPayoff? normalized,decimal risk,decimal cost,Action<string>? diagnostic=null)
    {
        if(normalized is null||risk<=0m||cost<0m)
        {diagnostic?.Invoke("CENTERED_INSUFFICIENT_SUPPORT");return null;}
        decimal gross=normalized.GrossMeanEur*risk,grossLower=normalized.GrossLowerEur*risk;
        decimal net=Math.Min(normalized.NetMeanEur*risk,gross-cost);
        decimal netLower=Math.Min(normalized.NetLowerEur*risk,grossLower-cost);
        diagnostic?.Invoke(normalized.Cohort!);
        diagnostic?.Invoke(grossLower<=0m?"CENTERED_GROSS_LOWER_NONPOSITIVE":
            netLower<=0m?"CENTERED_NET_LOWER_NONPOSITIVE":"CENTERED_POSITIVE");
        return normalized with {GrossMeanEur=gross,GrossLowerEur=grossLower,NetMeanEur=net,NetLowerEur=netLower,
            NetWorstEur=normalized.NetWorstEur*risk,NetBestEur=normalized.NetBestEur*risk};
    }

    // Predeclared dimensionless bands compare historical execution-cost burden
    // at the actual candidate risk, without reducing its executable fees.
    internal static int CostBand(decimal costRisk)=>costRisk<=.1m?0:costRisk<=.25m?1:costRisk<=.5m?2:3;
    internal static NativeEurPayoff? Estimate(IEnumerable<NativeEurCalibrationOutcome> history,
        string family,int side,NativeEurDecisionContext context,long at,decimal risk,decimal cost,
        int minimumEpisodes,int minimumDays,decimal penalty,bool transfer,Action<string>? diagnostic=null,bool costMatched=false,int halfLifeDays=0)
    {
        if(risk<=0m||cost<0m||minimumEpisodes<minimumDays||minimumDays<2||penalty<0m||halfLifeDays<0)return null;
        int? Regime(NativeEurDecisionContext c)=>c.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1)?.Direction;
        int? FastRegime(NativeEurDecisionContext x)=>x.ClosedStates.SingleOrDefault(s=>s.Timeframe==NativeBarTimeframe.M15)?.Direction;
        int? regime=Regime(context);
        var valid=history.Where(x=>x.AvailableAt<at&&x.ClosedAt<=x.AvailableAt&&x.RiskEur>0m&&
            x.Family==family&&x.Side==side&&x.Context is not null).ToArray();
        bool Supported(NativeEurCalibrationOutcome[] rows)=>rows.Length>=minimumEpisodes&&
            rows.Select(x=>x.ClosedAt/86_400_000L).Distinct().Take(minimumDays).Count()==minimumDays;
        if(costMatched)
        {
            if(context.CostRiskFraction<0m)return null;
            int band=CostBand(context.CostRiskFraction);
            valid=valid.Where(x=>x.Context!.CostRiskFraction>=0m&&CostBand(x.Context.CostRiskFraction)==band).ToArray();
        }
        var local=valid.Where(x=>x.Context!.Symbol==context.Symbol).ToArray();
        var pool=local.Where(x=>Regime(x.Context!)==regime).ToArray();
        string cohort="LOCAL_REGIME";
        if(costMatched)
        {
            int? fast=FastRegime(context);
            var close=pool.Where(x=>FastRegime(x.Context!)==fast).ToArray();
            if(Supported(close)){pool=close;cohort="LOCAL_H1_M15_REGIME";}
        }
        // Hierarchy uses support ONLY. Never abandon a supported losing cohort
        // for a profitable one. No cross-family or cross-direction transfer.
        if(!Supported(pool)&&transfer)
        {
            pool=local;cohort="LOCAL_ALL_REGIMES";
            if(!Supported(pool)&&!string.IsNullOrWhiteSpace(context.AssetClass))
            {
                pool=valid.Where(x=>x.Context!.Symbol!=context.Symbol&&x.Context.AssetClass==context.AssetClass&&
                    Regime(x.Context)==regime).ToArray();
                cohort="CLASS_OTHER_SYMBOLS_REGIME";
                if(pool.Select(x=>x.Context!.Symbol).Distinct().Take(2).Count()<2)pool=Array.Empty<NativeEurCalibrationOutcome>();
            }
        }
        if(!Supported(pool)){diagnostic?.Invoke(costMatched?"COST_CONTEXT_INSUFFICIENT_SUPPORT":"CENTERED_INSUFFICIENT_SUPPORT");return null;}
        if(costMatched)cohort+=":COST_BAND_"+CostBand(context.CostRiskFraction);
        // Equal day weights and equal symbol weights within each day.
        var daily=pool.GroupBy(x=>x.ClosedAt/86_400_000L).Select(day=>
        {
            var symbols=day.GroupBy(x=>x.Context!.Symbol).Select(symbol=>(Gross:symbol.Average(x=>x.GrossEur/x.RiskEur)*risk,
                Net:symbol.Average(x=>x.NetEur/x.RiskEur)*risk,
                Positive:symbol.Average(x=>x.NetEur>0m?1m:0m))).ToArray();
            return (Day:day.Key,Gross:symbols.Average(x=>x.Gross),Net:symbols.Average(x=>x.Net),Positive:symbols.Average(x=>x.Positive));
        }).ToArray();
        // Relative age to newest eligible day preserves a frozen calibration cache.
        // The same causal estimator applies to every family and direction.
        long newest=daily.Max(x=>x.Day);
        var weights=daily.Select(x=>halfLifeDays==0?1m:(decimal)Math.Pow(.5,(newest-x.Day)/(double)halfLifeDays)).ToArray();
        decimal mass=weights.Sum(),squares=weights.Sum(w=>w*w);
        decimal effective=mass*mass/squares;
        if(halfLifeDays>0&&effective<minimumDays)
        {diagnostic?.Invoke("RECENCY_EFFECTIVE_DAYS_INSUFFICIENT");return null;}
        decimal Weighted(IEnumerable<decimal> values)=>values.Zip(weights,(v,w)=>v*w).Sum()/mass;
        decimal gross=halfLifeDays==0?daily.Average(x=>x.Gross):Weighted(daily.Select(x=>x.Gross));
        decimal historicalNet=halfLifeDays==0?daily.Average(x=>x.Net):Weighted(daily.Select(x=>x.Net));
        decimal Lower(decimal mean,IEnumerable<decimal> values)
        {
            if(halfLifeDays==0)return mean-penalty*(decimal)Math.Sqrt(values.Sum(v=>Math.Pow((double)(v-mean),2))/(daily.Length*(daily.Length-1d)));
            decimal variance=Weighted(values.Select(v=>(v-mean)*(v-mean)))*effective/(effective-1m);
            return mean-penalty*(decimal)Math.Sqrt((double)(variance/effective));
        }
        decimal grossLower=Lower(gross,daily.Select(x=>x.Gross));
        decimal historicalLower=Lower(historicalNet,daily.Select(x=>x.Net));
        decimal net=Math.Min(historicalNet,gross-cost),netLower=Math.Min(historicalLower,grossLower-cost);
        if(halfLifeDays>0)cohort+=$"/RECENCY_HALF_LIFE_DAYS:{halfLifeDays}";
        diagnostic?.Invoke("CENTERED_"+cohort);
        diagnostic?.Invoke(grossLower<=0m?"CENTERED_GROSS_LOWER_NONPOSITIVE":
            netLower<=0m?"CENTERED_NET_LOWER_NONPOSITIVE":"CENTERED_POSITIVE");
        return new(pool.Length,daily.Length,gross,grossLower,net,netLower,halfLifeDays==0?daily.Average(x=>x.Positive):Weighted(daily.Select(x=>x.Positive)),
            pool.Min(x=>x.NetEur/x.RiskEur)*risk,pool.Max(x=>x.NetEur/x.RiskEur)*risk)
            {Cohort="CENTERED_"+cohort};
    }
}
