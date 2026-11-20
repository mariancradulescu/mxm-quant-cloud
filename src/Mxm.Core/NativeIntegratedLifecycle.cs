using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeProtectionDistances(decimal Stop, decimal Target, bool Percentage)
{
    public bool Allows(decimal price, decimal stopDistance, decimal targetDistance)
    {
        decimal scale = Percentage ? price / 100m : 1m;
        return Stop >= 0m && Target >= 0m && stopDistance >= Stop * scale && targetDistance >= Target * scale;
    }
}

public sealed record NativeEntryThesis(string Family, decimal ReclaimedBoundary,
    long AdmissionM15CloseAt, long FillM15CloseAt = 0L, long InvalidatingM15CloseAt = 0L,
    decimal? ProbabilityLower = null, decimal? EstimatedEdgeAtAdmissionEur = null,
    decimal? EstimatedEdgeAtFillEur = null, decimal? StressedRiskAtFillEur = null);

public static class NativeIntegratedLifecycle
{
    public const long IntervalMs = 30_000L;
    public const long CalibrationMs = 7 * 86_400_000L;
    public const string Economic = "INTEGRATED_COHERENT_ECONOMIC";
    public const string First = "INTEGRATED_COHERENT_FIRST";
    public const string Random = "INTEGRATED_COHERENT_RANDOM";
    public const string Long = "INTEGRATED_COHERENT_LONG";
    public const string Short = "INTEGRATED_COHERENT_SHORT";
    public const string Cash = "INTEGRATED_COHERENT_CASH";
    public const string EconomicAdverse = Economic + "_ADVERSE";
    public const string FirstAdverse = First + "_ADVERSE";
    public static readonly string[] Policies =
        { Cash, First, Random, Long, Short, Economic, FirstAdverse, EconomicAdverse };

    public static bool IsPolicy(string policy) => Policies.Contains(policy, StringComparer.Ordinal);
    public static bool SelectsEconomically(string policy) => policy is Economic or EconomicAdverse;

    static (long ClosedAt, decimal Trend, decimal LastClose) CompletedM15(Ucp1MarketFrame market)
    {
        var bars = market.M15.Where(x => x.CloseAt < market.Quote.At).TakeLast(3).ToArray();
        return bars.Length == 3 && market.Quote.At - bars[^1].CloseAt <= 900_000L
            && bars.All(b => b.CloseAt - b.OpenAt == 900_000L)
            && bars[0].CloseAt == bars[1].OpenAt && bars[1].CloseAt == bars[2].OpenAt
            ? (bars[^1].CloseAt, bars[^1].Close - bars[0].Close, bars[^1].Close)
            : (0L, 0m, 0m);
    }

    public static NativeEntryThesis? Freeze(NativeIntegratedCandidate signal, Ucp1MarketFrame market,
        bool directionControl)
    {
        var context = CompletedM15(market);
        if (directionControl) return new("", 0m, context.ClosedAt);
        if (context.ClosedAt == 0L) return null;
        var priorHour = market.Integrated!.H1[^1];
        decimal boundary = signal.Family == "FAILED_AUCTION"
            ? signal.Side > 0 ? priorHour.Low : priorHour.High
            : 0m;
        var thesis = new NativeEntryThesis(signal.Family, boundary, context.ClosedAt);
        return AtFill(thesis, signal.Side, market) is null ? null : thesis;
    }

    public static NativeEntryThesis? AtFill(NativeEntryThesis thesis, int side, Ucp1MarketFrame market)
    {
        var context = CompletedM15(market);
        if (thesis.Family.Length > 0 && context.ClosedAt < thesis.AdmissionM15CloseAt)
            return null;
        decimal price = side > 0 ? market.Quote.Bid : market.Quote.Ask;
        if (thesis.Family == "TREND_PULLBACK" && side * context.Trend <= 0m ||
            thesis.Family == "FAILED_AUCTION" && side * (price - thesis.ReclaimedBoundary) <= 0m)
            return null;
        return thesis with { FillM15CloseAt = context.ClosedAt };
    }

    public static NativeEntryThesis Observe(NativeEntryThesis thesis, int side, long filledAt,
        Ucp1MarketFrame market)
    {
        if (thesis.InvalidatingM15CloseAt != 0 || thesis.Family.Length == 0) return thesis;
        var context = CompletedM15(market);
        if (context.ClosedAt <= Math.Max(filledAt, thesis.FillM15CloseAt)) return thesis;
        bool adverse = thesis.Family == "TREND_PULLBACK"
            ? side * context.Trend < 0m
            : side * (context.LastClose - thesis.ReclaimedBoundary) < 0m;
        return adverse ? thesis with { InvalidatingM15CloseAt = context.ClosedAt } : thesis;
    }

