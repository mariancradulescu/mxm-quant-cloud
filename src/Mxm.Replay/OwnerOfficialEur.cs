using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

// The protected Open API readback supplies already authenticated observations.
// Every policy calls the same Core.Advance method as the Cloud parity adapter.
internal static class OwnerOfficialEur
{
    internal sealed record Market(NativeObservedContractTerms Contract,decimal Bid,decimal Ask,long QuoteAt,
        Dictionary<string,NativeOriginalFxHop[]?> Routes,string? MinimumFeeAsset,NativeEurMarginObservation[] Margin,
        Dictionary<string,long[][]> Bars,int? TradingMode,bool? ShortAllowed,long? VerifiedManagementClock,
        string ContractSha256,long? LastContractChange,bool? AccountSwapFree,long? LeverageId);
    internal sealed record Clock(long At,Market[] Markets);
    internal sealed record Input(Clock[] Frames,long StreamStart,long StreamEnd,bool ContinuousSessionObserved);

    static NativeClosedMarketBar[] Bars(Market m,string period,long width,long at)
        =>(m.Bars.GetValueOrDefault(period)??Array.Empty<long[]>()).Select(r=>
        {
            if(r.Length!=7||r[1]-r[0]!=width||r[1]>=at||r[4]<=0||r[4]>Math.Min(r[2],r[5])||
               r[3]<Math.Max(r[2],r[5])||r[6]<0)throw new ArgumentException("OFFICIAL_EUR_CLOSED_BAR");
            return new NativeClosedMarketBar(r[0],r[1],r[2]/100000m,r[3]/100000m,r[4]/100000m,r[5]/100000m,r[6]);
        }).OrderBy(r=>r.CloseAt).ToArray();

    // The official schedule expresses the first charge in UTC minutes and
    // period in hours. No source rate is used when a charge can occur.
    internal static bool NoScheduledCharge(Market m,long from,long through)
    {
        if(m.AccountSwapFree is not false || m.Contract.SwapPeriodHours is not int hours ||
            hours<=0||24%hours!=0||m.Contract.SwapTimeUtcMinute is not (>=0 and <1440))return false;
        long width=hours*3_600_000L;
        long phase=(m.Contract.SwapTimeUtcMinute!.Value*60_000L)%width;
        long next=(from-phase)/width*width+phase;
        if(next<=from)next+=width;
        return next>through;
    }

    static Ucp1MarketFrame? MarketFrame(Input input,Market market,long at)
    {
        var c=market.Contract;
        var margins=market.Margin.Where(x=>x.ObservedAt<=at&&at-x.ObservedAt<=60_000&&x.Units>0m&&x.MarginEur>0m)
            .ToArray();
        if(market.QuoteAt>at||at-market.QuoteAt>60_000||c.ObservedAtUtcMs>at||c.ObservedAtUtcMs<at-60_000||
           market.Bid<=0m||market.Ask<market.Bid||margins.Length==0)return null;
        try
        {
            NativeOriginalFxRate? Route(string asset)
                =>market.Routes.GetValueOrDefault(asset) is { } path
                    ?NativeBrokerContractCosts.ComposeCausalQuoteToEur(asset,at,path):null;
            var conversion=Route(c.QuoteAsset);
            if(conversion is null)return null;
            var usd=Route("USD")?.DebitToEur??0m;
            var minimumFee=market.MinimumFeeAsset is {Length:>0} f?Route(f)?.DebitToEur:null;
            decimal marginPerUnit=margins.Max(x=>x.MarginEur/x.Units);
            var quote=NativeBrokerContractCosts.Quote(c,new(at,market.Bid,market.Ask,conversion.CreditToEur,
                conversion.DebitToEur,usd,minimumFee,marginPerUnit*c.MinimumUnits,c.MinimumUnits,0m));
            var active=margins.Where(m=>market.TradingMode==0 && (m.Side>0||market.ShortAllowed is true)).ToArray();
            var offers=input.ContinuousSessionObserved && at>=input.StreamStart && market.VerifiedManagementClock is long next &&
                NoScheduledCharge(market,at,next)
                    ?active.Select(x=>new NativeFundingOfferEvidence(c.Symbol,x.Side,x.Units,c.ObservedAtUtcMs,
                        c.ObservedAtUtcMs,next,next,0m,market.ContractSha256)).ToArray()
                    :Array.Empty<NativeFundingOfferEvidence>();
            var m5=Bars(market,"M5",300_000,at);
            var m15=Bars(market,"M15",900_000,at);
            return new Ucp1MarketFrame(c.Symbol,quote.Quote,c,m5,m15,0m,
                "ORIGINAL_OBSERVED_QUOTE_CONDITIONAL_FILL_NO_HISTORICAL_SWAP_ASSUMPTION")
                {FundingOffers=offers,EurMargins=active};
        }
        catch(ArgumentException){return null;}
        catch(InvalidOperationException){return null;}
    }

