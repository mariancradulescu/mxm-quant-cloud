using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Mxm.Core;

// V3.2: ONE modeled economic study, reusing the exact existing native funded ledger.
// Authentic OHLC inputs. Historical BID/ASK, FX, slippage and financing are NOT certified fills.
public sealed record V32Bar(long OpenAt,decimal Open,decimal High,decimal Low,decimal Close,long TickVolume);
public sealed record V32Terms(string Symbol,string QuoteAsset,decimal? MinimumUnits,
    decimal? StepUnits,decimal? MaximumUnits,decimal? LotUnits,int? CommissionType,
    long? PreciseRateWire,int? MinimumCommissionType,long? PreciseMinimumWire,
    string? MinimumCommissionAsset,int? PnlConversionFeeBps,int? SwapCalculationType,
    decimal? LongSwap,decimal? ShortSwap,int? PipPosition,int? SwapPeriodHours,
    int? SwapTimeUtcMinute,int? TripleSwapWeekday,decimal? MarginMinimumEur,
    decimal? SpreadBps,long ObservedAtUtcMs,bool HistoricallyCertified=false);
public sealed record V32Market(string Symbol,V32Terms? Terms,Dictionary<string,V32Bar[]> Bars);
public sealed record V32Tape(string[] SourceRuns,string ProtocolSha256,string PriceNormalization,
    bool DevelopmentOnly,V32Market[] Markets);
public sealed record V32ClosedModelTrade(string Symbol,long OpenedAt,long ClosedAt,
    string Week,int Side,decimal Units,decimal GrossEur,decimal SpreadEur,decimal SlippageEur,
    decimal CommissionsEur,decimal ConversionEur,decimal FinancingEur,decimal NetEur,string Reason);

