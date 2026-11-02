namespace Mxm.Core;

/// <summary>
/// A narrow native funded-entry feasibility screen. Its outputs are necessary
/// conditions ONLY, never a brokerage execution guarantee or NET backtest.
/// No cost can silently default to zero and none may be backfilled from prices.
/// </summary>
public sealed record FundedBrokerQuote(
    string Symbol, decimal? Bid, decimal? Ask,
    decimal? UnitsPerMinimumTrade, decimal? QuoteCurrencyToEur,
    decimal? EntryCommissionEur, decimal? ExitCommissionEur,
    decimal? SlippageCostEur, decimal? FinancingCostEur,
    decimal? MarginRequirementEur, decimal? ConversionCostEur,
    bool SourceAuthenticated, bool BrokerContractComplete);

public sealed record FundedEntryScreen(
    bool Complete, bool CanFundFromInitialCapital,
    decimal? MinimumNonnegativeProfitMoveInQuote,
    decimal? MinimumAllInCostEur,
    decimal? MaximumEquityAtRiskEur,
    string Status);

public static class FundedBrokerCostScreen
{
    public const decimal InitialEur=200m;
    public const decimal MaxDrawdownEur=60m;
    public static FundedEntryScreen Assess(FundedBrokerQuote q)
    {
        ArgumentNullException.ThrowIfNull(q);
        if(!q.SourceAuthenticated || !q.BrokerContractComplete)
            return new(false,false,null,null,null,"AUTHENTIC_BROKER_CONTRACT_NOT_COMPLETE");
        if(q.Bid is not decimal bid || q.Ask is not decimal ask ||
            q.UnitsPerMinimumTrade is not decimal units ||
            q.QuoteCurrencyToEur is not decimal conversion ||
            q.EntryCommissionEur is not decimal entry ||
            q.ExitCommissionEur is not decimal exit ||
            q.SlippageCostEur is not decimal slip ||
            q.FinancingCostEur is not decimal funding ||
            q.MarginRequirementEur is not decimal margin ||
            q.ConversionCostEur is not decimal fx)
            return new(false,false,null,null,null,"OBSERVED_BID_ASK_MARGIN_OR_COST_MISSING");
        if(bid<=0m || ask<bid || units<=0m || conversion<=0m ||
            entry<0m || exit<0m || slip<0m || funding<0m ||
            margin<0m || fx<0m)
            throw new ArgumentException("BROKER_QUOTE_OR_COST_INVALID");
        // Spread is paid through ask-side buy and bid-side sale; a round trip
        // starting here needs this much strictly observed incremental move.
        decimal spread=(ask-bid)*units*conversion;
        decimal cost=spread+entry+exit+slip+funding+fx;
        decimal move=(ask-bid)+((entry+exit+slip+funding+fx)/(units*conversion));
        bool affordable=margin<=InitialEur && cost<=MaxDrawdownEur;
        return new(true,affordable,move,cost,MaxDrawdownEur,
            affordable ? "COST_FLOOR_ONLY_NO_STRATEGY_OR_NET_CLAIM":
                         "INITIAL_200_EUR_OR_MAX_DRAWDOWN_INCOMPATIBLE");
    }
}
