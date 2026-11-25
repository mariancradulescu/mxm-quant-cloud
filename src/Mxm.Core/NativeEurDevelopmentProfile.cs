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

    internal string GeometryIdentity => FormattableString.Invariant(
        $"{UseAvailableContext}/{DistributionTargetRanges:G29}/{StopReserveMultiplier:G29}") +
        (ModeledStopLatencyMs is long latency ? FormattableString.Invariant($"/Trade/{latency}") : "") +
        (ObserveIntentExecutionOnTicks?"/TICK_INTENTS":"") +
        (IncludeRecoveredStructure?"/RANGE_TRANSITION+EQUILIBRIUM_REPAIR":"") +
        (ModelFundingAtPriorClosedSessionQuote?"/CLOSED_SESSION_FUNDING":"") +
        (ObserveFamilyDirectionsOnClosedBars?"/CLOSED_BAR_FAMILY_DIRECTION_OBSERVATION":"");

    internal void Verify()
    {
        if (DistributionTargetRanges <= 0m || (!UseAvailableContext && DistributionTargetRanges != 2m) ||
            MinimumDays < 2 || MinimumEpisodes < MinimumDays ||
            DayPenalty < 0m || StopReserveMultiplier < 1m || ModeledStopLatencyMs is <= 0L ||
            (LearnFromOpportunityEpisodes || ObserveIntentExecutionOnTicks) && ModeledStopLatencyMs is null ||
            UseExtendedLocalPayoff&&!UseRecoveredLocalPayoff ||
            ObserveFamilyDirectionsOnClosedBars&&!LearnFromOpportunityEpisodes||
            UseAdaptivePayoff&&!UseRecoveredLocalPayoff||
            (UseAdaptiveAllocation||UseAdaptiveManagement||UseRealizedForecastFeedback)&&!UseAdaptivePayoff)
            throw new ArgumentException("EUR_REGISTERED_DEVELOPMENT_PROFILE");
    }
}
