using System;
using Mxm.Core;

internal static class ExecutableEconomicsChecks
{
    public static void Run(Action<bool,string> check)
    {
        var opening = new LedgerQuote("FX", 2_000, 100m, 102m, .80m, .90m, .10m, .20m, 15m);
        foreach(var plan in new[] { (Side: 1, Stop: 97m, Target: 108m), (Side: -1, Stop: 105m, Target: 94m) })
        foreach(decimal slip in new[]{.50m, 1m})
        {
            var bracket = NativeExecutableEconomics.Bracket(opening, plan.Side, 1m, plan.Stop, plan.Target, slip, slip);
            decimal target = Settle(opening, plan.Side, plan.Target, slip, slip);
            decimal stop = Settle(opening, plan.Side, plan.Stop, slip, slip);
            check(bracket.RewardEur == target && bracket.RiskEur == -stop,
                "Executable-side estimate reconciles exactly to modeled stop and target fills for both sides");
            check(bracket.RewardEur == (slip==.50m ? 3.60m : 2.80m) &&
                  bracket.RiskEur == (slip==.50m ? 5.80m : 6.70m),
                "Spread is applied once and adverse slippage is explicit and direction-aware");
            decimal delayed = plan.Stop-plan.Side*2m;
            decimal observed = Settle(opening, plan.Side, delayed, slip, slip+.15m);
            check(observed == NativeExecutableEconomics.EstimateNet(opening, ExitQuote(opening, plan.Side, delayed),
                plan.Side, 1m, bracket.Entry, delayed, slip+.15m) && observed < stop,
                "The ledger settles beyond the stop using a strictly later observed price");
        }
    }

    static LedgerQuote ExitQuote(LedgerQuote entry, int side, decimal level)
        => entry with { At=4_000, Bid=side>0?level:level-2m, Ask=side>0?level+2m:level };

    static decimal Settle(LedgerQuote entry, int side, decimal exitSide, decimal entrySlip, decimal exitSlip)
    {
        var ledger = new NativeFundedLedger();
        var exit = ExitQuote(entry, side, exitSide);
        LedgerEvent Fact(string kind, long at, LedgerQuote[] quotes, decimal price=0m, decimal fee=0m)
            => new(kind, at, kind, "position", entry.Symbol, side, 1m, price, fee, 15m, entrySlip,
                at, at-1, 100L, "SYNTHETIC_ARITHMETIC_ONLY", new string('a',64),quotes);
        ledger.Apply(Fact("REQUEST_OPEN", 1_000, Array.Empty<LedgerQuote>()));
        ledger.Apply(Fact("OPEN_FILL", 2_000, new[]{entry}, side>0?entry.Ask+entrySlip:entry.Bid-entrySlip, .20m));
        ledger.Apply(Fact("REQUEST_CLOSE", 3_000, Array.Empty<LedgerQuote>()));
        ledger.Apply(Fact("CLOSE_FILL", 4_000, new[]{exit}, exitSide-side*exitSlip, .20m)
            with { ObservedExitSlippagePerSide=exitSlip });
        var fragment = ledger.ClosedFragments()[0];
        if(Math.Abs(fragment.GrossEur-fragment.SpreadEur!.Value-fragment.SlippageEur!.Value-
            fragment.ConversionEur!.Value-fragment.CommissionsEur-fragment.NetEur)>.000000000001m)
            throw new InvalidOperationException("EXECUTABLE_ARITHMETIC_COST_WATERFALL");
        return fragment.NetEur;
    }
}
