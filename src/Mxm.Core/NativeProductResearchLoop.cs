using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Mxm.Core;

// Causal, bounded, NO-ORDER product research. All market/contract inputs arrive
// from the caller and are explicitly labeled model observations, never fills.
public sealed record NativeProductMarket(
    string Symbol, NativeClosedMarketBar[] M5, NativeClosedMarketBar[] M15,
    LedgerQuote Quote, NativeObservedContractTerms? Contract,
    decimal SlippagePerSideQuote, int HoldingMinutes=30,
    bool IndependentlySupportedAgainstBenchmark=false);

public sealed record NativeProductSignal(
    string Symbol,long At,int Direction,string Status,
    decimal? GrossForecastEur,decimal? CentralForecastEur,
    decimal? AdverseForecastEur,string DecisionReason);

public sealed record NativeProductResearchReport(
    long At,int Forecasts,int AcceptedModelIntents,int RejectedIntents,
    int ModelOpenPositions,int ModelPendingIntents,int ModelClosedRoundTrips,
    decimal ModelCashEur,decimal? ModelEquityEur,decimal ModelGrossEur,
    decimal ModelCentralNetEur,decimal ModelAdverseNetProxyEur,
    decimal ModelMaximumSampledDrawdown,
    Dictionary<string,int> ModelRoundTripsPerIsoWeek,
    NativeProductSignal[] LatestSignals,string Status,
    bool BrokerNetCertified=false,bool Qualified=false,bool OrdersEnabled=false);

public sealed class NativeProductResearchLoop
{
    private sealed record Tracked(string Symbol,int Side,decimal Units,long RequestAt,
        long OpenAt,int HoldMinutes,decimal SlippagePerSideQuote,
        NativeObservedContractTerms Contract,bool CloseRequested=false);
    private const string ResearchDomain="UNQUALIFIED_CAUSAL_MODEL_REPLAY_NOT_BROKER_EXECUTION";
    private readonly NativeFundedSession session=new("NATIVE_PRODUCT_MODEL_REPLAY_ONLY");
    private readonly Dictionary<string,Tracked> tracked=new(StringComparer.Ordinal);
    private readonly Dictionary<string,long> previousForecastBar=new(StringComparer.Ordinal);
    private readonly Dictionary<string,int> weekly=new(StringComparer.Ordinal);
    private readonly List<NativeProductSignal> signals=new();
    private long lastClock=-1;
    private int eventSequence, forecasts, accepted, rejected;

