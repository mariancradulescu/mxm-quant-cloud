using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeFundedActionOffer(string Kind, string Key, string Symbol, string Family,
    int Side, long At, decimal ScaleEur, decimal[] Features)
{
    public string Group => Kind + "/" + Family + (Side > 0 ? "/LONG" : "/SHORT");
}

public sealed record NativeFundedActionReceipt(NativeFundedActionOffer Offer,
    NativeCompletePrediction? Prediction, string Decision);

public sealed record NativeFundedActionDistributions(NativeCompleteDistribution? Context,
    NativeCompleteDistribution? Pooled, NativeCompleteDistribution? Placebo);

public sealed record NativeFundedActionModel(long FitEnd, long AvailableAt, bool Adverse,
    Dictionary<string, NativeFundedActionDistributions> Actions)
{
    public void Validate()
    {
        if (FitEnd <= 0 || AvailableAt <= FitEnd || Actions is null ||
            Actions.Values.SelectMany(a => new[] { a.Context, a.Pooled, a.Placebo }).OfType<NativeCompleteDistribution>()
                .Any(d => d.UncertaintyR < 0 || d.Samples.Any(s =>
                    s.DecisionAt <= 0 || s.SettledAt <= s.DecisionAt || s.SettledAt >= FitEnd)))
            throw new ArgumentException("FUNDED_ACTION_MODEL_CHRONOLOGY");
    }

    public NativeCompletePrediction? Predict(string variant, NativeFundedActionOffer action)
    {
        if (action.At <= AvailableAt || !Actions.TryGetValue(action.Group, out var model))
            return null;
        return variant switch
        {
            NativeFundedActionValue.Pooled => model.Pooled?.Predict(new[] { 0m }, action.At, action.ScaleEur),
            NativeFundedActionValue.Placebo => model.Placebo?.Predict(action.Features, action.At, action.ScaleEur),
            _ => model.Context?.Predict(action.Features, action.At, action.ScaleEur)
        };
    }
}

// Only the chronological research runner can supply an override.
internal sealed class NativeFundedActionProbe
{
    internal List<NativeFundedActionOffer> Available { get; } = new();
    internal string? Enter { get; init; }
    internal string? Close { get; init; }
    internal bool Wait { get; init; }
}

public static class NativeFundedActionValue
{
    public const string Context = "VALUE_CONTEXT";
    internal const string First = "VALUE_FIRST";
    internal const string Cash = "VALUE_CASH";
    internal const string Hash = "VALUE_HASH";
    internal const string EntryOnly = "VALUE_ENTRY";
    internal const string Pooled = "VALUE_POOLED";
    internal const string Placebo = "VALUE_PLACEBO";
    internal const string WithoutExhaustion = "VALUE_NO_EXHAUSTION";
    internal const string Enter = "ENTER";
    internal const string Close = "CLOSE";
    internal static readonly string[] Variants = { Cash, First, Hash, Pooled, Placebo, EntryOnly, Context, WithoutExhaustion };
    internal static bool IsVariant(string variant) => Variants.Contains(variant, StringComparer.Ordinal);
    internal static bool Forecasts(string variant) => variant is Context or EntryOnly or Pooled or Placebo or WithoutExhaustion;
    internal static bool ValuesHolding(string variant) => Forecasts(variant) && variant != EntryOnly;

    static decimal Move(NativeBarWindow window)
        => (window.Bars[^1].Close - window.Bars[0].Open) /
            Math.Max(window.Bars.Max(b => b.High) - window.Bars.Min(b => b.Low), .000000001m);

    internal static decimal[] Features(Ucp1MarketFrame market, Ucp1Frame frame, int side,
        LedgerSummary book, decimal reserved, decimal actionRisk, decimal actionMargin,
        decimal[] actionState)
    {
        var bars = market.ClosedBars!;
        var minute = bars.For(NativeBarTimeframe.M1).Bars;
        decimal activityPast = minute.Take(minute.Length - 5).Average(b => (decimal)b.TickVolume);
        decimal activityRecent = minute.TakeLast(5).Average(b => (decimal)b.TickVolume);
        var peers = frame.Markets.Where(m => m.Symbol != market.Symbol)
            .Select(m => m.ClosedBars is { } observed && observed.DecisionAt == frame.At
                ? observed.Windows.FirstOrDefault(w => w.Timeframe == NativeBarTimeframe.H1 && w.Ready) : null)
            .OfType<NativeBarWindow>().ToArray();
        decimal equity = book.LiquidationEquityEur!.Value;
        decimal session = (frame.At % NativeCompletePolicy.Day) / (decimal)NativeCompletePolicy.Day;
        var context = new[]
        {
            side * Move(bars.For(NativeBarTimeframe.M5)),
            side * Move(bars.For(NativeBarTimeframe.M15)),
            side * Move(bars.For(NativeBarTimeframe.M30)),
            side * Move(bars.For(NativeBarTimeframe.H1)),
            (activityRecent - activityPast) / Math.Max(1m, activityPast),
            peers.Length == 0 ? 0m : side * peers.Average(Move),
            peers.Length == 0 ? 0m : 1m,
            (decimal)Math.Sin((double)(session * 2m) * Math.PI),
            (decimal)Math.Cos((double)(session * 2m) * Math.PI),
            book.UsedMarginEur!.Value / equity, reserved / (.06m * equity),
            actionRisk / (.02m * equity), actionMargin / equity,
            (book.OpenPositions + book.PendingIntents) / 4m
        };
        return context.Concat(actionState).Select(x => Math.Max(-4m, Math.Min(4m, x))).ToArray();
    }
}
