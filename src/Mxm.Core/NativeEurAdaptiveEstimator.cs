using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

internal sealed record EurEstimatorCandidate(string Id,int HalfLifeDays,double Ridge,double ScopePriorDays,
    double SlowFrameWeight,int MinimumDays,int MinimumLabels)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool Predictive { get; init; }
}
internal sealed record EurEstimatorScore(string Id,int ValidationDays,int Labels,double? Loss)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public double? EconomicUtility { get; init; }
}

internal sealed partial class NativeEurAdaptiveEstimator
{
    const long Day=86_400_000L;
    static readonly int[] Local={2,3,4,5};
    static readonly int[] Extended=Enumerable.Range(0,16).ToArray();
    static readonly EurEstimatorCandidate[] Grid=
    {
        new("POOLED",0,.7,0,1,2,8),
        new("SHRUNK_TRANSFER",12,.7,5,1,2,8),
        new("RECENT_TRANSFER",4,1.2,3,.7,2,12),
        new("SLOW_CONTEXT",16,1.4,8,1.6,4,16)
    };

    sealed record Row(NativeEurCalibrationOutcome Label,NativeEurDecisionContext Context,long Day,double?[] Features)
    {
        public double Gross => (double)(Label.GrossEur/Label.RiskEur);
        public double Net => (double)(Label.NetEur/Label.RiskEur);
        public (string Family,int Side) Group => (Label.Family,Label.Side);
    }
    sealed record Normalization(double[] Mean,double[] StandardDeviation,bool Extended,RegimeCuts? Regime=null);
    sealed record ScopeResidual(int Days,double Gross,double Net);
    sealed record ErrorBand(double GrossBias,double GrossWidth,double NetBias,double NetWidth);
    sealed record GroupModel(Normalization Scale,double[] Gross,double[] Net,Dictionary<string,ScopeResidual> Scopes,
        int Days,int Labels,double PositiveFraction,decimal MinimumNetR,decimal MaximumNetR,ErrorBand Errors);
    sealed record Validation(Row Row,double GrossError,double NetError,bool Supported=true);

    readonly Dictionary<(string Family,int Side),GroupModel> groups;
    readonly EurEstimatorCandidate selected;
    readonly long fittedThrough;
    readonly EurEstimatorScore[] scores;

    NativeEurAdaptiveEstimator(Dictionary<(string Family,int Side),GroupModel> groups,EurEstimatorCandidate selected,
        long fittedThrough,EurEstimatorScore[] scores)
    {
        this.groups=groups;
        this.selected=selected;
        this.fittedThrough=fittedThrough;
        this.scores=scores;
    }

    internal object Receipt()=>selected.Predictive?PredictiveReceipt():LegacyReceipt();

    object LegacyReceipt()=>new
    {
        Selected=selected,ObservationThrough=fittedThrough,Grid=scores,
        Groups=groups.Select(x=>new {x.Key.Family,x.Key.Side,x.Value.Days,x.Value.Labels,
            ScopeCells=x.Value.Scopes.Count,x.Value.Errors.GrossBias,x.Value.Errors.GrossWidth,
            x.Value.Errors.NetBias,x.Value.Errors.NetWidth}).ToArray()
    };

    static double?[] Values(NativeEurDecisionContext context,bool extended,bool predictive=false)
    {
        var state=context.MarketState!;
        var values=(extended?Extended:Local).Select(i=>(double?)state[i]).ToList();
        if(extended)
        {
            double phase=2*Math.PI*context.UtcMinute/1440d;
            values.Add(Math.Sin(phase));
            values.Add(Math.Cos(phase));
        }
        if(predictive&&extended)
            for(int i=0;i<7;i++)
            {
                var relative=context.RelativeVolatility is {Length:7} v?v[i]:null;
                values.Add(relative is >0m?Math.Log((double)relative.Value):null);
            }
        decimal cost=Math.Max(0m,context.CostRiskFraction);
        values.Add((double)(cost/(1m+cost)));
        return values.ToArray();
    }

    static string Regime(NativeEurDecisionContext context)
    {
        var state=context.MarketState!;
        int trend=state[8] is decimal move?Math.Sign(move):2;
        int volatility=state[9] is decimal range?Math.Sign(range):2;
        return FormattableString.Invariant($"H1:{trend}/{volatility}");
    }

    static IEnumerable<string> ScopeKeys(NativeEurDecisionContext context,bool extended,RegimeCuts? cuts=null)
    {
        if(context.AssetClass is { } asset)yield return "CLASS:"+asset;
        yield return "SYMBOL:"+context.Symbol;
        if(extended)
        {
            string regime=cuts is null?Regime(context):PredictiveRegime(context,cuts);
            yield return "REGIME:"+regime;
            yield return "SYMBOL_REGIME:"+context.Symbol+":"+regime;
        }
    }

