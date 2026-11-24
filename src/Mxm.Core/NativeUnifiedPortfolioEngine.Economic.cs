using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// CPE1 is NOT another book, scorer or strategy engine: these methods are
// part of NativeUnifiedPortfolioEngine.Advance and use its ONE funded session.
// The two predeclared modes use identical causal M5/M15 candidate generators.
public sealed partial class NativeUnifiedPortfolioEngine
{
    static bool Cpe1Usable(Ucp1MarketFrame m,long at)
        => m.M5.Length>=5 && m.M15.Length>=3 &&
           m.M5[^1].CloseAt<at && m.M15[^1].CloseAt<at &&
           at-m.M5[^1].CloseAt<=300000L &&
           at-m.M15[^1].CloseAt<=900000L &&
           m.Contract.MinimumUnits>0m && m.Contract.VolumeStepUnits>0m &&
           m.Contract.MaximumUnits>=m.Contract.MinimumUnits &&
           m.Quote.MarginPerUnit>0m &&
           m.Quote.EurCredit>0m && m.Quote.EurDebit>=m.Quote.EurCredit;

    static (decimal Stop,decimal Target)? Cpe1Levels(
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

    NativePendingCapitalGate.Commitment[] Cpe1Commitments(bool pending)
    {
        var ledger=model.Ledger;
        var items=pending?ledger.PendingSnapshot()
            .Where(x=>x.Kind=="REQUEST_OPEN")
            .Select(x=>(Id:x.PositionId,Symbol:x.Symbol,Units:x.Units,Margin:x.MarginPerUnit)).ToArray():
            ledger.PositionSnapshot().Select(x=>
                (Id:x.Id,Symbol:x.Symbol,Units:x.Units,Margin:x.MarginPerUnit)).ToArray();
        return items.Select(x=>new NativePendingCapitalGate.Commitment(
            x.Id,x.Symbol,x.Units,x.Margin,
            plans.TryGetValue(x.Id,out var p)?
                Math.Max(0m,p.RiskEur):0m,
            "CPE1_SINGLE_ECONOMIC_EPISODE",pending)).ToArray();
    }

    static decimal? Cpe1LowerObservedGross(
        Ucp1Episode[] known,string family)
    {
        var a=known.Where(x=>x.Family==family &&
            !x.CrossedUnknownHistory&&x.EconomicEvidence is {
                CompletePair:true,ConditionalNetKnown:true,RealizedGrossR:not null})
            .ToArray();
        if(a.Length<20 || a.Select(x=>x.CloseAt/86400000L).Distinct().Count()<3)
            return null;
        // Descriptive one-sided sampling bound. Sequential reuse and market
        // dependence forbid an independent statistical certification.
        var values=a.Select(x=>x.EconomicEvidence!.RealizedGrossR!.Value).ToArray();
        decimal mean=values.Average();
        double sampleVariance=values.Select(v=>Math.Pow((double)(v-mean),2)).Sum()/(values.Length-1);
        return mean-1.645m*(decimal)(Math.Sqrt(sampleVariance/values.Length));
    }

    Ucp1FrameResult AdvanceCpe1(long at,Ucp1Frame frame,
        List<(Ucp1DecisionSignal Signal,Ucp1MarketFrame Frame)> options)
    {
        var book=model.Ledger.Summary(at);
        if(policy=="CPE1_CASH" || cpe1UnreconciledFunding ||
           book.LiquidationEquityEur is not >0m ||
           book.MaximumSampledDrawdown>=.28m)
            return RecordIntegratedFrame(at,book);
        var held=Cpe1Commitments(false);
        var pending=Cpe1Commitments(true);
        if(held.Length+pending.Length>=2 || held.Any(x=>
            plans.TryGetValue(x.PositionId,out var p)&&p.FinancingUnknown))
        {
            Count("CPE1_HELD_OR_PENDING_CAPACITY_OR_UNKNOWN_FINANCE");
            return RecordIntegratedFrame(at,book);
        }
        var candidates=new List<(Ucp1DecisionSignal Signal,Ucp1MarketFrame Market,
            NativeIntegratedPlan Geometry,decimal Units,decimal Score)>();
        foreach(var (signal,market) in options.OrderBy(x=>x.Frame.Symbol,StringComparer.Ordinal)
            .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal))
        {
            if(!Cpe1Usable(market,at) || !Cpe1Levels(signal,market).HasValue)
                continue;
            var levels=Cpe1Levels(signal,market)!.Value;
            decimal units=market.Contract.MinimumUnits;
            decimal slip=market.SlippagePerSideQuote;
            var q=market.Quote;
            var bracket=NativeExecutableEconomics.Bracket(
                q,signal.Side,units,levels.Stop,levels.Target,slip,slip);
            if(bracket.RiskEur<=0m || bracket.RewardEur<=0m ||
               signal.Side*(bracket.Entry-levels.Stop)<=0m)
            {
                Count("CPE1_NO_FINANCIALLY_POSITIVE_PRICE_GEOMETRY");
                continue;
            }
            var gate=NativePendingCapitalGate.Assess(book.LiquidationEquityEur,
                book.UsedMarginEur is not null,held,pending,
                new NativePendingCapitalGate.Proposal(market.Symbol,
                    "CPE1_SINGLE_ECONOMIC_EPISODE",units,market.Contract.VolumeStepUnits,
                    units,q.MarginPerUnit,bracket.RiskEur/units));
            if(!gate.IsFinanceable)
            {
                Count("CPE1_HELD_PENDING_"+gate.Status);continue;
            }
            // Causal evidence refers only to previously COMPLETED episodes,
            // never to still-Held future outcomes or this candidate's payoff.
            var lower=Cpe1LowerObservedGross(trips.ToArray(),signal.Family);
            // One declared initial learning phase: use affordable minimum
            // trades until 20 uncensored whole episodes become observable.
            // Calibration trades are REAL modeled P/L, not free shadow labels.
            bool calibration=trips.Count(x=>x.Family==signal.Family &&
                x.EconomicEvidence is {CompletePair:true,ConditionalNetKnown:true}
                && !x.CrossedUnknownHistory)<20;
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
                if(lower is not >0m || lower.Value*bracket.RiskEur-
                    fullRoundTripCost<=0m)
                {Count("CPE1_WAIT_GROSS_OR_CASH_LOWER_NOT_POSITIVE");continue;}
            }
            decimal score=Cpe1Economic && lower.HasValue?
                lower.Value*bracket.RiskEur:bracket.RewardEur/bracket.RiskEur;
            candidates.Add((signal,market,
                new NativeIntegratedPlan(levels.Stop,levels.Target,
                    bracket.RiskEur,bracket.RewardEur)
                    {EntrySlippage=slip},units,score));
        }
        if(candidates.Count==0)
        {
            Count("CPE1_WAIT_NO_FINANCEABLE_EDGE");
            return RecordIntegratedFrame(at,book);
        }
        var chosen=Cpe1Economic?
            candidates.OrderByDescending(x=>x.Score)
                .ThenBy(x=>x.Market.Symbol,StringComparer.Ordinal).First():
            candidates[0];
        var s=chosen.Signal;var m=chosen.Market;
        string id="UCP1/"+policy+"/"+m.Symbol+"/"+s.Family+"/"+at;
        Apply(Event("REQUEST_OPEN",at,id,m.Symbol,s.Side,chosen.Units,
            margin:m.Quote.MarginPerUnit,slip:m.SlippagePerSideQuote,
            reason:"NATIVE_CONDITIONAL_SELECTION"));
        plans.Add(id,new Ucp1Plan(id,m.Symbol,s.Family,s.Side,s.Atr,s.Equilibrium,
            chosen.Geometry.InitialRiskEur,chosen.Geometry.Stop,0m,0L,0m,
            chosen.Units,0m,0m,0L,false,chosen.Geometry));
        admitted++;Count("CPE1_EUR_REWARD_RISK_FUNDED_PENDING");
        return RecordIntegratedFrame(at,model.Ledger.Summary(at));
    }

    NativeIntegratedPlan? Cpe1RecheckFill(Ucp1Plan plan,LedgerEvent intent,
        LedgerSummary current,Ucp1MarketFrame observed,decimal execution)
    {
        if(plan.Integrated is not { } prior || current.LiquidationEquityEur is not >0m ||
           current.MaximumSampledDrawdown>=.28m || !Cpe1Usable(observed,observed.Quote.At) ||
           plan.Side*(execution-prior.Stop)<=0m ||
           plan.Side*(prior.Target-execution)<=0m)
            return null;
        var q=observed.Quote;
        if(cpe1UnreconciledFunding || q.At-intent.At>300000L)
            return null; // No late fill after a missing M5 source clock.
        var bracket=NativeExecutableEconomics.Bracket(q,plan.Side,plan.Units,
            prior.Stop,prior.Target,intent.SlippagePerSide,
            q.LiquidationSlippagePerSide??intent.SlippagePerSide);
        if(bracket.RiskEur<=0m||bracket.RewardEur<=0m)return null;
        var held=Cpe1Commitments(false);
        // The pending intent must be REPRICED at the actual next witnessed
        // fill. Never pass its stale admission risk or stale minimum margin
        // into postfill Held+Pending projected-equity verification.
        var pending=Cpe1Commitments(true)
            .Select(x=>x.PositionId==plan.Id ?
                x with {ReservedStopRiskEur=bracket.RiskEur,
                        MarginPerUnit=Math.Max(x.MarginPerUnit,q.MarginPerUnit)}
                : x).ToArray();
        if(!NativePendingCapitalGate.RevalidatePendingFill(
            current.LiquidationEquityEur,current.UsedMarginEur is not null,
            held,pending,plan.Id))return null;
        var guard=NativePostFillCapitalGuard.Assess(current.LiquidationEquityEur,
            held,pending,plan.Id,plan.Side,q,intent.SlippagePerSide);
        if(!guard.Allowed)return null;
        return prior with {InitialRiskEur=bracket.RiskEur,
            InitialRewardEur=bracket.RewardEur};
    }

    Ucp1Plan Cpe1AccrueOrMarkFunding(Ucp1Plan plan,LedgerPosition held,
        Ucp1MarketFrame market,Ucp1Frame frame)
    {
        var contract=market.Contract;
        var q=market.Quote;
        long at=frame.At;
        long day=86400000L;
        bool intradayKnown=false;
        if(contract.SwapPeriodHours==24 &&
           contract.SwapTimeUtcMinute is int minute && minute>=0&&minute<1440)
        {
            long first=(held.EntryAt/day)*day+minute*60000L;
            if(first<=held.EntryAt)first+=day;
            intradayKnown=first>at;
        }
        decimal? accumulated=null;
        if(intradayKnown)accumulated=0m;
        else
        {
            try
            {
                accumulated=contract.OriginalBrokerAuthenticated?
                    NativeBrokerContractCosts.SignedFinancing(contract,held.EntryAt,
                        at,held.Side,held.Units,q.EurCredit,q.EurDebit):
                    NativeBrokerContractCosts.SignedFinancingCurrentAlgo(contract,
                        held.EntryAt,at,held.Side,held.Units,q.EurCredit,q.EurDebit);
            }
            catch(ArgumentException){accumulated=null;}
            catch(InvalidOperationException){accumulated=null;}
        }
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
        if(model.Ledger.Summary(frame.At).MaximumSampledDrawdown>=.28m)
            return (plan,new("INTEGRATED_CPE1_GLOBAL_DD_PROTECTION",position.Units));
        if(side*(sidePrice-geometry.Stop)<=0m)
            return (plan,new("INTEGRATED_CPE1_OBSERVED_STRUCTURAL_STOP",position.Units));
        var bars=market.M15.Where(x=>x.CloseAt<frame.At).TakeLast(2).ToArray();
        if(bars.Length<2||bars[0].CloseAt!=bars[1].OpenAt)
            return (plan,null); // no invented regime or time exit
        long witness=bars[^1].CloseAt;
        if(witness<=Math.Max(plan.OpenAt,plan.LastEconomicM15))
            return (plan,null);
        plan=plan with {LastEconomicM15=witness};
        decimal displacement=side*(bars[^1].Close-bars[0].Close);
        if(displacement<0m && side*(bars[^1].Close-plan.Equilibrium)<=0m)
            return (plan,new("INTEGRATED_CPE1_M15_THESIS_INVALIDATION",position.Units));
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
        var history=trips.Where(x=>x.Family==plan.Family &&
            !x.CrossedUnknownHistory&&x.EconomicEvidence is {
                CompletePair:true,ConditionalNetKnown:true}).ToArray();
        if(history.Length<20)
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
        decimal probability=(decimal)history.Count(x=>x.GrossEur>0m)/history.Length;
        decimal remainingReward=Math.Max(0m,
            side*(geometry.Target-sidePrice))*position.Units*q.EurCredit;
        decimal remainingLoss=Math.Max(0m,
            side*(sidePrice-geometry.Stop))*position.Units*q.EurDebit;
        decimal futureExitCost=Fee(q,position.Units);
        decimal incrementalValue=probability*remainingReward-
            (1m-probability)*remainingLoss-futureExitCost;
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
        Ucp1Plan plan,LedgerPosition held,LedgerClosedFragment finalPart)
    {
        if(plan.EconomicEntry is null)return null;
        var parts=model.Ledger.ClosedFragments().Where(x=>x.PositionId==held.Id).ToArray();
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
