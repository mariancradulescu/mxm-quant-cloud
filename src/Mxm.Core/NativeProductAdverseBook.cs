using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace Mxm.Core;

// A SECOND SCENARIO of the EXISTING native financial ledger, not a new ledger
// implementation or trading account. Replays each intended/executed model fact
// at doubled spread, fee and slippage, adverse FX conversion and financing.
// Missing or unfinanceable adverse marks make NET unknown, never positive by fiat.
public sealed class NativeProductAdverseBook
{
    private NativeFundedLedger book=new();
    private Dictionary<string,LedgerQuote> market=new(StringComparer.Ordinal);
    public bool Complete {get;private set;}=true;
    public string Failure {get;private set;}="";
    public LedgerSummary? Summary=>Complete?book.Summary():null;
    public string Export()=>JsonSerializer.Serialize(new {
        Version=1,Book=book.Checkpoint(),Market=market,Complete,Failure
    });
    public static NativeProductAdverseBook Restore(string json)
    {
        using var d=JsonDocument.Parse(json);
        if(d.RootElement.GetProperty("Version").GetInt32()!=1)
            throw new ArgumentException("ADVERSE_REPLAY_VERSION");
        var a=new NativeProductAdverseBook();
        a.book=NativeFundedLedger.Restore(d.RootElement.GetProperty("Book").GetString()!);
        a.market=JsonSerializer.Deserialize<Dictionary<string,LedgerQuote>>(
            d.RootElement.GetProperty("Market").GetRawText())!;
        a.Complete=d.RootElement.GetProperty("Complete").GetBoolean();
        a.Failure=d.RootElement.GetProperty("Failure").GetString()??"";
        return a;
    }
    private static LedgerQuote Stress(LedgerQuote q)
    {
        var width=q.Ask-q.Bid;
        return q with {
            Bid=q.Bid-width/2m,
            Ask=q.Ask+width/2m,
            EurCredit=q.EurCredit*.999m,
            EurDebit=q.EurDebit*1.001m,
            ExitFeePerUnit=q.ExitFeePerUnit*2m,
            ExitFeeFloor=q.ExitFeeFloor*2m
        };
    }
    private LedgerEvent Reprice(LedgerEvent e,Dictionary<string,LedgerQuote> state)
    {
        var quotes=e.Quotes.Select(Stress).ToArray();
        foreach(var q in quotes)state[q.Symbol]=q;
        decimal slip=e.SlippagePerSide*2m;
        decimal execution=e.ExecutionPrice,fee=e.FeeEur;
        if(e.Kind is "OPEN_FILL" or "CLOSE_FILL")
        {
            if(!state.TryGetValue(e.Symbol,out var q))
                throw new InvalidOperationException("ADVERSE_MISSING_MARK");
            execution=e.Kind=="OPEN_FILL"
                ?(e.Side>0?q.Ask+slip:q.Bid-slip)
                :(e.Side>0?q.Bid-slip:q.Ask+slip);
            fee=Math.Max(q.ExitFeePerUnit*e.Units,q.ExitFeeFloor);
        }
        decimal finance=e.SignedFinancingEur<0?
            e.SignedFinancingEur*2m:0m;
        return e with {Quotes=quotes,ExecutionPrice=execution,
            FeeEur=fee,SlippagePerSide=slip,SignedFinancingEur=finance};
    }
    public void Apply(params LedgerEvent[] facts)
    {
        if(!Complete)return;
        try
        {
            var candidate=NativeFundedLedger.Restore(book.Checkpoint());
            var next=new Dictionary<string,LedgerQuote>(market,StringComparer.Ordinal);
            foreach(var f in facts)candidate.Apply(Reprice(f,next));
            book=candidate;market=next;
        }
        catch(Exception ex) when(ex is InvalidOperationException or ArgumentException
            or OverflowException)
        {
            Complete=false;
            Failure="ADVERSE_REPRICED_PATH_UNFINANCEABLE_OR_INCOMPLETE:"+ex.GetType().Name;
        }
    }
}
