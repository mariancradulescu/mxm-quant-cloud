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
    Dictionary<string,int>? ModelExitReasons=null,
    decimal? ModelMatchedShortBenchmarkEur=null,
    decimal? ModelMatchedOppositeSignalBenchmarkEur=null);

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
    private readonly NativeEntryOutcomeCalibration? calibration;
    private readonly long calibrationBoundary;
    public NativeEntryCalibrationReport? CalibrationReport=>calibration?.Report();
    // Both independent economically motivated families below are fixed BEFORE
    // any new extended original-account data collection is opened.
    public NativeProductResearchLoop(string researchMode="FROZEN_LEGACY_M5_M15",long calibrationBoundary=0)
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
            "ONLY_CRUDE_W24W25" or
            "US_INDEX_JOINT_W20W21" or "US_INDEX_NAS_ONLY_W20W21" or
            "US_INDEX_SP_ONLY_W20W21" or
            "NG_AUD_JOINT_W38W39" or "NG_ONLY_W38W39" or
            "AUD_ONLY_W38W39" or
            "HK_BRENT_JOINT_W40W41" or "HK_ONLY_W40W41" or
            "BRENT_ONLY_W40W41" or
            "CAL1_JOINT" or "CAL1_FX" or "CAL1_COMMODITY" or "CAL1_LONG" or "CAL1_SHORT" or "CAL1_CASH" or
            "WFG1_JOINT" or "WFG1_FX" or "WFG1_COMMODITY" or "WFG1_LONG" or "WFG1_SHORT" or
            "WFG1_FX_LONG" or "WFG1_FX_SHORT" or "WFG1_COMMODITY_LONG" or "WFG1_COMMODITY_SHORT" or
            "WFG1_CASH" or
            "SCT1_JOINT" or "SCT1_INDEX" or "SCT1_OIL" or "SCT1_LONG" or "SCT1_SHORT" or "SCT1_REPEATED" or
            "JRS1_JOINT" or "JRS1_FX" or "JRS1_COMMODITY" or "JRS1_LONG" or "JRS1_SHORT" or "JRS1_REPEATED" or
            "FCE1_JOINT" or "FCE1_FX" or "FCE1_COMMODITY" or "FCE1_LONG" or "FCE1_SHORT" or "FCE1_MINIMUM" or
            "PRR1_JOINT" or "PRR1_INDEX" or "PRR1_CRUDE" or "PRR1_LONG" or "PRR1_SHORT" or
            "BMR1_JOINT" or "BMR1_FX" or "BMR1_GOLD" or "BMR1_LONG" or "BMR1_SHORT" or
            "MCT2_JOINT" or "MCT2_CRYPTO" or "MCT2_METAL" or "MCT2_LONG" or "MCT2_SHORT" or
            "OTC1_JOINT" or "OTC1_OIL" or "OTC1_FX" or "OTC1_LONG" or "OTC1_SHORT" or
            "JRC1_JOINT" or "JRC1_RISK" or "JRC1_REVERSION" or "JRC1_LONG" or "JRC1_SHORT" or
            "LDP1_JOINT" or "LDP1_SILVER" or "LDP1_FX" or "LDP1_LONG" or "LDP1_SHORT" or
            "RRP1_JOINT" or "RRP1_EQUITY" or "RRP1_GOLD" or
            "BRENT_AMD_JOINT_W42W43" or
            "ONLY_BRENT_W42W43" or "ONLY_AMD_W42W43"))
            throw new ArgumentException("UNDECLARED_RESEARCH_MECHANISM");
        this.researchMode=researchMode;
        if(researchMode.StartsWith("CAL1_",StringComparison.Ordinal))
        {
            this.calibrationBoundary=calibrationBoundary>0?calibrationBoundary:
                NativeEntryOutcomeCalibration.DevelopmentBoundary;
            calibration=new(this.calibrationBoundary);
        }
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
    private decimal matchedShortBenchmarkNetEur;
    private decimal matchedInverseBenchmarkNetEur;
    private bool benchmarkSettlementComplete=true;
    private readonly Dictionary<string,int> weekly=new(StringComparer.Ordinal);
    private readonly Dictionary<string,int> exitReasonCounts=new(StringComparer.Ordinal);
    private readonly List<NativeProductSignal> signals=new();
    private long lastClock=-1;
    private string epochId="EPISODE-"+Guid.NewGuid().ToString("N");
    private bool recoveredCheckpoint=false;
    private int eventSequence, forecasts, accepted, rejected;
    public int UnfinancedModelOpenCancellations {get;private set;}
    public int DistinctHistoricalStressDecisions {get;private set;}
    public int DistinctHistoricalStressDecisionsWithExposure {get;private set;}

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
            UnfinancedModelOpenCancellations,
            UnobservedM5=unobservedM5DecisionSlots,
            UnresolvedGaps=unresolvedCalendarGaps,
            MaxLag=maximumBarObservationLagMs,
            HistoryPathComplete=historicalPathComplete,
            Benchmark=matchedLongBenchmarkNetEur,
            MatchedShort=matchedShortBenchmarkNetEur,
            MatchedInverse=matchedInverseBenchmarkNetEur,
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
        if(p.TryGetProperty("UnfinancedModelOpenCancellations",out var cancellations))
            loop.UnfinancedModelOpenCancellations=cancellations.GetInt32();
        loop.unobservedM5DecisionSlots=p.GetProperty("UnobservedM5").GetInt32();
        loop.unresolvedCalendarGaps=p.GetProperty("UnresolvedGaps").GetInt32();
        loop.maximumBarObservationLagMs=p.GetProperty("MaxLag").GetInt64();
        loop.historicalPathComplete=p.GetProperty("HistoryPathComplete").GetBoolean();
        loop.matchedLongBenchmarkNetEur=p.GetProperty("Benchmark").GetDecimal();
        loop.matchedShortBenchmarkNetEur=p.TryGetProperty("MatchedShort",out var shortB)
            ?shortB.GetDecimal():0m;
        loop.matchedInverseBenchmarkNetEur=p.TryGetProperty("MatchedInverse",out var invertedB)
            ?invertedB.GetDecimal():0m;
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
    private static decimal? RrpHourMove(NativeClosedMarketBar[] bars,long at)
    {
        var window=bars.TakeLast(5).ToArray();
        if(window.Length!=5 || window[^1].CloseAt!=at-1500L ||
           window.Zip(window.Skip(1)).Any(pair=>pair.First.CloseAt!=pair.Second.OpenAt))
            return null;
        return window[^1].Close/window[0].Close-1m;
    }
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
        var calibrationSetups=calibration?.Observe(at,markets);
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
                if(calibration is not null && at-p.RequestAt>=600000L)
                {
                    ApplyFacts(new[]{Event("CONFIRMED_CANCEL",at,id,p.Symbol,p.Side,p.Units) with {
                        Reason="CALIBRATION_ENTRY_QUOTE_TOO_LATE"
                    }});
                    tracked.Remove(id);
                    continue;
                }
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
                try
                {
                    ApplyFacts(new[]{Event("OPEN_FILL",at,id,p.Symbol,p.Side,
                        p.Units,px,Fee(q,p.Units),q.MarginPerUnit,p.SlippagePerSideQuote)});
                }
                catch(InvalidOperationException ex) when(
                    (calibration is not null || researchMode.StartsWith("LDP1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("JRC1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("OTC1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("MCT2_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("WFG1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("SCT1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("JRS1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("FCE1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("PRR1_",StringComparison.Ordinal) ||
                     researchMode.StartsWith("BMR1_",StringComparison.Ordinal)) &&
                    ex.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL")
                {
                    // ApplyResearchFacts is transactional. Record the refused
                    // model fill as a cancellation in both books, without a fee.
                    ApplyFacts(new[]{Event("CONFIRMED_CANCEL",at,id,p.Symbol,p.Side,p.Units) with {
                        Reason="MODEL_MARGIN_RECHECK_AT_FILL_FAILED"
                    }});
                    tracked.Remove(id);
                    UnfinancedModelOpenCancellations++;
                    continue;
                }
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
                    var shortCarry=Financing(p.Contract,p.OpenAt,at,-1,
                        p.Units,q.EurCredit,q.EurDebit);
                    decimal shortGross=(entry.Bid-p.SlippagePerSideQuote-
                        q.Ask-p.SlippagePerSideQuote)*p.Units;
                    decimal shortConverted=shortGross*(shortGross>=0?
                        q.EurCredit:q.EurDebit);
                    decimal fees=Fee(entry,p.Units)+Fee(q,p.Units);
                    if(longCarry is decimal carry && shortCarry is decimal shortFunding)
                    {
                        decimal longNet=converted-fees+carry;
                        decimal shortNet=shortConverted-fees+shortFunding;
                        matchedLongBenchmarkNetEur+=longNet;
                        matchedShortBenchmarkNetEur+=shortNet;
                        matchedInverseBenchmarkNetEur+=p.Side>0?shortNet:longNet;
                    }
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
        bool sessionStudy=researchMode.StartsWith("SCT1_",StringComparison.Ordinal);
        bool fundingGateStudy=researchMode.StartsWith("WFG1_",StringComparison.Ordinal);
        bool jointStudy=fundingGateStudy || sessionStudy || researchMode.StartsWith("JRS1_",StringComparison.Ordinal);
        bool useJointStress=jointStudy && researchMode is not ("JRS1_REPEATED" or "SCT1_REPEATED");
        var stressEuro=jointStudy?byName.GetValueOrDefault("EURUSD"):null;
        bool factorStudy=researchMode.StartsWith("FCE1_",StringComparison.Ordinal);
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
            decimal a=p5.NormalizedDrift??0m,b=p15.NormalizedDrift??0m;
            if((calibration is null && (!p5.Ready || !p15.Ready ||
                p5.NormalizedDrift is null || p15.NormalizedDrift is null)) ||
                previousForecastBar.GetValueOrDefault(market.Symbol)==p5.LastClosedAt)
                continue;
            int side=0;string mechanism="FROZEN_LEGACY_M5_M15";
            decimal driver=Math.Abs(4m*a+b);
            NativeEntryForecast? calibratedForecast=null;
            bool directionalControl=researchMode is "CAL1_LONG" or "CAL1_SHORT";
            if(calibration is not null)
            {
                if(at<calibrationBoundary || researchMode=="CAL1_CASH" ||
                   !calibrationSetups!.TryGetValue(market.Symbol,out var setup))continue;
                var family=NativeEntryOutcomeCalibration.Family(market.Symbol)!;
                if((researchMode=="CAL1_FX" && family!="FX") ||
                   (researchMode=="CAL1_COMMODITY" && family!="COMMODITY"))continue;
                calibratedForecast=setup.Forecast;
                side=directionalControl?(researchMode=="CAL1_LONG"?1:-1):calibratedForecast?.Direction??0;
                mechanism="CAL1_"+family;
                if(side==0)
                {
                    forecasts++;rejected++;
                    recent.Add(new(market.Symbol,at,0,"MODEL_CALIBRATION_UNAVAILABLE",
                        null,null,null,"INSUFFICIENT_MATURE_TRAINING_DAYS",mechanism));
                    continue;
                }
            }
            else if(researchMode=="FROZEN_LEGACY_M5_M15")
            {
                if(a*b<=0)continue;
                side=a>0?1:-1;
            }


            else if(researchMode is "US_INDEX_JOINT_W20W21" or
                "US_INDEX_NAS_ONLY_W20W21" or "US_INDEX_SP_ONLY_W20W21")
            {
                // W20–W21 source-locked US index 1-hour-equivalent (4x
                // completed M15) microstructure. These hypotheses are NOT
                // the closed Asian index synch or classic FX breakout rules.
                var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(utc.Hour<14 || utc.Hour>=19 || 
                   (utc.Hour==14 && utc.Minute<30))continue;
                if(market.Symbol=="NAS100" &&
                   researchMode!="US_INDEX_SP_ONLY_W20W21" &&
                   byName.TryGetValue("US500",out var broad) &&
                   market.M15.Length>=5 && broad.M15.Length>=5)
                {
                    var nas=market.M15.TakeLast(5).ToArray();
                    var sp=broad.M15.TakeLast(5).ToArray();
                    bool aligned=nas[^1].CloseAt<at &&
                        sp[^1].CloseAt==nas[^1].CloseAt &&
                        nas.Zip(nas.Skip(1)).All(x=>
                            x.First.CloseAt==x.Second.OpenAt) &&
                        sp.Zip(sp.Skip(1)).All(x=>
                            x.First.CloseAt==x.Second.OpenAt);
                    if(!aligned)continue;
                    decimal nasReturn=nas[^1].Close/nas[0].Close-1m;
                    decimal spReturn=sp[^1].Close/sp[0].Close-1m;
                    decimal residual=nasReturn-spReturn;
                    if(Math.Abs(residual)<0.00035m)continue;
                    side=residual>0m?-1:1;
                    driver=Math.Abs(residual);
                    mechanism="NAS100_US_CASH_INDEX_RELATIVE_DISPERSION_FADE";
                }
                else if(market.Symbol=="US500" &&
                    researchMode!="US_INDEX_NAS_ONLY_W20W21" &&
                    market.M15.Length>=16)
                {
                    // No synthetic H1 bars: 4 contiguous completed M15
                    // closes define the H1-equivalent market regime.
                    var bars=market.M15.TakeLast(16).ToArray();
                    if(!bars.Zip(bars.Skip(1)).All(x=>
                            x.First.CloseAt==x.Second.OpenAt) ||
                       bars[^1].CloseAt>=at)continue;
                    var prior=bars.Take(12).ToArray();
                    var current=bars.Skip(12).ToArray();
                    decimal oldRange=prior.Average(x=>
                        (x.High-x.Low)/x.Close);
                    decimal newRange=current.Average(x=>
                        (x.High-x.Low)/x.Close);
                    decimal oldVolume=prior.Average(x=>(decimal)x.TickVolume);
                    decimal change=current[^1].Close/prior[^1].Close-1m;
                    decimal meanReturn=prior.Zip(prior.Skip(1))
                        .Average(x=>Math.Abs(x.Second.Close/
                            x.First.Close-1m));
                    decimal lastMove=current[^1].Close-current[^1].Open;
                    if(oldRange<=0m || oldVolume<=0m ||
                       newRange<1.10m*oldRange ||
                       Math.Abs(change)<meanReturn ||
                       change*lastMove<=0m ||
                       current[^1].TickVolume<0.90m*oldVolume)continue;
                    side=change>0m?1:-1;
                    driver=Math.Abs(change);
                    mechanism="US500_US_CASH_H1_VOLATILITY_PERSISTENCE";
                }
                else continue;
            }
            else if(fundingGateStudy)
            {
                bool isFx=NativeLiquidityRegimeResearch.IsFx(market.Symbol);
                if(researchMode=="WFG1_CASH" ||
                   (isFx && researchMode.StartsWith("WFG1_COMMODITY",StringComparison.Ordinal)) ||
                   (!isFx && researchMode.StartsWith("WFG1_FX",StringComparison.Ordinal)))
                    continue;
                var forecast=NativeLiquidityRegimeResearch.Forecast(market,stressEuro,at);
                if(forecast.Side==0)continue;
                side=researchMode.EndsWith("_LONG",StringComparison.Ordinal)?1:
                    researchMode.EndsWith("_SHORT",StringComparison.Ordinal)?-1:forecast.Side;
                driver=forecast.Magnitude;
                mechanism=forecast.Mechanism;
            }
            else if(sessionStudy)
            {
                bool isIndex=NativeCashTransmissionResearch.IsIndex(market.Symbol);
                if((isIndex && researchMode=="SCT1_OIL") ||
                   (!isIndex && researchMode=="SCT1_INDEX"))continue;
                var forecast=NativeCashTransmissionResearch.Forecast(market,byName,at);
                if(forecast.Side==0)continue;
                side=researchMode=="SCT1_LONG"?1:
                    researchMode=="SCT1_SHORT"?-1:forecast.Side;
                driver=forecast.Magnitude;
                mechanism=forecast.Mechanism;
            }
            else if(jointStudy)
            {
                bool isFx=NativeRelativeRotationResearch.IsFx(market.Symbol);
                if((isFx && researchMode=="JRS1_COMMODITY") ||
                   (!isFx && researchMode=="JRS1_FX"))continue;
                var forecast=NativeRelativeRotationResearch.Forecast(market,byName,at);
                if(forecast.Side==0)continue;
                side=researchMode=="JRS1_LONG"?1:
                    researchMode=="JRS1_SHORT"?-1:forecast.Side;
                driver=forecast.Magnitude;
                mechanism=forecast.Mechanism;
            }
            else if(factorStudy)
            {
                bool isFx=NativeFactorExhaustionResearch.IsFx(market.Symbol);
                if((isFx && researchMode=="FCE1_COMMODITY") ||
                   (!isFx && researchMode=="FCE1_FX"))continue;
                var forecast=NativeFactorExhaustionResearch.Forecast(market,
                    byName.GetValueOrDefault("EURUSD"),at);
                if(forecast.Side==0)continue;
                side=researchMode=="FCE1_LONG"?1:
                    researchMode=="FCE1_SHORT"?-1:forecast.Side;
                driver=forecast.Magnitude;
                mechanism=forecast.Mechanism;
            }
            else if(researchMode.StartsWith("PRR1_",StringComparison.Ordinal))
            {
                if(market.Symbol is not ("US2000" or "SpotCrude") ||
                    (market.Symbol=="US2000" && researchMode=="PRR1_CRUDE") ||
                    (market.Symbol=="SpotCrude" && researchMode=="PRR1_INDEX"))
                    continue;
                var forecast=NativePullbackRangeResearch.Forecast(market,
                    byName.GetValueOrDefault("US500"),at);
                if(forecast.Side==0)continue;
                side=researchMode=="PRR1_LONG"?1:
                    researchMode=="PRR1_SHORT"?-1:forecast.Side;
                driver=forecast.Magnitude;
                mechanism=forecast.Mechanism;
            }
            else if(researchMode is "BMR1_JOINT" or "BMR1_FX" or "BMR1_GOLD" or
                "BMR1_LONG" or "BMR1_SHORT")
            {
                var clock=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(clock.Hour!=12 || clock.Minute!=45 || p5.LastClosedAt!=at-1500L ||
                   !byName.TryGetValue("EURUSD",out var euro) ||
                   !byName.TryGetValue("GBPUSD",out var sterling))continue;
                decimal Pulse(NativeProductMarket input)
                {
                    if(input.M15.Length==0 || input.M15[^1].CloseAt!=at-1500L)
                        return 0m;
                    var bar=input.M15[^1];
                    return bar.Close/bar.Open-1m;
                }
                decimal euroPulse=Pulse(euro),sterlingPulse=Pulse(sterling);
                if(Math.Abs(euroPulse)<.0008m || Math.Abs(sterlingPulse)<.0006m ||
                   euroPulse*sterlingPulse<=0m)continue;
                if(market.Symbol=="EURUSD" && researchMode!="BMR1_GOLD")
                {
                    side=Math.Sign(euroPulse);driver=Math.Abs(euroPulse);
                    mechanism="BMR1_EURUSD_RELEASE_PRICE_DISCOVERY";
                }
                else if(market.Symbol=="XAUUSD" && researchMode!="BMR1_FX")
                {
                    decimal goldPulse=Pulse(market);
                    if(Math.Abs(goldPulse)<.0015m || euroPulse*goldPulse<=0m)continue;
                    side=Math.Sign(goldPulse);driver=Math.Abs(goldPulse);
                    mechanism="BMR1_XAUUSD_RELEASE_REPRICING";
                }
                else continue;
                if(researchMode=="BMR1_LONG")side=1;
                if(researchMode=="BMR1_SHORT")side=-1;
            }
            else if(researchMode is "MCT2_JOINT" or "MCT2_CRYPTO" or "MCT2_METAL" or
                "MCT2_LONG" or "MCT2_SHORT")
            {
                var clock=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(clock.Hour<13 || clock.Hour>=17 || p5.LastClosedAt!=at-1500L ||
                   RrpHourMove(market.M15,at) is not decimal own)continue;
                var window=market.M15.TakeLast(17).ToArray();
                if(window.Length!=17 || window.Zip(window.Skip(1))
                    .Any(x=>x.First.CloseAt!=x.Second.OpenAt))continue;
                var last=window[^1];
                if(market.Symbol=="ETHUSD" && researchMode!="MCT2_METAL" &&
                   byName.TryGetValue("NAS100",out var nas) &&
                   RrpHourMove(nas.M15,at) is decimal equity && Math.Abs(equity)<=.0008m)
                {
                    decimal fourHours=last.Close/window[0].Close-1m;
                    if(Math.Abs(fourHours)<.004m || Math.Abs(own)<.0015m ||
                       own*fourHours<=0m || own*(last.Close-last.Open)<=0m)continue;
                    side=Math.Sign(own);driver=Math.Abs(own);
                    mechanism="MCT2_ETH_CRYPTO_SPECIFIC_PERSISTENCE";
                }
                else if(market.Symbol=="XAUUSD" && researchMode!="MCT2_CRYPTO" &&
                        byName.TryGetValue("EURUSD",out var euro) &&
                        RrpHourMove(euro.M15,at) is decimal dollarMove && Math.Abs(dollarMove)>=.0004m)
                {
                    var compressed=window.Skip(12).Take(4).ToArray();
                    var previous=window.Skip(8).Take(4).ToArray();
                    decimal high=compressed.Max(x=>x.High),low=compressed.Min(x=>x.Low);
                    decimal priorWidth=previous.Max(x=>x.High)-previous.Min(x=>x.Low);
                    if(priorWidth<=0m || high-low>.60m*priorWidth)continue;
                    side=last.Close>high && dollarMove>0m?1:last.Close<low && dollarMove<0m?-1:0;
                    if(side==0)continue;
                    driver=Math.Abs(last.Close-last.Open)/last.Open;
                    mechanism="MCT2_XAU_DOLLAR_CONFIRMED_RANGE_RELEASE";
                }
                else continue;
                if(researchMode=="MCT2_LONG")side=1;
                if(researchMode=="MCT2_SHORT")side=-1;
            }
            else if(researchMode is "OTC1_JOINT" or "OTC1_OIL" or "OTC1_FX" or
                "OTC1_LONG" or "OTC1_SHORT")
            {
                var clock=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(clock.Hour<13 || clock.Hour>=17 || p5.LastClosedAt!=at-1500L ||
                   RrpHourMove(market.M15,at) is not decimal own)continue;
                var last=market.M15[^1];
                if(market.Symbol=="SpotCrude" && researchMode!="OTC1_FX" &&
                   byName.TryGetValue("SpotBrent",out var brent) &&
                   RrpHourMove(brent.M15,at) is decimal peer &&
                   Math.Abs(peer)<=.0010m && Math.Abs(own-peer)>=.0025m &&
                   (own-peer)*(last.Close-last.Open)<0m)
                {
                    side=-Math.Sign(own-peer);driver=Math.Abs(own-peer);
                    mechanism="OTC1_WTI_LOCAL_BASIS_REVERSION";
                }
                else if(market.Symbol=="GBPUSD" && researchMode!="OTC1_OIL" &&
                   byName.TryGetValue("EURUSD",out var eur) &&
                   RrpHourMove(eur.M15,at) is decimal euro &&
                   Math.Abs(euro)>=.0005m && own*euro>0m &&
                   Math.Abs(own)>=Math.Abs(euro)+.0007m &&
                   own*(last.Close-last.Open)>0m)
                {
                    side=Math.Sign(own);driver=Math.Abs(own);
                    mechanism="OTC1_GBP_RELATIVE_STRENGTH_CONTINUATION";
                }
                else continue;
                if(researchMode=="OTC1_LONG")side=1;
                if(researchMode=="OTC1_SHORT")side=-1;
            }
            else if(researchMode is "JRC1_JOINT" or "JRC1_RISK" or "JRC1_REVERSION" or
                "JRC1_LONG" or "JRC1_SHORT")
            {
                var clock=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(clock.Hour<7 || clock.Hour>=11 || p5.LastClosedAt!=at-1500L ||
                   RrpHourMove(market.M15,at) is not decimal own)continue;
                if(market.Symbol=="EURJPY" && researchMode!="JRC1_REVERSION" &&
                   byName.TryGetValue("AUDJPY",out var risk) &&
                   byName.TryGetValue("EURUSD",out var eur) &&
                   RrpHourMove(risk.M15,at) is decimal riskMove &&
                   RrpHourMove(eur.M15,at) is decimal euroMove &&
                   Math.Abs(riskMove)>=.0015m && Math.Abs(own)>=.0010m &&
                   Math.Abs(euroMove)<=.0004m && riskMove*own>0m &&
                   own*(market.M15[^1].Close-market.M15[^1].Open)>0m)
                {
                    side=Math.Sign(own);driver=Math.Abs(riskMove);
                    mechanism="JRC1_EURJPY_JPY_RISK_PARTICIPATION";
                }
                else if(market.Symbol=="USDJPY" && researchMode!="JRC1_RISK")
                {
                    var window=market.M15.TakeLast(5).ToArray();
                    if(window.Length!=5 || Math.Abs(own)<.0015m)continue;
                    decimal priorRange=window.Take(4).Average(x=>x.High-x.Low);
                    var last=window[^1];
                    if(priorRange<=0 || last.High-last.Low<1.5m*priorRange ||
                       own*(last.Close-last.Open)>=0m)continue;
                    side=-Math.Sign(own);driver=Math.Abs(own);
                    mechanism="JRC1_USDJPY_VOLATILITY_CLIMAX_UNWIND";
                }
                else continue;
                if(researchMode=="JRC1_LONG")side=1;
                if(researchMode=="JRC1_SHORT")side=-1;
            }
            else if(researchMode is "LDP1_JOINT" or "LDP1_SILVER" or "LDP1_FX" or
                "LDP1_LONG" or "LDP1_SHORT")
            {
                var clock=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(clock.Hour<7 || clock.Hour>=11 || p5.LastClosedAt!=at-1500L ||
                   RrpHourMove(market.M15,at) is not decimal own)
                    continue;
                if(market.Symbol=="XAGUSD" && researchMode!="LDP1_FX" &&
                   byName.TryGetValue("EURUSD",out var eur) &&
                   RrpHourMove(eur.M15,at) is decimal eurMove &&
                   Math.Abs(own)>=.002m && Math.Abs(eurMove)>=.0004m &&
                   own*eurMove>0m && Math.Sign(market.M15[^1].Close-market.M15[^1].Open)==Math.Sign(own))
                {
                    side=Math.Sign(own);
                    driver=Math.Abs(own);
                    mechanism="LDP1_SILVER_USD_REPRICING";
                }
                else if(market.Symbol=="NZDUSD" && researchMode!="LDP1_SILVER" &&
                        byName.TryGetValue("AUDUSD",out var aud) &&
                        RrpHourMove(aud.M15,at) is decimal audMove &&
                        Math.Abs(audMove)<=.0005m && Math.Abs(own-audMove)>=.0009m)
                {
                    decimal residual=own-audMove;
                    decimal last=market.M15[^1].Close-market.M15[^1].Open;
                    if(last*residual>=0m)continue;
                    side=-Math.Sign(residual);
                    driver=Math.Abs(residual);
                    mechanism="LDP1_NZD_LOCAL_INVENTORY_UNWIND";
                }
                else continue;
                if(researchMode=="LDP1_LONG")side=1;
                if(researchMode=="LDP1_SHORT")side=-1;
            }
            else if(researchMode is "RRP1_JOINT" or "RRP1_EQUITY" or "RRP1_GOLD")
            {
                var clock=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(clock.TimeOfDay<TimeSpan.FromMinutes(870) ||
                   clock.TimeOfDay>=TimeSpan.FromHours(18) ||
                   p5.LastClosedAt!=at-1500L ||
                   !byName.TryGetValue("US500",out var broad))
                    continue;
                decimal? broadMove=RrpHourMove(broad.M15,at);
                if(broadMove is not decimal broadReturn)continue;
                if(market.Symbol=="US500" && researchMode!="RRP1_GOLD" &&
                   byName.TryGetValue("NAS100",out var lead) &&
                   RrpHourMove(lead.M15,at) is decimal leadReturn &&
                   Math.Abs(leadReturn)>=.0015m &&
                   broadReturn*leadReturn>=0m &&
                   Math.Abs(broadReturn)<=Math.Abs(leadReturn)*.5m)
                {
                    side=Math.Sign(leadReturn);
                    driver=Math.Abs(leadReturn-broadReturn);
                    mechanism="RRP1_US500_LEADERSHIP_TRANSMISSION";
                }
                else if(market.Symbol=="XAUUSD" && researchMode!="RRP1_EQUITY" &&
                        RrpHourMove(market.M15,at) is decimal goldReturn &&
                        Math.Abs(broadReturn)>=.0015m &&
                        Math.Abs(goldReturn)>=.0010m && goldReturn*broadReturn<0m)
                {
                    side=Math.Sign(goldReturn);
                    driver=Math.Abs(goldReturn);
                    mechanism="RRP1_XAUUSD_DEFENSIVE_ROTATION";
                }
                else continue;
            }
            else if(researchMode is "BRENT_AMD_JOINT_W42W43" or
                "ONLY_BRENT_W42W43" or "ONLY_AMD_W42W43")
            {
                // Immutable source-frozen 2026-W42/W43 new families.
                // Distinct from old Brent-to-Crude lag, energy 4H H1 impulse,
                // AMD first-hour momentum and failed HK index W40/W41.
                var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(market.M15.Length<13 ||
                   market.M15[^1].CloseAt+1500L!=at)continue;
                var day=utc.Date;
                if(market.Symbol=="SpotBrent" &&
                   researchMode!="ONLY_AMD_W42W43" &&
                   utc.Hour>=10 && utc.Hour<15)
                {
                    long openStart=new DateTimeOffset(day.AddHours(7),
                        TimeSpan.Zero).ToUnixTimeMilliseconds();
                    long openStop=openStart+120*60000L;
                    var morning=market.M15.Where(x=>x.OpenAt>=openStart &&
                        x.CloseAt<=openStop).ToArray();
                    if(morning.Length!=8 || morning[0].OpenAt!=openStart ||
                       morning[^1].CloseAt!=openStop ||
                       !morning.Zip(morning.Skip(1)).All(x=>
                           x.First.CloseAt==x.Second.OpenAt))continue;
                    decimal start=morning[0].Open;
                    decimal end=morning[^1].Close;
                    decimal impulse=end-start;
                    decimal averageRange=morning.Average(x=>x.High-x.Low);
                    decimal averageTicks=morning.Average(x=>(decimal)x.TickVolume);
                    var last=market.M15[^1];
                    decimal lastRange=last.High-last.Low;
                    decimal spreadObserved=market.Quote.Ask-market.Quote.Bid;
                    if(averageRange<=0m||averageTicks<=0m||
                       Math.Abs(impulse)<averageRange || lastRange<=0m ||
                       last.CloseAt<openStop ||
                       last.TickVolume<0.65m*averageTicks ||
                       spreadObserved>0.35m*lastRange ||
                       impulse*(last.Close-last.Open)<=0m)continue;
                    // Opposite impulse retracement 40%-80% of first drive.
                    decimal pullback=(end-last.Close)/impulse;
                    if(pullback<0.40m || pullback>0.80m)continue;
                    side=impulse>0m?1:-1;
                    driver=Math.Abs(impulse)/last.Close;
                    mechanism="SPOTBRENT_EU_MORNING_DRIVE_PULLBACK_CONTINUATION";
                }
                else if(market.Symbol=="AMD.US" &&
                   researchMode!="ONLY_BRENT_W42W43" &&
                   utc.Hour>=17 && (utc.Hour<19 ||
                       (utc.Hour==19 && utc.Minute<=30)) &&
                   market.M15.Length>=13)
                {
                    var group=market.M15.TakeLast(13).ToArray();
                    if(!group.Zip(group.Skip(1)).All(x=>
                         x.First.CloseAt==x.Second.OpenAt))continue;
                    var p=group.Take(8).ToArray();
                    var compress=group.Skip(8).Take(4).ToArray();
                    var latest=group[^1];
                    if(DateTimeOffset.FromUnixTimeMilliseconds(group[0].OpenAt)
                           .UtcDateTime.Date!=day)continue;
                    decimal baseRange=p.Average(x=>x.High-x.Low);
                    decimal baseVolume=p.Average(x=>(decimal)x.TickVolume);
                    decimal contraction=compress.Average(x=>x.High-x.Low);
                    decimal upper=p.Max(x=>x.High);
                    decimal lower=p.Min(x=>x.Low);
                    decimal latestRange=latest.High-latest.Low;
                    decimal spreadObserved=market.Quote.Ask-market.Quote.Bid;
                    if(baseRange<=0m||baseVolume<=0m||latestRange<=0m||
                       contraction>0.85m*baseRange ||
                       latest.TickVolume<1.10m*baseVolume ||
                       spreadObserved>0.35m*latestRange ||
                       compress.Any(x=>x.High>upper+0.10m*baseRange ||
                           x.Low<lower-0.10m*baseRange))continue;
                    if(latest.Close>upper+0.05m*baseRange &&
                       latest.Close>latest.Open)
                    {
                        side=1;
                        driver=(latest.Close-upper)/latest.Close;
                    }
                    else if(latest.Close<lower-0.05m*baseRange &&
                        latest.Close<latest.Open)
                    {
                        side=-1;
                        driver=(lower-latest.Close)/latest.Close;
                    }
                    else continue;
                    mechanism="AMD_US_LATE_CASH_COMPRESSION_BREAK_TICK_ACCELERATION";
                }
                else continue;
            }
            else if(researchMode is "HK_BRENT_JOINT_W40W41" or
                "HK_ONLY_W40W41" or "BRENT_ONLY_W40W41")
            {
                // Protocol-fixed HK cash opening range false-break and
                // European Brent range expansion. Both are globally exposed
                // 2026-W40/W41 development, NEVER independent confirmation.
                var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                if(market.M15.Length<16 || 
                   market.M15[^1].CloseAt+1500L!=at)continue;
                if(market.Symbol=="HK50" &&
                   researchMode!="BRENT_ONLY_W40W41" &&
                   utc.Hour>=2 && (utc.Hour>2 || utc.Minute>=15) &&
                   (utc.Hour<3 || (utc.Hour==3 && utc.Minute<=30)))
                {
                    var day=utc.Date;
                    long openStart=new DateTimeOffset(day.AddHours(1).AddMinutes(30),
                        TimeSpan.Zero).ToUnixTimeMilliseconds();
                    long openStop=openStart+30*60000L;
                    var opening=market.M15.Where(x=>x.OpenAt>=openStart &&
                        x.CloseAt<=openStop).ToArray();
                    if(opening.Length!=2 ||
                       opening[0].OpenAt!=openStart ||
                       opening[^1].CloseAt!=openStop ||
                       opening[0].CloseAt!=opening[1].OpenAt)continue;
                    var bar=market.M15[^1];
                    if(bar.OpenAt<openStop)continue;
                    decimal high=Math.Max(opening[0].High,opening[1].High);
                    decimal low=Math.Min(opening[0].Low,opening[1].Low);
                    decimal averageRange=opening.Average(x=>x.High-x.Low);
                    decimal averageVolume=opening.Average(x=>(decimal)x.TickVolume);
                    decimal barRange=bar.High-bar.Low;
                    decimal openingSpread=market.Quote.Ask-market.Quote.Bid;
                    if(averageRange<=0m || averageVolume<=0m ||
                       barRange<=0m || bar.TickVolume<0.70m*averageVolume ||
                       openingSpread>0.35m*barRange ||
                       bar.Close<=low || bar.Close>=high)continue;
                    if(bar.High>=high+0.10m*averageRange && 
                       bar.Close<bar.Open)
                    {
                        side=-1;
                        driver=(bar.High-high)/bar.Close;
                    }
                    else if(bar.Low<=low-0.10m*averageRange &&
                        bar.Close>bar.Open)
                    {
                        side=1;
                        driver=(low-bar.Low)/bar.Close;
                    }
                    else continue;
                    mechanism="HK50_HK_CASH_OPEN_RANGE_FALSE_BREAK_REVERSION";
                }
                else if(market.Symbol=="SpotBrent" &&
                    researchMode!="HK_ONLY_W40W41" &&
                    utc.Hour>=7 && utc.Hour<12)
                {
                    var sixteen=market.M15.TakeLast(16).ToArray();
                    if(!sixteen.Zip(sixteen.Skip(1)).All(x=>
                        x.First.CloseAt==x.Second.OpenAt))continue;
                    var prior=sixteen.Take(12).ToArray();
                    var current=sixteen.Skip(12).ToArray();
                    decimal oldRange=prior.Average(x=>(x.High-x.Low)/x.Close);
                    decimal newRange=current.Average(x=>(x.High-x.Low)/x.Close);
                    decimal oldActivity=prior.Average(x=>(decimal)x.TickVolume);
                    decimal oldMeanAbs=prior.Zip(prior.Skip(1)).Average(x=>
                        Math.Abs(x.Second.Close/x.First.Close-1m));
                    decimal move=current[^1].Close/prior[^1].Close-1m;
                    decimal latestBody=current[^1].Close-current[^1].Open;
                    decimal latestBarRange=current[^1].High-current[^1].Low;
                    decimal brentSpread=market.Quote.Ask-market.Quote.Bid;
                    if(oldRange<=0m || oldActivity<=0m || oldMeanAbs<=0m ||
                       latestBarRange<=0m ||
                       newRange<1.25m*oldRange ||
                       Math.Abs(move)<1.10m*oldMeanAbs ||
                       move*latestBody<=0m ||
                       current[^1].TickVolume<1.10m*oldActivity ||
                       brentSpread>0.35m*latestBarRange)continue;
                    side=move>0m?1:-1;
                    driver=Math.Abs(move);
                    mechanism="SPOTBRENT_EU_OPEN_RANGE_EXPANSION_CONTINUATION";
                }
                else continue;
            }
            else if(researchMode is "NG_AUD_JOINT_W38W39" or
                "NG_ONLY_W38W39" or "AUD_ONLY_W38W39")
            {
                // Predeclared 2026-W38/W39 economic *development*, NOT independent.
                // NatGas: H1 compression around prior-three-hour equilibrium.
                // AUDUSD: session-specific 02–05 UTC late-Asia range sweep
                // rejected on a completed M15 bar, NOT FX M5 shock or breadth.
                var utc=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
                var newest=market.M15[^1];
                if(newest.CloseAt>=at || newest.CloseAt<=0)continue;
                if(market.Symbol=="NatGas" &&
                   researchMode!="AUD_ONLY_W38W39" &&
                   utc.Hour>=13 && utc.Hour<19 && market.M15.Length>=16)
                {
                    var bars=market.M15.TakeLast(16).ToArray();
                    if(!bars.Zip(bars.Skip(1)).All(x=>
                        x.First.CloseAt==x.Second.OpenAt))continue;
                    var prior=bars.Take(12).ToArray();
                    var current=bars.Skip(12).ToArray();
                    decimal oldRange=prior.Average(x=>x.High-x.Low);
                    decimal recentRange=current.Average(x=>x.High-x.Low);
                    decimal mean=prior.Average(x=>x.Close);
                    decimal oldVolume=prior.Average(x=>(decimal)x.TickVolume);
                    decimal deviation=mean-current[^1].Close;
                    decimal body=current[^1].Close-current[^1].Open;
                    decimal gasSpread=market.Quote.Ask-market.Quote.Bid;
                    if(oldRange<=0m || oldVolume<=0m ||
                       recentRange>0.75m*oldRange ||
                       Math.Abs(deviation)<1.25m*oldRange ||
                       deviation*body<=0m ||
                       current[^1].TickVolume<0.75m*oldVolume ||
                       gasSpread>0.50m*(current[^1].High-current[^1].Low))
                        continue;
                    side=deviation>0m?1:-1;
                    driver=Math.Abs(deviation)/current[^1].Close;
                    mechanism="NATGAS_US_LIQUIDITY_VOL_COMPRESSION_REVERSION";
                }
                else if(market.Symbol=="AUDUSD" &&
                    researchMode!="NG_ONLY_W38W39" &&
                    utc.Hour>=7 &&
                    (utc.Hour<9 || (utc.Hour==9 && utc.Minute<=30)))
                {
                    // The 33-bar feature prefix covers the full 02–05 range
                    // at every allowed 07:00–09:30 UTC decision clock.
                    var date=utc.Date;
                    long start=new DateTimeOffset(date.AddHours(2),TimeSpan.Zero)
                        .ToUnixTimeMilliseconds();
                    long stop=new DateTimeOffset(date.AddHours(5),TimeSpan.Zero)
                        .ToUnixTimeMilliseconds();
                    var asia=market.M15.Where(x=>x.OpenAt>=start &&
                        x.CloseAt<=stop).ToArray();
                    if(asia.Length!=12||asia[0].OpenAt!=start||
                       asia[^1].CloseAt!=stop||
                       !asia.Zip(asia.Skip(1)).All(x=>
                           x.First.CloseAt==x.Second.OpenAt))continue;
                    decimal high=asia.Max(x=>x.High);
                    decimal low=asia.Min(x=>x.Low);
                    decimal meanRange=asia.Average(x=>x.High-x.Low);
                    decimal volume=asia.Average(x=>(decimal)x.TickVolume);
                    var bar=market.M15[^1];
                    decimal barRange=bar.High-bar.Low;
                    decimal asiaSpread=market.Quote.Ask-market.Quote.Bid;
                    if(meanRange<=0m||volume<=0m||barRange<=0m||
                       bar.TickVolume<0.85m*volume||
                       asiaSpread>0.40m*barRange)continue;
                    if(bar.High>=high+0.15m*meanRange &&
                       bar.Close<high && bar.Close>low &&
                       bar.Close<bar.Open)
                    {
                        side=-1;
                        driver=(bar.High-high)/bar.Close;
                    }
                    else if(bar.Low<=low-0.15m*meanRange &&
                       bar.Close>low && bar.Close<high &&
                       bar.Close>bar.Open)
                    {
                        side=1;
                        driver=(low-bar.Low)/bar.Close;
                    }
                    else continue;
                    mechanism="AUDUSD_LATE_ASIA_LONDON_SWEEP_FAILURE";
                }
                else continue;
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
            long signalBarClock=calibration is null?p5.LastClosedAt:calibrationSetups![market.Symbol].KnownAt;
            previousForecastBar[market.Symbol]=signalBarClock;
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
                "SPOTBRENT_EU_MORNING_DRIVE_PULLBACK_CONTINUATION"=>
                    NativeCausalExitResearch.VolatilityTarget,
                "AMD_US_LATE_CASH_COMPRESSION_BREAK_TICK_ACCELERATION"=>
                    NativeCausalExitResearch.Chandelier,
                "HK50_HK_CASH_OPEN_RANGE_FALSE_BREAK_REVERSION"=>
                    NativeCausalExitResearch.EquilibriumReversion,
                "SPOTBRENT_EU_OPEN_RANGE_EXPANSION_CONTINUATION"=>
                    NativeCausalExitResearch.Chandelier,
                "NATGAS_US_LIQUIDITY_VOL_COMPRESSION_REVERSION"=>
                    NativeCausalExitResearch.EquilibriumReversion,
                "AUDUSD_LATE_ASIA_LONDON_SWEEP_FAILURE"=>
                    NativeCausalExitResearch.VolatilityTarget,
                "NAS100_US_CASH_INDEX_RELATIVE_DISPERSION_FADE"=>
                    NativeCausalExitResearch.EquilibriumReversion,
                "US500_US_CASH_H1_VOLATILITY_PERSISTENCE"=>
                    NativeCausalExitResearch.Chandelier,
                "RRP1_US500_LEADERSHIP_TRANSMISSION"=>NativeCausalExitResearch.PredictionInvalidation,
                "RRP1_XAUUSD_DEFENSIVE_ROTATION"=>NativeCausalExitResearch.VolatilityTarget,
                "LDP1_SILVER_USD_REPRICING"=>NativeCausalExitResearch.Chandelier,
                "LDP1_NZD_LOCAL_INVENTORY_UNWIND"=>NativeCausalExitResearch.EquilibriumReversion,
                "JRC1_EURJPY_JPY_RISK_PARTICIPATION"=>NativeCausalExitResearch.PredictionInvalidation,
                "JRC1_USDJPY_VOLATILITY_CLIMAX_UNWIND"=>NativeCausalExitResearch.EquilibriumReversion,
                "OTC1_WTI_LOCAL_BASIS_REVERSION"=>NativeCausalExitResearch.EquilibriumReversion,
                "OTC1_GBP_RELATIVE_STRENGTH_CONTINUATION"=>NativeCausalExitResearch.PredictionInvalidation,
                "MCT2_ETH_CRYPTO_SPECIFIC_PERSISTENCE"=>NativeCausalExitResearch.Chandelier,
                "MCT2_XAU_DOLLAR_CONFIRMED_RANGE_RELEASE"=>NativeCausalExitResearch.PredictionInvalidation,
                "BMR1_EURUSD_RELEASE_PRICE_DISCOVERY"=>NativeCausalExitResearch.PredictionInvalidation,
                "BMR1_XAUUSD_RELEASE_REPRICING"=>NativeCausalExitResearch.PredictionInvalidation,
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
                "SPOTBRENT_EU_MORNING_DRIVE_PULLBACK_CONTINUATION"=>150,
                "AMD_US_LATE_CASH_COMPRESSION_BREAK_TICK_ACCELERATION"=>120,
                "HK50_HK_CASH_OPEN_RANGE_FALSE_BREAK_REVERSION"=>105,
                "SPOTBRENT_EU_OPEN_RANGE_EXPANSION_CONTINUATION"=>120,
                "NATGAS_US_LIQUIDITY_VOL_COMPRESSION_REVERSION"=>105,
                "AUDUSD_LATE_ASIA_LONDON_SWEEP_FAILURE"=>120,
                "NAS100_US_CASH_INDEX_RELATIVE_DISPERSION_FADE"=>105,
                "US500_US_CASH_H1_VOLATILITY_PERSISTENCE"=>180,
                "RRP1_US500_LEADERSHIP_TRANSMISSION"=>90,
                "RRP1_XAUUSD_DEFENSIVE_ROTATION"=>120,
                "LDP1_SILVER_USD_REPRICING"=>60,
                "LDP1_NZD_LOCAL_INVENTORY_UNWIND"=>60,
                "JRC1_EURJPY_JPY_RISK_PARTICIPATION"=>60,
                "JRC1_USDJPY_VOLATILITY_CLIMAX_UNWIND"=>60,
                "OTC1_WTI_LOCAL_BASIS_REVERSION"=>60,
                "OTC1_GBP_RELATIVE_STRENGTH_CONTINUATION"=>60,
                "MCT2_ETH_CRYPTO_SPECIFIC_PERSISTENCE"=>60,
                "MCT2_XAU_DOLLAR_CONFIRMED_RANGE_RELEASE"=>60,
                "BMR1_EURUSD_RELEASE_PRICE_DISCOVERY"=>45,
                "BMR1_XAUUSD_RELEASE_REPRICING"=>45,
                _=>market.HoldingMinutes
            };
            NativeExitSeed decisionSeed=new(0m,0m);
            if(effectiveExitPolicy!=NativeCausalExitResearch.FrozenFixed &&
               !NativeCausalExitResearch.TrySeed(market.M5,market.M15,
                    at,out decisionSeed))
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
            decimal projectedGross=(calibration is null?driver:calibratedForecast?.MeanGrossReturn??0m)*mid*units*fx;
            decimal spread=(q.Ask-q.Bid)*units*fx;
            decimal commission=2m*Fee(q,units);
            decimal slippage=2m*market.SlippagePerSideQuote*units*fx;
            decimal fundingDebit=Math.Max(0,-signedFunding.Value);
            decimal conversion=(calibration is null?projectedGross:Math.Abs(projectedGross))*
                Math.Max(0,q.EurDebit-q.EurCredit)/Math.Max(.00000001m,fx);
            decimal uncertainty=calibratedForecast is not null?
                calibratedForecast.MeanUncertaintyReturn*mid*units*fx:(researchMode=="FROZEN_LEGACY_M5_M15"?
                Math.Abs(a-b):Math.Abs(b)+(p15.MeanAbsoluteReturn??0m))*
                mid*units*fx+(p5.MeanAbsoluteReturn??0m)*mid*units*fx;
            decimal predictedNet=projectedGross-spread-commission-slippage-
                fundingDebit-conversion;
            decimal adverse=predictedNet-spread-slippage;
            string id="EXPLORATORY/"+mechanism+"/"+market.Symbol+"/"+signalBarClock;
            var baseClock=calibration is not null?(calibratedForecast?.OutcomesKnownThrough??signalBarClock):fundingGateStudy?Math.Max(p5.LastClosedAt,p15.LastClosedAt)
                :Math.Min(p5.LastClosedAt,p15.LastClosedAt);
            if(baseClock>=at-1)
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_FEATURE_UNAVAILABLE_BEFORE_DECISION",
                    projectedGross,predictedNet,adverse,"CAUSAL_CLOCK_UNSUPPORTED",mechanism));
                continue;
            }
            decimal minMargin=q.MarginPerUnit*units;
            var grid=new AdaptiveRiskInputs(300m,0m,300m,units,c.VolumeStepUnits,
                factorStudy && researchMode!="FCE1_MINIMUM"
                    ?Math.Min(c.MaximumUnits,units+c.VolumeStepUnits):units,
                q.MarginPerUnit,0m,false,false,2,0m);
            decimal perUnit=(predictedNet-uncertainty)/(factorStudy||jointStudy?units:Math.Max(1,units))*.5m;
            if(calibration is not null)
            {
                // Underwrite at doubled execution costs, consistently with the
                // adverse book; this is a conservative price assumption.
                decimal minFee=Fee(q,units);
                decimal conversionStress=conversion+(.001m*Math.Abs(projectedGross));
                decimal costs=2m*(spread+commission+slippage+fundingDebit)+conversionStress;
                decimal benchmarkGross=(calibratedForecast?.MeanBenchmarkGrossReturn??0m)*mid*units*fx;
                adverse=projectedGross-costs;
                // Round conservatively so EUR -> physical units -> EUR cannot
                // cross the evidence ceiling through decimal operation order.
                decimal standalone=projectedGross-costs-uncertainty;
                decimal incremental=projectedGross-benchmarkGross-costs-uncertainty;
                perUnit=directionalControl?.001m:
                    Math.Floor(1000000000m*Math.Min(standalone,incremental)/units)/1000000000m;
                decimal downside=Math.Max(1.5m*decisionSeed.AtrQuote,
                    (calibratedForecast?.DownsideReturn??0m)*mid);
                var scenarios=Enumerable.Range(0,8).Select(i=>new OpportunityScenario(
                    "STATE"+i,baseClock,true,perUnit,0m,downside*q.EurDebit+costs/units,0m)).ToArray();
                offered.Add(new(id,mechanism,market.Symbol,id,side,at-1,baseClock,
                    EvidenceLevel.Preliminary,false,grid,scenarios));
                evidence.Add(new SpecialistEuroEvidence(id,signalBarClock,at,60,effectiveHolding,
                    true,true,true,true,false,projectedGross-benchmarkGross,uncertainty,
                    2m*spread,2m*minFee,2m*minFee,conversionStress,2m*slippage,2m*fundingDebit,minMargin)
                    {GrossStandaloneEur=projectedGross});
                terms.Add(new(id,1000,market.SlippagePerSideQuote,Fingerprint(id)));
                recent.Add(new(market.Symbol,at,side,"MODEL_FORECAST_ONLY",
                    projectedGross,predictedNet,adverse,directionalControl?
                    "FUNDED_DIRECTIONAL_CONTROL_NO_PREDICTIVE_CLAIM":"LOCKED_POST_ENTRY_CALIBRATION",mechanism));
                continue;
            }
            decimal riskPerUnit=factorStudy||jointStudy
                ? (1.5m*decisionSeed.AtrQuote+q.Ask-q.Bid+
                    2m*market.SlippagePerSideQuote)*q.EurDebit+commission/units
                : Math.Abs(a)*mid*fx*.25m+.00001m;
            var shocks=jointStudy?NativeHistoricalJointStress.Observe(market,stressEuro,side,at):null;
            if(jointStudy && shocks is null)
            {
                rejected++;
                recent.Add(new(market.Symbol,at,side,"MODEL_JOINT_STRESS_HISTORY_MISSING",
                    projectedGross,predictedNet,adverse,"SOURCE_JOINT_STRESS_HISTORY_MISSING",mechanism));
                continue;
            }
            decimal meanShock=shocks?.Average(x=>x.NetPerUnit)??0m;
            var candidates=useJointStress
                ?shocks!.Select(x=>new OpportunityScenario(x.Id,x.KnownAt,true,
                    perUnit+x.NetPerUnit-meanShock,0m,riskPerUnit+x.LossPerUnit,x.PeakPerUnit)).ToArray()
                :Enumerable.Range(0,8).Select(i=>
                    new OpportunityScenario("STATE"+i,baseClock,true,perUnit,0m,
                        riskPerUnit,0m)).ToArray();
            offered.Add(new EconomicOpportunity(id,mechanism,
                market.Symbol,id,side,at-1,baseClock,
                EvidenceLevel.Exploratory,false,grid,candidates));
            // This market adapter has a gross forecast, but no measured
            // benchmark excess. A caller's support flag cannot supply it.
            evidence.Add(new(id,baseClock,at-1,5,effectiveHolding,
                true,false,true,true,
                false,null,uncertainty,spread,
                Fee(q,units),Fee(q,units),conversion,slippage,fundingDebit,minMargin));
            terms.Add(new(id,1000,market.SlippagePerSideQuote,Fingerprint(id)));
            recent.Add(new(market.Symbol,at,side,"MODEL_FORECAST_ONLY",
                projectedGross,predictedNet,adverse,
                "EXPLORATORY_NO_MEASURED_BENCHMARK_EXCESS",mechanism));
        }
        if(offered.Count>0)
        {
            var states=Enumerable.Range(0,8).Select(i=>
                new PortfolioScenario((useJointStress?"ALIGNED_H15_":"STATE")+i,
                    at-2,true,0m,0m,0m,0m)).ToArray();
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
                var shocks=jointStudy?NativeHistoricalJointStress.Observe(
                    quoteEvidence,stressEuro,p.Side,at):null;
                if(jointStudy && shocks is null)continue;
                exposures.Add(new(p.Id,p.Symbol,p.Side,p.Units,useJointStress
                    ?shocks!.Select(x=>new PortfolioScenario(x.Id,x.KnownAt,true,
                        x.NetPerUnit*p.Units,loss+x.LossPerUnit*p.Units,
                        x.PeakPerUnit*p.Units,margin)).ToArray()
                    :states.Select(st=>st with {
                        KnownAt=at-2,NetEur=0m,LossEur=loss,
                        MarginEur=margin,PeakEur=0m
                    }).ToArray()));
            }
            if(useJointStress && offered.Any(x=>x.Scenarios.Select(v=>
                (v.NetPerUnitEur,v.LossPerUnitEur,v.PeakPerUnitEur)).Distinct().Count()>1))
            {
                DistinctHistoricalStressDecisions++;
                if(exposures.Count>0)DistinctHistoricalStressDecisionsWithExposure++;
            }
            var d=new NativeResearchDecision("PRODUCT/"+at,at,
                new ScenarioSizingInputs(300,300,300,1,1,1,1,1,2,0),
                states,offered.ToArray(),exposures.ToArray(),
                terms.ToArray(),Fingerprint("PRODUCT/"+at),evidence.ToArray());
            // Exact same prospectively gated path for independently supported
            // evidence. UNQUALIFIED shadow mode is explicit, never promoted.
            var conditional=(calibration is null?EnableUnqualifiedShadowSimulation:
                researchMode is "CAL1_LONG" or "CAL1_SHORT")
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
                    "SPOTBRENT_EU_MORNING_DRIVE_PULLBACK_CONTINUATION"=>
                        (Policy:NativeCausalExitResearch.VolatilityTarget,Minutes:150),
                    "AMD_US_LATE_CASH_COMPRESSION_BREAK_TICK_ACCELERATION"=>
                        (Policy:NativeCausalExitResearch.Chandelier,Minutes:120),
                    "HK50_HK_CASH_OPEN_RANGE_FALSE_BREAK_REVERSION"=>
                        (Policy:NativeCausalExitResearch.EquilibriumReversion,Minutes:105),
                    "SPOTBRENT_EU_OPEN_RANGE_EXPANSION_CONTINUATION"=>
                        (Policy:NativeCausalExitResearch.Chandelier,Minutes:120),
                    "NATGAS_US_LIQUIDITY_VOL_COMPRESSION_REVERSION"=>
                        (Policy:NativeCausalExitResearch.EquilibriumReversion,Minutes:105),
                    "AUDUSD_LATE_ASIA_LONDON_SWEEP_FAILURE"=>
                        (Policy:NativeCausalExitResearch.VolatilityTarget,Minutes:120),
                    "NAS100_US_CASH_INDEX_RELATIVE_DISPERSION_FADE"=>
                        (Policy:NativeCausalExitResearch.EquilibriumReversion,Minutes:105),
                    "US500_US_CASH_H1_VOLATILITY_PERSISTENCE"=>
                        (Policy:NativeCausalExitResearch.Chandelier,Minutes:180),
                    "RRP1_US500_LEADERSHIP_TRANSMISSION"=>(Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:90),
                    "RRP1_XAUUSD_DEFENSIVE_ROTATION"=>(Policy:NativeCausalExitResearch.VolatilityTarget,Minutes:120),
                    "LDP1_SILVER_USD_REPRICING"=>(Policy:NativeCausalExitResearch.Chandelier,Minutes:60),
                    "LDP1_NZD_LOCAL_INVENTORY_UNWIND"=>(Policy:NativeCausalExitResearch.EquilibriumReversion,Minutes:60),
                    "JRC1_EURJPY_JPY_RISK_PARTICIPATION"=>(Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:60),
                    "JRC1_USDJPY_VOLATILITY_CLIMAX_UNWIND"=>(Policy:NativeCausalExitResearch.EquilibriumReversion,Minutes:60),
                    "OTC1_WTI_LOCAL_BASIS_REVERSION"=>(Policy:NativeCausalExitResearch.EquilibriumReversion,Minutes:60),
                    "OTC1_GBP_RELATIVE_STRENGTH_CONTINUATION"=>(Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:60),
                    "MCT2_ETH_CRYPTO_SPECIFIC_PERSISTENCE"=>(Policy:NativeCausalExitResearch.Chandelier,Minutes:60),
                    "MCT2_XAU_DOLLAR_CONFIRMED_RANGE_RELEASE"=>(Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:60),
                    "BMR1_EURUSD_RELEASE_PRICE_DISCOVERY"=>(Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:45),
                    "BMR1_XAUUSD_RELEASE_REPRICING"=>(Policy:NativeCausalExitResearch.PredictionInvalidation,Minutes:45),
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
            ModelExitReasons:new Dictionary<string,int>(exitReasonCounts,StringComparer.Ordinal),
            ModelMatchedShortBenchmarkEur:benchmarkSettlementComplete?
                matchedShortBenchmarkNetEur:null,
            ModelMatchedOppositeSignalBenchmarkEur:benchmarkSettlementComplete?
                matchedInverseBenchmarkNetEur:null);
    }
}
