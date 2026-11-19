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
    long ClosedM15DirectionKnownAt=0);

public sealed record NativeModelCloseStep(
    NativeModelCloseProtection Protection,string Status,
    LedgerEvent[] AppliedFacts,LedgerSummary CommonBook,
    bool ModelPositionClosed,bool OrdersSubmitted=false,
    bool BrokerCancellationConfirmed=false);

public static class NativeSimulatedCloseLifecycle
{
    // The 120 seconds describes validity of a modeled close instruction,
    // not duration of holding exposure or a strategy-specific trading exit.
    public const long ModelCloseResponseWindowMs=120000L;
    public const long ModelRequestLatencyMs=100L;

    static string Hash(string input)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(input))).ToLowerInvariant();

    static LedgerEvent Fact(string kind,LedgerPosition position,long at,
        decimal price=0m,decimal fee=0m,decimal slip=0m,
        string reason="MODEL_UNTRANSMITTED",LedgerQuote[]? quotes=null,
        long latency=ModelRequestLatencyMs)
    {
        // Stable evidence-bound identity for replay, restart and duplicate tests.
        string identity="SIR1/"+position.Id+"/"+at+"/"+kind;
        return new LedgerEvent(identity,at,kind,position.Id,position.Symbol,
            position.Side,position.Units,price,fee,0m,slip,
            Math.Max(0,at-1),Math.Max(0,at-2),latency,reason,
            Hash(identity),quotes??Array.Empty<LedgerQuote>());
    }

    public static NativeModelCloseStep Advance(NativeFundedSession session,
        NativeModelCloseProtection protection,NativeModelCloseObservation observation)
    {
        if(session is null || protection is null || observation is null ||
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
            session.ApplyResearchFacts(new[]{e});
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

        if(pending is not null && at-pending.At>ModelCloseResponseWindowMs)
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
                decimal exitPrice=held.Side>0 ?
                    quote.Bid-held.SlippagePerSide :
                    quote.Ask+held.SlippagePerSide;
                decimal fee=Math.Max(quote.ExitFeePerUnit*held.Units,
                    quote.ExitFeeFloor);
                var close=Fact("CLOSE_FILL",held,at,exitPrice,fee,
                    held.SlippagePerSide,pending.Reason,
                    latency:pending.LatencyMs);
                Apply(close);
                return new(protection with {LastObservedQuoteAt=at},
                    "MODEL_QUOTE_BOUND_CLOSE_SETTLED",facts.ToArray(),
                    session.Ledger.Summary(at),true);
            }
            return new(protection with {LastObservedQuoteAt=at},
                "MODEL_CLOSE_INTENT_PENDING_UNTRANSMITTED",
                facts.ToArray(),session.Ledger.Summary(at),false);
        }

        // Re-assess on the FIRST actually observed quote after expiry or gap.
        // Supplied closed-bar direction is required to be timestamped strictly
        // earlier than this observation; no future return is inspected.
        var verdict=NativeCausalExitResearch.AssessLifecycle(
            protection.Policy,held.Side,entry,protection.EntryFrozenSeed,
            protection.EntryFrozenStop,protection.FavorableExtreme,quote,
            observation.ClosedM15Direction,false);
        var updated=protection with {FavorableExtreme=verdict.FavorableExtreme,
            LastObservedQuoteAt=at};
        if(verdict.RequestClose)
        {
            Apply(Fact("REQUEST_CLOSE",held,at,
                reason:"MODEL_UNTRANSMITTED_"+verdict.Reason));
            return new(updated,"MODEL_CAUSAL_CLOSE_REISSUED_UNTRANSMITTED",
                facts.ToArray(),session.Ledger.Summary(at),false);
        }
        return new(updated,"MODEL_CAUSAL_SIGNAL_HOLD",
            facts.ToArray(),session.Ledger.Summary(at),false);
    }
}
