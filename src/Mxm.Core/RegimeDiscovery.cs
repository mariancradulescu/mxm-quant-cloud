using System.Text.Json;
namespace Mxm.Core;

// Development research only. No closed model calls, execution APIs, or risk sizing.
public static class RegimeDiscovery
{
    public record Bar(string Symbol,string Tf,long T,long End,double O,double H,double L,double C,double V);
    public record Point(long Entry,long Exit,double[] X,double Y,int Regime);
    public static readonly string[] Families={"INTERCEPT_BASELINE","TREND_RIDGE","CANDLE_REVERSION_RIDGE","VOLATILITY_INTERACTION_RIDGE","INTERMARKET_RIDGE","POOLED_RIDGE","REGIME_SPECIALIST_RIDGE","FIXED_EQUAL_ENSEMBLE"};
    static readonly int[][] Columns={new[]{0},new[]{0,1,2,3},new[]{0,1,4,5},new[]{0,1,6,7,8},new[]{0,9,10,11},Enumerable.Range(0,14).ToArray(),Enumerable.Range(0,14).ToArray()};
    public static Bar[] Read(JsonElement root)
    {
        _=EconomicSourceAdmission.ReadReceipt(root);
        return root.GetProperty("bars").EnumerateArray().Select(b=>new Bar(
            b.GetProperty("symbol").GetString()!,b.GetProperty("resolution").GetString()!,
            b.GetProperty("openTime").GetInt64(),b.GetProperty("availableTime").GetInt64(),
            b.GetProperty("open").GetDouble(),b.GetProperty("high").GetDouble(),b.GetProperty("low").GetDouble(),
            b.GetProperty("close").GetDouble(),b.GetProperty("tickVolume").GetDouble())).ToArray();
    }
    public static Bar[] Aggregate(IEnumerable<Bar> source,string tf,long duration)
    {
        return source.GroupBy(b=>(b.Symbol,bucket:b.T/duration)).Select(g=>{
            var a=g.OrderBy(b=>b.T).ToArray();long start=g.Key.bucket*duration;
            return a[0].T==start && a[^1].End==start+duration &&
                Enumerable.Range(1,a.Length-1).All(i=>a[i].T==a[i-1].End) ?
                new Bar(g.Key.Symbol,tf,start,start+duration,a[0].O,a.Max(b=>b.H),a.Min(b=>b.L),a[^1].C,a.Sum(b=>b.V)):null;
        }).Where(x=>x!=null).Select(x=>x!).ToArray();
    }
    public static Point[] Features(Bar[] input, Dictionary<string,Bar[]> peers,int horizon)
    {
        var a=input.OrderBy(b=>b.T).ToArray();var result=new List<Point>();
        var peerMaps=peers.Where(k=>k.Key!=a[0].Symbol).Select(k=>k.Value.OrderBy(b=>b.End).ToArray()).ToArray();
        for(int i=32;i+horizon<a.Length;i++)
        {
            // Reject missing intervals, including discontinuous target windows.
            if(!Enumerable.Range(i-31,32+horizon).All(j=>a[j].T==a[j-1].End))continue;
            double R(int n)=>(a[i].C/a[i-n].C-1)*10000;
            var returns=Enumerable.Range(i-31,32).Select(j=>(a[j].C/a[j-1].C-1)*10000).ToArray();
            double vol=Math.Sqrt(returns.Select(r=>r*r).Average())+1e-9;
            double shortVol=Math.Sqrt(returns.Skip(24).Select(r=>r*r).Average());
            double efficiency=Math.Abs(a[i].C-a[i-16].C)/(Enumerable.Range(i-15,16).Sum(j=>Math.Abs(a[j].C-a[j-1].C))+1e-9);
            double imbalance=(a[i].C-a[i].O)/(a[i].H-a[i].L+1e-9);
            double closeLocation=(2*a[i].C-a[i].H-a[i].L)/(a[i].H-a[i].L+1e-9);
            var cross=new List<double>();
            foreach(var p in peerMaps)
            {
                // Binary search uses only bars completed by the prediction clock.
                int l=0,r=p.Length;
                while(l<r){int m=(l+r)/2;if(p[m].End<=a[i].End)l=m+1;else r=m;}
                int j=l-1;
                if(j>=4 && p[j].End==a[i].End && Enumerable.Range(j-3,4).All(k=>p[k].T==p[k-1].End))
                    cross.Add((p[j].C/p[j-4].C-1)*10000);
            }
            double peer=cross.Count==0?0:cross.Average()/vol;
            var dt=DateTimeOffset.FromUnixTimeMilliseconds(a[i].End).UtcDateTime;
            double[] x={1,R(1)/vol,R(4)/vol,R(16)/vol,imbalance,closeLocation,
                shortVol/vol,efficiency,R(1)/vol*(shortVol/vol-1),peer,peer*R(4)/vol,cross.Count,
                Math.Sin(2*Math.PI*dt.Hour/24),Math.Cos(2*Math.PI*dt.Hour/24)};
            // Regimes use causal dimensionless features, with thresholds frozen as
            // experimental descriptors, never universal trading/risk constraints.
            int regime=(efficiency>.35?1:0)+(shortVol>vol?2:0);
            result.Add(new(a[i+1].T,a[i+horizon].End,x,(a[i+horizon].C/a[i+1].O-1)*10000,regime));
        }
        return result.ToArray();
    }
    // Train-only scaling and regularised normal equations; no package/runtime outside C#.
    public record Fit(int[] Columns,double[] Mean,double[] Scale,double[] Beta)
    {
        public double Predict(Point p)=>Columns.Select((c,j)=>Beta[j]*(c==0?1:(p.X[c]-Mean[j])/Scale[j])).Sum();
    }
    public static Fit Train(Point[] train,int[] cols)
    {
        int d=cols.Length;var mean=new double[d];var scale=new double[d];
        for(int j=0;j<d;j++) {mean[j]=cols[j]==0?0:train.Average(p=>p.X[cols[j]]);scale[j]=cols[j]==0?1:Math.Sqrt(train.Average(p=>Math.Pow(p.X[cols[j]]-mean[j],2)))+1e-9;}
        var m=new double[d,d+1];
        foreach(var p in train)
        {
            var x=cols.Select((c,j)=>c==0?1:(p.X[c]-mean[j])/scale[j]).ToArray();
            for(int j=0;j<d;j++){m[j,d]+=x[j]*p.Y;for(int k=0;k<d;k++)m[j,k]+=x[j]*x[k];}
        }
        for(int j=0;j<d;j++)m[j,j]+=j==0?1e-8:train.Length*.10; // fixed shrinkage, no tuned lambda
        for(int j=0;j<d;j++)
        {
            int pivot=j;for(int k=j+1;k<d;k++)if(Math.Abs(m[k,j])>Math.Abs(m[pivot,j]))pivot=k;
            for(int k=j;k<=d;k++)(m[j,k],m[pivot,k])=(m[pivot,k],m[j,k]);
            double q=m[j,j];if(Math.Abs(q)<1e-12)throw new ArgumentException("SINGULAR_RESEARCH_FIT");
            for(int k=j;k<=d;k++)m[j,k]/=q;
            for(int k=0;k<d;k++)if(k!=j){double v=m[k,j];for(int z=j;z<=d;z++)m[k,z]-=v*m[j,z];}
        }
        return new(cols,mean,scale,Enumerable.Range(0,d).Select(j=>m[j,d]).ToArray());
    }
    public record Outcome(long Entry,long Exit,int Fold,int Regime,int Direction,double Gross,double Forecast);
    public static Outcome[][] Walk(Point[] points)
    {
        var rows=Families.Select(_=>new List<Outcome>()).ToArray();
        if(points.Length<100)return rows.Select(x=>x.ToArray()).ToArray();
        for(int fold=0;fold<3;fold++)
        {
            int lo=(int)(points.Length*(.5+.1*fold)),hi=(int)(points.Length*(.6+.1*fold));
            long clock=points[lo].Entry;
            var train=points.Take(lo).Where(p=>p.Exit<clock).ToArray(); // purge boundary labels, strict embargo
            if(train.Length<80)continue;
            var fits=Columns.Select(c=>Train(train,c)).ToArray();
            var specialist=Enumerable.Range(0,4).ToDictionary(k=>k,k=>{
                var sub=train.Where(p=>p.Regime==k).ToArray();return sub.Length>=80?Train(sub,Columns[6]):fits[5];});
            var next=Families.Select(_=>0L).ToArray();
            foreach(var p in points.Skip(lo).Take(hi-lo).Where(p=>p.Exit<points[hi].Entry))
            {
                var f=fits.Select(x=>x.Predict(p)).ToList();f[6]=specialist[p.Regime].Predict(p);f.Add((f[5]+f[6])/2);
                for(int k=0;k<f.Count;k++)
                {
                    if(p.Entry<next[k])continue;
                    int sign=Math.Sign(f[k]);if(sign==0)continue;
                    rows[k].Add(new(p.Entry,p.Exit,fold,p.Regime,sign,sign*p.Y,f[k]));next[k]=p.Exit;
                }
            }
        }
        return rows.Select(x=>x.ToArray()).ToArray();
    }
    static string Week(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;return $"{System.Globalization.ISOWeek.GetYear(d)}-{System.Globalization.ISOWeek.GetWeekOfYear(d):00}";}
    public static object Metrics(Outcome[] rows,double z,double cost)
    {
        var weeks=rows.GroupBy(x=>Week(x.Exit)).OrderBy(x=>x.Key,StringComparer.Ordinal).Select(g=>g.Sum(x=>x.Gross-cost)).ToArray();
        double mean=weeks.Length==0?0:weeks.Average(),se=0;
        if(weeks.Length>1)
        {
            var x=weeks.Select(v=>v-mean).ToArray();double variance=x.Sum(v=>v*v)/weeks.Length;
            double hac=variance;
            for(int lag=1;lag<=Math.Min(2,weeks.Length-1);lag++)hac+=2*(1-lag/3.0)*Enumerable.Range(lag,weeks.Length-lag).Sum(i=>x[i]*x[i-lag])/weeks.Length;
            se=Math.Sqrt(Math.Max(variance,hac)/weeks.Length);
        }
        return new {episodes=rows.Length,observedExitWeeks=weeks.Length,meanGrossBps=rows.Length>0?(double?)rows.Average(x=>x.Gross):null,
            hypotheticalRoundTripCostBps=cost,sumCostAdjustedBps=rows.Sum(x=>x.Gross-cost),
            weeklyApproxMultiplicityLowerBps=weeks.Length>=8?(double?)(mean-z*se):null,
            foldGrossBps=Enumerable.Range(0,3).Select(k=>rows.Where(x=>x.Fold==k).Sum(x=>x.Gross)).ToArray(),
            regimeCounts=Enumerable.Range(0,4).Select(k=>rows.Count(x=>x.Regime==k)).ToArray(),
            regimeMeanGrossBps=Enumerable.Range(0,4).Select(k=>rows.Any(x=>x.Regime==k)?(double?)rows.Where(x=>x.Regime==k).Average(x=>x.Gross):null).ToArray(),
            approximateExploratorySupportOnly=weeks.Length>=8 && rows.Length>=30 && mean-z*se>0,
            positiveFolds=Enumerable.Range(0,3).Count(k=>rows.Any(x=>x.Fold==k)&&rows.Where(x=>x.Fold==k).Sum(x=>x.Gross-cost)>0)};
    }
    public static object Assess(JsonElement root)
    {
        var original=Read(root);
        var all=original.Concat(Aggregate(original.Where(b=>b.Tf=="M15"),"H1",3600000))
            .Concat(Aggregate(original.Where(b=>b.Tf=="H4"),"D1",86400000)).ToArray();
        var groups=all.GroupBy(x=>(x.Symbol,x.Tf)).OrderBy(g=>g.Key.Symbol).ThenBy(g=>g.Key.Tf).ToArray();
        int trials=groups.Length*3*Families.Length;double z=Math.Sqrt(2*Math.Log(2*trials/.05));
        var results=new List<object>();
        foreach(var g in groups)
        {
            var a=g.OrderBy(b=>b.T).ToArray();
            var peers=all.Where(b=>b.Tf==g.Key.Tf).GroupBy(b=>b.Symbol).ToDictionary(p=>p.Key,p=>p.ToArray());
            foreach(int h in new[]{1,4,16})
            {
                var points=Features(a,peers,h);var walk=Walk(points);
                for(int k=0;k<Families.Length;k++)results.Add(new{symbol=g.Key.Symbol,timeframe=g.Key.Tf,horizonBars=h,
                    family=Families[k],sourceBars=a.Length,featureLabels=points.Length,
                    status=points.Length<100?"INSUFFICIENT_CAUSAL_SOURCE":"EXPLORATORY_WALK_FORWARD_NOT_CONFIRMATION",
                    scenarios=new[]{0.0,1.0,3.0,10.0}.Select(cost=>Metrics(walk[k],z,cost)).ToArray()});
            }
        }
        return new {schema="mxm-wide-regime-discovery-v1",sourceRunId=41476636915L,trialCount=trials,
            familyNames=Families,results,multiplicityApproxZ=z,
            phases="EXPANDING_0_50_TRAIN__50_60_60_70_70_80_WALK__LAST20_NO_PERFORMANCE",
            historicalExposure="PREVIOUSLY_EXPOSED_DEVELOPMENT_DATA_NOT_UNTOUCHED_CONFIRMATION",
            costStatus="0_1_3_10_BPS_HYPOTHETICAL_ROUNDTRIP_SENSITIVITY_NOT_BROKER_NET",
            brokerNetEur=(decimal?)null,funded200EurProven=false,hard21Proven=false,
            independentConfirmation=false,ordersSubmitted=0};
    }
}
