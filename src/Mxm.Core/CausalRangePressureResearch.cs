namespace Mxm.Core;

// Distinct, unpromoted H1 causal research hypothesis: adaptively predict
// next-bar directional probability from *completed* candle geometry, one
// bar behind all target outcomes. Not an order signal, trading system,
// or claim of NET advantage. Gaps discard warmup and pending predictions.
public sealed record CompletedH1Candle(string Symbol, DateTime OpenUtc,
    DateTime EvidenceAvailableUtc, decimal Open, decimal High, decimal Low,
    decimal Close, long TickVolume, string SourceEvidenceSha256);

public sealed record ResearchForecast(string Symbol, DateTime AsOfUtc,
    DateTime TargetBarEndsUtc, decimal ProbabilityUp,
    int AdaptationUpdates, string Status);

public sealed class CausalRangePressureResearch
{
    private CompletedH1Candle? previous;
    private decimal[]? previousFeatures;
    private decimal previousProbability;
    private string? symbol;
    private readonly decimal[] weights = new decimal[4];
    private int contiguousBars;
    private int updates;
    public const int WarmupBars = 12;
    public const string ResearchOnly = "UNQUALIFIED_OBSERVATION_NO_TRADING";

    public void Reset()
    {
        previous = null;
        previousFeatures = null;
        symbol = null;
        previousProbability = 0m;
        Array.Clear(weights, 0, weights.Length);
        contiguousBars = 0;
        updates = 0;
    }

    private static decimal Clamp(decimal v, decimal lo, decimal hi) =>
        Math.Min(hi, Math.Max(lo, v));

    public ResearchForecast? Observe(CompletedH1Candle bar)
    {
        if (string.IsNullOrWhiteSpace(bar.Symbol) || bar.Symbol.Length > 40 ||
            bar.OpenUtc.Kind != DateTimeKind.Utc ||
            bar.EvidenceAvailableUtc.Kind != DateTimeKind.Utc ||
            bar.EvidenceAvailableUtc != bar.OpenUtc.AddHours(1) ||
            bar.Low <= 0m || bar.Low > bar.Open || bar.Open > bar.High ||
            bar.Low > bar.Close || bar.Close > bar.High ||
            bar.TickVolume < 0 || bar.SourceEvidenceSha256 is not {Length: 64} hash ||
            !hash.All(Uri.IsHexDigit))
            throw new ArgumentException("INCOMPLETE_UNVERIFIED_H1_BAR");
        if (symbol is not null && bar.Symbol != symbol)
            throw new ArgumentException("SYMBOL_STATE_MUST_NOT_BE_SHARED");
        if (previous is not null && bar.OpenUtc <= previous.OpenUtc)
            throw new ArgumentException("NONMONOTONIC_CAUSAL_INPUT");
        if (previous is not null && bar.OpenUtc != previous.OpenUtc.AddHours(1))
            Reset(); // Weekend/data outage: no continuity inference or forced trade.
        symbol = bar.Symbol;

        if (previous is not null)
        {
            // Learn only after the previous prediction's TARGET bar has closed.
            if (previousFeatures is not null)
            {
                decimal realized = bar.Close > previous.Close ? 1m :
                    bar.Close < previous.Close ? 0m : .5m;
                decimal error = realized - previousProbability;
                for (int i = 0; i < weights.Length; i++)
                    weights[i] = Clamp(weights[i] + .05m * error *
                        previousFeatures[i], -3m, 3m);
                updates++;
            }
            decimal range = Math.Max(1m, bar.High - bar.Low);
            decimal priorRange = Math.Max(1m, previous.High - previous.Low);
            decimal totalVol = Math.Max(1m, bar.TickVolume + (decimal)previous.TickVolume);
            var features = new[] {
                Clamp((bar.Close-bar.Open)/range,-1m,1m),
                Clamp((2m*bar.Close-bar.High-bar.Low)/range,-1m,1m),
                Clamp((bar.Close-previous.Close)/priorRange,-1m,1m),
                Clamp(((decimal)bar.TickVolume-previous.TickVolume)/totalVol,-1m,1m)
            };
            decimal score = 0m;
            for (int i=0; i<weights.Length; i++) score += weights[i]*features[i];
            previousProbability = Clamp(.5m + .10m*score, .05m, .95m);
            previousFeatures = features;
        }

        previous = bar;
        contiguousBars++;
        if (contiguousBars < WarmupBars || previousFeatures is null)
            return null;
        return new ResearchForecast(bar.Symbol,bar.EvidenceAvailableUtc,
            bar.EvidenceAvailableUtc.AddHours(1),previousProbability,updates,ResearchOnly);
    }
}
