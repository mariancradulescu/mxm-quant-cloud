using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// CPE1 is NOT another book, scorer or strategy engine: these methods are
// part of NativeUnifiedPortfolioEngine.Advance and use its ONE funded session.
// The two predeclared modes use identical causal M5/M15 candidate generators.
public sealed partial class NativeUnifiedPortfolioEngine
{
    readonly Dictionary<string,Cpe1FamilyHistory> cpe1History=new(StringComparer.Ordinal);
    readonly HashSet<string> cpe1ScoredEpisodes=new(StringComparer.Ordinal);

    sealed class Cpe1FamilyHistory
    {
        readonly bool fundingAware;
        readonly List<decimal> grossReturns=new();
        readonly HashSet<long> closeDays=new();
        decimal? lowerBound;
        bool returnsChanged;
        public int Settled { get; private set; }
        public int Winners { get; private set; }

        public Cpe1FamilyHistory(bool fundingAware)=>this.fundingAware=fundingAware;

        public Cpe1FamilyHistory(Cpe1FamilyResearchState state)
        {
            fundingAware=state.FundingAware;
            grossReturns.AddRange(state.GrossReturns);
            closeDays.UnionWith(state.CloseDays);
            lowerBound=state.LowerBound;
            returnsChanged=state.ReturnsChanged;
            Settled=state.Settled;
            Winners=state.Winners;
        }

        public Cpe1FamilyResearchState ResearchState(string family)=>new(family,fundingAware,
            grossReturns.ToArray(),closeDays.ToArray(),lowerBound,returnsChanged,Settled,Winners);

        public void Add(Ucp1Episode episode,NativeJointOpportunityEpisodeEvidence evidence)
        {
            Settled++;
            if((fundingAware?evidence.ClosedGrossEur:episode.GrossEur)>0m)Winners++;
            if(evidence.RealizedGrossR is not decimal grossR)return;
            grossReturns.Add(grossR);
            closeDays.Add(episode.CloseAt/86400000L);
            returnsChanged=true;
        }

        public decimal? LowerObservedGross()
        {
            if(grossReturns.Count<20 || closeDays.Count<3)return null;
            if(returnsChanged)
            {
                // Retain exactly the frozen two-pass calculation in close
                // order. Only a newly completed eligible episode invalidates it.
                decimal mean=grossReturns.Average();
                // Late outcomes can arrive in another order than their closes.
                // Use the same numerical order when rebuilding from a checkpoint.
                IEnumerable<decimal> samples=fundingAware?grossReturns.OrderBy(value=>value):grossReturns;
                double sampleVariance=samples.Select(v=>Math.Pow((double)(v-mean),2))
                    .Sum()/(grossReturns.Count-1);
                lowerBound=mean-1.645m*(decimal)Math.Sqrt(sampleVariance/grossReturns.Count);
                returnsChanged=false;
            }
            return lowerBound;
        }
    }

    Ucp1ReconciledEpisode? ReconcileCpe1Episode(Ucp1Episode episode,long at)
    {
        if(episode.EconomicEvidence is not {CompletePair:true} evidence || episode.CloseAt>at)
            return null;
        if(fundingReserves is null)
            return evidence.ConditionalNetKnown?new(episode.PositionId,episode.CloseAt,evidence):null;

        long legacyKnowledgeAt=evidence.ConditionalNetKnown?episode.CloseAt:at;
        long? availableAt=fundingReserves.ClosedReconciliationAt(episode.PositionId,episode.CloseAt,legacyKnowledgeAt);
        if(availableAt is null || availableAt>at)return null;
        var ledger=model.Ledger;
        var parts=ledger.ReconciledFragments(episode.PositionId,at);
        if(parts.Length==0 || !parts[^1].Original.CompletesRoundTrip)return null;
        decimal net=parts.Sum(part=>part.NetEur);
        return new Ucp1ReconciledEpisode(episode.PositionId,availableAt.Value,evidence with
        {
            ConditionalNetKnown=true,
            ClosedNetEur=net,
            RealizedNetR=net/evidence.ReservedRiskEur,
            EvidenceStatus=FundingScenarioId is not null?"COMPLETE_EXPLICIT_SCENARIO_MODELED_EPISODE":
                evidence.MarkCoverageComplete?"COMPLETE_CONDITIONAL_MODELED_EPISODE":
                "COMPLETE_CASH_BUT_SAMPLE_MARKS_INCOMPLETE"
        });
    }

