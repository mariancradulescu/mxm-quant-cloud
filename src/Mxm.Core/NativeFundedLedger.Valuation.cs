using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;
public sealed record LedgerConditionalPositionValuation(string PositionId,string Symbol,int Side,decimal Units,
    decimal? FloatingAfterExitCostsEur,decimal? MarginEur,LedgerQuote? Mark,string Status);

public sealed partial class NativeFundedLedger
{
    // Read-only restatement of a saved model book. Cash, fills, decisions,
    // event hashes and the original observed peak remain untouched.
    public LedgerSummary InspectConditionalValuation(long at,IEnumerable<LedgerQuote> marks)
    {
        var quotes=ConditionalValuationQuotes(at,marks);
        decimal? equity=null,margin=null;
        try
        {
            equity=Equity(quotes,at);
            margin=state.Positions.Values.Sum(p=>p.Units*Math.Max(p.MarginPerUnit,Quote(quotes,p.Symbol,at).MarginPerUnit));
        }
        catch(InvalidOperationException){}
        var before=Summary(at);
        return before with {LiquidationEquityEur=equity,UsedMarginEur=margin,FreeMarginEur=equity-margin};
    }

    Dictionary<string,LedgerQuote> ConditionalValuationQuotes(long at,IEnumerable<LedgerQuote> marks)
    {
        if(at<state.Clock)throw new ArgumentException("VALUATION_BEFORE_LEDGER_CLOCK");
        var input=marks.ToArray();
        if(input.Select(q=>q.Symbol).Distinct().Count()!=input.Length||
            input.Any(q=>q.At!=at||q.Bid<=0m||q.Ask<q.Bid||q.EurCredit<=0m||
                q.EurDebit<q.EurCredit||q.MarginPerUnit<=0m||
                !state.Positions.Values.Any(p=>p.Symbol==q.Symbol)))
            throw new ArgumentException("VALUATION_MARK_CONTRACT");
        var quotes=new Dictionary<string,LedgerQuote>(state.Quotes,StringComparer.Ordinal);
        foreach(var q in input)quotes[q.Symbol]=q;
        return quotes;
    }

    // Individual floating value is incremental to already-booked cash; entry
    // fees and posted financing must not be counted a second time.
    public LedgerConditionalPositionValuation[] InspectConditionalPositions(long at,IEnumerable<LedgerQuote> marks)
    {
        var quotes=ConditionalValuationQuotes(at,marks);
        return state.Positions.Values.Select(p=>
        {
            try
            {
                var q=Quote(quotes,p.Symbol,at);
                return new LedgerConditionalPositionValuation(p.Id,p.Symbol,p.Side,p.Units,Floating(p,q),
                    p.Units*Math.Max(p.MarginPerUnit,q.MarginPerUnit),q,"CONDITIONAL_MONETARY_VALUE");
            }
            catch(InvalidOperationException)
            {
                return new LedgerConditionalPositionValuation(p.Id,p.Symbol,p.Side,p.Units,null,null,null,
                    "CONDITIONAL_MONETARY_VALUE_UNKNOWN");
            }
        }).ToArray();
    }
}
