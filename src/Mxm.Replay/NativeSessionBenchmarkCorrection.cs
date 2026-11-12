using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class NativeSessionBenchmarkCorrection
{
    private static readonly string[] SemTargets = { "NAS100", "XAGEUR", "ETHEUR" };
    private static readonly string[] Policies = { "Filtered", "Momentum", "Long", "Short", "Cash" };
    private static readonly JsonSerializerOptions Wire = new() { NumberHandling = JsonNumberHandling.AllowReadingFromString };
    private const long Minute = 60000;
    private sealed record Tape(string SourceLabel, NativeHistoricalBars[] Bars, NativeOriginalOpenApiMarketMark[] Marks,
        Dictionary<string, NativeSessionEconomicsMap.Schedule>? Schedules);
    private sealed record Candidate(string Symbol, long Entry, long Exit, int Signal, int Momentum,
        NativeOriginalOpenApiMarketMark? First, NativeOriginalOpenApiMarketMark? Last, bool ContractOpen);
    private sealed record Position(Candidate Candidate, int Side, decimal Units, decimal EntrySlip, string Id);
    private sealed record Outcome(int CompleteTrips, int OpenPositions, int UnobservedFixedExits, decimal GrossEur,
        decimal ClosedNetEur, decimal CashEur, decimal PeakMarginEur, int PeakConcurrentPositions,
        decimal MaxSampledDrawdown, int MarkClocksWithoutFullEquity, Dictionary<string,int> Rejections,
        Dictionary<string,int> TripsByWeek, Dictionary<string,decimal> ClosedNetByWeek, Dictionary<string,int> TripsBySymbol,
        string EventChainHash);

    internal static int Run(string semPath, string esdPath, string output)
    {
        try
        {
            var sem = Read(semPath, "ORIGINAL_PEPPERSTONE_SEM1");
            var esd = Read(esdPath, "ORIGINAL_PEPPERSTONE_ESD1");
            var semResults = new Dictionary<string,object>();
            foreach (int horizon in new[] {30,90})
            {
                var candidates = SemCandidates(sem.Tape,horizon);
                semResults.Add($"{horizon}m", new {
                    Joint = Compare(sem.Tape, candidates, sem.Hash),
                    Individual = SemTargets.ToDictionary(s => s, s => Compare(sem.Tape,
                        candidates.Where(c=>c.Symbol==s).ToArray(),sem.Hash)),
                    Without = SemTargets.ToDictionary(s => s, s => Compare(sem.Tape,
                        candidates.Where(c=>c.Symbol!=s).ToArray(),sem.Hash))
                });
            }
            File.WriteAllText(output,JsonSerializer.Serialize(new {
                Study="SEM1_ESD1_BENCHMARK_CORRECTION", SEM1SourceSha256=sem.Hash, ESD1SourceSha256=esd.Hash,
                SEM1=semResults, ESD1=Compare(esd.Tape,EsdCandidates(esd.Tape),esd.Hash),
                CapitalEur=300, PortfolioReplayExecuted=true, IndependentConfirmation=false,
                OrdersSubmitted=0, CloudActivated=false, ContinuousDrawdownCertified=false
            }));
            return 0;
        }
        catch(Exception ex)
        {
            string message = System.Text.RegularExpressions.Regex.IsMatch(ex.Message, "^[A-Z][A-Z0-9_]{2,100}$")
                ? ex.Message : ex.GetType().Name;
            Console.Error.WriteLine("SESSION_BENCHMARK_CORRECTION_REJECTED:"+message);
            return 67;
        }
    }

    private static (Tape Tape,string Hash) Read(string path,string label)
    {
        byte[] bytes=File.ReadAllBytes(path);
        var tape=JsonSerializer.Deserialize<Tape>(bytes,Wire);
        if(tape?.SourceLabel!=label)throw new ArgumentException("CORRECTION_SOURCE_LABEL");
        return (tape,Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
    }

    private static Dictionary<string,Dictionary<long,NativeClosedMarketBar>> Bars(Tape t) =>
        t.Bars.ToDictionary(b=>b.Symbol,b=>b.M5.ToDictionary(x=>x.OpenAt));
    private static Dictionary<(string Symbol,long At),NativeOriginalOpenApiMarketMark> Marks(Tape t) =>
        t.Marks.ToDictionary(m=>(m.Symbol,m.At));

    private static Candidate[] SemCandidates(Tape tape,int horizon)
    {
        var bars=Bars(tape);
        var marks=Marks(tape);
        var rows=new List<Candidate>();
        var start=new DateTimeOffset(2026,8,17,0,0,0,TimeSpan.Zero);
        foreach(string s in SemTargets)
        {
            var schedule=tape.Schedules!.GetValueOrDefault(s);
            var zone=NativeSessionEconomicsMap.Zone(schedule?.TimeZone);
            for(int week=0;week<10;week++)
            {
                var weekday=start.AddDays(7*week+week%5);
                var dates=s=="ETHEUR"?new[]{weekday,start.AddDays(7*week+5+week%2)}:new[]{weekday};
                foreach(var date in dates)
                for(int hour=1;hour<24;hour+=3)
                {
                    long clock=date.AddHours(hour).ToUnixTimeMilliseconds(), entry=clock+1500, exit=entry+horizon*Minute;
                    var (signal,momentum)=NativeSessionEconomicsMap.Signal(s,bars,clock);
                    if(signal is null)continue;
                    rows.Add(new(s,entry,exit,signal.Value,momentum,marks.GetValueOrDefault((s,entry)),
                        marks.GetValueOrDefault((s,exit)),NativeSessionEconomicsMap.IsOpen(schedule,zone,entry,exit)));
                }
            }
        }
        return rows.ToArray();
    }

    private static Candidate[] EsdCandidates(Tape tape)
    {
        const string symbol="LTCUSD";
        var bars=Bars(tape)[symbol];
        var marks=Marks(tape);
        var rows=new List<Candidate>();
        var start=new DateTimeOffset(2026,7,20,0,0,0,TimeSpan.Zero);
        for(var day=start;day<start.AddDays(112);day=day.AddDays(1))
        {
            if(day.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)continue;
            foreach(int hour in new[]{7,13})
            {
                long clock=day.AddHours(hour).ToUnixTimeMilliseconds(),entry=clock+1500,exit=entry+60*Minute;
                var prefix=Enumerable.Range(0,12).Select(i=>bars.GetValueOrDefault(clock-(12-i)*5*Minute)).ToArray();
                if(prefix.Any(x=>x is null||x.CloseAt!=x.OpenAt+5*Minute||x.CloseAt>clock))continue;
                int momentum=Math.Sign(prefix[^1]!.Close-prefix[0]!.Open);
                int signal=NativeExtendedSessionExperiment.Signal(symbol,prefix!);
                // ESD1 retained marks only after its original contract-hours check.
                var first=marks.GetValueOrDefault((symbol,entry));
                rows.Add(new(symbol,entry,exit,signal,momentum,first,marks.GetValueOrDefault((symbol,exit)),first is not null));
            }
        }
        return rows.ToArray();
    }

    private static object Compare(Tape tape,Candidate[] candidates,string hash)
    {
        if(candidates.Any(c=>c.Signal!=0&&c.Signal!=c.Momentum))
            throw new InvalidOperationException("CORRECTION_FILTER_DIRECTION_PARITY");
        var symbols=candidates.Select(c=>c.Symbol).ToHashSet();
        var observations=tape.Marks.Where(m=>symbols.Contains(m.Symbol)).ToArray();
        object Scenario(bool adverse,bool paired) => Policies.ToDictionary(p=>p,
            p=>Replay(candidates,observations,hash,p,adverse,paired));
        return new {
            CausalCentral=Scenario(false,false), CausalAdverse=Scenario(true,false),
            CompleteEndpointsCentral=Scenario(false,true), CompleteEndpointsAdverse=Scenario(true,true),
            CandidateClocks=candidates.Length, OriginalFilteredSignals=candidates.Count(c=>c.Signal!=0)
        };
    }

    private static decimal? Funding(Candidate c,int side,NativeOriginalOpenApiMarketMark quote) =>
        NativeBrokerContractCosts.SignedFinancing(quote.Contract,c.Entry,c.Exit,side,quote.Contract.MinimumUnits,
            quote.QuoteCreditToEur,quote.QuoteDebitToEur);

    private static LedgerQuote Quote(NativeOriginalOpenApiMarketMark m,bool adverse,bool buy)
    {
        var q=NativeBrokerContractCosts.Quote(m.Contract,new(m.At,m.Bid,m.Ask,m.QuoteCreditToEur,m.QuoteDebitToEur,
            m.UsdToEur,m.MinimumFeeAssetToEur,m.MarginRequirementEur,m.Contract.MinimumUnits,m.SlippagePerSideQuote),
            executionIsBuy:buy).Quote;
        if(!adverse)return q;
        decimal half=(q.Ask-q.Bid)/2,stress=m.Contract.QuoteAsset=="EUR"?0m:.001m;
        return q with {Bid=q.Bid-half,Ask=q.Ask+half,EurCredit=q.EurCredit*(1-stress),EurDebit=q.EurDebit*(1+stress),
            ExitFeePerUnit=2*q.ExitFeePerUnit,ExitFeeFloor=2*q.ExitFeeFloor};
    }

    private static string Week(long at)
    {
        var dt=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return $"{ISOWeek.GetYear(dt)}-W{ISOWeek.GetWeekOfYear(dt):00}";
    }

    private static Outcome Replay(Candidate[] universe,NativeOriginalOpenApiMarketMark[] source,
        string hash,string policy,bool adverse,bool paired)
    {
        var book=new NativeFundedLedger(maximumStalenessMs:2);
        var held=new Dictionary<string,Position>(StringComparer.Ordinal);
        var rejected=new Dictionary<string,int>();
        void Reject(string cause)=>rejected[cause]=rejected.GetValueOrDefault(cause)+1;
        int sequence=0, missingExits=0, incompleteMarks=0, maxPositions=0;
        decimal maxMargin=0;
        var entries=universe.ToLookup(c=>c.Entry);
        var marks=source.ToLookup(m=>m.At);
        var times=source.Select(m=>m.At).Concat(universe.SelectMany(c=>new[]{c.Entry,c.Exit})).Distinct().Order();
        foreach(long at in times)
        {
            var snapshot=marks[at].ToDictionary(m=>m.Symbol,m=>m);
            // All events at a common clock must bind to one immutable fee quote per symbol.
            var quotes=snapshot.Values.ToDictionary(m=>m.Symbol,m=>{
                bool buy=held.TryGetValue(m.Symbol,out var position)
                    ? position.Side<0 : Pick(entries[at].FirstOrDefault(c=>c.Symbol==m.Symbol),policy)>0;
                return Quote(m,adverse,buy);
            });
            LedgerEvent Event(string kind,Position? p,long stamp,decimal price=0,decimal fee=0,decimal funding=0)=>
                new($"{++sequence}",stamp,kind,p?.Id??"",p?.Candidate.Symbol??"",p?.Side??0,p?.Units??0,
                    price,fee,p is null?0:quotes.GetValueOrDefault(p.Candidate.Symbol)?.MarginPerUnit??0,
                    p?.EntrySlip??0,at,at,1,"SESSION_BENCHMARK_FIXED_ENDPOINT",hash,
                    kind=="MARK"?quotes.Values.ToArray():Array.Empty<LedgerQuote>(),funding);
            book.Apply(Event("MARK",null,at));
            if(book.Summary().LiquidationEquityEur is null)incompleteMarks++;

            foreach(var p in held.Values.Where(p=>p.Candidate.Exit==at).ToArray())
            {
                string s=p.Candidate.Symbol;
                if(!snapshot.TryGetValue(s,out var last))
                {
                    missingExits++;
                    continue;
                }
                var funding=Funding(p.Candidate,p.Side,last)
                    ?? throw new InvalidOperationException("CORRECTION_FINANCING_UNKNOWN_AT_EXIT");
                if(adverse)funding=2*Math.Min(0,funding);
                if(funding!=0)book.Apply(Event("FINANCING",p,at,funding:funding));
                book.Apply(Event("REQUEST_CLOSE",p,at));
            }
            foreach(var p in held.Values.Where(p=>p.Candidate.Exit==at&&snapshot.ContainsKey(p.Candidate.Symbol)).ToArray())
            {
                string s=p.Candidate.Symbol;
                var q=quotes[s];
                decimal slip=snapshot[s].SlippagePerSideQuote*(adverse?2:1);
                decimal price=p.Side>0?q.Bid-slip:q.Ask+slip;
                decimal fee=Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*p.Units);
                book.Apply(Event("CLOSE_FILL",p,at+1,price,fee) with {ObservedExitSlippagePerSide=slip});
                held.Remove(s);
            }

            foreach(var c in entries[at].OrderBy(c=>c.Symbol,StringComparer.Ordinal))
            {
                int side=Pick(c,policy);
                if(side==0){Reject("POLICY_ABSTAINED");continue;}
                if(!c.ContractOpen){Reject("SESSION_INELIGIBLE");continue;}
                if(c.First is not { } first){Reject("MISSING_ENTRY_MARK");continue;}
                if(Funding(c,side,first) is null){Reject("UNSUPPORTED_CONTRACT_FUNDING");continue;}
                if(paired && c.Last is null){Reject("PAIRED_ENDPOINT_EXCLUSION");continue;}
                if(held.ContainsKey(c.Symbol)){Reject("SYMBOL_ALREADY_HELD");continue;}
                if(held.Values.Any(p=>p.Candidate.Exit<=at)){Reject("UNRESOLVED_FIXED_EXIT");continue;}
                var summary=book.Summary(at+1);
                if(summary.LiquidationEquityEur is not decimal eq||summary.UsedMarginEur is not decimal used)
                { Reject("MISSING_HELD_MARK");continue; }
                var q=quotes[c.Symbol];
                decimal units=first.Contract.MinimumUnits,slip=first.SlippagePerSideQuote*(adverse?2:1);
                decimal fee=Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units);
                decimal projected=eq-2*fee-units*(q.Ask-q.Bid+2*slip)*q.EurDebit;
                if(summary.MaximumSampledDrawdown>=.30m||projected<=.70m*summary.ObservedPeakEur)
                { Reject("SAMPLED_DRAWDOWN_LIMIT");continue; }
                if(projected<=used+q.MarginPerUnit*units)
                { Reject("INSUFFICIENT_SHARED_MARGIN");continue; }
                // Shift the fact pair by one modeled millisecond if a prior fill
                // used this clock. Every mark remains at the original observed clock.
                var p=new Position(c,side,units,slip,$"{c.Symbol}/{at}");
                book.Apply(Event("REQUEST_OPEN",p,at+1));
                decimal price=side>0?q.Ask+slip:q.Bid-slip;
                book.Apply(Event("OPEN_FILL",p,at+2,price,fee));
                held.Add(c.Symbol,p);
                maxPositions=Math.Max(maxPositions,held.Count);
                maxMargin=Math.Max(maxMargin,book.Summary().UsedMarginEur??0);
            }
        }

        var final=book.Summary();
        var closed=book.ClosedFragments();
        var weeks=universe.Select(c=>Week(c.Entry)).Distinct().Order().ToArray();
        return new(final.CompleteRoundTrips,final.OpenPositions,missingExits,closed.Sum(f=>f.GrossEur),
            final.ClosedNetEur,final.CashEur,maxMargin,maxPositions,final.MaximumSampledDrawdown,incompleteMarks,rejected,
            weeks.ToDictionary(w=>w,w=>closed.Count(f=>Week(f.ClosedAt)==w)),
            weeks.ToDictionary(w=>w,w=>closed.Where(f=>Week(f.ClosedAt)==w).Sum(f=>f.NetEur)),
            closed.GroupBy(f=>f.Symbol).ToDictionary(g=>g.Key,g=>g.Count()),final.EventChainHash);
    }

    private static int Pick(Candidate? c,string policy)=>c is null?0:policy switch {
        "Filtered"=>c.Signal,"Momentum"=>c.Momentum,"Long"=>1,"Short"=>-1,_=>0
    };
}
