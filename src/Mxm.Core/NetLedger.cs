namespace Mxm.Core;

// All inputs are explicitly EUR and require source evidence. No implicit zero
// costs, invented conversions, fixed margin or favorable-excursion profits.
public sealed record NetSettlement(string EventId, decimal GrossEur, decimal CommissionEur,
    decimal FinancingEur, decimal ConversionCostEur, string EvidenceHash);
public sealed class NetLedger
{
    private readonly Dictionary<string, NetSettlement> events = new();
    public decimal Balance { get; private set; } = 200m;
    public void Apply(NetSettlement e)
    {
        if (string.IsNullOrWhiteSpace(e.EventId) || e.EvidenceHash.Length != 64 ||
            !e.EvidenceHash.All(Uri.IsHexDigit) || e.CommissionEur < 0 || e.ConversionCostEur < 0)
            throw new ArgumentException("Unproven monetary settlement");
        if (events.TryGetValue(e.EventId, out var previous))
        {
            if (previous != e) throw new InvalidOperationException("Conflicting economic event");
            return;
        }
        Balance += e.GrossEur - e.CommissionEur + e.FinancingEur - e.ConversionCostEur;
        events.Add(e.EventId, e);
    }
}
