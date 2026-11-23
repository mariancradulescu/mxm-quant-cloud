using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Core;

// PEL1 forward-only native economic programme. A simulated limit response is
// NOT an exchange queue fill, broker acknowledgement or certified execution.
// No cTrader order API, no token, no file/network dependencies in shared Core.
public sealed record Pel1Day(long Start,long[][] Bid,long[][] Ask);
public sealed record Pel1Market(string Name,NativeObservedContractTerms Contract,
    decimal MinMargin,decimal TickSize,Dictionary<string,long[][]> Frames,
    Pel1Day[] Days);
public sealed record Pel1Tape(long Start,long End,Pel1Market[] Markets);
public static class NativePel1Economic
{
    const long Second=1000L,Minute=60*Second,DayMs=86400000L;
    public const string Version="PEL1_PASSIVE_LIMIT_PRICE_IMPROVEMENT_CSHARP_ORIGINAL_EXPOSED";
    const decimal HardStop=.28m;
    const decimal MaxQuoteSpreadToRange=.5m;
    sealed record Tick(long At,decimal Bid,decimal Ask,bool Valid);
    sealed class Position
    {
        public string Id="",Symbol="";public int Side;public decimal Units,MarginPerUnit,Risk;
        public decimal Limit,Range,Entry,Stop,TickSize,Slip;
        public long RequestedAt,OpenedAt,ExpiresAt,FirstCrossAt;
        public bool LimitConfirmed,CloseRequested;public string LastReason="";
    }
    sealed class MarketDay
    {
        public required Pel1Market Source;public required Tick[] Ticks;
        public required long[][] M5;
    }
    sealed class Book
    {
        public required string Policy;public required decimal Stress;
        public NativeFundedLedger Ledger=new(1000);
        public Dictionary<string,Position> Held=new(StringComparer.Ordinal);
        public Dictionary<string,Position> Pending=new(StringComparer.Ordinal);
        public long Seq,LastAt;public bool IrreversibleStop,Incomplete;
        public int Offers,Requests,LimitConfirmed,Financed,Completed,Expired,
            StopTriggers,TargetTriggers,UnknownQuotes,TemporarySuspensions,
            HardStops,Rejections,HoldActions,ReductionUnavailable;
        public decimal MaxHeldPending,MaxHeldPendingRisk,MaxModelMarginFraction;
        public Dictionary<string,int> Rejects=new(StringComparer.Ordinal);
        public Dictionary<string,int> CompletedWeekly=new(StringComparer.Ordinal);
        public Dictionary<string,decimal> NetWeekly=new(StringComparer.Ordinal);
        public Dictionary<string,int> SourceWeekly=new(StringComparer.Ordinal);
        public void Reject(string s){Rejections++;Rejects[s]=Rejects.GetValueOrDefault(s)+1;}
        public long At(long clock){LastAt=Math.Max(clock,LastAt+1);return LastAt;}
        public LedgerEvent Fact(long clock,string kind,Position? p,LedgerQuote[] quotes,
            decimal price=0m,decimal fee=0m,decimal margin=0m,decimal slip=0m,
            string reason="NATIVE_CONDITIONAL_SELECTION",decimal? exitSlip=null)
        {
            long at=At(clock);
            string evidence=Hash($"{Version}|{Policy}|{Stress}|{at}|{kind}|{p?.Symbol}|{p?.Id}|{price}|{fee}");
            return new LedgerEvent($"{Policy}-{Stress}-{++Seq}",at,kind,p?.Id??"",
                p?.Symbol??"",p?.Side??0,p?.Units??0,price,fee,margin,slip,
                Math.Max(0,clock),Math.Max(0,clock),100L,reason,evidence,quotes)
                {ObservedExitSlippagePerSide=exitSlip};
        }
        public void Mark(long t,LedgerQuote[] quotes)
        {
            Ledger.Apply(Fact(t,"MARK",null,quotes));
            var s=Ledger.Summary();
            if(s.MaximumSampledDrawdown>=HardStop && !IrreversibleStop)
            {IrreversibleStop=true;HardStops++;}
            if(s.LiquidationEquityEur is null && Held.Count>0)
            {UnknownQuotes++;Incomplete=true;}
            var held=Held.Values.Sum(x=>x.Units*x.MarginPerUnit);
            var pending=Pending.Values.Sum(x=>x.Units*x.MarginPerUnit);
            MaxHeldPending=Math.Max(MaxHeldPending,held+pending);
            MaxHeldPendingRisk=Math.Max(MaxHeldPendingRisk,
                Held.Values.Sum(x=>x.Risk)+Pending.Values.Sum(x=>x.Risk));
            if(s.LiquidationEquityEur is decimal eq && eq>0)
                MaxModelMarginFraction=Math.Max(MaxModelMarginFraction,(held+pending)/eq);
        }
        public NativePendingCapitalGate.Commitment[] HeldCapital(
            IReadOnlyDictionary<string,LedgerQuote> quotes)=>
            Held.Values.Select(x=>new NativePendingCapitalGate.Commitment(
                x.Id,x.Symbol,x.Units,
                Math.Max(x.MarginPerUnit,quotes[x.Symbol].MarginPerUnit),
                x.Risk,"FX",false)).ToArray();
        public NativePendingCapitalGate.Commitment[] PendingCapital()=>
            Pending.Values.Select(x=>new NativePendingCapitalGate.Commitment(
                x.Id,x.Symbol,x.Units,x.MarginPerUnit,x.Risk,"FX",true)).ToArray();
        public object Receipt(long start,long end)
        {
            var summary=Ledger.Summary();
            var trades=Ledger.ClosedFragments();
            var weeks=new List<object>();
            for(long d=start;d<end;d+=7*DayMs)
            {
                string key=Iso(d);
                weeks.Add(new{Week=key,OriginalSourceCalendar=true,
                    Completed=CompletedWeekly.GetValueOrDefault(key),
                    NET_EUR=NetWeekly.GetValueOrDefault(key),
                    SourceDecisionClocks=SourceWeekly.GetValueOrDefault(key),
                    HARD21_MODELED=CompletedWeekly.GetValueOrDefault(key)>=21,
                    OfficialEligible=false});
            }
            return new{
                Policy,CostMultiplier=Stress,InitialCashEur=300m,
                LedgerClosedNetEur=summary.ClosedNetEur,
                FinalCashEur=summary.CashEur,
                FinalLiquidationEquityEur=summary.LiquidationEquityEur,
                FinalFullySettled=Held.Count==0&&Pending.Count==0,
                NetFullyQualified=false,
                Summary=summary,
                SampledDrawdownPercent=100m*summary.MaximumSampledDrawdown,
                MaxHeldPlusPendingEur=MaxHeldPending,
                MaxHeldPlusPendingStopRiskEur=MaxHeldPendingRisk,
                MaxHeldPlusPendingMarginToEquity=MaxModelMarginFraction,
                OpenUnresolved=Held.Count,PendingUnresolved=Pending.Count,
                Offers,Requests,LimitConfirmed,Financed,Completed,Expired,
                StopTriggers,TargetTriggers,UnknownQuotes,TemporarySuspensions,
                HardStops,IrreversibleStop,Incomplete,Rejections,RejectReasons=Rejects,
                HoldActions,ReductionUnavailable,Weeks=weeks,
                Trips=trades.Select(x=>new {x.PositionId,x.Symbol,x.OpenedAt,x.ClosedAt,
                    x.NetEur,x.GrossEur,x.SpreadEur,x.SlippageEur,
                    x.CommissionsEur,x.ConversionEur,x.FinancingEur,
                    x.CompletesRoundTrip,x.Reason}).ToArray(),
                EventChainSha256=summary.EventChainHash,
                BrokerFillsCertified=false,IntratickDdCertified=false,
                HistoricalTariffContinuityCertified=false,IndependentConfirmation=false,
                BrokerOrders=0,CloudActivated=false
            };
        }
    }

    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static string Iso(long at)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return System.Globalization.ISOWeek.GetYear(d)+"-W"+
            System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
    }
    static int Before(Tick[] a,long t)
    {
        int low=0,hi=a.Length;
        while(low<hi){int m=(low+hi)/2;if(a[m].At<=t)low=m+1;else hi=m;}
        return low-1;
    }
    // A side event really changes the quote. Repeated conflicting same-ms
    // sides are not resolved by cherry-picking the favorable update.
    static Tick[] Decode(Pel1Day day)
    {
        var result=new List<Tick>();
        int ib=0,ia=0;decimal bid=0,ask=0;long bt=0,at=0;
        while(ib<day.Bid.Length||ia<day.Ask.Length)
        {
            long t=Math.Min(ib<day.Bid.Length?day.Bid[ib][0]:long.MaxValue,
                ia<day.Ask.Length?day.Ask[ia][0]:long.MaxValue);
            decimal? xb=null,xa=null;bool conflict=false;
            while(ib<day.Bid.Length&&day.Bid[ib][0]==t)
            {decimal x=day.Bid[ib++][1]/100000m;conflict|=xb.HasValue&&xb!=x;xb=x;bid=x;bt=t;}
            while(ia<day.Ask.Length&&day.Ask[ia][0]==t)
            {decimal x=day.Ask[ia++][1]/100000m;conflict|=xa.HasValue&&xa!=x;xa=x;ask=x;at=t;}
            result.Add(new(t,bid,ask,!conflict && bid>0m && ask>=bid &&
                t-bt<=30000L && t-at<=30000L));
        }
        return result.ToArray();
    }
    static Tick? AsOf(Tick[] ticks,long clock)
    {
        int i=Before(ticks,clock);
        return i>=0&&ticks[i].Valid&&clock-ticks[i].At<=30000L?
            ticks[i]:null;
    }
    static long[]? ClosedM5(long[][] bars,long at)
    {
        int low=0,hi=bars.Length;
        while(low<hi){int mid=(low+hi)/2;if(bars[mid][1]<=at)low=mid+1;else hi=mid;}
        return low>=20 ? bars[low-1] : null;
    }
    public static int LastClosedSide(long[] bar)
    {
        if(bar.Length<7 || bar[1]<=bar[0] || bar[4]>bar[3] ||
            bar[5]<bar[4] || bar[5]>bar[3])
            throw new ArgumentException("PEL1_CLOSED_BAR_GEOMETRY_INVALID");
        decimal mid=(bar[3]+bar[4])/2m;
        return bar[5]<mid?1:bar[5]>mid?-1:0;
    }
    public static bool TwoQuoteLimitCross(bool buy,decimal limit,decimal tick,
        long intentAt,long firstAt,long secondAt,
        decimal firstBid,decimal firstAsk,decimal secondBid,decimal secondAsk)
    {
        if(tick<=0m||limit<=0m||firstAt<=intentAt||secondAt-firstAt<100 ||
            firstAsk<firstBid||secondAsk<secondBid||firstBid<=0||secondBid<=0)
            return false;
        return buy?(firstAsk<=limit-tick&&secondAsk<=limit-tick):
            (firstBid>=limit+tick&&secondBid>=limit+tick);
    }
    static LedgerQuote? Quote(Pel1Market market,Tick quote,Tick eur,
        long at,decimal multiplier)
    {
        try
        {
            // Cost stress widens exactly the evidenced dealer spread. No
            // historical spread has been invented, and original quote pairs
            // remain accessible separately to prove the limit-cross witness.
            decimal extra=(multiplier-1m)*(quote.Ask-quote.Bid)/2m;
            decimal bid=quote.Bid-extra,ask=quote.Ask+extra;
            if(bid<=0m||eur.Bid<=0||eur.Ask<eur.Bid)return null;
            var q=NativeBrokerContractCosts.Quote(market.Contract,
                new NativeMarketCostContext(at,bid,ask,1m/eur.Ask,
                    1m/eur.Bid,1m/eur.Bid,null,
                    market.MinMargin,market.Contract.MinimumUnits,0m));
            return q.Quote with {
                LiquidationSlippagePerSide=Math.Max(market.TickSize,
                    (ask-bid)*.25m*multiplier)
            };
        }
        catch(ArgumentException){return null;}
        catch(InvalidOperationException){return null;}
    }
    static decimal Fee(LedgerQuote q,decimal units)=>
        Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units);
    static decimal ExitSlippage(Pel1Market m,LedgerQuote q,decimal factor)=>
        Math.Max(m.TickSize,(q.Ask-q.Bid)*.25m*factor);
    static Position New(Pel1Market market,LedgerQuote q,int side,decimal range,
        decimal limit,decimal units,long now)
    {
        decimal adverse=range+2m*(q.Ask-q.Bid)+2m*ExitSlippage(market,q,1m);
        decimal risk=adverse*units*q.EurDebit+2m*Fee(q,units);
        return new Position{
            Symbol=market.Name,Side=side,Limit=limit,Units=units,
            MarginPerUnit=q.MarginPerUnit,Risk=risk,Range=range,
            TickSize=market.TickSize,RequestedAt=now,ExpiresAt=now+300000,
            Stop=side>0?limit-range:limit+range
        };
    }
    static void CloseRequest(Book book,Position p,long clock,LedgerQuote[] quotes,string reason)
    {
        if(p.CloseRequested)return;
        book.Ledger.Apply(book.Fact(clock,"REQUEST_CLOSE",p,quotes,
            reason:"MODEL_UNTRANSMITTED_"+reason));
        p.CloseRequested=true;p.LastReason=reason;
    }
    static void Cancel(Book book,Position p,long clock,string reason)
    {
        book.Ledger.Apply(book.Fact(clock,"MODEL_OPEN_INTENT_EXPIRED",p,
            Array.Empty<LedgerQuote>(),reason:reason));
        book.Pending.Remove(p.Symbol);
        book.Expired++;
    }
    static void Advance(Book book,long now,MarketDay[] days,Dictionary<string,LedgerQuote> quotes)
    {
        var qa=quotes.Values.OrderBy(x=>x.Symbol,StringComparer.Ordinal).ToArray();
        book.Mark(now,qa);
        var sum=book.Ledger.Summary();
        // The same FULL shared book must have all its existing positions
        // freshly and causally marked; no admission when even one is unknown.
        bool fullyMarked=sum.LiquidationEquityEur is decimal &&
            book.Held.Keys.All(quotes.ContainsKey);
        // CLOSE_FILL first. Request-close never freed its held risk earlier.
        foreach(var p in book.Held.Values.Where(x=>x.CloseRequested).ToArray())
        {
            if(!quotes.TryGetValue(p.Symbol,out var q)){book.Incomplete=true;continue;}
            long closedAt=book.At(now+5);
            decimal slip=ExitSlippage(days.Single(x=>x.Source.Name==p.Symbol).Source,q,book.Stress);
            decimal exit=NativeExecutableEconomics.ExitPrice(p.Side>0?q.Bid:q.Ask,p.Side,slip);
            book.Ledger.Apply(book.Fact(closedAt,"CLOSE_FILL",p,qa,
                exit,Fee(q,p.Units),q.MarginPerUnit,0m,
                reason:p.LastReason,exitSlip:slip));
            book.Held.Remove(p.Symbol);
            if(book.Ledger.ClosedFragments().Last() is var f)
            {
                if(f.CompletesRoundTrip){book.Completed++;string key=Iso(f.ClosedAt);
                    book.CompletedWeekly[key]=book.CompletedWeekly.GetValueOrDefault(key)+1;
                    book.NetWeekly[key]=book.NetWeekly.GetValueOrDefault(key)+f.NetEur;}
            }
        }
        // Reconcile the now-current book after actual modeled CLOSE_FILL.
        sum=book.Ledger.Summary();fullyMarked=sum.LiquidationEquityEur is decimal &&
            book.Held.Keys.All(quotes.ContainsKey);
        foreach(var p in book.Held.Values.ToArray())
        {
            if(!quotes.TryGetValue(p.Symbol,out var q))
            {book.Incomplete=true;continue;}
            var market=days.Single(x=>x.Source.Name==p.Symbol).Source;
            decimal slip=ExitSlippage(market,q,book.Stress);
            decimal exit=NativeExecutableEconomics.ExitPrice(
                p.Side>0?q.Bid:q.Ask,p.Side,slip);
            decimal liquid=p.Side*p.Units*(exit-p.Entry)*
                (p.Side*(exit-p.Entry)>=0?q.EurCredit:q.EurDebit)-
                2m*Fee(q,p.Units);
            decimal minGain=p.Units*market.TickSize*q.EurCredit;
            // Genuine quote-side target is profit AFTER both modeled fees.
            bool target=liquid>minGain;
            bool stop=p.Side*(exit-p.Stop)<=0m || book.IrreversibleStop;
            bool end=now%DayMs>=11*60*Minute;
            if(stop||target||end)
            {
                string reason=stop?(book.IrreversibleStop?
                    "PEL1_PERMANENT_CAPITAL_STOP":"PEL1_PRICE_INVALIDATION"):
                    target?"PEL1_POSITIVE_NET_TARGET":"PEL1_SESSION_SAFETY_FAILSAFE";
                CloseRequest(book,p,now+12,qa,reason);
                if(stop)book.StopTriggers++;
                else if(target)book.TargetTriggers++;
            }
            else{book.HoldActions++;book.ReductionUnavailable++;}
        }
        // A modeled pending order holds capital until a true fill or expiry.
        foreach(var p in book.Pending.Values.ToArray())
        {
            if(now>=p.ExpiresAt){Cancel(book,p,now+18,
                "MODEL_UNTRANSMITTED_OPEN_RESPONSE_WINDOW_EXPIRED");continue;}
            if(!fullyMarked||!quotes.TryGetValue(p.Symbol,out var q))
            {book.UnknownQuotes++;continue;}
            var m=days.Single(x=>x.Source.Name==p.Symbol);
            Tick[] ticks=m.Ticks;
            int i=Before(ticks,now);
            if(i<1)continue;
            // Two distinct real post-intent side-quote events. Any return
            // inside the limit before confirmation resets the pair.
            int first=-1,second=-1;
            for(int z=i;z>=0&&ticks[z].At>=p.RequestedAt&&z>i-2000;z--)
            {
                if(ticks[z].Valid && ticks[z].At>p.RequestedAt &&
                    (p.Side>0?ticks[z].Ask<=p.Limit-p.TickSize:
                         ticks[z].Bid>=p.Limit+p.TickSize))
                {
                    if(second<0)second=z;
                    else if(ticks[second].At-ticks[z].At>=100){first=z;break;}
                }
                else if(ticks[z].At<now-5000L)break;
                else if(second>=0)break;
            }
            bool crossed=first>=0&&TwoQuoteLimitCross(p.Side>0,p.Limit,p.TickSize,
                p.RequestedAt,ticks[first].At,ticks[second].At,
                ticks[first].Bid,ticks[first].Ask,ticks[second].Bid,ticks[second].Ask);
            if(book.Policy=="TAKER")crossed=true;
            if(!crossed)continue;
            var original=AsOf(ticks,now);
            if(original is null)continue;
            decimal requested=p.Limit;
            decimal currentPrice=p.Side>0?q.Ask:q.Bid;
            decimal slack=p.Side>0?requested-q.Ask:q.Bid-requested;
            if(book.Policy=="TAKER"||book.Policy=="FILL_TIME_TAKER")
            {
                // This fully financed comparison crosses at same real mark.
                requested=NativeExecutableEconomics.EntryPrice(q,p.Side,
                    ExitSlippage(m.Source,q,book.Stress));
                slack=ExitSlippage(m.Source,q,book.Stress);
            }
            else if(slack<0)continue;
            if(book.IrreversibleStop||book.Held.ContainsKey(p.Symbol))continue;
            var held=book.HeldCapital(quotes);
            var pending=book.PendingCapital();
            var guard=NativePostFillCapitalGuard.Assess(
                sum.LiquidationEquityEur,held,pending,p.Id,p.Side,q,slack,
                p.Risk*.1m);
            if(!guard.Allowed){book.Reject(guard.Reason);
                Cancel(book,p,now+24,"MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED");
                continue;}
            decimal fee=Fee(q,p.Units);
            string kind=book.Policy=="PASSIVE"?"MODEL_LIMIT_OPEN_FILL":"OPEN_FILL";
            if(book.Policy=="FILL_TIME_TAKER")
            {
                // It must have been a resting limit-selection intent, but
                // market entry uses authentic current executable side.
                kind="OPEN_FILL";
            }
            // Market comparators have market-side fill requests. They must
            // not be relabelled a limit to fabricate spread improvement.
            book.Ledger.Apply(book.Fact(now+26,kind,p,qa,requested,fee,
                q.MarginPerUnit,slack));
            p.Entry=requested;p.OpenedAt=now;p.Slip=slack;
            book.Pending.Remove(p.Symbol);book.Held.Add(p.Symbol,p);
            book.Financed++;book.LimitConfirmed+=crossed&&book.Policy!="TAKER"?1:0;
        }
        if(book.IrreversibleStop||!fullyMarked)return;
        foreach(var day in days)
        {
            var m=day.Source;
            if(book.Held.ContainsKey(m.Name)||book.Pending.ContainsKey(m.Name))continue;
            if(!quotes.TryGetValue(m.Name,out var q))continue;
            // Main decisions only once per genuinely CLOSED 5-minute bar.
            if(now%300000L!=5000L)continue;
            var prev=ClosedM5(day.M5,now-1);
            if(prev is null||prev[1]>now)continue;
            var priorBars=day.M5.Where(x=>x[1]<=now).TakeLast(20).ToArray();
            if(priorBars.Length<20||priorBars.Zip(priorBars.Skip(1))
                .Any(x=>x.First[1]>x.Second[0])){book.Reject("M5_WARMUP_GAP");continue;}
            decimal range=Math.Max(m.TickSize,(prev[3]-prev[4])/100000m);
            int side=LastClosedSide(prev);
            if(side==0)continue;
            book.Offers++;
            book.SourceWeekly[Iso(now)]=book.SourceWeekly.GetValueOrDefault(Iso(now))+1;
            if(q.Ask-q.Bid>MaxQuoteSpreadToRange*
                priorBars.Average(x=>(x[3]-x[4])/100000m))
            {book.TemporarySuspensions++;book.Reject("SPREAD_ABNORMAL_TEMPORARY");continue;}
            var s=book.Ledger.Summary();
            if(s.LiquidationEquityEur is not decimal equity||equity<=0)
            {book.Reject("LIQUIDATION_EQUITY_MISSING");continue;}
            var limit=side>0?day.Ticks[Before(day.Ticks,now)].Bid:
                day.Ticks[Before(day.Ticks,now)].Ask;
            decimal units=m.Contract.MinimumUnits;
            Position p=New(m,q,side,range,limit,units,now);
            p.Id="PEL1-"+book.Policy+"-"+book.Stress+"-"+m.Name+"-"+now;
            var offer=new NativePendingCapitalGate.Proposal(
                m.Name,"FX",units,m.Contract.VolumeStepUnits,m.Contract.MaximumUnits,
                q.MarginPerUnit,p.Risk/units);
            var pre=NativePendingCapitalGate.Assess(equity,true,
                book.HeldCapital(quotes),book.PendingCapital(),offer);
            if(!pre.IsFinanceable){book.Reject(pre.Status);continue;}
            p.Units=pre.Units;
            // Strict minimum-only source programme; volume is legal, never
            // scaled up to manufacture HARD21.
            book.Ledger.Apply(book.Fact(now+33,"REQUEST_OPEN",p,qa,
                p.Limit,0m,q.MarginPerUnit,0m));
            book.Pending.Add(p.Symbol,p);book.Requests++;
        }
    }
    public static object Evaluate(Pel1Tape tape,string frozenProtocolSha256)
    {
        if(tape.Markets.Length!=3 || tape.Markets[0].Name!="EURUSD" ||
           tape.Markets[1].Name!="GBPUSD"||tape.Markets[2].Name!="AUDUSD" ||
           tape.Start!=1777852800000L || tape.End!=1785110400000L ||
           frozenProtocolSha256.Length!=64 ||
           tape.Markets.Any(x=>!x.Contract.OriginalBrokerAuthenticated||
               x.TickSize<=0||x.MinMargin<=0||x.Contract.MinimumUnits<=0))
            throw new ArgumentException("PEL1_FROZEN_CVP1_INPUT_OR_CONTRACT");
        var books=(from factor in new[]{1m,1.5m,2m}
                   from policy in new[]{"PASSIVE","TAKER","FILL_TIME_TAKER","CASH"}
                   select new Book{Policy=policy,Stress=factor}).ToArray();
        for(long day=tape.Start;day<tape.End;day+=DayMs)
        {
            var markets=new List<MarketDay>();
            foreach(var market in tape.Markets)
            {
                var d=market.Days.FirstOrDefault(x=>x.Start==day);
                if(d is null)continue;
                if(!market.Frames.TryGetValue("M5",out var bars))continue;
                markets.Add(new MarketDay{Source=market,Ticks=Decode(d),M5=bars});
            }
            if(markets.Count!=3)continue;
            for(long t=day+8*60*Minute+5000;t<=day+11*60*Minute;t+=5000)
            {
                var eur=AsOf(markets[0].Ticks,t);
                foreach(var b in books)
                {
                    if(b.Policy=="CASH")continue;
                    var quotes=new Dictionary<string,LedgerQuote>(StringComparer.Ordinal);
                    if(eur is not null)
                    foreach(var m in markets)
                    {
                        var mark=AsOf(m.Ticks,t);
                        if(mark is null)continue;
                        var q=Quote(m.Source,mark,eur,t,b.Stress);
                        if(q is not null)quotes[m.Source.Name]=q;
                    }
                    Advance(b,t,markets.ToArray(),quotes);
                }
            }
        }
        return new{Version,OriginalSource="CVP1 #44162043538",
            SourceSha256="ccd0cd7b4c659a24045023475c51680b2c8800d6879f6f74430ed429dcc2fee9",
            FrozenProtocolSha256=frozenProtocolSha256,
            SourceWeeks=12,SourceExposure="GLOBAL_EXPOSED_DEVELOPMENT",
            ClaimsNoActualBrokerFills=true,CostHistoricalContinuityUnverified=true,
            ModelTimeClock="CLOSED_M5_AND_AUTHENTIC_ASOF_BIDASK",
            Books=books.Select(b=>b.Receipt(tape.Start,tape.End)).ToArray(),
            ZeroBrokerRequests=true,Orders=0,Cloud=false,Independent=false,
            Hard21Certified=false,GlobalDrawdownCertified=false};
    }
}
