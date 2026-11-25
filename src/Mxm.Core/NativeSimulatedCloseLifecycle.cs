using System;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace Mxm.Core;

// SIR1 is the shared product lifecycle for model-only, NEVER TRANSMITTED
// close intents. It never submits, modifies, confirms or cancels broker orders.
// The sole monetary authority remains NativeFundedSession/NativeFundedLedger.
public sealed record NativeModelCloseProtection(
    string PositionId,string Policy,NativeExitSeed EntryFrozenSeed,
    decimal EntryFrozenStop,decimal FavorableExtreme,long LastObservedQuoteAt);

public sealed record NativeModelCloseObservation(
    long Clock,LedgerQuote? AuthenticatedQuote,decimal ClosedM15Direction=0m,
    long ClosedM15DirectionKnownAt=0,NativeModelCloseInstruction? Instruction=null,
    bool FullSessionMark=false,bool IntegratedManagesProtection=false);

public sealed record NativeModelCloseInstruction(string Reason,decimal Units);

public sealed record NativeModelCloseStep(
    NativeModelCloseProtection Protection,string Status,
    LedgerEvent[] AppliedFacts,LedgerSummary CommonBook,
    bool ModelPositionClosed,bool OrdersSubmitted=false,
    bool BrokerCancellationConfirmed=false);

public static class NativeSimulatedCloseLifecycle
{
    internal const string MarginReduction = "INTEGRATED_EUR_GENERAL_MARGIN_REDUCTION";
    internal const string AdaptiveContinuationReduction = "INTEGRATED_EUR_ADVERSE_CONTINUATION_REDUCE";
    internal const string AdaptiveContinuationClose = "INTEGRATED_EUR_ADVERSE_CONTINUATION_CLOSE";
    internal static bool IsReductionReason(string reason) =>
        reason is "MODEL_UNTRANSMITTED_INTEGRATED_FAVORABLE_REDUCTION" or ("MODEL_UNTRANSMITTED_" + MarginReduction)
            or ("MODEL_UNTRANSMITTED_" + AdaptiveContinuationReduction);

    // The 120 seconds describes validity of a modeled close instruction,
    // not duration of holding exposure or a strategy-specific trading exit.
    public const long ModelCloseResponseWindowMs=120000L;
    public const long ModelRequestLatencyMs=100L;

