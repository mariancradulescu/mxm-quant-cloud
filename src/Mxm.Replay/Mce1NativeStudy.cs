using System;
using System.IO;
using System.Text.Json;
using Mxm.Core;

// MCE1 new historical mechanism-stability study: Replay only delegates to
// the SAME original CDH1 Core causal population/Bayes/Softmax/score helpers.
// No duplicate fitting logic, no broker orders, no future Cloud activation.
internal static class Mce1NativeStudy
{
    public static int Run(string path,string output)
    {
        var original=JsonSerializer.Deserialize<Cdh1Input>(
            File.ReadAllBytes(path),new JsonSerializerOptions{
                PropertyNameCaseInsensitive=true
            })??throw new ArgumentException("MCE1_MISSING_AUTHENTIC_XMH2_SOURCE");
        var report=Cdh1NativeResearch.RunCumulativeMce1(original);
        File.WriteAllText(output,JsonSerializer.Serialize(report,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("MCE1_ORIGINAL_XMH2_REUSED_NATIVE_CDH1_MECHANISMS_HISTORICAL_ONLY");
        return 0;
    }
}
