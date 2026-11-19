using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
namespace Mxm.Core;

// A NEW native, source-bound experiment. OEI1/A1/LPM1/SPE1/MVO1 are never called.
// These observations are original BID/ASK as-of snapshots, NOT executed fills.
public sealed record Npi1ObservedQuote(long At,decimal Bid,decimal Ask,long BidAt,long AskAt);
public sealed record Npi1OriginalMarket(string Name,NativeObservedContractTerms Contract,
    decimal MinMarginEur,decimal TickSize,Npi1ObservedQuote[] Quotes);
public sealed record Npi1OriginalTape(string OriginalSourceSha256,long Start,long End,
    Npi1OriginalMarket[] Markets);

public static class NativeNpi1IntegratedResearch
{
    private const long Minute=60000,Five=300000,Day=86400000;
    private sealed record Step(long At,decimal Mid,decimal Spread);
    private sealed record Signal(string Symbol,string Family,int Side,decimal Atr,
        decimal Equilibrium,decimal ExpectedMove);
    private sealed class Plan
    {
        public required string Id,Symbol,Family;
        public required int Side;
        public required decimal Atr,Equilibrium,Slippage;
        public long OpenedAt,LastAt;
        public decimal Entry,Extreme;
        public bool GapSeen;
    }
    private sealed class Book
    {
        public required string Name;
        public readonly NativeFundedSession Session=new("NPI1_RESEARCH_ONLY");
        public readonly Dictionary<string,Plan> Plans=new(StringComparer.Ordinal);
        public readonly Dictionary<string,List<Step>> History=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> Reasons=new(StringComparer.Ordinal);
        public int Proposals,Selected,OpenFills,CloseRequests,CloseFills,MissingHeldMarks,GapExposures;
        public int UnknownFinancingExposure,FeeSideUncertified;
        public long Serial;
        public void Count(string reason)=>Reasons[reason]=Reasons.GetValueOrDefault(reason)+1;
    }
    private static string Sha(string s)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    private static string Week(long t)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);
    }
    private static LedgerEvent Fact(Book b,long at,string kind,string id="",string symbol="",int side=0,
        decimal units=0,decimal price=0,decimal fee=0,decimal margin=0,decimal slip=0,
        string reason="SOURCE_BOUND",LedgerQuote[]? quotes=null,long available=0,long calibrated=0,long latency=100)
    {
        string eventId="NPI1/"+b.Name+"/"+(++b.Serial)+"/"+kind+"/"+at;
        return new LedgerEvent(eventId,at,kind,id,symbol,side,units,price,fee,margin,
            slip,available,calibrated,latency,reason,Sha(eventId),quotes??Array.Empty<LedgerQuote>());
    }
    private static decimal Fee(LedgerQuote q,decimal units)=>
        Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);

    // One clock's quote-to-cash terms come from the genuine same-clock original
    // EURUSD BID/ASK source and the previously observed original-account contract.
    private static bool TryQuote(Npi1OriginalMarket market,Npi1ObservedQuote x,
        Npi1ObservedQuote? fx,out LedgerQuote quote)
    {
        quote=null!;
        if(fx is null || x.At!=fx.At || x.Bid<=0 || x.Ask<x.Bid ||
           x.BidAt>x.At||x.AskAt>x.At||x.At-x.BidAt>30000||x.At-x.AskAt>30000||
           fx.Bid<=0||fx.Ask<fx.Bid||fx.At-fx.BidAt>30000||fx.At-fx.AskAt>30000||
           market.MinMarginEur<=0 || market.TickSize<=0 ||
           market.Contract.MinimumUnits<=0 || market.Contract.QuoteAsset!="USD")
            return false;
        // The native quote schema has one per-unit commission per market mark.
        // Price-sensitive rate types can require opposing entry/exit-side
        // fees not representable by one quote; fail closed on those types.
        if(market.Contract.CommissionType is 1 or 3)return false;
        try
        {
            var ctx=new NativeMarketCostContext(x.At,x.Bid,x.Ask,
                1m/fx.Ask,1m/fx.Bid,1m/fx.Bid,null,market.MinMarginEur,
                market.Contract.MinimumUnits,Math.Max(market.TickSize,x.Ask-x.Bid));
            quote=NativeBrokerContractCosts.Quote(market.Contract,ctx).Quote;
            return true;
        }
        catch(ArgumentException){return false;}
        catch(InvalidOperationException){return false;}
        catch(OverflowException){return false;}
    }
    private static Signal[] Candidates(Book b,Dictionary<string,LedgerQuote> quotes,
        long at)
    {
        if(!quotes.TryGetValue("EURUSD",out var fx) ||
           !b.History.TryGetValue("EURUSD",out var macro) || macro.Count<7)
            return Array.Empty<Signal>();
        var reference=macro[^1].Mid-macro[^4].Mid;
        var list=new List<Signal>();
        foreach(var (symbol,q) in quotes.OrderBy(x=>x.Key,StringComparer.Ordinal))
        {
            if(!b.History.TryGetValue(symbol,out var h)||h.Count<7)continue;
            var v=h.TakeLast(7).ToArray();
            if(v[^1].At!=at || v.Zip(v.Skip(1)).Any(p=>p.Second.At-p.First.At!=Five))
                continue;
            decimal mid=v[^1].Mid,drift5=mid-v[^2].Mid,drift15=mid-v[^4].Mid;
            decimal equilibrium=v.Average(x=>x.Mid);
            decimal atr=v.Zip(v.Skip(1)).Average(p=>Math.Abs(p.Second.Mid-p.First.Mid));
            decimal medianSpread=v.Take(6).OrderBy(x=>x.Spread).ElementAt(3).Spread;
            if(atr<=0 || medianSpread<=0 || q.Ask-q.Bid>1.5m*medianSpread)
                continue;
            // Cross-reference observable direction is a conditioning input,
            // never an ex-post favorable instrument or gap filter.
            if(drift5!=0 && Math.Sign(drift5)==Math.Sign(drift15) &&
               (symbol=="EURUSD" || Math.Sign(reference)==Math.Sign(drift15)) &&
               Math.Abs(drift15)>=.75m*atr)
                list.Add(new Signal(symbol,"CROSS_MARKET_PERSISTENCE",
                    Math.Sign(drift15),atr,equilibrium,Math.Abs(drift15)/3m));
            // A prior displacement followed by an observed opposite move.
            decimal priorDisplacement=v[^2].Mid-equilibrium;
            if(priorDisplacement!=0 && Math.Abs(priorDisplacement)>=1.25m*atr &&
               drift5!=0 && Math.Sign(drift5)!=Math.Sign(priorDisplacement))
                list.Add(new Signal(symbol,"MICROPRICE_REJECTION",
                    -Math.Sign(priorDisplacement),atr,equilibrium,Math.Abs(priorDisplacement)/3m));
        }
        return list.ToArray();
    }
    private static void AddHistory(Book b,Dictionary<string,LedgerQuote> quotes,long at)
    {
        if(at%Five!=0)return;
        foreach(var (symbol,q) in quotes)
        {
            if(!b.History.TryGetValue(symbol,out var h))
                b.History[symbol]=h=new List<Step>();
            h.Add(new Step(at,(q.Ask+q.Bid)/2m,q.Ask-q.Bid));
            if(h.Count>14)h.RemoveRange(0,h.Count-14);
        }
    }
    private static object Replay(string policy,Npi1OriginalTape tape)
    {
        var book=new Book{Name=policy};
        var markets=tape.Markets.ToDictionary(x=>x.Name,StringComparer.Ordinal);
        var chronological=tape.Markets.SelectMany(m=>m.Quotes.Select(x=>(m.Name,Q:x)))
            .GroupBy(x=>x.Q.At).OrderBy(g=>g.Key);
        foreach(var clock in chronological)
        {
            long t=clock.Key;
            var raw=clock.ToDictionary(x=>x.Name,x=>x.Q,StringComparer.Ordinal);
            raw.TryGetValue("EURUSD",out var fx);
            var quotes=new Dictionary<string,LedgerQuote>(StringComparer.Ordinal);
            foreach(var (symbol,x) in raw)
            {
                if(TryQuote(markets[symbol],x,fx,out var quote))quotes[symbol]=quote;
                else book.Count("ORIGINAL_QUOTE_CONTRACT_FX_OR_SIDE_FEE_INCOMPLETE");
            }
            if(quotes.Count==0)continue;
            var ledger=book.Session.Ledger;
            ledger.Apply(Fact(book,t,"MARK",quotes:quotes.Values.ToArray(),reason:"ORIGINAL_ASOF_QUOTE"));
            var postmark=ledger.Summary(t);
            if(postmark.OpenPositions>0 && postmark.LiquidationEquityEur is null)
            {
                book.MissingHeldMarks++;
                book.Count("HELD_POSITION_MARK_UNKNOWN_NO_NEW_ADMISSION");
            }

            // Consume genuine next observed quotes only. Pending intent never
            // turns into a fill during an unobserved interval or on its request clock.
            foreach(var request in ledger.PendingSnapshot().OrderBy(x=>x.PositionId,StringComparer.Ordinal).ToArray())
            {
                if(!quotes.TryGetValue(request.Symbol,out var q) ||
                   t<request.At+request.LatencyMs)continue;
                var plan=book.Plans.GetValueOrDefault(request.PositionId);
                if(plan is null)throw new InvalidOperationException("NPI1_PENDING_PLAN_ORIGIN_MISSING");
                if(request.Kind=="REQUEST_OPEN")
                {
                    decimal entry=request.Side>0?q.Ask+request.SlippagePerSide:
                        q.Bid-request.SlippagePerSide;
                    try
                    {
                        ledger.Apply(Fact(book,t,"OPEN_FILL",request.PositionId,request.Symbol,
                            request.Side,request.Units,entry,Fee(q,request.Units),
                            q.MarginPerUnit,request.SlippagePerSide,
                            "SOURCE_QUOTE_CONDITIONAL_MODEL_FILL",available:request.AvailableAt,
                            calibrated:request.CalibratedThrough,latency:request.LatencyMs));
                        plan.OpenedAt=t;plan.LastAt=t;plan.Entry=entry;plan.Extreme=entry;
                        book.OpenFills++;
                    }
                    catch(InvalidOperationException e) when(e.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL" ||
                        e.Message=="NATIVE_LEDGER_HELD_MARK_UNKNOWN")
                    {
                        // This is model-intent cancellation only, NOT broker fill or cancel.
                        ledger.Apply(Fact(book,t,"CONFIRMED_CANCEL",request.PositionId,
                            reason:"CONDITIONAL_INTENT_UNFINANCED_NO_BROKER_ORDER"));
                        book.Plans.Remove(request.PositionId);
                        book.Count("UNFINANCED_OR_UNMARKED_CONDITIONAL_OPEN_REJECTED");
                    }
                }
                else if(request.Kind=="REQUEST_CLOSE")
                {
                    var held=ledger.PositionSnapshot().SingleOrDefault(x=>x.Id==request.PositionId);
                    if(held is null)throw new InvalidOperationException("NPI1_UNMATCHED_HELD_CLOSE");
                    decimal exit=held.Side>0?q.Bid-held.SlippagePerSide:q.Ask+held.SlippagePerSide;
                    ledger.Apply(Fact(book,t,"CLOSE_FILL",held.Id,held.Symbol,held.Side,
                        held.Units,exit,Fee(q,held.Units),q.MarginPerUnit,
                        held.SlippagePerSide,request.Reason,
                        available:request.AvailableAt,calibrated:request.CalibratedThrough,
                        latency:request.LatencyMs));
                    book.Plans.Remove(held.Id);book.CloseFills++;
                }
            }

            // Evaluate the existing native causal exit on observed, real quote
            // marks. No fixed holding horizon; no synthesized stop fills.
            foreach(var held in ledger.PositionSnapshot().OrderBy(x=>x.Id,StringComparer.Ordinal).ToArray())
            {
                if(!quotes.TryGetValue(held.Symbol,out var q) ||
                   ledger.PendingSnapshot().Any(x=>x.PositionId==held.Id))continue;
                var p=book.Plans[held.Id];
                if(p.OpenedAt==t)continue;
                if(t-p.LastAt>Minute)
                {
                    p.GapSeen=true;book.GapExposures++;
                    if(t/Day>p.LastAt/Day)book.UnknownFinancingExposure++;
                }
                p.LastAt=t;
                decimal trend=0;
                if(book.History.TryGetValue(held.Symbol,out var history) && history.Count>=2 &&
                   history[^1].At<=t)
                    trend=history[^1].Mid-history[^2].Mid;
                decimal stop=p.Entry-p.Side*1.5m*p.Atr;
                var exit=NativeCausalExitResearch.AssessLifecycle(
                    p.Family=="CROSS_MARKET_PERSISTENCE"?"ADAPT":"STRUCT",
                    p.Side,p.Entry,new NativeExitSeed(p.Atr,p.Equilibrium),
                    stop,p.Extreme,q,trend,false);
                p.Extreme=exit.FavorableExtreme;
                if(!exit.RequestClose)continue;
                ledger.Apply(Fact(book,t,"REQUEST_CLOSE",held.Id,held.Symbol,held.Side,
                    held.Units,reason:exit.Reason,available:Math.Max(0,t-1),
                    calibrated:Math.Max(0,t-2),latency:100));
                book.CloseRequests++;
            }

            AddHistory(book,quotes,t);
            if(t%Five!=0 || ledger.PendingSnapshot().Any(x=>x.Kind=="REQUEST_CLOSE"))
                continue;
            var options=Candidates(book,quotes,t).Where(x=>policy=="FIRST" ||
                policy=="CROSS"&&x.Family=="CROSS_MARKET_PERSISTENCE" ||
                policy=="REJECT"&&x.Family=="MICROPRICE_REJECTION")
                .GroupBy(x=>x.Symbol).Select(x=>x.OrderBy(v=>v.Family,StringComparer.Ordinal).First())
                .OrderBy(x=>x.Symbol,StringComparer.Ordinal).ToArray();
            book.Proposals+=options.Length;
            if(options.Length==0)continue;
            var summary=ledger.Summary(t);
            if(summary.LiquidationEquityEur is not decimal equity ||
               summary.FreeMarginEur is not decimal free || equity<=0)
            {
                book.Count("ORIGINAL_HELD_OR_PENDING_MARK_UNKNOWN");
                continue;
            }
            var baselines=new[]{"NORMAL","ADVERSE","PRESSURE"}.Select(
                k=>new PortfolioScenario(k,t-1,true,0,0,0,0)).ToArray();
            var exposures=ledger.PositionSnapshot().Select(p=>
                new ResearchExposureScenarios(p.Id,p.Symbol,p.Side,p.Units,
                    baselines.Select(s=>s with {LossEur=2m*p.Units*
                        markets[p.Symbol].TickSize*quotes[p.Symbol].EurDebit,
                        MarginEur=p.Units*Math.Max(p.MarginPerUnit,quotes[p.Symbol].MarginPerUnit)}).ToArray()))
                .Concat(ledger.PendingSnapshot().Where(p=>p.Kind=="REQUEST_OPEN").Select(p=>
                    new ResearchExposureScenarios(p.PositionId,p.Symbol,p.Side,p.Units,
                        baselines.Select(s=>s with {LossEur=2m*p.Units*
                            markets[p.Symbol].TickSize*quotes[p.Symbol].EurDebit,
                            MarginEur=p.Units*Math.Max(p.MarginPerUnit,quotes[p.Symbol].MarginPerUnit)}).ToArray())))
                .ToArray();
            var opportunities=new List<EconomicOpportunity>();
            var terms=new List<ResearchEntryTerms>();
            var offeredPlans=new Dictionary<string,Plan>(StringComparer.Ordinal);
            foreach(var s in options)
            {
                var m=markets[s.Symbol];var q=quotes[s.Symbol];
                decimal units=m.Contract.MinimumUnits;
                decimal slip=Math.Max(m.TickSize,q.Ask-q.Bid);
                decimal friction=(q.Ask-q.Bid+2m*slip)*q.EurDebit+2m*Fee(q,units)/units;
                decimal expected=s.ExpectedMove*q.EurCredit-friction;
                if(expected<=0){book.Count("PREDECISION_EXPECTED_FRICITON_EXCEEDS_MOVE");continue;}
                decimal riskPerUnit=(2m*s.Atr+q.Ask-q.Bid+2m*slip)*q.EurDebit;
                string id="NPI1/"+policy+"/"+s.Symbol+"/"+t;
                decimal[] multipliers={1.0m,0.6m,-0.3m};
                var scenarios=baselines.Select((st,i)=>new OpportunityScenario(st.StateId,t-1,
                    true,expected*multipliers[i],0m,riskPerUnit*(i==2?1.5m:1m),
                    Math.Max(0,expected)*multipliers[i]>0?expected:0)).ToArray();
                var grid=new AdaptiveRiskInputs(equity,0,free,units,
                    m.Contract.VolumeStepUnits,units,q.MarginPerUnit,
                    0,false,false,3,0);
                opportunities.Add(new EconomicOpportunity(id,s.Family,s.Symbol,s.Symbol,s.Side,
                    t,t-1,EvidenceLevel.Exploratory,false,grid,scenarios));
                terms.Add(new ResearchEntryTerms(id,100,slip,Sha(id)));
                offeredPlans.Add(id,new Plan {Id=id,Symbol=s.Symbol,Family=s.Family,
                    Side=s.Side,Atr=s.Atr,Equilibrium=s.Equilibrium,Slippage=slip});
            }
            if(opportunities.Count==0)continue;
            try
            {
                var d=new NativeResearchDecision("NPI1/"+policy+"/"+t,t,
                    new ScenarioSizingInputs(equity,Math.Max(equity,summary.ObservedPeakEur),
                        free,1,1,1,1,1,3,0m),
                    baselines,opportunities.ToArray(),exposures,
                    terms.ToArray(),Sha("NPI1/"+policy+"/"+t));
                var selection=book.Session.DecideResearch(d);
                foreach(var admit in selection.Selection.Allocations)
                {
                    book.Plans.Add(admit.Id,offeredPlans[admit.Id]);
                    book.Selected++;
                }
                foreach(var declined in selection.Selection.Declined)book.Count(declined.Reason);
            }
            catch(ArgumentException e){book.Count("NATIVE_DECISION_REJECTED_"+e.Message);}
            catch(InvalidOperationException e){book.Count("NATIVE_DECISION_UNKNOWN_"+e.Message);}
        }
        var last=book.Session.Ledger.Summary();
        var completed=book.Session.Ledger.ClosedFragments();
        var perWeek=completed.Where(x=>x.CompletesRoundTrip)
            .GroupBy(x=>Week(x.ClosedAt)).ToDictionary(x=>x.Key,x=>x.Count());
        return new {
            Policy=policy,StartCashEur=300m,
            AuthenticatedOriginalSourceQuoteClocks=true,
            NativeCommonBookExecuted=true,NativeCoreAllocatorUsed=true,
            NativeSignalExitUsed=true,NoTradingOrders=true,
            book.Proposals,book.Selected,book.OpenFills,book.CloseRequests,book.CloseFills,
            book.GapExposures,book.MissingHeldMarks,book.UnknownFinancingExposure,
            HeldPositions=last.OpenPositions,UnfilledOrUnclosedIntents=last.PendingIntents,
            CompleteModeledTrips=last.CompleteRoundTrips,
            ConditionalQuotePricedClosedNetBeforeUnverifiedFinancingEur=last.ClosedNetEur,
            CashEur=last.CashEur,CurrentlyMarkedEquityEur=last.LiquidationEquityEur,
            SampledDrawdownNotContinuous=last.MaximumSampledDrawdown,
            EventChainHash=last.EventChainHash,
            ModeledTripsPerWeek=perWeek,Rejections=book.Reasons,
            RealizedBrokerNetEur=(decimal?)null,
            CertifiedAdverseNetEur=(decimal?)null,
            CertifiedContinuousFloatingDrawdown=(decimal?)null,
            CertifiedSystemicHard21=false,
            OriginalBrokerFillEvidence=false,
            HistoricalFundingAndTariffContinuityKnown=false,
            SourceSessionScheduleCertified=false,
            ResultStatus="ORIGINAL_OBSERVATIONS_CONDITIONAL_MODELED_LEDGER_NOT_BROKER_EXECUTION"
        };
    }
    public static object Evaluate(Npi1OriginalTape tape)
    {
        if(tape is null || tape.OriginalSourceSha256.Length!=64 ||
           !tape.OriginalSourceSha256.All(Uri.IsHexDigit) ||
           tape.Start<=0||tape.End<=tape.Start||tape.Markets is null||
           !tape.Markets.Select(x=>x.Name).OrderBy(x=>x,StringComparer.Ordinal)
                .SequenceEqual(new[]{"ETHUSD","EURUSD","SpotBrent","US500"}) ||
           tape.Markets.Any(m=>m.Contract is null || m.Contract.Symbol!=m.Name ||
               m.Quotes is null || m.Quotes.Any(x=>x.At<m.StartSafe(tape.Start) ||
                   x.At>=tape.End ||x.BidAt>x.At || x.AskAt>x.At ||
                   x.Bid<=0||x.Ask<x.Bid) ||
               m.Quotes.Zip(m.Quotes.Skip(1)).Any(x=>x.First.At>=x.Second.At)))
            throw new ArgumentException("NPI1_AUTHENTIC_SOURCE_SHAPE_OR_CLOCK");
        return new {Study="NPI1",tape.OriginalSourceSha256,
            Provenance="ORIGINAL_OEI1_44247979857_NEW_SOURCE_BOUND_CSHARP_REPLAY",
            SourceClasses=new[]{"FX","CRYPTO","ENERGY","INDEX"},
            SourceMarks=tape.Markets.ToDictionary(x=>x.Name,x=>x.Quotes.Length),
            CashComparatorEur=300m,
            FirstAdmissible=Replay("FIRST",tape),
            CrossMarketPersistence=Replay("CROSS",tape),
            MicropriceRejection=Replay("REJECT",tape),
            NewBrokerRequests=0,OrdersSubmitted=0,CloudActivated=false,
            Stage="GLOBALLY_EXPOSED_EXPLORATORY",
            IndependentConfirmation=false,NetCertified=false,
            ContinuousFloatingRiskCertified=false};
    }
    private static long StartSafe(this Npi1OriginalMarket m,long start)=>start;
}
