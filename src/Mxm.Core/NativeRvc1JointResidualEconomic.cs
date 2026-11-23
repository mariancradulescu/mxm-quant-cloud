using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Globalization;

namespace Mxm.Core;

// RVC1: a new, frozen, native Core joint FX residual INVENTORY experiment.
// Historical bars/cost models are CONDITIONAL, never certified broker fills.
// Entirely observation-only, no broker requests, no order methods or secrets.
public static class NativeRvc1JointResidualEconomic
{
    public const string Version="RVC1_FROZEN_FX_JOINT_RESIDUAL_DEVELOPMENT_ONLY";
    const long M5=300000L,M15=900000L,H1=3600000L,DAY=86400000L;
    const decimal Capital=300m,IrreversibleDd=.28m,StopSigma=3m;
    static readonly string[] Policies={"JOINT_RESIDUAL","PAIRED_NO_CONVERGENCE","SINGLE_EURUSD","CASH"};
    static readonly decimal[] Factors={1m,1.5m,2m};
    static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static string Week(long at){var d=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);}
    static bool Valid(V32Bar b)=>b.Open>0m&&b.High>=Math.Max(b.Open,b.Close)&&b.Low<=Math.Min(b.Open,b.Close)&&b.Low>0&&b.TickVolume>=0;
    static decimal Fee(LedgerQuote q,decimal units)=>Math.Max(q.ExitFeeFloor,q.ExitFeePerUnit*units);
    sealed record Reading(long At,double Ratio,double Mu,double Sigma,double Z,decimal LatestEur,decimal LatestGbp)
    {
        public int Signal=>Z>=1.5?1:Z<=-1.5?-1:0;
    }
    sealed class Leg
    {
        public string Symbol="",Id="";
        public int Side;public decimal Units,Margin,StopRisk,EntryPrice,StopPrice,Slip;
        public long OpenedAt;public bool RequestedClose,FundingBooked;
    }
    sealed class PairState
    {
        public double FrozenMu,FrozenSigma,EntryZ;
        public long SignaledAt,RequestedAt;public bool Orphaned;
    }
    sealed class Book
    {
        public readonly string Policy;
        public readonly decimal Factor;
        public NativeFundedLedger Ledger=new(M5+5000L);
        public Dictionary<string,Leg> Held=new(StringComparer.Ordinal);
        public Dictionary<string,Leg> Pending=new(StringComparer.Ordinal);
        public PairState? Pair;
        public bool Irreversible,Incomplete,UnknownFunding;
        public long Seq,LastAt;
        public int Decisions,PairOffers,FinancedPairs,CompletePairs,CompleteLegs,
            Waits,Holds,ReductionsUnavailable,CloseActions,TemporarySuspensions,
            HardStops,OrphanEvents,MarginRejects,UnknownMarks;
        public decimal PeakHeldPendingMargin,PeakHeldPendingRisk;
        public readonly Dictionary<string,int> Rejects=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> CompleteWeeks=new(StringComparer.Ordinal);
        public readonly Dictionary<string,decimal> NetWeeks=new(StringComparer.Ordinal);
        public readonly Dictionary<string,int> SourceWeeks=new(StringComparer.Ordinal);
        public Book(string policy,decimal factor){Policy=policy;Factor=factor;}
        public void Reject(string reason){Rejects[reason]=Rejects.GetValueOrDefault(reason)+1;}
        public long Clock(long now){LastAt=Math.Max(LastAt+1,now);return LastAt;}
        public LedgerEvent Event(long now,string kind,Leg? leg,LedgerQuote[] quotes,
            decimal price=0m,decimal fee=0m,decimal margin=0m,decimal slip=0m,
            string reason="NATIVE_CONDITIONAL_SELECTION",decimal financing=0m)
        {
            long at=Clock(now);
            string id="RVC1/"+Policy+"/"+Factor+"/"+(++Seq);
            return new LedgerEvent(id,at,kind,leg?.Id??"",leg?.Symbol??"",
                leg?.Side??0,leg?.Units??0,price,fee,margin,slip,
                Math.Max(0,now-10),Math.Max(0,now-10),100L,reason,
                Hash(id+"|"+kind+"|"+at+"|"+price),quotes,financing);
        }
        public void UpdateExposure(LedgerQuote[] quotes)
        {
            var m=quotes.ToDictionary(x=>x.Symbol,x=>x,StringComparer.Ordinal);
            decimal held=Held.Values.Sum(x=>x.Units*(m.TryGetValue(x.Symbol,out var q)?
                Math.Max(x.Margin,q.MarginPerUnit):x.Margin));
            decimal pending=Pending.Values.Sum(x=>x.Units*(m.TryGetValue(x.Symbol,out var q)?
                Math.Max(x.Margin,q.MarginPerUnit):x.Margin));
            PeakHeldPendingMargin=Math.Max(PeakHeldPendingMargin,held+pending);
            PeakHeldPendingRisk=Math.Max(PeakHeldPendingRisk,
                Held.Values.Sum(x=>x.StopRisk)+Pending.Values.Sum(x=>x.StopRisk));
        }
        public NativePendingCapitalGate.Commitment[] Commitments(bool pending,
            IReadOnlyDictionary<string,LedgerQuote> quotes)
        {
            var legs=(pending?Pending:Held).Values;
            return legs.Select(x=>new NativePendingCapitalGate.Commitment(
                x.Id,x.Symbol,x.Units,
                quotes.TryGetValue(x.Symbol,out var q)?
                    Math.Max(x.Margin,q.MarginPerUnit):x.Margin,
                x.StopRisk,"COMMON_FX",pending)).ToArray();
        }
        public object Receipt(string[] allWeeks)
        {
            var summary=Ledger.Summary();var fragments=Ledger.ClosedFragments();
            return new{
                Policy,Factor,StartingCapitalEUR=Capital,
                ClosingCashEur=summary.CashEur,
                ClosingLiquidationEquityEur=summary.LiquidationEquityEur,
                ClosedNetEUR=summary.ClosedNetEur,
                FinalOpenPositions=summary.OpenPositions,
                FinalPendingIntents=summary.PendingIntents,
                IsFullySettled=summary.OpenPositions==0&&summary.PendingIntents==0,
                ModeledMaxSampledDDPercent=summary.MaximumSampledDrawdown*100m,
                summary.ObservedPeakEur,summary.HistoryEvidenceIncomplete,
                EventChainSha256=summary.EventChainHash,
                PeakHeldPendingMarginEur=PeakHeldPendingMargin,
                PeakHeldPendingStopRiskEur=PeakHeldPendingRisk,
                Decisions,PairOffers,FinancedPairs,CompletePairs,CompleteLegs,
                Waits,Holds,ReductionsUnavailable,CloseActions,TemporarySuspensions,
                HardStops,OrphanEvents,MarginRejects,UnknownMarks,
                Irreversible,Incomplete,UnknownFunding,RejectReasons=Rejects,
                Weekly=allWeeks.Select(w=>new{
                    Week=w,SourceClocks=SourceWeeks.GetValueOrDefault(w),
                    CompleteJointPairs=CompleteWeeks.GetValueOrDefault(w),
                    NET_EUR=NetWeeks.GetValueOrDefault(w),
                    ModeledHARD21=CompleteWeeks.GetValueOrDefault(w)>=21,
                    EligibilityBrokerCertified=false}).ToArray(),
                ClosedFragments=fragments.Select(x=>new{
                    x.PositionId,x.Symbol,x.OpenedAt,x.ClosedAt,x.Units,x.GrossEur,
                    x.SpreadEur,x.SlippageEur,x.CommissionsEur,
                    x.ConversionEur,x.FinancingEur,x.NetEur,
                    x.CompletesRoundTrip,x.Reason}).ToArray(),
                AuthenticBrokerFillsCertified=false,
                ContinuousIntrabarDDCertified=false,
                HistoricalTariffContinuityCertified=false,
                IndependentConfirmation=false,Orders=0,Cloud=false
            };
        }
    }
    static V32Bar[] Bars(V32Market m,string tf)=>m.Bars.TryGetValue(tf,out var a)?
        a.OrderBy(x=>x.OpenAt).ToArray():Array.Empty<V32Bar>();
    static int LastClosed(V32Bar[] bars,long t,long width)
    {
        int l=0,h=bars.Length;
        while(l<h){int mid=(l+h)/2;if(bars[mid].OpenAt+width<=t)l=mid+1;else h=mid;}
        return l-1;
    }
    static Reading? Read(V32Bar[] hE,V32Bar[] hG,
        IReadOnlyDictionary<long,V32Bar> mE,IReadOnlyDictionary<long,V32Bar> mG,
        long decisionTime)
    {
        if(!mE.TryGetValue(decisionTime-M15,out var e) ||
           !mG.TryGetValue(decisionTime-M15,out var g) ||
           !mE.TryGetValue(decisionTime-2*M15,out var prevE) ||
           !mG.TryGetValue(decisionTime-2*M15,out var prevG) ||
           !Valid(e)||!Valid(g)||!Valid(prevE)||!Valid(prevG))return null;
        // Do not mix the present decision M15 close into its H1 reference.
        int ie=LastClosed(hE,decisionTime-1,H1),ig=LastClosed(hG,decisionTime-1,H1);
        if(ie<47||ig<47)return null;
        var ratios=new double[48];long prev=-1;
        for(int j=0;j<48;j++)
        {
            var a=hE[ie-47+j];var b=hG[ig-47+j];
            if(!Valid(a)||!Valid(b)||a.OpenAt!=b.OpenAt||
                (prev>=0&&a.OpenAt-prev!=H1))return null;
            ratios[j]=Math.Log((double)(a.Close/b.Close));prev=a.OpenAt;
        }
        double mean=ratios.Average();
        double variance=ratios.Sum(x=>(x-mean)*(x-mean))/47d;
        if(!double.IsFinite(variance)||variance<=0)return null;
        double sigma=Math.Sqrt(variance);
        double ratio=Math.Log((double)(e.Close/g.Close));
        double z=(ratio-mean)/sigma;
        if(!double.IsFinite(z))return null;
        return new Reading(decisionTime,ratio,mean,sigma,z,e.Close,g.Close);
    }
    // Conditional original-account MINIMUM-size EUR cost model. Causal 
    // price comes from genuine M5 OPEN at that clock; never the future bar high/low.
    // No quote-depth/order acknowledgement invented.
    static LedgerQuote? Quote(V32Market market,V32Bar now,V32Bar eur,
        decimal factor,out decimal slip)
    {
        slip=0;
        var t=market.Terms;
        if(t is null||t.MinimumUnits is not >0m||t.StepUnits is not >0m||
           t.MaximumUnits is not >0m||t.LotUnits is not >0m||
           t.CommissionType is null||t.PreciseRateWire is null||
           t.MinimumCommissionType is null||t.PreciseMinimumWire is null||
           t.PnlConversionFeeBps is null||t.SpreadBps is not >0m||
           t.MarginMinimumEur is not >0m||t.ObservedAtUtcMs<=0||
           market.Symbol is not ("EURUSD" or "GBPUSD")||
           eur.Open<=0m||!Valid(now)||!Valid(eur))return null;
        var terms=new NativeObservedContractTerms(t.Symbol,t.QuoteAsset,t.ObservedAtUtcMs,
            t.MinimumUnits.Value,t.StepUnits.Value,t.MaximumUnits.Value,
            t.LotUnits.Value,t.CommissionType.Value,t.PreciseRateWire.Value,
            t.MinimumCommissionType.Value,t.PreciseMinimumWire.Value,
            t.MinimumCommissionAsset,t.PnlConversionFeeBps.Value,
            t.SwapCalculationType,t.LongSwap,t.ShortSwap,t.PipPosition,
            t.SwapPeriodHours,t.SwapTimeUtcMinute,t.TripleSwapWeekday,null,null,true,false);
        if(terms.QuoteAsset!="USD")return null;
        decimal spread=now.Open*t.SpreadBps.Value*factor/10000m;
        slip=spread/2m;decimal bid=now.Open-spread/2m,ask=now.Open+spread/2m;
        if(bid<=0||ask<bid)return null;
        decimal fx=1m/eur.Open,fxWedge=.00025m*factor;
        if(fxWedge>=1m)return null;
        try
        {
            decimal? minimumFeeFx=terms.MinimumCommissionAsset switch {
                null=>null,"USD"=>fx,"EUR"=>1m,_=>null};
            var attributed=NativeBrokerContractCosts.Quote(terms,
                new NativeMarketCostContext(now.OpenAt,bid,ask,fx*(1-fxWedge),
                    fx*(1+fxWedge),fx,minimumFeeFx,t.MarginMinimumEur.Value,
                    terms.MinimumUnits,slip));
            return attributed.Quote with {
                ExitFeePerUnit=attributed.Quote.ExitFeePerUnit*factor,
                ExitFeeFloor=attributed.Quote.ExitFeeFloor*factor,
                LiquidationSlippagePerSide=slip
            };
        }
        catch(ArgumentException){return null;}
        catch(InvalidOperationException){return null;}
    }
    static Leg MakeLeg(string id,V32Market market,LedgerQuote quote,
        int side,double sigma,double entryZ,decimal slip)
    {
        var units=market.Terms!.MinimumUnits!.Value;
        decimal displacement=Math.Max(0m,StopSigma-(decimal)Math.Abs(entryZ))*(decimal)sigma;
        decimal adverseMove=quote.Ask*displacement;
        decimal risk=(adverseMove+2m*(quote.Ask-quote.Bid+slip))*units*quote.EurDebit+
            2m*Fee(quote,units);
        decimal price=NativeExecutableEconomics.EntryPrice(quote,side,slip);
        decimal stop=side>0?price-adverseMove:price+adverseMove;
        return new Leg{Id=id,Symbol=market.Symbol,Side=side,Units=units,
            Margin=quote.MarginPerUnit,StopRisk=risk,Slip=slip,StopPrice=stop};
    }
    static decimal WorstPairRisk(Book book)=>book.Held.Values.Sum(x=>x.StopRisk)+
        book.Pending.Values.Sum(x=>x.StopRisk);
    static bool EligibleNewBook(Book book,LedgerQuote[] quotes)
    {
        var s=book.Ledger.Summary();
        return !book.Irreversible && s.LiquidationEquityEur is >0m &&
            !book.Held.Any()&&!book.Pending.Any() && book.Pair is null &&
            quotes.Length==2;
    }
    static void SubmitNew(Book book,Reading reading,
        V32Market eurMarket,V32Market gbpMarket,LedgerQuote[] quotes,
        decimal[] slips,long t)
    {
        int sign=reading.Signal;if(sign==0){book.Waits++;return;}
        if(Math.Abs(reading.Z)>=3d)
        {book.Reject("ALREADY_BEYOND_ENTRY_FROZEN_ADVERSE_BARRIER");return;}
        if(!EligibleNewBook(book,quotes)){book.Waits++;return;}
        var q=quotes.ToDictionary(x=>x.Symbol,x=>x,StringComparer.Ordinal);
        var ledgerSummary=book.Ledger.Summary();
        decimal equity=ledgerSummary.LiquidationEquityEur??0m;
        // A high residual has EUR rich relative GBP: sell EUR, buy GBP.
        var candidates=new List<Leg> {
            MakeLeg("RVC1/"+book.Policy+"/"+book.Factor+"/"+t+"/EUR",eurMarket,q["EURUSD"],
                -sign,reading.Sigma,reading.Z,slips[0])
        };
        if(book.Policy!="SINGLE_EURUSD")
            candidates.Add(MakeLeg("RVC1/"+book.Policy+"/"+book.Factor+"/"+t+"/GBP",
                gbpMarket,q["GBPUSD"],sign,reading.Sigma,reading.Z,slips[1]));
        decimal totalRisk=candidates.Sum(x=>x.StopRisk);
        if(totalRisk>equity*.03m){book.Reject("PAIR_COMBINED_STOP_RISK");return;}
        var reserve=new List<NativePendingCapitalGate.Commitment>();
        foreach(var c in candidates)
        {
            var proposal=new NativePendingCapitalGate.Proposal(c.Symbol,"COMMON_FX",
                c.Units,c.Symbol=="EURUSD"?eurMarket.Terms!.StepUnits!.Value:
                    gbpMarket.Terms!.StepUnits!.Value,c.Units,c.Margin,
                c.StopRisk/c.Units);
            var guard=NativePendingCapitalGate.Assess(equity,true,
                Array.Empty<NativePendingCapitalGate.Commitment>(),reserve,proposal);
            if(!guard.IsFinanceable){book.Reject("JOINT_PREFILL_"+guard.Status);
                book.MarginRejects++;return;}
            reserve.Add(new NativePendingCapitalGate.Commitment(
                c.Id,c.Symbol,c.Units,c.Margin,c.StopRisk,"COMMON_FX",true));
        }
        foreach(var c in candidates)
        {
            book.Ledger.Apply(book.Event(t+100+book.Pending.Count*100,"REQUEST_OPEN",
                c,quotes,slip:c.Slip,margin:c.Margin));
            book.Pending[c.Symbol]=c;
        }
        book.Pair=new PairState{FrozenMu=reading.Mu,FrozenSigma=reading.Sigma,
            EntryZ=reading.Z,SignaledAt=reading.At,RequestedAt=t};
        book.PairOffers++;
        book.UpdateExposure(quotes);
    }
    static void RequestClose(Book book,LedgerQuote[] quotes,long t,string reason)
    {
        foreach(var l in book.Held.Values)
        {
            if(l.RequestedClose)continue;
            book.Ledger.Apply(book.Event(t+50+book.CloseActions,"REQUEST_CLOSE",
                l,quotes,reason:"MODEL_UNTRANSMITTED_"+reason));
            l.RequestedClose=true;book.CloseActions++;
        }
    }
    static void ExpireOpen(Book book,LedgerQuote[] quotes,long t,string reason)
    {
        foreach(var leg in book.Pending.Values.ToArray())
        {
            book.Ledger.Apply(book.Event(t+500,"MODEL_OPEN_INTENT_EXPIRED",leg,
                Array.Empty<LedgerQuote>(),
                reason:"MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED"));
            book.Pending.Remove(leg.Symbol);
        }
        if(book.Held.Count==0)book.Pair=null;
        else{book.OrphanEvents++;book.Incomplete=true;
            if(book.Pair is not null)book.Pair.Orphaned=true;
            RequestClose(book,quotes,t+700,"RVC1_ORPHAN_PROTECTIVE_CLOSE");}
        book.Reject(reason);
    }
    static void TryFill(Book book,LedgerQuote[] quotes,long t)
    {
        if(book.Pair is null||book.Pending.Count==0||t<=book.Pair.RequestedAt+1000)
            return;
        if(t>book.Pair.RequestedAt+2*M5)
        {ExpireOpen(book,quotes,t,"PENDING_EXPIRED_ON_GENUINE_NEW_M5_CLOCK");return;}
        if(quotes.Length<2){book.TemporarySuspensions++;return;}
        var q=quotes.ToDictionary(x=>x.Symbol,x=>x,StringComparer.Ordinal);
        var current=book.Ledger.Summary().LiquidationEquityEur;
        if(current is null){book.UnknownMarks++;return;}
        foreach(var leg in book.Pending.Values.ToArray())
        {
            if(book.Irreversible){ExpireOpen(book,quotes,t,"IRREVERSIBLE_DD");return;}
            var held=book.Commitments(false,q);
            var pending=book.Commitments(true,q);
            var cost=q[leg.Symbol];
            var guard=NativePostFillCapitalGuard.Assess(current,held,pending,
                leg.Id,leg.Side,cost,leg.Slip,0m);
            if(!guard.Allowed){ExpireOpen(book,quotes,t,"POSTFILL_"+guard.Reason);return;}
            var priced=NativeExecutableEconomics.EntryPrice(cost,leg.Side,leg.Slip);
            book.Ledger.Apply(book.Event(t+500,"OPEN_FILL",leg,quotes,
                price:priced,fee:Fee(cost,leg.Units),
                margin:cost.MarginPerUnit,slip:leg.Slip));
            leg.EntryPrice=priced;leg.OpenedAt=t;leg.Margin=cost.MarginPerUnit;
            book.Pending.Remove(leg.Symbol);book.Held[leg.Symbol]=leg;
            current=book.Ledger.Summary().LiquidationEquityEur;
        }
        if(book.Held.Count==(book.Policy=="SINGLE_EURUSD"?1:2)&&book.Pending.Count==0)
            book.FinancedPairs++;
        book.UpdateExposure(quotes);
    }
    static bool FundingCost(Book book,V32Market market,Leg leg,LedgerQuote quote,
        long closeTime,out decimal amount)
    {
        amount=0m;
        if(leg.FundingBooked)return true;
        var t=market.Terms;
        if(t is null)return false;
        if(leg.OpenedAt/DAY==closeTime/DAY)return true;
        if(t.MinimumUnits is null||t.StepUnits is null||t.MaximumUnits is null||
           t.LotUnits is null||t.CommissionType is null||t.PreciseRateWire is null||
           t.MinimumCommissionType is null||t.PreciseMinimumWire is null||
           t.PnlConversionFeeBps is null)return false;
        var original=new NativeObservedContractTerms(t.Symbol,t.QuoteAsset,t.ObservedAtUtcMs,
            t.MinimumUnits.Value,t.StepUnits.Value,t.MaximumUnits.Value,
            t.LotUnits.Value,t.CommissionType.Value,t.PreciseRateWire.Value,
            t.MinimumCommissionType.Value,t.PreciseMinimumWire.Value,
            t.MinimumCommissionAsset,t.PnlConversionFeeBps.Value,t.SwapCalculationType,
            t.LongSwap,t.ShortSwap,t.PipPosition,t.SwapPeriodHours,
            t.SwapTimeUtcMinute,t.TripleSwapWeekday,null,null,true,false);
        decimal? result=NativeBrokerContractCosts.SignedFinancing(original,
            leg.OpenedAt,closeTime,leg.Side,leg.Units,quote.EurCredit,quote.EurDebit);
        if(result is null)return false;
        amount=result.Value;
        return true;
    }
    static void SettleClose(Book book,LedgerQuote[] quotes,V32Market e,V32Market g,
        long t)
    {
        if(book.Held.Count==0)return;
        if(quotes.Length<2){book.TemporarySuspensions++;return;}
        var q=quotes.ToDictionary(x=>x.Symbol,x=>x,StringComparer.Ordinal);
        // Never partially settle a supposedly hedged pair when another leg
        // has unknown financing; retain both actual Held capital and risk.
        foreach(var l in book.Held.Values.Where(x=>x.RequestedClose))
            if(!FundingCost(book,l.Symbol=="EURUSD"?e:g,l,q[l.Symbol],t,out _))
            {book.Incomplete=true;book.UnknownFunding=true;
                book.Reject("ROLLOVER_CONTRACT_UNKNOWN");return;}
        foreach(var leg in book.Held.Values.ToArray())
        {
            if(!leg.RequestedClose)continue;
            var quote=q[leg.Symbol];
            if(!FundingCost(book,leg.Symbol=="EURUSD"?e:g,leg,quote,t,out var financing))
                throw new InvalidOperationException("RVC1_FINANCING_PREFLIGHT_DIVERGED");
            if(!leg.FundingBooked)
            {
                if(financing!=0m)
                    book.Ledger.Apply(book.Event(t+200,"FINANCING",leg,quotes,financing:financing,
                        reason:"CONDITIONAL_BROKER_COST_ORIGINAL_TERMS"));
                leg.FundingBooked=true;
            }
            decimal exit=NativeExecutableEconomics.ExitPrice(
                leg.Side>0?quote.Bid:quote.Ask,leg.Side,leg.Slip);
            book.Ledger.Apply(book.Event(t+800,"CLOSE_FILL",leg,quotes,
                price:exit,fee:Fee(quote,leg.Units),
                margin:quote.MarginPerUnit,reason:"RVC1_JOINT_RISK_OR_RESIDUAL"));
            book.Held.Remove(leg.Symbol);
            book.CompleteLegs++;
        }
        // A matched pair contributes a single completion only after
        // every leg is closed and no pending id remains.
        if(book.Held.Count==0&&book.Pending.Count==0&&book.Pair is not null)
        {
            if(!book.Pair.Orphaned)
            {
                book.CompletePairs++;
                var fragments=book.Ledger.ClosedFragments();
                // Per-cycle grouping key is frozen entry event, not summing
                // unrelated portfolios.
                var cycle=fragments.Where(x=>x.PositionId.Contains(
                    "/"+book.Pair.RequestedAt+"/",StringComparison.Ordinal)).ToArray();
                var w=Week(t);
                book.CompleteWeeks[w]=book.CompleteWeeks.GetValueOrDefault(w)+1;
                book.NetWeeks[w]=book.NetWeeks.GetValueOrDefault(w)+cycle.Sum(x=>x.NetEur);
            }
            book.Pair=null;
        }
        book.UpdateExposure(quotes);
    }
    static bool ExitNeeded(Book book,Reading? latest,LedgerQuote[] quotes)
    {
        if(book.Pair is null||book.Held.Count==0)return false;
        if(book.Irreversible)return true;
        if(latest is not null && latest.At>book.Pair.SignaledAt)
        {
            double r=latest.Ratio,m=book.Pair.FrozenMu,
                sigma=book.Pair.FrozenSigma;
            int original=book.Pair.EntryZ>0?1:-1;
            bool target=original>0?r<=m:r>=m;
            bool beyond=original>0?r>=m+3*(double)sigma:
                r<=m-3*(double)sigma;
            bool regime=original>0?latest.Mu>m+1.5*(double)sigma:
                latest.Mu<m-1.5*(double)sigma;
            if(beyond||regime||target&&book.Policy!="PAIRED_NO_CONVERGENCE")
                return true;
        }
        foreach(var leg in book.Held.Values)
        {
            var q=quotes.FirstOrDefault(x=>x.Symbol==leg.Symbol);
            if(q is null)return false; // missing mark never fabricates CLOSE
            var sidePrice=leg.Side>0?q.Bid:q.Ask;
            if(leg.Side>0?sidePrice<=leg.StopPrice:sidePrice>=leg.StopPrice)
                return true;
        }
        return false;
    }
    static void Advance(Book book,long t,LedgerQuote[] quotes,Reading? reading,
        V32Market e,V32Market g)
    {
        if(book.Policy=="CASH")return;
        book.Ledger.Apply(book.Event(t+10,"MARK",null,quotes));
        book.UpdateExposure(quotes);
        if(quotes.Length<2)
        {
            book.TemporarySuspensions++;
            if(book.Pair is not null){book.Incomplete=true;book.UnknownMarks++;}
            return;
        }
        var summary=book.Ledger.Summary();
        if(summary.MaximumSampledDrawdown>=IrreversibleDd&&!book.Irreversible)
        {book.Irreversible=true;book.HardStops++;}
        if(summary.LiquidationEquityEur is null)
        {book.UnknownMarks++;book.Incomplete=true;book.TemporarySuspensions++;return;}
        // An original pending request is never allowed to fill after an
        // unobserved long gap. The model only expires on a genuinely later
        // source clock, preserving the original censored funding history.
        if(book.Pending.Count>0 && book.Pair is not null &&
            t>book.Pair.RequestedAt+2*M5)
            ExpireOpen(book,quotes,t+20,"PENDING_POSTGAP_EXPIRED");
        // Prior CLOSE request must reach a LATER authentic M5 open.
        if(book.Held.Values.Any(x=>x.RequestedClose))
        {
            SettleClose(book,quotes,e,g,t+50);
            if(book.Held.Values.Any(x=>x.RequestedClose))return;
        }
        if(book.Pending.Count>0)
            TryFill(book,quotes,t+30);
        if(book.Pair is not null&&ExitNeeded(book,reading,quotes))
            RequestClose(book,quotes,t+120,
                book.Irreversible?"RVC1_IRREVERSIBLE_RISK":"RVC1_RESIDUAL_OR_PROTECTION");
        if(book.Pair is not null)
        {
            book.Holds++;
            // A one-minimum-unit leg cannot be reduced while preserving
            // original-account legal minimum volume. Never invent a partial.
            if(book.Held.Count>0)book.ReductionsUnavailable++;
            return;
        }
        if(book.Irreversible)return;
        if(reading is null||reading.At!=t||quotes.Length!=2)
        {book.Waits++;return;}
        book.Decisions++;
        book.SourceWeeks[Week(t)]=book.SourceWeeks.GetValueOrDefault(Week(t))+1;
        var qe=quotes.First(x=>x.Symbol=="EURUSD");
        var qg=quotes.First(x=>x.Symbol=="GBPUSD");
        decimal slipE=(qe.Ask-qe.Bid)/2m,slipG=(qg.Ask-qg.Bid)/2m;
        SubmitNew(book,reading,e,g,quotes,new[]{slipE,slipG},t+150);
    }
    public static object Evaluate(V32Tape tape,string frozenProtocolSha256)
    {
        if(tape is null||!tape.DevelopmentOnly||
           frozenProtocolSha256.Length!=64||
           tape.Markets.Count(x=>x.Symbol=="EURUSD")!=1||
           tape.Markets.Count(x=>x.Symbol=="GBPUSD")!=1)
            throw new ArgumentException("RVC1_AUTHENTIC_SOURCE_AND_FROZEN_SCOPE_REQUIRED");
        var e=tape.Markets.Single(x=>x.Symbol=="EURUSD");
        var g=tape.Markets.Single(x=>x.Symbol=="GBPUSD");
        var e5=Bars(e,"M5").ToDictionary(x=>x.OpenAt);
        var g5=Bars(g,"M5").ToDictionary(x=>x.OpenAt);
        var me=Bars(e,"M15").ToDictionary(x=>x.OpenAt);
        var mg=Bars(g,"M15").ToDictionary(x=>x.OpenAt);
        var he=Bars(e,"H1");var hg=Bars(g,"H1");
        if(e5.Count==0||g5.Count==0||me.Count==0||mg.Count==0||he.Length==0||hg.Length==0)
            throw new ArgumentException("RVC1_GENUINE_M5_M15_H1_COVERAGE_MISSING");
        var dates=e5.Keys.Union(g5.Keys).OrderBy(x=>x).ToArray();
        if(dates.Length==0)throw new ArgumentException("RVC1_SOURCE_WITHOUT_COMMON_CLOCK");
        var weeks=new List<string>();
        DateTime first=DateTimeOffset.FromUnixTimeMilliseconds(dates[0]).UtcDateTime.Date;
        DateTime last=DateTimeOffset.FromUnixTimeMilliseconds(dates[^1]).UtcDateTime.Date;
        first=first.AddDays(-((7+(int)first.DayOfWeek-1)%7));
        for(var day=first;day<=last;day=day.AddDays(7))
            weeks.Add(Week(new DateTimeOffset(day,TimeSpan.Zero).ToUnixTimeMilliseconds()));
        var books=(from factor in Factors from policy in Policies
            select new Book(policy,factor)).ToArray();
        foreach(var t in dates)
        {
            bool hasE=e5.TryGetValue(t,out var a);
            bool hasG=g5.TryGetValue(t,out var b);
            bool good=hasE&&hasG&&a is not null&&b is not null&&Valid(a)&&Valid(b);
            Reading? reading=good&&t%M15==0 ? Read(he,hg,me,mg,t):null;
            foreach(var book in books)
            {
                if(book.Policy=="CASH")continue;
                LedgerQuote[] marks=Array.Empty<LedgerQuote>();
                if(good)
                {
                    var x=Quote(e,a!,a!,book.Factor,out _);
                    var y=Quote(g,b!,a!,book.Factor,out _);
                    if(x is not null&&y is not null)
                        marks=new[]{x,y};
                }
                Advance(book,t,marks,reading,e,g);
            }
        }
        return new {
            Version,FrozenProtocolSha256=frozenProtocolSha256,
            OriginalSources=tape.SourceRuns,
            SourceDisclosure="PREVIOUSLY_EXPOSED_AUTHENTIC_BARS_CONDITIONAL_COSTS",
            EarliestCommonM5=dates[0],LatestCommonM5=dates[^1],
            CommonM5Clocks=dates.Length,CommonISOWeeks=weeks.Count,
            Books=books.Select(x=>x.Receipt(weeks.ToArray())).ToArray(),
            CashBenchmarkEur=0,ActualBrokerFillsCertified=false,
            HistoricalAllInCostsCertified=false,IntrabarDDCertified=false,
            SystemicHARD21Certified=false,IndependentConfirmation=false,
            BrokerOrders=0,CloudActivated=false,ClosedStudyReruns=0
        };
    }
}
