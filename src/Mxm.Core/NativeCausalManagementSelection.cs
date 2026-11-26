using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public static class NativeCausalManagementSelection
{
    public sealed record Choice(string Management,int Pairs,int Days,decimal? MeanDeltaR,decimal? LowerDeltaR);

    // Compare the same entry, symbol, family, direction, initial H1 regime and
    // admission risk under both management rules. Both outcomes must have
    // matured before this entry. Unequal, duplicate or unpaired labels grant
    // no switching evidence. This is development evidence, not certification.
    public static Choice Select(IEnumerable<NativeEurCalibrationOutcome> history,string family,int side,
        NativeEurDecisionContext context,long at,int minimumPairs,int minimumDays,decimal penalty)
    {
        const string baseline="TRANSITION_VALUE";
        var fallback=new Choice(baseline,0,0,null,null);
        if(minimumPairs<2||minimumDays<2||penalty<0m)return fallback;
        int? regime=context.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1)?.Direction;
        var rows=history.Where(x=>x.Family==family&&x.Side==side&&x.Context?.Symbol==context.Symbol&&
            x.Context.ClosedStates.SingleOrDefault(s=>s.Timeframe==NativeBarTimeframe.H1)?.Direction==regime&&
            x.DecisionAt is >0L&&x.DecisionAt<x.ClosedAt&&x.AvailableAt>=x.ClosedAt&&x.AvailableAt<at&&x.RiskEur>0m&&
            x.EconomicManagement is baseline or NativeEconomicMechanisms.MonetaryReduce);
        var pairs=rows.GroupBy(x=>x.DecisionAt!.Value).Select(g=>
        {
            var a=g.Where(x=>x.EconomicManagement==baseline).ToArray();
            var b=g.Where(x=>x.EconomicManagement==NativeEconomicMechanisms.MonetaryReduce).ToArray();
            return a.Length==1&&b.Length==1&&a[0].RiskEur==b[0].RiskEur
                ?new {Day=g.Key/86_400_000L,Delta=(b[0].NetEur-a[0].NetEur)/a[0].RiskEur}:null;
        }).Where(x=>x is not null).Select(x=>x!).ToArray();
        var days=pairs.GroupBy(x=>x.Day).Select(g=>g.Average(x=>x.Delta)).ToArray();
        if(pairs.Length<minimumPairs||days.Length<minimumDays)
            return fallback with {Pairs=pairs.Length,Days=days.Length};
        decimal mean=days.Average();
        decimal lower=mean-penalty*(decimal)Math.Sqrt(days.Sum(x=>Math.Pow((double)(x-mean),2))/
            (days.Length*(days.Length-1d)));
        return new(lower>0m?NativeEconomicMechanisms.MonetaryReduce:baseline,pairs.Length,days.Length,mean,lower);
    }
}