    public static bool ProtectionCompatible(int side, decimal stop, decimal target, Ucp1MarketFrame market)
    {
        decimal price = side > 0 ? market.Quote.Bid : market.Quote.Ask;
        decimal stopDistance = side * (price - stop);
        decimal targetDistance = side * (target - price);
        return stopDistance > 0m && targetDistance > 0m &&
            (market.Integrated?.Protection?.Allows(price, stopDistance, targetDistance) ?? true);
    }

    public static NativeIntegratedTerms Revalue(NativeIntegratedTerms terms, int side,
        decimal stop, decimal target, Ucp1MarketFrame market)
    {
        var q = market.Quote;
        decimal slip = terms.ExecutionSlippage;
        decimal execution = side > 0 ? q.Ask + slip : q.Bid - slip;
        decimal curvature = (q.Ask - q.Bid) / 2m + slip;
        decimal fees = 2m * Math.Max(terms.Units * q.ExitFeePerUnit, q.ExitFeeFloor);
        return terms with {
            RiskEur = (side * (execution - stop) + curvature) * terms.Units * q.EurDebit + fees,
            RewardEur = (side * (target - execution) - curvature) * terms.Units * q.EurCredit - fees,
            MarginEur = terms.Units * q.MarginPerUnit
        };
    }

    public static decimal MarginWithFees(NativeIntegratedTerms terms, LedgerQuote quote)
        => terms.MarginEur + 2m * Math.Max(terms.Units * quote.ExitFeePerUnit, quote.ExitFeeFloor);

    public static decimal StressedRisk(NativeIntegratedTerms terms, decimal meanM5Range, LedgerQuote quote)
        => terms.RiskEur + meanM5Range * terms.Units * quote.EurDebit;

    public static decimal EstimatedEdge(decimal p, decimal reward, decimal stressedLoss)
        => p * reward - (1m - p) * stressedLoss;

    public static (bool Stop, bool Target) ObserveBrackets(int side, NativeObservedQuotePath path,
        decimal stop, decimal target)
        => side > 0 ? (path.BidLow <= stop, path.BidHigh >= target)
            : (path.AskHigh >= stop, path.AskLow <= target);
}

public sealed record NativeBarrierCell(string Key, int TargetFirst, int StopFirst, int Unknown, long[] AdmissionDays)
{
    public int Observations => TargetFirst + StopFirst + Unknown;
    public decimal? LowerProbability
    {
        get
        {
            if (Observations < 12 || AdmissionDays.Length < 3) return null;
            const double z = 1.645;
            double n = Observations, rate = TargetFirst / n;
            double square = z * z;
            return (decimal)Math.Max(0, (rate + square / (2 * n) -
                z * Math.Sqrt((rate * (1 - rate) + square / (4 * n)) / n)) / (1 + square / n));
        }
    }
}

public sealed record NativeBarrierProbe(string Symbol, long At, string Cell, NativeIntegratedCandidate Signal,
    NativeIntegratedTerms Terms, NativeEntryThesis Thesis, long FilledAt = 0L);
public sealed record NativeIntegratedCalibrationState(long EndAt, bool Complete, int Cancelled,
    Dictionary<string, long> LastBar, NativeBarrierCell[] Cells, NativeBarrierProbe[] Pending);

internal sealed class NativeIntegratedBarrierCalibration
{
    readonly Dictionary<string, NativeBarrierProbe> pending = new(StringComparer.Ordinal);
    readonly Dictionary<string, long> lastBar = new(StringComparer.Ordinal);
    readonly Dictionary<string, NativeBarrierCell> cells = new(StringComparer.Ordinal);
    long endAt;
    bool complete;
    int cancelled;

    public NativeIntegratedBarrierCalibration(NativeIntegratedCalibrationState? state = null)
    {
        if (state is null) return;
        endAt = state.EndAt;
        complete = state.Complete;
        cancelled = state.Cancelled;
        foreach (var row in state.LastBar) lastBar.Add(row.Key, row.Value);
        foreach (var row in state.Cells) cells.Add(row.Key, row);
        foreach (var row in state.Pending) pending.Add(row.Symbol, row);
    }

    public NativeIntegratedCalibrationState Checkpoint()
        => new(endAt, complete, cancelled, new(lastBar, StringComparer.Ordinal),
            cells.Values.OrderBy(x => x.Key, StringComparer.Ordinal).ToArray(), pending.Values.ToArray());

    public bool Evaluation(long at)
    {
        if (endAt == 0L) endAt = at + NativeIntegratedLifecycle.CalibrationMs;
        if (at < endAt) return false;
        if (!complete)
        {
            foreach (var probe in pending.Values)
                if (probe.FilledAt > 0L) Count(probe, false, false);
                else cancelled++;
            pending.Clear();
            complete = true;
        }
        return true;
    }

