using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeRecoveryForecast(long DecisionAt,long LatestLabelAt,int CalendarSide,int RunSide,
    int CalendarDays,int RunDays);

// Price-information forecasts only. All economic admissions, fills and exits
// continue through the common funded ledger. Original recipes remain intact.
public sealed class NativeRecoveryHistory
{
    const long Hour=3_600_000L,Day=86_400_000L;
    sealed record Label(long Mature,int Weekday,int Slot,int Side,int Run,decimal Move);
    readonly Label[] labels;int consumed;
    sealed class Bucket
    {
        readonly Dictionary<long,(decimal Sum,int Count)> days=new();
        bool dirty=true; (int Side,int Days) cached;
        public void Add(long at,decimal value)
        {long day=at/Day;var previous=days.GetValueOrDefault(day);days[day]=(previous.Sum+value,previous.Count+1);dirty=true;}
        public (int Side,int Days) Estimate(int minimum)
        {
            if(!dirty)return cached;
            dirty=false;
            if(days.Count<minimum)return cached=(0,days.Count);
            var values=days.Values.Select(x=>x.Sum/x.Count).ToArray();
            decimal mean=values.Sum()/(values.Length+12m);
            decimal sem=(decimal)Math.Sqrt((double)(values.Sum(x=>(x-mean)*(x-mean))/(values.Length*(values.Length-1m))));
            return cached=(Math.Abs(mean)>sem?Math.Sign(mean):0,values.Length);
        }
    }
    readonly Dictionary<(int,int),Bucket> calendar=new();
    readonly Dictionary<(int,int),Bucket> states=new();
    long last=-1,latest;
    public NativeRecoveryHistory(NativeClosedMarketBar[] bars)
    {
        if(bars.Zip(bars.Skip(1)).Any(x=>x.First.CloseAt>x.Second.OpenAt))
            throw new ArgumentException("RECOVERY_HISTORY_OVERLAP");
        var rows=new List<Label>();int run=0,side=0;
        for(int i=1;i+1<bars.Length;i++)
        {
            if(bars[i-1].CloseAt!=bars[i].OpenAt||bars[i].CloseAt!=bars[i+1].OpenAt||
                bars[i].CloseAt-bars[i].OpenAt!=Hour||bars[i+1].CloseAt-bars[i+1].OpenAt!=Hour||bars[i].Close<=0m)
            {run=0;side=0;continue;}
            int s=Math.Sign(bars[i].Close-bars[i-1].Close);run=s!=0&&s==side?run+1:1;side=s;
            long at=bars[i].CloseAt;
            int weekday=(int)DateTimeOffset.FromUnixTimeMilliseconds(at).DayOfWeek;
            rows.Add(new(bars[i+1].CloseAt,weekday,(int)(at%Day/(4*Hour)),s,Math.Min(run,4),
                (bars[i+1].Close-bars[i].Close)/bars[i].Close));
        }
        labels=rows.OrderBy(x=>x.Mature).ToArray();
    }
    static void Add(Dictionary<(int,int),Bucket> map,(int,int) key,Label l)
    {if(!map.TryGetValue(key,out var rows))map.Add(key,rows=new());rows.Add(l.Mature,l.Move);}
    public NativeRecoveryForecast At(long at,NativeClosedMarketBar[] current)
    {
        if(at<last)throw new ArgumentException("RECOVERY_HISTORY_CLOCK_REVERSED");last=at;
        while(consumed<labels.Length&&labels[consumed].Mature<at)
        {
            var l=labels[consumed++];latest=l.Mature;
            Add(calendar,(l.Weekday,l.Slot),l);if(l.Side!=0)Add(states,(l.Side,l.Run),l);
        }
        int weekday=(int)DateTimeOffset.FromUnixTimeMilliseconds(at).DayOfWeek;
        (int Side,int Days) c=calendar.GetValueOrDefault((weekday,(int)(at%Day/(4*Hour))))?.Estimate(8)??(0,0);
        int side=0,run=0;
        for(int i=current.Length-1;i>=1;i--)
        {
            if(current[i-1].CloseAt!=current[i].OpenAt)break;
            int s=Math.Sign(current[i].Close-current[i-1].Close);
            if(s==0||run>0&&s!=side)break;
            side=s;if(++run==4)break;
        }
        (int Side,int Days) r=states.GetValueOrDefault((side,run))?.Estimate(5)??(0,0);
        // Source is hourly; stale states cannot be repaired by a price forecast.
        bool fresh=current.Length>1&&current.All(x=>x.CloseAt<at)&&at-current[^1].CloseAt<Hour;
        return new(at,latest,fresh&&(at-15_000L)%(4*Hour)==0?c.Side:0,fresh?r.Side:0,c.Days,r.Days);
    }
}

