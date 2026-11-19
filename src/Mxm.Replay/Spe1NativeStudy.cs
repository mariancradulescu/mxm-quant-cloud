using System;
using System.IO;
using System.Text.Json;
using Mxm.Core;

// SPE1 Replay is input/output routing only; one shared C# Core holds signals,
// signal exits, joint multi-symbol capacity, comparators and all diagnostics.
internal static class Spe1NativeStudy
{
    public static int Run(string privateInput,string publicOutput)
    {
        var input=JsonSerializer.Deserialize<Cdh1Input>(File.ReadAllBytes(privateInput),
            new JsonSerializerOptions{PropertyNameCaseInsensitive=true})
            ??throw new ArgumentException("SPE1_PRIVATE_ORIGINAL_M15_SOURCE_UNAVAILABLE");
        var result=NativeSignalEconomicResearch.Evaluate(input);
        File.WriteAllText(publicOutput,JsonSerializer.Serialize(result,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("SPE1_TWELVE_GENUINE_M15_PRICE_ONLY_CAUSAL_ECONOMICS_SCORE_COMPLETE_NET_UNKNOWN");
        return 0;
    }
}
