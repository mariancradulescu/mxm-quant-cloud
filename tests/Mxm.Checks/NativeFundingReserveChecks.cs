using Mxm.Core;
using Mxm.Cloud;
using System.Text.Json;
using static Cpe1IntegratedEconomicChecks;

internal static class NativeFundingReserveChecks
{
    const long M5=300_000;
    static readonly long Origin=new DateTimeOffset(2026,11,23,21,45,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly string Proof=new string('a',64);
    static long Clock(int slot)=>Origin+slot*M5;

    static Ucp1Frame Observation(int slot,decimal bid,decimal? offer=0m,decimal? margin=null)
    {
        var frame=Frame(Origin,Clock(slot),bid,unknownSwap:true);
        var market=Named(frame.Markets.Single(),"EURUSD",margin);
        return frame with {Markets=new[]{market with {FundingOffers=offer is decimal cap?
            new[]{new NativeFundingOfferEvidence(market.Symbol,1,1m,frame.At,frame.At,
                frame.At+M5,frame.At+M5,cap,Proof)}:null}}};
    }

    static NativeAccruedFundingEvidence Evidence(LedgerEvent fill,int through,int available,
        decimal? exact=null,decimal? ceiling=null)
        =>new(fill.PositionId,fill.Symbol,fill.Side,fill.Units,fill.At,
            Clock(through),Clock(available),exact,ceiling,Proof);

    static NativeUnifiedPortfolioEngine Engine()=>new("CPE1_ECONOMIC",reserveAccruedFunding:true);

    static void BoundedAfterClose(Action<bool,string> check)
    {
        var engine=Engine();
        var adapter=new NativeUnifiedCloudParityAdapter("CPE1_ECONOMIC",reserveAccruedFunding:true);
        Ucp1FrameResult Step(Ucp1Frame frame)
        {
            var result=engine.Advance(frame);
            check(result==adapter.Observe(frame) &&
                JsonSerializer.Serialize(engine.OriginalModelEvents)==JsonSerializer.Serialize(adapter.ModelFacts),
                "Funding-aware Replay and Cloud adapter preserve eventwise parity");
            return result;
        }
        check(Step(Observation(1,100.95m)).FundingCapital is {PendingOpenMarginEur:1m},
            "Funding-aware OPEN intent reserves pending margin");
        Step(Observation(2,100.95m));
        var fill=engine.OriginalModelEvents.Single(e=>e.Kind=="OPEN_FILL");

        var invalid=Observation(3,100.11m) with {FundingEvidence=new[]{Evidence(fill,3,4,ceiling:.4m)}};
        var before=engine.Checkpoint();
        try
        {
            engine.Advance(invalid);
            check(false,"Prospective funding evidence with future availability must fail");
        }
        catch(ArgumentException)
        {
            check(engine.Checkpoint()==before,"Rejected funding proof leaves engine and ledger untouched");
        }

        var protection=Step(Observation(3,100.11m));
        check(protection is {Held:1,Pending:1,FundingCapital:{HeldMarginEur:1m,
            PendingOpenMarginEur:0m,OutstandingHeldWindows:1,DemonstrableEquityEur:null}},
            "Unbounded held financing blocks new risk and preserves protective CLOSE margin");
        var flat=Step(Observation(4,100.10m));
        check(flat is {Held:0,Pending:0,FundingCapital:{HeldMarginEur:0m,
            OutstandingClosedWindows:1,OutstandingDebitCeilingEur:null,ReconciledClosedModelNetEur:null}},
            "Settled CLOSE releases position margin while the unbounded historical liability persists");
        check(engine.CompleteModelTrips.Single().EconomicEvidence is
            {ConditionalNetKnown:false,ClosedNetEur:null,RealizedNetR:null},
            "Unreconciled funding censors episode NET and realized R");

        engine=NativeUnifiedPortfolioEngine.Restore(engine.Checkpoint());
        adapter.Restore(adapter.Checkpoint());
        var stillBlocked=Step(Observation(5,100.95m));
        check(stillBlocked.Proposed>flat.Proposed && stillBlocked.Admitted==flat.Admitted &&
            stillBlocked.FundingCapital?.DemonstrableFreeMarginEur is null,
            "Unbounded closed debt preserves detector activity while later admissions remain unfunded");
        var bounded=Step(Observation(6,100.95m) with
            {FundingEvidence=new[]{Evidence(fill,4,6,ceiling:.40m)}});
        check(bounded is {Pending:1,FundingCapital:{OutstandingClosedWindows:1,
            OutstandingDebitCeilingEur:.40m,PostedFinancingEur:0m,ReconciledClosedModelNetEur:null}} &&
            bounded.FundingCapital.DemonstrableFreeMarginEur==bounded.ModelBook.CashEur-1.40m &&
            bounded.ModelBook.CashEur==flat.ModelBook.CashEur,
            "Authenticated ceiling state reserves only proven debit and pending margin, without booking hypothetical cash");

        var rejected=Step(Observation(7,100.95m,margin:250m));
        check(rejected is {Held:0,Pending:0,FundingCapital.OutstandingDebitCeilingEur:.40m} &&
            engine.OriginalModelEvents.Count(e=>e.Kind=="OPEN_FILL")==1 &&
            rejected.ModelBook.CashEur==flat.ModelBook.CashEur,
            "Later fill rechecks margin after reserve and preserves the one ledger");
    }

    static void ConfirmedSettlement(Action<bool,string> check)
    {
        var engine=Engine();
        check(engine.Advance(Observation(1,100.95m,offer:null)) is {Proposed:>0,Admitted:0},
            "New opportunity without its causal funding ceiling stays WAIT");
        engine.Advance(Observation(2,100.95m));
        engine.Advance(Observation(3,100.95m));
        var fill=engine.OriginalModelEvents.Single(e=>e.Kind=="OPEN_FILL");
        var closing=Observation(4,100.11m) with {FundingEvidence=new[]{Evidence(fill,4,4,exact:-.20m)}};
        var held=engine.Advance(closing);
        check(held.FundingCapital is {PostedFinancingEur:-.20m,OutstandingDebitCeilingEur:0m},
            "Known funding posts to the existing cash ledger");
        engine=NativeUnifiedPortfolioEngine.Restore(engine.Checkpoint());
        var flat=engine.Advance(Observation(5,100.10m) with {FundingEvidence=new[]{Evidence(fill,5,5,exact:-.20m)}});
        var audit=new NativeFundedLedger();
        foreach(var fact in engine.OriginalModelEvents)audit.Apply(fact);
        check(audit.Summary()==engine.ModelSummary &&
            flat.FundingCapital?.ReconciledClosedModelNetEur==engine.ModelSummary.ClosedNetEur &&
            audit.ClosedFragments().Single().FinancingEur==.20m &&
            engine.OriginalModelEvents.Count(e=>e.Kind=="FINANCING"&&e.EvidenceHash==Proof&&
                e.AvailableAt==Clock(4)&&e.CalibratedThrough==Clock(4))==1,
            "Repeated cumulative funding evidence and restore yield one settled debit and exact ledger reconciliation");
    }

    static void LateExactSettlement(Action<bool,string> check,decimal amount)
    {
        var engine=Engine();
        var adapter=new NativeUnifiedCloudParityAdapter("CPE1_ECONOMIC",reserveAccruedFunding:true);
        Ucp1FrameResult Step(Ucp1Frame frame)
        {
            var result=engine.Advance(frame);
            check(result==adapter.Observe(frame) &&
                JsonSerializer.Serialize(engine.OriginalModelEvents)==JsonSerializer.Serialize(adapter.ModelFacts),
                "Late funding Core/Cloud adapter parity");
            return result;
        }
        Step(Observation(1,100.95m));
        Step(Observation(2,100.95m));
        var fill=engine.OriginalModelEvents.Single(x=>x.Kind=="OPEN_FILL");
        Step(Observation(3,100.11m));
        var flat=Step(Observation(4,100.10m));
        var original=engine.OriginalModelEvents.Single(x=>x.Kind=="CLOSE_FILL");
        var episode=engine.CompleteModelTrips.Single();
        check(flat.FundingCapital?.OutstandingClosedWindows==1,"Late funding obligation survives close");
        engine=NativeUnifiedPortfolioEngine.Restore(engine.Checkpoint());
        adapter.Restore(adapter.Checkpoint());
        var proof=Evidence(fill,4,6,exact:amount);
        var settled=Step(Observation(6,100.95m,offer:null) with {FundingEvidence=new[]{proof}});
        check(settled.FundingCapital is {OutstandingClosedWindows:0,OutstandingDebitCeilingEur:0m} &&
            settled.FundingCapital.PostedFinancingEur==amount &&
            settled.FundingCapital.ReconciledClosedModelNetEur==flat.ModelBook.ClosedNetEur+amount &&
            settled.ModelBook.CashEur==flat.ModelBook.CashEur+amount &&
            settled.ModelBook.CompleteRoundTrips==flat.ModelBook.CompleteRoundTrips,
            "Late exact debit or credit settles the obligation once in the common cash ledger");
        engine=NativeUnifiedPortfolioEngine.Restore(engine.Checkpoint());
        adapter.Restore(adapter.Checkpoint());
        var repeated=Step(Observation(7,100.95m,offer:null) with {FundingEvidence=new[]{proof}});
        check(repeated.ModelBook.CashEur==settled.ModelBook.CashEur &&
            engine.OriginalModelEvents.Count(x=>x.Kind=="CLOSED_FUNDING_SETTLEMENT")==1 &&
            engine.OriginalModelEvents.Single(x=>x.Kind=="CLOSE_FILL")==original &&
            engine.CompleteModelTrips.Single()==episode,
            "Repeated proof after checkpoint neither double books nor rewrites original close or episode");
        var before=engine.Checkpoint();
        try
        {
            engine.Advance(Observation(8,100.95m,offer:null) with
                {FundingEvidence=new[]{proof with {ExactSignedEur=amount+1m}}});
            check(false,"Conflicting settled funding evidence must fail");
        }
        catch(ArgumentException)
        {
            check(engine.Checkpoint()==before,"Conflicting settled evidence leaves state unchanged");
        }
        var audit=new NativeFundedLedger();
        foreach(var fact in engine.OriginalModelEvents)
        {
            audit.Apply(fact);
            audit=NativeFundedLedger.Restore(audit.Checkpoint());
            audit.Apply(fact);
        }
        var adjustment=audit.ClosedFundingSettlements().Single();
        check(audit.Summary()==engine.ModelSummary &&
            adjustment.PositionId==fill.PositionId && adjustment.SignedDeltaEur==amount &&
            adjustment.ThroughInclusive==Clock(4) && adjustment.PostedAt==Clock(6) &&
            audit.ClosedFragments().Single().NetEur==flat.ModelBook.ClosedNetEur,
            "Independent ledger restart and idempotence preserve separate closed funding settlement");
    }

    static void PartialExposure(Action<bool,string> check)
    {
        var funding=new NativePortfolioFunding();
        funding.Open("portfolio-model/A","EURUSD",1,2m,Clock(1));
        var first=new NativeAccruedFundingEvidence("portfolio-model/A","EURUSD",1,2m,
            Clock(1),Clock(2),Clock(2),null,1.5m,Proof);
        funding.Validate(Clock(2),new[]{first});
        funding.Observe(new[]{first},(_,_,_)=>throw new InvalidOperationException());
        funding.Close(first.PositionId,1m,Clock(2));
        var restored=new NativePortfolioFunding(funding.Checkpoint());
        var remainder=first with {Units=1m,FromExclusive=Clock(2),ThroughInclusive=Clock(3),
            AvailableAt=Clock(3),MaximumTotalDebitEur=.5m};
        restored.Validate(Clock(3),new[]{remainder});
        restored.Observe(new[]{remainder},(_,_,_)=>throw new InvalidOperationException());
        var book=new LedgerSummary(300m,299m,20m,279m,300m,0m,1,1,0,0m,false,Proof);
        var capital=restored.Capital(book,15m);
        check(capital is {OutstandingClosedWindows:1,OutstandingHeldWindows:1,
            OutstandingDebitCeilingEur:2m,DemonstrableFreeMarginEur:262m,ReconciledClosedModelNetEur:null},
            "A partial close preserves its original funding window and reserves both remaining held and pending margin");
    }

    static void InsufficientOfferCoverage(Action<bool,string> check)
    {
        var engine=Engine();
        var frame=Observation(1,100.95m);
        var market=frame.Markets.Single();
        var offer=market.FundingOffers!.Single();
        var marketClosing=frame with {Markets=new[]{market with
            {FundingOffers=new[]{offer with {NextScheduledManagementAt=frame.At+12*M5}}}}};
        check(engine.Advance(marketClosing) is {Proposed:>0,Pending:0},
            "Funding offer must cover the next verified management clock through a scheduled pause");
        check(engine.Advance(Observation(2,100.95m)) is {Pending:1,Held:0},
            "Funding offer covering the next decision allows a pending entry");
        check(engine.Advance(Observation(3,100.95m,offer:null)) is {Pending:0,Held:0},
            "A stale or withdrawn funding offer cannot support the later OPEN_FILL");
    }

    public static void Run(Action<bool,string> check)
    {
        BoundedAfterClose(check);
        ConfirmedSettlement(check);
        LateExactSettlement(check,-.40m);
        LateExactSettlement(check,.25m);
        PartialExposure(check);
        InsufficientOfferCoverage(check);
    }
}