    static NativeAccruedFundingEvidence[] Accrued(Input input,Clock clock,NativeUnifiedPortfolioEngine engine)
    {
        if(!input.ContinuousSessionObserved)return Array.Empty<NativeAccruedFundingEvidence>();
        var markets=clock.Markets.ToDictionary(x=>x.Contract.Symbol,StringComparer.Ordinal);
        var result=new List<NativeAccruedFundingEvidence>();
        foreach(var exposure in engine.FundingExposureSnapshot())
        {
            if(exposure.ClosedAt.HasValue&&exposure.ExactInLedger)continue;
            long through=exposure.ClosedAt??clock.At;
            if(exposure.FromExclusive<input.StreamStart||through>input.StreamEnd||
               !markets.TryGetValue(exposure.Symbol,out var market)||
               market.LastContractChange>exposure.FromExclusive||!NoScheduledCharge(market,exposure.FromExclusive,through))
                continue;
            var original=input.Frames.Where(f=>f.At<=exposure.FromExclusive)
                .SelectMany(f=>f.Markets.Where(m=>m.Contract.Symbol==exposure.Symbol)).LastOrDefault();
            if(original is null||original.ContractSha256!=market.ContractSha256)continue;
            result.Add(new(exposure.PositionId,exposure.Symbol,exposure.Side,exposure.Units,exposure.FromExclusive,
                through,clock.At,0m,null,market.ContractSha256));
        }
        return result.ToArray();
    }

