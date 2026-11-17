using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
namespace Mxm.Core;

// Reporting only: receives receipts of the existing native EUR book, never
// creates a second allocator, order, finance estimate or portfolio state.
public sealed record NativeEconomicMark(long At,decimal? LiquidationEquityEur,
    decimal? UsedMarginEur,decimal? FreeMarginEur,int OpenPositions,
    bool FullExposureMarkKnown=true,string Regime="UNKNOWN");
public sealed record NativeEntryRisk(string PositionId,decimal RiskEur,
    long EstimatedAt,string CalibrationHash);
public sealed record NativeEconomicScorecardInput(string Policy,
    LedgerClosedFragment[] Closed,NativeEconomicMark[] Marks,NativeEntryRisk[] InitialRisks,
    string[] EligibleIsoWeeks,decimal InitialCapitalEur=300m,
    decimal? BrokerOrConditionalNetEur=null,decimal? MatchedBenchmarkNetEur=0m,
    bool FullBookSettlementKnown=false,bool QuoteAndCostsVerified=false,
    bool ContinuousFloatingDrawdownCertified=false);
public sealed record NativeEconomicScorecard(
    string Policy,string EvidenceClass,int CompletedRoundTrips,
    decimal? NetEur,decimal? ReturnOnCapital,decimal? IncrementalVersusBenchmarkEur,
    decimal? NetExpectancyPerTradeEur,decimal? WinRate,decimal? MeanWinEur,
    decimal? MeanLossEur,decimal? ProfitFactor,decimal? PayoffRatio,
    decimal? MeanRiskMultiple,decimal? TotalNetToCommittedRisk,
    decimal? WorstTradeEur,decimal? ExpectedShortfall5PctEur,
    int? MaximumConsecutiveLosses,decimal? MaximumSampledFloatingDrawdown,
    bool ContinuousDrawdownCertified,decimal? PeakMarginEur,
    decimal? MinimumFreeMarginEur,int? MaximumConcurrentPositions,
    decimal? PeakMarginToInitialCapital,decimal? NetToPeakMargin,
    Dictionary<string,int> FundedCompletionsByIsoWeek,bool Hard21AllEligibleWeeks,
    bool FullFinancialOutcomeKnown,bool StatisticalSupportSufficient,
    Dictionary<string,decimal>? RegimeNetEur,string[] UnknownOrNotApplicable);

