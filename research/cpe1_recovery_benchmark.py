"""Offline technical CPE1 comparison at the exact failed run's commit.

Only bounded generated fixtures are available here. This does not read custody,
dispatch Actions or produce an authenticated economic result.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .cpe1_recovery_execute import run_replay_process

ROOT = Path(__file__).resolve().parents[1]
BASE = "cf6d830ee8c8c9866332af3cd96ac9f7ac22987d"
REPLAY = Path("src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll")
TRACE = Path("tests/Mxm.Checks/bin/Release/net8.0/Mxm.Checks.dll")
PROFILE_PREFIX = "CPE1_TECH_PROFILE "
PROGRESS_PREFIX = "EPM1 "
M5 = 300_000
START = 1_795_440_000_000


def run(args, cwd=ROOT, **kwargs):
    return subprocess.run(args, cwd=cwd, check=True, timeout=480, **kwargs)


def archive_baseline(folder):
    tar = folder.parent / "original.tar"
    run(["git", "archive", "-o", str(tar), BASE, "src", "tests", "Directory.Build.props"])
    folder.mkdir()
    run(["tar", "-xf", str(tar), "-C", str(folder)])
    tar.unlink()


def fixture(path, clocks):
    # Price geometry repeats with positive and adverse moves. One missing EUR
    # conversion clock exercises the runner's no-observation path. Use integer
    # wire prices so both runtimes receive byte-identical decimals.
    pattern = [10000, 10010, 10020, 10030, 10090, 10095, 10120,
               10012, 10010, 10000, 10005, 10010]
    markets, funding = [], []
    for symbol, offset in (("EURUSD", 0), ("GBPUSD", 5)):
        def bar(i, span):
            # Serialize as decimal strings, which is also accepted by the
            # production source adapter's native JSON options.
            opened = pattern[i % len(pattern)] + offset
            closed = pattern[(i + span) % len(pattern)] + offset
            wire = lambda value: f"{value // 100}.{value % 100:02d}"
            return dict(OpenAt=START + i*M5, Open=wire(opened),
                        High=wire(max(opened, closed) + 2),
                        Low=wire(min(opened, closed) - 2), Close=wire(closed),
                        TickVolume=100)

        terms = dict(
            Symbol=symbol, QuoteAsset="USD", MinimumUnits=1, StepUnits=1,
            MaximumUnits=2, LotUnits=100, CommissionType=2, PreciseRateWire=0,
            MinimumCommissionType=2, PreciseMinimumWire=0,
            PnlConversionFeeBps=0, SwapCalculationType=0, LongSwap="-0.3",
            ShortSwap="-0.1", PipPosition=4, SwapPeriodHours=24,
            SwapTimeUtcMinute=1320, TripleSwapWeekday=3, MarginMinimumEur=1,
            SpreadBps="0.2", ObservedAtUtcMs=START-1)
        markets.append(dict(Symbol=symbol, Terms=terms, Bars={
            "M5": [bar(i, 1) for i in range(clocks) if symbol != "EURUSD" or i != 81],
            "M15": [bar(i, 3) for i in range(0, clocks-2, 3)],
        }))
        funding.append(dict(Symbol=symbol, ChargeSwapAtWeekends=False,
                            SkipSwapPeriods=0, ObservedAtUtcMs=START-1,
                            OriginalBrokerAuthenticated=True))
    tape = dict(SourceRuns=[f"TECHNICAL_FIXTURE_{i}" for i in range(5)],
                ProtocolSha256="0"*64, PriceNormalization="TECHNICAL_FIXTURE",
                DevelopmentOnly=True, Markets=markets)
    path.write_text(json.dumps(dict(Tape=tape, Funding=funding)), encoding="utf-8")


def inject_profile(folder):
    """Instrument an ephemeral production-code copy, pinned by the baseline SHA."""
    core = folder / "src/Mxm.Core"
    replay = folder / "src/Mxm.Replay"
    (core / "Cpe1TechnicalProfile.cs").write_text(r"""
using System.Diagnostics;
using System.Text.Json;
namespace Mxm.Core;