    static object Portfolio(string policy,Input input,Ucp1MarketFrame[][] observations)
    {
        var engine=new NativeUnifiedPortfolioEngine(policy);
        var parity=new Mxm.Cloud.NativeUnifiedCloudParityAdapter(policy);
        var curve=new List<Ucp1FrameResult>();
        for(int i=0;i<input.Frames.Length;i++)
        {
            var clock=input.Frames[i];
            var frame=new Ucp1Frame(clock.At,observations[i])
                {FundingEvidence=Accrued(input,clock,engine)};
            var result=engine.Advance(frame);
            if(result!=parity.Observe(frame))throw new InvalidOperationException("OFFICIAL_EUR_ADAPTER_PARITY");
            curve.Add(result);
        }
        var events=engine.OriginalModelEvents;
        using var digest=System.Security.Cryptography.SHA256.Create();
        var audit=new NativeFundedLedger();
        foreach(var fact in events)audit.Apply(fact);
        var last=engine.ModelSummary;
        if(last!=audit.Summary())throw new InvalidOperationException("OFFICIAL_EUR_LEDGER_REPLAY");
        var trips=engine.CompleteModelTrips;
        var settled=engine.ReconciledModelEpisodes;
        var candidates=engine.EurOpportunityReceipts;
        var final=curve.LastOrDefault();
        decimal? conditionalNet=trips.Length>0&&settled.Length==trips.Length&&
            last.OpenPositions==0&&last.PendingIntents==0?settled.Sum(x=>x.Evidence.ClosedNetEur):null;
        return new
        {
            Policy=policy,InitialCapitalEur=OwnerRiskAuthority.InitialCapitalEur,
            MoneyEvidence="CONDITIONAL_MODEL_ON_AUTHENTIC_OFFICIAL_QUOTES",
            CompleteEpisodes=trips.Length,ReconciledEpisodes=settled.Length,
            GrossOnCompletedEur=trips.Length>0?trips.Sum(t=>t.EconomicEvidence?.ClosedGrossEur):(decimal?)null,
            ConditionalClosedNetEur=conditionalNet,BrokerCertifiedNetEur=(decimal?)null,
            ClosingCashEur=last.CashEur,ClosingLiquidationEquityEur=last.LiquidationEquityEur,
            DemonstrableFreeMarginEur=final?.FundingCapital?.DemonstrableFreeMarginEur,
            OutstandingHeldFunding=final?.FundingCapital?.OutstandingHeldWindows,
            OutstandingClosedFunding=final?.FundingCapital?.OutstandingClosedWindows,
            SampledDrawdown=last.MaximumSampledDrawdown,Held=last.OpenPositions,Pending=last.PendingIntents,
            PeakHeld=curve.Count==0?0:curve.Max(x=>x.Held),
            PeakPending=curve.Count==0?0:curve.Max(x=>x.Pending),
            PeakHeldAndPendingMarginEur=curve.Count==0?null:curve.Max(x=>x.FundingCapital is { } c?
                c.HeldMarginEur+c.PendingOpenMarginEur:null),
            IntentAndFillCounts=events.GroupBy(e=>e.Kind).ToDictionary(g=>g.Key,g=>g.Count()),
            ReductionFills=events.Count(e=>e.Kind=="CLOSE_FILL" && e.Reason=="MODEL_UNTRANSMITTED_INTEGRATED_FAVORABLE_REDUCTION"),
            SourceGaps=last.HistoryEvidenceIncomplete,
            ChoiceCounts=candidates.GroupBy(c=>c.Decision).ToDictionary(g=>g.Key,g=>g.Count()),
            CandidateCount=candidates.Length,MonetaryCandidates=candidates,
            NativeReplaySameLedger=true,CloudAdapterSameInputParity=true,
            EventTraceSha256=Convert.ToHexString(digest.ComputeHash(JsonSerializer.SerializeToUtf8Bytes(events))).ToLowerInvariant(),
            Hard21Certified=false,ContinuousDrawdownCertified=false,OrdersSubmitted=0,CloudActivated=false
        };
    }

    public static int Run(string inputFile,string output)
    {
        var options=new JsonSerializerOptions {NumberHandling=JsonNumberHandling.AllowReadingFromString};
        var input=JsonSerializer.Deserialize<Input>(File.ReadAllText(inputFile),options)
            ??throw new ArgumentException("OFFICIAL_EUR_SOURCE_MISSING");
        if(input.Frames.Length==0||input.Frames.Any(f=>f.At<input.StreamStart||f.At>input.StreamEnd)||
            !input.Frames.Zip(input.Frames.Skip(1)).All(p=>p.Second.At-p.First.At==300_000L))
            throw new ArgumentException("OFFICIAL_EUR_SOURCE_CLOCK");
        var observations=input.Frames.Select(f=>f.Markets.Select(m=>MarketFrame(input,m,f.At))
            .OfType<Ucp1MarketFrame>().ToArray()).ToArray();
        var reports=new[]{NativeUnifiedPortfolioEngine.EurFirst,NativeUnifiedPortfolioEngine.EurRank,
            NativeUnifiedPortfolioEngine.EurCash}.Select(p=>Portfolio(p,input,observations)).ToArray();
        File.WriteAllText(output,JsonSerializer.Serialize(new
        {
            Purpose="PROSPECTIVE_FUNDED_EUR_CAPACITY_WITNESS_WITH_AUTHENTIC_OBSERVATIONS",
            OfficialClockObservations=input.Frames.Select((f,i)=>new {f.At,MarketQuotes=observations[i].Length}),
            IndependentConfirmation=false,HistoricalSwapContinuityCertified=false,
            Books=reports
        },options));
        return 0;
    }
}
