using System.Text.Json;
using Mxm.Core;
internal static partial class IntegratedEconomicReplay
{
    // Read-only reduction of immutable ledger facts. No policy evaluation.
    public static int RunFrozenDrawdownAudit(string checkpoint,string reportPath,string id,string output)
    {
        using var report=JsonDocument.Parse(File.ReadAllBytes(reportPath));
        var root=report.RootElement;
        if(root.GetProperty("Study").GetString()!="MONETARY_MANAGEMENT_FACTORIAL_1"||
            root.GetProperty("Stress").GetDecimal()!=.5m||id!="CENTERED_CONTROL")
            throw new InvalidDataException("FROZEN_DD_SCOPE");
        var book=root.GetProperty("CommonBooks").EnumerateArray().Single(x=>x.GetProperty("Id").GetString()==id);
        var expected=book.GetProperty("Result");
        var wrapper=JsonSerializer.Deserialize<FrozenWrapper>(File.ReadAllBytes(checkpoint),NativeHistoricalCheckpointJson.Options)
            ??throw new InvalidDataException("FROZEN_DD_WRAPPER");
        var core=JsonSerializer.Deserialize<FrozenCore>(wrapper.CoreCheckpoint,Json)
            ??throw new InvalidDataException("FROZEN_DD_CORE");
        using var savedSession=JsonDocument.Parse(core.Session);
        string payload=savedSession.RootElement.GetProperty("Payload").GetString()!;
        if(GeneralSha(System.Text.Encoding.UTF8.GetBytes(payload))!=savedSession.RootElement.GetProperty("Sha256").GetString())
            throw new InvalidDataException("FROZEN_DD_SESSION_HASH");
        using var session=JsonDocument.Parse(payload);
        string raw=session.RootElement.GetProperty("Ledger").GetString()!;
        using var stored=JsonDocument.Parse(raw);
        var ledger=new NativeFundedLedger(stored.RootElement.GetProperty("MaximumStalenessMs").GetInt64());
        var curve=core.Curve;
        var published=book.GetProperty("Details").GetProperty("EquityPath").EnumerateArray().ToArray();
        if(published.Length!=curve.Length||curve.Length==0)throw new InvalidDataException("FROZEN_DD_CURVE_COUNT");
        decimal? DD(Ucp1CurvePoint x)=>x.FundingCapital?.MaximumSampledFundingAdjustedDrawdown;
        decimal? Eq(Ucp1CurvePoint x)=>x.FundingCapital?.ConditionalEquityEur;
        long preventive=curve.First(x=>DD(x)>=.28m).At,hard=curve.First(x=>DD(x)>=.30m).At;
        var worst=curve.Where(x=>Eq(x).HasValue).OrderBy(x=>Eq(x)).First();
        var admissions=book.GetProperty("Details").GetProperty("Admissions").EnumerateArray().ToArray();
        var episodes=book.GetProperty("Details").GetProperty("Episodes").EnumerateArray().ToArray();
        var observed=new List<object>();int index=0,unknown=0,exposed=0;
        decimal maxMargin=0;int maxHeld=0,maxPending=0;long? firstUnknown=null;
        for(int i=0;i<curve.Length;i++)
        {
            var point=curve[i];var p=published[i];
            decimal? P(string field)=>p.GetProperty(field).ValueKind==JsonValueKind.Null?null:p.GetProperty(field).GetDecimal();
            if(p.GetProperty("At").GetInt64()!=point.At||P("EquityEur")!=Eq(point)||P("CashEur")!=point.CashEur||
                P("Drawdown")!=DD(point)||p.GetProperty("Held").GetInt32()!=point.Held||
                p.GetProperty("Pending").GetInt32()!=point.Pending)
                throw new InvalidDataException("FROZEN_DD_PUBLIC_CURVE_PARITY");
            while(index<core.Events.Length&&core.Events[index].At<=point.At)ledger.Apply(core.Events[index++]);
            var state=ledger.Summary(point.At);
            if(Math.Abs(state.CashEur-point.CashEur)>.00000001m||state.OpenPositions!=point.Held||state.PendingIntents!=point.Pending)
                throw new InvalidDataException("FROZEN_DD_LEDGER_STATE_PARITY");
            if(Eq(point) is not decimal equity)
            {unknown++;if(point.Held>0){exposed++;firstUnknown??=point.At;}}
            else if(equity>0&&point.UsedMarginEur.HasValue&&point.FundingCapital?.PendingOpenMarginEur is decimal pending)
                maxMargin=Math.Max(maxMargin,(point.UsedMarginEur.Value+pending)/equity);
            maxHeld=Math.Max(maxHeld,point.Held);maxPending=Math.Max(maxPending,point.Pending);
            if(point.At==preventive||point.At==hard||point.At==worst.At||point.At==curve[^1].At||point.At==firstUnknown)
            {
                var positions=ledger.PositionSnapshot();
                var intents=ledger.PendingSnapshot();
                var related=positions.Select(x=>x.Id).Concat(intents.Select(x=>x.PositionId)).ToHashSet(StringComparer.Ordinal);
                observed.Add(new {point.At,point.CashEur,EquityEur=Eq(point),Drawdown=DD(point),
                    state.ObservedPeakEur,point.UsedMarginEur,point.Held,point.Pending,
                    Positions=positions.Select(x=>new{x.Id,x.Symbol,x.Side,x.Units,x.EntryAt,x.EntryPrice,x.MarginPerUnit}),
                    PendingIntents=intents.Select(x=>new{x.PositionId,x.Kind,x.Reason,x.At,x.LatencyMs,x.Units}),
                    Admissions=admissions.Where(a=>related.Contains(a.GetProperty("PositionId").GetString()!)),
                    ReservesOfCompletedEpisodes=episodes.Where(a=>related.Contains(a.GetProperty("PositionId").GetString()!))
                });
            }
        }
        if(index!=core.Events.Length)throw new InvalidDataException("FROZEN_DD_EVENT_COUNT");
        var final=ledger.Summary(curve[^1].At);var restored=NativeFundedLedger.Restore(raw).Summary();
        if(final.EventChainHash!=restored.EventChainHash||final.EventChainHash!=expected.GetProperty("EventChainHash").GetString()||
            Math.Abs(final.CashEur-expected.GetProperty("CashEur").GetDecimal())>.00000001m||
            final.OpenPositions!=expected.GetProperty("OpenPositions").GetInt32())
            throw new InvalidDataException("FROZEN_DD_TERMINAL_CHAIN");
        var openIds=ledger.PositionSnapshot().Select(x=>x.Id).ToHashSet(StringComparer.Ordinal);
        var lifecycle=core.Events.Where(e=>openIds.Contains(e.PositionId)&&e.Kind!="MARK")
            .Select(e=>new{e.At,e.Kind,e.PositionId,e.Symbol,e.Side,e.Units,e.ExecutionPrice,e.LatencyMs,e.Reason,e.AvailableAt,e.CalibratedThrough}).ToArray();
        var fills=core.Events.Where(e=>e.Kind=="CLOSE_FILL").ToArray();
        var requests=core.Events.Where(e=>e.Kind is "REQUEST_CLOSE" or "MODEL_NATIVE_STOP_TRIGGER").GroupBy(e=>e.PositionId)
            .ToDictionary(g=>g.Key,g=>g.OrderBy(e=>e.At).ToArray(),StringComparer.Ordinal);
        var latency=fills.Select(f=>{
            var request=requests.GetValueOrDefault(f.PositionId)?.LastOrDefault(e=>e.At<f.At);
            return new{f.PositionId,FillAt=f.At,RequestAt=request?.At,RequestKind=request?.Kind,
                RequestLatencyMs=request?.LatencyMs,ObservedElapsedMs=request is null?(long?)null:f.At-request.At};
        }).ToArray();
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{
            Study="OWNER_FROZEN_DD_AUDIT_1",CheckpointSha256=FactorialFileSha(checkpoint),ReportSha256=FactorialFileSha(reportPath),
            final.EventChainHash,FirstPreventiveAt=preventive,FirstHardAt=hard,WorstEquityAt=worst.At,PreventiveToHardMs=hard-preventive,
            SampledDrawdown=expected.GetProperty("SampledDrawdown").GetDecimal(),UnknownEquityClocks=unknown,
            UnknownWithExposure=exposed,MaxHeld=maxHeld,MaxPending=maxPending,MaxSampledHeldPendingMarginFraction=maxMargin,
            Observations=observed,TerminalOpenLifecycle=lifecycle,CloseFillLatencies=latency,
            NativeStopTriggers=core.Events.Count(e=>e.Kind=="MODEL_NATIVE_STOP_TRIGGER"),CurveAndEventChainVerified=true,
            OriginalPoliciesReplayed=0,OriginalResultsModified=false,ContinuousDrawdownCertified=false,Orders=0,CloudActivated=false
        },Json));
        return 0;
    }
}
