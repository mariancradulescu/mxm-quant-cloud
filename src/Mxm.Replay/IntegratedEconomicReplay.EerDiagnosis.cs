using System.Globalization;
using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record EerClosedEpisode(string PositionId,string Symbol,string Family,int Side,long OpenAt,
        long CloseAt,decimal Units,bool CrossedUnknownHistory,decimal GrossEur,decimal? ReconciledNetEur);
    sealed record EerOriginalWindow(NativeFundingExposure Exposure);
    sealed record EerOriginalTicket(NativeEurOpportunity[] OpportunityDecisionTrace, EerOriginalWindow[] ScenarioFundingWindows);
    sealed record EerClosedBook(EerOriginalTicket Base, EerClosedEpisode[] Episodes);
    sealed record EerOriginalScenario(string Stress, string ScenarioId,decimal SlippagePerSideSpreadMultiple,
        EerClosedBook Fit,EerClosedBook[] Books);
    sealed record EerOriginalMoney(string EvidenceManifestSha256,string EngineRevision,string ProtocolSha256,
        EerOriginalScenario[] Results);
    sealed record EerClosedPart(long At,decimal Units,decimal SpreadEur,decimal SlippageEur,
        decimal ConversionEur,decimal CommissionEur,decimal GrossEur,decimal ConvertedEur);
    sealed record EerClosedAttribution(EerClosedEpisode Original,string Status,decimal? LotUnits=null,
        decimal? MinimumUnits=null,decimal? StepUnits=null,
        decimal? StopDistance=null,decimal? AdmissionRiskEur=null,decimal? FillRiskEur=null,
        decimal? GrossEur=null,decimal? SpreadEur=null,decimal? SlippageEur=null,decimal? ConversionEur=null,
        decimal? CommissionEur=null,decimal? FinancingEur=null,decimal? NetEur=null,decimal? MaximumExitBeyondStop=null,
        EerClosedPart[]? Parts=null);

    public static int AuditEerClosedSource(string protectedSource,string originalLedger,string output)
    {
        byte[] original = File.ReadAllBytes(originalLedger);
        const string digest = "b8239d32b80c5b6a87722ebb6e07de0a2455cea52e4b2dde460a52be38f4a9e2";
        if(GeneralSha(original)!=digest)throw new ArgumentException("EER1_CLOSED_ECONOMIC_SHA");
        var ticket=JsonSerializer.Deserialize<EerOriginalMoney>(original,Json)!;
        var source=JsonSerializer.Deserialize<EerInput>(File.ReadAllBytes(protectedSource),Json)!;
        if(source.EngineRevision!=ticket.EngineRevision || source.ProtocolSha256!=ticket.ProtocolSha256 ||
            source.EvidenceManifestSha256!=ticket.EvidenceManifestSha256 || source.Markets.Length!=16)
            throw new ArgumentException("EER1_DIAGNOSTIC_SOURCE_BINDING");
        var evidence=new EerEvidence(source);
        var reports=new List<object>();
        object? eligibility=null;
        foreach(var scenario in ticket.Results)
        {
            var streams=source.Markets.ToDictionary(m=>m.Market.Name,m=>new EerStream(m),StringComparer.Ordinal);
            Ucp1MarketFrame? Frame(string symbol,long at)=>
                evidence.Frame(streams[symbol],at,scenario.ScenarioId,scenario.SlippagePerSideSpreadMultiple,general:true);
            if(eligibility is null)
            {
                var carryReady=new Dictionary<(string,bool),int>();
                for(long at=source.Start+EurOffset;at<source.End;at+=EurStep)
                    foreach(var name in streams.Keys)
                        if(Frame(name,at)?.FundingOffers is {Length:>0})
                        {
                            var key=(name,at<source.FitEnd);
                            carryReady[key]=carryReady.GetValueOrDefault(key)+1;
                        }
                eligibility=streams.Values.Select(x=>new {x.Source.Market.Name,x.Source.CalendarStatus,
                    ScheduledFit=x.Source.ScheduledClocks?.Count(t=>source.Start<=t&&t<source.FitEnd),
                    ScheduledComparison=x.Source.ScheduledClocks?.Count(t=>source.FitEnd<=t&&t<source.End),
                    MonetaryFit=x.Availability.Count(t=>t.Key<source.FitEnd&&t.Value=="MONETARY_FRAME"),
                    MonetaryComparison=x.Availability.Count(t=>t.Key>=source.FitEnd&&t.Value=="MONETARY_FRAME"),
                    FitWithFundingOffer=carryReady.GetValueOrDefault((x.Source.Market.Name,true)),
                    ComparisonWithFundingOffer=carryReady.GetValueOrDefault((x.Source.Market.Name,false)),
                    x.Counts}).ToArray();
            }
            object Ledger(EerClosedBook book)
            {
                var manual=book.Base.ScenarioFundingWindows.ToLookup(x=>x.Exposure.PositionId,x=>x.Exposure,StringComparer.Ordinal);
                var entry=book.Base.OpportunityDecisionTrace.Where(x=>x.Decision is "LONG_PENDING" or "SHORT_PENDING")
                    .ToDictionary(x=>(x.Symbol,x.Family,x.Side,x.At));
                var all=book.Episodes.Select(t=>AttributeClosed(t,entry,manual[t.PositionId],Frame,scenario.ScenarioId)).ToArray();
                return new {Episodes=all,
                    BySymbol=all.GroupBy(e=>e.Original.Symbol).Select(g=>new
                    {
                        Symbol=g.Key, Original=g.Count(), Reconciled=g.Count(x=>x.Status=="RECONCILED_TO_ORIGINAL"),
                        GrossEur=g.Sum(x=>x.GrossEur),NetEur=g.Sum(x=>x.NetEur),SpreadEur=g.Sum(x=>x.SpreadEur),
                        SlippageEur=g.Sum(x=>x.SlippageEur),ConversionEur=g.Sum(x=>x.ConversionEur),
                        CommissionEur=g.Sum(x=>x.CommissionEur),FinancingEur=g.Sum(x=>x.FinancingEur),
                        PartialReductions=g.Sum(x=>Math.Max(0,(x.Parts?.Length??0)-1)),
                        Gaps=g.Count(x=>x.Original.CrossedUnknownHistory),
                        KnownRiskOverruns=g.Count(x=>x.Status=="RECONCILED_TO_ORIGINAL"&&-x.NetEur>x.FillRiskEur),
                        ConcurrencyAtEntry=g.Count(x=>book.Episodes.Any(t=>t.Symbol!=x.Original.Symbol&&
                            t.OpenAt<=x.Original.OpenAt&&t.CloseAt>x.Original.OpenAt))
                    }).OrderBy(g=>g.Symbol).ToArray()};
            }
            reports.Add(new {scenario.Stress,Fit=Ledger(scenario.Fit),Comparison=Ledger(scenario.Books[0])});
        }
        File.WriteAllText(output,JsonSerializer.Serialize(new {OriginalEconomicSha256=digest,OriginalArchive=15000522105,
            CalendarQualification="CONDITIONAL_OFFICIAL_CAPTURE_SNAPSHOT",Eligibility=eligibility,Results=reports,
            BrokerRequests=0,EconomicEvaluations=0,Orders=0,CloudActivated=false},Json));
        return 0;
    }

    static EerClosedAttribution AttributeClosed(EerClosedEpisode original,
        Dictionary<(string,string,int,long),NativeEurOpportunity> admissions,IEnumerable<NativeFundingExposure> windows,
        Func<string,long,Ucp1MarketFrame?> frame,string scenario)
    {
        string name=original.Symbol;
        int direction=original.Side;
        decimal units=original.Units;
        if(!long.TryParse(original.PositionId.Split('/')[^1],NumberStyles.None,CultureInfo.InvariantCulture,out long requestAt) ||
            !admissions.TryGetValue((name,original.Family,direction,requestAt),out var ticket) || ticket.Units!=units)
            return new(original,"PUBLISHED_ADMISSION_NOT_LINKED");
        var segments=windows.OrderBy(x=>x.FromExclusive).ToArray();
        if(segments.Length==0 || segments[0].FromExclusive!=original.OpenAt || segments[0].Units!=units ||
            segments[^1].ClosedAt!=original.CloseAt ||
            segments.Any(x=>x.Symbol!=name||x.Side!=direction||!x.ExactInLedger||x.ClosedAt is null))
            return new(original,"PUBLISHED_FUNDING_EXPOSURE_NOT_LINKED");
        var admission=frame(name,requestAt);
        var opened=frame(name,original.OpenAt);
        if(admission is null||opened is null)
            return new(original,"ADMISSION_OR_FILL_QUOTE_UNAVAILABLE");
        var signal=Ucp1CausalSignals.Describe(admission,requestAt).SingleOrDefault(s=>s.Family==original.Family&&s.Side==direction);
        if(signal is null||NativeUnifiedPortfolioEngine.Cpe1Levels(signal,admission) is not { } geometry)
            return new(original,"PUBLISHED_ENTRY_GEOMETRY_NOT_LINKED");
        var entry=opened.Quote;
        var contract=opened.Contract;
        decimal entrySlip=admission.SlippagePerSideQuote;
        decimal entryPrice=NativeExecutableEconomics.EntryPrice(entry,direction,entrySlip);
        decimal entryFee=NativeFundedLedger.Fee(entry,units,direction);
        var bracket=NativeExecutableEconomics.Bracket(entry,direction,units,geometry.Stop,geometry.Target,
            entrySlip,entry.LiquidationSlippagePerSide??entrySlip);
        var firstQuote=admission.Quote;
        var initial=NativeExecutableEconomics.Bracket(firstQuote,direction,units,geometry.Stop,geometry.Target,
            entrySlip,firstQuote.LiquidationSlippagePerSide??entrySlip);
        decimal? reserveAtFill=NativePortfolioFunding.OfferDebit(opened,direction,units,original.OpenAt,scenario);
        var parts=new List<EerClosedPart>();
        decimal overshoot=0m;
        for(int i=0;i<segments.Length;i++)
        {
            var segment=segments[i];
            long closedAt=segment.ClosedAt!.Value;
            var next=i+1<segments.Length?segments[i+1]:null;
            if(next is not null && (next.FromExclusive!=closedAt||next.Units>=segment.Units))
                return new(original,"REDUCTION_WINDOWS_NOT_CONTIGUOUS");
            decimal filledUnits=segment.Units-(next?.Units??0m);
            if(frame(name,closedAt) is not { } closed)return new(original,"CLOSE_QUOTE_UNAVAILABLE");
            var q=closed.Quote;
            decimal slip=q.LiquidationSlippagePerSide??entrySlip;
            decimal witnessed=direction>0?q.Bid:q.Ask;
            decimal price=NativeExecutableEconomics.ExitPrice(witnessed,direction,slip);
            var cost=NativeExecutableEconomics.ClosedPriceMoney(entry,q,direction,filledUnits,entryPrice,price,entrySlip,slip);
            decimal commission=NativeFundedLedger.Fee(q,filledUnits,-direction);
            parts.Add(new(closedAt,filledUnits,cost.Spread,cost.Slippage,cost.Conversion,
                commission+entryFee*filledUnits/units,cost.Gross,cost.Converted));
            overshoot=Math.Max(overshoot,direction*(geometry.Stop-witnessed));
        }
        decimal funding=segments.Sum(x=>x.BookedSignedEur);
        decimal gross=parts.Sum(x=>x.GrossEur),commissionEur=parts.Sum(x=>x.CommissionEur);
        decimal net=parts.Sum(x=>x.ConvertedEur)-commissionEur+funding;
        if(original.ReconciledNetEur is not decimal reported || Math.Abs(reported-net)>.000000001m ||
            Math.Abs(original.GrossEur-gross)>.000000001m)
            return new(original,"PRICE_OR_COST_RECONCILIATION_MISMATCH");
        return new(original,"RECONCILED_TO_ORIGINAL",contract.LotUnits,contract.MinimumUnits,contract.VolumeStepUnits,
            direction*(entryPrice-geometry.Stop),
            initial.RiskEur+ticket.NextManagementFundingCeilingEur,bracket.RiskEur+reserveAtFill,
            gross,parts.Sum(x=>x.SpreadEur),parts.Sum(x=>x.SlippageEur),parts.Sum(x=>x.ConversionEur),
            commissionEur,funding,net,overshoot,parts.ToArray());
    }
}