    void RememberCpe1Episode(Ucp1Episode episode,long at)
    {
        if(episode.CrossedUnknownHistory || cpe1ScoredEpisodes.Contains(episode.PositionId) ||
           ReconcileCpe1Episode(episode,at) is not { } reconciled)return;
        cpe1ScoredEpisodes.Add(episode.PositionId);
        if(!cpe1History.TryGetValue(episode.Family,out var history))
            cpe1History.Add(episode.Family,history=new(fundingReserves is not null));
        history.Add(episode,reconciled.Evidence);
        if(fundingReserves is not null)RememberEurOutcome(episode,reconciled);
    }

    static bool Cpe1Usable(Ucp1MarketFrame m,long at)
        => m.M5.Length>=5 && m.M15.Length>=3 &&
           m.M5[^1].CloseAt<at && m.M15[^1].CloseAt<at &&
           at-m.M5[^1].CloseAt<=300000L &&
           at-m.M15[^1].CloseAt<=900000L &&
           m.Contract.MinimumUnits>0m && m.Contract.VolumeStepUnits>0m &&
           m.Contract.MaximumUnits>=m.Contract.MinimumUnits &&
           m.Quote.MarginPerUnit>0m &&
           m.Quote.EurCredit>0m && m.Quote.EurDebit>=m.Quote.EurCredit;

    internal static (decimal Stop,decimal Target)? Cpe1Levels(
        Ucp1DecisionSignal signal,Ucp1MarketFrame m)
    {
        // Ranges are completed M5 structural boundaries, never ATR alone.
        var recent=m.M5.TakeLast(3).ToArray();
        decimal start=m.M5[^1].Close;
        decimal stop=signal.Side>0?recent.Min(b=>b.Low):
            recent.Max(b=>b.High);
        // Breakout: project observed preceding price displacement from last
        // completed close. Failed continuation: return to completed M15 mean.
        decimal target=signal.Family=="RANGE_TRANSITION"?
            start+signal.Side*signal.ExpectedMove:signal.Equilibrium;
        if(signal.Side*(start-stop)<=0m||signal.Side*(target-start)<=0m)
            return null;
        return (stop,target);
    }

    NativePendingCapitalGate.Commitment[] Cpe1Commitments(bool pending,Ucp1Frame? frame=null)
    {
        var ledger=model.Ledger;
        var items=pending?ledger.PendingSnapshot()
            .Where(x=>x.Kind=="REQUEST_OPEN")
            .Select(x=>(Id:x.PositionId,Symbol:x.Symbol,Units:x.Units,Margin:x.MarginPerUnit)).ToArray():
            ledger.PositionSnapshot().Select(x=>
                (Id:x.Id,Symbol:x.Symbol,Units:x.Units,Margin:x.MarginPerUnit)).ToArray();
        return items.Select(x=>new NativePendingCapitalGate.Commitment(
            x.Id,x.Symbol,x.Units,Math.Max(x.Margin,(fundingReserves is null?null:
                frame?.Markets.FirstOrDefault(m=>m.Symbol==x.Symbol)?.Quote.MarginPerUnit)??0m),
            plans.TryGetValue(x.Id,out var p)?
                Math.Max(0m,p.RiskEur):0m,
            "CPE1_SINGLE_ECONOMIC_EPISODE",pending)).ToArray();
    }

    NativeFundingCapital? Cpe1FundingCapital(LedgerSummary book,Ucp1Frame? frame)
        =>fundingReserves?.Capital(book,Cpe1Commitments(true,frame).Sum(x=>x.MarginEur));

