using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Core;

// NEW prospective Bayesian transition study, not a historical strategy replay.
// One observed CLOSED quote per clock. No retroactive intrabar triggers/fills.
public sealed record NativeBayesObservation(long At, LedgerQuote Quote,
    bool CompletedObservation=true, decimal SignedFinancingEur=0m);

public sealed record NativeBayesEventFact(string Kind,long At,string PositionId,
    int Side,decimal Units,decimal ExecutionPrice,decimal FeeEur,
    decimal SlippageQuote,decimal MarginPerUnit,string Reason);

public sealed record NativeBayesStep(
    int Index,long At,decimal? PriorCloseChange,int PositiveTransitions,
    int NegativeTransitions,decimal PosteriorUp,int ForecastSide,
    decimal? Stop,decimal? Target,NativeBayesEventFact[] Events,
    decimal CashEur,decimal? LiquidationEquityEur,decimal? UsedMarginEur,
    decimal? FreeMarginEur,decimal MaximumSampledDrawdown,
    int OpenPositions,int PendingIntents,int CompleteRoundTrips,
    decimal ClosedNetEur,string LedgerEventChainHash,string StepSha256,
    bool CompleteFloatingRiskCertified=false,bool OrdersEnabled=false);

public sealed class NativeBayesianCommonEpisode
{
    // Freeze BEFORE new economic scoring; NOT fitted to a fixture outcome.
    public const string Version="NATIVE_BAYES_SIGN_TRANSITION_V1";
    public const decimal LongPosteriorThreshold=.70m;
    public const decimal ShortPosteriorThreshold=.30m;
    public const int MinimumMaturedTransitions=4;
    public const decimal FixedSlippageQuote=.005m;
    public const long MinimumFillLatencyMs=1000L;
    public const long MaximumOpenDurationMs=1800000L;
    private const decimal PhysicalSyntheticUnits=1m;
    private static readonly string Evidence=new string('b',64);
    private readonly NativeFundedLedger ledger=new();
    private decimal? lastMid;
    private int up,down;
    private decimal cumulativeAbsoluteMovement;
    private string positionId="";
    private int positionSide;
    private decimal entryReference,stop,target;
    private long openingRequestAt,closingRequestAt,filledAt;
    private bool pendingOpen,pendingClose,holding;
    private int nextPosition=0,nextEvent=0,lastIndex=-1;
    private long lastAt=-1;
    private string? symbol;
    public LedgerSummary CurrentBook=>ledger.Summary();
    public LedgerClosedFragment[] ClosedFragments()=>ledger.ClosedFragments();
    private static string Hash(string s)=>Convert.ToHexString(
        SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    private static decimal Fee(LedgerQuote q,decimal units)=>
        Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);

