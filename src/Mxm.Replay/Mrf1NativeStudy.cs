using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

// MRF1: bounded native original EURUSD 30m quote-side action execution research.
// One unchanged existing NativeFundedSession / OpportunityOrchestrator /
// NativeFundedLedger and economic scorecard; no trading account or order APIs.
// MRF1 is DISTINCT from frozen PVE3/HXP1/CXL1 strategies.
internal static class Mrf1NativeStudy
{
    const long H=3600000, Week=7*24*H;
    sealed record Offer(long At,long ExitAt,string Symbol,string Variant,
        long CalibratedThrough,string MinUnits,string MinMarginEur,
        decimal[] MeanAdverseEur,decimal[] RiskEur,decimal[] ActionScore,
        decimal[][] ScenarioNetEur);
    sealed record Input(long Start,long End,string Scenario,
        LedgerQuote[] Quotes,Offer[] Offers);
    sealed record Held(string Id,int Side,decimal Units,long ExitAt,
        decimal RiskEur,decimal EntrySlippage,decimal InitialMargin,
        long OpenedAt);
    sealed record Check(double[] Features,int[] Columns,double[] Coefficients,double Expected);
    static readonly JsonSerializerOptions Json=new(){PropertyNameCaseInsensitive=true,
        NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString};
    static string Hash(string x)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(x))).ToLowerInvariant();
    static string Iso(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return System.Globalization.ISOWeek.GetYear(d)+"-W"+
            System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");}
    public static int Parity(string input,string output)
    {
        var rows=JsonSerializer.Deserialize<Check[]>(File.ReadAllBytes(input),Json)
            ??throw new ArgumentException("MRF1_PARITY_INPUT");
        if(rows.Length<4)throw new ArgumentException("MRF1_PARITY_SMALL");
        double worst=0;
        foreach(var row in rows)
        {
            if(row.Features.Length!=26 || row.Columns.Length+1!=row.Coefficients.Length ||
               row.Columns.Any(i=>i<0||i>=26)||
               row.Features.Any(x=>!double.IsFinite(x))||
               row.Coefficients.Any(x=>!double.IsFinite(x)))
                throw new ArgumentException("MRF1_PARITY_FEATURES");
            double n=row.Coefficients[0];
            for(int k=0;k<row.Columns.Length;k++)n+=row.Features[row.Columns[k]]*row.Coefficients[k+1];
            worst=Math.Max(worst,Math.Abs(n-row.Expected));
        }
        if(worst>1e-10)throw new InvalidOperationException("MRF1_CSHARP_PREDICTOR_PARITY");
        File.WriteAllText(output,JsonSerializer.Serialize(new{
            Cases=rows.Length,MaximumAbsoluteDifference=worst,Passed=true}));
        return 0;
    }
    static object Book(Input input,string variant,
        SortedDictionary<long,LedgerQuote> tape,Dictionary<long,Offer[]> byTime)
    {
        var session=new NativeFundedSession("MRF1_"+variant+"_"+input.Scenario);
        var counts=new Dictionary<string,int>(StringComparer.Ordinal);
        var risk=new List<NativeEntryRisk>();
        var marks=new List<NativeEconomicMark>();
        var offersUsed=new List<object>();
        Held? held=null;
        int seq=0,calls=0,unknownHeld=0,refusedFinancing=0;
        void Count(string reason)=>counts[reason]=counts.GetValueOrDefault(reason)+1;
        LedgerEvent Fact(long t,string kind,Held? pos=null,decimal execution=0,
            decimal fee=0,decimal margin=0,decimal slip=0,LedgerQuote[]? quotes=null)
        {
            string id="MRF1/"+variant+"/"+input.Scenario+"/"+(++seq);
            return new LedgerEvent(id,t,kind,pos?.Id??"",
                pos is null?"":"EURUSD",pos?.Side??0,pos?.Units??0,execution,
                fee,margin,slip,0,0,1,"MRF1_GENUINE_QUOTE_MODELED_FILL",
                Hash(id),quotes??Array.Empty<LedgerQuote>());
        }
        void Apply(LedgerEvent e)=>session.Ledger.Apply(e);
        foreach(var entry in tape)
        {
            long t=entry.Key;var q=entry.Value;
            // Quote as-of at this exact mark. No exit/future market data is
            // read until the elapsed clock reaches that quote.
            if(byTime.GetValueOrDefault(t+1,Array.Empty<Offer>()).All(o=>o.Variant!=variant)
               && held is null)continue;
            Apply(Fact(t,"MARK",quotes:new[]{q}));
            if(held is not null && t>=held.ExitAt)
            {
                var pos=held;
                if(t!=held.ExitAt)
                {unknownHeld++;Count("ORIGINAL_EXIT_MARK_MISSING_OR_LATE");continue;}
                Apply(Fact(t+1,"REQUEST_CLOSE",pos,margin:q.MarginPerUnit));
                decimal fill=pos.Side>0?q.Bid-pos.EntrySlippage:q.Ask+pos.EntrySlippage;
                decimal fee=Math.Max(q.ExitFeePerUnit*pos.Units,q.ExitFeeFloor);
                Apply(Fact(t+2,"CLOSE_FILL",pos,execution:fill,fee:fee,
                           margin:q.MarginPerUnit,slip:pos.EntrySlippage));
                held=null;
            }
            var sum=session.Ledger.Summary(t+2);
            marks.Add(new NativeEconomicMark(t+2,sum.LiquidationEquityEur,
                sum.UsedMarginEur,sum.FreeMarginEur,sum.OpenPositions,
                !sum.HistoryEvidenceIncomplete && sum.LiquidationEquityEur.HasValue));
            if(variant=="CASH")continue;
            var candidates=byTime.GetValueOrDefault(t+1,Array.Empty<Offer>())
                .Where(o=>o.Variant==variant).ToArray();
            if(candidates.Length==0)continue;
            if(held is not null){Count("FUNDED_ALREADY_HELD");continue;}
            if(sum.LiquidationEquityEur is not decimal eq ||
               sum.FreeMarginEur is not decimal free)
            {Count("UNKNOWN_CURRENT_NATIVE_CAPITAL");continue;}
            long calibrated=candidates.Max(o=>o.CalibratedThrough);
            if(calibrated>=t-120*60000L)throw new InvalidOperationException("MRF1_CAUSAL_EMBARGO");
            var states=Enumerable.Range(0,16)
                .Select(j=>new PortfolioScenario("MRF1_CAUSAL_"+j,calibrated,true,0,0,0,0))
                .ToArray();
            var research=new List<EconomicOpportunity>();
            var lookup=new Dictionary<string,(Offer,int,decimal,decimal)>();
            foreach(var o in candidates)
            {
                if(o.Symbol!="EURUSD" || o.RiskEur.Length!=2 ||
                   o.ActionScore.Length!=2 || o.ScenarioNetEur.Length!=2 ||
                   o.ScenarioNetEur.Any(s=>s.Length!=16)||
                   o.ExitAt!=t+30*60000L)
                    throw new ArgumentException("MRF1_LOCKED_ORIGINAL_OFFER_INVALID");
                decimal units=decimal.Parse(o.MinUnits,System.Globalization.CultureInfo.InvariantCulture);
                decimal margin=decimal.Parse(o.MinMarginEur,System.Globalization.CultureInfo.InvariantCulture);
                if(units!=1000m || margin!=33.33m)
                    throw new InvalidOperationException("MRF1_ORIGINAL_CONTRACT_TERMS_CHANGED");
                for(int j=0;j<2;j++)
                {
                    if(o.ActionScore[j]<=0m){Count("CASH_BEATS_EXANTE_ES_ADJUSTED_ACTION");continue;}
                    int side=j==0?1:-1;decimal exante=o.RiskEur[j];
                    if(exante<=0 || exante>0.30m*eq)
                    {Count("CAUSAL_INITIAL_RISK_TOO_LARGE");continue;}
                    string id="MRF1/"+variant+"/"+t+"/"+side;
                    var grid=new AdaptiveRiskInputs(eq,0,free,units,units,units,
                        q.MarginPerUnit,1,false,false,4,1);
                    var scenarios=o.ScenarioNetEur[j].Select((v,k)=>new OpportunityScenario(
                        states[k].StateId,calibrated,true,v/units,0,
                        exante/units,Math.Max(0,v)/units)).ToArray();
                    research.Add(new EconomicOpportunity(id,"MRF1_M1_MTF_VALUE",
                        "EURUSD","EURUSD",side,t,calibrated,
                        EvidenceLevel.Exploratory,false,grid,scenarios));
                    decimal bps=input.Scenario=="central"?.5m:2m;
                    decimal slip=(q.Bid+q.Ask)/2*bps/20000m;
                    lookup[id]=(o,side,exante,slip);
                }
            }
            var iden="MRF1/"+variant+"/"+input.Scenario+"/"+t;
            var decide=new NativeResearchDecision(iden,t+1,
                new ScenarioSizingInputs(eq,Math.Max(eq,sum.ObservedPeakEur),free,
                    1,1,1,1,1,4,1),
                states,research.ToArray(),Array.Empty<ResearchExposureScenarios>(),
                research.Select(o=>new ResearchEntryTerms(o.Id,1,
                    lookup[o.Id].Item4,Hash(o.Id))).ToArray(),Hash(iden));
            var selected=session.DecideResearch(decide);calls++;
            foreach(var rejected in selected.Selection.Declined)Count(rejected.Reason);
            if(selected.Selection.Allocations.Length>1)
                throw new InvalidOperationException("MRF1_ONE_SYMBOL_TWO_SIDES_ILLEGAL");
            foreach(var a in selected.Selection.Allocations)
            {
                var (model,side,stressed,slip)=lookup[a.Id];
                held=new Held(a.Id,side,a.Units,model.ExitAt,stressed,
                    slip,q.MarginPerUnit,t+2);
                decimal fill=side>0?q.Ask+slip:q.Bid-slip;
                decimal fee=Math.Max(q.ExitFeePerUnit*a.Units,q.ExitFeeFloor);
                try {Apply(Fact(t+2,"OPEN_FILL",held,execution:fill,fee:fee,
                                margin:q.MarginPerUnit,slip:slip));}
                catch(InvalidOperationException e) when(e.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL")
                {
                    Apply(Fact(t+2,"CONFIRMED_CANCEL",held));
                    held=null;refusedFinancing++;
                    continue;
                }
                risk.Add(new NativeEntryRisk(a.Id,stressed,t,Hash(a.Id+"RISK_AT_ENTRY")));
                offersUsed.Add(new{At=t+1,Side=side,a.Units,ModelExAnteRisk=stressed,
                    ModelScore=model.ActionScore[side>0?0:1]});
            }
        }
        var last=session.Ledger.Summary();
        var closed=session.Ledger.ClosedFragments();
        bool settled=held is null && last.PendingIntents==0 && last.OpenPositions==0 &&
            unknownHeld==0;
        var eligible=new[]{Iso(input.Start),Iso(input.Start+Week)};
        var card=NativePerformanceScorecard.Calculate(new NativeEconomicScorecardInput(
            variant+"_"+input.Scenario,closed,marks.ToArray(),risk.ToArray(),
            eligible,300m,settled?last.ClosedNetEur:null,0m,
            settled,false,false));
        return new{Variant=variant,input.Scenario,Scorecard=card,
            NativeCash=last,CausalSelectorCalls=calls,
            Admitted=offersUsed,Rejections=counts,UnknownHeldMarks=unknownHeld,
            UnfinancedCancels=refusedFinancing,
            PendingOrHeldUnsettled=!settled,
            Trades=closed,EventChainHash=last.EventChainHash,
            OrdersSubmitted=0,CloudActivated=false,Qualified=false,
            IndependentlyConfirmed=false};
    }
    public static int Run(string path,string output)
    {
        var input=JsonSerializer.Deserialize<Input>(File.ReadAllBytes(path),Json)
            ??throw new ArgumentException("MRF1_EMPTY_NATIVE_INPUT");
        if(input.Scenario is not ("central" or "adverse") || input.Quotes is null ||
           input.Offers is null || input.Start<=0 || input.End<=input.Start)
            throw new ArgumentException("MRF1_NATIVE_CONTRACT");
        var tape=new SortedDictionary<long,LedgerQuote>();
        foreach(var q in input.Quotes)
        {
            if(q.Symbol!="EURUSD" || tape.ContainsKey(q.At))
                throw new ArgumentException("MRF1_QUOTE_INCONSISTENCY");
            tape.Add(q.At,q);
        }
        var byTime=input.Offers.GroupBy(o=>o.At).ToDictionary(g=>g.Key,g=>g.ToArray());
        var outputData=new Dictionary<string,object>();
        foreach(var variant in new[]{"FULL","BASE","CASH"})
        {
            outputData[variant]=Book(input,variant,tape,byTime);
            Console.WriteLine("MRF1_NATIVE_SOURCE_EUR300_FINISHED "+variant);
        }
        File.WriteAllText(output,JsonSerializer.Serialize(outputData));
        return 0;
    }
}
