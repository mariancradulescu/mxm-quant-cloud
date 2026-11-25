using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    const long EurStep=300_000L;
    const long EurOffset=15_000L;
    static readonly long DatedEurStart=new DateTimeOffset(2026,11,4,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly long DatedEurComparison=new DateTimeOffset(2026,11,10,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly long DatedEurEnd=new DateTimeOffset(2026,11,16,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();

    sealed record DatedEurTerms(NativeObservedContractTerms Contract,NativeObservedVolume[] Margin,
        bool ShortAllowed,int TradingMode,bool? AccountSwapFree,string Digest,string SourceRun,
        int? AccountType,int? MoneyDigits,int? PriceDigits);

    sealed class DatedEurMarket
    {
        public readonly SourceMarket Source;
        readonly BarPrefix m5,m15;
        public readonly Dictionary<long,SourceQuote> Quotes;
        public readonly Dictionary<string,int> Counts=new(StringComparer.Ordinal);
        public DatedEurMarket(SourceMarket m)
        {
            Source=m;
            m5=new(m.M5,5);
            m15=new(m.M15,3);
            Quotes=m.Quotes.ToDictionary(q=>q.At);
        }
        void Count(string key)=>Counts[key]=Counts.GetValueOrDefault(key)+1;

        public Ucp1MarketFrame? Frame(long at,SourceQuote? eurUsd)
        {
            if(!Quotes.TryGetValue(at,out var q)||!Fresh(q,at,30_000L))
            {Count("NO_MATCHED_MARKET_QUOTE");return null;}
            Count("MARKET_QUOTE");
            var context=DatedEurContext(Source,q);
            foreach(var w in context.Windows)Count(w.Timeframe+"_"+w.Status);
            if(Source.DatedDevelopment is not { } terms || terms.Contract.ObservedAtUtcMs>at)
            {Count("NO_PRECEDING_AUTHENTIC_TERMS");return null;}
            if(terms.TradingMode!=0 || terms.Margin.Length==0)
            {Count("NO_PRECEDING_FULL_TRADE_MODE_AND_MARGIN");return null;}
            var c=terms.Contract;
            var fx=Conversion(c.QuoteAsset,at,eurUsd);
            if(fx is null){Count("NO_MATCHED_EUR_CONVERSION");return null;}
            decimal unitMargin=terms.Margin.Where(m=>m.Units>0m)
                .Select(m=>Math.Max(m.BuyMargin,m.SellMargin)/m.Units).DefaultIfEmpty().Max();
            LedgerQuote quote;
            try
            {
                quote=NativeBrokerContractCosts.QuoteBothDirections(c,new(at,q.Bid,q.Ask,fx.CreditToEur,
                    fx.DebitToEur,Conversion("USD",at,eurUsd)?.DebitToEur??0m,null,unitMargin*c.MinimumUnits,
                    c.MinimumUnits,0m)).Quote;
            }
            catch(ArgumentException){Count("DATED_COMMISSION_OR_VOLUME_UNSUPPORTED");return null;}
            var margins=terms.Margin.SelectMany(m=>new[]
            {
                new NativeEurMarginObservation(1,m.Units,m.BuyMargin,c.ObservedAtUtcMs,terms.Digest),
                new NativeEurMarginObservation(-1,m.Units,m.SellMargin,c.ObservedAtUtcMs,terms.Digest)
            }).Where(m=>m.MarginEur>0m&&(m.Side>0||terms.ShortAllowed)).ToArray();
            long next=at+EurStep;
            var offers=new List<NativeFundingOfferEvidence>();
            foreach(var m in margins)
            {
                // A forecast has no charge-time BID or conversion. Offer only
                // the bounds that the observed schedule can prove in advance.
                var expected=Financing(terms,at,next,m.Side,m.Units,_=>new(null,null));
                if(expected.HasValue)
                    offers.Add(new(Source.Name,m.Side,m.Units,c.ObservedAtUtcMs,c.ObservedAtUtcMs,next,next,
                        Math.Max(0m,-expected.Value),terms.Digest));
            }
            Count(offers.Count>0?"QUOTED_WITH_DATED_SCENARIO":"QUOTED_WITHOUT_FUNDING_BOUND");
            return new(Source.Name,quote,c,m5.Observe(at),m15.Observe(at),0m,
                "ORIGINAL_QUOTES_DATED_PRECEDING_TERMS_CONDITIONAL") {ClosedBars=context,
                OfficialAssetClass=Source.OfficialAssetClass,EurDatedMarginScenario=true,EurMargins=margins,
                FundingOffers=offers.ToArray()};
        }
    }

    static bool Fresh(SourceQuote q,long at,long maximumAge)
        =>q.At<=at&&q.BidAt<=q.At&&q.AskAt<=q.At&&at-Math.Min(q.BidAt,q.AskAt)<=maximumAge&&
            q.BidAt>0&&q.AskAt>0&&q.Bid>0m&&q.Ask>=q.Bid;

    static NativeBarContext DatedEurContext(SourceMarket market,SourceQuote quote)
    {
        var context=HistoricalContext(market,quote);
        var daily=ContextSource(market,NativeBarTimeframe.D1);
        if(daily is null)return context;
        long? witness=NativeClosedMarketContext.QuoteWitness(quote.At,quote.BidAt,quote.AskAt,30_000L);
        return context with {Windows=context.Windows.Select(w=>w.Timeframe!=NativeBarTimeframe.D1?w:
            NativeClosedMarketContext.WitnessedDailySessions(w.RequiredBars,quote.At,witness,daily.Source,
                daily.Bars.Length,i=>daily.Bars[i].OpenAt,i=>daily.Bars[i])).ToArray()};
    }

    static NativeOriginalFxRate? Conversion(string asset,long at,SourceQuote? eurUsd)
    {
        if(asset=="EUR")return NativeBrokerContractCosts.ComposeCausalQuoteToEur(asset,at,Array.Empty<NativeOriginalFxHop>());
        return asset=="USD"&&eurUsd is { } q&&Fresh(q,at,60_000L)?
            NativeBrokerContractCosts.ComposeCausalQuoteToEur(asset,at,new[] {
                new NativeOriginalFxHop("EURUSD","EUR","USD",Math.Min(q.BidAt,q.AskAt),q.Bid,q.Ask,true)}):null;
    }

    static decimal? Financing(DatedEurTerms terms,long from,long through,int side,decimal units,
        Func<long,NativeObservedRolloverQuote> quoteAt)
        =>NativeBrokerContractCosts.ObservedDailySwapEur(terms.Contract,from,through,side,units,
            terms.AccountSwapFree,terms.AccountType,terms.MoneyDigits,terms.PriceDigits,quoteAt);

    static NativeObservedRolloverQuote ChargeQuote(string asset,long charge,
        Dictionary<long,SourceQuote> market,Dictionary<long,SourceQuote> eurUsd)
    {
        long sample=NativeClosedMarketContext.LatestClock(charge,30_000L,EurOffset);
        var quote=market.GetValueOrDefault(sample);
        return new(quote is not null&&Fresh(quote,charge,60_000L)?quote.Bid:null,
            Conversion(asset,charge,eurUsd.GetValueOrDefault(sample)));
    }

    static void AdvanceDatedEur(NativeUnifiedPortfolioEngine book,Ucp1Frame frame,
        Dictionary<string,DatedEurTerms> terms,Dictionary<string,Dictionary<long,SourceQuote>> quotes,
        Dictionary<long,SourceQuote> fxQuotes)
    {
        var funding=new List<NativeAccruedFundingEvidence>();
        foreach(var x in book.FundingExposureSnapshot().Where(x=>x.ClosedAt is null||!x.ExactInLedger))
        {
            long through=x.ClosedAt??frame.At;
            if(through<=x.FromExclusive||!terms.TryGetValue(x.Symbol,out var t))continue;
            var market=quotes[x.Symbol];
            if(Financing(t,x.FromExclusive,through,x.Side,x.Units,
                charge=>ChargeQuote(t.Contract.QuoteAsset,charge,market,fxQuotes)) is decimal accrued)
                funding.Add(new(x.PositionId,x.Symbol,x.Side,x.Units,x.FromExclusive,through,frame.At,accrued,null,t.Digest));
        }
        book.Advance(frame with {FundingEvidence=funding.ToArray()});
    }

    static object DatedEurReport(string policy,NativeUnifiedPortfolioEngine engine,
        long from,long through,NativeEurCalibration? calibration)
    {
        var summary=engine.ModelSummary;
        var all=engine.CompleteModelTrips;
        var reconciled=engine.ReconciledModelEpisodes;
        var known=reconciled.ToDictionary(t=>t.PositionId,StringComparer.Ordinal);
        var curve=engine.CommonBookEquityPath;
        var candidates=engine.EurOpportunityReceipts;
        var realizedGross=all.Sum(t=>t.EconomicEvidence?.ClosedGrossEur??t.GrossEur);
        var settledNet=reconciled.Sum(r=>r.Evidence.ClosedNetEur);
        var weeks=Enumerable.Range(0,(int)((through-from)/86_400_000L))
            .Select(i=>Week(from+i*86_400_000L)).Distinct().ToArray();
        var final=curve.LastOrDefault()?.FundingCapital;
        var ledger=new NativeFundedLedger();
        foreach(var e in engine.OriginalModelEvents)ledger.Apply(e);
        if(ledger.Summary()!=summary)throw new InvalidOperationException("DATED_EUR_LEDGER_REPLAY");
        return new
        {
            Policy=policy,InitialCapitalEur=OwnerRiskAuthority.InitialCapitalEur,Summary=summary,
            ConditionalGrossClosedEur=all.Length>0?(decimal?)realizedGross:null,
            ConditionalNetReconciledClosedEur=reconciled.Length>0?settledNet:null,
            WholeFlatConditionalNetEur=all.Length==reconciled.Length&&summary.OpenPositions==0&&
                summary.PendingIntents==0?summary.ClosedNetEur:(decimal?)null,
            CertifiedBrokerNetEur=(decimal?)null,
            CompleteEpisodes=all.Length,ReconciledEpisodes=reconciled.Length,UnresolvedClose=all.Length-reconciled.Length,
            UnusableForFit=all.Count(t=>t.CrossedUnknownHistory),FinalFunding=final,
            CalibrationChain=calibration?.LedgerEventChainSha256,
            SampledHeldPeak=curve.Select(x=>x.Held).DefaultIfEmpty().Max(),
            HeldAndPendingPeakEur=curve.Max(x=>x.FundingCapital is { } c?c.HeldMarginEur+c.PendingOpenMarginEur:null),
            ClocksWithUnknownEquity=curve.Count(x=>x.EquityEur is null||x.FundingCapital?.DemonstrableEquityEur is null),
            ModelActions=engine.OriginalModelEvents.GroupBy(e=>e.Kind).ToDictionary(g=>g.Key,g=>g.Count()),
            Reductions=engine.OriginalModelEvents.Count(e=>e.Kind=="CLOSE_FILL"&&e.Reason.Contains("REDUCTION",StringComparison.Ordinal)),
            Weekly=weeks.Select(w=>new {Week=w,Closes=all.Count(t=>Week(t.CloseAt)==w),
                Reconciled=reconciled.Count(t=>all.Any(x=>x.PositionId==t.PositionId&&Week(x.CloseAt)==w))}).ToArray(),
            Contributions=all.GroupBy(t=>new {t.Symbol,t.Family,t.Side,AssetClass=t.EurContext?.AssetClass})
                .Select(g=>
                {
                    var matches=g.Where(t=>known.ContainsKey(t.PositionId)).ToArray();
                    return new {g.Key,Episodes=g.Count(),Reconciled=matches.Length,
                        ConditionalGrossEur=g.Sum(t=>t.EconomicEvidence?.ClosedGrossEur??t.GrossEur),
                        ReconciledNetEur=matches.Length>0?matches.Sum(t=>known[t.PositionId].Evidence.ClosedNetEur):null};
                }).ToArray(),
            Candidates=candidates.GroupBy(c=>c.Decision).ToDictionary(g=>g.Key,g=>g.Count()),
            PayoffCohorts=candidates.Where(c=>c.Payoff?.Cohort is not null).GroupBy(c=>c.Payoff!.Cohort!)
                .ToDictionary(g=>g.Key,g=>g.Count()),
            PositiveGrossBounds=candidates.Count(c=>c.Payoff?.GrossLowerEur>0m),
            PositiveNetBounds=candidates.Count(c=>c.Payoff?.NetLowerEur>0m),
            RecurrentConditionalPositiveWeeks=all.Where(t=>known.ContainsKey(t.PositionId)).GroupBy(t=>Week(t.CloseAt))
                .Count(g=>g.Sum(t=>known[t.PositionId].Evidence.ClosedNetEur)>0m),
            IndependentReplayExact=true
        };
    }

    public static int AuditDatedEurEvidence(string input,string report)
    {
        var source=JsonSerializer.Deserialize<Source>(File.ReadAllText(input),Json)
            ??throw new ArgumentException("DATED_EUR_SOURCE_MISSING");
        if(source.End!=DatedEurEnd||source.Start>DatedEurStart||source.ManagementIntervalMs!=30_000L)
            throw new ArgumentException("DATED_EUR_REGISTERED_WINDOW_MISMATCH");
        var fx=source.Markets.Single(m=>m.Name=="EURUSD").Quotes.ToDictionary(q=>q.At);
        var markets=source.Markets.Select(m=>
        {
            var clocks=m.Quotes.Where(q=>q.At>=DatedEurStart&&q.At<DatedEurEnd&&q.At%EurStep==EurOffset).ToArray();
            var days=clocks.Select(q=>DatedEurContext(m,q).For(NativeBarTimeframe.D1)).ToArray();
            var dated=m.DatedDevelopment;
            var c=dated?.Contract;
            var quotes=m.Quotes.ToDictionary(q=>q.At);
            var rollovers=new List<object>();
            if(dated is not null&&c is not null)
                for(long day=DatedEurStart;day<DatedEurEnd;day+=86_400_000L)
                {
                    long? roll=NativeBrokerContractCosts.NextScheduledSwapCharge(c,day-1);
                    if(roll is not long time||time>=day+86_400_000L)continue;
                    var quote=ChargeQuote(c.QuoteAsset,time,quotes,fx);
                    rollovers.Add(new {At=time,MarketBidWitness=quote.Bid.HasValue,
                        ConversionWitness=quote.QuoteToEur is not null});
                }
            return new {m.Name,OfficialClass=m.OfficialAssetClass,M5WitnessClocks=clocks.Length,
                DailySessionsReady=days.Count(d=>d.Ready),
                DailySessionGapsPreserved=days.Count(d=>d.DailyCalendarBreaks>0),
                DailyStatuses=days.GroupBy(d=>d.Status).ToDictionary(g=>g.Key.ToString(),g=>g.Count()),
                Terms=c is null?null:new {c.ObservedAtUtcMs,c.SwapCalculationType,
                    c.SwapPeriodHours,c.SwapTimeUtcMinute,WeekendFlag=c.ChargeSwapAtWeekends.HasValue,
                    SkipPeriods=c.SkipSwapPeriods.HasValue,TripleWeekday=c.TripleSwapWeekday.HasValue,
                    PipPosition=c.PipPosition.HasValue,LongRate=c.LongSwap.HasValue,ShortRate=c.ShortSwap.HasValue,
                    AccountType=dated!.AccountType,MoneyDigits=dated.MoneyDigits,PriceDigits=dated.PriceDigits},
                Rollovers=rollovers};
        }).ToArray();
        File.WriteAllText(report,JsonSerializer.Serialize(new {source.SourceRun,source.ProtocolSha256,Markets=markets,
            EconomicEvaluations=0,BrokerRequests=0,Orders=0,CloudActivated=false,HistoricalTariffContinuityCertified=false},Json));
        return 0;
    }

    public static int RunDatedEur(string input,string report,string calibrationPath)
    {
        var source=JsonSerializer.Deserialize<Source>(File.ReadAllText(input),Json)
            ??throw new ArgumentException("DATED_EUR_SOURCE_MISSING");
        if(source.End!=DatedEurEnd||source.Start>DatedEurStart||source.ManagementIntervalMs!=30_000L)
            throw new ArgumentException("DATED_EUR_REGISTERED_WINDOW_MISMATCH");
        var markets=source.Markets.Select(m=>new DatedEurMarket(m)).ToArray();
        var fx=markets.Single(m=>m.Source.Name=="EURUSD").Quotes;
        var quotes=markets.ToDictionary(m=>m.Source.Name,m=>m.Quotes,StringComparer.Ordinal);
        var terms=markets.Where(m=>m.Source.DatedDevelopment is not null)
            .ToDictionary(m=>m.Source.Name,m=>m.Source.DatedDevelopment!,StringComparer.Ordinal);
        var first=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst);
        var names=new[]{NativeUnifiedPortfolioEngine.EurFirst,NativeUnifiedPortfolioEngine.EurRank,
            NativeUnifiedPortfolioEngine.EurContextRank,NativeUnifiedPortfolioEngine.EurCash};
        var books=names.ToDictionary(n=>n,n=>new NativeUnifiedPortfolioEngine(n),StringComparer.Ordinal);
        var clocksWith2Quotes=new Dictionary<string,int>();
        var matchedClocks=new Dictionary<string,int>();
        NativeEurCalibration? calibration=null;
        string? firstCheckpointHash=null;
        decimal? firstCalibratedRankEquity=null;
        for(long at=DatedEurStart+EurOffset;at<DatedEurEnd;at+=EurStep)
        {
            var observed=markets.Select(m=>m.Frame(at,fx.GetValueOrDefault(at))).OfType<Ucp1MarketFrame>().ToArray();
            string phase=at<DatedEurComparison?"FIT":"COMPARISON";
            if(markets.Count(m=>m.Quotes.TryGetValue(at,out var q)&&Fresh(q,at,30_000L))>=2)
                clocksWith2Quotes[phase]=clocksWith2Quotes.GetValueOrDefault(phase)+1;
            if(observed.Length>=2)matchedClocks[phase]=matchedClocks.GetValueOrDefault(phase)+1;
            var frame=new Ucp1Frame(at,observed);
            if(at<DatedEurComparison){AdvanceDatedEur(first,frame,terms,quotes,fx);continue;}
            if(calibration is null)
            {
                string checkpoint=first.Checkpoint();
                firstCheckpointHash=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(checkpoint))).ToLowerInvariant();
                var restored=NativeUnifiedPortfolioEngine.Restore(checkpoint);
                if(restored.ModelSummary!=first.ModelSummary)throw new InvalidOperationException("DATED_EUR_FIT_CHECKPOINT");
                calibration=restored.ExportEurCalibration();
                if(calibration.ObservationThrough>=at || calibration.Outcomes.Any(r=>r.AvailableAt>=at))
                    throw new InvalidOperationException("DATED_EUR_FUTURE_OUTCOME");
                books[NativeUnifiedPortfolioEngine.EurRank].LoadEurCalibration(calibration);
                books[NativeUnifiedPortfolioEngine.EurContextRank].LoadEurCalibration(calibration);
                firstCalibratedRankEquity=books[NativeUnifiedPortfolioEngine.EurRank].ModelSummary.CashEur;
            }
            foreach(var book in books.Values)AdvanceDatedEur(book,frame,terms,quotes,fx);
        }
        if(calibration is null)throw new InvalidOperationException("DATED_EUR_CALIBRATION_WINDOW_EMPTY");
        File.WriteAllText(calibrationPath,JsonSerializer.Serialize(calibration,Json));
        var pooled=books[NativeUnifiedPortfolioEngine.EurRank].EurOpportunityReceipts;
        var contextual=books[NativeUnifiedPortfolioEngine.EurContextRank].EurOpportunityReceipts;
        var matched=pooled.Join(contextual,Match,Match,(a,b)=>(a,b)).ToArray();
        static (long,string,string,int,decimal) Match(NativeEurOpportunity c)=>(c.At,c.Symbol,c.Family,c.Side,c.Units);
        File.WriteAllText(report,JsonSerializer.Serialize(new
        {
            Purpose="AUTHENTIC_EUR_INTEGRATED_EXPOSED_DEVELOPMENT_DATED_SCENARIO",
            source.ProtocolSha256,source.SourceRun,Start=DatedEurStart,ComparisonStart=DatedEurComparison,EndExclusive=DatedEurEnd,
            CommonQuoteClocks=clocksWith2Quotes,CommonDatedMonetaryClocks=matchedClocks,
            Terms=terms.ToDictionary(p=>p.Key,p=>new {p.Value.SourceRun,p.Value.Contract.ObservedAtUtcMs,
                p.Value.Contract.SwapCalculationType,p.Value.Contract.SwapTimeUtcMinute,
                p.Value.Contract.SwapPeriodHours,p.Value.AccountSwapFree,p.Value.TradingMode}),
            MarketEvidence=markets.Select(m=>new {m.Source.Name,m.Source.OfficialAssetClass,m.Counts}).ToArray(),
            FirstCheckpointSha256=firstCheckpointHash,calibration.LedgerEventChainSha256,
            calibration.ObservationThrough,CalibrationEpisodes=calibration.Outcomes.Length,RankCapitalBeforeComparison=firstCalibratedRankEquity,
            CalibrationCells=calibration.Outcomes.GroupBy(x=>new {x.Family,x.Side})
                .Select(g=>new {g.Key,Episodes=g.Count(),Days=g.Select(x=>x.ClosedAt/86_400_000L).Distinct().Count(),
                    GrossEur=g.Sum(x=>x.GrossEur),NetEur=g.Sum(x=>x.NetEur)}).ToArray(),
            CalibrationBook=DatedEurReport(NativeUnifiedPortfolioEngine.EurFirst,first,DatedEurStart,DatedEurComparison,null),
            Books=names.Select(n=>DatedEurReport(n,books[n],DatedEurComparison,DatedEurEnd,
                n is NativeUnifiedPortfolioEngine.EurRank or NativeUnifiedPortfolioEngine.EurContextRank?calibration:null)).ToArray(),
            ContextTransfer=new {Matched=matched.Length,ComparablePayoffs=matched.Count(p=>p.a.Payoff is not null&&p.b.Payoff is not null),
                ChangedNetBound=matched.Count(p=>p.a.Payoff?.NetLowerEur!=p.b.Payoff?.NetLowerEur),
                ChangedDecision=matched.Count(p=>p.a.Decision!=p.b.Decision)},
            BrokerGrossCertified=false,BrokerNetCertified=false,HistoricalTariffContinuityCertified=false,
            IndependentConfirmation=false,ContinuousDrawdownCertified=false,Hard21Certified=false,
            OrdersSubmitted=0,CloudActivated=false
        },Json));
        return 0;
    }
}