    static string Cell(string family, decimal reward, decimal stressed)
    {
        decimal probability = stressed / (reward + stressed);
        return family + (probability < 1m / 3m ? "/LOW_BREAK_EVEN" :
            probability < 2m / 3m ? "/MID_BREAK_EVEN" : "/HIGH_BREAK_EVEN");
    }

    public decimal? Probability(string family, decimal reward, decimal stressed)
        => reward > 0m && complete
            ? cells.GetValueOrDefault(Cell(family, reward, stressed))?.LowerProbability
            : null;

    void Count(NativeBarrierProbe probe, bool target, bool stop)
    {
        if (!cells.TryGetValue(probe.Cell, out var cell))
            cell = new(probe.Cell, 0, 0, 0, Array.Empty<long>());
        long day = probe.At / 86_400_000L;
        cells[probe.Cell] = cell with {
            TargetFirst = cell.TargetFirst + (target && !stop ? 1 : 0),
            StopFirst = cell.StopFirst + (stop && !target ? 1 : 0),
            Unknown = cell.Unknown + (target == stop ? 1 : 0),
            AdmissionDays = cell.AdmissionDays.Contains(day) ? cell.AdmissionDays : cell.AdmissionDays.Append(day).ToArray()
        };
    }

    public void Observe(Ucp1Frame frame, bool adverse)
    {
        long at = frame.At;
        var markets = frame.Markets.ToDictionary(x => x.Symbol, StringComparer.Ordinal);
        foreach (var probe in pending.Values.ToArray())
        {
            markets.TryGetValue(probe.Symbol, out var market);
            var path = market?.Integrated?.Path;
            var signal = probe.Signal;
            if (probe.FilledAt == 0L)
            {
                var terms = market is null ? null :
                    NativeIntegratedLifecycle.Revalue(probe.Terms, signal.Side, signal.Stop, signal.Target, market);
                if (at - probe.At != NativeIntegratedLifecycle.IntervalMs || market is null ||
                    path?.Complete != true || terms is null ||
                    NativeIntegratedLifecycle.MarginWithFees(terms, market.Quote) > 225m ||
                    terms.RewardEur <= 0m || NativeIntegratedLifecycle.StressedRisk(terms, signal.Volatility, market.Quote) > 6m ||
                    NativeIntegratedLifecycle.AtFill(probe.Thesis, signal.Side, market) is null ||
                    !NativeIntegratedLifecycle.ProtectionCompatible(signal.Side, signal.Stop, signal.Target, market))
                {
                    cancelled++;
                    pending.Remove(probe.Symbol);
                }
                else pending[probe.Symbol] = probe with { FilledAt = at };
                continue;
            }
            if (path is not { Complete: true })
            {
                Count(probe, false, false);
                pending.Remove(probe.Symbol);
                continue;
            }
            var (stop, target) = NativeIntegratedLifecycle.ObserveBrackets(signal.Side, path, signal.Stop, signal.Target);
            if (stop || target)
            {
                Count(probe, target, stop);
                pending.Remove(probe.Symbol);
            }
        }
        if (at % 60_000L != NativeIntegratedEconomicPolicy.ClockOffsetMs) return;
        foreach (var market in frame.Markets.OrderBy(x => x.Symbol, StringComparer.Ordinal))
        {
            if (market.Integrated is not { Path.Complete: true } input || market.M5.Length == 0)
                continue;
            var completed = market.M5[^1].CloseAt;
            if (completed >= at || completed <= lastBar.GetValueOrDefault(market.Symbol)) continue;
            lastBar[market.Symbol] = completed;
            if (pending.ContainsKey(market.Symbol)) continue;
            var volume = input.Volumes.FirstOrDefault(x => x.Units == market.Contract.MinimumUnits);
            if (volume is null) continue;
            foreach (var signal in NativeIntegratedEconomicPolicy.Describe(market, at).OrderBy(x => x.Family, StringComparer.Ordinal))
            {
                var terms = NativeIntegratedEconomicPolicy.Terms(signal, market, volume, adverse);
                var thesis = NativeIntegratedLifecycle.Freeze(signal, market, false);
                if (terms is null || thesis is null || terms.RewardEur <= 0m ||
                    NativeIntegratedLifecycle.MarginWithFees(terms, market.Quote) > 225m ||
                    !NativeIntegratedLifecycle.ProtectionCompatible(signal.Side, signal.Stop, signal.Target, market))
                    continue;
                decimal stressed = NativeIntegratedLifecycle.StressedRisk(terms, signal.Volatility, market.Quote);
                if (stressed > 6m) continue;
                pending.Add(market.Symbol, new(market.Symbol, at, Cell(signal.Family, terms.RewardEur, stressed),
                    signal, terms, thesis));
                break;
            }
        }
    }
}
