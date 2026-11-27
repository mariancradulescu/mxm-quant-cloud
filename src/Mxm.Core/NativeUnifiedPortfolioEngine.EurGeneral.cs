using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Mxm.Core;

public sealed partial class NativeUnifiedPortfolioEngine
{
    public const string EurGeneralProbe = "EUR_GENERAL_PROBE";
    public const string EurGeneralSelect = "EUR_GENERAL_SELECT";
    public const string EurGeneralPooled = "EUR_GENERAL_POOLED";
    public const string EurGeneralCash = "EUR_GENERAL_CASH";
    internal const string EurGeneralSchema = "EUR_GENERAL_V1";
    const int GeneralStateSize = 16;

    bool IsEurGeneral => policy is EurGeneralProbe or EurGeneralSelect or EurGeneralPooled or EurGeneralCash;

    internal Ucp1DecisionSignal[] DescribeEurGeneral(Ucp1MarketFrame market, long at,Ucp1Frame? sharedFrame=null)
    {
        if (market.Quote.At != at || market.EurTickSize is not decimal tick || !Cpe1Usable(market, at))
            return Array.Empty<Ucp1DecisionSignal>();
        NativeIntegratedCandidate[] candidates;
        if(eurDevelopmentProfile is {CompeteEconomicFamilies:true} joint)
            candidates=NativeEconomicMechanisms.All.Where(x=>x!=NativeEconomicMechanisms.Scored)
                .SelectMany(x=>NativeEconomicMechanisms.Describe(x,market,at,joint.DistributionTargetRanges,sharedFrame,
                    joint.EconomicGeometryTimeframe,joint.EconomicStopRanges,joint.AnchorEconomicGeometryToClosedStructure,
                    joint.EconomicStructureLookbackBars,joint.ConfirmEconomicEntryOnM5)).ToArray();
        else if(eurDevelopmentProfile is {EconomicMechanism:{ } mechanism} distinct)
            candidates=NativeEconomicMechanisms.Describe(mechanism,market,at,distinct.DistributionTargetRanges,sharedFrame,
                distinct.EconomicGeometryTimeframe,distinct.EconomicStopRanges,distinct.AnchorEconomicGeometryToClosedStructure,
                distinct.EconomicStructureLookbackBars,distinct.ConfirmEconomicEntryOnM5,distinct.Pav1TransitionBars);
        else if(eurDevelopmentProfile is {UseAvailableContext:true} profile)
        {
            if(ObservedWindow(market,NativeBarTimeframe.M5,at) is not { } m5||
                ObservedWindow(market,NativeBarTimeframe.M15,at) is null||
                m5.Bars[^1].CloseAt!=market.M5[^1].CloseAt)
                return Array.Empty<Ucp1DecisionSignal>();
            candidates=NativeGeneralOpportunity.Geometries(market,tick,m5.Bars,
                ObservedWindow(market,NativeBarTimeframe.H1,at)?.Bars??Array.Empty<NativeClosedMarketBar>(),
                profile.DistributionTargetRanges);
        }
        else
        {
            if (NativeClosedMarketContext.CoverageWindows.Where(w => w.Timeframe <= NativeBarTimeframe.H1)
                .Any(w => ObservedWindow(market, w.Timeframe, at) is null))
                return Array.Empty<Ucp1DecisionSignal>();
            candidates=NativeGeneralOpportunity.Describe(market,tick).Select(x=>x.Signal).ToArray();
        }
        if(eurDevelopmentProfile is {RequireEconomicBoundaryEdge:true} edge)
            candidates=candidates.Where(g=>
            {
                var q=market.Quote;
                int side=g.Side;
                decimal now=side>0?q.Bid:q.Ask,entry=side>0?q.Ask:q.Bid,units=market.Contract.MinimumUnits;
                if(NativeEconomicMechanisms.BoundaryContinuationEur(market,at,side,now,g.Stop,g.Target,
                    edge.EconomicManagementTimeframe??edge.EconomicGeometryTimeframe) is not { } value||
                    NativePortfolioFunding.OfferDebit(market,side,units,at,FundingScenarioId) is not decimal carry)return false;
                decimal immediate=NativeExecutableEconomics.EstimateNet(q,q,side,units,entry,now,
                    q.LiquidationSlippagePerSide??market.SlippagePerSideQuote);
                // One adjacent-bar opportunity must cover current round-trip
                // economics. Lifecycle labels and final portfolio still decide.
                return (value.Mean-value.Sem)*units+immediate-carry>0m;
            }).ToArray();
        var general=candidates.Select(geometry =>
        {
            decimal origin = market.M5[^1].Close;
            return new Ucp1DecisionSignal(market.Symbol, geometry.Family, geometry.Side,
                geometry.Volatility, origin, Math.Abs(geometry.Target - origin), geometry.DecisionBar)
            { GeneralGeometry = geometry };
        });
        return (eurDevelopmentProfile is { IncludeRecoveredStructure:true }
            ?general.Concat(Ucp1CausalSignals.Describe(market,at)):general).ToArray();
    }

