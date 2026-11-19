using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class Npi1NativeStudy
{
    public static int Run(string originalInput,string publicOutput)
    {
        var settings=new JsonSerializerOptions{
            NumberHandling=JsonNumberHandling.AllowReadingFromString,
            WriteIndented=true
        };
        var data=JsonSerializer.Deserialize<Npi1OriginalTape>(
            File.ReadAllText(originalInput),settings)
            ??throw new ArgumentException("NPI1_ORIGINAL_SOURCE_NOT_DESERIALIZED");
        var report=NativeNpi1IntegratedResearch.Evaluate(data);
        File.WriteAllText(publicOutput,JsonSerializer.Serialize(report,settings)+"\n");
        return 0;
    }
}
