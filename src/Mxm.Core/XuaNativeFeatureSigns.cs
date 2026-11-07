using System;
using System.Linq;
namespace Mxm.Core;

// Pure, deterministic, native C# Cloud-compatible candidate features.
// Read-only H1 observations: no order APIs, network, Python or durable storage.
// All four families remain exploratory and are NOT plugged into the cBot allocator.
public sealed record XuaH1(long CloseAt, double Open, double High, double Low,
    double Close, double Volume);
public sealed record XuaFeatureFrame(string Mechanism,string Symbol,
    XuaH1[] History,XuaH1[]? PeerHistory);
public static class XuaNativeFeatureSigns
{
    public const long HourMs=3600000L;
    public const string Energy="ENERGY_NEWS_IMPULSE_PERSISTENCE_4H";
    public const string Crypto="CRYPTO_PANIC_REBOUND_6H";
    public const string Asia="ASIAN_INDEX_RISK_SYNCHRONY_3H";
    public const string Forex="GBPJPY_REJECTION_WICK_2H";

    private static double Median(double[] values)
    {
        if(values.Length==0)return double.NaN;
        Array.Sort(values);
        int mid=values.Length/2;
        return values.Length%2==1?values[mid]:(values[mid-1]+values[mid])/2;
    }
    private static int Sign(double v)=>v>0?1:v<0?-1:0;
    private static bool Valid(XuaH1[]? rows)
    {
        if(rows is null || rows.Length!=25)return false;
        for(int i=0;i<rows.Length;i++)
        {
            var a=rows[i];
            if(a.CloseAt<=0 || a.Open<=0 || a.High<a.Open || a.High<a.Close ||
                a.Low<=0 || a.Low>a.Open || a.Low>a.Close || a.High<a.Low ||
                a.Close<=0 || a.Volume<0 || !double.IsFinite(a.Close) ||
                !double.IsFinite(a.High) || !double.IsFinite(a.Low) ||
                !double.IsFinite(a.Open) || !double.IsFinite(a.Volume) ||
                (i>0 && rows[i-1].CloseAt>=a.CloseAt))return false;
        }
        return true;
    }
    private static XuaH1? At(XuaH1[] rows,long t)
    {
        for(int i=rows.Length-1;i>=0;i--)
            if(rows[i].CloseAt==t)return rows[i];
        return null;
    }
    public static int Decide(XuaFeatureFrame x)
    {
        var h=x.History;
        if(!Valid(h))return 0;
        var c=h[^1];
        if(x.Mechanism==Energy)
        {
            if(x.Symbol is not ("SpotCrude" or "SpotBrent"))return 0;
            var older=At(h,c.CloseAt-4*HourMs);
            if(older is null)return 0;
            double move=10000*Math.Log(c.Close/older.Close);
            var r=Enumerable.Range(1,24)
                .Where(i=>h[i].CloseAt-h[i-1].CloseAt==HourMs && i<24)
                .Select(i=>10000*Math.Abs(Math.Log(h[i].Close/h[i-1].Close))).ToArray();
            if(r.Length<12)return 0;
            double past=Median(r);
            double volume=Median(h.Skip(4).Take(20).Select(z=>z.Volume).ToArray());
            return Math.Abs(move)>=Math.Max(15,3*past) &&
                   c.Volume>=1.10*volume && volume>0 ? Sign(move):0;
        }
        if(x.Mechanism==Crypto)
        {
            if(x.Symbol!="ETHUSD")return 0;
            var earlier=At(h,c.CloseAt-24*HourMs);
            var last=At(h,c.CloseAt-HourMs);
            if(earlier is null || last is null)return 0;
            double day=10000*Math.Log(c.Close/earlier.Close);
            double bounce=10000*Math.Log(c.Close/last.Close);
            return Math.Abs(day)>=180 && Math.Abs(bounce)>=10 &&
                   Sign(day)*Sign(bounce)==-1 ? Sign(bounce):0;
        }
        if(x.Mechanism==Asia)
        {
            if(x.Symbol is not ("HK50" or "JPN225-F") || !Valid(x.PeerHistory))return 0;
            var peer=x.PeerHistory!;
            var p=peer[^1];
            if(p.CloseAt!=c.CloseAt)return 0;
            var older=At(h,c.CloseAt-4*HourMs);
            var olderPeer=At(peer,c.CloseAt-4*HourMs);
            if(older is null || olderPeer is null)return 0;
            double r1=10000*Math.Log(c.Close/older.Close),
                   r2=10000*Math.Log(p.Close/olderPeer.Close);
            if(Math.Abs(r1)<20 || Math.Abs(r2)<20 || Sign(r1)!=Sign(r2))return 0;
            double m=Median(h.Skip(12).Take(12).Select(z=>z.Volume).ToArray());
            return m>0 && c.Volume>=m ? Sign(r1):0;
        }
        if(x.Mechanism==Forex)
        {
            if(x.Symbol!="GBPJPY")return 0;
            double range=c.High-c.Low;
            if(range<=0)return 0;
            double volume=Median(h.Skip(12).Take(12).Select(z=>z.Volume).ToArray());
            if(volume<=0 || c.Volume<volume)return 0;
            double upper=c.High-Math.Max(c.Open,c.Close);
            double lower=Math.Min(c.Open,c.Close)-c.Low;
            if(upper>=0.6*range && c.Close<c.Open)return -1;
            if(lower>=0.6*range && c.Close>c.Open)return 1;
        }
        return 0;
    }
    public static int[] DecideBatch(XuaFeatureFrame[] frames)=>
        frames.Select(Decide).ToArray();
}