    static string Hash(string input)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(input))).ToLowerInvariant();

    static LedgerEvent Fact(string kind,LedgerPosition position,long at,
        decimal price=0m,decimal fee=0m,decimal slip=0m,
        string reason="MODEL_UNTRANSMITTED",LedgerQuote[]? quotes=null,
        long latency=ModelRequestLatencyMs,decimal? units=null)
    {
        // Stable evidence-bound identity for replay, restart and duplicate tests.
        string identity="SIR1/"+position.Id+"/"+at+"/"+kind;
        return new LedgerEvent(identity,at,kind,position.Id,position.Symbol,
            position.Side,units??position.Units,price,fee,0m,slip,
            Math.Max(0,at-1),Math.Max(0,at-2),latency,reason,
            Hash(identity),quotes??Array.Empty<LedgerQuote>());
    }

    public static NativeModelCloseStep Advance(NativeFundedSession session,
        NativeModelCloseProtection protection,NativeModelCloseObservation observation,
        long responseWindowMs=ModelCloseResponseWindowMs)
        =>Advance(session,protection,observation,responseWindowMs,ownedModelLedger:false);

    internal static NativeModelCloseStep Advance(NativeFundedSession session,
        NativeModelCloseProtection protection,NativeModelCloseObservation observation,
        long responseWindowMs,bool ownedModelLedger)
    {
        if(responseWindowMs<=0L||responseWindowMs>600000L ||
           session is null || protection is null || observation is null ||
           session.Ledger.MonetaryDomain!="MODEL_REPLAY" ||
           string.IsNullOrWhiteSpace(protection.PositionId) ||
           protection.Policy is not ("VOL" or "STRUCT" or "ADAPT") ||
           protection.EntryFrozenSeed.AtrQuote<=0m ||
           protection.FavorableExtreme<=0m ||
           observation.Clock<=0 || protection.LastObservedQuoteAt>observation.Clock ||
           observation.ClosedM15DirectionKnownAt>=observation.Clock &&
              observation.ClosedM15Direction!=0m)
            throw new ArgumentException("SIR1_MODEL_DOMAIN_CAUSAL_PROTECTION_INVALID");

        var ledger=session.Ledger;
        var held=ledger.PositionSnapshot().SingleOrDefault(p=>p.Id==protection.PositionId);
        if(held is null)
        {
            if(!ledger.ClosedFragments().Any(x=>x.PositionId==protection.PositionId &&
                x.CompletesRoundTrip))
                throw new ArgumentException("SIR1_POSITION_NOT_HELD_OR_SETTLED");
            return new(protection,"MODEL_POSITION_ALREADY_SETTLED",
                Array.Empty<LedgerEvent>(),ledger.Summary(),true);
        }
        if(held.EntryPrice is not decimal entry || entry<=0m ||
           held.Side*(entry-protection.EntryFrozenStop)<=0m ||
           held.Side*(protection.FavorableExtreme-entry)<0m)
            throw new ArgumentException("SIR1_PROTECTION_DOES_NOT_MATCH_ENTRY");

        LedgerQuote? quote=observation.AuthenticatedQuote;
        long at=observation.Clock;
        if(quote is not null &&
           (quote.Symbol!=held.Symbol || quote.At!=at ||
            quote.Bid<=0m || quote.Ask<quote.Bid))
            throw new ArgumentException("SIR1_INVALID_REAL_QUOTE_CLOCK_OR_SYMBOL");

        var facts=new List<LedgerEvent>();
        void Apply(LedgerEvent e)
        {
            if(ownedModelLedger)session.ApplyOwnedResearchFact(e);
            else if(e.Kind=="MARK" && observation.FullSessionMark)session.RecordResearchMark(e);
            else session.ApplyResearchFacts(new[]{e});
            facts.Add(e);
        }

        // An unobserved clock is a real monitoring event, not a tradable price.
        // This may set the ledger's sampled history-incomplete flag, but never
        // effects position closure or releases margin/cash.
        Apply(Fact("MARK",held,at,reason:quote is null
            ?"MODEL_UNTRANSMITTED_UNKNOWN_MARK"
            :"SOURCE_BOUND_AUTHENTIC_OBSERVED_MARK",
            quotes:quote is null?Array.Empty<LedgerQuote>():new[]{quote}));

        var pending=session.Ledger.PendingSnapshot()
            .SingleOrDefault(x=>x.PositionId==held.Id);
        if(pending is not null &&
           (pending.Kind!="REQUEST_CLOSE" ||
            !pending.Reason.StartsWith("MODEL_UNTRANSMITTED_",StringComparison.Ordinal)))
            return new(protection,"NON_SIR1_INTENT_PRESERVED_NO_MODEL_RECONCILIATION",
                facts.ToArray(),session.Ledger.Summary(at),false);

        if(pending is not null && at-pending.At>responseWindowMs)
        {
            Apply(Fact("MODEL_CLOSE_INTENT_EXPIRED",held,at,
                reason:"MODEL_UNTRANSMITTED_CLOSE_RESPONSE_WINDOW_EXPIRED",
                latency:pending.LatencyMs));
            pending=null;
            // No CLOSE_FILL, fee, cash debit/credit, volume or margin change.
        }

        if(quote is null)
            return new(protection,"HOLD_UNOBSERVED_QUOTE_NO_MODEL_FILL",
                facts.ToArray(),session.Ledger.Summary(at),false);

        // Existing nonexpired model request may only fill on a genuinely later
        // observed quote after latency; never the decision quote or a missing
        // intragap/overnight fill.
        if(pending is not null)
        {
            if(pending.Kind=="REQUEST_CLOSE" &&
               at>=pending.At+pending.LatencyMs && at>pending.At)
            {
                decimal exitPrice=NativeExecutableEconomics.ExitPrice(held.Side>0?quote.Bid:quote.Ask,
                    held.Side,quote.LiquidationSlippagePerSide??held.SlippagePerSide);
                decimal units=IsReductionReason(pending.Reason)
                    ?pending.Units:held.Units;
                if(units<=0m || units>held.Units)
                    throw new ArgumentException("INTEGRATED_REDUCTION_VOLUME");
                decimal fee=NativeFundedLedger.Fee(quote,units,-held.Side);
                var close=Fact("CLOSE_FILL",held,at,exitPrice,fee,
                    held.SlippagePerSide,pending.Reason,
                    latency:pending.LatencyMs,units:units)
                    with { ObservedExitSlippagePerSide=quote.LiquidationSlippagePerSide };
                Apply(close);
                return new(protection with {LastObservedQuoteAt=at},
                    "MODEL_QUOTE_BOUND_CLOSE_SETTLED",facts.ToArray(),
                    session.Ledger.Summary(at),units==held.Units);
            }
            return new(protection with {LastObservedQuoteAt=at},
                "MODEL_CLOSE_INTENT_PENDING_UNTRANSMITTED",
                facts.ToArray(),session.Ledger.Summary(at),false);
        }

        // Re-assess on the FIRST actually observed quote after expiry or gap.
        // Supplied closed-bar direction is required to be timestamped strictly
        // earlier than this observation; no future return is inspected.
        var verdict=observation.IntegratedManagesProtection
            ?new NativeExitVerdict(false,"INTEGRATED_HOLD",protection.FavorableExtreme)
            :NativeCausalExitResearch.AssessLifecycle(
            protection.Policy,held.Side,entry,protection.EntryFrozenSeed,
            protection.EntryFrozenStop,protection.FavorableExtreme,quote,
            observation.ClosedM15Direction,false);
        var updated=protection with {FavorableExtreme=verdict.FavorableExtreme,
            LastObservedQuoteAt=at};
        var instruction=observation.Instruction;
        if(instruction is not null && (instruction.Units<=0m || instruction.Units>held.Units ||
           !instruction.Reason.StartsWith("INTEGRATED_",StringComparison.Ordinal) ||
           (instruction.Units<held.Units && !IsReductionReason("MODEL_UNTRANSMITTED_"+instruction.Reason))))
            throw new ArgumentException("INTEGRATED_CAUSAL_CLOSE_INSTRUCTION");
        if(instruction is not null || verdict.RequestClose)
        {
            Apply(Fact("REQUEST_CLOSE",held,at,
                reason:"MODEL_UNTRANSMITTED_"+(instruction?.Reason??verdict.Reason),
                units:instruction?.Units));
            return new(updated,"MODEL_CAUSAL_CLOSE_REISSUED_UNTRANSMITTED",
                facts.ToArray(),session.Ledger.Summary(at),false);
        }
        return new(updated,"MODEL_CAUSAL_SIGNAL_HOLD",
            facts.ToArray(),session.Ledger.Summary(at),false);
    }
}
