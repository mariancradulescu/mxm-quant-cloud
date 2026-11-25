using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Distinct from the confidence bound on expected monetary value.
// Intervals are empirical residual intervals, not a guaranteed loss limit.
public sealed record NativeEurPredictiveEvidence(string Scope,int ValidationDays,int ValidationLabels,
    decimal EffectiveDays,decimal GrossMeanStandardErrorEur,decimal NetMeanStandardErrorEur,
    decimal NetIndividualP10Eur,decimal NetIndividualP90Eur,decimal ConditionalNetPositiveFraction,
    decimal GrossCostPositiveFraction,decimal JointPositiveLowerBound);

internal sealed partial class NativeEurAdaptiveEstimator
{
    sealed record RegimeCuts(double[] Volatility,double[] Expansion,double[] TrendMagnitude);
    sealed record WeightedError(long Day,double Gross,double Net,double Weight);
    sealed record ScopedErrors(ErrorDistribution Base,Dictionary<string,ErrorDistribution> Cells);
    readonly Dictionary<(string Family,int Side),ScopedErrors> predictiveErrors=new();
    ErrorDistribution? pooledErrors;
    long[] selectionDates=Array.Empty<long>(),errorDates=Array.Empty<long>();
    bool economicSelection;

    static double[] Terciles(IEnumerable<double?> values)
    {
        var sorted=values.OfType<double>().Where(double.IsFinite).OrderBy(x=>x).ToArray();
        if(sorted.Length==0)return Array.Empty<double>();
        return new[]{sorted[(sorted.Length-1)/3],sorted[2*(sorted.Length-1)/3]};
    }

    static double? Volatility(NativeEurDecisionContext c)
        =>c.RelativeVolatility is {Length:7} v&&v[4] is >0m?Math.Log((double)v[4]!.Value):null;
    static double? Expansion(NativeEurDecisionContext c)=>(double?)c.MarketState![9];
    static double? TrendMagnitude(NativeEurDecisionContext c)
        =>c.MarketState![8] is decimal v?Math.Abs((double)v):null;
    static RegimeCuts FitRegime(IEnumerable<NativeEurDecisionContext> rows)
    {
        var contexts=rows.ToArray();
        return new(Terciles(contexts.Select(Volatility)),Terciles(contexts.Select(Expansion)),
            Terciles(contexts.Select(TrendMagnitude)));
    }
    static string Bucket(double? value,double[] cuts)
        =>value is not double v||cuts.Length!=2?"NA":v<cuts[0]?"LOW":v>cuts[1]?"HIGH":"MID";
    static string PredictiveRegime(NativeEurDecisionContext c,RegimeCuts cuts)
        =>FormattableString.Invariant($"H1:{(c.MarketState![8] is decimal m?Math.Sign(m):2)}/{Bucket(TrendMagnitude(c),cuts.TrendMagnitude)}/{Bucket(Volatility(c),cuts.Volatility)}/{Bucket(Expansion(c),cuts.Expansion)}");