    public NativeBayesStep Advance(NativeBayesObservation o,int index)
    {
        if(o is null || o.Quote is null || !o.CompletedObservation ||
           o.At<=lastAt || o.At<=0 || o.Quote.At!=o.At ||
           string.IsNullOrWhiteSpace(o.Quote.Symbol) ||
           (symbol is not null && symbol!=o.Quote.Symbol) ||
           o.Quote.Bid<=0 || o.Quote.Ask<o.Quote.Bid ||
           o.Quote.EurCredit<=0 || o.Quote.EurDebit<o.Quote.EurCredit ||
           o.Quote.MarginPerUnit<=0 || o.Quote.ExitFeePerUnit<0 ||
           o.Quote.ExitFeeFloor<0 || o.SignedFinancingEur>0 ||
           index!=lastIndex+1)
            throw new ArgumentException("NEW_NATIVE_BAYES_CAUSAL_SOURCE_OR_CLOCK");
        symbol??=o.Quote.Symbol;lastAt=o.At;lastIndex=index;
        var q=o.Quote;
        var facts=new List<NativeBayesEventFact>();
        void Record(LedgerEvent e)
        {
            ledger.Apply(e);
            facts.Add(new NativeBayesEventFact(e.Kind,e.At,e.PositionId,
                e.Side,e.Units,e.ExecutionPrice,e.FeeEur,e.SlippagePerSide,
                e.MarginPerUnit,e.Reason));
        }
        LedgerEvent Make(string kind,string id,int side=0,decimal units=0m,
            decimal price=0m,decimal fee=0m,string reason="",bool quote=false,
            decimal financing=0m) =>
            new("native-bayes-"+(++nextEvent).ToString(CultureInfo.InvariantCulture),
                o.At,kind,id,q.Symbol,side,units,price,fee,q.MarginPerUnit,
                FixedSlippageQuote,Math.Max(0,o.At-1L),
                Math.Max(0,o.At-1L),MinimumFillLatencyMs,reason,Evidence,
                quote?new[]{q}:Array.Empty<LedgerQuote>(),financing);

        // Ground the ledger FIRST in the observed executable quote.
        Record(Make("MARK","",quote:true,reason:"CLOSED_OBSERVED_QUOTE"));
        if(pendingOpen && o.At-openingRequestAt>=MinimumFillLatencyMs)
        {
            decimal price=positionSide==1?q.Ask+FixedSlippageQuote:
                q.Bid-FixedSlippageQuote;
            Record(Make("OPEN_FILL",positionId,positionSide,PhysicalSyntheticUnits,
                price,Fee(q,PhysicalSyntheticUnits),"NEXT_OBSERVED_SIDE",quote:true));
            pendingOpen=false;holding=true;filledAt=o.At;
            entryReference=price;
        }
        if(pendingClose && o.At-closingRequestAt>=MinimumFillLatencyMs)
        {
            decimal price=positionSide==1?q.Bid-FixedSlippageQuote:
                q.Ask+FixedSlippageQuote;
            Record(Make("CLOSE_FILL",positionId,positionSide,PhysicalSyntheticUnits,
                price,Fee(q,PhysicalSyntheticUnits),"NEXT_OBSERVED_SIDE",quote:true));
            pendingClose=false;holding=false;positionId="";positionSide=0;
            entryReference=0m;stop=0m;target=0m;
        }
        if(holding && o.SignedFinancingEur!=0m)
            Record(Make("FINANCING",positionId,positionSide,PhysicalSyntheticUnits,
                reason:"SUPPLIED_NEGATIVE_FINANCING",financing:o.SignedFinancingEur));
        if(holding && !pendingClose)
        {
            decimal executable=positionSide>0?q.Bid:q.Ask;
            bool stopHit=positionSide>0?executable<=stop:executable>=stop;
            bool targetHit=positionSide>0?executable>=target:executable<=target;
            bool duration=o.At-filledAt>=MaximumOpenDurationMs;
            if(stopHit||targetHit||duration)
            {
                string reason=stopHit?"OBSERVED_STOP_REQUEST":
                    targetHit?"OBSERVED_TARGET_REQUEST":"MAXIMUM_DURATION_REQUEST";
                Record(Make("REQUEST_CLOSE",positionId,positionSide,
                    PhysicalSyntheticUnits,reason:reason));
                pendingClose=true;closingRequestAt=o.At;
            }
        }

        decimal mid=(q.Bid+q.Ask)/2m;
        decimal? change=lastMid is decimal p?mid-p:null;
        if(change is decimal delta && delta!=0m)
        {
            if(delta>0)up++;else down++;
            cumulativeAbsoluteMovement+=Math.Abs(delta);
        }
        lastMid=mid;
        decimal posterior=(2m+up)/(4m+up+down);
        int forecast=up+down<MinimumMaturedTransitions?0:
            posterior>=LongPosteriorThreshold?1:
            posterior<=ShortPosteriorThreshold?-1:0;
        if(!holding && !pendingOpen && !pendingClose && forecast!=0)
        {
            // SL/TP are frozen structural intentions, NOT broker stop orders.
            decimal width=Math.Max(.01m,cumulativeAbsoluteMovement/
                Math.Max(1,up+down))*2m;
            positionSide=forecast;positionId="native-bayes-"+(++nextPosition);
            stop=forecast>0?q.Ask-width:q.Bid+width;
            target=forecast>0?q.Ask+2m*width:q.Bid-2m*width;
            if(stop<=0m || target<=0m)
                throw new ArgumentException("NEW_NATIVE_BAYES_INVALID_PRICE_BARRIERS");
            Record(Make("REQUEST_OPEN",positionId,forecast,PhysicalSyntheticUnits,
                reason:"BAYES_TRANSITION_POSTERIOR"));
            pendingOpen=true;openingRequestAt=o.At;
        }
        var s=ledger.Summary(o.At);
        var provisional=new NativeBayesStep(index,o.At,change,up,down,posterior,
            forecast,positionId==""?null:stop,positionId==""?null:target,
            facts.ToArray(),s.CashEur,s.LiquidationEquityEur,s.UsedMarginEur,
            s.FreeMarginEur,s.MaximumSampledDrawdown,s.OpenPositions,s.PendingIntents,
            s.CompleteRoundTrips,s.ClosedNetEur,s.EventChainHash,"");
        return provisional with {StepSha256=Hash(JsonSerializer.Serialize(provisional))};
    }
}
