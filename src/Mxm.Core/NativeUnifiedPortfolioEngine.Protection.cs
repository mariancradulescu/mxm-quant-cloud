using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Tick pages can prove that a Trade trigger was observed without proving a
// market fill. Multiple prices at one millisecond have no reliable ordering.
public sealed record Ucp1StopTouch(string PositionId, decimal Minimum, decimal Maximum, bool CompleteSinceOpen);
public sealed record Ucp1StopQuote(string PositionId, bool CompleteSinceTrigger);
public sealed record Ucp1ProtectionObservation(bool BetweenDecisions, Ucp1StopTouch[] Touches,
    Ucp1StopQuote[] ExecutableQuotes, string[] UnverifiedPositionIds)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string[]? ExecutableIntentIds { get; init; }
}
public sealed record Ucp1StopWatch(string PositionId, string Symbol, int Side, long OpenedAt, decimal Stop,
    long? TriggerAt, long? FillNotBefore);
internal sealed record Ucp1IntentWatch(string PositionId,string Symbol,bool Buy,bool Opening,long DecisionAt,
    long FillNotBefore,long ExpiresAfter);
public sealed record Ucp1StopTrigger(long At, decimal MinimumGap, decimal MaximumGap,
    bool CompleteSinceOpen, bool TickSource);
public sealed record Ucp1StopExecution(Ucp1StopTrigger Trigger, long FillAt, long ModeledLatencyMs,
    decimal MinimumMoveAfterTrigger, decimal MaximumMoveAfterTrigger, decimal QuotedDistanceBeyondStop,
    decimal ModeledSlippage, bool TickFillQuote, bool CompleteSinceTrigger);
public sealed record Ucp1MarginObservation(long At, string Phase, string? PositionId,
    decimal HeldMarginEur, decimal PendingMarginEur, decimal EquityEur)
{
    public decimal MarginFraction => (HeldMarginEur+PendingMarginEur)/EquityEur;
}

public sealed partial class NativeUnifiedPortfolioEngine
{
    internal const string NativeStopModelReason = "MODEL_UNTRANSMITTED_INTEGRATED_NATIVE_TRADE_STOP";
    bool ModelsNativeStops => eurDevelopmentProfile?.ModeledStopLatencyMs is not null;
    internal bool ModelsEurStopOnTicks => ModelsNativeStops;
    internal bool UsesClosedSessionFundingQuotes => eurDevelopmentProfile?.ModelFundingAtPriorClosedSessionQuote==true;
    bool CaptureEurDiagnostics => eurDevelopmentProfile is { CaptureStudyDiagnostics:true } && !researchFork;
    readonly List<Ucp1MarginObservation> eurMarginExceedances = new();
    readonly Dictionary<string,Ucp1MarginObservation> eurMarginMaxima = new(StringComparer.Ordinal);

    internal Ucp1StopWatch[] ProtectionWatches() => !ModelsNativeStops ? Array.Empty<Ucp1StopWatch>() :
        PlanValues.Where(p=>p.OpenAt>0 && p.Integrated is not null).Select(p=>new Ucp1StopWatch(
            p.Id,p.Symbol,p.Side,p.OpenAt,p.Stop,p.NativeStop?.At,
            p.NativeStop is { } trigger ? trigger.At+eurDevelopmentProfile!.ModeledStopLatencyMs!.Value : null)).ToArray();

    internal Ucp1IntentWatch[] IntentWatches() => eurDevelopmentProfile is not { ObserveIntentExecutionOnTicks:true }
        ?Array.Empty<Ucp1IntentWatch>():model.Ledger.PendingSnapshot()
            .Where(p=>p.Kind=="REQUEST_OPEN"||p.Kind=="REQUEST_CLOSE"&&
                p.Reason.StartsWith("MODEL_UNTRANSMITTED_",StringComparison.Ordinal)&&p.Reason!=NativeStopModelReason)
            .Select(p=>new Ucp1IntentWatch(p.PositionId,p.Symbol,p.Kind=="REQUEST_OPEN"?p.Side>0:p.Side<0,
                p.Kind=="REQUEST_OPEN",p.At,p.At+p.LatencyMs,NativeSimulatedCloseLifecycle.IsPersistentPortfolioClose(p.Reason)?long.MaxValue:p.At+600_000L)).ToArray();

    internal Ucp1MarginObservation[] EurMarginExceedances => eurMarginExceedances.ToArray();
    internal Ucp1MarginObservation[] EurMarginMaxima => eurMarginMaxima.Values.OrderBy(x=>x.Phase,StringComparer.Ordinal).ToArray();

