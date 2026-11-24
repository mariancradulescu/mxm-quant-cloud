using Mxm.Core;
using Mxm.Cloud;
using static Cpe1IntegratedEconomicChecks;

internal static class NativeEurPortfolioChecks
{
    const long Step=300_000L;
    static readonly long Origin=new DateTimeOffset(2026,11,24,14,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly string Proof=new string('a',64);

    static Ucp1Frame OfficialShape(int slot,int symbols)
    {
        long at=Origin+slot*Step;
        var frame=Frame(Origin,at,100.95m,unknownSwap:true);
        return frame with {Markets=Enumerable.Range(0,symbols).Select(i=>
        {
            var market=Named(frame.Markets[0],"MARKET"+i);
            return market with
            {
                EurMargins=new[]{new NativeEurMarginObservation(1,1m,1m,at,Proof)},
                FundingOffers=new[]{new NativeFundingOfferEvidence(market.Symbol,1,1m,at,at,at+Step,
                    at+Step,0m,Proof)}
            };
        }).ToArray()};
    }

    internal static void Run(Action<bool,string> check)
    {
        var first=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst);
        var rank=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank);
        var cash=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurCash);
        var parity=new NativeUnifiedCloudParityAdapter(NativeUnifiedPortfolioEngine.EurFirst);
        var input=OfficialShape(1,3);
        var initial=first.Advance(input);
        check(initial==parity.Observe(input) && initial is {Pending:3,Held:0,
            FundingCapital:{PendingOpenMarginEur:3m,DemonstrableFreeMarginEur:297m}},
            "EUR FIRST reserves three simultaneous positions in a single 300 EUR book");
        check(rank.Advance(input).Pending==0 && rank.EurOpportunityReceipts.Any(x=>
            x.Decision=="WAIT_RECONCILED_PAYOFF_EVIDENCE"),
            "EUR RANK waits with no causally reconciled payoffs");
        check(cash.Advance(input) is {Held:0,Pending:0,ModelBook.CashEur:300m},
            "EUR CASH receives the same input and preserves its own 300 EUR");
        var next=OfficialShape(2,3);
        var later=first.Advance(next);
        check(later==parity.Observe(next) && later is {Held:3,Pending:0,
            FundingCapital:{HeldMarginEur:3m,PendingOpenMarginEur:0m}},
            "Three witnessed fills are repriced and equity-admitted after Pending");
        var restored=NativeUnifiedPortfolioEngine.Restore(first.Checkpoint());
        check(restored.ModelSummary==first.ModelSummary,"EUR checkpoint retains common funded book");
    }
}
