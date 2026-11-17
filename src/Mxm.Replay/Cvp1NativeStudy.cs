using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;
using V=Mxm.Core.NativeContextValueResearch;

internal static class Cvp1NativeStudy
{
    const long Minute=60000,DayMs=86400000,Week=7*DayMs;
    static readonly string[] Frames={"M1","M5","M15","M30","H1","H4","D1"};
    static readonly string[] Variants={"FULL","NO_PEER","NO_ACTIVITY"};
    static readonly JsonSerializerOptions Json=new(){NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString};
    sealed record RawDay(long Start,long[][] Bid,long[][] Ask);
    sealed record Market(string Name,NativeObservedContractTerms Contract,decimal MinMargin,decimal TickSize,Dictionary<string,long[][]> Frames,RawDay[] Days);
    sealed record Input(long Start,long End,Market[] Markets);
    sealed record Tick(long At,decimal Bid,decimal Ask,bool Uncertain);
    sealed record State(double[] X,decimal Atr,decimal Equilibrium,decimal Low,decimal High,double Efficiency,decimal Impulse);
    sealed record Candidate(int Market,int Family,int Side,long At,State State,decimal Stop,decimal Target,decimal Risk,decimal Scale);
    sealed record PathResult(long FillAt,long TriggerAt,long ExitAt,decimal EntryPrice,decimal Stop,decimal Target,decimal Net,decimal Mfe,decimal Mae,string Reason,bool Uncertain,bool Canceled=false);
    sealed record Sample(int Week,int Family,int Side,string Symbol,long At,double[] X,double Outcome,decimal Net,decimal Scale,string Reason,decimal Mfe,decimal Mae);
    sealed record EntryModel(double[] Beta,double Bias,double[] Residual,int Train,int Calibration);
    sealed record Pipeline(string Variant,double[] Continuation,int Iterations,bool Converged,int Transitions,EntryModel?[] Entry,List<Sample> Samples,Dictionary<string,int> Census);
    sealed class Day
    {
        public required long Start;public required Tick[][] Ticks;
        public Dictionary<(int,long),State?> States=new();public Candidate[] Candidates=Array.Empty<Candidate>();
    }
    sealed class Position
    {
        public required string Id;public required Candidate C;public required PathResult Path;
        public required decimal Slip;public bool Filled;public bool CloseRequested;public long CloseAt;
        public string Reason="";public decimal EntryPrice;public decimal Extreme;public decimal Mfe;public decimal Mae;
        public bool Uncertain;
    }
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static string Iso(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;return System.Globalization.ISOWeek.GetYear(d)+"-W"+System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");}
    static int Lower(Tick[] ticks,long at){int lo=0,hi=ticks.Length;while(lo<hi){int m=(lo+hi)/2;if(ticks[m].At<at)lo=m+1;else hi=m;}return lo;}
    static NativeClosedMarketBar Bar(long[] b)=>new(b[0],b[1],b[2]/100000m,b[3]/100000m,b[4]/100000m,b[5]/100000m,b[6]);
    static Tick[] Decode(RawDay d)
    {
        var rows=new List<Tick>();int b=0,a=0;decimal bid=0,ask=0;long bt=0,at=0,last=0;bool missing=false;
        while(b<d.Bid.Length||a<d.Ask.Length)
        {
            long t=Math.Min(b<d.Bid.Length?d.Bid[b][0]:long.MaxValue,a<d.Ask.Length?d.Ask[a][0]:long.MaxValue);
            decimal? sb=null,sa=null;bool uncertain=false;
            while(b<d.Bid.Length&&d.Bid[b][0]==t){decimal x=d.Bid[b++][1]/100000m;uncertain|=sb.HasValue&&sb!=x;sb=x;bid=x;bt=t;}
            while(a<d.Ask.Length&&d.Ask[a][0]==t){decimal x=d.Ask[a++][1]/100000m;uncertain|=sa.HasValue&&sa!=x;sa=x;ask=x;at=t;}
            if(bid<=0||ask<bid||t-bt>30000||t-at>30000){missing=true;continue;}
            rows.Add(new(t,bid,ask,uncertain||missing||(last>0&&t-last>30000)));last=t;missing=false;
        }
        return rows.ToArray();
    }
    static Tick? AsOf(Day d,int m,long t){int i=Lower(d.Ticks[m],t+1)-1;return i>=0&&t-d.Ticks[m][i].At<=30000?d.Ticks[m][i]:null;}
    static LedgerQuote? Quote(Input input,Day d,int m,long t)
    {
        var q=AsOf(d,m,t);var eur=AsOf(d,0,t);if(q is null||eur is null)return null;
        var market=input.Markets[m];
        return NativeBrokerContractCosts.Quote(market.Contract,new(t,q.Bid,q.Ask,1m/eur.Ask,1m/eur.Bid,(1m/eur.Ask+1m/eur.Bid)/2,null,market.MinMargin,market.Contract.MinimumUnits,0)).Quote;
    }
    static decimal Fee(LedgerQuote q,decimal units)=>Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);
    static decimal Money(LedgerQuote q,decimal x)=>x*(x>=0?q.EurCredit:q.EurDebit);
    static decimal Slip(Market m,LedgerQuote q,bool adverse)=>Math.Max(m.TickSize,(q.Ask-q.Bid)*(adverse?1m:.25m));
    static long Clock(long t)=>(t-1500)/Minute*Minute+1500;
    static State? GetState(Input input,Day d,Dictionary<string,NativeClosedMarketBar[]>[] bars,int m,long t)
    {
        t=Clock(t);if(d.States.TryGetValue((m,t),out var saved))return saved;
        State? Result()
        {
            var quote=Quote(input,d,m,t);if(quote is null)return null;
            var parts=new double[7][];var windows=new NativeClosedMarketBar[7][];
            for(int f=0;f<7;f++)
            {
                var all=bars[m][Frames[f]];int lo=0,hi=all.Length;
                while(lo<hi){int mid=(lo+hi)/2;if(all[mid].CloseAt<t)lo=mid+1;else hi=mid;}
                if(lo<64)return null;var w=all.Skip(lo-64).Take(64).ToArray();
                if(f<=1&&(t-w[^1].CloseAt>(f==0?Minute:5*Minute)+1500||w.Zip(w.Skip(1)).Any(x=>x.First.CloseAt!=x.Second.OpenAt)))return null;
                parts[f]=V.Frame(w);windows[f]=w;
            }
            var x=new double[35];for(int f=0;f<7;f++)Array.Copy(parts[f],0,x,4*f,4);
            decimal atr=(decimal)parts[1][4];decimal impulse=windows[0][^1].Close-windows[0][^2].Close;
            x[28]=V.Clip((double)(impulse/atr));x[29]=V.Clip((double)(atr/quote.Bid)*10000);
            x[30]=V.Clip((double)((quote.Ask-quote.Bid)/atr));x[31]=V.Clip((t-d.Start-8*60*Minute)/(double)(3*60*Minute));
            var peersH=new List<double>();var peersD=new List<double>();
            for(int peer=0;peer<input.Markets.Length;peer++)if(peer!=m)
            {
                foreach(var pair in new[]{("H1",peersH),("D1",peersD)})
                {
                    var w=bars[peer][pair.Item1].Where(b=>b.CloseAt<t).TakeLast(64).ToArray();
                    if(w.Length!=64)return null;pair.Item2.Add(V.Frame(w)[0]);
                }
            }
            x[32]=V.Clip(peersH.Average());x[33]=V.Clip(peersD.Average());x[34]=V.Clip(parts[4][0]-x[32]);
            var h=windows[4].TakeLast(21).ToArray();decimal travel=h.Zip(h.Skip(1)).Sum(z=>Math.Abs(z.Second.Close-z.First.Close));
            double eff=travel>0?(double)(Math.Abs(h[^1].Close-h[0].Close)/travel):0;
            return new(x,atr,(decimal)parts[4][5],windows[0].TakeLast(20).Min(b=>b.Low),windows[0].TakeLast(20).Max(b=>b.High),eff,impulse);
        }
        var state=Result();d.States[(m,t)]=state;return state;
    }
    static bool Eligible(State s,LedgerQuote q,int family,int side,decimal tick)
    {
        if(side*s.Impulse<=0)return false;
        if(family==0)return side*s.X[16]>0&&side*s.X[9]>0;
        decimal mid=(q.Ask+q.Bid)/2;
        return s.Efficiency<.35 && side*(s.Equilibrium-mid)>2*(q.Ask-q.Bid)+tick;
    }
    static Candidate[] Candidates(Input input,Day d,Dictionary<string,NativeClosedMarketBar[]>[] bars)
    {
        var result=new List<Candidate>();
        for(long t=d.Start+8*60*Minute+1500;t<=d.Start+(9*60+55)*Minute+1500;t+=5*Minute)
        for(int m=0;m<input.Markets.Length;m++)
        {
            var state=GetState(input,d,bars,m,t);var q=Quote(input,d,m,t);if(state is null||q is null)continue;
            var market=input.Markets[m];decimal units=market.Contract.MinimumUnits;
            for(int family=0;family<2;family++)foreach(int side in new[]{1,-1})
            {
                if(!Eligible(state,q,family,side,market.TickSize))continue;
                decimal slip=Slip(market,q,true),entry=side>0?q.Ask+slip:q.Bid-slip;
                decimal stop=side>0?state.Low-.25m*state.Atr:state.High+.25m*state.Atr;
                decimal target=family==1?state.Equilibrium:0;
                if(side*(entry-stop)<=0)continue;
                var guard=NativeCausalExitResearch.AssessValueProtection(side,entry,stop,target,state.Atr,entry,q,0,false);
                if(guard.RequestClose)continue;
                decimal risk=side*(entry-stop)*units*q.EurDebit+2*Fee(q,units)+2*slip*units*q.EurDebit;
                result.Add(new(m,family,side,t,state,stop,target,risk,state.Atr*units*q.EurDebit));
            }
        }
        return result.OrderBy(c=>c.At).ThenBy(c=>input.Markets[c.Market].Name,StringComparer.Ordinal).ThenBy(c=>c.Family).ThenByDescending(c=>c.Side).ToArray();
    }
    static (double[] Beta,int Iterations,bool Converged,int Count) FitContinuation(Input input,List<Day> days,Dictionary<string,NativeClosedMarketBar[]>[] bars,string variant)
    {
        var xs=new List<double[]>();var next=new List<double[]>();var reward=new List<double>();var terminal=new List<bool>();
        foreach(var d in days.Where(d=>d.Start<input.Start+4*Week))for(int m=0;m<input.Markets.Length;m++)
        for(long t=d.Start+8*60*Minute+1500;t<d.Start+11*60*Minute-60000;t+=Minute)
        {
            var a=GetState(input,d,bars,m,t);var b=GetState(input,d,bars,m,t+Minute);var q=Quote(input,d,m,t);var z=Quote(input,d,m,t+Minute);
            if(a is null||b is null||q is null||z is null||AsOf(d,m,t)?.Uncertain!=false||AsOf(d,m,t+Minute)?.Uncertain!=false||AsOf(d,0,t)?.Uncertain!=false||AsOf(d,0,t+Minute)?.Uncertain!=false)continue;
            foreach(int side in new[]{1,-1})
            {xs.Add(V.Orient(a.X,side,variant));next.Add(V.Orient(b.X,side,variant));reward.Add((double)(side*((side>0?z.Bid:z.Ask)-(side>0?q.Bid:q.Ask))/a.Atr));terminal.Add(t+2*Minute>=d.Start+11*60*Minute);}
        }
        if(xs.Count<1000)throw new Exception("CVP1_CONTINUATION_TRAIN_SOURCE_SMALL");
        var x=xs.ToArray();var beta=new double[36];bool converged=false;int iteration=0;
        for(;iteration<32;iteration++)
        {
            var y=Enumerable.Range(0,x.Length).Select(i=>reward[i]+(terminal[i]?0:.995*Math.Max(0,V.Clip(V.Predict(beta,next[i]))))).ToArray();
            var fitted=V.Ridge(x,y);double delta=fitted.Zip(beta).Max(z=>Math.Abs(z.First-z.Second));beta=fitted;
            if(delta<1e-8){converged=true;iteration++;break;}
        }
        return(beta,iteration,converged,x.Length);
    }
    static PathResult? Trace(Input input,Day d,Dictionary<string,NativeClosedMarketBar[]>[] bars,Candidate c,Pipeline p,bool adverse,bool protectionOnly=false)
    {
        var market=input.Markets[c.Market];var tape=d.Ticks[c.Market];var request=Quote(input,d,c.Market,c.At);if(request is null)return null;
        int start=Lower(tape,c.At+100);while(start<tape.Length&&Quote(input,d,c.Market,tape[start].At) is null)start++;
        if(start==tape.Length)return null;long fillAt=tape[start].At;var fill=Quote(input,d,c.Market,fillAt)!;
        decimal slip=Slip(market,request,adverse),entry=c.Side>0?fill.Ask+slip:fill.Bid-slip;
        if(c.Side*(entry-c.Stop)<=0 || NativeCausalExitResearch.AssessValueProtection(c.Side,entry,c.Stop,c.Target,c.State.Atr,entry,fill,0,false).RequestClose)
            return new(fillAt,fillAt,fillAt,entry,c.Stop,c.Target,0,0,0,"ENTRY_ALREADY_INVALID_AT_FILL",false,true);
        var fillState=GetState(input,d,bars,c.Market,fillAt);
        if(fillState is null||!Eligible(fillState,fill,c.Family,c.Side,market.TickSize)||(!protectionOnly&&V.Predict(p.Continuation,V.Orient(fillState.X,c.Side,p.Variant))<=0))
            return new(fillAt,fillAt,fillAt,entry,c.Stop,c.Target,0,0,0,"ENTRY_CONTEXT_INVALID_AT_FILL",false,true);
        decimal extreme=entry,mfe=0,mae=0,costLock=0;bool uncertain=tape[start].Uncertain||AsOf(d,0,fillAt)?.Uncertain!=false;long lastMinute=Clock(fillAt);
        for(int i=start+1;i<tape.Length;i++)
        {
            long t=tape[i].At;var q=Quote(input,d,c.Market,t);if(q is null){uncertain=true;continue;}
            uncertain|=tape[i].Uncertain||AsOf(d,0,t)?.Uncertain!=false;decimal gain=c.Side*((c.Side>0?q.Bid:q.Ask)-entry);
            mfe=Math.Max(mfe,gain);mae=Math.Max(mae,-gain);
            decimal costs=Fee(q,market.Contract.MinimumUnits)/(market.Contract.MinimumUnits*q.EurDebit)+Slip(market,q,adverse);
            costLock=Math.Max(costLock,costs);
            var guard=NativeCausalExitResearch.AssessValueProtection(c.Side,entry,c.Stop,c.Target,c.State.Atr,extreme,q,costLock,t>=d.Start+11*60*Minute);
            extreme=guard.FavorableExtreme;bool close=guard.RequestClose;string reason=guard.Reason;
            long minute=Clock(t);
            if(!close&&!protectionOnly&&minute>lastMinute)
            {
                var state=GetState(input,d,bars,c.Market,t);lastMinute=minute;
                if(state is null){uncertain=true;continue;}
                if(V.Predict(p.Continuation,V.Orient(state.X,c.Side,p.Variant))<=0){close=true;reason="LEARNED_CONTINUATION_NONPOSITIVE";}
            }
            if(!close)continue;
            int exit=Lower(tape,t+100);while(exit<tape.Length&&Quote(input,d,c.Market,tape[exit].At) is null){uncertain=true;exit++;}
            if(exit==tape.Length)return null;var qx=Quote(input,d,c.Market,tape[exit].At)!;
            decimal px=c.Side>0?qx.Bid-Slip(market,qx,adverse):qx.Ask+Slip(market,qx,adverse);
            decimal net=Money(qx,c.Side*market.Contract.MinimumUnits*(px-entry))-Fee(fill,market.Contract.MinimumUnits)-Fee(qx,market.Contract.MinimumUnits);
            return new(fillAt,t,tape[exit].At,entry,c.Stop,c.Target,net,mfe,mae,reason,uncertain||tape[exit].Uncertain||AsOf(d,0,tape[exit].At)?.Uncertain!=false);
        }
        return null;
    }
    static Pipeline Learn(Input input,List<Day> days,Dictionary<string,NativeClosedMarketBar[]>[] bars,string variant)
    {
        var fit=FitContinuation(input,days,bars,variant);var samples=new List<Sample>();
        var p=new Pipeline(variant,fit.Beta,fit.Iterations,fit.Converged,fit.Count,new EntryModel?[2],samples,new());
        foreach(var d in days.Where(d=>d.Start>=input.Start+4*Week))foreach(var c in d.Candidates)
        {
            var x=V.Orient(c.State.X,c.Side,variant);
            void Count(string reason){string key=((d.Start-input.Start)/Week)+"/"+c.Family+"/"+reason;p.Census[key]=p.Census.GetValueOrDefault(key)+1;}
            Count("COMPATIBLE_PROTECTION");
            if(V.Predict(fit.Beta,x)<=0){Count("CONTINUATION_NONPOSITIVE");continue;}
            var path=Trace(input,d,bars,c,p,true);
            if(path is null){Count("FUTURE_PATH_UNSETTLED");continue;}
            if(path.Uncertain){Count("FUTURE_PATH_UNCERTAIN");continue;}
            Count(path.Canceled?"CAUSAL_FILL_CANCEL":"KNOWN_COMPLETE_PATH");
            samples.Add(new((int)((d.Start-input.Start)/Week),c.Family,c.Side,input.Markets[c.Market].Name,c.At,x,(double)(path.Net/c.Scale),path.Net,c.Scale,path.Reason,path.Mfe,path.Mae));
        }
        for(int family=0;family<2;family++)
        {
            var train=samples.Where(s=>s.Family==family&&s.Week>=4&&s.Week<6).ToArray();
            var cal=samples.Where(s=>s.Family==family&&s.Week>=6&&s.Week<9).ToArray();
            if(train.Length<40||cal.Length<20)continue;
            var beta=V.Ridge(train.Select(s=>s.X).ToArray(),train.Select(s=>s.Outcome).ToArray());
            var residual=cal.Select(s=>s.Outcome-V.Predict(beta,s.X)).Order().ToArray();double bias=residual.Average();
            p.Entry[family]=new(beta,bias,Enumerable.Range(0,16).Select(k=>residual[Math.Min(residual.Length-1,(int)((k+.5)*residual.Length/16))]-bias).ToArray(),train.Length,cal.Length);
        }
        return p;
    }
    static object Distribution(decimal[] xs)=>new{Count=xs.Length,Mean=xs.Length==0?(decimal?)null:xs.Average(),
        Quantiles=xs.Length==0?Array.Empty<decimal>():new[]{0m,.05m,.25m,.5m,.75m,.95m,1m}.Select(q=>xs.Order().ElementAt((int)(q*(xs.Length-1)))).ToArray(),Values=xs};
    static object Book(Input input,List<Day> days,Dictionary<string,NativeClosedMarketBar[]>[] bars,Pipeline pipeline,string name,bool adverse)
    {
        var session=new NativeFundedSession("CVP1_"+name+(adverse?"_A":"_C"),new NativeFundedLedger(30000));
        var ledger=session.Ledger;var positions=new Dictionary<string,Position>();var all=new Dictionary<string,Position>();
        var risk=new List<NativeEntryRisk>();var marks=new List<NativeEconomicMark>();var counts=new Dictionary<string,int>();
        int seq=0,unknown=0,canceled=0,unsettled=0,uncertainTrades=0,selectorCalls=0;bool suspend=false;
        decimal peak=300,maxDd=0,maxMargin=0,minFree=300;int maxConcurrent=0;
        void Count(string s)=>counts[s]=counts.GetValueOrDefault(s)+1;
        decimal Units(Candidate c)=>input.Markets[c.Market].Contract.MinimumUnits;
        LedgerEvent Fact(long t,string kind,Position? p=null,LedgerQuote? q=null,decimal price=0,string reason="CVP1")
        {
            string id="CVP1/"+name+"/"+(adverse?"A":"C")+"/"+(++seq);
            return new(id,t,kind,p?.Id??"",p is null?"":input.Markets[p.C.Market].Name,p?.C.Side??0,p is null?0:Units(p.C),price,
                p is null||q is null?0:Fee(q,Units(p.C)),q?.MarginPerUnit??0,p?.Slip??0,t,t-1,100,reason,Hash(id),q is null?Array.Empty<LedgerQuote>():new[]{q});
        }
        long NextFill(Day d,int m,long t)
        {int i=Lower(d.Ticks[m],t+100);while(i<d.Ticks[m].Length&&Quote(input,d,m,d.Ticks[m][i].At) is null)i++;return i<d.Ticks[m].Length?d.Ticks[m][i].At:long.MaxValue;}
        (decimal? Eq,decimal Margin,decimal ReservedRisk) Mark(Day d,long t,bool ledgerMark=true)
        {
            var quotes=Enumerable.Range(0,input.Markets.Length).Select(m=>Quote(input,d,m,t)).Where(q=>q is not null).Select(q=>q!).ToArray();
            if(ledgerMark)ledger.Apply(Fact(t,"MARK") with {Quotes=quotes});
            decimal equity=ledger.Summary(t).CashEur,margin=0,reserved=0;bool known=true;
            foreach(var p in positions.Values)
            {
                var q=quotes.FirstOrDefault(q=>q.Symbol==input.Markets[p.C.Market].Name);
                reserved+=p.C.Risk;
                if(!p.Filled)continue;
                if(q is null){known=false;continue;}
                var m=input.Markets[p.C.Market];decimal slip=Slip(m,q,adverse);
                decimal liq=p.C.Side>0?q.Bid-slip:q.Ask+slip;
                equity+=Money(q,p.C.Side*Units(p.C)*(liq-p.EntryPrice))-Fee(q,Units(p.C));
                margin+=q.MarginPerUnit*Units(p.C);
                decimal grossGain=p.C.Side*((p.C.Side>0?q.Bid:q.Ask)-p.EntryPrice);
                p.Mfe=Math.Max(p.Mfe,grossGain);p.Mae=Math.Max(p.Mae,-grossGain);
                // Conservative remaining-risk reserve, no diversification credit.
                reserved+=Math.Max(0,Money(q,p.C.Side*((p.C.Side>0?q.Bid:q.Ask)-p.C.Stop)*Units(p.C))-p.C.Risk);
                bool uncertain=AsOf(d,p.C.Market,t)?.Uncertain!=false||AsOf(d,0,t)?.Uncertain!=false;
                p.Uncertain|=uncertain;known&=!uncertain;
            }
            if(!known)unknown++;
            if(known){peak=Math.Max(peak,equity);maxDd=Math.Max(maxDd,(peak-equity)/peak);maxMargin=Math.Max(maxMargin,margin);minFree=Math.Min(minFree,equity-margin);}
            maxConcurrent=Math.Max(maxConcurrent,positions.Values.Count(p=>p.Filled));
            marks.Add(new(t,known?equity:null,known?margin:null,known?equity-margin:null,positions.Values.Count(p=>p.Filled),known));
            return(known?equity:null,margin,reserved);
        }
        foreach(var day in days.Where(d=>d.Start>=input.Start+9*Week))
        {
            var offers=day.Candidates.GroupBy(c=>c.At).ToDictionary(g=>g.Key,g=>g.ToArray());
            var times=day.Ticks.SelectMany(x=>x).Select(t=>t.At).Concat(offers.Keys).Distinct().Order().ToArray();
            foreach(long t in times)
            {
                bool hasOffers=offers.ContainsKey(t);
                if(positions.Count==0&&!hasOffers)continue;
                bool changed=false;var state=Mark(day,t,hasOffers||positions.Values.Any(p=>t==p.Path.FillAt||t==p.Path.TriggerAt||t==p.CloseAt));
                if(state.Eq.HasValue&&(peak-state.Eq.Value)/peak>=.30m)suspend=true;
                foreach(var p in positions.Values.ToArray())
                {
                    var q=Quote(input,day,p.C.Market,t);if(q is null)continue;
                    if(!p.Filled&&t==p.Path.FillAt)
                    {
                        if(p.Path.Canceled||state.Eq is null||state.Eq-state.Margin<=input.Markets[p.C.Market].MinMargin+2*Fee(q,Units(p.C)))
                        {ledger.Apply(Fact(t,"CONFIRMED_CANCEL",p,reason:p.Path.Canceled?"ENTRY_ALREADY_INVALID_AT_FILL":"UNFINANCED_AT_FILL"));positions.Remove(p.Id);changed=true;canceled++;continue;}
                        try{ledger.Apply(Fact(t,"OPEN_FILL",p,q,p.Path.EntryPrice));}
                        catch(InvalidOperationException ex) when(ex.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL")
                        {ledger.Apply(Fact(t,"CONFIRMED_CANCEL",p,reason:"UNFINANCED_AT_FILL"));positions.Remove(p.Id);changed=true;canceled++;continue;}
                        changed=true;p.Filled=true;p.EntryPrice=p.Path.EntryPrice;p.Extreme=p.EntryPrice;
                        risk.Add(new(p.Id,p.C.Risk,p.C.At,Hash(p.Id+"risk")));all[p.Id]=p;
                    }
                    if(!p.Filled)continue;
                    if(!p.CloseRequested&&(t==p.Path.TriggerAt||suspend))
                    {
                        p.Reason=suspend?"SYSTEM_FLOATING_DD_PROTECTION":p.Path.Reason;
                        ledger.Apply(Fact(t,"REQUEST_CLOSE",p,q,reason:p.Reason));p.CloseRequested=true;
                        p.CloseAt=suspend?NextFill(day,p.C.Market,t):p.Path.ExitAt;
                    }
                    if(p.CloseRequested&&t==p.CloseAt)
                    {
                        decimal sl=Slip(input.Markets[p.C.Market],q,adverse),px=p.C.Side>0?q.Bid-sl:q.Ask+sl;
                        ledger.Apply(Fact(t,"CLOSE_FILL",p,q,px,p.Reason) with {ObservedExitSlippagePerSide=sl});
                        if(p.Uncertain||p.Path.Uncertain)uncertainTrades++;
                        positions.Remove(p.Id);changed=true;
                    }
                }
                if(changed)state=Mark(day,t);
                if(!hasOffers||name=="CASH"||suspend)continue;
                if(state.Eq is not decimal eq){Count("CURRENT_PORTFOLIO_MARK_UNKNOWN");continue;}
                decimal free=eq-state.Margin,capacity=eq-.7m*peak-state.ReservedRisk;
                var candidates=offers[t].Where(c=>!positions.Values.Any(p=>p.C.Market==c.Market)).ToArray();
                var opportunities=new List<EconomicOpportunity>();var lookup=new Dictionary<string,Candidate>();
                long known=input.Start+9*Week-1;
                var states=Enumerable.Range(0,16).Select(j=>new PortfolioScenario("CVP1_COMONOTONE_"+j,known,true,0,0,0,0)).ToArray();
                foreach(var c in candidates)
                {
                    Count("COMPATIBLE_CURRENT_OPPORTUNITY");
                    if((name=="FLOW_ONLY"&&c.Family!=0)||(name=="RETURN_ONLY"&&c.Family!=1))continue;
                    if(c.Risk>capacity){Count("COMMON_FLOATING_RISK_CAPACITY");continue;}
                    string id="CVP1/"+name+"/"+t+"/"+input.Markets[c.Market].Name+"/"+c.Family+"/"+c.Side;
                    var q=Quote(input,day,c.Market,t)!;var market=input.Markets[c.Market];
                    if(name=="SIMPLE")
                    {
                        if(positions.Values.Any(p=>p.C.Market==c.Market))continue;
                        if(free<=market.MinMargin+2*Fee(q,Units(c))){Count("SIMPLE_MARGIN_REJECTED");continue;}
                        var path=Trace(input,day,bars,c,pipeline,adverse,true);
                        var p=new Position{Id=id,C=c,Path=path??new(long.MaxValue,0,0,0,c.Stop,c.Target,0,0,0,"UNKNOWN",true),Slip=Slip(market,q,adverse)};
                        ledger.Apply(Fact(t,"REQUEST_OPEN",p,q));positions[id]=p;
                        free-=market.MinMargin+2*Fee(q,Units(c));capacity-=c.Risk;
                        if(path is null){unsettled++;suspend=true;Count("SELECTED_FUTURE_PATH_UNKNOWN");}
                        continue;
                    }
                    var model=pipeline.Entry[c.Family];if(model is null){Count("ENTRY_TRAIN_CALIBRATION_UNAVAILABLE");continue;}
                    var x=V.Orient(c.State.X,c.Side,pipeline.Variant);
                    if(V.Predict(pipeline.Continuation,x)<=0){Count("ENTRY_NOT_COMPATIBLE_WITH_LEARNED_HOLD");continue;}
                    double mean=V.Predict(model.Beta,x)+model.Bias;
                    decimal units=Units(c);var grid=new AdaptiveRiskInputs(eq,0,free,units,market.Contract.VolumeStepUnits,units,q.MarginPerUnit,1,false,false,3,1);
                    opportunities.Add(new(id,c.Family==0?"CVP1_FLOW":"CVP1_RETURN",market.Name,market.Name,c.Side,t,known,EvidenceLevel.Exploratory,false,grid,
                        model.Residual.Select((z,j)=>{decimal net=(decimal)(mean+z)*c.Scale;return new OpportunityScenario(states[j].StateId,known,true,net/units,0,Math.Max(c.Risk,-net)/units,Math.Max(0,net)/units);}).ToArray()));lookup[id]=c;
                }
                if(name!="SIMPLE"&&opportunities.Count>0)
                {
                    var exposures=positions.Values.Select(p=>new ResearchExposureScenarios(p.Id,input.Markets[p.C.Market].Name,p.C.Side,Units(p.C),
                        states.Select(s=>s with {NetEur=-p.C.Risk,LossEur=p.C.Risk,MarginEur=input.Markets[p.C.Market].MinMargin}).ToArray())).ToArray();
                    var decision=new NativeResearchDecision("CVP1/"+name+"/"+t,t,new(eq,Math.Max(peak,ledger.Summary(t).ObservedPeakEur),free,1,1,1,1,1,3,1),states,opportunities.ToArray(),exposures,
                        opportunities.Select(o=>new ResearchEntryTerms(o.Id,100,Slip(input.Markets[lookup[o.Id].Market],Quote(input,day,lookup[o.Id].Market,t)!,adverse),Hash(o.Id))).ToArray(),Hash(name+t));
                    var selected=session.DecideResearch(decision);ledger=session.Ledger;selectorCalls++;
                    foreach(var rejected in selected.Selection.Declined)Count(rejected.Reason);
                    foreach(var allocation in selected.Selection.Allocations)
                    {
                        var c=lookup[allocation.Id];var q=Quote(input,day,c.Market,t)!;
                        var path=Trace(input,day,bars,c,pipeline,adverse,name=="PROTECT_ONLY");
                        var p=new Position{Id=allocation.Id,C=c,Path=path??new(long.MaxValue,0,0,0,c.Stop,c.Target,0,0,0,"UNKNOWN",true),Slip=Slip(input.Markets[c.Market],q,adverse)};
                        if(c.Risk>capacity){ledger.Apply(Fact(t,"CONFIRMED_CANCEL",p,reason:"JOINT_SHADOW_FLOATING_RISK_CAPACITY"));Count("JOINT_SHADOW_FLOATING_RISK_CAPACITY");continue;}
                        positions[p.Id]=p;capacity-=c.Risk;
                        if(path is null){unsettled++;suspend=true;Count("SELECTED_FUTURE_PATH_UNKNOWN");}
                    }
                }
            }
            if(positions.Count>0){unsettled++;break;}
        }
        var last=ledger.Summary();var trades=ledger.ClosedFragments();bool settled=positions.Count==0&&last.PendingIntents==0&&last.OpenPositions==0&&unsettled==0;
        var card=NativePerformanceScorecard.Calculate(new(name,trades,marks.ToArray(),risk.ToArray(),Enumerable.Range(9,3).Select(w=>Iso(input.Start+w*Week)).ToArray(),300,settled?last.ClosedNetEur:null,0,settled,false,false));
        return new{Name=name,Scenario=adverse?"adverse":"central",Scorecard=card,Ledger=last,FullSettlementKnown=settled,
            Rejections=counts,SelectorCalls=selectorCalls,CanceledPendingEntries=canceled,UnknownLifecycles=unsettled,UnknownHoldingMarks=unknown,UncertainTrades=uncertainTrades,
            SampledCurrentExitCostFloatingDrawdown=maxDd,PeakCurrentMarginEur=maxMargin,MinimumCurrentFreeMarginEur=minFree,MaximumConcurrentPositions=maxConcurrent,
            Trades=trades,Entries=all.Values.Select(p=>new{p.Id,Symbol=input.Markets[p.C.Market].Name,Family=p.C.Family==0?"FLOW":"RETURN",p.C.Side,At=p.C.At,InitialRiskEur=p.C.Risk,
                InitialRewardRisk=p.C.Target>0?p.C.Side*(p.C.Target-p.EntryPrice)/(p.C.Side*(p.EntryPrice-p.C.Stop)):(decimal?)null,
                MfeQuote=p.Mfe,MaeQuote=p.Mae,p.Uncertain}).ToArray(),
            NetDistribution=Distribution(trades.Select(t=>t.NetEur).ToArray()),RDistribution=Distribution(trades.Select(t=>t.NetEur/all[t.PositionId].C.Risk).ToArray()),
            Mechanisms=trades.GroupBy(t=>all[t.PositionId].C.Family).ToDictionary(g=>g.Key==0?"FLOW":"RETURN",g=>new{Trades=g.Count(),NetEur=g.Sum(t=>t.NetEur),Reasons=g.GroupBy(t=>t.Reason).ToDictionary(z=>z.Key,z=>z.Count())}),
            PartialReduction="INFEASIBLE_BELOW_LEGAL_MINIMUM_IN_THIS_MINIMUM_UNIT_EXPERIMENT",Qualified=false,IndependentConfirmation=false};
    }
    public static int Run(string path,string output)
    {
        byte[] bytes=File.ReadAllBytes(path);string sourceHash=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        var input=JsonSerializer.Deserialize<Input>(bytes,Json)??throw new Exception("CVP1_EMPTY_INPUT");
        if(input.End-input.Start!=12*Week||!input.Markets.Select(m=>m.Name).SequenceEqual(new[]{"EURUSD","GBPUSD","AUDUSD"}))throw new Exception("CVP1_FROZEN_POPULATION");
        foreach(var m in input.Markets){NativeBrokerContractCosts.Validate(m.Contract,m.Contract.MinimumUnits);if(m.Days.Length!=60||!Frames.All(f=>m.Frames.ContainsKey(f)))throw new Exception("CVP1_SOURCE_ROLES");}
        var bars=input.Markets.Select(m=>m.Frames.ToDictionary(f=>f.Key,f=>f.Value.Select(Bar).OrderBy(b=>b.OpenAt).ToArray())).ToArray();
        var days=new List<Day>();
        for(int i=0;i<60;i++)
        {
            long t=input.Markets[0].Days[i].Start;if(input.Markets.Any(m=>m.Days[i].Start!=t))throw new Exception("CVP1_DAY_ALIGNMENT");
            var day=new Day{Start=t,Ticks=input.Markets.Select(m=>Decode(m.Days[i])).ToArray()};
            day.Candidates=Candidates(input,day,bars);days.Add(day);
        }
        var pipelines=new Dictionary<string,Pipeline>();var books=new Dictionary<string,object>();
        object[] Diagnostics()=>pipelines.Values.SelectMany(p=>Enumerable.Range(0,2).SelectMany(f=>new[]{"entry_train","calibration","evaluation"}.Select(phase=>
        {
            var samples=p.Samples.Where(s=>s.Family==f&&(phase=="entry_train"?s.Week<6:phase=="calibration"?s.Week>=6&&s.Week<9:s.Week>=9)).ToArray();var model=p.Entry[f];
            return (object)new{p.Variant,Family=f==0?"FLOW":"RETURN",Phase=phase,KnownSamples=samples.Length,
                NetEurDiagnostic=samples.Sum(s=>s.Net),
                MaeEur=model is null||samples.Length==0?(double?)null:samples.Average(s=>Math.Abs((V.Predict(model.Beta,s.X)+(phase=="evaluation"?model.Bias:0)-s.Outcome)*(double)s.Scale)),
                Brier=model is null||samples.Length==0?(double?)null:samples.Average(s=>{double mean=V.Predict(model.Beta,s.X)+model.Bias;double win=model.Residual.Count(z=>mean+z>0)/16d;return Math.Pow(win-(s.Net>0?1:0),2);}),
                StopTargetReasons=samples.GroupBy(s=>s.Reason).ToDictionary(g=>g.Key,g=>g.Count()),
                MfeQuote=samples.Length==0?(decimal?)null:samples.Average(s=>s.Mfe),MaeQuote=samples.Length==0?(decimal?)null:samples.Average(s=>s.Mae)};
        }))).ToArray();
        void Save()=>File.WriteAllText(output,JsonSerializer.Serialize(new{Study="CVP1",SourceSha256=sourceHash,StartingCapitalEur=300,
            SourceTimeframes=Frames,Symbols=input.Markets.Select(m=>m.Name),
            CandidateCounts=days.GroupBy(d=>Iso(d.Start)).ToDictionary(g=>g.Key,g=>g.SelectMany(d=>d.Candidates).GroupBy(c=>c.Family).ToDictionary(z=>z.Key==0?"FLOW":"RETURN",z=>z.Count())),
            ScheduledEntryClocksPerSymbolPerWeek=120,Models=pipelines.ToDictionary(p=>p.Key,p=>new{p.Value.Continuation,p.Value.Iterations,p.Value.Converged,p.Value.Transitions,p.Value.Entry,p.Value.Census}),
            PredictiveDiagnostics=Diagnostics(),Books=books,OriginalClosedPoliciesInvoked=false,AllCalendarsExposed=true,Qualified=false,IndependentConfirmation=false,OrdersSubmitted=0,CloudActivated=false}));
        Save();
        foreach(string variant in Variants){pipelines[variant]=Learn(input,days,bars,variant);Save();Console.WriteLine("CVP1_NATIVE_LEARNED "+variant);}
        foreach(bool adverse in new[]{false,true})foreach(string name in new[]{"FULL","NO_PEER","NO_ACTIVITY","PROTECT_ONLY","SIMPLE","FLOW_ONLY","RETURN_ONLY","CASH"})
        {
            var model=pipelines[name is "NO_PEER" or "NO_ACTIVITY"?name:"FULL"];
            books[name+(adverse?"_adverse":"_central")]=Book(input,days,bars,model,name,adverse);Save();Console.WriteLine("CVP1_NATIVE_BOOK "+name+" "+adverse);
        }
        return 0;
    }
}
