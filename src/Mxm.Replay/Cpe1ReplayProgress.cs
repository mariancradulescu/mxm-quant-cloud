using System.Diagnostics;
using System.Text.Json;

// EPM1 emits progress from completed work inside Replay. These records contain
// no quotes, account identities, decisions, positions, or economic results.
internal sealed class Cpe1ReplayProgress
{
    readonly Stopwatch elapsed = Stopwatch.StartNew();
    TimeSpan lastEmission = TimeSpan.MinValue;

    public void Report(string stage, int completed = 0, int? total = null,
        int? book = null, bool force = false)
    {
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
}
