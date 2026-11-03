using System.Text.Json;
namespace Mxm.Core;

public sealed record HoldingExposure(string Id,string Symbol,decimal Units,decimal EntryMarginPerUnitEur,
    decimal StressLossEur);
public sealed record HoldingRiskInput(decimal? EquityEur,decimal PeakReferenceEur,bool DataComplete,
    HoldingExposure[] Positions,JsonElement SourceSymbols,JsonElement RawQuotes,decimal? AccountLeverage,
    decimal DocumentedReferenceStopoutRatio=.5m,decimal TierLeverageDivisor=0m);
public sealed record HoldingMargin(string Id,decimal EntryMarginEur,decimal? RepricedMarginEur,
    decimal? MarginEnvelopeEur,decimal StressLossEur);
public sealed record HoldingRiskResult(HoldingMargin[] Positions,decimal? UsedMarginEnvelopeEur,
    decimal? EquityToMargin,decimal? StressEquityEur,bool? DocumentedReferenceCrossed,
    string[] ExitIds,bool SuspendEntries,bool OutcomeUncertain,string Reason,
    bool AccountStopoutThresholdVerified,bool GlobalDrawdownCertified);

// Conditional research monitor using the same OWNER drawdown objective and
// full-margin coverage already used by the allocator. Not a broker stopout emulator.
public static class HoldingPortfolioRisk
{
    public static object MarketContext(JsonElement root)
    {
        var source=RegimeDiscovery.Read(root.GetProperty("source")).Where(b=>b.Tf=="H4").GroupBy(b=>b.Symbol).ToArray();
        var output=new List<object>();
        foreach(var clockValue in root.GetProperty("clocks").EnumerateArray())
        {
            long clock=clockValue.GetInt64();
            foreach(var group in source)
            {
                var past=group.Where(b=>b.End<=clock).OrderBy(b=>b.End).TakeLast(33).ToArray();
                if(past.Length<33)continue;
                var changes=Enumerable.Range(1,32).Select(i=>(past[i].C/past[i-1].C-1)*10000).ToArray();
                double path=Enumerable.Range(1,32).Sum(i=>Math.Abs(past[i].C-past[i-1].C));
                output.Add(new {Clock=clock,Symbol=group.Key,LastAvailableAt=past[^1].End,
                    Past32RmsBps=Math.Sqrt(changes.Select(x=>x*x).Average()),
                    DirectionalEfficiency=path>0?Math.Abs(past[^1].C-past[0].C)/path:0,
                    Status="CAUSAL_DESCRIPTIVE_CONTEXT_NOT_A_REGIME_SELECTION_FILTER"});
            }
        }
        return output;
    }
    public static HoldingRiskResult Assess(HoldingRiskInput a)
    {
        if(a.Positions.Select(p=>p.Id).Distinct(StringComparer.Ordinal).Count()!=a.Positions.Length ||
           a.Positions.Any(p=>p.Units<=0 || p.EntryMarginPerUnitEur<=0 || p.StressLossEur<0) ||
           a.DocumentedReferenceStopoutRatio<=0 || a.DocumentedReferenceStopoutRatio>1 ||
           a.TierLeverageDivisor is not (1m or 100m))
            throw new ArgumentException("INVALID_HOLDING_RISK_INPUT");
        if(a.Positions.Length==0)return new(Array.Empty<HoldingMargin>(),0,null,a.EquityEur,false,
            Array.Empty<string>(),!a.DataComplete,false,"FLAT",false,false);
        if(!a.DataComplete || a.EquityEur is null || a.AccountLeverage is null || a.AccountLeverage<=0)
            return new(Array.Empty<HoldingMargin>(),null,null,null,null,a.Positions.Select(p=>p.Id).ToArray(),
                true,true,"EVIDENCE_GAP_EXIT_AT_NEXT_OBSERVED_QUOTE",false,false);
        decimal Bid(string s)=>a.RawQuotes.GetProperty(s).GetProperty("bid").GetDecimal()/100000m;
        decimal Ask(string s)=>a.RawQuotes.GetProperty(s).GetProperty("ask").GetDecimal()/100000m;
        var margins=new List<HoldingMargin>();
        try
        {
            foreach(var p in a.Positions)
            {
                var symbol=a.SourceSymbols.GetProperty(p.Symbol);
                string quote=symbol.GetProperty("quoteAsset").GetString()!;
                decimal usdPerQuote=quote switch {"USD"=>1,"JPY"=>1/Bid("USDJPY"),"CAD"=>1/Bid("USDCAD"),
                    _=>throw new ArgumentException("UNSUPPORTED_MARGIN_CURRENCY")};
                decimal notional=p.Units*Ask(p.Symbol)*usdPerQuote;
                decimal leverage=a.AccountLeverage.Value;
                var tiers=symbol.GetProperty("dynamicLeverage").EnumerateArray().ToArray();
                if(tiers.Length==0)throw new ArgumentException("MISSING_DYNAMIC_LEVERAGE");
                decimal priorCap=0;
                foreach(var tier in tiers)
                {
                    decimal cap=tier.GetProperty("volume").GetDecimal()/100m;
                    // The caller must declare raw hundredths (100) or already decoded
                    // ratios (1). Never silently mix account 1:N with raw wire values.
                    decimal lev=tier.GetProperty("leverage").GetDecimal()/a.TierLeverageDivisor;
                    if(cap<=priorCap || lev<=0)throw new ArgumentException("INVALID_LEVERAGE_TIERS");
                    // Conservative full-notional rate at the least leverage of
                    // all touched tiers, without inventing broker historical tiers.
                    if(priorCap<notional)leverage=Math.Min(leverage,lev);
                    priorCap=cap;
                }
                decimal repriced=notional/leverage/Bid("EURUSD");
                decimal entry=p.Units*p.EntryMarginPerUnitEur;
                margins.Add(new(p.Id,entry,repriced,Math.Max(entry,repriced),p.StressLossEur));
            }
        }
        catch(Exception e) when(e is ArgumentException or KeyNotFoundException or InvalidOperationException or DivideByZeroException)
        {return new(margins.ToArray(),null,null,null,null,a.Positions.Select(p=>p.Id).ToArray(),true,true,
            "MARGIN_REVALUATION_UNKNOWN_EXIT_AT_NEXT_OBSERVED_QUOTE",false,false);}
        decimal equity=a.EquityEur.Value,margin=margins.Sum(p=>p.MarginEnvelopeEur!.Value),stress=margins.Sum(p=>p.StressLossEur);
        decimal peak=Math.Max(200m,Math.Max(a.PeakReferenceEur,equity));
        decimal floor=(1-OwnerRiskAuthority.MaximumSystemDrawdown)*peak;
        bool crossed=equity<=margin*a.DocumentedReferenceStopoutRatio;
        var exits=new List<string>();decimal remainingMargin=margin,remainingStress=stress;
        foreach(var p in margins.OrderByDescending(p=>p.MarginEnvelopeEur!.Value+p.StressLossEur).ThenBy(p=>p.Id,StringComparer.Ordinal))
        {
            if(equity-remainingStress>Math.Max(floor,remainingMargin))break;
            exits.Add(p.Id);remainingMargin-=p.MarginEnvelopeEur!.Value;remainingStress-=p.StressLossEur;
        }
        return new(margins.ToArray(),margin,margin>0?equity/margin:null,equity-stress,crossed,exits.ToArray(),
            exits.Count>0 || equity<=floor,crossed,
            exits.Count>0?"MODEL_HOLDING_MARGIN_OR_DRAWDOWN_BUFFER_EXIT":"MODEL_HOLDING_CAPACITY_WITHIN_SCENARIO",false,false);
    }
}
