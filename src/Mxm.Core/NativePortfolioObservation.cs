using System.Text.Json;
namespace Mxm.Core;

public sealed record PositionRiskMark(string PositionId,string Symbol,int Side,decimal Units,decimal? NetPnlEur);
public sealed record PortfolioRiskMark(string AccountBinding,string Domain,string EquityBasis,long At,long AvailableAt,
    decimal? CashEur,decimal? EquityEur,decimal? MarginEur,decimal? FreeMarginEur,decimal? CreditEur,
    bool InventoryStable,bool ComponentsIndependent,PositionRiskMark[] Positions,decimal? AdditionalExitCostBoundEur,decimal? StressLossEur,
    decimal? PlatformReportedStopoutRatio,decimal RoundingToleranceEur,string EvidenceHash);
public sealed record PortfolioObservationState(string AccountBinding,string Domain,string EquityBasis,long LastAt,
    decimal? ObservedPeakEur,decimal? WorstSampledDrawdown,int ValidSamples,bool ObservationGap,string LastHash);
public sealed record PortfolioRiskReport(decimal? ObservedEquityEur,decimal? ConservativeExitEquityEur,decimal? UsedMarginEur,
    decimal? EquityToMargin,decimal? StressEquityEur,decimal? ObservedPeakEur,decimal? MaximumSampledDrawdown,int ValidSamples,
    bool ObservationGap,bool? ComponentsReconciled,bool? PlatformReferenceCrossed,bool SuspendNewExposure,
    string[] ReviewReductionIds,string Reason,bool LifetimePeakCertified=false,bool ContinuousDrawdownCertified=false,
    bool ActualLiquidationPredicted=false,bool OrdersEnabled=false);

