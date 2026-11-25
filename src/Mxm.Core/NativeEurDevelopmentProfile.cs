using System;

namespace Mxm.Core;

// Registered choices for conditional development using the existing EUR book.
// Immutable legacy runs retain their original default settings.
public sealed record NativeEurDevelopmentProfile(bool UseAvailableContext = false,
    decimal DistributionTargetRanges = 2m, int MinimumEpisodes = 20, int MinimumDays = 3,
    decimal DayPenalty = 1.645m, decimal StopReserveMultiplier = 1m)
{
    internal string GeometryIdentity => FormattableString.Invariant(
        $"{UseAvailableContext}/{DistributionTargetRanges:G29}/{StopReserveMultiplier:G29}");

    internal void Verify()
    {
        if (DistributionTargetRanges <= 0m || (!UseAvailableContext && DistributionTargetRanges != 2m) ||
            MinimumDays < 2 || MinimumEpisodes < MinimumDays ||
            DayPenalty < 0m || StopReserveMultiplier < 1m)
            throw new ArgumentException("EUR_REGISTERED_DEVELOPMENT_PROFILE");
    }
}
