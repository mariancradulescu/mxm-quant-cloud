using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeEurMarginObservation(int Side,decimal Units,decimal MarginEur,
    long ObservedAt,string SourceSha256);
public sealed record NativeEurPayoff(int ReconciledEpisodes,int ObservationDays,
    decimal GrossMeanEur,decimal GrossLowerEur,decimal NetMeanEur,decimal NetLowerEur,
    decimal ObservedPositiveNetFraction,decimal NetWorstEur,decimal NetBestEur);
public sealed record NativeEurOpportunity(long At,string Symbol,string Family,int Side,
    decimal Units,decimal GrossTargetEur,decimal GrossRiskEur,decimal KnownRoundTripCostEur,
    decimal? NextManagementFundingCeilingEur,decimal? CurrentMarginEstimateEur,
    decimal? ReservedRiskEur,decimal? HeldMarginEur,decimal? PendingMarginEur,
    decimal? EquityEur,NativeEurPayoff? Payoff,string Decision);

public sealed partial class NativeUnifiedPortfolioEngine
{
    public const string EurFirst="EUR_FIRST";
    public const string EurRank="EUR_RANK";
    public const string EurCash="EUR_CASH";

    sealed record ReconciledPayoff(long CloseDay,decimal GrossEur,decimal NetEur,decimal RiskEur);
    sealed record EurCandidate(Ucp1DecisionSignal Signal,Ucp1MarketFrame Market,
        NativeIntegratedPlan Geometry,NativeEurOpportunity Receipt);
    readonly Dictionary<(string Family,int Side),List<ReconciledPayoff>> eurHistory=new();
    readonly List<NativeEurOpportunity> eurOpportunities=new();

    void RememberEurOutcome(Ucp1Episode trip,Ucp1ReconciledEpisode reconciled)
    {
        var evidence=reconciled.Evidence;
        if(evidence is not {ClosedGrossEur:decimal gross,ClosedNetEur:decimal net,ReservedRiskEur:>0m})return;
        var key=(trip.Family,trip.Side);
        if(!eurHistory.TryGetValue(key,out var history))eurHistory.Add(key,history=new());
        history.Add(new(trip.CloseAt/86400000L,gross,net,evidence.ReservedRiskEur));
    }

    // Compare CASH against paired, settled cash outcomes at candidate risk.
    // The currently evidenced closing cost can make a historical outcome worse.
    // Taking the smaller NET avoids crediting a cheaper historical tariff and
    // avoids charging the same cost twice. Use day means as the sample unit.
    internal NativeEurPayoff? EurPayoff(string family,int side,decimal candidateRiskEur,decimal currentCostFloorEur)
    {
        if(!eurHistory.TryGetValue((family,side),out var history)||history.Count<20)return null;
        var samples=history.Select(x=>
        {
            decimal scale=candidateRiskEur/x.RiskEur;
            decimal gross=x.GrossEur*scale;
            return (x.CloseDay,Gross:gross,Net:Math.Min(x.NetEur*scale,gross-currentCostFloorEur));
        }).ToArray();
        var days=samples.GroupBy(x=>x.CloseDay).OrderBy(g=>g.Key)
            .Select(g=>(Gross:g.Average(x=>x.Gross),Net:g.Average(x=>x.Net))).ToArray();
        if(days.Length<3)return null;
        decimal grossMean=days.Average(x=>x.Gross),netMean=days.Average(x=>x.Net);
        // The existing program's one-sided 1.645 standard-error penalty,
        // applied separately to the day-block series. Diagnostic only.
        decimal Lower(decimal mean,IEnumerable<decimal> sample)
            =>mean-1.645m*(decimal)Math.Sqrt(sample.Sum(x=>Math.Pow((double)(x-mean),2))/
                ((double)days.Length*(days.Length-1)));
        return new(history.Count,days.Length,grossMean,Lower(grossMean,days.Select(x=>x.Gross)),
            netMean,Lower(netMean,days.Select(x=>x.Net)),
            (decimal)samples.Count(x=>x.Net>0m)/samples.Length,samples.Min(x=>x.Net),samples.Max(x=>x.Net));
    }

