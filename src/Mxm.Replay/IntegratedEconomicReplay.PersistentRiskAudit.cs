using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    static object PersistentRiskFacts(string id,LedgerEvent[] events,Ucp1CurvePoint[] curve)
    {
        long? Preventive()=>curve.FirstOrDefault(x=>x.FundingCapital?.MaximumSampledFundingAdjustedDrawdown>=.28m)?.At;
        long? Hard()=>curve.FirstOrDefault(x=>x.FundingCapital?.MaximumSampledFundingAdjustedDrawdown>=.30m)?.At;
        long? preventive=Preventive(),hard=Hard();
        var rows=events.Where(e=>e.Kind=="OPEN_FILL").Select(open=>
        {
            var own=events.Where(e=>e.PositionId==open.PositionId).OrderBy(e=>e.At).ToArray();
            decimal closedUnits=0m;LedgerEvent? close=null;
            foreach(var fill in own.Where(e=>e.Kind=="CLOSE_FILL"))
            {closedUnits+=fill.Units;if(closedUnits>=open.Units){close=fill;break;}}
            var decisions=own.Where(e=>e.Kind is "REQUEST_CLOSE" or "MODEL_NATIVE_STOP_TRIGGER").ToArray();
            var request=decisions.LastOrDefault(e=>close is null||e.At<close.At);
            var expired=own.Where(e=>e.Kind=="MODEL_CLOSE_INTENT_EXPIRED").Select(e=>e.At).ToArray();
            bool exposedAtPreventive=preventive.HasValue&&open.At<=preventive&&
                (close is null||close.At>preventive);
            long? quoteAt=request is null?null:events.Where(e=>e.At>request.At&&e.At>=request.At+request.LatencyMs&&
                e.Quotes.Any(q=>q.Symbol==open.Symbol&&q.At==e.At&&q.Bid>0m&&q.Ask>=q.Bid)).Select(e=>(long?)e.At).FirstOrDefault();
            return new{open.PositionId,open.Symbol,OpenAt=open.At,ExposedAtFirstPreventive=exposedAtPreventive,
                FirstCloseDecisionAt=decisions.FirstOrDefault()?.At,
                CloseDecisions=decisions.Select(e=>new{e.At,e.Kind,e.Reason,e.Units,e.LatencyMs}),
                CloseFillFragments=own.Where(e=>e.Kind=="CLOSE_FILL").Select(e=>new{e.At,e.Units}),
                CloseDecisionAt=request?.At,CloseDecisionKind=request?.Kind,CloseDecisionReason=request?.Reason,
                RequestedLatencyMs=request?.LatencyMs,ExpiredIntentClocks=expired,FirstLaterObservedQuoteAt=quoteAt,
                CloseFillAt=close?.At,ObservedDecisionToFillMs=request is null||close is null?(long?)null:close.At-request.At,
                ObservedDecisionToQuoteMs=request is null||quoteAt is null?(long?)null:quoteAt-request.At,
                Diagnosis=request is null?"NO_CLOSE_DECISION":expired.Length>0?"INTENT_EXPIRATION_OBSERVED":
                    close is null&&quoteAt is null?"NO_LATER_EXECUTABLE_SIDE_OBSERVED":
                    close is null?"QUOTE_OBSERVED_FILL_NOT_ESTABLISHED":"MODELED_FILL_OBSERVED"};
        }).ToArray();
        return new{Id=id,FirstPreventiveAt=preventive,FirstHardAt=hard,
            PreventiveToHardMs=preventive.HasValue&&hard.HasValue?hard-preventive:null,
            UnknownWithExposure=curve.Count(x=>x.Held>0&&x.FundingCapital?.ConditionalEquityEur is null),
            MaximumSampledDrawdown=curve.Select(x=>x.FundingCapital?.MaximumSampledFundingAdjustedDrawdown).Max(),
            Positions=rows,ContinuousDrawdownCertified=false,BrokerFillCertified=false};
    }
    static void WritePersistentRiskAudit((string Id,NativeUnifiedPortfolioEngine Book)[] books,string directory)
        =>File.WriteAllBytes(Path.Combine(directory,"persistent-risk-audit.json"),JsonSerializer.SerializeToUtf8Bytes(
            books.Select(c=>PersistentRiskFacts(c.Id,c.Book.OriginalModelEvents,c.Book.CommonBookEquityPath)),Json));

    public static int CheckPersistentRiskAudit()
    {
        LedgerEvent E(string kind,long at,decimal units=1m)=>new(kind+at,at,kind,"P","SYNTHETIC",1,units,
            1m,0m,1m,0m,at-1,at-2,100,"SYNTHETIC_AUDIT_FIXTURE",new string('a',64),Array.Empty<LedgerQuote>());
        var curve=new[]{new Ucp1CurvePoint(1000,220m,220m,1m,1,0,0)
            {FundingCapital=new NativeFundingCapital(0m,0,0,0m,220m,1m,0m,219m,0m,.28m){ConditionalEquityEur=220m}}};
        var events=new[]{E("OPEN_FILL",100,2m),E("REQUEST_CLOSE",200),E("CLOSE_FILL",400),
            E("REQUEST_CLOSE",1500),E("CLOSE_FILL",2000)};
        var partial=JsonSerializer.SerializeToElement(PersistentRiskFacts("SYNTHETIC",events,curve),Json)
            .GetProperty("Positions")[0];
        if(!partial.GetProperty("ExposedAtFirstPreventive").GetBoolean()||
            partial.GetProperty("CloseFillAt").GetInt64()!=2000||partial.GetProperty("CloseDecisionAt").GetInt64()!=1500)
            throw new InvalidDataException("RISK_AUDIT_PARTIAL_CLOSE_NOT_FULL_EXIT");
        var remaining=JsonSerializer.SerializeToElement(PersistentRiskFacts("SYNTHETIC",events[..3],curve),Json)
            .GetProperty("Positions")[0];
        if(!remaining.GetProperty("ExposedAtFirstPreventive").GetBoolean()||
            remaining.GetProperty("CloseFillAt").ValueKind!=JsonValueKind.Null)
            throw new InvalidDataException("RISK_AUDIT_REMAINING_EXPOSURE");
        Console.WriteLine("PERSISTENT_RISK_AUDIT_CHECKS_PASS synthetic partial/full close attribution");return 0;
    }

    public static int RunPersistentRiskAudit(string checkpoint,string id,string output)
    {
        var wrapper=JsonSerializer.Deserialize<FrozenWrapper>(File.ReadAllBytes(checkpoint),NativeHistoricalCheckpointJson.Options)
            ??throw new InvalidDataException("RISK_AUDIT_WRAPPER");
        var core=JsonSerializer.Deserialize<FrozenCore>(wrapper.CoreCheckpoint,Json)
            ??throw new InvalidDataException("RISK_AUDIT_CORE");
        using var saved=JsonDocument.Parse(core.Session);
        string payload=saved.RootElement.GetProperty("Payload").GetString()!;
        if(GeneralSha(System.Text.Encoding.UTF8.GetBytes(payload))!=saved.RootElement.GetProperty("Sha256").GetString())
            throw new InvalidDataException("RISK_AUDIT_SESSION_HASH");
        using var session=JsonDocument.Parse(payload);
        string raw=session.RootElement.GetProperty("Ledger").GetString()!;
        var restored=NativeFundedLedger.Restore(raw);
        using var stored=JsonDocument.Parse(raw);
        var ledger=new NativeFundedLedger(stored.RootElement.GetProperty("MaximumStalenessMs").GetInt64());
        foreach(var e in core.Events)ledger.Apply(e);
        if(ledger.Summary().EventChainHash!=restored.Summary().EventChainHash)
            throw new InvalidDataException("RISK_AUDIT_EVENT_CHAIN");
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{Study="OWNER_PERSISTENT_RISK_FACT_AUDIT_1",
            CheckpointSha256=FactorialFileSha(checkpoint),ledger.Summary().EventChainHash,
            EventChainVerified=true,Facts=PersistentRiskFacts(id,core.Events,core.Curve),
            OriginalPoliciesReplayed=0,Orders=0,CloudActivated=false},Json));
        return 0;
    }
}