    static NativeBarWindow? ObservedWindow(Ucp1MarketFrame market, NativeBarTimeframe timeframe, long at)
        => market.ClosedBars is { } context && context.DecisionAt == at
            ? context.Windows.SingleOrDefault(w => w.Timeframe == timeframe && w.Ready &&
                w.Bars.Length >= 2 && w.Bars.All(b => b.CloseAt < at))
            : null;

    static decimal WindowMove(NativeBarWindow window)
    {
        var bars = window.Bars;
        decimal range = bars.Max(b => b.High) - bars.Min(b => b.Low);
        return range > 0m ? (bars[^1].Close - bars[0].Open) / range : 0m;
    }

    static decimal?[] DescribeGeneralState(Ucp1MarketFrame market, Ucp1Frame frame, int side)
    {
        var state = new decimal?[GeneralStateSize];
        int i = 0;
        foreach (var requirement in NativeClosedMarketContext.CoverageWindows)
        {
            var w = ObservedWindow(market, requirement.Timeframe, frame.At);
            if (w is not null)
            {
                state[i] = side * WindowMove(w);
                decimal last = w.Bars[^1].High - w.Bars[^1].Low;
                decimal previous = w.Bars.Take(w.Bars.Length - 1).Average(b => b.High - b.Low);
                if (last + previous > 0m)
                    state[i + 1] = (last - previous) / (last + previous);
            }
            i += 2;
        }

        if (ObservedWindow(market, NativeBarTimeframe.M1, frame.At) is { } minute)
        {
            decimal total = minute.Bars.Sum(b => (decimal)b.TickVolume);
            if (total > 0m)
                state[i] = side * minute.Bars.Sum(b => Math.Sign(b.Close - b.Open) * (decimal)b.TickVolume) / total;
        }
        if (ObservedWindow(market, NativeBarTimeframe.H1, frame.At) is { } hourly && market.OfficialAssetClass is not null)
        {
            var peers = frame.Markets.Where(p => p.Symbol != market.Symbol && p.OfficialAssetClass == market.OfficialAssetClass)
                .Select(p => ObservedWindow(p, NativeBarTimeframe.H1, frame.At)).OfType<NativeBarWindow>()
                .Where(p => p.ExpectedCloseAt == hourly.ExpectedCloseAt).ToArray();
            if (peers.Length > 0)
                state[i + 1] = side * (WindowMove(hourly) - peers.Average(WindowMove)) / 2m;
        }
        return state;
    }

