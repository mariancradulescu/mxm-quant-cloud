using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

// Bounded SDP2 research adapter. The existing native selector and ledger own
// funding and cash. Modeled bar/cost inputs never become real historical quotes.
internal static class Sdp2ActionValueResearch
{
    const long M5=300000,H=3600000,Day=24*H,Week=7*Day;
    internal sealed record Terms(string Symbol,decimal MinimumUnits,decimal StepUnits,
        int SwapMinute,bool FundingKnown,decimal LongDailyDebitBps,decimal ShortDailyDebitBps);
    internal sealed record Offer(long At,string Symbol,int HorizonHours,string Variant,
        long CalibratedThrough,decimal[] Means,decimal[][] Scenarios,decimal[] Risk);
    internal sealed record Input(long Start,long End,string Scenario,LedgerQuote[] Quotes,Terms[] Contracts,Offer[] Offers);
    sealed record Held(string Id,string Symbol,int Side,decimal Units,long RequestAt,
        int HorizonHours,decimal Risk,decimal Margin,long Opened=0,long CloseRequest=0,long FinanceThrough=0);
    static readonly JsonSerializerOptions Json=new(){PropertyNameCaseInsensitive=true};
    static string Hash(string x)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(x))).ToLowerInvariant();
    static decimal Fee(LedgerQuote q,decimal u)=>Math.Max(q.ExitFeePerUnit*u,q.ExitFeeFloor);
    static int Cross(long a,long b,int minute)=>(int)Math.Max(0,(b-minute*60000L)/Day-(a-minute*60000L)/Day);
    static string Iso(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00");}
    static object Book(Input input,string variant,
        SortedDictionary<long,Dictionary<string,LedgerQuote>> marks,
        Dictionary<long,Offer[]> offers)
    {
        var session=new NativeFundedSession("SDP2_CONDITIONAL_"+variant+"_"+input.Scenario);
        var contracts=input.Contracts.ToDictionary(x=>x.Symbol);
        var held=new Dictionary<string,Held>();var rejected=new Dictionary<string,int>();
        var admissions=new List<object>();int seq=0,calls=0,missing=0,delayed=0,cancelled=0;
        decimal maxMargin=0,maxStress=0;int maxHeld=0;
        void Count(string why)=>rejected[why]=rejected.GetValueOrDefault(why)+1;
        LedgerEvent Fact(long at,string kind,Held? p=null,decimal price=0,decimal fee=0,
            decimal margin=0,LedgerQuote[]? qs=null,decimal financing=0)
        {
            string id="SDP2/"+variant+"/"+input.Scenario+"/"+(++seq);
            return new(id,at,kind,p?.Id??"",p?.Symbol??"",p?.Side??0,p?.Units??0,
                price,fee,margin,0,0,0,1,"SDP2_CONDITIONAL_MODEL_NOT_HISTORICAL_FILL",
                Hash(id),qs??Array.Empty<LedgerQuote>(),financing);
        }
        void Apply(LedgerEvent e)=>session.Ledger.Apply(e);
        foreach(var entry in marks)
        {
            long at=entry.Key;var qs=entry.Value;
            bool decision=offers.ContainsKey(at+1) && variant!="CASH";
            if(held.Count==0&&!decision)continue;
            Apply(Fact(at,"MARK",qs:qs.Values.ToArray()));
            foreach(var p in held.Values.OrderBy(x=>x.Id,StringComparer.Ordinal).ToArray())
            {
                if(!qs.TryGetValue(p.Symbol,out var q)){missing++;continue;}
                var terms=contracts[p.Symbol];
                if(p.Opened==0)
                {
                    if(at<=p.RequestAt)continue;
                    if(at-p.RequestAt>M5){Apply(Fact(at,"CONFIRMED_CANCEL",p));held.Remove(p.Id);cancelled++;continue;}
                    if(session.Ledger.Summary(at).LiquidationEquityEur is null){Count("MISSING_HELD_MARK_AT_FILL");continue;}
                    try {
                        Apply(Fact(at,"OPEN_FILL",p,p.Side>0?q.Ask:q.Bid,Fee(q,p.Units),q.MarginPerUnit));
                        held[p.Id]=p with{Opened=at,FinanceThrough=at,Margin=q.MarginPerUnit};
                    } catch(InvalidOperationException e) when(e.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL") {
                        Apply(Fact(at,"CONFIRMED_CANCEL",p));held.Remove(p.Id);cancelled++;
                    }
                    continue;
                }
                int crossings=Cross(p.FinanceThrough,at,terms.SwapMinute);
                if(crossings>0)
                {
                    if(!terms.FundingKnown){Count("FUNDING_UNKNOWN_EXPOSURE_RETAINED");continue;}
                    decimal rate=p.Side>0?terms.LongDailyDebitBps:terms.ShortDailyDebitBps;
                    Apply(Fact(at,"FINANCING",p,financing:-3m*crossings*rate*p.Units*q.Bid*q.EurDebit/10000m));
                }
                var current=p with{FinanceThrough=at};held[p.Id]=current;
                if(p.CloseRequest>0 && at>p.CloseRequest)
                {
                    if(at>p.Opened+p.HorizonHours*H)delayed++;
                    Apply(Fact(at,"CLOSE_FILL",current,p.Side>0?q.Bid:q.Ask,Fee(q,p.Units),q.MarginPerUnit));
                    held.Remove(p.Id);
                }
                else if(at>=p.Opened+p.HorizonHours*H-M5)
                {
                    Apply(Fact(at,"REQUEST_CLOSE",current));held[p.Id]=current with{CloseRequest=at};
                }
            }
            var sum=session.Ledger.Summary(at);
            maxMargin=Math.Max(maxMargin,sum.UsedMarginEur??0);
            maxStress=Math.Max(maxStress,held.Values.Sum(x=>x.Risk));maxHeld=Math.Max(maxHeld,held.Count);
            if(!decision || at+1>=input.End)continue;
            if(held.Values.Any(p=>!qs.ContainsKey(p.Symbol))){Count("PENDING_OR_HELD_MARK_UNKNOWN");continue;}
            if(sum.LiquidationEquityEur is not decimal equity || sum.FreeMarginEur is not decimal free)
            {Count("HELD_VALUATION_UNKNOWN");continue;}
            var available=offers[at+1].Where(x=>x.Variant==variant&&contracts.ContainsKey(x.Symbol)&&qs.ContainsKey(x.Symbol))
                .OrderByDescending(x=>Math.Max(x.Means[2],x.Means[3])).ThenBy(x=>x.Symbol,StringComparer.Ordinal).ThenBy(x=>x.HorizonHours).ToArray();
            if(available.Length==0)continue;
            long calibrated=available.Max(x=>x.CalibratedThrough);
            if(calibrated>=at-4*H)throw new InvalidOperationException("SDP2_EMBARGO_VIOLATION");
            var states=Enumerable.Range(0,16).Select(i=>new PortfolioScenario("RESIDUAL_"+i,calibrated,true,0,0,0,0)).ToArray();
            var opportunities=new List<EconomicOpportunity>();var lookup=new Dictionary<string,(Offer offer,int side,decimal risk)>();
            int targetOffset=input.Scenario=="adverse"?2:0;
            foreach(var o in available)
            {
                if(held.Values.Any(x=>x.Symbol==o.Symbol))continue;
                var c=contracts[o.Symbol];var q=qs[o.Symbol];
                // Forecast policy is always ranked by adverse action value, even
                // for the central valuation counterfactual. CASH is zero.
                for(int sideIndex=0;sideIndex<2;sideIndex++)
                {
                    int side=sideIndex==0?1:-1;int target=targetOffset+sideIndex;
                    if(o.Means[2+sideIndex]<=0){Count("FORECAST_PREFERS_CASH");continue;}
                    if(!c.FundingKnown && Cross(at,at+M5+o.HorizonHours*H,c.SwapMinute)>0)
                    {Count("CAUSAL_FUNDING_UNKNOWN");continue;}
                    decimal risk=o.Risk[2+sideIndex];
                    if(risk<=0||held.Values.Sum(x=>x.Risk)+risk>=equity-.70m*Math.Max(sum.ObservedPeakEur,equity))
                    {Count("AGGREGATE_STRESS_HEADROOM");continue;}
                    string id="SDP2/"+variant+"/"+at+"/"+o.Symbol+"/"+o.HorizonHours+"/"+side;
                    var grid=new AdaptiveRiskInputs(equity,0,free,c.MinimumUnits,c.StepUnits,c.MinimumUnits,q.MarginPerUnit,1,false,false,4,1);
                    // Sorted marginal residuals are comonotonic stresses; no
                    // historical joint-scenario or diversification claim.
                    var scenarios=o.Scenarios[target].Select((net,i)=>new OpportunityScenario(states[i].StateId,
                        o.CalibratedThrough,true,net/c.MinimumUnits,0,risk/c.MinimumUnits,
                        Math.Max(0,net)/c.MinimumUnits)).ToArray();
                    opportunities.Add(new(id,"SDP2_ACTION_VALUE",o.Symbol,o.Symbol,side,at,o.CalibratedThrough,
                        EvidenceLevel.Exploratory,false,grid,scenarios));lookup[id]=(o,side,risk);
                }
            }
            var exposure=held.Values.Select(p=>new ResearchExposureScenarios(p.Id,p.Symbol,p.Side,p.Units,
                states.Select(s=>s with{LossEur=p.Risk,MarginEur=Math.Max(p.Margin,qs[p.Symbol].MarginPerUnit)*p.Units}).ToArray())).ToArray();
            string decisionId="SDP2/"+variant+"/"+input.Scenario+"/"+at;
            var d=new NativeResearchDecision(decisionId,at+1,
                new ScenarioSizingInputs(equity,Math.Max(equity,sum.ObservedPeakEur),free,1,1,1,1,1,4,1),
                states,opportunities.ToArray(),exposure,
                opportunities.Select(o=>new ResearchEntryTerms(o.Id,1,0,Hash(o.Id))).ToArray(),Hash(decisionId));
            var result=session.DecideResearch(d);calls++;
            foreach(var r in result.Selection.Declined)Count(r.Reason);
            foreach(var a in result.Selection.Allocations)
            {
                var (o,side,risk)=lookup[a.Id];held[a.Id]=new(a.Id,o.Symbol,side,a.Units,at+1,o.HorizonHours,risk,qs[o.Symbol].MarginPerUnit);
                admissions.Add(new{At=at+1,o.Symbol,o.HorizonHours,Side=side,a.Units,RiskEur=risk,a.MarginalUtilityLower});
            }
        }
        var final=session.Ledger.Summary();var trades=session.Ledger.ClosedFragments();
        var weeks=Enumerable.Range(0,26).ToDictionary(w=>Iso(input.Start+w*Week),w=>trades.Count(t=>t.CompletesRoundTrip&&Iso(t.ClosedAt)==Iso(input.Start+w*Week)));
        return new{Variant=variant,Scenario=input.Scenario,InitialCapitalEur=300,
            Domain="CONDITIONAL_BAR_COST_MODEL_NOT_BROKER_EXECUTION",Final=final,NativeCalls=calls,
            WeeklyCompletions=weeks,Hard21EveryWeek=weeks.Values.All(n=>n>=21),MissingHeldMarks=missing,
            DelayedExits=delayed,CancelledPending=cancelled,MaxMarginEur=maxMargin,MaxStressEur=maxStress,
            MaxConcurrentExposure=maxHeld,Rejections=rejected,Admissions=admissions,Trades=trades,
            Qualified=false,IndependentConfirmation=false,ContinuousDrawdownCertified=false,Orders=0};
    }
    public static int Run(string source,string output)
    {
        var input=JsonSerializer.Deserialize<Input>(File.ReadAllBytes(source),Json)!;
        if(input is null||input.Scenario is not("central" or "adverse"))throw new ArgumentException("SDP2_INPUT");
        var marks=new SortedDictionary<long,Dictionary<string,LedgerQuote>>(input.Quotes.GroupBy(x=>x.At).ToDictionary(g=>g.Key,g=>g.ToDictionary(q=>q.Symbol)));
        var offers=input.Offers.GroupBy(x=>x.At).ToDictionary(g=>g.Key,g=>g.ToArray());
        var result=new Dictionary<string,object>();
        foreach(string variant in new[]{"CASH","FULL","NO_PEERS","NO_ACTIVITY","OWN_PRICE","PRIOR"})
        {result[variant]=Book(input,variant,marks,offers);Console.WriteLine("SDP2_NATIVE_COMPLETE "+input.Scenario+" "+variant);}
        File.WriteAllText(output,JsonSerializer.Serialize(result));return 0;
    }
    public static int FeatureParity(string source,string output)
    {
        var windows=JsonSerializer.Deserialize<double[][][]>(File.ReadAllBytes(source))!;
        var answer=new List<double[]>();
        foreach(var p in windows)
        {
            if(p.Length!=8)throw new ArgumentException("SDP2_FEATURE_WINDOW");
            var ranges=p.Select(r=>r[3]-r[4]).ToArray();var last=p[7];
            double sig=Math.Max(.0001,Math.Sqrt(p.Average(r=>Math.Pow(Math.Log(r[5]/r[2]),2))));
            answer.Add(new[]{(last[5]-last[2])/ranges[7],(last[3]-Math.Max(last[2],last[5]))/ranges[7],
                (Math.Min(last[2],last[5])-last[4])/ranges[7],(last[5]-last[4])/ranges[7],
                Math.Log(last[5]/last[2])/sig,Math.Log(last[5]/p[4][2])/(sig*2),
                Math.Log(last[5]/p[0][2])/(sig*Math.Sqrt(8)),
                Math.Abs(last[5]-p[0][2])/Math.Max(1e-12,p.Sum(r=>Math.Abs(r[5]-r[2]))),
                Math.Log(sig),ranges[7]/ranges.Take(7).Average(),Math.Log(last[6]/p.Take(7).Average(r=>r[6])),
                Enumerable.Range(1,7).Count(j=>p[j][0]!=p[j-1][1])/7d});
        }
        File.WriteAllText(output,JsonSerializer.Serialize(answer));return 0;
    }
    public static int Parity(string source,string output)
    {
        using var doc=JsonDocument.Parse(File.ReadAllBytes(source));double max=0;int count=0;
        foreach(var row in doc.RootElement.EnumerateArray())
        {
            var m=row.GetProperty("model");var x=row.GetProperty("x").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
            var columns=m.GetProperty("columns").EnumerateArray().Select(v=>v.GetInt32()).ToArray();
            var cuts=m.GetProperty("cuts").EnumerateArray().ToArray();
            var z=columns.Select((c,i)=>cuts[i].EnumerateArray().Count(v=>x[c]>v.GetDouble())).ToArray();
            var pred=m.GetProperty("initial").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
            foreach(var tree in m.GetProperty("trees").EnumerateArray())
            {
                int n=0;var left=tree.GetProperty("left");var right=tree.GetProperty("right");
                while(left[n].GetInt32()>=0)
                {int f=tree.GetProperty("feature")[n].GetInt32();n=z[f]<=tree.GetProperty("threshold")[n].GetDouble()?left[n].GetInt32():right[n].GetInt32();}
                for(int k=0;k<4;k++)pred[k]+=.1*tree.GetProperty("value")[n][k].GetDouble();
            }
            for(int k=0;k<4;k++)max=Math.Max(max,Math.Abs(pred[k]-row.GetProperty("expected")[k].GetDouble()));
            count++;
        }
        if(max>1e-10||count==0)throw new InvalidOperationException("SDP2_NATIVE_TREE_PARITY");
        File.WriteAllText(output,JsonSerializer.Serialize(new{Cases=count,MaximumAbsoluteError=max,Passed=true}));return 0;
    }
}
