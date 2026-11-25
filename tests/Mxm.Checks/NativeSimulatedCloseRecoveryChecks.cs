using System;
using System.Linq;
using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using Mxm.Core;
using Mxm.Cloud;

// Deterministic source-shaped SYNTHETIC fixture. This does not prove historical
// broker fills, original source authenticity, financed HARD21 or continuous DD.
internal static class NativeSimulatedCloseRecoveryChecks
{
    private const long First=1800000000000L;
    private const string A="SIR1_SYNTH_A";
    private const string B="SIR1_SYNTH_B";
    private const string Position="SIR1_SYNTH_POSITION_A";
    private const string SessionBinding="SIR1_SYNTH_MODEL_ONLY";
    private static readonly string Hash=new string('a',64);

    static LedgerQuote Q(string symbol,long at,decimal bid)=>
        new(symbol,at,bid,bid+.01m,1m,1m,.01m,0m,1m);

    static LedgerEvent E(string eventId,string kind,long at,
        string id=Position,string symbol=A,int side=1,decimal units=1m,
        decimal price=0m,decimal slip=0m,string reason="SIR1_SYNTHETIC_ONLY",
        LedgerQuote[]? qs=null)=>
        new(eventId,at,kind,id,symbol,side,units,price,
            kind is "OPEN_FILL" or "CLOSE_FILL" ?.01m:0m,1m,slip,
            at-20,at-30,100,reason,Hash,qs??Array.Empty<LedgerQuote>());

    static (NativeFundedSession Session,NativeModelCloseProtection Protection) Begin(long at,decimal units=1m)
    {
        var s=new NativeFundedSession(SessionBinding);
        var opening=Q(A,at+1000,10m);
        s.ApplyResearchFacts(new[]{
            E("SIR1/initial/open", "REQUEST_OPEN",at,units:units),
            E("SIR1/initial/fill", "OPEN_FILL",at+1000,
                units:units,price:opening.Ask,qs:new[]{opening}) with {FeeEur=.01m*units}
        });
        var protectedState=new NativeModelCloseProtection(Position,"ADAPT",
            new NativeExitSeed(.1m,10.5m),9.8m,opening.Ask,at+1000);
        return (s,protectedState);
    }

