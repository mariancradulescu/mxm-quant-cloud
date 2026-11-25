using Mxm.Core;
using Mxm.Cloud;
using static Cpe1IntegratedEconomicChecks;

internal static class NativeEurPortfolioChecks
{
    const long Step=300_000L;
    static readonly long Origin=new DateTimeOffset(2026,11,24,14,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly string Proof=new string('a',64);

    static Ucp1Frame OfficialShape(int slot,int symbols,long? day=null,decimal bid=100.95m,bool offer=true)
    {
        long origin=day??Origin;
        long at=origin+slot*Step;
        var frame=Frame(origin,at,bid,unknownSwap:true);
        return frame with {Markets=Enumerable.Range(0,symbols).Select(i=>
        {
            var market=Named(frame.Markets[0],"MARKET"+i);
            return market with
            {
                EurMargins=new[]{new NativeEurMarginObservation(1,1m,1m,at,Proof)},
                FundingOffers=offer?new[]{new NativeFundingOfferEvidence(market.Symbol,1,1m,at,at,at+Step,
                    at+Step,0m,Proof)}:null
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
        var known=later.FundingCapital!;
        const string missingMark="MISSING_CURRENT_LIQUIDATION_MARK";
        check(NativeUnifiedPortfolioEngine.EurRejectedCapital(missingMark,later.ModelBook,
                  known with { OutstandingDebitCeilingEur=null })=="WAIT_UNBOUNDED_PORTFOLIO_FUNDING"&&
              NativeUnifiedPortfolioEngine.EurRejectedCapital(missingMark,
                  later.ModelBook with {LiquidationEquityEur=null},known)=="WAIT_"+missingMark,
            "EUR distinguishes missing collateral marks from fully marked equity with unbounded carry");
        LateNetChangesRanking(check);
        ContractClocksAndDirectionalCosts(check);
        var flexible=input.Markets[0] with {EurNativeClock=true};
        check(NativeUnifiedPortfolioEngine.EurFrameFollows(flexible,input.At+1_000,input.At+Step+2_000)&&
            !NativeUnifiedPortfolioEngine.EurFrameFollows(flexible,input.At+1_000,input.At+2*Step+2_000)&&
            !NativeUnifiedPortfolioEngine.EurFrameFollows(input.Markets[0],input.At+1_000,input.At+Step+2_000),
            "Native platform margin observation jitter permits adjacent slots but cannot bridge a missing slot");
        const long day=86_400_000L;
        var opens=new[]{Origin,Origin+day,Origin+4*day};
        NativeClosedMarketBar Read(int index)
        {
            if(index==2)throw new InvalidOperationException("The active daily OHLC must never be read");
            return new(opens[index],opens[index]+day,100m,102m,99m,101m,100);
        }
        var ready=NativeClosedMarketContext.WitnessedDailySessions(2,opens[2]+15_000,opens[2]+1,"TEST_D1",
            opens.Length,i=>opens[i],Read);
        var tooEarly=NativeClosedMarketContext.WitnessedDailySessions(2,opens[2],opens[2]-1,"TEST_D1",
            opens.Length,i=>opens[i],Read);
        check(ready is {Ready:true,DailyCalendarBreaks:1}&&ready.Bars[1].OpenAt==opens[1]&&!tooEarly.Ready,
            "Daily EUR context retains a calendar gap and requires a witnessed active successor");
    }

    static void ContractClocksAndDirectionalCosts(Action<bool,string> check)
    {
        var c=OfficialShape(1,1).Markets[0].Contract with
            {CommissionType=3,PreciseRateWire=10_000,SwapPeriodHours=6,SwapTimeUtcMinute=240};
        var quote=NativeBrokerContractCosts.QuoteBothDirections(c,
            new(Origin,100m,101m,1m,1m,1m,null,1m,1m,0m)).Quote;
        check(quote is {ExitFeePerUnit:.101m,SellFeePerUnit:.100m} &&
            NativeExecutableEconomics.EstimateNet(quote,quote,1,1m,101m,100m,0m)==-1.201m &&
            NativeExecutableEconomics.EstimateNet(quote,quote,-1,1m,100m,101m,0m)==-1.201m,
            "Official proportional commission uses the witnessed bid on sells and ask on buys");
        long midnight=Origin/86_400_000L*86_400_000L;
        check(NativeBrokerContractCosts.NextScheduledSwapCharge(c,midnight+23*3_600_000L)==
            midnight+28*3_600_000L&&NativeBrokerContractCosts.NextScheduledSwapCharge(
                c with {SwapTimeUtcMinute=null},Origin) is null,
            "Rollover respects the first charge hour and preserves an absent official clock");
    }

    static void LateNetChangesRanking(Action<bool,string> check)
    {
        var profitable=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst);
        var financed=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst);
        const long day=86_400_000L;
        Ucp1Frame Evidence(Ucp1Frame frame,LedgerEvent fill,long through,decimal amount)
            =>frame with {FundingEvidence=new[]{new NativeAccruedFundingEvidence(fill.PositionId,fill.Symbol,
                fill.Side,fill.Units,fill.At,through,frame.At,amount,null,Proof)}};
        void Cycle(NativeUnifiedPortfolioEngine book,long origin,decimal late)
        {
            book.Advance(OfficialShape(1,1,origin));
            book.Advance(OfficialShape(2,1,origin));
            var fill=book.OriginalModelEvents.Last(e=>e.Kind=="OPEN_FILL");
            book.Advance(OfficialShape(3,1,origin,102.20m,offer:false));
            book.Advance(OfficialShape(4,1,origin,102.20m,offer:false));
            var closed=book.Advance(OfficialShape(5,1,origin,102.20m,offer:false));
            if(closed is not {Held:0,ModelBook.CompleteRoundTrips:>0})
                throw new InvalidOperationException("EUR test failed to close an observed favorable episode");
            book.Advance(Evidence(OfficialShape(6,1,origin,102.20m,offer:false),fill,origin+5*Step,late));
        }
        for(int i=0;i<20;i++)
        {
            Cycle(profitable,Origin+i*day,0m);
            Cycle(financed,Origin+i*day,-2m);
        }

        var positiveRank=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank);
        var negativeRank=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurRank);
        positiveRank.CalibrateEurRankFrom(profitable);
        negativeRank.CalibrateEurRankFrom(financed);
        var input=OfficialShape(1,1,Origin+20*day);
        var invalidClock=OfficialShape(1,1,Origin+19*day);
        var before=negativeRank.Checkpoint();
        try
        {
            negativeRank.Advance(invalidClock);
            check(false,"RANK cannot read a calibration completed after its decision");
        }
        catch(ArgumentException)
        {
            check(negativeRank.Checkpoint()==before,"Future calibration rejection is atomic");
        }
        negativeRank=NativeUnifiedPortfolioEngine.Restore(before);
        check(positiveRank.ModelSummary.CashEur==300m&&negativeRank.ModelSummary.CashEur==300m,
            "RANK calibration carries no cash from the FIRST ledger");
        check(positiveRank.Advance(input).Pending==1&&negativeRank.Advance(input).Pending==0,
            "Same recurrent gross with a late financing debit changes the actual RANK decision");
        var positive=positiveRank.EurOpportunityReceipts.Single().Payoff;
        var negative=negativeRank.EurOpportunityReceipts.Single().Payoff;
        check(positive is {GrossLowerEur:>0m,NetLowerEur:>0m} &&
            negative is {GrossLowerEur:>0m,NetLowerEur:<0m} &&
            positive.GrossLowerEur==negative.GrossLowerEur,
            "RANK keeps gross and reconciled net separate through settlement, scoring and admission");
    }
}