internal static class NativeRecoveredEconomicMechanisms
{
    internal static readonly string[] Families={"RECOVERED_HRC4","RECOVERED_HRC8","RECOVERED_HRC21",
        "RECOVERED_SQP_RUN","RECOVERED_TWC_CALENDAR","RECOVERED_RCP_COMPRESSION",
        "RECOVERED_RCP_DISPERSION","RECOVERED_RCP_TAIL","RECOVERED_VIA_ABSORPTION"};
    internal static int SerialCorrelationSide(NativeClosedMarketBar[] bars,int n)
    {
        if(bars.Length<n+2)return 0;
        var b=bars.TakeLast(n+2).ToArray();var r=new decimal[n+1];
        for(int j=0;j<=n;j++)
        {if(b[j].CloseAt!=b[j+1].OpenAt)return 0;r[j]=b[j+1].Close-b[j].Close;}
        decimal x=r.Take(n).Average(),y=r.Skip(1).Average(),xy=0m,xx=0m,yy=0m;
        for(int j=0;j<n;j++){decimal a=r[j]-x,c=r[j+1]-y;xy+=a*c;xx+=a*a;yy+=c*c;}
        if(xx==0m||yy==0m)return 0;
        double correlation=(double)xy/(Math.Sqrt((double)xx)*Math.Sqrt((double)yy));
        return Math.Abs(correlation)<.2?0:Math.Sign(correlation)*Math.Sign(r[^1]);
    }
    internal static NativeIntegratedCandidate[] Describe(Ucp1MarketFrame m,Ucp1Frame? frame,long at,
        NativeEurDevelopmentProfile profile)
    {
        NativeClosedMarketBar[] Bars(NativeBarTimeframe tf)=>m.EconomicTransitionWindows?
            .FirstOrDefault(x=>x.Timeframe==tf&&x.Ready&&x.WitnessAt==at)?.Bars??Array.Empty<NativeClosedMarketBar>();
        var b=Bars(NativeBarTimeframe.M15);var fast=Bars(NativeBarTimeframe.M5);
        if(b.Length<24||fast.Length<19||m.EurTickSize is not >0m||
            b.Any(x=>x.CloseAt>=at)||fast.Any(x=>x.CloseAt>=at))return Array.Empty<NativeIntegratedCandidate>();
        decimal tick=m.EurTickSize.Value;
        decimal atr=b.TakeLast(9).Skip(1).Select((x,i)=>Math.Max(x.High-x.Low,
            Math.Max(Math.Abs(x.High-b[b.Length-9+i].Close),Math.Abs(x.Low-b[b.Length-9+i].Close)))).Average();
        if(atr<=0m)return Array.Empty<NativeIntegratedCandidate>();
        var offers=new List<NativeIntegratedCandidate>();
        bool Adjacent(NativeClosedMarketBar[] rows,int n)=>rows.TakeLast(n).Zip(rows.TakeLast(n).Skip(1))
            .All(x=>x.First.CloseAt==x.Second.OpenAt);
        void Offer(string family,int side,decimal? destination=null)
        {
            if(side==0)return;
            decimal entry=side>0?m.Quote.Ask:m.Quote.Bid,exit=side>0?m.Quote.Bid:m.Quote.Ask;
            decimal Round(decimal p,bool up)=>(up?Math.Ceiling(p/tick):Math.Floor(p/tick))*tick;
            var structure=b.TakeLast(profile.EconomicStructureLookbackBars).ToArray();
            decimal boundary=side>0?Math.Min(structure.Min(x=>x.Low),fast[^1].Low):Math.Max(structure.Max(x=>x.High),fast[^1].High);
            decimal stop=Round(boundary-side*Math.Max(tick,fast[^1].High-fast[^1].Low),side<0);
            decimal target=Round(destination??b[^1].Close+side*profile.DistributionTargetRanges*atr,side>0);
            if(stop>0m&&target>0m&&side*(exit-stop)>0m&&side*(target-entry)>0m&&
                NativeIntegratedLifecycle.ProtectionCompatible(side,stop,target,m))
                offers.Add(new(family,side,stop,target,atr,fast[^1].CloseAt));
        }
        for(int j=0;j<3;j++)
        {
            int n=new[]{4,8,21}[j];if(!Adjacent(b,n+1))continue;
            Offer(Families[j],SerialCorrelationSide(b,n));
        }
        if(m.RecoveryForecast is { } forecast&&forecast.DecisionAt==at&&forecast.LatestLabelAt<at)
        {Offer(Families[3],forecast.RunSide);Offer(Families[4],forecast.CalendarSide);}
        if(Adjacent(b,9))
        {
            var prior=b.TakeLast(9).Take(8).ToArray();decimal upper=prior.Max(x=>x.High),lower=prior.Min(x=>x.Low);
            if(upper-lower<=prior.Sum(x=>x.High-x.Low)*.65m)
                Offer(Families[5],b[^1].Close>upper?1:b[^1].Close<lower?-1:0);
            var tail=b[^2];decimal body=Math.Abs(tail.Close-tail.Open),wick=tail.High-tail.Low-body;
            int shock=Math.Sign(tail.Close-tail.Open),turn=Math.Sign(b[^1].Close-b[^2].Close);
            if(wick>body&&turn==-shock)Offer(Families[7],turn,(tail.High+tail.Low)/2m);
        }
        // Original RCP's measured contribution was primarily relative dispersion,
        // not its compression ablation. Retain an explicit distinct repair offer.
        var h=NativeEconomicMechanisms.Window(m,NativeBarTimeframe.H1,at);
        if(h is not null&&frame is not null&&m.OfficialAssetClass is not null)
        {
            var peers=frame.Markets.Where(p=>p.Symbol!=m.Symbol&&p.OfficialAssetClass==m.OfficialAssetClass)
                .Select(p=>NativeEconomicMechanisms.Window(p,NativeBarTimeframe.H1,at)).OfType<NativeBarWindow>()
                .Where(w=>w.ExpectedCloseAt==h.ExpectedCloseAt&&w.Bars[0].OpenAt==h.Bars[0].OpenAt).ToArray();
            if(peers.Length>=2)
            {
                decimal Move(NativeBarWindow w)=>(w.Bars[^1].Close-w.Bars[0].Open)/w.Bars[0].Open;
                decimal target=h.Bars[0].Open*(1m+peers.Average(Move));
                Offer(Families[6],Math.Sign(target-h.Bars[^1].Close),target);
            }
        }
        if(Adjacent(fast,19))
        {
            var q=fast.TakeLast(19).ToArray();var moves=Enumerable.Range(0,6)
                .Select(i=>q[3*i+3].Close-q[3*i].Close).ToArray();
            int side=-Math.Sign(moves[^1]);
            if(side!=0&&Math.Abs(moves[^1])>moves.Take(5).Max(Math.Abs)&&
                side*Math.Sign(q[^1].Close-q[^2].Close)>0)
                Offer(Families[8],side,q[15].Close);
        }
        return offers.ToArray();
    }
}