    internal static NativeEurMarginObservation? EurMargin(Ucp1MarketFrame market,int side,decimal units,long at)
    {
        var contract=market.Contract;
        if(contract.VolumeStepUnits<=0m||units<contract.MinimumUnits||units>contract.MaximumUnits||
            (units-contract.MinimumUnits)%contract.VolumeStepUnits!=0m)return null;
        var offers=market.EurMargins?.Where(x=>x.Side==side&&x.Units==units&&x.MarginEur>0m&&
            x.ObservedAt>=contract.ObservedAtUtcMs&&x.ObservedAt<=at&&at-x.ObservedAt<=60_000L&&
            x.SourceSha256 is {Length:64}&&x.SourceSha256.All(Uri.IsHexDigit)&&
            x.MarginEur-market.Quote.MarginPerUnit*units<=.0000000000000001m).Take(2).ToArray();
        return offers is {Length:1}?offers[0]:null;
    }

    Ucp1FrameResult AdvanceEur(long at,Ucp1Frame frame,
        List<(Ucp1DecisionSignal Signal,Ucp1MarketFrame Frame)> options)
    {
        var book=model.Ledger.Summary(at);
        var capital=Cpe1FundingCapital(book,frame)!;
        var held=Cpe1Commitments(false,frame);
        var pending=Cpe1Commitments(true,frame).ToList();
        var choices=new List<EurCandidate>();
        void Trace(NativeEurOpportunity o,string state)
        {
            Count("EUR_"+state);
            if(!researchFork)eurOpportunities.Add(o with {Decision=state,
                HeldMarginEur=capital.HeldMarginEur,PendingMarginEur=pending.Sum(x=>x.MarginEur)});
        }
        foreach(var (s,market) in options.OrderBy(x=>x.Frame.Symbol,StringComparer.Ordinal)
            .ThenBy(x=>x.Signal.Family,StringComparer.Ordinal).ThenBy(x=>x.Signal.Side))
        {
            if(!Cpe1Usable(market,at)||Cpe1Levels(s,market) is not { } levels)continue;
            var unitsOffered=(market.EurMargins??Array.Empty<NativeEurMarginObservation>())
                .Where(x=>x.Side==s.Side&&x.Units>0m).Select(x=>x.Units)
                .Append(market.Contract.MinimumUnits).Distinct().OrderByDescending(x=>x);
            foreach(var units in unitsOffered)
            {
                var q=market.Quote;
                var bracket=NativeExecutableEconomics.Bracket(q,s.Side,units,levels.Stop,levels.Target,
                    market.SlippagePerSideQuote,q.LiquidationSlippagePerSide??market.SlippagePerSideQuote);
                decimal mid=(q.Bid+q.Ask)/2m,conversion=(q.EurCredit+q.EurDebit)/2m;
                decimal grossTarget=s.Side*(levels.Target-mid)*units*conversion;
                decimal grossRisk=s.Side*(mid-levels.Stop)*units*conversion;
                decimal roundTripCost=Math.Max(0m,-NativeExecutableEconomics.EstimateNet(q,q,s.Side,
                    units,bracket.Entry,s.Side>0?q.Bid:q.Ask,
                    q.LiquidationSlippagePerSide??market.SlippagePerSideQuote));
                var margin=EurMargin(market,s.Side,units,at);
                var debit=NativePortfolioFunding.OfferDebit(market,s.Side,units,at);
                decimal? risk=bracket.RiskEur+debit;
                var payoff=risk is >0m?EurPayoff(s.Family,s.Side,risk.Value,roundTripCost+debit!.Value):null;
                var receipt=new NativeEurOpportunity(at,market.Symbol,s.Family,s.Side,units,grossTarget,grossRisk,
                    roundTripCost,debit,margin?.MarginEur,risk,capital.HeldMarginEur,capital.PendingOpenMarginEur,
                    capital.DemonstrableEquityEur,payoff,"ASSESS");
                string? unavailable=margin is null?"WAIT_VOLUME_MARGIN_EVIDENCE":debit is null?"WAIT_FUNDING_CEILING":
                    grossRisk<=0m||grossTarget<=0m||risk is not >0m||bracket.RewardEur<=debit.Value?"WAIT_PRICE_GEOMETRY":
                    policy==EurCash?"WAIT_CASH":
                    capital.MaximumSampledFundingAdjustedDrawdown>=.28m?"WAIT_PORTFOLIO_DRAWDOWN":
                    policy==EurRank&&!frame.EurCalibration&&payoff is not {GrossLowerEur:>0m,NetLowerEur:>0m}
                        ?"WAIT_RECONCILED_PAYOFF_EVIDENCE":null;
                if(unavailable is not null){Trace(receipt,unavailable);continue;}
                choices.Add(new(s,market,new NativeIntegratedPlan(levels.Stop,levels.Target,risk!.Value,
                    bracket.RewardEur-debit!.Value){EntrySlippage=market.SlippagePerSideQuote},receipt));
            }
        }

        IEnumerable<EurCandidate> ranked=policy==EurRank&&!frame.EurCalibration?
            choices.OrderByDescending(x=>x.Receipt.Payoff!.NetLowerEur):choices;
        foreach(var choice in ranked)
        {
            var s=choice.Signal;
            var market=choice.Market;
            var receipt=choice.Receipt;
            decimal units=receipt.Units, margin=market.Quote.MarginPerUnit;
            var gate=NativePendingCapitalGate.Assess(capital.DemonstrableEquityEur,book.UsedMarginEur is not null,
                held,pending,new(market.Symbol,s.Family,units,market.Contract.VolumeStepUnits,units,
                    margin,choice.Geometry.InitialRiskEur/units));
            if(!gate.IsFinanceable){Trace(receipt,"WAIT_"+gate.Status);continue;}
            string id="UCP1/"+policy+"/"+market.Symbol+"/"+s.Family+"/"+at;
            Apply(Event("REQUEST_OPEN",at,id,market.Symbol,s.Side,units,margin:margin,
                slip:market.SlippagePerSideQuote,reason:"NATIVE_CONDITIONAL_SELECTION") with
                {AvailableAt=at,CalibratedThrough=s.LastCompletedM5At,TracksLateFunding=true});
            plans.Add(id,new(id,market.Symbol,s.Family,s.Side,s.Atr,s.Equilibrium,choice.Geometry.InitialRiskEur,
                choice.Geometry.Stop,0m,0L,0m,units,0m,0m,0L,false,choice.Geometry));
            pending.Add(new(id,market.Symbol,units,margin,choice.Geometry.InitialRiskEur,s.Family,true));
            admitted++;
            Trace(receipt,s.Side>0?"LONG_PENDING":"SHORT_PENDING");
        }
        return RecordIntegratedFrame(at,model.Ledger.Summary(at),frame);
    }