    void RecordEurRiskObservation(long at, string phase, Ucp1Frame frame, string? positionId=null)
    {
        var book=model.Ledger.Summary(at);
        var pending=Cpe1Commitments(true,frame).Sum(x=>x.MarginEur);
        if(book.UsedMarginEur is not decimal held ||
            fundingReserves?.Capital(book,pending,updateObservedDrawdown:false) is not { ResearchAdmissionEquityEur:>0m } capital)return;
        var point=new Ucp1MarginObservation(at,phase,positionId,held,capital.PendingOpenMarginEur,
            capital.ResearchAdmissionEquityEur!.Value);
        if(!eurMarginMaxima.TryGetValue(phase,out var previous)||point.MarginFraction>previous.MarginFraction)
            eurMarginMaxima[phase]=point;
        if(point.MarginFraction>NativePendingCapitalGate.MaximumMarginFraction)eurMarginExceedances.Add(point);
    }

    // Same preventive 28% boundary used by existing admission/management.
    // A missing valuation cannot become a proven breach. A known conditional
    // mark may authorize a MODEL close request, never an executable quote/fill.
    internal static bool WitnessedPortfolioProtectionDue(decimal? equity,decimal observedDrawdown)
        =>equity.HasValue&&observedDrawdown>=.28m;

    void RequestWitnessedPortfolioProtection(Ucp1Frame frame)
    {
        if(researchFork||!IsEurRank||FundingScenarioId is null||fundingReserves is null)return;
        var summary=model.Ledger.Summary(frame.At);
        if(summary.OpenPositions==0)return;
        var capital=Cpe1FundingCapital(summary,frame);
        if(capital is null||!WitnessedPortfolioProtectionDue(capital.ResearchAdmissionEquityEur,
            capital.MaximumSampledFundingAdjustedDrawdown))return;
        var pending=model.Ledger.PendingSnapshot().Select(x=>x.PositionId).ToHashSet(StringComparer.Ordinal);
        foreach(var held in model.Ledger.PositionSnapshot().OrderBy(x=>x.Id,StringComparer.Ordinal))
        {
            if(held.EntryAt>=frame.At||pending.Contains(held.Id)||!plans.TryGetValue(held.Id,out var plan)||
                plan.Integrated is null||plan.NativeStop is not null)continue;
            // The existing intent watcher requires a later genuine executable
            // tick after latency; no valuation-only mark enters Markets.
            Apply(Event("REQUEST_CLOSE",frame.At,held.Id,held.Symbol,held.Side,held.Units,
                reason:eurDevelopmentProfile!.PersistWitnessedPortfolioCloseUntilExecutable
                    ?NativeSimulatedCloseLifecycle.PersistentPortfolioCloseReason
                    :"MODEL_UNTRANSMITTED_INTEGRATED_WITNESSED_PORTFOLIO_DD_PROTECTION")
                with {AvailableAt=frame.At,CalibratedThrough=frame.At});
            closeRequests++;
            Count("EUR_WITNESSED_PORTFOLIO_DD_CLOSE_REQUEST");
        }
    }

