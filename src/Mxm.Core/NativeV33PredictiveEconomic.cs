using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Mxm.Core;

// ONE prospectively frozen new V3.3 causal economic policy. V3.2 and all
// previously closed policy implementations remain byte-identical.
// NativeFundedLedger is the sole execution/accounting authority; no other
// financial simulator and NO broker order/Cloud API exists in this code.
public static class NativeV33PredictiveEconomic
{
    public const string Version="V33_ONE_CAUSAL_PREDICTIVE_FUNDED_EUR300_DEV";
    const long Minute=60_000, Day=86_400_000;
    const decimal Capital=300m, RiskPerTrade=.015m, AggregateStopRisk=.05m,
        MaximumMargin=.70m, ModelFXWedge=.00025m, FundingBpsPerDay=5m;
    const int LabelBars=6, Prior=64, MinMatured=64;
    static readonly string Evidence=new string('b',64);
    static readonly decimal[] Multipliers={1m,1.5m,2m};
    static readonly string[] Policies={"CASH","FIRST","FULL","PRICE_ONLY","NO_M1","LONG","SHORT"};
    static readonly string[] Tfs={"M1","M5","M15","M30","H1","H4","D1"};
    static long Width(string tf)=>tf switch
    {"M1"=>Minute,"M5"=>5*Minute,"M15"=>15*Minute,"M30"=>30*Minute,
     "H1"=>60*Minute,"H4"=>240*Minute,"D1"=>Day,
     _=>throw new ArgumentException("V33_BAD_TIMEFRAME")};
    static string Week(long t)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);
    }
    static int Sign(decimal x)=>x>0?1:x<0?-1:0;
    static decimal Clip(decimal x,decimal max)=>Math.Max(-max,Math.Min(max,x));
    static decimal Abs(decimal x)=>Math.Abs(x);

    sealed class Moments
    {
        public int N;
        public decimal Mean, M2;
        public void Add(decimal x)
        {
            ++N;decimal delta=x-Mean;
            Mean+=delta/N;M2+=delta*(x-Mean);
        }
        public decimal Variance=>N>1?Math.Max(0m,M2/(N-1)):0m;
    }
    sealed record Feature(int Channel,int Bin);
    sealed record Observation(long At,long MatureAt,string BaseTf,int Index,Feature[] Features);
    sealed record Estimate(decimal MeanBps,decimal LowerLongBps,decimal UpperShortBps,
        decimal ErrorBps,int Matured,int ActiveChannels,int M1Channels,string Regime);
    sealed record Offer(StudyMarket Market,int Side,string Tf,Estimate Estimate,
        decimal Atr,decimal MeanNetEur,decimal LowerNetEur,decimal RiskEur,
        decimal SuggestedUnits,LedgerQuote Quote,decimal Slippage);
    sealed record BarEvent(StudyMarket Market,string Tf,int Index,long At,V32Bar Bar);
    sealed class StudyMarket
    {
        public readonly V32Market Source;
        public readonly Dictionary<string,V32Bar[]> Bars;
        public readonly Dictionary<string,Dictionary<long,int>> Index=new(StringComparer.Ordinal);
        public readonly Dictionary<long,BarEvent> Events=new();
        public readonly Queue<Observation> Unmatured=new();
        readonly Dictionary<(int,int),Moments> cells=new();
        readonly Moments baseline=new();
        public int LabelsMatured=>baseline.N;
        public long M1FeatureClocks, M5FeatureClocks;
        public StudyMarket(V32Market source)
        {
            Source=source;Bars=new(StringComparer.Ordinal);
            foreach(var kv in source.Bars)
            {
                long width=Width(kv.Key);
                var data=kv.Value.OrderBy(b=>b.OpenAt).ToArray();
                long prev=-1;
                foreach(var b in data)
                {
                    if(b.OpenAt<=prev||b.OpenAt<0||b.Open<=0||
                       b.Low<=0||b.Low>Math.Min(b.Open,b.Close)||
                       b.High<Math.Max(b.Open,b.Close)||b.TickVolume<0)
                        throw new ArgumentException("V33_AUTHENTIC_RAW_BAR_GEOMETRY");
                    prev=b.OpenAt;
                }
                Bars[kv.Key]=data;
                Index[kv.Key]=data.Select((b,i)=>(b,i)).ToDictionary(z=>z.b.OpenAt,z=>z.i);
            }
            // M5 preferred only where actual original M5 exists at that clock.
            // M15 is alternative only when no genuine same-clock M5.
            foreach(string tf in new[]{"M15","M5"})
            {
                if(!Bars.TryGetValue(tf,out var data))continue;
                for(int i=0;i<data.Length;i++)
                {
                    V32Bar b=data[i];
                    if(tf=="M15" && Events.ContainsKey(b.OpenAt))continue;
                    Events[b.OpenAt]=new(this,tf,i,b.OpenAt,b);
                }
            }
        }
        public V32Bar? At(string tf,long at)
        {
            if(!Index.TryGetValue(tf,out var idx)||!idx.TryGetValue(at,out int i))return null;
            return Bars[tf][i];
        }
        public V32Bar[] Closed(string tf,long at,int take)
        {
            if(!Bars.TryGetValue(tf,out var arr))return Array.Empty<V32Bar>();
            long width=Width(tf);int l=0,r=arr.Length;
            while(l<r){int mid=(l+r)/2;if(arr[mid].OpenAt+width<=at)l=mid+1;else r=mid;}
            return arr[Math.Max(0,l-take)..l];
        }
        // Exactly 2 completed genuine adjacent bars per TF, no anticipated bar
        // values or synthetic carryover from last week/day.
        public Feature[] Features(long t,string tf)
        {
            var output=new List<Feature>(14);
            for(int j=0;j<Tfs.Length;j++)
            {
                string channel=Tfs[j];long w=Width(channel);
                var bars=Closed(channel,t,4);
                if(bars.Length<4||bars[^1].OpenAt+w>t||
                   t-(bars[^1].OpenAt+w)>2*w||
                   bars.Zip(bars.Skip(1)).Any(p=>p.Second.OpenAt-p.First.OpenAt!=w))
                    continue;
                decimal range=Math.Max(.00000001m,bars.Average(x=>x.High-x.Low));
                decimal normalized=(bars[^1].Close-bars[^2].Close)/range;
                int bucket=normalized>.25m?1:normalized<-.25m?-1:0;
                output.Add(new(2*j,bucket));
                decimal prior=(bars[0].TickVolume+bars[1].TickVolume+bars[2].TickVolume)/3m;
                if(prior>0)
                {
                    decimal volume=bars[^1].TickVolume/prior;
                    output.Add(new(2*j+1,volume>1.2m?1:volume<.8m?-1:0));
                }
            }
            if(output.Any(x=>x.Channel<2))M1FeatureClocks++;
            if(output.Any(x=>x.Channel is 2 or 3))M5FeatureClocks++;
            return output.ToArray();
        }
        public bool Ready(BarEvent e)
        {
            long w=Width(e.Tf);
            var x=Closed(e.Tf,e.At,8);
            return x.Length==8&&x[^1].OpenAt+w==e.At &&
                x.Zip(x.Skip(1)).All(p=>p.Second.OpenAt-p.First.OpenAt==w);
        }
        public decimal Atr(BarEvent e)
        {
            var x=Closed(e.Tf,e.At,8);
            return x.Length==8?Math.Max(.000000001m,x.Average(b=>b.High-b.Low)):0m;
        }
        public void Mature(long current)
        {
            while(Unmatured.Count>0&&Unmatured.Peek().MatureAt<current)
            {
                var p=Unmatured.Dequeue();long w=Width(p.BaseTf);
                var data=Bars[p.BaseTf];
                if(p.Index+LabelBars>=data.Length)continue;
                var next=data[p.Index+1];var last=data[p.Index+LabelBars];
                if(next.OpenAt!=p.At+w || last.OpenAt!=p.At+LabelBars*w ||
                   last.OpenAt+w!=p.MatureAt)continue;
                bool contiguous=true;
                for(int i=p.Index+2;i<=p.Index+LabelBars;i++)
                    if(data[i].OpenAt-data[i-1].OpenAt!=w){contiguous=false;break;}
                if(!contiguous||next.Open<=0)continue;
                decimal outcome=Clip(10000m*(last.Close-next.Open)/next.Open,5000m);
                baseline.Add(outcome);
                foreach(var f in p.Features)
                {
                    var key=(f.Channel,f.Bin);
                    if(!cells.TryGetValue(key,out var m)){m=new Moments();cells.Add(key,m);}
                    m.Add(outcome);
                }
            }
        }
        public void QueueLabel(BarEvent e,Feature[] features)
        {
            Unmatured.Enqueue(new(e.At,e.At+(LabelBars+1)*Width(e.Tf),e.Tf,e.Index,features));
        }
        public Estimate? Predict(Feature[] features,string policy,long t)
        {
            if(baseline.N<MinMatured)return null;
            var chosen=features.Where(f=>policy!="PRICE_ONLY"||f.Channel%2==0)
                .Where(f=>policy!="NO_M1"||f.Channel>=2).ToArray();
            decimal weighted=0m,denom=0m;
            foreach(var f in chosen)
            {
                if(!cells.TryGetValue((f.Channel,f.Bin),out var cell)||cell.N<16)continue;
                decimal weight=(decimal)cell.N/(cell.N+Prior);
                weighted+=weight*cell.Mean;denom+=weight;
            }
            // Baseline is a contemporaneously matured label distribution.
            // It is not a fixed bullish/bearish candle direction.
            decimal mean=denom>0 ?(.5m*baseline.Mean+.5m*weighted/denom):baseline.Mean;
            decimal var=Math.Max(1m,baseline.Variance);
            decimal err=(decimal)Math.Sqrt((double)(var/Math.Max(1,baseline.N)));
            decimal radius=2.5m*err;
            string regime=chosen.Any(f=>f.Channel>=10)?"HIGHER_TF":
                chosen.Any(f=>f.Channel>=4)?"MULTISCALE":"SHORT_TF_ONLY";
            return new(Clip(mean,2000m),mean-radius,mean+radius,
                err,baseline.N,chosen.Length,chosen.Count(f=>f.Channel<2),regime);
        }
        public object Coverage()=>new{
            Source.Symbol,LabelsMatured,M1FeatureClocks,M5FeatureClocks,
            Timeframes=Bars.ToDictionary(k=>k.Key,k=>new{
                Count=k.Value.Length,First=k.Value.Length>0?(long?)k.Value[0].OpenAt:null,
                Last=k.Value.Length>0?(long?)k.Value[^1].OpenAt:null}),
            GenuineDecisionEvents=Events.Count
        };
    }
    static NativeObservedContractTerms? Contract(V32Terms? c)
    {
        if(c is null||c.MinimumUnits is not >0||c.StepUnits is not >0||
           c.MaximumUnits is not >0||c.LotUnits is not >0||
           c.CommissionType is null||c.PreciseRateWire is null||
           c.MinimumCommissionType is null||c.PreciseMinimumWire is null||
           c.PnlConversionFeeBps is null)return null;
        return new(c.Symbol,c.QuoteAsset,c.ObservedAtUtcMs,c.MinimumUnits.Value,
            c.StepUnits.Value,c.MaximumUnits.Value,c.LotUnits.Value,
            c.CommissionType.Value,c.PreciseRateWire.Value,c.MinimumCommissionType.Value,
            c.PreciseMinimumWire.Value,c.MinimumCommissionAsset,c.PnlConversionFeeBps.Value,
            c.SwapCalculationType,c.LongSwap,c.ShortSwap,c.PipPosition,c.SwapPeriodHours,
            c.SwapTimeUtcMinute,c.TripleSwapWeekday,null,null,true,false);
    }
    static decimal? Fx(string currency,Dictionary<string,(decimal,long)> fx,long now)
    {
        bool Get(string s,out decimal v)
        {v=0m;if(!fx.TryGetValue(s,out var x)||x.Item1<=0||x.Item2>now||
                     now-x.Item2>60*Minute)return false;v=x.Item1;return true;}
        if(currency=="EUR")return 1m;
        if(!Get("EURUSD",out var euro))return null;
        if(currency=="USD")return 1m/euro;
        if(currency=="GBP"&&Get("GBPUSD",out var gb))return gb/euro;
        if(currency=="AUD"&&Get("AUDUSD",out var au))return au/euro;
        if(currency=="NZD"&&Get("NZDUSD",out var nz))return nz/euro;
        if(currency=="JPY"&&Get("USDJPY",out var jp))return 1m/(euro*jp);
        if(currency=="CAD"&&Get("USDCAD",out var ca))return 1m/(euro*ca);
        if(currency=="CHF"&&Get("USDCHF",out var ch))return 1m/(euro*ch);
        return null;
    }
    static LedgerQuote? Quote(StudyMarket market,V32Bar bar,decimal multiplier,
        Dictionary<string,(decimal,long)> fx,out decimal slippage)
    {
        slippage=0m;var c=market.Source.Terms;var contract=Contract(c);
        if(contract is null||c?.SpreadBps is not >0||c.MarginMinimumEur is not >0||
           c.MinimumUnits is not >0)return null;
        decimal? route=Fx(c.QuoteAsset,fx,bar.OpenAt);
        decimal? usd=Fx("USD",fx,bar.OpenAt);
        if(route is not >0||usd is not >0)return null;
        decimal spread=bar.Open*c.SpreadBps.Value*multiplier/10000m;
        if(spread<=0||spread>=bar.Open)return null;
        decimal bid=bar.Open-spread/2m,ask=bar.Open+spread/2m;
        slippage=spread/2m;
        decimal? fee=c.MinimumCommissionAsset is null?null:Fx(c.MinimumCommissionAsset,fx,bar.OpenAt);
        try
        {
            var ctx=new NativeMarketCostContext(bar.OpenAt,bid,ask,
                route.Value*(1-ModelFXWedge*multiplier),
                route.Value*(1+ModelFXWedge*multiplier),
                usd.Value,fee,c.MarginMinimumEur.Value,c.MinimumUnits.Value,slippage);
            var built=NativeBrokerContractCosts.Quote(contract,ctx).Quote;
            return built with{
                ExitFeePerUnit=built.ExitFeePerUnit*multiplier,
                ExitFeeFloor=built.ExitFeeFloor*multiplier,
                LiquidationSlippagePerSide=slippage
            };
        }
        catch(ArgumentException){return null;}
        catch(InvalidOperationException){return null;}
    }
    static decimal Fee(LedgerQuote q,decimal units)=>
        Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units);
    static decimal Price(LedgerQuote q,int side,decimal slip,bool entry)
        =>entry?NativeExecutableEconomics.EntryPrice(q,side,slip):
           NativeExecutableEconomics.ExitPrice(side>0?q.Bid:q.Ask,side,slip);
    sealed class Position
    {
        public string Id="";
        public StudyMarket Market=null!;
        public int Side;
        public decimal Units, Entry, Stop, Target, Best, Atr, Slippage, ReservedRisk;
        public long OpenAt,LastFinancingAt;
    }
    sealed class Pending
    {
        public string Id="";
        public string Kind="";
        public StudyMarket Market=null!;
        public int Side;
        public decimal Units,Slippage,Atr;
        public long RequestedAt,Width;
        public string Why="";
    }
    sealed class Book
    {
        public readonly string Policy;
        public readonly decimal Multiplier;
        public readonly NativeFundedLedger Ledger=new(120*Minute);
        public readonly Dictionary<string,Position> Held=new(StringComparer.Ordinal);
        public readonly Dictionary<string,Pending> Pending=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> Counters=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> Rejections=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> Context=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> RiskGroup=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> SideByPosition=new(StringComparer.Ordinal);
        public readonly List<(long at,decimal? equity,decimal? margin,decimal dd)> Equity=new();
        public long Seq;
        public long LastEventAt=-1;
        public int Evaluated,Proposed,Accepted,Financed,Reductions;
        public int RightCensored=0;
        public decimal SumMarginPeak,SumRiskPeak;
        public bool MissingFloatingMarks;
        public Book(string policy,decimal mult){Policy=policy;Multiplier=mult;}
        public string Id(string action)=>"V33/"+Policy+"/"+Multiplier.ToString(CultureInfo.InvariantCulture)+"/"+action+"/"+(++Seq);
        public void Count(string key)=>Counters[key]=Counters.GetValueOrDefault(key)+1;
        public void Reject(string key)=>Rejections[key]=Rejections.GetValueOrDefault(key)+1;
        public LedgerEvent Fact(long at,string kind,LedgerQuote? q=null,string pos="",int side=0,
            decimal units=0,decimal price=0,decimal fee=0,decimal margin=0,
            decimal slip=0,long available=0,long calibrated=0,long latency=100,
            string reason="MODELED_ONLY",decimal financing=0,string sym="")
        {
            // Multi-position ACCOUNT chronology: same-clock funding, reductions
            // and other intents cannot reverse the ledger's monetary clock.
            // Millisecond ordering is strictly within the real next-bar gap,
            // and never moves a price or feature backward or into the future.
            long eventAt=Math.Max(at,LastEventAt+1L);
            LastEventAt=eventAt;
            return new(Id(kind),eventAt,kind,pos,q?.Symbol??sym,side,units,price,
                fee,margin,slip,available,calibrated,latency,reason,Evidence,
                q is null?Array.Empty<LedgerQuote>():new[]{q},financing);
        }
        public void Observe(long now)
        {
            var s=Ledger.Summary();
            Equity.Add((now,s.LiquidationEquityEur,s.UsedMarginEur,s.MaximumSampledDrawdown));
            if(s.LiquidationEquityEur is null)MissingFloatingMarks=true;
            SumMarginPeak=Math.Max(SumMarginPeak,s.UsedMarginEur??0m);
            SumRiskPeak=Math.Max(SumRiskPeak,Held.Values.Sum(x=>x.ReservedRisk));
        }
        public object Receipt(Dictionary<string,int> sourceWeeks)
        {
            var summary=Ledger.Summary();
            var fragments=Ledger.ClosedFragments();
            var completed=fragments.Where(x=>x.CompletesRoundTrip).ToArray();
            var expected=completed.Length;
            if(expected!=summary.CompleteRoundTrips||fragments.Sum(x=>x.NetEur)!=summary.ClosedNetEur)
                throw new InvalidOperationException("V33_EXISTING_LEDGER_CLOSED_CASH_IDENTITY");
            var completedByWeek=completed.GroupBy(x=>Week(x.ClosedAt))
                .ToDictionary(g=>g.Key,g=>g.ToArray(),StringComparer.Ordinal);
            var byWeek=sourceWeeks.OrderBy(g=>g.Key,StringComparer.Ordinal)
                .Select(g=>{
                    var items=completedByWeek.TryGetValue(g.Key,out var observed)
                        ? observed:Array.Empty<LedgerClosedFragment>();
                    return new{Week=g.Key,GenuineDecisionEvents=g.Value,
                        Completed=items.Length,NET_EUR=items.Sum(x=>x.NetEur),
                        HARD21Mathematical=items.Length>=21,EligibilityOfficial=false};
                }).ToArray();
            var trades=fragments.Select(x=>new{
                x.PositionId,x.Symbol,x.OpenedAt,x.ClosedAt,
                Week=Week(x.ClosedAt),Side=SideByPosition.GetValueOrDefault(x.PositionId),
                x.Units,x.GrossEur,x.SpreadEur,x.SlippageEur,x.ConversionEur,
                x.CommissionsEur,x.FinancingEur,x.NetEur,x.CompletesRoundTrip,x.Reason
            }).ToArray();
            return new{
                Policy,Multiplier,InitialCapitalEur=Capital,
                NET_EUR=summary.ClosedNetEur,
                NET_VS_CASH_PERCENT=summary.ClosedNetEur/Capital*100m,
                EndCashEur=summary.CashEur,EndMarkedEquityEur=summary.LiquidationEquityEur,
                EndMarginEur=summary.UsedMarginEur,
                PeakSampledMarginEur=SumMarginPeak,PeakReservedStopRiskEur=SumRiskPeak,
                SampledDDPercent=summary.MaximumSampledDrawdown*100m,
                IntrabarDDCertified=false,HistoricalNETCertified=false,
                Evaluated,Proposed,Accepted,Financed,Completed=expected,Reductions,
                Rejected=Rejections.Values.Sum(),RejectReasons=Rejections,
                RightCensored=Held.Count+Pending.Count+RightCensored,
                MaximumConcurrentHeld=Equity.Count>0?MaxConcurrentHeld:0,
                UncertainFloatingMarks=MissingFloatingMarks,
                Counters,Context,BySymbol=completed.GroupBy(x=>x.Symbol).OrderBy(g=>g.Key)
                    .Select(g=>new{Symbol=g.Key,Trips=g.Count(),NET_EUR=g.Sum(x=>x.NetEur)}).ToArray(),
                Weekly=byWeek,AllModeledLedgerFragments=trades,
                CashEventHash=summary.EventChainHash,
                RemainingHeld=Held.Keys.OrderBy(x=>x).ToArray(),
                RemainingPending=Pending.Keys.OrderBy(x=>x).ToArray(),
                EligibleWeeksCertified=0,HARD21Certified=false,Orders=0,Cloud=false
            };
        }
        public int MaxConcurrentHeld;
    }
    static string Group(string symbol)
    {
        if(symbol.Length==6 && symbol.All(char.IsLetter))return "FX";
        if(symbol.Contains("USD",StringComparison.Ordinal)||
           symbol.Contains("XAU",StringComparison.Ordinal))return "USD_EXPOSED";
        return "OTHER";
    }
    static void CloseRequest(Book book,Position pos,LedgerQuote q,long at,decimal units,string why,long width)
    {
        if(book.Pending.ContainsKey(pos.Market.Source.Symbol))return;
        string reason=units<pos.Units?"MODEL_UNTRANSMITTED_INTEGRATED_FAVORABLE_REDUCTION":why;
        book.Ledger.Apply(book.Fact(at+500,"REQUEST_CLOSE",q,pos.Id,pos.Side,units,reason:reason));
        book.Pending[pos.Market.Source.Symbol]=new Pending{Id=pos.Id,Kind="CLOSE",
            Market=pos.Market,Side=pos.Side,Units=units,Slippage=pos.Slippage,
            RequestedAt=at+500,Width=width,Why=reason};
        book.Count(units<pos.Units?"REDUCE_REQUEST":"CLOSE_REQUEST");
    }
    static decimal? ExpectedNet(V32Terms t,LedgerQuote q,int side,decimal units,
        decimal predictedBps,decimal slippage,long clock,long width)
    {
        // One signed gross prediction at genuinely available EUR conversion.
        decimal notional=q.Bid*units*(q.EurCredit+q.EurDebit)/2m;
        decimal gross=side*predictedBps/10000m*notional;
        decimal roundtrip=2m*Fee(q,units)+
            (q.Ask-q.Bid+2m*slippage)*units*q.EurDebit;
        // This is a conservative modeled funding reserve, never an
        // authenticated historical overnight tariff or observed broker deal.
        decimal overnight=notional*FundingBpsPerDay/10000m*
            (width>6*60*Minute?1m:0m);
        return gross-roundtrip-overnight;
    }
    static decimal RiskAtStop(Offer offer,decimal units)
    {
        var q=offer.Quote;
        decimal risk=1.5m*offer.Atr*units*q.EurDebit+
            (q.Ask-q.Bid+2m*offer.Slippage)*units*q.EurDebit+
            2m*Fee(q,units);
        return Math.Max(0m,risk);
    }
    static Offer? Score(StudyMarket market,BarEvent evt,Feature[] features,
        string policy,decimal factor,Dictionary<string,(decimal,long)> fx,Book book,int side)
    {
        book.Evaluated++;
        var model=market.Predict(features,policy,evt.At);
        if(model is null){book.Reject("INSUFFICIENT_MATURED_LABELS");return null;}
        if(policy=="LONG"&&side<0||policy=="SHORT"&&side>0)return null;
        var q=Quote(market,evt.Bar,factor,fx,out var slippage);
        if(q is null){book.Reject("COST_FX_CONTRACT_UNKNOWN");return null;}
        var t=market.Source.Terms!;
        decimal units=t.MinimumUnits!.Value,atr=market.Atr(evt);
        if(atr<=0){book.Reject("ATR_UNKNOWN");return null;}
        decimal predicted=side*model.MeanBps;
        decimal lower=side>0?model.LowerLongBps:-model.UpperShortBps;
        decimal meanNet=ExpectedNet(t,q,1,units,predicted,slippage,evt.At,Width(evt.Tf))??decimal.MinValue;
        decimal lowerNet=ExpectedNet(t,q,1,units,lower,slippage,evt.At,Width(evt.Tf))??decimal.MinValue;
        // FIRST is a non-predictive, deterministic financeable comparator.
        if(policy!="FIRST"&&lowerNet<=0m)
        {book.Reject("PREDICTIVE_NET_LOWER_NOT_POSITIVE");return null;}
        book.Proposed++;
        return new(market,side,evt.Tf,model,atr,meanNet,lowerNet,
            0m,units,q,slippage);
    }
    static decimal RecentAbsoluteCorrelation(StudyMarket candidate,StudyMarket held,long asOf)
    {
        const int window=16;
        var x=candidate.Closed("M15",asOf,window+1);
        var y=held.Closed("M15",asOf,window+1);
        if(x.Length<window+1||y.Length<window+1)
            return 1m; // unknown correlation is never assumed safely zero
        for(int i=0;i<x.Length;i++)
        {
            if(x[i].OpenAt!=y[i].OpenAt||x[i].Open<=0m||y[i].Open<=0m)
                return 1m;
        }
        decimal meanX=0m,meanY=0m;
        var a=new decimal[window];var b=new decimal[window];
        for(int i=0;i<window;i++)
        {
            a[i]=(x[i+1].Close-x[i+1].Open)/x[i+1].Open;
            b[i]=(y[i+1].Close-y[i+1].Open)/y[i+1].Open;
            meanX+=a[i];meanY+=b[i];
        }
        meanX/=window;meanY/=window;
        decimal xx=0m,yy=0m,xy=0m;
        for(int i=0;i<window;i++)
        {
            decimal u=a[i]-meanX,v=b[i]-meanY;
            xx+=u*u;yy+=v*v;xy+=u*v;
        }
        if(xx<=0m||yy<=0m)return 1m;
        return Math.Min(1m,Math.Abs(xy)/(decimal)Math.Sqrt((double)(xx*yy)));
    }
    static bool Fundable(Book book,Offer o,out decimal units,out string reason)
    {
        units=0m;reason="RISK";
        var terms=o.Market.Source.Terms!;
        var summary=book.Ledger.Summary();
        decimal eq=summary.LiquidationEquityEur??summary.CashEur;
        if(eq<=0m||summary.MaximumSampledDrawdown>=.245m){reason="EQUITY_KILL";return false;}
        if(book.Held.Count>0 && summary.LiquidationEquityEur is null)
        {reason="HOLDING_MARK_UNKNOWN";return false;}
        if(book.Held.ContainsKey(o.Market.Source.Symbol)||
           book.Pending.ContainsKey(o.Market.Source.Symbol))
        {reason="SAME_SYMBOL_OCCUPIED";return false;}
        decimal min=terms.MinimumUnits!.Value,max=terms.MaximumUnits!.Value,step=terms.StepUnits!.Value;
        decimal risk=RiskAtStop(o,min),perUnit=risk/min;
        decimal marginUnit=terms.MarginMinimumEur!.Value/min;
        decimal reserved=book.Held.Values.Sum(x=>x.ReservedRisk);
        // Correlation: conservative double-count same-class stop exposure.
        string group=Group(o.Market.Source.Symbol);
        decimal correlated=book.Held.Values.Sum(p=>
            p.ReservedRisk*Math.Max(RecentAbsoluteCorrelation(o.Market,p.Market,o.Quote.At),
                Group(p.Market.Source.Symbol)==group?0.5m:0m));
        decimal remainingRisk=Math.Min(RiskPerTrade*eq,
            AggregateStopRisk*eq-reserved-.5m*correlated);
        decimal usedMargin=book.Held.Values.Sum(x=>x.Units*
            x.Market.Source.Terms!.MarginMinimumEur!.Value/
            x.Market.Source.Terms.MinimumUnits!.Value);
        decimal remainMargin=MaximumMargin*eq-usedMargin;
        if(perUnit<=0||marginUnit<=0||remainingRisk<perUnit*min)
        {reason="STOP_RISK_BUDGET";return false;}
        if(remainMargin<=marginUnit*min){reason="MARGIN_BUDGET";return false;}
        decimal maxRisk=remainingRisk/perUnit,maxMargin=remainMargin/marginUnit;
        decimal upper=Math.Min(max,Math.Min(maxRisk,maxMargin));
        if(upper<min){reason="LEGAL_VOLUME";return false;}
        units=Math.Min(upper,min+Math.Floor((upper-min)/step)*step);
        if(units<min){reason="LEGAL_STEP";return false;}
        reason="ACCEPT";return true;
    }
    static void OpenRequest(Book book,Offer o,decimal units,long now)
    {
        string sym=o.Market.Source.Symbol;
        book.Ledger.Apply(book.Fact(now+100,"REQUEST_OPEN",o.Quote,book.Id("POS"),
            o.Side,units,margin:o.Market.Source.Terms!.MarginMinimumEur!.Value/
                o.Market.Source.Terms.MinimumUnits!.Value,slip:o.Slippage,
            available:now,calibrated:now,latency:100,
            reason:"NATIVE_CONDITIONAL_SELECTION"));
        // Retrieve exact pending id from the above request event? Reserve ID first.
    }
    // The single authoritative simulation is NativeFundedLedger.Apply.
    public static object Evaluate(V32Tape input,string frozenProtocolSha256)
    {
        if(!input.DevelopmentOnly||input.PriceNormalization!="ORIGINAL_PROTOWIRE_1E5_NO_SYNTHETIC_BAR"||
           input.SourceRuns.Length!=5||input.Markets.Length<48||
           frozenProtocolSha256.Length!=64||!frozenProtocolSha256.All(Uri.IsHexDigit)||
           input.Markets.Select(x=>x.Symbol).Distinct(StringComparer.Ordinal).Count()!=input.Markets.Length)
            throw new ArgumentException("V33_SOURCE_OR_PREREGISTRATION");
        var markets=input.Markets.Select(x=>new StudyMarket(x)).ToArray();
        var events=markets.SelectMany(m=>m.Events.Values)
            .OrderBy(e=>e.At).ThenBy(e=>e.Market.Source.Symbol,StringComparer.Ordinal).ToArray();
        var fx=new Dictionary<string,(decimal,long)>(StringComparer.Ordinal);
        var sourceWeeks=events.GroupBy(e=>Week(e.At))
            .ToDictionary(g=>g.Key,g=>g.Count(),StringComparer.Ordinal);
        var books=Multipliers.SelectMany(m=>Policies.Select(p=>new Book(p,m))).ToArray();
        // At every decision clock train ONLY fully matured earlier outcomes.
        foreach(var clock in events.GroupBy(e=>e.At))
        {
            long now=clock.Key;
            var active=clock.ToArray();
            foreach(var market in markets)market.Mature(now);
            foreach(var evt in active)
                if(evt.Market.Source.Symbol is "EURUSD" or "USDJPY" or "USDCAD" or
                    "GBPUSD" or "AUDUSD" or "NZDUSD" or "USDCHF")
                    fx[evt.Market.Source.Symbol]=(evt.Bar.Open,now);
            var observed=active.ToDictionary(e=>e.Market.Source.Symbol,e=>e,StringComparer.Ordinal);
            var features=active.Where(e=>e.Market.Ready(e))
                .ToDictionary(e=>e.Market.Source.Symbol,
                    e=>e.Market.Features(now,e.Tf),StringComparer.Ordinal);
            foreach(var book in books)
            {
                if(book.Policy=="CASH")continue;
                // Only use genuine market clocks for modeled quotes.
                var quotes=new Dictionary<string,LedgerQuote>(StringComparer.Ordinal);
                var slips=new Dictionary<string,decimal>(StringComparer.Ordinal);
                foreach(var e in active)
                {
                    var q=Quote(e.Market,e.Bar,book.Multiplier,fx,out var sl);
                    if(q is null)continue;
                    quotes[e.Market.Source.Symbol]=q;slips[e.Market.Source.Symbol]=sl;
                }
                if(book.Held.Count>0)
                {
                    if(book.Held.Keys.All(quotes.ContainsKey))
                    {
                        var sorted=book.Held.Keys.Select(k=>quotes[k]).ToArray();
                        book.Ledger.Apply(new LedgerEvent(book.Id("MARK"),now,"MARK","", "",0,0m,
                            0m,0m,0m,0m,now,now,100,"ASOF_CONDITIONAL_MODEL",Evidence,sorted));
                        book.LastEventAt=now;
                        book.Observe(now);
                    }
                    else{book.MissingFloatingMarks=true;book.Count("HOLDING_MARK_UNKNOWN");}
                }
                // Close intents and open intents are distinct from fills;
                // model fills occur ONLY on the next genuine broker bar.
                foreach(var intent in book.Pending.Values.ToArray())
                {
                    string sym=intent.Market.Source.Symbol;
                    if(now<=intent.RequestedAt)continue;
                    if(!observed.TryGetValue(sym,out var evt)||!quotes.TryGetValue(sym,out var q))
                    {
                        if(intent.Kind=="OPEN" && now-intent.RequestedAt>intent.Width+1000)
                        {
                            book.Ledger.Apply(book.Fact(now+200,"MODEL_OPEN_INTENT_EXPIRED",null,
                                intent.Id,intent.Side,intent.Units,
                                reason:"MODEL_UNTRANSMITTED_OPEN_RESPONSE_WINDOW_EXPIRED",sym:sym));
                            book.Pending.Remove(sym);book.Reject("UNFILLED_SOURCE_GAP");
                        }
                        else if(intent.Kind=="CLOSE")book.Count("CLOSE_WITNESS_UNKNOWN");
                        continue;
                    }
                    if(intent.Kind=="OPEN")
                    {
                        if(now-intent.RequestedAt>intent.Width+1000)
                        {
                            book.Ledger.Apply(book.Fact(now+200,"MODEL_OPEN_INTENT_EXPIRED",null,
                                intent.Id,intent.Side,intent.Units,
                                reason:"MODEL_UNTRANSMITTED_OPEN_RESPONSE_WINDOW_EXPIRED",sym:sym));
                            book.Pending.Remove(sym);book.Reject("LATE_FILL_CENSORED");continue;
                        }
                        decimal entry=Price(q,intent.Side,intent.Slippage,true);
                        decimal perMargin=intent.Market.Source.Terms!.MarginMinimumEur!.Value/
                            intent.Market.Source.Terms.MinimumUnits!.Value;
                        try
                        {
                            book.Ledger.Apply(book.Fact(now+200,"OPEN_FILL",q,intent.Id,intent.Side,
                                intent.Units,entry,Fee(q,intent.Units),perMargin,intent.Slippage));
                            var p=new Position{Id=intent.Id,Market=intent.Market,Side=intent.Side,
                                Units=intent.Units,Entry=entry,Stop=entry-intent.Side*1.5m*intent.Atr,
                                Target=entry+intent.Side*3m*intent.Atr,Best=entry,Atr=intent.Atr,
                                Slippage=intent.Slippage,OpenAt=now,LastFinancingAt=now,
                                ReservedRisk=1.5m*intent.Atr*intent.Units*q.EurDebit+
                                    (q.Ask-q.Bid+2m*intent.Slippage)*intent.Units*q.EurDebit+
                                    2m*Fee(q,intent.Units)};
                            book.Held[sym]=p;
                            book.Financed++;book.SideByPosition[intent.Id]=intent.Side;
                            book.MaxConcurrentHeld=Math.Max(book.MaxConcurrentHeld,book.Held.Count);
                            book.Count("OPEN_FILL");
                        }
                        catch(InvalidOperationException)
                        {
                            book.Ledger.Apply(book.Fact(now+300,"MODEL_OPEN_INTENT_EXPIRED",
                                null,intent.Id,intent.Side,intent.Units,
                                reason:"MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED",sym:sym));
                            book.Reject("BROKER_LEDGER_FINANCING_REJECT");
                        }
                        book.Pending.Remove(sym);
                    }
                    else if(intent.Kind=="CLOSE" && book.Held.TryGetValue(sym,out var held))
                    {
                        decimal exit=Price(q,held.Side,intent.Slippage,false);
                        decimal perMargin=held.Market.Source.Terms!.MarginMinimumEur!.Value/
                            held.Market.Source.Terms.MinimumUnits!.Value;
                        book.Ledger.Apply(book.Fact(now+200,"CLOSE_FILL",q,held.Id,held.Side,
                            intent.Units,exit,Fee(q,intent.Units),perMargin,
                            intent.Slippage,reason:intent.Why));
                        if(intent.Units==held.Units){book.Held.Remove(sym);book.Count("CLOSE_FILL");}
                        else
                        {
                            held.Units-=intent.Units;
                            held.ReservedRisk*=held.Units/(held.Units+intent.Units);
                            book.Reductions++;book.Count("REDUCE_FILL");
                        }
                        book.Pending.Remove(sym);
                    }
                }
                // Existing held positions are managed on genuinely completed bars.
                foreach(var position in book.Held.Values.ToArray())
                {
                    string sym=position.Market.Source.Symbol;
                    if(book.Pending.ContainsKey(sym) || !observed.TryGetValue(sym,out var evt) ||
                       !quotes.TryGetValue(sym,out var q))continue;
                    if(now-position.LastFinancingAt>=Day)
                    {
                        int days=(int)((now-position.LastFinancingAt)/Day);
                        decimal notional=position.Entry*position.Units*(q.EurCredit+q.EurDebit)/2m;
                        decimal financing=-days*notional*FundingBpsPerDay*book.Multiplier/10000m;
                        book.Ledger.Apply(book.Fact(now+300,"FINANCING",q,position.Id,
                            position.Side,position.Units,financing:financing));
                        position.LastFinancingAt+=days*Day;
                    }
                    var history=position.Market.Closed(evt.Tf,now,4);
                    if(history.Length<4)continue;
                    decimal last=history[^1].Close;
                    position.Best=position.Side>0?Math.Max(position.Best,last):
                        Math.Min(position.Best,last);
                    decimal trail=position.Best-position.Side*1.5m*position.Atr;
                    position.Stop=position.Side>0?Math.Max(position.Stop,trail):
                        Math.Min(position.Stop,trail);
                    bool stop=position.Side*(last-position.Stop)<=0m;
                    bool target=position.Side*(last-position.Target)>=0m;
                    var feature=features.GetValueOrDefault(sym);
                    var continuation=feature is null?null:position.Market.Predict(feature,book.Policy,now);
                    bool invalid=continuation is not null &&
                        position.Side*(continuation.MeanBps)<0m;
                    bool equityProtect=book.Ledger.Summary().MaximumSampledDrawdown>=.245m;
                    string? reason=equityProtect?"PORTFOLIO_DD_GUARD":
                        stop?"COMPLETED_BAR_STOP":target?"COMPLETED_BAR_TARGET":
                        invalid?"PREDICTIVE_INVALIDATION":null;
                    if(reason is not null)
                    {
                        CloseRequest(book,position,q,now,position.Units,reason,Width(evt.Tf));
                        continue;
                    }
                    // REDUCE only if a legal partial position remains and there is
                    // risk headroom uncertainty while expected continuation weakens.
                    decimal min=position.Market.Source.Terms?.MinimumUnits??decimal.MaxValue;
                    decimal step=position.Market.Source.Terms?.StepUnits??decimal.MaxValue;
                    decimal cut=step>0m?Math.Floor(position.Units/2m/step)*step:0m;
                    bool legal=cut>=min&&position.Units-cut>=min;
                    if(legal&&continuation is not null&&
                       position.Side*continuation.MeanBps<continuation.ErrorBps)
                    {
                        CloseRequest(book,position,q,now,cut,"WEAK_CONTINUATION_REDUCE",Width(evt.Tf));
                        continue;
                    }
                    book.Count("HOLD");
                }
                if(book.Ledger.Summary().MaximumSampledDrawdown>=.245m)
                {book.Count("RISK_PAUSE");continue;}
                if(book.Held.Keys.Any(sym=>!observed.ContainsKey(sym)||!quotes.ContainsKey(sym)))
                {
                    // No same-clock executable-side model witness for at least
                    // one held risk. Never use stale equity to underwrite a
                    // fresh position from a different market.
                    book.Reject("PORTFOLIO_HOLDING_CLOCK_UNKNOWN");
                    continue;
                }
                var offered=new List<Offer>();
                foreach(var evt in active)
                {
                    if(!features.TryGetValue(evt.Market.Source.Symbol,out var f))continue;
                    foreach(int side in new[]{1,-1})
                    {
                        var a=Score(evt.Market,evt,f,book.Policy,book.Multiplier,fx,book,side);
                        if(a is not null)offered.Add(a);
                    }
                }
                var ranked=book.Policy=="FIRST"?
                    offered.OrderBy(x=>x.Market.Source.Symbol,StringComparer.Ordinal)
                        .ThenBy(x=>x.Side):
                    offered.OrderByDescending(x=>x.LowerNetEur)
                        .ThenBy(x=>x.Market.Source.Symbol,StringComparer.Ordinal);
                foreach(var offer in ranked)
                {
                    if(!Fundable(book,offer,out var units,out var reason))
                    {book.Reject(reason);continue;}
                    string sym=offer.Market.Source.Symbol;
                    string id=book.Id("POSITION");
                    long width=Width(offer.Tf);
                    try
                    {
                        book.Ledger.Apply(book.Fact(now+700+book.Pending.Count,"REQUEST_OPEN",
                            offer.Quote,id,offer.Side,units,
                            margin:offer.Market.Source.Terms!.MarginMinimumEur!.Value/
                                offer.Market.Source.Terms.MinimumUnits!.Value,
                            slip:offer.Slippage,available:now,calibrated:now,
                            latency:100,reason:"NATIVE_CONDITIONAL_SELECTION"));
                    }
                    catch(ArgumentException){book.Reject("HELD_MARK_UNKNOWN");continue;}
                    book.Pending[sym]=new Pending{Id=id,Kind="OPEN",Market=offer.Market,
                        Side=offer.Side,Units=units,Slippage=offer.Slippage,
                        Atr=offer.Atr,Width=width,RequestedAt=now+700+book.Pending.Count};
                    book.Accepted++;book.Count("ALLOCATE_REQUEST");
                    string ctx=offer.Estimate.Regime;
                    book.Context[ctx]=book.Context.GetValueOrDefault(ctx)+1;
                }
                book.Count("WAIT_CLOCK");
            }
            foreach(var evt in active)
            {
                if(!features.TryGetValue(evt.Market.Source.Symbol,out var f))continue;
                evt.Market.QueueLabel(evt,f);
            }
        }
        return new{
            Schema=Version,InputRuns=input.SourceRuns,
            OriginalSourceProtocolSha256=input.ProtocolSha256,
            PreregisteredNewProtocolSha256=frozenProtocolSha256,
            SourceCoverage=markets.OrderBy(x=>x.Source.Symbol,StringComparer.Ordinal).Select(x=>x.Coverage()).ToArray(),
            GenuineMarketClocks=events.Length,
            Results=books.Select(b=>b.Receipt(sourceWeeks)).ToArray(),
            CashBenchmarkEur=0,AllResultsDevelopmentExposed=true,
            HistoricalTariffContinuity=false,HistoricalExecutablePricesCertified=false,
            IntrabarDDCertified=false,HARD21Certified=false,IndependentConfirmation=false,
            BrokerRequests=0,Orders=0,Cloud=false,ClosedStudyReruns=0
        };
    }
}
