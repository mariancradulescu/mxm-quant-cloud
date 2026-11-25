using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record EerStopTick(long At,decimal Price);
    sealed record EerStopTape(string PositionId,int Side,long FillAt,long OriginalCloseAt,
        EerStopTick AtFill,decimal Stop,EerStopTick[] TradeSideTicks);

    public static int AuditEerStopTrigger(string packetEvidence,string output)
    {
        var tape=JsonSerializer.Deserialize<EerStopTape>(File.ReadAllBytes(packetEvidence),Json)
            ?? throw new ArgumentException("EER1_STOP_TAPE");
        if(tape.Side is not (1 or -1) || tape.Stop<=0m || tape.FillAt>=tape.OriginalCloseAt ||
           tape.AtFill.Price<=0m || tape.AtFill.At>tape.FillAt || tape.FillAt-tape.AtFill.At>30_000L ||
           tape.TradeSideTicks.Any(t=>t.Price<=0m || t.At<=tape.FillAt || t.At>tape.OriginalCloseAt) ||
           !tape.TradeSideTicks.Select(t=>t.At).SequenceEqual(tape.TradeSideTicks.Select(t=>t.At).Order()))
            throw new ArgumentException("EER1_STOP_INVALID_QUOTE_CLOCK");
        bool Crossed(decimal quote)=>NativeExecutableEconomics.TradeStopReached(tape.Side,quote,tape.Stop);
        bool breachedAtFill=Crossed(tape.AtFill.Price);
        var first=tape.TradeSideTicks.FirstOrDefault(t=>Crossed(t.Price));
        long? firstBreachAt=breachedAtFill?tape.FillAt:first?.At;
        var crossingQuotes=breachedAtFill?new[]{tape.AtFill}:
            tape.TradeSideTicks.Where(t=>t.At==firstBreachAt&&Crossed(t.Price)).ToArray();
        File.WriteAllText(output,JsonSerializer.Serialize(new {tape.PositionId,tape.Side,tape.FillAt,
            tape.OriginalCloseAt,QuoteSide=tape.Side>0?"BID":"ASK",
            ProtectionTriggerMethod="Trade", SourceTicks=tape.TradeSideTicks.Length,
            TriggerAlreadyObservedAtFill=breachedAtFill,FirstBreachAt=firstBreachAt,
            FirstBreachBeforeOriginalCloseMilliseconds=tape.OriginalCloseAt-firstBreachAt,
            FirstBreachMinimumOvershootInPrice=crossingQuotes.Length==0?(decimal?)null:
                crossingQuotes.Min(t=>tape.Side*(tape.Stop-t.Price)),
            FirstBreachMaximumOvershootInPrice=crossingQuotes.Length==0?(decimal?)null:
                crossingQuotes.Max(t=>tape.Side*(tape.Stop-t.Price)),
            MultipleDistinctQuotesAtFirstBreach=!breachedAtFill&&firstBreachAt is not null&&
                tape.TradeSideTicks.Where(t=>t.At==firstBreachAt).Select(t=>t.Price).Distinct().Skip(1).Any(),
            ObservedTriggeredQuoteIsFill=false,Orders=0,CloudActivated=false},Json));
        return 0;
    }
}
