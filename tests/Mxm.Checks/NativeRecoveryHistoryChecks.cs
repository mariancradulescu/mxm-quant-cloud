using Mxm.Core;
internal static class NativeRecoveryHistoryChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long hour=3600000;
        long start=new DateTimeOffset(2025,1,1,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
        var bars=Enumerable.Range(0,5000).Select(i=>new NativeClosedMarketBar(start+i*hour,start+(i+1)*hour,
            100m+i*.01m,101m+i*.01m,99m+i*.01m,100.01m+i*.01m,100)).ToArray();
        long at=bars[3000].OpenAt+15000;
        var current=bars.Take(3000).TakeLast(8).ToArray();
        var a=new NativeRecoveryHistory(bars).At(at,current);
        var changed=bars.Select((b,i)=>i<3000?b:b with {Close=b.Close-10m}).ToArray();
        var b=new NativeRecoveryHistory(changed).At(at,current);
        var c=new NativeRecoveryHistory(bars.Take(3000).ToArray()).At(at,current);
        check(a==b&&a==c&&a.LatestLabelAt<at,"recovered calendar and run forecasts ignore changed and censored future labels");
        check(a.RunDays>5&&a.RunSide==1,"recovered run forecast uses matured same-symbol daily evidence");
        var stale=new NativeRecoveryHistory(bars).At(at+2*hour,current);
        check(stale.RunSide==0&&stale.CalendarSide==0,"stale current states cannot authorize recovered offers");
        var future=new NativeRecoveryHistory(bars).At(at,current.Append(bars[3000]).ToArray());
        check(future.RunSide==0&&future.CalendarSide==0,"forming hourly bars cannot enter recovered current-state decisions");
        var one=new NativeRecoveryHistory(bars.Take(10).ToArray()).At(bars[10].OpenAt+15000,bars.Take(10).TakeLast(4).ToArray());
        check(one.RunSide==0&&one.CalendarSide==0,"recovered history retains abstention below actual daily support");
        var alternating=Enumerable.Range(0,30).Select(i=>bars[i] with {Close=100m+(i%2==0?1m:0m)}).ToArray();
        int side=NativeRecoveredEconomicMechanisms.SerialCorrelationSide(alternating,8);
        check(side==1,"HRC recovery uses lag-one serial correlation rather than a range-midpoint substitute");
        alternating[27]=alternating[27] with {CloseAt=alternating[27].CloseAt-1};
        check(NativeRecoveredEconomicMechanisms.SerialCorrelationSide(alternating,8)==0,"HRC serial correlation rejects a broken information interval");
    }
}