    // Same causal forecasts are scored for each candidate, including the cash
    // decision for unsupported rows. The last dates are reserved for error
    // calibration; they do not participate in candidate selection.
    static NativeEurAdaptiveEstimator FitPredictive(NativeEurCalibration calibration,bool extended,bool economic)
    {
        using var profile=NativeEconomicProfiler.Measure("eur.predictive_fit");
        if(!extended)throw new ArgumentException("EUR_PREDICTIVE_REQUIRES_EXTENDED");
        var rows=calibration.Outcomes.Where(o=>o.AvailableAt<=calibration.ObservationThrough&&
                o.DecisionAt.HasValue&&o.Context?.MarketState is {Length:16})
            .Select(o=>new Row(o,o.Context!,o.DecisionAt!.Value/Day,Values(o.Context!,true,true))).ToArray();
        var dates=rows.Select(x=>x.Day).Distinct().OrderBy(x=>x).Skip(2).TakeLast(12).ToArray();
        int reserved=Math.Min(dates.Length,Math.Max(2,dates.Length/3));
        var selection=dates.Take(dates.Length-reserved).ToArray();
        var errorDays=dates.Skip(dates.Length-reserved).ToArray();
        // A small structured grid: half-life, ridge, transfer strength and
        // slow-frame weights. The last two are coupled in this first search.
        var grid=(from half in new[]{0,4,12}
                  from ridge in new[]{.7,2.0}
                  from prior in new[]{3d,8d}
                  select new EurEstimatorCandidate(FormattableString.Invariant($"V2_H{half}_R{ridge}_P{prior}"),
                      half,ridge,prior,prior==3d?.7:1.4,2,8){Predictive=true}).ToArray();

        Validation[] Forward(EurEstimatorCandidate p,long[] clocks)
        {
            var result=new List<Validation>();
            foreach(long day in clocks)
            {
                long cutoff=day*Day;
                var models=FitGroups(rows.Where(x=>x.Label.AvailableAt<cutoff).ToArray(),cutoff,p,true);
                foreach(var row in rows.Where(x=>x.Day==day))
                {
                    bool supported=models.TryGetValue(row.Group,out var model);
                    var pred=supported?Estimate(model!,row.Context,row.Features,p):(0d,0d);
                    result.Add(new(row,row.Gross-pred.Item1,row.Net-pred.Item2,supported));
                }
            }
            return result.ToArray();
        }

        double? DayScore(Validation[] validation,Func<Validation,double> value)
        {
            var daily=validation.GroupBy(x=>x.Row.Day).Select(day=>
                day.GroupBy(x=>x.Row.Context.Symbol,StringComparer.Ordinal).Average(symbol=>symbol.Average(value))).ToArray();
            return daily.Length==0?null:daily.Average();
        }

        var scores=grid.Select(p=>
        {
            var validation=Forward(p,selection);
            var loss=DayScore(validation,x=>(x.GrossError*x.GrossError+2*x.NetError*x.NetError)/3);
            // Value of the sign decision against CASH, in reserved-risk units.
            // This is a selection proxy, not a funded common-book return.
            var utility=DayScore(validation,x=>x.Supported&&x.Row.Gross-x.GrossError>0&&
                x.Row.Net-x.NetError>0?x.Row.Net:0);
            return (Parameters:p,Score:new EurEstimatorScore(p.Id,selection.Length,validation.Length,loss)
                {EconomicUtility=utility});
        }).ToArray();
        var winner=economic?scores.OrderByDescending(x=>x.Score.EconomicUtility??double.NegativeInfinity)
            .ThenBy(x=>x.Score.Loss??double.PositiveInfinity).First():
            scores.OrderBy(x=>x.Score.Loss??double.PositiveInfinity).First();
        var fitted=FitGroups(rows,calibration.ObservationThrough,winner.Parameters,true);
        var output=new NativeEurAdaptiveEstimator(fitted,winner.Parameters,calibration.ObservationThrough,
            scores.Select(x=>x.Score).ToArray())
            {selectionDates=selection,errorDates=errorDays,economicSelection=economic};
        var held=Forward(winner.Parameters,errorDays).Where(x=>x.Supported).ToArray();
        var pooled=Weighted(held,calibration.ObservationThrough/Day,winner.Parameters.HalfLifeDays);
        if(pooled.Select(x=>x.Day).Distinct().Count()>=2)
            output.pooledErrors=new ErrorDistribution(pooled);
        foreach(var group in held.GroupBy(x=>x.Row.Group))
        {
            if(!fitted.TryGetValue(group.Key,out var model))continue;
            var groupWeights=Weighted(group,calibration.ObservationThrough/Day,winner.Parameters.HalfLifeDays);
            if(groupWeights.Select(x=>x.Day).Distinct().Count()<2)continue;
            var baseline=new ErrorDistribution(groupWeights);
            var cells=new Dictionary<string,ErrorDistribution>(StringComparer.Ordinal);
            foreach(var cell in group.SelectMany(e=>ScopeKeys(e.Row.Context,true,model.Scale.Regime)
                    .Select(k=>(Key:k,Error:e))).GroupBy(x=>x.Key,StringComparer.Ordinal))
            {
                var local=Weighted(cell.Select(x=>x.Error),calibration.ObservationThrough/Day,winner.Parameters.HalfLifeDays);
                int days=local.Select(x=>x.Day).Distinct().Count();
                if(days<2)continue;
                double blend=days/(days+winner.Parameters.ScopePriorDays);
                // Combine weights of overlapping residuals at the day level;
                // they are not counted as independent replications.
                cells.Add(cell.Key,new ErrorDistribution(Normalized(groupWeights,1-blend)
                    .Concat(Normalized(local,blend)).ToArray(),days,local.Length));
            }
            output.predictiveErrors.Add(group.Key,new ScopedErrors(baseline,cells));
        }
        return output;
    }

