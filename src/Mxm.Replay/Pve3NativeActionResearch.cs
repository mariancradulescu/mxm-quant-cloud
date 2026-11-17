using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

// New bounded PVE3 distributional decision adapter. All funding, selection,
// risk and settlements remain in the EXISTING native C# core. No trade API.
internal static class Pve3NativeActionResearch
{
    const long M5=300000,H=3600000,Week=7*24*H;
    internal sealed record Offer(long At,string Symbol,string Variant,long CalibratedThrough,
        decimal CentralLong,decimal CentralShort,decimal AdverseLong,decimal AdverseShort,
        decimal[] RiskEur,decimal[][] ScenarioNetEur,decimal[] ActionScore);
    internal sealed record Terms(string Symbol,decimal MinimumUnits,decimal StepUnits,
        int SwapMinute,bool FundingKnown,decimal LongDailyDebitBps,decimal ShortDailyDebitBps);
    internal sealed record Input(long Start,long End,string Scenario,LedgerQuote[] Quotes,
        Terms[] Contracts,Offer[] Offers);
    private sealed record Held(string Id,string Symbol,int Side,decimal Units,decimal Risk,
        decimal Margin,long RequestAt,long OpenedAt=0,long CloseRequestedAt=0,long FinanceThrough=0);
    static readonly JsonSerializerOptions Options=new(){PropertyNameCaseInsensitive=true};
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static decimal Fee(LedgerQuote q,decimal u)=>Math.Max(q.ExitFeePerUnit*u,q.ExitFeeFloor);
    static int Cross(long a,long b,int minute)=>(int)Math.Max(0,(b-minute*60000L)/(24*H)-(a-minute*60000L)/(24*H));
    static string WeekIso(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return System.Globalization.ISOWeek.GetYear(d)+"-W"+System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");}
    static object Book(Input x,string variant,
        SortedDictionary<long,Dictionary<string,LedgerQuote>> marks,
        Dictionary<long,Offer[]> offers)
    {
        var session=new NativeFundedSession("PVE3_"+variant+"_"+x.Scenario);
        var terms=x.Contracts.ToDictionary(q=>q.Symbol,StringComparer.Ordinal);
        var held=new Dictionary<string,Held>(StringComparer.Ordinal);
        var rejections=new Dictionary<string,int>(StringComparer.Ordinal);
        var risks=new List<NativeEntryRisk>();
        var snap=new List<NativeEconomicMark>();
        var offered=new List<object>();
        int sequence=0,calls=0,missingHeld=0,delay=0,cancelled=0,maxActive=0;
        void Count(string s)=>rejections[s]=rejections.GetValueOrDefault(s)+1;
        LedgerEvent Fact(long at,string kind,Held? p=null,decimal price=0,decimal fee=0,
            decimal margin=0,LedgerQuote[]? qs=null,decimal financing=0)
        {
            var id="PVE3/"+variant+"/"+x.Scenario+"/"+(++sequence);
            return new LedgerEvent(id,at,kind,p?.Id??"",p?.Symbol??"",p?.Side??0,p?.Units??0,
                price,fee,margin,0,0,0,1,
                "PVE3_ORIGINAL_BAR_CURRENT_TARIFF_CONDITIONAL_MODEL",Hash(id),
                qs??Array.Empty<LedgerQuote>(),financing);
        }
        void Apply(LedgerEvent e)=>session.Ledger.Apply(e);
        foreach(var point in marks)
        {
            long t=point.Key;var qs=point.Value;
            var available=offers.GetValueOrDefault(t+1,Array.Empty<Offer>())
                .Where(o=>o.Variant==variant && terms.ContainsKey(o.Symbol) && qs.ContainsKey(o.Symbol)).ToArray();
            if(held.Count==0 && available.Length==0)continue;
            Apply(Fact(t,"MARK",qs:qs.Values.ToArray()));
            foreach(var p in held.Values.OrderBy(p=>p.Id,StringComparer.Ordinal).ToArray())
            {
                if(!qs.TryGetValue(p.Symbol,out var q)){missingHeld++;continue;}
                var term=terms[p.Symbol];
                if(p.OpenedAt==0)
                {
                    if(t<=p.RequestAt)continue;
                    if(t-p.RequestAt>M5)
                    {Apply(Fact(t,"CONFIRMED_CANCEL",p));held.Remove(p.Id);cancelled++;continue;}
                    try
                    {
                        Apply(Fact(t,"OPEN_FILL",p,p.Side>0?q.Ask:q.Bid,Fee(q,p.Units),q.MarginPerUnit));
                        held[p.Id]=p with{OpenedAt=t,FinanceThrough=t,Margin=q.MarginPerUnit};
                    }
                    catch(InvalidOperationException e) when(e.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL")
                    {Apply(Fact(t,"CONFIRMED_CANCEL",p));held.Remove(p.Id);cancelled++;}
                    continue;
                }
                int crossings=Cross(p.FinanceThrough,t,term.SwapMinute);
                if(crossings>0)
                {
                    if(!term.FundingKnown){Count("UNKNOWN_FUNDING_RETAIN_OPEN");continue;}
                    decimal debit=p.Side>0?term.LongDailyDebitBps:term.ShortDailyDebitBps;
                    Apply(Fact(t,"FINANCING",p,financing:-3m*crossings*debit*p.Units*q.Bid*q.EurDebit/10000m));
                }
                var current=p with{FinanceThrough=t};held[p.Id]=current;
                if(p.CloseRequestedAt>0 && t>p.CloseRequestedAt)
                {
                    if(t>p.OpenedAt+H)delay++;
                    Apply(Fact(t,"CLOSE_FILL",current,p.Side>0?q.Bid:q.Ask,Fee(q,p.Units),q.MarginPerUnit));
                    held.Remove(p.Id);
                }
                else if(t>=p.OpenedAt+H-M5)
                {
                    Apply(Fact(t,"REQUEST_CLOSE",current));
                    held[p.Id]=current with{CloseRequestedAt=t};
                }
            }
            var summary=session.Ledger.Summary(t);
            snap.Add(new NativeEconomicMark(t,summary.LiquidationEquityEur,summary.UsedMarginEur,
                summary.FreeMarginEur,summary.OpenPositions,
                !summary.HistoryEvidenceIncomplete && summary.LiquidationEquityEur.HasValue));
            maxActive=Math.Max(maxActive,summary.OpenPositions);
            if(available.Length==0 || variant=="CASH" || t+1>=x.End)continue;
            if(held.Values.Any(p=>!qs.ContainsKey(p.Symbol)))
            {Count("MISSING_EXISTING_MARK");continue;}
            if(summary.LiquidationEquityEur is not decimal eq || summary.FreeMarginEur is not decimal free)
            {Count("UNKNOWN_EQUITY_OR_MARGIN");continue;}
            long calibrated=available.Max(o=>o.CalibratedThrough);
            if(calibrated>=t-4*H)throw new InvalidOperationException("PVE3_CAUSAL_EMBARGO");
            var states=Enumerable.Range(0,16)
                .Select(i=>new PortfolioScenario("PVE3_TAIL_"+i,calibrated,true,0,0,0,0)).ToArray();
            var opts=new List<EconomicOpportunity>();
            var lookup=new Dictionary<string,(Offer,int,decimal)>();
            foreach(var o in available.OrderBy(z=>z.Symbol,StringComparer.Ordinal))
            {
                if(held.Values.Any(p=>p.Symbol==o.Symbol))continue;
                if(o.RiskEur.Length!=2 || o.ActionScore.Length!=2 ||
                   o.ScenarioNetEur.Length!=2 || o.ScenarioNetEur.Any(v=>v.Length!=16))
                    throw new InvalidOperationException("PVE3_INCONSISTENT_FORECAST_SCENARIOS");
                var c=terms[o.Symbol];var q=qs[o.Symbol];
                for(int j=0;j<2;j++)
                {
                    int side=j==0?1:-1;
                    if(o.ActionScore[j]<=0){Count("PVE3_CASH_BEATS_RISK_ADJUSTED_ACTION");continue;}
                    if(!c.FundingKnown && Cross(t,t+M5+H,c.SwapMinute)>0)
                    {Count("UNKNOWN_PRETRADE_FINANCING");continue;}
                    var risk=o.RiskEur[j];
                    if(risk<=0 || held.Values.Sum(p=>p.Risk)+risk>=eq-0.70m*Math.Max(summary.ObservedPeakEur,eq))
                    {Count("JOINT_MONETARY_DRAWDOWN_HEADROOM");continue;}
                    string id="PVE3/"+variant+"/"+t+"/"+o.Symbol+"/"+side;
                    var grid=new AdaptiveRiskInputs(eq,0,free,c.MinimumUnits,c.StepUnits,c.MinimumUnits,
                        q.MarginPerUnit,1,false,false,4,1);
                    var scenarios=o.ScenarioNetEur[j].Select((v,i)=>new OpportunityScenario(
                        states[i].StateId,calibrated,true,v/c.MinimumUnits,0,risk/c.MinimumUnits,
                        Math.Max(0,v)/c.MinimumUnits)).ToArray();
                    opts.Add(new EconomicOpportunity(id,"PVE3_RISK_TAIL_INNOVATION",
                        o.Symbol,o.Symbol,side,t,calibrated,EvidenceLevel.Exploratory,
                        false,grid,scenarios));
                    lookup[id]=(o,side,risk);
                }
            }
            var exposure=held.Values.Select(p=>new ResearchExposureScenarios(p.Id,p.Symbol,p.Side,p.Units,
                states.Select(s=>s with{LossEur=p.Risk,
                    MarginEur=Math.Max(p.Margin,qs[p.Symbol].MarginPerUnit)*p.Units}).ToArray())).ToArray();
            string identity="PVE3/"+variant+"/"+x.Scenario+"/"+t;
            var decision=new NativeResearchDecision(identity,t+1,
                new ScenarioSizingInputs(eq,Math.Max(eq,summary.ObservedPeakEur),free,1,1,1,1,1,4,1),
                states,opts.ToArray(),exposure,
                opts.Select(o=>new ResearchEntryTerms(o.Id,1,0,Hash(o.Id))).ToArray(),Hash(identity));
            var selected=session.DecideResearch(decision);calls++;
            foreach(var bad in selected.Selection.Declined)Count(bad.Reason);
            foreach(var a in selected.Selection.Allocations)
            {
                var (o,side,risk)=lookup[a.Id];
                held[a.Id]=new Held(a.Id,o.Symbol,side,a.Units,risk,
                    qs[o.Symbol].MarginPerUnit,t+1);
                risks.Add(new NativeEntryRisk(a.Id,risk,t,Hash(a.Id+"EXANTE")));
                offered.Add(new{t,o.Symbol,Side=side,a.Units,ExpectedScore=o.ActionScore[side>0?0:1],ExAnteRiskEur=risk});
            }
        }
        var last=session.Ledger.Summary();var closed=session.Ledger.ClosedFragments();
        string[] eligible=Enumerable.Range(0,26).Select(i=>WeekIso(x.Start+i*Week)).ToArray();
        bool settled=held.Count==0 && last.PendingIntents==0 && last.OpenPositions==0 && missingHeld==0;
        var score=NativePerformanceScorecard.Calculate(new NativeEconomicScorecardInput(
            variant+"_"+x.Scenario,closed,snap.ToArray(),risks.ToArray(),eligible,300m,
            settled?last.ClosedNetEur:null,0m,settled,false,false));
        return new{Variant=variant,x.Scenario,Book=last,Scorecard=score,NativeCalls=calls,
            Admissions=offered,Rejections=rejections,MissingHeldMarks=missingHeld,
            DelayedExits=delay,CancelledIntents=cancelled,StillHeld=held.Count,
            MaxActive=maxActive,Completed=closed.Count(v=>v.CompletesRoundTrip),
            EventChainHash=last.EventChainHash,NoOrders=true,Qualified=false,IndependentConfirmation=false};
    }
    public static int Parity(string source,string output)
    {
        using var doc=JsonDocument.Parse(File.ReadAllBytes(source));
        int count=0;double diff=0;
        foreach(var row in doc.RootElement.EnumerateArray())
        {
            double[] Beta(string field)=>row.GetProperty(field).EnumerateArray().Select(x=>x.GetDouble()).ToArray();
            var beta=Beta("beta");var features=Beta("features");
            var cols=row.GetProperty("columns").EnumerateArray().Select(x=>x.GetInt32()).ToArray();
            var expected=row.GetProperty("expected").GetDouble();
            var expanded=NativePve3FeatureMath.Expand(features.Take(13).ToArray());
            for(int i=0;i<17;i++)diff=Math.Max(diff,Math.Abs(expanded[i]-features[i]));
            diff=Math.Max(diff,Math.Abs(NativePve3FeatureMath.Predict(beta,features,cols)-expected));
            count++;
        }
        if(count==0 || diff>1e-10)throw new InvalidOperationException("PVE3_NATIVE_PREDICTION_PARITY_FAILED");
        File.WriteAllText(output,JsonSerializer.Serialize(new{Cases=count,MaximumAbsoluteDifference=diff,Passed=true}));
        return 0;
    }
    public static int Run(string source,string output)
    {
        var x=JsonSerializer.Deserialize<Input>(File.ReadAllBytes(source),Options)
            ??throw new ArgumentException("PVE3_NATIVE_SOURCE_EMPTY");
        if(x.Scenario is not ("central" or "adverse") || x.Start<=0 || x.End<=x.Start)
            throw new ArgumentException("PVE3_NATIVE_SCENARIO_INVALID");
        var marks=new SortedDictionary<long,Dictionary<string,LedgerQuote>>(
            x.Quotes.GroupBy(q=>q.At).ToDictionary(g=>g.Key,g=>g.ToDictionary(q=>q.Symbol)));
        var offers=x.Offers.GroupBy(o=>o.At).ToDictionary(g=>g.Key,g=>g.ToArray());
        var result=new Dictionary<string,object>();
        foreach(var variant in new[]{"FULL","OWN","CASH"})
        {
            result[variant]=Book(x,variant,marks,offers);
            Console.WriteLine("PVE3_NATIVE_BOOK_COMPLETE "+variant+" "+x.Scenario);
        }
        File.WriteAllText(output,JsonSerializer.Serialize(result));return 0;
    }
}
