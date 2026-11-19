using System;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace Mxm.Core;

// SIR1-SOURCE: fixed-clock original-source lifecycle witness, NOT an alpha
// policy; early model-close injection is explicitly a test stimulus.
// Reuses existing ledger/contract costs/causal exit, NEVER broker order APIs.
public sealed record Sir1SourceQuote(long At,decimal Bid,decimal Ask,
    long BidAt,long AskAt);
public sealed record Sir1SourceMarket(string Name,NativeObservedContractTerms Contract,
    decimal MinMarginEur,decimal TickSize,Sir1SourceQuote[] Quotes);
public sealed record Sir1OriginalSourceWitnessTape(string SourceSha256,
    Sir1SourceMarket[] Markets);
public sealed record Sir1SourceModelReceipt(string Policy,LedgerSummary Ledger,
    int ModeledOpened,int ModeledClosed,int ModelExpiredCloseIntents,
    int StillHeld,int PendingIntents,string[] Deferrals,
    LedgerEvent[] OriginalSourceBoundModelFacts,
    string SourceWindowStatus,string EvidenceClass);
public static class NativeSir1OriginalSourceWitness
{
    private static readonly string[] RequiredMarkets={"ETHUSD","EURUSD","SpotBrent","US500"};
    private static readonly long[] Clocks={
        new DateTimeOffset(2026,8,21,15,27,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
        new DateTimeOffset(2026,8,21,15,28,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
        new DateTimeOffset(2026,8,21,15,29,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
        new DateTimeOffset(2026,8,24,13,30,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
        new DateTimeOffset(2026,8,24,13,31,0,TimeSpan.Zero).ToUnixTimeMilliseconds(),
        new DateTimeOffset(2026,8,24,13,32,0,TimeSpan.Zero).ToUnixTimeMilliseconds()
    };
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static LedgerEvent Event(string policy,string kind,long at,string id="",
        string symbol="",int side=0,decimal units=0,decimal price=0,
        decimal fee=0,decimal margin=0,decimal slip=0,string reason="SIR1_ORIGINAL_MODEL_ONLY",
        LedgerQuote[]? quotes=null)
    {
        string eventId="SIR1_SOURCE/"+policy+"/"+kind+"/"+at+"/"+id;
        return new(eventId,at,kind,id,symbol,side,units,price,fee,
            margin,slip,at-1,at-2,100,reason,Hash(eventId),
            quotes??Array.Empty<LedgerQuote>());
    }
    static bool TryQuote(Sir1SourceMarket m,Sir1SourceQuote? original,
        Sir1SourceQuote? fx,out LedgerQuote result)
    {
        result=null!;
        if(original is null || fx is null || original.At!=fx.At ||
           original.At-original.BidAt>30000 ||
           original.At-original.AskAt>30000 ||
           fx.At-fx.BidAt>30000 ||fx.At-fx.AskAt>30000 ||
           original.BidAt>original.At ||original.AskAt>original.At ||
           fx.BidAt>fx.At ||fx.AskAt>fx.At ||
           original.Bid<=0||original.Ask<original.Bid ||
           fx.Bid<=0||fx.Ask<fx.Bid ||
           m.Contract.CommissionType is 1 or 3 ||
           m.Contract.QuoteAsset!="USD"||
           m.MinMarginEur<=0||m.TickSize<=0)
            return false;
        try
        {
            var quote=new NativeMarketCostContext(original.At,original.Bid,
                original.Ask,1m/fx.Ask,1m/fx.Bid,1m/fx.Bid,
                null,m.MinMarginEur,m.Contract.MinimumUnits,0m);
            result=NativeBrokerContractCosts.Quote(m.Contract,quote).Quote;
            return true;
        }
        catch(ArgumentException){return false;}
        catch(InvalidOperationException){return false;}
        catch(OverflowException){return false;}
    }
    private static Sir1SourceModelReceipt Replay(string policy,
        Sir1OriginalSourceWitnessTape input)
    {
        var model=new NativeFundedSession("SIR1_ORIGINAL_SOURCE_MODEL_"+policy);
        var raw=input.Markets.ToDictionary(x=>x.Name,StringComparer.Ordinal);
        var trace=new List<LedgerEvent>();
        var issues=new List<string>();
        var positions=new Dictionary<string,NativeModelCloseProtection>(StringComparer.Ordinal);
        var pendingOpen=new Dictionary<string,(Sir1SourceMarket Market,decimal Slip)>(StringComparer.Ordinal);
        var start=new Dictionary<string,LedgerQuote>(StringComparer.Ordinal);
        int opened=0,closed=0,expired=0;
        void Apply(LedgerEvent fact)
        {
            model.Ledger.Apply(fact);
            trace.Add(fact);
        }
        for(int k=0;k<Clocks.Length;k++)
        {
            long t=Clocks[k];
            var source=input.Markets.ToDictionary(m=>m.Name,
                m=>m.Quotes.SingleOrDefault(q=>q.At==t),StringComparer.Ordinal);
            var fx=source["EURUSD"];
            var valid=new Dictionary<string,LedgerQuote>(StringComparer.Ordinal);
            foreach(var m in input.Markets)
            {
                if(TryQuote(m,source[m.Name],fx,out var q))valid[m.Name]=q;
                else issues.Add("UNPRICED_OR_UNOBSERVED/"+m.Name+"/"+t);
            }
            if(k<3)
            {
                Apply(Event(policy,"MARK",t,reason:"ACTUAL_SOURCE_ASOF_QUOTE",
                    quotes:valid.Values.ToArray()));
                if(k==0)
                {
                    // Both controls have identical precommitted selection clocks,
                    // original instrument ordering, and the SAME EUR300 budget
                    // within each side's own counterfactual model account.
                    decimal reserved=0;
                    foreach(var market in input.Markets.OrderBy(m=>m.Name,StringComparer.Ordinal))
                    {
                        if(!valid.TryGetValue(market.Name,out var quote))continue;
                        decimal units=market.Contract.MinimumUnits;
                        decimal margin=units*quote.MarginPerUnit;
                        decimal slip=Math.Max(market.TickSize,quote.Ask-quote.Bid);
                        decimal expectedFees=2m*Math.Max(quote.ExitFeeFloor,quote.ExitFeePerUnit*units);
                        var book=model.Ledger.Summary(t);
                        if(book.FreeMarginEur is not decimal free || margin+reserved+
                           expectedFees+units*(quote.Ask-quote.Bid+2*slip)*quote.EurDebit>=free)
                        {
                            issues.Add("ORIGINAL_MINIMUM_NOT_FINANCED/"+market.Name);
                            continue;
                        }
                        string id="SIR1_MODEL/"+policy+"/"+market.Name;
                        int side=policy=="LONG"?1:-1;
                        Apply(Event(policy,"REQUEST_OPEN",t,id,market.Name,side,units,
                            margin:quote.MarginPerUnit,slip:slip,
                            reason:"SIR1_ORIGINAL_SOURCE_FIXED_CLOCK_CONTROL"));
                        pendingOpen.Add(id,(market,slip));
                        reserved+=margin;
                        start.Add(market.Name,quote);
                    }
                }
                else if(k==1)
                {
                    foreach(var p in model.Ledger.PendingSnapshot()
                        .Where(p=>p.Kind=="REQUEST_OPEN").ToArray())
                    {
                        if(!valid.TryGetValue(p.Symbol,out var quote))
                        {
                            issues.Add("ORIGINAL_ENTRY_OBSERVATION_MISSING/"+p.Symbol);
                            continue;
                        }
                        decimal entry=p.Side>0?quote.Ask+p.SlippagePerSide:
                            quote.Bid-p.SlippagePerSide;
                        decimal cost=Math.Max(quote.ExitFeeFloor,quote.ExitFeePerUnit*p.Units);
                        try
                        {
                            Apply(Event(policy,"OPEN_FILL",t,p.PositionId,p.Symbol,
                                p.Side,p.Units,entry,cost,quote.MarginPerUnit,
                                p.SlippagePerSide,"LATER_AUTHENTIC_QUOTE_MODEL_FILL"));
                            opened++;
                            var m=pendingOpen[p.PositionId].Market;
                            var previous=start[p.Symbol];
                            decimal atr=Math.Max(m.TickSize,
                                Math.Abs((quote.Bid+quote.Ask-
                                    previous.Bid-previous.Ask)/2m));
                            decimal riskDistance=Math.Max(2m*atr,
                                2m*(quote.Ask-quote.Bid));
                            var stop=entry-p.Side*riskDistance;
                            positions.Add(p.PositionId,
                                new NativeModelCloseProtection(p.PositionId,
                                    "ADAPT",new NativeExitSeed(atr,entry),
                                    stop,entry,t));
                        }
                        catch(InvalidOperationException ex)
                        {
                            issues.Add("UNFINANCED_MODEL_FILL_NO_FAKE_CANCEL/"+
                                p.Symbol+"/"+ex.Message);
                        }
                    }
                }
                else
                {
                    // Fixed-clock technical stress only, NEVER a normal signal
                    // exit or economic policy. It intentionally misses 15:30.
                    foreach(var held in model.Ledger.PositionSnapshot().ToArray())
                    {
                        if(model.Ledger.PendingSnapshot().Any(x=>x.PositionId==held.Id))
                            continue;
                        Apply(Event(policy,"REQUEST_CLOSE",t,held.Id,held.Symbol,
                            held.Side,held.Units,
                            reason:"MODEL_UNTRANSMITTED_SOURCE_WINDOW_STRESS_ONLY"));
                    }
                }
                continue;
            }
            foreach(var p in model.Ledger.PositionSnapshot().ToArray())
            {
                if(!positions.TryGetValue(p.Id,out var state))continue;
                var observed=valid.TryGetValue(p.Symbol,out var quote)?quote:null;
                var step=NativeSimulatedCloseLifecycle.Advance(model,state,
                    new NativeModelCloseObservation(t,observed));
                positions[p.Id]=step.Protection;
                trace.AddRange(step.AppliedFacts);
                expired+=step.AppliedFacts.Count(e=>e.Kind=="MODEL_CLOSE_INTENT_EXPIRED");
                closed+=step.AppliedFacts.Count(e=>e.Kind=="CLOSE_FILL");
            }
        }
        // Original, canonical model-fact stream is independently replayable
        // against the exact same already-installed native ledger class.
        var reconstructed=NativeFundedLedger.ReceiveFacts(trace.ToArray());
        var book=model.Ledger.Summary();
        // Strict original-source model replays can be still held; don't fabricate
        // floating equity over Friday–Monday or historically missing swaps.
        return new Sir1SourceModelReceipt(policy,book,opened,closed,expired,
            book.OpenPositions,book.PendingIntents,issues.Distinct().ToArray(),
            trace.ToArray(),
            "FRIDAY_SOURCE_WINDOW_END_IS_NOT_BROKER_SESSION_CLOSE",
            "ORIGINAL_PAIRED_BIDASK_CONDITIONAL_CURRENT_TARIFF_MODEL_NO_ORIGINAL_FILLS_OR_FUNDING");
    }
    public static object Evaluate(Sir1OriginalSourceWitnessTape input)
    {
        if(input is null ||input.SourceSha256 is null ||
           input.SourceSha256.Length!=64 || !input.SourceSha256.All(Uri.IsHexDigit) ||
           input.Markets is null ||input.Markets.Length!=4 ||
           !input.Markets.Select(m=>m.Name).OrderBy(x=>x,StringComparer.Ordinal)
             .SequenceEqual(RequiredMarkets) ||
           input.Markets.Any(m=>m.Contract is null||m.Contract.Symbol!=m.Name||
               m.Quotes is null||m.Quotes.Any(q=>!Clocks.Contains(q.At)||
               q.Bid<=0||q.Ask<q.Bid||q.BidAt>q.At||q.AskAt>q.At) ||
               m.Quotes.Zip(m.Quotes.Skip(1)).Any(z=>z.First.At>=z.Second.At)))
            throw new ArgumentException("SIR1_SOURCE_OR_CLOCKS_NOT_AUTHENTICALLY_BOUND");
        return new {Study="SIR1_SOURCE_WITNESS",input.SourceSha256,
            FrozenDates=Clocks,SourceOriginalRun=44247979857L,
            CashControlInitialAndFinalEur=300m,
            Long=Replay("LONG",input),Short=Replay("SHORT",input),
            CrossDayFinancingHistoricalUnknown=true,
            RealBrokerNetEur=(decimal?)null,AdverseBrokerNetEur=(decimal?)null,
            ContinuousFloatingDrawdown=(decimal?)null,
            FundedSystemHard21Certified=false,
            NeverBrokerOrdersSubmitted=true,CloudActivated=false,
            NotAProductionAlphaPolicy=true,IndependentConfirmation=false};
    }
}
