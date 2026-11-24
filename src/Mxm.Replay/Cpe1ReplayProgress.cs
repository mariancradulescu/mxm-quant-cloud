using System.Diagnostics;
using System.Text.Json;

// EPM1 emits progress from completed work inside Replay. These records contain
// no quotes, account identities, decisions, positions, or economic results.
internal sealed class Cpe1ReplayProgress
{
    readonly Stopwatch elapsed = Stopwatch.StartNew();
    TimeSpan lastEmission = TimeSpan.MinValue;
    string activeStage = "READ_NATIVE_INPUT";

    public void Report(string stage, int completed = 0, int? total = null,
        int? book = null, bool force = false)
    {
        activeStage = stage;
        var now = elapsed.Elapsed;
        if (!force && completed != total &&
            lastEmission != TimeSpan.MinValue && now - lastEmission < TimeSpan.FromSeconds(15))
            return;

        lastEmission = now;
        Console.WriteLine("EPM1 " + JsonSerializer.Serialize(new
        {
            stage, completed, total, book, elapsedSeconds = (long)now.TotalSeconds
        }));
        Console.Out.Flush();
    }

    public void ReportFailure(Exception error)
    {
        // Exception text, inner exceptions and stack traces can include
        // fields from the source tape and runner filesystem paths.
        var code = error switch
        {
            JsonException => "REPLAY_INVALID_INPUT_JSON",
            FileNotFoundException or DirectoryNotFoundException => "REPLAY_FILE_MISSING",
            UnauthorizedAccessException => "REPLAY_FILE_ACCESS_DENIED",
            IOException => "REPLAY_IO_FAILED",
            OverflowException => "REPLAY_NUMERIC_OVERFLOW",
            ArgumentException { Message: "CPE1_PROTOCOL_HASH" } => "REPLAY_PROTOCOL_HASH_INVALID",
            ArgumentException => "REPLAY_INPUT_CONTRACT_FAILED",
            InvalidOperationException
                { Message: "CPE1_ORIGINAL_NATIVE_EVENT_CHAIN_EUR300_RECONCILIATION" } =>
                "REPLAY_EVENT_CHAIN_RECONCILIATION_FAILED",
            InvalidOperationException => "REPLAY_STATE_VALIDATION_FAILED",
            _ => "REPLAY_UNEXPECTED_ERROR"
        };
        Console.Error.WriteLine("EPM1_REPLAY_ERROR " + JsonSerializer.Serialize(new
        {
            stage = activeStage, code
        }));
    }
}
