namespace Mxm.Core;

// Native, instrument-agnostic EUR economic math. This is a BOUNDED quote
// scenario, NOT a simulated broker fill or evidence of economic edge.
public enum PositionDirection { Buy, Sell }

public sealed record ExecutableQuoteEvidence(
    string Symbol, PositionDirection Direction,
    DateTime EntryUtc, DateTime ExitUtc,
    decimal? EntryBid, decimal? EntryAsk, decimal? ExitBid, decimal? ExitAsk,
    decimal? Units, decimal? BrokerMinUnits, decimal? BrokerStepUnits,
    decimal? QuoteToEurAtExit, decimal? EntryCommissionEur,
    decimal? ExitCommissionEur, decimal? SlippageUpperEur,
    decimal? FinancingUpperEur, decimal? ConversionUpperEur,
    decimal? RequiredMarginEur, decimal? FreeMarginEur,
    string? AuthenticatedSourceSha256, bool AccountIdentityBound,
    bool BothQuoteEventsVerified, bool CostsAndBrokerContractBound,
    bool Original300EurNoDepositsReconciled);

public sealed record ExecutableNetObservation(
    bool FullyPriced, bool FundableWithAvailableMargin, decimal? QuoteGrossEur,
    decimal? AdverseNetLowerEur, decimal? TotalCostUpperEur,
    decimal? MarginAfterEur, string Verdict, bool EconomicQualified);

public static class ExecutableNet
{
    public static ExecutableNetObservation Evaluate(ExecutableQuoteEvidence e)
    {
        ArgumentNullException.ThrowIfNull(e);
        ExecutableNetObservation Refuse(string reason) =>
            new(false,false,null,null,null,null,reason,false);
        if(e.AuthenticatedSourceSha256 is not {Length:64} digest ||
            !digest.All(Uri.IsHexDigit) || !e.AccountIdentityBound ||
            !e.BothQuoteEventsVerified)
            return Refuse("AUTHENTIC_ENTRY_EXIT_QUOTES_NOT_BOUND");
        if(!e.CostsAndBrokerContractBound ||
           !e.Original300EurNoDepositsReconciled)
            return Refuse("BROKER_COST_OR_FUNDED_CAPITAL_NOT_RECONCILED");
        if(e.EntryUtc.Kind!=DateTimeKind.Utc ||
           e.ExitUtc.Kind!=DateTimeKind.Utc ||
           e.ExitUtc<=e.EntryUtc)
            return Refuse("CAUSAL_ENTRY_EXIT_TIMES_INVALID");
        if(e.EntryBid is not decimal eb || e.EntryAsk is not decimal ea ||
           e.ExitBid is not decimal xb || e.ExitAsk is not decimal xa ||
           e.Units is not decimal units || e.BrokerMinUnits is not decimal min ||
           e.BrokerStepUnits is not decimal step ||
           e.QuoteToEurAtExit is not decimal conversion ||
           e.EntryCommissionEur is not decimal ec ||
           e.ExitCommissionEur is not decimal xc ||
           e.SlippageUpperEur is not decimal slip ||
           e.FinancingUpperEur is not decimal financing ||
           e.ConversionUpperEur is not decimal fx ||
           e.RequiredMarginEur is not decimal margin ||
           e.FreeMarginEur is not decimal free)
            return Refuse("EXECUTABLE_QUOTE_MARGIN_OR_NET_COST_MISSING");
        if(eb<=0m || ea<eb || xb<=0m || xa<xb ||
           units<=0m || min<=0m || step<=0m || conversion<=0m ||
           ec<0m || xc<0m || slip<0m || financing<0m ||
           fx<0m || margin<=0m || free<0m)
            throw new ArgumentException("INVALID_BROKER_QUOTE_OR_COST_BOUND");
        // Broker volume is discrete; never round it to a convenient size.
        if(units<min || (units-min)%step!=0m)
            return Refuse("BROKER_MINIMUM_OR_STEP_UNSATISFIED");
        var gross=(e.Direction==PositionDirection.Buy?xb-ea:eb-xa)*units*conversion;
        var allCosts=ec+xc+slip+financing+fx;
        var conservativeNet=gross-allCosts;
        // Capital feasibility is only a necessary check; free-margin
        // margin stress, concurrent risk and global DD require separate proof.
        var fundable=margin<=free;
        return new(true,fundable,gross,conservativeNet,allCosts,
            free-margin,
            fundable ? "PRICED_QUOTE_SCENARIO_NO_BROKER_FILL_OR_NET_QUALIFICATION" :
                       "CURRENT_FREE_MARGIN_INSUFFICIENT",
            false);
    }
}
