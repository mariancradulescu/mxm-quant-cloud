using Mxm.Core;

namespace Mxm.Cloud;

// The very SAME C# Core portfolio, funded ledger, signal and modeled
// intent/exit lifecycle used by Ucp1OriginalUnifiedRunner in Mxm.Replay.
// No Robot, TradeOperation or order API is called by this adapter.
public sealed class NativeUnifiedCloudParityAdapter
{
    private NativeUnifiedPortfolioEngine engine;
    private readonly NativeQuoteResidenceStream? residence;
    public NativeUnifiedCloudParityAdapter(string policy="JOINT",
        
        string brokerAccountBinding="",Scp1ScoreModel? scoreModel=null,NativeCompleteModels? models=null,
        NativeStructuralModels? closedContextModels=null, NativeFundedActionModel? actionModel=null)
    {
        engine=new NativeUnifiedPortfolioEngine(policy,brokerAccountBinding,scoreModel,models,
            closedContextModels:closedContextModels, actionModel:actionModel);
        if(NativeCompletePolicy.IsPolicy(policy)) residence=new NativeQuoteResidenceStream();
    }
    public Ucp1FrameResult Observe(Ucp1Frame frame)=>engine.Advance(residence?.Observe(frame)??frame);
    public string[] ActiveSymbols=>engine.ActiveSymbols;
    public LedgerEvent[] ModelFacts=>engine.OriginalModelEvents;
    public Scp1ChoiceReceipt[] Scp1Choices=>engine.Scp1ChoiceReceipts;
    public LedgerSummary ModelBook=>engine.ModelSummary;
    public NativeFundedActionReceipt[] FundedActions=>engine.FundedActionReceipts;
    public string Checkpoint()=>engine.Checkpoint();
    public void Restore(string checkpoint)
        =>engine=NativeUnifiedPortfolioEngine.Restore(checkpoint);
}