    void AdvanceNativeStops(Ucp1Frame frame, Dictionary<string,Ucp1MarketFrame> markets)
    {
        long at=frame.At;
        long latency=eurDevelopmentProfile!.ModeledStopLatencyMs!.Value;
        var observations=frame.Protection;
        var touches=observations?.Touches.ToDictionary(o=>o.PositionId,StringComparer.Ordinal);
        var executable=observations?.ExecutableQuotes.ToDictionary(o=>o.PositionId,StringComparer.Ordinal);
        var unverified=observations?.UnverifiedPositionIds.ToHashSet(StringComparer.Ordinal);
        foreach(var held in model.Ledger.PositionSnapshot().OrderBy(p=>p.Id,StringComparer.Ordinal))
        {
            if(at<=held.EntryAt)continue;
            var plan=plans[held.Id];
            if(plan.Integrated is null)continue;
            var quote=markets.GetValueOrDefault(held.Symbol)?.Quote;
            decimal? executablePrice=held.Side>0?quote?.Bid:quote?.Ask;
            if(unverified?.Contains(held.Id)==true)plan=plan with {CrossedUnknownHistory=true};

            if(plan.NativeStop is not { } trigger)
            {
                var touch=touches?.GetValueOrDefault(held.Id);
                if(touch is null && observations is not { BetweenDecisions:true } && executablePrice is decimal sampled)
                    touch=new(held.Id,sampled,sampled,false);
                if(touch is null)
                {
                    plans[held.Id]=plan;
                    continue;
                }
                decimal far=held.Side>0?touch.Minimum:touch.Maximum;
                if(touch.Minimum<=0m || touch.Maximum<touch.Minimum)
                    throw new ArgumentException("MODEL_NATIVE_STOP_PRICE_RANGE");
                if(!NativeExecutableEconomics.TradeStopReached(held.Side,far,plan.Stop))
                {
                    plans[held.Id]=plan;
                    continue;
                }
                decimal near=held.Side>0?touch.Maximum:touch.Minimum;
                bool tick=touches?.ContainsKey(held.Id)==true;
                trigger=new(at,Math.Max(0m,held.Side*(plan.Stop-near)),held.Side*(plan.Stop-far),
                    touch.CompleteSinceOpen,tick);
                Apply(Event("MODEL_NATIVE_STOP_TRIGGER",at,held.Id,held.Symbol,held.Side,held.Units,
                    reason:NativeStopModelReason) with {AvailableAt=at,CalibratedThrough=at,LatencyMs=latency});
                plans[held.Id]=plan with {NativeStop=trigger,
                    CrossedUnknownHistory=plan.CrossedUnknownHistory||!trigger.CompleteSinceOpen};
                closeRequests++;
                Count(tick?"EUR_NATIVE_STOP_TICK_TRIGGER":"EUR_NATIVE_STOP_GRID_FALLBACK_TRIGGER");
                continue;
            }

            var execution=executable?.GetValueOrDefault(held.Id);
            if(at-trigger.At<latency || executablePrice is not decimal price || quote is null ||
                (observations is { BetweenDecisions:true } && execution is null))
            {
                plans[held.Id]=plan;
                continue;
            }
            decimal slip=quote.LiquidationSlippagePerSide??held.SlippagePerSide;
            decimal exit=NativeExecutableEconomics.ExitPrice(price,held.Side,slip);
            if(exit<=0m)
            {
                plans[held.Id]=plan with {CrossedUnknownHistory=true};
                Count("EUR_NATIVE_STOP_CONDITIONAL_EXIT_PRICE_UNSUPPORTED");
                continue;
            }
            decimal distance=held.Side*(plan.Stop-price);
            var modeled=new Ucp1StopExecution(trigger,at,latency,distance-trigger.MaximumGap,
                distance-trigger.MinimumGap,distance,slip,execution is not null,execution?.CompleteSinceTrigger==true);
            Apply(Event("CLOSE_FILL",at,held.Id,held.Symbol,held.Side,held.Units,exit,
                Fee(quote,held.Units,-held.Side),slip:held.SlippagePerSide,reason:NativeStopModelReason) with
                {ObservedExitSlippagePerSide=slip,AvailableAt=at,CalibratedThrough=trigger.At,LatencyMs=latency});
            fundingReserves?.Close(held.Id,held.Units,at);
            Count(execution is null?"EUR_NATIVE_STOP_GRID_FALLBACK_FILL":"EUR_NATIVE_STOP_CONDITIONAL_TICK_FILL");
            CompleteModelPosition(held,plan with {CrossedUnknownHistory=plan.CrossedUnknownHistory||
                !modeled.CompleteSinceTrigger},at,modeled);
        }
    }

    void CompleteModelPosition(LedgerPosition held,Ucp1Plan plan,long at,Ucp1StopExecution? stop=null)
    {
        var close=model.Ledger.LastClosedRoundTrip(held.Id);
        var trip=new Ucp1Episode(held.Id,held.Symbol,plan.Family,held.Side,plan.OpenAt,close.ClosedAt,
            held.Units,close.NetEur,close.GrossEur,plan.RiskEur,plan.RiskEur>0m?close.NetEur/plan.RiskEur:null,
            plan.MfeEur,plan.MaeEur,close.Reason,plan.CrossedUnknownHistory) {EurContext=plan.EurContext,StopExecution=stop};
        if(plan.Integrated is { } geometry)
        {
            var parts=Cpe1&&!geometry.Reduced?new[]{close}:model.Ledger.ClosedFragments(held.Id);
            if(Cpe1)trip=trip with {EconomicEntry=plan.EconomicEntry,EconomicEvidence=Cpe1CompleteEpisode(plan,held,close,parts)};
            trip=CompleteIntegrated(trip,plan,parts);
        }
        trips.Add(trip);
        if(Cpe1)RememberCpe1Episode(trip,at);
        RemovePlan(held.Id);
    }
}
