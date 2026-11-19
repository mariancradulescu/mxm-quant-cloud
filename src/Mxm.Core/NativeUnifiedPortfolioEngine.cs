using System;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Core;

// UCP1 authoritative C# COMPLETE policy: one model ledger/account/allocator
// per predeclared policy. Replay and observation-only Cloud both invoke Advance.
// Historical source quotes are modeled observations, NEVER broker deal receipts.
public sealed record Ucp1MarketFrame(
    string Symbol,LedgerQuote Quote,NativeObservedContractTerms Contract,
    NativeClosedMarketBar[] M5,NativeClosedMarketBar[] M15,
    decimal SlippagePerSideQuote,string PriceEvidenceClass);
public sealed record Ucp1BrokerFrame(BrokerIdentitySnapshot Identity,
    decimal? AccountCashEur,string AccountType);
public sealed record Ucp1Frame(long At,Ucp1MarketFrame[] Markets,
    Ucp1BrokerFrame? Broker=null);
public sealed record Ucp1DecisionSignal(string Symbol,string Family,int Side,
    decimal Atr,decimal Equilibrium,decimal ExpectedMove,long LastCompletedM5At);
public sealed record Ucp1Episode(string PositionId,string Symbol,string Family,
    int Side,long OpenAt,long CloseAt,decimal Units,decimal NetEur,
    decimal GrossEur,decimal EntryRiskEur,decimal? R,
    decimal SampledMfeEur,decimal SampledMaeEur,string ExitReason,
    bool CrossedUnknownHistory);
public sealed record Ucp1CurvePoint(long At,decimal CashEur,decimal? EquityEur,
    decimal? UsedMarginEur,int Held,int Pending,int Completed);
public sealed record Ucp1Checkpoint(string Version,string Policy,string Session,
    string BrokerSession,string BrokerBinding,Dictionary<string,Ucp1Plan> Plans,
    Dictionary<string,long> LastSignalBar,long LastAt,long Sequence,
    int Proposed,int Admitted,int OpenFills,int ExpiredOpens,
    int ExpiredCloses,int CloseRequests,int Rejections,
    int SourceUnknownClocks,int GapExposures,
    Dictionary<string,int> Reasons,LedgerEvent[] Events,
    Ucp1Episode[] Trips,Ucp1CurvePoint[] Curve,
    string LastBrokerEvidence);
public sealed record Ucp1Plan(string Id,string Symbol,string Family,int Side,
    decimal Atr,decimal Equilibrium,decimal RiskEur,
    decimal Stop,decimal Extreme,long OpenAt,decimal Entry,
    decimal Units,decimal MfeEur,decimal MaeEur,long LastObservedAt,
    bool CrossedUnknownHistory);
public sealed record Ucp1FrameResult(string Policy,long At,
    LedgerSummary ModelBook,int Proposed,int Admitted,int OpenFills,
    int CloseFills,int Pending,int Held,string BrokerStatus,
    string ModelEventChain,bool OrdersSubmitted=false,bool CloudActivated=false);

