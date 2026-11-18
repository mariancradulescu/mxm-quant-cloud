using Mxm.Core;

namespace Mxm.Cloud;

// Source file compiled unchanged into Mxm.Cloud AND the no-order native
// verification runner. This adapter contains NO model, economic, risk,
// fill, financing or SL/TP formula. It never instantiates a Robot.
public sealed class NativeCloudResearchParityAdapter
{
    private readonly NativeBayesianCommonEpisode engine=new();
    public NativeBayesStep ObserveCompletedQuote(NativeBayesObservation eventAtClose,int index)
        =>engine.Advance(eventAtClose,index);
    public LedgerSummary CommonBook=>engine.CurrentBook;
    public LedgerClosedFragment[] Closed=>engine.ClosedFragments();
}
