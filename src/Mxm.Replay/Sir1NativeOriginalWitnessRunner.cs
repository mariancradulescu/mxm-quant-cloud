using System;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class Sir1NativeOriginalWitnessRunner
{
    public static int Run(string input,string output)
    {
        var options=new JsonSerializerOptions{
            WriteIndented=true,
            NumberHandling=JsonNumberHandling.AllowReadingFromString};
        var tape=JsonSerializer.Deserialize<Sir1OriginalSourceWitnessTape>(
            File.ReadAllText(input),options)
            ??throw new ArgumentException("SIR1_ORIGINAL_SOURCE_WITNESS_INPUT");
        var result=NativeSir1OriginalSourceWitness.Evaluate(tape);
        File.WriteAllText(output,JsonSerializer.Serialize(result,options)+"\n");
        return 0;
    }
}