public static class NativePerformanceScorecard
{
    const int MinimumTradeDiagnostic=20;
    static string Week(long at)
    {
        var t=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return ISOWeek.GetYear(t)+"-W"+ISOWeek.GetWeekOfYear(t).ToString("00",CultureInfo.InvariantCulture);
    }
    public static NativeEconomicScorecard Calculate(NativeEconomicScorecardInput x)
    {
        if(x is null || string.IsNullOrWhiteSpace(x.Policy) || x.InitialCapitalEur<=0m ||
           x.Closed is null || x.Marks is null || x.InitialRisks is null || x.EligibleIsoWeeks is null ||
           x.Marks.Any(m=>m.OpenPositions<0 || m.UsedMarginEur<0 || m.FreeMarginEur<0) ||
           x.InitialRisks.Any(r=>r.RiskEur<=0m || string.IsNullOrWhiteSpace(r.PositionId) ||
             string.IsNullOrWhiteSpace(r.CalibrationHash) || r.EstimatedAt<0) ||
           x.InitialRisks.GroupBy(r=>r.PositionId).Any(g=>g.Count()!=1))
            throw new ArgumentException("NATIVE_SCORECARD_INVALID_INPUT");
        var complete=x.Closed.GroupBy(t=>t.PositionId).Where(g=>g.Any(t=>t.CompletesRoundTrip))
            .Select(g=>new {Id=g.Key,At=g.Max(t=>t.ClosedAt),Opened=g.Min(t=>t.OpenedAt),
                Net=g.Sum(t=>t.NetEur),Gross=g.Sum(t=>t.GrossEur)}).OrderBy(t=>t.At).ThenBy(t=>t.Id).ToArray();
        if(complete.Any(t=>t.At<t.Opened))throw new ArgumentException("NATIVE_SCORECARD_REVERSED_TRADE");
        int n=complete.Length;
        var weeks=x.EligibleIsoWeeks.Distinct(StringComparer.Ordinal).OrderBy(t=>t,StringComparer.Ordinal)
            .ToDictionary(t=>t,t=>complete.Count(z=>Week(z.At)==t),StringComparer.Ordinal);
        bool allRisk=complete.All(t=>x.InitialRisks.Any(r=>r.PositionId==t.Id && r.EstimatedAt<t.Opened));
        decimal committed=allRisk?complete.Sum(t=>x.InitialRisks.Single(r=>r.PositionId==t.Id).RiskEur):0;
        bool completeBook=x.FullBookSettlementKnown && x.Closed.All(t=>complete.Any(p=>p.Id==t.PositionId));
        var unknown=new List<string>();
        decimal? net=x.BrokerOrConditionalNetEur;
        if(!completeBook || !net.HasValue)unknown.Add("TERMINAL_NET_UNKNOWN_OR_UNRECONCILED");
        else if(Math.Abs(net.Value-complete.Sum(t=>t.Net))>0.0000001m)
            throw new ArgumentException("NATIVE_SCORECARD_CASH_TRADE_IDENTITY");
        var snap=x.Marks.OrderBy(m=>m.At).ToArray();
        bool marksKnown=snap.Length>0 && snap.All(m=>m.FullExposureMarkKnown &&
            m.LiquidationEquityEur.HasValue && m.UsedMarginEur.HasValue && m.FreeMarginEur.HasValue);
        decimal? dd=null,peakMargin=null,minFree=null,peakUtil=null,netToPeak=null;
        int? maxPositions=null;
        Dictionary<string,decimal>? regime=null;
        if(marksKnown)
        {
            decimal peak=x.InitialCapitalEur,worst=0m;
            foreach(var m in snap)
            {
                decimal equity=m.LiquidationEquityEur!.Value;
                peak=Math.Max(peak,equity);
                worst=Math.Max(worst,(peak-equity)/peak);
            }
            dd=worst;peakMargin=snap.Max(m=>m.UsedMarginEur!.Value);
            minFree=snap.Min(m=>m.FreeMarginEur!.Value);
            maxPositions=snap.Max(m=>m.OpenPositions);
            peakUtil=peakMargin/x.InitialCapitalEur;
            if(net.HasValue && peakMargin>0m)netToPeak=net/peakMargin;
        }
        else unknown.Add("FLOATING_EQUITY_MARGIN_OR_FREE_MARGIN_MARKS_UNKNOWN");
        if(!x.ContinuousFloatingDrawdownCertified)
            unknown.Add("CONTINUOUS_INTRATICK_AND_GAP_DRAWDOWN_NOT_CERTIFIED");
        if(!allRisk)unknown.Add("INITIAL_ENTRY_RISK_NOT_DOCUMENTED_FOR_ALL_TRADES");
        if(n<MinimumTradeDiagnostic)unknown.Add("TRADE_METRICS_INSUFFICIENT_SAMPLE_LT20");
        decimal? avg=null,winRate=null,avgWin=null,avgLoss=null,pf=null,payoff=null,
            rMultiple=null,netRisk=null,worstLoss=null,es=null;
        int? streak=null;
        if(n>=MinimumTradeDiagnostic)
        {
            decimal wins=complete.Where(t=>t.Net>0m).Sum(t=>t.Net);
            decimal losses=-complete.Where(t=>t.Net<0m).Sum(t=>t.Net);
            var positives=complete.Where(t=>t.Net>0m).ToArray();
            var negatives=complete.Where(t=>t.Net<0m).ToArray();
            avg=complete.Average(t=>t.Net);
            winRate=(decimal)positives.Length/n;
            avgWin=positives.Length==0?null:positives.Average(t=>t.Net);
            avgLoss=negatives.Length==0?null:negatives.Average(t=>t.Net);
            pf=losses>0m?wins/losses:null;
            payoff=avgWin.HasValue&&avgLoss.HasValue&&avgLoss!=0?avgWin/(-avgLoss):null;
            worstLoss=complete.Min(t=>t.Net);
            // Exact lower 5% empirical trade tail, minimum 20 trades,
            // no parametric or independent-observation guarantee.
            es=complete.OrderBy(t=>t.Net).Take((int)Math.Ceiling(n*0.05m)).Average(t=>t.Net);
            int running=0,maximum=0;
            foreach(var tr in complete){running=tr.Net<0m?running+1:0;maximum=Math.Max(maximum,running);}
            streak=maximum;
            if(allRisk)
            {
                rMultiple=complete.Average(t=>t.Net/x.InitialRisks.Single(r=>r.PositionId==t.Id).RiskEur);
                netRisk=committed>0?complete.Sum(t=>t.Net)/committed:null;
            }
        }
        if(!x.QuoteAndCostsVerified)unknown.Add("HISTORICAL_BROKER_COSTS_OR_FILLS_NOT_CERTIFIED");
        if(n==0)unknown.Add("NO_FINANCED_ROUND_TRIPS_CASH_IS_NOT_PERFORMANCE");
        bool known=completeBook && net.HasValue;
        if(!known)net=null;
        return new NativeEconomicScorecard(x.Policy,
            x.QuoteAndCostsVerified?"SOURCE_QUOTE_CONDITIONAL":"UNKNOWN_OR_MODEL_SCENARIO",
            n,net,net/x.InitialCapitalEur,
            net.HasValue && x.MatchedBenchmarkNetEur.HasValue?net-x.MatchedBenchmarkNetEur:null,
            avg,winRate,avgWin,avgLoss,pf,payoff,rMultiple,netRisk,
            worstLoss,es,streak,dd,x.ContinuousFloatingDrawdownCertified,
            peakMargin,minFree,maxPositions,peakUtil,netToPeak,weeks,
            weeks.Count>0 && weeks.Values.All(v=>v>=21),known,
            n>=MinimumTradeDiagnostic,regime,unknown.Distinct().ToArray());
    }
}