    static double[] Design(double?[] values,Normalization scale,EurEstimatorCandidate p)
    {
        var x=new double[1+2*values.Length];
        x[0]=1;
        for(int i=0;i<values.Length;i++)
        {
            double weight=scale.Extended&&i>=8&&i<14?p.SlowFrameWeight:1;
            if(values[i] is double v)
                x[1+2*i]=weight*NativeContextValueResearch.Clip((v-scale.Mean[i])/scale.StandardDeviation[i]);
            else x[2+2*i]=weight;
        }
        return x;
    }

    // Within-day symbols and their overlapping opportunities share their
    // day's weight. Every label contributes and no observation is treated as an independent day.
    static IEnumerable<(Row Row,double Weight)> Weights(IEnumerable<Row> rows,long throughDay,int halfLife)
    {
        foreach(var day in rows.GroupBy(x=>x.Day))
        {
            double ageWeight=halfLife==0?1:Math.Pow(.5,Math.Max(0,throughDay-day.Key)/(double)halfLife);
            var symbols=day.GroupBy(x=>x.Context.Symbol,StringComparer.Ordinal).ToArray();
            foreach(var symbol in symbols)
            {
                double w=ageWeight/(symbols.Length*(double)symbol.Count());
                foreach(var row in symbol)yield return (row,w);
            }
        }
    }

    static (double Gross,double Net) Estimate(GroupModel fitted,NativeEurDecisionContext context,
        double?[] values,EurEstimatorCandidate p)
    {
        var x=Design(values,fitted.Scale,p);
        double gross=0,net=0;
        for(int i=0;i<x.Length;i++)
        {
            gross+=x[i]*fitted.Gross[i];
            net+=x[i]*fitted.Net[i];
        }
        if(p.ScopePriorDays==0)return (gross,net);
        double sw=p.ScopePriorDays,dg=0,dn=0;
        foreach(var key in ScopeKeys(context,fitted.Scale.Extended,fitted.Scale.Regime))
        {
            if(!fitted.Scopes.TryGetValue(key,out var entry))continue;
            // Each specificity level contributes a shrunken transfer correction.
            // A thin symbol/regime cell cannot override representative pooled evidence.
            double w=Math.Sqrt(entry.Days);
            sw+=w;
            dg+=w*entry.Gross;
            dn+=w*entry.Net;
        }
        return (gross+dg/sw,net+dn/sw);
    }

    static ErrorBand Uncertainty(Validation[] errors)
    {
        var days=errors.GroupBy(x=>x.Row.Day).Select(day=>
        {
            var symbols=day.GroupBy(e=>e.Row.Context.Symbol,StringComparer.Ordinal).ToArray();
            return (Gross:symbols.Average(s=>s.Average(e=>e.GrossError)),Net:symbols.Average(s=>s.Average(e=>e.NetError)));
        }).ToArray();
        (double Bias,double Width) Fit(double[] x)
        {
            if(x.Length==0)return (0,0);
            double mean=x.Average();
            double sem=x.Length>1?Math.Sqrt(x.Sum(v=>(v-mean)*(v-mean))/(x.Length*(x.Length-1d))):Math.Abs(mean);
            return (Math.Min(0,mean),1.645*sem);
        }
        var g=Fit(days.Select(d=>d.Gross).ToArray());
        var n=Fit(days.Select(d=>d.Net).ToArray());
        return new(g.Bias,g.Width,n.Bias,n.Width);
    }

    static Dictionary<(string Family,int Side),GroupModel> FitGroups(Row[] rows,long through,
        EurEstimatorCandidate p,bool extended)
    {
        var output=new Dictionary<(string Family,int Side),GroupModel>();
        foreach(var group in rows.GroupBy(x=>x.Group))
        {
            int days=group.Select(r=>r.Day).Distinct().Count(),count=group.Count();
            if(days<p.MinimumDays||count<p.MinimumLabels)continue;
            var weighted=Weights(group,through/Day,p.HalfLifeDays).ToArray();
            int n=weighted[0].Row.Features.Length;
            var mean=new double[n];
            var standard=new double[n];
            for(int i=0;i<n;i++)
            {
                int k=i;
                var observed=weighted.Where(r=>r.Row.Features[k].HasValue).ToArray();
                double mass=observed.Sum(r=>r.Weight);
                mean[i]=mass>0?observed.Sum(r=>r.Weight*r.Row.Features[k]!.Value)/mass:0;
                standard[i]=mass>0?Math.Max(.000001,Math.Sqrt(observed.Sum(r=>
                    r.Weight*Math.Pow(r.Row.Features[k]!.Value-mean[k],2))/mass)):1;
            }
            var scale=new Normalization(mean,standard,extended,p.Predictive?FitRegime(group.Select(r=>r.Context)):null);
            var regressors=weighted.Select(r=>(X:Design(r.Row.Features,scale,p),r.Row.Gross,r.Row.Net,r.Weight)).ToArray();
            var (gross,net)=NativeContextValueResearch.WeightedRidgePair(regressors,p.Ridge);
            var model=new GroupModel(scale,gross,net,new(StringComparer.Ordinal),days,count,
                weighted.Sum(w=>w.Row.Net>0?w.Weight:0)/weighted.Sum(w=>w.Weight),
                group.Min(r=>r.Label.NetEur/r.Label.RiskEur),group.Max(r=>r.Label.NetEur/r.Label.RiskEur),new(0,0,0,0));
            var errors=group.Select(row=>
            {
                var pred=Estimate(model,row.Context,row.Features,p);
                return new Validation(row,row.Gross-pred.Gross,row.Net-pred.Net);
            }).ToArray();
            if(p.ScopePriorDays>0)
                foreach(var scope in errors.SelectMany(e=>ScopeKeys(e.Row.Context,extended,scale.Regime).Select(k=>(Key:k,Error:e)))
                    .GroupBy(x=>x.Key,StringComparer.Ordinal))
                {
                    var scopeDays=scope.GroupBy(x=>x.Error.Row.Day).ToArray();
                    model.Scopes.Add(scope.Key,new(scopeDays.Length,scopeDays.Average(d=>d.Average(e=>e.Error.GrossError)),
                        scopeDays.Average(d=>d.Average(e=>e.Error.NetError))));
                }
            output.Add(group.Key,model with {Errors=Uncertainty(errors)});
        }
        return output;
    }

