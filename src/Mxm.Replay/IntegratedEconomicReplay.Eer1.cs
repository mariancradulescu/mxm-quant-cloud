using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record EerHop(string Symbol,string BaseAsset,string QuoteAsset);
    sealed record EerTape(string Name,SourceQuote[] Quotes,DatedRolloverQuote[] FundingQuotes);
    sealed record EerMarket(SourceMarket Market,long TermsAcquiredAt,long[]? ScheduledClocks)
    {
        public long[]? AmbiguousCalendarClocks { get; init; }
        public string? CalendarStatus { get; init; }
        public long[]? ClosedRolloverClocks { get; init; }
    }
    sealed record EerInput(long Start,long FitEnd,long End,string ProtocolSha256,string EngineRevision,
        string EvidenceManifestSha256,long SourceAcquiredAt,EerMarket[] Markets,EerTape[] Tapes,
        Dictionary<string,EerHop[]> Routes)
    {
        public bool ExtendedEconomicContext { get; init; }
    }
    sealed class EerStream
    {
        public EerMarket Source;
        public Dictionary<string,int> Counts=new(StringComparer.Ordinal);
        public Dictionary<long,string> Availability=new();
        public void Mark(long at,string reason){Count(reason);Availability[at]=reason;}
        public EerStream(EerMarket source){Source=source;}
        public void Count(string reason)=>Counts[reason]=Counts.GetValueOrDefault(reason)+1;
        public long? Next(long at)
        {
            if(Source.ScheduledClocks is not { } schedule)return null;
            int i=Array.BinarySearch(schedule,at);
            if(i<0)return null;
            if(i+1>=schedule.Length)return null;
            long next=schedule[i+1];
            if(Source.AmbiguousCalendarClocks is {Length:>0} ambiguous)
            {
                int first=Array.BinarySearch(ambiguous,at);
                if(first<0)first=~first;
                if(first<ambiguous.Length&&ambiguous[first]<next)return null;
            }
            return next;
        }

        public long? AtOrAfter(long from,long at)
        {
            if(Source.ScheduledClocks is not { } schedule)return null;
            int i=Array.BinarySearch(schedule,from);
            if(i<0)i=~i;
            if(i>=schedule.Length)return null;
            if(Source.AmbiguousCalendarClocks is {Length:>0} ambiguous)
            {
                int first=Array.BinarySearch(ambiguous,at);
                if(first<0)first=~first;
                if(first<ambiguous.Length&&ambiguous[first]<schedule[i])return null;
            }
            return schedule[i];
        }
    }
    static string EerHash(string text)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();

    sealed class EerEvidence
    {
        public long MinimumFundingHorizonMs {get;init;}
        public bool CaptureHoldingValuationGaps {get;init;}
        public bool RecoverFreshHoldingMarks {get;init;}
        public bool CaptureBetweenDecisionValuationGaps {get;init;}
        readonly HashSet<(string Symbol,long At,string Reason)> holdingValuationGaps=new();
        public object HoldingValuationGapReport()=>holdingValuationGaps.GroupBy(x=>new{x.Symbol,x.Reason})
            .OrderBy(g=>g.Key.Symbol,StringComparer.Ordinal).ThenBy(g=>g.Key.Reason,StringComparer.Ordinal)
            .Select(g=>new{g.Key.Symbol,g.Key.Reason,Clocks=g.Select(x=>x.At).OrderBy(x=>x).ToArray()}).ToArray();
        public EerInput Input;
        readonly Dictionary<string,Dictionary<long,SourceQuote>> tape;
        readonly Dictionary<string,Dictionary<long,DatedRolloverQuote>> funding;
        readonly Dictionary<string,EerMarket> marketCalendars;
        readonly Dictionary<string,NativeMarketTimeCalendar> marketTimeCalendars;
        public bool MarketTimeFx { get; init; }
        public EerProtectionTape? ValuationTape { get; init; }
        public Dictionary<string,int> FxEvidenceCounts { get; }=new(StringComparer.Ordinal);
        public Dictionary<string,NativeMarketTimePrice> ClosedPriceWitnesses { get; }=new(StringComparer.Ordinal);
        void FxCount(string reason)=>FxEvidenceCounts[reason]=FxEvidenceCounts.GetValueOrDefault(reason)+1;
        bool reuseCurrentFrames;
        readonly Dictionary<(string Asset,long At,bool Tick),NativeOriginalFxRate?> clockConversions=new();
        readonly Dictionary<(string Symbol,long At,decimal Stress),Ucp1MarketFrame?> protectionMarks=new();
        readonly Dictionary<(string Symbol,long At,string Scenario,decimal Stress),Ucp1MarketFrame?> intentMarks=new();
        readonly Dictionary<(string Symbol,long At),NativeBarWindow[]> transitionWindows=new();

        public void BeginHistoricalClock()
        {
            reuseCurrentFrames=true;
            clockConversions.Clear();
            protectionMarks.Clear();
            intentMarks.Clear();
            transitionWindows.Clear();
        }

        public EerEvidence(EerInput input)
        {
            Input=input;
            tape=input.Tapes.ToDictionary(m=>m.Name,m=>m.Quotes.ToDictionary(q=>q.At),StringComparer.Ordinal);
            funding=input.Tapes.ToDictionary(m=>m.Name,m=>m.FundingQuotes.ToDictionary(q=>q.At),StringComparer.Ordinal);
            marketCalendars=input.Markets.ToDictionary(m=>m.Market.Name,StringComparer.Ordinal);
            marketTimeCalendars=input.Markets.Where(m=>m.ScheduledClocks is not null&&m.AmbiguousCalendarClocks is not null&&
                m.CalendarStatus is "CONDITIONAL_OFFICIAL_SNAPSHOT" or "PARTIALLY_SUPPORTED_SNAPSHOT" or "SYNTHETIC_COMPLETE_CALENDAR")
                .ToDictionary(m=>m.Market.Name,m=>new NativeMarketTimeCalendar(input.Start,input.End+7*HistoricalDay,
                    m.ScheduledClocks,m.AmbiguousCalendarClocks,EerHash(input.EvidenceManifestSha256+"|"+m.Market.Name)),StringComparer.Ordinal);
        }
        public SourceQuote? At(string name,long at)=>tape.GetValueOrDefault(name)?.GetValueOrDefault(at);
        public DatedRolloverQuote? FundingAt(string name,long at)=>funding.GetValueOrDefault(name)?.GetValueOrDefault(at);

        bool VerifiedClosedNow(string name,long at)
        {
            if(at<Input.Start||at>=Input.End+7*HistoricalDay||marketTimeCalendars.GetValueOrDefault(name)?.Valid!=true||
                marketCalendars.GetValueOrDefault(name) is not {ScheduledClocks:{ } opened,AmbiguousCalendarClocks:{ } ambiguous})return false;
            long grid=at-(at-EurOffset)%EurStep;
            return Array.BinarySearch(opened,grid)<0&&Array.BinarySearch(ambiguous,grid)<0;
        }

        NativeMarketTimePrice? MarketPrice(string name,bool bid,long at,NativeHistoricalFundingPrefix? prefix=null)
        {
            prefix??=ValuationTape?.LatestPrefix(name,bid,at);
            var point=prefix is null?null:NativeMarketTimeFx.Resolve(prefix,at,marketTimeCalendars.GetValueOrDefault(name));
            if(point?.UsedClosedSessions==true)
            {FxCount("VERIFIED_CLOSED_SESSION_PRICE");ClosedPriceWitnesses[FormattableString.Invariant($"{name}/{(bid?"BID":"ASK")}/{at}")]=point;}
            else if(point is null)FxCount("MARKET_TIME_PRICE_UNSUPPORTED");
            return point;
        }

        public LedgerQuote[] HoldingValuations(NativeUnifiedPortfolioEngine book,Ucp1Frame frame,decimal stress)
        {
            if(!MarketTimeFx)return Array.Empty<LedgerQuote>();
            var observed=frame.Markets.Select(m=>m.Symbol).ToHashSet(StringComparer.Ordinal);
            var quotes=new List<LedgerQuote>();
            foreach(string name in book.ProtectionWatches().Select(w=>w.Symbol).Distinct(StringComparer.Ordinal))
            {
                void Gap(string reason)
                {
                    bool between=frame.Protection?.BetweenDecisions==true;
                    if(CaptureHoldingValuationGaps&&(!between||CaptureBetweenDecisionValuationGaps))
                        holdingValuationGaps.Add((name,frame.At,between?"BETWEEN_DECISIONS/"+reason:reason));
                }
                if(observed.Contains(name))continue;
                // An authenticated fresh tape mark is usable for held valuation only,
                // even when no complete executable market frame exists. Never create
                // a signal, execution or a synthetic price from a missing frame.
                if(RecoverFreshHoldingMarks&&ValuationTape is { } observedTape&&
                    marketCalendars.TryGetValue(name,out var holdingMarket)&&
                    ProtectionMark(observedTape,holdingMarket,frame.At,stress) is { } fresh)
                {
                    quotes.Add(fresh.Quote);
                    FxCount("FRESH_HELD_TAPE_VALUATION_NO_EXECUTION");
                    continue;
                }
                if(!marketCalendars.TryGetValue(name,out var m)||m.ScheduledClocks is null||m.AmbiguousCalendarClocks is null)
                {Gap("MISSING_CONTRACT_CALENDAR");continue;}
                if(!VerifiedClosedNow(name,frame.At))
                {Gap("NO_EXECUTABLE_FRAME_AND_NOT_VERIFIED_CLOSED");continue;}
                var bid=MarketPrice(name,true,frame.At);
                if(!CaptureBetweenDecisionValuationGaps&&bid is null){Gap("MISSING_CLOSED_BID_WITNESS");continue;}
                var ask=MarketPrice(name,false,frame.At);
                if(bid is null)Gap("MISSING_CLOSED_BID_WITNESS");
                if(ask is null)Gap("MISSING_CLOSED_ASK_WITNESS");
                if(bid is null||ask is null)continue;
                if(ask.Price<bid.Price){Gap("INCONSISTENT_CLOSED_MARK");continue;}
                if(m.Market.DatedDevelopment is not { } terms){Gap("MISSING_DATED_TERMS");continue;}
                if(ConversionAt(terms.Contract.QuoteAsset,frame.At,false,ValuationTape) is not { } fx)
                {Gap("MISSING_QUOTE_CONVERSION:"+terms.Contract.QuoteAsset);continue;}
                var usd=ConversionAt("USD",frame.At,false,ValuationTape);
                var min=terms.Contract.MinimumCommissionAsset is { } fee?ConversionAt(fee,frame.At,false,ValuationTape):null;
                decimal margin=terms.Margin.Where(x=>x.Units>0).Select(x=>Math.Max(x.BuyMargin,x.SellMargin)/x.Units).DefaultIfEmpty().Max();
                if(margin<=0m){Gap("MISSING_MARGIN");continue;}
                try
                {
                    decimal slip=(ask.Price-bid.Price)*stress;
                    var q=NativeBrokerContractCosts.QuoteBothDirections(terms.Contract,new(frame.At,bid.Price,ask.Price,
                        fx.CreditToEur,fx.DebitToEur,usd?.DebitToEur??0m,min?.DebitToEur,margin*terms.Contract.MinimumUnits,
                        terms.Contract.MinimumUnits,slip)).Quote;
                    quotes.Add(q with {LiquidationSlippagePerSide=slip,ExitFeePerUnit=q.ExitFeePerUnit*(1m+stress),
                        ExitFeeFloor=q.ExitFeeFloor*(1m+stress),SellFeePerUnit=q.SellFeePerUnit*(1m+stress)});
                    FxCount("CLOSED_HOLDING_CONDITIONAL_VALUATION_NO_EXECUTION");
                }
                catch(ArgumentException){FxCount("CLOSED_HOLDING_COST_UNSUPPORTED");Gap("CLOSED_HOLDING_COST_UNSUPPORTED");}
            }
            return quotes.ToArray();
        }

        NativeBarWindow[]? TransitionWindows(SourceMarket market,long at)
        {
            if(!Input.ExtendedEconomicContext)return null;
            if(transitionWindows.TryGetValue((market.Name,at),out var cached))return cached;
            NativeBarWindow Window(NativeBarTimeframe tf,NativeClosedMarketBar[] bars)
            {
                int lo=0,hi=bars.Length;
                while(lo<hi){int mid=lo+(hi-lo)/2;if(bars[mid].CloseAt<at)lo=mid+1;else hi=mid;}
                var rows=bars[Math.Max(0,lo-72)..lo];
                return new(tf,72,rows.LastOrDefault()?.CloseAt??0,at,"AUTHENTIC_EXTENDED_TRANSITION_CONTEXT",
                    rows.Length>=24?NativeBarStatus.Ready:NativeBarStatus.InsufficientHistory,rows);
            }
            var result=new[]{Window(NativeBarTimeframe.H1,market.H1),Window(NativeBarTimeframe.M15,market.M15),Window(NativeBarTimeframe.M5,market.M5)};
            transitionWindows.Add((market.Name,at),result);
            return result;
        }
        SourceQuote? LastClosedSessionMark(string name,long at)
        {
            if(marketCalendars.GetValueOrDefault(name) is not { ClosedRolloverClocks:{ } closed,ScheduledClocks:{ } schedule } market ||
               Array.BinarySearch(closed,at)<0)return null;
            int previous=Array.BinarySearch(schedule,at);
            if(previous>=0||~previous==0)return null;
            long clock=schedule[(~previous)-1];
            if(market.AmbiguousCalendarClocks is { Length:>0 } unclear)
            {
                int first=Array.BinarySearch(unclear,clock);
                if(first<0)first=~first;
                if(first<unclear.Length&&unclear[first]<=at)return null;
            }
            var prior=At(name,clock);
            return prior is not null&&Fresh(prior,clock,30_000L)?prior:null;
        }

        public NativeOriginalFxRate? ConversionAt(string asset,long at,bool charge,EerProtectionTape? protection=null,
            Dictionary<(string Symbol,long ChargeAt),long>? priorClocks=null)
        {
            if(!reuseCurrentFrames||charge)
                return SourceConversionAt(asset,at,charge,protection,priorClocks);
            var key=(asset,at,protection is not null);
            if(!clockConversions.TryGetValue(key,out var rate))
                clockConversions.Add(key,rate=SourceConversionAt(asset,at,false,protection,null));
            return rate;
        }

        NativeOriginalFxRate? SourceConversionAt(string asset,long at,bool charge,EerProtectionTape? protection,
            Dictionary<(string Symbol,long ChargeAt),long>? priorClocks)
        {
            if(asset=="EUR")return new(1m,1m,Array.Empty<string>());
            if(!Input.Routes.TryGetValue(asset,out var route)||route.Length is <1 or >4)return null;
            decimal credit=1m,debit=1m; string current=asset;
            var visited=new HashSet<string>(StringComparer.Ordinal){current};
            var hops=new List<NativeOriginalFxHop>();
            foreach(var h in route)
            {
                decimal bid,ask;
                if(charge)
                {
                    var q=FundingAt(h.Symbol,at);
                    if(q?.FundingPrice(false,7_200_000L,7_200_000L) is decimal fb&&
                       q.FundingPrice(true,7_200_000L,7_200_000L) is decimal fa&&fa>=fb)
                    {bid=fb;ask=fa;}
                    else if(priorClocks is not null && LastClosedSessionMark(h.Symbol,at) is { } prior)
                    {bid=prior.Bid;ask=prior.Ask;priorClocks[(h.Symbol,at)]=prior.At;}
                    else if(MarketTimeFx&&MarketPrice(h.Symbol,true,at,q?.LatestBidPrefix) is { } mb&&
                        MarketPrice(h.Symbol,false,at,q?.LatestAskPrefix) is { } ma&&ma.Price>=mb.Price)
                    {bid=mb.Price;ask=ma.Price;}
                    else return null;
                }
                else
                {
                    var q=protection?.QuoteAt(h.Symbol,at)??(MarketTimeFx?ValuationTape?.QuoteAt(h.Symbol,at):null)??At(h.Symbol,at);
                    if(q is null && protection is not null)
                        q=At(h.Symbol,(at-EurOffset)/EurStep*EurStep+EurOffset);
                    if(q is not null&&Fresh(q,at,30_000L))
                    {bid=q.Bid;ask=q.Ask;hops.Add(new(h.Symbol,h.BaseAsset,h.QuoteAsset,Math.Min(q.BidAt,q.AskAt),bid,ask,true));}
                    else if(MarketTimeFx&&VerifiedClosedNow(h.Symbol,at)&&MarketPrice(h.Symbol,true,at) is { } mb&&MarketPrice(h.Symbol,false,at) is { } ma&&ma.Price>=mb.Price)
                    {bid=mb.Price;ask=ma.Price;}
                    else return null;
                }
                if(string.IsNullOrWhiteSpace(h.BaseAsset)||string.IsNullOrWhiteSpace(h.QuoteAsset)||h.BaseAsset==h.QuoteAsset)return null;
                if(h.BaseAsset==current){credit*=bid;debit*=ask;current=h.QuoteAsset;}
                else if(h.QuoteAsset==current){credit/=ask;debit/=bid;current=h.BaseAsset;}
                else return null;
                if(!visited.Add(current))return null;
            }
            if(current!="EUR"||credit<=0m||debit<credit)return null;
            return charge||MarketTimeFx?new(credit,debit,route.Select(h=>h.Symbol).ToArray()):
                NativeBrokerContractCosts.ComposeCausalQuoteToEur(asset,at,hops);
        }
        // Same two accepted FX evidence paths as SourceConversionAt. Only
        // request missing sides when neither complete pair is available.
        public string[] MissingFundingFxSides(string name,long at)
        {
            var q=FundingAt(name,at);
            var fb=q?.FundingPrice(false,7_200_000L,7_200_000L);
            var fa=q?.FundingPrice(true,7_200_000L,7_200_000L);
            if(fb is decimal b&&fa is decimal a&&a>=b)return Array.Empty<string>();
            var mb=MarketTimeFx?MarketPrice(name,true,at,q?.LatestBidPrefix):null;
            var ma=MarketTimeFx?MarketPrice(name,false,at,q?.LatestAskPrefix):null;
            if(mb is not null&&ma is not null&&ma.Price>=mb.Price)return Array.Empty<string>();
            // Preserve contradictory existing quotes as a gap, not a new rate.
            if(fb.HasValue&&fa.HasValue)return Array.Empty<string>();
            var sides=new List<string>();
            if(!fb.HasValue)sides.Add("BID");
            if(!fa.HasValue)sides.Add("ASK");
            return sides.ToArray();
        }

        public NativeObservedRolloverQuote Charge(string name,string asset,long at,
            Dictionary<(string Symbol,long ChargeAt),long>? priorClocks=null)
        {
            var q=FundingAt(name,at);
            decimal? bid=q?.FundingPrice(false,7_200_000L,345_600_000L);
            if(bid is null && priorClocks is not null && LastClosedSessionMark(name,at) is { } prior)
            {bid=prior.Bid;priorClocks[(name,at)]=prior.At;}
            if(bid is null&&MarketTimeFx)bid=MarketPrice(name,true,at,q?.LatestBidPrefix)?.Price;
            return new(bid,ConversionAt(asset,at,true,priorClocks:priorClocks));
        }

        public decimal? ModeledFunding(DatedEurTerms terms,NativeFundingExposure exposure,long through,
            Dictionary<(string Symbol,long ChargeAt),long>? priorClocks=null)
        {
            try {return Financing(terms,exposure.FromExclusive,through,exposure.Side,exposure.Units,
                charge=>Charge(exposure.Symbol,terms.Contract.QuoteAsset,charge,priorClocks));}
            catch(ArgumentException){return null;}
        }
        public Ucp1MarketFrame? Frame(EerStream stream,long at,string scenario,decimal stress,bool general=false)
        {
            var m=stream.Source.Market;
            if(stream.Source.ScheduledClocks is null)
            {stream.Mark(at,general?stream.Source.CalendarStatus??"CALENDAR_NOT_COLLECTED":"UNKNOWN_OFFICIAL_SCHEDULE");return null;}
            if(general&&stream.Source.AmbiguousCalendarClocks is { } unclear&&Array.BinarySearch(unclear,at)>=0)
            {stream.Mark(at,"OFFICIAL_HOLIDAY_BOUNDS_AMBIGUOUS");return null;}
            long? next=stream.Next(at);
            if(next is null){stream.Mark(at,"SCHEDULE_CLOSED_OR_END");return null;}
            var q=At(m.Name,at);
            if(q is null||!Fresh(q,at,30_000L)){stream.Mark(at,"OPEN_SCHEDULE_MISSING_QUOTE");return null;}
            if(m.DatedDevelopment is not { } t||t.TradingMode!=0||m.EnabledAtCapture!=true)
            {stream.Mark(at,"CONTRACT_OR_TRADING_MODE");return null;}
            if(t.Margin.Length==0){stream.Mark(at,"MISSING_MARGIN");return null;}
            var c=t.Contract;
            var fx=ConversionAt(c.QuoteAsset,at,false);
            if(fx is null){stream.Mark(at,"MISSING_QUOTE_CONVERSION");return null;}
            var usd=ConversionAt("USD",at,false);
            var minFee=c.MinimumCommissionAsset is { } a?ConversionAt(a,at,false):null;
            decimal perUnit=t.Margin.Where(x=>x.Units>0m).Select(x=>Math.Max(x.BuyMargin,x.SellMargin)/x.Units).DefaultIfEmpty().Max();
            if(perUnit<=0m){stream.Mark(at,"NONPOSITIVE_MARGIN");return null;}
            decimal slip=(q.Ask-q.Bid)*stress;
            decimal costMultiple=1m+stress;
            LedgerQuote quote;
            try
            {
                quote=NativeBrokerContractCosts.QuoteBothDirections(c,new(at,q.Bid,q.Ask,fx.CreditToEur,fx.DebitToEur,
                    usd?.DebitToEur??0m,minFee?.DebitToEur,perUnit*c.MinimumUnits,c.MinimumUnits,slip)).Quote
                    with {LiquidationSlippagePerSide=slip};
                quote=quote with {ExitFeePerUnit=quote.ExitFeePerUnit*costMultiple,
                    ExitFeeFloor=quote.ExitFeeFloor*costMultiple,SellFeePerUnit=quote.SellFeePerUnit*costMultiple};
            }
            catch(ArgumentException){stream.Mark(at,"COMMISSION_OR_VOLUME_ROUTE_UNSUPPORTED");return null;}
            var margins=DatedMargins(t);
            long fundingThrough=MinimumFundingHorizonMs>0?
                stream.AtOrAfter(at+MinimumFundingHorizonMs,at)??next.Value:next.Value;
            var offers=ManagementFunding(margins,t,m.Name,at,fundingThrough,scenario,stress,q.Bid,fx);
            if(offers.Length==0)stream.Count("UNKNOWN_SCENARIO_CARRY");
            else stream.Count(next.Value>at+EurStep?"CLOSURE_CARRY_RESERVED":"CARRY_RESERVED");
            var context=DatedEurContext(m,q);
            foreach(var w in context.Windows)stream.Count(w.Timeframe+"_"+w.Status);
            stream.Mark(at,"MONETARY_FRAME");
            return new(m.Name,quote,c,context.For(NativeBarTimeframe.M5).Bars,context.For(NativeBarTimeframe.M15).Bars,
                slip,"AUTHENTIC_QUOTES_EXPLICIT_RETROSPECTIVE_TERMS_SCENARIO")
                {ClosedBars=context,EconomicTransitionWindows=TransitionWindows(m,at),OfficialAssetClass=m.OfficialAssetClass,EurDatedMarginScenario=true,
                 EurMargins=margins,FundingOffers=offers,EurTickSize=general?m.TickSize:null};
        }
        public void Advance(NativeUnifiedPortfolioEngine book,Ucp1Frame frame,
            Dictionary<string,EerStream> markets,string scenario,decimal stress)
        {
            var evidence=new List<NativeAccruedFundingEvidence>();
            foreach(var x in book.FundingEvidenceWindows())
            {
                long through=x.ClosedAt??frame.At;
                if(through<=x.FromExclusive||markets[x.Symbol].Source.Market.DatedDevelopment is not { } terms)continue;
                var prior=book.UsesClosedSessionFundingQuotes?new Dictionary<(string Symbol,long ChargeAt),long>():null;
                decimal? accrued=ModeledFunding(terms,x,through,prior);
                if(accrued is decimal amount)
                {
                    string provenance=prior is { Count:>0 }?"|CLOSED_SESSION|"+string.Join("|",prior
                        .OrderBy(p=>p.Key.Symbol,StringComparer.Ordinal).ThenBy(p=>p.Key.ChargeAt)
                        .Select(p=>FormattableString.Invariant($"{p.Key.Symbol}/{p.Key.ChargeAt}/{p.Value}"))):"";
                    evidence.Add(new(x.PositionId,x.Symbol,x.Side,x.Units,x.FromExclusive,through,frame.At,null,null,
                        EerHash(scenario+"|"+terms.Digest+"|"+x.PositionId+"|"+x.FromExclusive+"|"+through+provenance))
                        {ScenarioId=scenario,ConditionalSignedEur=amount<0m?amount*(1m+stress):amount,
                         SourceAcquiredAt=Input.SourceAcquiredAt});
                }
            }
            book.Advance(frame with {FundingEvidence=evidence.ToArray(),
                ConditionalHoldingValuations=MarketTimeFx?HoldingValuations(book,frame,stress):frame.ConditionalHoldingValuations});
        }

        public Ucp1MarketFrame? ProtectionMark(EerProtectionTape tape,EerMarket market,long at,decimal stress)
        {
            if(!reuseCurrentFrames)return BuildProtectionMark(tape,market,at,stress);
            var key=(market.Market.Name,at,stress);
            if(!protectionMarks.TryGetValue(key,out var mark))
                protectionMarks.Add(key,mark=BuildProtectionMark(tape,market,at,stress));
            return mark;
        }

        Ucp1MarketFrame? BuildProtectionMark(EerProtectionTape tape,EerMarket market,long at,decimal stress)
        {
            if(market.Market.DatedDevelopment is not { } terms || tape.QuoteAt(market.Market.Name,at) is not { } q)
                return null;
            var contract=terms.Contract;
            var fx=ConversionAt(contract.QuoteAsset,at,false,tape);
            if(fx is null)return null;
            var usd=ConversionAt("USD",at,false,tape);
            var minFee=contract.MinimumCommissionAsset is { } a?ConversionAt(a,at,false,tape):null;
            decimal perUnit=terms.Margin.Where(x=>x.Units>0m)
                .Select(x=>Math.Max(x.BuyMargin,x.SellMargin)/x.Units).DefaultIfEmpty().Max();
            if(perUnit<=0m)return null;
            decimal slip=(q.Ask-q.Bid)*stress;
            decimal costMultiple=1m+stress;
            try
            {
                var quote=NativeBrokerContractCosts.QuoteBothDirections(contract,new(at,q.Bid,q.Ask,fx.CreditToEur,fx.DebitToEur,
                    usd?.DebitToEur??0m,minFee?.DebitToEur,perUnit*contract.MinimumUnits,contract.MinimumUnits,slip)).Quote;
                return new(market.Market.Name,quote with
                {
                    LiquidationSlippagePerSide=slip,ExitFeePerUnit=quote.ExitFeePerUnit*costMultiple,
                    ExitFeeFloor=quote.ExitFeeFloor*costMultiple,SellFeePerUnit=quote.SellFeePerUnit*costMultiple
                },contract,Array.Empty<NativeClosedMarketBar>(),Array.Empty<NativeClosedMarketBar>(),slip,
                    "OBSERVED_TICK_CONDITIONAL_MONETARY_TERMS");
            }
            catch(ArgumentException){return null;}
        }

        public Ucp1MarketFrame? IntentEntryMark(EerProtectionTape tape,EerStream stream,long at,
            string scenario,decimal stress)
        {
            if(!reuseCurrentFrames)return BuildIntentEntryMark(tape,stream,at,scenario,stress);
            var key=(stream.Source.Market.Name,at,scenario,stress);
            if(!intentMarks.TryGetValue(key,out var mark))
                intentMarks.Add(key,mark=BuildIntentEntryMark(tape,stream,at,scenario,stress));
            return mark;
        }

        Ucp1MarketFrame? BuildIntentEntryMark(EerProtectionTape tape,EerStream stream,long at,
            string scenario,decimal stress)
        {
            var market=stream.Source.Market;
            if(ProtectionMark(tape,stream.Source,at,stress) is not { } seen ||
                tape.QuoteAt(market.Name,at) is not { } q ||
                market.DatedDevelopment is not { TradingMode:0 } terms || market.EnabledAtCapture!=true ||
                stream.AtOrAfter(at+EurStep,at) is not long through)return null;
            var fx=ConversionAt(terms.Contract.QuoteAsset,at,false,tape)!;
            var margins=DatedMargins(terms);
            var context=DatedEurContext(market,q);
            return seen with
            {
                M5=context.For(NativeBarTimeframe.M5).Bars,M15=context.For(NativeBarTimeframe.M15).Bars,
                ClosedBars=context,EconomicTransitionWindows=TransitionWindows(market,at),OfficialAssetClass=market.OfficialAssetClass,EurDatedMarginScenario=true,
                EurMargins=margins,FundingOffers=ManagementFunding(margins,terms,market.Name,at,
                    MinimumFundingHorizonMs>0?stream.AtOrAfter(at+MinimumFundingHorizonMs,at)??through:through,scenario,stress,q.Bid,fx),
                EurTickSize=market.TickSize
            };
        }

        static NativeEurMarginObservation[] DatedMargins(DatedEurTerms t)=>t.Margin.SelectMany(x=>new[]{
            new NativeEurMarginObservation(1,x.Units,x.BuyMargin,t.Contract.ObservedAtUtcMs,t.Digest),
            new NativeEurMarginObservation(-1,x.Units,x.SellMargin,t.Contract.ObservedAtUtcMs,t.Digest)})
            .Where(x=>x.MarginEur>0m&&(x.Side>0||t.ShortAllowed)).ToArray();

        static NativeFundingOfferEvidence[] ManagementFunding(NativeEurMarginObservation[] margins,DatedEurTerms terms,
            string symbol,long at,long next,string scenario,decimal stress,decimal bid,NativeOriginalFxRate rate)
        {
            var offers=new List<NativeFundingOfferEvidence>();
            foreach(var margin in margins)
            {
                decimal? amount;
                try {amount=Financing(terms,at,next,margin.Side,margin.Units,_=>new(bid,rate));}
                catch(ArgumentException){amount=null;}
                if(amount is decimal fundingDebit)offers.Add(new(symbol,margin.Side,margin.Units,
                    terms.Contract.ObservedAtUtcMs,terms.Contract.ObservedAtUtcMs,next,next,
                    Math.Max(0m,-fundingDebit)*(1m+stress),EerHash(scenario+"|"+terms.Digest+"|"+at+"|"+next))
                    {ScenarioId=scenario});
            }
            return offers.ToArray();
        }
    }

    static object EerBook(string policy,NativeUnifiedPortfolioEngine book,long start,long end,NativeEurCalibration? calibration,
        Dictionary<string,EerStream> streams)
    {
        var trips=book.CompleteModelTrips;
        var reconciled=book.ReconciledModelEpisodes.ToDictionary(x=>x.PositionId,StringComparer.Ordinal);
        var used=calibration?.Outcomes.Select(x=>x.PositionId).ToHashSet(StringComparer.Ordinal);
        var curve=book.CommonBookEquityPath;
        var risk=curve.Where(x=>x.FundingCapital?.ConditionalEquityEur is >0m)
            .Where(x=>x.UsedMarginEur.HasValue).Select(x=>(x.UsedMarginEur!.Value+x.FundingCapital!.PendingOpenMarginEur)/x.FundingCapital.ConditionalEquityEur!.Value).ToArray();
        var unknown=curve.Where(x=>x.FundingCapital?.ConditionalEquityEur is null).Select(x=>x.At).OrderBy(x=>x).ToArray();
        int run=0,maxRun=0;long prior=-1;
        foreach(long at in unknown){run=at-prior==EurStep?run+1:1;maxRun=Math.Max(run,maxRun);prior=at;}
        Dictionary<string,int> Coverage(Ucp1Episode x)
        {
            var counts=new Dictionary<string,int>(StringComparer.Ordinal);
            var clocks=streams[x.Symbol].Availability;
            for(long at=x.OpenAt;at<=x.CloseAt;at+=EurStep)
            {
                string reason=clocks.GetValueOrDefault(at,"UNOBSERVED_CLOCK");
                if(reason!="MONETARY_FRAME")counts[reason]=counts.GetValueOrDefault(reason)+1;
            }
            return counts;
        }
        return new {Base=DatedEurReport(policy,book,start,end,calibration),
            SampledUnknownEquityClocks=unknown.Length,LongestConsecutiveUnknownEquityClocks=maxRun,
            SampledUnknownEquityMinutes=unknown.Length*5,
            SampledFloatMinimumEur=curve.Where(x=>x.FundingCapital?.ConditionalEquityEur is not null)
                .Select(x=>x.FundingCapital!.ConditionalEquityEur-x.CashEur).DefaultIfEmpty(null).Min(),
            DaysWithClosed=trips.Select(x=>x.CloseAt/86_400_000L).Distinct().Count(),
            MaximumObservedHeldPendingEquityFraction=risk.Length==0?(decimal?)null:risk.Max(),
            ModeledClocksWithMarginOver70Percent=risk.Count(x=>x>.70m),
            CalibrationExcluded=used is null?null:trips.Where(x=>!used.Contains(x.PositionId)).Select(x=>new
            {
                x.PositionId,x.Symbol,x.Family,x.Side,x.OpenAt,x.CloseAt,x.Units,x.CrossedUnknownHistory,x.ExitReason,x.EntryRiskEur,
                MissingClocksByReason=Coverage(x),Context=x.EurContext,
                GrossEur=x.EconomicEvidence?.ClosedGrossEur??x.GrossEur,
                NetEur=reconciled.TryGetValue(x.PositionId,out var rec)?rec.Evidence.ClosedNetEur:null
            }).ToArray(),
            Episodes=trips.Select(x=>new {x.PositionId,x.Symbol,x.Family,x.Side,x.OpenAt,x.CloseAt,x.Units,x.CrossedUnknownHistory,
                GrossEur=x.EconomicEvidence?.ClosedGrossEur??x.GrossEur,
                ReconciledNetEur=reconciled.TryGetValue(x.PositionId,out var rec)?rec.Evidence.ClosedNetEur:null}).ToArray()};
    }

    public static int RunEer1(string inputPath,string reportPath,string calibrationFolder)
    {
        var raw=File.ReadAllBytes(inputPath);
        var input=JsonSerializer.Deserialize<EerInput>(raw,Json)??throw new ArgumentException("EER1_INPUT");
        long start=new DateTimeOffset(2026,10,26,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
        if(input.Start!=start||input.FitEnd!=start+14*86_400_000L||input.End!=start+28*86_400_000L||
            input.ProtocolSha256.Length!=64||input.EngineRevision.Length!=40||input.EvidenceManifestSha256.Length!=64||input.SourceAcquiredAt<input.End)
            throw new ArgumentException("EER1_PROTOCOL_BINDING");
        string manifest=Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant();
        var source=new EerEvidence(input);
        var names=new[]{NativeUnifiedPortfolioEngine.EurFirst,NativeUnifiedPortfolioEngine.EurRank,
            NativeUnifiedPortfolioEngine.EurContextRank,NativeUnifiedPortfolioEngine.EurCash};
        var results=new List<object>();
        foreach(var stress in new[]{0m,.5m,1m})
        {
            string label=stress==0m?"S0":stress==.5m?"S1":"S2";
            string id=EerHash(input.ProtocolSha256+"|"+input.EngineRevision+"|"+manifest+"|"+label);
            var streams=input.Markets.Select(x=>new EerStream(x)).ToDictionary(x=>x.Source.Market.Name,StringComparer.Ordinal);
            var fit=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurFirst,fundingScenarioId:id);
            var books=names.ToDictionary(x=>x,x=>new NativeUnifiedPortfolioEngine(x,fundingScenarioId:id));
            NativeEurCalibration? calibration=null;
            int matchedFit=0,matchedComparison=0;
            for(long at=input.Start+EurOffset;at<input.End;at+=EurStep)
            {
                var frames=streams.Values.Select(x=>source.Frame(x,at,id,stress)).OfType<Ucp1MarketFrame>().ToArray();
                var frame=new Ucp1Frame(at,frames);
                if(at<input.FitEnd)
                {if(frames.Length>=2)matchedFit++;source.Advance(fit,frame,streams,id,stress);}
                else
                {
                    if(calibration is null)
                    {
                        calibration=NativeUnifiedPortfolioEngine.Restore(fit.Checkpoint()).ExportEurCalibration();
                        if(calibration.ObservationThrough>=at||calibration.Outcomes.Any(x=>x.AvailableAt>=at))throw new ArgumentException("EER1_FUTURE_CALIBRATION");
                        books[NativeUnifiedPortfolioEngine.EurRank].LoadEurCalibration(calibration);
                        books[NativeUnifiedPortfolioEngine.EurContextRank].LoadEurCalibration(calibration);
                    }
                    if(frames.Length>=2)matchedComparison++;
                    foreach(var b in books.Values)source.Advance(b,frame,streams,id,stress);
                }
                if((at-EurOffset-input.Start)%86_400_000L==0)
                    Console.WriteLine("EER1 "+label+" day "+((at-input.Start)/86_400_000L+1)+" / 28");
            }
            if(calibration is null)throw new ArgumentException("EER1_EMPTY_FIT");
            File.WriteAllText(Path.Combine(calibrationFolder,label+"-calibration.json"),JsonSerializer.Serialize(calibration,Json));
            var pooled=books[NativeUnifiedPortfolioEngine.EurRank].EurOpportunityReceipts;
            var contextual=books[NativeUnifiedPortfolioEngine.EurContextRank].EurOpportunityReceipts;
            static (long,string,string,int,decimal) Match(NativeEurOpportunity x)=>(x.At,x.Symbol,x.Family,x.Side,x.Units);
            var matches=pooled.Join(contextual,Match,Match,(a,b)=>(a,b)).ToArray();
            results.Add(new {Stress=label,SlippagePerSideSpreadMultiple=stress,CommissionAndDebitMultiple=1m+stress,ScenarioId=id,
                ContextTransfer=new {Matched=matches.Length,ComparablePayoffs=matches.Count(p=>p.a.Payoff is not null&&p.b.Payoff is not null),
                    ChangedNetBound=matches.Count(p=>p.a.Payoff?.NetLowerEur!=p.b.Payoff?.NetLowerEur),
                    ChangedDecision=matches.Count(p=>p.a.Decision!=p.b.Decision)},
                FitClocksWithAtLeastTwo=matchedFit,ComparisonClocksWithAtLeastTwo=matchedComparison,
                MarketEvidence=streams.Values.Select(x=>new {x.Source.Market.Name,x.Source.Market.OfficialAssetClass,x.Source.TermsAcquiredAt,x.Counts}).ToArray(),
                Fit=EerBook(NativeUnifiedPortfolioEngine.EurFirst,fit,input.Start,input.FitEnd,calibration,streams),
                Books=names.Select(n=>EerBook(n,books[n],input.FitEnd,input.End,null,streams)).ToArray(),
                CalibrationEpisodes=calibration.Outcomes.Length,
                CalibrationDays=calibration.Outcomes.Select(x=>x.ClosedAt/86_400_000L).Distinct().Count(),
                CalibrationCells=calibration.Outcomes.GroupBy(x=>new {x.Family,x.Side,Symbol=x.Context?.Symbol,Class=x.Context?.AssetClass})
                    .Select(g=>new {g.Key,Episodes=g.Count(),Days=g.Select(x=>x.ClosedAt/86_400_000L).Distinct().Count(),
                        GrossEur=g.Sum(x=>x.GrossEur),NetEur=g.Sum(x=>x.NetEur)}).ToArray()});
            File.WriteAllText(reportPath,JsonSerializer.Serialize(new {Purpose="EER1_EXTENDED_EXPOSED_CONDITIONAL_DEVELOPMENT",
                ManifestSha256=manifest,input.EvidenceManifestSha256,input.ProtocolSha256,input.EngineRevision,input.SourceAcquiredAt,input.Start,input.FitEnd,input.End,
                Results=results,BrokerNetCertified=false,IndependentConfirmation=false,ContinuousDrawdownCertified=false,
                Hard21Certified=false,Orders=0,CloudActivated=false},Json));
        }
        return 0;
    }
}