    NativeModelCloseInstruction? ManageFundedTarget(Ucp1Plan plan,LedgerPosition position,
        Ucp1MarketFrame market,decimal price,decimal displacement)
    {
        var geometry=plan.Integrated!;
        if(position.Side*(price-geometry.Target)<0m)return null;
        decimal minimum=market.Contract.MinimumUnits,remainder=position.Units-minimum;
        bool legal=market.Contract.VolumeStepUnits>0m&&remainder>=minimum&&
            (remainder-minimum)%market.Contract.VolumeStepUnits==0m;
        if(geometry.Reduced)return displacement<=0m?new("INTEGRATED_EUR_TARGET_CONTINUATION_ENDED",position.Units):null;
        var q=market.Quote;
        var entry=position.EntryQuote;
        decimal increment=entry is null?0m:NativeExecutableEconomics.EstimateNet(entry,q,position.Side,
            position.Units,position.EntryPrice!.Value,price,q.LiquidationSlippagePerSide??position.SlippagePerSide);
        if(legal&&displacement>0m&&increment+position.FinancingRemaining>0m&&
            !fundingReserves!.IsOutstanding(position.Id))
            return new("INTEGRATED_FAVORABLE_REDUCTION",minimum);
        return new("INTEGRATED_EUR_TARGET_OBSERVED",position.Units);
    }
}