    static WeightedError[] Weighted(IEnumerable<Validation> errors,long through,int halfLife)
    {
        var result=new List<WeightedError>();
        foreach(var day in errors.GroupBy(e=>e.Row.Day))
        {
            double age=halfLife==0?1:Math.Pow(.5,Math.Max(0,through-day.Key)/(double)halfLife);
            var symbols=day.GroupBy(e=>e.Row.Context.Symbol,StringComparer.Ordinal).ToArray();
            foreach(var symbol in symbols)
            {
                double weight=age/(symbols.Length*(double)symbol.Count());
                foreach(var e in symbol)result.Add(new(day.Key,e.GrossError,e.NetError,weight));
            }
        }
        return result.ToArray();
    }

    static IEnumerable<WeightedError> Normalized(WeightedError[] rows,double mass)
    {
        double sum=rows.Sum(x=>x.Weight);
        return rows.Select(x=>x with {Weight=x.Weight*mass/sum});
    }

    sealed class Marginal
    {
        readonly double[] values,cumulative;
        public double Mean { get; }
        public double Minimum=>values[0];
        public double Maximum=>values[^1];
        public Marginal(WeightedError[] rows,Func<WeightedError,double> value)
        {
            var ordered=rows.Select(x=>(Value:value(x),x.Weight)).OrderBy(x=>x.Value).ToArray();
            double mass=ordered.Sum(x=>x.Weight);
            values=ordered.Select(x=>x.Value).ToArray();
            cumulative=new double[values.Length];
            double running=0;
            for(int i=0;i<ordered.Length;i++){running+=ordered[i].Weight/mass;cumulative[i]=running;}
            cumulative[^1]=1;
            Mean=ordered.Sum(x=>x.Value*x.Weight)/mass;
        }
        public double Quantile(double q)
        {
            int lo=0,hi=values.Length-1;
            while(lo<hi){int mid=lo+(hi-lo)/2;if(cumulative[mid]<q)lo=mid+1;else hi=mid;}
            return values[lo];
        }
        public double Tail(double threshold)
        {
            int lo=0,hi=values.Length;
            while(lo<hi){int mid=lo+(hi-lo)/2;if(values[mid]<=threshold)lo=mid+1;else hi=mid;}
            return lo==0?1:Math.Max(0,1-cumulative[lo-1]);
        }
    }

    sealed class ErrorDistribution
    {
        public int Days { get; }
        public int Labels { get; }
        public double EffectiveDays { get; }
        public double GrossSem { get; }
        public double NetSem { get; }
        public Marginal Gross { get; }
        public Marginal Net { get; }
        public ErrorDistribution(WeightedError[] rows,int? scopeDays=null,int? scopeLabels=null)
        {
            double total=rows.Sum(x=>x.Weight);
            var day=rows.GroupBy(x=>x.Day).Select(g=>
            {
                double w=g.Sum(x=>x.Weight);
                return (Weight:w/total,Gross:g.Sum(x=>x.Gross*x.Weight)/w,Net:g.Sum(x=>x.Net*x.Weight)/w);
            }).ToArray();
            double weightSquares=day.Sum(x=>x.Weight*x.Weight);
            EffectiveDays=1/weightSquares;
            Days=scopeDays??day.Length;
            Labels=scopeLabels??rows.Length;
            Gross=new Marginal(rows,x=>x.Gross);
            Net=new Marginal(rows,x=>x.Net);
            // Mean uncertainty from clustered day means, separate from individual dispersion.
            double Sem(Func<(double Weight,double Gross,double Net),double> value,double mean)
                =>weightSquares<1?Math.Sqrt(day.Sum(x=>x.Weight*Math.Pow(value(x)-mean,2))*weightSquares/(1-weightSquares)):Math.Abs(mean);
            GrossSem=Sem(x=>x.Gross,Gross.Mean);
            NetSem=Sem(x=>x.Net,Net.Mean);
        }
    }

