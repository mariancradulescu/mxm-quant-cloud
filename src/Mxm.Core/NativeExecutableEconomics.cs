namespace Mxm.Core;

public sealed record NativeExecutableBracket(decimal Entry, decimal RiskEur, decimal RewardEur);

// Brackets are expressed on the executable exit side. An actual modeled
// exit still requires a later observed quote, which can exceed the level.
public static class NativeExecutableEconomics
{
    public static decimal EntryPrice(LedgerQuote quote, int side, decimal slippage)
        => side > 0 ? quote.Ask + slippage : quote.Bid - slippage;

    public static decimal ExitPrice(decimal executableSide, int side, decimal slippage)
        => executableSide - side * slippage;

    public static decimal EstimateNet(LedgerQuote entryQuote, LedgerQuote exitQuote,
        int side, decimal units, decimal entry, decimal exitSide, decimal exitSlippage)
    {
        decimal exit = ExitPrice(exitSide, side, exitSlippage);
        decimal movement = side * units * (exit - entry);
        return NativeFundedLedger.ConvertQuote(exitQuote, movement) -
            NativeFundedLedger.Fee(entryQuote,units,side)-NativeFundedLedger.Fee(exitQuote,units,-side);
    }

    public static NativeExecutableBracket Bracket(LedgerQuote quote, int side, decimal units,
        decimal stop, decimal target, decimal entrySlippage, decimal exitSlippage)
    {
        decimal entry = EntryPrice(quote, side, entrySlippage);
        return new(entry, -EstimateNet(quote, quote, side, units, entry, stop, exitSlippage),
            EstimateNet(quote, quote, side, units, entry, target, exitSlippage));
    }
}