public static class Cpe1TechnicalProfile
{
    sealed class Metric
    {
        public long Calls {get; set;}
        public long Ticks {get; set;}
        public long AllocatedBytes {get; set;}
        public double Milliseconds => 1000.0 * Ticks / Stopwatch.Frequency;
    }
    static readonly Dictionary<string,Metric> metrics = new(StringComparer.Ordinal);
    public static Scope Measure(string name)
    {
        if (!metrics.TryGetValue(name, out var metric)) metrics.Add(name, new Metric());
        return new Scope(name);
    }
    public static void Print() => Console.Error.WriteLine(
        "CPE1_TECH_PROFILE " + JsonSerializer.Serialize(metrics));
    public readonly struct Scope : IDisposable
    {
        readonly string name;
        readonly long ticks;
        readonly long bytes;
        public Scope(string name)
        {
            this.name = name;
            ticks = Stopwatch.GetTimestamp();
            bytes = GC.GetAllocatedBytesForCurrentThread();
        }
        public void Dispose()
        {
            long allocated = GC.GetAllocatedBytesForCurrentThread() - bytes;
            long elapsed = Stopwatch.GetTimestamp() - ticks;
            var metric = metrics[name];
            metric.Calls++;
            metric.Ticks += elapsed;
            metric.AllocatedBytes += allocated;
        }
    }
}
""", encoding="utf-8")

    def replace(path, old, new):
        source = path.read_text(encoding="utf-8")
        if source.count(old) != 1:
            raise ValueError(f"profile anchor mismatch: {path.name} / {old}")
        path.write_text(source.replace(old, new, 1), encoding="utf-8")

    def scope(path, anchor, name):
        replace(path, anchor, anchor + f'\n        using var measure = Cpe1TechnicalProfile.Measure("{name}");')

    ledger = core / "NativeFundedLedger.cs"
    scope(ledger, "public LedgerSummary Summary(long? observedAt=null)\n    {", "Ledger.Summary")
    scope(ledger, "void Reconcile()\n    {", "Ledger.Reconcile")
    scope(ledger, "public void Apply(LedgerEvent e)\n    {", "Ledger.Apply")
    session = core / "NativeFundedDecisionCycle.cs"
    scope(session, "public LedgerSummary ApplyResearchFacts(LedgerEvent[] facts)\n    {", "Session.ApplyResearchFacts")
    replace(session, """        var candidate=NativeFundedLedger.Restore(Ledger.Checkpoint());
        foreach(var fact in facts)""",
            """        NativeFundedLedger candidate;
        using (Cpe1TechnicalProfile.Measure("Session.CheckpointAndRestore"))
            candidate=NativeFundedLedger.Restore(Ledger.Checkpoint());
        foreach(var fact in facts)""")
    economic = core / "NativeUnifiedPortfolioEngine.Economic.cs"
    scope(economic, "Ucp1Episode[] known,string family)\n    {", "Policy.LowerObservedGross")
    scope(economic, "Cpe1Manage(\n        Ucp1Plan plan,LedgerPosition position,Ucp1MarketFrame market,Ucp1Frame frame)\n    {",
          "Policy.Manage")
    scope(core / "NativeUnifiedPortfolioEngine.cs",
          "NativeFundedActionProbe? actionProbe = null)\n    {", "Engine.Advance")
    runner = replay / "Cpe1OriginalIntegratedRunner.cs"
    replace(runner, "        foreach(long t in times)",
            '        using (Cpe1TechnicalProfile.Measure("Replay.ProcessClocks"))\n        foreach(long t in times)')
    replace(runner, "        string Week(long t)", '        using var finalize = Cpe1TechnicalProfile.Measure("Replay.Finalize");\n        string Week(long t)')
    program = replay / "Program.cs"
    replace(program, "    return Cpe1OriginalIntegratedRunner.Run(args[0],args[1],args[3]);",
            """{
    int result;
    using (Mxm.Core.Cpe1TechnicalProfile.Measure("Replay.Total"))
        result = Cpe1OriginalIntegratedRunner.Run(args[0],args[1],args[3]);
    Mxm.Core.Cpe1TechnicalProfile.Print();
    return result;
}""")


def build(dotnet, directory, project):
    run([dotnet, "build", project, "-c", "Release", "--nologo", "-v", "quiet",
         "-p:NuGetAudit=false"], directory, stdout=subprocess.DEVNULL)


def replay(dotnet, directory, source, target, *, candidate=False):
    mode = ("--cpe1-recovery-native-funded-economics" if candidate else
            "--cpe1-one-unified-financed-economics")
    command = [dotnet, str(directory / REPLAY), str(source), str(target), mode, "0"*64]
    started = time.perf_counter()
    if candidate:
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            run_replay_process(command, os.environ, 480)
        progress = [json.loads(line.removeprefix(PROGRESS_PREFIX))
                    for line in captured.getvalue().splitlines()]
        profile = None
    else:
        process = run(command, directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        profile = next((json.loads(line.removeprefix(PROFILE_PREFIX))
                        for line in process.stderr.splitlines() if line.startswith(PROFILE_PREFIX)), None)
        progress = []
    elapsed = time.perf_counter() - started
    return elapsed, hashlib.sha256(target.read_bytes()).hexdigest(), profile, progress


def check_progress(progress, clocks):
    if not progress or progress[0]["stage"] != "READ_NATIVE_INPUT":
        raise AssertionError("CPE1 native begin event absent")
    if any(set(event) != {"stage", "completed", "total", "book", "elapsedSeconds"}
           for event in progress):
        raise AssertionError("CPE1 progress contains non-aggregate fields")
    advancing = [event for event in progress if event["stage"] == "ADVANCE_SOURCE_CLOCKS"]
    counts = [event["completed"] for event in advancing]
    if (len(counts) < 3 or counts[0] != 0 or counts[1] != 1 or counts[-1] != clocks or
            counts != sorted(set(counts)) or any(event["total"] != clocks for event in advancing)):
        raise AssertionError("CPE1 clock progress absent, incomplete or nonmonotonic")
    for stage in ("RECONCILE_BOOK_EVENTS", "SCORE_AND_REPORT_BOOK"):
        books = [event["book"] for event in progress if event["stage"] == stage
                 and event["completed"] == event["total"] and event["total"] > 0]
        if books != list(range(1, 10)):
            raise AssertionError("CPE1 nine-book completion evidence missing")
    if progress[-1]["stage"] != "WRITE_NATIVE_RECEIPT" or progress[-1]["completed"] != 1:
        raise AssertionError("CPE1 progress lacks completed native receipt")


def compare_trace(dotnet, original):
    checks = Path("tests/Mxm.Checks")
    for name in ("Cpe1IntegratedEconomicChecks.cs", "Cpe1RecoveryParityChecks.cs"):
        shutil.copyfile(ROOT / checks / name, original / checks / name)
    entry = original / checks / "Program.cs"
    code = entry.read_text(encoding="utf-8")
    entry.write_text(code.replace("var passed = 0;", """
