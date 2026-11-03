namespace Mxm.Core;

public sealed record QuoteSideEvent(long At,string Symbol,int Side,decimal Price);
public sealed record ObservationWindow(long Nominal,long LatencyMs,long SearchMs,long MaximumAgeMs,
    string[] Route,QuoteSideEvent[] Events,bool Complete);
public sealed record ObservedQuote(string Symbol,decimal Bid,decimal Ask,long BidAt,long AskAt);
public sealed record ObservationResult(string Status,long? At,ObservedQuote[] Quotes);

// A stopping time on an ordered event stream, never an extremum over prices.
// Same-timestamp events are atomic; conflicting duplicates fail closed.
// Complete means all requested pages were recovered, not a liquidity certificate.
public static class CausalObservationClock
{
    public static ObservationResult First(ObservationWindow w)
    {
        if(w.Nominal<0 || w.LatencyMs<0 || w.SearchMs<0 || w.MaximumAgeMs<0 ||
           w.Route.Length==0 || w.Route.Any(string.IsNullOrWhiteSpace) ||
           w.Route.Distinct(StringComparer.Ordinal).Count()!=w.Route.Length)
            throw new ArgumentException("OBSERVATION_WINDOW_CONTRACT");
        long start=checked(w.Nominal+w.LatencyMs),end=checked(start+w.SearchMs);
        if(!w.Complete)return new("INCOMPLETE_SOURCE",null,Array.Empty<ObservedQuote>());
        if(w.Events.Any(x=>x.At<0 || string.IsNullOrWhiteSpace(x.Symbol) || x.Side is <0 or >1))
            throw new ArgumentException("OBSERVATION_EVENT_CONTRACT");
        var state=new Dictionary<(string,int),QuoteSideEvent>();
        foreach(var batch in w.Events.Where(x=>x.At<=end).OrderBy(x=>x.At).GroupBy(x=>x.At))
        {
            foreach(var side in batch.GroupBy(x=>(x.Symbol,x.Side)))
            {
                if(side.Select(x=>x.Price).Distinct().Count()!=1)
                    throw new ArgumentException("AMBIGUOUS_SAME_TIME_SIDE");
                state[side.Key]=side.First();
            }
            long at=batch.Key;
            if(at<start)continue;
            bool valid=w.Route.All(s=>state.TryGetValue((s,0),out var b) &&
                state.TryGetValue((s,1),out var a) && at-b.At<=w.MaximumAgeMs &&
                at-a.At<=w.MaximumAgeMs && b.Price>0 && a.Price>=b.Price);
            if(!valid)continue;
            return new("OBSERVED",at,w.Route.OrderBy(x=>x,StringComparer.Ordinal).Select(s=>
                new ObservedQuote(s,state[(s,0)].Price,state[(s,1)].Price,
                    state[(s,0)].At,state[(s,1)].At)).ToArray());
        }
        return new("NO_CAUSAL_OBSERVATION",null,Array.Empty<ObservedQuote>());
    }
}
