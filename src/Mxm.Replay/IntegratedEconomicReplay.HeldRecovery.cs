using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record HeldDemand(string Symbol,long At,string[] Studies);
    sealed record RecoveryGroup(string Symbol,string Mode,long Session,long From,long Through,long[] Clocks);
    sealed record FrozenCore(LedgerEvent[] Events,Ucp1CurvePoint[] Curve,string Session);
    sealed record FrozenWrapper(string CoreCheckpoint);

    sealed record ValuationRegistryEnvelope(NativeValuationPrefix[] Rows);

    static NativeReusableValuationRegistry? LoadValuationRegistry(string? path)
    {
        if(path is null)return null;
        using var stream=File.OpenRead(path);
        // Deserialize the typed envelope directly: do not retain a multi-million
        // row JSON DOM while allocating the typed rows and building their index.
        var envelope=JsonSerializer.Deserialize<ValuationRegistryEnvelope>(stream,Json);
        if(envelope?.Rows is null)throw new InvalidDataException("VALUATION_REGISTRY_ROWS_REQUIRED");
        return new(envelope.Rows);
    }

    public static int RunHeldRecoveryPlan(string sourcePath,string tapePath,string demandsPath,string output,string? registryPath=null)
    {
        var bytes=File.ReadAllBytes(sourcePath);var input=JsonSerializer.Deserialize<EerInput>(bytes,Json)!;
        var demands=JsonSerializer.Deserialize<HeldDemand[]>(File.ReadAllBytes(demandsPath),Json)!;
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=new(tapePath),HeldRegistry=LoadValuationRegistry(registryPath)};
        var markets=input.Markets.ToDictionary(m=>m.Market.Name,StringComparer.Ordinal);
        var targets=new Dictionary<(string Symbol,string Mode,long Session),HashSet<long>>();
        int resolved=0;var assessments=new List<EerEvidence.HeldMarkReceipt>();
        foreach(var d in demands)
        {
            source.BeginHistoricalClock();
            var mark=source.InspectHeldMark(d.Symbol,d.At);
            if(registryPath is not null)assessments.Add(mark);
            if(mark.EvidenceSha256 is not null){resolved++;continue;}
            if(!markets.TryGetValue(d.Symbol,out var market)||market.Market.DatedDevelopment is not { } terms)continue;
            var names=new HashSet<string>(StringComparer.Ordinal){d.Symbol};
            foreach(var asset in new[]{terms.Contract.QuoteAsset,"USD",terms.Contract.MinimumCommissionAsset}.OfType<string>())
                if(input.Routes.TryGetValue(asset,out var route))foreach(var h in route)names.Add(h.Symbol);
            foreach(var name in names)
            {
                if(source.HasValuationPair(name,d.At))continue;
                bool closed=source.VerifiedClosedNow(name,d.At);
                long session=d.At/900_000L;
                if(closed&&markets[name].ScheduledClocks is { } clocks)
                {int i=Array.BinarySearch(clocks,d.At);i=i<0?~i:i;if(i>0)session=clocks[i-1];else closed=false;}
                var key=(name,closed?"CLOSED_PREFIX":"OPEN_INTERVAL",session);
                if(!targets.TryGetValue(key,out var set))targets.Add(key,set=new());set.Add(d.At);
            }
        }
        var groups=targets.OrderBy(x=>x.Key.Symbol,StringComparer.Ordinal).ThenBy(x=>x.Key.Session).Select(x=>
        {
            long through=x.Value.Max();
            return new RecoveryGroup(x.Key.Symbol,x.Key.Mode,x.Key.Session,
                x.Key.Mode=="CLOSED_PREFIX"?through-345600000L:x.Value.Min()-30_000L,through,x.Value.Order().ToArray());
        }).ToArray();
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{Study="OWNER_HELD_EQUITY_RECOVERY_1",
            SourceSha256=GeneralSha(bytes),DemandSha256=GeneralSha(File.ReadAllBytes(demandsPath)),
            DistinctSymbolClocks=demands.Length,ResolvedBefore=resolved,Groups=groups,Assessments=assessments,
            RegistrySha256=registryPath is null?null:GeneralSha(File.ReadAllBytes(registryPath)),
            Orders=0,CloudActivated=false,OriginalPoliciesReplayed=0},Json));
        return 0;
    }

    // Reprice original event facts only. No policy, signal, training or new fill.
    public static int RunFrozenHeldEquity(string sourcePath,string tapePath,string registryPath,
        string checkpointPath,string originalReport,string id,string output)
    {
        var input=JsonSerializer.Deserialize<EerInput>(File.ReadAllBytes(sourcePath),Json)!;
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=new(tapePath),HeldRegistry=LoadValuationRegistry(registryPath)};
        var wrapper=JsonSerializer.Deserialize<FrozenWrapper>(File.ReadAllBytes(checkpointPath),NativeHistoricalCheckpointJson.Options)!;
        var core=JsonSerializer.Deserialize<FrozenCore>(wrapper.CoreCheckpoint,Json)!;
        using var original=JsonDocument.Parse(File.ReadAllBytes(originalReport));
        decimal stress=original.RootElement.GetProperty("Stress").GetDecimal();
        var book=original.RootElement.GetProperty("CommonBooks").EnumerateArray().Single(b=>b.GetProperty("Id").GetString()==id);
        var points=book.GetProperty("Details").GetProperty("EquityPath").EnumerateArray().ToDictionary(p=>p.GetProperty("At").GetInt64());
        using var savedSession=JsonDocument.Parse(core.Session);
        string sessionPayload=savedSession.RootElement.GetProperty("Payload").GetString()!;
        if(GeneralSha(System.Text.Encoding.UTF8.GetBytes(sessionPayload))!=savedSession.RootElement.GetProperty("Sha256").GetString())
            throw new InvalidDataException("FROZEN_EQUITY_SESSION_HASH");
        using var savedPayload=JsonDocument.Parse(sessionPayload);
        using var savedLedger=JsonDocument.Parse(savedPayload.RootElement.GetProperty("Ledger").GetString()!);
        long staleness=savedLedger.RootElement.GetProperty("MaximumStalenessMs").GetInt64();
        var ledger=new NativeFundedLedger(staleness);int eventIndex=0,unknownBefore=0,unknownAfter=0,recovered=0;
        decimal peak=300m,dd=0m,maxMargin=0m;int newlyMeasurable=0,aboveMargin=0;
        var changes=new List<object>();
        foreach(var p in core.Curve)
        {
            while(eventIndex<core.Events.Length&&core.Events[eventIndex].At<=p.At)ledger.Apply(core.Events[eventIndex++]);
            var saved=points[p.At];var old=ledger.Summary(p.At);
            if(Math.Abs(old.CashEur-p.CashEur)>.00000001m||old.OpenPositions!=p.Held||old.PendingIntents!=p.Pending)
                throw new InvalidDataException("FROZEN_EQUITY_EVENT_CASH_POSITION_PARITY");
            decimal? ceiling=p.FundingCapital?.ConditionalUnmodeledDebitCeilingEur;
            decimal? before=p.FundingCapital?.ConditionalEquityEur;
            if(before is null)unknownBefore++;
            source.BeginHistoricalClock();
            var marks=ledger.PositionSnapshot().Select(x=>x.Symbol).Distinct(StringComparer.Ordinal)
                .Select(name=>source.InspectHeldMark(name,p.At,stress,true).Quote).OfType<LedgerQuote>().ToArray();
            var current=ledger.InspectConditionalValuation(p.At,marks);
            decimal? equity=before??(current.LiquidationEquityEur-ceiling);
            if(equity is null)unknownAfter++;
            else
            {
                peak=Math.Max(peak,equity.Value);dd=Math.Max(dd,1m-equity.Value/peak);
                if(current.UsedMarginEur is decimal margin&&equity>0m)
                {
                    decimal fraction=(margin+(p.FundingCapital?.PendingOpenMarginEur??0m))/equity.Value;
                    maxMargin=Math.Max(maxMargin,fraction);
                    if(before is null){newlyMeasurable++;if(fraction>.7m)aboveMargin++;}
                }
            }
            if(before is null&&equity is not null)
            {recovered++;changes.Add(new{p.At,EquityEur=equity,current.UsedMarginEur,p.Held,p.Pending});}
        }
        while(eventIndex<core.Events.Length)ledger.Apply(core.Events[eventIndex++]);
        var expected=book.GetProperty("Result");var final=ledger.Summary();
        if(final.EventChainHash!=expected.GetProperty("EventChainHash").GetString()||
            Math.Abs(final.CashEur-expected.GetProperty("CashEur").GetDecimal())>.00000001m)
            throw new InvalidDataException("FROZEN_EQUITY_FINAL_CHAIN_PARITY");
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{Study="OWNER_HELD_EQUITY_RECOVERY_1",Id=id,
            stress,OriginalReportSha256=GeneralSha(File.ReadAllBytes(originalReport)),CheckpointSha256=GeneralSha(File.ReadAllBytes(checkpointPath)),
            RegistrySha256=GeneralSha(File.ReadAllBytes(registryPath)),OriginalEquityPoints=core.Curve.Length,
            UnknownBefore=unknownBefore,UnknownAfter=unknownAfter,RecoveredEquityPoints=recovered,
            NewlyMeasurableMarginPoints=newlyMeasurable,NewlyObservedMarginAbove70Percent=aboveMargin,
            MaximumMeasuredHeldPendingMarginFraction=maxMargin,SampledDrawdownWithRecoveredMarks=dd,
            final.CashEur,final.EventChainHash,NewAdmissions=0,AdmissionPolicyReevaluated=false,
            OriginalPoliciesReplayed=0,Orders=0,CloudActivated=false,ContinuousDrawdownCertified=false,Changes=changes},Json));
        return 0;
    }
}
