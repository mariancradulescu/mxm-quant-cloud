using Mxm.Core;
internal static class NativeCausalWarmupChecks
{
    public static void Run(Action<bool,string> check)
    {
        const long baseAt=1793790000000L;
        const long span=300000L;
        var bars=Enumerable.Range(0,33).Select(i=>{
            decimal c=1.1m+i*.0001m;
            return new NativeClosedMarketBar(baseAt+i*span,baseAt+(i+1)*span,
                c,c+.0002m,c-.0002m,c,100+i);
        }).ToArray();
        var input=new NativeWarmupInput("EURUSD","M5",5,bars[^1].CloseAt+1000,bars);
        var ready=NativeCausalWarmup.Rebuild(input);
        check(ready.Ready&&ready.UsedBars==33&&ready.LastClosedAt==bars[^1].CloseAt&&
              ready.NormalizedDrift>0&&ready.RelativeTickActivity>0&&
              !ready.ForecastModelRestored&&!ready.BrokerDecisionEligible,
            "bounded source rewarm reconstructs factual causal features, not fitted forecast or order permission");
        check(ready==NativeCausalWarmup.Rebuild(input),
            "the same broker closed-bar prefix recreates identical state without LocalStorage");
        check(ready==NativeCausalWarmup.Rebuild(input with {
            ClosedBars=new[]{new NativeClosedMarketBar(baseAt-span,baseAt,1m,2m,.5m,1m,0L)}.Concat(bars).ToArray()}),
            "old research history outside the finite prefix cannot change feature rewarm");
        check(!NativeCausalWarmup.Rebuild(input with {ClosedBars=bars.Take(32).ToArray()}).Ready,
            "missing required closed history suspends only the affected feature lane");
        check(!NativeCausalWarmup.Rebuild(input with {
            ClosedBars=bars.Take(32).Append(bars[^1] with {CloseAt=input.ObservedAt+1000}).ToArray()}).Ready,
            "a bar that finishes after observation cannot enter causal state");
        check(!NativeCausalWarmup.Rebuild(input with {ClosedBars=bars.Take(16).Concat(bars.Skip(17)).ToArray()}).Ready,
            "missing bar cannot be silently replaced by an adjacent future observation");
        check(!NativeCausalWarmup.Rebuild(input with {ObservedAt=bars[^1].CloseAt+3*span}).Ready,
            "stale warmup cannot remain current after a prolonged data outage");
        check(!NativeCausalWarmup.Rebuild(input with {ClosedBars=bars.Take(32).Append(
            bars[^1] with {OpenAt=bars[^2].OpenAt}).ToArray()}).Ready,
            "duplicates and reversed bar clocks invalidate deterministic rewarm");
        check(!NativeCausalWarmup.Rebuild(input with {ClosedBars=bars.Take(32).Append(
            bars[^1] with {High=0}).ToArray()}).Ready,
            "invalid OHLC geometry is not interpreted as a market signal");
        var zeros=bars.Select(b=>b with {TickVolume=0}).ToArray();
        var quiet=NativeCausalWarmup.Rebuild(input with {ClosedBars=zeros});
        check(quiet.Ready&&quiet.RelativeTickActivity is null,
            "missing relative activity information stays unknown, not a fabricated volume effect");
    }
}