// Current observations are separate from monetary cash reconstruction and
// operational certification. A sampled peak is only a lower bound on lifetime peak.
public sealed class NativePortfolioObservation
{
    public PortfolioObservationState State {get;private set;}
    public NativePortfolioObservation(string accountBinding)=>State=new(accountBinding,"","",-1,null,null,0,false,"");
    public static NativePortfolioObservation Restore(PortfolioObservationState s,string accountBinding)
    {
        if(s.AccountBinding!=accountBinding||s.ValidSamples<0||s.LastAt< -1||s.WorstSampledDrawdown is <0)
            throw new ArgumentException("INVALID_RISK_OBSERVATION_STATE");
        return new(accountBinding){State=s};
    }
    public PortfolioRiskReport Observe(PortfolioRiskMark m,long now)
    {
        if(m.AccountBinding!=State.AccountBinding||m.Domain is not ("BROKER_PLATFORM_OBSERVATION" or "FROZEN_MODELED_HOLDING")||
            m.EquityBasis is not ("PLATFORM_MARK_EQUITY" or "CONDITIONAL_LIQUIDATION_ESTIMATE")||
            m.RoundingToleranceEur<0||m.EvidenceHash.Length!=64||!m.EvidenceHash.All(Uri.IsHexDigit)||
            m.Positions.Any(p=>p.Side is not (-1 or 1)||p.Units<=0)||m.Positions.Select(p=>p.PositionId).Distinct().Count()!=m.Positions.Length)
            throw new ArgumentException("INVALID_PORTFOLIO_OBSERVATION");
        if(State.ValidSamples>0&&(m.Domain!=State.Domain||m.EquityBasis!=State.EquityBasis))
            throw new ArgumentException("RISK_SOURCE_OR_EQUITY_BASIS_MIXING_PROHIBITED");
        if(m.At<State.LastAt)throw new ArgumentException("RISK_OBSERVATION_CLOCK_REVERSED");
        if(m.At==State.LastAt&&m.EvidenceHash!=State.LastHash)throw new ArgumentException("CONFLICTING_SAME_CLOCK_RISK_MARK");
        bool fresh=m.At<=m.AvailableAt&&m.AvailableAt<=now&&now-m.AvailableAt<=2000&&m.AvailableAt-m.At<=2000;
        // Frozen observations are known only at technical ingestion, not at the
        // original modeled trade decision. Their event clocks remain unchanged.
        if(m.Domain=="FROZEN_MODELED_HOLDING")fresh=m.At<=m.AvailableAt&&m.AvailableAt<=now&&now-m.AvailableAt<=2000;
        bool? components=null;
        if(m.ComponentsIndependent)
        {
            components=m.CashEur.HasValue&&m.CreditEur.HasValue&&m.EquityEur.HasValue&&m.Positions.All(p=>p.NetPnlEur.HasValue)&&
                Math.Abs(m.CashEur.Value+m.CreditEur.Value+m.Positions.Sum(p=>p.NetPnlEur!.Value)-m.EquityEur.Value)<=m.RoundingToleranceEur;
        }
        bool valid=fresh&&m.InventoryStable&&m.EquityEur.HasValue&&m.MarginEur is >=0&&
            m.FreeMarginEur.HasValue&&Math.Abs(m.EquityEur.Value-m.MarginEur.Value-m.FreeMarginEur.Value)<=m.RoundingToleranceEur&&components!=false;
        bool duplicate=m.At==State.LastAt&&m.EvidenceHash==State.LastHash;
        if(valid&&!duplicate)
        {
            decimal eq=m.EquityEur!.Value,peak=Math.Max(State.ObservedPeakEur??eq,eq);int samples=State.ValidSamples+1;
            decimal? dd=samples>=2&&peak>0?Math.Max(State.WorstSampledDrawdown??0,1-eq/peak):null;
            State=State with {Domain=m.Domain,EquityBasis=m.EquityBasis,LastAt=m.At,ObservedPeakEur=peak,
                WorstSampledDrawdown=dd,ValidSamples=samples,LastHash=m.EvidenceHash};
        }
        if(!valid)State=State with {ObservationGap=true};
        decimal? liquidation=valid&&m.AdditionalExitCostBoundEur is >=0?m.EquityEur-m.AdditionalExitCostBoundEur:null;
        decimal? ratio=valid&&m.MarginEur>0?m.EquityEur/m.MarginEur:null;
        bool? crossed=ratio.HasValue&&m.PlatformReportedStopoutRatio is >0 and <=1?ratio<=m.PlatformReportedStopoutRatio:null;
        bool ddBreach=State.WorstSampledDrawdown>=OwnerRiskAuthority.MaximumSystemDrawdown;
        decimal? stressed=liquidation.HasValue&&m.StressLossEur is >=0?liquidation-m.StressLossEur:null;
        bool marginPressure=valid&&(m.EquityEur<=m.MarginEur || stressed.HasValue&&
            (stressed<=m.MarginEur || State.ObservedPeakEur>0&&stressed<=.70m*State.ObservedPeakEur));
        bool reduction=!valid||crossed==true||ddBreach||marginPressure;
        string reason=!valid?"OBSERVATION_INCOMPLETE_OR_INCONSISTENT":ddBreach?
            (m.Domain=="BROKER_PLATFORM_OBSERVATION"?"OBSERVED_PLATFORM_EQUITY_DECLINE_REACHES_REFERENCE_CASHFLOW_HISTORY_UNPROVEN":"OBSERVED_DRAWDOWN_LOWER_BOUND_REACHES_OWNER_LIMIT"):
            crossed==true?"PLATFORM_REPORTED_MARGIN_REFERENCE_CROSSED_NOT_LIQUIDATION_CERTIFICATE":marginPressure?"OBSERVED_OR_DECLARED_STRESS_MARGIN_DRAWDOWN_COVERAGE_LOST":
            liquidation is null?"CURRENT_MARK_OBSERVED_EXIT_COST_OR_LIQUIDITY_UNKNOWN":"CONDITIONAL_EXIT_EQUITY_OBSERVED_NOT_CONTINUOUS_CERTIFICATE";
        return new(valid?m.EquityEur:null,liquidation,valid?m.MarginEur:null,ratio,stressed,State.ObservedPeakEur,
            State.WorstSampledDrawdown,State.ValidSamples,State.ObservationGap,components,crossed,true,
            reduction?m.Positions.Select(p=>p.PositionId).ToArray():Array.Empty<string>(),reason);
    }
}

public sealed partial class NativeFundedSession
{
    public NativePortfolioObservation PortfolioObservation {get;private set;}=null!;
    public PortfolioRiskReport ObservePortfolio(PortfolioRiskMark mark,long now)=>PortfolioObservation.Observe(mark,now);
}
