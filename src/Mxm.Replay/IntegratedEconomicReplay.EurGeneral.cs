using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    const string GeneralEurProtocol = "244ae44bffd5129239d55f9a6b36a0cda882b7adee1fd3ead0491c0c45a3ba9b";
    static long GeneralEurUtc(int year, int month, int day) =>
        new DateTimeOffset(year, month, day, 0, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();
    static readonly long GeneralFitStart = GeneralEurUtc(2026, 11, 30);
    static readonly long GeneralFitEnd = GeneralEurUtc(2027, 1, 25);
    static readonly long GeneralComparisonEnd = GeneralEurUtc(2027, 3, 22);
    static readonly long GeneralConfirmationEnd = GeneralEurUtc(2027, 5, 17);
    static readonly string[] GeneralPolicies =
    {
        NativeUnifiedPortfolioEngine.EurGeneralSelect, NativeUnifiedPortfolioEngine.EurGeneralPooled,
        NativeUnifiedPortfolioEngine.EurGeneralProbe, NativeUnifiedPortfolioEngine.EurGeneralCash
    };
    sealed record GeneralEurFrozen(string ProtocolSha256, string ComparisonReportSha256,
        Dictionary<string,string> CalibrationHashes);

    public static int RunGeneralEur(string phase, string sourcePath, string reportPath, string models)
    {
        if (phase is not ("comparison" or "confirmation"))
            throw new ArgumentException("GENERAL_EUR_REGISTERED_PHASE");
        if (File.Exists(reportPath)) throw new IOException("GENERAL_EUR_REPORT_ALREADY_EXISTS");
        bool fit = phase == "comparison";
        var frozen = fit ? null : ReadFrozenGeneralModel(models);
        var raw = File.ReadAllBytes(sourcePath);
        var input = JsonSerializer.Deserialize<EerInput>(raw, Json)
            ?? throw new ArgumentException("GENERAL_EUR_SOURCE_INPUT_REQUIRED");
        if (input.Start != (fit ? GeneralFitStart : GeneralComparisonEnd) ||
            input.FitEnd != (fit ? GeneralFitEnd : GeneralComparisonEnd) ||
            input.End != (fit ? GeneralComparisonEnd : GeneralConfirmationEnd) ||
            input.ProtocolSha256 != GeneralEurProtocol || input.SourceAcquiredAt < input.End ||
            !GeneralDigestShape(input.EngineRevision, 40) || !GeneralDigestShape(input.EvidenceManifestSha256, 64) ||
            input.Markets.Length == 0 || input.Markets.Any(m => m.CalendarStatus is null ||
                !VerifiedGrid(m.ScheduledClocks) || !VerifiedGrid(m.AmbiguousCalendarClocks) ||
                (m.ScheduledClocks ?? Array.Empty<long>()).Intersect(m.AmbiguousCalendarClocks ?? Array.Empty<long>()).Any() ||
                m.Market.DatedDevelopment?.Contract.OriginalBrokerAuthenticated != true))
            throw new ArgumentException("GENERAL_EUR_SOURCE_OR_PROTOCOL_BINDING");
        if (fit)
        {
            if (Directory.Exists(models) && Directory.EnumerateFileSystemEntries(models).Any())
                throw new IOException("GENERAL_EUR_MODEL_DIRECTORY_NOT_EMPTY");
            Directory.CreateDirectory(models);
        }

        var source = new EerEvidence(input);
        var reports = new List<object>();
        var hashes = new Dictionary<string,string>(StringComparer.Ordinal);
        foreach (decimal stress in new[] { 0m, .5m, 1m })
        {
            string code = stress == 0m ? "S0" : stress == .5m ? "S1" : "S2";
            string scenario = EerHash(GeneralEurProtocol + "|" + code);
            var streams = input.Markets.ToDictionary(m => m.Market.Name, m => new EerStream(m), StringComparer.Ordinal);
            void Observe(long from, long to, NativeUnifiedPortfolioEngine[] books, string subphase)
            {
                for (long day = from; day < to; day += 86_400_000L)
                {
                    for (long at = day + EurOffset; at < day + 86_400_000L; at += EurStep)
                    {
                        var observed = streams.Values.Select(s => source.Frame(s, at, scenario, stress, general:true))
                            .OfType<Ucp1MarketFrame>().ToArray();
                        var frame = new Ucp1Frame(at, observed);
                        foreach (var book in books) source.Advance(book, frame, streams, scenario, stress);
                    }
                    Console.WriteLine($"GENERAL_EUR {code} {subphase} {DateTimeOffset.FromUnixTimeMilliseconds(day):yyyy-MM-dd} complete");
                }
            }
            var modelPath = Path.Combine(models, code + "-calibration.json");
            NativeEurCalibration calibration;
            object? fitting = null;
            if (fit)
            {
                var probe = new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe, fundingScenarioId:scenario);
                Observe(input.Start, input.FitEnd, new[] { probe }, "FIT");
                calibration = probe.ExportEurCalibration();
                var modelBytes = JsonSerializer.SerializeToUtf8Bytes(calibration, Json);
                File.WriteAllBytes(modelPath, modelBytes);
                hashes[code] = GeneralSha(modelBytes);
                fitting = GeneralEurBook(probe, streams, input.Start, input.FitEnd, calibration);
            }
            else
            {
                byte[] modelBytes = File.ReadAllBytes(modelPath);
                if (frozen!.CalibrationHashes.GetValueOrDefault(code) != GeneralSha(modelBytes))
                    throw new ArgumentException("GENERAL_EUR_FROZEN_CALIBRATION_SHA");
                calibration = JsonSerializer.Deserialize<NativeEurCalibration>(modelBytes, Json)
                    ?? throw new ArgumentException("GENERAL_EUR_CALIBRATION");
                if (calibration.ObservationThrough >= GeneralFitEnd)
                    throw new ArgumentException("GENERAL_EUR_CALIBRATION_OUTSIDE_FIT");
            }

            var comparison = GeneralPolicies.Select(name => new NativeUnifiedPortfolioEngine(name, fundingScenarioId:scenario)).ToArray();
            comparison[0].LoadEurCalibration(calibration);
            comparison[1].LoadEurCalibration(calibration);
            Observe(input.FitEnd, input.End, comparison, phase);
            reports.Add(new {Scenario=code, SlippageSpreadPerSide=stress, CommissionAndDebitMultiple=1m+stress,
                Fitting=fitting, Books=comparison.Select(b => GeneralEurBook(b, streams, input.FitEnd, input.End, null)).ToArray(),
                Calendar=streams.Values.Select(s => new {s.Source.Market.Name,s.Source.CalendarStatus,s.Counts}).ToArray()});
        }

        var report = JsonSerializer.SerializeToUtf8Bytes(new
        {
            Phase=phase, ProtocolSha256=GeneralEurProtocol, SourceSha256=GeneralSha(raw), input.EvidenceManifestSha256,
            input.EngineRevision, input.Start, input.FitEnd, input.End, Results=reports, CapitalEur=300m,
            SameEngineReplicaOnly=true, IndependentConfirmationCertified=false, ContinuousDrawdownCertified=false,
            BrokerNetCertified=false, Orders=0, CloudActivated=false
        }, Json);
        File.WriteAllBytes(reportPath, report);
        if (fit)
        {
            File.WriteAllBytes(Path.Combine(models, "comparison.json"), report);
            File.WriteAllBytes(Path.Combine(models, "frozen-models.json"),
                JsonSerializer.SerializeToUtf8Bytes(new GeneralEurFrozen(GeneralEurProtocol, GeneralSha(report), hashes), Json));
        }
        return 0;
    }

    static bool VerifiedGrid(long[]? clocks) => clocks is null ||
        clocks.Select((t, i) => t > 0L && t % EurStep == EurOffset && (i == 0 || t > clocks[i - 1])).All(x => x);
    static bool GeneralDigestShape(string value, int length) => value is not null && value.Length == length && value.All(Uri.IsHexDigit);
    static string GeneralSha(byte[] raw) => Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant();

    static GeneralEurFrozen ReadFrozenGeneralModel(string models)
    {
        var frozen = JsonSerializer.Deserialize<GeneralEurFrozen>(File.ReadAllBytes(Path.Combine(models, "frozen-models.json")), Json);
        if (frozen is null || frozen.ProtocolSha256 != GeneralEurProtocol || frozen.CalibrationHashes.Count != 3 ||
            frozen.ComparisonReportSha256 != GeneralSha(File.ReadAllBytes(Path.Combine(models, "comparison.json"))))
            throw new ArgumentException("GENERAL_EUR_COMPARISON_RECEIPT_MISMATCH");
        return frozen;
    }

    static object GeneralEurBook(NativeUnifiedPortfolioEngine engine, Dictionary<string,EerStream> streams,
        long from, long through, NativeEurCalibration? calibration)
    {
        var trips = engine.CompleteModelTrips;
        var facts = engine.OriginalModelEvents.Where(e => e.Kind != "MARK")
            .ToLookup(e => e.PositionId, StringComparer.Ordinal);
        var reconciled = engine.ReconciledModelEpisodes.ToDictionary(x => x.PositionId, StringComparer.Ordinal);
        var openings = engine.EurOpportunityReceipts.Where(x => x.Decision is "LONG_PENDING" or "SHORT_PENDING")
            .ToDictionary(x => (x.At, x.Symbol, x.Family, x.Side));
        var weeks = Enumerable.Range(0, (int)((through-from)/604_800_000L)).Select(i =>
        {
            long start = from + i * 604_800_000L;
            var closed = trips.Where(t => t.CloseAt >= start && t.CloseAt < start + 604_800_000L).ToArray();
            int unknown = closed.Count(x => !reconciled.ContainsKey(x.PositionId));
            return new {Week=Week(start), RoundTrips=closed.Length, Hard21=closed.Length>=21,
                GrossEur=closed.Sum(x => x.GrossEur),
                ReconciledNetEur=unknown==0?closed.Sum(x => reconciled[x.PositionId].Evidence.ClosedNetEur):(decimal?)null,
                Unreconciled=unknown};
        }).ToArray();
        return new
        {
            Ledger=EerBook(engine.PolicyName,engine,from,through,calibration,streams),
            Weeks=weeks,
            FullWeeksMeetHard21=weeks.All(w=>w.Hard21),
            Episodes=trips.Select(t =>
            {
                var entry = t.EconomicEntry;
                var offer = entry is null ? null : openings.GetValueOrDefault((entry.DecisionAt,t.Symbol,t.Family,t.Side));
                var market = streams[t.Symbol].Source.Market;
                var contract = market.DatedDevelopment!.Contract;
                var closes = facts[t.PositionId].Where(e=>e.Kind=="CLOSE_FILL").ToArray();
                var open = facts[t.PositionId].Single(e=>e.Kind=="OPEN_FILL");
                return new
                {
                    t.PositionId,t.Symbol,t.Family,t.Side,t.Units,t.OpenAt,t.CloseAt,t.ExitReason,t.CrossedUnknownHistory,
                    contract.LotUnits,contract.MinimumUnits,contract.VolumeStepUnits,contract.QuoteAsset,
                    AdmissionRiskEur=offer?.ReservedRiskEur,FillRiskEur=t.EntryRiskEur,
                    StopAtAdmission=offer?.ProtectiveStop,TargetAtAdmission=offer?.PriceTarget,
                    EntryPrice=open.ExecutionPrice,
                    FillMarginEur=entry?.ReservedMarginEur,DisplacedAlternativeEur=offer?.DisplacedAlternativeEur,
                    t.GrossEur,NetEur=reconciled.GetValueOrDefault(t.PositionId)?.Evidence.ClosedNetEur,
                    GrossR=t.EconomicEvidence?.RealizedGrossR,
                    NetR=reconciled.GetValueOrDefault(t.PositionId)?.Evidence.RealizedNetR,
                    CommissionsEur=t.Integrated?.CommissionsEur,SpreadEur=t.Integrated?.SpreadEur,
                    SlippageEur=t.Integrated?.SlippageEur,ConversionEur=t.Integrated?.ConversionEur,
                    FundingEur=facts[t.PositionId].Where(e=>e.Kind is "FINANCING" or "CLOSED_FUNDING_SETTLEMENT")
                        .Sum(x=>x.SignedFinancingEur),
                    ClosedParts=closes.Select(x=>new {x.At,x.ExecutionPrice,x.Units,x.Reason}).ToArray()
                };
            }).ToArray()
        };
    }
}