public static class NativeV32UnifiedEconomic
{
    public const string Version="V32_INTEGRATED_EUR300_NATIVE_DEVELOPMENT";
    const long Minute=60000, M15=900000, Day=86400000;
    const decimal Initial=300m, Stress=210m, RiskPerTrade=.015m;
    const decimal ModelFxWedge=.00025m, ModelFundingBpsPerDay=5m;
    static readonly string Evidence=new string('a',64);
    static readonly string[] Variants={"CASH","FIRST","FULL","NO_M1","NO_M5","LONG","SHORT"};
    static readonly decimal[] StressMultipliers={1m,1.5m,2m};
    static long Width(string k)=>k switch{
        "M1"=>Minute,"M5"=>5*Minute,"M15"=>M15,"M30"=>30*Minute,
        "H1"=>60*Minute,"H4"=>240*Minute,"D1"=>Day,_=>throw new ArgumentException("V32_BAD_TIMEFRAME")};
    static string Week(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);}
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static int Sign(decimal x)=>x>0?1:x<0?-1:0;

    sealed class Market
    {
        public readonly V32Market Source;
        public readonly Dictionary<string,V32Bar[]> Bars;
        public readonly Dictionary<long,V32Bar> At;
        public Market(V32Market source)
        {
            Source=source;
            Bars=source.Bars.ToDictionary(p=>p.Key,p=>p.Value.OrderBy(x=>x.OpenAt).ToArray());
            foreach(var p in Bars)
            {
                long width=Width(p.Key);long prev=-1;
                foreach(var b in p.Value)
                {
                    if(b.OpenAt<=prev || b.Open<=0 || b.Low<=0 || b.High<Math.Max(b.Open,b.Close)||
                       b.Low>Math.Min(b.Open,b.Close)||b.TickVolume<0 ||
                       b.OpenAt%width!=0)throw new ArgumentException("V32_ORIGINAL_PRICE_CLOCK_OR_GEOMETRY");
                    prev=b.OpenAt;
                }
            }
            At=(Bars.GetValueOrDefault("M15")??Array.Empty<V32Bar>())
                .ToDictionary(x=>x.OpenAt);
        }
        public V32Bar[] Closed(string tf,long at,int take)
        {
            if(!Bars.TryGetValue(tf,out var a))return Array.Empty<V32Bar>();
            long w=Width(tf);int lo=0,hi=a.Length;
            while(lo<hi){int mid=(lo+hi)/2;if(a[mid].OpenAt+w<=at)lo=mid+1;else hi=mid;}
            return a[Math.Max(0,lo-take)..lo];
        }
    }
    sealed record Signal(Market Market,int Side,decimal Atr,decimal Strength,string Regime,string Context);
    sealed class Position
    {
        public Signal Signal;
        public string Id;
        public decimal Units;
        public decimal Entry;
        public decimal Stop;
        public decimal Target;
        public decimal Best;
        public decimal Slippage;
        public long OpenAt;
        public long LastMark;
        public string ExitReason="";
    }
    sealed class Intent
    {
        public string Kind;
        public Signal Signal;
        public string Id;
        public decimal Units;
        public decimal Slippage;
        public long At;
        public string Reason="";
    }
    sealed class Book
    {
        public readonly string Name;
        public readonly decimal Factor;
        public readonly NativeFundedLedger Money=new(M15+1000);
        public Position? Open;
        public Intent? Pending;
        public long Seq;
        public int Proposed,Admitted,RejectCost,RejectRisk,RejectMargin,UnknownMarks,
            Censored,HoldActions,CloseActions,WaitActions,ReduceActions;
        public readonly Dictionary<string,int> Regimes=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> Contexts=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> Actions=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> SideByPosition=new(StringComparer.Ordinal);
        public Book(string name,decimal factor){Name=name;Factor=factor;}
        public string Id(string kind)=>"V32/"+Name+"/"+Factor.ToString(CultureInfo.InvariantCulture)+"/"+kind+"/"+(++Seq);
        public void Action(string k){Actions[k]=Actions.GetValueOrDefault(k)+1;}
        public object Receipt()
        {
            var status=Money.Summary();var closed=Money.ClosedFragments();
            var complete=closed.Where(x=>x.CompletesRoundTrip).ToArray();
            var weekly=complete.GroupBy(t=>Week(t.ClosedAt)).OrderBy(g=>g.Key)
                .Select(g=>new{Week=g.Key,Completed=g.Count(),NET_EUR=g.Sum(t=>t.NetEur),
                    HARD21_Conditional=g.Count()>=21,CalendarEligibleCertified=false}).ToArray();
            var detail=closed.Select(c=>new V32ClosedModelTrade(c.Symbol,c.OpenedAt,c.ClosedAt,
                Week(c.ClosedAt),SideByPosition.GetValueOrDefault(c.PositionId),c.Units,c.GrossEur,
                c.SpreadEur??0m,c.SlippageEur??0m,c.CommissionsEur,c.ConversionEur??0m,
                c.FinancingEur,c.NetEur,c.Reason)).ToArray();
            return new{
                Policy=Name,CostMultiplier=Factor,InitialEur=Initial,
                ClosingCashEur=status.CashEur,NET_EUR=status.ClosedNetEur,
                NET_VS_CASH_Pct=status.ClosedNetEur/Initial*100m,
                FundedModeledCompleteTrips=status.CompleteRoundTrips,
                FloatingSampledDD_Pct=status.MaximumSampledDrawdown*100m,
                FloatingIntrabarDDCertified=false,
                EndingMarkedEquityEur=status.LiquidationEquityEur,
                EndingUsedMarginEur=status.UsedMarginEur,EndingFreeMarginEur=status.FreeMarginEur,
                ActivePositions=status.OpenPositions,PendingIntents=status.PendingIntents,
                HistoryEvidenceIncomplete=status.HistoryEvidenceIncomplete,
                status.EventChainHash,
                Proposed,Admitted,RejectCost,RejectRisk,RejectMargin,UnknownMarks,Censored,
                HoldActions,CloseActions,WaitActions,ReduceActions,Actions,Regimes,Contexts,
                Weekly=weekly,BySymbol=complete.GroupBy(x=>x.Symbol).OrderBy(g=>g.Key)
                    .Select(g=>new{Symbol=g.Key,Complete=g.Count(),NET_EUR=g.Sum(x=>x.NetEur)}).ToArray(),
                CompletedAndPartialTrades=detail,
                BrokerCertifiedNet=false,CertifiedHARD21=false,CertifiedDD30=false,
                CertifiedEligibleWeeks=0,Orders=0,CloudActivated=false
            };
        }
    }
    static decimal? Fx(string currency,Dictionary<string,(decimal,long)> fx,long now)
    {
        bool Get(string s,out decimal v)
        {v=0; if(!fx.TryGetValue(s,out var p)||p.Item1<=0||p.Item2>now||
                  now-p.Item2>3600000)return false;v=p.Item1;return true;}
        if(currency=="EUR")return 1m;
        if(!Get("EURUSD",out decimal eu))return null;
        if(currency=="USD")return 1m/eu;
        if(currency=="GBP"&&Get("GBPUSD",out var gb))return gb/eu;
        if(currency=="AUD"&&Get("AUDUSD",out var au))return au/eu;
        if(currency=="NZD"&&Get("NZDUSD",out var nz))return nz/eu;
        if(currency=="JPY"&&Get("USDJPY",out var jy))return 1m/(eu*jy);
        if(currency=="CAD"&&Get("USDCAD",out var ca))return 1m/(eu*ca);
        if(currency=="CHF"&&Get("USDCHF",out var ch))return 1m/(eu*ch);
        return null;
    }
    static NativeObservedContractTerms? Contract(V32Terms? c)
    {
        if(c is null || c.MinimumUnits is not >0 || c.StepUnits is not >0 ||
           c.MaximumUnits is not >0||c.LotUnits is not >0||
           c.CommissionType is null||c.PreciseRateWire is null||
           c.MinimumCommissionType is null||c.PreciseMinimumWire is null||
           c.PnlConversionFeeBps is null||c.PipPosition is null)return null;
        return new NativeObservedContractTerms(c.Symbol,c.QuoteAsset,c.ObservedAtUtcMs,
            c.MinimumUnits.Value,c.StepUnits.Value,c.MaximumUnits.Value,c.LotUnits.Value,
            c.CommissionType.Value,c.PreciseRateWire.Value,c.MinimumCommissionType.Value,
            c.PreciseMinimumWire.Value,c.MinimumCommissionAsset,c.PnlConversionFeeBps.Value,
            c.SwapCalculationType,c.LongSwap,c.ShortSwap,c.PipPosition,c.SwapPeriodHours,
            c.SwapTimeUtcMinute,c.TripleSwapWeekday,null,null,true,false);
    }
    static LedgerQuote? MakeQuote(Market m,V32Bar bar,decimal k,
        Dictionary<string,(decimal,long)> fx,out decimal slip)
    {
        slip=0;var c=m.Source.Terms;var actual=Contract(c);
        if(actual is null||c?.SpreadBps is not >0||c.MarginMinimumEur is not >0||
           c.MinimumUnits is not >0)return null;
        var route=Fx(c.QuoteAsset,fx,bar.OpenAt);var usd=Fx("USD",fx,bar.OpenAt);
        if(route is not >0 || usd is not >0)return null;
        decimal spread=bar.Open*c.SpreadBps.Value*k/10000m;
        decimal bid=bar.Open-spread/2m,ask=bar.Open+spread/2m;
        if(bid<=0)return null;
        slip=spread/2m;
        decimal? feeFx=c.MinimumCommissionAsset is null?null:Fx(c.MinimumCommissionAsset,fx,bar.OpenAt);
        try{
            var cost=new NativeMarketCostContext(bar.OpenAt,bid,ask,
                route.Value*(1-ModelFxWedge),route.Value*(1+ModelFxWedge),
                usd.Value,feeFx,c.MarginMinimumEur.Value,c.MinimumUnits.Value,slip);
            return NativeBrokerContractCosts.Quote(actual,cost).Quote with{LiquidationSlippagePerSide=slip};
        }catch(ArgumentException){return null;}catch(InvalidOperationException){return null;}
    }
    static Signal? Predict(Market m,long at,string policy)
    {
        var a=m.Closed("M15",at,9);
        if(a.Length<9)return null;
        for(int i=1;i<a.Length;i++)if(a[i].OpenAt-a[i-1].OpenAt!=M15)return null;
        decimal atr=0;
        for(int i=2;i<a.Length;i++)atr+=Math.Max(a[i].High-a[i].Low,
            Math.Max(Math.Abs(a[i].High-a[i-1].Close),Math.Abs(a[i].Low-a[i-1].Close)));
        atr/=7m;if(atr<=0)return null;
        int side=Sign(a[^1].Close-a[^1].Open);
        if(side==0||Sign(a[^2].Close-a[^2].Open)!=side)return null;
        if(policy=="LONG"&&side<0||policy=="SHORT"&&side>0)return null;
        var h1=m.Closed("H1",at,2);
        if(h1.Length==2 && h1[^1].OpenAt+3600000>=at-3600000 &&
           Sign(h1[^1].Close-h1[^2].Close)==-side && policy!="FIRST")return null;
        // Missing optional M1/M5 never vetoes the instrument.
        if(policy!="NO_M5"&&policy!="FIRST")
        {
            var micro=m.Closed("M5",at,3);
            if(micro.Length==3&&micro[^1].OpenAt+300000==at &&
               Sign(micro[^1].Close-micro[0].Open)==-side)return null;
        }
        if(policy!="NO_M1"&&policy!="FIRST")
        {
            var micro=m.Closed("M1",at,3);
            if(micro.Length==3&&micro[^1].OpenAt+Minute==at &&
               Sign(micro[^1].Close-micro[0].Open)==-side)return null;
        }
        var m30=m.Closed("M30",at,2);
        var h4=m.Closed("H4",at,2);
        var d1=m.Closed("D1",at,2);
        string regime=h4.Length==2?(Sign(h4[^1].Close-h4[^2].Close)==side?"H4_ALIGNED":"H4_OTHER"):
            h1.Length==2?"H1_ONLY":"M15_ONLY";
        string context="M15"+(m30.Length>0?"_M30":"")+(h1.Length>0?"_H1":"")+
            (h4.Length>0?"_H4":"")+(d1.Length>0?"_D1":"");
        return new Signal(m,side,atr,Math.Abs(a[^1].Close-a[^2].Open)/atr,regime,context);
    }
    static decimal Fee(LedgerQuote q,decimal units)=>Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units);
    static LedgerEvent Event(Book b,long at,string kind,LedgerQuote? quote=null,
        string pos="",int side=0,decimal units=0,decimal price=0,decimal fee=0,
        decimal margin=0,decimal slip=0,long available=0,long calibrated=0,long latency=100,
        string reason="MODEL_ONLY",decimal financing=0,string symbol="")
        =>new(b.Id(kind),at,kind,pos,quote?.Symbol??symbol,side,units,price,fee,
            margin,slip,available,calibrated,latency,reason,Evidence,
            quote is null?Array.Empty<LedgerQuote>():new[]{quote},financing);
    static void RequestClose(Book b,Position p,LedgerQuote quote,long at,string why)
    {
        if(b.Pending is not null)return;
        b.Money.Apply(Event(b,at+100,"REQUEST_CLOSE",quote,p.Id,p.Signal.Side,p.Units,
            reason:why));
        b.Pending=new Intent{Kind="CLOSE",Signal=p.Signal,Id=p.Id,
            Units=p.Units,Slippage=p.Slippage,At=at+100,Reason=why};
        b.CloseActions++;b.Action("CLOSE_REQUEST");
    }
    public static object Evaluate(V32Tape input)
    {
        if(!input.DevelopmentOnly || input.ProtocolSha256.Length!=64 ||
           input.PriceNormalization!="ORIGINAL_PROTOWIRE_1E5_NO_SYNTHETIC_BAR"||
           input.SourceRuns.Length!=5||input.Markets.Length<48||
           input.Markets.Select(m=>m.Symbol).Distinct(StringComparer.Ordinal).Count()!=input.Markets.Length)
            throw new ArgumentException("V32_AUTHENTIC_SOURCE_CONTRACT");
        var all=input.Markets.Select(x=>new Market(x)).ToArray();
        var markets=all.Where(x=>x.At.Count>0).ToArray();
        var clocks=markets.SelectMany(m=>m.At.Keys).Distinct().OrderBy(x=>x).ToArray();
        var fx=new Dictionary<string,(decimal,long)>(StringComparer.Ordinal);
        var books=StressMultipliers.SelectMany(k=>Variants.Select(p=>new Book(p,k))).ToArray();
        var coverage=all.OrderBy(m=>m.Source.Symbol,StringComparer.Ordinal).Select(m=>new{
            Symbol=m.Source.Symbol,SourceMarginEur=m.Source.Terms?.MarginMinimumEur,
            SampledSpreadBps=m.Source.Terms?.SpreadBps,
            Timeframes=m.Bars.ToDictionary(k=>k.Key,k=>new{Count=k.Value.Length,
                First=k.Value.Length>0?(long?)k.Value[0].OpenAt:null,
                Last=k.Value.Length>0?(long?)k.Value[^1].OpenAt:null})
        }).ToArray();
        foreach(long t in clocks)
        {
            var available=markets.Where(x=>x.At.ContainsKey(t)).OrderBy(x=>x.Source.Symbol,StringComparer.Ordinal).ToArray();
            foreach(var market in available)
            {
                string name=market.Source.Symbol;
                if(name is "EURUSD" or "USDJPY" or "USDCAD" or "GBPUSD" or "AUDUSD" or "NZDUSD" or "USDCHF")
                    fx[name]=(market.At[t].Open,t);
            }
            foreach(var b in books)
            {
                if(b.Name=="CASH")continue;
                if(b.Open is { } held)
                {
                    if(!held.Signal.Market.At.TryGetValue(t,out var bar))continue;
                    var quote=MakeQuote(held.Signal.Market,bar,b.Factor,fx,out _);
                    if(quote is null){b.UnknownMarks++;continue;}
                    b.Money.Apply(Event(b,t,"MARK",quote));
                    if(t/Day>held.LastMark/Day)
                    {
                        decimal notional=held.Entry*held.Units*(quote.EurCredit+quote.EurDebit)/2;
                        decimal funding=-notional*ModelFundingBpsPerDay*(t/Day-held.LastMark/Day)/10000m;
                        b.Money.Apply(Event(b,t+10,"FINANCING",quote,held.Id,held.Signal.Side,financing:funding));
                    }
                    if(t-held.LastMark>M15)b.UnknownMarks++;
                    held.LastMark=t;
                    if(b.Pending is {Kind:"CLOSE"} close)
                    {
                        decimal price=NativeExecutableEconomics.ExitPrice(
                            held.Signal.Side>0?quote.Bid:quote.Ask,held.Signal.Side,held.Slippage);
                        b.Money.Apply(Event(b,t+100,"CLOSE_FILL",quote,held.Id,held.Signal.Side,
                            held.Units,price,Fee(quote,held.Units),
                            held.Signal.Market.Source.Terms!.MarginMinimumEur!.Value/
                              held.Signal.Market.Source.Terms.MinimumUnits!.Value,
                            held.Slippage,reason:close.Reason));
                        b.Pending=null;b.Open=null;b.Action("CLOSE");continue;
                    }
                    var snapshot=b.Money.Summary();
                    if(snapshot.MaximumSampledDrawdown>=.30m)
                    {RequestClose(b,held,quote,t,"DRAWDOWN");continue;}
                    var completed=held.Signal.Market.Closed("M15",t,2);
                    if(completed.Length<2||completed[^1].OpenAt+M15!=t)
                    {b.UnknownMarks++;continue;}
                    decimal last=completed[^1].Close;
                    held.Best=held.Signal.Side>0?Math.Max(held.Best,last):Math.Min(held.Best,last);
                    decimal trail=held.Best-held.Signal.Side*1.5m*held.Signal.Atr;
                    held.Stop=held.Signal.Side>0?Math.Max(held.Stop,trail):Math.Min(held.Stop,trail);
                    bool stop=held.Signal.Side*(last-held.Stop)<=0;
                    bool target=held.Signal.Side*(last-held.Target)>=0;
                    bool invalid=Sign(completed[^1].Close-completed[^1].Open)==-held.Signal.Side &&
                        Sign(completed[^2].Close-completed[^2].Open)==-held.Signal.Side;
                    if(stop||target||invalid)RequestClose(b,held,quote,t,
                        stop?"STOP_CLOSED_BAR":target?"TARGET_CLOSED_BAR":"INVALIDATION_CLOSED_BAR");
                    else{b.HoldActions++;b.Action("HOLD");}
                    continue;
                }
                if(b.Pending is {Kind:"OPEN"} intent)
                {
                    if(!intent.Signal.Market.At.TryGetValue(t,out var bar))continue;
                    var quote=MakeQuote(intent.Signal.Market,bar,b.Factor,fx,out _);
                    if(quote is null){b.RejectCost++;b.UnknownMarks++;continue;}
                    b.Money.Apply(Event(b,t,"MARK",quote));
                    if(t-intent.At>M15+1000){b.Censored++;continue;}
                    decimal price=NativeExecutableEconomics.EntryPrice(quote,intent.Signal.Side,intent.Slippage);
                    try
                    {
                        b.Money.Apply(Event(b,t+100,"OPEN_FILL",quote,intent.Id,intent.Signal.Side,
                            intent.Units,price,Fee(quote,intent.Units),
                            intent.Signal.Market.Source.Terms!.MarginMinimumEur!.Value/
                              intent.Signal.Market.Source.Terms.MinimumUnits!.Value,intent.Slippage));
                        decimal dist=1.5m*intent.Signal.Atr;
                        b.Open=new Position{Signal=intent.Signal,Id=intent.Id,Entry=price,
                            Units=intent.Units,Stop=price-intent.Signal.Side*dist,
                            Target=price+intent.Signal.Side*2m*dist,Best=price,
                            Slippage=intent.Slippage,OpenAt=t,LastMark=t};
                        b.SideByPosition[intent.Id]=intent.Signal.Side;
                        b.Action("OPEN");
                    }
                    catch(InvalidOperationException)
                    {
                        b.Money.Apply(Event(b,t+200,"MODEL_OPEN_INTENT_EXPIRED",null,intent.Id,
                            intent.Signal.Side,intent.Units,
                            reason:"MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED",
                            symbol:intent.Signal.Market.Source.Symbol));
                        b.RejectMargin++;
                    }
                    b.Pending=null;continue;
                }
                if(b.Money.Summary().MaximumSampledDrawdown>=.30m){b.RejectRisk++;continue;}
                var found=available.Select(m=>Predict(m,t,b.Name)).Where(p=>p is not null).Cast<Signal>().ToArray();
                b.Proposed+=found.Length;
                if(found.Length==0){b.WaitActions++;b.Action("WAIT");continue;}
                var candidates=b.Name=="FIRST"?
                    found.OrderBy(s=>s.Market.Source.Symbol,StringComparer.Ordinal).ThenBy(s=>s.Side):
                    found.OrderByDescending(s=>s.Strength).ThenBy(s=>s.Market.Source.Symbol,StringComparer.Ordinal);
                bool placed=false;
                foreach(var signal in candidates)
                {
                    var market=signal.Market;
                    var quote=MakeQuote(market,market.At[t],b.Factor,fx,out decimal slip);
                    if(quote is null){b.RejectCost++;continue;}
                    var terms=market.Source.Terms!;
                    decimal units=terms.MinimumUnits!.Value;
                    var summary=b.Money.Summary();
                    decimal equity=summary.LiquidationEquityEur??summary.CashEur;
                    decimal fees=2m*Fee(quote,units);
                    decimal friction=(quote.Ask-quote.Bid+2m*slip)*units*quote.EurDebit+fees;
                    decimal risk=1.5m*signal.Atr*units*quote.EurDebit+friction;
                    if(risk<=0||risk>equity*RiskPerTrade ||
                       terms.MarginMinimumEur!.Value+friction>=Math.Min(equity,Stress))
                    {b.RejectRisk++;continue;}
                    b.Money.Apply(Event(b,t,"MARK",quote));
                    string id=b.Id("POS");
                    b.Money.Apply(Event(b,t+100,"REQUEST_OPEN",quote,id,signal.Side,units,
                        margin:terms.MarginMinimumEur.Value/units,slip:slip,
                        available:t,calibrated:t,latency:100,reason:"NATIVE_CONDITIONAL_SELECTION"));
                    b.Pending=new Intent{Kind="OPEN",Signal=signal,Id=id,Units=units,
                        Slippage=slip,At=t+100};
                    b.Admitted++;
                    b.Regimes[signal.Regime]=b.Regimes.GetValueOrDefault(signal.Regime)+1;
                    b.Contexts[signal.Context]=b.Contexts.GetValueOrDefault(signal.Context)+1;
                    b.Action(signal.Side>0?"LONG":"SHORT");placed=true;break;
                }
                if(!placed){b.RejectMargin++;b.WaitActions++;b.Action("WAIT");}
            }
        }
        return new{
            Schema=Version,input.SourceRuns,input.ProtocolSha256,
            Inputs=coverage,SourceMarkets=input.Markets.Length,
            DevelopmentOnly=true,PriceFills="MODEL_ONLY_NEXT_AUTHENTIC_M15_BAR_OPEN_NOT_OBSERVED_BID_ASK",
            Costs="ORIGINAL_CURRENT_CONTRACT_FIELDS_AND_QUOTE_SPREAD_WITH_ESTIMATED_FX_SLIPPAGE_SWAP",
            ModelFundingBpsPerDay,ModelFxWedge,
            Results=books.Select(b=>b.Receipt()).ToArray(),
            AllInHistoricalCostCertified=false,IndependentConfirmation=false,
            EligibilityCertifiedWeeks=0,HARD21Certified=false,IntrabarDDCertified=false,
            ModelOrders=0,CloudActivated=false,NoClosedStudyRerun=true
        };
    }
}