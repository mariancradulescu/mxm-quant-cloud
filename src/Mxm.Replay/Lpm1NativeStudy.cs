using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

internal static class Lpm1NativeStudy
{
    const long Minute=60000,DayMs=86400000,Week=7*DayMs;
    static readonly string[] Modes={"VOL","STRUCT","ADAPT"};
    static readonly JsonSerializerOptions Json=new(){NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString};
    sealed record Day(long Start,long[][] Bid,long[][] Ask);
    sealed record Input(long Start,long End,NativeObservedContractTerms Contract,decimal MinMargin,decimal TickSize,long[][] Bars,Day[] Days);
    sealed record Tick(long At,decimal Bid,decimal Ask,bool Ambiguous,bool Gap,LedgerQuote Quote,decimal Direction);
    sealed record Candidate(int Index,long Clock,int Week,int Cell,NativeExitSeed Seed,decimal Low,decimal High);
    sealed record PathResult(int Entry,int Trigger,int Exit,decimal Price,decimal Stop,decimal Risk,decimal? Ratio,decimal Net,string Reason,bool Uncertain);
    sealed record Sample(int Day,int Candidate,int Action,int Week,int Cell,decimal Net);
    sealed record Model(decimal Global,Dictionary<int,decimal> Means,Dictionary<int,decimal> Wins,decimal Win,decimal Bias,decimal[] Residual,int Train,int Calibration);
    sealed record Prepared(Day Day,Tick[] Ticks,Candidate[] Candidates,PathResult?[][] Central,PathResult?[][] Adverse);
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static string Iso(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;return System.Globalization.ISOWeek.GetYear(d)+"-W"+System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");}
    static int Lower(Tick[] ticks,long at){int lo=0,hi=ticks.Length;while(lo<hi){int m=(lo+hi)/2;if(ticks[m].At<at)lo=m+1;else hi=m;}return lo;}
    static NativeClosedMarketBar Bar(long[] b)=>new(b[0],b[1],b[2]/100000m,b[3]/100000m,b[4]/100000m,b[5]/100000m,b[6]);
    static decimal Slip(Input input,Tick q,bool adverse)=>Math.Max(input.TickSize,(q.Ask-q.Bid)*(adverse?1m:.25m));
    static decimal Fee(LedgerQuote q,decimal units)=>Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);
    static decimal ConvertMoney(LedgerQuote q,decimal money)=>money*(money>=0?q.EurCredit:q.EurDebit);
    static decimal Tr(NativeClosedMarketBar x,decimal previous)=>Math.Max(x.High-x.Low,Math.Max(Math.Abs(x.High-previous),Math.Abs(x.Low-previous)));
    static NativeClosedMarketBar[] Aggregate(NativeClosedMarketBar[] bars)=>bars.GroupBy(b=>b.OpenAt/900000*900000)
        .Where(g=>g.Count()==3 && g.First().OpenAt==g.Key && g.Last().CloseAt==g.Key+900000)
        .Select(g=>new NativeClosedMarketBar(g.Key,g.Key+900000,g.First().Open,g.Max(x=>x.High),g.Min(x=>x.Low),g.Last().Close,g.Sum(x=>x.TickVolume))).ToArray();
    static Prepared Prepare(Input input,Day day,NativeClosedMarketBar[] bars,NativeClosedMarketBar[] m15)
    {
        var ticks=new List<Tick>();int b=0,a=0,barIndex=0;decimal bid=0,ask=0;long bidAt=0,askAt=0,last=0;bool missing=false;
        while(b<day.Bid.Length || a<day.Ask.Length)
        {
            long t=Math.Min(b<day.Bid.Length?day.Bid[b][0]:long.MaxValue,a<day.Ask.Length?day.Ask[a][0]:long.MaxValue);
            bool ambiguous=false;decimal? seenBid=null,seenAsk=null;
            while(b<day.Bid.Length && day.Bid[b][0]==t){decimal v=day.Bid[b++][1]/100000m;ambiguous|=seenBid.HasValue&&seenBid!=v;seenBid=v;bid=v;bidAt=t;}
            while(a<day.Ask.Length && day.Ask[a][0]==t){decimal v=day.Ask[a++][1]/100000m;ambiguous|=seenAsk.HasValue&&seenAsk!=v;seenAsk=v;ask=v;askAt=t;}
            if(bid<=0 || ask<bid || t-bidAt>30000 || t-askAt>30000){missing=true;continue;}
            while(barIndex+1<m15.Length && m15[barIndex+1].CloseAt<t)barIndex++;
            decimal direction=barIndex>0&&m15[barIndex].CloseAt<t?m15[barIndex].Close-m15[barIndex-1].Close:0;
            var context=new NativeMarketCostContext(t,bid,ask,1m/ask,1m/bid,(1m/bid+1m/ask)/2,null,input.MinMargin,input.Contract.MinimumUnits,0);
            var q=NativeBrokerContractCosts.Quote(input.Contract,context).Quote;
            ticks.Add(new(t,bid,ask,ambiguous,missing||(last>0&&t-last>30000),q,direction));last=t;missing=false;
        }
        var tape=ticks.ToArray();var candidates=new List<Candidate>();
        for(long clock=day.Start+8*60*Minute;clock<=day.Start+(10*60+45)*Minute;clock+=15*Minute)
        {
            int i=Lower(tape,clock+1500);if(i==tape.Length || tape[i].At>=clock+15*Minute)continue;
            var past=bars.Where(x=>x.CloseAt<clock+1500).TakeLast(30).ToArray();
            var context=m15.Where(x=>x.CloseAt<clock+1500).TakeLast(8).ToArray();
            if(past.Length<30 || !NativeCausalExitResearch.TrySeed(past,context,clock+1500,out var seed))continue;
            if(past.Zip(past.Skip(1)).Any(x=>x.First.CloseAt!=x.Second.OpenAt))continue;
            decimal old=Enumerable.Range(1,14).Average(k=>Tr(past[k],past[k-1].Close));
            int cell=(Math.Sign(context[^1].Close-context[^2].Close)+1)*6+(Math.Sign(past[^1].Close-past[^13].Close)+1)*2+(seed.AtrQuote>old?1:0);
            candidates.Add(new(i,tape[i].At,(int)((day.Start-input.Start)/Week),cell,seed,past.TakeLast(8).Min(x=>x.Low),past.TakeLast(8).Max(x=>x.High)));
        }
        var cs=candidates.ToArray();var central=new PathResult?[cs.Length][];var adverse=new PathResult?[cs.Length][];
        for(int j=0;j<cs.Length;j++)
        {
            central[j]=new PathResult?[6];adverse[j]=new PathResult?[6];
            for(int k=0;k<6;k++){central[j][k]=Trace(input,day,tape,cs[j],k,false);adverse[j][k]=Trace(input,day,tape,cs[j],k,true);}
        }
        return new(day,tape,cs,central,adverse);
    }
    static PathResult? Trace(Input input,Day day,Tick[] tape,Candidate c,int action,bool adverse)
    {
        int side=action%2==0?1:-1;string mode=Modes[action/2];
        int entry=Lower(tape,c.Clock+100);if(entry==tape.Length)return null;
        var fill=tape[entry];decimal slip=Slip(input,tape[c.Index],adverse);
        decimal price=side>0?fill.Ask+slip:fill.Bid-slip;
        decimal stop=mode=="STRUCT"?(side>0?c.Low-.25m*c.Seed.AtrQuote:c.High+.25m*c.Seed.AtrQuote):price-side*1.5m*c.Seed.AtrQuote;
        decimal distance=side*(price-stop);if(distance<=0)return null;
        decimal risk=distance*input.Contract.MinimumUnits*fill.Quote.EurDebit+2*Fee(fill.Quote,input.Contract.MinimumUnits)+2*slip*input.Contract.MinimumUnits*fill.Quote.EurDebit;
        decimal? ratio=mode=="VOL"?2m*c.Seed.AtrQuote/distance:mode=="STRUCT"&&side*(c.Seed.EquilibriumQuote-price)>0?side*(c.Seed.EquilibriumQuote-price)/distance:null;
        decimal extreme=price;bool uncertain=false;
        for(int i=c.Index;i<=entry;i++)uncertain|=tape[i].Gap||tape[i].Ambiguous;
        for(int i=entry+1;i<tape.Length;i++)
        {
            var q=tape[i];uncertain|=q.Gap||q.Ambiguous;
            var verdict=NativeCausalExitResearch.AssessLifecycle(mode,side,price,c.Seed,stop,extreme,q.Quote,q.Direction,q.At>=day.Start+12*60*Minute);
            extreme=verdict.FavorableExtreme;if(!verdict.RequestClose)continue;
            int exit=Lower(tape,q.At+100);if(exit==tape.Length)return null;
            for(int j=i;j<=exit;j++)uncertain|=tape[j].Gap||tape[j].Ambiguous;
            decimal exitSlip=Slip(input,tape[exit],adverse);
            decimal close=side>0?tape[exit].Bid-exitSlip:tape[exit].Ask+exitSlip;
            decimal net=ConvertMoney(tape[exit].Quote,side*input.Contract.MinimumUnits*(close-price))-Fee(fill.Quote,input.Contract.MinimumUnits)-Fee(tape[exit].Quote,input.Contract.MinimumUnits);
            return new(entry,i,exit,price,stop,risk,ratio,net,verdict.Reason,uncertain);
        }
        return null;
    }
    static Model? Fit(List<Sample> samples,int action,bool context)
    {
        var train=samples.Where(x=>x.Week<6 && x.Action==action).ToArray();
        var cal=samples.Where(x=>x.Week>=6&&x.Week<9&&x.Action==action).ToArray();
        if(train.Length<80||cal.Length<40)return null;
        decimal global=train.Average(x=>x.Net),win=train.Average(x=>x.Net>0?1m:0m);
        var means=new Dictionary<int,decimal>();var wins=new Dictionary<int,decimal>();
        for(int c=0;c<18;c++){var rows=train.Where(x=>x.Cell==c).ToArray();means[c]=(rows.Sum(x=>x.Net)+32*global)/(rows.Length+32);wins[c]=(rows.Count(x=>x.Net>0)+32*win)/(rows.Length+32);}
        var residual=cal.Select(x=>x.Net-(context?means[x.Cell]:global)).Order().ToArray();
        decimal bias=residual.Average();
        var quant=Enumerable.Range(0,16).Select(i=>residual[Math.Min(residual.Length-1,(int)((i+.5)*residual.Length/16))]-bias).ToArray();
        return new(global,means,wins,win,bias,quant,train.Length,cal.Length);
    }
    static object Metrics(decimal[] values)=>new{Count=values.Length,Mean=values.Length==0?(decimal?)null:values.Average(),
        Quantiles=values.Length==0?Array.Empty<decimal>():new[]{0m,.05m,.25m,.5m,.75m,.95m,1m}.Select(p=>values.Order().ElementAt((int)(p*(values.Length-1)))).ToArray(),Values=values};
    static object Book(Input input,List<Prepared> days,Model?[] models,string name,bool adverse,int fixedAction=-1)
    {
        var session=new NativeFundedSession("LPM1_"+name+(adverse?"_ADVERSE":"_CENTRAL"));
        var ledger=session.Ledger;var risks=new List<NativeEntryRisk>();var marks=new List<NativeEconomicMark>();
        var admissions=new List<object>();var rr=new List<decimal>();var counts=new Dictionary<string,int>();
        int sequence=0,uncertainTrades=0,unsettled=0;bool suspended=false;
        void Count(string s)=>counts[s]=counts.GetValueOrDefault(s)+1;
        LedgerEvent Fact(long t,string kind,string id="",int side=0,decimal price=0,decimal slip=0,LedgerQuote? q=null,string reason="LPM1")
        {
            string eid="LPM1/"+name+"/"+(adverse?"A":"C")+"/"+(++sequence);
            return new(eid,t,kind,id,id==""?"":"EURUSD",side,id==""?0:input.Contract.MinimumUnits,price,
                q is null||id==""?0:Fee(q,input.Contract.MinimumUnits),q?.MarginPerUnit??0,slip,t,t-1,100,reason,Hash(eid),q is null?Array.Empty<LedgerQuote>():new[]{q});
        }
        void Mark(Tick tick)
        {
            ledger.Apply(Fact(tick.At,"MARK",q:tick.Quote));var sum=ledger.Summary(tick.At);
            marks.Add(new(tick.At,sum.LiquidationEquityEur,sum.UsedMarginEur,sum.FreeMarginEur,sum.OpenPositions,!tick.Gap&&!tick.Ambiguous));
        }
        foreach(var day in days.Where(d=>d.Day.Start>=input.Start+9*Week))
        {
            int occupiedThrough=-1;
            for(int ci=0;ci<day.Candidates.Length;ci++)
            {
                var c=day.Candidates[ci];if(c.Index<=occupiedThrough){Count("ALREADY_HELD");continue;}
                var quote=day.Ticks[c.Index];Mark(quote);var sum=ledger.Summary(c.Clock);
                if(name=="CASH")continue;
                if(suspended || sum.MaximumSampledDrawdown>=.30m){Count("DD_STOP");continue;}
                if(sum.LiquidationEquityEur is not decimal equity || sum.FreeMarginEur is not decimal free){Count("CAPITAL_UNKNOWN");continue;}
                int chosen=fixedAction;string id="LPM1/"+name+"/"+c.Clock;decimal slip=Slip(input,quote,adverse);
                // Pre-entry risk uses only current quote and previously completed bars.
                decimal RiskNow(int k)
                {
                    int s=k%2==0?1:-1;decimal px=s>0?quote.Ask+slip:quote.Bid-slip;
                    decimal stop=k/2==1?(s>0?c.Low-.25m*c.Seed.AtrQuote:c.High+.25m*c.Seed.AtrQuote):px-s*1.5m*c.Seed.AtrQuote;
                    return s*(px-stop)*input.Contract.MinimumUnits*quote.Quote.EurDebit+2*Fee(quote.Quote,input.Contract.MinimumUnits)+2*slip*input.Contract.MinimumUnits*quote.Quote.EurDebit;
                }
                if(fixedAction<0)
                {
                    if(models.Any(x=>x is null)){Count("MODEL_TRAIN_CAL_INCOMPLETE");continue;}
                    long known=input.Start+9*Week-1;
                    var states=Enumerable.Range(0,16).Select(j=>new PortfolioScenario("LPM1_"+j,known,true,0,0,0,0)).ToArray();
                    var opportunities=new List<EconomicOpportunity>();
                    for(int k=0;k<6;k++)
                    {
                        var model=models[k]!;decimal mean=(name=="CONTEXT"?model.Means[c.Cell]:model.Global)+model.Bias;
                        decimal risk=RiskNow(k);if(risk<=0 || risk>equity-.7m*sum.ObservedPeakEur)continue;
                        decimal units=input.Contract.MinimumUnits;
                        var grid=new AdaptiveRiskInputs(equity,0,free,units,input.Contract.VolumeStepUnits,units,quote.Quote.MarginPerUnit,1,false,false,3,1);
                        opportunities.Add(new(id+"/"+k,"LPM1_"+Modes[k/2],"EURUSD","EURUSD",k%2==0?1:-1,c.Clock,known,EvidenceLevel.Exploratory,false,grid,
                            model.Residual.Select((r,j)=>new OpportunityScenario(states[j].StateId,known,true,(mean+r)/units,0,Math.Max(risk,-mean-r)/units,Math.Max(0,mean+r)/units)).ToArray()));
                    }
                    var decision=new NativeResearchDecision(id,c.Clock,new ScenarioSizingInputs(equity,sum.ObservedPeakEur,free,1,1,1,1,1,3,1),states,opportunities.ToArray(),Array.Empty<ResearchExposureScenarios>(),opportunities.Select(o=>new ResearchEntryTerms(o.Id,100,slip,Hash(o.Id))).ToArray(),Hash(id));
                    var result=session.DecideResearch(decision);ledger=session.Ledger;
                    foreach(var r in result.Selection.Declined)Count(r.Reason);
                    if(result.Selection.Allocations.Length==0)continue;
                    if(result.Selection.Allocations.Length!=1)throw new Exception("LPM1_SINGLE_SYMBOL_ALLOCATION");
                    id=result.Selection.Allocations[0].Id;chosen=int.Parse(id.Split('/')[^1]);
                }
                else
                {
                    decimal risk=RiskNow(chosen);
                    if(risk<=0 || risk>equity-.7m*sum.ObservedPeakEur || free<=input.MinMargin+2*Fee(quote.Quote,input.Contract.MinimumUnits)){Count("FIXED_ACTION_UNFINANCED_OR_RISK");continue;}
                    ledger.Apply(Fact(c.Clock,"REQUEST_OPEN",id,chosen%2==0?1:-1,slip:slip,q:quote.Quote));
                }
                // Future path is read only AFTER the action/intention is selected.
                var path=(adverse?day.Adverse:day.Central)[ci][chosen];
                if(path is null){unsettled++;Count("SELECTED_FUTURE_PATH_UNKNOWN");suspended=true;break;}
                int side=chosen%2==0?1:-1;var atEntry=day.Ticks[path.Entry];Mark(atEntry);
                try{ledger.Apply(Fact(atEntry.At,"OPEN_FILL",id,side,path.Price,slip,atEntry.Quote));}
                catch(InvalidOperationException ex) when(ex.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL")
                {ledger.Apply(Fact(atEntry.At,"CONFIRMED_CANCEL",id,side,reason:"UNFINANCED_AT_FILL"));Count("UNFINANCED_AT_FILL");continue;}
                decimal initialRisk=RiskNow(chosen);risks.Add(new(id,initialRisk,c.Clock,Hash(id+"risk")));
                if(path.Ratio.HasValue)rr.Add(path.Ratio.Value);
                int trigger=path.Trigger,exit=path.Exit;string reason=path.Reason;bool requested=false,uncertain=path.Uncertain;
                for(int i=path.Entry+1;i<=exit;i++)
                {
                    var tick=day.Ticks[i];Mark(tick);var state=ledger.Summary(tick.At);
                    if(!requested && (i>=trigger||state.MaximumSampledDrawdown>=.30m))
                    {
                        if(state.MaximumSampledDrawdown>=.30m){reason="SYSTEM_DD_PROTECTION";suspended=true;exit=Lower(day.Ticks,tick.At+100);if(exit==day.Ticks.Length){unsettled++;break;}}
                        ledger.Apply(Fact(tick.At,"REQUEST_CLOSE",id,side,q:tick.Quote,reason:reason));requested=true;
                    }
                    if(requested && i==exit)
                    {
                        decimal exitSlip=Slip(input,tick,adverse),px=side>0?tick.Bid-exitSlip:tick.Ask+exitSlip;
                        ledger.Apply(Fact(tick.At,"CLOSE_FILL",id,side,px,slip,tick.Quote,reason) with {ObservedExitSlippagePerSide=exitSlip});
                        var closedState=ledger.Summary(tick.At);marks.Add(new(tick.At,closedState.LiquidationEquityEur,closedState.UsedMarginEur,closedState.FreeMarginEur,0));
                    }
                }
                occupiedThrough=exit;if(uncertain)uncertainTrades++;
                admissions.Add(new{At=c.Clock,Action=chosen,Manager=Modes[chosen/2],Side=side,InitialRiskEur=initialRisk,InitialRewardRisk=path.Ratio,PathUncertain=uncertain});
                if(unsettled>0)break;
            }
            if(unsettled>0)break;
        }
        var last=ledger.Summary();var trades=ledger.ClosedFragments();
        bool settled=last.OpenPositions==0&&last.PendingIntents==0&&unsettled==0;
        var score=NativePerformanceScorecard.Calculate(new(name,trades,marks.ToArray(),risks.ToArray(),Enumerable.Range(9,3).Select(w=>Iso(input.Start+w*Week)).ToArray(),300,settled?last.ClosedNetEur:null,0,settled,false,false));
        return new{Name=name,Scenario=adverse?"adverse":"central",Scorecard=score,Ledger=last,FullSettlementKnown=settled,
            UnknownLifecycleCount=unsettled,UncertainTrades=uncertainTrades,Rejections=counts,Admissions=admissions,Trades=trades,
            NetDistribution=Metrics(trades.Select(x=>x.NetEur).ToArray()),RDistribution=Metrics(trades.Select(x=>x.NetEur/risks.Single(r=>r.PositionId==x.PositionId).RiskEur).ToArray()),
            InitialRewardRiskDistribution=Metrics(rr.ToArray()),SampledFloatingDrawdown=last.MaximumSampledDrawdown,
            ContinuousRiskCertified=false,Qualified=false};
    }
    public static int Run(string path,string output)
    {
        var input=JsonSerializer.Deserialize<Input>(File.ReadAllBytes(path),Json)??throw new Exception("LPM1_INPUT");
        if(input.End-input.Start!=12*Week || input.Contract.Symbol!="EURUSD" || input.Days.Length!=60)throw new Exception("LPM1_FROZEN_POPULATION");
        NativeBrokerContractCosts.Validate(input.Contract,input.Contract.MinimumUnits);
        var bars=input.Bars.Select(Bar).OrderBy(x=>x.OpenAt).ToArray();var m15=Aggregate(bars);
        var days=new List<Prepared>();var samples=new List<Sample>();
        foreach(var d in input.Days)
        {
            var ready=Prepare(input,d,bars,m15);int di=days.Count;days.Add(ready);
            for(int c=0;c<ready.Candidates.Length;c++)for(int a=0;a<6;a++)
                if(ready.Adverse[c][a] is PathResult p && !p.Uncertain)
                {var cand=ready.Candidates[c];samples.Add(new(di,c,a,cand.Week,cand.Cell,p.Net));}
            Console.WriteLine("LPM1_NATIVE_PATH_DAY "+days.Count);
        }
        var contextual=Enumerable.Range(0,6).Select(a=>Fit(samples,a,true)).ToArray();
        var pooled=Enumerable.Range(0,6).Select(a=>Fit(samples,a,false)).ToArray();
        var prediction=new List<object>();
        foreach(bool context in new[]{true,false})for(int a=0;a<6;a++)
        {
            var model=(context?contextual:pooled)[a];if(model is null)continue;
            foreach(var phase in new[]{"calibration","evaluation"})
            {
                var selected=samples.Where(x=>x.Action==a&&(phase=="calibration"?x.Week>=6&&x.Week<9:x.Week>=9)).ToArray();
                prediction.Add(new{Context=context,Action=a,Phase=phase,Count=selected.Length,
                    MAE=selected.Length==0?(decimal?)null:selected.Average(x=>Math.Abs(x.Net-(context?model.Means[x.Cell]:model.Global)-(phase=="evaluation"?model.Bias:0))),
                    Brier=selected.Length==0?(decimal?)null:selected.Average(x=>{decimal p=context?model.Wins[x.Cell]:model.Win;return (p-(x.Net>0?1:0))*(p-(x.Net>0?1:0));})});
            }
        }
        var books=new Dictionary<string,object>();
        void Save()=>File.WriteAllText(output,JsonSerializer.Serialize(new{Study="LPM1",SourceSha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant(),
            CandidateCountsByWeek=Enumerable.Range(0,12).ToDictionary(w=>Iso(input.Start+w*Week),w=>days.Sum(d=>d.Candidates.Count(c=>c.Week==w))),
            CompleteUnambiguousLabels=samples.Count,UnknownOrUncertainLabels=days.Sum(d=>d.Candidates.Length)*6-samples.Count,
            ContextModels=contextual,PooledModels=pooled,PredictionDiagnostics=prediction,Books=books,
            AllWeeksGloballyExposed=true,IndependentConfirmation=false,Qualified=false,OrdersSubmitted=0,CloudActivated=false}));
        Save();
        foreach(bool adverse in new[]{false,true})
        {
            foreach(var name in new[]{"CONTEXT","POOLED","CASH"})
            {books[name+(adverse?"_adverse":"_central")]=Book(input,days,name=="CONTEXT"?contextual:pooled,name,adverse);Save();}
            for(int a=0;a<6;a++){string name=Modes[a/2]+(a%2==0?"_LONG":"_SHORT");books[name+(adverse?"_adverse":"_central")]=Book(input,days,pooled,name,adverse,a);Save();}
        }
        return 0;
    }
}