    public static void Run(Action<bool,string> check)
    {
        var (session,protection)=Begin(First);
        var start=session.Ledger.Summary(First+1000);
        check(start.OpenPositions==1 && start.CashEur==299.99m &&
              start.CompleteRoundTrips==0 && start.UsedMarginEur==1m,
            "SIR1 initial EUR300 model cash and held margin are native ledger only");

        var exitQuote=Q(A,First+2000,9.69m);
        var first=NativeSimulatedCloseLifecycle.Advance(session,protection,
            new(First+2000,exitQuote));
        protection=first.Protection;
        check(first.Status=="MODEL_CAUSAL_CLOSE_REISSUED_UNTRANSMITTED" &&
              first.AppliedFacts.Any(e=>e.Kind=="REQUEST_CLOSE" &&
                  e.Reason.StartsWith("MODEL_UNTRANSMITTED_")) &&
              first.CommonBook.PendingIntents==1 &&
              first.CommonBook.OpenPositions==1 &&
              first.CommonBook.CashEur==start.CashEur,
            "existing NativeCausalExitResearch signal requests an untransmitted modeled close only");

        // A different symbol's native intent is not blocked by an unrelated
        // model close, provided there are fresh genuine-shaped marks and margin.
        var parallel=NativeFundedSession.Restore(session.Checkpoint(),SessionBinding);
        parallel.ApplyResearchFacts(new[]{E("SIR1/unrelated/mark","MARK",First+2000,
            id:"",symbol:"",side:0,units:0,qs:new[]{Q(B,First+2000,20m)})});
        parallel.ApplyResearchFacts(new[]{E("SIR1/unrelated/request","REQUEST_OPEN",
            First+2000,id:"SIR1_SYNTH_POSITION_B",symbol:B,side:-1)});
        var pendingParallel=parallel.Ledger.Summary(First+2000);
        check(pendingParallel.OpenPositions==1 && pendingParallel.PendingIntents==2 &&
              pendingParallel.UsedMarginEur==1m,
            "pending modeled close does not globally prohibit a legal second-symbol research request");
        parallel.ApplyResearchFacts(new[]{E("SIR1/unrelated/fresh","MARK",First+3000,
            id:"",symbol:"",side:0,units:0,qs:new[]{Q(A,First+3000,9.69m),
                Q(B,First+3000,20m)}),
            E("SIR1/unrelated/fill","OPEN_FILL",First+3000,
                id:"SIR1_SYNTH_POSITION_B",symbol:B,side:-1,price:20m)});
        check(parallel.Ledger.Summary(First+3000).OpenPositions==2 &&
              parallel.Ledger.Summary(First+3000).UsedMarginEur==2m &&
              parallel.Ledger.Summary(First+3000).PendingIntents==1,
            "second symbol can enter the SAME native funded ledger with unrelated close pending");

        // Source stops giving observations; this is NOT official market closure.
        long gap=First+2000+5*60000L;
        var expired=NativeSimulatedCloseLifecycle.Advance(session,protection,
            new(gap,null));
        var postExpiry=expired.CommonBook;
        check(expired.AppliedFacts.Any(e=>e.Kind=="MODEL_CLOSE_INTENT_EXPIRED") &&
              postExpiry.OpenPositions==1 && postExpiry.PendingIntents==0 &&
              postExpiry.CashEur==start.CashEur && postExpiry.CompleteRoundTrips==0 &&
              postExpiry.LiquidationEquityEur is null &&
              postExpiry.HistoryEvidenceIncomplete &&
              expired.Status=="HOLD_UNOBSERVED_QUOTE_NO_MODEL_FILL",
            "expiring only simulated request does not pretend to fill, free held margin or mark unknown equity as zero");
        check(!expired.AppliedFacts.Any(e=>e.Kind is "CLOSE_FILL" or "CONFIRMED_CANCEL"),
            "SIR1 model-only expiration never claims broker cancellation/fill");
        // At exact restoration, replay and pure Cloud observation-only adapter
        // invoke the SAME Core implementation, byte-identical event facts.
        string snapshot=session.Checkpoint();
        var fromReplay=NativeFundedSession.Restore(snapshot,SessionBinding);
        var fromCloud=NativeFundedSession.Restore(snapshot,SessionBinding);
        var restoredInput=new NativeModelCloseObservation(gap+60000L,
            Q(A,gap+60000L,9.68m));
        var replayResult=NativeSimulatedCloseLifecycle.Advance(fromReplay,
            expired.Protection,restoredInput);
        var cloudAdapter=new NativeCloudResearchParityAdapter();
        var cloudResult=cloudAdapter.ObserveModelCloseOnly(fromCloud,
            expired.Protection,restoredInput);
        check(JsonSerializer.Serialize(replayResult.AppliedFacts)==
              JsonSerializer.Serialize(cloudResult.AppliedFacts) &&
              JsonSerializer.Serialize(replayResult.CommonBook)==
              JsonSerializer.Serialize(cloudResult.CommonBook) &&
              replayResult.Protection==cloudResult.Protection &&
              replayResult.Status==cloudResult.Status &&
              replayResult.Status=="MODEL_CAUSAL_CLOSE_REISSUED_UNTRANSMITTED" &&
              replayResult.CommonBook.OpenPositions==1 &&
              replayResult.CommonBook.PendingIntents==1,
            "Replay and actual Cloud-linked adapter share eventwise Core intent recovery parity");

        // Duplicate same-clock observation cannot submit, close or settle again.
        var afterReplay=fromReplay.Ledger.Summary(gap+60000L);
        var repeated=NativeSimulatedCloseLifecycle.Advance(fromReplay,
            replayResult.Protection,restoredInput);
        check(repeated.Status=="MODEL_CLOSE_INTENT_PENDING_UNTRANSMITTED" &&
              fromReplay.Ledger.Summary(gap+60000L)==afterReplay,
            "duplicate same-clock replay is idempotent under restored Core session");

        var nextAt=gap+2*60000L;
        var completed=NativeSimulatedCloseLifecycle.Advance(fromReplay,
            repeated.Protection,new(nextAt,Q(A,nextAt,9.66m)));
        check(completed.Status=="MODEL_QUOTE_BOUND_CLOSE_SETTLED" &&
              completed.AppliedFacts.Any(x=>x.Kind=="CLOSE_FILL" && x.At==nextAt) &&
              completed.CommonBook.OpenPositions==0 &&
              completed.CommonBook.PendingIntents==0 &&
              completed.CommonBook.CompleteRoundTrips==1 &&
              completed.CommonBook.CashEur<start.CashEur,
            "a NEW request alone permits next actual quote-model settlement; cost and cash reconcile");

        var replayedClose=NativeSimulatedCloseLifecycle.Advance(fromReplay,
            completed.Protection,new(nextAt,Q(A,nextAt,9.66m)));
        check(replayedClose.ModelPositionClosed && replayedClose.AppliedFacts.Length==0 &&
              fromReplay.Ledger.Summary()==completed.CommonBook,
            "repeated terminal observation cannot settle a position twice");

        bool futureQuoteDenied=false;
        try{NativeSimulatedCloseLifecycle.Advance(
            NativeFundedSession.Restore(snapshot,SessionBinding),
            expired.Protection,new(gap+60000L,Q(A,gap+60000L+1000,9.68m)));}
        catch(ArgumentException){futureQuoteDenied=true;}
        check(futureQuoteDenied,"future or nonmatching quote cannot drive a causal model fill");

        bool futureRegimeDenied=false;
        try{NativeSimulatedCloseLifecycle.Advance(
            NativeFundedSession.Restore(snapshot,SessionBinding),
            expired.Protection,new(gap+60000L,Q(A,gap+60000L,9.68m),
                -1m,gap+60000L));}
        catch(ArgumentException){futureRegimeDenied=true;}
        check(futureRegimeDenied,"future closed-bar regime state cannot authorize a modeled exit");

        bool conflictDenied=false;
        try
        {
            var e=completed.AppliedFacts.Single(x=>x.Kind=="CLOSE_FILL");
            fromReplay.ApplyResearchFacts(new[]{e with {FeeEur=e.FeeEur+1m}});
        }
        catch(InvalidOperationException){conflictDenied=true;}
        check(conflictDenied,"conflicting duplicate monetary settlement rejected by native ledger");

        // Weekend example. A 15:29 Friday close intent with no next quote
        // becomes a canceled model instruction, NEVER an invented 15:30 fill.
        long fri=new DateTimeOffset(2026,11,20,15,28,0,TimeSpan.Zero)
            .ToUnixTimeMilliseconds();
        var (friday,fProtection)=Begin(fri);
        var f=NativeSimulatedCloseLifecycle.Advance(friday,fProtection,
            new(fri+2000,Q(A,fri+2000,9.69m)));
        long monday=new DateTimeOffset(2026,11,23,13,30,0,TimeSpan.Zero)
            .ToUnixTimeMilliseconds();
        var noHistory=NativeSimulatedCloseLifecycle.Advance(friday,f.Protection,
            new(monday-60000L,null));
        check(noHistory.CommonBook.OpenPositions==1 &&
              noHistory.CommonBook.PendingIntents==0 &&
              noHistory.AppliedFacts.Any(x=>x.Kind=="MODEL_CLOSE_INTENT_EXPIRED") &&
              noHistory.CommonBook.CompleteRoundTrips==0,
            "Friday/source-window end plus weekend expires only UNTRANSMITTED instruction, not the position");
        var resumedMonday=NativeSimulatedCloseLifecycle.Advance(friday,
            noHistory.Protection,new(monday,Q(A,monday,9.69m)));
        check(resumedMonday.CommonBook.OpenPositions==1 &&
              resumedMonday.CommonBook.PendingIntents==1 &&
              !resumedMonday.ModelPositionClosed &&
              !resumedMonday.AppliedFacts.Any(x=>x.Kind=="CLOSE_FILL"),
            "Monday quote can reissue thesis-based modeled close; not a guessed weekend execution");
        var finalMonday=NativeSimulatedCloseLifecycle.Advance(friday,
            resumedMonday.Protection,new(monday+60000L,Q(A,monday+60000L,9.67m)));
        check(finalMonday.CommonBook.CompleteRoundTrips==1 &&
              finalMonday.CommonBook.OpenPositions==0,
            "Monday observed next quote settles native model, not Friday's stale request");

        // Broker-like or old historical request cannot be reinterpreted
        // as safely canceled purely because of SIR1 model expiry semantics.
        var (old,oldProtection)=Begin(First+1000000L);
        old.ApplyResearchFacts(new[]{E("SIR1/legacy/close","REQUEST_CLOSE",
            First+1002000L,reason:"HISTORIC_LEGACY_REQUEST_NO_MODEL_PROOF")});
        var oldStep=NativeSimulatedCloseLifecycle.Advance(old,oldProtection,
            new(First+1002000L+300000L,null));
        check(oldStep.Status=="NON_SIR1_INTENT_PRESERVED_NO_MODEL_RECONCILIATION" &&
              oldStep.CommonBook.PendingIntents==1,
            "non-SIR1 unresolved model or broker-like request is not silently expired");
        bool falseModelExpiryDenied=false;
        try{old.ApplyResearchFacts(new[]{E("SIR1/legacy/falsecancel",
            "MODEL_CLOSE_INTENT_EXPIRED",First+1002000L+400000L,
            price:0,reason:"MODEL_UNTRANSMITTED_CLOSE_RESPONSE_WINDOW_EXPIRED") with {
                MarginPerUnit=0m
            }});}
        catch(ArgumentException){falseModelExpiryDenied=true;}
        check(falseModelExpiryDenied,"only explicitly UNTRANSMITTED model close may expire");

        var (pressured,riskProtection)=Begin(First,2m);
        var reduction=NativeSimulatedCloseLifecycle.Advance(pressured,riskProtection,
            new(First+2000,Q(A,First+2000,9.99m),Instruction:new(NativeSimulatedCloseLifecycle.MarginReduction,1m),
                IntegratedManagesProtection:true));
        check(reduction.CommonBook.UsedMarginEur==2m&&reduction.CommonBook.PendingIntents==1,
            "General margin reduction keeps its entire commitment until a later witnessed fill");
        var reduced=NativeSimulatedCloseLifecycle.Advance(pressured,reduction.Protection,
            new(First+3000,Q(A,First+3000,9.98m),IntegratedManagesProtection:true));
        check(reduced.CommonBook.UsedMarginEur==1m&&reduced.CommonBook.PendingIntents==0&&
            reduced.CommonBook.CompleteRoundTrips==0&&reduced.AppliedFacts.Single(e=>e.Kind=="CLOSE_FILL").Units==1m,
            "General margin reduction releases only the actually filled volume");

        // Synthetic serialized audit digest; not proof of historical broker
        // source, independent real NET, continuity of intraminute risk or HARD21.
        var serialized=JsonSerializer.Serialize(new {
            Domain="SYNTHETIC_PRODUCT_LIFECYCLE_FIXTURE_NO_BROKER_EVIDENCE",
            ClosedStudyReruns=0,OriginalBrokerOrders=0,
            Events=first.AppliedFacts.Concat(expired.AppliedFacts)
                .Concat(replayResult.AppliedFacts).Concat(completed.AppliedFacts).ToArray(),
            End=completed.CommonBook,ReplayCloudEventsIdentical=true});
        var sha=Convert.ToHexString(SHA256.HashData(
            Encoding.UTF8.GetBytes(serialized))).ToLowerInvariant();
        Console.WriteLine("SIR1_SYNTHETIC_EVENT_RECEIPT_SHA256="+sha);
    }
}
