namespace Mxm.Core;
// Authority provenance only. Latest OWNER mandate withdraws fixed 1%/2% and
// historical EUR2/80/120 constraints. No admission routine may infer such caps.
public static class OwnerRiskAuthority
{
    public const string Authority="OWNER_EXPLICIT_ADAPTIVE_PORTFOLIO_MANDATE_20261103";
    public const decimal InitialCapitalEur=300m;
    public const decimal MaximumSystemDrawdown=.30m;
    public const int MinimumSystemRoundTripsPerEligibleWeek=21;
}