    NativeEurPayoff? PredictivePayoff(string family,int side,GroupModel model,NativeEurDecisionContext context,
        decimal risk,decimal cost)
    {
        if(risk<=0)return null;
        string scope="POOLED_OUT_OF_TIME";
        ErrorDistribution? error=pooledErrors;
        if(predictiveErrors.TryGetValue((family,side),out var cells))
        {
            error=cells.Base;scope="FAMILY_DIRECTION_OUT_OF_TIME";
            foreach(var key in ScopeKeys(context,true,model.Scale.Regime).Reverse())
                if(cells.Cells.TryGetValue(key,out var cell))
                {error=cell;scope=key;break;}
        }
        if(error is null)return null; // never substitute training residuals
        var (g,n)=Estimate(model,context,Values(context,true,true),selected);
        double grossMean=g+error.Gross.Mean,netMean=n+error.Net.Mean;
        decimal gross=(decimal)grossMean*risk;
        decimal net=Math.Min((decimal)netMean*risk,gross-cost);
        decimal grossLower=(decimal)(grossMean-1.645*error.GrossSem)*risk;
        decimal netLower=Math.Min((decimal)(netMean-1.645*error.NetSem)*risk,grossLower-cost);
        double netPositive=error.Net.Tail(-n),grossPositive=error.Gross.Tail((double)(cost/risk)-g);
        // Without a joint dependence model, the Frechet lower bound is valid
        // for the two empirical marginal probability estimates.
        double joint=Math.Max(0,netPositive+grossPositive-1);
        return new NativeEurPayoff(model.Labels,model.Days,gross,grossLower,net,netLower,(decimal)joint,
            Math.Min((decimal)(n+error.Net.Minimum)*risk,(decimal)(g+error.Gross.Minimum)*risk-cost),
            Math.Min((decimal)(n+error.Net.Maximum)*risk,(decimal)(g+error.Gross.Maximum)*risk-cost))
        {Cohort=selected.Id,PredictiveEvidence=new(scope,error.Days,error.Labels,(decimal)error.EffectiveDays,
            (decimal)error.GrossSem*risk,(decimal)error.NetSem*risk,
            (decimal)(n+error.Net.Quantile(.1))*risk,(decimal)(n+error.Net.Quantile(.9))*risk,
            (decimal)netPositive,(decimal)grossPositive,(decimal)joint)};
    }

    object PredictiveReceipt()=>new
    {
        Selected=selected,ObservationThrough=fittedThrough,Grid=scores,
        Objective=economicSelection?"DAY_SYMBOL_SIGN_DECISION_NET_UTILITY":"DAY_SYMBOL_PREDICTION_LOSS",
        SelectionDays=selectionDates,ResidualCalibrationDays=errorDates,
        PooledValidationDays=pooledErrors?.Days??0,PooledValidationLabels=pooledErrors?.Labels??0,
        Groups=groups.Select(x=>new {x.Key.Family,x.Key.Side,x.Value.Days,x.Value.Labels,
            Regime=x.Value.Scale.Regime,ScopeCells=x.Value.Scopes.Count,
            ErrorCells=predictiveErrors.TryGetValue(x.Key,out var e)?e.Cells.Count:0,
            ValidationDays=e?.Base.Days??0,ValidationLabels=e?.Base.Labels??0}).ToArray()
    };
}
