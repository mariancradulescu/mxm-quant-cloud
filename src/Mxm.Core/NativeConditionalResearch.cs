namespace Mxm.Core;

public static class NativeConditionalResearch
{
    public const string Profile="CDE1";
    public const string Universe="AUDUSD,NZDUSD,Copper,EURUSD";
    public static string? Family(string symbol)=>symbol switch
    {
        "AUDUSD" or "NZDUSD"=>"FX","Copper"=>"METAL",_=>null
    };

    public static string Exit(string symbol)=>symbol=="Copper"?NativeCausalExitResearch.PredictionInvalidation:
        NativeIntegratedResearch.Exit(symbol);

    public static (int Side,string? Cohort) Observe(NativeProductMarket market)
    {
        var family=Family(market.Symbol);
        if(family is null || market.M15.Length<6)return (0,null);
        var bars=market.M15.TakeLast(6).ToArray();
        if(!bars.Zip(bars.Skip(1),(a,b)=>a.CloseAt==b.OpenAt).All(x=>x))return (0,null);
        decimal move;
        if(family=="FX")
        {
            var hour=bars.TakeLast(4).ToArray();
            move=hour[^1].Close-hour[0].Open;
            int side=Math.Sign(move);
            int pressure=hour.Count(b=>side*(2m*b.Close-b.High-b.Low)>0m);
            if(side==0 || pressure<3)return (0,null);
        }
        else
        {
            if(market.Quote.At/60000%60!=30)return (0,null);
            var before=bars[3].Close-bars[0].Open;
            move=bars[5].Close-bars[4].Open;
            if(before*move>=0m)return (0,null);
        }
        var q=market.Quote;
        var units=market.Contract!.MinimumUnits;
        var fx=(q.EurCredit+q.EurDebit)/2m;
        decimal twoWayFee=2m*Math.Max(q.ExitFeeFloor,units*q.ExitFeePerUnit);
        decimal friction=2m*((q.Ask-q.Bid+2m*market.SlippagePerSideQuote)*units*fx+twoWayFee);
        // This is a pre-entry cost burden, not an estimate of future motion.
        string bucket=friction<=Math.Abs(move)*units*fx/4m?"LOW":"HIGH";
        return (Math.Sign(move),family+"/"+bucket);
    }
}

public sealed record NativeConditionalDistribution(int Pairs,int Wins,int Losses,int Flat,
    decimal GrossBps,decimal CentralBps,decimal AdverseBps,decimal ReverseBps,
    decimal AdverseP10Bps,decimal AdverseMedianBps,decimal AdverseP90Bps,
    decimal? MeanWinBps,decimal? MeanLossBps,decimal MeanAdverseFrictionBps,
    decimal? Brier,decimal? TrainingPooledBrier);
