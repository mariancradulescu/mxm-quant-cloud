using System;

namespace Mxm.Core;

// Registered choices for conditional development using the existing EUR book.
// Immutable legacy runs retain their original default settings.
public sealed record NativeEurDevelopmentProfile(bool UseAvailableContext = false,
    decimal DistributionTargetRanges = 2m, int MinimumEpisodes = 20, int MinimumDays = 3,
    decimal DayPenalty = 1.645m, decimal StopReserveMultiplier = 1m)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public long? ModeledStopLatencyMs { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool CaptureStudyDiagnostics { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool IncludeRecoveredStructure { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool LearnFromOpportunityEpisodes { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool ObserveIntentExecutionOnTicks { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseRecoveredLocalPayoff { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseExtendedLocalPayoff { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool ObserveFamilyDirectionsOnClosedBars { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool ModelFundingAtPriorClosedSessionQuote { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseAdaptivePayoff { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseAdaptiveAllocation { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseAdaptiveManagement { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseRealizedForecastFeedback { get; init; }

    // New research-only context and calibration, opt-in to preserve historical studies.
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool CaptureVolatilityContext { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UsePredictiveCalibration { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseEconomicEstimatorObjective { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseSelectionAwarePredictiveGrid { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool RevalidatePredictiveVolatilityAtFill { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool KeepAdmissionRiskAtFill { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool ResizeWithinAdmissionRiskAtFill { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseJointMonetaryAllocation { get; init; }

    // Zero preserves the registered eight-wide search. New studies may select
    // any positive computational width without altering the OWNER risk gates.
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public int JointMonetarySearchWidth { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseForecastBandCalibration { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool CaptureClosedBarActivity { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? EconomicMechanism { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? EconomicManagement { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool MinimumContractVolumeOnly { get; init; }

    // Optional research geometry. Null fields preserve every frozen original.
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? EconomicGeometryTimeframe { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? EconomicStopRanges { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public int? EconomicOpportunityVolumeIndex { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool AnchorEconomicGeometryToClosedStructure { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? EconomicManagementTimeframe { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool OptimizeEconomicOpportunityVolume { get; init; }

    // Separate identities preserve the original geometry/fill experiment.
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool MatchEconomicTransitionHorizonAtFill { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public int EconomicStructureLookbackBars { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool ConfirmEconomicEntryOnM5 { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool OptimizeTransitionNetVolume { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool UseMarketTimeFxValuation { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool RequirePav1FastAgreement { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public int Pav1TransitionBars { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool RequireMaturedCashForLargerVolume { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool ReserveObservedBarGaps { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool AllocatePav1AtMinimumVolume { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool CompeteEconomicFamilies { get; init; }

    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool SelectEconomicManagementCausally { get; init; }

    internal string GeometryIdentity => FormattableString.Invariant(
        $"{UseAvailableContext}/{DistributionTargetRanges:G29}/{StopReserveMultiplier:G29}") +
        (ModeledStopLatencyMs is long latency ? FormattableString.Invariant($"/Trade/{latency}") : "") +
        (ObserveIntentExecutionOnTicks?"/TICK_INTENTS":"") +
        (IncludeRecoveredStructure?"/RANGE_TRANSITION+EQUILIBRIUM_REPAIR":"") +
        (ModelFundingAtPriorClosedSessionQuote?"/CLOSED_SESSION_FUNDING":"") +
        (ObserveFamilyDirectionsOnClosedBars?"/CLOSED_BAR_FAMILY_DIRECTION_OBSERVATION":"") +
        (CaptureVolatilityContext?"/CLOSED_BAR_RELATIVE_VOLATILITY_V2":"") +
        (CaptureClosedBarActivity?"/CLOSED_BAR_ACTIVITY_V1":"") +
        (EconomicMechanism is not null?$"/MECHANISM:{EconomicMechanism}/MANAGEMENT:{EconomicManagement}/MINIMUM:{MinimumContractVolumeOnly}":"") +
        (EconomicGeometryTimeframe is not null?FormattableString.Invariant($"/GEOMETRY:{EconomicGeometryTimeframe}/{EconomicStopRanges:G29}"):"") +
        (EconomicOpportunityVolumeIndex is int volume?FormattableString.Invariant($"/OBSERVED_VOLUME_INDEX:{volume}"):"") +
        (AnchorEconomicGeometryToClosedStructure?"/CLOSED_STRUCTURE_ANCHOR":"") +
        (OptimizeEconomicOpportunityVolume?"/OBSERVED_VOLUME_NET_REWARD_RISK":"") +
        (MatchEconomicTransitionHorizonAtFill?"/MATCH_TRANSITION_HORIZON_AT_FILL":"") +
        (EconomicStructureLookbackBars>0?$"/SWING_BARS:{EconomicStructureLookbackBars}/M5_TRUE_RANGE_BUFFER":"") +
        (ConfirmEconomicEntryOnM5?"/M5_ENTRY_CONFIRMATION":"") +
        (OptimizeTransitionNetVolume?"/JOINT_EXPECTED_TRANSITION_NET_VOLUME":"") +
        (UseMarketTimeFxValuation?"/CONDITIONAL_MARKET_TIME_FX":"") +
        (RequirePav1FastAgreement?"/PAV1_M15_AGREEMENT":"") +
        (Pav1TransitionBars>0?$"/PAV1_TRANSITION_BARS:{Pav1TransitionBars}":"") +
        (RequireMaturedCashForLargerVolume?"/MATURED_CASH_MARGINAL_VOLUME":"") +
        (ReserveObservedBarGaps?"/OBSERVED_GAP_RESERVE":"") +
        (AllocatePav1AtMinimumVolume?"/PAV1_MINIMUM_VOLUME_MONETARY_ALLOCATION":"") +
        (CompeteEconomicFamilies?"/SEVEN_FAMILY_CAUSAL_COMMON_BOOK_V1":"") +
        (SelectEconomicManagementCausally?"/MATURED_PAIRED_MANAGEMENT_CHOICE_V1":"") +
        (EconomicManagementTimeframe is not null?$"/MANAGEMENT_TIMEFRAME:{EconomicManagementTimeframe}":"") +
        (EconomicMechanism is not null&&KeepAdmissionRiskAtFill?$"/MECHANISM_KEEP_RISK/RESIZE:{ResizeWithinAdmissionRiskAtFill}":"");

    internal void Verify()
    {
        if(SelectEconomicManagementCausally&&(!CompeteEconomicFamilies||!LearnFromOpportunityEpisodes||
            EconomicManagement!="TRANSITION_VALUE"))
            throw new ArgumentException("EUR_CAUSAL_MANAGEMENT_PROFILE");
        if(CompeteEconomicFamilies&&(EconomicMechanism!=NativeEconomicMechanisms.Scored||
            !UseAvailableContext||!KeepAdmissionRiskAtFill||!ResizeWithinAdmissionRiskAtFill||
            !ObserveIntentExecutionOnTicks||EconomicGeometryTimeframe is null||
            LearnFromOpportunityEpisodes&&!ObserveFamilyDirectionsOnClosedBars))
            throw new ArgumentException("EUR_COMPETITIVE_FAMILY_PROFILE");
        if(AllocatePav1AtMinimumVolume&&(EconomicMechanism!=NativeEconomicMechanisms.Transition||
            !MinimumContractVolumeOnly||!MatchEconomicTransitionHorizonAtFill||!KeepAdmissionRiskAtFill||!ResizeWithinAdmissionRiskAtFill))
            throw new ArgumentException("PAV1_MINIMUM_MONETARY_ALLOCATION");
        if((RequirePav1FastAgreement||Pav1TransitionBars>0||RequireMaturedCashForLargerVolume||ReserveObservedBarGaps&&!CompeteEconomicFamilies)&&
            EconomicMechanism!=NativeEconomicMechanisms.Transition||
            Pav1TransitionBars!=0&&Pav1TransitionBars is not (24 or 72)||
            RequireMaturedCashForLargerVolume&&!OptimizeTransitionNetVolume)
            throw new ArgumentException("PAV1_REGISTERED_MONETARY_PROFILE");
        if(MatchEconomicTransitionHorizonAtFill&&(EconomicMechanism is null||EconomicGeometryTimeframe is null)||
            EconomicStructureLookbackBars!=0&&(EconomicStructureLookbackBars<2||EconomicStructureLookbackBars>16||
                !AnchorEconomicGeometryToClosedStructure)||
            ConfirmEconomicEntryOnM5&&EconomicMechanism is null||
            OptimizeTransitionNetVolume&&(EconomicMechanism!=NativeEconomicMechanisms.Transition||
                MinimumContractVolumeOnly||OptimizeEconomicOpportunityVolume||EconomicOpportunityVolumeIndex is not null||
                !MatchEconomicTransitionHorizonAtFill||!KeepAdmissionRiskAtFill||!ResizeWithinAdmissionRiskAtFill))
            throw new ArgumentException("EUR_CAUSAL_LIFECYCLE_PROFILE");
        if(OptimizeEconomicOpportunityVolume&&(EconomicMechanism is null||MinimumContractVolumeOnly||EconomicOpportunityVolumeIndex is not null||!KeepAdmissionRiskAtFill||!ResizeWithinAdmissionRiskAtFill)||
            AnchorEconomicGeometryToClosedStructure&&(EconomicMechanism is null||EconomicGeometryTimeframe is null)||
            EconomicManagementTimeframe is not null&&(EconomicMechanism is null||EconomicManagement=="BRACKET"||
                !Enum.TryParse<NativeBarTimeframe>(EconomicManagementTimeframe,out var mtf)||!NativeClosedMarketContext.CoverageWindows.Any(x=>x.Timeframe==mtf))||
            EconomicGeometryTimeframe is not null&&
            (EconomicMechanism is null||!Enum.TryParse<NativeBarTimeframe>(EconomicGeometryTimeframe,out var tf)||
             !NativeClosedMarketContext.CoverageWindows.Any(x=>x.Timeframe==tf)||EconomicStopRanges is not >0m)||
            EconomicGeometryTimeframe is null&&EconomicStopRanges is not null||
            EconomicOpportunityVolumeIndex is <0||
            EconomicOpportunityVolumeIndex is not null&&(EconomicMechanism is null||MinimumContractVolumeOnly))
            throw new ArgumentException("EUR_MECHANISM_GEOMETRY_OR_VOLUME");
        if(EconomicMechanism is not null&&(!NativeEconomicMechanisms.All.Contains(EconomicMechanism,StringComparer.Ordinal)||
            !NativeEconomicMechanisms.Management.Contains(EconomicManagement,StringComparer.Ordinal)||UseAdaptivePayoff||
            LearnFromOpportunityEpisodes&&!CompeteEconomicFamilies||!UseAvailableContext)||EconomicManagement is not null&&EconomicMechanism is null)
            throw new ArgumentException("EUR_DISTINCT_MECHANISM_PROFILE");
        if (DistributionTargetRanges <= 0m || (!UseAvailableContext && DistributionTargetRanges != 2m) ||
            MinimumDays < 2 || MinimumEpisodes < MinimumDays ||
            DayPenalty < 0m || StopReserveMultiplier < 1m || ModeledStopLatencyMs is <= 0L ||
            (LearnFromOpportunityEpisodes || ObserveIntentExecutionOnTicks) && ModeledStopLatencyMs is null ||
            UseExtendedLocalPayoff&&!UseRecoveredLocalPayoff ||
            ObserveFamilyDirectionsOnClosedBars&&!LearnFromOpportunityEpisodes||
            UseAdaptivePayoff&&!UseRecoveredLocalPayoff||
            UsePredictiveCalibration&&(!UseAdaptivePayoff||!CaptureVolatilityContext||!UseExtendedLocalPayoff)||
            UseEconomicEstimatorObjective&&!UsePredictiveCalibration||
            UseSelectionAwarePredictiveGrid&&(!UsePredictiveCalibration||!UseEconomicEstimatorObjective)||
            RevalidatePredictiveVolatilityAtFill&&!UsePredictiveCalibration||
            KeepAdmissionRiskAtFill&&!UsePredictiveCalibration&&EconomicMechanism is null||
            ResizeWithinAdmissionRiskAtFill&&!KeepAdmissionRiskAtFill||
            UseJointMonetaryAllocation&&!UsePredictiveCalibration||
            JointMonetarySearchWidth<0||JointMonetarySearchWidth>0&&!UseJointMonetaryAllocation||
            UseForecastBandCalibration&&!UseSelectionAwarePredictiveGrid||
            (UseAdaptiveAllocation||UseAdaptiveManagement||UseRealizedForecastFeedback)&&!UseAdaptivePayoff)
            throw new ArgumentException("EUR_REGISTERED_DEVELOPMENT_PROFILE");
    }
}
