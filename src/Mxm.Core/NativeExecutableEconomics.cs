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

    // Spotware StopTriggerMethod.Trade uses Bid for a long stop and Ask for a short stop.
    // A trigger is a price observation. The execution price is independent.
    public static bool TradeStopReached(int side,decimal executableSide,decimal stop)
        => side*(executableSide-stop)<=0m;

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

    internal static (decimal Gross,decimal Spread,decimal Slippage,decimal Conversion,decimal Converted) ClosedPriceMoney(
        LedgerQuote entry,LedgerQuote exit,int side,decimal units,decimal entryPrice,decimal exitPrice,
        decimal entrySlippage,decimal exitSlippage)
    {
        decimal converted=NativeFundedLedger.ConvertQuote(exit,side*units*(exitPrice-entryPrice));
        decimal reference=(exit.EurCredit+exit.EurDebit)/2;
        decimal gross=side*units*((exit.Bid+exit.Ask)/2-(entry.Bid+entry.Ask)/2)*reference;
        decimal spread=units*((entry.Ask-entry.Bid)+(exit.Ask-exit.Bid))/2*reference;
        decimal slip=units*(entrySlippage+exitSlippage)*reference;
        decimal conversion=gross-spread-slip-converted;
        if(conversion<-.000000001m)throw new InvalidOperationException("NATIVE_LEDGER_CONVERSION_COST");
        return (gross,spread,slip,Math.Max(0m,conversion),converted);
    }
}
