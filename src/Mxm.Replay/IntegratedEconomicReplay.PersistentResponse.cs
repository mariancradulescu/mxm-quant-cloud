using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    public static int RunPersistentResponse(string sourcePath,string checkpoint,string reportPath,
        string originalTapePath,string extendedTapePath,string output)
    {
        var sourceBytes=File.ReadAllBytes(sourcePath);
        var input=JsonSerializer.Deserialize<EerInput>(sourceBytes,Json)!;
        using var report=JsonDocument.Parse(File.ReadAllBytes(reportPath));var r=report.RootElement;
        if(r.GetProperty("Study").GetString()!="MONETARY_PERSISTENT_RISK_RECOVERY_1"||
            r.GetProperty("Stress").GetDecimal()!=.5m||GeneralSha(sourceBytes)!=r.GetProperty("SourceSha256").GetString())
            throw new InvalidDataException("PERSISTENT_RESPONSE_ORIGINAL_SOURCE");
        var published=r.GetProperty("CommonBooks").EnumerateArray().Single(x=>x.GetProperty("Id").GetString()=="CENTERED_GUARD");
        var wrapper=JsonSerializer.Deserialize<FrozenWrapper>(File.ReadAllBytes(checkpoint),NativeHistoricalCheckpointJson.Options)!;
        var core=JsonSerializer.Deserialize<FrozenCore>(wrapper.CoreCheckpoint,Json)!;
        using var saved=JsonDocument.Parse(core.Session);string payload=saved.RootElement.GetProperty("Payload").GetString()!;
        if(GeneralSha(System.Text.Encoding.UTF8.GetBytes(payload))!=saved.RootElement.GetProperty("Sha256").GetString())
            throw new InvalidDataException("PERSISTENT_RESPONSE_SESSION_HASH");
        using var sessionDoc=JsonDocument.Parse(payload);string ledgerText=sessionDoc.RootElement.GetProperty("Ledger").GetString()!;
        var terminal=NativeFundedLedger.Restore(ledgerText);
        if(terminal.Summary().EventChainHash!=published.GetProperty("Result").GetProperty("EventChainHash").GetString())
            throw new InvalidDataException("PERSISTENT_RESPONSE_ORIGINAL_EVENT_CHAIN");
        var preventive=core.Curve.First(x=>x.FundingCapital?.MaximumSampledFundingAdjustedDrawdown>=.28m);
        long hard=core.Curve.First(x=>x.FundingCapital?.MaximumSampledFundingAdjustedDrawdown>=.30m).At;
        if(preventive.At!=1795578015000L||hard!=1795599015000L)
            throw new InvalidDataException("PERSISTENT_RESPONSE_REGISTERED_CLOCKS");
        using var ledgerDoc=JsonDocument.Parse(ledgerText);
        var ledger=new NativeFundedLedger(ledgerDoc.RootElement.GetProperty("MaximumStalenessMs").GetInt64());
        var prefix=core.Events.Where(x=>x.At<=preventive.At).ToArray();foreach(var e in prefix)ledger.Apply(e);
        var before=ledger.Summary(preventive.At);
        if(before.CashEur!=preventive.CashEur||before.OpenPositions!=1||before.PendingIntents!=1)
            throw new InvalidDataException("PERSISTENT_RESPONSE_PREFIX_STATE");
        var held=ledger.PositionSnapshot().Single();var pending=ledger.PendingSnapshot().Single();
        if(held.EntryPrice is not >0m||held.Symbol!="GBPUSD"||pending.PositionId!=held.Id||pending.Kind!="REQUEST_CLOSE"||
            !NativeSimulatedCloseLifecycle.IsPersistentPortfolioClose(pending.Reason))
            throw new InvalidDataException("PERSISTENT_RESPONSE_REQUIRES_EXISTING_PERSISTENT_INTENT");
        using var coreDoc=JsonDocument.Parse(wrapper.CoreCheckpoint);
        var plans=coreDoc.RootElement.GetProperty("Plans").Deserialize<Dictionary<string,Ucp1Plan>>(Json)!;
        var plan=plans[held.Id];var market=input.Markets.Single(m=>m.Market.Name==held.Symbol);
        var evidence=new EerEvidence(input);var original=new EerProtectionTape(originalTapePath);var extended=new EerProtectionTape(extendedTapePath);
        Ucp1MarketFrame? First(EerProtectionTape tape)
        {
            foreach(long at in tape.ObservedQuoteClocks(held.Symbol,Math.Max(pending.At+pending.LatencyMs,pending.At+1),hard))
                if(evidence.ProtectionMark(tape,market,at,.5m) is { } q)return q;
            return null;
        }
        var originalWitness=First(original);var witness=First(extended);
        NativeModelCloseStep? closed=null;
        if(witness is { } observed)
        {
            if(NativeBrokerContractCosts.NextScheduledSwapCharge(market.Market.DatedDevelopment!.Contract,preventive.At) is long charge&&charge<=observed.Quote.At)
                throw new InvalidDataException("PERSISTENT_RESPONSE_NEW_UNPRICED_FINANCING");
            var session=new NativeFundedSession("SOURCE_CORRECTED_ORIGINAL_MODEL_PREFIX",ledger,journalContinuityProven:true);
            var protection=new NativeModelCloseProtection(held.Id,"ADAPT",new(plan.Atr,plan.Equilibrium),plan.Stop,
                held.EntryPrice.Value,held.EntryAt);
            closed=NativeSimulatedCloseLifecycle.Advance(session,protection,new(observed.Quote.At,observed.Quote),600000L,ownedModelLedger:true);
            if(!closed.ModelPositionClosed||closed.CommonBook.OpenPositions!=0||closed.CommonBook.PendingIntents!=0)
                throw new InvalidDataException("PERSISTENT_RESPONSE_NATIVE_CLOSE_NOT_SETTLED");
        }
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{Study="OWNER_PERSISTENT_EXECUTABLE_RESPONSE_1",
            SourceSha256=GeneralSha(sourceBytes),CheckpointSha256=FactorialFileSha(checkpoint),OriginalReportSha256=FactorialFileSha(reportPath),
            OriginalTerminalEventChainHash=terminal.Summary().EventChainHash,PrefixEventChainHash=before.EventChainHash,
            PrefixCashEur=before.CashEur,OriginalFirstPreventiveAt=preventive.At,OriginalFirstHardAt=hard,
            OriginalSampledDrawdown=published.GetProperty("Result").GetProperty("SampledDrawdown").GetDecimal(),
            held.Id,held.Symbol,held.Units,held.EntryAt,held.EntryPrice,OriginalIntentAt=pending.At,OriginalIntentLatencyMs=pending.LatencyMs,
            OriginalExecutableWitnessAt=originalWitness?.Quote.At,RecoveredExecutableWitnessAt=witness?.Quote.At,
            ObservedIntentToQuoteMs=witness is null?(long?)null:witness.Quote.At-pending.At,
            NeedAdditionalQuoteCapture=originalWitness is null,
            ObservedStopBeforeOriginalPreventive=extended.ObservedTradeStop(held.Symbol,held.Side,plan.Stop,held.EntryAt,1795564800000L,preventive.At),
            ModeledClose=closed,InheritedOriginalStateResponseOnly=true,WholePolicyReevaluated=false,
            OriginalPrefixReconstructedWithoutPolicyReplay=true,OriginalResultsModified=false,NewEntries=0,
            GlobalDrawdownCertified=false,BrokerFillCertified=false,IndependentConfirmationCertified=false,
            EconomicPromotionCertified=false,Orders=0,CloudActivated=false},Json));
        return 0;
    }
}
