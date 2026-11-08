using System;
using System.Linq;
using Mxm.Core;

static class McsNativeChecks
{
    public static void Run(Action<bool,string> check)
    {
        long t=new DateTimeOffset(2026,11,5,17,0,0,TimeSpan.Zero)
            .ToUnixTimeMilliseconds();
        McsH1Bar[] Bars(double[] prices,long v=100)
            =>prices.Select((p,i)=>new McsH1Bar(
                t-(prices.Length-1-i)*McsNativeH1Features.Hour,
                p,p,p,p,i==prices.Length-1?200:v)).ToArray();
        var gas=Bars(new[]{100d,115d,118d,115d,110d});
        var dollar=Bars(new[]{100d,100d,100d});
        var o=new McsH1Frame(McsNativeH1Features.Gas,"NatGas","USDX",
            t,gas,dollar);
        check(McsNativeH1Features.Evaluate(o)==new McsH1Signs(-1,1,true),
            "NatGas true contiguous 4H reversal with USD index quiet and volume");
        var up=Bars(new[]{100d,100.1d,100.2d});
        check(McsNativeH1Features.Evaluate(new(McsNativeH1Features.Dollar,
             "USDX",null,t,up,null))==new McsH1Signs(1,1,true),
            "USD index genuine 2H overlap direction and same event long benchmark");
        var equity=Bars(new[]{100d,100d,100d,100d,101d});
        check(McsNativeH1Features.Evaluate(new(McsNativeH1Features.Equity,
             "AMD.US",null,t,equity,null))==new McsH1Signs(-1,1,true),
            "AMD completed H1 flow climax fades with cash-session activity");
        check(!McsNativeH1Features.Evaluate(o with {
             Target=gas.Skip(1).ToArray()}).Complete,
            "missing H1 bar never forward-fills a 4H gas feature");
        check(McsNativeH1Features.Evaluate(o with {Target=gas.Append(
            new McsH1Bar(t+McsNativeH1Features.Hour,1,1,1,1,100)).ToArray()})==
            McsNativeH1Features.Evaluate(o),
            "future authentic H1 price cannot change earlier signal");
        check(McsNativeH1Features.Evaluate(o with {Symbol="GBPJPY"}).Side==0,
            "no migration of frozen GBPJPY or unrelated symbol to MCS1");
    }
}