    // Mean closed-bar true range relative to the preceding close; no forming bar.
    // Preserve missingness and avoid treating absolute points across assets as comparable.
    static decimal?[] DescribeRelativeVolatility(Ucp1MarketFrame market,long at)
    {
        return NativeClosedMarketContext.CoverageWindows.Select(r=>
        {
            var w=ObservedWindow(market,r.Timeframe,at);
            if(w is null||w.Bars.Take(w.Bars.Length-1).Any(b=>b.Close<=0m))return (decimal?)null;
            return w.Bars.Skip(1).Select((bar,i)=>
            {
                decimal prior=w.Bars[i].Close;
                return Math.Max(bar.High-bar.Low,Math.Max(Math.Abs(bar.High-prior),Math.Abs(bar.Low-prior)))/prior;
            }).Average();
        }).ToArray();
    }

    // Recover the useful V3.3 closed-bar impulse and relative tick activity
    // without its old categorical thresholds or BPS objective. Each timeframe
    // remains distinct and unavailable windows stay missing.
    internal static decimal?[] DescribeClosedBarActivity(Ucp1MarketFrame market,long at,int side)
    {
        var result=new List<decimal?>(14);
        foreach(var req in NativeClosedMarketContext.CoverageWindows)
        {
            var w=ObservedWindow(market,req.Timeframe,at);
            if(w is null){result.Add(null);result.Add(null);continue;}
            var last=w.Bars[^1];
            var prior=w.Bars[^2];
            decimal range=Math.Max(last.High-last.Low,
                Math.Max(Math.Abs(last.High-prior.Close),Math.Abs(last.Low-prior.Close)));
            decimal priorVolume=w.Bars.Take(w.Bars.Length-1).Average(b=>(decimal)b.TickVolume);
            decimal sum=last.TickVolume+priorVolume;
            result.Add(range>0m?side*(last.Close-prior.Close)/range:null);
            result.Add(sum>0m?(last.TickVolume-priorVolume)/sum:null);
        }
        return result.ToArray();
    }

