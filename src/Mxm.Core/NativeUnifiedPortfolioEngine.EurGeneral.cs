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
    const string EurGeneralSchema = "EUR_GENERAL_V1";
    const int GeneralStateSize = 16;

    bool IsEurGeneral => policy is EurGeneralProbe or EurGeneralSelect or EurGeneralPooled or EurGeneralCash;

    Ucp1DecisionSignal[] DescribeEurGeneral(Ucp1MarketFrame market, long at)
    {
        if (market.Quote.At != at || market.EurTickSize is not decimal tick || !Cpe1Usable(market, at))
            return Array.Empty<Ucp1DecisionSignal>();
        NativeIntegratedCandidate[] candidates;
        if(eurDevelopmentProfile is {UseAvailableContext:true} profile)
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
        return candidates.Select(geometry =>
        {
            decimal origin = market.M5[^1].Close;
            return new Ucp1DecisionSignal(market.Symbol, geometry.Family, geometry.Side,
                geometry.Volatility, origin, Math.Abs(geometry.Target - origin), geometry.DecisionBar)
            { GeneralGeometry = geometry };
        }).ToArray();
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

        string? Rejection(EurCandidate candidate, EurCandidate? first = null)
        {
            // Preview an alternative without releasing any held or pending
            // exposure. No volume or risk is reused until an actual close fill.
            const string preview = "GENERAL_PREVIEW";
            var projected = first is null ? new List<NativePendingCapitalGate.Commitment>(pending) :
                pending.Append(Reserve(first, preview)).ToList();
            decimal extra = 0m;
            foreach (var open in held.Concat(projected))
            {
                if (!markets.TryGetValue(open.Symbol, out var peer)) continue;
                int side = open.PositionId == preview ? first!.Signal.Side : plans[open.PositionId].Side;
                extra += CoMovement(candidate, peer, side) * Math.Min(candidate.Geometry.InitialRiskEur, open.ReservedStopRiskEur);
            }
            var gate = AssessEurCandidate(capital, book, held, projected, candidate, extra);
            if (!gate.IsFinanceable) return EurRejectedCapital(gate.Status, book, capital);

            const string next = "GENERAL_NEXT";
            projected.Add(Reserve(candidate, next));
            var quote = candidate.Market.Quote;
            var check = NativePostFillCapitalGuard.Assess(capital.ResearchAdmissionEquityEur, held, projected,
                next, candidate.Signal.Side, quote, candidate.Market.SlippagePerSideQuote,
                candidate.Receipt.NextManagementFundingCeilingEur!.Value, quote.LiquidationSlippagePerSide);
            if (!check.Allowed) return "WAIT_" + check.Reason;
            decimal floor = book.ObservedPeakEur * (1m - OwnerRiskAuthority.MaximumSystemDrawdown);
            return Math.Min(check.ProjectedPostFillLiquidationEquityEur,
                check.PreFillLiquidationEquityEur - gate.ReservedRiskAfterEur) < floor
                ? "WAIT_DRAWDOWN_RISK_BUDGET" : null;
        }

        decimal Value(EurCandidate candidate) => candidate.Receipt.Payoff!.NetLowerEur;
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
                displacement = (competing is null ? 0m : Value(competing)) -
                    (companion is null ? 0m : Value(companion));
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
        if (residual <= 0m)
            return ManageFundedTarget(plan, position, market, price, displacement);

        // Compare the remaining target with immediate liquidation; entry fees
        // and already earned P&L are sunk. No assumed fill or unknown carry.
        decimal? carry = NativePortfolioFunding.OfferDebit(market, side, position.Units, frame.At, FundingScenarioId);
        decimal? remaining = residual * position.Units * q.EurCredit - carry;
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
