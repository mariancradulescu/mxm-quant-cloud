using Mxm.Core;

internal static class BrokerFlatReadbackChecks
{
    public static void Run(Action<bool,string> check)
    {
        const string account="CLOUD_RESTART_TEST_ACCOUNT";
        var deposits=new[]{new BrokerNativeCashflow("deposit-1",1000,"DEPOSIT",200m,200m,200m)};
        var empty=new BrokerFlatReadback(account,6000,true,200m,200m,0m,0m,0,0,
            deposits,Array.Empty<BrokerNativeClosedTrade>());
        var first=new NativeFundedSession(account);
        check(!first.ReconcileBrokerFlat(empty with {SnapshotStable=false}).Adopted,
            "first broker poll cannot substitute for a stable native account readback");
        var accepted=first.ReconcileBrokerFlat(empty);
        check(accepted.Adopted&&accepted.BrokerCashIdentityMatched&&accepted.DecisionResearchMayResume&&
            !accepted.HistoricalEquityPeakCertified&&!accepted.CompleteBrokerHistoryCertified&&
            !accepted.OrdersEnabled&&first.Ledger.Summary().CashEur==200m,
            "lost Cloud checkpoint can recover flat original capital from a broker deposit without enabling orders");
        string stableCheckpoint=first.Checkpoint();
        check(first.ReconcileBrokerFlat(empty).Adopted&&first.Checkpoint()==stableCheckpoint,
            "flat native readback is idempotent on repeated observations");
        check(!first.ReconcileBrokerFlat(empty with {Cashflows=Array.Empty<BrokerNativeCashflow>()}).Adopted,
            "empty transaction collection is not positive original funding proof");
        check(!first.ReconcileBrokerFlat(empty with {Cashflows=deposits.Append(
            new BrokerNativeCashflow("withdraw",3000,"WITHDRAWAL",10m,190m,null)).ToArray()}).Adopted,
            "external cashflows never silently change the OWNER single-capital book");
        check(!first.ReconcileBrokerFlat(empty with {OpenPositions=1}).Adopted,
            "an open broker position requires nonflat execution reconstruction");
        check(!first.ReconcileBrokerFlat(empty with {PendingOrders=1}).Adopted,
            "a pending order cannot be assumed absent on restart");
        var unresolved=new NativeFundedSession(account,intents:new[]{
            new LocalIntentIdentity("client-1","","","EURUSD",1,1000m,false,1500,"ledger-id")});
        check(!unresolved.ReconcileBrokerFlat(empty).Adopted,
            "an unresolved historical order intent is never cleared by an empty current inventory");

        var gain=new BrokerNativeClosedTrade("close-1","position-A","EURUSD",2000,3000,
            3.5m,.5m,0m,3m,203m);
        var loss=new BrokerNativeClosedTrade("close-2","position-B","AUDUSD",3500,5000,
            -1m,0m,0m,-1m,202m);
        var both=empty with {BalanceEur=202m,EquityEur=202m,Closed=new[]{gain,loss}};
        // New process, no local journal: broker-native history reconstructs
        // cumulative EUR capital as a single account, without independent wallets.
        var recovered=new NativeFundedSession(account);
        var result=recovered.ReconcileBrokerFlat(both);
        check(result.Adopted&&result.ReconstructedCashEur==202m&&
            recovered.Ledger.Summary().CashEur==202m&&
            recovered.Ledger.Summary().CompleteRoundTrips==0&&
            recovered.Ledger.ClosedFragments().Length==2,
            "two closed broker outcomes rebuild one continuous cash book without inventing certified round trips");
        check(result.ObservedPeakLowerBoundEur==202m&&!result.HistoricalEquityPeakCertified,
            "historical cash balances cannot masquerade as observed equity peaks");
        var before=recovered.Checkpoint();
        var mismatched=both with {Closed=new[]{gain,loss with {NetEur=-2m}}};
        check(!recovered.ReconcileBrokerFlat(mismatched).Adopted&&recovered.Checkpoint()==before,
            "historical net inconsistency never balances cash by invention");
        check(!recovered.ReconcileBrokerFlat(both with {Closed=new[]{gain},BalanceEur=203m,EquityEur=203m}).Adopted &&
              recovered.Checkpoint()==before,
            "a later truncated history cannot drop a previously adopted losing settlement");
        check(!recovered.ReconcileBrokerFlat(both with {Closed=new[]{gain,loss with {GrossEur=-.5m}}}).Adopted,
            "unexplained costs cannot be inserted to make the broker NET fit");
        check(recovered.ReconcileBrokerFlat(both).Adopted&&recovered.Checkpoint()==before,
            "the same native facts are deterministic under repeated full readback");
        var seenHigh=both with {Cashflows=new[]{deposits[0] with {ReportedMaximumEquityEur=250m}}};
        check(recovered.ReconcileBrokerFlat(seenHigh).ObservedPeakLowerBoundEur==250m &&
            recovered.Ledger.Summary().MaximumSampledDrawdown>=.192m,
            "native reported equity high is preserved with its current observed drawdown");
        check(recovered.ReconcileBrokerFlat(both).Adopted &&
            recovered.Ledger.Summary().ObservedPeakEur==250m &&
            recovered.Ledger.Summary().MaximumSampledDrawdown>=.192m,
            "later readback without repeated peak evidence cannot reset observed risk");
        recovered=NativeFundedSession.Restore(before,account);
        check(recovered.ReconcileBrokerFlat(both).Adopted&&
              recovered.Ledger.Summary().ObservedPeakEur>=202m,
            "retained historical lower-bound peak survives available local checkpoint");
        // A fresh process without a checkpoint also reconstructs a documented
        // lower bound from historical broker records, but never claims the
        // unknown unsampled lifetime peak to be 203.
        var lostStorage=new NativeFundedSession(account);
        check(lostStorage.ReconcileBrokerFlat(both).Adopted &&
            !lostStorage.ReconcileBrokerFlat(both).HistoricalEquityPeakCertified,
            "native reconstruction is independent of LocalStorage lifetime");
    }
}