    public NativeFundedSession ResearchSession=>session;
    private static string Fingerprint(string value)=>Convert.ToHexString(
        SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    private LedgerEvent Event(string kind,long at,string id="",string symbol="",int side=0,
        decimal units=0,decimal execution=0,decimal fee=0,decimal margin=0,
        decimal slippage=0,long available=0,long calibrated=0,long latency=1000,
        LedgerQuote[]? quotes=null,decimal financing=0)
        =>new("PRODUCT/"+(++eventSequence)+"/"+kind,at,kind,id,symbol,side,units,
            execution,fee,margin,slippage,available,calibrated,latency,ResearchDomain,
            Fingerprint(ResearchDomain+":"+at+":"+symbol+":"+eventSequence),
            quotes??Array.Empty<LedgerQuote>(),financing);
    private static decimal Fee(LedgerQuote q,decimal units)=>
        Math.Max(q.ExitFeePerUnit*units,q.ExitFeeFloor);
    private static string Week(long at)
    {
        var date=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return ISOWeek.GetYear(date)+"-W"+ISOWeek.GetWeekOfYear(date).ToString("00",CultureInfo.InvariantCulture);
    }
    public NativeProductResearchReport Advance(long at,NativeProductMarket[] markets,
        bool EnableUnqualifiedShadowSimulation)
    {
        if(at<=lastClock||at<=0||markets is null||
           markets.Select(x=>x.Symbol).Distinct(StringComparer.Ordinal).Count()!=markets.Length ||
           markets.Any(x=>x.Quote.At!=at||string.IsNullOrWhiteSpace(x.Symbol)||
               x.Symbol!=x.Quote.Symbol||x.SlippagePerSideQuote<0||
               x.HoldingMinutes<15||x.HoldingMinutes>240))
            throw new ArgumentException("PRODUCT_REPLAY_NONCAUSAL_MARKET_CLOCK");
        // One coherent multiasset mark; no broker ledger/account state is ever
        // accessed or modified. No synthetic fill is created on the intent clock.
        session.ApplyResearchFacts(new[]{Event("MARK",at,quotes:markets.Select(x=>x.Quote).ToArray())});
        var byName=markets.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        foreach(var id in tracked.Keys.ToArray())
        {
            var p=tracked[id];
            if(!byName.TryGetValue(p.Symbol,out var m))continue;
            var q=m.Quote;
            if(p.OpenAt==0 && at>=p.RequestAt+1000)
            {
                decimal px=p.Side>0?q.Ask+p.SlippagePerSideQuote:q.Bid-p.SlippagePerSideQuote;
                session.ApplyResearchFacts(new[]{Event("OPEN_FILL",at,id,p.Symbol,p.Side,
                    p.Units,px,Fee(q,p.Units),q.MarginPerUnit,p.SlippagePerSideQuote)});
                tracked[id]=p with {OpenAt=at};
            }
            else if(p.OpenAt>0 && p.CloseRequested && at>=p.RequestAt+1000)
            {
                // Contractual rollover is never guessed. Without a complete
                // financing model, hold the position as unknown, not zero-cost.
                var finance=NativeBrokerContractCosts.SignedFinancing(p.Contract,
                    p.OpenAt,at,p.Side,p.Units,q.EurCredit,q.EurDebit);
                if(finance is null)continue;
                decimal px=p.Side>0?q.Bid-p.SlippagePerSideQuote:q.Ask+p.SlippagePerSideQuote;
                session.ApplyResearchFacts(new[]{
                    Event("FINANCING",at,id,p.Symbol,p.Side,p.Units,
                        financing:finance.Value),
                    Event("CLOSE_FILL",at,id,p.Symbol,p.Side,p.Units,
                        px,Fee(q,p.Units),q.MarginPerUnit,p.SlippagePerSideQuote)
                });
                tracked.Remove(id);
                var k=Week(at);
                weekly[k]=weekly.GetValueOrDefault(k)+1;
            }
            else if(p.OpenAt>0 && !p.CloseRequested &&
                    at-p.OpenAt>=p.HoldMinutes*60000L)
            {
                session.ApplyResearchFacts(new[]{Event("REQUEST_CLOSE",at,id,
                    p.Symbol,p.Side,p.Units,latency:1000)});
                tracked[id]=p with {CloseRequested=true,RequestAt=at};
            }
        }

        var offered=new List<EconomicOpportunity>();
        var evidence=new List<SpecialistEuroEvidence>();
        var terms=new List<ResearchEntryTerms>();
        var recent=new List<NativeProductSignal>();
        foreach(var market in markets)
        {
            var p5=NativeCausalWarmup.Rebuild(new(market.Symbol,"M5",5,at,market.M5));
            var p15=NativeCausalWarmup.Rebuild(new(market.Symbol,"M15",15,at,market.M15));
            if(!p5.Ready || !p15.Ready || p5.NormalizedDrift is not decimal a ||
                p15.NormalizedDrift is not decimal b || a*b<=0 ||
                previousForecastBar.GetValueOrDefault(market.Symbol)==p5.LastClosedAt)
                continue;
            previousForecastBar[market.Symbol]=p5.LastClosedAt;
            forecasts++;
            int side=a>0?1:-1;
            var q=market.Quote;
            if(market.Contract is not NativeObservedContractTerms c ||
               c.Symbol!=market.Symbol ||
               c.MinimumUnits<=0 || c.MinimumUnits>c.MaximumUnits ||
               !c.OriginalBrokerAuthenticated)
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_COST_CONTRACT_NOT_AVAILABLE",
                    null,null,null,"SOURCE_OR_CONTRACT_UNATTESTED"));
                continue;
            }
            decimal units=c.MinimumUnits;
            if(tracked.Values.Any(x=>x.Symbol==market.Symbol))
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_SYMBOL_ALREADY_OPEN_OR_PENDING",
                    null,null,null,"SINGLE_POSITION_PER_SYMBOL"));
                continue;
            }
            decimal? signedFunding=NativeBrokerContractCosts.SignedFinancing(
                c,at,at+market.HoldingMinutes*60000L,side,units,q.EurCredit,q.EurDebit);
            if(signedFunding is null)
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_FUNDING_UNKNOWN",
                    null,null,null,"NO_UNPRICED_ROLLOVER"));
                continue;
            }
            decimal mid=(q.Bid+q.Ask)/2m;
            decimal fx=(q.EurCredit+q.EurDebit)/2m;
            // EXPLORATORY forecast, not a fitted/qualified alpha: agreement
            // between completed M5 and M15 direction, magnitude from past
            // normalized movement. No closing or future sample is consulted.
            decimal projectedGross=Math.Abs((4m*a+b)*mid*units*fx);
            decimal spread=(q.Ask-q.Bid)*units*fx;
            decimal commission=2m*Fee(q,units);
            decimal slippage=2m*market.SlippagePerSideQuote*units*fx;
            decimal fundingDebit=Math.Max(0,-signedFunding.Value);
            decimal conversion=projectedGross*
                Math.Max(0,q.EurDebit-q.EurCredit)/Math.Max(.00000001m,fx);
            decimal uncertainty=Math.Abs(a-b)*mid*units*fx+
                (p5.MeanAbsoluteReturn??0m)*mid*units*fx;
            decimal predictedNet=projectedGross-spread-commission-slippage-
                fundingDebit-conversion;
            decimal adverse=predictedNet-spread-slippage;
            string id="EXPLORATORY/"+market.Symbol+"/"+p5.LastClosedAt;
            var baseClock=Math.Min(p5.LastClosedAt,p15.LastClosedAt);
            if(baseClock>=at-1)
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_FEATURE_UNAVAILABLE_BEFORE_DECISION",
                    projectedGross,predictedNet,adverse,"CAUSAL_CLOCK_UNSUPPORTED"));
                continue;
            }
            decimal minMargin=q.MarginPerUnit*units;
            var grid=new AdaptiveRiskInputs(300m,0m,300m,units,c.VolumeStepUnits,
                units,q.MarginPerUnit,0m,false,false,2,0m);
            decimal perUnit=(predictedNet-uncertainty)/Math.Max(1,units)*.5m;
            decimal riskPerUnit=Math.Abs(a)*mid*fx*.25m+.00001m;
            var candidates=Enumerable.Range(0,8).Select(i=>
                new OpportunityScenario("STATE"+i,baseClock,true,perUnit,0m,
                    riskPerUnit,0m)).ToArray();
            offered.Add(new EconomicOpportunity(id,"EXPLORATORY_M5_M15_AGREEMENT_NOT_FITTED",
                market.Symbol,id,side,at-1,baseClock,
                EvidenceLevel.Exploratory,false,grid,candidates));
            evidence.Add(new(id,baseClock,at-1,5,market.HoldingMinutes,
                true,market.IndependentlySupportedAgainstBenchmark,true,true,
                false,projectedGross,uncertainty,spread,
                Fee(q,units),Fee(q,units),conversion,slippage,fundingDebit,minMargin));
            terms.Add(new(id,1000,market.SlippagePerSideQuote,Fingerprint(id)));
            recent.Add(new(market.Symbol,at,side,"MODEL_FORECAST_ONLY",
                projectedGross,predictedNet,adverse,
                market.IndependentlySupportedAgainstBenchmark?
                    "EXTERNAL_BENCHMARK_SUPPORT_SUPPLIED":"EXPLORATORY_NO_INDEPENDENT_BENCHMARK_SUPPORT"));
        }
        if(offered.Count>0)
        {
            var states=Enumerable.Range(0,8).Select(i=>
                new PortfolioScenario("STATE"+i,at-2,true,0m,0m,0m,0m)).ToArray();
            var d=new NativeResearchDecision("PRODUCT/"+at,at,
                new ScenarioSizingInputs(300,300,300,1,1,1,1,1,2,0),
                states,offered.ToArray(),Array.Empty<ResearchExposureScenarios>(),
                terms.ToArray(),Fingerprint("PRODUCT/"+at),evidence.ToArray());
            // Exact same prospectively gated path for independently supported
            // evidence. UNQUALIFIED shadow mode is explicit, never promoted.
            var conditional=EnableUnqualifiedShadowSimulation
                ?session.DecideResearch(d with {SpecialistEvidence=null})
                :session.DecideProspective(d);
            accepted+=conditional.Selection.Allocations.Length;
            rejected+=conditional.Selection.Declined.Length;
            foreach(var chosen in conditional.Selection.Allocations)
            {
                var opportunity=offered.Single(x=>x.Id==chosen.Id);
                var market=byName[opportunity.Symbol];
                tracked.Add(chosen.Id,new(market.Symbol,opportunity.Direction,
                    chosen.Units,at,0,market.HoldingMinutes,market.SlippagePerSideQuote,
                    market.Contract!));
            }
            foreach(var declined in conditional.Selection.Declined)
            {
                var ix=recent.FindIndex(x=>declined.Id.EndsWith(
                    x.Symbol+"/"+previousForecastBar.GetValueOrDefault(x.Symbol)));
                if(ix>=0)recent[ix]=recent[ix] with {DecisionReason=declined.Reason};
            }
        }
        signals.AddRange(recent);
        if(signals.Count>300)signals.RemoveRange(0,signals.Count-300);
        lastClock=at;
        return Report(at,recent.ToArray());
    }

    private NativeProductResearchReport Report(long at,NativeProductSignal[] recent)
    {
        var s=session.Ledger.Summary(at);
        var closed=session.Ledger.ClosedFragments();
        decimal extraStress=closed.Sum(x=>x.SpreadEur??0m);
        return new(at,forecasts,accepted,rejected,s.OpenPositions,s.PendingIntents,
            s.CompleteRoundTrips,s.CashEur,s.LiquidationEquityEur,
            closed.Sum(x=>x.GrossEur),s.ClosedNetEur,
            s.ClosedNetEur-extraStress,s.MaximumSampledDrawdown,
            new Dictionary<string,int>(weekly,StringComparer.Ordinal),recent,
            "MODEL_ONLY_FIXED_EUR300_CASH_BENCHMARK_ZERO_NOT_INDEPENDENT_OR_BROKER_NET");
    }
}
