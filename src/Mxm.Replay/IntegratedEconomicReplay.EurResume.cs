using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    const string HistoricalStateVersion="EUR_HISTORICAL_REPLAY_V1";

    sealed record HistoricalReplayBinding(string Protocol,string Source,string Protection,string Scenario,string? Revision,
        bool BoundedNeighbors,bool PairedDistribution,bool ReuseFrames);
    sealed record HistoricalStreamState(Dictionary<string,int> Counts,Dictionary<long,string> Availability);
    sealed record HistoricalReplayState(string Version,HistoricalReplayBinding Binding,int CompletedPhases,long LastClock,
        Dictionary<string,HistoricalStreamState> Streams,Dictionary<string,string> Probes,
        Dictionary<string,ObserverCheckpoint> Observers,Dictionary<string,string> Trials,JsonElement[] Fits);

    static string ProtectionFingerprint(string directory)
    {
        var files=Directory.EnumerateFiles(directory).OrderBy(p=>Path.GetFileName(p),StringComparer.Ordinal);
        var digests=files.Select(path=>
        {
            using var file=File.OpenRead(path);
            return Path.GetFileName(path)+":"+Convert.ToHexString(SHA256.HashData(file));
        });
        return EerHash(string.Join("\n",digests));
    }

    static void WriteHistoricalState(string path,HistoricalReplayState state)
    {
        string temporary=path+".tmp";
        using(var file=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write))
        {
            JsonSerializer.Serialize(file,state);
            file.Flush(true);
        }
        File.Move(temporary,path);
    }

    static NativeUnifiedPortfolioEngine RestoreHistoricalBook(string payload,string policy,string scenario,long expectedClock)
    {
        var book=NativeUnifiedPortfolioEngine.RestoreHistoricalEurCheckpoint(payload);
        if(book.PolicyName!=policy || book.FundingScenarioId!=scenario || book.LastObservationAt!=expectedClock)
            throw new InvalidDataException("EUR_HISTORICAL_CHECKPOINT_BOOK_BINDING");
        return book;
    }
}
