using Mxm.Core;

namespace Mxm.Cloud;

// The very SAME C# Core portfolio, funded ledger, signal and modeled
// intent/exit lifecycle used by Ucp1OriginalUnifiedRunner in Mxm.Replay.
// No Robot, TradeOperation or order API is called by this adapter.
public sealed class NativeUnifiedCloudParityAdapter
{
    private NativeUnifiedPortfolioEngine engine;
    public NativeUnifiedCloudParityAdapter(string policy="JOINT",
        string brokerAccountBinding="",Scp1ScoreModel? scoreModel=null)
        =>engine=new NativeUnifiedPortfolioEngine(policy,brokerAccountBinding,scoreModel);
    public Ucp1FrameResult Observe(Ucp1Frame frame)=>engine.Advance(frame);
    public string[] ActiveSymbols=>engine.ActiveSymbols;
    public LedgerEvent[] ModelFacts=>engine.OriginalModelEvents;
    public Scp1ChoiceReceipt[] Scp1Choices=>engine.Scp1ChoiceReceipts;
    public LedgerSummary ModelBook=>engine.ModelSummary;
    public string Checkpoint()=>engine.Checkpoint();
    public void Restore(string checkpoint)
        =>engine=NativeUnifiedPortfolioEngine.Restore(checkpoint);
}
