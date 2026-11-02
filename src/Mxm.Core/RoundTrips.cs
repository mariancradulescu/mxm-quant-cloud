namespace Mxm.Core;

public sealed record ClosedDeal(long DealId, long PositionId, DateTime ClosedUtc, decimal ClosedVolume);
public static class RoundTrips
{
    // Requires independently proven complete opening/closing history. Partial closes
    // are not separate round trips. Week eligibility is frozen outside this counter.
    public static int Count(DateTime startUtc, DateTime endUtc, IEnumerable<ClosedDeal> deals,
        IReadOnlyDictionary<long, decimal> openedVolumes, ISet<long> openPositions)
    {
        var rows = deals.ToArray();
        if (startUtc.Kind != DateTimeKind.Utc || endUtc.Kind != DateTimeKind.Utc || endUtc <= startUtc)
            throw new ArgumentException("UTC half-open interval required");
        if (rows.Any(x => x.ClosedUtc.Kind != DateTimeKind.Utc || x.ClosedVolume <= 0) ||
            rows.GroupBy(x => x.DealId).Any(g => g.Distinct().Count() != 1))
            throw new ArgumentException("Invalid or conflicting deal evidence");
        return rows.Distinct().GroupBy(x => x.PositionId).Count(g =>
            !openPositions.Contains(g.Key) && openedVolumes.TryGetValue(g.Key, out var opened) &&
            opened > 0 && g.Sum(x => x.ClosedVolume) == opened &&
            g.Max(x => x.ClosedUtc) >= startUtc && g.Max(x => x.ClosedUtc) < endUtc);
    }
}
