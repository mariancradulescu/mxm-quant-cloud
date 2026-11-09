using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Core;

// Causal, bounded, NO-ORDER product research. All market/contract inputs arrive
// from the caller and are explicitly labeled model observations, never fills.
public sealed record NativeProductMarket(
    string Symbol, NativeClosedMarketBar[] M5, NativeClosedMarketBar[] M15,
    LedgerQuote Quote, NativeObservedContractTerms? Contract,
    decimal SlippagePerSideQuote, int HoldingMinutes=30,
    bool IndependentlySupportedAgainstBenchmark=false,
    string ExitPolicy=NativeCausalExitResearch.FrozenFixed);

public sealed record NativeProductSignal(
    string Symbol,long At,int Direction,string Status,
    decimal? GrossForecastEur,decimal? CentralForecastEur,
    decimal? AdverseForecastEur,string DecisionReason,
    string Mechanism="FROZEN_LEGACY_M5_M15");

public sealed record NativeProductResearchReport(
    long At,int Forecasts,int AcceptedModelIntents,int RejectedIntents,
    int ModelOpenPositions,int ModelPendingIntents,int ModelClosedRoundTrips,
    decimal ModelCashEur,decimal? ModelEquityEur,decimal ModelGrossEur,
    decimal ModelCentralNetEur,decimal? ModelAdverseNetProxyEur,
    decimal ModelMaximumSampledDrawdown,
    Dictionary<string,int> ModelRoundTripsPerIsoWeek,
    NativeProductSignal[] LatestSignals,string Status,
    bool BrokerNetCertified=false,bool Qualified=false,bool OrdersEnabled=false,
    decimal? ModelMatchedLongBenchmarkEur=null,
    decimal? ModelIncrementalVsLongEur=null,
    bool AdversePathFullyRepriced=false,int ObservedM5SlotsNotScored=0,
    long MaxObservedM5LagMs=0,bool HistoryPathComplete=false,
    string ModelEpochId="",string ContinuityBoundary="ISOLATED_MODEL_EPISODE",
    int UnresolvedCalendarGaps=0,
    Dictionary<string,int>? ModelExitReasons=null);

public sealed class NativeProductResearchLoop
{
    private sealed record Tracked(string Symbol,int Side,decimal Units,long RequestAt,
        long OpenAt,int HoldMinutes,decimal SlippagePerSideQuote,
        NativeObservedContractTerms Contract,bool CloseRequested=false,
        LedgerQuote? EntryQuote=null,
        string ExitPolicy=NativeCausalExitResearch.FrozenFixed,
        decimal EntryPrice=0m,decimal EntryAtr=0m,
        decimal EntryEquilibrium=0m,decimal FavorableExtreme=0m);
    private const string ResearchDomain="UNQUALIFIED_CAUSAL_MODEL_REPLAY_NOT_BROKER_EXECUTION";
    private readonly string researchMode;
    // Both independent economically motivated families below are fixed BEFORE
    // any new extended original-account data collection is opened.
    public NativeProductResearchLoop(string researchMode="FROZEN_LEGACY_M5_M15")
    {
        if(researchMode is not ("FROZEN_LEGACY_M5_M15" or
            "FX_CAUSAL_BREAKOUT_PLUS_RELATIVE_VALUE" or
            "FX_ONLY_BREAKOUT" or "FX_ONLY_RELATIVE_VALUE" or
            "FX_BREADTH_SHOCK_W45" or "FX_ONLY_BREADTH_W45" or
            "FX_ONLY_SHOCK_W45" or "FX_SHOCK_ABSORPTION_W36W37" or
            "FX_ONLY_SHOCK_W36W37" or "FX_ONLY_ABSORPTION_W36W37" or
            "CROSS_OIL_EQUITY_W30W31" or "CROSS_ONLY_OIL_W30W31" or
            "CROSS_ONLY_EQUITY_W30W31" or
            "CRYPTO_CRUDE_W24W25" or "ONLY_CRYPTO_W24W25" or
            "ONLY_CRUDE_W24W25"))
            throw new ArgumentException("UNDECLARED_RESEARCH_MECHANISM");
        this.researchMode=researchMode;
    }
    private NativeFundedSession session=new("NATIVE_PRODUCT_MODEL_REPLAY_ONLY");
    private NativeProductAdverseBook adverse=new();
    private readonly Dictionary<string,Tracked> tracked=new(StringComparer.Ordinal);
    private readonly Dictionary<string,long> previousForecastBar=new(StringComparer.Ordinal);
    private readonly Dictionary<string,long> lastSeenM5Bar=new(StringComparer.Ordinal);
    private int unobservedM5DecisionSlots,unresolvedCalendarGaps;
    private long maximumBarObservationLagMs;
    private bool historicalPathComplete=true;
    private decimal matchedLongBenchmarkNetEur;
    private bool benchmarkSettlementComplete=true;
    private readonly Dictionary<string,int> weekly=new(StringComparer.Ordinal);
    private readonly Dictionary<string,int> exitReasonCounts=new(StringComparer.Ordinal);
    private readonly List<NativeProductSignal> signals=new();
    private long lastClock=-1;
    private string epochId="EPISODE-"+Guid.NewGuid().ToString("N");
    private bool recoveredCheckpoint=false;
    private int eventSequence, forecasts, accepted, rejected;