public static class Ucp1CausalSignals
{
    public static Ucp1DecisionSignal[] Describe(Ucp1MarketFrame m,long at)
    {
        var x=(m.M5??Array.Empty<NativeClosedMarketBar>())
            .Where(p=>p.CloseAt<at).TakeLast(5).ToArray();
        var z=(m.M15??Array.Empty<NativeClosedMarketBar>())
            .Where(p=>p.CloseAt<at).TakeLast(3).ToArray();
        if(x.Length!=5||z.Length!=3 ||
           x.Any(t=>t.Open<=0 ||t.Close<=0||t.High<t.Low||
               t.CloseAt-t.OpenAt!=300000) ||
           z.Any(t=>t.Open<=0||t.Close<=0||
               t.CloseAt-t.OpenAt!=900000) ||
           x.Zip(x.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt) ||
           z.Zip(z.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt) ||
           at-x[^1].CloseAt>300000 ||
           at-z[^1].CloseAt>900000)
            return Array.Empty<Ucp1DecisionSignal>();
        decimal atr=0;
        for(int i=1;i<x.Length;i++)
            atr+=Math.Max(x[i].High-x[i].Low,
                Math.Max(Math.Abs(x[i].High-x[i-1].Close),
                         Math.Abs(x[i].Low-x[i-1].Close)));
        atr/=4m;
        if(atr<=0)return Array.Empty<Ucp1DecisionSignal>();
        decimal slope15=z[^1].Close-z[^2].Close;
        decimal priorHigh=x.Take(4).Max(p=>p.High);
        decimal priorLow=x.Take(4).Min(p=>p.Low);
        var list=new List<Ucp1DecisionSignal>();
        if(x[^1].Close>priorHigh && slope15>0)
            list.Add(new(m.Symbol,"RANGE_TRANSITION",1,atr,
                z.Average(p=>p.Close),Math.Max(atr,x[^1].Close-priorLow),
                x[^1].CloseAt));
        else if(x[^1].Close<priorLow && slope15<0)
            list.Add(new(m.Symbol,"RANGE_TRANSITION",-1,atr,
                z.Average(p=>p.Close),Math.Max(atr,priorHigh-x[^1].Close),
                x[^1].CloseAt));
        // Prior 3-bar directional displacement followed by first opposite
        // completed 5m bar; 15m slope still points toward prior extreme.
        decimal priorMove=x[^2].Close-x[0].Close;
        decimal repair=x[^1].Close-x[^2].Close;
        if(priorMove>atr && repair<0 && slope15>0)
            list.Add(new(m.Symbol,"EQUILIBRIUM_REPAIR",-1,atr,
                z.Average(p=>p.Close),Math.Max(atr,Math.Abs(priorMove)),
                x[^1].CloseAt));
        else if(priorMove< -atr && repair>0 && slope15<0)
            list.Add(new(m.Symbol,"EQUILIBRIUM_REPAIR",1,atr,
                z.Average(p=>p.Close),Math.Max(atr,Math.Abs(priorMove)),
                x[^1].CloseAt));
        return list.ToArray();
    }
}