    Ucp1FrameResult AdvanceCpe1(long at,Ucp1Frame frame,
        List<(Ucp1DecisionSignal Signal,Ucp1MarketFrame Frame)> options)
    {
        if(OwnerEur)return AdvanceEur(at,frame,options);
        var book=model.Ledger.Summary(at);
        var financial=Cpe1FundingCapital(book,frame);
        var equity=financial is null?book.LiquidationEquityEur:financial.ResearchAdmissionEquityEur;
        if(financial is {OutstandingDebitCeilingEur:null})
            Count("ACCRUED_FUNDING_UNBOUNDED");
        if(policy=="CPE1_CASH" || (fundingReserves is null&&cpe1UnreconciledFunding) ||
           equity is not >0m ||
           (financial?.MaximumSampledFundingAdjustedDrawdown??book.MaximumSampledDrawdown)>=.28m)
            return RecordIntegratedFrame(at,book,frame);
        var held=Cpe1Commitments(false,frame);
        var pending=Cpe1Commitments(true,frame);
        if(held.Length+pending.Length>=2 || (fundingReserves is null && held.Any(x=>
            plans.TryGetValue(x.PositionId,out var p)&&p.FinancingUnknown)))
        {
            Count("CPE1_HELD_OR_PENDING_CAPACITY_OR_UNKNOWN_FINANCE");
            return RecordIntegratedFrame(at,book,frame);
        }
        var candidates=new List<(Ucp1DecisionSignal Signal,Ucp1MarketFrame Market,
            NativeIntegratedPlan Geometry,decimal Units,decimal Score)>();
        foreach(var (signal,market) in options.OrderBy(x=>x.Frame.Symbol,StringComparer.Ordinal)
            .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal))
        {
            if(!Cpe1Usable(market,at) || Cpe1Levels(signal,market) is not { } levels)
                continue;
            decimal units=market.Contract.MinimumUnits;
            var carriedDebit=fundingReserves is null?0m:NativePortfolioFunding.OfferDebit(market,signal.Side,units,at);
            if(carriedDebit is not decimal debit)
            {
                Count("ENTRY_FUNDING_CEILING_UNAVAILABLE");
                continue;
            }
            decimal slip=market.SlippagePerSideQuote;
            var q=market.Quote;
            var bracket=NativeExecutableEconomics.Bracket(
                q,signal.Side,units,levels.Stop,levels.Target,slip,slip);
            decimal risk=bracket.RiskEur+debit,reward=bracket.RewardEur-debit;
            if(bracket.RiskEur<=0m || reward<=0m ||
               signal.Side*(bracket.Entry-levels.Stop)<=0m)
            {
                Count("CPE1_NO_FINANCIALLY_POSITIVE_PRICE_GEOMETRY");
                continue;
            }
            var gate=NativePendingCapitalGate.Assess(equity,
                book.UsedMarginEur is not null,held,pending,
                new NativePendingCapitalGate.Proposal(market.Symbol,
                    "CPE1_SINGLE_ECONOMIC_EPISODE",units,market.Contract.VolumeStepUnits,
                    units,q.MarginPerUnit,risk/units));
            if(!gate.IsFinanceable)
            {
                Count("CPE1_HELD_PENDING_"+gate.Status);continue;
            }
            // Causal evidence refers only to previously COMPLETED episodes,
            // never to still-Held future outcomes or this candidate's payoff.
            var history=cpe1History.GetValueOrDefault(signal.Family);
            var lower=fundingReserves is null?history?.LowerObservedGross():null;
            NativeEurPayoff? netProjection=null;
            // One declared initial learning phase: use affordable minimum
            // trades until 20 uncensored whole episodes become observable.
            // Calibration trades are REAL modeled P/L, not free shadow labels.
            bool calibration=(history?.Settled??0)<20;
            if(Cpe1Economic&&!calibration)
            {
                // First justify recurrent GROSS advantage, then compare its
                // pessimistic EUR lower bound to the FULL conditional round
                // trip CASH alternative. No retuning by spread; same frozen
                // risk and mandatory transaction costs for every offered leg.
                decimal entered=NativeExecutableEconomics.EntryPrice(q,
                    signal.Side,slip);
                decimal liquidationSide=signal.Side>0?q.Bid:q.Ask;
                decimal fullRoundTripCost=Math.Max(0m,-
                    NativeExecutableEconomics.EstimateNet(q,q,signal.Side,
                        units,entered,liquidationSide,slip));
                if(fundingReserves is not null)
                    netProjection=EurPayoff(signal.Family,signal.Side,risk,fullRoundTripCost+debit);
                bool superior=fundingReserves is null
                    ?lower is >0m && lower.Value*bracket.RiskEur-fullRoundTripCost-debit>0m
                    :netProjection is {GrossLowerEur:>0m,NetLowerEur:>0m};
                if(!superior)
                {Count("CPE1_WAIT_GROSS_OR_CASH_LOWER_NOT_POSITIVE");continue;}
            }
            decimal score=netProjection?.NetLowerEur??(Cpe1Economic && lower.HasValue?
                lower.Value*bracket.RiskEur-debit:reward/risk);
            candidates.Add((signal,market,
                new NativeIntegratedPlan(levels.Stop,levels.Target,
                    risk,reward)
                    {EntrySlippage=slip},units,score));
        }
        if(candidates.Count==0)
        {
            Count("CPE1_WAIT_NO_FINANCEABLE_EDGE");
            return RecordIntegratedFrame(at,book,frame);
        }
        var chosen=Cpe1Economic?
            candidates.OrderByDescending(x=>x.Score)
                .ThenBy(x=>x.Market.Symbol,StringComparer.Ordinal).First():
            candidates[0];
        var s=chosen.Signal;var m=chosen.Market;
        string id="UCP1/"+policy+"/"+m.Symbol+"/"+s.Family+"/"+at;
        var request=Event("REQUEST_OPEN",at,id,m.Symbol,s.Side,chosen.Units,
            margin:m.Quote.MarginPerUnit,slip:m.SlippagePerSideQuote,
            reason:"NATIVE_CONDITIONAL_SELECTION");
        Apply(fundingReserves is null?request:
            request with {AvailableAt=at,CalibratedThrough=s.LastCompletedM5At,TracksLateFunding=true});
        AddPlan(id,new Ucp1Plan(id,m.Symbol,s.Family,s.Side,s.Atr,s.Equilibrium,
            chosen.Geometry.InitialRiskEur,chosen.Geometry.Stop,0m,0L,0m,
            chosen.Units,0m,0m,0L,false,chosen.Geometry));
        admitted++;Count("CPE1_EUR_REWARD_RISK_FUNDED_PENDING");
        return RecordIntegratedFrame(at,model.Ledger.Summary(at),frame);
    }

    NativeIntegratedPlan? Cpe1RecheckFill(Ucp1Plan plan,LedgerEvent intent,
        LedgerSummary current,Ucp1MarketFrame observed,decimal execution,Ucp1Frame frame,out decimal fillUnits)
    {
        fillUnits=plan.Units;
        var financial=Cpe1FundingCapital(current,frame);
        var equity=financial is null?current.LiquidationEquityEur:financial.ResearchAdmissionEquityEur;
        if(plan.Integrated is not { } prior || equity is not >0m ||
           (financial?.MaximumSampledFundingAdjustedDrawdown??current.MaximumSampledDrawdown)>=.28m ||
           !Cpe1Usable(observed,observed.Quote.At) ||
           plan.Side*(execution-prior.Stop)<=0m ||
           plan.Side*(prior.Target-execution)<=0m)
            return null;
        var q=observed.Quote;
        if(ModelsNativeStops && NativeExecutableEconomics.TradeStopReached(plan.Side,
            plan.Side>0?q.Bid:q.Ask,prior.Stop))
        {
            Count("EUR_FILL_STOP_ALREADY_MARKETABLE");
            return null;
        }
        if((fundingReserves is null&&cpe1UnreconciledFunding) || !EurFrameFollows(observed,intent.At,q.At))
            return null; // No late fill after a missing M5 source clock.

        var full=Cpe1RecheckFillVolume(plan,prior,intent,current,observed,frame,equity.Value,plan.Units);
        if(full is not null||eurDevelopmentProfile?.ResizeWithinAdmissionRiskAtFill!=true)
            return full;
        // Evaluate each evidenced smaller size with its own margin, fee floor,
        // conversion and funding. The original stop and risk ceiling remain binding.
        var alternatives=(observed.EurMargins??Array.Empty<NativeEurMarginObservation>())
            .Where(m=>m.Side==plan.Side&&m.Units<plan.Units).Select(m=>m.Units).Distinct().OrderByDescending(x=>x);
        foreach(var units in alternatives)
        {
            var smaller=Cpe1RecheckFillVolume(plan,prior,intent,current,observed,frame,equity.Value,units);
            if(smaller is null)continue;
            fillUnits=units;
            return smaller;
        }
        return null;
    }

    NativeIntegratedPlan? Cpe1RecheckFillVolume(Ucp1Plan plan,NativeIntegratedPlan prior,LedgerEvent intent,
        LedgerSummary current,Ucp1MarketFrame observed,Ucp1Frame frame,decimal equity,decimal units)
    {
        var q=observed.Quote;
        if(OwnerEur && EurMargin(observed,plan.Side,units,q.At) is null)return null;
        var carriedDebit=fundingReserves is null?0m:
            NativePortfolioFunding.OfferDebit(observed,plan.Side,units,q.At,FundingScenarioId);
        if(carriedDebit is not decimal debit)return null;
        var bracket=NativeExecutableEconomics.Bracket(q,plan.Side,units,
            prior.Stop,prior.Target,intent.SlippagePerSide,
            q.LiquidationSlippagePerSide??intent.SlippagePerSide);
        var risk=ReservedEurRisk(bracket.RiskEur,debit)+prior.GapReservePerUnitQuote*units*q.EurDebit;
        var reward=bracket.RewardEur-debit;
        if(bracket.RiskEur<=0m||reward<=0m)return null;
        // Registered ablation: no post-admission enlargement of the same
        // order's monetary stop budget; retain all existing portfolio guards.
        if(eurDevelopmentProfile?.KeepAdmissionRiskAtFill==true&&risk>prior.InitialRiskEur)
        {
            Count("EUR_FILL_EXCEEDS_ADMISSION_RESERVE");
            return null;
        }
        var held=Cpe1Commitments(false,frame);
        // The pending intent must be REPRICED at the actual next witnessed
        // fill. Never pass its stale admission risk or stale minimum margin
        // into postfill Held+Pending projected-equity verification.
        var pending=Cpe1Commitments(true,frame)
            .Select(x=>x.PositionId==plan.Id ?
                x with {Units=units,ReservedStopRiskEur=risk,
                        MarginPerUnit=Math.Max(x.MarginPerUnit,q.MarginPerUnit)}
                : x).ToArray();
        if(!NativePendingCapitalGate.RevalidatePendingFill(
            equity,current.UsedMarginEur is not null,
            held,pending,plan.Id))return null;
        var guard=NativePostFillCapitalGuard.Assess(equity,
            held,pending,plan.Id,plan.Side,q,intent.SlippagePerSide,debit,
            IsEurGeneral?q.LiquidationSlippagePerSide:null);
        if(!guard.Allowed || (fundingReserves is not null && guard.ProjectedPostFillLiquidationEquityEur <
            current.ObservedPeakEur*(1m-OwnerRiskAuthority.MaximumSystemDrawdown)))return null;
        if(IsEurGeneral&&guard.PreFillLiquidationEquityEur-guard.AggregateReservedRiskEur<
            current.ObservedPeakEur*(1m-OwnerRiskAuthority.MaximumSystemDrawdown))return null;
        if(eurDevelopmentProfile?.EconomicMechanism==NativeEconomicMechanisms.Transition)
        {
            decimal transitionCost=Math.Max(0m,-NativeExecutableEconomics.EstimateNet(q,q,plan.Side,units,
                bracket.Entry,plan.Side>0?q.Bid:q.Ask,q.LiquidationSlippagePerSide??intent.SlippagePerSide));
            string? horizon=eurDevelopmentProfile.MatchEconomicTransitionHorizonAtFill
                ?eurDevelopmentProfile.EconomicGeometryTimeframe:null;
            if(NativeEconomicMechanisms.TransitionPayoff(observed,frame.At,plan.Side,units,transitionCost+debit,horizon,
                    eurDevelopmentProfile.Pav1TransitionBars)
                is not {GrossLowerEur:>0m,NetLowerEur:>0m})
            {
                if(eurDevelopmentProfile.MatchEconomicTransitionHorizonAtFill)
                    Count("EUR_FILL_TRANSITION_PAYOFF_UNSUPPORTED_OR_NONPOSITIVE");
                return null;
            }
            if(eurDevelopmentProfile.RequirePav1FastAgreement&&
                NativeEconomicMechanisms.TransitionPayoff(observed,frame.At,plan.Side,units,transitionCost+debit,"M15",
                    eurDevelopmentProfile.Pav1TransitionBars) is not {GrossLowerEur:>0m,NetLowerEur:>0m})
            {Count("EUR_PAV1_M15_FILL_DISAGREEMENT");return null;}
        }
        if(policy is EurGeneralSelect or EurGeneralPooled)
        {
            decimal cost=Math.Max(0m,-NativeExecutableEconomics.EstimateNet(q,q,plan.Side,units,
                bracket.Entry,plan.Side>0?q.Bid:q.Ask,q.LiquidationSlippagePerSide??intent.SlippagePerSide));
            var context=DescribeEurContext(observed,frame.At,plan.Side,guard.TotalReservedMarginEur,equity,risk,cost);
            if(context is not null)context=context with {MarketState=DescribeGeneralState(observed,frame,plan.Side),
                RelativeVolatility=eurDevelopmentProfile?.RevalidatePredictiveVolatilityAtFill==true
                    ?DescribeRelativeVolatility(observed,frame.At):null,
                ClosedBarActivity=eurDevelopmentProfile?.CaptureClosedBarActivity==true
                    ?DescribeClosedBarActivity(observed,frame.At,plan.Side):null};
            if(EurPayoff(plan.Family,plan.Side,risk,cost+debit,policy==EurGeneralSelect?context:null,decisionAt:frame.At,
                managementOverride:prior.SelectedEconomicManagement)
                is not {GrossLowerEur:>0m,NetLowerEur:>0m})return null;
        }
        return prior with {InitialRiskEur=risk,InitialRewardEur=reward};
    }

    Ucp1Plan Cpe1AccrueOrMarkFunding(Ucp1Plan plan,LedgerPosition held,
        Ucp1MarketFrame market,Ucp1Frame frame)
    {
        long at=frame.At;
        decimal? accumulated=Cpe1ObservedFunding(market.Contract,market.Quote,
            held.EntryAt,held.Side,held.Units,at);
        if(accumulated is not decimal known)
        {
            Count("CPE1_FINANCING_UNKNOWN_RISK_STILL_HELD");
            return plan with {FinancingUnknown=true};
        }
        decimal delta=known-plan.BookedFinancingEur;
        if(delta!=0m)
        {
            Apply(Event("FINANCING",at,held.Id,held.Symbol,held.Side,held.Units,
                reason:"CONDITIONAL_ORIGINAL_CONTRACT_SWAP_CLOCK",
                quotes:frame.Markets.Select(x=>x.Quote).ToArray(),financing:delta));
        }
        // Once ANY historical funding leg was unknown, that liability is
        // never silently restored by a later as-of quote or price update.
        return plan with {BookedFinancingEur=known};
    }

    internal static decimal? Cpe1ObservedFunding(NativeObservedContractTerms contract,
        LedgerQuote quote,long entryAt,int side,decimal units,long at)
    {
        long day=86400000L;
        if(contract.SwapPeriodHours==24 &&
           contract.SwapTimeUtcMinute is int minute && minute>=0&&minute<1440)
        {
            long first=(entryAt/day)*day+minute*60000L;
            if(first<=entryAt)first+=day;
            if(first>at)return 0m;
        }
        try
        {
            return contract.OriginalBrokerAuthenticated?
                NativeBrokerContractCosts.SignedFinancing(contract,entryAt,
                    at,side,units,quote.EurCredit,quote.EurDebit):
                NativeBrokerContractCosts.SignedFinancingCurrentAlgo(contract,
                    entryAt,at,side,units,quote.EurCredit,quote.EurDebit);
        }
        catch(ArgumentException){return null;}
        catch(InvalidOperationException){return null;}
    }

    (Ucp1Plan,NativeModelCloseInstruction?) Cpe1Manage(
        Ucp1Plan plan,LedgerPosition position,Ucp1MarketFrame market,Ucp1Frame frame)
    {
        var geometry=plan.Integrated!;
        var q=market.Quote;
        int side=position.Side;
        decimal sidePrice=side>0?q.Bid:q.Ask;
        long closed=market.M5.Where(x=>x.CloseAt<frame.At)
            .Select(x=>x.CloseAt).LastOrDefault();
        if(plan.EconomicEntry is not null && closed>=plan.EconomicEntry.FillAt &&
           plan.EconomicMarks.LastOrDefault()?.ObservedAt!=frame.At)
        {
            decimal change=side*(NativeExecutableEconomics.ExitPrice(sidePrice,side,
                    q.LiquidationSlippagePerSide??position.SlippagePerSide)
                -(position.EntryPrice??plan.Entry))*position.Units;
            decimal gross=change*(change>=0m?q.EurCredit:q.EurDebit);
            plan=plan with {EconomicMarks=plan.EconomicMarks.Append(
                new NativeJointOpportunityMark(frame.At,closed,gross,
                    q.EurCredit>0m&&q.EurDebit>=q.EurCredit)).ToArray()};
        }
        var book=model.Ledger.Summary(frame.At);
        var capital=Cpe1FundingCapital(book,frame);
        if((capital?.MaximumSampledFundingAdjustedDrawdown??book.MaximumSampledDrawdown)>=.28m)
            return (plan,new("INTEGRATED_CPE1_GLOBAL_DD_PROTECTION",position.Units));
        if(!ModelsNativeStops && NativeExecutableEconomics.TradeStopReached(side,sidePrice,geometry.Stop))
            return (plan,new("INTEGRATED_CPE1_OBSERVED_STRUCTURAL_STOP",position.Units));
        var bars=market.M15.Where(x=>x.CloseAt<frame.At).TakeLast(2).ToArray();
        if(bars.Length<2||bars[0].CloseAt!=bars[1].OpenAt)
            return (plan,null); // no invented regime or time exit
        long witness=bars[^1].CloseAt;
        if(witness<=Math.Max(plan.OpenAt,plan.LastEconomicM15))
            return (plan,null);
        plan=plan with {LastEconomicM15=witness};
        decimal displacement=side*(bars[^1].Close-bars[0].Close);
        if(IsEurGeneral)
            return (plan,ManageGeneralEur(plan,position,market,frame,capital,sidePrice,displacement));
        if(displacement<0m && side*(bars[^1].Close-plan.Equilibrium)<=0m)
            return (plan,new("INTEGRATED_CPE1_M15_THESIS_INVALIDATION",position.Units));
        if(fundingReserves is not null)
            return (plan,ManageFundedTarget(plan,position,market,sidePrice,displacement));
        if(policy=="CPE1_SIMPLE")
        {
            if(side*(sidePrice-geometry.Target)>=0m)
                return (plan,new("INTEGRATED_CPE1_SIMPLE_OBSERVED_TARGET",position.Units));
            return (plan,null);
        }
        // CONTINUE vs CLOSE: incremental prospective EUR payoff from the
        // current witnessed executable price, not an already-earned gain.
        // Prior outcome probability is diagnostic unless enough previous
        // settled non-gap same-family episodes are present.
        var history=cpe1History.GetValueOrDefault(plan.Family);
        if(history is null || history.Settled<20)
        {
            // Before any calibrated same-family outcome distribution exists,
            // HOLD a continuing witness, but close a realized prior price
            // objective only when newly CLOSED M15 confirms the original
            // directional impulse has stalled. This is NOT a fixed time exit
            // or a blind cap at the static target.
            if(side*(sidePrice-geometry.Target)>=0m && displacement<=0m)
                return (plan,new("INTEGRATED_CPE1_OBSERVED_CONTINUATION_FAILURE",
                    position.Units));
            return (plan,null);
        }
        decimal probability=(decimal)history.Winners/history.Settled;
        decimal remainingReward=Math.Max(0m,
            side*(geometry.Target-sidePrice))*position.Units*q.EurCredit;
        decimal remainingLoss=Math.Max(0m,
            side*(sidePrice-geometry.Stop))*position.Units*q.EurDebit;
        decimal futureExitCost=Fee(q,position.Units,-position.Side);
        var carriedDebit=fundingReserves is null?0m:
            NativePortfolioFunding.OfferDebit(market,side,position.Units,frame.At,FundingScenarioId);
        if(carriedDebit is not decimal debit)return (plan,null);
        decimal incrementalValue=probability*remainingReward-
            (1m-probability)*remainingLoss-futureExitCost-debit;
        if(incrementalValue<=0m)
            return (plan,new("INTEGRATED_CPE1_CONTINUATION_WORSE_THAN_CASH",position.Units));
        // Legal proportional release of booked risk only if remaining volume
        // stays on original cTrader min+step grid and risk is already reduced.
        decimal minimum=market.Contract.MinimumUnits;
        decimal rest=position.Units-minimum;
        bool legalReduce=rest>=minimum && (rest-minimum)%market.Contract.VolumeStepUnits==0m;
        if(legalReduce && !geometry.Reduced &&
            side*(sidePrice-plan.Entry)>0m &&
            side*(sidePrice-plan.Entry)>=side*(geometry.Target-plan.Entry)/2m)
            return (plan,new("INTEGRATED_FAVORABLE_REDUCTION",minimum));
        return (plan,null);
    }

    NativeJointOpportunityEpisodeEvidence? Cpe1CompleteEpisode(
        Ucp1Plan plan,LedgerPosition held,LedgerClosedFragment finalPart,
        LedgerClosedFragment[] parts)
    {
        if(plan.EconomicEntry is null)return null;
        decimal gross=parts.Sum(x=>x.GrossEur);
        decimal net=parts.Sum(x=>x.NetEur);
        var reason=finalPart.Reason;
        NativeJointExitCause kind=reason.Contains("STOP",StringComparison.Ordinal)?
            NativeJointExitCause.ObservedProtectivePrice:
            reason.Contains("DD",StringComparison.Ordinal)?
            NativeJointExitCause.CapitalProtection:
            reason.Contains("INVALIDATION",StringComparison.Ordinal)?
            NativeJointExitCause.StructuralInvalidation:
            reason.Contains("TARGET",StringComparison.Ordinal)?
            NativeJointExitCause.Convergence:
            reason.Contains("UNKNOWN",StringComparison.Ordinal)?
            NativeJointExitCause.GapRecovery:NativeJointExitCause.OtherObservedCause;
        var close=new NativeJointOpportunityLegClose(held.Id,
            plan.EconomicEntry.FillAt,finalPart.ClosedAt,gross,
            plan.FinancingUnknown?null:net,!plan.FinancingUnknown);
        return NativeJointOpportunityEvidence.Evaluate(plan.EconomicEntry,
            plan.EconomicMarks,new[]{close},kind,
            !plan.CrossedUnknownHistory&&!plan.FinancingUnknown);
    }
}
