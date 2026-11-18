using System;
using System.IO;
using System.Text.Json;
using Mxm.Core;

// SHD1 execution shell: NO features, scoring, choices or money outside Mxm.Core.
internal static class Shd1NativeStudy
{
    public static int Run(string path,string output)
    {
        var input=JsonSerializer.Deserialize<Shd1Input>(File.ReadAllBytes(path),
            new JsonSerializerOptions{PropertyNameCaseInsensitive=true})
            ??throw new ArgumentException("SHD1_MISSING_AUTHENTIC_INPUT");
        var receipt=Shd1NativeDiscovery.Run(input);
        File.WriteAllText(output,JsonSerializer.Serialize(receipt,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("SHD1_AUTHENTIC_H1_M15_NATIVE_PREDICTIVE_AGGREGATE_NO_ORDERS");
        return 0;
    }
    public static int SelfTest(string output)
    {
        var receipt=Shd1NativeDiscovery.SelfTest();
        File.WriteAllText(output,JsonSerializer.Serialize(receipt,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("SHD1_CAUSAL_SESSION_AND_NONLINEAR_LEARNING_SYNTHETIC_ONLY_PASS");
        return 0;
    }
}
