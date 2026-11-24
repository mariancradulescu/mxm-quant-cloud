using Mxm.Core;

internal static class Cpe1OwnedLedgerChecks
{
    public static void Run(Action<bool, string> check)
    {
        var engine = new NativeUnifiedPortfolioEngine("CPE1_ECONOMIC");
        foreach (var frame in Cpe1RecoveryParityChecks.FinancingFrames(false))
            engine.Advance(frame);

        var owned = new NativeFundedSession("CPE1_TECHNICAL");
        var original = new NativeFundedSession("CPE1_TECHNICAL");
        foreach (var fact in engine.OriginalModelEvents)
        {
            if (fact.Kind == "FINANCING")
            {
                VerifyRejection(owned, fact with { SignedFinancingEur = decimal.MaxValue }, check);
            }
            if (fact.Kind == "MARK" && fact.EventId.StartsWith("UCP1/", StringComparison.Ordinal) &&
                owned.Ledger.Summary().OpenPositions > 0 && fact.Quotes.Length > 0)
            {
                var invalidQuote = fact.Quotes[0] with {
                    Bid = decimal.MaxValue, Ask = decimal.MaxValue, EurCredit = 2m, EurDebit = 2m
                };
                VerifyRejection(owned, fact with { Quotes = new[] { invalidQuote } }, check);
            }

            var expected = original.ApplyResearchFacts(new[] { fact });
            owned.ApplyOwnedResearchFact(fact);
            check(owned.Ledger.Summary() == expected && owned.Checkpoint() == original.Checkpoint(),
                "CPE1 atomic fact preserves settlement, timestamp, identity and full checkpoint");
            owned.ApplyOwnedResearchFact(fact);
            check(owned.Checkpoint() == original.Checkpoint(), "CPE1 accepted fact is idempotent");
        }
    }

    static void VerifyRejection(NativeFundedSession owned, LedgerEvent invalid, Action<bool, string> check)
    {
        string before = owned.Checkpoint();
        bool failed = false;
        try { owned.ApplyOwnedResearchFact(invalid); }
        catch (OverflowException) { failed = true; }
        check(failed && owned.Checkpoint() == before,
            "CPE1 rejected provisional observation or financing leaves the entire ledger retryable");
    }
}