    internal static NativeEurAdaptiveEstimator Fit(NativeEurCalibration calibration,bool extended,bool predictive=false,bool economicObjective=false)
    {
        if(predictive)return FitPredictive(calibration,extended,economicObjective);
        var rows=calibration.Outcomes.Where(o=>o.AvailableAt<=calibration.ObservationThrough&&
                o.DecisionAt.HasValue&&o.Context?.MarketState is {Length:16})
            .Select(o=>new Row(o,o.Context!,o.DecisionAt!.Value/Day,Values(o.Context!,extended))).ToArray();
        var validationDays=rows.Select(x=>x.Day).Distinct().OrderBy(x=>x).TakeLast(4).Skip(1).ToArray();
        var trials=Grid.Select(p=>
        {
            var validation=new List<Validation>();
            foreach(long day in validationDays)
            {
                long cutoff=day*Day;
                var fitRows=rows.Where(x=>x.Label.AvailableAt<cutoff).ToArray();
                var models=FitGroups(fitRows,cutoff,p,extended);
                foreach(var row in rows.Where(x=>x.Day==day))
                {
                    var predicted=models.TryGetValue(row.Group,out var model)?Estimate(model,row.Context,row.Features,p):(0d,0d);
                    validation.Add(new(row,row.Gross-predicted.Item1,row.Net-predicted.Item2));
                }
            }
            // Equal weight per date and symbol. Score the same validation rows
            // for every candidate, including the cash estimate for unsupported decisions.
            var daily=validation.GroupBy(x=>x.Row.Day).Select(day=>
                day.GroupBy(x=>x.Row.Context.Symbol,StringComparer.Ordinal).Average(symbol=>
                    symbol.Average(x=>(x.GrossError*x.GrossError+2*x.NetError*x.NetError)/3))).ToArray();
            return (Parameters:p,Validation:validation,Score:new EurEstimatorScore(p.Id,daily.Length,validation.Count,
                daily.Length==0?null:daily.Average()));
        }).ToArray();
        var winner=trials.OrderBy(x=>x.Score.Loss??double.PositiveInfinity).First();
        var fitted=FitGroups(rows,calibration.ObservationThrough,winner.Parameters,extended);
        foreach(var validation in winner.Validation.GroupBy(x=>x.Row.Group))
            if(fitted.TryGetValue(validation.Key,out var model)&&validation.Select(x=>x.Row.Day).Distinct().Count()>=2)
                fitted[validation.Key]=model with {Errors=Uncertainty(validation.ToArray())};
        return new(fitted,winner.Parameters,calibration.ObservationThrough,trials.Select(x=>x.Score).ToArray());
    }

    internal NativeEurPayoff? Payoff(string family,int side,NativeEurDecisionContext? context,long at,decimal risk,decimal cost)
    {
        if(at<=fittedThrough||context?.MarketState is not {Length:16}||!groups.TryGetValue((family,side),out var model))
            return null;
        if(selected.Predictive)return PredictivePayoff(family,side,model,context,risk,cost);
        var (g,n)=Estimate(model,context,Values(context,model.Scale.Extended),selected);
        var errors=model.Errors;
        decimal gross=(decimal)g*risk,net=(decimal)n*risk;
        decimal grossLower=(decimal)(g+errors.GrossBias-errors.GrossWidth)*risk;
        decimal netLower=(decimal)(n+errors.NetBias-errors.NetWidth)*risk;
        return new(model.Labels,model.Days,gross,grossLower,Math.Min(net,gross-cost),Math.Min(netLower,grossLower-cost),
            (decimal)model.PositiveFraction,model.MinimumNetR*risk,model.MaximumNetR*risk){Cohort=selected.Id};
    }
}
