using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeEurMarginObservation(int Side,decimal Units,decimal MarginEur,
    long ObservedAt,string SourceSha256);
public sealed record NativeEurPayoff(int ReconciledEpisodes,int ObservationDays,
    decimal GrossMeanEur,decimal GrossLowerEur,decimal NetMeanEur,decimal NetLowerEur,
    decimal ObservedPositiveNetFraction,decimal NetWorstEur,decimal NetBestEur)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativePathDistributionForecast? PathDistribution { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? Cohort { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeEurPredictiveEvidence? PredictiveEvidence { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? EffectiveObservationDays { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public long? LatestEligibleObservationAt { get; init; }
}
public sealed record NativeEurBarState(NativeBarTimeframe Timeframe,int Direction,bool AboveRecentRange);
public sealed record NativeEurDecisionContext(string Symbol,string? AssetClass, int UtcMinute,
    NativeEurBarState[] ClosedStates,decimal CommittedMarginFraction,decimal CostRiskFraction,
    bool DatedTermsScenario)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal?[]? MarketState { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal?[]? RelativeVolatility { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal?[]? ClosedBarActivity { get; init; }
}
public sealed record NativeEurOpportunity(long At,string Symbol,string Family,int Side,
    decimal Units,decimal GrossTargetEur,decimal GrossRiskEur,decimal KnownRoundTripCostEur,
    decimal? NextManagementFundingCeilingEur,decimal? CurrentMarginEstimateEur,
    decimal? ReservedRiskEur,decimal? HeldMarginEur,decimal? PendingMarginEur,
    decimal? EquityEur,NativeEurPayoff? Payoff,string Decision)
{
    public decimal? ConditionalNetAtTargetEur { get; init; }
    public decimal? ConditionalNetRewardRisk { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? DisplacedAlternativeEur { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? ProtectiveStop { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? PriceTarget { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeEurDecisionContext? Context { get; init; }
}

public sealed record NativeEurCalibrationOutcome(string PositionId,string Family,int Side,
    long ClosedAt,long AvailableAt,decimal GrossEur,decimal NetEur,decimal RiskEur)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeEconomicPathEvidence? PathEvidence { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeEurDecisionContext? Context { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public long? DecisionAt { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? EconomicManagement { get; init; }
}
public sealed record NativeEurCalibration(long ObservationThrough,string LedgerEventChainSha256,
    NativeEurCalibrationOutcome[] Outcomes)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? FundingScenarioId { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? OpportunitySchema { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? DevelopmentGeometry { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public bool OpportunityEpisodeLabels { get; init; }
}
public sealed record Ucp1EurDecisionActivity(long At,int Opportunities,int Admitted,
    IReadOnlyDictionary<string,int> CandidateDecisions);

public sealed partial class NativeUnifiedPortfolioEngine
{
    public const string EurFirst="EUR_FIRST";
    public const string EurRank="EUR_RANK";
    public const string EurContextRank="EUR_RANK_CONTEXT";
    public const string EurCash="EUR_CASH";

    sealed record EurCandidate(Ucp1DecisionSignal Signal,Ucp1MarketFrame Market,
        NativeIntegratedPlan Geometry,NativeEurOpportunity Receipt);
    readonly Dictionary<(string Family,int Side),List<NativeEurCalibrationOutcome>> eurHistory=new();
    readonly List<NativeEurOpportunity> eurOpportunities=new();
    readonly List<Ucp1EurDecisionActivity> eurDecisionActivity=new();
    internal Ucp1EurDecisionActivity[] EurDecisionActivity => eurDecisionActivity.ToArray();
    NativeEurCalibration? eurCalibration;
    readonly Dictionary<(string Symbol,string Family,int Side,int? Regime),NativeCausalManagementSelection.Choice> eurManagementChoices=new();
    // Normalized daily statistics are invariant across candidate volumes and
    // executable fee schedules within one frozen causal calibration.
    readonly Dictionary<(string Symbol,string? AssetClass,string Family,int Side,int? Regime,int? Fast,int? CostBand),NativeEurPayoff?> eurCenteredPayoffs=new();
    readonly Dictionary<(string Symbol,string Family,int Side,decimal Cost),(long At,NativeEurPayoff? Payoff)> eurPathPayoffs=new();
    NativeEurAdaptiveEstimator? adaptivePayoff;
    sealed record EurRealizedForecastError(string Symbol,string Family,int Side,long AvailableAt,decimal GrossR,decimal NetR);
    readonly Dictionary<(string Symbol,string Family,int Side),List<EurRealizedForecastError>> eurRealizedErrors=new();

    void RememberEurForecastError(EurRealizedForecastError error)
    {
        var key=(error.Symbol,error.Family,error.Side);
        if(!eurRealizedErrors.TryGetValue(key,out var errors))eurRealizedErrors.Add(key,errors=new());
        errors.Add(error);
    }

    internal object? AdaptiveFitReceipt()=>adaptivePayoff?.Receipt();
    readonly Dictionary<(string Family,int Side),(NativeCompleteDistribution Gross,NativeCompleteDistribution Net)> localEurPayoff=new();
    sealed record EurPairedCalibrationState(string Family,int Side,NativeCompleteResidual?[] Residuals);
    Dictionary<(string Family,int Side),(NativeCompleteDistributionPair Distribution,NativeCompleteResidual?[] Residuals)> pairedEurPayoff=new();
    static readonly bool UsePairedDistribution=Environment.GetEnvironmentVariable("MXM_ECONOMIC_PAIRED_DISTRIBUTION")=="1";
    public long LastObservationAt=>previousClock;
    public string PolicyName=>policy;

    void VerifyEurDevelopmentProfile(NativeEurDevelopmentProfile? options)
    {
        if(options is null)return;
        if(!IsEurGeneral)throw new ArgumentException("EUR_PROFILE_REQUIRES_GENERAL_POLICY");
        options.Verify();
    }

    decimal ReservedEurRisk(decimal executableRisk,decimal debit)
        =>executableRisk*(eurDevelopmentProfile?.StopReserveMultiplier??1m)+debit;

    // The native platform computes margin inside the callback. Consecutive
    // observed grid slots can have different real completion timestamps.
    internal static bool EurFrameFollows(Ucp1MarketFrame frame,long earlier,long at)
        =>frame.EurNativeClock? (at-15_000L)/300_000L-(earlier-15_000L)/300_000L<=1:
            at-earlier<=300_000L;

    void RememberEurOutcome(Ucp1Episode trip,Ucp1ReconciledEpisode reconciled)
    {
        var evidence=reconciled.Evidence;
        if(evidence is not {ClosedGrossEur:decimal gross,ClosedNetEur:decimal net,ReservedRiskEur:>0m})return;
        if(IsEurRank&&eurCalibration is not null)
        {
            if(eurDevelopmentProfile is {UseRealizedForecastFeedback:true} && trip.EconomicEntry is { } entry &&
                eurOpportunities.FindLast(o=>o.At==entry.DecisionAt && o.Symbol==trip.Symbol && o.Family==trip.Family &&
                    o.Side==trip.Side && o.ReservedRiskEur is >0m && o.Payoff is not null &&
                    (eurDevelopmentProfile.UsePredictiveCalibration!=true || o.Decision is "LONG_PENDING" or "SHORT_PENDING")) is { } admission)
            {
                decimal realizedRisk=eurDevelopmentProfile.UsePredictiveCalibration?admission.ReservedRiskEur!.Value:evidence.ReservedRiskEur;
                RememberEurForecastError(new(trip.Symbol,trip.Family,trip.Side,reconciled.AvailableAt,
                    gross/realizedRisk-admission.Payoff!.GrossMeanEur/admission.ReservedRiskEur!.Value,
                    net/realizedRisk-admission.Payoff.NetMeanEur/admission.ReservedRiskEur.Value));
            }
            return;
        }
        AddEurOutcome(new(trip.PositionId,trip.Family,trip.Side,trip.CloseAt,reconciled.AvailableAt,
            gross,net,evidence.ReservedRiskEur)
            {Context=trip.EurContext,DecisionAt=ModelsNativeStops?trip.EconomicEntry?.DecisionAt:null,
                PathEvidence=eurDevelopmentProfile?.CaptureOpportunityPathEvidence==true&&!trip.CrossedUnknownHistory
                    ?new(Math.Max(0m,trip.SampledMfeEur)/evidence.ReservedRiskEur,
                        Math.Max(0m,-trip.SampledMaeEur)/evidence.ReservedRiskEur,
                        trip.ExitReason.Contains("TARGET",StringComparison.Ordinal)?1m:0m,
                        trip.ExitReason.Contains("STOP",StringComparison.Ordinal)?0m:1m,
                        (trip.CloseAt-trip.OpenAt)/60000m):null});
    }

    void AddEurOutcome(NativeEurCalibrationOutcome outcome)
    {
        var key=(outcome.Family,outcome.Side);
        if(!eurHistory.TryGetValue(key,out var history))eurHistory.Add(key,history=new());
        history.Add(outcome);
    }

    public void CalibrateEurRankFrom(NativeUnifiedPortfolioEngine first)
    {
        ArgumentNullException.ThrowIfNull(first);
        LoadEurCalibration(first.ExportEurCalibration());
    }

    public NativeEurCalibration ExportEurCalibration()
    {
        if(policy is not (EurFirst or EurGeneralProbe)||previousClock<=0)
            throw new ArgumentException("EUR_CALIBRATION_REQUIRES_COMPLETED_FIRST_LEDGER_BEFORE_CONFIRMATION");
        var outcomes=eurHistory.Values.SelectMany(rows=>rows)
            .OrderBy(o=>o.ClosedAt).ThenBy(o=>o.PositionId,StringComparer.Ordinal).ToArray();
        return new(previousClock,ModelSummary.EventChainHash,outcomes) {FundingScenarioId=FundingScenarioId,
            OpportunitySchema=IsEurGeneral?EurGeneralSchema:null,
            DevelopmentGeometry=eurDevelopmentProfile?.GeometryIdentity};
    }

    public void LoadEurCalibration(NativeEurCalibration calibration)
    {
        if(previousClock!=-1||eurCalibration is not null)
            throw new ArgumentException("EUR_CALIBRATION_REQUIRES_NEW_COMPARISON_BOOK");
        RestoreEurCalibration(calibration);
    }

    public void UpdateEurResearchCalibration(NativeEurCalibration calibration)
    {
        if(eurDevelopmentProfile is null||eurCalibration is null||
            calibration.ObservationThrough<=eurCalibration.ObservationThrough||
            calibration.ObservationThrough>previousClock)
            throw new ArgumentException("EUR_RECALIBRATION_MUST_ADVANCE_CAUSALLY_ON_SAME_BOOK");
        RestoreEurCalibration(calibration);
    }

    void RestoreEurCalibration(NativeEurCalibration calibration,EurPairedCalibrationState[]? restored=null)
    {
        using var calibrationProfile=NativeEconomicProfiler.Measure("eur.restore_calibration");
        if(!IsEurRank||calibration.FundingScenarioId!=FundingScenarioId||calibration.ObservationThrough<=0||
            calibration.OpportunitySchema!=(IsEurGeneral?EurGeneralSchema:null)||
            calibration.DevelopmentGeometry!=eurDevelopmentProfile?.GeometryIdentity||
            calibration.OpportunityEpisodeLabels!=(eurDevelopmentProfile?.LearnFromOpportunityEpisodes??false)||
            (IsEurGeneral&&calibration.Outcomes.Any(x=>x.Context?.MarketState is not { Length: GeneralStateSize }))||
            calibration.LedgerEventChainSha256 is not {Length:64}||
            !calibration.LedgerEventChainSha256.All(Uri.IsHexDigit)||
            calibration.Outcomes.Select(o=>o.PositionId).Distinct(StringComparer.Ordinal)
                .Count()!=calibration.Outcomes.Length||
            calibration.Outcomes.Any(o=>o.AvailableAt>calibration.ObservationThrough||
                eurDevelopmentProfile?.SelectEconomicManagementCausally==true&&
                    o.EconomicManagement is not ("TRANSITION_VALUE" or NativeEconomicMechanisms.MonetaryReduce)||
                o.ClosedAt<=0||o.AvailableAt<o.ClosedAt||o.RiskEur<=0m||o.Side is not (-1 or 1)||
                o.DecisionAt is long decision&&(decision<=0L||decision>=o.ClosedAt)))
            throw new ArgumentException("EUR_CALIBRATION_INVALID_CAUSAL_OUTCOME");
        eurHistory.Clear();
        eurManagementChoices.Clear();
        eurCenteredPayoffs.Clear();eurPathPayoffs.Clear();
        eurCalibration=calibration;
        foreach(var outcome in calibration.Outcomes)AddEurOutcome(outcome);
        if(eurDevelopmentProfile is {UseAdaptivePayoff:true} adaptive)
        {
            adaptivePayoff=NativeEurAdaptiveEstimator.Fit(calibration,adaptive.UseExtendedLocalPayoff,adaptive.UsePredictiveCalibration,adaptive.UseEconomicEstimatorObjective,adaptive.UseSelectionAwarePredictiveGrid,adaptive.UseForecastBandCalibration,adaptive.CaptureClosedBarActivity);
            return;
        }
        if(eurDevelopmentProfile is { UseRecoveredLocalPayoff:true } profile)
        {
            localEurPayoff.Clear();
            var previous=pairedEurPayoff;
            pairedEurPayoff=new();
            var saved=restored?.ToDictionary(x=>(x.Family,x.Side));
            foreach(var (key,history) in eurHistory)
            {
                var features=history.Where(o=>o.DecisionAt.HasValue)
                    .Select(o=>(Outcome:o,State:LocalEurPayoffFeatures(o.Context,profile.UseExtendedLocalPayoff)))
                    .Where(x=>x.State is not null).ToArray();
                NativeCompleteDistribution Build(Func<NativeEurCalibrationOutcome,decimal> value)
                {
                    var samples=features.Select(x=>new NativeCompleteSample(x.Outcome.Context!.Symbol,
                        x.Outcome.DecisionAt!.Value,x.Outcome.AvailableAt,x.State!,value(x.Outcome)/x.Outcome.RiskEur)
                        {AssetClass=profile.UseExtendedLocalPayoff?x.Outcome.Context!.AssetClass:null}).ToArray();
                    return new NativeCompleteDistribution(samples,WithoutResidence:false)
                        {MaskedEconomicContext=profile.UseExtendedLocalPayoff};
                }
                NativeCompleteDistribution Fit(string component,Func<NativeEurCalibrationOutcome,decimal> value)
                {
                    using var fitProfile=NativeEconomicProfiler.Measure(component);
                    var model=Build(value);
                    return model.Calibrate(model.Samples);
                }
                if(UsePairedDistribution)
                {
                    using var pairedProfile=NativeEconomicProfiler.Measure("eur.calibrate_pair");
                    var model=new NativeCompleteDistributionPair(Build(o=>o.GrossEur),Build(o=>o.NetEur));
                    var prefix=Array.Empty<NativeCompleteResidual?>();
                    if(saved is not null)
                    {
                        if(!saved.Remove(key,out var frozen)||frozen.Residuals.Length!=model.Gross.Samples.Length)
                            throw new ArgumentException("EUR_CHECKPOINT_CALIBRATION_GROUP");
                        prefix=frozen.Residuals;
                    }
                    else if(previous.TryGetValue(key,out var prior)&&model.CanReuseCalibration(prior.Distribution))
                        prefix=prior.Residuals;
                    var pair=model.Calibrate(prefix,out var residuals);
                    pairedEurPayoff.Add(key,(pair,residuals));
                    localEurPayoff.Add(key,(pair.Gross,pair.Net));
                }
                else localEurPayoff.Add(key,(Fit("eur.calibrate_gross",o=>o.GrossEur),Fit("eur.calibrate_net",o=>o.NetEur)));
            }
            if(saved is {Count:>0})throw new ArgumentException("EUR_CHECKPOINT_CALIBRATION_GROUP");
        }
    }

    // Use common completed M5/M15 features from the registered state. A row
    // with absent features remains outside this local estimator's sample.
    static decimal[]? LocalEurPayoffFeatures(NativeEurDecisionContext? context,bool extended=false)
    {
        if(context?.MarketState is not { Length:GeneralStateSize } state)return null;
        if(!extended)
            return state[2] is decimal move5 && state[3] is decimal range5 &&
                state[4] is decimal move15 && state[5] is decimal range15
                ?new[]{move5,range5,move15,range15}:null;
        if(!state.Any(v=>v.HasValue))return null;
        // All already-closed timeframe windows plus the existing M1 volume and
        // aligned peer-H1 state. Session is circular; cost/risk is bounded.
        // Shared-book committed margin is deliberately not a predictor of an
        // isolated episode's payoff; allocation is handled by the common book.
        double phase=2d*Math.PI*context.UtcMinute/1440d;
        decimal cost=Math.Max(0m,context.CostRiskFraction);
        var raw=state.Concat(new decimal?[]{(decimal)Math.Sin(phase),(decimal)Math.Cos(phase),
            cost/(1m+cost)}).ToArray();
        return raw.SelectMany(v=>new[]{v??0m,v.HasValue?1m:0m}).ToArray();
    }

    NativeEurPayoff? RecoveredLocalPayoff(string family,int side,long at,decimal risk,decimal cost,
        NativeEurDecisionContext? context,Action<string>? diagnostic)
    {
        using var payoffProfile=NativeEconomicProfiler.Measure("eur.local_payoff");
        bool extended=eurDevelopmentProfile?.UseExtendedLocalPayoff==true;
        if(LocalEurPayoffFeatures(context,extended) is not { } features)
        {diagnostic?.Invoke("LOCAL_CONTEXT_MISSING");return null;}
        if(!localEurPayoff.TryGetValue((family,side),out var model))
        {diagnostic?.Invoke("NO_FAMILY_DIRECTION_HISTORY");return null;}
        NativeCompletePrediction? gross,net;
        (decimal Minimum,decimal Maximum) range;
        if(pairedEurPayoff.TryGetValue((family,side),out var pair))
        {
            using var pairProfile=NativeEconomicProfiler.Measure("eur.predict_pair");
            (gross,net)=pair.Distribution.Predict(features,at,risk,out range,context?.Symbol,context?.AssetClass);
        }
        else
        {
            using (NativeEconomicProfiler.Measure("eur.predict_gross"))
                gross=model.Gross.Predict(features,at,risk,out _,context?.Symbol,context?.AssetClass);
            using (NativeEconomicProfiler.Measure("eur.predict_net"))
                net=model.Net.Predict(features,at,risk,out range,context?.Symbol,context?.AssetClass);
        }
        if(gross is null||net is null)
        {diagnostic?.Invoke("LOCAL_DISTRIBUTION_SUPPORT");return null;}
        decimal netLower=Math.Min(net.Lower,gross.Lower-cost);
        diagnostic?.Invoke(gross.Lower<=0m?"LOCAL_GROSS_LOWER_NONPOSITIVE":net.Lower<=0m?"LOCAL_NET_LOWER_NONPOSITIVE":
            netLower<=0m?"CURRENT_COST_FLOOR":"PAYOFF_PASSES");
        return new NativeEurPayoff(net.Observations,net.Days,gross.Mean,gross.Lower,
            Math.Min(net.Mean,gross.Mean-cost),netLower,net.PositiveProbability,range.Minimum,range.Maximum)
            {Cohort=extended?"EXTENDED_MASKED_CONTEXT_LOCAL_DISTRIBUTION":"RECOVERED_LOCAL_COMPLETE_POSITION_DISTRIBUTION"};
    }

    // Compare CASH against paired, settled cash outcomes at candidate risk.
    // The currently evidenced closing cost can make a historical outcome worse.
    // Taking the smaller NET avoids crediting a cheaper historical tariff and
    // avoids charging the same cost twice. Use day means as the sample unit.
    NativeCausalManagementSelection.Choice CausalManagement(string family,int side,NativeEurDecisionContext context,long at)
    {
        var profile=eurDevelopmentProfile!;
        int? regime=context.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1)?.Direction;
        var key=(context.Symbol,family,side,regime);
        // Ranking books retain a frozen matured calibration between updates.
        // This derived cache is discarded on every update or checkpoint restore.
        bool cache=eurCalibration is not null&&eurCalibration.ObservationThrough<at;
        if(cache&&eurManagementChoices.TryGetValue(key,out var prior))return prior;
        var rows=eurHistory.GetValueOrDefault((family,side))??new List<NativeEurCalibrationOutcome>();
        var choice=NativeEconomicMechanisms.SelectManagement(rows,family,side,context,at,
            profile.MinimumEpisodes,profile.MinimumDays,profile.DayPenalty);
        if(cache)eurManagementChoices[key]=choice;
        return choice;
    }

    NativeEurPayoff? CompetitiveCandidatePayoff(Ucp1MarketFrame market,long at,string family,int side,
        decimal units,decimal risk,decimal cost,NativeEurDecisionContext? context,Action<string>? diagnostic=null,
        string? managementOverride=null)
    {
        if(eurDevelopmentProfile is {Pav1CompetitiveForecast:{ } mode} profile&&family==NativeEconomicMechanisms.Transition)
        {
            var direct=NativeEconomicMechanisms.TransitionPayoff(market,at,side,units,cost,
                profile.EconomicGeometryTimeframe,profile.Pav1TransitionBars);
            diagnostic?.Invoke(direct is {GrossLowerEur:>0m,NetLowerEur:>0m}
                ?"PAV1_COMPETITIVE_DIRECT_POSITIVE":"PAV1_COMPETITIVE_DIRECT_UNSUPPORTED_OR_NONPOSITIVE");
            if(mode=="DIRECT")return direct;
            var empirical=EurPayoff(family,side,risk,cost,context,diagnostic,at,managementOverride);
            return NativeCenteredLifecycle.Corroborate(empirical,direct);
        }
        return EurPayoff(family,side,risk,cost,context,diagnostic,at,managementOverride);
    }

    internal NativeEurPayoff? EurPayoff(string family,int side,decimal candidateRiskEur,decimal currentCostFloorEur,
        NativeEurDecisionContext? target=null,Action<string>? diagnostic=null,long? decisionAt=null,string? managementOverride=null)
    {
        if(eurDevelopmentProfile is {UseAdaptivePayoff:true} && decisionAt is long adaptiveClock)
        {
            var feedback=eurDevelopmentProfile is {UsePredictiveCalibration:true,UseRealizedForecastFeedback:true}&&target is not null
                ?RealizedForecastAdjustment(target.Symbol,family,side,adaptiveClock):null;
            var estimate=adaptivePayoff?.Payoff(family,side,target,adaptiveClock,candidateRiskEur,currentCostFloorEur,feedback);
            if(estimate is not null && target is not null && eurDevelopmentProfile.UseRealizedForecastFeedback&&!eurDevelopmentProfile.UsePredictiveCalibration)
                estimate=ApplyRealizedForecastErrors(estimate,target.Symbol,family,side,adaptiveClock,candidateRiskEur);
            diagnostic?.Invoke(estimate is null?"ADAPTIVE_INSUFFICIENT_SUPPORT":
                estimate.GrossLowerEur<=0m?"ADAPTIVE_GROSS_LOWER_NONPOSITIVE":
                estimate.NetLowerEur<=0m?"ADAPTIVE_NET_LOWER_NONPOSITIVE":"ADAPTIVE_PAYOFF_PASSES");
            return estimate;
        }
        if(eurDevelopmentProfile is {EconomicMechanism:NativeEconomicMechanisms.Scored} scored&&
            decisionAt is long scoredAt&&target is not null)
        {
            IEnumerable<NativeEurCalibrationOutcome> scoredHistory=eurHistory.GetValueOrDefault((family,side))??new List<NativeEurCalibrationOutcome>();
            if(scored.SelectEconomicManagementCausally)
            {
                string management=managementOverride??CausalManagement(family,side,target,scoredAt).Management;
                scoredHistory=scoredHistory.Where(x=>x.EconomicManagement==management);
            }
            if(scored.LifecycleEstimator is { } estimator)
            {
                if(candidateRiskEur<=0m||currentCostFloorEur<0m)return null;
                if(estimator.StartsWith("DISTRIBUTION_",StringComparison.Ordinal))
                {
                    var distributionKey=(target.Symbol,family,side,target.CostRiskFraction);
                    if(!eurPathPayoffs.TryGetValue(distributionKey,out var cached)||cached.At!=scoredAt)
                    {
                        cached=(scoredAt,NativeDistributionLifecycle.Estimate(scoredHistory,family,side,target,scoredAt,
                            estimator[13..],scored.MinimumEpisodes,scored.MinimumDays,scored.DayPenalty,diagnostic));
                        eurPathPayoffs[distributionKey]=cached;
                    }
                    return NativeCenteredLifecycle.Reprice(cached.Payoff,candidateRiskEur,currentCostFloorEur,diagnostic);
                }
                int? regime=target.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1)?.Direction;
                bool matched=estimator=="CENTERED_COST_CONTEXT";
                int? fast=matched?target.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.M15)?.Direction:null;
                int? costBand=matched?NativeCenteredLifecycle.CostBand(target.CostRiskFraction):null;
                var key=(target.Symbol,target.AssetClass,family,side,regime,fast,costBand);
                bool cache=eurCalibration is not null&&eurCalibration.ObservationThrough<scoredAt;
                NativeEurPayoff? normalized;
                if(!cache||!eurCenteredPayoffs.TryGetValue(key,out normalized))
                {
                    normalized=NativeCenteredLifecycle.Estimate(scoredHistory,family,side,target,scoredAt,
                        1m,0m,scored.MinimumEpisodes,scored.MinimumDays,scored.DayPenalty,
                        estimator!="CENTERED_LOCAL",costMatched:matched,halfLifeDays:scored.LifecycleRecencyHalfLifeDays,
                        captureRecencyEvidence:scored.CaptureLifecycleRecencyEvidence);
                    if(cache)eurCenteredPayoffs[key]=normalized;
                }
                if(scored.CaptureLifecycleRecencyEvidence&&normalized is {LatestEligibleObservationAt:long newest,EffectiveObservationDays:decimal effective})
                {
                    long age=(scoredAt-newest)/86_400_000L;
                    string ageBand=age<2?"LT2":age<7?"2_6":age<14?"7_13":age<28?"14_27":"GE28";
                    string supportBand=effective<5m?"LT5":effective<10m?"5_9":effective<20m?"10_19":"GE20";
                    diagnostic?.Invoke("RECENCY_ABSOLUTE_AGE_DAYS_"+ageBand);
                    diagnostic?.Invoke("RECENCY_EFFECTIVE_DAY_BAND_"+supportBand);
                }
                return NativeCenteredLifecycle.Reprice(normalized,candidateRiskEur,currentCostFloorEur,diagnostic);
            }
            return NativeEconomicMechanisms.LifecyclePayoff(scoredHistory,family,side,target,
                scoredAt,candidateRiskEur,currentCostFloorEur,scored.MinimumEpisodes,scored.MinimumDays,scored.DayPenalty);
        }
        if(eurDevelopmentProfile is { UseRecoveredLocalPayoff:true } && decisionAt is long at)
            return RecoveredLocalPayoff(family,side,at,candidateRiskEur,currentCostFloorEur,target,diagnostic);
        int minEpisodes=eurDevelopmentProfile?.MinimumEpisodes??20;
        int minDays=eurDevelopmentProfile?.MinimumDays??3;
        if(!eurHistory.TryGetValue((family,side),out var history))
        {diagnostic?.Invoke("NO_FAMILY_DIRECTION_HISTORY");return null;}
        if(history.Count<minEpisodes)
        {diagnostic?.Invoke("INSUFFICIENT_EPISODES");return null;}
        NativeEurCalibrationOutcome[] pool=history.ToArray();
        string? cohort=null;
        if(target is not null)
        {
            var sameSymbol=pool.Where(x=>x.Context?.Symbol==target.Symbol).ToArray();
            var sameClass=pool.Where(x=>target.AssetClass is not null&&x.Context?.AssetClass==target.AssetClass).ToArray();
            bool Supported(NativeEurCalibrationOutcome[] rows)
                =>rows.Length>=minEpisodes&&rows.Select(r=>r.ClosedAt/86400000L).Distinct().Take(minDays).Count()==minDays;
            if(Supported(sameSymbol)){pool=sameSymbol;cohort="SYMBOL";}
            else if(Supported(sameClass)){pool=sameClass;cohort="OFFICIAL_CLASS";}
            else cohort="POOLED_FAMILY_DIRECTION";
            diagnostic?.Invoke("TRANSFER_"+cohort);
        }
        var samples=pool.Select(x=>
        {
            decimal scale=candidateRiskEur/x.RiskEur;
            decimal gross=x.GrossEur*scale;
            return (CloseDay:x.ClosedAt/86400000L,Gross:gross,
                HistoricalNet:x.NetEur*scale,Net:Math.Min(x.NetEur*scale,gross-currentCostFloorEur),
                Weight:target is not null&&x.Context is { } observed?EurAffinity(target,observed):1m);
        }).ToArray();
        var days=samples.GroupBy(x=>x.CloseDay).OrderBy(g=>g.Key)
            .Select(g=> (Gross:g.Sum(x=>x.Gross*x.Weight)/g.Sum(x=>x.Weight),
                Net:g.Sum(x=>x.Net*x.Weight)/g.Sum(x=>x.Weight))).ToArray();
        if(days.Length<minDays)
        {diagnostic?.Invoke("INSUFFICIENT_OBSERVATION_DAYS");return null;}
        decimal grossMean=days.Average(x=>x.Gross),netMean=days.Average(x=>x.Net);
        // The existing program's one-sided 1.645 standard-error penalty,
        // applied separately to the day-block series. Diagnostic only.
        decimal Lower(decimal mean,IEnumerable<decimal> sample)
            =>mean-(eurDevelopmentProfile?.DayPenalty??1.645m)*(decimal)Math.Sqrt(sample.Sum(x=>Math.Pow((double)(x-mean),2))/
                ((double)days.Length*(days.Length-1)));
        decimal grossLower=Lower(grossMean,days.Select(x=>x.Gross));
        decimal netLower=Lower(netMean,days.Select(x=>x.Net));
        if(diagnostic is not null)
        {
            if(grossMean<=0m)diagnostic("GROSS_MEAN_NONPOSITIVE");
            else if(grossLower<=0m)diagnostic("GROSS_DAY_UNCERTAINTY");

            if(netLower<=0m)
            {
                var historicalDays=samples.GroupBy(x=>x.CloseDay).OrderBy(g=>g.Key)
                    .Select(g=>g.Sum(x=>x.HistoricalNet*x.Weight)/g.Sum(x=>x.Weight)).ToArray();
                decimal historicalMean=historicalDays.Average();
                if(historicalMean<=0m)diagnostic("HISTORICAL_NET_MEAN_NONPOSITIVE");
                else if(Lower(historicalMean,historicalDays)<=0m)diagnostic("HISTORICAL_NET_DAY_UNCERTAINTY");
                else diagnostic("CURRENT_COST_FLOOR");
            }
            if(grossLower>0m&&netLower>0m)diagnostic("PAYOFF_PASSES");
        }
        return new NativeEurPayoff(pool.Length,days.Length,grossMean,grossLower,netMean,netLower,
            (decimal)samples.Count(x=>x.Net>0m)/samples.Length,samples.Min(x=>x.Net),samples.Max(x=>x.Net)) { Cohort=cohort };
    }

    NativeEurForecastAdjustment? RealizedForecastAdjustment(string symbol,string family,int side,long at)
    {
        const long day=86_400_000L;
        if(!eurRealizedErrors.TryGetValue((symbol,family,side),out var history))return null;
        var errors=history.Where(e=>e.AvailableAt<at).GroupBy(e=>e.AvailableAt/day)
            .Select(g=>(Weight:Math.Pow(.5,(at/day-g.Key)/7d),Gross:(double)g.Average(e=>e.GrossR),
                Net:(double)g.Average(e=>e.NetR))).ToArray();
        if(errors.Length==0)return null;
        double mass=3d+errors.Sum(e=>e.Weight);
        double gross=errors.Sum(e=>e.Weight*e.Gross)/mass,net=errors.Sum(e=>e.Weight*e.Net)/mass;
        // Three prior zero-error day units shrink signed feedback; the added
        // uncertainty is not treated as independent of the calibration error.
        double Sem(Func<(double Weight,double Gross,double Net),double> value,double mean)
            =>Math.Sqrt((3d*mean*mean+errors.Sum(e=>e.Weight*Math.Pow(value(e)-mean,2)))/mass*
                (3d+errors.Sum(e=>e.Weight*e.Weight))/(mass*mass));
        return new(errors.Length,gross,net,Sem(e=>e.Gross,gross),Sem(e=>e.Net,net));
    }

    NativeEurPayoff ApplyRealizedForecastErrors(NativeEurPayoff estimate,string symbol,string family,int side,
        long at,decimal risk)
    {
        const long day=86_400_000L;
        if(!eurRealizedErrors.TryGetValue((symbol,family,side),out var history))return estimate;
        var errors=history.Where(e=>e.AvailableAt<at)
            .GroupBy(e=>e.AvailableAt/day).Select(g=>(Weight:(decimal)Math.Pow(.5,(at/day-g.Key)/7d),
                Gross:g.Average(e=>e.GrossR),Net:g.Average(e=>e.NetR))).ToArray();
        decimal mass=3m+errors.Sum(e=>e.Weight);
        decimal gross=Math.Min(0m,errors.Sum(e=>e.Weight*e.Gross)/mass)*risk;
        decimal net=Math.Min(0m,errors.Sum(e=>e.Weight*e.Net)/mass)*risk;
        return estimate with {GrossLowerEur=estimate.GrossLowerEur+gross,NetLowerEur=estimate.NetLowerEur+Math.Min(gross,net)};
    }

    static decimal EurAffinity(NativeEurDecisionContext target,NativeEurDecisionContext observed)
    {
        var paired=target.ClosedStates.Join(observed.ClosedStates,x=>x.Timeframe,x=>x.Timeframe,(a,b)=>(a,b)).ToArray();
        int minutes=Math.Abs(target.UtcMinute-observed.UtcMinute);
        decimal clock=1m-Math.Min(minutes,1440-minutes)/720m;
        decimal capital=1m-Math.Min(1m,Math.Abs(target.CommittedMarginFraction-observed.CommittedMarginFraction));
        decimal cost=1m-Math.Min(1m,Math.Abs(target.CostRiskFraction-observed.CostRiskFraction));
        decimal affinity=1m+clock+capital+cost+paired.Sum(x=>(x.a.Direction==x.b.Direction?1m:0m)+
            (x.a.AboveRecentRange==x.b.AboveRecentRange?1m:0m));
        int terms=4+2*paired.Length;
        if(target.MarketState is { } current && observed.MarketState is { } history)
            for(int i=0;i<current.Length;i++)
                if(current[i] is decimal a&&history[i] is decimal b)
                {
                    affinity+=1m-Math.Min(1m,Math.Abs(a-b)/2m);
                    terms++;
                }
        return affinity/terms;
    }

    static NativeEurDecisionContext? DescribeEurContext(Ucp1MarketFrame market,long at,int side,
        decimal committed,decimal? equity,decimal? risk,decimal cost)
    {
        if(market.ClosedBars is not { } context || context.DecisionAt!=at)return null;
        var states=context.Windows.Where(w=>w.Ready&&w.Bars.Length>=2&&w.Bars.All(b=>b.CloseAt<at))
            .Select(w=>
            {
                var latest=w.Bars[^1];
                return new NativeEurBarState(w.Timeframe,Math.Sign(side*(latest.Close-w.Bars[0].Close)),
                    latest.High-latest.Low>w.Bars.Take(w.Bars.Length-1).Average(b=>b.High-b.Low));
            }).ToArray();
        return new(market.Symbol,market.OfficialAssetClass,(int)(at/60_000L%1440),states,
            equity is >0m?committed/equity.Value:0m,risk is >0m?cost/risk.Value:0m,market.EurDatedMarginScenario);
    }

    internal static NativeEurMarginObservation? EurMargin(Ucp1MarketFrame market,int side,decimal units,long at)
    {
        var contract=market.Contract;
        if(contract.VolumeStepUnits<=0m||units<contract.MinimumUnits||units>contract.MaximumUnits||
            (units-contract.MinimumUnits)%contract.VolumeStepUnits!=0m)return null;
        var offers=market.EurMargins?.Where(x=>x.Side==side&&x.Units==units&&x.MarginEur>0m&&
            x.ObservedAt>=contract.ObservedAtUtcMs&&x.ObservedAt<=at&&
            (market.EurDatedMarginScenario||at-x.ObservedAt<=60_000L)&&
            x.SourceSha256 is {Length:64}&&x.SourceSha256.All(Uri.IsHexDigit)&&
            x.MarginEur-market.Quote.MarginPerUnit*units<=.0000000000000001m).Take(2).ToArray();
        return offers is {Length:1}?offers[0]:null;
    }

    internal static string EurRejectedCapital(string status,LedgerSummary book,NativeFundingCapital capital)
        =>status=="MISSING_CURRENT_LIQUIDATION_MARK"&&book.LiquidationEquityEur.HasValue&&
            book.UsedMarginEur.HasValue&&(capital.ScenarioId is null?capital.OutstandingDebitCeilingEur:capital.ConditionalUnmodeledDebitCeilingEur) is null
            ?"WAIT_UNBOUNDED_PORTFOLIO_FUNDING":"WAIT_"+status;

    Ucp1FrameResult AdvanceEur(long at,Ucp1Frame frame,
        List<(Ucp1DecisionSignal Signal,Ucp1MarketFrame Frame)> options)
    {
        var book=model.Ledger.Summary(at);
        var capital=Cpe1FundingCapital(book,frame)!;
        var held=Cpe1Commitments(false,frame);
        var pending=Cpe1Commitments(true,frame).ToList();
        var choices=new List<EurCandidate>();
        int admittedBefore=admitted;
        NativeEurCalibrationOutcome[]? maturedCash=null;
        var activity=CaptureEurDiagnostics?new Dictionary<string,int>(StringComparer.Ordinal):null;
        void ScoreDiagnostic(string state) => Count("EUR_PAYOFF_"+state);
        void Trace(NativeEurOpportunity o,string state)
        {
            Count("EUR_"+state);
            if(activity is not null)activity[state]=activity.GetValueOrDefault(state)+1;
            if(!researchFork&&(eurDevelopmentProfile is null||state is "LONG_PENDING" or "SHORT_PENDING"))eurOpportunities.Add(o with {Decision=state,
                HeldMarginEur=capital.HeldMarginEur,PendingMarginEur=pending.Sum(x=>x.MarginEur)});
        }
        foreach(var (s,market) in options.OrderBy(x=>x.Frame.Symbol,StringComparer.Ordinal)
            .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal).ThenBy(x=>x.Signal.Side))
        {
            if(!Cpe1Usable(market,at)||EurLevels(s,market) is not { } levels)continue;
            var marketState=IsEurGeneral?DescribeGeneralState(market,frame,s.Side):null;
            var volatility=eurDevelopmentProfile?.CaptureVolatilityContext==true?DescribeRelativeVolatility(market,frame.At):null;
            var activityContext=eurDevelopmentProfile?.CaptureClosedBarActivity==true?DescribeClosedBarActivity(market,frame.At,s.Side):null;
            var witnessedUnits=(market.EurMargins??Array.Empty<NativeEurMarginObservation>())
                .Where(x=>x.Side==s.Side&&x.Units>0m).Select(x=>x.Units)
                .Append(market.Contract.MinimumUnits).Distinct().OrderBy(x=>x).ToArray();
            var unitsOffered=eurDevelopmentProfile?.OptimizeTransitionNetVolume==true||
                frame.ObservationEpisodeOnly&&eurDevelopmentProfile?.OptimizeEconomicOpportunityVolume==true
                ?witnessedUnits
                :frame.ObservationEpisodeOnly&&eurDevelopmentProfile?.EconomicOpportunityVolumeIndex is int volumeIndex
                ?witnessedUnits.Skip(volumeIndex).Take(1)
                :witnessedUnits.Where(units=>(!frame.ObservationEpisodeOnly&&eurDevelopmentProfile?.MinimumContractVolumeOnly!=true)||
                    units==market.Contract.MinimumUnits).OrderByDescending(x=>x);
            foreach(var units in unitsOffered)
            {
                var q=market.Quote;
                var bracket=NativeExecutableEconomics.Bracket(q,s.Side,units,levels.Stop,levels.Target,
                    market.SlippagePerSideQuote,q.LiquidationSlippagePerSide??market.SlippagePerSideQuote);
                decimal mid=(q.Bid+q.Ask)/2m,conversion=(q.EurCredit+q.EurDebit)/2m;
                decimal grossTarget=s.Side*(levels.Target-mid)*units*conversion;
                decimal grossRisk=s.Side*(mid-levels.Stop)*units*conversion;
                decimal roundTripCost=Math.Max(0m,-NativeExecutableEconomics.EstimateNet(q,q,s.Side,
                    units,bracket.Entry,s.Side>0?q.Bid:q.Ask,
                    q.LiquidationSlippagePerSide??market.SlippagePerSideQuote));
                var margin=EurMargin(market,s.Side,units,at);
                var debit=NativePortfolioFunding.OfferDebit(market,s.Side,units,at,FundingScenarioId);
                decimal gap=0m;
                if(eurDevelopmentProfile?.ReserveObservedBarGaps==true&&market.ClosedBars is { } bars)
                {
                    var w=market.EconomicTransitionWindows?.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1&&x.Ready&&
                        x.Bars.All(b=>b.CloseAt<at))??bars.Windows.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1&&x.Ready);
                    if(w is not null)gap=w.Bars.Skip(1).Select((b,i)=>Math.Abs(b.Open-w.Bars[i].Close)).DefaultIfEmpty(0m).Max();
                }
                decimal? risk=debit is decimal knownDebit?ReservedEurRisk(bracket.RiskEur,knownDebit)+gap*units*q.EurDebit:null;
                var context=DescribeEurContext(market,at,s.Side,(capital.HeldMarginEur??0m)+pending.Sum(x=>x.MarginEur),
                    capital.ResearchAdmissionEquityEur,risk,roundTripCost);
                if(context is not null&&marketState is not null)context=context with {MarketState=marketState,RelativeVolatility=volatility,ClosedBarActivity=activityContext};
                if(CaptureEurDiagnostics&&policy==EurGeneralSelect&&context is null)ScoreDiagnostic("NO_CONTEXT");
                var payoff=risk is >0m&&(IsEurRank||eurDevelopmentProfile is null)?CompetitiveCandidatePayoff(market,at,s.Family,s.Side,units,risk.Value,roundTripCost+debit!.Value,
                    policy is EurContextRank or EurGeneralSelect?context:null,CaptureEurDiagnostics||eurDevelopmentProfile?.LifecycleEstimator is not null?ScoreDiagnostic:null):null;
                if(eurDevelopmentProfile?.EconomicMechanism==NativeEconomicMechanisms.Transition&&risk is >0m&&debit.HasValue)
                    payoff=NativeEconomicMechanisms.TransitionPayoff(market,at,s.Side,units,roundTripCost+debit.Value,
                        eurDevelopmentProfile.EconomicGeometryTimeframe,eurDevelopmentProfile.Pav1TransitionBars);
                if(eurDevelopmentProfile?.RequirePav1FastAgreement==true&&
                    NativeEconomicMechanisms.TransitionPayoff(market,at,s.Side,units,roundTripCost+(debit??0m),"M15",eurDevelopmentProfile.Pav1TransitionBars)
                        is not {GrossLowerEur:>0m,NetLowerEur:>0m})
                {Count("EUR_PAV1_M15_ADMISSION_DISAGREEMENT");continue;}
                if(eurDevelopmentProfile?.RequireMaturedCashForLargerVolume==true&&units>market.Contract.MinimumUnits)
                {
                    if(maturedCash is null)
                    {
                    var closed=CompleteModelTrips.ToDictionary(t=>t.PositionId,StringComparer.Ordinal);
                    maturedCash=ReconciledModelEpisodes.Where(e=>e.AvailableAt<at&&e.Evidence.ClosedNetEur.HasValue&&closed.ContainsKey(e.PositionId))
                        .Select(e=>
                        {
                            var trip=closed[e.PositionId];
                            return new NativeEurCalibrationOutcome(trip.PositionId,trip.Family,trip.Side,trip.CloseAt,e.AvailableAt,
                                e.Evidence.ClosedGrossEur??trip.GrossEur,e.Evidence.ClosedNetEur!.Value,
                                trip.EconomicEntry?.AdmissionReservedRiskEur??trip.EntryRiskEur)
                                {Context=trip.EurContext,DecisionAt=trip.EconomicEntry?.DecisionAt};
                        }).ToArray();
                    }
                    var fitted=context is not null&&risk is >0m?NativeEconomicMechanisms.EntryQualityPayoff(maturedCash,s.Family,s.Side,
                        context,at,risk.Value,roundTripCost+(debit??0m),eurDevelopmentProfile.MinimumEpisodes,
                        eurDevelopmentProfile.MinimumDays,eurDevelopmentProfile.DayPenalty,true):null;
                    if(fitted is not {GrossLowerEur:>0m,NetLowerEur:>0m})
                    {Count("EUR_PAV1_LARGER_VOLUME_NO_MATURED_MONETARY_EDGE");continue;}
                    if(payoff is not null)payoff=payoff with {GrossLowerEur=Math.Min(payoff.GrossLowerEur,fitted.GrossLowerEur),
                        NetLowerEur=Math.Min(payoff.NetLowerEur,fitted.NetLowerEur),Cohort="PAV1_CORROBORATED_ACTUAL_MATURED_CASH_VOLUME"};
                }
                var receipt=new NativeEurOpportunity(at,market.Symbol,s.Family,s.Side,units,grossTarget,grossRisk,
                    roundTripCost,debit,margin?.MarginEur,risk,capital.HeldMarginEur,capital.PendingOpenMarginEur,
                    capital.ResearchAdmissionEquityEur,payoff,"ASSESS")
                {
                    ConditionalNetAtTargetEur=bracket.RewardEur-debit,
                    ConditionalNetRewardRisk=risk is >0m?(bracket.RewardEur-debit)/risk:null,
                    ProtectiveStop=IsEurGeneral?levels.Stop:null,
                    PriceTarget=IsEurGeneral?levels.Target:null,
                    Context=context
                };
                string? unavailable=margin is null?"WAIT_VOLUME_MARGIN_EVIDENCE":debit is null?"WAIT_FUNDING_CEILING":
                    grossRisk<=0m||grossTarget<=0m||risk is not >0m||bracket.RewardEur<=debit.Value?"WAIT_PRICE_GEOMETRY":
                    policy is EurCash or EurGeneralCash?"WAIT_CASH":
                    capital.MaximumSampledFundingAdjustedDrawdown>=.28m?"WAIT_PORTFOLIO_DRAWDOWN":
                    (IsEurRank||eurDevelopmentProfile?.EconomicMechanism==NativeEconomicMechanisms.Transition)&&
                        payoff is not {GrossLowerEur:>0m,NetLowerEur:>0m}
                        ?"WAIT_RECONCILED_PAYOFF_EVIDENCE":null;
                if(unavailable is not null){Trace(receipt,unavailable);continue;}
                choices.Add(new(s,market,new NativeIntegratedPlan(levels.Stop,levels.Target,risk!.Value,
                    bracket.RewardEur-debit!.Value){EntrySlippage=market.SlippagePerSideQuote,GapReservePerUnitQuote=gap},receipt));
            }
        }

        void Admit(EurCandidate choice)
        {
            var s=choice.Signal;
            var market=choice.Market;
            var receipt=choice.Receipt;
            decimal units=receipt.Units, margin=market.Quote.MarginPerUnit;
            if(eurDevelopmentProfile is {SelectEconomicManagementCausally:true} actionProfile&&receipt.Context is { } context)
            {
                var selected=CausalManagement(s.Family,s.Side,context,at);
                choice=choice with {Geometry=choice.Geometry with {SelectedEconomicManagement=selected.Management}};
                Count("EUR_CAUSAL_MANAGEMENT_"+selected.Management);
            }
            string id="UCP1/"+policy+"/"+market.Symbol+"/"+s.Family+"/"+at;
            Apply(Event("REQUEST_OPEN",at,id,market.Symbol,s.Side,units,margin:margin,
                slip:market.SlippagePerSideQuote,reason:"NATIVE_CONDITIONAL_SELECTION") with
                {AvailableAt=at,CalibratedThrough=s.LastCompletedM5At,TracksLateFunding=true});
            AddPlan(id,new(id,market.Symbol,s.Family,s.Side,s.Atr,s.Equilibrium,choice.Geometry.InitialRiskEur,
                choice.Geometry.Stop,0m,0L,0m,units,0m,0m,0L,false,choice.Geometry) {EurContext=receipt.Context});
            pending.Add(new(id,market.Symbol,units,margin,choice.Geometry.InitialRiskEur,s.Family,true));
            admitted++;
            Trace(receipt,s.Side>0?"LONG_PENDING":"SHORT_PENDING");
            if(CaptureEurDiagnostics)RecordEurRiskObservation(at,"ADMISSION",frame,id);
        }
        if(policy is EurGeneralSelect or EurGeneralPooled||eurDevelopmentProfile?.OptimizeTransitionNetVolume==true||
            eurDevelopmentProfile?.AllocatePav1AtMinimumVolume==true)
            AllocateGeneralEur(frame,book,capital,held,pending,choices,Admit,Trace);
        else
        {
            IEnumerable<EurCandidate> ranked=IsEurRank?choices.OrderByDescending(x=>x.Receipt.Payoff!.NetLowerEur):
                policy==EurGeneralProbe?choices.OrderBy(x=>ProbeKey(x.Receipt),StringComparer.Ordinal):choices;
            bool optimizeVolume=frame.ObservationEpisodeOnly&&eurDevelopmentProfile?.OptimizeEconomicOpportunityVolume==true;
            if(optimizeVolume)
            {
                if(options.Count>1)throw new InvalidOperationException("EUR_OPTIMIZED_VOLUME_REQUIRES_ONE_ISOLATED_SIGNAL");
                // This is a geometric target reward/risk comparison, not a
                // learned expected NET forecast. Prefer lower risk on ties.
                ranked=choices.OrderByDescending(x=>x.Receipt.ConditionalNetRewardRisk)
                    .ThenBy(x=>x.Geometry.InitialRiskEur).ThenBy(x=>x.Receipt.Units);
            }
            foreach(var choice in ranked)
            {
                var gate=AssessEurCandidate(capital,book,held,pending,choice);
                if(!gate.IsFinanceable){Trace(choice.Receipt,EurRejectedCapital(gate.Status,book,capital));continue;}
                Admit(choice);
                if(optimizeVolume)break; // one isolated entry, never multiple volume orders
            }
        }
        if(activity is not null&&options.Count>0)eurDecisionActivity.Add(new(at,options.Count,admitted-admittedBefore,activity));
        return RecordIntegratedFrame(at,model.Ledger.Summary(at),frame);
    }

    static (decimal Stop,decimal Target)? EurLevels(Ucp1DecisionSignal signal,Ucp1MarketFrame market)
        =>signal.GeneralGeometry is { } geometry?(geometry.Stop,geometry.Target):Cpe1Levels(signal,market);

    NativePendingCapitalGate.Admission AssessEurCandidate(NativeFundingCapital capital,LedgerSummary book,
        NativePendingCapitalGate.Commitment[] held,List<NativePendingCapitalGate.Commitment> pending,
        EurCandidate choice,decimal extraRisk=0m)
    {
        var market=choice.Market;
        decimal units=choice.Receipt.Units;
        var gate=NativePendingCapitalGate.Assess(capital.ResearchAdmissionEquityEur,book.UsedMarginEur is not null,
            held,pending,new(market.Symbol,choice.Signal.Family,units,market.Contract.VolumeStepUnits,units,
                market.Quote.MarginPerUnit,choice.Geometry.InitialRiskEur/units,extraRisk));
        if(gate.IsFinanceable&&eurDevelopmentProfile?.ReserveMarginForStopRisk==true&&
            !NativePendingCapitalGate.StopAdjustedMarginFits(gate.EquityEur,gate.ReservedMarginAfterEur,gate.ReservedRiskAfterEur))
            return gate with {IsFinanceable=false,Status="PENDING_PLUS_HELD_STOP_ADJUSTED_MARGIN_CAP"};
        return gate;
    }

    NativeModelCloseInstruction? ManageFundedTarget(Ucp1Plan plan,LedgerPosition position,
        Ucp1MarketFrame market,decimal price,decimal displacement)
    {
        var geometry=plan.Integrated!;
        if(position.Side*(price-geometry.Target)<0m)return null;
        decimal minimum=market.Contract.MinimumUnits,remainder=position.Units-minimum;
        bool legal=market.Contract.VolumeStepUnits>0m&&remainder>=minimum&&
            (remainder-minimum)%market.Contract.VolumeStepUnits==0m;
        if(geometry.Reduced)return displacement<=0m?new("INTEGRATED_EUR_TARGET_CONTINUATION_ENDED",position.Units):null;
        var q=market.Quote;
        var entry=position.EntryQuote;
        decimal increment=entry is null?0m:NativeExecutableEconomics.EstimateNet(entry,q,position.Side,
            position.Units,position.EntryPrice!.Value,price,q.LiquidationSlippagePerSide??position.SlippagePerSide);
        if(legal&&displacement>0m&&increment+position.FinancingRemaining>0m&&
            !fundingReserves!.IsOutstanding(position.Id))
            return new("INTEGRATED_FAVORABLE_REDUCTION",minimum);
        return new("INTEGRATED_EUR_TARGET_OBSERVED",position.Units);
    }
}