if (args is ["--cpe1-technical-parity"])
{
    Cpe1RecoveryParityChecks.WriteTrace();
    return;
}
var passed = 0;""", 1), encoding="utf-8")
    for repository in (original, ROOT):
        build(dotnet, repository, str(checks))
    original_trace, candidate_trace = [
        run([dotnet, str(repo / TRACE), "--cpe1-technical-parity"], repo,
            stdout=subprocess.PIPE).stdout for repo in (original, ROOT)
    ]
    if original_trace != candidate_trace:
        raise AssertionError("CPE1 decisions, facts, settlements or restart digests differ")
    print(json.dumps(dict(Scope="TECHNICAL_FIXTURE_ONLY", Reference=BASE,
                          TraceSha256=hashlib.sha256(candidate_trace).hexdigest(),
                          Scenarios=json.loads(candidate_trace))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet", default="dotnet")
    parser.add_argument("--sizes", nargs="+", type=int, default=[512, 1024, 2048])
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--baseline-profile", action="store_true")
    parser.add_argument("--trace-only", action="store_true")
    args = parser.parse_args()
    if any(n < 500 or n > 4096 for n in args.sizes) or not 1 <= args.repeat <= 5:
        parser.error("technical benchmark requires 500–4096 clocks and 1–5 trials")
    with tempfile.TemporaryDirectory(prefix="cpe1-technical-") as tmp:
        folder = Path(tmp)
        original = folder / "original"
        archive_baseline(original)
        if args.trace_only:
            compare_trace(args.dotnet, original)
            return
        if args.baseline_profile:
            inject_profile(original)
        build(args.dotnet, original, "src/Mxm.Replay")
        if not args.baseline_profile:
            build(args.dotnet, ROOT, "src/Mxm.Replay")
            compare_trace(args.dotnet, original)
        for clocks in args.sizes:
            source = folder / "fixture.json"
            fixture(source, clocks)
            for repetition in range(args.repeat):
                output = folder / "replay.json"
                before = replay(args.dotnet, original, source, output)
                row = dict(Scope="TECHNICAL_FIXTURE_ONLY", Clocks=clocks,
                           Trial=repetition + 1, BaselineSeconds=round(before[0], 4),
                           OutputSha256=before[1])
                if args.baseline_profile:
                    row["Profile"] = before[2]
                else:
                    after = replay(args.dotnet, ROOT, source, output, candidate=True)
                    if before[1] != after[1]:
                        raise AssertionError(f"CPE1 runner output differs at {clocks} clocks")
                    if after[0] >= before[0]:
                        raise AssertionError(f"CPE1 recovery was slower at {clocks} clocks")
                    check_progress(after[3], clocks)
                    row.update(CandidateSeconds=round(after[0], 4), ByteParity=True,
                               Epm1ProgressVerified=True)
                print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
