using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeObservedVolume(decimal Units, decimal BuyMargin, decimal SellMargin);

// Executable-side extrema are observations within the previous clock interval.
// They disclose barrier crossings, never a fill price or the order of two crossings.
public sealed record NativeObservedQuotePath(decimal BidLow, decimal BidHigh,
    decimal AskLow, decimal AskHigh, bool Complete);

public sealed record NativeIntegratedMarket(
    NativeClosedMarketBar[] H1, NativeObservedVolume[] Volumes, bool ShortAllowed,
    decimal TickSize, NativeObservedQuotePath? Path)
{
    public NativeProtectionDistances? Protection { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeQuoteResidence? Residence { get; init; }
}

public sealed record NativeIntegratedCandidate(string Family, int Side, decimal Stop,
    decimal Target, decimal Volatility, long DecisionBar);

public sealed record NativeIntegratedTerms(decimal Units, decimal RiskEur,
    decimal RewardEur, decimal MarginEur, decimal ExecutionSlippage);

public sealed record NativeIntegratedPlan(decimal Stop, decimal Target,
    decimal InitialRiskEur, decimal InitialRewardEur, decimal ProtectedLevel = 0m,
    bool Reduced = false, string FirstBarrier = "")
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeEntryThesis? Thesis { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeCompleteEntry? CompletePolicy { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public decimal? EntrySlippage { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingDefault)]
    public decimal GapReservePerUnitQuote { get; init; }
}

public sealed record NativeIntegratedEpisode(decimal InitialPlannedRewardEur,
    decimal PlannedRewardToRisk, decimal? RealizedReturnToPlannedRisk, string FirstObservedBarrier,
    bool Gap, bool PartialReduction, decimal CaptureOfSampledMfe,
    decimal CommissionsEur, decimal SpreadEur, decimal SlippageEur, decimal ConversionEur)
{
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeEntryThesis? Thesis { get; init; }
    [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public NativeCompleteEntry? CompletePolicy { get; init; }
}

public static class NativeIntegratedEconomicPolicy
{
    public const long ClockOffsetMs = 15_000;
    public static readonly string[] Policies = {
        "INTEGRATED_CASH", "INTEGRATED_FIRST_MIN", "INTEGRATED_LONG_MIN",
        "INTEGRATED_SHORT_MIN", "INTEGRATED_FIRST_BUDGET", "INTEGRATED_STRUCTURE_MIN",
        "INTEGRATED_STRUCTURE_BUDGET", "INTEGRATED_RANDOM_MIN"
    };
    public static bool IsPolicy(string policy)
        => Policies.Contains(policy, StringComparer.Ordinal) || NativeIntegratedLifecycle.IsPolicy(policy) || NativeCompletePolicy.IsPolicy(policy) ||
           NativeStructuralOpportunity.IsPolicy(policy) ||
           (policy.EndsWith("_ADVERSE", StringComparison.Ordinal) &&
            policy[..^8] is "INTEGRATED_FIRST_MIN" or "INTEGRATED_STRUCTURE_BUDGET");

    public static bool CanUseContract(NativeObservedContractTerms contract)
        // One authentic model quote has a single fee schedule in the ledger.
        // Price-proportional fees require distinct execution-side fee terms.
        => contract.QuoteAsset == "USD" &&
           (contract.CommissionType is 2 or 4 || contract.PreciseRateWire == 0m);

    public static decimal Slippage(decimal bid, decimal ask, decimal tick, bool adverse)
        => Math.Max(tick, (ask - bid) * (adverse ? 1m : .25m));

    public static LedgerQuote BuildQuote(NativeObservedContractTerms contract, long at,
        decimal bid, decimal ask, decimal fxBid, decimal fxAsk, NativeObservedVolume[] volumes,
        decimal tick)
    {
        if (!CanUseContract(contract) || fxBid <= 0m || fxAsk < fxBid || tick <= 0m)
            throw new ArgumentException("INTEGRATED_EXECUTION_COST_OR_FX_UNAVAILABLE");
        decimal minimum = contract.MinimumUnits;
        var verified = volumes.Where(v => v.Units >= minimum && v.BuyMargin > 0m).ToArray();
        if (verified.Length == 0)
            throw new ArgumentException("INTEGRATED_MARGIN_GRID_UNAVAILABLE");
        decimal envelope = verified.Max(v => Math.Max(v.BuyMargin, v.SellMargin) / v.Units);
        var context = new NativeMarketCostContext(at, bid, ask, 1m / fxAsk, 1m / fxBid,
            1m / fxBid, null, envelope * minimum, minimum, Slippage(bid, ask, tick, false));
        return (contract.OriginalBrokerAuthenticated
            ? NativeBrokerContractCosts.Quote(contract, context)
            : NativeBrokerContractCosts.QuoteCurrentAlgo(contract, context)).Quote;
    }

    static bool Complete(NativeClosedMarketBar[] bars, long at, int length, long period)
    {
        if (bars.Length < length || bars[^1].CloseAt >= at || at - bars[^1].CloseAt > period)
            return false;
        for (int i = bars.Length - length; i < bars.Length; i++)
        {
            var bar = bars[i];
            if (bar.CloseAt - bar.OpenAt != period || bar.Low <= 0m ||
                bar.Low > Math.Min(bar.Open, bar.Close) || bar.High < Math.Max(bar.Open, bar.Close) ||
                (i > bars.Length - length && bars[i - 1].CloseAt != bar.OpenAt))
                return false;
        }
        return true;
    }

    public static NativeIntegratedCandidate[] Describe(Ucp1MarketFrame market, long at)
    {
        if (market.Integrated is not { } input || !Complete(market.M5, at, 5, 300_000) ||
            !Complete(market.M15, at, 3, 900_000) || !Complete(input.H1, at, 2, 3_600_000))
            return Array.Empty<NativeIntegratedCandidate>();
        var trendWarmup = Complete(input.H1, at, 6, 3_600_000);
        var h = input.H1.TakeLast(trendWarmup ? 6 : 2).ToArray();
        var m = market.M5.TakeLast(5).ToArray();
        var last = m[^1];
        decimal volatility = Math.Max(input.TickSize, m.Average(b => b.High - b.Low));
        decimal referenceHigh = h.Max(b => b.High);
        decimal referenceLow = h.Min(b => b.Low);
        if (referenceHigh <= referenceLow) return Array.Empty<NativeIntegratedCandidate>();
        decimal signedTravel = h[^1].Close - h[0].Close;
        decimal efficiency = Math.Abs(signedTravel) / (referenceHigh - referenceLow);
        int trend = Math.Sign(signedTravel);
        var choices = new List<NativeIntegratedCandidate>();
        void Add(string family, int side, decimal stop, decimal target)
        {
            if (side * (last.Close - stop) > 0m && side * (target - last.Close) > 0m)
                choices.Add(new(family, side, stop, target, volatility, last.CloseAt));
        }
        if (trendWarmup && efficiency >= .25m &&
            trend * (market.M15[^1].Close - market.M15[^3].Close) > 0m)
        {
            if (trend == 1 && m[^2].Close < m[^3].Close && last.Close > m[^2].High)
                Add("TREND_PULLBACK", 1, m.TakeLast(3).Min(x => x.Low) - input.TickSize, referenceHigh);
            if (trend == -1 && m[^2].Close > m[^3].Close && last.Close < m[^2].Low)
                Add("TREND_PULLBACK", -1, m.TakeLast(3).Max(x => x.High) + input.TickSize, referenceLow);
        }
        var priorHour = h[^1];
        if (efficiency < .60m && last.Close > priorHour.Low && last.Close < priorHour.High)
        {
            decimal midpoint = (priorHour.High + priorHour.Low) / 2m;
            if (last.Low < priorHour.Low && m[^2].Close > priorHour.Low)
                Add("FAILED_AUCTION", 1, last.Low - input.TickSize, midpoint);
            if (last.High > priorHour.High && m[^2].Close < priorHour.High)
                Add("FAILED_AUCTION", -1, last.High + input.TickSize, midpoint);
        }
        return choices.ToArray();
    }

    public static NativeIntegratedTerms? Terms(NativeIntegratedCandidate signal,
        Ucp1MarketFrame market, NativeObservedVolume volume, bool adverse)
    {
        var q = market.Quote;
        var input = market.Integrated;
        var c = market.Contract;
        if (input is null || !CanUseContract(c) || (signal.Side == -1 && !input.ShortAllowed) ||
            volume.Units < c.MinimumUnits || volume.Units > c.MaximumUnits ||
            (volume.Units - c.MinimumUnits) % c.VolumeStepUnits != 0m ||
            (signal.Side == 1 ? volume.BuyMargin : volume.SellMargin) <= 0m)
            return null;
        decimal slip = Slippage(q.Bid, q.Ask, input.TickSize, adverse);
        decimal reference = (q.Bid + q.Ask) / 2m;
        decimal execution = signal.Side > 0 ? q.Ask + slip : q.Bid - slip;
        if (signal.Side * (reference - signal.Stop) <= 0m ||
            signal.Side * (signal.Target - execution) <= 0m)
            return null;
        decimal fees = 2m * Math.Max(volume.Units * q.ExitFeePerUnit, q.ExitFeeFloor);
        decimal risk = (signal.Side * (execution - signal.Stop) + (q.Ask - q.Bid) / 2m + slip)
                       * volume.Units * q.EurDebit + fees;
        decimal reward = (signal.Side * (signal.Target - execution) - (q.Ask - q.Bid) / 2m - slip)
                         * volume.Units * q.EurCredit - fees;
        return new(volume.Units, risk, reward, volume.Units * q.MarginPerUnit, slip);
    }
}
