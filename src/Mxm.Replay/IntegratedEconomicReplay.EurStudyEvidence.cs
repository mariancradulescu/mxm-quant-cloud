using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed class EurOpportunityObserver(NativeEurDevelopmentProfile profile,string scenario,decimal stress,
        EerEvidence source,EerProtectionTape protection,Dictionary<string,EerStream> markets)
    {
        readonly NativeEurDevelopmentProfile episodeProfile=profile with
            {CaptureStudyDiagnostics=false,LearnFromOpportunityEpisodes=false};
        readonly Dictionary<string,NativeUnifiedPortfolioEngine> active=new(StringComparer.Ordinal);
        readonly List<NativeEurCalibrationOutcome> labels=new();
        readonly Dictionary<string,int> results=new(StringComparer.Ordinal);
        long observedThrough;
        int maxConcurrent;

        NativeUnifiedPortfolioEngine ResearchEpisode() => new(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            fundingScenarioId:scenario,eurDevelopmentProfile:episodeProfile);

        void Count(string reason,int amount=1) => results[reason]=results.GetValueOrDefault(reason)+amount;

        public void Advance(Ucp1Frame frame)
        {
            observedThrough=frame.At;
            foreach(var (symbol,episode) in active.ToArray())
            {
                protection.Between(episode,frame.At-1,source,markets,scenario,stress);
                source.Advance(episode,frame with {ObservationEpisodeOnly=true,
                    Protection=protection.GridCoverage(episode,frame.At)},markets,scenario,stress);
                var book=episode.ModelSummary;
                if(book.OpenPositions+book.PendingIntents>0)continue;
                active.Remove(symbol);
                if(episode.CompleteModelTrips.SingleOrDefault() is not { } trip)
                {Count("ENTRY_EXPIRED_OR_FAILED_REVALIDATION");continue;}
                Count("CLOSED");
                if(episode.ExportEurCalibration().Outcomes.SingleOrDefault() is { } label)
                {
                    labels.Add(label);
                    Count("MATURED_RECONCILED_LABEL");
                }
                else
                {
                    if(trip.CrossedUnknownHistory)Count("UNVERIFIED_PRICE_PATH");
                    if(episode.ReconciledModelEpisodes.Length==0)Count("NO_RECONCILED_MONETARY_OUTCOME");
                }
            }

            // Sample at the close-based hourly clock, rotate between offers
            // with a pre-outcome ordering, and observe at most one episode per
            // symbol at a time. Co-moving markets still share calendar days.
            if(frame.At%3_600_000L!=EurOffset)return;
            var describe=ResearchEpisode();
            foreach(var market in frame.Markets)
            {
                var offers=describe.DescribeEurGeneral(market,frame.At);
                Count("SIGNALS",offers.Length);
                if(offers.Length==0)continue;
                if(active.ContainsKey(market.Symbol))
                {Count("SAME_SYMBOL_OVERLAP_EXCLUDED",offers.Length);continue;}
                var chosen=offers.OrderBy(o=>EerHash(FormattableString.Invariant($"{frame.At}/{o.Symbol}/{o.Family}/{o.Side}")),
                    StringComparer.Ordinal).First();
                var episode=ResearchEpisode();
                source.Advance(episode,frame with {ObservationEpisodeOnly=true,OpportunityToObserve=chosen},markets,scenario,stress);
                if(episode.ModelSummary.PendingIntents>0)
                {
                    active.Add(market.Symbol,episode);
                    Count("ISOLATED_MINIMUM_VOLUME_ADMISSION");
                }
                else
                {
                    Count("NOT_CONTRACTUALLY_OR_MONETARILY_ADMITTED");
                    foreach(var (reason,count) in episode.ResearchDecisionCounts)Count(reason,count);
                }
            }
            maxConcurrent=Math.Max(maxConcurrent,active.Count);
        }

        public NativeEurCalibration Export()
        {
            var matured=labels.OrderBy(x=>x.ClosedAt).ThenBy(x=>x.PositionId,StringComparer.Ordinal).ToArray();
            return new NativeEurCalibration(observedThrough,GeneralSha(JsonSerializer.SerializeToUtf8Bytes(matured,Json)),matured)
            {
                FundingScenarioId=scenario,OpportunitySchema=NativeUnifiedPortfolioEngine.EurGeneralSchema,
                DevelopmentGeometry=profile.GeometryIdentity,OpportunityEpisodeLabels=true
            };
        }

        public object Report()=>new {Counts=results,RightCensoredEpisodes=active.Count,
            SimultaneousSymbolsMaximum=maxConcurrent,Observation="ISOLATED_ONE_CONTRACTUAL_MINIMUM_VOLUME_EPISODE",
            CountedAsSharedBookRoundTrips=false,IndependentSamples=false,Labels=Export().Outcomes.Select(l=>new
            {l.PositionId,l.Family,l.Side,l.DecisionAt,l.ClosedAt,l.AvailableAt,l.GrossEur,l.NetEur,l.RiskEur,Symbol=l.Context?.Symbol})};
    }

    static object EconomicStudyDetails(NativeUnifiedPortfolioEngine book,EerEvidence source,
        Dictionary<string,EerStream> markets,NativeEurCalibration? calibration=null)
    {
        var trips=book.CompleteModelTrips;
        var reconciled=book.ReconciledModelEpisodes.ToDictionary(x=>x.PositionId,StringComparer.Ordinal);
        var included=calibration?.Outcomes.ToDictionary(x=>x.PositionId,StringComparer.Ordinal);
        var exposures=book.FundingExposureSnapshot();
        var outstanding=exposures.Where(w=>!w.ExactInLedger).Select(w=>
        {
            var terms=markets[w.Symbol].Source.Market.DatedDevelopment!;
            var contract=terms.Contract;
            long through=w.ClosedAt??book.LastObservationAt;
            var charges=new List<object>();
            for(long? at=NativeBrokerContractCosts.NextScheduledSwapCharge(contract,w.FromExclusive);at<=through;
                at=NativeBrokerContractCosts.NextScheduledSwapCharge(contract,at.Value))
            {
                var evidence=source.Charge(w.Symbol,contract.QuoteAsset,at.Value);
                charges.Add(new {At=at,HasRolloverBid=evidence.Bid.HasValue,HasRolloverConversion=evidence.QuoteToEur is not null});
            }
            return new {w.PositionId,w.Symbol,w.Side,w.Units,w.FromExclusive,w.ClosedAt,Through=through,
                w.BookedSignedEur,w.AdditionalDebitCeilingEur,contract.SwapCalculationType,contract.SwapPeriodHours,
                ContractRateAvailable=(w.Side>0?contract.LongSwap:contract.ShortSwap).HasValue,
                contract.ChargeSwapAtWeekends,contract.SkipSwapPeriods,contract.TripleSwapWeekday,
                contract.QuoteAsset,terms.AccountSwapFree,terms.MoneyDigits,ChargeEvidence=charges};
        }).ToArray();
        var admissions=book.OriginalModelEvents.Where(e=>e.Kind=="REQUEST_OPEN").ToArray();
        var fills=book.OriginalModelEvents.Where(e=>e.Kind=="OPEN_FILL").ToDictionary(e=>e.PositionId,StringComparer.Ordinal);
        var conditional=new List<object>();
        if(book.UsesClosedSessionFundingQuotes)
            foreach(var window in exposures.Where(x=>x.ExactInLedger))
            {
                var terms=markets[window.Symbol].Source.Market.DatedDevelopment!;
                var basis=new Dictionary<(string Symbol,long ChargeAt),long>();
                long through=window.ClosedAt??book.LastObservationAt;
                if(source.ModeledFunding(terms,window,through,basis) is decimal amount && basis.Count>0)
                    conditional.Add(new {window.PositionId,window.Symbol,window.Side,window.FromExclusive,window.ClosedAt,
                        AmountAtOriginalScale=amount,ScenarioBookedEur=window.BookedSignedEur,QuoteBasis=StaleRolloverWitness(basis)});
            }
        return new
        {
            MarginMaxima=book.EurMarginMaxima,MarginExceedances=book.EurMarginExceedances,
            OutstandingFunding=outstanding,ClosedSessionFunding=conditional,Activity=book.EurDecisionActivity,
            EquityPath=book.CommonBookEquityPath.Select(x=>new
            {
                x.At,x.CashEur,EquityEur=x.FundingCapital?.ConditionalEquityEur,x.UsedMarginEur,
                PendingMarginEur=x.FundingCapital?.PendingOpenMarginEur,x.Held,x.Pending,x.Completed,
                Drawdown=x.FundingCapital?.MaximumSampledFundingAdjustedDrawdown,
                FundingWindowsWithoutCeiling=x.FundingCapital?.ConditionalUnmodeledDebitCeilingEur is null
                    ? x.FundingCapital?.OutstandingHeldWindows+x.FundingCapital?.OutstandingClosedWindows:null
            }),
            Admissions=admissions.Select(a=>new {a.PositionId,a.Symbol,a.Side,a.Units,DecisionAt=a.At,
                FillAt=fills.GetValueOrDefault(a.PositionId)?.At}),
            Episodes=trips.Select(t=>
            {
                var entry=t.EconomicEntry;
                var settlement=reconciled.GetValueOrDefault(t.PositionId);
                var net=settlement?.Evidence.ClosedNetEur;
                decimal? grossLoss=t.GrossEur<0m?-t.GrossEur:0m;
                decimal? costs=t.Integrated is { } c?c.CommissionsEur+c.SpreadEur+c.SlippageEur+c.ConversionEur:null;
                return new {t.PositionId,t.Symbol,t.Family,t.Side,t.OpenAt,t.CloseAt,t.Units,
                    t.ExitReason,t.GrossEur,NetEur=net,ReconciledAt=settlement?.AvailableAt,
                    ReservedRiskAtAdmissionEur=entry?.AdmissionReservedRiskEur,
                    ReservedRiskAtFillEur=entry?.ReservedRiskEur,RiskChangeAtFillEur=entry?.ReservedRiskEur-entry?.AdmissionReservedRiskEur,
                    LossBeyondReserveEur=net is decimal n&&entry is not null?Math.Max(0m,-n-entry.ReservedRiskEur):(decimal?)null,
                    GrossLossEur=grossLoss,ExplicitExecutionCostsEur=costs,
                    ReconciledFinancingEur=net-t.GrossEur+costs,t.CrossedUnknownHistory,t.StopExecution,
                    LearningEligibleAtEnd=included?.ContainsKey(t.PositionId),
                    LearningExclusions=new[]{settlement is null?"UNRECONCILED_MONETARY_OUTCOME":null,
                        t.CrossedUnknownHistory?"UNVERIFIED_PRICE_PATH":null}.OfType<string>().ToArray()};
            })
        };
    }

    static object StaleRolloverWitness(Dictionary<(string Symbol,long ChargeAt),long> basis) => basis
        .OrderBy(p=>p.Key.ChargeAt).ThenBy(p=>p.Key.Symbol,StringComparer.Ordinal)
        .Select(p=>new {p.Key.Symbol,p.Key.ChargeAt,LastOfficialSessionClock=p.Value}).ToArray();
}
