using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal sealed record Sir1ModelStepInput(string ModelBinding,string SourceSha256,
    string SourceEvidenceClass,string SessionCheckpoint,
    NativeModelCloseProtection Protection,NativeModelCloseObservation Observation);
internal static class Sir1NativeStepRunner
{
    public static int Run(string inputPath,string outputPath)
    {
        var options=new JsonSerializerOptions{WriteIndented=true,
            NumberHandling=JsonNumberHandling.AllowReadingFromString};
        var input=JsonSerializer.Deserialize<Sir1ModelStepInput>(
            File.ReadAllText(inputPath),options)
            ??throw new ArgumentException("SIR1_INPUT_NOT_PRESENT");
        if(input.SourceSha256.Length!=64 ||
           !input.SourceSha256.All(Uri.IsHexDigit) ||
           input.SourceEvidenceClass is not ("SYNTHETIC" or
             "ORIGINAL_BIDASK_MODEL_ONLY_NOT_BROKER_EXECUTION"))
            throw new ArgumentException("SIR1_SOURCE_IDENTITY_NOT_SPECIFIED");

        // The same Core class is compiled into the observation-only Cloud
        // adapter and Replay. Neither side owns another financial engine.
        var model=NativeFundedSession.Restore(input.SessionCheckpoint,
            input.ModelBinding);
        var step=NativeSimulatedCloseLifecycle.Advance(
            model,input.Protection,input.Observation);
        string eventJson=JsonSerializer.Serialize(step.AppliedFacts,options);
        string eventHash=Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(eventJson))).ToLowerInvariant();
        File.WriteAllText(outputPath,JsonSerializer.Serialize(new {
            Product="SIR1_SINGLE_NATIVE_MODEL_CLOSE_STEP",
            input.SourceSha256,input.SourceEvidenceClass,
            NativeCoreCodepath="Mxm.Core.NativeSimulatedCloseLifecycle.Advance",
            Step=step,EventReceiptSha256=eventHash,
            NextModelCheckpoint=model.Checkpoint(),
            FundedBrokerNetCertified=false,ContinuousDrawdownCertified=false,
            OrdersSubmitted=0,CloudActivated=false
        },options)+"\n");
        return 0;
    }
}