// All model SOURCE and broker observation events are read-only or simulated.
// This class does not import cTrader Robot or expose any trade action.
public sealed class NativeUnifiedPortfolioEngine
{
    const string Version="UCP1_UNIFIED_CSHARP_COMPLETE_POLICY_V1";
    const long ResponseWindow=120000L;
    const long Latency=100L;
    readonly string policy;
    readonly NativeFundedSession model;
    readonly NativeFundedSession broker;
    readonly Dictionary<string,Ucp1Plan> plans=new(StringComparer.Ordinal);
    readonly Dictionary<string,long> lastSignalBar=new(StringComparer.Ordinal);
    readonly Dictionary<string,int> reasons=new(StringComparer.Ordinal);
    readonly List<LedgerEvent> facts=new();
    readonly List<Ucp1Episode> trips=new();
    readonly List<Ucp1CurvePoint> curve=new();
    long previousClock=-1,seq;
    int proposed,admitted,openFills,expiredOpens,expiredCloses,
        closeRequests,rejections,sourceUnknownClocks,gapExposures;
    string lastBrokerEvidence="NO_BROKER_FACT_REPLAY_ONLY";
    public NativeUnifiedPortfolioEngine(string policy,string brokerBinding="")
    {
        if(policy is not ("JOINT" or "TRANSITION_ONLY" or "REPAIR_ONLY" or
                          "LONG" or "SHORT" or "CASH"))
            throw new ArgumentException("UCP1_UNDECLARED_COMPLETE_POLICY");
        this.policy=policy;
        model=new NativeFundedSession("UCP1_MODEL_EUR300_"+policy);
        broker=new NativeFundedSession(string.IsNullOrWhiteSpace(brokerBinding)?
            "UCP1_BROKER_READ_ONLY_"+policy:brokerBinding);
    }
    private NativeUnifiedPortfolioEngine(Ucp1Checkpoint s)
    {
        if(s.Version!=Version)throw new ArgumentException("UCP1_CHECKPOINT_VERSION");
        policy=s.Policy;
        model=NativeFundedSession.Restore(s.Session,"UCP1_MODEL_EUR300_"+policy);
        broker=NativeFundedSession.Restore(s.BrokerSession,s.BrokerBinding);
        foreach(var p in s.Plans)plans.Add(p.Key,p.Value);
        foreach(var p in s.LastSignalBar)lastSignalBar.Add(p.Key,p.Value);
        foreach(var p in s.Reasons)reasons.Add(p.Key,p.Value);
        facts.AddRange(s.Events);trips.AddRange(s.Trips);curve.AddRange(s.Curve);
        previousClock=s.LastAt;seq=s.Sequence;
        proposed=s.Proposed;admitted=s.Admitted;openFills=s.OpenFills;
        expiredOpens=s.ExpiredOpens;expiredCloses=s.ExpiredCloses;
        closeRequests=s.CloseRequests;rejections=s.Rejections;
        sourceUnknownClocks=s.SourceUnknownClocks;gapExposures=s.GapExposures;
        lastBrokerEvidence=s.LastBrokerEvidence;
    }
    public static NativeUnifiedPortfolioEngine Restore(string checkpoint)
        =>new(JsonSerializer.Deserialize<Ucp1Checkpoint>(checkpoint)
             ??throw new ArgumentException("UCP1_MISSING_CHECKPOINT"));
    public LedgerEvent[] OriginalModelEvents=>facts.ToArray();
    public LedgerSummary ModelSummary=>model.Ledger.Summary();
    public string[] ActiveSymbols=>plans.Values.Where(p=>p.OpenAt>0)
        .Select(p=>p.Symbol).Distinct(StringComparer.Ordinal).ToArray();
    public string Checkpoint()=>JsonSerializer.Serialize(new Ucp1Checkpoint(
        Version,policy,model.Checkpoint(),broker.Checkpoint(),broker.AccountBinding,
        new(plans,StringComparer.Ordinal),new(lastSignalBar,StringComparer.Ordinal),
        previousClock,seq,proposed,admitted,openFills,expiredOpens,
        expiredCloses,closeRequests,rejections,sourceUnknownClocks,
        gapExposures,new(reasons,StringComparer.Ordinal),
        facts.ToArray(),trips.ToArray(),curve.ToArray(),lastBrokerEvidence));
    static string Sha(string s)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    LedgerEvent Event(string kind,long at,string id="",string sym="",int side=0,
        decimal units=0,decimal price=0,decimal fee=0,decimal margin=0,
        decimal slip=0,string reason="UCP1_MODEL_UNTRANSMITTED",
        LedgerQuote[]? quotes=null)
    {
        string eventId="UCP1/"+policy+"/"+(++seq)+"/"+kind+"/"+at;
        return new(eventId,at,kind,id,sym,side,units,price,fee,margin,
            slip,Math.Max(0,at-1),Math.Max(0,at-2),Latency,
            reason,Sha(eventId),quotes??Array.Empty<LedgerQuote>());
    }
    void Count(string s){reasons[s]=reasons.GetValueOrDefault(s)+1;}
    void Apply(LedgerEvent e)
    {
        model.ApplyResearchFacts(new[]{e});
        facts.Add(e);
    }
    static decimal Fee(LedgerQuote q,decimal units)
        =>Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);
    static string Week(long at)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);
    }
    // Official account/event status is observed and reconciled in an
    // independent broker-only session. It never emits or authorizes MODEL_FILL.
    void ReadBroker(Ucp1BrokerFrame? b)
    {
        if(b is null)return;
        if(b.AccountType is not ("Netted" or "Hedged"))
        {
            lastBrokerEvidence="BROKER_ACCOUNT_TYPE_UNKNOWN_PROTECTIVE";return;
        }
        if(b.Identity.AccountBinding!=broker.AccountBinding)
        {
            // Replay fixtures may specify symbolic account identity; never
            // alias a broker account to a model EUR300 funding balance.
            lastBrokerEvidence="BROKER_ACCOUNT_BINDING_MISMATCH_PROTECTIVE";return;
        }
        var report=broker.Observe(b.Identity,b.AccountCashEur);
        lastBrokerEvidence="BROKER_"+b.AccountType+"_"+
            report.Status+"_NO_MODEL_IMPORT";
    }
    public static bool ModelSlotsPermitAdmission(LedgerSummary summary,
        LedgerEvent[] pendingFacts)
    {
        if(pendingFacts is null || summary.OpenPositions<0)
            throw new ArgumentException("UCP1_INVALID_MODEL_CAPACITY_INPUT");
        int open=pendingFacts.Count(x=>x.Kind=="REQUEST_OPEN");
        return summary.OpenPositions+open<2;
    }
    public Ucp1FrameResult Advance(Ucp1Frame frame)
    {
        if(frame is null||frame.At<=previousClock||frame.At<=0||
           frame.Markets is null||frame.Markets.Select(m=>m.Symbol)
               .Distinct(StringComparer.Ordinal).Count()!=frame.Markets.Length||
           frame.Markets.Any(m=>m.Symbol!=m.Quote.Symbol||
               m.Quote.At!=frame.At||m.M5 is null||m.M15 is null||
               m.Contract is null||m.Contract.Symbol!=m.Symbol||
               m.Contract.MinimumUnits<=0||m.SlippagePerSideQuote<0))
            throw new ArgumentException("UCP1_NONCAUSAL_OBSERVATION_OR_DUPLICATE_CLOCK");
        ReadBroker(frame.Broker);
        long t=frame.At;
        var by=frame.Markets.ToDictionary(m=>m.Symbol,StringComparer.Ordinal);
        var quotes=frame.Markets.OrderBy(x=>x.Symbol,StringComparer.Ordinal)
            .Select(x=>x.Quote).ToArray();
        Apply(Event("MARK",t,reason:"AUTHENTIC_SOURCE_OR_PLATFORM_OBSERVATION",
            quotes:quotes));
        var start=model.Ledger.Summary(t);
        if(start.OpenPositions>0 && start.LiquidationEquityEur is null)
        {
            sourceUnknownClocks++;
            Count("UNKNOWN_HELD_LIQUIDATION_EQUITY_NO_NEW_ENTRY");
        }
        // Handle outstanding OPEN decisions first. A REQUEST is NOT a fill.
        foreach(var request in model.Ledger.PendingSnapshot()
            .Where(x=>x.Kind=="REQUEST_OPEN")
            .OrderBy(x=>x.PositionId,StringComparer.Ordinal).ToArray())
        {
            if(t-request.At>ResponseWindow)
            {
                Apply(Event("MODEL_OPEN_INTENT_EXPIRED",t,request.PositionId,
                    request.Symbol,request.Side,request.Units,
                    reason:"MODEL_UNTRANSMITTED_OPEN_RESPONSE_WINDOW_EXPIRED"));
                plans.Remove(request.PositionId);
                expiredOpens++;
                continue;
            }
            if(!by.TryGetValue(request.Symbol,out var input)||
               t<request.At+request.LatencyMs || t<=request.At)continue;
            var q=input.Quote;
            decimal px=request.Side>0?q.Ask+request.SlippagePerSide:
                q.Bid-request.SlippagePerSide;
            try
            {
                Apply(Event("OPEN_FILL",t,request.PositionId,request.Symbol,
                    request.Side,request.Units,px,Fee(q,request.Units),
                    q.MarginPerUnit,request.SlippagePerSide,
                    "LATER_AUTHENTIC_QUOTE_CONDITIONAL_MODEL_FILL"));
                var p=plans[request.PositionId];
                decimal risk=Math.Max(.00000001m,p.Atr*1.5m+
                    q.Ask-q.Bid+2m*request.SlippagePerSide)*request.Units*q.EurDebit;
                var entry=px;
                plans[request.PositionId]=p with {OpenAt=t,Entry=entry,
                    Units=request.Units,RiskEur=risk,Extreme=entry,
                    Stop=entry-request.Side*1.5m*p.Atr,LastObservedAt=t};
                openFills++;
            }
            catch(InvalidOperationException e) when(e.Message is
               ("NATIVE_LEDGER_UNFINANCED_MODEL_FILL" or
                "NATIVE_LEDGER_HELD_MARK_UNKNOWN"))
            {
                Apply(Event("MODEL_OPEN_INTENT_EXPIRED",t,request.PositionId,
                    request.Symbol,request.Side,request.Units,
                    reason:"MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED"));
                plans.Remove(request.PositionId);expiredOpens++;
                Count("MODEL_UNFINANCED_ENTRY_AT_LATER_OBSERVED_QUOTE");
            }
        }

        // Every held position persists across observation gaps. SIR1 can only
        // expire UNTRANSMITTED close requests, never broker orders or positions.
        foreach(var held in model.Ledger.PositionSnapshot()
            .OrderBy(x=>x.Id,StringComparer.Ordinal).ToArray())
        {
            if(held.EntryAt>=t)continue;
            if(!plans.TryGetValue(held.Id,out var p))
                throw new InvalidOperationException("UCP1_HELD_PLAN_MISSING");
            by.TryGetValue(held.Symbol,out var input);
            var q=input?.Quote;
            if(t-p.LastObservedAt>60000L)
            {
                p=p with {CrossedUnknownHistory=true};
                gapExposures++;
            }
            decimal direction=0;
            if(input is not null)
            {
                var m15=input.M15.Where(x=>x.CloseAt<t).TakeLast(2).ToArray();
                if(m15.Length==2&&m15[0].CloseAt==m15[1].OpenAt)
                    direction=m15[1].Close-m15[0].Close;
            }
            var state=new NativeModelCloseProtection(held.Id,
                p.Family=="EQUILIBRIUM_REPAIR"?"STRUCT":"ADAPT",
                new NativeExitSeed(p.Atr,p.Equilibrium),p.Stop,p.Extreme,
                p.LastObservedAt);
            var verdict=NativeSimulatedCloseLifecycle.Advance(model,state,
                new NativeModelCloseObservation(t,q,direction,t-1));
            facts.AddRange(verdict.AppliedFacts);
            expiredCloses+=verdict.AppliedFacts.Count(x=>
                x.Kind=="MODEL_CLOSE_INTENT_EXPIRED");
            closeRequests+=verdict.AppliedFacts.Count(x=>x.Kind=="REQUEST_CLOSE");
            if(q is not null)
            {
                decimal liquidation=held.Side>0?q.Bid-held.SlippagePerSide:
                    q.Ask+held.SlippagePerSide;
                decimal movement=held.Side*(liquidation-
                    (held.EntryPrice??throw new InvalidOperationException("UCP1_NO_ENTRY")));
                decimal eur=movement*held.Units*
                    (movement>=0?q.EurCredit:q.EurDebit);
                p=p with {MfeEur=Math.Max(p.MfeEur,eur),
                    MaeEur=Math.Min(p.MaeEur,eur)};
            }
            p=p with {Extreme=verdict.Protection.FavorableExtreme,
                LastObservedAt=q is null?p.LastObservedAt:t};
            plans[held.Id]=p;
            if(verdict.ModelPositionClosed)
            {
                var close=model.Ledger.ClosedFragments()
                    .Last(x=>x.PositionId==held.Id&&x.CompletesRoundTrip);
                trips.Add(new Ucp1Episode(held.Id,held.Symbol,p.Family,held.Side,
                    p.OpenAt,close.ClosedAt,held.Units,close.NetEur,
                    close.GrossEur,p.RiskEur,p.RiskEur>0?close.NetEur/p.RiskEur:null,
                    p.MfeEur,p.MaeEur,close.Reason,p.CrossedUnknownHistory));
                plans.Remove(held.Id);
            }
        }
        // Signal time is LAST COMPLETED M5 clock, not the still-forming bar.
        // Selection is conducted in one C# portfolio allocator, not per asset.
        if(policy!="CASH")
        {
            var options=new List<(Ucp1DecisionSignal Signal,Ucp1MarketFrame Frame)>();
            foreach(var m in frame.Markets.OrderBy(x=>x.Symbol,StringComparer.Ordinal))
            {
                var signals=Ucp1CausalSignals.Describe(m,t);
                if(signals.Length==0)continue;
                long completed=signals[0].LastCompletedM5At;
                if(lastSignalBar.GetValueOrDefault(m.Symbol)>=completed)continue;
                lastSignalBar[m.Symbol]=completed;
                var choices=policy switch {
                    "TRANSITION_ONLY"=>signals.Where(s=>s.Family=="RANGE_TRANSITION"),
                    "REPAIR_ONLY"=>signals.Where(s=>s.Family=="EQUILIBRIUM_REPAIR"),
                    "LONG"=>signals.Take(1).Select(s=>s with {Family="FUNDED_LONG_CONTROL",Side=1}),
                    "SHORT"=>signals.Take(1).Select(s=>s with {Family="FUNDED_SHORT_CONTROL",Side=-1}),
                    _=>signals.AsEnumerable()};
                foreach(var s in choices.Take(1)) options.Add((s,m));
            }
            proposed+=options.Count;
            var ledger=model.Ledger;
            var summary=ledger.Summary(t);
            // Held position with REQUEST_CLOSE retains its booked exposure
            // but its pending close NEVER consumes an extra position slot.
            // Pending REQUEST_OPEN does reserve a future capacity slot.
            // All held/pending-open marks must be present before marginal
            // scenario construction; UNKNOWN is not a zero-price exposure.
            var pendingEntryFacts=ledger.PendingSnapshot()
                .Where(x=>x.Kind=="REQUEST_OPEN").ToArray();
            if(summary.LiquidationEquityEur is decimal equity &&
               summary.FreeMarginEur is decimal free && equity>210m &&
               ModelSlotsPermitAdmission(summary,pendingEntryFacts) &&
               ledger.PositionSnapshot().All(x=>by.ContainsKey(x.Symbol)) &&
               pendingEntryFacts.All(x=>by.ContainsKey(x.Symbol)))
            {
                var baselines=new[]{"NORMAL","ADVERSE","PRESSURE"}
                    .Select(x=>new PortfolioScenario(x,t-1,true,0m,0m,0m,0m)).ToArray();
                var exposure=ledger.PositionSnapshot().Select(p=>
                    new ResearchExposureScenarios(p.Id,p.Symbol,p.Side,p.Units,
                        baselines.Select(s=>s with {
                            LossEur=2m*p.Units*by[p.Symbol].SlippagePerSideQuote*
                                by[p.Symbol].Quote.EurDebit,
                            MarginEur=p.Units*Math.Max(p.MarginPerUnit,
                                by[p.Symbol].Quote.MarginPerUnit)}).ToArray()))
                    .Concat(ledger.PendingSnapshot().Where(x=>x.Kind=="REQUEST_OPEN")
                    .Select(p=>new ResearchExposureScenarios(p.PositionId,p.Symbol,
                        p.Side,p.Units,baselines.Select(s=>s with {
                            LossEur=2m*p.Units*by[p.Symbol].SlippagePerSideQuote*
                                by[p.Symbol].Quote.EurDebit,
                            MarginEur=p.Units*Math.Max(p.MarginPerUnit,
                                by[p.Symbol].Quote.MarginPerUnit)}).ToArray())))
                    .ToArray();
                var offers=new List<EconomicOpportunity>();
                var terms=new List<ResearchEntryTerms>();
                var local=new Dictionary<string,Ucp1Plan>(StringComparer.Ordinal);
                foreach(var (signal,m) in options.OrderBy(x=>x.Signal.Symbol,StringComparer.Ordinal))
                {
                    if(ledger.PositionSnapshot().Any(x=>x.Symbol==signal.Symbol) ||
                       ledger.PendingSnapshot().Any(x=>x.Symbol==signal.Symbol))
                    {Count("ALREADY_HELD_OR_PENDING_SYMBOL");continue;}
                    decimal units=m.Contract.MinimumUnits,qCost=m.Quote.Ask-m.Quote.Bid;
                    decimal slip=m.SlippagePerSideQuote,qMargin=m.Quote.MarginPerUnit;
                    if(units<=0||slip<0||qMargin<=0||
                       m.Contract.VolumeStepUnits<=0 ||
                       m.Contract.MaximumUnits<units)
                    {Count("ORIGINAL_ACCOUNT_VOLUME_UNSUPPORTED");continue;}
                    decimal fee=Fee(m.Quote,units);
                    decimal excess=signal.ExpectedMove-
                        (qCost+2m*slip+2m*fee/units/m.Quote.EurDebit);
                    if(excess<=0){Count("NO_PREDECISION_COST_SURPLUS");continue;}
                    decimal riskPerUnit=(1.5m*signal.Atr+qCost+2m*slip)*
                        m.Quote.EurDebit;
                    string id="UCP1/"+policy+"/"+signal.Symbol+"/"+
                        signal.Family+"/"+t;
                    var samples=baselines.Select((s,i)=>
                        new OpportunityScenario(s.StateId,t-1,true,
                            excess*units*m.Quote.EurCredit*
                                (i==0?1m:i==1?.55m:-.3m),
                            0m,riskPerUnit*units*(i==2?1.5m:1m),
                            Math.Max(0,excess)*units*m.Quote.EurCredit))
                        .ToArray();
                    var grid=new AdaptiveRiskInputs(equity,0,free,
                        units,m.Contract.VolumeStepUnits,units,
                        qMargin,0,false,false,2,0m);
                    offers.Add(new EconomicOpportunity(id,signal.Family,m.Symbol,
                        m.Symbol,signal.Side,t,t-1,EvidenceLevel.Exploratory,
                        false,grid,samples));
                    terms.Add(new ResearchEntryTerms(id,Latency,slip,Sha(id)));
                    local[id]=new Ucp1Plan(id,m.Symbol,signal.Family,signal.Side,
                        signal.Atr,signal.Equilibrium,0m,0m,0m,0L,
                        0m,0m,0m,0m,0L,false);
                }
                if(offers.Count>0)
                {
                    try
                    {
                        string dId="UCP1/"+policy+"/"+t;
                        var d=new NativeResearchDecision(dId,t,
                            new ScenarioSizingInputs(equity,
                                Math.Max(equity,summary.ObservedPeakEur),free,
                                1m,1m,1m,1m,1m,2,0m),
                            baselines,offers.ToArray(),exposure,
                            terms.ToArray(),Sha(dId),
                            MaximumFundedOpenSlots:2);
                        var selected=model.DecideResearch(d);
                        foreach(var chosen in selected.Selection.Allocations)
                        {
                            var offer=offers.Single(x=>x.Id==chosen.Id);
                            var entry=terms.Single(x=>x.OpportunityId==chosen.Id);
                            // EXACT same fact constructed in DecideResearchCore,
                            // recorded for external event-chain verification.
                            var fact=new LedgerEvent("DECISION/"+d.Id+"/"+chosen.Id,t,
                                "REQUEST_OPEN",chosen.Id,offer.Symbol,offer.Direction,
                                chosen.Units,0m,0m,offer.VolumeGrid.MarginPerUnitEur,
                                entry.SlippagePerSide,offer.AvailableAt,
                                offer.CalibratedThrough,entry.LatencyMs,
                                "NATIVE_CONDITIONAL_SELECTION",entry.EvidenceHash,
                                Array.Empty<LedgerQuote>());
                            facts.Add(fact);
                            plans[chosen.Id]=local[chosen.Id];
                            admitted++;
                        }
                        foreach(var no in selected.Selection.Declined)
                        {Count(no.Reason);rejections++;}
                    }
                    catch(ArgumentException e){Count("UNIFIED_ADMISSION_"+e.Message);rejections++;}
                    catch(InvalidOperationException e){Count("UNIFIED_ADMISSION_"+e.Message);rejections++;}
                }
            }
            else if(options.Count>0){Count("COMMON_CAPITAL_OR_MARK_UNKNOWN");rejections+=options.Count;}
        }
        previousClock=t;
        var end=model.Ledger.Summary(t);
        curve.Add(new Ucp1CurvePoint(t,end.CashEur,end.LiquidationEquityEur,
            end.UsedMarginEur,end.OpenPositions,end.PendingIntents,
            end.CompleteRoundTrips));
        return new(policy,t,end,proposed,admitted,openFills,trips.Count,
            end.PendingIntents,end.OpenPositions,lastBrokerEvidence,
            end.EventChainHash);
    }
    public object OriginalOutcomeReport(long start,long calibrationStart,
        long evaluationStart,long end,string sourceSha256)
    {
        var last=model.Ledger.Summary();
        var complete=trips.ToArray();
        var stages=new[]{
            new {Name="DEVELOPMENT_GLOBALLY_EXPOSED",Lo=start,Hi=calibrationStart},
            new {Name="CALIBRATION_GLOBALLY_EXPOSED",Lo=calibrationStart,Hi=evaluationStart},
            new {Name="EVALUATION_GLOBALLY_EXPOSED",Lo=evaluationStart,Hi=end}
        };
        object Segment(string name,Ucp1Episode[] subset)
        {
            var wins=subset.Where(x=>x.NetEur>0).ToArray();
            var losses=subset.Where(x=>x.NetEur<0).ToArray();
            decimal sumGain=wins.Sum(x=>x.NetEur);
            decimal sumLoss=losses.Sum(x=>x.NetEur);
            return new {
                Name=name,CompleteConditionalFinancedModelTrips=subset.Length,
                ConditionalNetEurBeforeUnverifiedHistoricFinancing=subset.Sum(x=>x.NetEur),
                WinRate=subset.Length>0?(decimal?)wins.Length/subset.Length:null,
                ProfitFactor=losses.Length>0?(decimal?)(sumGain/-sumLoss):null,
                ExpectancyEurPerTrip=subset.Length>0?
                    (decimal?)subset.Average(x=>x.NetEur):null,
                PayoffWinLoss=losses.Length>0&&wins.Length>0?
                    (decimal?)(wins.Average(x=>x.NetEur)/
                        -losses.Average(x=>x.NetEur)):null,
                MeanR=subset.Where(x=>x.R is not null).Any()?
                    subset.Where(x=>x.R is not null).Average(x=>x.R!.Value):(decimal?)null,
                MedianNetEur=subset.Length>0?
                    (decimal?)subset.OrderBy(x=>x.NetEur)
                        .ElementAt(subset.Length/2).NetEur:null,
                WorstNetEur=subset.Length>0?(decimal?)subset.Min(x=>x.NetEur):null,
                BestNetEur=subset.Length>0?(decimal?)subset.Max(x=>x.NetEur):null,
                MeanSampledMfeEur=subset.Length>0?
                    (decimal?)subset.Average(x=>x.SampledMfeEur):null,
                MeanSampledMaeEur=subset.Length>0?
                    (decimal?)subset.Average(x=>x.SampledMaeEur):null,
                WithUnobservedExposureGap=subset.Count(x=>x.CrossedUnknownHistory),
                ModelFinancedCompleteTripsPerIsoWeek=subset
                    .GroupBy(x=>Week(x.CloseAt)).ToDictionary(x=>x.Key,x=>x.Count()),
                Reasons=subset.GroupBy(x=>x.ExitReason)
                    .ToDictionary(x=>x.Key,x=>x.Count()),
                ByFamily=subset.GroupBy(x=>x.Family)
                    .ToDictionary(x=>x.Key,x=>new {
                        Trades=x.Count(),ClosedNetEur=x.Sum(z=>z.NetEur)}),
                BySymbol=subset.GroupBy(x=>x.Symbol)
                    .ToDictionary(x=>x.Key,x=>new {
                        Trades=x.Count(),ClosedNetEur=x.Sum(z=>z.NetEur)})
            };
        }
        return new {
            Policy=policy,SourceSha256=sourceSha256,CapitalInitialEur=300m,
            Completed=Segment("ALL_GLOBALLY_EXPOSED",complete),
            Stages=stages.Select(s=>Segment(s.Name,complete.Where(x=>
                x.CloseAt>=s.Lo&&x.CloseAt<s.Hi).ToArray())).ToArray(),
            FinalCashEur=last.CashEur,
            LastSampledLiquidationEquityEur=last.LiquidationEquityEur,
            ClosedConditionalNetEurBeforeUnverifiedFunding=last.ClosedNetEur,
            SampledMaximumDrawdownNotContinuous=last.MaximumSampledDrawdown,
            MaximumObservedConcurrentOpen=curve.Count==0?0:curve.Max(x=>x.Held),
            MaximumObservedMarginEur=curve.Where(x=>x.UsedMarginEur is not null).Any()?
                (decimal?)curve.Where(x=>x.UsedMarginEur is not null)
                    .Max(x=>x.UsedMarginEur!.Value):null,
            PeakSampledEquityEur=curve.Where(x=>x.EquityEur is not null).Any()?
                (decimal?)curve.Where(x=>x.EquityEur is not null)
                    .Max(x=>x.EquityEur!.Value):null,
            HeldPositions=last.OpenPositions,PendingIntents=last.PendingIntents,
            proposed,admitted,openFills,expiredOpens,expiredCloses,
            closeRequests,rejections,sourceUnknownClocks,gapExposures,
            reasons,
            WeeklyCompleteFundedModelTrips=complete.GroupBy(x=>Week(x.CloseAt))
                .ToDictionary(x=>x.Key,x=>x.Count()),
            IndividualTrips=complete,
            SampledEquityCurve=curve.ToArray(),
            OriginalCSharpNativeLedgerEvents=facts.ToArray(),
            EventChainHash=last.EventChainHash,
            NoOrderSideEffect=true,NoCloudActivation=true,
            BrokerExecutedNetEur=(decimal?)null,
            CertifiedAdverseBrokerNetEur=(decimal?)null,
            CertifiedContinuousFloatingDd=(decimal?)null,
            CertifiedHard21=false,
            HistoricalFundingCertified=false,
            HistoricalTariffContinuityCertified=false,
            OriginalBrokerFillsCertified=false,
            Independent12MonthConfirmation=false,
            SourceQualification="GLOBALLY_EXPOSED_ORIGINAL_SAMPLE_M5_M15_PROXY_CONDITIONAL"
        };
    }
}
