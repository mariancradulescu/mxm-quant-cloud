using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// FCP1 is a distinct prospective comparator, not a patch to any SCP1 receipt.
// The same pure predecision function is called by Mxm.Replay and the
// observation-only Mxm.Cloud adapter through NativeUnifiedPortfolioEngine.
// Candidate order is fixed without future results; every candidate is tested
// for financing BEFORE a FIRST candidate can be chosen.
public sealed record Fcp1Offer(Ucp1DecisionSignal Signal,Ucp1MarketFrame Market);
public sealed record Fcp1Examined(
    Ucp1DecisionSignal Signal,Ucp1MarketFrame Market,
    bool Fundable,decimal Units,decimal ReservedAdverseRiskEur,
    double? FavorableProbability,decimal? CentralNetPerMinUnitEur,
    decimal? LowerNetPerMinUnitEur,string ScoreMethod,string Reason);
public sealed record Fcp1Decision(Fcp1Examined[] Examined,
    Fcp1Examined? Selected,string Status);

public static class NativeFcp1FinancedSelection
{
    public const string Version="FCP1_PRESOURCE_FIRST_FINANCE_COMPARATORS_V1";
    public static readonly string[] Policies={
        "FCP1_FIRST","FCP1_SCORE","FCP1_RIDGE","FCP1_MARGINAL",
        "FCP1_ABSTAIN","FCP1_LONG","FCP1_SHORT","FCP1_CASH"
    };
    static decimal Fee(LedgerQuote q,decimal units)
        =>Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);

    public static Fcp1Decision Choose(string policy,long at,Scp1ScoreModel model,
        IReadOnlyList<Fcp1Offer> input,LedgerSummary book,
        LedgerPosition[] held,LedgerEvent[] pending,
        decimal committedAdverseRiskEur,decimal breadth)
    {
        if(!Policies.Contains(policy,StringComparer.Ordinal)||
           model is null||model.Version!=NativeScp1EconomicScorer.Version||
           at<=0||input is null||held is null||pending is null||
           committedAdverseRiskEur<0m ||
           input.Any(x=>x.Signal.Symbol!=x.Market.Symbol ||
               x.Market.Quote.At!=at))
            throw new ArgumentException("FCP1_INVALID_CAUSAL_CANDIDATE_SET");
        if(policy=="FCP1_CASH")
            return new(Array.Empty<Fcp1Examined>(),null,"FCP1_CASH_NO_ENTRY");
        var all=input.OrderBy(x=>x.Signal.Symbol,StringComparer.Ordinal)
            .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal)
            .ThenBy(x=>x.Signal.Side).ToArray();
        var observed=all.Select(x=>{
            var s=x.Signal;
            if(policy=="FCP1_LONG")
                s=s with {Side=1,Family="FUNDED_LONG_CONTROL"};
            if(policy=="FCP1_SHORT")
                s=s with {Side=-1,Family="FUNDED_SHORT_CONTROL"};
            return new Fcp1Offer(s,x.Market);
        }).ToArray();
        var byMarket=observed.Select(x=>x.Market).GroupBy(x=>x.Symbol)
            .ToDictionary(g=>g.Key,g=>g.First(),StringComparer.Ordinal);
        var occupied=held.Select(p=>p.Symbol).Concat(pending.Where(p=>
            p.Kind=="REQUEST_OPEN").Select(p=>p.Symbol))
            .ToHashSet(StringComparer.Ordinal);
        var pendingOpen=pending.Where(x=>x.Kind=="REQUEST_OPEN").ToArray();
        bool missingPending=pendingOpen.Any(x=>!byMarket.ContainsKey(x.Symbol));
        decimal reservedPending=missingPending?0m:pendingOpen.Sum(x=>x.Units*
            Math.Max(x.MarginPerUnit,byMarket[x.Symbol].Quote.MarginPerUnit));
        bool accountKnown=book.LiquidationEquityEur is decimal &&
            book.FreeMarginEur is decimal &&book.UsedMarginEur is decimal &&
            !book.HistoryEvidenceIncomplete &&!missingPending &&
            book.MaximumSampledDrawdown<.30m;
        decimal equity=book.LiquidationEquityEur??0m;
        decimal free=book.FreeMarginEur??0m;
        decimal marginBudget=Math.Max(0m,free-reservedPending-
            Math.Max(.10m, .10m*equity));
        // The recorded book peak, not a reset 300EUR pocket, determines the
        // remaining 30%-DD budget. Reserve 20% for unmodeled stop gaps.
        decimal peak=Math.Max(book.ObservedPeakEur,equity);
        decimal riskBudget=Math.Max(0m,(equity-.70m*peak-
            committedAdverseRiskEur)*.80m);
        var examined=new List<Fcp1Examined>();
        foreach(var offer in observed)
        {
            var s=offer.Signal;var m=offer.Market;var q=m.Quote;var c=m.Contract;
            double? probability=null;
            decimal? central=null,lower=null;
            string method=policy=="FCP1_RIDGE"?"RIDGE_NONLINEAR":"BAYES_CONTEXT";
            try
            {
                var x=NativeScp1EconomicScorer.Features(m.Symbol,at,s.Side,
                    s.Family,m.M5,m.M15,breadth);
                var p=NativeScp1EconomicScorer.Predict(model,s.Family,s.Side,x,method);
                probability=p.PWin;
                decimal riskPrice=1.5m*s.Atr;
                decimal min=c.MinimumUnits;
                if(min>0m)
                {
                    decimal estimatedAllCosts=(q.Ask-q.Bid+
                        2m*m.SlippagePerSideQuote)*q.EurDebit*min+
                        2m*Fee(q,min);
                    central=(decimal)p.MeanR*riskPrice*q.EurCredit*min-
                        estimatedAllCosts;
                    lower=(decimal)p.LowerConfidenceR*riskPrice*q.EurDebit*min-
                        estimatedAllCosts;
                }
            }
            catch(ArgumentException)
            {
                // A forecast gap cannot veto the simple comparator: FIRST is
                // intentionally model-independent. Score policies fail closed.
                method="UNAVAILABLE_CAUSAL_SCORE";
            }
            string reject="";
            decimal units=0m,riskEur=0m;
            if(occupied.Contains(s.Symbol))
                reject="FCP1_HELD_OR_PENDING_SYMBOL";
            else if(!accountKnown||equity<=0m)
                reject="FCP1_COMMON_ACCOUNT_MARK_OR_DD_UNAVAILABLE";
            else if(s.Atr<=0m||c.MinimumUnits<=0m||c.VolumeStepUnits<=0m||
                    c.MaximumUnits<c.MinimumUnits||q.MarginPerUnit<=0m||
                    q.EurDebit<=0m||q.EurCredit<=0m||q.Ask<q.Bid||
                    m.SlippagePerSideQuote<0m)
                reject="FCP1_ORIGINAL_CONTRACT_OR_COST_UNAVAILABLE";
            else
            {
                decimal min=c.MinimumUnits,step=c.VolumeStepUnits;
                decimal perUnitLoss=(1.5m*s.Atr+q.Ask-q.Bid+
                    2m*m.SlippagePerSideQuote)*q.EurDebit;
                decimal perUnitMargin=q.MarginPerUnit;
                decimal minRisk=perUnitLoss*min+2m*Fee(q,min);
                // Margin, actual min/step/max and joint adverse stop-loss
                // commitment are hard feasibility gates, never expected alpha.
                if(marginBudget<perUnitMargin*min || riskBudget<minRisk)
                    reject="FCP1_MINIMUM_NOT_FINANCEABLE_COMMON_EUR300";
                else
                {
                    decimal maxByMargin=decimal.Floor(marginBudget/perUnitMargin);
                    decimal maxByRisk=decimal.Floor(
                        (riskBudget-2m*q.ExitFeeFloor)/
                        Math.Max(.0000000001m,perUnitLoss+
                            2m*q.ExitFeePerUnit));
                    decimal maxUnits=Math.Min(c.MaximumUnits,
                        Math.Min(maxByMargin,maxByRisk));
                    if(maxUnits<min)
                        reject="FCP1_MAX_UNITS_BELOW_LEGAL_MINIMUM";
                    else
                    {
                        units=min+decimal.Floor((maxUnits-min)/step)*step;
                        riskEur=perUnitLoss*units+2m*Fee(q,units);
                        if(units<min ||riskEur>riskBudget ||
                           units*perUnitMargin>marginBudget)
                        {
                            units=0m;riskEur=0m;
                            reject="FCP1_COST_OR_RISK_RESERVE_EXCEEDED";
                        }
                    }
                }
            }
            examined.Add(new(s,m,units>0m,units,riskEur,probability,
                central,lower,method,reject==""?"FCP1_FINANCEABLE":reject));
        }
        IEnumerable<Fcp1Examined> ordered=examined;
        if(policy=="FCP1_SCORE")
            ordered=ordered.OrderByDescending(x=>x.FavorableProbability??double.NegativeInfinity)
                .ThenBy(x=>x.Signal.Symbol,StringComparer.Ordinal)
                .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal);
        else if(policy=="FCP1_RIDGE")
            ordered=ordered.OrderByDescending(x=>x.FavorableProbability??double.NegativeInfinity)
                .ThenBy(x=>x.Signal.Symbol,StringComparer.Ordinal)
                .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal);
        else if(policy is "FCP1_MARGINAL" or "FCP1_ABSTAIN")
            ordered=ordered.OrderByDescending(x=>x.LowerNetPerMinUnitEur??decimal.MinValue)
                .ThenBy(x=>x.Signal.Symbol,StringComparer.Ordinal)
                .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal);
        var eligible=ordered.Where(x=>x.Fundable);
        if(policy is "FCP1_SCORE" or "FCP1_RIDGE")
            eligible=eligible.Where(x=>x.FavorableProbability.HasValue);
        if(policy is "FCP1_MARGINAL" or "FCP1_ABSTAIN")
            eligible=eligible.Where(x=>x.LowerNetPerMinUnitEur>0m);
        if(policy=="FCP1_ABSTAIN")
            eligible=eligible.Where(x=>
                x.FavorableProbability>model.GlobalPrior);
        var chosen=eligible.FirstOrDefault();
        return new(examined.ToArray(),chosen,chosen is null?
            "FCP1_NO_FEASIBLE_OR_SCORE_ADMITTED_OPPORTUNITY":
            "FCP1_FIRST_FINANCEABLE_IN_PREDECLARED_POLICY_ORDER");
    }
}