    public NativeFundedSession ResearchSession=>session;
    public string ModelEpochId=>epochId;
    public long LastObservedAt=>lastClock;
    // This SHA-256 only detects accidental/unauthorised checkpoint mutation.
    // It is NOT a signature, custody receipt or evidence that missing prices
    // were observed. Caller must verify its source dataset independently.
    public string ExportIntegrityCheckpoint(string sourceDatasetSha256)
    {
        if(sourceDatasetSha256.Length!=64 ||
            !sourceDatasetSha256.All(Uri.IsHexDigit))
            throw new ArgumentException("MODEL_REPLAY_CHECKPOINT_SOURCE_SHA_MISSING");
        string payload=JsonSerializer.Serialize(new {
            Version="mxm-product-shadow-episode-v1",EpochId=epochId,
            SourceSha=sourceDatasetSha256,LastClock=lastClock,
            ExitReasonCounts=exitReasonCounts,
            Session=session.Checkpoint(),Adverse=adverse.Export(),
            Tracked=tracked,PreviousForecastBar=previousForecastBar,
            LastSeenM5=lastSeenM5Bar,Weekly=weekly,Signals=signals,
            EventSequence=eventSequence,Forecasts=forecasts,
            Accepted=accepted,Rejected=rejected,
            UnobservedM5=unobservedM5DecisionSlots,
            UnresolvedGaps=unresolvedCalendarGaps,
            MaxLag=maximumBarObservationLagMs,
            HistoryPathComplete=historicalPathComplete,
            Benchmark=matchedLongBenchmarkNetEur,
            BenchmarkSettlementComplete=benchmarkSettlementComplete,
            ResearchMode=researchMode
        });
        return JsonSerializer.Serialize(new {Payload=payload,Sha256=Fingerprint(payload)});
    }
    public static NativeProductResearchLoop RestoreIntegrityCheckpoint(
        string json,string expectedSourceDatasetSha256)
    {
        using var d=JsonDocument.Parse(json);
        var root=d.RootElement;
        var payload=root.GetProperty("Payload").GetString()??"";
        if(Fingerprint(payload)!=root.GetProperty("Sha256").GetString())
            throw new ArgumentException("MODEL_REPLAY_CHECKPOINT_INTEGRITY_MISMATCH");
        using var parsed=JsonDocument.Parse(payload);
        var p=parsed.RootElement;
        if(p.GetProperty("Version").GetString()!="mxm-product-shadow-episode-v1"||
           p.GetProperty("SourceSha").GetString()!=expectedSourceDatasetSha256)
            throw new ArgumentException("MODEL_REPLAY_CHECKPOINT_SOURCE_OR_VERSION_MISMATCH");
        var loop=new NativeProductResearchLoop(
            p.GetProperty("ResearchMode").GetString() ??
                "FROZEN_LEGACY_M5_M15");
        loop.epochId=p.GetProperty("EpochId").GetString()??throw new ArgumentException("MODEL_EPOCH_MISSING");
        loop.session=NativeFundedSession.Restore(
            p.GetProperty("Session").GetString()!,"NATIVE_PRODUCT_MODEL_REPLAY_ONLY");
        loop.adverse=NativeProductAdverseBook.Restore(p.GetProperty("Adverse").GetString()!);
        void Load<T>(Dictionary<string,T> target,string name)
        {
            var src=JsonSerializer.Deserialize<Dictionary<string,T>>(
                p.GetProperty(name).GetRawText())??throw new ArgumentException("MODEL_REPLAY_MISSING_STATE");
            foreach(var entry in src)target.Add(entry.Key,entry.Value);
        }
        Load(loop.tracked,"Tracked");
        Load(loop.previousForecastBar,"PreviousForecastBar");
        Load(loop.lastSeenM5Bar,"LastSeenM5");
        Load(loop.weekly,"Weekly");
        if(p.TryGetProperty("ExitReasonCounts",out _))
            Load(loop.exitReasonCounts,"ExitReasonCounts");
        loop.signals.AddRange(JsonSerializer.Deserialize<NativeProductSignal[]>(
            p.GetProperty("Signals").GetRawText())??Array.Empty<NativeProductSignal>());
        loop.eventSequence=p.GetProperty("EventSequence").GetInt32();
        loop.forecasts=p.GetProperty("Forecasts").GetInt32();
        loop.accepted=p.GetProperty("Accepted").GetInt32();
        loop.rejected=p.GetProperty("Rejected").GetInt32();
        loop.unobservedM5DecisionSlots=p.GetProperty("UnobservedM5").GetInt32();
        loop.unresolvedCalendarGaps=p.GetProperty("UnresolvedGaps").GetInt32();
        loop.maximumBarObservationLagMs=p.GetProperty("MaxLag").GetInt64();
        loop.historicalPathComplete=p.GetProperty("HistoryPathComplete").GetBoolean();
        loop.matchedLongBenchmarkNetEur=p.GetProperty("Benchmark").GetDecimal();
        loop.benchmarkSettlementComplete=p.GetProperty(
            "BenchmarkSettlementComplete").GetBoolean();
        loop.lastClock=p.GetProperty("LastClock").GetInt64();
        var money=loop.session.Ledger.Summary();
        var stress=loop.adverse.Summary;
        if(loop.lastClock<0||money.CashEur<=0||money.OpenPositions!=
            loop.tracked.Values.Count(x=>x.OpenAt>0)||
           (loop.adverse.Complete && stress is null))
            throw new ArgumentException("MODEL_REPLAY_CHECKPOINT_MONETARY_OR_CLOCK_MISMATCH");
        loop.recoveredCheckpoint=true;
        return loop;
    }
    public bool HistoricalPathComplete=>historicalPathComplete;
    public int UnobservedM5DecisionSlots=>unobservedM5DecisionSlots;
    public int UnresolvedCalendarGaps=>unresolvedCalendarGaps;
    public long MaxBarObservationLagMs=>maximumBarObservationLagMs;
    public NativeProductAdverseBook AdverseScenario=>adverse;
    private void ApplyFacts(LedgerEvent[] facts)
    {
        session.ApplyResearchFacts(facts);
        adverse.Apply(facts);
    }
    public string[] ActiveSymbols=>tracked.Values.Select(x=>x.Symbol)
        .Distinct(StringComparer.Ordinal).ToArray();
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
    private static bool ContractUsableForModel(NativeObservedContractTerms c)
        =>c.OriginalBrokerAuthenticated ||
            (!c.HistoricalTariffContinuityCertified && c.ObservedAtUtcMs>0);
    private static decimal? Financing(NativeObservedContractTerms c,
        long opened,long closed,int side,decimal units,
        decimal credit,decimal debit)
        =>c.OriginalBrokerAuthenticated
            ?NativeBrokerContractCosts.SignedFinancing(c,opened,closed,
                side,units,credit,debit)
            :NativeBrokerContractCosts.SignedFinancingCurrentAlgo(c,opened,closed,
                side,units,credit,debit);
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
               x.HoldingMinutes<15||x.HoldingMinutes>240||
               !NativeCausalExitResearch.Supported(x.ExitPolicy)))
            throw new ArgumentException("PRODUCT_REPLAY_NONCAUSAL_MARKET_CLOCK");
        // Do not silently bridge unobserved intrahorizon equity. Offline replay
        // can preserve a full path by supplying every historical decision clock;
        // Cloud restart creates an independent model epoch until such a path
        // and a verified checkpoint have been provided.
        if(lastClock>0 && at-lastClock>315000L)
        {
            historicalPathComplete=false;
            unresolvedCalendarGaps++;
        }
        // One coherent multiasset mark; no broker ledger/account state is ever
        // accessed or modified. No synthetic fill is created on the intent clock.
        ApplyFacts(new[]{Event("MARK",at,quotes:markets.Select(x=>x.Quote).ToArray())});
        var byName=markets.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        foreach(var outstanding in tracked.Values)
            if(!byName.ContainsKey(outstanding.Symbol))
            {
                // A missing held mark makes equity/financing history incomplete:
                // no forward-filled mark or fictitious model close is allowed.
                historicalPathComplete=false;
                unresolvedCalendarGaps++;
            }
        foreach(var id in tracked.Keys.ToArray())
        {
            var p=tracked[id];
            if(!byName.TryGetValue(p.Symbol,out var m))continue;
            var q=m.Quote;
            if(p.OpenAt==0 && at>=p.RequestAt+1000)
            {
                NativeExitSeed seed=new(0m,0m);
                if(p.ExitPolicy!=NativeCausalExitResearch.FrozenFixed &&
                   !NativeCausalExitResearch.TrySeed(m.M5,m.M15,at,out seed))
                {
                    // No fabricated missing ATR/equilibrium at model fill.
                    // Keep the original pending request, do not forge a fill.
                    historicalPathComplete=false;
                    continue;
                }
                decimal px=p.Side>0?q.Ask+p.SlippagePerSideQuote:q.Bid-p.SlippagePerSideQuote;
                ApplyFacts(new[]{Event("OPEN_FILL",at,id,p.Symbol,p.Side,
                    p.Units,px,Fee(q,p.Units),q.MarginPerUnit,p.SlippagePerSideQuote)});
                tracked[id]=p with {OpenAt=at,EntryQuote=q,
                    EntryPrice=px,EntryAtr=seed.AtrQuote,
                    EntryEquilibrium=seed.EquilibriumQuote,
                    FavorableExtreme=px};
            }
            else if(p.OpenAt>0 && p.CloseRequested && at>=p.RequestAt+1000)
            {
                // Contractual rollover is never guessed. Without a complete
                // financing model, hold the position as unknown, not zero-cost.
                var finance=Financing(p.Contract,
                    p.OpenAt,at,p.Side,p.Units,q.EurCredit,q.EurDebit);
                if(finance is null)continue;
                decimal px=p.Side>0?q.Bid-p.SlippagePerSideQuote:q.Ask+p.SlippagePerSideQuote;
                // Matched, fixed-side buy-and-hold benchmark on the *same*
                // observed entry/exit clock, units and model cost surface.
                // Counterfactual benchmark is descriptive, not separately
                // financed or independently validated.
                if(p.EntryQuote is LedgerQuote entry)
                {
                    decimal gross=(q.Bid-p.SlippagePerSideQuote-
                        entry.Ask-p.SlippagePerSideQuote)*p.Units;
                    decimal converted=gross*(gross>=0?q.EurCredit:q.EurDebit);
                    var longCarry=Financing(p.Contract,p.OpenAt,at,1,
                        p.Units,q.EurCredit,q.EurDebit);
                    if(longCarry is decimal carry)
                        matchedLongBenchmarkNetEur+=converted-
                            Fee(entry,p.Units)-Fee(q,p.Units)+carry;
                    else benchmarkSettlementComplete=false;
                }
                else benchmarkSettlementComplete=false;
                ApplyFacts(new[]{
                    Event("FINANCING",at,id,p.Symbol,p.Side,p.Units,
                        financing:finance.Value),
                    Event("CLOSE_FILL",at,id,p.Symbol,p.Side,p.Units,
                        px,Fee(q,p.Units),q.MarginPerUnit,p.SlippagePerSideQuote)
                });
                tracked.Remove(id);
                var k=Week(at);
                weekly[k]=weekly.GetValueOrDefault(k)+1;
            }
            else if(p.OpenAt>0 && !p.CloseRequested)
            {
                // A causal policy can invalidate/target/trail before the
                // exposure cap. Legacy reproduction retains its old clock.
                var verdict=NativeCausalExitResearch.Assess(p.ExitPolicy,
                    at,p.OpenAt,p.Side,p.EntryPrice>0m?p.EntryPrice:
                        (p.Side>0?q.Ask:q.Bid),
                    new NativeExitSeed(p.EntryAtr,p.EntryEquilibrium),
                    p.FavorableExtreme,q,m.M5,m.M15,p.HoldMinutes);
                tracked[id]=p with {FavorableExtreme=verdict.FavorableExtreme};
                if(verdict.RequestClose)
                {
                    ApplyFacts(new[]{Event("REQUEST_CLOSE",at,id,
                        p.Symbol,p.Side,p.Units,latency:1000)});
                    tracked[id]=tracked[id] with {
                        CloseRequested=true,RequestAt=at};
                    exitReasonCounts[verdict.Reason]=
                        exitReasonCounts.GetValueOrDefault(verdict.Reason)+1;
                }
            }
        }

        // Cross-sectional USD factor is defined only by the SAME known M15
        // clock of at least 3 USD-quoted account markets. The median of
        // completed normalized M15 returns is a causal benchmark, not a
        // fitted parameter or outcome-ranked symbol choice.
        var cross=markets.Where(x=>x.Contract?.QuoteAsset=="USD")
            .Select(x=>(x.Symbol,R:NativeCausalWarmup.Rebuild(
                new(x.Symbol,"M15",15,at,x.M15))))
            .Where(x=>x.R.Ready && x.R.NormalizedDrift is not null)
            .ToArray();
        decimal? crossMedian=null;
        if(cross.Length>=3)
        {
            var d=cross.Select(x=>x.R.NormalizedDrift!.Value)
                .OrderBy(v=>v).ToArray();
            crossMedian=d.Length%2==1?d[d.Length/2]:
                (d[d.Length/2-1]+d[d.Length/2])/2m;
        }
        var offered=new List<EconomicOpportunity>();
        var evidence=new List<SpecialistEuroEvidence>();
        var terms=new List<ResearchEntryTerms>();
        var recent=new List<NativeProductSignal>();
        foreach(var market in markets)
        {
            var p5=NativeCausalWarmup.Rebuild(new(market.Symbol,"M5",5,at,market.M5));
            var p15=NativeCausalWarmup.Rebuild(new(market.Symbol,"M15",15,at,market.M15));
            if(p5.Ready)
            {
                long old=lastSeenM5Bar.GetValueOrDefault(market.Symbol);
                if(old>0 && p5.LastClosedAt>old+300000L)
                {
                    // Only count unobserved completed slots, never fabricate
                    // the directions or profitability of missing signals.
                    if(p5.MissingIntervals==0)
                        unobservedM5DecisionSlots+=checked((int)(
                            (p5.LastClosedAt-old)/300000L-1));
                    else unresolvedCalendarGaps++;
                }
                if(old==0||p5.LastClosedAt>old)
                    lastSeenM5Bar[market.Symbol]=p5.LastClosedAt;
                maximumBarObservationLagMs=Math.Max(maximumBarObservationLagMs,
                    Math.Max(0,at-p5.LastClosedAt));
            }
            if(!p5.Ready || !p15.Ready || p5.NormalizedDrift is not decimal a ||
                p15.NormalizedDrift is not decimal b ||
                previousForecastBar.GetValueOrDefault(market.Symbol)==p5.LastClosedAt)
                continue;
            int side=0;string mechanism="FROZEN_LEGACY_M5_M15";
            decimal driver=Math.Abs(4m*a+b);
            if(researchMode=="FROZEN_LEGACY_M5_M15")
            {
                if(a*b<=0)continue;
                side=a>0?1:-1;
            }

            else if(researchMode is "CRYPTO_CRUDE_W24W25" or
                "ONLY_CRYPTO_W24W25" or "ONLY_CRUDE_W24W25")
            {
                // Two separate predeclared W24/W25 economic hypotheses.
                // Prior closed ETH H1 panic and oil 4H impulse families
                // are not invoked or rescored.
                if(market.M5.Length<9)continue;
                var window=market.M5.TakeLast(9).ToArray();
                var bar=window[^1];
                var previous=window.Take(8).ToArray();
                bool contiguous=bar.CloseAt<at &&
                    window.Zip(window.Skip(1)).All(x=>
                        x.First.CloseAt==x.Second.OpenAt);
                decimal range=bar.High-bar.Low;
                decimal priorAverageRange=previous.Average(x=>x.High-x.Low);
                decimal priorAverageVolume=previous.Average(x=>(decimal)x.TickVolume);
                decimal spreadNow=market.Quote.Ask-market.Quote.Bid;
                if(!contiguous||range<=0m||priorAverageRange<=0m||
                   priorAverageVolume<=0m)continue;
                if(market.Symbol=="ETHUSD" &&
                   researchMode!="ONLY_CRUDE_W24W25")
                {
                    decimal upper=bar.High-Math.Max(bar.Open,bar.Close);
                    decimal lower=Math.Min(bar.Open,bar.Close)-bar.Low;
                    decimal wick=Math.Max(upper,lower);
                    if(range<0.90m*priorAverageRange ||
                       wick<0.55m*range ||
                       bar.TickVolume<1.25m*priorAverageVolume ||
                       spreadNow>0.35m*range ||
                       (upper>lower?b<=0m:b>=0m))continue;
                    side=upper>lower?-1:1;
                    driver=wick/bar.Close;
                    mechanism="CRYPTO_M5_LIQUIDITY_WICK_ABSORPTION";
                }
                else if(market.Symbol=="SpotCrude" &&
                    researchMode!="ONLY_CRYPTO_W24W25")
                {
                    var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                    decimal drift=window[^1].Close-window[^4].Close;
                    decimal body=bar.Close-bar.Open;
                    if(utc.Hour<13||utc.Hour>=19 ||
                       Math.Abs(drift)<0.75m*priorAverageRange ||
                       drift*b<=0m || drift*body<=0m ||
                       bar.TickVolume<1.15m*priorAverageVolume ||
                       spreadNow>0.50m*range)continue;
                    side=drift>0m?1:-1;
                    driver=Math.Abs(drift)/bar.Close;
                    mechanism="CRUDE_US_SESSION_TICK_ACTIVITY_DRIFT";
                }
                else continue;
            }
            else if(researchMode is "CROSS_OIL_EQUITY_W30W31" or
                "CROSS_ONLY_OIL_W30W31" or "CROSS_ONLY_EQUITY_W30W31")
            {
                bool oil=false,equity=false;
                var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(researchMode!="CROSS_ONLY_EQUITY_W30W31" &&
                   market.Symbol=="SpotCrude" &&
                   utc.Hour>=8 && utc.Hour<17 &&
                   byName.TryGetValue("SpotBrent",out var brent) &&
                   market.M15.Length>=5 && brent.M15.Length>=5)
                {
                    // Shared same-clock completed M15 observations.
                    // Brent is pure context; never a phantom funded leg.
                    var cb=market.M15.TakeLast(5).ToArray();
                    var bb=brent.M15.TakeLast(5).ToArray();
                    bool common=cb[^1].CloseAt==bb[^1].CloseAt &&
                        cb[^1].CloseAt<at &&
                        cb.Zip(cb.Skip(1)).All(x=>
                            x.First.CloseAt==x.Second.OpenAt) &&
                        bb.Zip(bb.Skip(1)).All(x=>
                            x.First.CloseAt==x.Second.OpenAt);
                    var bw=NativeCausalWarmup.Rebuild(new(
                        "SpotBrent","M15",15,at,brent.M15));
                    decimal cr=cb[^1].Close/cb[0].Close-1m;
                    decimal br=bb[^1].Close/bb[0].Close-1m;
                    if(common && bw.Ready &&
                       bw.MeanAbsoluteReturn is decimal mean && mean>0 &&
                       Math.Abs(br)>4m*1.2m*mean &&
                       br*cr>0 && Math.Abs(cr)<0.65m*Math.Abs(br) &&
                       a*br>0)
                    {
                        side=br>0?1:-1;
                        driver=Math.Abs(br)-Math.Abs(cr);
                        oil=true;
                        mechanism="ENERGY_BRENT_TO_CRUDE_LAG";
                    }
                }
                if(researchMode!="CROSS_ONLY_OIL_W30W31" &&
                   market.Symbol=="AMD.US" &&
                   utc.Hour==14 && utc.Minute==30 &&
                   market.M5.Length>=12)
                {
                    // Predeclared summer US cash session: 13:30–14:30 UTC.
                    // Twelve REAL contiguous M5 source bars, each closed.
                    var openHour=market.M5.TakeLast(12).ToArray();
                    var begin=DateTimeOffset.FromUnixTimeMilliseconds(
                        openHour[0].OpenAt).UtcDateTime;
                    bool valid=begin.Hour==13 && begin.Minute==30 &&
                        openHour[^1].CloseAt<at &&
                        openHour.Zip(openHour.Skip(1)).All(x=>
                            x.First.CloseAt==x.Second.OpenAt);
                    decimal averageRange=openHour.Average(x=>x.High-x.Low);
                    decimal signedMove=openHour[^1].Close-openHour[0].Open;
                    long firstVolume=openHour.Take(6).Sum(x=>x.TickVolume);
                    long lastVolume=openHour.Skip(6).Sum(x=>x.TickVolume);
                    if(valid && averageRange>0 && firstVolume>0 &&
                       Math.Abs(signedMove)>=0.65m*averageRange &&
                       lastVolume>=1.15m*firstVolume &&
                       signedMove*b>0m)
                    {
                        side=signedMove>0?1:-1;
                        driver=Math.Abs(signedMove)/openHour[^1].Close;
                        equity=true;
                        mechanism="AMD_US_OPENING_HOUR_TICKFLOW";
                    }
                }
                if(!oil && !equity)continue;
            }
            else if(researchMode is "FX_BREADTH_SHOCK_W45" or
                "FX_ONLY_BREADTH_W45" or "FX_ONLY_SHOCK_W45" or
                "FX_SHOCK_ABSORPTION_W36W37" or
                "FX_ONLY_SHOCK_W36W37" or "FX_ONLY_ABSORPTION_W36W37")
            {
                // New prespecified, entirely separate W45 mechanisms.
                // No PR160 breakout signal is evaluated or rescued.
                bool breadth=false,shock=false;
                if(researchMode is "FX_BREADTH_SHOCK_W45" or
                    "FX_ONLY_BREADTH_W45" &&
                   cross.Length>=3 && crossMedian is decimal med &&
                   p15.MeanAbsoluteReturn is decimal mar && mar>0 &&
                   Math.Abs(med)>0.35m*mar && med*b>0 &&
                   Math.Abs(b)<0.60m*Math.Abs(med) &&
                   a*med>0 && Math.Abs(a)>0.25m*Math.Abs(med))
                {
                    side=med>0?1:-1;
                    driver=Math.Abs(med-b);
                    breadth=true;
                    mechanism="FX_USD_BREADTH_DELAYED_CATCHUP";
                }
                if(!breadth && researchMode is not (
                    "FX_ONLY_BREADTH_W45" or "FX_ONLY_ABSORPTION_W36W37") &&
                   market.M5.Length>=10)
                {
                    var shockWindow=market.M5.TakeLast(10).ToArray();
                    bool consecutive=shockWindow.Zip(shockWindow.Skip(1)).All(x=>
                        x.First.CloseAt==x.Second.OpenAt);
                    var last=shockWindow[^1];
                    // The eight bars immediately preceding the signal bar,
                    // not earlier bars or future outcome.
                    var prior=shockWindow.Skip(1).Take(8).ToArray();
                    decimal range=last.High-last.Low;
                    decimal priorRange=prior.Average(x=>x.High-x.Low);
                    decimal body=last.Close-last.Open;
                    decimal quoteSpread=market.Quote.Ask-market.Quote.Bid;
                    if(consecutive && range>0 && priorRange>0 &&
                       range>1.60m*priorRange &&
                       Math.Abs(body)>0.60m*range &&
                       Math.Sign(body)==Math.Sign(last.Close-shockWindow[^2].Close) &&
                       quoteSpread<=0.40m*range)
                    {
                        side=body>0?-1:1;
                        driver=Math.Abs(body)/last.Close;
                        shock=true;
                        mechanism="FX_M5_SHOCK_EXHAUSTION_REVERSION";
                    }
                }
                bool absorption=false;
                if(!breadth && !shock &&
                   researchMode is "FX_SHOCK_ABSORPTION_W36W37" or
                       "FX_ONLY_ABSORPTION_W36W37" &&
                   market.M5.Length>=10)
                {
                    // Prespecified W36/W37 absorption hypothesis. Entirely
                    // different from the frozen W45 wide shock: unusually
                    // active tick count with compressed range and small body.
                    var flowWindow=market.M5.TakeLast(9).ToArray();
                    bool flowContiguous=flowWindow.Zip(flowWindow.Skip(1))
                        .All(x=>x.First.CloseAt==x.Second.OpenAt);
                    var signalBar=flowWindow[^1];
                    var flowPrior=flowWindow.Take(8).ToArray();
                    decimal averageRange=flowPrior.Average(x=>x.High-x.Low);
                    decimal averageVolume=flowPrior.Average(x=>(decimal)x.TickVolume);
                    decimal signalRange=signalBar.High-signalBar.Low;
                    decimal recentDrift=flowPrior[^1].Close-flowPrior[^4].Close;
                    decimal liveSpread=market.Quote.Ask-market.Quote.Bid;
                    if(flowContiguous && averageRange>0 && averageVolume>0 &&
                       signalBar.TickVolume>=1.50m*averageVolume &&
                       signalRange>0 && signalRange<=0.95m*averageRange &&
                       Math.Abs(signalBar.Close-signalBar.Open)<=0.40m*signalRange &&
                       Math.Abs(recentDrift)>=0.65m*averageRange &&
                       recentDrift*b>0 &&
                       liveSpread<=0.40m*signalRange)
                    {
                        side=recentDrift>0?-1:1;
                        driver=Math.Abs(recentDrift)/signalBar.Close;
                        absorption=true;
                        mechanism="FX_HIGH_TICK_ACTIVITY_ABSORPTION";
                    }
                }
                if(!breadth && !shock && !absorption)continue;
            }
            else
            {
                // Family A: break of the PREVIOUS 8 completed M5 high/low,
                // accompanied by M15 drift in the same direction and a
                // contemporaneous range expansion relative to past M5 bars.
                // This is a price-extremum event, NOT retuning the legacy
                // M5/M15 directional-agreement strategy.
                bool breakout=false;
                if(market.M5.Length>=10 && p5.RelativeRange is decimal rr &&
                   rr>0 && market.M15.Length>=NativeCausalWarmup.WindowBars)
                {
                    var last=market.M5[^1];
                    var prior=market.M5.TakeLast(9).SkipLast(1).ToArray();
                    decimal upper=prior.Max(x=>x.High);
                    decimal lower=prior.Min(x=>x.Low);
                    decimal tr=(last.High-last.Low)/last.Open;
                    if(last.Close>upper && b>0 && tr>=rr*1.25m){side=1;breakout=true;
                        driver=(last.Close-upper)/last.Close+Math.Abs(b);}
                    else if(last.Close<lower && b<0 && tr>=rr*1.25m){side=-1;breakout=true;
                        driver=(lower-last.Close)/last.Close+Math.Abs(b);}
                }
                if(breakout && researchMode!="FX_ONLY_RELATIVE_VALUE")
                    mechanism="FX_CAUSAL_RANGE_EXPANSION_BREAK";
                else if(researchMode!="FX_ONLY_BREAKOUT" &&
                    market.Contract?.QuoteAsset=="USD" &&
                    crossMedian is decimal med &&
                    p15.MeanAbsoluteReturn is decimal mar && mar>0 &&
                    Math.Abs(b-med)>2m*mar &&
                    a*(b-med)<0)
                {
                    // Family B: a USD cross-sectional M15 factor residual
                    // with M5 reversion already visible; no clock-hour
                    // constant, no chosen winning instrument, no index
                    // dispersion, and a distinct FX relative-value rationale.
                    side=b>med?-1:1;
                    driver=Math.Abs(b-med);
                    mechanism="FX_CAUSAL_USD_FACTOR_RELATIVE_VALUE";
                }
                else continue;
            }
            previousForecastBar[market.Symbol]=p5.LastClosedAt;
            forecasts++;
            var q=market.Quote;
            if(market.Contract is not NativeObservedContractTerms c ||
               c.Symbol!=market.Symbol ||
               c.MinimumUnits<=0 || c.MinimumUnits>c.MaximumUnits ||
               !ContractUsableForModel(c))
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_COST_CONTRACT_NOT_AVAILABLE",
                    null,null,null,"SOURCE_OR_CONTRACT_UNATTESTED",mechanism));
                continue;
            }
            decimal units=c.MinimumUnits;
            string effectiveExitPolicy=mechanism switch {
                "FX_USD_BREADTH_DELAYED_CATCHUP"=>
                    NativeCausalExitResearch.VolatilityTarget,
                "FX_M5_SHOCK_EXHAUSTION_REVERSION"=>
                    NativeCausalExitResearch.EquilibriumReversion,
                "FX_HIGH_TICK_ACTIVITY_ABSORPTION"=>
                    NativeCausalExitResearch.VolatilityTarget,
                "ENERGY_BRENT_TO_CRUDE_LAG"=>
                    NativeCausalExitResearch.PredictionInvalidation,
                "AMD_US_OPENING_HOUR_TICKFLOW"=>
                    NativeCausalExitResearch.Chandelier,
                "CRYPTO_M5_LIQUIDITY_WICK_ABSORPTION"=>
                    NativeCausalExitResearch.VolatilityTarget,
                "CRUDE_US_SESSION_TICK_ACTIVITY_DRIFT"=>
                    NativeCausalExitResearch.PredictionInvalidation,
                _=>market.ExitPolicy
            };
            int effectiveHolding=mechanism switch {
                "FX_USD_BREADTH_DELAYED_CATCHUP"=>120,
                "FX_M5_SHOCK_EXHAUSTION_REVERSION"=>90,
                "FX_HIGH_TICK_ACTIVITY_ABSORPTION"=>75,
                "ENERGY_BRENT_TO_CRUDE_LAG"=>120,
                "AMD_US_OPENING_HOUR_TICKFLOW"=>180,
                "CRYPTO_M5_LIQUIDITY_WICK_ABSORPTION"=>150,
                "CRUDE_US_SESSION_TICK_ACTIVITY_DRIFT"=>120,
                _=>market.HoldingMinutes
            };
            if(effectiveExitPolicy!=NativeCausalExitResearch.FrozenFixed &&
               !NativeCausalExitResearch.TrySeed(market.M5,market.M15,
                    at,out _))
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,
                    "MODEL_CAUSAL_EXIT_EVIDENCE_MISSING",null,null,null,
                    "EXIT_ENTRY_WARMUP_OR_CALENDAR_INVALID",mechanism));
                continue;
            }
            if(tracked.Values.Any(x=>x.Symbol==market.Symbol))
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_SYMBOL_ALREADY_OPEN_OR_PENDING",
                    null,null,null,"SINGLE_POSITION_PER_SYMBOL",mechanism));
                continue;
            }
            decimal? signedFunding=Financing(
                c,at,at+effectiveHolding*60000L,side,units,q.EurCredit,q.EurDebit);
            if(signedFunding is null)
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_FUNDING_UNKNOWN",
                    null,null,null,"NO_UNPRICED_ROLLOVER",mechanism));
                continue;
            }
            decimal mid=(q.Bid+q.Ask)/2m;
            decimal fx=(q.EurCredit+q.EurDebit)/2m;
            // EXPLORATORY forecast, not a fitted/qualified alpha: agreement
            // between completed M5 and M15 direction, magnitude from past
            // normalized movement. No closing or future sample is consulted.
            decimal projectedGross=driver*mid*units*fx;
            decimal spread=(q.Ask-q.Bid)*units*fx;
            decimal commission=2m*Fee(q,units);
            decimal slippage=2m*market.SlippagePerSideQuote*units*fx;
            decimal fundingDebit=Math.Max(0,-signedFunding.Value);
            decimal conversion=projectedGross*
                Math.Max(0,q.EurDebit-q.EurCredit)/Math.Max(.00000001m,fx);
            decimal uncertainty=(researchMode=="FROZEN_LEGACY_M5_M15"?
                Math.Abs(a-b):Math.Abs(b)+(p15.MeanAbsoluteReturn??0m))*
                mid*units*fx+(p5.MeanAbsoluteReturn??0m)*mid*units*fx;
            decimal predictedNet=projectedGross-spread-commission-slippage-
                fundingDebit-conversion;
            decimal adverse=predictedNet-spread-slippage;
            string id="EXPLORATORY/"+mechanism+"/"+market.Symbol+"/"+p5.LastClosedAt;
            var baseClock=Math.Min(p5.LastClosedAt,p15.LastClosedAt);
            if(baseClock>=at-1)
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_FEATURE_UNAVAILABLE_BEFORE_DECISION",
                    projectedGross,predictedNet,adverse,"CAUSAL_CLOCK_UNSUPPORTED",mechanism));
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
            offered.Add(new EconomicOpportunity(id,mechanism,
                market.Symbol,id,side,at-1,baseClock,
                EvidenceLevel.Exploratory,false,grid,candidates));
            evidence.Add(new(id,baseClock,at-1,5,effectiveHolding,
                true,market.IndependentlySupportedAgainstBenchmark,true,true,
                false,projectedGross,uncertainty,spread,
                Fee(q,units),Fee(q,units),conversion,slippage,fundingDebit,minMargin));
            terms.Add(new(id,1000,market.SlippagePerSideQuote,Fingerprint(id)));
            recent.Add(new(market.Symbol,at,side,"MODEL_FORECAST_ONLY",
                projectedGross,predictedNet,adverse,
                market.IndependentlySupportedAgainstBenchmark?
                    "EXTERNAL_BENCHMARK_SUPPORT_SUPPLIED":"EXPLORATORY_NO_INDEPENDENT_BENCHMARK_SUPPORT",
                mechanism));
        }
        if(offered.Count>0)
        {
            var states=Enumerable.Range(0,8).Select(i=>
                new PortfolioScenario("STATE"+i,at-2,true,0m,0m,0m,0m)).ToArray();
            // Capital and risk are common across staggered decisions. All
            // genuinely held and pending positions are carried into EACH
            // joint adverse state; no independent-capital accounts, no hidden
            // exposure or diversification credit. These loss estimates remain
            // explicit conditional stress, NOT certified tail calibration.
            var held=session.Ledger.PositionSnapshot()
                .Select(p=>(Id:p.Id,p.Symbol,p.Side,p.Units,p.MarginPerUnit));
            var pending=session.Ledger.PendingSnapshot()
                .Where(p=>p.Kind=="REQUEST_OPEN")
                .Select(p=>(Id:p.PositionId,p.Symbol,p.Side,p.Units,
                    MarginPerUnit:p.MarginPerUnit));
            var exposures=new List<ResearchExposureScenarios>();
            foreach(var p in held.Concat(pending))
            {
                if(!byName.TryGetValue(p.Symbol,out var quoteEvidence))
                {
                    historicalPathComplete=false;
                    // Unknown held market facts stay blocked by native
                    // conservative exposure matching in DecideResearch.
                    continue;
                }
                var q=quoteEvidence.Quote;
                decimal margin=p.Units*Math.Max(p.MarginPerUnit,q.MarginPerUnit);
                decimal range=quoteEvidence.M5.Length>0?
                    quoteEvidence.M5[^1].High-quoteEvidence.M5[^1].Low:0m;
                decimal fx=(q.EurCredit+q.EurDebit)/2m;
                decimal loss=p.Units*(Math.Max(range,q.Ask-q.Bid)*fx*2m+
                    quoteEvidence.SlippagePerSideQuote*fx);
                exposures.Add(new(p.Id,p.Symbol,p.Side,p.Units,
                    states.Select(st=>st with {
                        KnownAt=at-2,NetEur=0m,LossEur=loss,
                        MarginEur=margin,PeakEur=0m
                    }).ToArray()));
            }
            var d=new NativeResearchDecision("PRODUCT/"+at,at,
                new ScenarioSizingInputs(300,300,300,1,1,1,1,1,2,0),
                states,offered.ToArray(),exposures.ToArray(),
                terms.ToArray(),Fingerprint("PRODUCT/"+at),evidence.ToArray());
            // Exact same prospectively gated path for independently supported
            // evidence. UNQUALIFIED shadow mode is explicit, never promoted.
            var conditional=EnableUnqualifiedShadowSimulation
                ?session.DecideResearch(d with {SpecialistEvidence=null})
                :session.DecideProspective(d);
            // Record precisely the existing core's accepted model intents in
            // a second adverse-cost replay of the SAME allocation/funding path.
            var decisions=conditional.Selection.Allocations
                .Select(x=>x.Id).ToHashSet(StringComparer.Ordinal);
            if(decisions.Count>0)
                adverse.Apply(session.Ledger.PendingSnapshot().Where(x=>
                    x.Kind=="REQUEST_OPEN" && decisions.Contains(x.PositionId))
                    .ToArray());
            accepted+=conditional.Selection.Allocations.Length;
            rejected+=conditional.Selection.Declined.Length;
            foreach(var chosen in conditional.Selection.Allocations)
            {
                var opportunity=offered.Single(x=>x.Id==chosen.Id);
                var market=byName[opportunity.Symbol];
                var plan=opportunity.Candidate switch {
                    "FX_USD_BREADTH_DELAYED_CATCHUP"=>
                        (Policy:NativeCausalExitResearch.VolatilityTarget,Minutes:120),
                    "FX_M5_SHOCK_EXHAUSTION_REVERSION"=>
                        (Policy:NativeCausalExitResearch.EquilibriumReversion,Minutes:90),
                    "FX_HIGH_TICK_ACTIVITY_ABSORPTION"=>
                        (Policy:NativeCausalExitResearch.VolatilityTarget,Minutes:75),
                    "ENERGY_BRENT_TO_CRUDE_LAG"=>
                        (Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:120),
                    "AMD_US_OPENING_HOUR_TICKFLOW"=>
                        (Policy:NativeCausalExitResearch.Chandelier,Minutes:180),
                    "CRYPTO_M5_LIQUIDITY_WICK_ABSORPTION"=>
                        (Policy:NativeCausalExitResearch.VolatilityTarget,Minutes:150),
                    "CRUDE_US_SESSION_TICK_ACTIVITY_DRIFT"=>
                        (Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:120),
                    _=>(Policy:market.ExitPolicy,Minutes:market.HoldingMinutes)
                };
                tracked.Add(chosen.Id,new(market.Symbol,opportunity.Direction,
                    chosen.Units,at,0,plan.Minutes,market.SlippagePerSideQuote,
                    market.Contract!,ExitPolicy:plan.Policy));
                var selectedIndex=recent.FindIndex(x=>x.Symbol==market.Symbol &&
                    x.Status=="MODEL_FORECAST_ONLY");
                if(selectedIndex>=0)
                    recent[selectedIndex]=recent[selectedIndex] with {
                        Status="SHADOW_MODEL_INTENT_ALLOCATED_NOT_TRADING",
                        DecisionReason=chosen.Reason
                    };
            }
            foreach(var declined in conditional.Selection.Declined)
            {
                var ix=recent.FindIndex(x=>declined.Id.EndsWith(
                    x.Symbol+"/"+previousForecastBar.GetValueOrDefault(x.Symbol)));
                if(ix>=0)recent[ix]=recent[ix] with {
                    Status="SHADOW_MODEL_INTENT_DECLINED_NOT_TRADING",
                    DecisionReason=declined.Reason};
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
        return new(at,forecasts,accepted,rejected,s.OpenPositions,s.PendingIntents,
            s.CompleteRoundTrips,s.CashEur,s.LiquidationEquityEur,
            closed.Sum(x=>x.GrossEur),s.ClosedNetEur,
            adverse.Summary?.ClosedNetEur,s.MaximumSampledDrawdown,
            new Dictionary<string,int>(weekly,StringComparer.Ordinal),recent,
            "EXPLORATORY_MODEL_ONLY_NOT_ORIGINAL_AUTHENTICATED_OR_BROKER_NET",
            ModelMatchedLongBenchmarkEur:benchmarkSettlementComplete?
                matchedLongBenchmarkNetEur:null,
            ModelIncrementalVsLongEur:benchmarkSettlementComplete?
                s.ClosedNetEur-matchedLongBenchmarkNetEur:null,
            AdversePathFullyRepriced:adverse.Complete,
            ObservedM5SlotsNotScored:unobservedM5DecisionSlots,
            MaxObservedM5LagMs:maximumBarObservationLagMs,
            HistoryPathComplete:historicalPathComplete,
            ModelEpochId:epochId,
            ContinuityBoundary:recoveredCheckpoint?
                "VERIFIED_INTEGRITY_CHECKPOINT_SAME_SOURCE_EPOCH_NOT_BROKER_CERTIFIED":
                "NEW_ISOLATED_MODEL_EPOCH_NOT_CLOUD_HISTORY_CONTINUATION",
            UnresolvedCalendarGaps:unresolvedCalendarGaps,
            ModelExitReasons:new Dictionary<string,int>(exitReasonCounts,StringComparer.Ordinal));
    }
}
