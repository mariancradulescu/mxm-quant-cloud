using System;
using System.IO;
using System.Text.Json;
using Mxm.Core;

// MVO1: immutable original-source reader only; ALL causal price and
// portfolio occupancy logic lives in the existing shared C# Core assembly.
internal static class Mvo1NativeStudy
{
    public static int Run(string originalInput,string publicOutput)
    {
        var source=JsonSerializer.Deserialize<Cdh1Input>(File.ReadAllBytes(originalInput),
            new JsonSerializerOptions{PropertyNameCaseInsensitive=true})
            ??throw new ArgumentException("MVO1_AUTHENTIC_READONLY_TAPE_MISSING");
        var report=NativeMarginalValueResearch.Evaluate(source);
        File.WriteAllText(publicOutput,JsonSerializer.Serialize(report,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("MVO1_NEW_NATIVE_GENUINE_M15_CAUSAL_MARGINAL_VALUE_COMPLETED_FINANCE_UNKNOWN");
        return 0;
    }
}
