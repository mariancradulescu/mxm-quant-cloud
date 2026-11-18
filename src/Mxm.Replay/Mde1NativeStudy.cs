using System;
using System.IO;
using System.Text.Json;
using Mxm.Core;

// MDE1: no model, monetary engine or finance in Replay; all reusable C# Core.
internal static class Mde1NativeStudy
{
    public static int Run(string sourcePath,string publicPath)
    {
        var original=JsonSerializer.Deserialize<Cdh1Input>(File.ReadAllBytes(sourcePath),
            new JsonSerializerOptions {PropertyNameCaseInsensitive=true})
            ??throw new ArgumentException("MDE1_AUTHENTIC_SOURCE_MISSING");
        var result=Cdh1NativeResearch.RunCumulativeMde1(original);
        File.WriteAllText(publicPath,JsonSerializer.Serialize(result,
            new JsonSerializerOptions {WriteIndented=true}));
        Console.WriteLine("MDE1_ORIGINAL_EXISTING_CDH1_METHODS_ALL12_DIRECTION_VS_EVENT_COMPLETE");
        return 0;
    }
    public static int SelfTest(string output)
    {
        var result=Cdh1NativeResearch.SelfTestMde1();
        File.WriteAllText(output,JsonSerializer.Serialize(result,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("MDE1_SYNTHETIC_CAUSAL_SIGN_DECOMPOSITION_PASS");
        return 0;
    }
}
