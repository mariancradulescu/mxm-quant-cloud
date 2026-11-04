namespace Mxm.Core;

public sealed record FrozenMoneyRecoveryCase(string Id,string AccountBinding,LocalIntentIdentity[] Intents,MoneyRecoveryBatch[] Batches);
// Technical use of immutable modeled settlements only. Never a broker fill claim.
public static class FrozenMoneyRecoveryReceipt
{
    public static object Receive(FrozenMoneyRecoveryCase[] cases)
    {
        return cases.Select(c=>{
            if(c.Batches.Any(b=>b.Domain!="FROZEN_MODELED_SETTLEMENT"))throw new ArgumentException("RECEIPT_SOURCE_NOT_FROZEN_MODELED_FACTS");
            var session=new NativeFundedSession(c.AccountBinding,intents:c.Intents,journalContinuityProven:true);
            var receipts=new List<MoneyRecoveryReport>();
            foreach(var b in c.Batches)
            {
                var report=session.ReconcileMoney(b);if(!report.Adopted)throw new InvalidOperationException(string.Join("/",report.Reasons));
                string before=session.Checkpoint();session=NativeFundedSession.Restore(before,c.AccountBinding);
                var duplicate=session.ReconcileMoney(b);
                if(!duplicate.Adopted||before!=session.Checkpoint())throw new InvalidOperationException("MONEY_RESTART_OR_DUPLICATION_MISMATCH");
                receipts.Add(report);
            }
            return new {c.Id,Receipts=receipts,Summary=session.Ledger.Summary(),Trades=session.Ledger.ClosedFragments(),
                RestartEveryCutMatched=true,DuplicatesIdempotent=true,OriginalStudyRerun=false,ActualBrokerRecoveryProven=false,OrdersSubmitted=0};
        }).ToArray();
    }
}