    static string ProbeKey(NativeEurOpportunity offer)
    {
        var key = FormattableString.Invariant($"{offer.At}|{offer.Symbol}|{offer.Family}|{offer.Side}|{offer.Units:G29}");
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(key)));
    }

    // The extra charge is positive signed H1 co-movement, measured only on
    // common already-closed intervals. The ordinary stop sum grants no offset
    // for negative correlation or unavailable evidence.
    static decimal SignedHourlyCoMovement(Ucp1MarketFrame a, int sideA, Ucp1MarketFrame b, int sideB, long at)
    {
        var left = ObservedWindow(a, NativeBarTimeframe.H1, at);
        var right = ObservedWindow(b, NativeBarTimeframe.H1, at);
        if (left is null || right is null) return 0m;
        var samples = left.Bars.Join(right.Bars, x => (x.OpenAt, x.CloseAt), x => (x.OpenAt, x.CloseAt),
            (x, y) => (X: sideA * (x.Close - x.Open) / x.Open,
                       Y: sideB * (y.Close - y.Open) / y.Open)).ToArray();
        if (samples.Length < 3) return 0m;
        decimal meanX = samples.Average(x => x.X), meanY = samples.Average(x => x.Y);
        decimal x2 = 0m, y2 = 0m, xy = 0m;
        foreach (var (x, y) in samples)
        {
            decimal dx = x - meanX, dy = y - meanY;
            x2 += dx * dx;
            y2 += dy * dy;
            xy += dx * dy;
        }
        return (xy > 0m && x2 > 0m && y2 > 0m)
            ? (decimal)Math.Min(1d, (double)xy / (Math.Sqrt((double)x2) * Math.Sqrt((double)y2))) : 0m;
    }

    void AllocateGeneralEur(Ucp1Frame frame, LedgerSummary book, NativeFundingCapital capital,
        NativePendingCapitalGate.Commitment[] held, List<NativePendingCapitalGate.Commitment> pending,
        List<EurCandidate> choices, Action<EurCandidate> admit, Action<NativeEurOpportunity,string> trace)
    {
        var markets = frame.Markets.ToDictionary(x => x.Symbol, StringComparer.Ordinal);
        var relation = new Dictionary<(string,int,string,int),decimal>();
        decimal CoMovement(EurCandidate a, Ucp1MarketFrame b, int side)
        {
            var key = (a.Market.Symbol, a.Signal.Side, b.Symbol, side);
            if (!relation.TryGetValue(key, out decimal value))
            {
                value = SignedHourlyCoMovement(a.Market, a.Signal.Side, b, side, frame.At);
                relation.Add(key, value);
            }
            return value;
        }

        NativePendingCapitalGate.Commitment Reserve(EurCandidate item, string id)
            => new(id, item.Market.Symbol, item.Receipt.Units, item.Market.Quote.MarginPerUnit,
                item.Geometry.InitialRiskEur, item.Signal.Family, true);

        decimal CorrelatedRisk(EurCandidate candidate,IEnumerable<NativePendingCapitalGate.Commitment> commitments,
            string preview="",EurCandidate? first=null)
        {
            decimal extra=0m;
            foreach(var open in commitments)
            {
                if(!markets.TryGetValue(open.Symbol,out var peer))continue;
                int side=open.PositionId==preview?first!.Signal.Side:plans[open.PositionId].Side;
                extra+=CoMovement(candidate,peer,side)*Math.Min(candidate.Geometry.InitialRiskEur,open.ReservedStopRiskEur);
            }
            return extra;
        }

        string? Rejection(EurCandidate candidate, EurCandidate? first = null)
        {
            // Preview an alternative without releasing any held or pending
            // exposure. No volume or risk is reused until an actual close fill.
            const string preview = "GENERAL_PREVIEW";
            var projected = first is null ? new List<NativePendingCapitalGate.Commitment>(pending) :
                pending.Append(Reserve(first, preview)).ToList();
            var gate=AssessEurCandidate(capital,book,held,projected,candidate,
                CorrelatedRisk(candidate,held.Concat(projected),preview,first));
            if (!gate.IsFinanceable) return EurRejectedCapital(gate.Status, book, capital);

            const string next = "GENERAL_NEXT";
            projected.Add(Reserve(candidate, next));
            var quote = candidate.Market.Quote;
            var check = NativePostFillCapitalGuard.Assess(capital.ResearchAdmissionEquityEur, held, projected,
                next, candidate.Signal.Side, quote, candidate.Market.SlippagePerSideQuote,
                candidate.Receipt.NextManagementFundingCeilingEur!.Value, quote.LiquidationSlippagePerSide);
            if (!check.Allowed) return "WAIT_" + check.Reason;
            if(eurDevelopmentProfile?.ReserveMarginForStopRisk==true&&
                !NativePendingCapitalGate.StopAdjustedMarginFits(check.ProjectedPostFillLiquidationEquityEur,
                    check.TotalReservedMarginEur,gate.ReservedRiskAfterEur))return "WAIT_STOP_ADJUSTED_POST_FILL_MARGIN";
            decimal floor = book.ObservedPeakEur * (1m - OwnerRiskAuthority.MaximumSystemDrawdown);
            return Math.Min(check.ProjectedPostFillLiquidationEquityEur,
                check.PreFillLiquidationEquityEur - gate.ReservedRiskAfterEur) < floor
                ? "WAIT_DRAWDOWN_RISK_BUDGET" : null;
        }

        decimal Net(EurCandidate candidate)=>candidate.Receipt.Payoff!.NetLowerEur;
        decimal Value(EurCandidate candidate)
        {
            if(eurDevelopmentProfile?.UseAdaptiveAllocation!=true)return Net(candidate);
            var risk=candidate.Geometry.InitialRiskEur+CorrelatedRisk(candidate,held.Concat(pending));
            return Net(candidate)/risk;
        }
        if(eurDevelopmentProfile?.UseJointMonetaryAllocation==true||eurDevelopmentProfile?.OptimizeTransitionNetVolume==true||
            eurDevelopmentProfile?.CompeteEconomicFamilies==true)
        {
            // Preview whole financeable sets under the same held+pending
            // and post-fill protections. A requested close never frees cash.
            bool Feasible(EurCandidate candidate,IReadOnlyList<EurCandidate> previous)
            {
                var projected=new List<NativePendingCapitalGate.Commitment>(pending);
                var sides=new Dictionary<string,int>(StringComparer.Ordinal);
                for(int i=0;i<previous.Count;i++)
                {
                    string id="JOINT_PREVIEW_"+i;
                    projected.Add(Reserve(previous[i],id));
                    sides.Add(id,previous[i].Signal.Side);
                }
                decimal extra=0m;
                foreach(var exposure in held.Concat(projected))
                {
                    if(!markets.TryGetValue(exposure.Symbol,out var peer))continue;
                    int side=sides.TryGetValue(exposure.PositionId,out int simulated)?simulated:plans[exposure.PositionId].Side;
                    extra+=CoMovement(candidate,peer,side)*Math.Min(candidate.Geometry.InitialRiskEur,exposure.ReservedStopRiskEur);
                }
                var gate=AssessEurCandidate(capital,book,held,projected,candidate,extra);
                if(!gate.IsFinanceable)return false;
                const string next="JOINT_NEXT";
                projected.Add(Reserve(candidate,next));
                var q=candidate.Market.Quote;
                var guard=NativePostFillCapitalGuard.Assess(capital.ResearchAdmissionEquityEur,held,projected,
                    next,candidate.Signal.Side,q,candidate.Market.SlippagePerSideQuote,
                    candidate.Receipt.NextManagementFundingCeilingEur!.Value,q.LiquidationSlippagePerSide);
                decimal floor=book.ObservedPeakEur*(1m-OwnerRiskAuthority.MaximumSystemDrawdown);
                return guard.Allowed&&(eurDevelopmentProfile?.ReserveMarginForStopRisk!=true||
                    NativePendingCapitalGate.StopAdjustedMarginFits(guard.ProjectedPostFillLiquidationEquityEur,
                        guard.TotalReservedMarginEur,gate.ReservedRiskAfterEur))&&Math.Min(guard.ProjectedPostFillLiquidationEquityEur,
                    guard.PreFillLiquidationEquityEur-gate.ReservedRiskAfterEur)>=floor;
            }
            for(int i=choices.Count-1;i>=0;i--)
                if(Rejection(choices[i]) is { } reason)
                {trace(choices[i].Receipt,reason);choices.RemoveAt(i);}
            var selected=NativeEurMonetaryAllocation.Search(choices,x=>x.Market.Symbol,Net,Feasible,
                eurDevelopmentProfile.JointMonetarySearchWidth>0?eurDevelopmentProfile.JointMonetarySearchWidth:8);
            foreach(var item in selected.Items)
            {
                if(Rejection(item) is { } reason){trace(item.Receipt,reason);continue;}
                admit(item);
            }
            foreach(var item in choices.Where(x=>!selected.Items.Contains(x)))
                trace(item.Receipt,"WAIT_JOINT_MONETARY_ALTERNATIVE");
            return;
        }
        while (choices.Count > 0)
        {
            for (int i = choices.Count - 1; i >= 0; i--)
                if (Rejection(choices[i]) is { } reason)
                {
                    trace(choices[i].Receipt, reason);
                    choices.RemoveAt(i);
                }
            if (choices.Count == 0) break;
            var ordered = choices.OrderByDescending(Value).ToArray();
            var winner = ordered[0];
            decimal best = 0m, displacement = 0m;
            foreach (var item in ordered)
            {
                var competing = ordered.FirstOrDefault(x => x != item);
                var companion = ordered.FirstOrDefault(x => x.Market.Symbol != item.Market.Symbol &&
                    Rejection(x, item) is null);
                decimal attainable = Value(item) + (companion is null ? 0m : Value(companion));
                if (attainable <= best) continue;
                winner = item;
                best = attainable;
                displacement = (competing is null ? 0m : Net(competing)) -
                    (companion is null ? 0m : Net(companion));
            }
            admit(winner with { Receipt = winner.Receipt with { DisplacedAlternativeEur = displacement } });
            choices.Remove(winner);
        }
    }

    NativeModelCloseInstruction? ManageGeneralEur(Ucp1Plan plan, LedgerPosition position,
        Ucp1MarketFrame market, Ucp1Frame frame, NativeFundingCapital? capital, decimal price, decimal displacement)
    {
        var geometry = plan.Integrated!;
        var q = market.Quote;
        int side = position.Side;
        decimal residual = side * (geometry.Target - price);
        if(eurDevelopmentProfile?.EconomicMechanism is not null)
        {
            if(residual<=0m)return new("INTEGRATED_MECHANISM_TARGET",position.Units);
            string? management=geometry.SelectedEconomicManagement??eurDevelopmentProfile.EconomicManagement;
            if(management=="BRACKET")return null;
            decimal? debit=NativePortfolioFunding.OfferDebit(market,side,position.Units,frame.At,FundingScenarioId);
            bool boundary=management is NativeEconomicMechanisms.BoundaryValue or NativeEconomicMechanisms.BoundaryReduce;
            string? tf=eurDevelopmentProfile.EconomicManagementTimeframe??eurDevelopmentProfile.EconomicGeometryTimeframe;
            var estimate=boundary?NativeEconomicMechanisms.BoundaryContinuationEur(market,frame.At,side,price,geometry.Stop,geometry.Target,tf):
                NativeEconomicMechanisms.Continuation(market,frame.At,tf,eurDevelopmentProfile.Pav1TransitionBars);
            if(debit is null||estimate is not { } transition)return null;
            // Preserve the original decimal operation order for all frozen
            // management policies. Only the new boundary mode is in EUR/unit.
            decimal change=side*transition.Mean*position.Units;
            decimal value=(boundary?transition.Mean*position.Units:change*(change>=0m?q.EurCredit:q.EurDebit))-debit.Value;
            decimal uncertainty=boundary?transition.Sem*position.Units:transition.Sem*position.Units*q.EurDebit;
            decimal uncertaintyEur=boundary?transition.Sem:transition.Sem*q.EurDebit;
            if(management is NativeEconomicMechanisms.MonetaryReduce or NativeEconomicMechanisms.BoundaryReduce)
            {
                // Do not use differences of funding ceilings as a guaranteed
                // monetary saving. First compare actual common-book constraints.
                decimal best=0m,closeUnits=0m;
                if(!geometry.Reduced&&fundingReserves is not null&&!fundingReserves.IsOutstanding(position.Id)&&
                    capital?.ResearchAdmissionEquityEur is decimal equity&&equity>0m&&capital.HeldMarginEur.HasValue&&
                    !model.Ledger.PendingSnapshot().Any(x=>x.Kind=="REQUEST_CLOSE"))
                {
                    var commitments=Cpe1Commitments(false,frame).Concat(Cpe1Commitments(true,frame)).ToArray();
                    var own=commitments.SingleOrDefault(x=>x.PositionId==position.Id);
                    if(own is not null&&own.Units==position.Units)
                    {
                        decimal otherMargin=commitments.Where(x=>x.PositionId!=position.Id).Sum(x=>x.MarginEur);
                        decimal otherRisk=commitments.Where(x=>x.PositionId!=position.Id).Sum(x=>x.ReservedStopRiskEur);
                        decimal floor=model.Ledger.Summary(frame.At).ObservedPeakEur*(1m-OwnerRiskAuthority.MaximumSystemDrawdown);
                        var offers=market.FundingOffers??Array.Empty<NativeFundingOfferEvidence>();
                        long? Horizon(decimal units)
                        {
                            var rows=offers.Where(f=>f.ScenarioId==FundingScenarioId&&f.Symbol==market.Symbol&&
                                f.Side==side&&f.Units==units&&f.AvailableAt>0&&f.AvailableAt<=frame.At&&
                                f.EffectiveFrom>0&&f.EffectiveFrom<=frame.At).Take(2).ToArray();
                            return rows.Length==1?rows[0].NextScheduledManagementAt:null;
                        }
                        long? fullHorizon=Horizon(position.Units);
                        decimal meanPerUnit=boundary?transition.Mean:Math.Min(side*transition.Mean,residual);
                        if(!boundary)meanPerUnit*=meanPerUnit>=0m?q.EurCredit:q.EurDebit;
                        decimal fullFee=Fee(q,position.Units,-side);
                        decimal slip=q.LiquidationSlippagePerSide??position.SlippagePerSide;
                        decimal stopDistance=Math.Max(0m,side*(price-geometry.Stop))+slip+geometry.GapReservePerUnitQuote;
                        decimal riskPerUnit=stopDistance*q.EurDebit;
                        decimal fullRisk=Math.Max(own.ReservedStopRiskEur,riskPerUnit*position.Units+fullFee+debit.Value);
                        foreach(decimal retainedUnits in offers.Select(f=>f.Units).Distinct().OrderBy(u=>u))
                        {
                            if(retainedUnits<=0m||retainedUnits>=position.Units||fullHorizon is null||
                                Horizon(retainedUnits)!=fullHorizon||EurMargin(market,side,retainedUnits,frame.At) is null)continue;
                            decimal close=position.Units-retainedUnits;
                            var remainderDebit=NativePortfolioFunding.OfferDebit(market,side,retainedUnits,frame.At,FundingScenarioId);
                            if(remainderDebit is not decimal residualDebit)continue;
                            decimal residualFee=Fee(q,retainedUnits,-side);
                            // The common ledger releases booked risk proportionally.
                            // Do not accept a residual that exceeds that reserve.
                            decimal residualRisk=riskPerUnit*retainedUnits+residualFee+residualDebit;
                            decimal reservedResidual=own.ReservedStopRiskEur*retainedUnits/position.Units;
                            if(residualRisk>reservedResidual)continue;
                            var advantage=NativeEconomicMechanisms.ConstrainedReductionValue(position.Units,close,
                                market.Contract.MinimumUnits,market.Contract.MaximumUnits,market.Contract.VolumeStepUnits,
                                meanPerUnit,uncertaintyEur,residualDebit,fullFee,
                                Fee(q,close,-side),residualFee,equity,floor,otherMargin,otherRisk,own.MarginPerUnit,
                                fullRisk,reservedResidual);
                            if(advantage is decimal candidate&&candidate>best){best=candidate;closeUnits=close;}
                        }
                    }
                }
                if(closeUnits>0m)
                {
                    Count("EUR_MONETARY_REDUCE_FEASIBLE_POSITIVE_RESIDUAL");
                    return new(NativeSimulatedCloseLifecycle.AdaptiveContinuationReduction,closeUnits);
                }
                Count("EUR_MONETARY_REDUCE_NO_EVIDENCED_DOMINANCE");
                return value+uncertainty<0m?new("INTEGRATED_MECHANISM_NEGATIVE_CONTINUATION",position.Units):null;
            }
            if(value+uncertainty<0m)return new("INTEGRATED_MECHANISM_NEGATIVE_CONTINUATION",position.Units);
            if((management=="CAPTURE_VALUE"||management==NativeEconomicMechanisms.BoundaryValue)&&position.EntryQuote is { } entry&&
                position.EntryPrice is decimal entryPrice)
            {
                // Immediate executable liquidation is the alternative to HOLD.
                // No future MFE is referenced and already paid entry costs are sunk.
                decimal now=NativeExecutableEconomics.EstimateNet(entry,q,side,position.Units,
                    entryPrice,price,q.LiquidationSlippagePerSide??position.SlippagePerSide)+position.FinancingRemaining;
                if(now>0m&&value<=0m&&fundingReserves is not null&&!fundingReserves.IsOutstanding(position.Id))
                    return new("INTEGRATED_MECHANISM_CAPTURE_NONPOSITIVE_CONTINUATION",position.Units);
            }
            if(boundary)return null; // no arbitrary minimum-lot reduction without portfolio dominance
            decimal minimum=market.Contract.MinimumUnits,volumeStep=market.Contract.VolumeStepUnits;
            decimal rest=position.Units-minimum;
            return value<0m&&!geometry.Reduced&&minimum>0m&&volumeStep>0m&&rest>=minimum&&(rest-minimum)%volumeStep==0m
                ?new(NativeSimulatedCloseLifecycle.AdaptiveContinuationReduction,minimum):null;
        }
        if (residual <= 0m)
            return ManageFundedTarget(plan, position, market, price, displacement);

        // Compare the remaining target with immediate liquidation; entry fees
        // and already earned P&L are sunk. No assumed fill or unknown carry.
        decimal? carry = NativePortfolioFunding.OfferDebit(market, side, position.Units, frame.At, FundingScenarioId);
        decimal? remaining = residual * position.Units * q.EurCredit - carry;
        if(eurDevelopmentProfile?.UseAdaptiveManagement==true&&remaining is decimal upside&&displacement<0m&&
            ObservedWindow(market,NativeBarTimeframe.H1,frame.At) is { } hourly&&
            side*(hourly.Bars[^1].Close-hourly.Bars[0].Open)<0m)
        {
            // Value of continuing is measured against liquidation now. Entry
            // fees are sunk. Use executable liquidation costs at each boundary.
            decimal slip=q.LiquidationSlippagePerSide??position.SlippagePerSide;
            decimal stop=NativeExecutableEconomics.ExitPrice(geometry.Stop,side,slip);
            decimal current=NativeExecutableEconomics.ExitPrice(price,side,slip);
            decimal downside=side*(current-stop)*position.Units*q.EurDebit+carry!.Value;
            if(downside>0m&&upside<downside)
            {
                decimal lot=market.Contract.MinimumUnits,volumeStep=market.Contract.VolumeStepUnits;
                decimal rest=position.Units-lot;
                bool canReduce=!geometry.Reduced&&upside>0m&&lot>0m&&volumeStep>0m&&rest>=lot&&(rest-lot)%volumeStep==0m;
                return new(canReduce?NativeSimulatedCloseLifecycle.AdaptiveContinuationReduction:
                    NativeSimulatedCloseLifecycle.AdaptiveContinuationClose,canReduce?lot:position.Units);
            }
        }
        if (displacement < 0m && (remaining is <= 0m || side * (market.M15[^1].Close - plan.Equilibrium) <= 0m))
            return new("INTEGRATED_EUR_GENERAL_THESIS_LOST_VALUE", position.Units);

        if (capital?.ResearchAdmissionEquityEur is not > 0m || capital.HeldMarginEur is null ||
            capital.HeldMarginEur + capital.PendingOpenMarginEur <=
                capital.ResearchAdmissionEquityEur * NativePendingCapitalGate.MaximumMarginFraction ||
            displacement > 0m || model.Ledger.PendingSnapshot().Any(x => x.Kind == "REQUEST_CLOSE"))
            return null;

        decimal min = market.Contract.MinimumUnits, step = market.Contract.VolumeStepUnits;
        decimal remainingUnits = position.Units - min;
        return min > 0m && step > 0m && remainingUnits >= min && (remainingUnits - min) % step == 0m
            ? new(NativeSimulatedCloseLifecycle.MarginReduction, min)
            : new("INTEGRATED_EUR_GENERAL_MARGIN_PRESSURE", position.Units);
    }
}
