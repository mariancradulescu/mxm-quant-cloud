using System;
using System.IO;
using System.Text.Json;
using Mxm.Core;

// Authentic original market bars enter Mxm.Core unchanged from verified custody.
// This runner does not implement features, models, selection, outcomes or money.
internal static class Ahr1NativeStudy
{
    public static int Run(string path,string output)
    {
        var input=JsonSerializer.Deserialize<Ahr1H1Input>(
            File.ReadAllBytes(path),new JsonSerializerOptions{
                PropertyNameCaseInsensitive=true
            }) ?? throw new ArgumentException("AHR1_MISSING_INPUT");
        var report=Ahr1NativeResearch.Run(input);
        File.WriteAllText(output,JsonSerializer.Serialize(report,
            new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("AHR1_NATIVE_AUTHENTIC_H1_AGGREGATE_COMPLETE_NO_ORDER_NO_FINANCIAL_CLAIM");
        return 0;
    }
}
