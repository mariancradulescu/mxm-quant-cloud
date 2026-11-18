using System;
using System.IO;
using System.Text.Json;
using Mxm.Core;

// Thin C# runner: ALL causal admission, models, outcomes, scoring and decision
// controls are Mxm.Core. No alternate Python/Replay economic authority.
internal static class Cdh1NativeStudy
{
    public static int Run(string input,string output)
    {
        var payload=JsonSerializer.Deserialize<Cdh1Input>(
            File.ReadAllBytes(input),
            new JsonSerializerOptions{PropertyNameCaseInsensitive=true})
            ??throw new ArgumentException("CDH1_EMPTY_SOURCE");
        var result=Cdh1NativeResearch.Run(payload);
        File.WriteAllText(output,JsonSerializer.Serialize(result,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("CDH1_CSHARP_CAUSAL_EXANTE_COMPETING_RISKS_COMPLETE_NO_ORDERS");
        return 0;
    }
    public static int SelfTest(string output)
    {
        var check=Cdh1NativeResearch.SelfTest();
        File.WriteAllText(output,JsonSerializer.Serialize(check,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("CDH1_SYNTHETIC_CAUSAL_ADMISSION_CENSOR_AMBIGUOUS_SOFTMAX_PASS");
        return 0;
    }
}