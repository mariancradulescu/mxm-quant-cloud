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
        NativeStructuralModels? closedContextModels=null, NativeFundedActionModel? actionModel=null,
        bool reserveAccruedFunding=false)
    {
        engine=new NativeUnifiedPortfolioEngine(policy,brokerAccountBinding,scoreModel,models,
            closedContextModels:closedContextModels, actionModel:actionModel,
            reserveAccruedFunding:reserveAccruedFunding);
        if(NativeCompletePolicy.IsPolicy(policy)) residence=new NativeQuoteResidenceStream();
    }
    public Ucp1FrameResult Observe(Ucp1Frame frame)=>engine.Advance(residence?.Observe(frame)??frame);
    public void UseFundedActionModel(NativeFundedActionModel snapshot, long at)=>engine.UseFundedActionModel(snapshot,at);
    public void CalibrateEurRankFrom(NativeUnifiedCloudParityAdapter first)=>engine.CalibrateEurRankFrom(first.engine);
    public void LoadEurCalibration(NativeEurCalibration calibration)=>engine.LoadEurCalibration(calibration);
    public long LastObservationAt=>engine.LastObservationAt;
    public string PolicyName=>engine.PolicyName;
    public NativeFundingExposure[] FundingExposureSnapshot()=>engine.FundingExposureSnapshot();
    public string[] ActiveSymbols=>engine.ActiveSymbols;
    public LedgerEvent[] ModelFacts=>engine.OriginalModelEvents;
    public Scp1ChoiceReceipt[] Scp1Choices=>engine.Scp1ChoiceReceipts;
    public LedgerSummary ModelBook=>engine.ModelSummary;
    public Ucp1ReconciledEpisode[] ReconciledModelEpisodes=>engine.ReconciledModelEpisodes;
    public NativeFundedActionReceipt[] FundedActions=>engine.FundedActionReceipts;
    public string Checkpoint()=>engine.Checkpoint();
    public void Restore(string checkpoint)
        =>engine=NativeUnifiedPortfolioEngine.Restore(checkpoint);
}
