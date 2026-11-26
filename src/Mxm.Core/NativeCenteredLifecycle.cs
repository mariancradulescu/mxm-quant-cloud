namespace Mxm.Core;

// New selection-only estimator. Preserve legacy SCP1 and every frozen result.
// Do not measure dispersion around a cost-capped mean of a different series.
internal static class NativeCenteredLifecycle
{
    internal static NativeEurPayoff? Estimate(IEnumerable<NativeEurCalibrationOutcome> history,
        string family,int side,NativeEurDecisionContext context,long at,decimal risk,decimal cost,
        int minimumEpisodes,int minimumDays,decimal penalty,bool transfer,Action<string>? diagnostic=null)
    {
        if(risk<=0m||cost<0m||minimumEpisodes<minimumDays||minimumDays<2||penalty<0m)return null;
        int? Regime(NativeEurDecisionContext c)=>c.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1)?.Direction;
        int? regime=Regime(context);
        var valid=history.Where(x=>x.AvailableAt<at&&x.ClosedAt<=x.AvailableAt&&x.RiskEur>0m&&
            x.Family==family&&x.Side==side&&x.Context is not null).ToArray();
        bool Supported(NativeEurCalibrationOutcome[] rows)=>rows.Length>=minimumEpisodes&&
            rows.Select(x=>x.ClosedAt/86_400_000L).Distinct().Take(minimumDays).Count()==minimumDays;
        var local=valid.Where(x=>x.Context!.Symbol==context.Symbol).ToArray();
        var pool=local.Where(x=>Regime(x.Context!)==regime).ToArray();
        string cohort="LOCAL_REGIME";
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
        if(!Supported(pool)){diagnostic?.Invoke("CENTERED_INSUFFICIENT_SUPPORT");return null;}
        // Equal day weights and equal symbol weights within each day.
        var daily=pool.GroupBy(x=>x.ClosedAt/86_400_000L).Select(day=>
        {
            var symbols=day.GroupBy(x=>x.Context!.Symbol).Select(symbol=>(Gross:symbol.Average(x=>x.GrossEur/x.RiskEur)*risk,
                Net:symbol.Average(x=>x.NetEur/x.RiskEur)*risk,
                Positive:symbol.Average(x=>x.NetEur>0m?1m:0m))).ToArray();
            return (Gross:symbols.Average(x=>x.Gross),Net:symbols.Average(x=>x.Net),Positive:symbols.Average(x=>x.Positive));
        }).ToArray();
        decimal gross=daily.Average(x=>x.Gross),historicalNet=daily.Average(x=>x.Net);
        decimal Lower(decimal mean,IEnumerable<decimal> values)
            =>mean-penalty*(decimal)Math.Sqrt(values.Sum(v=>Math.Pow((double)(v-mean),2))/(daily.Length*(daily.Length-1d)));
        decimal grossLower=Lower(gross,daily.Select(x=>x.Gross));
        decimal historicalLower=Lower(historicalNet,daily.Select(x=>x.Net));
        decimal net=Math.Min(historicalNet,gross-cost),netLower=Math.Min(historicalLower,grossLower-cost);
        diagnostic?.Invoke("CENTERED_"+cohort);
        diagnostic?.Invoke(grossLower<=0m?"CENTERED_GROSS_LOWER_NONPOSITIVE":
            netLower<=0m?"CENTERED_NET_LOWER_NONPOSITIVE":"CENTERED_POSITIVE");
        return new(pool.Length,daily.Length,gross,grossLower,net,netLower,daily.Average(x=>x.Positive),
            pool.Min(x=>x.NetEur/x.RiskEur)*risk,pool.Max(x=>x.NetEur/x.RiskEur)*risk)
            {Cohort="CENTERED_"+cohort};
    }
}
